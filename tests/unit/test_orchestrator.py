"""
Unit tests for the Orchestrator class
"""

import pytest
import time
from unittest.mock import MagicMock, patch, mock_open
import yaml

from conductor import Orchestrator, Task, TaskResult, create_task


class TestOrchestrator:
    """Test cases for Orchestrator class"""
    
    def test_orchestrator_initialization(self):
        """Test orchestrator initialization with default config"""
        orchestrator = Orchestrator()
        
        assert orchestrator.config["num_agents"] == 3
        assert orchestrator.config["max_workers"] == 10
        assert orchestrator.config["task_timeout"] == 300
        assert len(orchestrator.agents) == 0
        assert len(orchestrator.results) == 0
    
    def test_orchestrator_with_config_file(self, temp_dir):
        """Test orchestrator initialization with config file"""
        config_data = {
            "num_agents": 5,
            "max_workers": 20,
            "task_timeout": 600
        }
        
        config_file = f"{temp_dir}/test_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        orchestrator = Orchestrator(config_file)
        
        assert orchestrator.config["num_agents"] == 5
        assert orchestrator.config["max_workers"] == 20
        assert orchestrator.config["task_timeout"] == 600
    
    def test_orchestrator_with_invalid_config(self):
        """Test orchestrator with invalid config file"""
        # Non-existent file should use defaults
        orchestrator = Orchestrator("non_existent_config.yaml")
        assert orchestrator.config["num_agents"] == 3
    
    @patch('conductor.orchestrator.ClaudeAgent')
    @patch('conductor.orchestrator.UnixSocketChannel')
    def test_orchestrator_start(self, mock_socket, mock_agent_class):
        """Test orchestrator start process"""
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 2
        
        orchestrator.start()
        
        # Should create 2 agents
        assert mock_agent_class.call_count == 2
        assert len(orchestrator.agents) == 2
        
        # Should call start on each agent
        assert mock_agent.start.call_count == 2
    
    @patch('conductor.orchestrator.ClaudeAgent')
    def test_orchestrator_start_with_agent_failure(self, mock_agent_class):
        """Test orchestrator start with one agent failing"""
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        
        # Make the first agent fail to start
        mock_agent.start.side_effect = [Exception("Agent failed"), None]
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 2
        
        orchestrator.start()
        
        # Should have only 1 agent (second one succeeded)
        assert len(orchestrator.agents) == 1
    
    def test_orchestrator_stop(self, mock_orchestrator):
        """Test orchestrator stop process"""
        # Add mock agents
        mock_agent1 = MagicMock()
        mock_agent2 = MagicMock()
        mock_orchestrator.agents = {
            "agent_001": mock_agent1,
            "agent_002": mock_agent2
        }
        
        # Mock broker channel
        mock_orchestrator.broker_channel = MagicMock()
        mock_orchestrator.executor = MagicMock()
        
        mock_orchestrator.stop()
        
        # Should stop all agents
        mock_agent1.stop.assert_called_once()
        mock_agent2.stop.assert_called_once()
        
        # Should close broker channel
        mock_orchestrator.broker_channel.close.assert_called_once()
        
        # Should shutdown executor
        mock_orchestrator.executor.shutdown.assert_called_once()
    
    def test_execute_task_success(self, mock_orchestrator, sample_task):
        """Test successful task execution"""
        # Mock available agent
        mock_agent = MagicMock()
        mock_agent.is_running = True
        mock_agent.current_task = None
        mock_agent.agent_id = "agent_001"
        
        # Mock task execution result
        task_result = TaskResult(
            task_id=sample_task.task_id,
            agent_id="agent_001",
            status="success",
            result={"issues": 2},
            execution_time=1.5
        )
        mock_agent.execute_task.return_value = task_result
        
        mock_orchestrator.agents = {"agent_001": mock_agent}
        mock_orchestrator._get_available_agent = MagicMock(return_value=mock_agent)
        
        # Mock executor
        mock_future = MagicMock()
        mock_future.result.return_value = task_result
        mock_orchestrator.executor.submit.return_value = mock_future
        
        result = mock_orchestrator.execute_task(sample_task)
        
        assert result.status == "success"
        assert result.agent_id == "agent_001"
        assert result.task_id == sample_task.task_id
        assert mock_orchestrator.results[sample_task.task_id] == result
    
    def test_execute_task_no_agents(self, mock_orchestrator, sample_task):
        """Test task execution with no available agents"""
        mock_orchestrator.agents = {}
        mock_orchestrator._get_available_agent = MagicMock(return_value=None)
        
        result = mock_orchestrator.execute_task(sample_task)
        
        assert result.status == "failed"
        assert result.error == "No available agents"
        assert result.agent_id == "none"
    
    def test_execute_task_timeout(self, mock_orchestrator, sample_task):
        """Test task execution timeout"""
        mock_agent = MagicMock()
        mock_orchestrator._get_available_agent = MagicMock(return_value=mock_agent)
        
        # Mock executor to raise timeout
        mock_future = MagicMock()
        mock_future.result.side_effect = TimeoutError("Task timeout")
        mock_orchestrator.executor.submit.return_value = mock_future
        
        result = mock_orchestrator.execute_task(sample_task)
        
        assert result.status == "timeout"
        assert result.error == "Task execution timeout"
    
    def test_execute_parallel_task(self, mock_orchestrator):
        """Test parallel task execution"""
        # Create parallel task
        parallel_task = Task(
            task_id="parallel_001",
            task_type="analysis",
            parallel=True,
            subtasks=[
                {"type": "code_review", "description": "Review part 1"},
                {"type": "code_review", "description": "Review part 2"}
            ]
        )
        
        # Mock agents
        mock_agent1 = MagicMock()
        mock_agent1.agent_id = "agent_001"
        mock_agent2 = MagicMock()
        mock_agent2.agent_id = "agent_002"
        
        mock_orchestrator._get_available_agent = MagicMock(
            side_effect=[mock_agent1, mock_agent2]
        )
        
        # Mock futures
        result1 = TaskResult("parallel_001_sub0", "agent_001", "success", {})
        result2 = TaskResult("parallel_001_sub1", "agent_002", "success", {})
        
        mock_future1 = MagicMock()
        mock_future1.result.return_value = result1
        mock_future2 = MagicMock()
        mock_future2.result.return_value = result2
        
        mock_orchestrator.executor.submit.side_effect = [mock_future1, mock_future2]
        
        results = mock_orchestrator.execute_parallel_task(parallel_task)
        
        assert len(results) == 2
        assert all(r.status == "success" for r in results)
    
    def test_get_available_agent(self, mock_orchestrator):
        """Test agent selection logic"""
        # Create mock agents
        busy_agent = MagicMock()
        busy_agent.is_running = True
        busy_agent.current_task = MagicMock()  # Busy
        
        available_agent = MagicMock()
        available_agent.is_running = True
        available_agent.current_task = None  # Available
        
        stopped_agent = MagicMock()
        stopped_agent.is_running = False
        stopped_agent.current_task = None
        
        mock_orchestrator.agents = {
            "busy": busy_agent,
            "available": available_agent,
            "stopped": stopped_agent
        }
        
        result = mock_orchestrator._get_available_agent()
        assert result == available_agent
    
    def test_get_available_agent_all_busy(self, mock_orchestrator):
        """Test agent selection when all agents are busy"""
        busy_agent1 = MagicMock()
        busy_agent1.is_running = True
        busy_agent1.current_task = MagicMock()
        
        busy_agent2 = MagicMock()
        busy_agent2.is_running = True
        busy_agent2.current_task = MagicMock()
        
        mock_orchestrator.agents = {
            "busy1": busy_agent1,
            "busy2": busy_agent2
        }
        
        # Should return first agent as fallback
        result = mock_orchestrator._get_available_agent()
        assert result == busy_agent1
    
    def test_get_available_agent_no_agents(self, mock_orchestrator):
        """Test agent selection with no agents"""
        mock_orchestrator.agents = {}
        
        result = mock_orchestrator._get_available_agent()
        assert result is None
    
    def test_update_stats(self, mock_orchestrator):
        """Test statistics update"""
        # Test successful task
        success_result = TaskResult("task1", "agent1", "success", {}, execution_time=1.5)
        mock_orchestrator._update_stats(success_result)
        
        assert mock_orchestrator.stats["tasks_completed"] == 1
        assert mock_orchestrator.stats["tasks_failed"] == 0
        assert mock_orchestrator.stats["total_execution_time"] == 1.5
        
        # Test failed task
        failed_result = TaskResult("task2", "agent1", "failed", {}, execution_time=0.5)
        mock_orchestrator._update_stats(failed_result)
        
        assert mock_orchestrator.stats["tasks_completed"] == 1
        assert mock_orchestrator.stats["tasks_failed"] == 1
        assert mock_orchestrator.stats["total_execution_time"] == 2.0
    
    def test_get_agent_status(self, mock_orchestrator):
        """Test agent status retrieval"""
        mock_agent = MagicMock()
        mock_agent.is_running = True
        mock_agent.current_task = None
        mock_agent.health_check_failed = 0
        mock_agent.config.container_name = "test_container"
        
        mock_orchestrator.agents = {"agent_001": mock_agent}
        
        status = mock_orchestrator.get_agent_status()
        
        assert "agent_001" in status
        assert status["agent_001"]["running"] is True
        assert status["agent_001"]["current_task"] is None
        assert status["agent_001"]["health_check_failed"] == 0
        assert status["agent_001"]["container_name"] == "test_container"
    
    def test_get_statistics(self, mock_orchestrator):
        """Test statistics retrieval"""
        mock_orchestrator.stats = {
            "start_time": time.time() - 100,
            "tasks_completed": 5,
            "tasks_failed": 1,
            "total_execution_time": 10.0
        }
        
        # Mock agents
        running_agent = MagicMock()
        running_agent.is_running = True
        stopped_agent = MagicMock()
        stopped_agent.is_running = False
        
        mock_orchestrator.agents = {
            "running": running_agent,
            "stopped": stopped_agent
        }
        
        stats = mock_orchestrator.get_statistics()
        
        assert stats["tasks_completed"] == 5
        assert stats["tasks_failed"] == 1
        assert stats["total_execution_time"] == 10.0
        assert stats["active_agents"] == 1
        assert stats["total_agents"] == 2
        assert "runtime" in stats
        assert "avg_execution_time" in stats


class TestCreateTask:
    """Test cases for create_task helper function"""
    
    def test_create_task_defaults(self):
        """Test task creation with defaults"""
        task = create_task()
        
        assert task.task_type == "generic"
        assert task.description == ""
        assert task.files == []
        assert task.priority == 5
        assert task.timeout == 300.0
    
    def test_create_task_with_parameters(self):
        """Test task creation with parameters"""
        task = create_task(
            task_type="code_review",
            description="Review code",
            files=["main.py", "utils.py"],
            priority=8,
            timeout=120.0
        )
        
        assert task.task_type == "code_review"
        assert task.description == "Review code"
        assert task.files == ["main.py", "utils.py"]
        assert task.priority == 8
        assert task.timeout == 120.0
    
    def test_create_task_with_kwargs(self):
        """Test task creation with additional kwargs"""
        task = create_task(
            task_type="refactor",
            parallel=True,
            subtasks=[{"type": "analysis"}]
        )
        
        assert task.task_type == "refactor"
        assert task.parallel is True
        assert task.subtasks == [{"type": "analysis"}]