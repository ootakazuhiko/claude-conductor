#!/usr/bin/env python3
"""
Advanced configuration example for Claude Conductor
"""

import yaml
import tempfile
import os
from conductor import Orchestrator, create_task


def main():
    """Demonstrate advanced configuration options"""
    print("=== Claude Conductor Advanced Configuration ===\n")
    
    # Create custom configuration
    config_file = create_custom_config()
    print(f"Created custom configuration: {config_file}")
    
    try:
        # Initialize orchestrator with custom config
        orchestrator = Orchestrator(config_file)
        
        print("\nConfiguration loaded:")
        print(f"  Number of agents: {orchestrator.config['num_agents']}")
        print(f"  Max workers: {orchestrator.config['max_workers']}")
        print(f"  Task timeout: {orchestrator.config['task_timeout']}s")
        print(f"  Log level: {orchestrator.config['log_level']}")
        
        # Start with custom configuration
        orchestrator.start()
        
        # Demonstrate different task configurations
        demonstrate_task_priorities(orchestrator)
        demonstrate_task_timeouts(orchestrator)
        demonstrate_custom_task_types(orchestrator)
        
        # Show configuration in action
        print("\n--- Configuration Impact ---")
        stats = orchestrator.get_statistics()
        print(f"Active agents: {stats['active_agents']}/{stats['total_agents']}")
        print(f"Worker threads: {orchestrator.config['max_workers']}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        orchestrator.stop()
        cleanup_config_file(config_file)
        print("\nCleanup completed.")


def create_custom_config():
    """Create a custom configuration file"""
    config = {
        'orchestrator': {
            'num_agents': 5,
            'max_workers': 15,
            'task_timeout': 180,
            'log_level': 'DEBUG'
        },
        'agent': {
            'container_memory': '3g',
            'container_cpu': '1.5',
            'health_check_interval': 20,
            'startup_timeout': 90
        },
        'communication': {
            'socket_path': '/tmp/claude_orchestrator_advanced.sock',
            'message_timeout': 10.0,
            'retry_count': 5
        },
        'task_queue': {
            'max_size': 2000,
            'priority_levels': 15
        },
        'performance': {
            'enable_caching': True,
            'cache_size': 1000,
            'enable_metrics': True,
            'metrics_interval': 30
        },
        'security': {
            'enable_encryption': False,
            'max_file_size': '100MB',
            'allowed_file_types': ['.py', '.js', '.ts', '.java', '.cpp', '.h']
        }
    }
    
    # Write to temporary file
    fd, config_file = tempfile.mkstemp(suffix='.yaml', prefix='claude_config_')
    try:
        with os.fdopen(fd, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
    except:
        os.close(fd)
        raise
    
    return config_file


def demonstrate_task_priorities(orchestrator):
    """Demonstrate task priority handling"""
    print("\n--- Task Priority Demonstration ---")
    
    # Create tasks with different priorities
    tasks = [
        create_task(
            task_type="analysis",
            description="Low priority background analysis",
            priority=2
        ),
        create_task(
            task_type="code_review",
            description="High priority security review",
            priority=9
        ),
        create_task(
            task_type="refactor",
            description="Medium priority refactoring",
            priority=5
        ),
        create_task(
            task_type="test_generation",
            description="Critical test generation",
            priority=10
        )
    ]
    
    print("Executing tasks with different priorities:")
    for task in tasks:
        print(f"  Priority {task.priority}: {task.description}")
    
    # Execute tasks (orchestrator should handle priority ordering)
    results = []
    for task in tasks:
        result = orchestrator.execute_task(task)
        results.append(result)
        print(f"  Completed: {task.description} -> {result.status}")


def demonstrate_task_timeouts(orchestrator):
    """Demonstrate different timeout configurations"""
    print("\n--- Task Timeout Demonstration ---")
    
    # Tasks with different timeout requirements
    timeout_tasks = [
        create_task(
            task_type="analysis",
            description="Quick analysis (short timeout)",
            timeout=5.0
        ),
        create_task(
            task_type="refactor",
            description="Complex refactoring (long timeout)",
            timeout=300.0
        ),
        create_task(
            task_type="test_generation",
            description="Standard test generation (default timeout)",
            # Uses default timeout from config
        )
    ]
    
    for task in timeout_tasks:
        print(f"Executing task with {task.timeout}s timeout: {task.description}")
        result = orchestrator.execute_task(task)
        print(f"  Result: {result.status} (took {result.execution_time:.2f}s)")


def demonstrate_custom_task_types(orchestrator):
    """Demonstrate custom task type handling"""
    print("\n--- Custom Task Types ---")
    
    # Custom task configurations
    custom_tasks = [
        {
            "task": create_task(
                task_type="security_audit",
                description="Perform security vulnerability scan",
                priority=8,
                timeout=120.0
            ),
            "expected": "Custom security analysis"
        },
        {
            "task": create_task(
                task_type="performance_analysis",
                description="Analyze performance bottlenecks",
                priority=6,
                timeout=90.0
            ),
            "expected": "Performance profiling"
        },
        {
            "task": create_task(
                task_type="documentation_generation",
                description="Generate API documentation",
                priority=4,
                timeout=60.0
            ),
            "expected": "Documentation creation"
        }
    ]
    
    for item in custom_tasks:
        task = item["task"]
        print(f"Custom task: {task.task_type}")
        print(f"  Description: {task.description}")
        
        result = orchestrator.execute_task(task)
        print(f"  Status: {result.status}")
        print(f"  Agent: {result.agent_id}")
        
        if result.error:
            print(f"  Note: {result.error}")
        print()


def demonstrate_parallel_configuration(orchestrator):
    """Demonstrate parallel processing configuration"""
    print("\n--- Parallel Processing Configuration ---")
    
    # Large parallel task to test worker limits
    parallel_task = create_task(
        task_type="batch_analysis",
        description="Process large batch of files",
        parallel=True,
        subtasks=[
            {
                "type": "analysis",
                "description": f"Analyze batch item {i}",
                "timeout": 30.0
            }
            for i in range(10)  # 10 parallel subtasks
        ]
    )
    
    print(f"Executing {len(parallel_task.subtasks)} parallel subtasks")
    print(f"Max workers configured: {orchestrator.config['max_workers']}")
    
    import time
    start_time = time.time()
    results = orchestrator.execute_parallel_task(parallel_task)
    end_time = time.time()
    
    print(f"Parallel execution completed in {end_time - start_time:.2f}s")
    print(f"Successful tasks: {sum(1 for r in results if r.status == 'success')}")
    print(f"Failed tasks: {sum(1 for r in results if r.status == 'failed')}")


def demonstrate_resource_monitoring(orchestrator):
    """Demonstrate resource monitoring capabilities"""
    print("\n--- Resource Monitoring ---")
    
    # Get detailed agent status
    status = orchestrator.get_agent_status()
    print(f"Total agents: {len(status)}")
    
    for agent_id, info in status.items():
        print(f"\nAgent {agent_id}:")
        print(f"  Status: {'Running' if info['running'] else 'Stopped'}")
        print(f"  Current task: {info['current_task'] or 'None'}")
        print(f"  Health check failures: {info['health_check_failed']}")
        print(f"  Container: {info['container_name']}")
    
    # System statistics
    stats = orchestrator.get_statistics()
    print(f"\nSystem Statistics:")
    print(f"  Runtime: {stats['runtime']:.2f}s")
    print(f"  Tasks completed: {stats['tasks_completed']}")
    print(f"  Tasks failed: {stats['tasks_failed']}")
    print(f"  Average execution time: {stats['avg_execution_time']:.2f}s")
    print(f"  Total execution time: {stats['total_execution_time']:.2f}s")
    
    if stats['runtime'] > 0:
        efficiency = (stats['total_execution_time'] / stats['runtime']) * 100
        print(f"  System efficiency: {efficiency:.1f}%")


def cleanup_config_file(config_file):
    """Clean up the temporary config file"""
    try:
        os.unlink(config_file)
    except FileNotFoundError:
        pass


if __name__ == "__main__":
    main()