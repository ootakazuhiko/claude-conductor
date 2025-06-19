#!/usr/bin/env python3
"""
エージェント間の高度な協調パターンの実装
"""

import time
import uuid
import threading
import queue
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable, Set
from enum import Enum
import logging

from .agent import Task, TaskResult, ClaudeAgent
from .protocol import MessageType, AgentMessage

logger = logging.getLogger(__name__)

class AgentRole(Enum):
    """エージェントの役割"""
    LEAD = "lead"
    SUB = "sub"
    SPECIALIST = "specialist"
    REVIEWER = "reviewer"
    COORDINATOR = "coordinator"

class CoordinationStrategy(Enum):
    """協調戦略"""
    HIERARCHICAL = "hierarchical"      # リード・サブ階層
    PEER_TO_PEER = "peer_to_peer"      # ピア間協調
    CONSENSUS = "consensus"             # 合意形成
    PIPELINE = "pipeline"               # パイプライン処理
    BROADCAST = "broadcast"             # ブロードキャスト

@dataclass
class AgentCapability:
    """エージェントの能力定義"""
    agent_id: str
    role: AgentRole
    skills: Set[str] = field(default_factory=set)
    max_concurrent_tasks: int = 3
    specializations: List[str] = field(default_factory=list)
    performance_score: float = 1.0  # 0.0 - 1.0
    
@dataclass
class CoordinationTask:
    """協調タスク"""
    task_id: str
    strategy: CoordinationStrategy
    lead_agent_id: Optional[str] = None
    participating_agents: List[str] = field(default_factory=list)
    subtasks: List[Task] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    consensus_threshold: float = 0.7  # コンセンサス戦略用
    
@dataclass
class CoordinationResult:
    """協調結果"""
    task_id: str
    strategy: CoordinationStrategy
    lead_agent_id: Optional[str]
    agent_results: Dict[str, TaskResult]
    consensus_reached: Optional[bool] = None
    final_result: Optional[Dict[str, Any]] = None
    coordination_time: float = 0.0
    
class LeadAgent:
    """リードエージェント実装"""
    
    def __init__(
        self,
        agent_id: str,
        base_agent: ClaudeAgent,
        sub_agents: List[ClaudeAgent]
    ):
        self.agent_id = agent_id
        self.base_agent = base_agent
        self.sub_agents = sub_agents
        self.sub_agent_map = {agent.agent_id: agent for agent in sub_agents}
        
        # タスク管理
        self.active_tasks: Dict[str, CoordinationTask] = {}
        self.task_queue = queue.Queue()
        self.result_queue = queue.Queue()
        
        # 統計情報
        self.stats = {
            "tasks_coordinated": 0,
            "tasks_succeeded": 0,
            "tasks_failed": 0,
            "average_coordination_time": 0.0
        }
        
        # メッセージハンドラーを登録
        if base_agent.protocol:
            base_agent.protocol.register_handler(
                MessageType.COORDINATION,
                self._handle_coordination_message
            )
            
    def coordinate_task(
        self,
        task: Task,
        strategy: CoordinationStrategy = CoordinationStrategy.HIERARCHICAL
    ) -> CoordinationResult:
        """タスクを協調実行"""
        start_time = time.time()
        
        # 協調タスクを作成
        coord_task = CoordinationTask(
            task_id=task.task_id,
            strategy=strategy,
            lead_agent_id=self.agent_id
        )
        
        self.active_tasks[task.task_id] = coord_task
        
        try:
            # 戦略に基づいて実行
            if strategy == CoordinationStrategy.HIERARCHICAL:
                result = self._coordinate_hierarchical(task, coord_task)
            elif strategy == CoordinationStrategy.PEER_TO_PEER:
                result = self._coordinate_peer_to_peer(task, coord_task)
            elif strategy == CoordinationStrategy.CONSENSUS:
                result = self._coordinate_consensus(task, coord_task)
            elif strategy == CoordinationStrategy.PIPELINE:
                result = self._coordinate_pipeline(task, coord_task)
            elif strategy == CoordinationStrategy.BROADCAST:
                result = self._coordinate_broadcast(task, coord_task)
            else:
                raise ValueError(f"Unknown coordination strategy: {strategy}")
                
            # 統計を更新
            coordination_time = time.time() - start_time
            result.coordination_time = coordination_time
            self._update_stats(result)
            
            return result
            
        finally:
            # クリーンアップ
            if task.task_id in self.active_tasks:
                del self.active_tasks[task.task_id]
                
    def _coordinate_hierarchical(
        self,
        task: Task,
        coord_task: CoordinationTask
    ) -> CoordinationResult:
        """階層的協調"""
        logger.info(f"Lead agent {self.agent_id} coordinating task {task.task_id}")
        
        # タスクを分析
        subtasks = self._analyze_and_decompose(task)
        coord_task.subtasks = subtasks
        
        # サブエージェントに割り当て
        assignments = self._assign_to_sub_agents(subtasks)
        
        # タスクを配布
        futures = []
        for agent_id, assigned_tasks in assignments.items():
            agent = self.sub_agent_map[agent_id]
            coord_task.participating_agents.append(agent_id)
            
            for subtask in assigned_tasks:
                # サブタスクを送信
                if agent.protocol:
                    future = self._send_subtask_async(agent, subtask)
                    futures.append((agent_id, subtask.task_id, future))
                else:
                    # 直接実行
                    result = agent.execute_task(subtask)
                    self.result_queue.put((agent_id, result))
                    
        # 結果を収集
        agent_results = {}
        for agent_id, subtask_id, future in futures:
            try:
                result = future.get(timeout=300.0)
                agent_results[subtask_id] = result
            except Exception as e:
                logger.error(f"Subtask {subtask_id} failed on agent {agent_id}: {e}")
                agent_results[subtask_id] = TaskResult(
                    task_id=subtask_id,
                    agent_id=agent_id,
                    status="failed",
                    result={},
                    error=str(e)
                )
                
        # 結果を統合
        final_result = self._synthesize_results(agent_results)
        
        return CoordinationResult(
            task_id=task.task_id,
            strategy=CoordinationStrategy.HIERARCHICAL,
            lead_agent_id=self.agent_id,
            agent_results=agent_results,
            final_result=final_result
        )
        
    def _coordinate_peer_to_peer(
        self,
        task: Task,
        coord_task: CoordinationTask
    ) -> CoordinationResult:
        """ピア間協調"""
        # 全エージェントが対等に協力
        all_agents = [self.base_agent] + self.sub_agents
        
        # タスクを均等に分割
        chunk_size = len(task.files) // len(all_agents) if task.files else 1
        
        agent_results = {}
        for i, agent in enumerate(all_agents):
            # サブタスクを作成
            if task.files:
                start_idx = i * chunk_size
                end_idx = start_idx + chunk_size if i < len(all_agents) - 1 else len(task.files)
                files = task.files[start_idx:end_idx]
            else:
                files = []
                
            subtask = Task(
                task_id=f"{task.task_id}_peer_{i}",
                task_type=task.task_type,
                description=f"{task.description} (peer {i})",
                files=files,
                priority=task.priority,
                timeout=task.timeout
            )
            
            # 実行
            result = agent.execute_task(subtask)
            agent_results[subtask.task_id] = result
            coord_task.participating_agents.append(agent.agent_id)
            
        # ピア間で結果を共有（簡略化）
        final_result = self._peer_consensus(agent_results)
        
        return CoordinationResult(
            task_id=task.task_id,
            strategy=CoordinationStrategy.PEER_TO_PEER,
            lead_agent_id=None,  # ピア間なのでリードなし
            agent_results=agent_results,
            final_result=final_result
        )
        
    def _coordinate_consensus(
        self,
        task: Task,
        coord_task: CoordinationTask
    ) -> CoordinationResult:
        """コンセンサス協調"""
        # 複数のエージェントに同じタスクを実行させる
        agents = self.sub_agents[:3]  # 最大3エージェント
        
        agent_results = {}
        for agent in agents:
            result = agent.execute_task(task)
            agent_results[agent.agent_id] = result
            coord_task.participating_agents.append(agent.agent_id)
            
        # コンセンサスを評価
        consensus_reached, final_result = self._evaluate_consensus(
            agent_results,
            coord_task.consensus_threshold
        )
        
        return CoordinationResult(
            task_id=task.task_id,
            strategy=CoordinationStrategy.CONSENSUS,
            lead_agent_id=self.agent_id,
            agent_results=agent_results,
            consensus_reached=consensus_reached,
            final_result=final_result
        )
        
    def _coordinate_pipeline(
        self,
        task: Task,
        coord_task: CoordinationTask
    ) -> CoordinationResult:
        """パイプライン協調"""
        # ステージを定義
        pipeline_stages = [
            ("analysis", "analysis"),
            ("implementation", task.task_type),
            ("review", "code_review")
        ]
        
        agent_results = {}
        previous_result = None
        
        for i, (stage_name, stage_type) in enumerate(pipeline_stages):
            agent = self.sub_agents[i % len(self.sub_agents)]
            
            # ステージタスクを作成
            stage_task = Task(
                task_id=f"{task.task_id}_stage_{stage_name}",
                task_type=stage_type,
                description=f"{stage_name}: {task.description}",
                files=task.files,
                priority=task.priority,
                timeout=task.timeout / len(pipeline_stages)
            )
            
            # 前のステージの結果を含める
            if previous_result:
                stage_task.description += f"\nPrevious stage result: {previous_result}"
                
            # 実行
            result = agent.execute_task(stage_task)
            agent_results[stage_task.task_id] = result
            coord_task.participating_agents.append(agent.agent_id)
            
            # パイプラインを継続するかチェック
            if result.status != "success":
                break
                
            previous_result = result.result
            
        # 最終結果
        final_result = {
            "pipeline_complete": len(agent_results) == len(pipeline_stages),
            "stages_completed": len(agent_results),
            "final_output": previous_result
        }
        
        return CoordinationResult(
            task_id=task.task_id,
            strategy=CoordinationStrategy.PIPELINE,
            lead_agent_id=self.agent_id,
            agent_results=agent_results,
            final_result=final_result
        )
        
    def _coordinate_broadcast(
        self,
        task: Task,
        coord_task: CoordinationTask
    ) -> CoordinationResult:
        """ブロードキャスト協調"""
        # 全エージェントに同じタスクをブロードキャスト
        agent_results = {}
        
        for agent in self.sub_agents:
            # 各エージェントが独自の視点で実行
            specialized_task = Task(
                task_id=f"{task.task_id}_broadcast_{agent.agent_id}",
                task_type=task.task_type,
                description=f"{task.description} (perspective: {agent.agent_id})",
                files=task.files,
                priority=task.priority,
                timeout=task.timeout
            )
            
            result = agent.execute_task(specialized_task)
            agent_results[agent.agent_id] = result
            coord_task.participating_agents.append(agent.agent_id)
            
        # 全視点を統合
        final_result = self._merge_perspectives(agent_results)
        
        return CoordinationResult(
            task_id=task.task_id,
            strategy=CoordinationStrategy.BROADCAST,
            lead_agent_id=self.agent_id,
            agent_results=agent_results,
            final_result=final_result
        )
        
    def _analyze_and_decompose(self, task: Task) -> List[Task]:
        """タスクを分析して分解"""
        # 簡単な実装: ファイル数に基づいて分割
        subtasks = []
        
        if task.files and len(task.files) > 1:
            for i, file in enumerate(task.files):
                subtask = Task(
                    task_id=f"{task.task_id}_sub_{i}",
                    task_type=task.task_type,
                    description=f"{task.description} - {file}",
                    files=[file],
                    priority=task.priority,
                    timeout=task.timeout / len(task.files)
                )
                subtasks.append(subtask)
        else:
            # 単一タスクとして返す
            subtasks.append(task)
            
        return subtasks
        
    def _assign_to_sub_agents(
        self,
        subtasks: List[Task]
    ) -> Dict[str, List[Task]]:
        """サブタスクをエージェントに割り当て"""
        assignments = {}
        
        # ラウンドロビンで割り当て
        for i, subtask in enumerate(subtasks):
            agent = self.sub_agents[i % len(self.sub_agents)]
            agent_id = agent.agent_id
            
            if agent_id not in assignments:
                assignments[agent_id] = []
            assignments[agent_id].append(subtask)
            
        return assignments
        
    def _send_subtask_async(
        self,
        agent: ClaudeAgent,
        subtask: Task
    ) -> 'Future':
        """非同期でサブタスクを送信"""
        # 簡略化: 同期実行をFutureでラップ
        from concurrent.futures import Future
        future = Future()
        
        def execute():
            try:
                result = agent.execute_task(subtask)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
                
        thread = threading.Thread(target=execute)
        thread.start()
        
        return future
        
    def _synthesize_results(
        self,
        agent_results: Dict[str, TaskResult]
    ) -> Dict[str, Any]:
        """結果を統合"""
        synthesis = {
            "total_subtasks": len(agent_results),
            "successful": sum(1 for r in agent_results.values() if r.status == "success"),
            "failed": sum(1 for r in agent_results.values() if r.status == "failed"),
            "results": {}
        }
        
        # 各結果を統合
        for task_id, result in agent_results.items():
            synthesis["results"][task_id] = {
                "status": result.status,
                "agent": result.agent_id,
                "output": result.result
            }
            
        return synthesis
        
    def _peer_consensus(
        self,
        agent_results: Dict[str, TaskResult]
    ) -> Dict[str, Any]:
        """ピア間コンセンサス"""
        # 簡単な実装: 多数決
        status_votes = {}
        for result in agent_results.values():
            status = result.status
            status_votes[status] = status_votes.get(status, 0) + 1
            
        consensus_status = max(status_votes, key=status_votes.get)
        
        return {
            "consensus_status": consensus_status,
            "votes": status_votes,
            "peer_count": len(agent_results)
        }
        
    def _evaluate_consensus(
        self,
        agent_results: Dict[str, TaskResult],
        threshold: float
    ) -> Tuple[bool, Dict[str, Any]]:
        """コンセンサスを評価"""
        # 成功率を計算
        success_count = sum(1 for r in agent_results.values() if r.status == "success")
        success_rate = success_count / len(agent_results)
        
        consensus_reached = success_rate >= threshold
        
        final_result = {
            "consensus_reached": consensus_reached,
            "success_rate": success_rate,
            "threshold": threshold,
            "agent_count": len(agent_results)
        }
        
        return consensus_reached, final_result
        
    def _merge_perspectives(
        self,
        agent_results: Dict[str, TaskResult]
    ) -> Dict[str, Any]:
        """複数の視点を統合"""
        perspectives = {}
        
        for agent_id, result in agent_results.items():
            if result.status == "success":
                perspectives[agent_id] = result.result
                
        return {
            "perspectives_collected": len(perspectives),
            "total_agents": len(agent_results),
            "merged_data": perspectives
        }
        
    def _handle_coordination_message(self, message: AgentMessage):
        """協調メッセージを処理"""
        logger.info(
            f"Lead agent {self.agent_id} received coordination message "
            f"from {message.sender_id}"
        )
        
        # メッセージタイプに応じて処理
        if message.payload.get("type") == "subtask_complete":
            # サブタスク完了通知
            self.result_queue.put((
                message.sender_id,
                message.payload.get("result")
            ))
            
    def _update_stats(self, result: CoordinationResult):
        """統計を更新"""
        self.stats["tasks_coordinated"] += 1
        
        # 成功/失敗をカウント
        if all(r.status == "success" for r in result.agent_results.values()):
            self.stats["tasks_succeeded"] += 1
        else:
            self.stats["tasks_failed"] += 1
            
        # 平均協調時間を更新
        total_time = (
            self.stats["average_coordination_time"] * 
            (self.stats["tasks_coordinated"] - 1) +
            result.coordination_time
        )
        self.stats["average_coordination_time"] = (
            total_time / self.stats["tasks_coordinated"]
        )


class SubAgent:
    """サブエージェント実装"""
    
    def __init__(
        self,
        agent_id: str,
        base_agent: ClaudeAgent,
        lead_agent_id: str
    ):
        self.agent_id = agent_id
        self.base_agent = base_agent
        self.lead_agent_id = lead_agent_id
        
        # 能力を定義
        self.capability = AgentCapability(
            agent_id=agent_id,
            role=AgentRole.SUB,
            skills=set(["execution", "reporting"]),
            max_concurrent_tasks=2
        )
        
        # メッセージハンドラーを登録
        if base_agent.protocol:
            base_agent.protocol.register_handler(
                MessageType.TASK_REQUEST,
                self._handle_task_from_lead
            )
            
    def _handle_task_from_lead(self, message: AgentMessage):
        """リードエージェントからのタスクを処理"""
        if message.sender_id != self.lead_agent_id:
            logger.warning(
                f"Sub agent {self.agent_id} received task from "
                f"non-lead agent {message.sender_id}"
            )
            return
            
        # タスクを実行
        task_data = message.payload
        task = Task(**task_data)
        
        result = self.base_agent.execute_task(task)
        
        # 結果をリードに報告
        if self.base_agent.protocol:
            self.base_agent.protocol.send_task_response(
                message,
                asdict(result)
            )
            
    def report_to_lead(self, data: Dict[str, Any]):
        """リードエージェントに報告"""
        if not self.base_agent.protocol:
            return
            
        message = AgentMessage(
            message_id=f"{self.agent_id}_{int(time.time()*1000)}",
            sender_id=self.agent_id,
            receiver_id=self.lead_agent_id,
            message_type=MessageType.COORDINATION,
            payload=data,
            timestamp=time.time()
        )
        
        self.base_agent.protocol.channel.send(message)


class CoordinationManager:
    """協調マネージャー"""
    
    def __init__(self):
        self.agent_registry: Dict[str, AgentCapability] = {}
        self.lead_agents: Dict[str, LeadAgent] = {}
        self.sub_agents: Dict[str, SubAgent] = {}
        self.coordination_history: List[CoordinationResult] = []
        
    def register_agent(
        self,
        agent: ClaudeAgent,
        capability: AgentCapability
    ):
        """エージェントを登録"""
        self.agent_registry[agent.agent_id] = capability
        logger.info(
            f"Registered agent {agent.agent_id} with role {capability.role.value}"
        )
        
    def create_hierarchical_team(
        self,
        lead_agent: ClaudeAgent,
        sub_agents: List[ClaudeAgent]
    ) -> LeadAgent:
        """階層的チームを作成"""
        # リードエージェントを作成
        lead = LeadAgent(
            agent_id=lead_agent.agent_id,
            base_agent=lead_agent,
            sub_agents=sub_agents
        )
        
        self.lead_agents[lead_agent.agent_id] = lead
        
        # サブエージェントを作成
        for agent in sub_agents:
            sub = SubAgent(
                agent_id=agent.agent_id,
                base_agent=agent,
                lead_agent_id=lead_agent.agent_id
            )
            self.sub_agents[agent.agent_id] = sub
            
        logger.info(
            f"Created hierarchical team with lead {lead_agent.agent_id} "
            f"and {len(sub_agents)} sub agents"
        )
        
        return lead
        
    def get_suitable_agents(
        self,
        required_skills: Set[str],
        count: int = 3
    ) -> List[str]:
        """要求スキルに適したエージェントを取得"""
        suitable = []
        
        for agent_id, capability in self.agent_registry.items():
            if required_skills.issubset(capability.skills):
                suitable.append((agent_id, capability.performance_score))
                
        # パフォーマンススコアでソート
        suitable.sort(key=lambda x: x[1], reverse=True)
        
        return [agent_id for agent_id, _ in suitable[:count]]
        
    def record_coordination_result(self, result: CoordinationResult):
        """協調結果を記録"""
        self.coordination_history.append(result)
        
        # 統計を更新
        for agent_id in result.agent_results:
            if agent_id in self.agent_registry:
                # パフォーマンススコアを更新（簡略化）
                if result.agent_results[agent_id].status == "success":
                    self.agent_registry[agent_id].performance_score *= 1.01
                else:
                    self.agent_registry[agent_id].performance_score *= 0.99
                    
                # スコアを0.1〜1.0の範囲に制限
                score = self.agent_registry[agent_id].performance_score
                self.agent_registry[agent_id].performance_score = max(0.1, min(1.0, score))