"""
Pytest configuration and shared fixtures
"""

import pytest
import tempfile
import shutil
import os
from unittest.mock import MagicMock, patch

from conductor import Orchestrator, Task, TaskResult, ClaudeAgent, AgentConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        "num_agents": 2,
        "max_workers": 4,
        "task_timeout": 30,
        "log_level": "INFO"
    }


@pytest.fixture
def mock_orchestrator(sample_config):
    """Create a mock orchestrator for testing"""
    orchestrator = Orchestrator()
    orchestrator.config = sample_config
    return orchestrator


@pytest.fixture
def sample_task():
    """Create a sample task for testing"""
    return Task(
        task_id="test_task_001",
        task_type="code_review",
        description="Test code review task",
        files=["test_file.py"],
        priority=5,
        timeout=60.0
    )


@pytest.fixture
def sample_task_result():
    """Create a sample task result for testing"""
    return TaskResult(
        task_id="test_task_001",
        agent_id="agent_001",
        status="success",
        result={"issues": 2, "suggestions": ["Add type hints"]},
        execution_time=1.5
    )


@pytest.fixture
def mock_agent_config():
    """Create mock agent configuration"""
    return AgentConfig(
        agent_id="test_agent",
        container_name="test_container",
        work_dir="/tmp/test_workspace"
    )


@pytest.fixture
def mock_container_runtime():
    """Mock container runtime calls"""
    with patch('subprocess.run') as mock_run:
        # Mock successful container operations
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "container_id_12345"
        mock_run.return_value.stderr = ""
        yield mock_run


@pytest.fixture
def mock_socket():
    """Mock Unix socket for testing communication"""
    with patch('socket.socket') as mock_socket:
        mock_socket_instance = MagicMock()
        mock_socket.return_value = mock_socket_instance
        yield mock_socket_instance


@pytest.fixture
def mock_process():
    """Mock subprocess.Popen for testing process management"""
    with patch('subprocess.Popen') as mock_popen:
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        
        # Mock process attributes
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()
        mock_process.returncode = 0
        
        yield mock_process


@pytest.fixture
def clean_environment():
    """Ensure clean test environment"""
    # Store original environment
    original_env = os.environ.copy()
    
    # Clean test-specific environment variables
    test_vars = [
        'AGENT_ID',
        'WORKSPACE',
        'ORCHESTRATOR_SOCKET'
    ]
    
    for var in test_vars:
        if var in os.environ:
            del os.environ[var]
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture(autouse=True)
def disable_actual_containers():
    """Disable actual container operations in tests"""
    with patch('conductor.agent.ClaudeCodeWrapper.setup_container'):
        with patch('conductor.agent.ClaudeCodeWrapper.start_claude_code'):
            with patch('conductor.agent.ClaudeCodeWrapper.cleanup_container'):
                yield


@pytest.fixture
def sample_agent_messages():
    """Sample agent messages for testing communication"""
    from conductor.protocol import AgentMessage, MessageType
    
    return [
        AgentMessage(
            message_id="msg_001",
            sender_id="agent_001",
            receiver_id="agent_002",
            message_type=MessageType.TASK_REQUEST,
            payload={"task_type": "code_review", "files": ["test.py"]},
            timestamp=1234567890.0
        ),
        AgentMessage(
            message_id="msg_002",
            sender_id="agent_002",
            receiver_id="agent_001",
            message_type=MessageType.TASK_RESPONSE,
            payload={"status": "success", "issues": 3},
            timestamp=1234567891.0,
            correlation_id="msg_001"
        )
    ]


@pytest.fixture
def mock_file_system(temp_dir):
    """Create mock file system structure for testing"""
    # Create sample Python files
    sample_code = '''
def hello_world():
    """A simple hello world function"""
    print("Hello, World!")

if __name__ == "__main__":
    hello_world()
'''
    
    files = {
        "main.py": sample_code,
        "utils.py": "def utility_function():\n    pass",
        "README.md": "# Test Project"
    }
    
    for filename, content in files.items():
        with open(os.path.join(temp_dir, filename), 'w') as f:
            f.write(content)
    
    return temp_dir


# Pytest plugins and markers
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    config.addinivalue_line(
        "markers", "container: marks tests that require container runtime"
    )


# Skip container tests if no container runtime available
def pytest_collection_modifyitems(config, items):
    """Modify test collection based on available resources"""
    import subprocess
    
    # Check if container runtime is available
    has_podman = subprocess.run(['which', 'podman'], capture_output=True).returncode == 0
    has_docker = subprocess.run(['which', 'docker'], capture_output=True).returncode == 0
    
    if not (has_podman or has_docker):
        skip_container = pytest.mark.skip(reason="No container runtime available")
        for item in items:
            if "container" in item.keywords:
                item.add_marker(skip_container)