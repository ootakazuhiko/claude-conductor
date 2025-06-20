#!/usr/bin/env python3
"""
Performance Monitoring Middleware and Integration for Claude Conductor

This module provides middleware and integration points for comprehensive
performance monitoring throughout the Claude Conductor system.
"""

import time
import threading
import functools
import logging
import uuid
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import json
import traceback
from concurrent.futures import ThreadPoolExecutor

from .metrics import get_metrics_collector, MetricsCollector, TaskMetrics, PerformanceMonitor
from .utils import get_system_stats

logger = logging.getLogger(__name__)


@dataclass
class TraceContext:
    """Distributed tracing context"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    operation_name: str = ""
    start_time: float = 0.0
    tags: Dict[str, str] = None
    logs: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
        if self.logs is None:
            self.logs = []
        if self.start_time == 0.0:
            self.start_time = time.time()


class TracingMiddleware:
    """Distributed tracing middleware"""
    
    def __init__(self):
        self.active_traces: Dict[str, TraceContext] = {}
        self.completed_traces: List[TraceContext] = []
        self.max_completed_traces = 1000
        self.lock = threading.RLock()
    
    def start_trace(self, operation_name: str, parent_trace_id: str = None) -> TraceContext:
        """Start a new trace"""
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        parent_span_id = parent_trace_id
        
        trace_context = TraceContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name
        )
        
        with self.lock:
            self.active_traces[trace_id] = trace_context
        
        logger.debug(f"Started trace {trace_id} for operation {operation_name}")
        return trace_context
    
    def finish_trace(self, trace_id: str, status: str = "success", error: str = None):
        """Finish a trace"""
        with self.lock:
            if trace_id not in self.active_traces:
                logger.warning(f"Trace {trace_id} not found in active traces")
                return
            
            trace = self.active_traces.pop(trace_id)
            trace.tags['status'] = status
            trace.tags['duration'] = str(time.time() - trace.start_time)
            
            if error:
                trace.tags['error'] = error
                trace.logs.append({
                    'timestamp': time.time(),
                    'level': 'error',
                    'message': error
                })
            
            self.completed_traces.append(trace)
            
            # Limit memory usage
            if len(self.completed_traces) > self.max_completed_traces:
                self.completed_traces = self.completed_traces[-self.max_completed_traces:]
        
        logger.debug(f"Finished trace {trace_id} with status {status}")
    
    def add_trace_log(self, trace_id: str, level: str, message: str, **kwargs):
        """Add a log entry to an active trace"""
        with self.lock:
            if trace_id in self.active_traces:
                self.active_traces[trace_id].logs.append({
                    'timestamp': time.time(),
                    'level': level,
                    'message': message,
                    **kwargs
                })
    
    def add_trace_tag(self, trace_id: str, key: str, value: str):
        """Add a tag to an active trace"""
        with self.lock:
            if trace_id in self.active_traces:
                self.active_traces[trace_id].tags[key] = value
    
    def get_trace_summary(self) -> Dict[str, Any]:
        """Get tracing summary"""
        with self.lock:
            return {
                'active_traces': len(self.active_traces),
                'completed_traces': len(self.completed_traces),
                'total_traces': len(self.active_traces) + len(self.completed_traces)
            }


# Global tracing middleware instance
_tracing_middleware: Optional[TracingMiddleware] = None
_tracing_lock = threading.Lock()


def get_tracing_middleware() -> TracingMiddleware:
    """Get or create the global tracing middleware instance"""
    global _tracing_middleware
    
    with _tracing_lock:
        if _tracing_middleware is None:
            _tracing_middleware = TracingMiddleware()
        return _tracing_middleware


def traced(operation_name: str = None, include_args: bool = False):
    """Decorator to add distributed tracing to functions"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            tracing = get_tracing_middleware()
            trace = tracing.start_trace(op_name)
            
            # Add function metadata
            tracing.add_trace_tag(trace.trace_id, 'function', func.__name__)
            tracing.add_trace_tag(trace.trace_id, 'module', func.__module__)
            
            if include_args:
                tracing.add_trace_tag(trace.trace_id, 'args_count', str(len(args)))
                tracing.add_trace_tag(trace.trace_id, 'kwargs_count', str(len(kwargs)))
            
            try:
                result = func(*args, **kwargs)
                tracing.finish_trace(trace.trace_id, "success")
                return result
                
            except Exception as e:
                tracing.finish_trace(trace.trace_id, "error", str(e))
                raise
        
        return wrapper
    return decorator


class PerformanceInterceptor:
    """Performance monitoring interceptor for method calls"""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        self.metrics_collector = metrics_collector or get_metrics_collector()
        self.method_stats: Dict[str, List[float]] = {}
        self.lock = threading.RLock()
    
    def intercept_method(self, instance: Any, method_name: str, original_method: Callable):
        """Intercept and monitor method calls"""
        @functools.wraps(original_method)
        def monitored_method(*args, **kwargs):
            start_time = time.time()
            method_key = f"{instance.__class__.__name__}.{method_name}"
            
            try:
                result = original_method(*args, **kwargs)
                
                # Record successful execution
                duration = time.time() - start_time
                self._record_method_performance(method_key, duration, True)
                
                self.metrics_collector.record_api_request(
                    method='method_call',
                    endpoint=method_key,
                    status_code=200,
                    duration=duration
                )
                
                return result
                
            except Exception as e:
                # Record failed execution
                duration = time.time() - start_time
                self._record_method_performance(method_key, duration, False)
                
                self.metrics_collector.record_error(
                    error_type=type(e).__name__,
                    component=instance.__class__.__name__,
                    severity='error',
                    message=str(e)
                )
                
                self.metrics_collector.record_api_request(
                    method='method_call',
                    endpoint=method_key,
                    status_code=500,
                    duration=duration
                )
                
                raise
        
        return monitored_method
    
    def _record_method_performance(self, method_key: str, duration: float, success: bool):
        """Record method performance statistics"""
        with self.lock:
            if method_key not in self.method_stats:
                self.method_stats[method_key] = []
            
            self.method_stats[method_key].append(duration)
            
            # Keep only last 100 measurements per method
            if len(self.method_stats[method_key]) > 100:
                self.method_stats[method_key] = self.method_stats[method_key][-100:]
    
    def get_method_stats(self) -> Dict[str, Dict[str, float]]:
        """Get method performance statistics"""
        with self.lock:
            stats = {}
            for method_key, durations in self.method_stats.items():
                if durations:
                    stats[method_key] = {
                        'count': len(durations),
                        'avg_duration': sum(durations) / len(durations),
                        'min_duration': min(durations),
                        'max_duration': max(durations),
                        'total_duration': sum(durations)
                    }
            return stats


class OrchestratorMonitoringMixin:
    """Mixin to add monitoring capabilities to Orchestrator"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics_collector = get_metrics_collector()
        self.performance_interceptor = PerformanceInterceptor(self.metrics_collector)
        self.performance_monitor = PerformanceMonitor(self.metrics_collector)
        self.tracing = get_tracing_middleware()
        
        # Start performance monitoring
        self.performance_monitor.start()
        
        # Intercept key methods for monitoring
        self._intercept_monitoring_methods()
    
    def _intercept_monitoring_methods(self):
        """Add monitoring to key orchestrator methods"""
        methods_to_monitor = [
            'execute_task', 'execute_parallel_task', 'start', 'stop',
            '_get_available_agent', '_update_stats'
        ]
        
        for method_name in methods_to_monitor:
            if hasattr(self, method_name):
                original_method = getattr(self, method_name)
                monitored_method = self.performance_interceptor.intercept_method(
                    self, method_name, original_method
                )
                setattr(self, method_name, monitored_method)
    
    @traced("orchestrator.execute_task")
    def execute_task_with_monitoring(self, task, **kwargs):
        """Execute task with comprehensive monitoring"""
        # Start task metrics tracking
        task_metrics = self.metrics_collector.record_task_start(
            task_id=task.task_id,
            task_type=task.task_type,
            agent_id="orchestrator",  # Will be updated when assigned to agent
            priority=getattr(task, 'priority', 5),
            queue_time=getattr(task, 'queue_time', 0.0)
        )
        
        try:
            # Add trace information
            trace = get_tracing_middleware().start_trace(f"task_execution_{task.task_type}")
            get_tracing_middleware().add_trace_tag(trace.trace_id, 'task_id', task.task_id)
            get_tracing_middleware().add_trace_tag(trace.trace_id, 'task_type', task.task_type)
            
            # Execute the original task
            result = self.execute_task(task, **kwargs)
            
            # Update metrics with final agent assignment
            if hasattr(result, 'agent_id'):
                task_metrics.agent_id = result.agent_id
            
            # Record completion
            self.metrics_collector.record_task_completion(
                task.task_id,
                result.status if hasattr(result, 'status') else 'unknown'
            )
            
            # Finish trace
            get_tracing_middleware().finish_trace(trace.trace_id, "success")
            
            return result
            
        except Exception as e:
            # Record failure
            self.metrics_collector.record_task_completion(
                task.task_id,
                'failed',
                error_type=type(e).__name__,
                error_message=str(e)
            )
            
            # Finish trace with error
            get_tracing_middleware().finish_trace(trace.trace_id, "error", str(e))
            
            raise
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive system status including metrics"""
        base_status = self.get_agent_status() if hasattr(self, 'get_agent_status') else {}
        
        return {
            'timestamp': time.time(),
            'agent_status': base_status,
            'metrics_summary': self.metrics_collector.get_metrics_summary(),
            'method_performance': self.performance_interceptor.get_method_stats(),
            'tracing_summary': self.tracing.get_trace_summary(),
            'system_stats': get_system_stats(),
            'performance_snapshots': len(self.metrics_collector.performance_snapshots)
        }
    
    def get_monitoring_endpoints(self) -> Dict[str, str]:
        """Get available monitoring endpoints"""
        return {
            '/metrics': 'Prometheus metrics endpoint',
            '/health': 'Health check endpoint',
            '/status': 'Comprehensive status endpoint',
            '/performance': 'Performance metrics endpoint',
            '/traces': 'Distributed tracing endpoint'
        }


class AgentMonitoringMixin:
    """Mixin to add monitoring capabilities to Agent"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics_collector = get_metrics_collector()
        self.performance_interceptor = PerformanceInterceptor(self.metrics_collector)
        self.tracing = get_tracing_middleware()
        self.resource_monitor = ResourceMonitor()
        
        # Intercept key methods for monitoring
        self._intercept_agent_monitoring_methods()
        
        # Start resource monitoring
        self.resource_monitor.start_monitoring(self.agent_id)
    
    def _intercept_agent_monitoring_methods(self):
        """Add monitoring to key agent methods"""
        methods_to_monitor = [
            'execute_task', 'start', 'stop', '_execute_code_review',
            '_execute_refactor', '_execute_test_generation', '_execute_analysis'
        ]
        
        for method_name in methods_to_monitor:
            if hasattr(self, method_name):
                original_method = getattr(self, method_name)
                monitored_method = self.performance_interceptor.intercept_method(
                    self, method_name, original_method
                )
                setattr(self, method_name, monitored_method)
    
    @traced("agent.execute_task")
    def execute_task_with_monitoring(self, task, **kwargs):
        """Execute task with comprehensive agent monitoring"""
        start_time = time.time()
        
        # Update agent status - starting task
        self.metrics_collector.update_agent_status(
            agent_id=self.agent_id,
            is_running=True,
            current_tasks=1,
            health_failures=getattr(self, 'health_check_failed', 0)
        )
        
        try:
            # Start trace
            trace = self.tracing.start_trace(f"agent_task_{task.task_type}")
            self.tracing.add_trace_tag(trace.trace_id, 'agent_id', self.agent_id)
            self.tracing.add_trace_tag(trace.trace_id, 'task_id', task.task_id)
            
            # Get initial resource usage
            initial_resources = self.resource_monitor.get_current_usage()
            
            # Execute task
            result = self.execute_task(task, **kwargs)
            
            # Get final resource usage
            final_resources = self.resource_monitor.get_current_usage()
            
            # Calculate resource usage delta
            cpu_usage = final_resources.get('cpu_percent', 0) - initial_resources.get('cpu_percent', 0)
            memory_usage = final_resources.get('memory_bytes', 0) - initial_resources.get('memory_bytes', 0)
            
            # Update agent status - task completed
            self.metrics_collector.update_agent_status(
                agent_id=self.agent_id,
                is_running=True,
                current_tasks=0,
                health_failures=getattr(self, 'health_check_failed', 0),
                cpu_usage=max(0, cpu_usage),
                memory_usage=max(0, memory_usage)
            )
            
            # Add resource usage to trace
            self.tracing.add_trace_tag(trace.trace_id, 'cpu_delta', str(cpu_usage))
            self.tracing.add_trace_tag(trace.trace_id, 'memory_delta', str(memory_usage))
            
            # Finish trace
            self.tracing.finish_trace(trace.trace_id, "success")
            
            return result
            
        except Exception as e:
            # Update agent status - task failed
            self.metrics_collector.update_agent_status(
                agent_id=self.agent_id,
                is_running=True,
                current_tasks=0,
                health_failures=getattr(self, 'health_check_failed', 0)
            )
            
            # Record error
            self.metrics_collector.record_error(
                error_type=type(e).__name__,
                component=f"agent_{self.agent_id}",
                severity='error',
                message=str(e)
            )
            
            # Finish trace with error
            self.tracing.finish_trace(trace.trace_id, "error", str(e))
            
            raise
    
    def get_agent_performance_stats(self) -> Dict[str, Any]:
        """Get agent-specific performance statistics"""
        return {
            'agent_id': self.agent_id,
            'resource_usage': self.resource_monitor.get_current_usage(),
            'method_performance': self.performance_interceptor.get_method_stats(),
            'active_traces': len(self.tracing.active_traces),
            'health_status': {
                'is_running': getattr(self, 'is_running', False),
                'health_failures': getattr(self, 'health_check_failed', 0),
                'last_health_check': getattr(self, '_last_health_check', None)
            }
        }


class ResourceMonitor:
    """Monitor system and process resource usage"""
    
    def __init__(self):
        self.monitoring = False
        self.agent_resources: Dict[str, Dict[str, float]] = {}
        self.lock = threading.RLock()
    
    def start_monitoring(self, agent_id: str):
        """Start monitoring resources for an agent"""
        with self.lock:
            self.agent_resources[agent_id] = {
                'cpu_percent': 0.0,
                'memory_bytes': 0.0,
                'memory_percent': 0.0,
                'last_update': time.time()
            }
        
        if not self.monitoring:
            self.monitoring = True
            threading.Thread(target=self._monitor_loop, daemon=True).start()
    
    def stop_monitoring(self, agent_id: str):
        """Stop monitoring resources for an agent"""
        with self.lock:
            if agent_id in self.agent_resources:
                del self.agent_resources[agent_id]
    
    def get_current_usage(self) -> Dict[str, float]:
        """Get current system resource usage"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            return {
                'cpu_percent': psutil.cpu_percent(interval=None),
                'memory_bytes': memory.used,
                'memory_percent': memory.percent,
                'timestamp': time.time()
            }
        except Exception as e:
            logger.error(f"Error getting resource usage: {e}")
            return {
                'cpu_percent': 0.0,
                'memory_bytes': 0.0,
                'memory_percent': 0.0,
                'timestamp': time.time()
            }
    
    def _monitor_loop(self):
        """Resource monitoring loop"""
        while self.monitoring and self.agent_resources:
            try:
                current_usage = self.get_current_usage()
                
                with self.lock:
                    for agent_id in self.agent_resources:
                        self.agent_resources[agent_id].update(current_usage)
                
                time.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in resource monitoring loop: {e}")
                time.sleep(5)


def create_monitoring_config() -> Dict[str, Any]:
    """Create default monitoring configuration"""
    return {
        'metrics': {
            'enabled': True,
            'prometheus_port': 8000,
            'update_interval': 30,
            'cleanup_interval': 3600,
            'max_metrics_age_hours': 24
        },
        'tracing': {
            'enabled': True,
            'max_active_traces': 1000,
            'max_completed_traces': 1000,
            'include_function_args': False
        },
        'performance_monitoring': {
            'enabled': True,
            'method_interception': True,
            'resource_monitoring': True,
            'snapshot_interval': 60
        },
        'alerting': {
            'enabled': False,
            'error_rate_threshold': 0.1,
            'response_time_threshold': 5.0,
            'memory_usage_threshold': 0.9,
            'cpu_usage_threshold': 0.8
        }
    }


def setup_monitoring(orchestrator_class, agent_class, config: Dict[str, Any] = None):
    """Setup monitoring for orchestrator and agent classes"""
    if config is None:
        config = create_monitoring_config()
    
    # Create monitored orchestrator class
    class MonitoredOrchestrator(OrchestratorMonitoringMixin, orchestrator_class):
        pass
    
    # Create monitored agent class
    class MonitoredAgent(AgentMonitoringMixin, agent_class):
        pass
    
    return MonitoredOrchestrator, MonitoredAgent


def generate_monitoring_report(metrics_collector: Optional[MetricsCollector] = None) -> str:
    """Generate a comprehensive monitoring report"""
    if metrics_collector is None:
        metrics_collector = get_metrics_collector()
    
    tracing = get_tracing_middleware()
    
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'metrics_summary': metrics_collector.get_metrics_summary(),
        'tracing_summary': tracing.get_trace_summary(),
        'system_stats': get_system_stats(),
        'prometheus_available': metrics_collector.enable_prometheus
    }
    
    return json.dumps(report_data, indent=2, default=str)