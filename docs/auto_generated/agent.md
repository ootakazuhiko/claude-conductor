# agent

Claude Agent - Container wrapper and agent management

## Classes

### AgentConfig

Agent configuration

#### Attributes

- `agent_id` (str)
- `container_name` (str)
- `work_dir` (str)
- `podman_image` (str)
- `memory_limit` (str)
- `cpu_limit` (str)
- `use_isolated_workspace` (bool)
- `workspace_environment` (str)
- `enable_snapshots` (bool)

### CommandResult

Command execution result

#### Attributes

- `command` (str)
- `stdout` (str)
- `stderr` (str)
- `exit_code` (int)
- `timestamp` (float)

### Task

Task definition

#### Attributes

- `task_id` (str)
- `task_type` (str)
- `description` (str)
- `files` (List[str])
- `parallel` (bool)
- `subtasks` (Optional[List[Dict[(str, Any)]]])
- `priority` (int)
- `timeout` (float)

#### Methods

### TaskResult

Task execution result

#### Attributes

- `task_id` (str)
- `agent_id` (str)
- `status` (str)
- `result` (Dict[(str, Any)])
- `error` (Optional[str])
- `execution_time` (float)
- `timestamp` (float)

#### Methods

### ClaudeCodeWrapper

Wrapper for Claude Code processes

#### Methods

##### setup_container

`setup_container()` -> str

Set up Podman container

##### exec_in_container

`exec_in_container(command: str)` -> CommandResult

Execute command in container

**Parameters:**
- `command` (str)

##### start_claude_code

`start_claude_code(headless: bool = True)`

Start Claude Code process

**Parameters:**
- `headless` (bool) = True

##### send_command

`send_command(command: str)`

Send command to Claude Code

**Parameters:**
- `command` (str)

##### read_output

`read_output(timeout: float = 1.0)` -> List[tuple]

Read output

**Parameters:**
- `timeout` (float) = 1.0

##### stop

`stop()`

Stop process

##### cleanup_container

`cleanup_container()`

Clean up container

### ClaudeAgent

Claude Code agent

#### Methods

##### start

`start()`

Start agent

##### stop

`stop()`

Stop agent

##### execute_task

`execute_task(task: Task)` -> TaskResult

Execute task

**Parameters:**
- `task` (Task)

## Functions

### read_stdout

`read_stdout()`

### read_stderr

`read_stderr()`
