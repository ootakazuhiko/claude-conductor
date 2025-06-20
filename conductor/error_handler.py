#!/usr/bin/env python3
"""
Enhanced Error handling utilities and patterns for Claude Conductor
エラーハンドリングとリトライメカニズムの強化版
"""

import asyncio
import functools
import logging
import time
import json
import pickle
import sqlite3
from typing import Any, Callable, Optional, Dict, Type, List, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
import threading
from collections import defaultdict, deque
import uuid

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
    
@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    backoff_factor: float = 2.0
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_backoff: bool = True
    retryable_exceptions: tuple = (
        ConnectionError,
        TimeoutError,
        ServiceUnavailableError,
        CommunicationError
    )


class CircuitBreaker:
    """Circuit breaker pattern implementation"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "open":
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = "half-open"
                else:
                    raise ServiceUnavailableError(
                        f"Circuit breaker is open for {func.__name__}",
                        context={"state": self.state, "failure_count": self.failure_count}
                    )
            
            try:
                result = func(*args, **kwargs)
                if self.state == "half-open":
                    self._reset()
                return result
            except self.expected_exception as e:
                self._record_failure()
                raise
                
        return wrapper
    
    def _record_failure(self):
        """Record a failure and update circuit breaker state"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                f"Circuit breaker opened after {self.failure_count} failures"
            )
    
    def _reset(self):
        """Reset circuit breaker to closed state"""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"
        logger.info("Circuit breaker reset to closed state")


def retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple = None
):
    """Decorator for retry logic with exponential backoff"""
    if retryable_exceptions is None:
        retryable_exceptions = (ConnectionError, TimeoutError, ServiceUnavailableError)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            delay = initial_delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts",
                            extra={
                                "function": func.__name__,
                                "attempts": max_attempts,
                                "final_error": str(e)
                            }
                        )
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}, retrying in {delay}s",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "error": str(e),
                            "retry_delay": delay
                        }
                    )
                    
                    time.sleep(delay)
                    delay = min(delay * backoff_factor, max_delay)
                except Exception as e:
                    # Non-retryable exception
                    logger.error(
                        f"Non-retryable error in {func.__name__}: {e}",
                        extra={"function": func.__name__, "error": str(e)}
                    )
                    raise
            
            # This should never be reached, but just in case
            raise last_exception
            
        return wrapper
    return decorator


def async_retry(config: RetryConfig = None):
    """Async version of retry decorator"""
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = config.initial_delay
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e
                    if attempt == config.max_attempts - 1:
                        logger.error(
                            f"Async function {func.__name__} failed after {config.max_attempts} attempts",
                            extra={
                                "function": func.__name__,
                                "attempts": config.max_attempts,
                                "final_error": str(e)
                            }
                        )
                        raise
                    
                    logger.warning(
                        f"Async attempt {attempt + 1} failed for {func.__name__}, retrying in {delay}s",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "error": str(e),
                            "retry_delay": delay
                        }
                    )
                    
                    await asyncio.sleep(delay)
                    if config.exponential_backoff:
                        delay = min(delay * config.backoff_factor, config.max_delay)
                except Exception as e:
                    logger.error(
                        f"Non-retryable async error in {func.__name__}: {e}",
                        extra={"function": func.__name__, "error": str(e)}
                    )
                    raise
            
            raise last_exception
            
        return wrapper
    return decorator


class ErrorHandler:
    """Centralized error handling and logging"""
    
    def __init__(self, component_name: str):
        self.component_name = component_name
        self.logger = logging.getLogger(f"conductor.{component_name}")
    
    def handle_error(
        self,
        operation: str,
        error: Exception,
        context: Dict[str, Any] = None,
        correlation_id: str = None,
        reraise: bool = True
    ) -> ErrorContext:
        """Handle an error with standardized logging and context"""
        error_context = create_error_context(
            component=self.component_name,
            operation=operation,
            error=error,
            additional_context=context,
            correlation_id=correlation_id
        )
        
        # Log with appropriate severity
        if isinstance(error, (ResourceError, ServiceUnavailableError)):
            self.logger.critical(
                f"Critical error in {operation}: {error}",
                extra=error_context.to_dict()
            )
        elif isinstance(error, (AgentError, ContainerError, TaskExecutionError)):
            self.logger.error(
                f"Error in {operation}: {error}",
                extra=error_context.to_dict()
            )
        elif isinstance(error, CommunicationError):
            self.logger.warning(
                f"Communication error in {operation}: {error}",
                extra=error_context.to_dict()
            )
        else:
            self.logger.error(
                f"Unexpected error in {operation}: {error}",
                extra=error_context.to_dict()
            )
        
        if reraise:
            raise error
        
        return error_context
    
    def handle_warning(
        self,
        operation: str,
        message: str,
        context: Dict[str, Any] = None,
        correlation_id: str = None
    ):
        """Handle warnings with consistent logging"""
        self.logger.warning(
            f"Warning in {operation}: {message}",
            extra={
                "component": self.component_name,
                "operation": operation,
                "message": message,
                "context": context or {},
                "correlation_id": correlation_id,
                "timestamp": time.time()
            }
        )
    
    def log_operation_start(
        self,
        operation: str,
        context: Dict[str, Any] = None,
        correlation_id: str = None
    ):
        """Log operation start for debugging"""
        self.logger.debug(
            f"Starting operation: {operation}",
            extra={
                "component": self.component_name,
                "operation": operation,
                "context": context or {},
                "correlation_id": correlation_id,
                "timestamp": time.time()
            }
        )
    
    def log_operation_success(
        self,
        operation: str,
        context: Dict[str, Any] = None,
        correlation_id: str = None
    ):
        """Log successful operation completion"""
        self.logger.info(
            f"Successfully completed operation: {operation}",
            extra={
                "component": self.component_name,
                "operation": operation,
                "context": context or {},
                "correlation_id": correlation_id,
                "timestamp": time.time()
            }
        )


def safe_execute(
    func: Callable,
    error_handler: ErrorHandler,
    operation: str,
    default_return: Any = None,
    context: Dict[str, Any] = None,
    correlation_id: str = None
) -> Any:
    """Safely execute a function with error handling"""
    try:
        error_handler.log_operation_start(operation, context, correlation_id)
        result = func()
        error_handler.log_operation_success(operation, context, correlation_id)
        return result
    except Exception as e:
        error_handler.handle_error(
            operation=operation,
            error=e,
            context=context,
            correlation_id=correlation_id,
            reraise=False
        )
        return default_return


async def async_safe_execute(
    func: Callable,
    error_handler: ErrorHandler,
    operation: str,
    default_return: Any = None,
    context: Dict[str, Any] = None,
    correlation_id: str = None
) -> Any:
    """Safely execute an async function with error handling"""
    try:
        error_handler.log_operation_start(operation, context, correlation_id)
        result = await func()
        error_handler.log_operation_success(operation, context, correlation_id)
        return result
    except Exception as e:
        error_handler.handle_error(
            operation=operation,
            error=e,
            context=context,
            correlation_id=correlation_id,
            reraise=False
        )
        return default_return