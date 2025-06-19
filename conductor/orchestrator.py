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
from dataclasses import dataclass, field, asdict
from concurrent.futures import ThreadPoolExecutor, Future
import logging
from datetime import datetime

from .agent import ClaudeAgent, Task, TaskResult
from .protocol import UnixSocketChannel
from .exceptions import (
    ConfigurationError, AgentStartupError, CommunicationError,
    TaskExecutionError, TaskValidationError, TaskTimeoutError, ResourceError
)
from .error_handler import ErrorHandler, retry, CircuitBreaker
from .evaluator import LLMJudgeEvaluator, EvaluationResult

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Orchestrator:
    """Multi-agent orchestrator for Claude Conductor"""
    
    def __init__(self, config_path: Optional[str] = None):
        # Initialize error handler
        self.error_handler = ErrorHandler("orchestrator")
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Components
        self.agents: Dict[str, ClaudeAgent] = {}
        self.executor = ThreadPoolExecutor(
            max_workers=self.config.get("max_workers", 10)
        )
        self.task_queue: List[Task] = []
        self.results: Dict[str, TaskResult] = {}
        
        # Statistics
        self.stats = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "total_execution_time": 0.0,
            "start_time": None
        }
        
        # Communication socket
        self.broker_socket_path = "/tmp/claude_orchestrator.sock"
        self.broker_channel: Optional[UnixSocketChannel] = None
        
        # Circuit breakers for external dependencies
        self.agent_circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            timeout=30.0,
            expected_exception=AgentStartupError
        )
        
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
        
        if config_path:
            if not os.path.exists(config_path):
                raise ConfigurationError(
                    f"Configuration file not found: {config_path}",
                    context={"config_path": config_path}
                )
            
            try:
                with open(config_path, 'r') as f:
                    user_config = yaml.safe_load(f)
                    if user_config:
                        default_config.update(user_config)
                    else:
                        self.error_handler.handle_warning(
                            "config_load",
                            "Configuration file is empty, using defaults",
                            {"config_path": config_path}
                        )
            except yaml.YAMLError as e:
                self.error_handler.handle_error(
                    "config_parse",
                    ConfigurationError(f"Failed to parse config file: {e}", context={"config_path": config_path}),
                    reraise=False
                )
            except IOError as e:
                self.error_handler.handle_error(
                    "config_read",
                    ConfigurationError(f"Failed to read config file: {e}", context={"config_path": config_path}),
                    reraise=False
                )
                
        return default_config
    
    @retry(max_attempts=3, retryable_exceptions=(AgentStartupError, ConnectionError))
    def _start_agent_with_retry(self, agent_id: str) -> ClaudeAgent:
        """Start agent with retry logic"""
        try:
            agent = ClaudeAgent(agent_id, self.broker_socket_path, self.config)
            agent.start()
            return agent
        except Exception as e:
            raise AgentStartupError(
                f"Failed to start agent {agent_id}: {e}",
                context={"agent_id": agent_id, "original_error": str(e)}
            )
        
    def start(self):
        """Start orchestrator with comprehensive error handling"""
        self.error_handler.log_operation_start(
            "orchestrator_start",
            {"num_agents": self.config['num_agents']}
        )
        
        logger.info(f"Starting orchestrator with {self.config['num_agents']} agents")
        self.stats["start_time"] = time.time()
        
        # Start broker channel with proper error handling
        try:
            self.broker_channel = UnixSocketChannel(
                self.broker_socket_path,
                is_server=True
            )
            self.error_handler.log_operation_success(
                "broker_channel_start",
                {"socket_path": self.broker_socket_path}
            )
        except Exception as e:
            self.error_handler.handle_error(
                "broker_channel_start",
                CommunicationError(f"Failed to start broker channel: {e}", context={"socket_path": self.broker_socket_path}),
                reraise=False
            )
            self.broker_channel = None
        
        # Start agents with circuit breaker protection
        successful_agents = 0
        failed_agents = []
        
        for i in range(self.config["num_agents"]):
            agent_id = f"agent_{i:03d}"
            
            try:
                agent = self._start_agent_with_retry(agent_id)
                self.agents[agent_id] = agent
                successful_agents += 1
                self.error_handler.log_operation_success(
                    "agent_start",
                    {"agent_id": agent_id}
                )
            except AgentStartupError as e:
                failed_agents.append(agent_id)
                self.error_handler.handle_error(
                    "agent_start",
                    e,
                    context={"agent_id": agent_id},
                    reraise=False
                )
        
        # Validate minimum agent requirements
        min_agents = max(1, self.config["num_agents"] // 2)
        if successful_agents < min_agents:
            raise ResourceError(
                f"Failed to start minimum required agents ({successful_agents}/{min_agents})",
                context={
                    "successful_agents": successful_agents,
                    "failed_agents": failed_agents,
                    "min_required": min_agents
                }
            )
                
        logger.info(f"Orchestrator started with {successful_agents}/{self.config['num_agents']} active agents")
        
        # Register agents with coordination manager
        for agent_id, agent in self.agents.items():
            capability = AgentCapability(
                agent_id=agent_id,
                role=AgentRole.SUB,
                skills={"execution", "analysis", "testing"},
                performance_score=1.0
            )
            self.coordination_manager.register_agent(agent, capability)
        
        # Create lead agents if configured
        if self.config.get("enable_hierarchical_coordination", False):
            self._setup_hierarchical_teams()
        
        # Start statistics reporter thread
        threading.Thread(target=self._stats_reporter, daemon=True).start()
        
        self.error_handler.log_operation_success(
            "orchestrator_start",
            {
                "successful_agents": successful_agents,
                "failed_agents": len(failed_agents)
            }
        )
        
    def stop(self):
        """Stop orchestrator with proper cleanup"""
        self.error_handler.log_operation_start("orchestrator_stop")
        logger.info("Stopping orchestrator")
        
        # Stop all agents with error handling
        failed_stops = []
        for agent_id, agent in self.agents.items():
            try:
                agent.stop()
                self.error_handler.log_operation_success(
                    "agent_stop",
                    {"agent_id": agent_id}
                )
            except Exception as e:
                failed_stops.append(agent_id)
                self.error_handler.handle_error(
                    "agent_stop",
                    AgentError(f"Error stopping agent {agent_id}: {e}", context={"agent_id": agent_id}),
                    reraise=False
                )
                
        # Close broker channel
        if self.broker_channel:
            try:
                self.broker_channel.close()
                self.error_handler.log_operation_success("broker_channel_close")
            except Exception as e:
                self.error_handler.handle_error(
                    "broker_channel_close",
                    CommunicationError(f"Error closing broker channel: {e}"),
                    reraise=False
                )
        
        # Shutdown thread pool
        try:
            self.executor.shutdown(wait=True)
            self.error_handler.log_operation_success("executor_shutdown")
        except Exception as e:
            self.error_handler.handle_error(
                "executor_shutdown",
                ResourceError(f"Error shutting down executor: {e}"),
                reraise=False
            )
        
        self.error_handler.log_operation_success(
            "orchestrator_stop",
            {"failed_agent_stops": len(failed_stops)}
        )
        
        # Print final statistics
        self._print_final_stats()
        
        logger.info("Orchestrator stopped")
        
    def execute_task(self, task: Task) -> TaskResult:
        """Execute single task with comprehensive error handling"""
        correlation_id = str(uuid.uuid4())
        
        self.error_handler.log_operation_start(
            "task_execution",
            {"task_id": task.task_id, "task_type": task.task_type},
            correlation_id
        )
        
        try:
            # Validate task
            if not task.task_id or not task.task_type:
                raise TaskValidationError(
                    "Task missing required fields",
                    context={"task_id": getattr(task, 'task_id', None), "task_type": getattr(task, 'task_type', None)}
                )
            
            # Add to priority queue
            self.task_queue.append(task)
            self.task_queue.sort(key=lambda t: t.priority, reverse=True)
            
            # Select available agent
            agent = self._get_available_agent()
            if not agent:
                error_result = TaskResult(
                    task_id=task.task_id,
                    agent_id="none",
                    status="failed",
                    result={},
                    error="No available agents"
                )
                
                self.error_handler.handle_error(
                    "task_execution",
                    ResourceError("No available agents for task execution"),
                    context={"task_id": task.task_id},
                    correlation_id=correlation_id,
                    reraise=False
                )
                
                self._update_stats(error_result)
                self.results[task.task_id] = error_result
                return error_result
            
            # Execute task with timeout and error handling
            future = self.executor.submit(agent.execute_task, task)
            
            try:
                result = future.result(timeout=task.timeout)
                self.error_handler.log_operation_success(
                    "task_execution",
                    {"task_id": task.task_id, "agent_id": agent.agent_id, "status": result.status},
                    correlation_id
                )
            except TimeoutError:
                future.cancel()  # Attempt to cancel if still running
                result = TaskResult(
                    task_id=task.task_id,
                    agent_id=agent.agent_id,
                    status="timeout",
                    result={},
                    error=f"Task execution timeout after {task.timeout}s"
                )
                
                self.error_handler.handle_error(
                    "task_execution",
                    TaskTimeoutError(f"Task {task.task_id} timed out after {task.timeout}s"),
                    context={"task_id": task.task_id, "agent_id": agent.agent_id, "timeout": task.timeout},
                    correlation_id=correlation_id,
                    reraise=False
                )
            except Exception as e:
                result = TaskResult(
                    task_id=task.task_id,
                    agent_id=agent.agent_id,
                    status="failed",
                    result={},
                    error=str(e)
                )
                
                self.error_handler.handle_error(
                    "task_execution",
                    TaskExecutionError(f"Task {task.task_id} failed: {e}"),
                    context={"task_id": task.task_id, "agent_id": agent.agent_id},
                    correlation_id=correlation_id,
                    reraise=False
                )
            
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
                result={},
                error=f"Task setup failed: {e}"
            )
            
            self.error_handler.handle_error(
                "task_execution",
                e,
                context={"task_id": getattr(task, 'task_id', 'unknown')},
                correlation_id=correlation_id,
                reraise=False
            )
            
            self._update_stats(error_result)
            if hasattr(task, 'task_id') and task.task_id:
                self.results[task.task_id] = error_result
            return error_result
        
    def execute_parallel_task(self, task: Task) -> List[TaskResult]:
        """Execute parallel task with subtasks"""
        if not task.subtasks:
            return [self.execute_task(task)]
            
        futures: List[tuple] = []
        results: List[TaskResult] = []
        
        # Execute subtasks in parallel
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
                # Error result when no agent is available
                error_result = TaskResult(
                    task_id=subtask.task_id,
                    agent_id="none",
                    status="failed",
                    result={},
                    error="No available agents"
                )
                results.append(error_result)
                
        # Collect results
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
        """Get available agent for task execution"""
        # Find agent not currently executing a task
        for agent in self.agents.values():
            if agent.is_running and agent.current_task is None:
                return agent
                
        # If all are busy, select the least loaded agent
        # (Simple implementation: select first agent)
        if self.agents:
            return list(self.agents.values())[0]
            
        return None
        
    def _update_stats(self, result: TaskResult):
        """Update execution statistics"""
        if result.status == "success":
            self.stats["tasks_completed"] += 1
        else:
            self.stats["tasks_failed"] += 1
            
        self.stats["total_execution_time"] += result.execution_time
        
    def _stats_reporter(self):
        """Periodic statistics reporter thread"""
        while self.agents:
            time.sleep(60)  # Every minute
            
            if not any(agent.is_running for agent in self.agents.values()):
                break
                
            logger.info(
                f"Stats - Completed: {self.stats['tasks_completed']}, "
                f"Failed: {self.stats['tasks_failed']}, "
                f"Avg time: {self._get_avg_execution_time():.2f}s"
            )
            
    def _get_avg_execution_time(self) -> float:
        """Get average execution time"""
        total_tasks = self.stats["tasks_completed"] + self.stats["tasks_failed"]
        if total_tasks == 0:
            return 0.0
        return self.stats["total_execution_time"] / total_tasks
        
    def _print_final_stats(self):
        """Print final execution statistics"""
        runtime = time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        
        print("\n=== Final Statistics ===")
        print(f"Runtime: {runtime:.2f}s")
        print(f"Total tasks completed: {self.stats['tasks_completed']}")
        print(f"Total tasks failed: {self.stats['tasks_failed']}")
        print(f"Average execution time: {self._get_avg_execution_time():.2f}s")
        print(f"Total execution time: {self.stats['total_execution_time']:.2f}s")
        print(f"Active agents: {len([a for a in self.agents.values() if a.is_running])}/{len(self.agents)}")
        
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
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
        
        # Add evaluation statistics if available
        if hasattr(self, 'evaluator'):
            stats["evaluation"] = self.evaluator.get_statistics()
        
        return stats
    
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

# CLI entry point
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
        
    # Create orchestrator
    orchestrator = Orchestrator(args.config)
    
    if args.agents:
        orchestrator.config["num_agents"] = args.agents
        
    try:
        # Start orchestrator
        orchestrator.start()
        
        if args.demo:
            # Execute demo tasks
            print("\n=== Running Demo Tasks ===")
            
            # Task 1: Code review
            task1 = create_task(
                task_type="code_review",
                description="Review sample code",
                files=["examples/sample_code.py"]
            )
            result1 = orchestrator.execute_task(task1)
            print(f"Code review task: {result1.status}")
            
            # Task 2: Parallel test generation
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
            # Simple REPL
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