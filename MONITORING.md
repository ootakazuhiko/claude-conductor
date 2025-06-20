# Claude Conductor Comprehensive Performance Monitoring

This document provides a complete guide to the comprehensive performance monitoring system implemented for Claude Conductor, including setup, usage, and advanced features.

## Overview

The Claude Conductor monitoring system provides:

- **Prometheus-compatible metrics** with detailed performance data
- **Distributed tracing** with correlation IDs across agents
- **Real-time dashboards** with live performance visualization
- **HTTP API endpoints** for metrics access and analysis
- **Resource utilization tracking** at system and container levels
- **Queue performance monitoring** with backlog analysis
- **Error pattern analysis** and categorization
- **Agent performance profiling** and optimization suggestions
- **Health monitoring** with automatic alerting
- **Performance snapshots** for historical analysis

## Quick Start

### Basic Setup

```python
from conductor.monitored_orchestrator import create_monitored_orchestrator
from conductor.metrics_service import create_metrics_service

# Create monitored orchestrator with metrics service
orchestrator = create_monitored_orchestrator(enable_metrics_service=True)

# Start the system
orchestrator.start()

# Execute tasks as normal - monitoring is automatic
task = create_task(task_type="code_review", description="Review security")
result = orchestrator.execute_task(task)

# Stop when done
orchestrator.stop()
```

### Enhanced Dashboard

```python
from conductor.enhanced_dashboard import run_enhanced_dashboard

# Run the enhanced dashboard (requires FastAPI)
run_enhanced_dashboard(
    orchestrator=orchestrator,
    port=8080,
    open_browser=True
)
```

## Architecture

### Components

1. **MetricsCollector** (`conductor/metrics.py`)
   - Central metrics collection and Prometheus export
   - Task execution tracking with detailed timing
   - Resource usage monitoring
   - Error pattern analysis

2. **TracingMiddleware** (`conductor/monitoring.py`)
   - Distributed tracing with correlation IDs
   - Operation-level performance tracking
   - Cross-agent request correlation

3. **MetricsService** (`conductor/metrics_service.py`)
   - HTTP API for metrics access
   - Real-time data streaming
   - Export capabilities (JSON, Prometheus)

4. **MonitoredOrchestrator** (`conductor/monitored_orchestrator.py`)
   - Enhanced orchestrator with integrated monitoring
   - Queue performance tracking
   - Agent utilization analysis

5. **MonitoredAgent** (`conductor/monitored_agent.py`)
   - Agent with comprehensive resource monitoring
   - Task execution profiling
   - Container-level metrics

6. **EnhancedDashboard** (`conductor/enhanced_dashboard.py`)
   - Real-time web dashboard
   - Performance visualization
   - Alert management

### Data Flow

```
Task Execution → MetricsCollector → {
  ├── Prometheus Metrics
  ├── HTTP API Endpoints
  ├── Real-time Dashboard
  └── Performance Snapshots
}

Agent Operations → TracingMiddleware → {
  ├── Distributed Traces
  ├── Correlation IDs
  └── Operation Timing
}

System Resources → ResourceMonitor → {
  ├── CPU/Memory Usage
  ├── Container Stats
  └── Process Monitoring
}
```

## Metrics Reference

### Task Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `conductor_tasks_total` | Counter | Total tasks processed | `task_type`, `status`, `agent_id` |
| `conductor_task_duration_seconds` | Histogram | Task execution duration | `task_type`, `agent_id` |
| `conductor_task_queue_time_seconds` | Histogram | Time in queue before execution | `task_type`, `priority` |

### Agent Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `conductor_agent_status` | Gauge | Agent status (1=running, 0=stopped) | `agent_id` |
| `conductor_agent_current_tasks` | Gauge | Current tasks assigned to agent | `agent_id` |
| `conductor_agent_health_failures` | Gauge | Consecutive health check failures | `agent_id` |

### Resource Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `conductor_cpu_usage_percent` | Gauge | CPU usage percentage | `component`, `agent_id` |
| `conductor_memory_usage_bytes` | Gauge | Memory usage in bytes | `component`, `agent_id` |
| `conductor_memory_usage_percent` | Gauge | Memory usage percentage | `component`, `agent_id` |

### Queue Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `conductor_task_queue_length` | Gauge | Number of tasks in queue | `priority_level` |
| `conductor_queue_throughput_tasks_per_second` | Gauge | Tasks processed per second | - |

### Error Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `conductor_errors_total` | Counter | Total number of errors | `error_type`, `component`, `severity` |

### API Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `conductor_api_request_duration_seconds` | Histogram | API request duration | `method`, `endpoint`, `status_code` |
| `conductor_api_requests_total` | Counter | Total API requests | `method`, `endpoint`, `status_code` |

## HTTP API Endpoints

### Core Endpoints

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics
- `GET /api/v1/metrics/summary` - Comprehensive metrics summary

### Task Metrics

- `GET /api/v1/metrics/tasks` - Task execution metrics
- `GET /api/v1/metrics/tasks?status=success` - Filter by status
- `GET /api/v1/metrics/tasks?task_type=code_review` - Filter by type

### Agent Metrics

- `GET /api/v1/metrics/agents` - Agent performance data
- `GET /api/v1/metrics/agents/{agent_id}` - Specific agent metrics

### System Metrics

- `GET /api/v1/metrics/system` - System resource usage
- `GET /api/v1/metrics/performance/snapshots` - Performance snapshots

### Real-time Data

- `GET /api/v1/metrics/real-time` - Real-time metrics stream
- `GET /api/v1/metrics/real-time?metric_name=cpu_usage` - Specific metric
- `WebSocket /ws/dashboard` - Real-time dashboard updates

### Distributed Tracing

- `GET /api/v1/metrics/traces` - Trace data
- `GET /api/v1/metrics/traces/{trace_id}` - Specific trace details

### Data Export

- `GET /api/v1/metrics/export` - Export all metrics (JSON)
- `GET /api/v1/metrics/export?format=prometheus` - Prometheus format
- `GET /api/v1/metrics/export?compress=true` - Compressed export

## Configuration

### Basic Configuration

```yaml
# config/monitoring.yaml
metrics:
  prometheus_enabled: true
  prometheus_port: 8000
  api_enabled: true
  api_host: "0.0.0.0"
  api_port: 8080
  api_authentication: false

monitoring:
  update_interval: 30        # Metrics update interval (seconds)
  cleanup_interval: 3600     # Old data cleanup interval (seconds)
  max_metrics_age_hours: 24  # Maximum age for metrics retention

task_queue:
  max_size: 1000
  priority_levels: 10

alerting:
  enabled: true
  cpu_usage_threshold: 80.0
  memory_usage_threshold: 85.0
  error_rate_threshold: 10.0
  response_time_threshold: 5000.0
  queue_backlog_threshold: 100
```

### Advanced Configuration

```python
from conductor.metrics_service import create_metrics_service

# Custom metrics service configuration
metrics_config = {
    'prometheus': {
        'enabled': True,
        'port': 8000,
        'push_gateway': 'http://prometheus-pushgateway:9091'
    },
    'api': {
        'enabled': True,
        'host': '0.0.0.0',
        'port': 8080,
        'authentication': True,
        'api_key': 'your-secure-api-key'
    },
    'monitoring': {
        'update_interval': 15,
        'cleanup_interval': 3600,
        'max_metrics_age_hours': 48
    }
}

metrics_service = create_metrics_service(metrics_config)
```

## Dashboard Features

### Enhanced Dashboard Views

1. **System Health Overview**
   - Overall health score calculation
   - Component health breakdown
   - Real-time status indicators

2. **Real-time Performance Charts**
   - CPU and memory usage trends
   - Task throughput visualization
   - Error rate monitoring

3. **Agent Performance Analysis**
   - Individual agent metrics
   - Performance profiling
   - Resource efficiency scores

4. **Alert Management**
   - Active alert display
   - Threshold configuration
   - Alert history

5. **Queue Monitoring**
   - Queue length trends
   - Processing time analysis
   - Backlog alerts

### Accessing the Dashboard

```bash
# Start enhanced dashboard
python -m conductor.enhanced_dashboard --port 8080

# Or programmatically
from conductor.enhanced_dashboard import run_enhanced_dashboard
run_enhanced_dashboard(orchestrator=orchestrator, port=8080)
```

## Distributed Tracing

### Trace Context

Every operation gets a unique trace context:

```python
from conductor.monitoring import traced

@traced("custom_operation")
def my_function():
    # Function is automatically traced
    pass

# Manual tracing
from conductor.monitoring import get_tracing_middleware

tracing = get_tracing_middleware()
trace = tracing.start_trace("my_operation")
tracing.add_trace_tag(trace.trace_id, "key", "value")
# ... do work ...
tracing.finish_trace(trace.trace_id, "success")
```

### Correlation IDs

Traces are automatically correlated across:
- Task execution
- Agent operations
- API requests
- Error handling

## Performance Analysis

### Agent Performance Profiling

```python
# Get agent performance summary
agent = create_monitored_agent("agent_001")
performance_summary = agent.get_agent_performance_summary()

print(f"Resource efficiency: {performance_summary['resource_efficiency_score']:.2f}")
print(f"Specializations: {performance_summary['performance_profile']['specializations']}")
print(f"Success rates: {performance_summary['performance_profile']['success_rates']}")
```

### Task Type Analysis

```python
# Get task type performance breakdown
orchestrator = create_monitored_orchestrator()
performance_report = orchestrator.get_comprehensive_performance_report()

task_performance = performance_report['detailed_statistics']['task_type_performance']
for task_type, metrics in task_performance.items():
    print(f"{task_type}: {metrics['avg_execution_time']:.3f}s avg, {metrics['success_rate']:.1%} success")
```

### Resource Optimization

The system automatically identifies optimization opportunities:

```python
# Get optimization suggestions
agent_summary = agent.get_agent_performance_summary()
suggestions = agent_summary['optimization_suggestions']

for suggestion in suggestions:
    print(f"{suggestion['type']}: {suggestion['message']}")
    print(f"Recommendation: {suggestion['recommendation']}")
```

## Integration with Existing Systems

### Prometheus Integration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'claude-conductor'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 15s
    metrics_path: /metrics
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Claude Conductor Monitoring",
    "panels": [
      {
        "title": "Task Execution Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(conductor_tasks_total[5m])",
            "legendFormat": "Tasks/sec"
          }
        ]
      }
    ]
  }
}
```

### Kubernetes Monitoring

The system includes Kubernetes monitoring configurations:

```yaml
# k8s/monitoring.yaml - Already included in the project
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: claude-conductor-orchestrator
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: claude-conductor
  endpoints:
  - port: metrics
    path: /metrics
    interval: 30s
```

## Troubleshooting

### Common Issues

1. **Metrics not appearing in Prometheus**
   ```bash
   # Check if metrics endpoint is accessible
   curl http://localhost:8000/metrics
   
   # Verify Prometheus configuration
   curl http://localhost:9090/api/v1/targets
   ```

2. **Dashboard not loading data**
   ```bash
   # Check API endpoints
   curl http://localhost:8080/api/v1/metrics/summary
   
   # Verify WebSocket connection
   # Check browser console for errors
   ```

3. **High memory usage**
   ```python
   # Clean up old metrics
   from conductor.metrics import get_metrics_collector
   collector = get_metrics_collector()
   collector.cleanup_old_metrics(max_age_hours=12)
   ```

4. **Missing container metrics**
   ```bash
   # Verify container runtime
   podman --version
   # or
   docker --version
   
   # Check container permissions
   podman stats --no-stream
   ```

### Performance Tuning

1. **Reduce metrics granularity**
   ```python
   # Adjust collection intervals
   config = {
       'monitoring': {
           'update_interval': 60,  # Increase from 30s
           'snapshot_interval': 120,  # Increase from 60s
       }
   }
   ```

2. **Limit metrics retention**
   ```python
   # Reduce history size
   collector = get_metrics_collector()
   collector.performance_snapshots.maxlen = 500  # Default: 1000
   collector.task_metrics = {}  # Clear if needed
   ```

3. **Optimize dashboard updates**
   ```javascript
   // Reduce WebSocket update frequency
   await asyncio.sleep(10)  // Increase from 5 seconds
   ```

## Examples

### Complete Monitoring Setup

```python
from conductor.monitored_orchestrator import create_monitored_orchestrator
from conductor.metrics_service import create_metrics_service
from conductor.enhanced_dashboard import run_enhanced_dashboard

# Create configuration
config = {
    'num_agents': 3,
    'metrics': {
        'prometheus_enabled': True,
        'prometheus_port': 8000,
        'api_enabled': True,
        'api_port': 8080
    }
}

# Create and start monitored orchestrator
orchestrator = create_monitored_orchestrator()
orchestrator.config.update(config)
orchestrator.start()

# Execute tasks with monitoring
task = create_task(task_type="code_review", description="Security review")
result = orchestrator.execute_task(task)

# Get comprehensive performance report
report = orchestrator.get_comprehensive_performance_report()
print(f"Task completed in {result.execution_time:.3f}s")
print(f"System health: {report['system_health']['overall_score']}")

# Run dashboard
run_enhanced_dashboard(orchestrator=orchestrator, port=8080)

# Clean shutdown
orchestrator.stop()
```

### Custom Metrics

```python
from conductor.metrics import get_metrics_collector

collector = get_metrics_collector()

# Record custom task metrics
collector.record_task_start("custom_task_1", "analysis", "agent_001")
# ... do work ...
collector.record_task_completion("custom_task_1", "success")

# Record custom errors
collector.record_error("CustomError", "analysis_component", "warning")

# Record API requests
collector.record_api_request("POST", "/custom/endpoint", 200, 0.150)
```

## Best Practices

1. **Monitor from the start** - Enable monitoring when starting the orchestrator
2. **Use appropriate intervals** - Balance detail with performance
3. **Clean up regularly** - Remove old metrics to prevent memory issues
4. **Alert on key metrics** - Set up alerts for critical performance indicators
5. **Analyze trends** - Use historical data to identify performance patterns
6. **Optimize based on data** - Use monitoring insights to improve system performance

## Security Considerations

1. **API Authentication** - Enable authentication for production deployments
2. **Network Security** - Restrict access to metrics endpoints
3. **Data Privacy** - Be cautious about logging sensitive information
4. **Resource Limits** - Set appropriate limits to prevent resource exhaustion

## Future Enhancements

The monitoring system is designed for extensibility:

1. **Custom Exporters** - Add support for other monitoring systems
2. **Advanced Analytics** - Machine learning-based performance prediction
3. **Automated Optimization** - Self-tuning based on performance metrics
4. **Enhanced Alerting** - More sophisticated alert conditions and notifications
5. **Multi-cluster Monitoring** - Support for distributed deployments

For detailed examples and usage patterns, see `/examples/monitoring_example.py`.