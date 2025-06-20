#!/usr/bin/env python3
"""
Enhanced Orchestrator with Comprehensive Performance Monitoring

This module extends the base Orchestrator with comprehensive performance monitoring,
metrics collection, distributed tracing, and resource tracking capabilities.
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import uuid
from collections import defaultdict, deque

from .orchestrator import Orchestrator
from .agent import Task, TaskResult
from .metrics import get_metrics_collector, MetricsCollector
from .monitoring import (
    OrchestratorMonitoringMixin, traced, get_tracing_middleware,
    PerformanceInterceptor, ResourceMonitor
)
from .metrics_service import MetricsService, create_metrics_service

logger = logging.getLogger(__name__)


@dataclass
class QueueMetrics:
    """Task queue metrics tracking"""
    total_tasks: int = 0
    queued_tasks: int = 0
    processing_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_queue_time: float = 0.0
    avg_processing_time: float = 0.0
    throughput_per_minute: float = 0.0
    priority_distribution: Dict[int, int] = None
    
    def __post_init__(self):
        if self.priority_distribution is None:
            self.priority_distribution = defaultdict(int)


class EnhancedTaskQueue:
    """Enhanced task queue with comprehensive metrics tracking"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.queue: List[Task] = []
        self.processing: Dict[str, Task] = {}
        self.completed: deque = deque(maxlen=1000)  # Keep last 1000 completed tasks
        self.metrics_collector = get_metrics_collector()
        self.lock = threading.RLock()
        
        # Queue timing tracking
        self.enqueue_times: Dict[str, float] = {}
        self.processing_start_times: Dict[str, float] = {}
        
    def enqueue(self, task: Task, priority: int = 5) -> bool:
        """Add task to queue with priority"""
        with self.lock:
            if len(self.queue) >= self.max_size:
                logger.warning(f"Task queue is full ({self.max_size}), rejecting task {task.task_id}")
                return False
            
            task.priority = priority
            task.queue_time = 0.0  # Will be calculated when dequeued
            
            # Insert in priority order
            inserted = False
            for i, queued_task in enumerate(self.queue):
                if priority > queued_task.priority:
                    self.queue.insert(i, task)
                    inserted = True
                    break
            
            if not inserted:
                self.queue.append(task)
            
            # Track timing
            self.enqueue_times[task.task_id] = time.time()
            
            # Update metrics
            self._update_queue_metrics()
            
            logger.debug(f"Enqueued task {task.task_id} with priority {priority}")
            return True
    
    def dequeue(self) -> Optional[Task]:
        """Remove and return highest priority task"""
        with self.lock:
            if not self.queue:
                return None
            
            task = self.queue.pop(0)
            
            # Calculate queue time
            if task.task_id in self.enqueue_times:
                task.queue_time = time.time() - self.enqueue_times[task.task_id]
                del self.enqueue_times[task.task_id]
            
            # Move to processing
            self.processing[task.task_id] = task
            self.processing_start_times[task.task_id] = time.time()
            
            # Update metrics
            self._update_queue_metrics()
            
            return task
    
    def complete_task(self, task_id: str, result: TaskResult):
        """Mark task as completed"""
        with self.lock:
            if task_id in self.processing:
                task = self.processing.pop(task_id)
                
                # Calculate processing time
                if task_id in self.processing_start_times:
                    processing_time = time.time() - self.processing_start_times[task_id]
                    del self.processing_start_times[task_id]
                else:
                    processing_time = 0.0
                
                # Store completion data
                completion_data = {
                    'task': task,
                    'result': result,
                    'completion_time': time.time(),
                    'processing_time': processing_time
                }
                self.completed.append(completion_data)
                
                # Update metrics
                self._update_queue_metrics()
                
                # Record queue metrics in metrics collector
                self.metrics_collector.record_task_completion(
                    task_id,
                    result.status,
                    getattr(result, 'error_type', None),
                    getattr(result, 'error', None)
                )
    
    def get_metrics(self) -> QueueMetrics:
        """Get current queue metrics"""
        with self.lock:
            # Calculate averages from recent completions
            recent_completions = list(self.completed)[-100:]  # Last 100 tasks
            
            avg_queue_time = 0.0
            avg_processing_time = 0.0
            if recent_completions:
                queue_times = [c['task'].queue_time for c in recent_completions if hasattr(c['task'], 'queue_time')]
                processing_times = [c['processing_time'] for c in recent_completions]
                
                if queue_times:
                    avg_queue_time = sum(queue_times) / len(queue_times)
                if processing_times:
                    avg_processing_time = sum(processing_times) / len(processing_times)
            
            # Calculate throughput (tasks per minute)
            throughput_per_minute = 0.0
            if len(recent_completions) >= 2:
                time_span = recent_completions[-1]['completion_time'] - recent_completions[0]['completion_time']
                if time_span > 0:
                    throughput_per_minute = (len(recent_completions) / time_span) * 60
            
            # Priority distribution
            priority_dist = defaultdict(int)
            for task in self.queue:
                priority_dist[task.priority] += 1
            
            return QueueMetrics(
                total_tasks=len(self.queue) + len(self.processing) + len(self.completed),
                queued_tasks=len(self.queue),
                processing_tasks=len(self.processing),
                completed_tasks=len(self.completed),
                failed_tasks=len([c for c in recent_completions if c['result'].status == 'failed']),
                avg_queue_time=avg_queue_time,
                avg_processing_time=avg_processing_time,
                throughput_per_minute=throughput_per_minute,
                priority_distribution=dict(priority_dist)
            )
    
    def _update_queue_metrics(self):
        """Update queue metrics in metrics collector"""
        metrics = self.get_metrics()
        
        # Update Prometheus metrics
        self.metrics_collector.update_queue_metrics(
            queue_length=metrics.queued_tasks,
            priority_breakdown=metrics.priority_distribution
        )


class MonitoredOrchestrator(OrchestratorMonitoringMixin, Orchestrator):
    """Orchestrator with comprehensive performance monitoring"""
    
    def __init__(self, config_path: Optional[str] = None, enable_metrics_service: bool = True):
        # Initialize monitoring first
        self.metrics_collector = get_metrics_collector()
        self.tracing = get_tracing_middleware()
        
        # Initialize base orchestrator
        super().__init__(config_path)
        
        # Replace simple task queue with enhanced queue
        self.task_queue = EnhancedTaskQueue(
            max_size=self.config.get('task_queue', {}).get('max_size', 1000)
        )
        
        # Enhanced statistics tracking
        self.detailed_stats = {
            'agent_utilization': defaultdict(float),
            'task_type_performance': defaultdict(list),
            'error_patterns': defaultdict(int),
            'resource_usage_history': deque(maxlen=1440),  # 24 hours at 1-minute intervals
            'peak_performance_metrics': {
                'max_concurrent_tasks': 0,
                'peak_cpu_usage': 0.0,
                'peak_memory_usage': 0.0,
                'fastest_task_completion': float('inf'),
                'highest_throughput': 0.0
            }
        }
        
        # Resource monitoring
        self.resource_monitor = ResourceMonitor()
        
        # Metrics service
        self.metrics_service: Optional[MetricsService] = None
        if enable_metrics_service:
            self._setup_metrics_service()
        
        # Performance monitoring thread
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_enabled = True
        
        logger.info("MonitoredOrchestrator initialized with comprehensive monitoring")
    
    def _setup_metrics_service(self):
        """Setup the metrics service"""
        try:
            metrics_config = self.config.get('metrics', {})
            service_config = {
                'prometheus': {
                    'enabled': metrics_config.get('prometheus_enabled', True),
                    'port': metrics_config.get('prometheus_port', 8000)
                },
                'api': {
                    'enabled': metrics_config.get('api_enabled', True),
                    'host': metrics_config.get('api_host', '0.0.0.0'),
                    'port': metrics_config.get('api_port', 8080),
                    'authentication': metrics_config.get('api_authentication', False)
                }
            }
            
            self.metrics_service = create_metrics_service(service_config)
            logger.info("Metrics service configured")
            
        except Exception as e:
            logger.error(f"Failed to setup metrics service: {e}")
            self.metrics_service = None
    
    @traced("orchestrator.start")
    def start(self):
        """Start orchestrator with monitoring"""
        logger.info("Starting MonitoredOrchestrator")
        
        # Start metrics service first
        if self.metrics_service:
            try:
                service_info = self.metrics_service.start()
                logger.info(f"Metrics service started: {service_info}")
            except Exception as e:
                logger.error(f"Failed to start metrics service: {e}")
        
        # Start base orchestrator
        super().start()
        
        # Start monitoring thread
        self._start_monitoring_thread()
        
        # Record start metrics
        self.metrics_collector.update_system_metrics()
        
        logger.info("MonitoredOrchestrator started successfully")
    
    @traced("orchestrator.stop")
    def stop(self):
        """Stop orchestrator with cleanup"""
        logger.info("Stopping MonitoredOrchestrator")
        
        # Stop monitoring
        self.monitoring_enabled = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        # Stop base orchestrator
        super().stop()
        
        # Stop metrics service
        if self.metrics_service:
            try:
                self.metrics_service.stop()
                logger.info("Metrics service stopped")
            except Exception as e:
                logger.error(f"Error stopping metrics service: {e}")
        
        # Generate final report
        self._generate_final_performance_report()
        
        logger.info("MonitoredOrchestrator stopped successfully")
    
    @traced("orchestrator.execute_task")
    def execute_task(self, task: Task) -> TaskResult:
        """Execute task with comprehensive monitoring"""
        correlation_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Start task metrics tracking
        task_metrics = self.metrics_collector.record_task_start(
            task_id=task.task_id,
            task_type=task.task_type,
            agent_id="pending",  # Will be updated when agent is assigned
            priority=getattr(task, 'priority', 5),
            queue_time=0.0  # Will be calculated by queue
        )
        
        # Add to enhanced queue instead of simple list
        if not self.task_queue.enqueue(task, getattr(task, 'priority', 5)):
            # Queue is full
            error_result = TaskResult(
                task_id=task.task_id,
                agent_id="orchestrator",
                status="failed",
                result={},
                error="Task queue is full",
                execution_time=0.0
            )
            
            self.metrics_collector.record_task_completion(
                task.task_id,
                "failed",
                error_type="QueueFullError",
                error_message="Task queue is full"
            )
            
            return error_result
        
        try:
            # Get task from queue (this calculates queue time)
            queued_task = self.task_queue.dequeue()
            if not queued_task:
                raise Exception("Task disappeared from queue")
            
            # Update metrics with queue time
            task_metrics.queue_time = queued_task.queue_time
            
            # Find available agent
            agent = self._get_available_agent()
            if not agent:
                error_result = TaskResult(
                    task_id=task.task_id,
                    agent_id="none",
                    status="failed",
                    result={},
                    error="No available agents",
                    execution_time=time.time() - start_time
                )
                
                self.task_queue.complete_task(task.task_id, error_result)
                self._update_detailed_stats(task, error_result, "no_agent")
                
                return error_result
            
            # Update task metrics with assigned agent
            task_metrics.agent_id = agent.agent_id
            
            # Execute task with timeout and monitoring
            future = self.executor.submit(agent.execute_task, queued_task)
            
            try:
                result = future.result(timeout=queued_task.timeout)
                
                # Update agent utilization
                self._update_agent_utilization(agent.agent_id, result.execution_time)
                
                # Record successful completion
                self.task_queue.complete_task(task.task_id, result)
                self._update_detailed_stats(queued_task, result, "success")
                
                return result
                
            except TimeoutError:
                future.cancel()
                result = TaskResult(
                    task_id=task.task_id,
                    agent_id=agent.agent_id,
                    status="timeout",
                    result={},
                    error=f"Task execution timeout after {queued_task.timeout}s",
                    execution_time=queued_task.timeout
                )
                
                self.task_queue.complete_task(task.task_id, result)
                self._update_detailed_stats(queued_task, result, "timeout")
                
                return result
                
        except Exception as e:
            execution_time = time.time() - start_time
            error_result = TaskResult(
                task_id=task.task_id,
                agent_id="orchestrator",
                status="failed",
                result={},
                error=str(e),
                execution_time=execution_time
            )
            
            if hasattr(self, 'task_queue') and hasattr(self.task_queue, 'complete_task'):
                self.task_queue.complete_task(task.task_id, error_result)
            
            self._update_detailed_stats(task, error_result, "error")
            
            # Record error pattern
            self.detailed_stats['error_patterns'][type(e).__name__] += 1
            
            return error_result
    
    def _update_agent_utilization(self, agent_id: str, execution_time: float):
        """Update agent utilization metrics"""
        # Simple utilization calculation (can be enhanced)
        current_util = self.detailed_stats['agent_utilization'][agent_id]
        # Exponential moving average
        self.detailed_stats['agent_utilization'][agent_id] = 0.9 * current_util + 0.1 * execution_time
        
        # Update metrics collector
        self.metrics_collector.update_agent_status(
            agent_id=agent_id,
            is_running=True,
            current_tasks=0,  # Will be updated by agent monitoring
            health_failures=0
        )
    
    def _update_detailed_stats(self, task: Task, result: TaskResult, category: str):
        """Update detailed performance statistics"""
        # Task type performance tracking
        self.detailed_stats['task_type_performance'][task.task_type].append({
            'execution_time': result.execution_time,
            'status': result.status,
            'timestamp': time.time(),
            'category': category
        })
        
        # Keep only recent performance data
        max_entries = 1000
        if len(self.detailed_stats['task_type_performance'][task.task_type]) > max_entries:
            self.detailed_stats['task_type_performance'][task.task_type] = \
                self.detailed_stats['task_type_performance'][task.task_type][-max_entries:]
        
        # Update peak performance metrics
        peaks = self.detailed_stats['peak_performance_metrics']
        
        if result.execution_time < peaks['fastest_task_completion'] and result.status == 'success':
            peaks['fastest_task_completion'] = result.execution_time
        
        # Calculate current throughput
        queue_metrics = self.task_queue.get_metrics()
        if queue_metrics.throughput_per_minute > peaks['highest_throughput']:
            peaks['highest_throughput'] = queue_metrics.throughput_per_minute
    
    def _start_monitoring_thread(self):
        """Start background monitoring thread"""
        def monitoring_loop():
            while self.monitoring_enabled:
                try:
                    # Update system metrics
                    self.metrics_collector.update_system_metrics()
                    
                    # Create performance snapshot
                    self.metrics_collector.create_performance_snapshot()
                    
                    # Update resource usage history
                    self._record_resource_usage()
                    
                    # Update peak metrics
                    self._update_peak_metrics()
                    
                    # Sleep for monitoring interval
                    time.sleep(self.config.get('monitoring', {}).get('update_interval', 30))
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(30)
        
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("Monitoring thread started")
    
    def _record_resource_usage(self):
        """Record current resource usage"""
        try:
            from .utils import get_system_stats
            system_stats = get_system_stats()
            
            resource_point = {
                'timestamp': time.time(),
                'cpu_percent': system_stats.get('cpu_percent', 0),
                'memory_percent': system_stats.get('memory_percent', 0),
                'memory_used': system_stats.get('memory_used', 0),
                'active_agents': len([a for a in self.agents.values() if a.is_running]),
                'queue_length': len(self.task_queue.queue) if hasattr(self.task_queue, 'queue') else 0
            }
            
            self.detailed_stats['resource_usage_history'].append(resource_point)
            
        except Exception as e:
            logger.error(f"Error recording resource usage: {e}")
    
    def _update_peak_metrics(self):
        """Update peak performance metrics"""
        try:
            peaks = self.detailed_stats['peak_performance_metrics']
            
            # Current concurrent tasks
            current_concurrent = len(self.task_queue.processing) if hasattr(self.task_queue, 'processing') else 0
            if current_concurrent > peaks['max_concurrent_tasks']:
                peaks['max_concurrent_tasks'] = current_concurrent
            
            # CPU and memory usage
            if self.detailed_stats['resource_usage_history']:
                latest = self.detailed_stats['resource_usage_history'][-1]
                if latest['cpu_percent'] > peaks['peak_cpu_usage']:
                    peaks['peak_cpu_usage'] = latest['cpu_percent']
                if latest['memory_percent'] > peaks['peak_memory_usage']:
                    peaks['peak_memory_usage'] = latest['memory_percent']
                    
        except Exception as e:
            logger.error(f"Error updating peak metrics: {e}")
    
    def get_comprehensive_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        base_stats = self.get_statistics() if hasattr(self, 'get_statistics') else {}
        queue_metrics = self.task_queue.get_metrics()
        
        # Calculate task type averages
        task_type_averages = {}
        for task_type, performances in self.detailed_stats['task_type_performance'].items():
            if performances:
                successful = [p for p in performances if p['status'] == 'success']
                if successful:
                    avg_time = sum(p['execution_time'] for p in successful) / len(successful)
                    success_rate = len(successful) / len(performances)
                    task_type_averages[task_type] = {
                        'avg_execution_time': avg_time,
                        'success_rate': success_rate,
                        'total_tasks': len(performances),
                        'successful_tasks': len(successful)
                    }
        
        return {
            'timestamp': time.time(),
            'base_statistics': base_stats,
            'queue_metrics': queue_metrics.__dict__,
            'detailed_statistics': {
                'agent_utilization': dict(self.detailed_stats['agent_utilization']),
                'task_type_performance': task_type_averages,
                'error_patterns': dict(self.detailed_stats['error_patterns']),
                'peak_metrics': self.detailed_stats['peak_performance_metrics'],
                'resource_usage_trend': list(self.detailed_stats['resource_usage_history'])[-100:]  # Last 100 points
            },
            'monitoring_service_status': self.metrics_service.get_status() if self.metrics_service else None,
            'metrics_summary': self.metrics_collector.get_metrics_summary(),
            'tracing_summary': self.tracing.get_trace_summary()
        }
    
    def _generate_final_performance_report(self):
        """Generate and log final performance report"""
        try:
            report = self.get_comprehensive_performance_report()
            
            # Save to file
            import json
            timestamp = int(time.time())
            report_file = f"/tmp/claude_conductor_performance_report_{timestamp}.json"
            
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Performance report saved to {report_file}")
            
            # Log summary
            logger.info("=== FINAL PERFORMANCE SUMMARY ===")
            logger.info(f"Total runtime: {report['base_statistics'].get('runtime', 0):.2f}s")
            logger.info(f"Tasks completed: {report['base_statistics'].get('tasks_completed', 0)}")
            logger.info(f"Tasks failed: {report['base_statistics'].get('tasks_failed', 0)}")
            logger.info(f"Peak concurrent tasks: {report['detailed_statistics']['peak_metrics']['max_concurrent_tasks']}")
            logger.info(f"Peak CPU usage: {report['detailed_statistics']['peak_metrics']['peak_cpu_usage']:.1f}%")
            logger.info(f"Peak memory usage: {report['detailed_statistics']['peak_metrics']['peak_memory_usage']:.1f}%")
            logger.info(f"Fastest task: {report['detailed_statistics']['peak_metrics']['fastest_task_completion']:.3f}s")
            logger.info(f"Highest throughput: {report['detailed_statistics']['peak_metrics']['highest_throughput']:.1f} tasks/min")
            
        except Exception as e:
            logger.error(f"Error generating final performance report: {e}")


# Factory function for easy creation
def create_monitored_orchestrator(config_path: Optional[str] = None, 
                                enable_metrics_service: bool = True) -> MonitoredOrchestrator:
    """Create a monitored orchestrator instance"""
    return MonitoredOrchestrator(config_path, enable_metrics_service)


# Integration helper for existing code
def enhance_orchestrator_with_monitoring(orchestrator: Orchestrator) -> MonitoredOrchestrator:
    """Enhance an existing orchestrator with monitoring capabilities"""
    # This is a simplified approach - in practice, you might want to migrate state
    config_path = getattr(orchestrator, 'config_path', None)
    monitored = create_monitored_orchestrator(config_path)
    
    # Copy relevant state if needed
    monitored.config = orchestrator.config
    monitored.agents = orchestrator.agents
    
    return monitored