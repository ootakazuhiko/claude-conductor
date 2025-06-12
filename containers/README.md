# Container Configuration

This directory contains Docker and Podman configuration files for running Claude Conductor in containerized environments.

## Files

- `Dockerfile` - Main container image definition
- `docker-compose.yml` - Multi-container orchestration setup
- `install-claude-code.sh` - Claude Code CLI installation script
- `entrypoint.sh` - Container entrypoint script

## Quick Start with Docker Compose

1. Build and start all services:
```bash
cd containers/
docker-compose up --build
```

2. Scale agents:
```bash
docker-compose up --scale agent-001=3 --scale agent-002=3
```

## Manual Docker Build

```bash
# Build the image
docker build -f containers/Dockerfile -t claude-conductor .

# Run a single agent
docker run -it --rm \
  -v $(pwd)/workspace:/workspace \
  -e AGENT_ID=agent_001 \
  claude-conductor
```

## Podman Usage

```bash
# Build with Podman
podman build -f containers/Dockerfile -t claude-conductor .

# Run with Podman
podman run -it --rm \
  -v $(pwd)/workspace:/workspace:Z \
  -e AGENT_ID=agent_001 \
  claude-conductor
```

## Environment Variables

- `AGENT_ID` - Unique identifier for the agent
- `WORKSPACE` - Working directory path (default: /workspace)
- `ORCHESTRATOR_SOCKET` - Socket path for orchestrator communication

## Volumes

- `/workspace` - Agent working directory
- Container-specific workspaces are isolated between agents

## Networking

All containers run on the `claude-network` bridge network for inter-container communication.

## Development

To modify the Claude Code installation:

1. Edit `install-claude-code.sh` with actual installation steps
2. Rebuild the container image
3. Test with a single agent first

## Production Deployment

For production use:

1. Replace the mock Claude Code CLI with the real implementation
2. Configure proper resource limits in docker-compose.yml
3. Set up external volumes for persistent storage
4. Configure logging and monitoring