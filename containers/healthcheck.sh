#!/bin/bash
set -e

# Health check script for Claude Conductor container

# Check if supervisor is running
if ! pgrep supervisord > /dev/null; then
    echo "ERROR: supervisord is not running"
    exit 1
fi

# Check if orchestrator process is running
if ! supervisorctl status conductor-orchestrator | grep -q RUNNING; then
    echo "ERROR: conductor-orchestrator is not running"
    exit 1
fi

# Check if dashboard process is running
if ! supervisorctl status conductor-dashboard | grep -q RUNNING; then
    echo "ERROR: conductor-dashboard is not running"
    exit 1
fi

# Check if dashboard HTTP endpoint is responding
if ! curl -f -s http://localhost:8080/api/status > /dev/null; then
    echo "ERROR: dashboard HTTP endpoint is not responding"
    exit 1
fi

# Check workspace directory exists and is writable
if [ ! -d "/workspace" ] || [ ! -w "/workspace" ]; then
    echo "ERROR: workspace directory is not accessible"
    exit 1
fi

# Check log directory exists
if [ ! -d "/var/log/conductor" ]; then
    echo "ERROR: log directory does not exist"
    exit 1
fi

# All checks passed
echo "Health check passed: All services are running"
exit 0