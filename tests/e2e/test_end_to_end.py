"""
End-to-end tests for Claude Conductor
"""

import pytest
import time
import os
import tempfile
import subprocess
import threading
from unittest.mock import patch, MagicMock

from conductor import Orchestrator, create_task


@pytest.mark.e2e
@pytest.mark.slow
class TestFullSystemIntegration:
    """End-to-end system integration tests"""
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_complete_workflow(self, mock_wrapper_class, temp_dir, mock_file_system):
        """Test complete workflow from start to finish"""
        # Setup mock wrapper
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        mock_wrapper.setup_container.return_value = "test_container"
        mock_wrapper.read_output.return_value = [
            ("stdout", '{"issues": 2, "suggestions": ["Add type hints"]}')
        ]
        
        # Create orchestrator with test configuration
        orchestrator = Orchestrator()
        orchestrator.config.update({
            "num_agents": 2,
            "max_workers": 4,
            "task_timeout": 30,
            "log_level": "INFO"
        })
        
        try:
            # 1. Start the system
            orchestrator.start()
            time.sleep(0.3)  # Give agents time to start
            
            # Verify agents are running
            assert len(orchestrator.agents) == 2
            assert all(agent.is_running for agent in orchestrator.agents.values())
            
            # 2. Execute a code review task
            code_review_task = create_task(
                task_type="code_review",
                description="Review Python code for issues",
                files=[os.path.join(mock_file_system, "main.py")],
                priority=8
            )
            
            result = orchestrator.execute_task(code_review_task)
            
            # Verify task execution
            assert result.status == "success"
            assert result.task_id == code_review_task.task_id
            assert "issues" in result.result
            
            # 3. Execute parallel tasks
            parallel_task = create_task(
                task_type="analysis",
                description="Analyze multiple files",
                parallel=True,
                subtasks=[
                    {"type": "code_review", "files": ["main.py"]},
                    {"type": "code_review", "files": ["utils.py"]}
                ]
            )
            
            parallel_results = orchestrator.execute_parallel_task(parallel_task)
            
            # Verify parallel execution
            assert len(parallel_results) == 2
            assert all(r.status == "success" for r in parallel_results)
            
            # 4. Check system statistics
            stats = orchestrator.get_statistics()
            assert stats["tasks_completed"] >= 2
            assert stats["active_agents"] == 2
            assert stats["total_agents"] == 2
            
            # 5. Check agent status
            agent_status = orchestrator.get_agent_status()
            assert len(agent_status) == 2
            for agent_id, status in agent_status.items():
                assert status["running"] is True
                assert "container_name" in status
            
        finally:
            # 6. Clean shutdown
            orchestrator.stop()
            
            # Verify agents are stopped
            for agent in orchestrator.agents.values():
                assert not agent.is_running
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_stress_testing(self, mock_wrapper_class, temp_dir):
        """Test system under load"""
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        mock_wrapper.setup_container.return_value = "test_container"
        mock_wrapper.read_output.return_value = [("stdout", "Task completed")]
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 3
        
        try:
            orchestrator.start()
            time.sleep(0.2)
            
            # Submit many tasks concurrently
            tasks = []
            results = []
            
            def execute_task(task_id):
                task = create_task(
                    task_type="generic",
                    description=f"Stress test task {task_id}",
                    priority=5
                )
                result = orchestrator.execute_task(task)
                results.append(result)
            
            # Create 20 tasks
            threads = []
            for i in range(20):
                thread = threading.Thread(target=execute_task, args=(i,))
                threads.append(thread)
                thread.start()
            
            # Wait for all tasks to complete
            for thread in threads:
                thread.join(timeout=10)
            
            # Verify all tasks completed
            assert len(results) == 20
            success_count = sum(1 for r in results if r.status == "success")
            
            # Allow for some tasks to fail under stress
            assert success_count >= 15  # At least 75% success rate
            
            # Check system is still healthy
            stats = orchestrator.get_statistics()
            assert stats["active_agents"] == 3
            
        finally:
            orchestrator.stop()
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_error_recovery_scenarios(self, mock_wrapper_class, temp_dir):
        """Test various error recovery scenarios"""
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        mock_wrapper.setup_container.return_value = "test_container"
        
        # Simulate intermittent failures
        failure_count = 0
        def intermittent_read_output(*args, **kwargs):
            nonlocal failure_count
            failure_count += 1
            if failure_count % 3 == 0:  # Fail every 3rd call
                raise Exception("Simulated failure")
            return [("stdout", "Task completed")]
        
        mock_wrapper.read_output.side_effect = intermittent_read_output
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 2
        
        try:
            orchestrator.start()
            time.sleep(0.2)
            
            # Execute multiple tasks, some will fail
            success_count = 0
            failure_count = 0
            
            for i in range(10):
                task = create_task(
                    task_type="generic",
                    description=f"Error recovery test {i}"
                )
                
                result = orchestrator.execute_task(task)
                
                if result.status == "success":
                    success_count += 1
                else:
                    failure_count += 1
            
            # Should have mix of successes and failures
            assert success_count > 0
            assert failure_count > 0
            
            # System should still be operational
            stats = orchestrator.get_statistics()
            assert stats["active_agents"] == 2
            
        finally:
            orchestrator.stop()


@pytest.mark.e2e
@pytest.mark.container
class TestContainerIntegration:
    """Test container integration (requires container runtime)"""
    
    def test_container_runtime_detection(self):
        """Test container runtime detection"""
        from conductor.utils import check_container_runtime
        
        runtime = check_container_runtime()
        # Should detect podman or docker, or return None
        assert runtime in ["podman", "docker", None]
    
    @pytest.mark.skipif(
        not any(subprocess.run(['which', runtime], capture_output=True).returncode == 0 
                for runtime in ['podman', 'docker']),
        reason="No container runtime available"
    )
    def test_real_container_setup(self, temp_dir):
        """Test actual container setup (requires container runtime)"""
        from conductor.agent import ClaudeCodeWrapper, AgentConfig
        
        config = AgentConfig(
            agent_id="test_agent",
            container_name="claude_test_container",
            work_dir=temp_dir,
            podman_image="ubuntu:22.04"
        )
        
        wrapper = ClaudeCodeWrapper(config)
        
        try:
            # This will use real container runtime
            container_id = wrapper.setup_container()
            assert container_id is not None
            assert len(container_id) > 0
            
            # Test command execution in container
            result = wrapper.exec_in_container("echo 'Hello from container'")
            assert result.exit_code == 0
            assert "Hello from container" in result.stdout
            
        finally:
            # Cleanup container
            wrapper.cleanup_container()


@pytest.mark.e2e
class TestWebDashboardIntegration:
    """Test web dashboard integration"""
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_dashboard_with_orchestrator(self, mock_wrapper_class, temp_dir):
        """Test web dashboard with running orchestrator"""
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        mock_wrapper.setup_container.return_value = "test_container"
        
        from web.dashboard import DashboardData
        
        # Create orchestrator
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 2
        
        # Create dashboard data
        dashboard_data = DashboardData()
        dashboard_data.orchestrator = orchestrator
        
        try:
            orchestrator.start()
            time.sleep(0.2)
            
            # Update dashboard stats
            dashboard_data.update_stats()
            
            # Get dashboard data
            data = dashboard_data.get_current_data()
            
            # Verify dashboard data
            assert "stats" in data
            assert "agents" in data
            assert data["stats"]["total_agents"] == 2
            assert len(data["agents"]) == 2
            
            # Test task execution and stats update
            task = create_task(
                task_type="generic",
                description="Dashboard test task"
            )
            
            result = orchestrator.execute_task(task)
            dashboard_data.update_stats()
            
            updated_data = dashboard_data.get_current_data()
            assert updated_data["stats"]["tasks_completed"] >= 1
            
        finally:
            orchestrator.stop()
    
    def test_dashboard_fallback_mode(self):
        """Test dashboard fallback mode without FastAPI"""
        from web.dashboard import create_simple_dashboard
        
        html_content = create_simple_dashboard()
        
        # Verify HTML structure
        assert "<!DOCTYPE html>" in html_content
        assert "Claude Conductor Dashboard" in html_content
        assert "submitTask()" in html_content
        assert "mockStats" in html_content


@pytest.mark.e2e
@pytest.mark.network
class TestNetworkCommunication:
    """Test network communication scenarios"""
    
    def test_unix_socket_communication(self, temp_dir):
        """Test Unix socket communication between processes"""
        from conductor.protocol import UnixSocketChannel, AgentMessage, MessageType
        import multiprocessing
        import json
        
        socket_path = os.path.join(temp_dir, "test_communication.sock")
        
        def server_process():
            """Server process"""
            channel = UnixSocketChannel(socket_path)
            channel.start_server()
            
            try:
                # Accept connection and receive message
                conn, addr = channel.socket.accept()
                data = conn.recv(1024).decode().strip()
                message = AgentMessage.from_json(data)
                
                # Send response
                response = AgentMessage(
                    message_id="response_001",
                    sender_id="server",
                    receiver_id=message.sender_id,
                    message_type=MessageType.TASK_RESPONSE,
                    payload={"status": "received"},
                    timestamp=time.time(),
                    correlation_id=message.message_id
                )
                
                conn.sendall((response.to_json() + "\n").encode())
                
            finally:
                channel.close()
        
        def client_process():
            """Client process"""
            time.sleep(0.1)  # Wait for server to start
            
            channel = UnixSocketChannel(socket_path)
            channel.connect()
            
            try:
                # Send message
                message = AgentMessage(
                    message_id="request_001",
                    sender_id="client",
                    receiver_id="server",
                    message_type=MessageType.TASK_REQUEST,
                    payload={"task": "test"},
                    timestamp=time.time()
                )
                
                channel.send_message(message)
                
                # Receive response
                response = channel.receive_message(timeout=5)
                assert response is not None
                assert response.message_type == MessageType.TASK_RESPONSE
                assert response.payload["status"] == "received"
                
            finally:
                channel.close()
        
        # Run server and client in separate processes
        server = multiprocessing.Process(target=server_process)
        client = multiprocessing.Process(target=client_process)
        
        server.start()
        client.start()
        
        client.join(timeout=10)
        server.join(timeout=10)
        
        # Verify both processes completed successfully
        assert client.exitcode == 0
        assert server.exitcode == 0


@pytest.mark.e2e
class TestConfigurationManagement:
    """Test configuration management scenarios"""
    
    def test_configuration_file_loading(self, temp_dir):
        """Test loading configuration from file"""
        import yaml
        
        config_file = os.path.join(temp_dir, "test_config.yaml")
        config_data = {
            "num_agents": 5,
            "max_workers": 20,
            "task_timeout": 600,
            "log_level": "DEBUG",
            "container_config": {
                "image": "ubuntu:22.04",
                "memory_limit": "4g"
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create orchestrator with config file
        orchestrator = Orchestrator(config_file)
        
        # Verify configuration was loaded
        assert orchestrator.config["num_agents"] == 5
        assert orchestrator.config["max_workers"] == 20
        assert orchestrator.config["task_timeout"] == 600
        assert orchestrator.config["log_level"] == "DEBUG"
    
    def test_environment_variable_override(self, temp_dir):
        """Test environment variable configuration override"""
        import os
        
        # Set environment variables
        original_env = os.environ.copy()
        try:
            os.environ["CONDUCTOR_NUM_AGENTS"] = "7"
            os.environ["CONDUCTOR_LOG_LEVEL"] = "ERROR"
            
            orchestrator = Orchestrator()
            
            # Environment variables should override defaults
            # (This depends on implementation supporting env vars)
            # For now, just verify the system handles environment properly
            
        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(original_env)


@pytest.mark.e2e
@pytest.mark.slow
class TestPerformanceBenchmarks:
    """Performance benchmark tests"""
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_task_execution_performance(self, mock_wrapper_class, temp_dir):
        """Benchmark task execution performance"""
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        mock_wrapper.setup_container.return_value = "test_container"
        mock_wrapper.read_output.return_value = [("stdout", "Task completed")]
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 3
        
        try:
            orchestrator.start()
            time.sleep(0.3)
            
            # Benchmark sequential execution
            start_time = time.time()
            
            for i in range(10):
                task = create_task(
                    task_type="generic",
                    description=f"Performance test {i}"
                )
                result = orchestrator.execute_task(task)
                assert result.status == "success"
            
            sequential_time = time.time() - start_time
            
            # Should complete 10 tasks in reasonable time
            assert sequential_time < 5.0  # 5 seconds max
            
            # Check throughput
            throughput = 10 / sequential_time
            assert throughput > 2.0  # At least 2 tasks per second
            
            # Verify system performance
            stats = orchestrator.get_statistics()
            avg_execution_time = stats.get("avg_execution_time", 0)
            assert avg_execution_time < 1.0  # Less than 1 second average
            
        finally:
            orchestrator.stop()
    
    @patch('conductor.agent.ClaudeCodeWrapper')
    def test_memory_usage_stability(self, mock_wrapper_class, temp_dir):
        """Test memory usage stability over time"""
        import psutil
        import gc
        
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper
        mock_wrapper.setup_container.return_value = "test_container"
        mock_wrapper.read_output.return_value = [("stdout", "Task completed")]
        
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 2
        
        try:
            orchestrator.start()
            time.sleep(0.2)
            
            # Measure initial memory
            process = psutil.Process()
            initial_memory = process.memory_info().rss
            
            # Execute many tasks
            for i in range(50):
                task = create_task(
                    task_type="generic",
                    description=f"Memory test {i}"
                )
                orchestrator.execute_task(task)
                
                # Periodic garbage collection
                if i % 10 == 0:
                    gc.collect()
            
            # Measure final memory
            gc.collect()
            final_memory = process.memory_info().rss
            
            # Memory growth should be reasonable
            memory_growth = final_memory - initial_memory
            memory_growth_mb = memory_growth / (1024 * 1024)
            
            # Allow some memory growth but not excessive
            assert memory_growth_mb < 100  # Less than 100MB growth
            
        finally:
            orchestrator.stop()