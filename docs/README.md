# Claude Conductor Documentation

This directory contains comprehensive documentation for the Claude Conductor multi-agent orchestration system.

## Documentation Structure

### Main Documentation
- `architecture.md` - System architecture and design principles
- `api_reference.md` - Complete API documentation with examples
- `getting-started.md` - Quick start guide and tutorials
- `SECURITY.md` - Security considerations and best practices
- `isolated-workspaces.md` - Workspace isolation guide

### Auto-Generated Documentation
The `auto_generated/` directory contains automatically generated API documentation:
- `orchestrator.md` - Main orchestrator class
- `agent.md` - Individual agent wrapper
- `workspace_isolation.md` - Isolated workspace management
- `error_handler.md` - Error handling framework
- `exceptions.md` - Exception hierarchy
- `protocol.md` - Agent communication protocol
- `utils.md` - Utility functions

### Tools
- `generate_docs.py` - Auto-documentation generator script

## Quick Links

- [Getting Started](getting-started.md) - Begin here if you're new to Claude Conductor
- [Architecture Overview](architecture.md) - Understand the system design
- [API Reference](api_reference.md) - Complete function and class documentation
- [Security Guide](SECURITY.md) - Security considerations and best practices
- [Isolated Workspaces](isolated-workspaces.md) - Container isolation guide

## Contributing to Documentation

When contributing to the documentation:

1. Use clear, concise language
2. Include code examples where appropriate
3. Update the relevant sections when adding new features
4. Follow the existing structure and formatting

### Regenerating Auto-Documentation

To regenerate the auto-generated documentation after code changes:

```bash
python docs/generate_docs.py conductor docs/auto_generated
```

The documentation generator extracts docstrings, type hints, and function signatures to create comprehensive API documentation.

## Documentation Format

All documentation is written in Markdown format for easy reading and maintenance.