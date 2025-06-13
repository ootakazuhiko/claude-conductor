#!/bin/bash
set -e

# Claude Conductor - Quick Start Script for Single PC
# This script sets up a minimal, standalone version of Claude Conductor

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDUCTOR_HOME="$HOME/.claude-conductor"
VENV_DIR="$CONDUCTOR_HOME/venv"
CONFIG_DIR="$CONDUCTOR_HOME/config"
WORKSPACE_DIR="$CONDUCTOR_HOME/workspace"
LOGS_DIR="$CONDUCTOR_HOME/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    
    local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    log_info "Found Python $python_version"
    
    if [[ $(echo "$python_version >= 3.10" | bc -l) -eq 0 ]]; then
        log_warning "Python 3.10+ is recommended, but $python_version should work"
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
        log_error "pip is required but not installed"
        exit 1
    fi
    
    # Check for container runtime (optional)
    if command -v docker &> /dev/null; then
        log_info "Docker detected - container mode available"
        CONTAINER_RUNTIME="docker"
    elif command -v podman &> /dev/null; then
        log_info "Podman detected - container mode available"
        CONTAINER_RUNTIME="podman"
    else
        log_warning "No container runtime detected - running in local mode only"
        CONTAINER_RUNTIME=""
    fi
    
    log_success "System requirements check completed"
}

# Create directory structure
setup_directories() {
    log_info "Setting up directory structure..."
    
    mkdir -p "$CONDUCTOR_HOME"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$WORKSPACE_DIR"
    mkdir -p "$LOGS_DIR"
    
    log_success "Directory structure created at $CONDUCTOR_HOME"
}

# Setup Python virtual environment
setup_python_env() {
    log_info "Setting up Python virtual environment..."
    
    # Create virtual environment
    python3 -m venv "$VENV_DIR"
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install Claude Conductor in development mode
    pip install -e "$SCRIPT_DIR"
    
    log_success "Python environment setup completed"
}

# Create minimal configuration
create_config() {
    log_info "Creating minimal configuration..."
    
    cat > "$CONFIG_DIR/config.yaml" << EOF
# Claude Conductor - Standalone Configuration
num_agents: 2
max_workers: 4
task_timeout: 120
log_level: "INFO"

# Simplified container configuration
container_config:
  image: "ubuntu:22.04"
  memory_limit: "1g"
  cpu_limit: "0.5"

# Local storage paths
storage:
  workspace_path: "$WORKSPACE_DIR"
  logs_path: "$LOGS_DIR"

# Network configuration
network:
  dashboard_port: 8080
  health_check_interval: 30

# Disable complex features for standalone mode
features:
  redis_enabled: false
  monitoring_enabled: false
  clustering_enabled: false
EOF

    log_success "Configuration created at $CONFIG_DIR/config.yaml"
}

# Create simple docker-compose for standalone mode
create_simple_compose() {
    if [ -z "$CONTAINER_RUNTIME" ]; then
        log_info "Skipping Docker Compose creation (no container runtime)"
        return
    fi
    
    log_info "Creating simplified Docker Compose configuration..."
    
    cat > "$CONDUCTOR_HOME/docker-compose.yml" << EOF
version: '3.8'

services:
  conductor-standalone:
    build:
      context: $SCRIPT_DIR
      dockerfile: containers/Dockerfile
      target: production
    container_name: claude-conductor-standalone
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - conductor_workspace:/workspace
      - conductor_logs:/var/log/conductor
    environment:
      - CONDUCTOR_MODE=standalone
      - CONDUCTOR_LOG_LEVEL=INFO
      - CONDUCTOR_NUM_AGENTS=2
    command: ["full"]
    healthcheck:
      test: ["CMD", "/healthcheck.sh"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  conductor_workspace:
  conductor_logs:
EOF

    log_success "Docker Compose configuration created"
}

# Create startup scripts
create_scripts() {
    log_info "Creating startup scripts..."
    
    # Local startup script
    cat > "$CONDUCTOR_HOME/start-local.sh" << EOF
#!/bin/bash
# Start Claude Conductor in local mode

cd "$CONDUCTOR_HOME"
source "$VENV_DIR/bin/activate"

echo "Starting Claude Conductor locally..."
echo "Dashboard will be available at: http://localhost:8080"
echo "Press Ctrl+C to stop"

python -m conductor.orchestrator --config "$CONFIG_DIR/config.yaml" &
ORCHESTRATOR_PID=\$!

python "$SCRIPT_DIR/web/dashboard.py" --port 8080 --no-browser &
DASHBOARD_PID=\$!

# Wait for processes
wait \$ORCHESTRATOR_PID \$DASHBOARD_PID
EOF

    # Container startup script
    if [ -n "$CONTAINER_RUNTIME" ]; then
        cat > "$CONDUCTOR_HOME/start-container.sh" << EOF
#!/bin/bash
# Start Claude Conductor in container mode

cd "$CONDUCTOR_HOME"

echo "Starting Claude Conductor in container..."
echo "Dashboard will be available at: http://localhost:8080"
echo "Press Ctrl+C to stop"

$CONTAINER_RUNTIME compose up --build
EOF
    fi
    
    # Stop script
    cat > "$CONDUCTOR_HOME/stop.sh" << EOF
#!/bin/bash
# Stop Claude Conductor

echo "Stopping Claude Conductor..."

# Stop local processes
pkill -f "conductor.orchestrator" || true
pkill -f "dashboard.py" || true

# Stop containers if running
if [ -n "$CONTAINER_RUNTIME" ]; then
    cd "$CONDUCTOR_HOME"
    $CONTAINER_RUNTIME compose down || true
fi

echo "Claude Conductor stopped"
EOF
    
    # Make scripts executable
    chmod +x "$CONDUCTOR_HOME"/*.sh
    
    log_success "Startup scripts created"
}

# Create CLI wrapper
create_cli_wrapper() {
    log_info "Creating CLI wrapper..."
    
    cat > "$CONDUCTOR_HOME/conductor" << EOF
#!/bin/bash
# Claude Conductor CLI wrapper

CONDUCTOR_HOME="$CONDUCTOR_HOME"
VENV_DIR="$VENV_DIR"
CONFIG_DIR="$CONFIG_DIR"

# Activate Python environment
source "\$VENV_DIR/bin/activate"

case "\$1" in
    "start")
        echo "Starting Claude Conductor..."
        "\$CONDUCTOR_HOME/start-local.sh"
        ;;
    "start-container")
        echo "Starting Claude Conductor in container mode..."
        "\$CONDUCTOR_HOME/start-container.sh"
        ;;
    "stop")
        "\$CONDUCTOR_HOME/stop.sh"
        ;;
    "status")
        echo "Checking Claude Conductor status..."
        if pgrep -f "conductor.orchestrator" > /dev/null; then
            echo "Orchestrator: Running"
        else
            echo "Orchestrator: Stopped"
        fi
        if pgrep -f "dashboard.py" > /dev/null; then
            echo "Dashboard: Running"
        else
            echo "Dashboard: Stopped"
        fi
        ;;
    "logs")
        echo "Recent logs:"
        tail -n 50 "\$CONDUCTOR_HOME/logs"/*.log 2>/dev/null || echo "No logs found"
        ;;
    "config")
        echo "Opening configuration file..."
        \${EDITOR:-nano} "\$CONFIG_DIR/config.yaml"
        ;;
    "dashboard")
        echo "Opening dashboard..."
        python -c "import webbrowser; webbrowser.open('http://localhost:8080')"
        ;;
    "test")
        echo "Running basic test..."
        python -c "
from conductor import create_task, Orchestrator
print('Creating test task...')
task = create_task(task_type='generic', description='echo \"Hello from Claude Conductor!\"')
print(f'Task created: {task.task_id}')
print('Test completed successfully!')
"
        ;;
    *)
        echo "Claude Conductor - Standalone Mode"
        echo ""
        echo "Usage: \$0 [command]"
        echo ""
        echo "Commands:"
        echo "  start           Start in local mode"
        echo "  start-container Start in container mode"
        echo "  stop            Stop all services"
        echo "  status          Show service status"
        echo "  logs            Show recent logs"
        echo "  config          Edit configuration"
        echo "  dashboard       Open web dashboard"
        echo "  test            Run basic test"
        echo ""
        echo "Dashboard: http://localhost:8080"
        echo "Config:    \$CONFIG_DIR/config.yaml"
        echo "Logs:      \$CONDUCTOR_HOME/logs/"
        ;;
esac
EOF

    chmod +x "$CONDUCTOR_HOME/conductor"
    
    log_success "CLI wrapper created at $CONDUCTOR_HOME/conductor"
}

# Create quick start documentation
create_documentation() {
    log_info "Creating quick start documentation..."
    
    cat > "$CONDUCTOR_HOME/README.md" << EOF
# Claude Conductor - Standalone Setup

This is a simplified, single-PC installation of Claude Conductor.

## Quick Start

1. **Start the system:**
   \`\`\`bash
   ./conductor start
   \`\`\`

2. **Open the dashboard:**
   - URL: http://localhost:8080
   - Or run: \`./conductor dashboard\`

3. **Submit a test task:**
   \`\`\`bash
   ./conductor test
   \`\`\`

4. **Stop the system:**
   \`\`\`bash
   ./conductor stop
   \`\`\`

## Directory Structure

- **Config:** \`$CONFIG_DIR/\`
- **Workspace:** \`$WORKSPACE_DIR/\`
- **Logs:** \`$LOGS_DIR/\`
- **Python Env:** \`$VENV_DIR/\`

## Available Commands

- \`./conductor start\` - Start local mode
- \`./conductor start-container\` - Start container mode  
- \`./conductor stop\` - Stop all services
- \`./conductor status\` - Check service status
- \`./conductor logs\` - View recent logs
- \`./conductor config\` - Edit configuration
- \`./conductor dashboard\` - Open web dashboard
- \`./conductor test\` - Run basic test

## Configuration

Edit \`$CONFIG_DIR/config.yaml\` to customize:
- Number of agents
- Resource limits
- Log levels
- Storage paths

## Troubleshooting

1. **Check status:** \`./conductor status\`
2. **View logs:** \`./conductor logs\`
3. **Restart:** \`./conductor stop && ./conductor start\`

## Advanced Usage

For production deployment, see the full documentation in the main repository.
EOF

    log_success "Documentation created at $CONDUCTOR_HOME/README.md"
}

# Add to PATH
setup_path() {
    log_info "Setting up PATH..."
    
    # Add to bashrc if not already there
    if ! grep -q "claude-conductor" ~/.bashrc 2>/dev/null; then
        echo "" >> ~/.bashrc
        echo "# Claude Conductor" >> ~/.bashrc
        echo "export PATH=\"$CONDUCTOR_HOME:\$PATH\"" >> ~/.bashrc
        echo "alias conductor=\"$CONDUCTOR_HOME/conductor\"" >> ~/.bashrc
        
        log_success "Added to ~/.bashrc (restart terminal or run 'source ~/.bashrc')"
    fi
    
    # Create symlink for current session
    if [ -w "/usr/local/bin" ]; then
        ln -sf "$CONDUCTOR_HOME/conductor" "/usr/local/bin/conductor" 2>/dev/null || true
    fi
}

# Main installation function
main() {
    echo "=================================="
    echo "Claude Conductor - Quick Start"
    echo "Single PC Standalone Installation"
    echo "=================================="
    echo ""
    
    check_requirements
    setup_directories
    setup_python_env
    create_config
    create_simple_compose
    create_scripts
    create_cli_wrapper
    create_documentation
    setup_path
    
    echo ""
    echo "=================================="
    log_success "Installation completed!"
    echo "=================================="
    echo ""
    echo "🚀 Quick Start:"
    echo "   cd $CONDUCTOR_HOME"
    echo "   ./conductor start"
    echo ""
    echo "🌐 Dashboard: http://localhost:8080"
    echo "📖 Documentation: $CONDUCTOR_HOME/README.md"
    echo "⚙️  Configuration: $CONFIG_DIR/config.yaml"
    echo ""
    echo "Run './conductor' for all available commands"
    echo ""
}

# Handle command line arguments
case "${1:-install}" in
    "install")
        main
        ;;
    "uninstall")
        log_info "Uninstalling Claude Conductor..."
        "$CONDUCTOR_HOME/stop.sh" 2>/dev/null || true
        rm -rf "$CONDUCTOR_HOME"
        # Remove from bashrc
        sed -i '/# Claude Conductor/,+2d' ~/.bashrc 2>/dev/null || true
        # Remove symlink
        rm -f "/usr/local/bin/conductor" 2>/dev/null || true
        log_success "Uninstallation completed"
        ;;
    "help"|"-h"|"--help")
        echo "Claude Conductor Quick Start"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  install     Install Claude Conductor (default)"
        echo "  uninstall   Remove Claude Conductor completely"
        echo "  help        Show this help message"
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac