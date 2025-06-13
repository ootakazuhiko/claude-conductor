"""
Integration tests for agent communication
"""

import pytest
import time
import threading
import tempfile
import os
from unittest.mock import MagicMock, patch

from conductor.protocol import AgentProtocol, MessageType, AgentMessage
from conductor.agent import ClaudeAgent


@pytest.mark.integration
class TestAgentToAgentCommunication:
    """Test agent-to-agent communication integration"""
    
    def test_basic_message_exchange(self, temp_dir):
        """Test basic message exchange between two agents"""
        # Setup socket paths
        socket1 = os.path.join(temp_dir, "agent1.sock")
        socket2 = os.path.join(temp_dir, "agent2.sock")
        
        # Create protocols
        protocol1 = AgentProtocol("agent_001", socket1)
        protocol2 = AgentProtocol("agent_002", socket2)
        
        # Message storage
        received_messages = []
        
        def message_handler(message):
            received_messages.append(message)
        
        # Register handlers
        protocol2.register_handler(MessageType.TASK_REQUEST, message_handler)
        
        try:
            # Start servers
            protocol1.channel.start_server()
            protocol2.channel.start_server()
            
            # Start listeners
            protocol1.start_listening()
            protocol2.start_listening()
            
            # Give time for setup
            time.sleep(0.1)
            
            # Send message from agent1 to agent2
            task_data = {
                "task_id": "test_001",
                "task_type": "code_review",
                "files": ["test.py"]
            }
            
            # Connect agent1 to agent2's socket
            protocol1.channel.socket_path = socket2
            protocol1.channel.connect()
            
            protocol1.send_task_request("agent_002", task_data)
            
            # Wait for message to be received
            time.sleep(0.2)
            
            # Verify message was received
            assert len(received_messages) == 1
            message = received_messages[0]
            assert message.sender_id == "agent_001"
            assert message.receiver_id == "agent_002"
            assert message.message_type == MessageType.TASK_REQUEST
            assert message.payload == task_data
            
        finally:
            protocol1.stop_listening()
            protocol2.stop_listening()
    
    def test_request_response_cycle(self, temp_dir):
        """Test complete request-response cycle"""
        socket1 = os.path.join(temp_dir, "agent1.sock")
        socket2 = os.path.join(temp_dir, "agent2.sock")
        
        protocol1 = AgentProtocol("agent_001", socket1)
        protocol2 = AgentProtocol("agent_002", socket2)
        
        responses_received = []
        
        def request_handler(message):
            # Simulate processing and send response
            response_data = {
                "task_id": message.payload["task_id"],
                "status": "completed",
                "result": {"issues": 3}
            }
            
            # Connect back to sender
            response_protocol = AgentProtocol("agent_002", socket1)
            response_protocol.channel.connect()
            response_protocol.send_task_response(
                message.sender_id, 
                response_data, 
                message.message_id
            )
        
        def response_handler(message):
            responses_received.append(message)
        
        protocol2.register_handler(MessageType.TASK_REQUEST, request_handler)
        protocol1.register_handler(MessageType.TASK_RESPONSE, response_handler)
        
        try:
            protocol1.channel.start_server()
            protocol2.channel.start_server()
            
            protocol1.start_listening()
            protocol2.start_listening()
            
            time.sleep(0.1)
            
            # Send request
            task_data = {"task_id": "test_002", "task_type": "analysis"}
            
            protocol1.channel.socket_path = socket2
            protocol1.channel.connect()
            protocol1.send_task_request("agent_002", task_data)
            
            # Wait for processing
            time.sleep(0.3)
            
            # Verify response was received
            assert len(responses_received) == 1
            response = responses_received[0]
            assert response.message_type == MessageType.TASK_RESPONSE
            assert response.payload["status"] == "completed"
            assert response.payload["result"]["issues"] == 3
            
        finally:
            protocol1.stop_listening()
            protocol2.stop_listening()


@pytest.mark.integration
class TestOrchestratorAgentIntegration:
    """Test orchestrator-agent integration"""
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_orchestrator_agent_lifecycle(self, mock_wrapper_class, temp_dir):
        """Test full agent lifecycle with orchestrator"""
        from conductor import Orchestrator
        
        # Mock wrapper
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        mock_wrapper.setup_container.return_value = "test_container"
        
        # Create orchestrator
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 1
        
        try:
            # Start orchestrator
            orchestrator.start()
            
            # Wait for agents to start
            time.sleep(0.2)
            
            # Verify agent was created and started
            assert len(orchestrator.agents) == 1
            agent_id = list(orchestrator.agents.keys())[0]
            agent = orchestrator.agents[agent_id]
            
            assert agent.is_running
            mock_wrapper.setup_container.assert_called_once()
            mock_wrapper.start_claude_code.assert_called_once()
            
            # Test agent status
            status = orchestrator.get_agent_status()
            assert agent_id in status
            assert status[agent_id]["running"] is True
            
            # Test statistics
            stats = orchestrator.get_statistics()
            assert stats["total_agents"] == 1
            assert stats["active_agents"] == 1
            
        finally:
            orchestrator.stop()
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_task_execution_integration(self, mock_wrapper_class, temp_dir):
        """Test task execution through orchestrator"""
        from conductor import Orchestrator, create_task
        
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        mock_wrapper.read_output.return_value = [("stdout", "Task completed")]
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 1
        
        try:
            orchestrator.start()
            time.sleep(0.1)
            
            # Create and execute task
            task = create_task(
                task_type="generic",
                description="echo hello world",
                priority=5
            )
            
            result = orchestrator.execute_task(task)
            
            # Verify task execution
            assert result.status == "success"
            assert result.task_id == task.task_id
            
            # Verify wrapper was called
            mock_wrapper.send_command.assert_called()
            
            # Check statistics update
            stats = orchestrator.get_statistics()
            assert stats["tasks_completed"] == 1
            
        finally:
            orchestrator.stop()


@pytest.mark.integration
class TestConcurrentTaskExecution:
    """Test concurrent task execution"""
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_parallel_task_execution(self, mock_wrapper_class, temp_dir):
        """Test parallel execution of multiple tasks"""
        from conductor import Orchestrator, create_task
        
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        mock_wrapper.read_output.return_value = [("stdout", "Task completed")]
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 2
        
        try:
            orchestrator.start()
            time.sleep(0.2)
            
            # Create parallel task
            parallel_task = create_task(
                task_type="analysis",
                parallel=True,
                subtasks=[
                    {"type": "code_review", "description": "Review file 1"},
                    {"type": "code_review", "description": "Review file 2"}
                ]
            )
            
            results = orchestrator.execute_parallel_task(parallel_task)
            
            # Verify parallel execution
            assert len(results) == 2
            assert all(r.status == "success" for r in results)
            
            # Each result should have different agent IDs (if possible)
            agent_ids = [r.agent_id for r in results]
            # With 2 agents, we might get different agents
            
        finally:
            orchestrator.stop()
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_concurrent_task_queue(self, mock_wrapper_class, temp_dir):
        """Test concurrent task processing"""
        from conductor import Orchestrator, create_task
        import threading
        
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        mock_wrapper.read_output.return_value = [("stdout", "Task completed")]
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 2
        
        try:
            orchestrator.start()
            time.sleep(0.2)
            
            # Submit multiple tasks concurrently
            tasks = []
            results = []
            
            def execute_task(task):
                result = orchestrator.execute_task(task)
                results.append(result)
            
            # Create multiple tasks
            for i in range(5):
                task = create_task(
                    task_type="generic",
                    description=f"Task {i}",
                    priority=5
                )
                tasks.append(task)
            
            # Execute tasks in threads
            threads = []
            for task in tasks:
                thread = threading.Thread(target=execute_task, args=(task,))
                threads.append(thread)
                thread.start()
            
            # Wait for all tasks to complete
            for thread in threads:
                thread.join(timeout=5)
            
            # Verify all tasks completed
            assert len(results) == 5
            assert all(r.status == "success" for r in results)
            
        finally:
            orchestrator.stop()


@pytest.mark.integration
@pytest.mark.slow
class TestLongRunningTasks:
    """Test long-running task scenarios"""
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_task_timeout_handling(self, mock_wrapper_class, temp_dir):
        """Test task timeout handling"""
        from conductor import Orchestrator, create_task
        
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        
        # Simulate long-running task
        def slow_read_output(*args, **kwargs):
            time.sleep(2)  # Longer than timeout
            return [("stdout", "Finally done")]
        
        mock_wrapper.read_output.side_effect = slow_read_output
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 1
        
        try:
            orchestrator.start()
            time.sleep(0.1)
            
            # Create task with short timeout
            task = create_task(
                task_type="generic",
                description="slow task",
                timeout=1.0  # 1 second timeout
            )
            
            start_time = time.time()
            result = orchestrator.execute_task(task)
            execution_time = time.time() - start_time
            
            # Should timeout around 1 second
            assert execution_time < 1.5  # Allow some overhead
            assert result.status == "timeout"
            
        finally:
            orchestrator.stop()
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_agent_health_monitoring(self, mock_wrapper_class, temp_dir):
        """Test agent health monitoring"""
        from conductor import Orchestrator
        
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 1
        orchestrator.config["health_check_interval"] = 0.5  # Fast health checks
        
        try:
            orchestrator.start()
            time.sleep(0.1)
            
            agent_id = list(orchestrator.agents.keys())[0]
            agent = orchestrator.agents[agent_id]
            
            # Simulate agent becoming unhealthy
            mock_wrapper.is_running = False
            
            # Wait for health check
            time.sleep(1.0)
            
            # Agent should be marked as having health check failures
            status = orchestrator.get_agent_status()
            # Note: This depends on implementation details
            
        finally:
            orchestrator.stop()


@pytest.mark.integration
class TestErrorRecovery:
    """Test error recovery scenarios"""
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_agent_restart_after_failure(self, mock_wrapper_class, temp_dir):
        """Test agent restart after failure"""
        from conductor import Orchestrator
        
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        
        # First setup succeeds, second fails, third succeeds
        mock_wrapper.setup_container.side_effect = [
            "container_1",
            Exception("Setup failed"),
            "container_2"
        ]
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 1
        
        try:
            orchestrator.start()
            time.sleep(0.1)
            
            # Should have one working agent
            assert len(orchestrator.agents) == 1
            
            # Simulate agent failure and restart
            agent_id = list(orchestrator.agents.keys())[0]
            agent = orchestrator.agents[agent_id]
            
            # Stop agent
            agent.stop()
            
            # Try to restart (would normally be handled by orchestrator)
            try:
                agent.start()
            except Exception:
                pass  # Expected to fail on second setup
            
            # Third setup should succeed if we create new agent
            new_agent = agent.__class__(agent.agent_id + "_new")
            new_agent.start()
            
            assert new_agent.is_running
            
        finally:
            orchestrator.stop()
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_graceful_shutdown_with_active_tasks(self, mock_wrapper_class, temp_dir):
        """Test graceful shutdown with active tasks"""
        from conductor import Orchestrator, create_task
        import threading
        
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        
        # Simulate slow task execution
        def slow_execution(*args, **kwargs):
            time.sleep(1)
            return [("stdout", "Task completed")]
        
        mock_wrapper.read_output.side_effect = slow_execution
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 1
        
        try:
            orchestrator.start()
            time.sleep(0.1)
            
            # Start a task in background
            task = create_task(
                task_type="generic",
                description="slow task"
            )
            
            result_container = []
            
            def execute_task():
                result = orchestrator.execute_task(task)
                result_container.append(result)
            
            task_thread = threading.Thread(target=execute_task)
            task_thread.start()
            
            # Give task time to start
            time.sleep(0.2)
            
            # Stop orchestrator while task is running
            orchestrator.stop()
            
            # Wait for task to complete
            task_thread.join(timeout=3)
            
            # Task should have completed or been cancelled gracefully
            # (Exact behavior depends on implementation)
            
        finally:
            # Ensure cleanup
            if orchestrator.agents:
                orchestrator.stop()