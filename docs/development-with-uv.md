# Development with uv

This guide explains how to use `uv` for Python package management in Claude Conductor.

## What is uv?

`uv` is an extremely fast Python package manager written in Rust by Astral (the creators of Ruff). It's designed to be a drop-in replacement for pip, pip-tools, and virtualenv with significant performance improvements.

## Quick Start

### Prerequisites

1. Install uv:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Verify installation:
   ```bash
   uv --version
   ```

### Setting up the Project

1. Clone the repository:
   ```bash
   git clone https://github.com/ootakazuhiko/claude-conductor.git
   cd claude-conductor
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   # Create virtual environment using Python 3.11
   uv venv

   # Activate the virtual environment
   source .venv/bin/activate  # On Linux/macOS
   # or
   .venv\Scripts\activate  # On Windows

   # Install the project with all dependencies
   uv pip install -e ".[all]"
   ```

### Daily Development Workflow

#### Installing Dependencies

```bash
# Install only core dependencies
uv pip install -e .

# Install with development dependencies
uv pip install -e ".[dev]"

# Install with all optional dependencies
uv pip install -e ".[all]"
```

#### Adding New Dependencies

1. Add the dependency to `pyproject.toml`:
   ```toml
   dependencies = [
       "new-package>=1.0.0",
   ]
   ```

2. Install the updated dependencies:
   ```bash
   uv pip install -e .
   ```

#### Development Commands

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=conductor

# Format code
black conductor tests

# Lint code
ruff check conductor tests

# Type check
mypy conductor

# Run all checks
black conductor tests && ruff check conductor tests && mypy conductor && pytest
```

### Working with Docker

The Docker images have been updated to use uv:

```bash
# Build development image
docker-compose --profile development build

# Run development container
docker-compose --profile development up conductor-dev

# Build production image
docker-compose build conductor

# Run production container
docker-compose up conductor
```

### Benefits of uv

1. **Speed**: 10-100x faster than pip for dependency resolution and installation
2. **Reproducibility**: Consistent dependency resolution across different environments
3. **Simplicity**: Single tool replaces pip, pip-tools, and virtualenv
4. **Compatibility**: Works with existing `pyproject.toml` and `requirements.txt` files
5. **Safety**: Built-in dependency verification and security features

### Common uv Commands

```bash
# Create a new virtual environment
uv venv

# Install from requirements.txt
uv pip install -r requirements.txt

# Install editable package
uv pip install -e .

# Show installed packages
uv pip list

# Show package information
uv pip show package-name

# Uninstall package
uv pip uninstall package-name

# Upgrade package
uv pip install --upgrade package-name

# Install specific version
uv pip install package-name==1.0.0
```

### Troubleshooting

#### uv command not found

Make sure uv is in your PATH:
```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

Add this to your shell configuration file (`~/.bashrc`, `~/.zshrc`, etc.)

#### Virtual environment not activated

Always activate the virtual environment before running commands:
```bash
source .venv/bin/activate
```

#### Dependency conflicts

uv provides clear error messages for dependency conflicts. Read the error message carefully and adjust version constraints in `pyproject.toml` as needed.

### Migration from pip

If you have an existing environment with pip:

1. Export current dependencies:
   ```bash
   pip freeze > old-requirements.txt
   ```

2. Create new environment with uv:
   ```bash
   uv venv --python 3.11
   source .venv/bin/activate
   uv pip install -e ".[all]"
   ```

3. Verify all dependencies are installed:
   ```bash
   uv pip list
   ```

### CI/CD Integration

For GitHub Actions:

```yaml
- name: Install uv
  run: curl -LsSf https://astral.sh/uv/install.sh | sh

- name: Install dependencies
  run: |
    uv venv
    source .venv/bin/activate
    uv pip install -e ".[dev]"

- name: Run tests
  run: |
    source .venv/bin/activate
    pytest
```

## Additional Resources

- [uv Documentation](https://github.com/astral-sh/uv)
- [Python Packaging Guide](https://packaging.python.org/)
- [PEP 621 - Project Metadata](https://peps.python.org/pep-0621/)