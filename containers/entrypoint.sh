#!/bin/bash
set -e

# Claude Conductor Container Entrypoint Script

echo "Starting Claude Conductor..."

# Set default environment variables
export CONDUCTOR_MODE=${CONDUCTOR_MODE:-"production"}
export CONDUCTOR_LOG_LEVEL=${CONDUCTOR_LOG_LEVEL:-"INFO"}
export CONDUCTOR_CONFIG=${CONDUCTOR_CONFIG:-"/app/config/config.yaml"}
export WORKSPACE_DIR=${WORKSPACE_DIR:-"/workspace"}
export CONDUCTOR_DASHBOARD_PORT=${CONDUCTOR_DASHBOARD_PORT:-"8080"}

# Create necessary directories
mkdir -p "$WORKSPACE_DIR"
mkdir -p /var/log/conductor
mkdir -p /home/claude/.conductor

# Set proper permissions
chown -R claude:claude "$WORKSPACE_DIR" /var/log/conductor /home/claude/.conductor 2>/dev/null || true

# Git configuration for container
if [ ! -f ~/.gitconfig ]; then
    git config --global user.name "Claude Conductor"
    git config --global user.email "conductor@claude-conductor.local"
    git config --global init.defaultBranch main
    git config --global safe.directory '*'
fi

# Function to handle graceful shutdown
cleanup() {
    echo "Received shutdown signal, stopping services..."
    if [ -f /var/run/supervisord.pid ]; then
        supervisorctl stop all
        supervisord ctl shutdown
    fi
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Determine startup mode
case "$1" in
    "orchestrator")
        echo "Starting in orchestrator mode..."
        exec python -m conductor.orchestrator --config "$CONDUCTOR_CONFIG"
        ;;
    "agent")
        echo "Starting in agent mode..."
        AGENT_ID=${AGENT_ID:-"agent_$(date +%s)"}
        export AGENT_ID
        exec python -m conductor.agent --agent-id "$AGENT_ID"
        ;;
    "dashboard")
        echo "Starting dashboard only..."
        exec python /app/web/dashboard.py --port "$CONDUCTOR_DASHBOARD_PORT" --no-browser
        ;;
    "full"|"")
        echo "Starting full system with supervisor..."
        # Create supervisor configuration from template
        if [ ! -f /etc/supervisor/conf.d/conductor.conf ]; then
            cp /app/containers/supervisor.conf /etc/supervisor/conf.d/conductor.conf
        fi
        
        # Start supervisor in foreground
        exec supervisord -c /etc/supervisor/supervisord.conf
        ;;
    "dev"|"development")
        echo "Starting in development mode..."
        export CONDUCTOR_MODE="development"
        export CONDUCTOR_LOG_LEVEL="DEBUG"
        
        # Start with debug features
        exec python -m conductor.orchestrator --config "$CONDUCTOR_CONFIG" --debug
        ;;
    "test")
        echo "Running tests..."
        cd /app
        exec pytest tests/ -v
        ;;
    "bash"|"shell")
        echo "Starting interactive shell..."
        exec /bin/bash
        ;;
    "claude-code")
        echo "Starting Claude Code CLI..."
        shift  # Remove 'claude-code' from arguments
        if command -v claude-code > /dev/null; then
            exec claude-code "$@"
        else
            echo "Error: Claude Code CLI not found"
            exit 1
        fi
        ;;
    *)
        echo "Starting custom command: $*"
        exec "$@"
        ;;
esac