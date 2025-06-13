#!/bin/bash
# Claude Conductor - Run Collaborative Development Demo
# 複数のエージェントが協調してWebアプリケーションを開発するデモ

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Demo root directory
DEMO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$DEMO_DIR/.." && pwd )"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Claude Conductor - Collaborative Development Demo      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}This demo shows how 4 specialized agents work together to${NC}"
echo -e "${CYAN}develop a complete web application with:${NC}"
echo ""
echo -e "  ${GREEN}✓${NC} Flask REST API backend"
echo -e "  ${GREEN}✓${NC} Comprehensive test suite"
echo -e "  ${GREEN}✓${NC} Docker containerization"
echo -e "  ${GREEN}✓${NC} CI/CD pipeline"
echo -e "  ${GREEN}✓${NC} API documentation"
echo ""

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is not installed${NC}"
        exit 1
    fi
    
    # Check Podman/Docker
    if command -v podman &> /dev/null; then
        CONTAINER_RUNTIME="podman"
        echo -e "${GREEN}✅ Found Podman${NC}"
    elif command -v docker &> /dev/null; then
        CONTAINER_RUNTIME="docker"
        echo -e "${GREEN}✅ Found Docker${NC}"
    else
        echo -e "${RED}❌ Neither Podman nor Docker is installed${NC}"
        echo "Please install Podman or Docker first"
        exit 1
    fi
    
    # Check if conductor module is available
    if ! python3 -c "import conductor" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Conductor module not found in PYTHONPATH${NC}"
        echo -e "${CYAN}Adding project root to PYTHONPATH...${NC}"
        export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    fi
    
    echo -e "${GREEN}✅ All prerequisites met${NC}"
    echo ""
}

# Setup demo environment
setup_demo() {
    echo -e "${YELLOW}Setting up demo environment...${NC}"
    
    # Create necessary directories
    mkdir -p "$DEMO_DIR/sample-project/src"
    mkdir -p "$DEMO_DIR/sample-project/tests"
    mkdir -p "$DEMO_DIR/sample-project/docs"
    mkdir -p "$DEMO_DIR/logs"
    
    # Clean previous run artifacts if any
    if [ -d "$DEMO_DIR/sample-project/src/api" ]; then
        echo -e "${YELLOW}Cleaning previous demo artifacts...${NC}"
        rm -rf "$DEMO_DIR/sample-project/src/"*
        rm -rf "$DEMO_DIR/sample-project/tests/"*
        rm -rf "$DEMO_DIR/sample-project/docs/"*
        rm -f "$DEMO_DIR/sample-project/Dockerfile"
        rm -f "$DEMO_DIR/sample-project/docker-compose.yml"
        rm -f "$DEMO_DIR/sample-project/Makefile"
        rm -f "$DEMO_DIR/sample-project/.gitignore"
        rm -f "$DEMO_DIR/sample-project/setup.py"
        rm -f "$DEMO_DIR/sample-project/nginx.conf"
        rm -f "$DEMO_DIR/sample-project/deploy.sh"
    fi
    
    echo -e "${GREEN}✅ Demo environment ready${NC}"
    echo ""
}

# Run the demo
run_demo() {
    echo -e "${MAGENTA}🚀 Starting collaborative development demo...${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Set environment variables
    export CONDUCTOR_CONFIG="$DEMO_DIR/config/demo-config.yaml"
    export CONDUCTOR_LOG_DIR="$DEMO_DIR/logs"
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    
    # Run the demo
    cd "$DEMO_DIR/collaborative-dev"
    python3 multi_agent_demo.py
}

# Show results
show_results() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🎉 Demo completed successfully!${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}The agents have created a complete web application at:${NC}"
    echo -e "${BLUE}$DEMO_DIR/sample-project/${NC}"
    echo ""
    echo -e "${YELLOW}Project structure:${NC}"
    cd "$DEMO_DIR/sample-project"
    tree -L 3 2>/dev/null || find . -type f -not -path '*/\.*' | sort
    echo ""
    echo -e "${YELLOW}To test the application:${NC}"
    echo -e "${GREEN}1. cd $DEMO_DIR/sample-project${NC}"
    echo -e "${GREEN}2. python3 -m venv venv && source venv/bin/activate${NC}"
    echo -e "${GREEN}3. pip install -r requirements.txt${NC}"
    echo -e "${GREEN}4. python src/app.py${NC}"
    echo -e "${GREEN}5. curl http://localhost:5000/api/todos${NC}"
    echo ""
    echo -e "${YELLOW}Or use Docker:${NC}"
    echo -e "${GREEN}1. cd $DEMO_DIR/sample-project${NC}"
    echo -e "${GREEN}2. docker-compose up -d${NC}"
    echo -e "${GREEN}3. curl http://localhost/api/todos${NC}"
}

# Main execution
main() {
    clear
    check_prerequisites
    setup_demo
    
    # Confirmation
    echo -e "${YELLOW}This demo will:${NC}"
    echo -e "  • Start 4 specialized agents"
    echo -e "  • Execute ~8 development tasks"
    echo -e "  • Create a complete web application"
    echo -e "  • Take approximately 2-5 minutes"
    echo ""
    read -p "Press Enter to start the demo (Ctrl+C to cancel)..."
    echo ""
    
    # Run demo
    if run_demo; then
        show_results
    else
        echo -e "${RED}❌ Demo failed${NC}"
        echo -e "Check logs at: $DEMO_DIR/logs/"
        exit 1
    fi
}

# Handle cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"
    # Any cleanup commands here
}

trap cleanup EXIT

# Run main
main