"""
Claude Conductor - Multi-Agent Orchestration System

A system for managing multiple Claude Code instances in parallel,
enabling coordinated task distribution and execution.
"""

from .orchestrator import Orchestrator, Task, TaskResult
from .agent import ClaudeAgent, AgentConfig
from .protocol import Agent2AgentProtocol, AgentMessage, MessageType

__version__ = "0.1.0"
__author__ = "Claude Conductor Team"

__all__ = [
    "Orchestrator",
    "Task",
    "TaskResult", 
    "ClaudeAgent",
    "AgentConfig",
    "Agent2AgentProtocol",
    "AgentMessage",
    "MessageType"
]