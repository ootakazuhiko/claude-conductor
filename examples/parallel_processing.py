#!/usr/bin/env python3
"""
Parallel processing example for Claude Conductor
"""

import time
import os
from conductor import Orchestrator, create_task


def main():
    """Demonstrate parallel task processing"""
    print("=== Claude Conductor Parallel Processing ===\n")
    
    # Create orchestrator with multiple agents for parallel processing
    orchestrator = Orchestrator()
    orchestrator.config["num_agents"] = 4
    orchestrator.config["max_workers"] = 8
    
    try:
        print("Starting orchestrator with 4 agents for parallel processing...")
        orchestrator.start()
        time.sleep(3)
        
        # Create sample files for processing
        sample_files = create_sample_files()
        print(f"Created {len(sample_files)} sample files for processing\n")
        
        # Example 1: Parallel code review
        print("--- Example 1: Parallel Code Review ---")
        parallel_review_task = create_task(
            task_type="code_review",
            description="Review multiple files in parallel",
            parallel=True,
            subtasks=[
                {
                    "type": "code_review",
                    "description": f"Review {os.path.basename(file)}",
                    "files": [file]
                }
                for file in sample_files
            ]
        )
        
        start_time = time.time()
        review_results = orchestrator.execute_parallel_task(parallel_review_task)
        parallel_time = time.time() - start_time
        
        print(f"Parallel review completed in {parallel_time:.2f}s")
        print(f"Processed {len(review_results)} files")
        for result in review_results:
            print(f"  - {result.task_id}: {result.status} ({result.execution_time:.2f}s)")
        print()
        
        # Example 2: Mixed task types in parallel
        print("--- Example 2: Mixed Parallel Tasks ---")
        mixed_task = create_task(
            task_type="analysis",
            description="Perform different analyses in parallel",
            parallel=True,
            subtasks=[
                {
                    "type": "code_review",
                    "description": "Security review",
                    "files": sample_files[:2]
                },
                {
                    "type": "test_generation",
                    "description": "Generate unit tests",
                    "files": sample_files[2:4]
                },
                {
                    "type": "refactor",
                    "description": "Refactor for performance",
                    "files": sample_files[4:6]
                },
                {
                    "type": "analysis",
                    "description": "Code complexity analysis"
                }
            ]
        )
        
        start_time = time.time()
        mixed_results = orchestrator.execute_parallel_task(mixed_task)
        mixed_time = time.time() - start_time
        
        print(f"Mixed parallel tasks completed in {mixed_time:.2f}s")
        for result in mixed_results:
            print(f"  - {result.task_id}: {result.status} (Agent: {result.agent_id})")
        print()
        
        # Example 3: Compare sequential vs parallel execution
        print("--- Example 3: Sequential vs Parallel Comparison ---")
        
        # Sequential execution
        print("Running tasks sequentially...")
        sequential_tasks = [
            create_task(task_type="analysis", description=f"Analyze file {i}")
            for i in range(4)
        ]
        
        start_time = time.time()
        sequential_results = []
        for task in sequential_tasks:
            result = orchestrator.execute_task(task)
            sequential_results.append(result)
        sequential_time = time.time() - start_time
        
        print(f"Sequential execution: {sequential_time:.2f}s")
        print(f"Completed {len(sequential_results)} tasks")
        
        # Parallel execution of similar tasks
        print("Running similar tasks in parallel...")
        parallel_comparison_task = create_task(
            task_type="analysis",
            description="Parallel analysis comparison",
            parallel=True,
            subtasks=[
                {"type": "analysis", "description": f"Analyze file {i}"}
                for i in range(4)
            ]
        )
        
        start_time = time.time()
        parallel_comparison_results = orchestrator.execute_parallel_task(parallel_comparison_task)
        parallel_comparison_time = time.time() - start_time
        
        print(f"Parallel execution: {parallel_comparison_time:.2f}s")
        print(f"Completed {len(parallel_comparison_results)} tasks")
        
        # Calculate speedup
        if parallel_comparison_time > 0:
            speedup = sequential_time / parallel_comparison_time
            print(f"Speedup: {speedup:.2f}x")
        print()
        
        # Show agent utilization
        print("--- Agent Utilization ---")
        status = orchestrator.get_agent_status()
        for agent_id, info in status.items():
            print(f"{agent_id}:")
            print(f"  Running: {info['running']}")
            print(f"  Current task: {info['current_task']}")
            print(f"  Health check failures: {info['health_check_failed']}")
        
        # Final statistics
        print("\n--- Final Statistics ---")
        stats = orchestrator.get_statistics()
        print(f"Total tasks completed: {stats['tasks_completed']}")
        print(f"Total tasks failed: {stats['tasks_failed']}")
        print(f"Average execution time: {stats['avg_execution_time']:.2f}s")
        print(f"Total execution time: {stats['total_execution_time']:.2f}s")
        print(f"Runtime efficiency: {(stats['total_execution_time']/stats['runtime'])*100:.1f}%")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        cleanup_sample_files()
        orchestrator.stop()
        print("\nOrchestrator stopped and cleanup completed.")


def create_sample_files():
    """Create sample Python files for processing"""
    sample_codes = [
        # File 1: Simple function
        '''def calculate_area(radius):
    """Calculate the area of a circle."""
    return 3.14159 * radius * radius

def main():
    r = 5
    area = calculate_area(r)
    print(f"Area: {area}")

if __name__ == "__main__":
    main()
''',
        # File 2: Class example
        '''class Rectangle:
    def __init__(self, width, height):
        self.width = width
        self.height = height
    
    def area(self):
        return self.width * self.height
    
    def perimeter(self):
        return 2 * (self.width + self.height)

rect = Rectangle(10, 5)
print(f"Area: {rect.area()}")
''',
        # File 3: Data processing
        '''import json

def process_data(data):
    results = []
    for item in data:
        if item.get('active', False):
            results.append({
                'id': item['id'],
                'name': item['name'],
                'score': item.get('score', 0) * 2
            })
    return results

sample_data = [
    {'id': 1, 'name': 'Alice', 'score': 85, 'active': True},
    {'id': 2, 'name': 'Bob', 'score': 92, 'active': False},
    {'id': 3, 'name': 'Charlie', 'score': 78, 'active': True}
]

result = process_data(sample_data)
print(json.dumps(result, indent=2))
''',
        # File 4: Algorithm example
        '''def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def fibonacci_iterative(n):
    if n <= 1:
        return n
    
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b

for i in range(10):
    print(f"fib({i}) = {fibonacci_iterative(i)}")
''',
        # File 5: File I/O example
        '''import os
import csv

def read_csv_file(filename):
    data = []
    try:
        with open(filename, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                data.append(row)
    except FileNotFoundError:
        print(f"File {filename} not found")
    return data

def write_summary(data, output_file):
    with open(output_file, 'w') as file:
        file.write(f"Total records: {len(data)}\\n")
        for record in data[:5]:  # First 5 records
            file.write(f"{record}\\n")

# Example usage
# data = read_csv_file("input.csv")
# write_summary(data, "summary.txt")
''',
        # File 6: Error handling
        '''def divide_numbers(a, b):
    try:
        result = a / b
        return result
    except ZeroDivisionError:
        print("Error: Division by zero")
        return None
    except TypeError:
        print("Error: Invalid input types")
        return None

def validate_input(value):
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"Invalid number: {value}")

numbers = [(10, 2), (15, 3), (8, 0), (12, 4)]
for a, b in numbers:
    result = divide_numbers(a, b)
    if result is not None:
        print(f"{a} / {b} = {result}")
'''
    ]
    
    files = []
    for i, code in enumerate(sample_codes):
        filename = f"/tmp/sample_{i+1}.py"
        with open(filename, 'w') as f:
            f.write(code)
        files.append(filename)
    
    return files


def cleanup_sample_files():
    """Clean up created sample files"""
    for i in range(1, 7):
        filename = f"/tmp/sample_{i}.py"
        try:
            os.remove(filename)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()