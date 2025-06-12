# Getting Started with Claude Conductor

This guide will help you get up and running with Claude Conductor, a multi-agent orchestration system for Claude Code instances.

## Prerequisites

Before you begin, ensure you have:

- Python 3.10 or higher
- Podman or Docker installed
- Claude Code CLI (when available)
- At least 4GB of available RAM for multiple agents

## Installation

### Option 1: From Source

1. Clone the repository:
```bash
git clone https://github.com/ootakazuhiko/claude-conductor.git
cd claude-conductor
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Option 2: Using Docker

```bash
docker-compose -f containers/docker-compose.yml up --build
```

## Basic Usage

### 1. Start the Orchestrator

```python
from conductor import Orchestrator, create_task

# Create and start orchestrator with 3 agents
orchestrator = Orchestrator()
orchestrator.config["num_agents"] = 3
orchestrator.start()
```

### 2. Execute a Simple Task

```python
# Create a code review task
task = create_task(
    task_type="code_review",
    description="Review Python code for best practices",
    files=["src/main.py"]
)

# Execute the task
result = orchestrator.execute_task(task)
print(f"Task completed with status: {result.status}")
```

### 3. Run Parallel Tasks

```python
# Create a parallel task with subtasks
parallel_task = create_task(
    task_type="analysis",
    description="Analyze codebase components",
    parallel=True,
    subtasks=[
        {
            "type": "code_review",
            "description": "Review backend code",
            "files": ["backend/"]
        },
        {
            "type": "test_generation",
            "description": "Generate tests for frontend",
            "files": ["frontend/"]
        }
    ]
)

results = orchestrator.execute_parallel_task(parallel_task)
print(f"Completed {len(results)} parallel tasks")
```

### 4. Check System Status

```python
# Get agent status
status = orchestrator.get_agent_status()
print(json.dumps(status, indent=2))

# Get execution statistics
stats = orchestrator.get_statistics()
print(f"Tasks completed: {stats['tasks_completed']}")
print(f"Average execution time: {stats['avg_execution_time']:.2f}s")
```

### 5. Clean Shutdown

```python
# Always stop the orchestrator when done
orchestrator.stop()
```

## Command Line Interface

You can also use Claude Conductor from the command line:

```bash
# Start with default configuration
python -m conductor.orchestrator

# Start with custom number of agents
python -m conductor.orchestrator --agents 5

# Run with demo tasks
python -m conductor.orchestrator --demo

# Use custom configuration file
python -m conductor.orchestrator --config config/my-config.yaml
```

### Interactive Commands

When running the CLI, you can use these commands:

- `status` - Show agent status
- `stats` - Show execution statistics
- `task <type> <description>` - Execute a single task
- `parallel <description>` - Execute parallel subtasks
- `quit` - Exit the orchestrator

## Configuration

Create a configuration file `config/config.yaml`:

```yaml
orchestrator:
  num_agents: 3
  max_workers: 10
  task_timeout: 300

agent:
  container_memory: "2g"
  container_cpu: "1.0"
  health_check_interval: 30

communication:
  socket_path: "/tmp/claude_orchestrator.sock"
  message_timeout: 5.0
```

## Task Types

Claude Conductor supports several built-in task types:

### Code Review
```python
task = create_task(
    task_type="code_review",
    description="Review for security issues",
    files=["auth.py", "validators.py"]
)
```

### Refactoring
```python
task = create_task(
    task_type="refactor",
    description="Improve code structure and readability",
    files=["legacy_module.py"]
)
```

### Test Generation
```python
task = create_task(
    task_type="test_generation",
    description="Generate comprehensive test suite",
    files=["api/endpoints.py"]
)
```

### Code Analysis
```python
task = create_task(
    task_type="analysis",
    description="Analyze code complexity and maintainability"
)
```

## Container Deployment

For containerized deployment:

```bash
# Build the image
docker build -f containers/Dockerfile -t claude-conductor .

# Run with docker-compose
cd containers/
docker-compose up -d

# Scale agents
docker-compose up --scale agent-001=5
```

## Next Steps

- Read the [Architecture Guide](architecture.md) to understand the system design
- Check the [API Reference](api-reference.md) for detailed documentation
- See [Configuration Guide](configuration.md) for advanced settings
- Review [Deployment Guide](deployment.md) for production setup

## Troubleshooting

If you encounter issues:

1. Check that all prerequisites are installed
2. Verify container runtime (Podman/Docker) is working
3. Review logs for specific error messages
4. See [Troubleshooting Guide](troubleshooting.md) for common solutions

## Examples

Check the `examples/` directory for more comprehensive usage examples and integration patterns.