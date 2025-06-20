#!/usr/bin/env python3
"""
Enhanced Agent with Comprehensive Performance Monitoring

This module extends the base ClaudeAgent with comprehensive performance monitoring,
resource tracking, and detailed execution metrics.
"""

import time
import threading
import logging
import psutil
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import uuid

from .agent import ClaudeAgent, Task, TaskResult
from .metrics import get_metrics_collector, MetricsCollector
from .monitoring import (
    AgentMonitoringMixin, traced, get_tracing_middleware,
    ResourceMonitor, PerformanceInterceptor
)

logger = logging.getLogger(__name__)


@dataclass 
class TaskExecutionDetail:
    """Detailed task execution information"""
    task_id: str
    task_type: str
    start_time: float
    end_time: Optional[float] = None
    queue_time: float = 0.0
    execution_time: float = 0.0
    cpu_usage_start: float = 0.0
    cpu_usage_end: float = 0.0
    memory_usage_start: int = 0
    memory_usage_end: int = 0
    container_stats: Dict[str, Any] = None
    error_details: Optional[str] = None
    correlation_id: str = ""
    
    def __post_init__(self):
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())


@dataclass
class AgentPerformanceProfile:
    """Agent performance profiling data"""
    agent_id: str
    specializations: List[str]  # Task types this agent excels at
    avg_execution_times: Dict[str, float]  # By task type
    success_rates: Dict[str, float]  # By task type
    resource_efficiency: float  # CPU/memory efficiency score
    reliability_score: float  # Based on health checks and errors
    throughput_score: float  # Tasks completed per unit time
    last_updated: float = 0.0
    
    def __post_init__(self):
        if self.last_updated == 0.0:
            self.last_updated = time.time()


class MonitoredAgent(AgentMonitoringMixin, ClaudeAgent):
    """Agent with comprehensive performance monitoring"""
    
    def __init__(self, agent_id: str, orchestrator_socket_path: str = "/tmp/claude_orchestrator.sock",
                 config: Optional[Dict[str, Any]] = None):
        
        # Initialize monitoring components first
        self.metrics_collector = get_metrics_collector()
        self.tracing = get_tracing_middleware()
        
        # Initialize base agent
        super().__init__(agent_id, orchestrator_socket_path, config)
        
        # Enhanced monitoring state
        self.execution_history: deque = deque(maxlen=1000)  # Last 1000 task executions
        self.performance_profile = AgentPerformanceProfile(
            agent_id=agent_id,
            specializations=[],
            avg_execution_times={},
            success_rates={},
            resource_efficiency=1.0,
            reliability_score=1.0,
            throughput_score=0.0
        )
        
        # Resource monitoring
        self.process_monitor = ProcessMonitor(agent_id)
        self.container_monitor: Optional[ContainerMonitor] = None
        
        # Performance tracking
        self.task_performance_cache: Dict[str, List[TaskExecutionDetail]] = defaultdict(list)
        self.real_time_metrics = {
            'current_cpu_usage': 0.0,
            'current_memory_usage': 0,
            'current_memory_percent': 0.0,
            'container_cpu_usage': 0.0,
            'container_memory_usage': 0,
            'network_io': {'bytes_sent': 0, 'bytes_recv': 0},
            'disk_io': {'read_bytes': 0, 'write_bytes': 0}
        }
        
        # Error tracking and pattern analysis
        self.error_tracker = ErrorTracker()
        
        # Performance optimization tracking
        self.optimization_suggestions: List[Dict[str, Any]] = []
        
        logger.info(f"MonitoredAgent {agent_id} initialized with comprehensive monitoring")
    
    @traced("agent.start")
    def start(self):
        """Start agent with enhanced monitoring"""
        logger.info(f"Starting MonitoredAgent {self.agent_id}")
        
        # Start process monitoring
        self.process_monitor.start()
        
        # Setup container monitoring if using containers
        if self.config.container_name:
            self.container_monitor = ContainerMonitor(self.config.container_name)
            self.container_monitor.start()
        
        # Start base agent
        super().start()
        
        # Start performance profiling thread
        self._start_performance_profiling()
        
        # Record agent start in metrics
        self.metrics_collector.update_agent_status(
            agent_id=self.agent_id,
            is_running=True,
            current_tasks=0,
            health_failures=0
        )
        
        logger.info(f"MonitoredAgent {self.agent_id} started successfully")
    
    @traced("agent.stop")
    def stop(self):
        """Stop agent with monitoring cleanup"""
        logger.info(f"Stopping MonitoredAgent {self.agent_id}")
        
        # Generate final performance report
        self._generate_agent_performance_report()
        
        # Stop monitoring
        self.process_monitor.stop()
        if self.container_monitor:
            self.container_monitor.stop()
        
        # Stop base agent
        super().stop()
        
        # Update final agent status
        self.metrics_collector.update_agent_status(
            agent_id=self.agent_id,
            is_running=False,
            current_tasks=0,
            health_failures=self.health_check_failed
        )
        
        logger.info(f"MonitoredAgent {self.agent_id} stopped successfully")
    
    @traced("agent.execute_task")
    def execute_task(self, task: Task) -> TaskResult:
        """Execute task with comprehensive monitoring and profiling"""
        execution_detail = TaskExecutionDetail(
            task_id=task.task_id,
            task_type=task.task_type,
            start_time=time.time(),
            queue_time=getattr(task, 'queue_time', 0.0)
        )
        
        # Record initial resource usage
        initial_resources = self._capture_resource_snapshot()
        execution_detail.cpu_usage_start = initial_resources.get('cpu_percent', 0)
        execution_detail.memory_usage_start = initial_resources.get('memory_bytes', 0)
        
        # Start trace
        trace = self.tracing.start_trace(f"agent_{self.agent_id}_task_{task.task_type}")
        self.tracing.add_trace_tag(trace.trace_id, 'agent_id', self.agent_id)
        self.tracing.add_trace_tag(trace.trace_id, 'task_id', task.task_id)
        self.tracing.add_trace_tag(trace.trace_id, 'task_type', task.task_type)
        
        try:
            # Update agent status - task starting
            self.metrics_collector.update_agent_status(
                agent_id=self.agent_id,
                is_running=True,
                current_tasks=1,
                health_failures=self.health_check_failed
            )
            
            # Execute the task using base implementation
            result = super().execute_task(task)
            
            # Record completion details
            execution_detail.end_time = time.time()
            execution_detail.execution_time = execution_detail.end_time - execution_detail.start_time
            
            # Capture final resource usage
            final_resources = self._capture_resource_snapshot()
            execution_detail.cpu_usage_end = final_resources.get('cpu_percent', 0)
            execution_detail.memory_usage_end = final_resources.get('memory_bytes', 0)
            
            # Get container stats if available
            if self.container_monitor:
                execution_detail.container_stats = self.container_monitor.get_current_stats()
            
            # Add execution to history
            self.execution_history.append(execution_detail)
            self.task_performance_cache[task.task_type].append(execution_detail)
            
            # Update performance profile
            self._update_performance_profile(task.task_type, execution_detail, result.status == 'success')
            
            # Update agent status - task completed
            self.metrics_collector.update_agent_status(
                agent_id=self.agent_id,
                is_running=True,
                current_tasks=0,
                health_failures=self.health_check_failed,
                cpu_usage=max(0, execution_detail.cpu_usage_end - execution_detail.cpu_usage_start),
                memory_usage=max(0, execution_detail.memory_usage_end - execution_detail.memory_usage_start)
            )
            
            # Add resource usage to trace
            self.tracing.add_trace_tag(trace.trace_id, 'cpu_delta', 
                                     str(execution_detail.cpu_usage_end - execution_detail.cpu_usage_start))
            self.tracing.add_trace_tag(trace.trace_id, 'memory_delta', 
                                     str(execution_detail.memory_usage_end - execution_detail.memory_usage_start))
            self.tracing.add_trace_tag(trace.trace_id, 'execution_time', str(execution_detail.execution_time))
            
            # Finish trace
            self.tracing.finish_trace(trace.trace_id, "success")
            
            # Check for optimization opportunities
            self._analyze_optimization_opportunities(execution_detail, result)
            
            return result
            
        except Exception as e:
            # Record error details
            execution_detail.end_time = time.time()
            execution_detail.execution_time = execution_detail.end_time - execution_detail.start_time
            execution_detail.error_details = str(e)
            
            # Track error patterns
            self.error_tracker.record_error(task.task_type, str(e), execution_detail.execution_time)
            
            # Add to history even on failure
            self.execution_history.append(execution_detail)
            self.task_performance_cache[task.task_type].append(execution_detail)
            
            # Update performance profile (failure case)
            self._update_performance_profile(task.task_type, execution_detail, False)
            
            # Update agent status - task failed
            self.metrics_collector.update_agent_status(
                agent_id=self.agent_id,
                is_running=True,
                current_tasks=0,
                health_failures=self.health_check_failed
            )
            
            # Record error in metrics
            self.metrics_collector.record_error(
                error_type=type(e).__name__,
                component=f"agent_{self.agent_id}",
                severity='error',
                message=str(e)
            )
            
            # Finish trace with error
            self.tracing.finish_trace(trace.trace_id, "error", str(e))
            
            raise
    
    def _capture_resource_snapshot(self) -> Dict[str, Any]:
        """Capture current resource usage snapshot"""
        try:
            # System-level metrics
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            
            snapshot = {
                'timestamp': time.time(),
                'cpu_percent': cpu_percent,
                'memory_bytes': memory.used,
                'memory_percent': memory.percent
            }
            
            # Process-level metrics
            process_stats = self.process_monitor.get_current_stats()
            snapshot.update(process_stats)
            
            # Container-level metrics
            if self.container_monitor:
                container_stats = self.container_monitor.get_current_stats()
                snapshot['container'] = container_stats
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error capturing resource snapshot: {e}")
            return {'timestamp': time.time(), 'error': str(e)}
    
    def _update_performance_profile(self, task_type: str, execution_detail: TaskExecutionDetail, success: bool):
        """Update agent performance profile"""
        profile = self.performance_profile
        
        # Update execution times
        if task_type not in profile.avg_execution_times:
            profile.avg_execution_times[task_type] = execution_detail.execution_time
        else:
            # Exponential moving average
            current_avg = profile.avg_execution_times[task_type]
            profile.avg_execution_times[task_type] = 0.9 * current_avg + 0.1 * execution_detail.execution_time
        
        # Update success rates
        if task_type not in profile.success_rates:
            profile.success_rates[task_type] = 1.0 if success else 0.0
        else:
            # Exponential moving average
            current_rate = profile.success_rates[task_type]
            new_rate = 1.0 if success else 0.0
            profile.success_rates[task_type] = 0.95 * current_rate + 0.05 * new_rate
        
        # Update specializations (tasks with high success rate and good performance)
        if (profile.success_rates.get(task_type, 0) > 0.9 and 
            task_type not in profile.specializations):
            profile.specializations.append(task_type)
        
        # Calculate resource efficiency
        cpu_efficiency = 1.0 / max(1.0, execution_detail.cpu_usage_end - execution_detail.cpu_usage_start)
        memory_efficiency = 1.0 / max(1.0, (execution_detail.memory_usage_end - execution_detail.memory_usage_start) / 1024 / 1024)  # MB
        profile.resource_efficiency = 0.9 * profile.resource_efficiency + 0.1 * (cpu_efficiency + memory_efficiency) / 2
        
        # Update reliability score based on success
        if success:
            profile.reliability_score = min(1.0, profile.reliability_score + 0.01)
        else:
            profile.reliability_score = max(0.0, profile.reliability_score - 0.05)
        
        # Calculate throughput score
        recent_tasks = list(self.execution_history)[-10:]  # Last 10 tasks
        if len(recent_tasks) >= 2:
            time_span = recent_tasks[-1].end_time - recent_tasks[0].start_time
            if time_span > 0:
                profile.throughput_score = len(recent_tasks) / time_span
        
        profile.last_updated = time.time()
    
    def _analyze_optimization_opportunities(self, execution_detail: TaskExecutionDetail, result: TaskResult):
        """Analyze execution for optimization opportunities"""
        suggestions = []
        
        # High CPU usage detection
        cpu_delta = execution_detail.cpu_usage_end - execution_detail.cpu_usage_start
        if cpu_delta > 80:  # High CPU usage
            suggestions.append({
                'type': 'high_cpu_usage',
                'severity': 'warning',
                'message': f'Task {execution_detail.task_type} used {cpu_delta:.1f}% CPU',
                'recommendation': 'Consider task decomposition or resource allocation optimization'
            })
        
        # High memory usage detection
        memory_delta = execution_detail.memory_usage_end - execution_detail.memory_usage_start
        if memory_delta > 512 * 1024 * 1024:  # More than 512MB
            suggestions.append({
                'type': 'high_memory_usage',
                'severity': 'warning',
                'message': f'Task {execution_detail.task_type} used {memory_delta / 1024 / 1024:.1f}MB memory',
                'recommendation': 'Consider memory optimization or streaming processing'
            })
        
        # Slow execution detection
        avg_time = self.performance_profile.avg_execution_times.get(execution_detail.task_type, 0)
        if avg_time > 0 and execution_detail.execution_time > avg_time * 2:
            suggestions.append({
                'type': 'slow_execution',
                'severity': 'info',
                'message': f'Task took {execution_detail.execution_time:.2f}s vs avg {avg_time:.2f}s',
                'recommendation': 'Investigate performance bottlenecks for this task type'
            })
        
        # Add suggestions to agent's optimization list
        self.optimization_suggestions.extend(suggestions)
        
        # Keep only recent suggestions
        max_suggestions = 100
        if len(self.optimization_suggestions) > max_suggestions:
            self.optimization_suggestions = self.optimization_suggestions[-max_suggestions:]
    
    def _start_performance_profiling(self):
        """Start background performance profiling"""
        def profiling_loop():
            while self.is_running:
                try:
                    # Update real-time metrics
                    self._update_real_time_metrics()
                    
                    # Clean up old performance data
                    self._cleanup_old_performance_data()
                    
                    time.sleep(10)  # Update every 10 seconds
                    
                except Exception as e:
                    logger.error(f"Error in performance profiling loop: {e}")
                    time.sleep(10)
        
        thread = threading.Thread(target=profiling_loop, daemon=True)
        thread.start()
        logger.info(f"Performance profiling started for agent {self.agent_id}")
    
    def _update_real_time_metrics(self):
        """Update real-time performance metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            
            self.real_time_metrics.update({
                'current_cpu_usage': cpu_percent,
                'current_memory_usage': memory.used,
                'current_memory_percent': memory.percent,
                'timestamp': time.time()
            })
            
            # Process metrics
            if self.process_monitor:
                process_stats = self.process_monitor.get_current_stats()
                self.real_time_metrics['process'] = process_stats
            
            # Container metrics
            if self.container_monitor:
                container_stats = self.container_monitor.get_current_stats()
                self.real_time_metrics['container'] = container_stats
            
        except Exception as e:
            logger.error(f"Error updating real-time metrics: {e}")
    
    def _cleanup_old_performance_data(self):
        """Clean up old performance data to prevent memory leaks"""
        max_age = 24 * 3600  # 24 hours
        cutoff_time = time.time() - max_age
        
        # Clean up task performance cache
        for task_type in list(self.task_performance_cache.keys()):
            self.task_performance_cache[task_type] = [
                detail for detail in self.task_performance_cache[task_type]
                if detail.start_time > cutoff_time
            ]
            
            # Remove empty entries
            if not self.task_performance_cache[task_type]:
                del self.task_performance_cache[task_type]
        
        # Clean up optimization suggestions
        recent_suggestions = [
            s for s in self.optimization_suggestions
            if s.get('timestamp', time.time()) > cutoff_time
        ]
        self.optimization_suggestions = recent_suggestions
    
    def get_agent_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive agent performance summary"""
        return {
            'agent_id': self.agent_id,
            'performance_profile': asdict(self.performance_profile),
            'real_time_metrics': self.real_time_metrics,
            'execution_summary': {
                'total_executions': len(self.execution_history),
                'recent_executions': len([e for e in self.execution_history if time.time() - e.start_time < 3600]),
                'task_type_distribution': self._get_task_type_distribution(),
                'error_summary': self.error_tracker.get_summary()
            },
            'optimization_suggestions': self.optimization_suggestions[-10:],  # Last 10 suggestions
            'resource_efficiency_score': self._calculate_resource_efficiency_score(),
            'health_status': {
                'is_running': self.is_running,
                'health_failures': self.health_check_failed,
                'last_health_check': getattr(self, '_last_health_check', None)
            }
        }
    
    def _get_task_type_distribution(self) -> Dict[str, int]:
        """Get distribution of task types executed"""
        distribution = defaultdict(int)
        for execution in self.execution_history:
            distribution[execution.task_type] += 1
        return dict(distribution)
    
    def _calculate_resource_efficiency_score(self) -> float:
        """Calculate overall resource efficiency score"""
        if not self.execution_history:
            return 1.0
        
        # Calculate average resource usage per task
        recent_executions = list(self.execution_history)[-50:]  # Last 50 tasks
        
        total_cpu_usage = 0
        total_memory_usage = 0
        successful_tasks = 0
        
        for execution in recent_executions:
            if execution.end_time:  # Completed task
                cpu_usage = execution.cpu_usage_end - execution.cpu_usage_start
                memory_usage = execution.memory_usage_end - execution.memory_usage_start
                
                total_cpu_usage += cpu_usage
                total_memory_usage += memory_usage
                successful_tasks += 1
        
        if successful_tasks == 0:
            return 1.0
        
        # Efficiency is inverse of resource usage (lower usage = higher efficiency)
        avg_cpu_usage = total_cpu_usage / successful_tasks
        avg_memory_usage = total_memory_usage / successful_tasks / 1024 / 1024  # Convert to MB
        
        # Normalize to 0-1 scale (lower resource usage = higher score)
        cpu_efficiency = max(0, 1 - avg_cpu_usage / 100)
        memory_efficiency = max(0, 1 - avg_memory_usage / 1000)  # Assume 1GB is low efficiency
        
        return (cpu_efficiency + memory_efficiency) / 2
    
    def _generate_agent_performance_report(self):
        """Generate comprehensive performance report"""
        try:
            report = self.get_agent_performance_summary()
            
            # Add detailed execution history
            report['detailed_execution_history'] = [
                asdict(execution) for execution in list(self.execution_history)[-100:]  # Last 100 executions
            ]
            
            # Save to file
            import json
            timestamp = int(time.time())
            report_file = f"/tmp/claude_agent_{self.agent_id}_performance_report_{timestamp}.json"
            
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Agent performance report saved to {report_file}")
            
            # Log summary
            logger.info(f"=== AGENT {self.agent_id} PERFORMANCE SUMMARY ===")
            logger.info(f"Total executions: {len(self.execution_history)}")
            logger.info(f"Specializations: {', '.join(self.performance_profile.specializations)}")
            logger.info(f"Resource efficiency: {self._calculate_resource_efficiency_score():.3f}")
            logger.info(f"Reliability score: {self.performance_profile.reliability_score:.3f}")
            logger.info(f"Throughput score: {self.performance_profile.throughput_score:.3f} tasks/sec")
            logger.info(f"Optimization suggestions: {len(self.optimization_suggestions)}")
            
        except Exception as e:
            logger.error(f"Error generating agent performance report: {e}")


class ProcessMonitor:
    """Monitor process-level resource usage"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.monitoring = False
        self.current_stats = {}
        self.lock = threading.RLock()
    
    def start(self):
        """Start process monitoring"""
        self.monitoring = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
    
    def stop(self):
        """Stop process monitoring"""
        self.monitoring = False
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current process statistics"""
        with self.lock:
            return self.current_stats.copy()
    
    def _monitor_loop(self):
        """Process monitoring loop"""
        try:
            process = psutil.Process()
        except psutil.NoSuchProcess:
            logger.error(f"Cannot monitor process for agent {self.agent_id}")
            return
        
        while self.monitoring:
            try:
                with process.oneshot():
                    cpu_percent = process.cpu_percent()
                    memory_info = process.memory_info()
                    
                    with self.lock:
                        self.current_stats = {
                            'process_cpu_percent': cpu_percent,
                            'process_memory_rss': memory_info.rss,
                            'process_memory_vms': memory_info.vms,
                            'process_memory_percent': process.memory_percent(),
                            'process_num_threads': process.num_threads(),
                            'timestamp': time.time()
                        }
                
                time.sleep(5)  # Update every 5 seconds
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            except Exception as e:
                logger.error(f"Error in process monitoring: {e}")
                time.sleep(5)


class ContainerMonitor:
    """Monitor container-level resource usage"""
    
    def __init__(self, container_name: str):
        self.container_name = container_name
        self.monitoring = False
        self.current_stats = {}
        self.lock = threading.RLock()
    
    def start(self):
        """Start container monitoring"""
        self.monitoring = True
        thread = threading.Thread(target=self._monitor_loop, daemon=True)
        thread.start()
    
    def stop(self):
        """Stop container monitoring"""
        self.monitoring = False
    
    def get_current_stats(self) -> Dict[str, Any]:
        """Get current container statistics"""
        with self.lock:
            return self.current_stats.copy()
    
    def _monitor_loop(self):
        """Container monitoring loop"""
        while self.monitoring:
            try:
                # Get container stats using podman/docker
                stats = self._get_container_stats()
                
                with self.lock:
                    self.current_stats = stats
                
                time.sleep(10)  # Update every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in container monitoring: {e}")
                time.sleep(10)
    
    def _get_container_stats(self) -> Dict[str, Any]:
        """Get container statistics from runtime"""
        try:
            import subprocess
            import json
            
            # Try podman first, then docker
            for runtime in ['podman', 'docker']:
                try:
                    cmd = [runtime, 'stats', '--no-stream', '--format', 'json', self.container_name]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                    
                    if result.returncode == 0:
                        stats_data = json.loads(result.stdout)
                        return {
                            'container_cpu_percent': self._parse_cpu_percent(stats_data.get('CPUPerc', '0%')),
                            'container_memory_usage': self._parse_memory(stats_data.get('MemUsage', '0B / 0B')),
                            'container_memory_percent': self._parse_cpu_percent(stats_data.get('MemPerc', '0%')),
                            'container_network_io': stats_data.get('NetIO', '0B / 0B'),
                            'container_block_io': stats_data.get('BlockIO', '0B / 0B'),
                            'timestamp': time.time(),
                            'runtime': runtime
                        }
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            # Fallback if no container runtime available
            return {
                'error': 'No container runtime available',
                'timestamp': time.time()
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': time.time()
            }
    
    def _parse_cpu_percent(self, cpu_str: str) -> float:
        """Parse CPU percentage string"""
        try:
            return float(cpu_str.rstrip('%'))
        except (ValueError, AttributeError):
            return 0.0
    
    def _parse_memory(self, mem_str: str) -> Dict[str, int]:
        """Parse memory usage string"""
        try:
            used, total = mem_str.split(' / ')
            return {
                'used': self._parse_memory_size(used),
                'total': self._parse_memory_size(total)
            }
        except (ValueError, AttributeError):
            return {'used': 0, 'total': 0}
    
    def _parse_memory_size(self, size_str: str) -> int:
        """Parse memory size string to bytes"""
        try:
            size_str = size_str.strip()
            multipliers = {'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3}
            
            for unit, multiplier in multipliers.items():
                if size_str.endswith(unit):
                    number = float(size_str[:-len(unit)])
                    return int(number * multiplier)
            
            return int(float(size_str))
            
        except (ValueError, AttributeError):
            return 0


class ErrorTracker:
    """Track and analyze error patterns"""
    
    def __init__(self):
        self.error_history: deque = deque(maxlen=1000)
        self.error_patterns: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.lock = threading.RLock()
    
    def record_error(self, task_type: str, error_message: str, execution_time: float):
        """Record an error occurrence"""
        with self.lock:
            error_record = {
                'timestamp': time.time(),
                'task_type': task_type,
                'error_message': error_message,
                'execution_time': execution_time,
                'error_type': self._classify_error(error_message)
            }
            
            self.error_history.append(error_record)
            self.error_patterns[error_record['error_type']].append(error_record)
            
            # Keep pattern lists manageable
            for error_type in self.error_patterns:
                if len(self.error_patterns[error_type]) > 100:
                    self.error_patterns[error_type] = self.error_patterns[error_type][-100:]
    
    def _classify_error(self, error_message: str) -> str:
        """Classify error based on message content"""
        error_message_lower = error_message.lower()
        
        if 'timeout' in error_message_lower:
            return 'timeout_error'
        elif 'memory' in error_message_lower:
            return 'memory_error'
        elif 'connection' in error_message_lower:
            return 'connection_error'
        elif 'permission' in error_message_lower:
            return 'permission_error'
        elif 'not found' in error_message_lower:
            return 'not_found_error'
        else:
            return 'unknown_error'
    
    def get_summary(self) -> Dict[str, Any]:
        """Get error tracking summary"""
        with self.lock:
            return {
                'total_errors': len(self.error_history),
                'error_types': len(self.error_patterns),
                'error_type_counts': {
                    error_type: len(errors) 
                    for error_type, errors in self.error_patterns.items()
                },
                'recent_errors': list(self.error_history)[-10:]  # Last 10 errors
            }


# Factory function for easy creation
def create_monitored_agent(agent_id: str, orchestrator_socket_path: str = "/tmp/claude_orchestrator.sock",
                          config: Optional[Dict[str, Any]] = None) -> MonitoredAgent:
    """Create a monitored agent instance"""
    return MonitoredAgent(agent_id, orchestrator_socket_path, config)


# Integration helper for existing code
def enhance_agent_with_monitoring(agent: ClaudeAgent) -> MonitoredAgent:
    """Enhance an existing agent with monitoring capabilities"""
    monitored = create_monitored_agent(
        agent.agent_id,
        agent.orchestrator_socket_path,
        agent.full_config
    )
    
    # Copy relevant state if needed
    monitored.config = agent.config
    monitored.is_running = agent.is_running
    monitored.current_task = agent.current_task
    
    return monitored