"""
Utility functions and helpers for Claude Conductor
"""

import os
import shutil
import time
import logging
import yaml
import json
import hashlib
import subprocess
import functools
from typing import Any, Dict, List, Optional, Union, Callable
from pathlib import Path
import psutil


class ConfigValidationError(Exception):
    """Configuration validation error"""
    pass


def ensure_directory_exists(path: str) -> None:
    """Ensure directory exists, create if necessary"""
    os.makedirs(path, exist_ok=True)


def safe_file_copy(source: str, destination: str) -> None:
    """Safely copy file with error handling"""
    if not os.path.exists(source):
        raise FileNotFoundError(f"Source file not found: {source}")
    
    # Ensure destination directory exists
    dest_dir = os.path.dirname(destination)
    if dest_dir:
        ensure_directory_exists(dest_dir)
    
    shutil.copy2(source, destination)


def cleanup_temp_files(file_paths: List[str]) -> None:
    """Clean up temporary files"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError:
            pass  # Ignore cleanup errors


def load_yaml_config(config_file: str, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Load YAML configuration with defaults"""
    config = defaults.copy() if defaults else {}
    
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                loaded_config = yaml.safe_load(f) or {}
                config.update(loaded_config)
        except yaml.YAMLError as e:
            logging.warning(f"Error loading config file {config_file}: {e}")
    
    return config


def validate_config(config: Dict[str, Any], schema: Dict[str, Dict[str, Any]]) -> bool:
    """Validate configuration against schema"""
    for key, rules in schema.items():
        if key not in config:
            continue
        
        value = config[key]
        
        # Type validation
        expected_types = rules.get("type")
        if expected_types:
            if not isinstance(expected_types, (list, tuple)):
                expected_types = [expected_types]
            
            if not any(isinstance(value, t) for t in expected_types):
                raise ConfigValidationError(f"{key}: expected {expected_types}, got {type(value)}")
        
        # Range validation
        if "min" in rules and value < rules["min"]:
            raise ConfigValidationError(f"{key}: value {value} below minimum {rules['min']}")
        
        if "max" in rules and value > rules["max"]:
            raise ConfigValidationError(f"{key}: value {value} above maximum {rules['max']}")
        
        # Choice validation
        if "choices" in rules and value not in rules["choices"]:
            raise ConfigValidationError(f"{key}: value {value} not in {rules['choices']}")
    
    return True


def retry(max_attempts: int = 3, delay: float = 1.0, backoff_factor: float = 1.0):
    """Retry decorator with exponential backoff"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
            
            raise last_exception
        return wrapper
    return decorator


def setup_logger(name: str, level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Setup logger with consistent formatting"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)8s] %(name)s: %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        ensure_directory_exists(os.path.dirname(log_file))
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def format_execution_time(seconds: float) -> str:
    """Format execution time in human-readable format"""
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.2f}s"
    else:
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        remaining_seconds = seconds % 60
        return f"{hours}h {remaining_minutes}m {remaining_seconds:.2f}s"


def format_memory_size(bytes_size: int) -> str:
    """Format memory size in human-readable format"""
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    size = float(bytes_size)
    
    for unit in units:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    
    return f"{size:.1f} PB"


def get_system_stats() -> Dict[str, Any]:
    """Get current system statistics"""
    memory = psutil.virtual_memory()
    
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": memory.percent,
        "memory_total": memory.total,
        "memory_available": memory.available,
        "memory_used": memory.used,
        "timestamp": time.time()
    }


def check_container_runtime() -> Optional[str]:
    """Check which container runtime is available"""
    runtimes = ["podman", "docker"]
    
    for runtime in runtimes:
        try:
            result = subprocess.run(
                ["which", runtime], 
                capture_output=True, 
                check=False
            )
            if result.returncode == 0:
                return runtime
        except (subprocess.SubprocessError, FileNotFoundError):
            continue
    
    return None


def get_timestamp() -> str:
    """Get current timestamp in ISO format suitable for filenames"""
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def generate_unique_id(prefix: str = "") -> str:
    """Generate unique identifier"""
    timestamp = str(time.time())
    random_part = hashlib.md5(timestamp.encode()).hexdigest()[:8]
    return f"{prefix}{int(time.time())}_{random_part}"


def validate_file_permissions(file_path: str, readable: bool = False, writable: bool = False) -> bool:
    """Validate file permissions"""
    if not os.path.exists(file_path):
        return False
    
    if readable and not os.access(file_path, os.R_OK):
        return False
    
    if writable and not os.access(file_path, os.W_OK):
        return False
    
    return True


def calculate_task_priority(base_priority: int, age_seconds: int, importance_factor: float = 1.0) -> float:
    """Calculate dynamic task priority based on age and importance"""
    # Increase priority for older tasks (aging factor)
    aging_bonus = min(age_seconds / 3600, 2.0)  # Max 2 points for tasks older than 1 hour
    
    return base_priority * importance_factor + aging_bonus


def estimate_task_duration(task_type: str, file_count: int = 1, **kwargs) -> int:
    """Estimate task duration in seconds"""
    base_durations = {
        "code_review": 30,      # 30 seconds per file
        "refactor": 60,         # 1 minute per file
        "test_generation": 45,  # 45 seconds per file
        "analysis": 20,         # 20 seconds per file
        "generic": 30           # Default
    }
    
    base_duration = base_durations.get(task_type, 30)
    return base_duration * file_count


def safe_execute(func: Callable, default: Any = None, *args, **kwargs) -> Any:
    """Safely execute function with default return on error"""
    try:
        return func(*args, **kwargs)
    except Exception:
        return default


class error_context:
    """Context manager for error handling"""
    
    def __init__(self, operation: str, error_handler: Callable[[Exception], None]):
        self.operation = operation
        self.error_handler = error_handler
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            error_msg = f"Error in {self.operation}: {exc_val}"
            self.error_handler(Exception(error_msg))
        return True  # Suppress the exception


class SimpleCache:
    """Simple in-memory cache with TTL"""
    
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
    
    def get(self, key: str, ttl: int = 300) -> Any:
        """Get value from cache if not expired"""
        if key in self._cache:
            if time.time() - self._timestamps[key] < ttl:
                return self._cache[key]
            else:
                # Expired, remove from cache
                del self._cache[key]
                del self._timestamps[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Set value in cache"""
        self._cache[key] = value
        self._timestamps[key] = time.time()
    
    def clear(self) -> None:
        """Clear all cache entries"""
        self._cache.clear()
        self._timestamps.clear()


# Global cache instance
_cache = SimpleCache()


def cached(ttl: int = 300):
    """Decorator for caching function results"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Try to get from cache
            result = _cache.get(key, ttl)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            _cache.set(key, result)
            return result
        return wrapper
    return decorator


def get_file_hash(file_path: str) -> str:
    """Get MD5 hash of file content"""
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, IOError):
        return ""


def is_binary_file(file_path: str) -> bool:
    """Check if file is binary"""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except (OSError, IOError):
        return True


def get_file_info(file_path: str) -> Dict[str, Any]:
    """Get comprehensive file information"""
    if not os.path.exists(file_path):
        return {}
    
    stat = os.stat(file_path)
    
    return {
        "path": file_path,
        "name": os.path.basename(file_path),
        "size": stat.st_size,
        "modified": stat.st_mtime,
        "created": stat.st_ctime,
        "is_binary": is_binary_file(file_path),
        "hash": get_file_hash(file_path),
        "extension": os.path.splitext(file_path)[1].lower()
    }


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to maximum length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def parse_time_duration(duration_str: str) -> int:
    """Parse time duration string to seconds"""
    multipliers = {
        's': 1, 'sec': 1, 'second': 1, 'seconds': 1,
        'm': 60, 'min': 60, 'minute': 60, 'minutes': 60,
        'h': 3600, 'hour': 3600, 'hours': 3600,
        'd': 86400, 'day': 86400, 'days': 86400
    }
    
    duration_str = duration_str.strip().lower()
    
    # Try to parse number with unit
    for unit, multiplier in multipliers.items():
        if duration_str.endswith(unit):
            try:
                number = float(duration_str[:-len(unit)].strip())
                return int(number * multiplier)
            except ValueError:
                continue
    
    # Try to parse as pure number (assume seconds)
    try:
        return int(float(duration_str))
    except ValueError:
        raise ValueError(f"Invalid duration format: {duration_str}")