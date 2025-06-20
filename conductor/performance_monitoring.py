#!/usr/bin/env python3
"""
Comprehensive Performance Monitoring System for Claude Conductor
Provides real-time metrics, performance analysis, and monitoring capabilities
"""

import psutil
import time
import json
import threading
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging
import uuid
from enum import Enum
import statistics

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of performance metrics"""
    COUNTER = "counter"
    GAUGE = "gauge" 
    HISTOGRAM = "histogram"
    TIMER = "timer"

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class PerformanceMetric:
    """Individual performance metric"""
    name: str
    metric_type: MetricType
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    description: str = ""
    unit: str = ""

@dataclass
class SystemResourceMetrics:
    """System resource usage metrics"""
    cpu_percent: float
    memory_percent: float
    memory_used_bytes: int
    disk_usage_percent: float
    network_bytes_sent: int
    network_bytes_recv: int
    load_average: List[float] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

@dataclass
class TaskPerformanceMetrics:
    """Task execution performance metrics"""
    task_id: str
    agent_id: str
    task_type: str
    execution_time: float
    queue_wait_time: float
    cpu_usage_delta: float
    memory_usage_delta: int
    success: bool
    error_type: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

@dataclass
class AgentPerformanceMetrics:
    """Agent-specific performance metrics"""
    agent_id: str
    tasks_completed: int
    tasks_failed: int
    average_execution_time: float
    cpu_efficiency: float
    memory_efficiency: float
    utilization_rate: float
    specialization_score: Dict[str, float] = field(default_factory=dict)
    last_activity: float = field(default_factory=time.time)

@dataclass
class PerformanceAlert:
    """Performance alert definition"""
    alert_id: str
    name: str
    severity: AlertSeverity
    condition: str
    threshold: float
    current_value: float
    message: str
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False

class PerformanceCollector:
    """Collects and aggregates performance metrics"""
    
    def __init__(self, collection_interval: float = 1.0, max_history: int = 1000):
        self.collection_interval = collection_interval
        self.max_history = max_history
        
        # Metric storage
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self.current_metrics: Dict[str, PerformanceMetric] = {}
        self.system_metrics_history: deque = deque(maxlen=max_history)
        self.task_metrics_history: deque = deque(maxlen=max_history)
        self.agent_metrics: Dict[str, AgentPerformanceMetrics] = {}
        
        # Alert system
        self.alerts: List[PerformanceAlert] = []
        self.alert_rules: List[Dict[str, Any]] = []
        
        # Collection control
        self._collection_thread = None
        self._stop_collection = threading.Event()
        self._lock = threading.RLock()
        
        # Prometheus-style metrics
        self.prometheus_metrics = {}
        
        # Performance analysis
        self.performance_analyzer = PerformanceAnalyzer(self)
        
    def start_collection(self):
        """Start background metric collection"""
        if self._collection_thread and self._collection_thread.is_alive():
            return
        
        self._stop_collection.clear()
        self._collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True
        )
        self._collection_thread.start()
        logger.info("Performance collection started")
    
    def stop_collection(self):
        """Stop background metric collection"""
        self._stop_collection.set()
        if self._collection_thread:
            self._collection_thread.join(timeout=5)
        logger.info("Performance collection stopped")
    
    def _collection_loop(self):
        """Background collection loop"""
        while not self._stop_collection.wait(self.collection_interval):
            try:
                self._collect_system_metrics()
                self._check_alerts()
            except Exception as e:
                logger.error(f"Error in performance collection: {e}")
    
    def _collect_system_metrics(self):
        """Collect system-level performance metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=None)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Network metrics
            network = psutil.net_io_counters()
            
            # Load average (Unix-like systems)
            load_avg = []
            try:
                load_avg = list(psutil.getloadavg())
            except AttributeError:
                # Windows doesn't have load average
                pass
            
            system_metrics = SystemResourceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_bytes=memory.used,
                disk_usage_percent=disk.percent,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                load_average=load_avg
            )
            
            with self._lock:
                self.system_metrics_history.append(system_metrics)
                
                # Update current metrics
                self._update_metric("system_cpu_percent", cpu_percent, MetricType.GAUGE, "System CPU usage percentage", "%")
                self._update_metric("system_memory_percent", memory.percent, MetricType.GAUGE, "System memory usage percentage", "%")
                self._update_metric("system_memory_bytes", memory.used, MetricType.GAUGE, "System memory usage", "bytes")
                self._update_metric("system_disk_percent", disk.percent, MetricType.GAUGE, "System disk usage percentage", "%")
                
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
    
    def record_task_metrics(self, task_metrics: TaskPerformanceMetrics):
        """Record task performance metrics"""
        with self._lock:
            self.task_metrics_history.append(task_metrics)
            
            # Update agent metrics
            self._update_agent_metrics(task_metrics)
            
            # Update aggregate metrics
            self._update_metric("tasks_total", 1, MetricType.COUNTER, "Total tasks executed", "tasks", 
                              {"agent": task_metrics.agent_id, "type": task_metrics.task_type, "status": "success" if task_metrics.success else "failed"})
            
            self._update_metric("task_execution_time", task_metrics.execution_time, MetricType.HISTOGRAM, "Task execution time", "seconds",
                              {"agent": task_metrics.agent_id, "type": task_metrics.task_type})
            
            self._update_metric("task_queue_wait_time", task_metrics.queue_wait_time, MetricType.HISTOGRAM, "Task queue wait time", "seconds",
                              {"type": task_metrics.task_type})
    
    def _update_agent_metrics(self, task_metrics: TaskPerformanceMetrics):
        """Update agent-specific performance metrics"""
        agent_id = task_metrics.agent_id
        
        if agent_id not in self.agent_metrics:
            self.agent_metrics[agent_id] = AgentPerformanceMetrics(
                agent_id=agent_id,
                tasks_completed=0,
                tasks_failed=0,
                average_execution_time=0.0,
                cpu_efficiency=0.0,
                memory_efficiency=0.0,
                utilization_rate=0.0
            )
        
        agent_metrics = self.agent_metrics[agent_id]
        
        # Update task counts
        if task_metrics.success:
            agent_metrics.tasks_completed += 1
        else:
            agent_metrics.tasks_failed += 1
        
        # Update average execution time
        total_tasks = agent_metrics.tasks_completed + agent_metrics.tasks_failed
        agent_metrics.average_execution_time = (
            (agent_metrics.average_execution_time * (total_tasks - 1) + task_metrics.execution_time) / total_tasks
        )
        
        # Update specialization scores
        if task_metrics.task_type not in agent_metrics.specialization_score:
            agent_metrics.specialization_score[task_metrics.task_type] = 0.0
        
        # Calculate specialization based on success rate and execution time
        success_bonus = 1.0 if task_metrics.success else 0.0
        time_factor = max(0.1, 1.0 / max(task_metrics.execution_time, 0.1))  # Faster = better
        agent_metrics.specialization_score[task_metrics.task_type] = (
            agent_metrics.specialization_score[task_metrics.task_type] * 0.9 + 
            (success_bonus * time_factor) * 0.1
        )
        
        agent_metrics.last_activity = time.time()
    
    def _update_metric(self, name: str, value: float, metric_type: MetricType, 
                      description: str = "", unit: str = "", labels: Dict[str, str] = None):
        """Update a performance metric"""
        metric = PerformanceMetric(
            name=name,
            metric_type=metric_type,
            value=value,
            timestamp=time.time(),
            labels=labels or {},
            description=description,
            unit=unit
        )
        
        self.current_metrics[name] = metric
        self.metrics_history[name].append(metric)
    
    def get_current_metrics(self) -> Dict[str, PerformanceMetric]:
        """Get current performance metrics"""
        with self._lock:
            return self.current_metrics.copy()
    
    def get_metric_history(self, name: str, duration: Optional[float] = None) -> List[PerformanceMetric]:
        """Get historical data for a specific metric"""
        with self._lock:
            if name not in self.metrics_history:
                return []
            
            metrics = list(self.metrics_history[name])
            
            if duration is not None:
                cutoff_time = time.time() - duration
                metrics = [m for m in metrics if m.timestamp > cutoff_time]
            
            return metrics
    
    def get_system_metrics(self, duration: Optional[float] = None) -> List[SystemResourceMetrics]:
        """Get system resource metrics"""
        with self._lock:
            metrics = list(self.system_metrics_history)
            
            if duration is not None:
                cutoff_time = time.time() - duration
                metrics = [m for m in metrics if m.timestamp > cutoff_time]
            
            return metrics
    
    def get_task_metrics(self, duration: Optional[float] = None) -> List[TaskPerformanceMetrics]:
        """Get task performance metrics"""
        with self._lock:
            metrics = list(self.task_metrics_history)
            
            if duration is not None:
                cutoff_time = time.time() - duration
                metrics = [m for m in metrics if m.timestamp > cutoff_time]
            
            return metrics
    
    def get_agent_metrics(self) -> Dict[str, AgentPerformanceMetrics]:
        """Get agent performance metrics"""
        with self._lock:
            return self.agent_metrics.copy()
    
    def add_alert_rule(self, name: str, condition: str, threshold: float, 
                      severity: AlertSeverity = AlertSeverity.WARNING, message: str = ""):
        """Add performance alert rule"""
        rule = {
            'name': name,
            'condition': condition,
            'threshold': threshold,
            'severity': severity,
            'message': message or f"{condition} exceeded threshold {threshold}"
        }
        self.alert_rules.append(rule)
    
    def _check_alerts(self):
        """Check alert conditions and generate alerts"""
        current_time = time.time()
        
        for rule in self.alert_rules:
            try:
                # Evaluate condition
                current_value = self._evaluate_alert_condition(rule['condition'])
                
                if current_value is not None and current_value > rule['threshold']:
                    # Check if alert already exists and is recent
                    existing_alert = next(
                        (a for a in self.alerts 
                         if a.name == rule['name'] and not a.acknowledged and 
                         current_time - a.timestamp < 300),  # 5 minutes
                        None
                    )
                    
                    if not existing_alert:
                        alert = PerformanceAlert(
                            alert_id=str(uuid.uuid4()),
                            name=rule['name'],
                            severity=rule['severity'],
                            condition=rule['condition'],
                            threshold=rule['threshold'],
                            current_value=current_value,
                            message=rule['message']
                        )
                        self.alerts.append(alert)
                        logger.warning(f"Performance alert: {alert.message} (current: {current_value}, threshold: {rule['threshold']})")
                        
            except Exception as e:
                logger.error(f"Error checking alert rule {rule['name']}: {e}")
    
    def _evaluate_alert_condition(self, condition: str) -> Optional[float]:
        """Evaluate alert condition and return current value"""
        try:
            # Simple condition evaluation
            if condition == "cpu_percent":
                system_metrics = list(self.system_metrics_history)
                if system_metrics:
                    return system_metrics[-1].cpu_percent
            elif condition == "memory_percent":
                system_metrics = list(self.system_metrics_history)
                if system_metrics:
                    return system_metrics[-1].memory_percent
            elif condition == "task_failure_rate":
                recent_tasks = self.get_task_metrics(duration=300)  # Last 5 minutes
                if recent_tasks:
                    failed_tasks = sum(1 for t in recent_tasks if not t.success)
                    return (failed_tasks / len(recent_tasks)) * 100
            elif condition == "average_execution_time":
                recent_tasks = self.get_task_metrics(duration=300)  # Last 5 minutes
                if recent_tasks:
                    return statistics.mean(t.execution_time for t in recent_tasks)
                    
        except Exception as e:
            logger.error(f"Error evaluating condition {condition}: {e}")
        
        return None
    
    def get_active_alerts(self) -> List[PerformanceAlert]:
        """Get active (unacknowledged) alerts"""
        return [alert for alert in self.alerts if not alert.acknowledged]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        for metric in self.current_metrics.values():
            # Format metric name for Prometheus
            prometheus_name = f"claude_conductor_{metric.name.replace('-', '_')}"
            
            # Add help text
            if metric.description:
                lines.append(f"# HELP {prometheus_name} {metric.description}")
            
            # Add type
            type_mapping = {
                MetricType.COUNTER: "counter",
                MetricType.GAUGE: "gauge",
                MetricType.HISTOGRAM: "histogram",
                MetricType.TIMER: "histogram"
            }
            lines.append(f"# TYPE {prometheus_name} {type_mapping.get(metric.metric_type, 'gauge')}")
            
            # Add metric value with labels
            if metric.labels:
                label_str = ",".join(f'{k}="{v}"' for k, v in metric.labels.items())
                lines.append(f"{prometheus_name}{{{label_str}}} {metric.value} {int(metric.timestamp * 1000)}")
            else:
                lines.append(f"{prometheus_name} {metric.value} {int(metric.timestamp * 1000)}")
        
        return "\n".join(lines)

class PerformanceAnalyzer:
    """Analyzes performance data and provides insights"""
    
    def __init__(self, collector: PerformanceCollector):
        self.collector = collector
    
    def analyze_performance_trends(self, duration: float = 3600) -> Dict[str, Any]:
        """Analyze performance trends over specified duration"""
        analysis = {
            'duration': duration,
            'timestamp': time.time(),
            'system_trends': self._analyze_system_trends(duration),
            'task_trends': self._analyze_task_trends(duration),
            'agent_performance': self._analyze_agent_performance(),
            'bottlenecks': self._identify_bottlenecks(duration),
            'recommendations': self._generate_recommendations(duration)
        }
        
        return analysis
    
    def _analyze_system_trends(self, duration: float) -> Dict[str, Any]:
        """Analyze system resource trends"""
        metrics = self.collector.get_system_metrics(duration)
        if not metrics:
            return {}
        
        cpu_values = [m.cpu_percent for m in metrics]
        memory_values = [m.memory_percent for m in metrics]
        
        return {
            'cpu': {
                'average': statistics.mean(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values),
                'trend': self._calculate_trend(cpu_values)
            },
            'memory': {
                'average': statistics.mean(memory_values),
                'max': max(memory_values),
                'min': min(memory_values),
                'trend': self._calculate_trend(memory_values)
            }
        }
    
    def _analyze_task_trends(self, duration: float) -> Dict[str, Any]:
        """Analyze task execution trends"""
        metrics = self.collector.get_task_metrics(duration)
        if not metrics:
            return {}
        
        execution_times = [m.execution_time for m in metrics]
        success_rate = sum(1 for m in metrics if m.success) / len(metrics) * 100
        
        # Group by task type
        by_type = defaultdict(list)
        for m in metrics:
            by_type[m.task_type].append(m)
        
        type_analysis = {}
        for task_type, type_metrics in by_type.items():
            type_execution_times = [m.execution_time for m in type_metrics]
            type_success_rate = sum(1 for m in type_metrics if m.success) / len(type_metrics) * 100
            
            type_analysis[task_type] = {
                'count': len(type_metrics),
                'average_execution_time': statistics.mean(type_execution_times),
                'success_rate': type_success_rate,
                'trend': self._calculate_trend(type_execution_times)
            }
        
        return {
            'overall': {
                'total_tasks': len(metrics),
                'average_execution_time': statistics.mean(execution_times),
                'success_rate': success_rate,
                'execution_time_trend': self._calculate_trend(execution_times)
            },
            'by_type': type_analysis
        }
    
    def _analyze_agent_performance(self) -> Dict[str, Any]:
        """Analyze agent performance metrics"""
        agent_metrics = self.collector.get_agent_metrics()
        
        if not agent_metrics:
            return {}
        
        analysis = {}
        for agent_id, metrics in agent_metrics.items():
            total_tasks = metrics.tasks_completed + metrics.tasks_failed
            success_rate = (metrics.tasks_completed / max(total_tasks, 1)) * 100
            
            # Find best specializations
            best_specializations = sorted(
                metrics.specialization_score.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            
            analysis[agent_id] = {
                'total_tasks': total_tasks,
                'success_rate': success_rate,
                'average_execution_time': metrics.average_execution_time,
                'best_specializations': best_specializations,
                'utilization_rate': metrics.utilization_rate,
                'last_activity': metrics.last_activity
            }
        
        return analysis
    
    def _identify_bottlenecks(self, duration: float) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks"""
        bottlenecks = []
        
        # Check system resource bottlenecks
        system_metrics = self.collector.get_system_metrics(duration)
        if system_metrics:
            avg_cpu = statistics.mean(m.cpu_percent for m in system_metrics)
            avg_memory = statistics.mean(m.memory_percent for m in system_metrics)
            
            if avg_cpu > 80:
                bottlenecks.append({
                    'type': 'cpu',
                    'severity': 'high',
                    'description': f'High CPU usage: {avg_cpu:.1f}%'
                })
            
            if avg_memory > 85:
                bottlenecks.append({
                    'type': 'memory',
                    'severity': 'high',
                    'description': f'High memory usage: {avg_memory:.1f}%'
                })
        
        # Check task execution bottlenecks
        task_metrics = self.collector.get_task_metrics(duration)
        if task_metrics:
            avg_execution_time = statistics.mean(m.execution_time for m in task_metrics)
            avg_queue_time = statistics.mean(m.queue_wait_time for m in task_metrics)
            
            if avg_queue_time > avg_execution_time:
                bottlenecks.append({
                    'type': 'queue',
                    'severity': 'medium',
                    'description': f'Queue wait time ({avg_queue_time:.2f}s) exceeds execution time ({avg_execution_time:.2f}s)'
                })
        
        return bottlenecks
    
    def _generate_recommendations(self, duration: float) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []
        
        # Analyze system metrics
        system_metrics = self.collector.get_system_metrics(duration)
        if system_metrics:
            avg_cpu = statistics.mean(m.cpu_percent for m in system_metrics)
            avg_memory = statistics.mean(m.memory_percent for m in system_metrics)
            
            if avg_cpu > 70:
                recommendations.append("Consider increasing CPU resources or optimizing task execution")
            
            if avg_memory > 80:
                recommendations.append("Consider increasing memory allocation or implementing memory optimization")
        
        # Analyze task metrics
        task_metrics = self.collector.get_task_metrics(duration)
        if task_metrics:
            failure_rate = (sum(1 for m in task_metrics if not m.success) / len(task_metrics)) * 100
            
            if failure_rate > 10:
                recommendations.append("High task failure rate - investigate error patterns and improve error handling")
        
        # Analyze agent performance
        agent_metrics = self.collector.get_agent_metrics()
        if agent_metrics:
            underutilized_agents = [
                agent_id for agent_id, metrics in agent_metrics.items()
                if metrics.utilization_rate < 0.5 and time.time() - metrics.last_activity > 300
            ]
            
            if underutilized_agents:
                recommendations.append(f"Consider reducing agent count - {len(underutilized_agents)} agents are underutilized")
        
        return recommendations
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from values"""
        if len(values) < 2:
            return "stable"
        
        # Simple linear trend calculation
        n = len(values)
        x = list(range(n))
        y = values
        
        # Calculate slope
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        if slope > 0.1:
            return "increasing"
        elif slope < -0.1:
            return "decreasing"
        else:
            return "stable"

class PerformanceMonitoringMixin:
    """Mixin to add performance monitoring to orchestrator and agents"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.performance_collector = PerformanceCollector()
        self.performance_collector.start_collection()
        
        # Add default alert rules
        self._setup_default_alerts()
    
    def _setup_default_alerts(self):
        """Setup default performance alert rules"""
        self.performance_collector.add_alert_rule(
            "high_cpu_usage", "cpu_percent", 85.0, AlertSeverity.WARNING,
            "High CPU usage detected"
        )
        
        self.performance_collector.add_alert_rule(
            "high_memory_usage", "memory_percent", 90.0, AlertSeverity.CRITICAL,
            "High memory usage detected"
        )
        
        self.performance_collector.add_alert_rule(
            "high_task_failure_rate", "task_failure_rate", 15.0, AlertSeverity.WARNING,
            "High task failure rate detected"
        )
        
        self.performance_collector.add_alert_rule(
            "slow_task_execution", "average_execution_time", 300.0, AlertSeverity.WARNING,
            "Slow task execution detected"
        )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return {
            'current_metrics': {name: asdict(metric) for name, metric in self.performance_collector.get_current_metrics().items()},
            'system_metrics': [asdict(m) for m in self.performance_collector.get_system_metrics(duration=300)],
            'task_metrics': [asdict(m) for m in self.performance_collector.get_task_metrics(duration=300)],
            'agent_metrics': {aid: asdict(metrics) for aid, metrics in self.performance_collector.get_agent_metrics().items()},
            'active_alerts': [asdict(alert) for alert in self.performance_collector.get_active_alerts()],
            'analysis': self.performance_collector.performance_analyzer.analyze_performance_trends(duration=3600)
        }
    
    def stop_performance_monitoring(self):
        """Stop performance monitoring"""
        if hasattr(self, 'performance_collector'):
            self.performance_collector.stop_collection()