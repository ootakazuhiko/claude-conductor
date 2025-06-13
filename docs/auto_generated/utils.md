# utils

Utility functions and helpers for Claude Conductor

## Classes

### ConfigValidationError

**Inherits from:** Exception

Configuration validation error

### error_context

Context manager for error handling

#### Methods

### SimpleCache

Simple in-memory cache with TTL

#### Methods

##### get

`get(key: str, ttl: int = 300)` -> Any

Get value from cache if not expired

**Parameters:**
- `key` (str)
- `ttl` (int) = 300

##### set

`set(key: str, value: Any)` -> None

Set value in cache

**Parameters:**
- `key` (str)
- `value` (Any)

##### clear

`clear()` -> None

Clear all cache entries

## Functions

### ensure_directory_exists

`ensure_directory_exists(path: str)` -> None

Ensure directory exists, create if necessary

**Parameters:**
- `path` (str)

### safe_file_copy

`safe_file_copy(source: str, destination: str)` -> None

Safely copy file with error handling

**Parameters:**
- `source` (str)
- `destination` (str)

### cleanup_temp_files

`cleanup_temp_files(file_paths: List[str])` -> None

Clean up temporary files

**Parameters:**
- `file_paths` (List[str])

### load_yaml_config

`load_yaml_config(config_file: str, defaults: Optional[Dict[(str, Any)]] = None)` -> Dict[(str, Any)]

Load YAML configuration with defaults

**Parameters:**
- `config_file` (str)
- `defaults` (Optional[Dict[(str, Any)]]) = None

### validate_config

`validate_config(config: Dict[(str, Any)], schema: Dict[(str, Dict[(str, Any)])])` -> bool

Validate configuration against schema

**Parameters:**
- `config` (Dict[(str, Any)])
- `schema` (Dict[(str, Dict[(str, Any)])])

### retry

`retry(max_attempts: int = 3, delay: float = 1.0, backoff_factor: float = 1.0)`

Retry decorator with exponential backoff

**Parameters:**
- `max_attempts` (int) = 3
- `delay` (float) = 1.0
- `backoff_factor` (float) = 1.0

### setup_logger

`setup_logger(name: str, level: str = 'INFO', log_file: Optional[str] = None)` -> logging.Logger

Setup logger with consistent formatting

**Parameters:**
- `name` (str)
- `level` (str) = 'INFO'
- `log_file` (Optional[str]) = None

### format_execution_time

`format_execution_time(seconds: float)` -> str

Format execution time in human-readable format

**Parameters:**
- `seconds` (float)

### format_memory_size

`format_memory_size(bytes_size: int)` -> str

Format memory size in human-readable format

**Parameters:**
- `bytes_size` (int)

### get_system_stats

`get_system_stats()` -> Dict[(str, Any)]

Get current system statistics

### check_container_runtime

`check_container_runtime()` -> Optional[str]

Check which container runtime is available

### get_timestamp

`get_timestamp()` -> str

Get current timestamp in ISO format suitable for filenames

### generate_unique_id

`generate_unique_id(prefix: str = '')` -> str

Generate unique identifier

**Parameters:**
- `prefix` (str) = ''

### validate_file_permissions

`validate_file_permissions(file_path: str, readable: bool = False, writable: bool = False)` -> bool

Validate file permissions

**Parameters:**
- `file_path` (str)
- `readable` (bool) = False
- `writable` (bool) = False

### calculate_task_priority

`calculate_task_priority(base_priority: int, age_seconds: int, importance_factor: float = 1.0)` -> float

Calculate dynamic task priority based on age and importance

**Parameters:**
- `base_priority` (int)
- `age_seconds` (int)
- `importance_factor` (float) = 1.0

### estimate_task_duration

`estimate_task_duration(task_type: str, file_count: int = 1)` -> int

Estimate task duration in seconds

**Parameters:**
- `task_type` (str)
- `file_count` (int) = 1

### safe_execute

`safe_execute(func: Callable, default: Any = None)` -> Any

Safely execute function with default return on error

**Parameters:**
- `func` (Callable)
- `default` (Any) = None

### cached

`cached(ttl: int = 300)`

Decorator for caching function results

**Parameters:**
- `ttl` (int) = 300

### get_file_hash

`get_file_hash(file_path: str)` -> str

Get MD5 hash of file content

**Parameters:**
- `file_path` (str)

### is_binary_file

`is_binary_file(file_path: str)` -> bool

Check if file is binary

**Parameters:**
- `file_path` (str)

### get_file_info

`get_file_info(file_path: str)` -> Dict[(str, Any)]

Get comprehensive file information

**Parameters:**
- `file_path` (str)

### truncate_string

`truncate_string(text: str, max_length: int = 100, suffix: str = '...')` -> str

Truncate string to maximum length

**Parameters:**
- `text` (str)
- `max_length` (int) = 100
- `suffix` (str) = '...'

### parse_time_duration

`parse_time_duration(duration_str: str)` -> int

Parse time duration string to seconds

**Parameters:**
- `duration_str` (str)

### decorator

`decorator(func: Callable)` -> Callable

**Parameters:**
- `func` (Callable)

### wrapper

`wrapper()`
