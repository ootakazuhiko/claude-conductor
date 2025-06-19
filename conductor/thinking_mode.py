#!/usr/bin/env python3
"""
Extended Thinking Mode - エージェントの思考プロセスを可視化
"""

import time
import json
import threading
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ThoughtType(Enum):
    """思考タイプの定義"""
    ANALYSIS = "analysis"
    DECISION = "decision"
    CONSIDERATION = "consideration"
    REJECTION = "rejection"
    PLANNING = "planning"
    EVALUATION = "evaluation"
    ERROR_ANALYSIS = "error_analysis"

@dataclass
class Thought:
    """個別の思考単位"""
    thought_id: str
    thought_type: ThoughtType
    content: str
    reasoning: str
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0  # 0.0 - 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['thought_type'] = self.thought_type.value
        return data

@dataclass
class ThinkingContext:
    """思考プロセスのコンテキスト"""
    task_id: str
    agent_id: str
    start_time: float = field(default_factory=time.time)
    thoughts: List[Thought] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)
    rejected_options: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_thought(self, thought: Thought):
        """思考を追加"""
        self.thoughts.append(thought)
        
    def get_summary(self) -> Dict[str, Any]:
        """思考プロセスのサマリーを取得"""
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "duration": time.time() - self.start_time,
            "total_thoughts": len(self.thoughts),
            "thought_breakdown": self._get_thought_breakdown(),
            "decisions_made": len(self.decisions),
            "options_rejected": len(self.rejected_options)
        }
        
    def _get_thought_breakdown(self) -> Dict[str, int]:
        """思考タイプ別の内訳"""
        breakdown = {}
        for thought in self.thoughts:
            thought_type = thought.thought_type.value
            breakdown[thought_type] = breakdown.get(thought_type, 0) + 1
        return breakdown

class ThinkingModeManager:
    """Extended Thinking Mode マネージャー"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.contexts: Dict[str, ThinkingContext] = {}
        self.stream_handlers: List[Callable] = []
        self.is_enabled = True
        self._lock = threading.Lock()
        
    def enable(self):
        """Thinking Modeを有効化"""
        self.is_enabled = True
        logger.info(f"Extended Thinking Mode enabled for agent {self.agent_id}")
        
    def disable(self):
        """Thinking Modeを無効化"""
        self.is_enabled = False
        logger.info(f"Extended Thinking Mode disabled for agent {self.agent_id}")
        
    def start_thinking(self, task_id: str) -> ThinkingContext:
        """新しい思考コンテキストを開始"""
        if not self.is_enabled:
            return None
            
        with self._lock:
            context = ThinkingContext(task_id=task_id, agent_id=self.agent_id)
            self.contexts[task_id] = context
            
            # 初期思考を記録
            self.think(
                task_id,
                ThoughtType.ANALYSIS,
                f"Starting analysis of task {task_id}",
                "Initializing thinking process for new task"
            )
            
            return context
            
    def think(
        self,
        task_id: str,
        thought_type: ThoughtType,
        content: str,
        reasoning: str,
        confidence: float = 1.0,
        metadata: Dict[str, Any] = None
    ):
        """思考を記録"""
        if not self.is_enabled or task_id not in self.contexts:
            return
            
        thought = Thought(
            thought_id=f"{task_id}_{int(time.time() * 1000)}",
            thought_type=thought_type,
            content=content,
            reasoning=reasoning,
            confidence=confidence,
            metadata=metadata or {}
        )
        
        with self._lock:
            self.contexts[task_id].add_thought(thought)
            
        # ストリーミング通知
        self._notify_stream(thought)
        
        logger.debug(f"[{thought_type.value}] {content}")
        
    def make_decision(
        self,
        task_id: str,
        decision: str,
        reasoning: str,
        alternatives: List[str] = None
    ):
        """決定を記録"""
        if not self.is_enabled or task_id not in self.contexts:
            return
            
        # 決定の思考を記録
        self.think(
            task_id,
            ThoughtType.DECISION,
            f"Decision made: {decision}",
            reasoning
        )
        
        # 決定を保存
        with self._lock:
            self.contexts[task_id].decisions.append({
                "decision": decision,
                "reasoning": reasoning,
                "alternatives": alternatives or [],
                "timestamp": time.time()
            })
            
    def reject_option(
        self,
        task_id: str,
        option: str,
        reason: str
    ):
        """却下されたオプションを記録"""
        if not self.is_enabled or task_id not in self.contexts:
            return
            
        # 却下の思考を記録
        self.think(
            task_id,
            ThoughtType.REJECTION,
            f"Rejected option: {option}",
            f"Reason for rejection: {reason}",
            confidence=0.9
        )
        
        # 却下されたオプションを保存
        with self._lock:
            self.contexts[task_id].rejected_options.append({
                "option": option,
                "reason": reason,
                "timestamp": time.time()
            })
            
    def analyze_error(
        self,
        task_id: str,
        error: str,
        analysis: str,
        recovery_plan: Optional[str] = None
    ):
        """エラー分析を記録"""
        if not self.is_enabled or task_id not in self.contexts:
            return
            
        metadata = {
            "error": error,
            "recovery_plan": recovery_plan
        }
        
        self.think(
            task_id,
            ThoughtType.ERROR_ANALYSIS,
            f"Error encountered: {error}",
            f"Analysis: {analysis}",
            confidence=0.8,
            metadata=metadata
        )
        
    def complete_thinking(self, task_id: str) -> Optional[ThinkingContext]:
        """思考プロセスを完了"""
        if task_id not in self.contexts:
            return None
            
        with self._lock:
            context = self.contexts.get(task_id)
            if context:
                # 最終的な評価思考を追加
                self.think(
                    task_id,
                    ThoughtType.EVALUATION,
                    "Completing thinking process",
                    f"Total thoughts: {len(context.thoughts)}, Decisions: {len(context.decisions)}"
                )
                
            return context
            
    def get_thinking_history(self, task_id: str) -> Optional[List[Dict[str, Any]]]:
        """思考履歴を取得"""
        context = self.contexts.get(task_id)
        if not context:
            return None
            
        return [thought.to_dict() for thought in context.thoughts]
        
    def register_stream_handler(self, handler: Callable[[Thought], None]):
        """ストリーミングハンドラーを登録"""
        self.stream_handlers.append(handler)
        
    def _notify_stream(self, thought: Thought):
        """ストリーミングハンドラーに通知"""
        for handler in self.stream_handlers:
            try:
                handler(thought)
            except Exception as e:
                logger.error(f"Stream handler error: {e}")
                
    def export_thinking_log(self, task_id: str, format: str = "json") -> Optional[str]:
        """思考ログをエクスポート"""
        context = self.contexts.get(task_id)
        if not context:
            return None
            
        if format == "json":
            data = {
                "task_id": context.task_id,
                "agent_id": context.agent_id,
                "start_time": context.start_time,
                "duration": time.time() - context.start_time,
                "thoughts": [t.to_dict() for t in context.thoughts],
                "decisions": context.decisions,
                "rejected_options": context.rejected_options,
                "summary": context.get_summary()
            }
            return json.dumps(data, indent=2)
            
        elif format == "markdown":
            md = f"# Thinking Process Log\n\n"
            md += f"**Task ID**: {context.task_id}\n"
            md += f"**Agent ID**: {context.agent_id}\n"
            md += f"**Duration**: {time.time() - context.start_time:.2f}s\n\n"
            
            md += "## Thoughts\n\n"
            for thought in context.thoughts:
                md += f"### [{thought.thought_type.value}] {thought.content}\n"
                md += f"**Reasoning**: {thought.reasoning}\n"
                md += f"**Confidence**: {thought.confidence}\n"
                md += f"**Time**: {thought.timestamp}\n\n"
                
            md += "## Decisions\n\n"
            for decision in context.decisions:
                md += f"- **{decision['decision']}**: {decision['reasoning']}\n"
                
            md += "## Rejected Options\n\n"
            for option in context.rejected_options:
                md += f"- **{option['option']}**: {option['reason']}\n"
                
            return md
            
        return None


class ThinkingModeWebSocketHandler:
    """WebSocketを通じた思考プロセスのリアルタイム配信"""
    
    def __init__(self, thinking_manager: ThinkingModeManager):
        self.thinking_manager = thinking_manager
        self.clients: List[Any] = []  # WebSocketクライアント
        
        # ストリーミングハンドラーとして登録
        thinking_manager.register_stream_handler(self._on_thought)
        
    def add_client(self, client):
        """WebSocketクライアントを追加"""
        self.clients.append(client)
        
    def remove_client(self, client):
        """WebSocketクライアントを削除"""
        if client in self.clients:
            self.clients.remove(client)
            
    def _on_thought(self, thought: Thought):
        """新しい思考をクライアントに配信"""
        message = {
            "type": "thought",
            "data": thought.to_dict()
        }
        
        # 全クライアントに配信
        for client in self.clients[:]:  # コピーを作成して反復
            try:
                client.send(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send to client: {e}")
                self.remove_client(client)