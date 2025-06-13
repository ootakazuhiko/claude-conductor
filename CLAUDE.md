# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Conductor is a multi-agent orchestration system for Claude Code instances. It enables parallel execution and coordinated task distribution across multiple containerized agents.

## Development Commands

### Setup and Installation
```bash
# Initial setup
./scripts/setup.sh

# Setup with container build
./scripts/setup.sh --with-container

# Setup with tests
./scripts/setup.sh --with-tests
```

### Testing
```bash
# Run all tests
./scripts/test.sh

# Run specific test types
./scripts/test.sh --type unit
./scripts/test.sh --type integration
./scripts/test.sh --type e2e

# Run with coverage
./scripts/test.sh --coverage

# Run in watch mode
./scripts/test.sh --watch

# Run linting only
./scripts/test.sh lint

# Run security checks
./scripts/test.sh security
```

### Development and Deployment
```bash
# Local development
python -m conductor.orchestrator --agents 3

# Run with demo tasks
python -m conductor.orchestrator --demo

# Deploy locally
./scripts/deploy.sh --type local --agents 5

# Deploy with Docker
./scripts/deploy.sh --type docker --build --detached

# Deploy to Kubernetes
./scripts/deploy.sh --type k8s --config config/production.yaml

# Check deployment status
./scripts/deploy.sh status

# Cleanup deployment
./scripts/deploy.sh cleanup
```

### Container Operations
```bash
# Build container image
docker build -f containers/Dockerfile -t claude-conductor .

# Run with docker-compose
cd containers/ && docker-compose up

# Scale agents
docker-compose up --scale agent-001=5

# View logs
docker-compose logs -f
```

## Architecture Overview

The system consists of three main components:

### 1. Orchestrator (`conductor/orchestrator.py`)
- Central coordination and task distribution
- Agent lifecycle management
- Load balancing and resource monitoring
- Statistics collection and reporting

### 2. Agent System (`conductor/agent.py`)
- Claude Code wrapper for container management
- Task execution and result processing
- Health monitoring and recovery
- File system isolation

### 3. Communication Layer (`conductor/protocol.py`)
- Unix socket-based inter-agent communication
- Message routing and reliability
- Protocol abstraction for future extensions

## Key Configuration Files

### Main Configuration (`config/config.yaml`)
```yaml
orchestrator:
  num_agents: 3           # Number of agents to spawn
  max_workers: 10         # Thread pool size
  task_timeout: 300       # Default task timeout (seconds)

agent:
  container_memory: "2g"  # Memory limit per agent
  container_cpu: "1.0"    # CPU limit per agent
  health_check_interval: 30  # Health check frequency

communication:
  socket_path: "/tmp/claude_orchestrator.sock"
  message_timeout: 5.0
  retry_count: 3
```

### Container Configuration (`containers/docker-compose.yml`)
- Multi-agent orchestration setup
- Resource limits and networking
- Volume management and persistence

## Task Types and Usage

### Built-in Task Types
- `code_review`: Analyze code for issues and improvements
- `refactor`: Restructure code while maintaining functionality
- `test_generation`: Generate comprehensive test suites
- `analysis`: Perform code analysis and documentation
- `generic`: Execute custom commands

### Creating Tasks
```python
from conductor import create_task, Orchestrator

# Simple task
task = create_task(
    task_type="code_review",
    description="Review Python files for security issues",
    files=["src/auth.py", "src/validators.py"],
    priority=8,
    timeout=120.0
)

# Parallel task
parallel_task = create_task(
    task_type="analysis",
    parallel=True,
    subtasks=[
        {"type": "code_review", "files": ["backend/"]},
        {"type": "test_generation", "files": ["frontend/"]},
        {"type": "refactor", "files": ["utils/"]}
    ]
)
```

## Development Workflow

### Adding New Features
1. Create feature branch: `git checkout -b feature/new-feature`
2. Write tests first: `./scripts/test.sh --type unit`
3. Implement feature in appropriate module
4. Update documentation if needed
5. Run full test suite: `./scripts/test.sh`
6. Submit pull request

### Code Quality Standards
- All code must pass linting: `./scripts/test.sh lint`
- Minimum 80% test coverage
- Type hints required for public APIs
- Docstrings for all public functions and classes

### Testing Strategy
- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **E2E Tests**: Test complete workflows with mocked containers
- **Container Tests**: Test actual container functionality (when available)

## Common Development Tasks

### Adding a New Task Type
1. Extend `ClaudeAgent._execute_*` methods in `conductor/agent.py`
2. Add task type validation in `Task` class
3. Create tests in `tests/unit/test_agent.py`
4. Update documentation

### Modifying Agent Behavior
1. Update `ClaudeCodeWrapper` in `conductor/agent.py`
2. Modify container setup if needed in `containers/`
3. Update health check logic
4. Test with integration tests

### Extending Communication Protocol
1. Add new message types to `MessageType` enum in `conductor/protocol.py`
2. Implement handlers in `Agent2AgentProtocol`
3. Update message routing logic
4. Add protocol tests

## Debugging and Troubleshooting

### Common Issues

**No agents starting:**
```bash
# Check container runtime
podman --version  # or docker --version

# Check permissions
ls -la /tmp/claude_*

# Run with debug logging
python -m conductor.orchestrator --debug
```

**Task execution failures:**
```bash
# Check agent logs
./scripts/deploy.sh status

# Examine container logs
docker logs claude_agent_001

# Run individual agent
python -c "from conductor import ClaudeAgent; agent = ClaudeAgent('test'); agent.start()"
```

**Performance issues:**
```bash
# Monitor resource usage
./scripts/test.sh --coverage

# Check agent utilization
python -m conductor.orchestrator --agents 1  # Start with fewer agents

# Profile task execution
python -m cProfile -m conductor.orchestrator
```

### Log Locations
- Orchestrator logs: `logs/orchestrator.log`
- Agent logs: Container stdout/stderr
- Test results: `test-results.xml`, `htmlcov/`

## Security Considerations

- All agents run in isolated containers
- No network access by default
- File system access limited to workspace
- Resource limits enforced per container
- Socket communication uses local filesystem

## Performance Tuning

### Scaling Guidelines
- **Small projects**: 1-2 agents, 4-6 workers
- **Medium projects**: 3-5 agents, 8-12 workers  
- **Large projects**: 5-10 agents, 15-20 workers

### Resource Requirements
- **Memory**: 2GB per agent minimum
- **CPU**: 1 core per agent recommended
- **Storage**: 1GB for workspaces and logs

## Extension Points

The system is designed for extensibility:

1. **Custom Task Processors**: Add new task types
2. **Communication Backends**: Replace Unix sockets
3. **Container Runtimes**: Support different container engines
4. **Monitoring Integration**: Add metrics and observability
5. **Authentication**: Pluggable auth systems

## Future Development

Priority areas for enhancement:
1. Web UI for monitoring and control
2. Redis/database integration for persistence
3. Kubernetes native deployment
4. Real Claude Code CLI integration
5. Advanced scheduling and resource management