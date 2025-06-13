#!/usr/bin/env python3
"""
Simple Web Dashboard for Claude Conductor
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

try:
    from fastapi import FastAPI, WebSocket, Request
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("FastAPI not available. Install with: pip install fastapi uvicorn jinja2")

# Fallback to simple HTTP server if FastAPI not available
import http.server
import socketserver
import threading
import webbrowser
from urllib.parse import urlparse

from conductor import Orchestrator, create_task


class DashboardData:
    """Shared data store for dashboard"""
    
    def __init__(self):
        self.orchestrator: Optional[Orchestrator] = None
        self.stats_history = []
        self.max_history = 100
        self.last_update = time.time()
    
    def update_stats(self):
        """Update statistics from orchestrator"""
        if not self.orchestrator:
            return
        
        stats = self.orchestrator.get_statistics()
        agent_status = self.orchestrator.get_agent_status()
        
        # Add timestamp
        stats['timestamp'] = time.time()
        stats['agents'] = agent_status
        
        # Add to history
        self.stats_history.append(stats)
        if len(self.stats_history) > self.max_history:
            self.stats_history.pop(0)
        
        self.last_update = time.time()
    
    def get_current_data(self) -> Dict[str, Any]:
        """Get current dashboard data"""
        if not self.stats_history:
            return {
                'stats': {'tasks_completed': 0, 'tasks_failed': 0, 'runtime': 0},
                'agents': {},
                'history': [],
                'last_update': self.last_update
            }
        
        latest = self.stats_history[-1]
        return {
            'stats': latest,
            'agents': latest.get('agents', {}),
            'history': self.stats_history[-20:],  # Last 20 data points
            'last_update': self.last_update
        }


# Global dashboard data
dashboard_data = DashboardData()


# FastAPI Dashboard (if available)
if FASTAPI_AVAILABLE:
    app = FastAPI(title="Claude Conductor Dashboard", version="1.0.0")
    
    # Setup static files and templates
    web_dir = Path(__file__).parent
    app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")
    templates = Jinja2Templates(directory=web_dir / "templates")
    
    @app.get("/", response_class=HTMLResponse)
    async def dashboard_home(request: Request):
        """Main dashboard page"""
        return templates.TemplateResponse("dashboard.html", {"request": request})
    
    @app.get("/api/status")
    async def get_status():
        """Get current system status"""
        return dashboard_data.get_current_data()
    
    @app.get("/api/agents")
    async def get_agents():
        """Get agent status"""
        if dashboard_data.orchestrator:
            return dashboard_data.orchestrator.get_agent_status()
        return {}
    
    @app.post("/api/task")
    async def submit_task(task_data: dict):
        """Submit a new task"""
        if not dashboard_data.orchestrator:
            return {"error": "Orchestrator not running"}
        
        try:
            task = create_task(
                task_type=task_data.get("task_type", "generic"),
                description=task_data.get("description", ""),
                files=task_data.get("files", []),
                priority=task_data.get("priority", 5)
            )
            
            result = dashboard_data.orchestrator.execute_task(task)
            return {"success": True, "task_id": result.task_id, "status": result.status}
        except Exception as e:
            return {"error": str(e)}
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """WebSocket for real-time updates"""
        await websocket.accept()
        
        try:
            while True:
                # Send current data
                data = dashboard_data.get_current_data()
                await websocket.send_text(json.dumps(data))
                
                # Wait for 2 seconds before next update
                await asyncio.sleep(2)
                
                # Update stats
                dashboard_data.update_stats()
                
        except Exception as e:
            print(f"WebSocket error: {e}")


# Simple HTML Dashboard (fallback)
def create_simple_dashboard():
    """Create a simple HTML dashboard"""
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Claude Conductor Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 15px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; color: #333; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .stat-item { text-align: center; padding: 15px; background: #e8f4f8; border-radius: 6px; }
        .stat-value { font-size: 2em; font-weight: bold; color: #2196F3; }
        .stat-label { color: #666; margin-top: 5px; }
        .agents { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }
        .agent { padding: 15px; background: #f0f0f0; border-radius: 6px; border-left: 4px solid #4CAF50; }
        .agent.offline { border-left-color: #f44336; }
        .status-running { color: #4CAF50; font-weight: bold; }
        .status-stopped { color: #f44336; font-weight: bold; }
        .task-form { background: #fff3cd; padding: 20px; border-radius: 6px; }
        .form-group { margin: 10px 0; }
        .form-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .form-group input, .form-group select, .form-group textarea { 
            width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; 
        }
        .btn { background: #2196F3; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #1976D2; }
        .refresh-btn { float: right; background: #4CAF50; }
        .log { background: #f8f9fa; padding: 15px; border-radius: 6px; font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎭 Claude Conductor Dashboard</h1>
            <p>Multi-Agent Orchestration System</p>
            <button class="btn refresh-btn" onclick="location.reload()">🔄 Refresh</button>
        </div>

        <div class="card">
            <h2>📊 System Statistics</h2>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-value" id="tasks-completed">-</div>
                    <div class="stat-label">Tasks Completed</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="tasks-failed">-</div>
                    <div class="stat-label">Tasks Failed</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="avg-time">-</div>
                    <div class="stat-label">Avg Time (s)</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value" id="runtime">-</div>
                    <div class="stat-label">Runtime (s)</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>🤖 Agent Status</h2>
            <div class="agents" id="agents-container">
                <div class="agent">
                    <h4>No agents running</h4>
                    <p>Start the orchestrator to see agent status</p>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>➕ Submit Task</h2>
            <div class="task-form">
                <div class="form-group">
                    <label>Task Type:</label>
                    <select id="task-type">
                        <option value="generic">Generic</option>
                        <option value="code_review">Code Review</option>
                        <option value="refactor">Refactor</option>
                        <option value="test_generation">Test Generation</option>
                        <option value="analysis">Analysis</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Description:</label>
                    <textarea id="task-description" placeholder="Describe what you want to accomplish..."></textarea>
                </div>
                <div class="form-group">
                    <label>Priority (1-10):</label>
                    <input type="number" id="task-priority" value="5" min="1" max="10">
                </div>
                <button class="btn" onclick="submitTask()">🚀 Submit Task</button>
            </div>
        </div>

        <div class="card">
            <h2>📝 Activity Log</h2>
            <div class="log" id="activity-log">
                Dashboard loaded. Connect to orchestrator to see real-time updates.
            </div>
        </div>
    </div>

    <script>
        // Mock data for demonstration
        let mockStats = {
            tasks_completed: Math.floor(Math.random() * 50),
            tasks_failed: Math.floor(Math.random() * 5),
            avg_execution_time: (Math.random() * 10).toFixed(2),
            runtime: (Math.random() * 3600).toFixed(0)
        };

        let mockAgents = {
            'agent_001': { running: true, current_task: null, health_check_failed: 0 },
            'agent_002': { running: true, current_task: 'task_123', health_check_failed: 0 },
            'agent_003': { running: false, current_task: null, health_check_failed: 2 }
        };

        function updateStats(stats) {
            document.getElementById('tasks-completed').textContent = stats.tasks_completed || 0;
            document.getElementById('tasks-failed').textContent = stats.tasks_failed || 0;
            document.getElementById('avg-time').textContent = stats.avg_execution_time || '0.00';
            document.getElementById('runtime').textContent = stats.runtime || '0';
        }

        function updateAgents(agents) {
            const container = document.getElementById('agents-container');
            container.innerHTML = '';

            if (Object.keys(agents).length === 0) {
                container.innerHTML = '<div class="agent"><h4>No agents running</h4><p>Start the orchestrator to see agent status</p></div>';
                return;
            }

            for (const [agentId, info] of Object.entries(agents)) {
                const agentEl = document.createElement('div');
                agentEl.className = 'agent' + (info.running ? '' : ' offline');
                agentEl.innerHTML = `
                    <h4>${agentId}</h4>
                    <p>Status: <span class="${info.running ? 'status-running' : 'status-stopped'}">${info.running ? 'Running' : 'Stopped'}</span></p>
                    <p>Current Task: ${info.current_task || 'None'}</p>
                    <p>Health Failures: ${info.health_check_failed || 0}</p>
                `;
                container.appendChild(agentEl);
            }
        }

        function logActivity(message) {
            const log = document.getElementById('activity-log');
            const timestamp = new Date().toLocaleTimeString();
            log.innerHTML += `\\n[${timestamp}] ${message}`;
            log.scrollTop = log.scrollHeight;
        }

        function submitTask() {
            const taskType = document.getElementById('task-type').value;
            const description = document.getElementById('task-description').value;
            const priority = document.getElementById('task-priority').value;

            if (!description.trim()) {
                alert('Please enter a task description');
                return;
            }

            // Mock task submission
            const taskId = 'task_' + Math.random().toString(36).substr(2, 9);
            logActivity(`Task submitted: ${taskType} - ${description} (Priority: ${priority})`);
            logActivity(`Task ${taskId} created and queued for execution`);
            
            // Simulate task completion after a few seconds
            setTimeout(() => {
                const success = Math.random() > 0.2; // 80% success rate
                logActivity(`Task ${taskId} ${success ? 'completed successfully' : 'failed'}`);
                
                // Update mock stats
                if (success) {
                    mockStats.tasks_completed++;
                } else {
                    mockStats.tasks_failed++;
                }
                updateStats(mockStats);
            }, 2000 + Math.random() * 3000);

            // Clear form
            document.getElementById('task-description').value = '';
        }

        // Initialize with mock data
        updateStats(mockStats);
        updateAgents(mockAgents);
        logActivity('Dashboard initialized with mock data');
        logActivity('To connect to real orchestrator, use the FastAPI version with: python web/dashboard.py');

        // Simulate some activity
        setInterval(() => {
            // Randomly update agent tasks
            const agents = Object.keys(mockAgents);
            const randomAgent = agents[Math.floor(Math.random() * agents.length)];
            const hasTask = Math.random() > 0.7;
            
            if (mockAgents[randomAgent].running) {
                mockAgents[randomAgent].current_task = hasTask ? `task_${Math.random().toString(36).substr(2, 6)}` : null;
                updateAgents(mockAgents);
            }
        }, 5000);
    </script>
</body>
</html>
"""
    return html_content


class SimpleDashboardServer:
    """Simple HTTP server for dashboard"""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.server = None
        self.thread = None
    
    def start(self):
        """Start the dashboard server"""
        html_content = create_simple_dashboard()
        
        class DashboardHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/' or self.path == '/dashboard':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(html_content.encode())
                else:
                    self.send_response(404)
                    self.end_headers()
        
        self.server = socketserver.TCPServer(("", self.port), DashboardHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        
        print(f"Dashboard server started at http://localhost:{self.port}")
        return f"http://localhost:{self.port}"
    
    def stop(self):
        """Stop the dashboard server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()


def run_dashboard(orchestrator: Optional[Orchestrator] = None, port: int = 8080, open_browser: bool = True):
    """Run the dashboard"""
    if orchestrator:
        dashboard_data.orchestrator = orchestrator
    
    if FASTAPI_AVAILABLE:
        print("Starting FastAPI dashboard...")
        if open_browser:
            threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    else:
        print("FastAPI not available, starting simple dashboard...")
        server = SimpleDashboardServer(port)
        url = server.start()
        
        if open_browser:
            webbrowser.open(url)
        
        try:
            print("Dashboard running. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping dashboard...")
            server.stop()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Conductor Web Dashboard")
    parser.add_argument("--port", type=int, default=8080, help="Port to run dashboard on")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    parser.add_argument("--with-orchestrator", action="store_true", help="Start with orchestrator")
    
    args = parser.parse_args()
    
    orchestrator = None
    if args.with_orchestrator:
        print("Starting orchestrator...")
        orchestrator = Orchestrator()
        orchestrator.config["num_agents"] = 2
        orchestrator.start()
    
    try:
        run_dashboard(orchestrator, args.port, not args.no_browser)
    finally:
        if orchestrator:
            print("Stopping orchestrator...")
            orchestrator.stop()