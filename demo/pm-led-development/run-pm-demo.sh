#!/bin/bash
# Claude Conductor - Run PM-Led Hierarchical Development Demo
# PMエージェントが他のエージェントを管理する階層的開発デモ

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
PROJECT_ROOT="$( cd "$DEMO_DIR/../.." && pwd )"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      Claude Conductor - PM-Led Development Demo            ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${CYAN}This demo shows a PM (Project Manager) agent leading a team${NC}"
echo -e "${CYAN}of 4 specialized development agents to build an e-commerce${NC}"
echo -e "${CYAN}platform with:${NC}"
echo ""
echo -e "  ${GREEN}✓${NC} Hierarchical task delegation"
echo -e "  ${GREEN}✓${NC} PM creating project plans"
echo -e "  ${GREEN}✓${NC} PM assigning tasks to team members"
echo -e "  ${GREEN}✓${NC} PM monitoring progress"
echo -e "  ${GREEN}✓${NC} Team collaboration simulation"
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
    mkdir -p "$DEMO_DIR/logs"
    mkdir -p "$DEMO_DIR/pm-project"
    
    # Clean previous run artifacts if any
    if [ -d "$DEMO_DIR/pm-project/backend" ]; then
        echo -e "${YELLOW}Cleaning previous demo artifacts...${NC}"
        rm -rf "$DEMO_DIR/pm-project"/*
    fi
    
    echo -e "${GREEN}✅ Demo environment ready${NC}"
    echo ""
}

# Run the demo
run_demo() {
    echo -e "${MAGENTA}🚀 Starting PM-led hierarchical development demo...${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    # Set environment variables
    export CONDUCTOR_LOG_DIR="$DEMO_DIR/logs"
    export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"
    
    # Run the demo
    cd "$DEMO_DIR"
    python3 pm_agent_demo.py
}

# Show results
show_results() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}🎉 Demo completed successfully!${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}The PM agent successfully managed the team to create:${NC}"
    echo -e "${BLUE}$DEMO_DIR/pm-project/${NC}"
    echo ""
    echo -e "${YELLOW}Key deliverables:${NC}"
    if [ -f "$DEMO_DIR/pm-project/docs/PROJECT_CHARTER.md" ]; then
        echo -e "  ${GREEN}✓${NC} Project Charter"
    fi
    if [ -f "$DEMO_DIR/pm-project/docs/TASK_BOARD.md" ]; then
        echo -e "  ${GREEN}✓${NC} Task Board"
    fi
    if [ -f "$DEMO_DIR/pm-project/backend/Dockerfile" ]; then
        echo -e "  ${GREEN}✓${NC} Backend Infrastructure"
    fi
    if [ -f "$DEMO_DIR/pm-project/database/schema.sql" ]; then
        echo -e "  ${GREEN}✓${NC} Database Design"
    fi
    if [ -f "$DEMO_DIR/pm-project/backend/main.py" ]; then
        echo -e "  ${GREEN}✓${NC} API Implementation"
    fi
    if [ -f "$DEMO_DIR/pm-project/frontend/package.json" ]; then
        echo -e "  ${GREEN}✓${NC} Frontend Setup"
    fi
    if [ -f "$DEMO_DIR/pm-project/docs/EXECUTIVE_SUMMARY.md" ]; then
        echo -e "  ${GREEN}✓${NC} Executive Summary"
    fi
    echo ""
    echo -e "${YELLOW}PM Reports:${NC}"
    echo -e "${GREEN}1. View Project Charter:${NC}"
    echo -e "   cat $DEMO_DIR/pm-project/docs/PROJECT_CHARTER.md"
    echo -e "${GREEN}2. View Executive Summary:${NC}"
    echo -e "   cat $DEMO_DIR/pm-project/docs/EXECUTIVE_SUMMARY.md"
    echo -e "${GREEN}3. View Task Board:${NC}"
    echo -e "   cat $DEMO_DIR/pm-project/docs/TASK_BOARD.md"
}

# Main execution
main() {
    clear
    check_prerequisites
    setup_demo
    
    # Confirmation
    echo -e "${YELLOW}This demo will:${NC}"
    echo -e "  • Start a PM agent and 4 development agents"
    echo -e "  • PM will create a project plan for an e-commerce platform"
    echo -e "  • PM will delegate tasks to team members"
    echo -e "  • Team will execute tasks based on PM instructions"
    echo -e "  • PM will monitor progress and generate reports"
    echo -e "  • Take approximately 3-6 minutes"
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