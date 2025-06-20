#!/usr/bin/env python3
"""
Comprehensive Performance Metrics and Monitoring for Claude Conductor

This module provides Prometheus-compatible metrics collection, performance monitoring,
and observability features for the Claude Conductor multi-agent orchestration system.
"""

import time
import threading
import psutil
import json
from typing import Dict, Any, List, Optional, Callable, Union
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import logging
import uuid
import functools

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary, Info, Enum,
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST,
        start_http_server, push_to_gateway
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create mock classes if prometheus_client not available
    class Counter:
        def __init__(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    class Histogram:
        def __init__(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
        def time(self): return self
        def labels(self, *args, **kwargs): return self
        def __enter__(self): return self
        def __exit__(self, *args): pass
    
    class Gauge:
        def __init__(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def inc(self, *args, **kwargs): pass
        def dec(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
    
    Summary = Histogram
    Info = Counter
    Enum = Counter
    CollectorRegistry = lambda: None
    generate_latest = lambda x: b"# Prometheus client not available"
    CONTENT_TYPE_LATEST = "text/plain"

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'value': self.value,
            'labels': self.labels
        }


@dataclass
class PerformanceSnapshot:
    """Performance snapshot at a point in time"""
    timestamp: float
    orchestrator_stats: Dict[str, Any]
    agent_stats: Dict[str, Any]
    system_stats: Dict[str, Any]
    task_metrics: Dict[str, Any]
    error_stats: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TaskMetrics:
    """Detailed task execution metrics"""
    task_id: str
    task_type: str
    agent_id: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    status: str = "running"
    priority: int = 5
    queue_time: float = 0.0
    execution_time: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def complete(self, status: str, error_type: str = None, error_message: str = None):
        """Mark task as complete and calculate metrics"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.status = status
        self.error_type = error_type
        self.error_message = error_message


class MetricsCollector:
    """Central metrics collection system"""
    
    def __init__(self, enable_prometheus: bool = True, registry: Optional[CollectorRegistry] = None):
        self.enable_prometheus = enable_prometheus and PROMETHEUS_AVAILABLE
        self.registry = registry or CollectorRegistry()
        self.metrics_history: deque = deque(maxlen=10000)  # Keep last 10k metrics
        self.task_metrics: Dict[str, TaskMetrics] = {}
        self.performance_snapshots: deque = deque(maxlen=1000)  # Keep last 1k snapshots
        self.start_time = time.time()
        self.lock = threading.RLock()
        
        # Initialize Prometheus metrics
        self._init_prometheus_metrics()
        
        # Internal tracking
        self._agent_states: Dict[str, Dict[str, Any]] = {}
        self._error_patterns: Dict[str, int] = defaultdict(int)
        self._queue_metrics: Dict[str, List[float]] = defaultdict(list)
        self._api_response_times: deque = deque(maxlen=1000)
        
    def _init_prometheus_metrics(self):
        """Initialize all Prometheus metrics"""
        if not self.enable_prometheus:
            return
            
        # Task metrics
        self.task_counter = Counter(
            'conductor_tasks_total',
            'Total number of tasks processed',
            ['task_type', 'status', 'agent_id'],
            registry=self.registry
        )
        
        self.task_duration = Histogram(
            'conductor_task_duration_seconds',
            'Task execution duration in seconds',
            ['task_type', 'agent_id'],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, float('inf')],
            registry=self.registry
        )
        
        self.task_queue_time = Histogram(
            'conductor_task_queue_time_seconds',
            'Time tasks spend in queue before execution',
            ['task_type', 'priority'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, float('inf')],
            registry=self.registry
        )
        
        # Agent metrics
        self.agent_status = Gauge(
            'conductor_agent_status',
            'Agent status (1=running, 0=stopped)',
            ['agent_id'],
            registry=self.registry
        )
        
        self.agent_task_count = Gauge(
            'conductor_agent_current_tasks',
            'Number of tasks currently assigned to agent',
            ['agent_id'],
            registry=self.registry
        )
        
        self.agent_health_failures = Gauge(
            'conductor_agent_health_failures',
            'Number of consecutive health check failures',
            ['agent_id'],
            registry=self.registry
        )
        
        # Resource metrics
        self.cpu_usage = Gauge(
            'conductor_cpu_usage_percent',
            'CPU usage percentage',
            ['component', 'agent_id'],
            registry=self.registry
        )
        
        self.memory_usage = Gauge(
            'conductor_memory_usage_bytes',
            'Memory usage in bytes',
            ['component', 'agent_id'],
            registry=self.registry
        )
        
        self.memory_usage_percent = Gauge(
            'conductor_memory_usage_percent',
            'Memory usage percentage',
            ['component', 'agent_id'],
            registry=self.registry
        )
        
        # Queue metrics
        self.queue_length = Gauge(
            'conductor_task_queue_length',
            'Number of tasks in queue',
            ['priority_level'],
            registry=self.registry
        )
        
        self.queue_throughput = Gauge(
            'conductor_queue_throughput_tasks_per_second',
            'Tasks processed per second',
            registry=self.registry
        )
        
        # Error metrics
        self.error_counter = Counter(
            'conductor_errors_total',
            'Total number of errors',
            ['error_type', 'component', 'severity'],
            registry=self.registry
        )
        
        # API metrics
        self.api_request_duration = Histogram(
            'conductor_api_request_duration_seconds',
            'API request duration',
            ['method', 'endpoint', 'status_code'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')],
            registry=self.registry
        )
        
        self.api_request_counter = Counter(
            'conductor_api_requests_total',
            'Total API requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        # System metrics
        self.system_info = Info(
            'conductor_system_info',
            'System information',
            registry=self.registry
        )
        
        # Set system info
        import platform
        self.system_info.info({
            'version': '2.0.0',
            'platform': platform.system(),
            'python_version': platform.python_version(),
            'architecture': platform.machine()
        })
        
        # Uptime metric
        self.uptime = Gauge(
            'conductor_uptime_seconds',
            'System uptime in seconds',
            registry=self.registry
        )
        
    def record_task_start(self, task_id: str, task_type: str, agent_id: str, 
                         priority: int = 5, queue_time: float = 0.0) -> TaskMetrics:
        """Record task start and return metrics object"""
        with self.lock:
            correlation_id = str(uuid.uuid4())
            task_metrics = TaskMetrics(
                task_id=task_id,
                task_type=task_type,
                agent_id=agent_id,
                start_time=time.time(),
                priority=priority,
                queue_time=queue_time,
                correlation_id=correlation_id
            )
            
            self.task_metrics[task_id] = task_metrics
            
            # Update Prometheus metrics
            if self.enable_prometheus:
                self.task_queue_time.labels(
                    task_type=task_type,
                    priority=str(priority)
                ).observe(queue_time)
                
            logger.debug(f"Started tracking task {task_id} with correlation ID {correlation_id}")
            return task_metrics
    
    def record_task_completion(self, task_id: str, status: str, 
                             error_type: str = None, error_message: str = None):
        """Record task completion"""
        with self.lock:
            if task_id not in self.task_metrics:
                logger.warning(f"Task {task_id} not found in metrics tracking")
                return
                
            task_metrics = self.task_metrics[task_id]
            task_metrics.complete(status, error_type, error_message)
            
            # Update Prometheus metrics
            if self.enable_prometheus:
                self.task_counter.labels(
                    task_type=task_metrics.task_type,
                    status=status,
                    agent_id=task_metrics.agent_id
                ).inc()
                
                if task_metrics.duration:
                    self.task_duration.labels(
                        task_type=task_metrics.task_type,
                        agent_id=task_metrics.agent_id
                    ).observe(task_metrics.duration)
                
                if error_type:
                    self.error_counter.labels(
                        error_type=error_type,
                        component='task_execution',
                        severity='error'
                    ).inc()
            
            # Track error patterns
            if error_type:
                self._error_patterns[error_type] += 1
                
            logger.debug(f"Completed tracking task {task_id}: {status}")
    
    def update_agent_status(self, agent_id: str, is_running: bool, 
                           current_tasks: int = 0, health_failures: int = 0,
                           cpu_usage: float = 0.0, memory_usage: float = 0.0):
        """Update agent status metrics"""
        with self.lock:
            self._agent_states[agent_id] = {
                'is_running': is_running,
                'current_tasks': current_tasks,
                'health_failures': health_failures,
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'last_update': time.time()
            }
            
            if self.enable_prometheus:
                self.agent_status.labels(agent_id=agent_id).set(1 if is_running else 0)
                self.agent_task_count.labels(agent_id=agent_id).set(current_tasks)
                self.agent_health_failures.labels(agent_id=agent_id).set(health_failures)
                
                if cpu_usage > 0:
                    self.cpu_usage.labels(component='agent', agent_id=agent_id).set(cpu_usage)
                if memory_usage > 0:
                    self.memory_usage.labels(component='agent', agent_id=agent_id).set(memory_usage)
    
    def update_queue_metrics(self, queue_length: int, priority_breakdown: Dict[str, int] = None):
        """Update task queue metrics"""
        with self.lock:
            current_time = time.time()
            
            # Track overall queue length
            self._queue_metrics['total'].append(current_time)
            
            if self.enable_prometheus:
                if priority_breakdown:
                    for priority, count in priority_breakdown.items():
                        self.queue_length.labels(priority_level=str(priority)).set(count)
                else:
                    self.queue_length.labels(priority_level='all').set(queue_length)
            
            # Calculate throughput (tasks per second)
            if len(self._queue_metrics['total']) >= 2:
                recent_times = list(self._queue_metrics['total'])[-60:]  # Last 60 measurements
                if len(recent_times) >= 2:
                    time_span = recent_times[-1] - recent_times[0]
                    if time_span > 0:
                        throughput = len(recent_times) / time_span
                        if self.enable_prometheus:
                            self.queue_throughput.set(throughput)
    
    def record_api_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record API request metrics"""
        with self.lock:
            self._api_response_times.append({
                'timestamp': time.time(),
                'method': method,
                'endpoint': endpoint,
                'status_code': status_code,
                'duration': duration
            })
            
            if self.enable_prometheus:
                self.api_request_counter.labels(
                    method=method,
                    endpoint=endpoint,
                    status_code=str(status_code)
                ).inc()
                
                self.api_request_duration.labels(
                    method=method,
                    endpoint=endpoint,
                    status_code=str(status_code)
                ).observe(duration)
    
    def record_error(self, error_type: str, component: str, severity: str = 'error', 
                    message: str = None, context: Dict[str, Any] = None):
        """Record error occurrence"""
        with self.lock:
            error_key = f"{component}:{error_type}"
            self._error_patterns[error_key] += 1
            
            if self.enable_prometheus:
                self.error_counter.labels(
                    error_type=error_type,
                    component=component,
                    severity=severity
                ).inc()
            
            logger.debug(f"Recorded error: {error_type} in {component} ({severity})")
    
    def update_system_metrics(self):
        """Update system-level metrics"""
        try:
            # Get system stats
            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            
            with self.lock:
                if self.enable_prometheus:
                    self.cpu_usage.labels(component='system', agent_id='orchestrator').set(cpu_percent)
                    self.memory_usage.labels(component='system', agent_id='orchestrator').set(memory.used)
                    self.memory_usage_percent.labels(component='system', agent_id='orchestrator').set(memory.percent)
                    self.uptime.set(time.time() - self.start_time)
                    
        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")
    
    def create_performance_snapshot(self) -> PerformanceSnapshot:
        """Create a comprehensive performance snapshot"""
        with self.lock:
            current_time = time.time()
            
            # Aggregate task metrics
            task_metrics = {
                'total_tasks': len(self.task_metrics),
                'completed_tasks': len([t for t in self.task_metrics.values() if t.status in ['success', 'failed']]),
                'running_tasks': len([t for t in self.task_metrics.values() if t.status == 'running']),
                'failed_tasks': len([t for t in self.task_metrics.values() if t.status == 'failed']),
                'avg_duration': self._calculate_avg_duration(),
                'avg_queue_time': self._calculate_avg_queue_time()
            }
            
            # System stats
            try:
                memory = psutil.virtual_memory()
                system_stats = {
                    'cpu_percent': psutil.cpu_percent(interval=None),
                    'memory_percent': memory.percent,
                    'memory_used': memory.used,
                    'memory_total': memory.total,
                    'uptime': current_time - self.start_time
                }
            except Exception:
                system_stats = {'error': 'Unable to collect system stats'}
            
            snapshot = PerformanceSnapshot(
                timestamp=current_time,
                orchestrator_stats=self._get_orchestrator_stats(),
                agent_stats=dict(self._agent_states),
                system_stats=system_stats,
                task_metrics=task_metrics,
                error_stats=dict(self._error_patterns)
            )
            
            self.performance_snapshots.append(snapshot)
            return snapshot
    
    def _calculate_avg_duration(self) -> float:
        """Calculate average task duration"""
        completed_tasks = [t for t in self.task_metrics.values() if t.duration is not None]
        if not completed_tasks:
            return 0.0
        return sum(t.duration for t in completed_tasks) / len(completed_tasks)
    
    def _calculate_avg_queue_time(self) -> float:
        """Calculate average queue time"""
        tasks_with_queue_time = [t for t in self.task_metrics.values() if t.queue_time > 0]
        if not tasks_with_queue_time:
            return 0.0
        return sum(t.queue_time for t in tasks_with_queue_time) / len(tasks_with_queue_time)
    
    def _get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get orchestrator-specific statistics"""
        return {
            'active_agents': len([a for a in self._agent_states.values() if a.get('is_running', False)]),
            'total_agents': len(self._agent_states),
            'total_errors': sum(self._error_patterns.values()),
            'uptime': time.time() - self.start_time
        }
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        with self.lock:
            return {
                'timestamp': time.time(),
                'task_metrics': {
                    'total': len(self.task_metrics),
                    'by_status': self._get_task_counts_by_status(),
                    'by_type': self._get_task_counts_by_type(),
                    'avg_duration': self._calculate_avg_duration(),
                    'avg_queue_time': self._calculate_avg_queue_time()
                },
                'agent_metrics': {
                    'total_agents': len(self._agent_states),
                    'active_agents': len([a for a in self._agent_states.values() if a.get('is_running', False)]),
                    'agents_with_tasks': len([a for a in self._agent_states.values() if a.get('current_tasks', 0) > 0]),
                    'total_health_failures': sum(a.get('health_failures', 0) for a in self._agent_states.values())
                },
                'error_metrics': {
                    'total_errors': sum(self._error_patterns.values()),
                    'error_types': len(self._error_patterns),
                    'top_errors': sorted(self._error_patterns.items(), key=lambda x: x[1], reverse=True)[:10]
                },
                'performance_metrics': {
                    'uptime': time.time() - self.start_time,
                    'snapshots_captured': len(self.performance_snapshots),
                    'api_requests_tracked': len(self._api_response_times)
                }
            }
    
    def _get_task_counts_by_status(self) -> Dict[str, int]:
        """Get task counts grouped by status"""
        counts = defaultdict(int)
        for task in self.task_metrics.values():
            counts[task.status] += 1
        return dict(counts)
    
    def _get_task_counts_by_type(self) -> Dict[str, int]:
        """Get task counts grouped by type"""
        counts = defaultdict(int)
        for task in self.task_metrics.values():
            counts[task.task_type] += 1
        return dict(counts)
    
    def get_prometheus_metrics(self) -> bytes:
        """Get Prometheus-formatted metrics"""
        if not self.enable_prometheus:
            return b"# Prometheus metrics not available"
        
        # Update system metrics before generating output
        self.update_system_metrics()
        
        return generate_latest(self.registry)
    
    def export_metrics(self, format: str = 'json', time_range: Optional[timedelta] = None) -> Union[str, bytes]:
        """Export metrics in various formats"""
        if format == 'prometheus':
            return self.get_prometheus_metrics()
        elif format == 'json':
            return json.dumps(self.get_metrics_summary(), indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def cleanup_old_metrics(self, max_age_hours: int = 24):
        """Clean up old metrics to prevent memory leaks"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        with self.lock:
            # Clean up old task metrics
            old_tasks = [tid for tid, task in self.task_metrics.items() 
                        if task.start_time < cutoff_time]
            for tid in old_tasks:
                del self.task_metrics[tid]
            
            # Clean up old API request data
            while (self._api_response_times and 
                   self._api_response_times[0]['timestamp'] < cutoff_time):
                self._api_response_times.popleft()
            
            logger.info(f"Cleaned up {len(old_tasks)} old task metrics")


# Singleton metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None
_metrics_lock = threading.Lock()


def get_metrics_collector(enable_prometheus: bool = True) -> MetricsCollector:
    """Get or create the global metrics collector instance"""
    global _metrics_collector
    
    with _metrics_lock:
        if _metrics_collector is None:
            _metrics_collector = MetricsCollector(enable_prometheus=enable_prometheus)
        return _metrics_collector


def metrics_middleware(func: Callable) -> Callable:
    """Decorator to add automatic metrics collection to functions"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        collector = get_metrics_collector()
        
        # Extract context for metrics
        func_name = func.__name__
        component = getattr(func, '__module__', 'unknown').split('.')[-1]
        
        try:
            result = func(*args, **kwargs)
            
            # Record successful execution
            duration = time.time() - start_time
            collector.record_api_request(
                method='function_call',
                endpoint=func_name,
                status_code=200,
                duration=duration
            )
            
            return result
            
        except Exception as e:
            # Record error
            duration = time.time() - start_time
            collector.record_error(
                error_type=type(e).__name__,
                component=component,
                severity='error',
                message=str(e)
            )
            
            collector.record_api_request(
                method='function_call',
                endpoint=func_name,
                status_code=500,
                duration=duration
            )
            
            raise
    
    return wrapper


class PerformanceMonitor:
    """Background performance monitoring service"""
    
    def __init__(self, collector: MetricsCollector, update_interval: int = 30):
        self.collector = collector
        self.update_interval = update_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the performance monitoring service"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("Performance monitoring service started")
    
    def stop(self):
        """Stop the performance monitoring service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Performance monitoring service stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Update system metrics
                self.collector.update_system_metrics()
                
                # Create performance snapshot
                self.collector.create_performance_snapshot()
                
                # Clean up old metrics periodically
                if int(time.time()) % 3600 == 0:  # Every hour
                    self.collector.cleanup_old_metrics()
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in performance monitoring loop: {e}")
                time.sleep(self.update_interval)


def start_prometheus_server(port: int = 8000, collector: Optional[MetricsCollector] = None):
    """Start Prometheus metrics HTTP server"""
    if not PROMETHEUS_AVAILABLE:
        logger.warning("Prometheus client not available, cannot start metrics server")
        return None
        
    if collector is None:
        collector = get_metrics_collector()
    
    try:
        # Use the collector's registry
        server = start_http_server(port, registry=collector.registry)
        logger.info(f"Prometheus metrics server started on port {port}")
        return server
    except Exception as e:
        logger.error(f"Failed to start Prometheus server: {e}")
        return None