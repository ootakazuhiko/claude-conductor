#!/usr/bin/env python3
"""
Custom exceptions for Claude Conductor
"""

import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


class ConductorError(Exception):
    """Base exception for Claude Conductor"""
    
    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.timestamp = time.time()


class AgentError(ConductorError):
    """Agent-related errors"""
    pass


class AgentStartupError(AgentError):
    """Agent startup failures"""
    pass


class AgentCommunicationError(AgentError):
    """Agent communication failures"""
    pass


class ContainerError(ConductorError):
    """Container operation errors"""
    pass


class ContainerCreationError(ContainerError):
    """Container creation failures"""
    pass


class ContainerExecutionError(ContainerError):
    """Container command execution failures"""
    pass


class TaskExecutionError(ConductorError):
    """Task execution errors"""
    pass


class TaskTimeoutError(TaskExecutionError):
    """Task execution timeout"""
    pass


class TaskValidationError(TaskExecutionError):
    """Task validation failures"""
    pass


class CommunicationError(ConductorError):
    """Inter-agent communication errors"""
    pass


class ChannelError(CommunicationError):
    """Communication channel errors"""
    pass


class ProtocolError(CommunicationError):
    """Protocol-related errors"""
    pass


class WorkspaceError(ConductorError):
    """Workspace operation errors"""
    pass


class WorkspaceCreationError(WorkspaceError):
    """Workspace creation failures"""
    pass


class WorkspaceCleanupError(WorkspaceError):
    """Workspace cleanup failures"""
    pass


class ConfigurationError(ConductorError):
    """Configuration-related errors"""
    pass


class ResourceError(ConductorError):
    """Resource-related errors (memory, CPU, disk)"""
    pass


class ServiceUnavailableError(ConductorError):
    """Service unavailable errors"""
    pass


@dataclass
class ErrorContext:
    """Structured error context for logging and debugging"""
    component: str
    operation: str
    error_code: str
    details: Dict[str, Any]
    timestamp: float
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return asdict(self)


def create_error_context(
    component: str,
    operation: str,
    error: Exception,
    additional_context: Dict[str, Any] = None,
    correlation_id: str = None
) -> ErrorContext:
    """Create standardized error context"""
    context = additional_context or {}
    
    return ErrorContext(
        component=component,
        operation=operation,
        error_code=type(error).__name__,
        details={
            'error_message': str(error),
            'error_type': type(error).__name__,
            **context
        },
        timestamp=time.time(),
        correlation_id=correlation_id
    )