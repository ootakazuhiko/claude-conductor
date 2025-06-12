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
import subprocess
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, Future
import logging
from datetime import datetime

# 前述のモジュールをインポート
from .claude_code_wrapper import ClaudeCodeWrapper, AgentConfig
from .agent_communication import (
    AgentMessage, MessageType, UnixSocketChannel,
    Agent2AgentProtocol
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class Task:
    """タスク定義"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str = "generic"
    description: str = ""
    files: List[str] = field(default_factory=list)
    parallel: bool = False
    subtasks: Optional[List[Dict[str, Any]]] = None
    priority: int = 5  # 1-10, 10が最高
    timeout: float = 300.0  # 5分
    
@dataclass
class TaskResult:
    """タスク実行結果"""
    task_id: str
    agent_id: str
    status: str  # "success", "failed", "timeout", "partial"
    result: Dict[str, Any]
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: float = field(default_factory=time.time)

class ClaudeAgent:
    """Claude Codeエージェント"""
    
    def __init__(self, agent_id: str, orchestrator: 'Orchestrator'):
        self.agent_id = agent_id
        self.orchestrator = orchestrator
        
        # Podmanコンテナ設定
        self.config = AgentConfig(
            agent_id=agent_id,
            container_name=f"claude_agent_{agent_id}",
            work_dir=f"/tmp/claude_workspace_{agent_id}"
        )
        
        # コンポーネント
        self.wrapper: Optional[ClaudeCodeWrapper] = None
        self.protocol: Optional[Agent2AgentProtocol] = None
        self.channel: Optional[UnixSocketChannel] = None
        
        # 状態
        self.is_running = False
        self.current_task: Optional[Task] = None
        self.health_check_failed = 0
        
    def start(self):
        """エージェントを起動"""
        logger.info(f"Starting agent {self.agent_id}")
        
        try:
            # ワークスペース作成
            os.makedirs(self.config.work_dir, exist_ok=True)
            
            # Wrapperの初期化
            self.wrapper = ClaudeCodeWrapper(self.config)
            self.wrapper.setup_container()
            
            # 通信チャネルの初期化
            socket_path = f"/tmp/claude_agent_{self.agent_id}.sock"
            self.channel = UnixSocketChannel(socket_path, is_server=False)
            self.protocol = Agent2AgentProtocol(self.agent_id, self.channel)
            
            # メッセージハンドラー登録
            self.protocol.register_handler(
                MessageType.TASK_REQUEST,
                self._handle_task_request
            )
            
            # Claude Code起動
            self.wrapper.start_claude_code(headless=True)
            self.is_running = True
            
            # メッセージ処理スレッド
            threading.Thread(target=self._process_messages, daemon=True).start()
            
            # ヘルスチェックスレッド
            threading.Thread(target=self._health_check_loop, daemon=True).start()
            
            logger.info(f"Agent {self.agent_id} started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start agent {self.agent_id}: {e}")
            raise
            
    def stop(self):
        """エージェントを停止"""
        logger.info(f"Stopping agent {self.agent_id}")
        self.is_running = False
        
        if self.wrapper:
            self.wrapper.stop()
            self.wrapper.cleanup_container()
            
        if self.channel:
            self.channel.close()
            
    def execute_task(self, task: Task) -> TaskResult:
        """タスクを実行"""
        self.current_task = task
        start_time = time.time()
        
        try:
            logger.info(f"Agent {self.agent_id} executing task {task.task_id}")
            
            # タスクタイプに応じた処理
            if task.task_type == "code_review":
                result = self._execute_code_review(task)
            elif task.task_type == "refactor":
                result = self._execute_refactor(task)
            elif task.task_type == "test_generation":
                result = self._execute_test_generation(task)
            elif task.task_type == "analysis":
                result = self._execute_analysis(task)
            else:
                result = self._execute_generic_task(task)
                
            execution_time = time.time() - start_time
            
            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status="success",
                result=result,
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")
            return TaskResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                status="failed",
                result={},
                error=str(e),
                execution_time=time.time() - start_time
            )
        finally:
            self.current_task = None
            
    def _execute_code_review(self, task: Task) -> Dict[str, Any]:
        """コードレビュータスクの実行"""
        results = {}
        total_issues = 0
        
        for file_path in task.files:
            # ファイルをコンテナにコピー
            self._copy_file_to_container(file_path)
            
            # レビューコマンド送信
            command = f"review {os.path.basename(file_path)}"
            self.wrapper.send_command(command)
            
            # 結果を収集
            outputs = self.wrapper.read_output(timeout=10.0)
            
            # 結果をパース（実装に応じて調整）
            review_result = self._parse_review_output(outputs)
            results[file_path] = review_result
            total_issues += review_result.get("issue_count", 0)
            
        return {
            "files_reviewed": len(task.files),
            "total_issues": total_issues,
            "details": results
        }
        
    def _execute_refactor(self, task: Task) -> Dict[str, Any]:
        """リファクタリングタスクの実行"""
        # ファイルをコンテナにコピー
        for file_path in task.files:
            self._copy_file_to_container(file_path)
            
        # リファクタリングコマンド
        command = f"refactor {' '.join([os.path.basename(f) for f in task.files])}"
        if task.description:
            command += f" --description '{task.description}'"
            
        self.wrapper.send_command(command)
        
        # 結果を収集（タイムアウトを長めに）
        outputs = self.wrapper.read_output(timeout=30.0)
        
        return {
            "refactored": True,
            "files_affected": len(task.files),
            "output": self._format_output(outputs)
        }
        
    def _execute_test_generation(self, task: Task) -> Dict[str, Any]:
        """テスト生成タスクの実行"""
        results = {}
        total_tests = 0
        
        for file_path in task.files:
            self._copy_file_to_container(file_path)
            
            command = f"generate-tests {os.path.basename(file_path)}"
            self.wrapper.send_command(command)
            
            outputs = self.wrapper.read_output(timeout=20.0)
            test_result = self._parse_test_output(outputs)
            results[file_path] = test_result
            total_tests += test_result.get("test_count", 0)
            
        return {
            "files_processed": len(task.files),
            "total_tests_generated": total_tests,
            "details": results
        }
        
    def _execute_analysis(self, task: Task) -> Dict[str, Any]:
        """分析タスクの実行"""
        command = f"analyze {task.description}"
        self.wrapper.send_command(command)
        
        outputs = self.wrapper.read_output(timeout=task.timeout)
        
        return {
            "analysis_type": task.description,
            "result": self._format_output(outputs)
        }
        
    def _execute_generic_task(self, task: Task) -> Dict[str, Any]:
        """汎用タスクの実行"""
        command = task.description
        self.wrapper.send_command(command)
        
        outputs = self.wrapper.read_output(timeout=task.timeout)
        
        return {"output": self._format_output(outputs)}
        
    def _handle_task_request(self, message: AgentMessage):
        """他のエージェントからのタスクリクエストを処理"""
        logger.info(f"Agent {self.agent_id} received task request from {message.sender_id}")
        
        # タスクを作成
        task = Task(**message.payload)
        
        # タスクを実行
        result = self.execute_task(task)
        
        # レスポンスを送信
        self.protocol.send_task_response(message, asdict(result))
        
    def _copy_file_to_container(self, file_path: str):
        """ファイルをコンテナにコピー"""
        if os.path.exists(file_path):
            dest_path = os.path.join(self.config.work_dir, os.path.basename(file_path))
            subprocess.run([
                "cp", file_path, dest_path
            ])
            
    def _parse_review_output(self, outputs: List[tuple]) -> Dict[str, Any]:
        """レビュー出力をパース"""
        # TODO: 実際のClaude Code出力形式に合わせて実装
        text = "\n".join([line for _, line in outputs])
        try:
            return json.loads(text)
        except:
            return {"raw_output": text, "issue_count": 0}
            
    def _parse_test_output(self, outputs: List[tuple]) -> Dict[str, Any]:
        """テスト生成出力をパース"""
        # TODO: 実際のClaude Code出力形式に合わせて実装
        text = "\n".join([line for _, line in outputs])
        try:
            return json.loads(text)
        except:
            return {"raw_output": text, "test_count": 0}
            
    def _format_output(self, outputs: List[tuple]) -> str:
        """出力をフォーマット"""
        return "\n".join([f"[{stream}] {line}" for stream, line in outputs])
        
    def _process_messages(self):
        """メッセージを処理"""
        while self.is_running:
            try:
                self.protocol.process_messages()
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"Message processing error: {e}")
                
    def _health_check_loop(self):
        """定期的なヘルスチェック"""
        while self.is_running:
            time.sleep(30)  # 30秒ごと
            
            try:
                # 簡単なコマンドを送信してレスポンスを確認
                self.wrapper.send_command("echo health_check")
                outputs = self.wrapper.read_output(timeout=5.0)
                
                if outputs:
                    self.health_check_failed = 0
                else:
                    self.health_check_failed += 1
                    
                if self.health_check_failed > 3:
                    logger.error(f"Agent {self.agent_id} health check failed")
                    # TODO: 自動復旧処理
                    
            except Exception as e:
                logger.error(f"Health check error: {e}")
                self.health_check_failed += 1

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
            "total_execution_time": 0.0
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
                user_config = yaml.safe_load(f)
                default_config.update(user_config)
                
        return default_config
        
    def start(self):
        """オーケストレーターを起動"""
        logger.info(f"Starting orchestrator with {self.config['num_agents']} agents")
        
        # ブローカーチャネル起動
        self.broker_channel = UnixSocketChannel(
            self.broker_socket_path,
            is_server=True
        )
        
        # エージェントの起動
        for i in range(self.config["num_agents"]):
            agent_id = f"agent_{i:03d}"
            agent = ClaudeAgent(agent_id, self)
            
            try:
                agent.start()
                self.agents[agent_id] = agent
                logger.info(f"Agent {agent_id} added to orchestrator")
                
            except Exception as e:
                logger.error(f"Failed to start agent {agent_id}: {e}")
                
        logger.info(f"Orchestrator started with {len(self.agents)} active agents")
        
        # 統計情報スレッド
        threading.Thread(target=self._stats_reporter, daemon=True).start()
        
    def stop(self):
        """オーケストレーターを停止"""
        logger.info("Stopping orchestrator")
        
        # 全エージェントを停止
        for agent in self.agents.values():
            try:
                agent.stop()
            except Exception as e:
                logger.error(f"Error stopping agent: {e}")
                
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
            
        self._update_stats(result)
        self.results[task.task_id] = result
        
        return result
        
    def execute_parallel_task(self, task: Task) -> List[TaskResult]:
        """並列タスクを実行"""
        if not task.subtasks:
            return [self.execute_task(task)]
            
        futures: List[Future] = []
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
        # （簡易実装：ランダムに選択）
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
        while True:
            time.sleep(60)  # 1分ごと
            
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
        print("\n=== Final Statistics ===")
        print(f"Total tasks completed: {self.stats['tasks_completed']}")
        print(f"Total tasks failed: {self.stats['tasks_failed']}")
        print(f"Average execution time: {self._get_avg_execution_time():.2f}s")
        print(f"Total execution time: {self.stats['total_execution_time']:.2f}s")
        
    def get_agent_status(self) -> Dict[str, Any]:
        """全エージェントのステータスを取得"""
        status = {}
        for agent_id, agent in self.agents.items():
            status[agent_id] = {
                "running": agent.is_running,
                "current_task": agent.current_task.task_id if agent.current_task else None,
                "health_check_failed": agent.health_check_failed
            }
        return status
        
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """タスク結果を取得"""
        return self.results.get(task_id)


# CLIエントリーポイント
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Multi-Agent Orchestrator")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--agents", type=int, help="Number of agents")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        
    # 設定を準備
    config_path = args.config
    
    # オーケストレーター作成
    orchestrator = Orchestrator(config_path)
    
    if args.agents:
        orchestrator.config["num_agents"] = args.agents
        
    try:
        # 起動
        orchestrator.start()
        
        # 簡単なREPL
        print("\nClaude Code Orchestrator started")
        print("Commands: status, task <type> <description>, quit")
        
        while True:
            try:
                cmd = input("\n> ").strip()
                
                if cmd == "quit":
                    break
                elif cmd == "status":
                    status = orchestrator.get_agent_status()
                    print(json.dumps(status, indent=2))
                elif cmd.startswith("task"):
                    parts = cmd.split(maxsplit=2)
                    if len(parts) >= 3:
                        task_type = parts[1]
                        description = parts[2]
                        
                        task = Task(
                            task_type=task_type,
                            description=description
                        )
                        
                        result = orchestrator.execute_task(task)
                        print(f"Task {result.task_id}: {result.status}")
                        
            except KeyboardInterrupt:
                break
                
    finally:
        orchestrator.stop()


if __name__ == "__main__":
    main()