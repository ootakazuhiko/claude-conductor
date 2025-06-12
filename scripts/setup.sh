#!/bin/bash
# Claude Conductor Setup Script

set -e

echo "=== Claude Conductor Setup ==="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running on supported OS
check_os() {
    print_status "Checking operating system..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_status "Linux detected"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        print_status "macOS detected"
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
}

# Check Python version
check_python() {
    print_status "Checking Python version..."
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        REQUIRED_VERSION="3.10"
        
        if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
            print_status "Python $PYTHON_VERSION found (required: $REQUIRED_VERSION+)"
        else
            print_error "Python $REQUIRED_VERSION+ required, found $PYTHON_VERSION"
            exit 1
        fi
    else
        print_error "Python 3 not found. Please install Python 3.10+"
        exit 1
    fi
}

# Check container runtime
check_container_runtime() {
    print_status "Checking container runtime..."
    
    if command -v podman &> /dev/null; then
        print_status "Podman found"
        CONTAINER_CMD="podman"
    elif command -v docker &> /dev/null; then
        print_status "Docker found"
        CONTAINER_CMD="docker"
    else
        print_warning "No container runtime found. Please install Podman or Docker."
        print_warning "Container-based features will not be available."
        CONTAINER_CMD=""
    fi
}

# Create virtual environment
setup_python_env() {
    print_status "Setting up Python virtual environment..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_status "Virtual environment created"
    else
        print_status "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    python -m pip install --upgrade pip setuptools wheel
    
    # Install dependencies
    if [ -f "requirements.txt" ]; then
        print_status "Installing Python dependencies..."
        pip install -r requirements.txt
        print_status "Dependencies installed"
    else
        print_warning "requirements.txt not found"
    fi
    
    # Install development dependencies if available
    if [ -f "requirements-dev.txt" ]; then
        print_status "Installing development dependencies..."
        pip install -r requirements-dev.txt
    fi
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p logs
    mkdir -p workspace
    mkdir -p config
    
    print_status "Directories created"
}

# Generate default configuration
generate_config() {
    print_status "Generating default configuration..."
    
    if [ ! -f "config/config.yaml" ]; then
        cat > config/config.yaml << 'EOF'
# Claude Conductor Configuration
orchestrator:
  num_agents: 3
  max_workers: 10
  task_timeout: 300
  log_level: INFO

agent:
  container_memory: "2g"
  container_cpu: "1.0"
  health_check_interval: 30
  startup_timeout: 60

communication:
  socket_path: "/tmp/claude_orchestrator.sock"
  message_timeout: 5.0
  retry_count: 3

task_queue:
  max_size: 1000
  priority_levels: 10
EOF
        print_status "Default configuration created at config/config.yaml"
    else
        print_status "Configuration file already exists"
    fi
}

# Setup git hooks (if in git repo)
setup_git_hooks() {
    if [ -d ".git" ]; then
        print_status "Setting up git hooks..."
        
        # Pre-commit hook
        cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
# Run tests before commit
source venv/bin/activate
python -m pytest tests/ -x
EOF
        chmod +x .git/hooks/pre-commit
        
        print_status "Git hooks configured"
    fi
}

# Build container image
build_container() {
    if [ -n "$CONTAINER_CMD" ]; then
        print_status "Building container image..."
        
        if [ -f "containers/Dockerfile" ]; then
            $CONTAINER_CMD build -f containers/Dockerfile -t claude-conductor:latest .
            print_status "Container image built successfully"
        else
            print_warning "Dockerfile not found, skipping container build"
        fi
    fi
}

# Run tests
run_tests() {
    print_status "Running tests..."
    
    source venv/bin/activate
    
    if command -v pytest &> /dev/null; then
        python -m pytest tests/ -v
        print_status "Tests completed"
    else
        print_warning "pytest not found, skipping tests"
    fi
}

# Main setup function
main() {
    print_status "Starting Claude Conductor setup..."
    
    check_os
    check_python
    check_container_runtime
    setup_python_env
    create_directories
    generate_config
    setup_git_hooks
    
    if [ "$1" == "--with-container" ]; then
        build_container
    fi
    
    if [ "$1" == "--with-tests" ]; then
        run_tests
    fi
    
    print_status "Setup completed successfully!"
    echo
    print_status "Next steps:"
    echo "  1. Activate virtual environment: source venv/bin/activate"
    echo "  2. Run the orchestrator: python -m conductor.orchestrator"
    echo "  3. Or run with demo: python -m conductor.orchestrator --demo"
    echo
    print_status "For more information, see docs/getting-started.md"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --with-container)
            BUILD_CONTAINER=true
            shift
            ;;
        --with-tests)
            RUN_TESTS=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --with-container  Build container image"
            echo "  --with-tests      Run tests after setup"
            echo "  --help           Show this help"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main setup
main "$@"