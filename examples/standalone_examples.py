#!/usr/bin/env python3
"""
Claude Conductor - Standalone Examples
シンプルな使用例とサンプルタスク
"""

import time
import os
from conductor import create_task, Orchestrator
from conductor.utils import setup_logger

# ログ設定
logger = setup_logger("standalone_examples", level="INFO")

def example_basic_tasks():
    """基本的なタスクの例"""
    print("🚀 基本的なタスクの例")
    print("=" * 50)
    
    # 1. シンプルなコマンド実行
    task1 = create_task(
        task_type="generic",
        description="echo 'Hello from Claude Conductor!'",
        priority=5
    )
    print(f"✅ Task 1 created: {task1.task_id}")
    print(f"   Type: {task1.task_type}")
    print(f"   Description: {task1.description}")
    
    # 2. ファイル操作
    task2 = create_task(
        task_type="generic", 
        description="ls -la && pwd",
        priority=4
    )
    print(f"✅ Task 2 created: {task2.task_id}")
    
    # 3. Python コード実行
    task3 = create_task(
        task_type="generic",
        description="python3 -c \"import sys; print(f'Python version: {sys.version}')\"",
        priority=6
    )
    print(f"✅ Task 3 created: {task3.task_id}")
    
    return [task1, task2, task3]

def example_code_review():
    """コードレビュータスクの例"""
    print("\n📝 コードレビュータスクの例")
    print("=" * 50)
    
    # サンプルPythonファイルを作成
    sample_code = '''
def calculate_fibonacci(n):
    """フィボナッチ数列の計算"""
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

def main():
    print("フィボナッチ数列:")
    for i in range(10):
        print(f"F({i}) = {calculate_fibonacci(i)}")

if __name__ == "__main__":
    main()
'''
    
    # ワークスペースディレクトリを作成
    workspace_dir = os.path.expanduser("~/.claude-conductor/workspace")
    os.makedirs(workspace_dir, exist_ok=True)
    
    # サンプルファイルを保存
    sample_file = os.path.join(workspace_dir, "fibonacci.py")
    with open(sample_file, 'w') as f:
        f.write(sample_code)
    
    print(f"📄 Sample file created: {sample_file}")
    
    # コードレビュータスクを作成
    review_task = create_task(
        task_type="code_review",
        description="Review Python code for optimization and best practices",
        files=["fibonacci.py"],
        priority=8
    )
    
    print(f"✅ Code review task created: {review_task.task_id}")
    print(f"   Files to review: {review_task.files}")
    
    return review_task

def example_parallel_tasks():
    """並列タスクの例"""
    print("\n⚡ 並列タスクの例")
    print("=" * 50)
    
    # 複数のサブタスクを含む並列タスク
    parallel_task = create_task(
        task_type="analysis",
        description="Parallel analysis of multiple components",
        parallel=True,
        subtasks=[
            {
                "type": "generic",
                "description": "echo 'Analyzing component 1...' && sleep 2"
            },
            {
                "type": "generic", 
                "description": "echo 'Analyzing component 2...' && sleep 2"
            },
            {
                "type": "generic",
                "description": "echo 'Analyzing component 3...' && sleep 2"
            }
        ],
        priority=7
    )
    
    print(f"✅ Parallel task created: {parallel_task.task_id}")
    print(f"   Subtasks count: {len(parallel_task.subtasks)}")
    print(f"   Parallel execution: {parallel_task.parallel}")
    
    return parallel_task

def example_priority_tasks():
    """優先度付きタスクの例"""
    print("\n🎯 優先度付きタスクの例")
    print("=" * 50)
    
    tasks = []
    priorities = [1, 5, 10]  # 低、中、高
    priority_names = ["Low", "Medium", "High"]
    
    for priority, name in zip(priorities, priority_names):
        task = create_task(
            task_type="generic",
            description=f"echo 'This is a {name.lower()} priority task'",
            priority=priority
        )
        tasks.append(task)
        print(f"✅ {name} priority task created: {task.task_id} (Priority: {priority})")
    
    return tasks

def example_configuration_test():
    """設定テストの例"""
    print("\n⚙️ 設定テストの例")
    print("=" * 50)
    
    # 設定ファイルの場所を確認
    config_dir = os.path.expanduser("~/.claude-conductor/config")
    config_file = os.path.join(config_dir, "config.yaml")
    
    if os.path.exists(config_file):
        print(f"✅ Configuration file found: {config_file}")
        
        # 設定内容を表示するタスク
        config_task = create_task(
            task_type="generic",
            description=f"cat {config_file}",
            priority=3
        )
        print(f"✅ Config display task created: {config_task.task_id}")
        return config_task
    else:
        print(f"❌ Configuration file not found: {config_file}")
        print("   Run './quick-start.sh' first to set up the environment")
        return None

def example_workspace_setup():
    """ワークスペースセットアップの例"""
    print("\n📁 ワークスペースセットアップの例")
    print("=" * 50)
    
    workspace_dir = os.path.expanduser("~/.claude-conductor/workspace")
    
    # ディレクトリ構造を作成
    directories = [
        "projects/sample-project",
        "scripts",
        "data",
        "outputs"
    ]
    
    for directory in directories:
        full_path = os.path.join(workspace_dir, directory)
        os.makedirs(full_path, exist_ok=True)
        print(f"📁 Created directory: {directory}")
    
    # サンプルファイルを作成
    files = {
        "scripts/hello.py": "print('Hello from Claude Conductor!')",
        "scripts/system_info.py": """
import platform
import sys

print(f"OS: {platform.system()} {platform.release()}")
print(f"Python: {sys.version}")
print(f"Platform: {platform.platform()}")
""",
        "projects/sample-project/README.md": """
# Sample Project

This is a sample project for Claude Conductor demonstration.

## Features
- Task execution
- File processing
- Code analysis
""",
        "data/sample.txt": "This is sample data for processing."
    }
    
    for file_path, content in files.items():
        full_path = os.path.join(workspace_dir, file_path)
        with open(full_path, 'w') as f:
            f.write(content.strip())
        print(f"📄 Created file: {file_path}")
    
    # ワークスペース確認タスク
    workspace_task = create_task(
        task_type="generic",
        description=f"find {workspace_dir} -type f -name '*.py' -o -name '*.md' -o -name '*.txt' | head -20",
        priority=4
    )
    
    print(f"✅ Workspace exploration task created: {workspace_task.task_id}")
    return workspace_task

def run_orchestrator_example():
    """オーケストレーター実行例（デモ用）"""
    print("\n🎭 オーケストレーター実行例（デモ）")
    print("=" * 50)
    print("注意: この例は実際にオーケストレーターを起動しません")
    print("実際の実行には 'conductor start' を使用してください")
    
    # デモ用のオーケストレーター設定
    print("\n設定例:")
    demo_config = {
        "num_agents": 2,
        "max_workers": 4,
        "task_timeout": 120,
        "log_level": "INFO"
    }
    
    for key, value in demo_config.items():
        print(f"  {key}: {value}")
    
    # サンプルタスクの実行シミュレーション
    print("\nタスク実行シミュレーション:")
    sample_task = create_task(
        task_type="generic",
        description="echo 'Simulated task execution'",
        priority=5
    )
    
    print(f"1. Task created: {sample_task.task_id}")
    print("2. Task queued for execution")
    print("3. Agent assignment: agent_001")
    print("4. Task execution started")
    print("5. Task execution completed")
    print("6. Results stored")
    
    return sample_task

def main():
    """メイン実行関数"""
    print("🎭 Claude Conductor - Standalone Examples")
    print("=" * 60)
    print("これらの例は、Claude Conductorの基本的な使用方法を示しています")
    print("実際の実行には、先に 'conductor start' でシステムを起動してください")
    print("=" * 60)
    
    try:
        # 各例を実行
        basic_tasks = example_basic_tasks()
        review_task = example_code_review()
        parallel_task = example_parallel_tasks()
        priority_tasks = example_priority_tasks()
        config_task = example_configuration_test()
        workspace_task = example_workspace_setup()
        orchestrator_demo = run_orchestrator_example()
        
        # 実行サマリー
        print("\n📊 実行サマリー")
        print("=" * 50)
        
        all_tasks = []
        if basic_tasks:
            all_tasks.extend(basic_tasks)
        if review_task:
            all_tasks.append(review_task)
        if parallel_task:
            all_tasks.append(parallel_task)
        if priority_tasks:
            all_tasks.extend(priority_tasks)
        if config_task:
            all_tasks.append(config_task)
        if workspace_task:
            all_tasks.append(workspace_task)
        if orchestrator_demo:
            all_tasks.append(orchestrator_demo)
        
        print(f"✅ Total tasks created: {len(all_tasks)}")
        
        # タスクタイプ別集計
        task_types = {}
        for task in all_tasks:
            task_type = task.task_type
            task_types[task_type] = task_types.get(task_type, 0) + 1
        
        print("\nタスクタイプ別:")
        for task_type, count in task_types.items():
            print(f"  {task_type}: {count}")
        
        print("\n🚀 次のステップ:")
        print("1. 'conductor start' でシステムを起動")
        print("2. http://localhost:8080 でダッシュボードにアクセス")
        print("3. 上記で作成されたファイルを使ってタスクを実行")
        print("4. 'conductor test' で基本動作を確認")
        
    except Exception as e:
        logger.error(f"Example execution failed: {e}")
        print(f"❌ エラーが発生しました: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())