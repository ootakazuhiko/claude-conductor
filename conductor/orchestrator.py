#!/usr/bin/env python3
"""
Multi-agent orchestrator for Claude Conductor
"""

import os
import time
import json
import uuid
import threading
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, Future
import logging
from datetime import datetime
import asyncio

from .agent import ClaudeAgent, Task, TaskResult
from .protocol import UnixSocketChannel
from .exceptions import (
    ConfigurationError, AgentStartupError, CommunicationError,
    TaskExecutionError, TaskValidationError, TaskTimeoutError, ResourceError
)
from .error_handler import ErrorHandler, retry, CircuitBreaker
from .security import SecurityManager, SecurityConfig, Permission, UserRole
from .enhanced_error_handling import EnhancedErrorHandler, enhanced_retry, AdvancedCircuitBreaker
from .evaluator import LLMJudgeEvaluator, EvaluationResult
from .task_decomposer import TaskDecomposer, ComplexityAnalysis
from .coordination import CoordinationManager, CoordinationStrategy, LeadAgent, AgentCapability, AgentRole
from .token_optimizer import TokenOptimizer
from .mcp_integration import MCPClient, MCPServer, MCPCapability, MCPRegistry

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Orchestrator:
    """Multi-agent orchestrator for Claude Conductor"""
    
    def __init__(self, config_path: Optional[str] = None):
        # Initialize enhanced error handler
        self.error_handler = EnhancedErrorHandler("orchestrator")
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Components
        self.agents: Dict[str, ClaudeAgent] = {}
        self.executor = ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 10)
        )
        self.results: Dict[str, TaskResult] = {}
        self.stats = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_execution_time": 0.0,
            "start_time": None
        }
        
        # Communication socket
        self.broker_socket_path = "/tmp/claude_orchestrator.sock"
        self.broker_channel: Optional[UnixSocketChannel] = None
        
        # Advanced circuit breakers for external dependencies
        self.agent_circuit_breaker = AdvancedCircuitBreaker(
            failure_threshold=3,
            success_threshold=2,
            timeout=30.0,
            expected_exception=AgentStartupError,
            health_check_interval=10.0
        )
        
        # Security manager (optional, disabled by default)
        self.security_manager = None
        if self.config.get("security_enabled", False):
            security_config = SecurityConfig(
                jwt_secret=self.config.get("security", {}).get("jwt_secret", "default-secret"),
                jwt_expiration_hours=self.config.get("security", {}).get("jwt_expiration_hours", 24),
                audit_log_enabled=self.config.get("security", {}).get("audit_enabled", True)
            )
            self.security_manager = SecurityManager(security_config)
            logger.info("Security manager initialized")
        
        # Set up health check for agent circuit breaker
        self.agent_circuit_breaker.set_health_check(self._check_agent_health)
        
        # LLM-as-judge evaluator
        self.evaluator = LLMJudgeEvaluator()
        self.enable_evaluation = self.config.get("enable_evaluation", True)
        
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration file with proper error handling"""
        default_config = {
            "num_agents": 3,
            "max_workers": 10,
            "task_timeout": 300,
            "log_level": "INFO"
        }
        
        if not config_path:
            logger.info("No config path provided, using default configuration")
            return default_config
            
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            # Merge with defaults
            merged_config = {**default_config, **config}
            
            # Validate configuration
            self._validate_config(merged_config)
            return merged_config
            
        except FileNotFoundError:
            error = ConfigurationError(f"Configuration file not found: {config_path}")
            self.error_handler.handle_error(
                error,
                context={"config_path": config_path},
                reraise=True
            )
        except yaml.YAMLError as e:
            error = ConfigurationError(f"Invalid YAML configuration: {e}")
            self.error_handler.handle_error(
                error,
                context={"config_path": config_path},
                reraise=True
            )
        except Exception as e:
            error = ConfigurationError(f"Error loading configuration: {e}")
            self.error_handler.handle_error(
                error,
                context={"config_path": config_path},
                reraise=True
            )
            
    def _validate_config(self, config: Dict[str, Any]):
        """Validate configuration values"""
        if config["num_agents"] < 1:
            raise ConfigurationError("num_agents must be at least 1")
        if config["max_workers"] < 1:
            raise ConfigurationError("max_workers must be at least 1")
        if config["task_timeout"] < 1:
            raise ConfigurationError("task_timeout must be at least 1 second")
            
    def start(self, num_agents: Optional[int] = None):
        """Start orchestrator and agents with enhanced error handling"""
        correlation_id = str(uuid.uuid4())
        logger.info(f"Starting orchestrator with correlation_id: {correlation_id}")
        
        # Update stats
        self.stats["start_time"] = time.time()
        
        # Create broker socket
        try:
            self.broker_channel = UnixSocketChannel(self.broker_socket_path)
            self.broker_channel.bind()
            logger.info(f"Broker socket created at {self.broker_socket_path}")
        except Exception as e:
            self.error_handler.handle_error(
                CommunicationError(f"Failed to create broker socket: {e}"),
                context={"socket_path": self.broker_socket_path},
                correlation_id=correlation_id,
                reraise=True
            )
        
        # Start agents
        if num_agents is None:
            num_agents = self.config.get("num_agents", 3)
            
        for i in range(num_agents):
            agent_id = f"agent_{i:03d}"
            try:
                # Use circuit breaker for agent startup
                def start_agent():
                    agent = ClaudeAgent(agent_id, orchestrator_socket=self.broker_socket_path)
                    agent.start()
                    return agent
                    
                agent = self.agent_circuit_breaker.call(start_agent)
                self.agents[agent_id] = agent
                logger.info(f"Started agent {agent_id}")
            except Exception as e:
                self.error_handler.handle_error(
                    AgentStartupError(f"Failed to start agent {agent_id}: {e}"),
                    context={
                        "agent_id": agent_id,
                        "circuit_breaker_state": self.agent_circuit_breaker.state
                    },
                    correlation_id=correlation_id,
                    reraise=False  # Continue with other agents
                )
                
        active_agents = len([a for a in self.agents.values() if a.is_running])
        if active_agents == 0:
            self.error_handler.handle_error(
                AgentStartupError("No agents could be started"),
                context={"requested_agents": num_agents},
                correlation_id=correlation_id,
                reraise=True
            )
        else:
            logger.info(f"Started {active_agents}/{num_agents} agents successfully")
            
    def stop(self):
        """Stop orchestrator and all agents"""
        logger.info("Stopping orchestrator")
        
        # Stop all agents
        for agent_id, agent in self.agents.items():
            try:
                agent.stop()
                logger.info(f"Stopped agent {agent_id}")
            except Exception as e:
                logger.error(f"Error stopping agent {agent_id}: {e}")
                
        # Close broker socket
        if self.broker_channel:
            try:
                self.broker_channel.close()
                os.unlink(self.broker_socket_path)
            except Exception as e:
                logger.error(f"Error closing broker socket: {e}")
                
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Report final stats
        if self.stats["start_time"]:
            runtime = time.time() - self.stats["start_time"]
            logger.info(f"Orchestrator ran for {runtime:.2f} seconds")
            logger.info(f"Completed {self.stats['tasks_completed']} tasks")
            logger.info(f"Failed {self.stats['tasks_failed']} tasks")
            
    def submit_task(self, task: Task) -> Future[TaskResult]:
        """Submit task for execution with enhanced error handling"""
        correlation_id = str(uuid.uuid4())
        logger.info(f"Submitting task {task.task_id} with correlation_id: {correlation_id}")
        
        # Validate task
        try:
            self._validate_task(task)
        except TaskValidationError as e:
            self.error_handler.handle_error(
                e,
                context={"task": asdict(task)},
                correlation_id=correlation_id,
                reraise=True
            )
            
        # Find available agent using enhanced retry
        @enhanced_retry(
            max_attempts=3,
            exceptions=(RuntimeError,),
            error_handler=self.error_handler
        )
        def find_agent():
            agent = self._find_available_agent()
            if not agent:
                raise RuntimeError("No available agents")
            return agent
            
        try:
            agent = find_agent()
        except Exception as e:
            self.error_handler.handle_error(
                ResourceError(f"Failed to find available agent: {e}"),
                context={"task_id": task.task_id},
                correlation_id=correlation_id,
                reraise=True
            )
            
        # Submit task for execution
        future = self.executor.submit(self._execute_task, task, agent, correlation_id)
        return future
        
    def _validate_task(self, task: Task):
        """Validate task before execution"""
        if not task.task_id:
            raise TaskValidationError("Task ID is required")
        if not task.task_type:
            raise TaskValidationError("Task type is required")
        if task.priority < 0 or task.priority > 10:
            raise TaskValidationError("Task priority must be between 0 and 10")
        if task.timeout and task.timeout <= 0:
            raise TaskValidationError("Task timeout must be positive")
            
    def _find_available_agent(self) -> Optional[ClaudeAgent]:
        """Find an available agent for task execution"""
        # Simple round-robin for now
        for agent in self.agents.values():
            if agent.is_running and not agent.is_busy:
                return agent
        return None
        
    def _execute_task(self, task: Task, agent: ClaudeAgent, correlation_id: str) -> TaskResult:
        """Execute task on agent with enhanced error handling"""
        start_time = time.time()
        
        try:
            logger.info(f"Executing task {task.task_id} on agent {agent.agent_id}")
            
            # Set task timeout if specified
            timeout = task.timeout or self.config.get("task_timeout", 300)
            
            # Execute with timeout and error handling
            try:
                result = agent.execute_task(task)
            except TimeoutError:
                raise TaskTimeoutError(f"Task {task.task_id} timed out after {timeout}s")
            except Exception as e:
                raise TaskExecutionError(f"Task execution failed: {e}")
                
            # Check result
            if result.status == "failed":
                self.error_handler.handle_error(
                    TaskExecutionError(f"Task {task.task_id} failed: {result.error}"),
                    context={
                        "task_id": task.task_id,
                        "agent_id": agent.agent_id,
                        "error": result.error
                    },
                    correlation_id=correlation_id,
                    reraise=False
                )
                self.stats["tasks_failed"] += 1
            else:
                self.stats["tasks_completed"] += 1
            
            self._update_stats(result)
            self.results[task.task_id] = result
            
            # Evaluate task result if evaluation is enabled
            if self.enable_evaluation and result.status == "success":
                try:
                    # Schedule evaluation in background
                    threading.Thread(
                        target=self._run_evaluation,
                        args=(task, result),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.error(f"Failed to schedule evaluation for task {task.task_id}: {e}")
            
            return result
            
        except Exception as e:
            # Handle unexpected errors in task execution setup
            error_result = TaskResult(
                task_id=getattr(task, 'task_id', 'unknown'),
                agent_id="orchestrator",
                status="failed",
                error=str(e),
                result={},
                execution_time=time.time() - start_time
            )
            
            self.error_handler.handle_error(
                TaskExecutionError(f"Unexpected error executing task: {e}"),
                context={
                    "task_id": getattr(task, 'task_id', 'unknown'),
                    "agent_id": getattr(agent, 'agent_id', 'unknown')
                },
                correlation_id=correlation_id,
                reraise=False
            )
            
            self.stats["tasks_failed"] += 1
            self._update_stats(error_result)
            self.results[getattr(task, 'task_id', 'unknown')] = error_result
            
            return error_result
            
    def _update_stats(self, result: TaskResult):
        """Update execution statistics"""
        self.stats["total_execution_time"] += result.execution_time
        
    def submit_batch(self, tasks: List[Task]) -> List[Future[TaskResult]]:
        """Submit multiple tasks for execution"""
        futures = []
        for task in tasks:
            try:
                future = self.submit_task(task)
                futures.append(future)
            except Exception as e:
                logger.error(f"Failed to submit task {task.task_id}: {e}")
                # Create a failed future
                failed_future: Future[TaskResult] = Future()
                failed_future.set_exception(e)
                futures.append(failed_future)
        return futures
        
    def wait_for_batch(self, futures: List[Future[TaskResult]], timeout: Optional[float] = None) -> List[TaskResult]:
        """Wait for batch of tasks to complete"""
        results = []
        for future in futures:
            try:
                result = future.result(timeout=timeout)
                results.append(result)
            except Exception as e:
                logger.error(f"Task execution failed: {e}")
                # Create error result
                error_result = TaskResult(
                    task_id="unknown",
                    agent_id="orchestrator",
                    status="failed",
                    error=str(e),
                    result={},
                    execution_time=0.0
                )
                results.append(error_result)
        return results
        
    def get_agent_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all agents"""
        status = {}
        for agent_id, agent in self.agents.items():
            status[agent_id] = {
                "is_running": agent.is_running,
                "is_busy": agent.is_busy,
                "tasks_completed": agent.stats.get("tasks_completed", 0),
                "tasks_failed": agent.stats.get("tasks_failed", 0),
                "last_task": agent.stats.get("last_task", None)
            }
        return status
        
    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get task execution result by ID"""
        return self.results.get(task_id)
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator execution statistics"""
        runtime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        stats = {
            "runtime": runtime,
            "tasks_completed": self.stats["tasks_completed"],
            "tasks_failed": self.stats["tasks_failed"],
            "avg_execution_time": self._get_avg_execution_time(),
            "total_execution_time": self.stats["total_execution_time"],
            "active_agents": len([a for a in self.agents.values() if a.is_running]),
            "total_agents": len(self.agents)
        }
        
        # Add security statistics if security is enabled
        if self.security_manager:
            stats["security"] = self.security_manager.get_security_stats()
        
        # Add evaluation statistics if available
        if hasattr(self, 'evaluator'):
            stats["evaluation"] = self.evaluator.get_statistics()
        
        return stats
    
    def get_security_status(self) -> Dict[str, Any]:
        """セキュリティ状態を取得"""
        if not self.security_manager:
            return {"security_enabled": False}
        
        return {
            "security_enabled": True,
            "security_stats": self.security_manager.get_security_stats(),
            "audit_enabled": self.security_manager.config.audit_log_enabled,
            "recent_audit_events": len(self.security_manager.audit_logger.audit_log)
        }
    
    def _run_evaluation(self, task: Task, result: TaskResult):
        """Run evaluation in background thread"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            evaluation_result = loop.run_until_complete(
                self._evaluate_task_result(task, result)
            )
            logger.info(f"Task {task.task_id} evaluated with score {evaluation_result.overall_score:.1f}")
        except Exception as e:
            logger.error(f"Failed to evaluate task {task.task_id}: {e}")
        finally:
            loop.close()
    
    async def _evaluate_task_result(self, task: Task, result: TaskResult) -> EvaluationResult:
        """Evaluate task result using LLM-as-judge"""
        # Prepare task input data
        task_input = {
            "task_type": task.task_type,
            "description": task.description,
            "files": task.files,
            "priority": task.priority,
            "timeout": task.timeout
        }
        
        # Prepare task output data
        task_output = {
            "status": result.status,
            "result": result.result,
            "error": result.error,
            "execution_time": result.execution_time
        }
        
        return await self.evaluator.evaluate_task_result(
            task_id=task.task_id,
            agent_id=result.agent_id,
            task_input=task_input,
            task_output=task_output,
            task_type=task.task_type
        )
    
    def get_evaluation_report(self, agent_id: Optional[str] = None, task_type: Optional[str] = None) -> Dict[str, Any]:
        """Get evaluation report for agents and task types"""
        if not hasattr(self, 'evaluator'):
            return {"error": "Evaluation system not enabled"}
        
        history = self.evaluator.get_evaluation_history(agent_id=agent_id, task_type=task_type, limit=50)
        trends = self.evaluator.analyze_quality_trends()
        
        return {
            "evaluation_history": [asdict(eval_result) for eval_result in history],
            "quality_trends": [asdict(trend) for trend in trends],
            "statistics": self.evaluator.get_statistics()
        }
    
    def _check_agent_health(self) -> bool:
        """エージェントヘルスチェック"""
        try:
            active_agents = len([a for a in self.agents.values() if a.is_running])
            return active_agents > 0
        except Exception:
            return False
    
    def get_enhanced_statistics(self) -> Dict[str, Any]:
        """強化された統計情報を取得"""
        basic_stats = self.get_statistics()
        
        # エラーハンドリング統計を追加
        health_status = self.error_handler.get_health_status()
        
        return {
            **basic_stats,
            "error_handling": {
                "health_status": health_status,
                "circuit_breaker_state": self.agent_circuit_breaker.state,
                "adaptive_retry_stats": {
                    "total_patterns": len(self.error_handler.adaptive_retry.error_patterns),
                    "success_rate_data_points": sum(
                        len(rates) for rates in self.error_handler.adaptive_retry.success_rates.values()
                    )
                }
            }
        }
    
    def resolve_error_incident(self, incident_id: str, resolution_summary: str):
        """エラーインシデントを解決"""
        self.error_handler.resolve_incident(incident_id, resolution_summary)
        
    def _get_avg_execution_time(self) -> float:
        """Calculate average task execution time"""
        total_tasks = self.stats["tasks_completed"] + self.stats["tasks_failed"]
        if total_tasks == 0:
            return 0.0
        return self.stats["total_execution_time"] / total_tasks

def create_task(task_type: str = "generic", description: str = "", files: List[str] = None, **kwargs) -> Task:
    """Helper function to easily create tasks"""
    if files is None:
        files = []
    
    return Task(
        task_type=task_type,
        description=description,
        files=files,
        **kwargs
    )

# Demo tasks for testing
def create_demo_tasks() -> List[Task]:
    """Create demonstration tasks"""
    return [
        Task(
            task_id="demo_1",
            task_type="code_review",
            description="Review Python code for security issues",
            files=["demo/example.py"],
            priority=8
        ),
        Task(
            task_id="demo_2",
            task_type="refactor",
            description="Refactor legacy code to use modern patterns",
            files=["demo/legacy.py"],
            priority=5
        ),
        Task(
            task_id="demo_3",
            task_type="test_generation",
            description="Generate unit tests for utility functions",
            files=["demo/utils.py"],
            priority=6
        ),
        Task(
            task_id="demo_4",
            task_type="analysis",
            description="Analyze codebase for performance bottlenecks",
            files=["demo/"],
            priority=7
        )
    ]

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Conductor Orchestrator")
    parser.add_argument("--config", help="Configuration file path")
    parser.add_argument("--agents", type=int, help="Number of agents to start")
    parser.add_argument("--demo", action="store_true", help="Run with demo tasks")
    args = parser.parse_args()
    
    # Create orchestrator
    orchestrator = Orchestrator(config_path=args.config)
    
    try:
        # Start orchestrator
        orchestrator.start(num_agents=args.agents)
        
        if args.demo:
            # Run demo tasks
            logger.info("Running demo tasks")
            tasks = create_demo_tasks()
            futures = orchestrator.submit_batch(tasks)
            results = orchestrator.wait_for_batch(futures)
            
            # Print results
            for result in results:
                logger.info(f"Task {result.task_id}: {result.status}")
                if result.error:
                    logger.error(f"  Error: {result.error}")
                    
            # Print statistics
            stats = orchestrator.get_statistics()
            logger.info(f"Statistics: {json.dumps(stats, indent=2)}")
        else:
            # Interactive mode
            logger.info("Orchestrator started. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Stopping orchestrator...")
    finally:
        orchestrator.stop()



if __name__ == "__main__":
    main()