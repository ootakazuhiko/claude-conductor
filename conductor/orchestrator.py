#!/usr/bin/env python3
"""
Claude Code Multi-Agent Orchestrator
"""

import os
import time
import json
import uuid
import threading
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, Future
import logging
from datetime import datetime

from .agent import ClaudeAgent, Task, TaskResult
from .protocol import UnixSocketChannel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Orchestrator:
    """マルチエージェントオーケストレーター"""
    
    def __init__(self, config_path: Optional[str] = None):
        # 設定読み込み
        self.config = self._load_config(config_path)
        
        # コンポーネント
        self.agents: Dict[str, ClaudeAgent] = {}
        self.executor = ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 10)
        )
        self.task_queue: List[Task] = []
        self.results: Dict[str, TaskResult] = {}
        
        # 統計情報
        self.stats = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_execution_time": 0.0,
            "start_time": None
        }
        
        # 通信用ソケット
        self.broker_socket_path = "/tmp/claude_orchestrator.sock"
        self.broker_channel: Optional[UnixSocketChannel] = None
        
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """設定ファイルを読み込む"""
        default_config = {
            "num_agents": 3,
            "max_workers": 10,
            "task_timeout": 300,
            "log_level": "INFO"
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                try:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        default_config.update(user_config)
                except yaml.YAMLError as e:
                    logger.warning(f"Failed to parse config file: {e}")
                
        return default_config
        
    def start(self):
        """オーケストレーターを起動"""
        logger.info(f"Starting orchestrator with {self.config['num_agents']} agents")
        self.stats["start_time"] = time.time()
        
        # ブローカーチャネル起動
        try:
            self.broker_channel = UnixSocketChannel(
                self.broker_socket_path,
                is_server=True
            )
        except Exception as e:
            logger.warning(f"Failed to start broker channel: {e}")
            self.broker_channel = None
        
        # エージェントの起動
        successful_agents = 0
        for i in range(self.config["num_agents"]):
            agent_id = f"agent_{i:03d}"
            agent = ClaudeAgent(agent_id, self.broker_socket_path)
            
            try:
                agent.start()
                self.agents[agent_id] = agent
                successful_agents += 1
                logger.info(f"Agent {agent_id} added to orchestrator")
                
            except Exception as e:
                logger.error(f"Failed to start agent {agent_id}: {e}")
                
        logger.info(f"Orchestrator started with {successful_agents}/{self.config['num_agents']} active agents")
        
        # 統計情報スレッド
        threading.Thread(target=self._stats_reporter, daemon=True).start()
        
    def stop(self):
        """オーケストレーターを停止"""
        logger.info("Stopping orchestrator")
        
        # 全エージェントを停止
        for agent_id, agent in self.agents.items():
            try:
                agent.stop()
                logger.info(f"Agent {agent_id} stopped")
            except Exception as e:
                logger.error(f"Error stopping agent {agent_id}: {e}")
                
        # ブローカーチャネルを閉じる
        if self.broker_channel:
            self.broker_channel.close()
            
        # Executorをシャットダウン
        self.executor.shutdown(wait=True)
        
        # 統計情報を出力
        self._print_final_stats()
        
        logger.info("Orchestrator stopped")
        
    def execute_task(self, task: Task) -> TaskResult:
        """単一タスクを実行"""
        # 優先度キューに追加（簡易実装）
        self.task_queue.append(task)
        self.task_queue.sort(key=lambda t: t.priority, reverse=True)
        
        # 利用可能なエージェントを選択
        agent = self._get_available_agent()
        if not agent:
            return TaskResult(
                task_id=task.task_id,
                agent_id="none",
                status="failed",
                result={},
                error="No available agents"
            )
            
        # タスクを実行
        future = self.executor.submit(agent.execute_task, task)
        
        try:
            result = future.result(timeout=task.timeout)
        except TimeoutError:
            result = TaskResult(
                task_id=task.task_id,
                agent_id=agent.agent_id,
                status="timeout",
                result={},
                error="Task execution timeout"
            )
        except Exception as e:
            result = TaskResult(
                task_id=task.task_id,
                agent_id=agent.agent_id,
                status="failed",
                result={},
                error=str(e)
            )
            
        self._update_stats(result)
        self.results[task.task_id] = result
        
        return result
        
    def execute_parallel_task(self, task: Task) -> List[TaskResult]:
        """並列タスクを実行"""
        if not task.subtasks:
            return [self.execute_task(task)]
            
        futures: List[tuple] = []
        results: List[TaskResult] = []
        
        # サブタスクを並列実行
        for i, subtask_def in enumerate(task.subtasks):
            subtask = Task(
                task_id=f"{task.task_id}_sub{i}",
                task_type=subtask_def.get("type", task.task_type),
                description=subtask_def.get("description", ""),
                files=subtask_def.get("files", []),
                priority=task.priority,
                timeout=subtask_def.get("timeout", task.timeout)
            )
            
            agent = self._get_available_agent()
            if agent:
                future = self.executor.submit(agent.execute_task, subtask)
                futures.append((future, agent.agent_id, subtask))
            else:
                # エージェントが利用できない場合のエラー結果
                error_result = TaskResult(
                    task_id=subtask.task_id,
                    agent_id="none",
                    status="failed",
                    result={},
                    error="No available agents"
                )
                results.append(error_result)
                
        # 結果を収集
        for future, agent_id, subtask in futures:
            try:
                result = future.result(timeout=subtask.timeout)
            except Exception as e:
                result = TaskResult(
                    task_id=subtask.task_id,
                    agent_id=agent_id,
                    status="failed",
                    result={},
                    error=str(e)
                )
                
            results.append(result)
            self._update_stats(result)
            self.results[result.task_id] = result
            
        return results
        
    def _get_available_agent(self) -> Optional[ClaudeAgent]:
        """利用可能なエージェントを取得"""
        # 現在タスクを実行していないエージェントを探す
        for agent in self.agents.values():
            if agent.is_running and agent.current_task is None:
                return agent
                
        # 全てビジーの場合は、最も負荷の低いエージェントを選択
        # （簡易実装：最初のエージェントを選択）
        if self.agents:
            return list(self.agents.values())[0]
            
        return None
        
    def _update_stats(self, result: TaskResult):
        """統計情報を更新"""
        if result.status == "success":
            self.stats["tasks_completed"] += 1
        else:
            self.stats["tasks_failed"] += 1
            
        self.stats["total_execution_time"] += result.execution_time
        
    def _stats_reporter(self):
        """定期的に統計情報を報告"""
        while self.agents:
            time.sleep(60)  # 1分ごと
            
            if not any(agent.is_running for agent in self.agents.values()):
                break
                
            logger.info(
                f"Stats - Completed: {self.stats['tasks_completed']}, "
                f"Failed: {self.stats['tasks_failed']}, "
                f"Avg time: {self._get_avg_execution_time():.2f}s"
            )
            
    def _get_avg_execution_time(self) -> float:
        """平均実行時間を取得"""
        total_tasks = self.stats["tasks_completed"] + self.stats["tasks_failed"]
        if total_tasks == 0:
            return 0.0
        return self.stats["total_execution_time"] / total_tasks
        
    def _print_final_stats(self):
        """最終統計情報を出力"""
        runtime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        
        print("\n=== Final Statistics ===")
        print(f"Runtime: {runtime:.2f}s")
        print(f"Total tasks completed: {self.stats['tasks_completed']}")
        print(f"Total tasks failed: {self.stats['tasks_failed']}")
        print(f"Average execution time: {self._get_avg_execution_time():.2f}s")
        print(f"Total execution time: {self.stats['total_execution_time']:.2f}s")
        print(f"Active agents: {len([a for a in self.agents.values() if a.is_running])}/{len(self.agents)}")
        
    def get_agent_status(self) -> Dict[str, Any]:
        """全エージェントのステータスを取得"""
        status = {}
        for agent_id, agent in self.agents.items():
            status[agent_id] = {
                "running": agent.is_running,
                "current_task": agent.current_task.task_id if agent.current_task else None,
                "health_check_failed": agent.health_check_failed,
                "container_name": agent.config.container_name
            }
        return status
        
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """タスク結果を取得"""
        return self.results.get(task_id)
        
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報を取得"""
        runtime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        return {
            "runtime": runtime,
            "tasks_completed": self.stats["tasks_completed"],
            "tasks_failed": self.stats["tasks_failed"],
            "avg_execution_time": self._get_avg_execution_time(),
            "total_execution_time": self.stats["total_execution_time"],
            "active_agents": len([a for a in self.agents.values() if a.is_running]),
            "total_agents": len(self.agents)
        }

def create_task(task_type: str = "generic", description: str = "", files: List[str] = None, **kwargs) -> Task:
    """タスクを簡単に作成するためのヘルパー関数"""
    if files is None:
        files = []
    
    return Task(
        task_type=task_type,
        description=description,
        files=files,
        **kwargs
    )

# CLIエントリーポイント
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Multi-Agent Orchestrator")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--agents", type=int, help="Number of agents", default=3)
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--demo", action="store_true", help="Run demo tasks")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # オーケストレーター作成
    orchestrator = Orchestrator(args.config)
    
    if args.agents:
        orchestrator.config["num_agents"] = args.agents
        
    try:
        # 起動
        orchestrator.start()
        
        if args.demo:
            # デモタスクを実行
            print("\n=== Running Demo Tasks ===")
            
            # タスク1: コードレビュー
            task1 = create_task(
                task_type="code_review",
                description="Review sample code",
                files=["examples/sample_code.py"]
            )
            result1 = orchestrator.execute_task(task1)
            print(f"Code review task: {result1.status}")
            
            # タスク2: 並列テスト生成
            task2 = create_task(
                task_type="test_generation",
                description="Generate tests for multiple files",
                parallel=True,
                subtasks=[
                    {"type": "test_generation", "description": "Generate tests for main", "files": ["main.py"]},
                    {"type": "test_generation", "description": "Generate tests for utils", "files": ["utils.py"]}
                ]
            )
            results2 = orchestrator.execute_parallel_task(task2)
            print(f"Parallel test generation: {len(results2)} tasks completed")
            
        else:
            # 簡単なREPL
            print("\nClaude Code Orchestrator started")
            print("Commands: status, stats, task <type> <description>, parallel <description>, quit")
            
            while True:
                try:
                    cmd = input("\n> ").strip()
                    
                    if cmd == "quit":
                        break
                    elif cmd == "status":
                        status = orchestrator.get_agent_status()
                        print(json.dumps(status, indent=2))
                    elif cmd == "stats":
                        stats = orchestrator.get_statistics()
                        print(json.dumps(stats, indent=2))
                    elif cmd.startswith("task"):
                        parts = cmd.split(maxsplit=2)
                        if len(parts) >= 3:
                            task_type = parts[1]
                            description = parts[2]
                            
                            task = create_task(
                                task_type=task_type,
                                description=description
                            )
                            
                            result = orchestrator.execute_task(task)
                            print(f"Task {result.task_id}: {result.status}")
                            if result.error:
                                print(f"Error: {result.error}")
                    elif cmd.startswith("parallel"):
                        parts = cmd.split(maxsplit=1)
                        if len(parts) >= 2:
                            description = parts[1]
                            
                            task = create_task(
                                task_type="generic",
                                description=description,
                                parallel=True,
                                subtasks=[
                                    {"type": "analysis", "description": f"Analyze part 1 of {description}"},
                                    {"type": "analysis", "description": f"Analyze part 2 of {description}"}
                                ]
                            )
                            
                            results = orchestrator.execute_parallel_task(task)
                            print(f"Parallel task completed: {len(results)} subtasks")
                    else:
                        print("Unknown command. Use: status, stats, task <type> <description>, parallel <description>, quit")
                        
                except KeyboardInterrupt:
                    break
                except EOFError:
                    break
                    
    finally:
        orchestrator.stop()


if __name__ == "__main__":
    main()