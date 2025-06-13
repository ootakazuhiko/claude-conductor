"""
Unit tests for utility functions and helpers
"""

import pytest
import os
import time
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path


class TestFileOperations:
    """Test file operation utilities"""
    
    def test_ensure_directory_exists(self, temp_dir):
        """Test directory creation utility"""
        from conductor.utils import ensure_directory_exists
        
        test_path = os.path.join(temp_dir, "nested", "directory")
        ensure_directory_exists(test_path)
        
        assert os.path.exists(test_path)
        assert os.path.isdir(test_path)
    
    def test_safe_file_copy(self, temp_dir):
        """Test safe file copying"""
        from conductor.utils import safe_file_copy
        
        # Create source file
        source = os.path.join(temp_dir, "source.txt")
        with open(source, 'w') as f:
            f.write("test content")
        
        # Copy to destination
        dest = os.path.join(temp_dir, "dest.txt")
        safe_file_copy(source, dest)
        
        assert os.path.exists(dest)
        with open(dest, 'r') as f:
            assert f.read() == "test content"
    
    def test_safe_file_copy_nonexistent_source(self, temp_dir):
        """Test copying non-existent file"""
        from conductor.utils import safe_file_copy
        
        source = os.path.join(temp_dir, "nonexistent.txt")
        dest = os.path.join(temp_dir, "dest.txt")
        
        with pytest.raises(FileNotFoundError):
            safe_file_copy(source, dest)
    
    def test_cleanup_temp_files(self, temp_dir):
        """Test temporary file cleanup"""
        from conductor.utils import cleanup_temp_files
        
        # Create temporary files
        temp_files = []
        for i in range(3):
            temp_file = os.path.join(temp_dir, f"temp_{i}.tmp")
            with open(temp_file, 'w') as f:
                f.write(f"temp content {i}")
            temp_files.append(temp_file)
        
        cleanup_temp_files(temp_files)
        
        for temp_file in temp_files:
            assert not os.path.exists(temp_file)


class TestConfigurationHelpers:
    """Test configuration helper functions"""
    
    def test_load_yaml_config(self, temp_dir):
        """Test YAML configuration loading"""
        from conductor.utils import load_yaml_config
        
        config_file = os.path.join(temp_dir, "config.yaml")
        config_data = {
            "num_agents": 5,
            "timeout": 300,
            "settings": {
                "debug": True,
                "log_level": "INFO"
            }
        }
        
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        loaded_config = load_yaml_config(config_file)
        
        assert loaded_config["num_agents"] == 5
        assert loaded_config["timeout"] == 300
        assert loaded_config["settings"]["debug"] is True
    
    def test_load_yaml_config_with_defaults(self, temp_dir):
        """Test YAML config loading with default values"""
        from conductor.utils import load_yaml_config
        
        defaults = {
            "num_agents": 3,
            "timeout": 300,
            "debug": False
        }
        
        # Non-existent file should return defaults
        config = load_yaml_config("nonexistent.yaml", defaults)
        assert config == defaults
        
        # Partial config should merge with defaults
        config_file = os.path.join(temp_dir, "partial.yaml")
        partial_config = {"num_agents": 10}
        
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(partial_config, f)
        
        config = load_yaml_config(config_file, defaults)
        assert config["num_agents"] == 10  # From file
        assert config["timeout"] == 300    # From defaults
        assert config["debug"] is False    # From defaults
    
    def test_validate_config(self):
        """Test configuration validation"""
        from conductor.utils import validate_config, ConfigValidationError
        
        schema = {
            "num_agents": {"type": int, "min": 1, "max": 100},
            "timeout": {"type": [int, float], "min": 0},
            "log_level": {"type": str, "choices": ["DEBUG", "INFO", "WARNING", "ERROR"]}
        }
        
        # Valid config
        valid_config = {
            "num_agents": 5,
            "timeout": 300.0,
            "log_level": "INFO"
        }
        assert validate_config(valid_config, schema) is True
        
        # Invalid type
        with pytest.raises(ConfigValidationError):
            validate_config({"num_agents": "5"}, schema)
        
        # Out of range
        with pytest.raises(ConfigValidationError):
            validate_config({"num_agents": 200}, schema)
        
        # Invalid choice
        with pytest.raises(ConfigValidationError):
            validate_config({"log_level": "INVALID"}, schema)


class TestRetryDecorator:
    """Test retry decorator functionality"""
    
    def test_retry_success_first_attempt(self):
        """Test successful execution on first attempt"""
        from conductor.utils import retry
        
        @retry(max_attempts=3, delay=0.1)
        def successful_function():
            return "success"
        
        result = successful_function()
        assert result == "success"
    
    def test_retry_success_after_failures(self):
        """Test successful execution after failures"""
        from conductor.utils import retry
        
        attempt_count = 0
        
        @retry(max_attempts=3, delay=0.1)
        def eventually_successful():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Temporary failure")
            return "success"
        
        result = eventually_successful()
        assert result == "success"
        assert attempt_count == 3
    
    def test_retry_max_attempts_exceeded(self):
        """Test failure when max attempts exceeded"""
        from conductor.utils import retry
        
        @retry(max_attempts=2, delay=0.1)
        def always_fails():
            raise Exception("Always fails")
        
        with pytest.raises(Exception, match="Always fails"):
            always_fails()
    
    def test_retry_with_exponential_backoff(self):
        """Test retry with exponential backoff"""
        from conductor.utils import retry
        
        start_time = time.time()
        
        @retry(max_attempts=3, delay=0.1, backoff_factor=2)
        def failing_function():
            raise Exception("Test failure")
        
        with pytest.raises(Exception):
            failing_function()
        
        elapsed = time.time() - start_time
        # Should have delays of 0.1, 0.2, so minimum total delay ~0.3
        assert elapsed >= 0.3


class TestLoggingHelpers:
    """Test logging utility functions"""
    
    def test_setup_logger(self):
        """Test logger setup"""
        from conductor.utils import setup_logger
        
        logger = setup_logger("test_logger", level="INFO")
        
        assert logger.name == "test_logger"
        assert logger.level == 20  # INFO level
    
    def test_setup_logger_with_file(self, temp_dir):
        """Test logger setup with file output"""
        from conductor.utils import setup_logger
        
        log_file = os.path.join(temp_dir, "test.log")
        logger = setup_logger("test_logger", level="DEBUG", log_file=log_file)
        
        logger.info("Test message")
        
        assert os.path.exists(log_file)
        with open(log_file, 'r') as f:
            content = f.read()
            assert "Test message" in content
    
    def test_format_execution_time(self):
        """Test execution time formatting"""
        from conductor.utils import format_execution_time
        
        assert format_execution_time(1.5) == "1.50s"
        assert format_execution_time(65.3) == "1m 5.30s"
        assert format_execution_time(3665.0) == "1h 1m 5.00s"
    
    def test_format_memory_size(self):
        """Test memory size formatting"""
        from conductor.utils import format_memory_size
        
        assert format_memory_size(1024) == "1.0 KB"
        assert format_memory_size(1048576) == "1.0 MB"
        assert format_memory_size(1073741824) == "1.0 GB"
        assert format_memory_size(1500000) == "1.4 MB"


class TestSystemHelpers:
    """Test system utility functions"""
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    def test_get_system_stats(self, mock_memory, mock_cpu):
        """Test system statistics collection"""
        from conductor.utils import get_system_stats
        
        # Mock system metrics
        mock_cpu.return_value = 45.5
        mock_memory.return_value.percent = 67.2
        mock_memory.return_value.total = 8589934592  # 8GB
        mock_memory.return_value.available = 2684354560  # ~2.5GB
        
        stats = get_system_stats()
        
        assert stats["cpu_percent"] == 45.5
        assert stats["memory_percent"] == 67.2
        assert stats["memory_total"] > 0
        assert stats["memory_available"] > 0
    
    @patch('subprocess.run')
    def test_check_container_runtime(self, mock_run):
        """Test container runtime detection"""
        from conductor.utils import check_container_runtime
        
        # Test podman available
        mock_run.side_effect = [
            MagicMock(returncode=0),  # which podman
            MagicMock(returncode=1)   # which docker (not found)
        ]
        
        runtime = check_container_runtime()
        assert runtime == "podman"
        
        # Test docker available
        mock_run.side_effect = [
            MagicMock(returncode=1),  # which podman (not found)
            MagicMock(returncode=0)   # which docker
        ]
        
        runtime = check_container_runtime()
        assert runtime == "docker"
        
        # Test no runtime available
        mock_run.side_effect = [
            MagicMock(returncode=1),  # which podman (not found)
            MagicMock(returncode=1)   # which docker (not found)
        ]
        
        runtime = check_container_runtime()
        assert runtime is None
    
    def test_generate_unique_id(self):
        """Test unique ID generation"""
        from conductor.utils import generate_unique_id
        
        id1 = generate_unique_id()
        id2 = generate_unique_id()
        
        assert id1 != id2
        assert len(id1) > 0
        assert len(id2) > 0
        
        # Test with prefix
        id_with_prefix = generate_unique_id("test_")
        assert id_with_prefix.startswith("test_")
    
    def test_validate_file_permissions(self, temp_dir):
        """Test file permission validation"""
        from conductor.utils import validate_file_permissions
        
        # Create test file
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        
        # Should be readable by default
        assert validate_file_permissions(test_file, readable=True)
        
        # Test writable
        assert validate_file_permissions(test_file, writable=True)
        
        # Test non-existent file
        assert not validate_file_permissions("nonexistent.txt", readable=True)


class TestTaskHelpers:
    """Test task-related utility functions"""
    
    def test_calculate_task_priority(self):
        """Test task priority calculation"""
        from conductor.utils import calculate_task_priority
        
        # High priority: recent, important
        priority1 = calculate_task_priority(
            base_priority=8,
            age_seconds=60,
            importance_factor=1.5
        )
        assert priority1 > 8
        
        # Lower priority: old, less important
        priority2 = calculate_task_priority(
            base_priority=5,
            age_seconds=3600,
            importance_factor=0.8
        )
        assert priority2 < priority1
    
    def test_estimate_task_duration(self):
        """Test task duration estimation"""
        from conductor.utils import estimate_task_duration
        
        # Code review tasks
        duration = estimate_task_duration("code_review", file_count=5)
        assert duration > 0
        
        # Generic tasks
        duration = estimate_task_duration("generic", file_count=1)
        assert duration > 0
        
        # Unknown task type should have default duration
        duration = estimate_task_duration("unknown_type")
        assert duration > 0


class TestErrorHandling:
    """Test error handling utilities"""
    
    def test_safe_execute(self):
        """Test safe function execution"""
        from conductor.utils import safe_execute
        
        # Successful execution
        result = safe_execute(lambda: "success", default="failed")
        assert result == "success"
        
        # Failed execution with default
        result = safe_execute(lambda: 1/0, default="failed")
        assert result == "failed"
        
        # Failed execution without default
        result = safe_execute(lambda: 1/0)
        assert result is None
    
    def test_error_context_manager(self):
        """Test error context manager"""
        from conductor.utils import error_context
        
        errors = []
        
        with error_context("Test operation", errors.append):
            raise ValueError("Test error")
        
        assert len(errors) == 1
        assert "Test operation" in str(errors[0])
        assert "Test error" in str(errors[0])


class TestCacheUtilities:
    """Test caching utilities"""
    
    def test_simple_cache(self):
        """Test simple function caching"""
        from conductor.utils import cached
        
        call_count = 0
        
        @cached(ttl=60)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call with same argument (should use cache)
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Should not increment
        
        # Different argument
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2
    
    def test_cache_expiration(self):
        """Test cache expiration"""
        from conductor.utils import cached
        
        call_count = 0
        
        @cached(ttl=0.1)  # Very short TTL
        def short_lived_cache(x):
            nonlocal call_count
            call_count += 1
            return x
        
        # First call
        result1 = short_lived_cache(1)
        assert call_count == 1
        
        # Wait for cache to expire
        time.sleep(0.2)
        
        # Second call should hit function again
        result2 = short_lived_cache(1)
        assert call_count == 2