#!/bin/bash
# Claude Conductor Deployment Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DEPLOYMENT_TYPE="local"
AGENTS=3
CONFIG_FILE=""
BUILD_IMAGE=false
DETACHED=false

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

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Show usage information
show_usage() {
    cat << EOF
Claude Conductor Deployment Script

Usage: $0 [options]

Options:
  -t, --type TYPE        Deployment type: local, docker, k8s (default: local)
  -a, --agents NUM       Number of agents (default: 3)
  -c, --config FILE      Configuration file path
  -b, --build            Build container image before deployment
  -d, --detached         Run in detached mode (for docker/k8s)
  -h, --help             Show this help message

Deployment Types:
  local     - Run directly on host with Python
  docker    - Deploy using Docker Compose
  k8s       - Deploy to Kubernetes cluster

Examples:
  $0 --type local --agents 5
  $0 --type docker --build --detached
  $0 --type k8s --config config/production.yaml

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -t|--type)
                DEPLOYMENT_TYPE="$2"
                shift 2
                ;;
            -a|--agents)
                AGENTS="$2"
                shift 2
                ;;
            -c|--config)
                CONFIG_FILE="$2"
                shift 2
                ;;
            -b|--build)
                BUILD_IMAGE=true
                shift
                ;;
            -d|--detached)
                DETACHED=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# Validate deployment type
validate_deployment_type() {
    case $DEPLOYMENT_TYPE in
        local|docker|k8s)
            print_status "Deployment type: $DEPLOYMENT_TYPE"
            ;;
        *)
            print_error "Invalid deployment type: $DEPLOYMENT_TYPE"
            print_error "Valid types: local, docker, k8s"
            exit 1
            ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    case $DEPLOYMENT_TYPE in
        local)
            if ! command -v python3 &> /dev/null; then
                print_error "Python 3 not found"
                exit 1
            fi
            
            if [ ! -d "venv" ]; then
                print_warning "Virtual environment not found. Run scripts/setup.sh first."
                exit 1
            fi
            ;;
        docker)
            if ! command -v docker &> /dev/null; then
                print_error "Docker not found"
                exit 1
            fi
            
            if ! command -v docker-compose &> /dev/null; then
                print_error "Docker Compose not found"
                exit 1
            fi
            ;;
        k8s)
            if ! command -v kubectl &> /dev/null; then
                print_error "kubectl not found"
                exit 1
            fi
            
            # Check if kubectl can connect to cluster
            if ! kubectl cluster-info &> /dev/null; then
                print_error "Cannot connect to Kubernetes cluster"
                exit 1
            fi
            ;;
    esac
    
    print_status "Prerequisites check passed"
}

# Build container image if requested
build_image() {
    if [ "$BUILD_IMAGE" = true ]; then
        print_status "Building container image..."
        
        if [ "$DEPLOYMENT_TYPE" = "docker" ]; then
            docker build -f containers/Dockerfile -t claude-conductor:latest .
        elif [ "$DEPLOYMENT_TYPE" = "k8s" ]; then
            docker build -f containers/Dockerfile -t claude-conductor:latest .
            # Tag for registry if needed
            # docker tag claude-conductor:latest your-registry/claude-conductor:latest
            # docker push your-registry/claude-conductor:latest
        fi
        
        print_status "Container image built"
    fi
}

# Deploy locally
deploy_local() {
    print_header "Local Deployment"
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Build config arguments
    CONFIG_ARGS=""
    if [ -n "$CONFIG_FILE" ]; then
        CONFIG_ARGS="--config $CONFIG_FILE"
    fi
    
    # Start orchestrator
    print_status "Starting orchestrator with $AGENTS agents..."
    
    if [ "$DETACHED" = true ]; then
        nohup python -m conductor.orchestrator --agents $AGENTS $CONFIG_ARGS > logs/orchestrator.log 2>&1 &
        echo $! > logs/orchestrator.pid
        print_status "Orchestrator started in background (PID: $(cat logs/orchestrator.pid))"
        print_status "Logs: logs/orchestrator.log"
    else
        python -m conductor.orchestrator --agents $AGENTS $CONFIG_ARGS
    fi
}

# Deploy with Docker
deploy_docker() {
    print_header "Docker Deployment"
    
    cd containers/
    
    # Set environment variables for docker-compose
    export CLAUDE_AGENTS=$AGENTS
    
    if [ "$DETACHED" = true ]; then
        print_status "Starting services in detached mode..."
        docker-compose up -d
        print_status "Services started. Use 'docker-compose logs' to view logs."
        print_status "Stop with: docker-compose down"
    else
        print_status "Starting services..."
        docker-compose up
    fi
}

# Deploy to Kubernetes
deploy_k8s() {
    print_header "Kubernetes Deployment"
    
    # Create namespace if it doesn't exist
    kubectl create namespace claude-conductor --dry-run=client -o yaml | kubectl apply -f -
    
    # Generate Kubernetes manifests
    generate_k8s_manifests
    
    # Apply manifests
    print_status "Applying Kubernetes manifests..."
    kubectl apply -f k8s/ -n claude-conductor
    
    # Wait for deployment
    print_status "Waiting for deployment to be ready..."
    kubectl wait --for=condition=available --timeout=300s deployment/claude-orchestrator -n claude-conductor
    
    # Show status
    kubectl get pods -n claude-conductor
    
    print_status "Kubernetes deployment completed"
}

# Generate Kubernetes manifests
generate_k8s_manifests() {
    mkdir -p k8s/
    
    # Orchestrator deployment
    cat > k8s/orchestrator.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: claude-orchestrator
  labels:
    app: claude-orchestrator
spec:
  replicas: 1
  selector:
    matchLabels:
      app: claude-orchestrator
  template:
    metadata:
      labels:
        app: claude-orchestrator
    spec:
      containers:
      - name: orchestrator
        image: claude-conductor:latest
        command: ["python", "-m", "conductor.orchestrator"]
        args: ["--agents", "$AGENTS"]
        ports:
        - containerPort: 8080
        env:
        - name: AGENT_ID
          value: "orchestrator"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: claude-orchestrator-service
spec:
  selector:
    app: claude-orchestrator
  ports:
  - protocol: TCP
    port: 8080
    targetPort: 8080
  type: ClusterIP
EOF

    # Agent deployment
    cat > k8s/agents.yaml << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: claude-agents
  labels:
    app: claude-agent
spec:
  replicas: $AGENTS
  selector:
    matchLabels:
      app: claude-agent
  template:
    metadata:
      labels:
        app: claude-agent
    spec:
      containers:
      - name: agent
        image: claude-conductor:latest
        env:
        - name: AGENT_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
EOF
    
    print_status "Kubernetes manifests generated in k8s/"
}

# Cleanup function
cleanup() {
    print_header "Cleanup"
    
    case $DEPLOYMENT_TYPE in
        local)
            if [ -f "logs/orchestrator.pid" ]; then
                PID=$(cat logs/orchestrator.pid)
                if ps -p $PID > /dev/null; then
                    print_status "Stopping orchestrator (PID: $PID)..."
                    kill $PID
                    rm logs/orchestrator.pid
                fi
            fi
            ;;
        docker)
            cd containers/
            print_status "Stopping Docker services..."
            docker-compose down
            ;;
        k8s)
            print_status "Deleting Kubernetes resources..."
            kubectl delete namespace claude-conductor
            ;;
    esac
    
    print_status "Cleanup completed"
}

# Status check
check_status() {
    print_header "Status Check"
    
    case $DEPLOYMENT_TYPE in
        local)
            if [ -f "logs/orchestrator.pid" ]; then
                PID=$(cat logs/orchestrator.pid)
                if ps -p $PID > /dev/null; then
                    print_status "Orchestrator is running (PID: $PID)"
                else
                    print_warning "Orchestrator PID file exists but process not running"
                fi
            else
                print_warning "Orchestrator not running"
            fi
            ;;
        docker)
            cd containers/
            docker-compose ps
            ;;
        k8s)
            kubectl get pods -n claude-conductor
            ;;
    esac
}

# Main deployment function
main() {
    print_header "Claude Conductor Deployment"
    
    # Handle special commands
    case ${1:-} in
        cleanup)
            cleanup
            exit 0
            ;;
        status)
            check_status
            exit 0
            ;;
    esac
    
    validate_deployment_type
    check_prerequisites
    build_image
    
    case $DEPLOYMENT_TYPE in
        local)
            deploy_local
            ;;
        docker)
            deploy_docker
            ;;
        k8s)
            deploy_k8s
            ;;
    esac
    
    print_status "Deployment completed successfully!"
}

# Handle special cases
if [ "$1" = "cleanup" ] || [ "$1" = "status" ]; then
    main "$@"
else
    parse_args "$@"
    main
fi