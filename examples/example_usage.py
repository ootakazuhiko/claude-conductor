#!/usr/bin/env python3
"""
Example usage of Claude Code Orchestrator
"""

import time
from conductor import Orchestrator, Task, create_task

def main():
    # オーケストレーターを作成
    orchestrator = Orchestrator()
    
    # 2つのエージェントで起動
    orchestrator.config["num_agents"] = 2
    orchestrator.start()
    
    print("Orchestrator started with 2 agents")
    time.sleep(3)
    
    # タスク1: 単一ファイルのレビュー
    print("\n--- Task 1: Single file review ---")
    task1 = create_task(
        task_type="code_review",
        description="Review Python file for style and bugs",
        files=["examples/sample_code.py"]
    )
    
    result1 = orchestrator.execute_task(task1)
    print(f"Result: {result1.status}")
    print(f"Execution time: {result1.execution_time:.2f}s")
    
    # タスク2: 並列レビュー
    print("\n--- Task 2: Parallel review ---")
    task2 = create_task(
        task_type="code_review",
        description="Review multiple files in parallel",
        parallel=True,
        subtasks=[
            {
                "type": "code_review",
                "description": "Review frontend code",
                "files": ["frontend/app.js", "frontend/utils.js"]
            },
            {
                "type": "code_review",
                "description": "Review backend code",
                "files": ["backend/server.py", "backend/database.py"]
            }
        ]
    )
    
    results2 = orchestrator.execute_parallel_task(task2)
    print(f"Completed {len(results2)} subtasks")
    for result in results2:
        print(f"  - {result.task_id}: {result.status}")
        
    # エージェントステータス確認
    print("\n--- Agent Status ---")
    status = orchestrator.get_agent_status()
    for agent_id, info in status.items():
        print(f"{agent_id}: running={info['running']}, task={info['current_task']}")
        
    # クリーンアップ
    orchestrator.stop()
    print("\nOrchestrator stopped")

if __name__ == "__main__":
    main()