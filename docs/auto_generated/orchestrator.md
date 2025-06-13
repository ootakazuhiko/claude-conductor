# orchestrator

Claude Code Multi-Agent Orchestrator

## Classes

### Orchestrator

Multi-agent orchestrator for Claude Conductor

#### Methods

##### start

`start()`

Start orchestrator with comprehensive error handling

##### stop

`stop()`

Stop orchestrator with proper cleanup

##### execute_task

`execute_task(task: Task)` -> TaskResult

Execute single task with comprehensive error handling

**Parameters:**
- `task` (Task)

##### execute_parallel_task

`execute_parallel_task(task: Task)` -> List[TaskResult]

Execute parallel task with subtasks

**Parameters:**
- `task` (Task)

##### get_agent_status

`get_agent_status()` -> Dict[(str, Any)]

Get status of all agents

##### get_task_result

`get_task_result(task_id: str)` -> Optional[TaskResult]

Get task execution result by ID

**Parameters:**
- `task_id` (str)

##### get_statistics

`get_statistics()` -> Dict[(str, Any)]

Get orchestrator execution statistics

## Functions

### create_task

`create_task(task_type: str = 'generic', description: str = '', files: List[str] = None)` -> Task

Helper function to easily create tasks

**Parameters:**
- `task_type` (str) = 'generic'
- `description` (str) = ''
- `files` (List[str]) = None

### main

`main()`
