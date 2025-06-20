#!/usr/bin/env python3
"""
Comprehensive Performance Monitoring Example for Claude Conductor

This example demonstrates how to use the comprehensive performance monitoring
system with Claude Conductor, including metrics collection, distributed tracing,
real-time dashboards, and performance analysis.
"""

import time
import asyncio
import logging
from typing import Dict, Any
import random

# Import monitoring components
from conductor.monitored_orchestrator import create_monitored_orchestrator
from conductor.monitored_agent import create_monitored_agent
from conductor.metrics_service import create_metrics_service
from conductor.enhanced_dashboard import run_enhanced_dashboard, enhanced_dashboard_data
from conductor.metrics import get_metrics_collector, start_prometheus_server
from conductor.monitoring import setup_monitoring, generate_monitoring_report
from conductor.agent import Task, create_task

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


def create_sample_config() -> Dict[str, Any]:
    """Create sample configuration for monitoring"""
    return {
        'num_agents': 3,
        'max_workers': 8,
        'task_timeout': 120,
        'log_level': 'INFO',
        
        # Monitoring configuration
        'metrics': {
            'prometheus_enabled': True,
            'prometheus_port': 8000,
            'api_enabled': True,
            'api_host': '0.0.0.0',
            'api_port': 8080,
            'api_authentication': False
        },
        
        # Task queue configuration
        'task_queue': {
            'max_size': 1000,
            'priority_levels': 10
        },
        
        # Monitoring intervals
        'monitoring': {
            'update_interval': 15,  # Update metrics every 15 seconds
            'cleanup_interval': 3600,  # Cleanup old data every hour
            'snapshot_interval': 30  # Performance snapshots every 30 seconds
        }
    }


def generate_sample_tasks(count: int = 20) -> list[Task]:
    """Generate sample tasks for demonstration"""
    task_types = ['code_review', 'refactor', 'test_generation', 'analysis', 'generic']
    priorities = [1, 3, 5, 7, 10]
    
    tasks = []
    for i in range(count):
        task = create_task(
            task_type=random.choice(task_types),
            description=f"Sample task {i+1}: {random.choice(['optimize code', 'review security', 'generate tests', 'analyze performance', 'refactor module'])}",
            files=[f"file_{j}.py" for j in range(random.randint(1, 5))],
            priority=random.choice(priorities),
            timeout=random.randint(30, 180)
        )
        tasks.append(task)
    
    return tasks


async def simulate_workload(orchestrator, tasks: list[Task], delay_range: tuple = (1, 5)):
    """Simulate realistic workload by executing tasks with delays"""
    logger.info(f"Starting workload simulation with {len(tasks)} tasks")
    
    results = []
    for i, task in enumerate(tasks):
        logger.info(f"Executing task {i+1}/{len(tasks)}: {task.task_type}")
        
        try:
            # Execute task
            result = orchestrator.execute_task(task)
            results.append(result)
            
            logger.info(f"Task {task.task_id} completed with status: {result.status}")
            
            # Random delay between tasks to simulate realistic usage
            delay = random.uniform(*delay_range)
            await asyncio.sleep(delay)
            
        except Exception as e:
            logger.error(f"Task {task.task_id} failed: {e}")
            
        # Occasionally execute parallel tasks
        if i % 7 == 0 and i < len(tasks) - 3:
            logger.info("Executing parallel task batch")
            try:
                parallel_task = create_task(
                    task_type="analysis",
                    description="Parallel analysis task",
                    parallel=True,
                    subtasks=[
                        {"type": "code_review", "description": "Review module A", "files": ["moduleA.py"]},
                        {"type": "test_generation", "description": "Generate tests for module B", "files": ["moduleB.py"]},
                        {"type": "refactor", "description": "Refactor module C", "files": ["moduleC.py"]}
                    ]
                )
                
                parallel_results = orchestrator.execute_parallel_task(parallel_task)
                results.extend(parallel_results)
                logger.info(f"Parallel task completed with {len(parallel_results)} subtasks")
                
            except Exception as e:
                logger.error(f"Parallel task failed: {e}")
    
    logger.info(f"Workload simulation completed. {len(results)} tasks executed.")
    return results


def analyze_performance_results(orchestrator):
    """Analyze and display performance results"""
    logger.info("=" * 60)
    logger.info("PERFORMANCE ANALYSIS RESULTS")
    logger.info("=" * 60)
    
    # Get comprehensive performance report
    performance_report = orchestrator.get_comprehensive_performance_report()
    
    # Display key metrics
    base_stats = performance_report.get('base_statistics', {})
    detailed_stats = performance_report.get('detailed_statistics', {})
    queue_metrics = performance_report.get('queue_metrics', {})
    
    logger.info(f"Runtime: {base_stats.get('runtime', 0):.2f} seconds")
    logger.info(f"Tasks completed: {base_stats.get('tasks_completed', 0)}")
    logger.info(f"Tasks failed: {base_stats.get('tasks_failed', 0)}")
    logger.info(f"Average execution time: {base_stats.get('avg_execution_time', 0):.3f}s")
    
    # Queue performance
    logger.info(f"Queue throughput: {queue_metrics.get('throughput_per_minute', 0):.1f} tasks/min")
    logger.info(f"Average queue time: {queue_metrics.get('avg_queue_time', 0):.3f}s")
    
    # Agent utilization
    agent_util = detailed_stats.get('agent_utilization', {})
    if agent_util:
        logger.info("Agent Utilization:")
        for agent_id, utilization in agent_util.items():
            logger.info(f"  {agent_id}: {utilization:.2f}")
    
    # Task type performance
    task_perf = detailed_stats.get('task_type_performance', {})
    if task_perf:
        logger.info("Task Type Performance:")
        for task_type, metrics in task_perf.items():
            logger.info(f"  {task_type}: {metrics.get('avg_execution_time', 0):.3f}s avg, "
                       f"{metrics.get('success_rate', 0):.1%} success rate")
    
    # Peak metrics
    peak_metrics = detailed_stats.get('peak_metrics', {})
    if peak_metrics:
        logger.info("Peak Performance Metrics:")
        logger.info(f"  Max concurrent tasks: {peak_metrics.get('max_concurrent_tasks', 0)}")
        logger.info(f"  Peak CPU usage: {peak_metrics.get('peak_cpu_usage', 0):.1f}%")
        logger.info(f"  Peak memory usage: {peak_metrics.get('peak_memory_usage', 0):.1f}%")
        logger.info(f"  Fastest task: {peak_metrics.get('fastest_task_completion', 0):.3f}s")
        logger.info(f"  Highest throughput: {peak_metrics.get('highest_throughput', 0):.1f} tasks/min")
    
    # Error analysis
    error_patterns = detailed_stats.get('error_patterns', {})
    if error_patterns:
        logger.info("Error Patterns:")
        for error_type, count in error_patterns.items():
            logger.info(f"  {error_type}: {count} occurrences")


def demonstrate_metrics_api(metrics_service):
    """Demonstrate metrics API endpoints"""
    logger.info("=" * 60)
    logger.info("METRICS API DEMONSTRATION")
    logger.info("=" * 60)
    
    if not metrics_service:
        logger.warning("Metrics service not available")
        return
    
    # Display available endpoints
    status = metrics_service.get_status()
    endpoints = status.get('endpoints', {})
    
    logger.info("Available Metrics Endpoints:")
    for name, url in endpoints.items():
        logger.info(f"  {name}: {url}")
    
    logger.info("\nYou can access these endpoints to get:")
    logger.info("  - Prometheus metrics: /metrics")
    logger.info("  - API documentation: /docs")
    logger.info("  - Health check: /health")
    logger.info("  - Metrics summary: /api/v1/metrics/summary")
    logger.info("  - Task metrics: /api/v1/metrics/tasks")
    logger.info("  - Agent metrics: /api/v1/metrics/agents")
    logger.info("  - System metrics: /api/v1/metrics/system")
    logger.info("  - Real-time metrics: /api/v1/metrics/real-time")
    logger.info("  - Performance snapshots: /api/v1/metrics/performance/snapshots")
    logger.info("  - Distributed traces: /api/v1/metrics/traces")
    logger.info("  - Export data: /api/v1/metrics/export")


def demonstrate_distributed_tracing():
    """Demonstrate distributed tracing capabilities"""
    logger.info("=" * 60)
    logger.info("DISTRIBUTED TRACING DEMONSTRATION")
    logger.info("=" * 60)
    
    from conductor.monitoring import get_tracing_middleware
    
    tracing = get_tracing_middleware()
    summary = tracing.get_trace_summary()
    
    logger.info(f"Active traces: {summary.get('active_traces', 0)}")
    logger.info(f"Completed traces: {summary.get('completed_traces', 0)}")
    logger.info(f"Total traces: {summary.get('total_traces', 0)}")
    
    # Display recent completed traces
    if tracing.completed_traces:
        logger.info("\nRecent Completed Traces:")
        for trace in list(tracing.completed_traces)[-5:]:  # Last 5 traces
            duration = trace.tags.get('duration', 'unknown')
            status = trace.tags.get('status', 'unknown')
            logger.info(f"  {trace.operation_name} ({trace.trace_id[:8]}...): "
                       f"{duration}s, status: {status}")


async def main():
    """Main demonstration function"""
    logger.info("Starting Claude Conductor Comprehensive Monitoring Demonstration")
    
    # Create configuration
    config = create_sample_config()
    
    # Create monitored orchestrator with metrics service
    logger.info("Creating monitored orchestrator with comprehensive monitoring...")
    orchestrator = create_monitored_orchestrator(enable_metrics_service=True)
    orchestrator.config.update(config)
    
    # Start the orchestrator
    logger.info("Starting orchestrator...")
    orchestrator.start()
    
    try:
        # Wait for initialization
        await asyncio.sleep(2)
        
        # Demonstrate metrics service
        demonstrate_metrics_api(orchestrator.metrics_service)
        
        # Generate and execute sample tasks
        logger.info("Generating sample tasks...")
        tasks = generate_sample_tasks(15)
        
        # Simulate workload
        logger.info("Starting workload simulation...")
        await simulate_workload(orchestrator, tasks, delay_range=(0.5, 2.0))
        
        # Wait for final metrics collection
        await asyncio.sleep(5)
        
        # Analyze performance results
        analyze_performance_results(orchestrator)
        
        # Demonstrate distributed tracing
        demonstrate_distributed_tracing()
        
        # Generate comprehensive monitoring report
        logger.info("Generating comprehensive monitoring report...")
        report = generate_monitoring_report(orchestrator.metrics_collector)
        
        # Save report to file
        report_file = f"/tmp/monitoring_demo_report_{int(time.time())}.json"
        with open(report_file, 'w') as f:
            f.write(report)
        logger.info(f"Monitoring report saved to: {report_file}")
        
        # Display final statistics
        logger.info("=" * 60)
        logger.info("FINAL SYSTEM STATUS")
        logger.info("=" * 60)
        
        metrics_summary = orchestrator.metrics_collector.get_metrics_summary()
        logger.info(f"Total tasks tracked: {metrics_summary['task_metrics']['total']}")
        logger.info(f"Active agents: {metrics_summary['agent_metrics']['active_agents']}")
        logger.info(f"Total errors: {metrics_summary['error_metrics']['total_errors']}")
        logger.info(f"System uptime: {metrics_summary['performance_metrics']['uptime']:.1f}s")
        
        # Keep system running for dashboard demonstration
        logger.info("=" * 60)
        logger.info("DASHBOARD ACCESS INFORMATION")
        logger.info("=" * 60)
        logger.info("The monitoring system is now running with the following endpoints:")
        
        if orchestrator.metrics_service:
            status = orchestrator.metrics_service.get_status()
            endpoints = status.get('endpoints', {})
            for name, url in endpoints.items():
                logger.info(f"  {name}: {url}")
        
        logger.info("\nTo access the enhanced dashboard, visit:")
        logger.info("  http://localhost:8080 (if enhanced dashboard is running)")
        logger.info("\nPress Ctrl+C to stop the demonstration...")
        
        # Keep running for demonstration
        while True:
            await asyncio.sleep(10)
            
            # Occasionally execute more tasks to keep the demo active
            if random.random() < 0.3:  # 30% chance every 10 seconds
                logger.info("Executing additional demo task...")
                demo_task = create_task(
                    task_type=random.choice(['code_review', 'analysis']),
                    description="Demo maintenance task",
                    files=[f"demo_file_{random.randint(1,10)}.py"]
                )
                
                try:
                    result = orchestrator.execute_task(demo_task)
                    logger.info(f"Demo task completed: {result.status}")
                except Exception as e:
                    logger.error(f"Demo task failed: {e}")
                    
    except KeyboardInterrupt:
        logger.info("Demonstration interrupted by user")
        
    finally:
        # Clean shutdown
        logger.info("Shutting down orchestrator...")
        orchestrator.stop()
        logger.info("Demonstration completed")


def run_dashboard_demo():
    """Run the enhanced dashboard demonstration"""
    import threading
    import webbrowser
    
    logger.info("Starting enhanced dashboard demonstration...")
    
    # Create a simple orchestrator for the dashboard
    config = create_sample_config()
    orchestrator = create_monitored_orchestrator(enable_metrics_service=True)
    orchestrator.config.update(config)
    
    # Set dashboard data
    enhanced_dashboard_data.orchestrator = orchestrator
    enhanced_dashboard_data.metrics_service = orchestrator.metrics_service
    
    # Start orchestrator in background
    orchestrator.start()
    
    # Generate some initial data
    initial_tasks = generate_sample_tasks(5)
    for task in initial_tasks:
        try:
            orchestrator.execute_task(task)
        except Exception as e:
            logger.error(f"Initial task failed: {e}")
    
    # Open browser after a delay
    threading.Timer(2.0, lambda: webbrowser.open("http://localhost:8080")).start()
    
    try:
        # Run the enhanced dashboard
        run_enhanced_dashboard(
            orchestrator=orchestrator,
            metrics_service=orchestrator.metrics_service,
            port=8080,
            open_browser=False  # We're opening manually above
        )
    finally:
        orchestrator.stop()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--dashboard":
        # Run dashboard demo
        run_dashboard_demo()
    else:
        # Run full monitoring demo
        asyncio.run(main())