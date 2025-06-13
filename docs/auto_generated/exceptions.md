# exceptions

Custom exceptions for Claude Conductor

## Classes

### ConductorError

**Inherits from:** Exception

Base exception for Claude Conductor

#### Methods

### AgentError

**Inherits from:** ConductorError

Agent-related errors

### AgentStartupError

**Inherits from:** AgentError

Agent startup failures

### AgentCommunicationError

**Inherits from:** AgentError

Agent communication failures

### ContainerError

**Inherits from:** ConductorError

Container operation errors

### ContainerCreationError

**Inherits from:** ContainerError

Container creation failures

### ContainerExecutionError

**Inherits from:** ContainerError

Container command execution failures

### TaskExecutionError

**Inherits from:** ConductorError

Task execution errors

### TaskTimeoutError

**Inherits from:** TaskExecutionError

Task execution timeout

### TaskValidationError

**Inherits from:** TaskExecutionError

Task validation failures

### CommunicationError

**Inherits from:** ConductorError

Inter-agent communication errors

### ChannelError

**Inherits from:** CommunicationError

Communication channel errors

### ProtocolError

**Inherits from:** CommunicationError

Protocol-related errors

### WorkspaceError

**Inherits from:** ConductorError

Workspace operation errors

### WorkspaceCreationError

**Inherits from:** WorkspaceError

Workspace creation failures

### WorkspaceCleanupError

**Inherits from:** WorkspaceError

Workspace cleanup failures

### ConfigurationError

**Inherits from:** ConductorError

Configuration-related errors

### ResourceError

**Inherits from:** ConductorError

Resource-related errors (memory, CPU, disk)

### ServiceUnavailableError

**Inherits from:** ConductorError

Service unavailable errors

### ErrorContext

Structured error context for logging and debugging

#### Attributes

- `component` (str)
- `operation` (str)
- `error_code` (str)
- `details` (Dict[(str, Any)])
- `timestamp` (float)
- `correlation_id` (Optional[str])

#### Methods

##### to_dict

`to_dict()` -> Dict[(str, Any)]

Convert to dictionary for logging

## Functions

### create_error_context

`create_error_context(component: str, operation: str, error: Exception, additional_context: Dict[(str, Any)] = None, correlation_id: str = None)` -> ErrorContext

Create standardized error context

**Parameters:**
- `component` (str)
- `operation` (str)
- `error` (Exception)
- `additional_context` (Dict[(str, Any)]) = None
- `correlation_id` (str) = None
