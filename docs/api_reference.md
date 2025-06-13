# Claude Conductor API Reference

## Overview

Claude Conductor is a multi-agent orchestration system that manages multiple Claude Code instances in isolated containers. This document provides comprehensive API documentation for all components.

## Core Components

### Orchestrator

The main orchestrator class that manages agents and tasks.

#### Methods

##### `__init__(config_path: Optional[str] = None)`
Initialize the orchestrator with optional configuration file.

**Parameters:**
- `config_path` (Optional[str]): Path to YAML configuration file

**Raises:**
- `ConfigurationError`: If configuration file is invalid

##### `start()`
Start the orchestrator and all configured agents.

**Raises:**
- `ResourceError`: If minimum required agents cannot be started
- `CommunicationError`: If broker channel fails to start

##### `stop()`
Stop all agents and cleanup resources.

##### `execute_task(task: Task) -> TaskResult`
Execute a single task on an available agent.

**Parameters:**
- `task` (Task): Task to execute

**Returns:**
- `TaskResult`: Result of task execution

**Raises:**
- `TaskValidationError`: If task is invalid
- `TaskTimeoutError`: If task exceeds timeout
- `TaskExecutionError`: If task execution fails

##### `execute_parallel_task(task: Task) -> List[TaskResult]`
Execute a task with subtasks in parallel.

**Parameters:**
- `task` (Task): Task with subtasks to execute

**Returns:**
- `List[TaskResult]`: Results from all subtasks

##### `get_agent_status() -> Dict[str, Any]`
Get status of all agents.

**Returns:**
- `Dict[str, Any]`: Agent status information

##### `get_statistics() -> Dict[str, Any]`
Get orchestrator statistics.

**Returns:**
- `Dict[str, Any]`: Runtime statistics

### ClaudeAgent

Individual agent wrapper for Claude Code instances.

#### Methods

##### `__init__(agent_id: str, orchestrator_socket_path: str, config: Optional[Dict[str, Any]] = None)`
Initialize a Claude agent.

**Parameters:**
- `agent_id` (str): Unique identifier for the agent
- `orchestrator_socket_path` (str): Path to orchestrator socket
- `config` (Optional[Dict[str, Any]]): Agent configuration

##### `start()`
Start the agent and its Claude Code instance.

**Raises:**
- `AgentStartupError`: If agent fails to start

##### `stop()`
Stop the agent and cleanup resources.

##### `execute_task(task: Task) -> TaskResult`
Execute a task on this agent.

**Parameters:**
- `task` (Task): Task to execute

**Returns:**
- `TaskResult`: Task execution result

### Task

Task definition for agent execution.

#### Attributes

- `task_id` (str): Unique task identifier
- `task_type` (str): Type of task ("code_review", "refactor", "test_generation", "analysis", "generic")
- `description` (str): Task description
- `files` (List[str]): Files to process
- `parallel` (bool): Whether task can be parallelized
- `subtasks` (Optional[List[Dict[str, Any]]]): Subtasks for parallel execution
- `priority` (int): Task priority (1-10, 10 highest)
- `timeout` (float): Task timeout in seconds

### TaskResult

Result of task execution.

#### Attributes

- `task_id` (str): Task identifier
- `agent_id` (str): Agent that executed the task
- `status` (str): Execution status ("success", "failed", "timeout", "partial")
- `result` (Dict[str, Any]): Task output
- `error` (Optional[str]): Error message if failed
- `execution_time` (float): Time taken to execute
- `timestamp` (float): Completion timestamp

### WorkspaceIsolationManager

Manages isolated workspaces using Podman containers.

#### Methods

##### `__init__(config: Dict[str, Any])`
Initialize workspace manager.

**Parameters:**
- `config` (Dict[str, Any]): Configuration dictionary

##### `async create_workspace(agent_id: str, environment: str = "minimal") -> WorkspaceContainer`
Create isolated workspace for an agent.

**Parameters:**
- `agent_id` (str): Agent identifier
- `environment` (str): Environment type

**Returns:**
- `WorkspaceContainer`: Created workspace container

##### `async execute_in_workspace(agent_id: str, command: List[str]) -> Tuple[int, str, str]`
Execute command in agent's workspace.

**Parameters:**
- `agent_id` (str): Agent identifier
- `command` (List[str]): Command to execute

**Returns:**
- `Tuple[int, str, str]`: (exit_code, stdout, stderr)

##### `async create_snapshot(agent_id: str, snapshot_name: Optional[str] = None) -> str`
Create workspace snapshot.

**Parameters:**
- `agent_id` (str): Agent identifier
- `snapshot_name` (Optional[str]): Snapshot name

**Returns:**
- `str`: Snapshot name

##### `async restore_snapshot(agent_id: str, snapshot_name: str)`
Restore workspace from snapshot.

**Parameters:**
- `agent_id` (str): Agent identifier
- `snapshot_name` (str): Snapshot to restore

##### `async cleanup_workspace(agent_id: str, preserve_volumes: bool = False)`
Clean up agent workspace.

**Parameters:**
- `agent_id` (str): Agent identifier
- `preserve_volumes` (bool): Whether to preserve volume data

## Error Handling

### Exception Hierarchy

All Claude Conductor exceptions inherit from `ConductorError`:

- `ConductorError`: Base exception
  - `ConfigurationError`: Configuration-related errors
  - `AgentStartupError`: Agent startup failures
  - `CommunicationError`: Communication failures
  - `TaskExecutionError`: Task execution failures
  - `TaskValidationError`: Task validation errors
  - `TaskTimeoutError`: Task timeout errors
  - `ResourceError`: Resource availability errors

### Error Handler

The `ErrorHandler` class provides centralized error handling with retry mechanisms and circuit breaker patterns.

#### Methods

##### `handle_error(operation: str, error: Exception, context: Dict[str, Any] = None, correlation_id: str = None, reraise: bool = True)`
Handle and log errors with context.

##### `@retry(max_attempts: int = 3, retryable_exceptions: Tuple = ())`
Decorator for automatic retry with exponential backoff.

## Configuration

### Main Configuration

```yaml
# Number of agents to start
num_agents: 3

# Maximum worker threads
max_workers: 10

# Default task timeout (seconds)
task_timeout: 300

# Log level
log_level: "INFO"

# Isolated workspace configuration
isolated_workspace:
  enabled: true
  mode: "sandbox"  # or "development"
  agent_containers:
    base_image: "minimal"
    resources:
      limits:
        memory: "2Gi"
        cpu: "1.0"
    environments:
      - name: "python"
        image: "python:3.11-slim"
        packages: ["git", "curl", "vim"]
      - name: "node"
        image: "node:18-alpine"
        packages: ["git", "curl"]

# Storage paths
storage:
  isolated_workspaces_path: "~/claude-conductor/workspaces"
  snapshots_path: "~/claude-conductor/snapshots"
  logs_path: "~/claude-conductor/logs"

# Podman configuration
podman_config:
  network:
    name: "claude-dev-net"
    subnet: "10.89.0.0/24"
  security:
    userns: "keep-id"
    seccomp_profile: "default"

# Task execution settings
task_execution:
  isolation:
    preserve_on_error: true
    restore_on_error: true
    snapshot_frequency: "per_task"
```

## Usage Examples

### Basic Task Execution

```python
from conductor.orchestrator import Orchestrator, create_task

# Initialize orchestrator
orchestrator = Orchestrator("config.yaml")
orchestrator.start()

# Create and execute a task
task = create_task(
    task_type="code_review",
    description="Review Python code for best practices",
    files=["main.py", "utils.py"]
)

result = orchestrator.execute_task(task)
print(f"Task {result.task_id} completed with status: {result.status}")

# Cleanup
orchestrator.stop()
```

### Parallel Task Execution

```python
# Create parallel task
parallel_task = create_task(
    task_type="test_generation",
    description="Generate tests for multiple modules",
    parallel=True,
    subtasks=[
        {
            "type": "test_generation",
            "description": "Generate tests for main module",
            "files": ["main.py"]
        },
        {
            "type": "test_generation", 
            "description": "Generate tests for utils module",
            "files": ["utils.py"]
        }
    ]
)

results = orchestrator.execute_parallel_task(parallel_task)
print(f"Completed {len(results)} parallel subtasks")
```

### Isolated Workspace Usage

```python
from conductor.workspace_isolation import WorkspaceIsolationManager

# Initialize workspace manager
workspace_manager = WorkspaceIsolationManager(config)

# Create isolated workspace
workspace = await workspace_manager.create_workspace("agent_001", "python")

# Execute commands in isolation
exit_code, stdout, stderr = await workspace_manager.execute_in_workspace(
    "agent_001", 
    ["python", "-c", "print('Hello from isolated workspace!')"]
)

# Create snapshot
snapshot_name = await workspace_manager.create_snapshot("agent_001", "after_setup")

# Cleanup
await workspace_manager.cleanup_workspace("agent_001")
```

## Security Considerations

### Container Security

- All containers run with dropped capabilities (`--cap-drop=ALL`)
- Read-only root filesystem with specific writable volumes
- No sudo access or privilege escalation
- Resource limits enforced (CPU, memory, PIDs)
- User namespace isolation
- Seccomp and AppArmor profiles applied

### Network Security

- Isolated network for agent containers
- No direct access to host network
- Controlled port exposure

### File System Security

- Workspace directories isolated per agent
- No access to host file system outside workspace
- Temporary directories with restricted permissions

## Monitoring and Logging

### Metrics

- Task completion rates
- Average execution times
- Agent health status
- Resource utilization
- Error rates by operation

### Log Levels

- `DEBUG`: Detailed debugging information
- `INFO`: General operational messages
- `WARNING`: Warning conditions
- `ERROR`: Error conditions
- `CRITICAL`: Critical failures

### Health Checks

Agents perform periodic health checks:
- Every 30 seconds
- Simple command execution test
- Auto-recovery after 3 consecutive failures

## Troubleshooting

### Common Issues

#### Agent Startup Failures
- Check Podman installation and permissions
- Verify container images are available
- Check resource constraints (memory, CPU)

#### Task Timeouts
- Increase task timeout in configuration
- Check agent health status
- Review resource utilization

#### Communication Errors
- Verify Unix socket permissions
- Check orchestrator socket path
- Review network configuration

#### Workspace Isolation Issues
- Verify Podman network configuration
- Check volume mount permissions
- Review security context settings

### Debug Mode

Enable debug logging:
```bash
python -m conductor.orchestrator --debug
```

### Agent Status Check

```python
status = orchestrator.get_agent_status()
for agent_id, info in status.items():
    print(f"Agent {agent_id}: {'Running' if info['running'] else 'Stopped'}")
```