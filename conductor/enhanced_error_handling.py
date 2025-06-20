#!/usr/bin/env python3
"""
強化されたエラーハンドリングとリトライメカニズム
"""

import asyncio
import functools
import logging
import time
import json
import sqlite3
from typing import Any, Callable, Optional, Dict, Type, List, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
import threading
from collections import defaultdict, deque
import uuid

from .error_handler import ErrorHandler, RetryConfig, CircuitBreaker
from .exceptions import (
    ConductorError, AgentError, ContainerError, TaskExecutionError,
    CommunicationError, ResourceError, ServiceUnavailableError,
    ErrorContext, create_error_context
)

logger = logging.getLogger(__name__)

class ErrorSeverity(Enum):
    """エラー重要度レベル"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

class RecoveryStrategy(Enum):
    """復旧戦略"""
    IMMEDIATE_RETRY = "immediate_retry"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    CIRCUIT_BREAKER = "circuit_breaker"
    FALLBACK = "fallback"
    ESCALATION = "escalation"
    MANUAL_INTERVENTION = "manual_intervention"

@dataclass
class ErrorPattern:
    """エラーパターン定義"""
    pattern_id: str
    error_types: List[Type[Exception]]
    conditions: Dict[str, Any]
    severity: ErrorSeverity
    recovery_strategy: RecoveryStrategy
    max_retries: int = 3
    escalation_threshold: int = 5
    cooldown_period: float = 300.0  # 5 minutes
    
@dataclass
class ErrorStatistics:
    """エラー統計情報"""
    error_type: str
    total_count: int = 0
    recent_count: int = 0  # 直近1時間
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    resolution_rate: float = 0.0
    average_resolution_time: float = 0.0
    impact_score: float = 0.0
    
@dataclass
class ErrorIncident:
    """エラーインシデント"""
    incident_id: str
    error_type: str
    severity: ErrorSeverity
    affected_components: List[str]
    start_time: float
    end_time: Optional[float] = None
    recovery_actions: List[str] = field(default_factory=list)
    resolution_summary: Optional[str] = None
    lessons_learned: List[str] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """インシデント継続時間"""
        end = self.end_time or time.time()
        return end - self.start_time
    
    @property
    def is_resolved(self) -> bool:
        """解決済みかどうか"""
        return self.end_time is not None

@dataclass
class ErrorRecoveryPlan:
    """エラー復旧計画"""
    plan_id: str
    error_pattern: str
    steps: List[Dict[str, Any]]
    success_criteria: List[str]
    fallback_plan: Optional[str] = None
    estimated_time: float = 0.0

class AdaptiveRetryConfig:
    """適応的リトライ設定"""
    
    def __init__(self):
        self.success_rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.response_times: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        self.error_patterns: Dict[str, int] = defaultdict(int)
        
    def calculate_optimal_retry_params(self, operation: str, error_type: str) -> RetryConfig:
        """操作とエラータイプに基づいて最適なリトライパラメータを計算"""
        success_rate = self._get_success_rate(operation)
        avg_response_time = self._get_avg_response_time(operation)
        error_frequency = self.error_patterns.get(f"{operation}:{error_type}", 0)
        
        # 成功率に基づく調整
        if success_rate > 0.9:
            max_attempts = 2
            backoff_factor = 1.5
        elif success_rate > 0.7:
            max_attempts = 3
            backoff_factor = 2.0
        elif success_rate > 0.5:
            max_attempts = 5
            backoff_factor = 2.5
        else:
            max_attempts = 3
            backoff_factor = 3.0
        
        # レスポンス時間に基づく調整
        initial_delay = min(max(avg_response_time * 0.1, 0.1), 5.0)
        max_delay = min(avg_response_time * 10, 300.0)
        
        # エラー頻度に基づく調整
        if error_frequency > 10:
            backoff_factor *= 1.5
            max_delay *= 2
        
        return RetryConfig(
            max_attempts=max_attempts,
            backoff_factor=backoff_factor,
            initial_delay=initial_delay,
            max_delay=max_delay
        )
    
    def record_operation_result(self, operation: str, success: bool, response_time: float):
        """操作結果を記録"""
        self.success_rates[operation].append(1.0 if success else 0.0)
        self.response_times[operation].append(response_time)
    
    def record_error(self, operation: str, error_type: str):
        """エラーを記録"""
        key = f"{operation}:{error_type}"
        self.error_patterns[key] += 1
    
    def _get_success_rate(self, operation: str) -> float:
        """成功率を取得"""
        rates = self.success_rates[operation]
        return sum(rates) / len(rates) if rates else 0.5
    
    def _get_avg_response_time(self, operation: str) -> float:
        """平均レスポンス時間を取得"""
        times = self.response_times[operation]
        return sum(times) / len(times) if times else 1.0

class AdvancedCircuitBreaker(CircuitBreaker):
    """高度なサーキットブレーカー"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
        health_check_interval: float = 10.0
    ):
        super().__init__(failure_threshold, timeout, expected_exception)
        self.success_threshold = success_threshold
        self.success_count = 0
        self.health_check_interval = health_check_interval
        self.last_health_check = 0
        self.health_check_func: Optional[Callable] = None
        
    def set_health_check(self, health_check_func: Callable[[], bool]):
        """ヘルスチェック関数を設定"""
        self.health_check_func = health_check_func
    
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # ヘルスチェック実行
            if self._should_run_health_check():
                self._run_health_check()
            
            if self.state == "open":
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = "half-open"
                    self.success_count = 0
                else:
                    raise ServiceUnavailableError(
                        f"Circuit breaker is open for {func.__name__}",
                        context={
                            "state": self.state, 
                            "failure_count": self.failure_count,
                            "time_until_retry": self.timeout - (time.time() - self.last_failure_time)
                        }
                    )
            
            try:
                result = func(*args, **kwargs)
                
                if self.state == "half-open":
                    self.success_count += 1
                    if self.success_count >= self.success_threshold:
                        self._reset()
                
                return result
                
            except self.expected_exception as e:
                if self.state == "half-open":
                    self.state = "open"
                    self.last_failure_time = time.time()
                else:
                    self._record_failure()
                raise
                
        return wrapper
    
    def _should_run_health_check(self) -> bool:
        """ヘルスチェックを実行すべきかどうか"""
        return (
            self.health_check_func is not None and
            time.time() - self.last_health_check > self.health_check_interval
        )
    
    def _run_health_check(self):
        """ヘルスチェックを実行"""
        self.last_health_check = time.time()
        if self.state == "open" and self.health_check_func():
            logger.info("Health check passed, attempting to close circuit breaker")
            self.state = "half-open"
            self.success_count = 0

class ErrorAnalyzer:
    """エラー分析エンジン"""
    
    def __init__(self, db_path: str = "/tmp/error_analysis.db"):
        self.db_path = db_path
        self.error_patterns: List[ErrorPattern] = []
        self.statistics: Dict[str, ErrorStatistics] = {}
        self.incidents: Dict[str, ErrorIncident] = {}
        self._init_db()
        self._load_default_patterns()
    
    def _init_db(self):
        """データベースを初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                component TEXT NOT NULL,
                operation TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT,
                context TEXT,
                severity TEXT,
                resolved BOOLEAN DEFAULT FALSE,
                resolution_time REAL,
                correlation_id TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS error_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern_id TEXT UNIQUE NOT NULL,
                pattern_data TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON error_events(timestamp)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_error_type ON error_events(error_type)
        """)
        
        conn.commit()
        conn.close()
    
    def _load_default_patterns(self):
        """デフォルトエラーパターンを読み込み"""
        patterns = [
            ErrorPattern(
                pattern_id="container_failure",
                error_types=[ContainerError],
                conditions={"consecutive_failures": 3},
                severity=ErrorSeverity.HIGH,
                recovery_strategy=RecoveryStrategy.EXPONENTIAL_BACKOFF,
                max_retries=5,
                escalation_threshold=10
            ),
            ErrorPattern(
                pattern_id="communication_timeout",
                error_types=[CommunicationError, TimeoutError],
                conditions={"timeout_threshold": 30.0},
                severity=ErrorSeverity.MEDIUM,
                recovery_strategy=RecoveryStrategy.IMMEDIATE_RETRY,
                max_retries=3,
                escalation_threshold=5
            ),
            ErrorPattern(
                pattern_id="resource_exhaustion",
                error_types=[ResourceError],
                conditions={"memory_usage": 0.9},
                severity=ErrorSeverity.CRITICAL,
                recovery_strategy=RecoveryStrategy.ESCALATION,
                max_retries=1,
                escalation_threshold=2
            ),
            ErrorPattern(
                pattern_id="agent_startup_failure",
                error_types=[AgentError],
                conditions={"startup_phase": True},
                severity=ErrorSeverity.HIGH,
                recovery_strategy=RecoveryStrategy.CIRCUIT_BREAKER,
                max_retries=3,
                escalation_threshold=5
            )
        ]
        
        self.error_patterns.extend(patterns)
    
    def analyze_error(
        self, 
        error: Exception, 
        context: ErrorContext
    ) -> Optional[ErrorPattern]:
        """エラーを分析してパターンを特定"""
        for pattern in self.error_patterns:
            if self._matches_pattern(error, context, pattern):
                return pattern
        return None
    
    def _matches_pattern(
        self, 
        error: Exception, 
        context: ErrorContext, 
        pattern: ErrorPattern
    ) -> bool:
        """エラーがパターンにマッチするかチェック"""
        # エラータイプチェック
        if not any(isinstance(error, error_type) for error_type in pattern.error_types):
            return False
        
        # 条件チェック
        for condition_key, condition_value in pattern.conditions.items():
            context_value = context.details.get(condition_key)
            if context_value is None:
                continue
                
            if isinstance(condition_value, (int, float)):
                if context_value < condition_value:
                    return False
            elif isinstance(condition_value, bool):
                if bool(context_value) != condition_value:
                    return False
            elif isinstance(condition_value, str):
                if str(context_value) != condition_value:
                    return False
        
        return True
    
    def record_error_event(
        self, 
        component: str,
        operation: str,
        error: Exception,
        context: ErrorContext,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ):
        """エラーイベントを記録"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO error_events (
                timestamp, component, operation, error_type, error_message,
                context, severity, correlation_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            time.time(),
            component,
            operation,
            type(error).__name__,
            str(error),
            json.dumps(context.details),
            severity.value,
            context.correlation_id
        ))
        
        conn.commit()
        conn.close()
        
        # 統計情報を更新
        self._update_statistics(type(error).__name__)
    
    def _update_statistics(self, error_type: str):
        """エラー統計を更新"""
        if error_type not in self.statistics:
            self.statistics[error_type] = ErrorStatistics(error_type=error_type)
        
        stats = self.statistics[error_type]
        stats.total_count += 1
        stats.last_seen = time.time()
        
        # 直近1時間のカウントを更新
        current_time = time.time()
        one_hour_ago = current_time - 3600
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM error_events 
            WHERE error_type = ? AND timestamp > ?
        """, (error_type, one_hour_ago))
        
        stats.recent_count = cursor.fetchone()[0]
        conn.close()
    
    def get_error_trends(self, time_window: int = 3600) -> Dict[str, Any]:
        """エラートレンドを取得"""
        current_time = time.time()
        window_start = current_time - time_window
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 時間別エラー数
        cursor.execute("""
            SELECT 
                error_type,
                COUNT(*) as count,
                AVG(CASE WHEN resolved THEN resolution_time ELSE NULL END) as avg_resolution_time
            FROM error_events 
            WHERE timestamp > ?
            GROUP BY error_type
            ORDER BY count DESC
        """, (window_start,))
        
        trends = {}
        for row in cursor.fetchall():
            error_type, count, avg_resolution_time = row
            trends[error_type] = {
                "count": count,
                "avg_resolution_time": avg_resolution_time or 0,
                "frequency": count / (time_window / 3600)  # per hour
            }
        
        conn.close()
        return trends
    
    def suggest_recovery_actions(self, error_pattern: ErrorPattern) -> List[str]:
        """復旧アクションを提案"""
        actions = []
        
        if error_pattern.recovery_strategy == RecoveryStrategy.IMMEDIATE_RETRY:
            actions.append("Immediate retry with current parameters")
            actions.append("Check for transient network issues")
        
        elif error_pattern.recovery_strategy == RecoveryStrategy.EXPONENTIAL_BACKOFF:
            actions.append("Implement exponential backoff retry")
            actions.append("Increase timeout values gradually")
            actions.append("Monitor resource availability")
        
        elif error_pattern.recovery_strategy == RecoveryStrategy.CIRCUIT_BREAKER:
            actions.append("Activate circuit breaker")
            actions.append("Route traffic to backup systems")
            actions.append("Perform health check before retry")
        
        elif error_pattern.recovery_strategy == RecoveryStrategy.FALLBACK:
            actions.append("Switch to fallback mechanism")
            actions.append("Use cached or default responses")
            actions.append("Notify administrators")
        
        elif error_pattern.recovery_strategy == RecoveryStrategy.ESCALATION:
            actions.append("Escalate to operations team")
            actions.append("Trigger automated scaling")
            actions.append("Activate disaster recovery procedures")
        
        elif error_pattern.recovery_strategy == RecoveryStrategy.MANUAL_INTERVENTION:
            actions.append("Manual intervention required")
            actions.append("Contact system administrator")
            actions.append("Check system configuration")
        
        return actions

class EnhancedErrorHandler(ErrorHandler):
    """強化されたエラーハンドラー"""
    
    def __init__(self, component_name: str):
        super().__init__(component_name)
        self.analyzer = ErrorAnalyzer()
        self.adaptive_retry = AdaptiveRetryConfig()
        self.active_incidents: Dict[str, ErrorIncident] = {}
        
    def handle_error_with_analysis(
        self,
        operation: str,
        error: Exception,
        context: Dict[str, Any] = None,
        correlation_id: str = None,
        reraise: bool = True
    ) -> tuple[ErrorContext, Optional[ErrorPattern]]:
        """エラーを分析付きで処理"""
        # 基本的なエラー処理
        error_context = self.handle_error(
            operation, error, context, correlation_id, reraise=False
        )
        
        # エラーパターン分析
        error_pattern = self.analyzer.analyze_error(error, error_context)
        
        if error_pattern:
            logger.info(f"Identified error pattern: {error_pattern.pattern_id}")
            
            # 復旧アクションの提案
            recovery_actions = self.analyzer.suggest_recovery_actions(error_pattern)
            logger.info(f"Suggested recovery actions: {recovery_actions}")
            
            # インシデント管理
            self._handle_incident(error_pattern, error_context, recovery_actions)
        
        # エラーイベントを記録
        severity = self._determine_severity(error, error_pattern)
        self.analyzer.record_error_event(
            self.component_name, operation, error, error_context, severity
        )
        
        # 適応的リトライの設定更新
        self.adaptive_retry.record_error(operation, type(error).__name__)
        
        if reraise:
            raise error
        
        return error_context, error_pattern
    
    def _determine_severity(
        self, 
        error: Exception, 
        pattern: Optional[ErrorPattern]
    ) -> ErrorSeverity:
        """エラーの重要度を判定"""
        if pattern:
            return pattern.severity
        
        # パターンがない場合はエラータイプから推測
        if isinstance(error, (ResourceError, ServiceUnavailableError)):
            return ErrorSeverity.CRITICAL
        elif isinstance(error, (AgentError, ContainerError)):
            return ErrorSeverity.HIGH
        elif isinstance(error, (TaskExecutionError, CommunicationError)):
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.LOW
    
    def _handle_incident(
        self, 
        pattern: ErrorPattern, 
        context: ErrorContext, 
        recovery_actions: List[str]
    ):
        """インシデント処理"""
        incident_key = f"{pattern.pattern_id}:{context.component}"
        
        if incident_key not in self.active_incidents:
            # 新しいインシデント
            incident = ErrorIncident(
                incident_id=str(uuid.uuid4()),
                error_type=pattern.pattern_id,
                severity=pattern.severity,
                affected_components=[context.component],
                start_time=time.time(),
                recovery_actions=recovery_actions
            )
            self.active_incidents[incident_key] = incident
            
            logger.warning(
                f"New incident created: {incident.incident_id} "
                f"for pattern {pattern.pattern_id}"
            )
        else:
            # 既存インシデントの更新
            incident = self.active_incidents[incident_key]
            if context.component not in incident.affected_components:
                incident.affected_components.append(context.component)
    
    def resolve_incident(self, incident_id: str, resolution_summary: str):
        """インシデントを解決"""
        for key, incident in self.active_incidents.items():
            if incident.incident_id == incident_id:
                incident.end_time = time.time()
                incident.resolution_summary = resolution_summary
                
                logger.info(
                    f"Incident resolved: {incident_id} "
                    f"(duration: {incident.duration:.2f}s)"
                )
                
                # 解決済みインシデントを削除
                del self.active_incidents[key]
                break
    
    def get_health_status(self) -> Dict[str, Any]:
        """システムヘルス状態を取得"""
        current_time = time.time()
        
        error_trends = self.analyzer.get_error_trends()
        
        # アクティブインシデント数
        active_critical = len([
            i for i in self.active_incidents.values()
            if i.severity == ErrorSeverity.CRITICAL
        ])
        
        active_high = len([
            i for i in self.active_incidents.values()
            if i.severity == ErrorSeverity.HIGH
        ])
        
        # 全体的なヘルスステータス判定
        if active_critical > 0:
            overall_status = "critical"
        elif active_high > 2:
            overall_status = "degraded"
        elif sum(trend["count"] for trend in error_trends.values()) > 50:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        return {
            "overall_status": overall_status,
            "active_incidents": len(self.active_incidents),
            "critical_incidents": active_critical,
            "high_severity_incidents": active_high,
            "error_trends": error_trends,
            "component": self.component_name,
            "last_updated": current_time
        }

def enhanced_retry(
    operation: str,
    error_handler: EnhancedErrorHandler,
    adaptive: bool = True,
    custom_config: Optional[RetryConfig] = None
):
    """強化されたリトライデコレーター"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if adaptive:
                # 適応的リトライ設定
                config = error_handler.adaptive_retry.calculate_optimal_retry_params(
                    operation, "default"
                )
            else:
                config = custom_config or RetryConfig()
            
            last_exception = None
            delay = config.initial_delay
            start_time = time.time()
            
            for attempt in range(config.max_attempts):
                try:
                    result = func(*args, **kwargs)
                    
                    # 成功を記録
                    execution_time = time.time() - start_time
                    error_handler.adaptive_retry.record_operation_result(
                        operation, True, execution_time
                    )
                    
                    return result
                    
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    # エラーを分析付きで処理
                    try:
                        error_handler.handle_error_with_analysis(
                            operation, e, reraise=False
                        )
                    except Exception:
                        pass  # エラーハンドリング自体のエラーは無視
                    
                    if attempt == config.max_attempts - 1:
                        # 失敗を記録
                        execution_time = time.time() - start_time
                        error_handler.adaptive_retry.record_operation_result(
                            operation, False, execution_time
                        )
                        raise
                    
                    logger.warning(
                        f"Enhanced retry attempt {attempt + 1}/{config.max_attempts} "
                        f"for {operation}, retrying in {delay}s"
                    )
                    
                    time.sleep(delay)
                    delay = min(delay * config.backoff_factor, config.max_delay)
                    
                except Exception as e:
                    # 非リトライ可能なエラー
                    execution_time = time.time() - start_time
                    error_handler.adaptive_retry.record_operation_result(
                        operation, False, execution_time
                    )
                    
                    error_handler.handle_error_with_analysis(
                        operation, e, reraise=False
                    )
                    raise
            
            raise last_exception
            
        return wrapper
    return decorator