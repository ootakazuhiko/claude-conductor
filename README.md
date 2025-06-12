# Claude Conductor

A multi-agent orchestration system for Claude Code instances, enabling parallel execution and coordinated task distribution across multiple containerized agents.

## Overview

Claude Conductor allows you to run multiple Claude Code instances in headless mode within isolated containers (Podman/Docker), coordinate their work through an Agent2Agent protocol, and distribute complex tasks efficiently across the fleet.

## Features

- **Multi-Agent Orchestration**: Manage multiple Claude Code agents simultaneously
- **Containerized Isolation**: Each agent runs in its own Podman/Docker container
- **Agent2Agent Protocol**: Inter-agent communication for task coordination
- **Task Distribution**: Intelligent task scheduling and load balancing
- **Parallel Execution**: Execute multiple tasks concurrently
- **Health Monitoring**: Automatic health checks and recovery
- **Flexible Configuration**: YAML-based configuration system

## Quick Start

### Prerequisites

- Python 3.10+
- Podman or Docker
- Claude Code CLI

### Installation

1. Clone the repository:
```bash
git clone https://github.com/ootakazuhiko/claude-conductor.git
cd claude-conductor
```

2. Set up the environment:
```bash
chmod +x setup_project.sh
./setup_project.sh
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Basic Usage

```python
from conductor import Orchestrator, Task

# Create orchestrator with 3 agents
orchestrator = Orchestrator()
orchestrator.config["num_agents"] = 3
orchestrator.start()

# Execute a code review task
task = Task(
    task_type="code_review",
    description="Review Python files for style and bugs",
    files=["src/main.py", "src/utils.py"]
)

result = orchestrator.execute_task(task)
print(f"Task completed: {result.status}")

orchestrator.stop()
```

## Architecture

```
┌─────────────────┐
│   Orchestrator  │  Central coordination
└─────────┬───────┘
          │
    ┌─────┴─────┐
    │  Message  │  Agent2Agent Protocol
    │  Broker   │
    └─────┬─────┘
          │
   ┌──────┼──────┐
   │      │      │
┌──▼──┐ ┌─▼───┐ ┌─▼───┐
│Agent│ │Agent│ │Agent│  Claude Code Instances
│  1  │ │  2  │ │  3  │  (Podman Containers)
└─────┘ └─────┘ └─────┘
```

## Project Structure

```
claude-conductor/
├── README.md
├── LICENSE
├── .github/workflows/     # CI/CD workflows
├── conductor/             # Main package
│   ├── __init__.py
│   ├── orchestrator.py    # Main orchestration logic
│   ├── agent.py          # Agent wrapper and management
│   └── protocol.py       # Agent2Agent communication
├── containers/           # Docker/Podman configurations
├── examples/            # Usage examples
├── tests/              # Test suite
├── docs/               # Documentation
└── scripts/            # Utility scripts
```

## Configuration

Configure the system using `config/config.yaml`:

```yaml
orchestrator:
  num_agents: 3
  max_workers: 10
  task_timeout: 300

agent:
  container_memory: "2g"
  container_cpu: "1.0"
  health_check_interval: 30

communication:
  socket_path: "/tmp/claude_orchestrator.sock"
  message_timeout: 5.0
```

## Task Types

- **code_review**: Analyze code for issues and improvements
- **refactor**: Restructure code while maintaining functionality
- **test_generation**: Generate comprehensive test suites
- **analysis**: Perform code analysis and documentation
- **generic**: Execute custom commands

## Development

### Running Tests

```bash
./tests/run_tests.sh
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Roadmap

- [ ] Kubernetes deployment support
- [ ] Redis-based message broker
- [ ] Web UI for monitoring
- [ ] Auto-scaling capabilities
- [ ] Distributed deployment
- [ ] Performance metrics dashboard

## Support

For issues and questions, please open an issue on the [GitHub repository](https://github.com/ootakazuhiko/claude-conductor/issues).