"""
Unit tests for the Agent classes
"""

import pytest
import time
import json
from unittest.mock import MagicMock, patch, mock_open

from conductor.agent import ClaudeAgent, ClaudeCodeWrapper, AgentConfig, Task, TaskResult


class TestAgentConfig:
    """Test cases for AgentConfig class"""
    
    def test_agent_config_creation(self):
        """Test agent config creation with required fields"""
        config = AgentConfig(
            agent_id="test_agent",
            container_name="test_container",
            work_dir="/tmp/test"
        )
        
        assert config.agent_id == "test_agent"
        assert config.container_name == "test_container"
        assert config.work_dir == "/tmp/test"
        assert config.podman_image == "ubuntu:22.04"  # default
        assert config.memory_limit == "2g"  # default
        assert config.cpu_limit == "1.0"  # default
    
    def test_agent_config_with_custom_values(self):
        """Test agent config with custom values"""
        config = AgentConfig(
            agent_id="custom_agent",
            container_name="custom_container",
            work_dir="/custom/path",
            podman_image="alpine:latest",
            memory_limit="4g",
            cpu_limit="2.0"
        )
        
        assert config.podman_image == "alpine:latest"
        assert config.memory_limit == "4g"
        assert config.cpu_limit == "2.0"


class TestTask:
    """Test cases for Task class"""
    
    def test_task_creation_defaults(self):
        """Test task creation with defaults"""
        task = Task(task_id="test_001")
        
        assert task.task_id == "test_001"
        assert task.task_type == "generic"
        assert task.description == ""
        assert task.files == []
        assert task.parallel is False
        assert task.priority == 5
        assert task.timeout == 300.0
    
    def test_task_creation_full(self):
        """Test task creation with all fields"""
        task = Task(
            task_id="full_001",
            task_type="code_review",
            description="Review Python code",
            files=["main.py", "utils.py"],
            parallel=True,
            subtasks=[{"type": "analysis"}],
            priority=8,
            timeout=120.0
        )
        
        assert task.task_id == "full_001"
        assert task.task_type == "code_review"
        assert task.description == "Review Python code"
        assert task.files == ["main.py", "utils.py"]
        assert task.parallel is True
        assert task.subtasks == [{"type": "analysis"}]
        assert task.priority == 8
        assert task.timeout == 120.0


class TestTaskResult:
    """Test cases for TaskResult class"""
    
    def test_task_result_creation(self):
        """Test task result creation"""
        result = TaskResult(
            task_id="test_001",
            agent_id="agent_001",
            status="success",
            result={"issues": 3}
        )
        
        assert result.task_id == "test_001"
        assert result.agent_id == "agent_001"
        assert result.status == "success"
        assert result.result == {"issues": 3}
        assert result.error is None
        assert result.execution_time == 0.0
        assert result.timestamp is not None
    
    def test_task_result_with_error(self):
        """Test task result with error"""
        result = TaskResult(
            task_id="test_002",
            agent_id="agent_002",
            status="failed",
            result={},
            error="Connection timeout",
            execution_time=5.0
        )
        
        assert result.status == "failed"
        assert result.error == "Connection timeout"
        assert result.execution_time == 5.0


class TestClaudeCodeWrapper:
    """Test cases for ClaudeCodeWrapper class"""
    
    def test_wrapper_initialization(self, mock_agent_config):
        """Test wrapper initialization"""
        wrapper = ClaudeCodeWrapper(mock_agent_config)
        
        assert wrapper.config == mock_agent_config
        assert wrapper.process is None
        assert wrapper.container_id is None
        assert wrapper.is_running is False
    
    @patch('subprocess.run')
    def test_setup_container_success(self, mock_run, mock_agent_config):
        """Test successful container setup"""
        # Mock successful container creation
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "container_12345"
        mock_run.return_value.stderr = ""
        
        wrapper = ClaudeCodeWrapper(mock_agent_config)
        
        with patch.object(wrapper, '_install_base_tools'):
            with patch.object(wrapper, '_install_claude_code'):
                container_id = wrapper.setup_container()
        
        assert container_id == "container_12345"
        assert wrapper.container_id == "container_12345"
    
    @patch('subprocess.run')
    def test_setup_container_failure(self, mock_run, mock_agent_config):
        """Test container setup failure"""
        # Mock failed container creation
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Container creation failed"
        
        wrapper = ClaudeCodeWrapper(mock_agent_config)
        
        with pytest.raises(Exception, match="Container creation failed"):
            wrapper.setup_container()
    
    @patch('subprocess.run')
    def test_exec_in_container(self, mock_run, mock_agent_config):
        """Test command execution in container"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "command output"
        mock_run.return_value.stderr = ""
        
        wrapper = ClaudeCodeWrapper(mock_agent_config)
        result = wrapper.exec_in_container("echo hello")
        
        assert result.command == "echo hello"
        assert result.stdout == "command output"
        assert result.stderr == ""
        assert result.exit_code == 0
        assert isinstance(result.timestamp, float)
    
    @patch('subprocess.Popen')
    def test_start_claude_code(self, mock_popen, mock_agent_config):
        """Test Claude Code process start"""
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        
        wrapper = ClaudeCodeWrapper(mock_agent_config)
        
        with patch.object(wrapper, '_start_output_readers'):
            wrapper.start_claude_code(headless=True)
        
        assert wrapper.process == mock_process
        assert wrapper.is_running is True
        
        # Verify correct command
        call_args = mock_popen.call_args[0][0]
        assert "claude-code" in call_args
        assert "--headless" in call_args
    
    def test_send_command(self, mock_agent_config):
        """Test sending command to Claude Code"""
        wrapper = ClaudeCodeWrapper(mock_agent_config)
        wrapper.is_running = True
        
        mock_process = MagicMock()
        wrapper.process = mock_process
        
        wrapper.send_command("test command")
        
        mock_process.stdin.write.assert_called_with("test command\n")
        mock_process.stdin.flush.assert_called_once()
    
    def test_send_command_not_running(self, mock_agent_config):
        """Test sending command when not running"""
        wrapper = ClaudeCodeWrapper(mock_agent_config)
        wrapper.is_running = False
        
        with pytest.raises(Exception, match="Claude Code is not running"):
            wrapper.send_command("test command")
    
    def test_read_output(self, mock_agent_config):
        """Test reading output from Claude Code"""
        wrapper = ClaudeCodeWrapper(mock_agent_config)
        
        # Simulate output in queue
        wrapper.output_queue.put(("stdout", "line 1"))
        wrapper.output_queue.put(("stderr", "warning"))
        wrapper.output_queue.put(("stdout", "line 2"))
        
        outputs = wrapper.read_output(timeout=0.1)
        
        assert len(outputs) == 3
        assert outputs[0] == ("stdout", "line 1")
        assert outputs[1] == ("stderr", "warning")
        assert outputs[2] == ("stdout", "line 2")
    
    def test_stop_process(self, mock_agent_config):
        """Test stopping Claude Code process"""
        wrapper = ClaudeCodeWrapper(mock_agent_config)
        wrapper.is_running = True
        
        mock_process = MagicMock()
        wrapper.process = mock_process
        
        wrapper.stop()
        
        assert wrapper.is_running is False
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once()
    
    @patch('subprocess.run')
    def test_cleanup_container(self, mock_run, mock_agent_config):
        """Test container cleanup"""
        wrapper = ClaudeCodeWrapper(mock_agent_config)
        wrapper.container_id = "test_container_id"
        
        wrapper.cleanup_container()
        
        # Should call podman stop and rm
        assert mock_run.call_count == 2


class TestClaudeAgent:
    """Test cases for ClaudeAgent class"""
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    @patch('conductor.agent.UnixSocketChannel')
    def test_agent_initialization(self, mock_socket, mock_wrapper):
        """Test agent initialization"""
        agent = ClaudeAgent("test_agent")
        
        assert agent.agent_id == "test_agent"
        assert agent.config.agent_id == "test_agent"
        assert agent.config.container_name == "claude_agent_test_agent"
        assert agent.is_running is False
        assert agent.current_task is None
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    @patch('conductor.agent.UnixSocketChannel')
    @patch('os.makedirs')
    def test_agent_start_success(self, mock_makedirs, mock_socket, mock_wrapper_class):
        """Test successful agent start"""
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        
        mock_channel = MagicMock()
        mock_socket.return_value = mock_channel
        
        agent = ClaudeAgent("test_agent")
        
        with patch('threading.Thread'):
            agent.start()
        
        assert agent.is_running is True
        mock_wrapper.setup_container.assert_called_once()
        mock_wrapper.start_claude_code.assert_called_once()
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_agent_start_failure(self, mock_wrapper_class):
        """Test agent start failure"""
        mock_wrapper = MagicMock()
        mock_wrapper.setup_container.side_effect = Exception("Setup failed")
        mock_wrapper_class.return_value = mock_wrapper
        
        agent = ClaudeAgent("test_agent")
        
        with pytest.raises(Exception, match="Setup failed"):
            agent.start()
    
    def test_agent_stop(self):
        """Test agent stop"""
        agent = ClaudeAgent("test_agent")
        agent.is_running = True
        
        mock_wrapper = MagicMock()
        mock_channel = MagicMock()
        agent.wrapper = mock_wrapper
        agent.channel = mock_channel
        
        agent.stop()
        
        assert agent.is_running is False
        mock_wrapper.stop.assert_called_once()
        mock_wrapper.cleanup_container.assert_called_once()
        mock_channel.close.assert_called_once()
    
    def test_execute_task_code_review(self, mock_agent_config):
        """Test code review task execution"""
        agent = ClaudeAgent("test_agent")
        agent.config = mock_agent_config
        
        # Mock wrapper
        mock_wrapper = MagicMock()
        mock_wrapper.read_output.return_value = [
            ("stdout", '{"type": "review", "issues": 3}')
        ]
        agent.wrapper = mock_wrapper
        
        task = Task(
            task_id="review_001",
            task_type="code_review",
            files=["test.py"]
        )
        
        with patch.object(agent, '_copy_file_to_container'):
            result = agent.execute_task(task)
        
        assert result.status == "success"
        assert result.task_id == "review_001"
        assert result.agent_id == "test_agent"
        assert "files_reviewed" in result.result
    
    def test_execute_task_generic(self, mock_agent_config):
        """Test generic task execution"""
        agent = ClaudeAgent("test_agent")
        agent.config = mock_agent_config
        
        mock_wrapper = MagicMock()
        mock_wrapper.read_output.return_value = [
            ("stdout", "task completed")
        ]
        agent.wrapper = mock_wrapper
        
        task = Task(
            task_id="generic_001",
            task_type="generic",
            description="echo hello"
        )
        
        result = agent.execute_task(task)
        
        assert result.status == "success"
        mock_wrapper.send_command.assert_called_with("echo hello")
    
    def test_execute_task_failure(self, mock_agent_config):
        """Test task execution failure"""
        agent = ClaudeAgent("test_agent")
        agent.config = mock_agent_config
        
        mock_wrapper = MagicMock()
        mock_wrapper.send_command.side_effect = Exception("Command failed")
        agent.wrapper = mock_wrapper
        
        task = Task(task_id="fail_001", description="failing command")
        
        result = agent.execute_task(task)
        
        assert result.status == "failed"
        assert "Command failed" in result.error
    
    @patch('subprocess.run')
    def test_copy_file_to_container(self, mock_run, mock_agent_config, temp_dir):
        """Test copying file to container"""
        agent = ClaudeAgent("test_agent")
        agent.config = mock_agent_config
        
        # Create test file
        test_file = f"{temp_dir}/test.py"
        with open(test_file, 'w') as f:
            f.write("print('hello')")
        
        agent._copy_file_to_container(test_file)
        
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "cp" in call_args
        assert test_file in call_args
    
    def test_parse_review_output(self):
        """Test parsing review output"""
        agent = ClaudeAgent("test_agent")
        
        # Test valid JSON output
        outputs = [("stdout", '{"issues": 5, "suggestions": ["use type hints"]}')]
        result = agent._parse_review_output(outputs)
        
        assert result["issues"] == 5
        assert "suggestions" in result
        
        # Test invalid JSON output
        outputs = [("stdout", "invalid json")]
        result = agent._parse_review_output(outputs)
        
        assert "raw_output" in result
        assert result["issues"] == 0
    
    def test_format_output(self):
        """Test output formatting"""
        agent = ClaudeAgent("test_agent")
        
        outputs = [
            ("stdout", "line 1"),
            ("stderr", "warning"),
            ("stdout", "line 2")
        ]
        
        formatted = agent._format_output(outputs)
        expected = "[stdout] line 1\n[stderr] warning\n[stdout] line 2"
        
        assert formatted == expected
    
    def test_handle_task_request(self):
        """Test handling task request message"""
        from conductor.protocol import AgentMessage, MessageType
        
        agent = ClaudeAgent("test_agent")
        
        # Mock protocol
        mock_protocol = MagicMock()
        agent.protocol = mock_protocol
        
        # Create task request message
        message = AgentMessage(
            message_id="msg_001",
            sender_id="orchestrator",
            receiver_id="test_agent",
            message_type=MessageType.TASK_REQUEST,
            payload={
                "task_id": "request_001",
                "task_type": "code_review",
                "description": "Review code",
                "files": ["test.py"]
            },
            timestamp=time.time()
        )
        
        with patch.object(agent, 'execute_task') as mock_execute:
            mock_result = TaskResult("request_001", "test_agent", "success", {})
            mock_execute.return_value = mock_result
            
            agent._handle_task_request(message)
            
            mock_execute.assert_called_once()
            mock_protocol.send_task_response.assert_called_once()