#!/usr/bin/env python3
"""
Basic usage example for Claude Conductor
"""

import time
from conductor import Orchestrator, create_task


def main():
    """Basic usage demonstration"""
    print("=== Claude Conductor Basic Usage ===\n")
    
    # Create orchestrator with 2 agents
    orchestrator = Orchestrator()
    orchestrator.config["num_agents"] = 2
    
    try:
        # Start the orchestrator
        print("Starting orchestrator with 2 agents...")
        orchestrator.start()
        time.sleep(2)  # Give agents time to start
        
        # Check agent status
        status = orchestrator.get_agent_status()
        active_agents = sum(1 for info in status.values() if info['running'])
        print(f"Active agents: {active_agents}/{len(status)}")
        
        if active_agents == 0:
            print("No agents are running. This is expected in test/demo mode.")
            print("The system will use mock agents for demonstration.\n")
        
        # Task 1: Simple code review
        print("--- Task 1: Code Review ---")
        task1 = create_task(
            task_type="code_review",
            description="Review Python file for best practices",
            files=["examples/sample_code.py"]
        )
        
        result1 = orchestrator.execute_task(task1)
        print(f"Status: {result1.status}")
        print(f"Agent: {result1.agent_id}")
        print(f"Execution time: {result1.execution_time:.2f}s")
        if result1.error:
            print(f"Error: {result1.error}")
        print()
        
        # Task 2: Refactoring
        print("--- Task 2: Code Refactoring ---")
        task2 = create_task(
            task_type="refactor",
            description="Improve code structure and readability",
            files=["examples/sample_code.py"],
            priority=7
        )
        
        result2 = orchestrator.execute_task(task2)
        print(f"Status: {result2.status}")
        print(f"Agent: {result2.agent_id}")
        print(f"Execution time: {result2.execution_time:.2f}s")
        if result2.error:
            print(f"Error: {result2.error}")
        print()
        
        # Task 3: Test generation
        print("--- Task 3: Test Generation ---")
        task3 = create_task(
            task_type="test_generation",
            description="Generate comprehensive test suite",
            files=["examples/sample_code.py"],
            timeout=60.0
        )
        
        result3 = orchestrator.execute_task(task3)
        print(f"Status: {result3.status}")
        print(f"Agent: {result3.agent_id}")
        print(f"Execution time: {result3.execution_time:.2f}s")
        if result3.error:
            print(f"Error: {result3.error}")
        print()
        
        # Show final statistics
        print("--- Final Statistics ---")
        stats = orchestrator.get_statistics()
        print(f"Tasks completed: {stats['tasks_completed']}")
        print(f"Tasks failed: {stats['tasks_failed']}")
        print(f"Average execution time: {stats['avg_execution_time']:.2f}s")
        print(f"Total runtime: {stats['runtime']:.2f}s")
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Always clean up
        print("\nShutting down orchestrator...")
        orchestrator.stop()
        print("Done!")


if __name__ == "__main__":
    main()