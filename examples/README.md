# Claude Conductor Examples

This directory contains example scripts demonstrating various features and usage patterns of Claude Conductor.

## Examples Overview

### 1. Basic Usage (`basic_usage.py`)
Demonstrates fundamental operations:
- Starting an orchestrator with multiple agents
- Executing different types of tasks (code review, refactoring, test generation)
- Viewing execution results and statistics
- Proper shutdown and cleanup

**Run with:**
```bash
python examples/basic_usage.py
```

### 2. Parallel Processing (`parallel_processing.py`)
Shows advanced parallel task execution:
- Running multiple tasks simultaneously
- Comparing sequential vs parallel execution performance
- Mixed task types in parallel
- Agent utilization monitoring

**Run with:**
```bash
python examples/parallel_processing.py
```

### 3. Advanced Configuration (`advanced_configuration.py`)
Demonstrates sophisticated configuration options:
- Custom YAML configuration files
- Task priorities and timeouts
- Custom task types
- Resource monitoring and statistics

**Run with:**
```bash
python examples/advanced_configuration.py
```

### 4. Legacy Example (`example_usage.py`)
Original example showing basic orchestrator usage (updated for new structure).

**Run with:**
```bash
python examples/example_usage.py
```

## Sample Code Files

### `sample_code.py`
A simple Python file used by examples for demonstration purposes. Contains basic functions that can be analyzed, reviewed, or refactored by Claude agents.

## Prerequisites

Before running the examples:

1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Up Environment:**
   ```bash
   ./scripts/setup.sh
   ```

3. **Optional - Container Runtime:**
   - Install Podman or Docker for full container functionality
   - Examples will work with mock agents if no container runtime is available

## Understanding the Output

### Task Results
Each example shows task execution results with:
- **Status**: `success`, `failed`, `timeout`, or `partial`
- **Agent ID**: Which agent executed the task
- **Execution Time**: How long the task took
- **Error Messages**: If the task failed

### Statistics
Examples display system statistics including:
- Tasks completed/failed counts
- Average execution times
- System runtime and efficiency
- Agent utilization

## Customization

### Creating Custom Tasks
Use the `create_task()` helper function:

```python
from conductor import create_task

task = create_task(
    task_type="code_review",
    description="Review for security issues",
    files=["security_module.py"],
    priority=8,
    timeout=120.0
)
```

### Custom Configuration
Create YAML configuration files:

```yaml
orchestrator:
  num_agents: 5
  max_workers: 15
  task_timeout: 300

agent:
  container_memory: "4g"
  container_cpu: "2.0"
```

### Parallel Tasks
Define parallel execution with subtasks:

```python
parallel_task = create_task(
    task_type="analysis",
    parallel=True,
    subtasks=[
        {"type": "code_review", "files": ["file1.py"]},
        {"type": "test_generation", "files": ["file2.py"]},
        {"type": "refactor", "files": ["file3.py"]}
    ]
)
```

## Troubleshooting

### No Agents Running
If examples show "No agents are running":
- This is expected in test/demo environments
- The system uses mock agents for demonstration
- Install Podman/Docker for full functionality

### Task Failures
Common reasons for task failures:
- Missing or invalid file paths
- Container runtime issues
- Network/socket communication problems
- Resource constraints

### Performance Issues
To improve performance:
- Increase the number of agents
- Adjust worker thread limits
- Use appropriate task priorities
- Monitor system resources

## Integration Patterns

### Web Applications
```python
from conductor import Orchestrator, create_task

orchestrator = Orchestrator()
orchestrator.start()

def analyze_code(file_path):
    task = create_task(
        task_type="code_review",
        files=[file_path]
    )
    return orchestrator.execute_task(task)
```

### CI/CD Pipelines
```python
# Parallel code quality checks
quality_task = create_task(
    task_type="quality_check",
    parallel=True,
    subtasks=[
        {"type": "code_review", "files": changed_files},
        {"type": "test_generation", "files": new_files},
        {"type": "security_audit", "files": all_files}
    ]
)
```

### Batch Processing
```python
# Process large codebases
for batch in file_batches:
    batch_task = create_task(
        task_type="batch_analysis",
        files=batch,
        priority=5
    )
    results.append(orchestrator.execute_task(batch_task))
```

## Next Steps

1. Review the [Getting Started Guide](../docs/getting-started.md)
2. Read the [API Reference](../docs/api-reference.md)
3. Check the [Architecture Documentation](../docs/architecture.md)
4. Explore [Deployment Options](../docs/deployment.md)