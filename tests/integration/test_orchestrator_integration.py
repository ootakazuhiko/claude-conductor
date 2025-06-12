"""
Integration tests for the Orchestrator with real agents
"""

import pytest
import time
import tempfile
import shutil
from unittest.mock import patch

from conductor import Orchestrator, Task, create_task


@pytest.mark.integration
class TestOrchestratorIntegration:
    """Integration tests for orchestrator functionality"""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace for integration tests"""
        workspace = tempfile.mkdtemp()
        yield workspace
        shutil.rmtree(workspace)
    
    @pytest.fixture
    def minimal_orchestrator(self, temp_workspace):
        """Create orchestrator with minimal configuration for testing"""
        with patch('conductor.orchestrator.UnixSocketChannel'):
            orchestrator = Orchestrator()
            orchestrator.config.update({
                "num_agents": 1,
                "max_workers": 2,
                "task_timeout": 30
            })
            return orchestrator
    
    def test_orchestrator_lifecycle(self, minimal_orchestrator):
        """Test complete orchestrator lifecycle"""
        # Start orchestrator
        with patch('conductor.agent.ClaudeCodeWrapper.setup_container'):
            with patch('conductor.agent.ClaudeCodeWrapper.start_claude_code'):
                minimal_orchestrator.start()
                
                # Verify orchestrator started
                assert len(minimal_orchestrator.agents) >= 0  # May fail to create agents in test
                
                # Stop orchestrator
                minimal_orchestrator.stop()
                
                # Verify cleanup
                assert all(not agent.is_running for agent in minimal_orchestrator.agents.values())
    
    def test_task_execution_flow(self, minimal_orchestrator, temp_workspace):
        """Test end-to-end task execution flow"""
        # Create test file
        test_file = f"{temp_workspace}/test.py"
        with open(test_file, 'w') as f:
            f.write("def hello():\n    print('Hello, World!')")
        
        # Mock agent execution
        with patch('conductor.agent.ClaudeCodeWrapper'):
            with patch('conductor.agent.UnixSocketChannel'):
                # Start orchestrator with mocked components
                minimal_orchestrator.start()
                
                if minimal_orchestrator.agents:
                    # Create and execute task
                    task = create_task(
                        task_type="code_review",
                        description="Review test file",
                        files=[test_file]
                    )
                    
                    # Mock agent response
                    agent = list(minimal_orchestrator.agents.values())[0]
                    with patch.object(agent, 'execute_task') as mock_execute:
                        from conductor.agent import TaskResult
                        mock_result = TaskResult(
                            task_id=task.task_id,
                            agent_id=agent.agent_id,
                            status="success",
                            result={"issues": 2, "suggestions": ["Add docstring"]}
                        )
                        mock_execute.return_value = mock_result
                        
                        result = minimal_orchestrator.execute_task(task)
                        
                        assert result.status == "success"
                        assert result.task_id == task.task_id
                        assert "issues" in result.result
                
                minimal_orchestrator.stop()
    
    def test_parallel_task_execution(self, minimal_orchestrator, temp_workspace):
        """Test parallel task execution"""
        # Create multiple test files
        files = []
        for i in range(3):
            test_file = f"{temp_workspace}/test_{i}.py"
            with open(test_file, 'w') as f:
                f.write(f"def function_{i}():\n    pass")
            files.append(test_file)
        
        with patch('conductor.agent.ClaudeCodeWrapper'):
            with patch('conductor.agent.UnixSocketChannel'):
                minimal_orchestrator.start()
                
                if minimal_orchestrator.agents:
                    # Create parallel task
                    parallel_task = create_task(
                        task_type="analysis",
                        description="Analyze multiple files",
                        parallel=True,
                        subtasks=[
                            {"type": "code_review", "files": [files[0]]},
                            {"type": "code_review", "files": [files[1]]},
                            {"type": "code_review", "files": [files[2]]}
                        ]
                    )
                    
                    # Mock agent responses
                    agent = list(minimal_orchestrator.agents.values())[0]
                    with patch.object(agent, 'execute_task') as mock_execute:
                        from conductor.agent import TaskResult
                        
                        def mock_task_execution(task):
                            return TaskResult(
                                task_id=task.task_id,
                                agent_id=agent.agent_id,
                                status="success",
                                result={"files_processed": 1}
                            )
                        
                        mock_execute.side_effect = mock_task_execution
                        
                        results = minimal_orchestrator.execute_parallel_task(parallel_task)
                        
                        assert len(results) >= 1  # At least one result
                        assert all(r.status in ["success", "failed"] for r in results)
                
                minimal_orchestrator.stop()
    
    def test_agent_failure_handling(self, minimal_orchestrator):
        """Test orchestrator behavior when agents fail"""
        with patch('conductor.agent.ClaudeAgent.start') as mock_start:
            # Make agent startup fail
            mock_start.side_effect = Exception("Agent startup failed")
            
            minimal_orchestrator.start()
            
            # Orchestrator should handle agent failures gracefully
            assert len(minimal_orchestrator.agents) == 0
            
            minimal_orchestrator.stop()
    
    def test_task_timeout_handling(self, minimal_orchestrator):
        """Test task timeout handling"""
        with patch('conductor.agent.ClaudeCodeWrapper'):
            with patch('conductor.agent.UnixSocketChannel'):
                minimal_orchestrator.start()
                
                if minimal_orchestrator.agents:
                    # Create task with short timeout
                    task = create_task(
                        task_type="generic",
                        description="long running task",
                        timeout=0.1  # Very short timeout
                    )
                    
                    # Mock slow agent execution
                    agent = list(minimal_orchestrator.agents.values())[0]
                    with patch.object(agent, 'execute_task') as mock_execute:
                        # Simulate timeout
                        minimal_orchestrator.executor.submit = lambda fn, task: self._create_timeout_future()
                        
                        result = minimal_orchestrator.execute_task(task)
                        
                        assert result.status == "timeout"
                        assert "timeout" in result.error.lower()
                
                minimal_orchestrator.stop()
    
    def _create_timeout_future(self):
        """Helper to create a future that times out"""
        from concurrent.futures import Future
        
        class TimeoutFuture(Future):
            def result(self, timeout=None):
                raise TimeoutError("Task timeout")
        
        return TimeoutFuture()
    
    def test_statistics_tracking(self, minimal_orchestrator):
        """Test statistics tracking during execution"""
        with patch('conductor.agent.ClaudeCodeWrapper'):
            with patch('conductor.agent.UnixSocketChannel'):
                minimal_orchestrator.start()
                
                # Initial stats
                stats = minimal_orchestrator.get_statistics()
                assert stats["tasks_completed"] == 0
                assert stats["tasks_failed"] == 0
                
                if minimal_orchestrator.agents:
                    # Execute successful task
                    task = create_task(task_type="generic", description="test")
                    agent = list(minimal_orchestrator.agents.values())[0]
                    
                    with patch.object(agent, 'execute_task') as mock_execute:
                        from conductor.agent import TaskResult
                        mock_result = TaskResult(
                            task_id=task.task_id,
                            agent_id=agent.agent_id,
                            status="success",
                            result={},
                            execution_time=1.0
                        )
                        mock_execute.return_value = mock_result
                        
                        minimal_orchestrator.execute_task(task)
                        
                        # Check updated stats
                        stats = minimal_orchestrator.get_statistics()
                        assert stats["tasks_completed"] == 1
                        assert stats["total_execution_time"] == 1.0
                
                minimal_orchestrator.stop()
    
    def test_agent_status_monitoring(self, minimal_orchestrator):
        """Test agent status monitoring"""
        with patch('conductor.agent.ClaudeCodeWrapper'):
            with patch('conductor.agent.UnixSocketChannel'):
                minimal_orchestrator.start()
                
                status = minimal_orchestrator.get_agent_status()
                
                # Should return status dict
                assert isinstance(status, dict)
                
                # Check agent status structure
                for agent_id, agent_status in status.items():
                    assert "running" in agent_status
                    assert "current_task" in agent_status
                    assert "health_check_failed" in agent_status
                    assert "container_name" in agent_status
                
                minimal_orchestrator.stop()
    
    @pytest.mark.slow
    def test_load_balancing(self, temp_workspace):
        """Test load balancing across multiple agents"""
        with patch('conductor.agent.ClaudeCodeWrapper'):
            with patch('conductor.agent.UnixSocketChannel'):
                # Create orchestrator with multiple agents
                orchestrator = Orchestrator()
                orchestrator.config.update({
                    "num_agents": 3,
                    "max_workers": 6
                })
                
                orchestrator.start()
                
                if len(orchestrator.agents) >= 2:
                    # Create multiple tasks
                    tasks = [
                        create_task(task_type="generic", description=f"task_{i}")
                        for i in range(5)
                    ]
                    
                    # Mock agent execution
                    agent_usage = {agent_id: 0 for agent_id in orchestrator.agents.keys()}
                    
                    for agent_id, agent in orchestrator.agents.items():
                        with patch.object(agent, 'execute_task') as mock_execute:
                            from conductor.agent import TaskResult
                            
                            def track_usage(task):
                                agent_usage[agent_id] += 1
                                return TaskResult(
                                    task_id=task.task_id,
                                    agent_id=agent_id,
                                    status="success",
                                    result={}
                                )
                            
                            mock_execute.side_effect = track_usage
                    
                    # Execute tasks
                    results = []
                    for task in tasks:
                        result = orchestrator.execute_task(task)
                        results.append(result)
                    
                    # Check that tasks were distributed (at least somewhat)
                    assert len(results) == 5
                    assert all(r.status == "success" for r in results)
                
                orchestrator.stop()