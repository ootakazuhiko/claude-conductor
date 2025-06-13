#!/bin/bash
# Claude Conductor - Start with Isolated Workspaces
# 隔離されたワークスペースを使用してClaude Conductorを起動

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CONDUCTOR_HOME="${CLAUDE_CONDUCTOR_HOME:-$HOME/.claude-conductor}"
CONFIG_FILE="${CONDUCTOR_CONFIG:-$CONDUCTOR_HOME/config/standalone-isolated.yaml}"
LOG_DIR="$CONDUCTOR_HOME/logs"
WORKSPACE_DIR="$CONDUCTOR_HOME/isolated"

echo -e "${BLUE}🚀 Claude Conductor - Isolated Workspace Mode${NC}"
echo "=========================================="

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is not installed${NC}"
        exit 1
    fi
    
    # Check Podman
    if ! command -v podman &> /dev/null; then
        echo -e "${RED}❌ Podman is not installed${NC}"
        echo "Please install Podman: https://podman.io/getting-started/installation"
        exit 1
    fi
    
    # Check Podman version
    PODMAN_VERSION=$(podman version --format '{{.Version}}' 2>/dev/null || echo "0.0.0")
    MAJOR_VERSION=$(echo $PODMAN_VERSION | cut -d. -f1)
    if [ "$MAJOR_VERSION" -lt "3" ]; then
        echo -e "${RED}❌ Podman version 3.0 or higher is required (found: $PODMAN_VERSION)${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
}

# Setup directories
setup_directories() {
    echo -e "${YELLOW}Setting up directories...${NC}"
    
    mkdir -p "$LOG_DIR"
    mkdir -p "$WORKSPACE_DIR"
    mkdir -p "$CONDUCTOR_HOME/config"
    mkdir -p "$CONDUCTOR_HOME/workspace"
    
    # Copy default config if not exists
    if [ ! -f "$CONFIG_FILE" ]; then
        if [ -f "config/standalone-isolated.yaml" ]; then
            cp config/standalone-isolated.yaml "$CONFIG_FILE"
            echo -e "${GREEN}✅ Created config file: $CONFIG_FILE${NC}"
        else
            echo -e "${RED}❌ Config file not found: $CONFIG_FILE${NC}"
            exit 1
        fi
    fi
}

# Pull required container images
pull_images() {
    echo -e "${YELLOW}Pulling container images...${NC}"
    
    # Read images from config
    IMAGES=(
        "ubuntu:22.04"
        "python:3.11-slim"
        "node:18-alpine"
        "alpine:latest"
    )
    
    for IMAGE in "${IMAGES[@]}"; do
        echo -e "  Pulling $IMAGE..."
        if podman pull "$IMAGE" > /dev/null 2>&1; then
            echo -e "${GREEN}  ✅ $IMAGE${NC}"
        else
            echo -e "${YELLOW}  ⚠️  Failed to pull $IMAGE (will retry on first use)${NC}"
        fi
    done
}

# Initialize Podman network
init_network() {
    echo -e "${YELLOW}Initializing Podman network...${NC}"
    
    NETWORK_NAME="claude-dev-net"
    
    # Check if network exists
    if podman network exists "$NETWORK_NAME" 2>/dev/null; then
        echo -e "${GREEN}✅ Network $NETWORK_NAME already exists${NC}"
    else
        # Create network
        podman network create \
            --subnet 10.89.0.0/24 \
            --gateway 10.89.0.1 \
            "$NETWORK_NAME" > /dev/null
        echo -e "${GREEN}✅ Created network $NETWORK_NAME${NC}"
    fi
}

# Start orchestrator with isolated workspace support
start_orchestrator() {
    echo -e "${YELLOW}Starting orchestrator...${NC}"
    
    # Check if already running
    if pgrep -f "conductor.orchestrator" > /dev/null; then
        echo -e "${YELLOW}⚠️  Orchestrator already running${NC}"
        return
    fi
    
    # Start orchestrator
    cd "$CONDUCTOR_HOME"
    
    # Create Python command
    PYTHON_CMD="python3 -m conductor.orchestrator --config $CONFIG_FILE"
    
    # Start in background
    nohup $PYTHON_CMD > "$LOG_DIR/orchestrator.log" 2>&1 &
    ORCHESTRATOR_PID=$!
    
    # Save PID
    echo $ORCHESTRATOR_PID > "$CONDUCTOR_HOME/orchestrator.pid"
    
    # Wait for startup
    sleep 3
    
    # Check if running
    if kill -0 $ORCHESTRATOR_PID 2>/dev/null; then
        echo -e "${GREEN}✅ Orchestrator started (PID: $ORCHESTRATOR_PID)${NC}"
    else
        echo -e "${RED}❌ Failed to start orchestrator${NC}"
        cat "$LOG_DIR/orchestrator.log"
        exit 1
    fi
}

# Start web dashboard
start_dashboard() {
    echo -e "${YELLOW}Starting web dashboard...${NC}"
    
    # Check if already running
    if pgrep -f "conductor.dashboard" > /dev/null; then
        echo -e "${YELLOW}⚠️  Dashboard already running${NC}"
        return
    fi
    
    # Start dashboard
    cd "$CONDUCTOR_HOME"
    
    # Create Python command
    PYTHON_CMD="python3 -m conductor.dashboard --config $CONFIG_FILE"
    
    # Start in background
    nohup $PYTHON_CMD > "$LOG_DIR/dashboard.log" 2>&1 &
    DASHBOARD_PID=$!
    
    # Save PID
    echo $DASHBOARD_PID > "$CONDUCTOR_HOME/dashboard.pid"
    
    # Wait for startup
    sleep 2
    
    # Check if running
    if kill -0 $DASHBOARD_PID 2>/dev/null; then
        echo -e "${GREEN}✅ Dashboard started (PID: $DASHBOARD_PID)${NC}"
        echo -e "${BLUE}🌐 Dashboard URL: http://localhost:8080${NC}"
    else
        echo -e "${RED}❌ Failed to start dashboard${NC}"
        cat "$LOG_DIR/dashboard.log"
    fi
}

# Show example usage
show_examples() {
    echo ""
    echo -e "${BLUE}📚 Example Usage:${NC}"
    echo "=========================================="
    echo ""
    echo "1. Python Development Environment:"
    echo -e "${GREEN}curl -X POST http://localhost:8081/tasks \\
  -H 'Content-Type: application/json' \\
  -d '{
    \"task_type\": \"isolated_execution\",
    \"description\": \"Run Python tests\",
    \"environment\": \"python-dev\",
    \"commands\": [
      \"cd /workspace/src\",
      \"python -m pytest tests/\"
    ]
  }'${NC}"
    echo ""
    echo "2. Node.js Build Environment:"
    echo -e "${GREEN}curl -X POST http://localhost:8081/tasks \\
  -H 'Content-Type: application/json' \\
  -d '{
    \"task_type\": \"isolated_execution\",
    \"description\": \"Build Node.js project\",
    \"environment\": \"nodejs-dev\",
    \"commands\": [
      \"cd /workspace/src\",
      \"npm install\",
      \"npm run build\"
    ]
  }'${NC}"
    echo ""
    echo "3. Full Stack Development:"
    echo -e "${GREEN}curl -X POST http://localhost:8081/tasks \\
  -H 'Content-Type: application/json' \\
  -d '{
    \"task_type\": \"isolated_execution\",
    \"description\": \"Run integration tests\",
    \"environment\": \"fullstack\",
    \"commands\": [
      \"cd /workspace\",
      \"./scripts/setup-dev.sh\",
      \"./scripts/run-tests.sh\"
    ]
  }'${NC}"
}

# Show status
show_status() {
    echo ""
    echo -e "${BLUE}📊 Status:${NC}"
    echo "=========================================="
    echo -e "Config file: ${GREEN}$CONFIG_FILE${NC}"
    echo -e "Log directory: ${GREEN}$LOG_DIR${NC}"
    echo -e "Workspace directory: ${GREEN}$WORKSPACE_DIR${NC}"
    echo ""
    echo "Services:"
    
    # Check orchestrator
    if [ -f "$CONDUCTOR_HOME/orchestrator.pid" ]; then
        PID=$(cat "$CONDUCTOR_HOME/orchestrator.pid")
        if kill -0 $PID 2>/dev/null; then
            echo -e "  Orchestrator: ${GREEN}✅ Running (PID: $PID)${NC}"
        else
            echo -e "  Orchestrator: ${RED}❌ Not running${NC}"
        fi
    else
        echo -e "  Orchestrator: ${YELLOW}⚠️  No PID file${NC}"
    fi
    
    # Check dashboard
    if [ -f "$CONDUCTOR_HOME/dashboard.pid" ]; then
        PID=$(cat "$CONDUCTOR_HOME/dashboard.pid")
        if kill -0 $PID 2>/dev/null; then
            echo -e "  Dashboard: ${GREEN}✅ Running (PID: $PID)${NC}"
        else
            echo -e "  Dashboard: ${RED}❌ Not running${NC}"
        fi
    else
        echo -e "  Dashboard: ${YELLOW}⚠️  No PID file${NC}"
    fi
    
    # Check Podman
    CONTAINER_COUNT=$(podman ps --filter "name=claude-agent-*" --format "{{.Names}}" | wc -l)
    echo -e "  Active containers: ${GREEN}$CONTAINER_COUNT${NC}"
}

# Main execution
main() {
    check_prerequisites
    setup_directories
    pull_images
    init_network
    start_orchestrator
    start_dashboard
    show_status
    show_examples
    
    echo ""
    echo -e "${GREEN}✅ Claude Conductor started with isolated workspaces!${NC}"
    echo ""
    echo "To stop all services, run:"
    echo -e "${BLUE}$0 stop${NC}"
}

# Handle stop command
if [ "$1" == "stop" ]; then
    echo -e "${YELLOW}Stopping Claude Conductor...${NC}"
    
    # Stop orchestrator
    if [ -f "$CONDUCTOR_HOME/orchestrator.pid" ]; then
        PID=$(cat "$CONDUCTOR_HOME/orchestrator.pid")
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            echo -e "${GREEN}✅ Orchestrator stopped${NC}"
        fi
        rm -f "$CONDUCTOR_HOME/orchestrator.pid"
    fi
    
    # Stop dashboard
    if [ -f "$CONDUCTOR_HOME/dashboard.pid" ]; then
        PID=$(cat "$CONDUCTOR_HOME/dashboard.pid")
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            echo -e "${GREEN}✅ Dashboard stopped${NC}"
        fi
        rm -f "$CONDUCTOR_HOME/dashboard.pid"
    fi
    
    # Stop all agent containers
    echo -e "${YELLOW}Stopping agent containers...${NC}"
    podman stop $(podman ps --filter "name=claude-agent-*" -q) 2>/dev/null || true
    podman rm $(podman ps -a --filter "name=claude-agent-*" -q) 2>/dev/null || true
    
    echo -e "${GREEN}✅ All services stopped${NC}"
    exit 0
fi

# Run main
main