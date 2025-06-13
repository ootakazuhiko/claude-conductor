# error_handler

Error handling utilities and patterns for Claude Conductor

## Classes

### RetryConfig

Configuration for retry behavior

#### Attributes

- `max_attempts` (int)
- `backoff_factor` (float)
- `initial_delay` (float)
- `max_delay` (float)
- `exponential_backoff` (bool)
- `retryable_exceptions` (tuple)

### CircuitBreaker

Circuit breaker pattern implementation

#### Methods

### ErrorHandler

Centralized error handling and logging

#### Methods

##### handle_error

`handle_error(operation: str, error: Exception, context: Dict[(str, Any)] = None, correlation_id: str = None, reraise: bool = True)` -> ErrorContext

Handle an error with standardized logging and context

**Parameters:**
- `operation` (str)
- `error` (Exception)
- `context` (Dict[(str, Any)]) = None
- `correlation_id` (str) = None
- `reraise` (bool) = True

##### handle_warning

`handle_warning(operation: str, message: str, context: Dict[(str, Any)] = None, correlation_id: str = None)`

Handle warnings with consistent logging

**Parameters:**
- `operation` (str)
- `message` (str)
- `context` (Dict[(str, Any)]) = None
- `correlation_id` (str) = None

##### log_operation_start

`log_operation_start(operation: str, context: Dict[(str, Any)] = None, correlation_id: str = None)`

Log operation start for debugging

**Parameters:**
- `operation` (str)
- `context` (Dict[(str, Any)]) = None
- `correlation_id` (str) = None

##### log_operation_success

`log_operation_success(operation: str, context: Dict[(str, Any)] = None, correlation_id: str = None)`

Log successful operation completion

**Parameters:**
- `operation` (str)
- `context` (Dict[(str, Any)]) = None
- `correlation_id` (str) = None

## Functions

### retry

`retry(max_attempts: int = 3, backoff_factor: float = 2.0, initial_delay: float = 1.0, max_delay: float = 60.0, retryable_exceptions: tuple = None)`

Decorator for retry logic with exponential backoff

**Parameters:**
- `max_attempts` (int) = 3
- `backoff_factor` (float) = 2.0
- `initial_delay` (float) = 1.0
- `max_delay` (float) = 60.0
- `retryable_exceptions` (tuple) = None

### async_retry

`async_retry(config: RetryConfig = None)`

Async version of retry decorator

**Parameters:**
- `config` (RetryConfig) = None

### safe_execute

`safe_execute(func: Callable, error_handler: ErrorHandler, operation: str, default_return: Any = None, context: Dict[(str, Any)] = None, correlation_id: str = None)` -> Any

Safely execute a function with error handling

**Parameters:**
- `func` (Callable)
- `error_handler` (ErrorHandler)
- `operation` (str)
- `default_return` (Any) = None
- `context` (Dict[(str, Any)]) = None
- `correlation_id` (str) = None

### decorator

`decorator(func: Callable)` -> Callable

**Parameters:**
- `func` (Callable)

### wrapper

`wrapper()`
