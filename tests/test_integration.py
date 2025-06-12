import pytest
import time
import os
from src.orchestrator import Orchestrator, Task
from src.claude_code_wrapper import AgentConfig, ClaudeCodeWrapper

def test_orchestrator_startup():
    """オーケストレーターの起動テスト"""
    orchestrator = Orchestrator()
    orchestrator.config["num_agents"] = 1
    
    orchestrator.start()
    time.sleep(2)
    
    status = orchestrator.get_agent_status()
    assert len(status) == 1
    assert list(status.values())[0]["running"] == True
    
    orchestrator.stop()

def test_simple_task_execution():
    """簡単なタスク実行テスト"""
    orchestrator = Orchestrator()
    orchestrator.config["num_agents"] = 1
    
    orchestrator.start()
    time.sleep(2)
    
    task = Task(
        task_type="generic",
        description="echo 'Hello, World!'"
    )
    
    result = orchestrator.execute_task(task)
    
    assert result.status in ["success", "failed"]
    assert result.task_id == task.task_id
    
    orchestrator.stop()

@pytest.mark.skipif(
    not os.path.exists("/usr/bin/podman"),
    reason="Podman not installed"
)
def test_container_lifecycle():
    """コンテナライフサイクルテスト"""
    config = AgentConfig(
        agent_id="test_001",
        container_name="test_container_001",
        work_dir="/tmp/test_workspace"
    )
    
    with ClaudeCodeWrapper(config) as wrapper:
        # コンテナが作成されたことを確認
        result = wrapper.exec_in_container("echo 'Container is running'")
        assert result.exit_code == 0
        assert "Container is running" in result.stdout