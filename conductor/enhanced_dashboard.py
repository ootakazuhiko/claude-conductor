#!/usr/bin/env python3
"""
Enhanced Dashboard with Comprehensive Performance Monitoring Views

This module extends the existing dashboard with comprehensive performance
monitoring views, real-time metrics, and advanced visualization capabilities.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

try:
    from fastapi import FastAPI, WebSocket, Request, Depends, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from .metrics import get_metrics_collector
from .monitoring import get_tracing_middleware, generate_monitoring_report
from .metrics_service import MetricsService
from .monitored_orchestrator import MonitoredOrchestrator
from .monitored_agent import MonitoredAgent

logger = logging.getLogger(__name__)


class EnhancedDashboardData:
    """Enhanced data store for dashboard with comprehensive metrics"""
    
    def __init__(self):
        self.orchestrator: Optional[MonitoredOrchestrator] = None
        self.metrics_collector = get_metrics_collector()
        self.tracing = get_tracing_middleware()
        self.metrics_service: Optional[MetricsService] = None
        
        # Dashboard state
        self.stats_history = []
        self.max_history = 1000
        self.last_update = time.time()
        
        # Performance tracking
        self.real_time_metrics = {
            'cpu_usage': [],
            'memory_usage': [],
            'task_throughput': [],
            'error_rates': [],
            'response_times': []
        }
        self.max_real_time_points = 500
        
        # Alert system
        self.active_alerts = []
        self.alert_thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 85.0,
            'error_rate': 10.0,
            'response_time': 5000.0,  # milliseconds
            'queue_backlog': 100
        }
    
    def update_comprehensive_stats(self):
        """Update comprehensive statistics from all sources"""
        if not self.orchestrator:
            return
        
        try:
            # Get comprehensive performance report
            performance_report = self.orchestrator.get_comprehensive_performance_report()
            
            # Update stats history
            current_stats = {
                'timestamp': time.time(),
                'performance_report': performance_report,
                'metrics_summary': self.metrics_collector.get_metrics_summary(),
                'tracing_summary': self.tracing.get_trace_summary(),
                'agent_performance': self._get_agent_performance_summaries(),
                'system_health': self._calculate_system_health(),
                'alerts': self._check_alert_conditions(performance_report)
            }
            
            self.stats_history.append(current_stats)
            if len(self.stats_history) > self.max_history:
                self.stats_history.pop(0)
            
            # Update real-time metrics
            self._update_real_time_metrics(current_stats)
            
            self.last_update = time.time()
            
        except Exception as e:
            logger.error(f"Error updating comprehensive stats: {e}")
    
    def _get_agent_performance_summaries(self) -> List[Dict[str, Any]]:
        """Get performance summaries for all agents"""
        if not self.orchestrator or not hasattr(self.orchestrator, 'agents'):
            return []
        
        summaries = []
        for agent_id, agent in self.orchestrator.agents.items():
            if isinstance(agent, MonitoredAgent):
                summary = agent.get_agent_performance_summary()
                summaries.append(summary)
            else:
                # Fallback for non-monitored agents
                summaries.append({
                    'agent_id': agent_id,
                    'basic_info': {
                        'is_running': getattr(agent, 'is_running', False),
                        'health_failures': getattr(agent, 'health_check_failed', 0)
                    }
                })
        
        return summaries
    
    def _calculate_system_health(self) -> Dict[str, Any]:
        """Calculate overall system health score"""
        try:
            metrics_summary = self.metrics_collector.get_metrics_summary()
            
            # Calculate component health scores (0-100)
            task_health = 100.0
            if metrics_summary['task_metrics']['total'] > 0:
                success_rate = (
                    metrics_summary['task_metrics']['by_status'].get('success', 0) /
                    metrics_summary['task_metrics']['total']
                )
                task_health = success_rate * 100
            
            agent_health = 100.0
            if metrics_summary['agent_metrics']['total_agents'] > 0:
                active_ratio = (
                    metrics_summary['agent_metrics']['active_agents'] /
                    metrics_summary['agent_metrics']['total_agents']
                )
                agent_health = active_ratio * 100
            
            error_health = 100.0
            if metrics_summary['error_metrics']['total_errors'] > 0:
                # Deduct points based on error count (simplified)
                error_penalty = min(50, metrics_summary['error_metrics']['total_errors'] * 2)
                error_health = max(0, 100 - error_penalty)
            
            # Overall health is weighted average
            overall_health = (task_health * 0.4 + agent_health * 0.3 + error_health * 0.3)
            
            return {
                'overall_score': round(overall_health, 1),
                'task_health': round(task_health, 1),
                'agent_health': round(agent_health, 1),
                'error_health': round(error_health, 1),
                'status': self._get_health_status(overall_health),
                'last_calculated': time.time()
            }
            
        except Exception as e:
            logger.error(f"Error calculating system health: {e}")
            return {
                'overall_score': 0.0,
                'status': 'unknown',
                'error': str(e),
                'last_calculated': time.time()
            }
    
    def _get_health_status(self, score: float) -> str:
        """Get health status based on score"""
        if score >= 90:
            return 'excellent'
        elif score >= 75:
            return 'good'
        elif score >= 50:
            return 'fair'
        elif score >= 25:
            return 'poor'
        else:
            return 'critical'
    
    def _check_alert_conditions(self, performance_report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for alert conditions and update active alerts"""
        alerts = []
        current_time = time.time()
        
        try:
            # CPU usage alert
            system_stats = performance_report.get('detailed_statistics', {}).get('resource_usage_trend', [])
            if system_stats:
                latest_cpu = system_stats[-1].get('cpu_percent', 0)
                if latest_cpu > self.alert_thresholds['cpu_usage']:
                    alerts.append({
                        'id': 'high_cpu_usage',
                        'severity': 'warning',
                        'title': 'High CPU Usage',
                        'message': f'CPU usage is {latest_cpu:.1f}%',
                        'timestamp': current_time,
                        'value': latest_cpu,
                        'threshold': self.alert_thresholds['cpu_usage']
                    })
            
            # Memory usage alert
            if system_stats:
                latest_memory = system_stats[-1].get('memory_percent', 0)
                if latest_memory > self.alert_thresholds['memory_usage']:
                    alerts.append({
                        'id': 'high_memory_usage',
                        'severity': 'warning',
                        'title': 'High Memory Usage',
                        'message': f'Memory usage is {latest_memory:.1f}%',
                        'timestamp': current_time,
                        'value': latest_memory,
                        'threshold': self.alert_thresholds['memory_usage']
                    })
            
            # Queue backlog alert
            queue_metrics = performance_report.get('queue_metrics', {})
            queue_length = queue_metrics.get('queued_tasks', 0)
            if queue_length > self.alert_thresholds['queue_backlog']:
                alerts.append({
                    'id': 'high_queue_backlog',
                    'severity': 'warning',
                    'title': 'High Queue Backlog',
                    'message': f'Queue has {queue_length} pending tasks',
                    'timestamp': current_time,
                    'value': queue_length,
                    'threshold': self.alert_thresholds['queue_backlog']
                })
            
            # Error rate alert
            base_stats = performance_report.get('base_statistics', {})
            total_tasks = base_stats.get('tasks_completed', 0) + base_stats.get('tasks_failed', 0)
            if total_tasks > 0:
                error_rate = (base_stats.get('tasks_failed', 0) / total_tasks) * 100
                if error_rate > self.alert_thresholds['error_rate']:
                    alerts.append({
                        'id': 'high_error_rate',
                        'severity': 'error',
                        'title': 'High Error Rate',
                        'message': f'Error rate is {error_rate:.1f}%',
                        'timestamp': current_time,
                        'value': error_rate,
                        'threshold': self.alert_thresholds['error_rate']
                    })
            
            # Update active alerts
            self.active_alerts = alerts
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking alert conditions: {e}")
            return []
    
    def _update_real_time_metrics(self, current_stats: Dict[str, Any]):
        """Update real-time metrics for visualization"""
        try:
            timestamp = current_stats['timestamp']
            performance_report = current_stats['performance_report']
            
            # CPU usage
            system_stats = performance_report.get('detailed_statistics', {}).get('resource_usage_trend', [])
            if system_stats:
                latest_cpu = system_stats[-1].get('cpu_percent', 0)
                self.real_time_metrics['cpu_usage'].append({
                    'timestamp': timestamp,
                    'value': latest_cpu
                })
            
            # Memory usage
            if system_stats:
                latest_memory = system_stats[-1].get('memory_percent', 0)
                self.real_time_metrics['memory_usage'].append({
                    'timestamp': timestamp,
                    'value': latest_memory
                })
            
            # Task throughput
            queue_metrics = performance_report.get('queue_metrics', {})
            throughput = queue_metrics.get('throughput_per_minute', 0)
            self.real_time_metrics['task_throughput'].append({
                'timestamp': timestamp,
                'value': throughput
            })
            
            # Error rate
            base_stats = performance_report.get('base_statistics', {})
            total_tasks = base_stats.get('tasks_completed', 0) + base_stats.get('tasks_failed', 0)
            error_rate = 0
            if total_tasks > 0:
                error_rate = (base_stats.get('tasks_failed', 0) / total_tasks) * 100
            self.real_time_metrics['error_rates'].append({
                'timestamp': timestamp,
                'value': error_rate
            })
            
            # Response times (average task execution time)
            avg_exec_time = base_stats.get('avg_execution_time', 0) * 1000  # Convert to milliseconds
            self.real_time_metrics['response_times'].append({
                'timestamp': timestamp,
                'value': avg_exec_time
            })
            
            # Trim old data points
            for metric_name in self.real_time_metrics:
                if len(self.real_time_metrics[metric_name]) > self.max_real_time_points:
                    self.real_time_metrics[metric_name] = self.real_time_metrics[metric_name][-self.max_real_time_points:]
                    
        except Exception as e:
            logger.error(f"Error updating real-time metrics: {e}")
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data"""
        if not self.stats_history:
            return {
                'timestamp': time.time(),
                'error': 'No data available',
                'stats': {},
                'real_time_metrics': {},
                'alerts': [],
                'system_health': {'overall_score': 0, 'status': 'unknown'}
            }
        
        latest = self.stats_history[-1]
        
        return {
            'timestamp': latest['timestamp'],
            'performance_report': latest['performance_report'],
            'metrics_summary': latest['metrics_summary'],
            'tracing_summary': latest['tracing_summary'],
            'agent_performance': latest['agent_performance'],
            'system_health': latest['system_health'],
            'alerts': latest['alerts'],
            'real_time_metrics': self.real_time_metrics,
            'stats_history': self.stats_history[-100:],  # Last 100 data points
            'last_update': self.last_update
        }


# Global enhanced dashboard data
enhanced_dashboard_data = EnhancedDashboardData()


def create_enhanced_dashboard_app() -> FastAPI:
    """Create enhanced FastAPI dashboard application"""
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI is required for enhanced dashboard")
    
    app = FastAPI(
        title="Claude Conductor Enhanced Dashboard",
        description="Comprehensive performance monitoring dashboard",
        version="2.0.0"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Setup static files and templates
    web_dir = Path(__file__).parent.parent / "web"
    if (web_dir / "static").exists():
        app.mount("/static", StaticFiles(directory=web_dir / "static"), name="static")
    
    templates = Jinja2Templates(directory=web_dir / "templates")
    
    @app.get("/", response_class=HTMLResponse)
    async def enhanced_dashboard_home(request: Request):
        """Enhanced dashboard home page"""
        return HTMLResponse(content=generate_enhanced_dashboard_html())
    
    @app.get("/api/v1/dashboard/data")
    async def get_dashboard_data():
        """Get comprehensive dashboard data"""
        try:
            data = enhanced_dashboard_data.get_dashboard_data()
            return JSONResponse(content=data)
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v1/dashboard/health")
    async def get_system_health():
        """Get system health information"""
        try:
            if enhanced_dashboard_data.stats_history:
                latest = enhanced_dashboard_data.stats_history[-1]
                return JSONResponse(content=latest['system_health'])
            else:
                return JSONResponse(content={'overall_score': 0, 'status': 'unknown'})
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v1/dashboard/alerts")
    async def get_active_alerts():
        """Get active alerts"""
        try:
            return JSONResponse(content={
                'alerts': enhanced_dashboard_data.active_alerts,
                'alert_count': len(enhanced_dashboard_data.active_alerts),
                'thresholds': enhanced_dashboard_data.alert_thresholds
            })
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v1/dashboard/metrics/real-time")
    async def get_real_time_metrics(
        metric_name: Optional[str] = Query(None, description="Specific metric name"),
        time_range_minutes: int = Query(60, ge=1, le=1440, description="Time range in minutes")
    ):
        """Get real-time metrics data"""
        try:
            cutoff_time = time.time() - (time_range_minutes * 60)
            
            if metric_name and metric_name in enhanced_dashboard_data.real_time_metrics:
                filtered_data = [
                    point for point in enhanced_dashboard_data.real_time_metrics[metric_name]
                    if point['timestamp'] >= cutoff_time
                ]
                return JSONResponse(content={metric_name: filtered_data})
            else:
                # Return all metrics
                filtered_metrics = {}
                for name, data in enhanced_dashboard_data.real_time_metrics.items():
                    filtered_metrics[name] = [
                        point for point in data
                        if point['timestamp'] >= cutoff_time
                    ]
                return JSONResponse(content=filtered_metrics)
                
        except Exception as e:
            logger.error(f"Error getting real-time metrics: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v1/dashboard/agents/performance")
    async def get_agent_performance():
        """Get detailed agent performance data"""
        try:
            if enhanced_dashboard_data.stats_history:
                latest = enhanced_dashboard_data.stats_history[-1]
                return JSONResponse(content=latest['agent_performance'])
            else:
                return JSONResponse(content=[])
        except Exception as e:
            logger.error(f"Error getting agent performance: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/v1/dashboard/trace/{trace_id}")
    async def get_trace_details(trace_id: str):
        """Get detailed trace information"""
        try:
            # Get trace from tracing middleware
            tracing = get_tracing_middleware()
            
            # Look in active traces first
            if trace_id in tracing.active_traces:
                trace = tracing.active_traces[trace_id]
                return JSONResponse(content={
                    'trace': asdict(trace),
                    'status': 'active'
                })
            
            # Look in completed traces
            for trace in tracing.completed_traces:
                if trace.trace_id == trace_id:
                    return JSONResponse(content={
                        'trace': asdict(trace),
                        'status': 'completed'
                    })
            
            raise HTTPException(status_code=404, detail="Trace not found")
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting trace details: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.websocket("/ws/dashboard")
    async def websocket_dashboard_updates(websocket: WebSocket):
        """WebSocket for real-time dashboard updates"""
        await websocket.accept()
        
        try:
            while True:
                # Update dashboard data
                enhanced_dashboard_data.update_comprehensive_stats()
                
                # Send current data
                data = enhanced_dashboard_data.get_dashboard_data()
                data['server_time'] = datetime.now().isoformat()
                
                await websocket.send_text(json.dumps(data, default=str))
                
                # Wait before next update
                await asyncio.sleep(5)  # Update every 5 seconds
                
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    return app


def generate_enhanced_dashboard_html() -> str:
    """Generate enhanced dashboard HTML with comprehensive monitoring views"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Conductor - Enhanced Performance Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            background: #f5f7fa; 
            color: #333;
        }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            padding: 20px; 
            text-align: center; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header h1 { margin-bottom: 5px; }
        .header .subtitle { opacity: 0.9; font-size: 14px; }
        
        .dashboard-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
            gap: 20px; 
            padding: 20px; 
            max-width: 1400px; 
            margin: 0 auto; 
        }
        
        .card { 
            background: white; 
            border-radius: 12px; 
            padding: 20px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.08); 
            transition: transform 0.2s ease;
        }
        .card:hover { transform: translateY(-2px); }
        
        .card-header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            margin-bottom: 15px; 
            padding-bottom: 10px; 
            border-bottom: 2px solid #f0f0f0;
        }
        .card-title { font-size: 18px; font-weight: 600; color: #2c3e50; }
        .card-subtitle { font-size: 12px; color: #7f8c8d; margin-top: 2px; }
        
        .metric-value { 
            font-size: 32px; 
            font-weight: 700; 
            margin: 10px 0; 
        }
        .metric-label { 
            font-size: 14px; 
            color: #7f8c8d; 
            text-transform: uppercase; 
            letter-spacing: 0.5px;
        }
        
        .health-score { text-align: center; }
        .health-circle { 
            width: 100px; 
            height: 100px; 
            border-radius: 50%; 
            margin: 0 auto 15px; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            font-size: 24px; 
            font-weight: bold; 
            color: white;
        }
        .health-excellent { background: linear-gradient(135deg, #2ecc71, #27ae60); }
        .health-good { background: linear-gradient(135deg, #3498db, #2980b9); }
        .health-fair { background: linear-gradient(135deg, #f39c12, #e67e22); }
        .health-poor { background: linear-gradient(135deg, #e74c3c, #c0392b); }
        .health-critical { background: linear-gradient(135deg, #8e44ad, #9b59b6); }
        
        .alert { 
            padding: 12px; 
            border-radius: 8px; 
            margin: 8px 0; 
            border-left: 4px solid;
        }
        .alert-warning { background: #fff3cd; border-color: #ffc107; color: #856404; }
        .alert-error { background: #f8d7da; border-color: #dc3545; color: #721c24; }
        .alert-info { background: #d1ecf1; border-color: #17a2b8; color: #0c5460; }
        
        .chart-container { 
            position: relative; 
            height: 200px; 
            margin: 15px 0; 
        }
        
        .agent-list { max-height: 300px; overflow-y: auto; }
        .agent-item { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            padding: 10px; 
            border-bottom: 1px solid #ecf0f1; 
        }
        .agent-status { 
            padding: 4px 12px; 
            border-radius: 20px; 
            font-size: 12px; 
            font-weight: 600; 
        }
        .status-running { background: #d5f5d5; color: #2e7d32; }
        .status-stopped { background: #ffebee; color: #c62828; }
        
        .stats-grid { 
            display: grid; 
            grid-template-columns: repeat(2, 1fr); 
            gap: 15px; 
        }
        .stat-item { text-align: center; }
        
        .loading { 
            text-align: center; 
            padding: 50px; 
            color: #7f8c8d; 
        }
        
        .refresh-indicator { 
            position: fixed; 
            top: 20px; 
            right: 20px; 
            padding: 8px 16px; 
            background: rgba(46, 204, 113, 0.9); 
            color: white; 
            border-radius: 20px; 
            font-size: 12px; 
            opacity: 0; 
            transition: opacity 0.3s ease;
        }
        .refresh-indicator.show { opacity: 1; }
        
        @media (max-width: 768px) {
            .dashboard-grid { grid-template-columns: 1fr; padding: 10px; }
            .stats-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎭 Claude Conductor Enhanced Dashboard</h1>
        <div class="subtitle">Comprehensive Performance Monitoring & Analytics</div>
    </div>
    
    <div class="refresh-indicator" id="refreshIndicator">Data Updated</div>
    
    <div class="dashboard-grid">
        <!-- System Health Card -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">System Health</div>
                    <div class="card-subtitle">Overall system performance score</div>
                </div>
            </div>
            <div class="health-score">
                <div class="health-circle" id="healthCircle">--</div>
                <div class="metric-label" id="healthStatus">Calculating...</div>
            </div>
        </div>
        
        <!-- Real-time Metrics Card -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">Real-time Performance</div>
                    <div class="card-subtitle">Live system metrics</div>
                </div>
            </div>
            <div class="chart-container">
                <canvas id="performanceChart"></canvas>
            </div>
        </div>
        
        <!-- Task Statistics Card -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">Task Statistics</div>
                    <div class="card-subtitle">Task execution metrics</div>
                </div>
            </div>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="metric-value" id="tasksCompleted">--</div>
                    <div class="metric-label">Completed</div>
                </div>
                <div class="stat-item">
                    <div class="metric-value" id="tasksFailed">--</div>
                    <div class="metric-label">Failed</div>
                </div>
                <div class="stat-item">
                    <div class="metric-value" id="avgExecutionTime">--</div>
                    <div class="metric-label">Avg Time (s)</div>
                </div>
                <div class="stat-item">
                    <div class="metric-value" id="taskThroughput">--</div>
                    <div class="metric-label">Tasks/min</div>
                </div>
            </div>
        </div>
        
        <!-- Agent Performance Card -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">Agent Performance</div>
                    <div class="card-subtitle">Individual agent metrics</div>
                </div>
            </div>
            <div class="agent-list" id="agentList">
                <div class="loading">Loading agent data...</div>
            </div>
        </div>
        
        <!-- Active Alerts Card -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">Active Alerts</div>
                    <div class="card-subtitle">System warnings and notifications</div>
                </div>
            </div>
            <div id="alertsList">
                <div class="loading">Checking for alerts...</div>
            </div>
        </div>
        
        <!-- Resource Usage Card -->
        <div class="card">
            <div class="card-header">
                <div>
                    <div class="card-title">Resource Usage</div>
                    <div class="card-subtitle">CPU and memory utilization</div>
                </div>
            </div>
            <div class="chart-container">
                <canvas id="resourceChart"></canvas>
            </div>
        </div>
    </div>
    
    <script>
        // Global variables
        let performanceChart, resourceChart;
        let wsConnection;
        let lastUpdateTime = 0;
        
        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            initializeCharts();
            connectWebSocket();
            
            // Fallback: fetch data every 10 seconds if WebSocket fails
            setInterval(fetchDashboardData, 10000);
        });
        
        function initializeCharts() {
            // Performance chart
            const perfCtx = document.getElementById('performanceChart').getContext('2d');
            performanceChart = new Chart(perfCtx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'CPU Usage (%)',
                            data: [],
                            borderColor: '#3498db',
                            backgroundColor: 'rgba(52, 152, 219, 0.1)',
                            tension: 0.4
                        },
                        {
                            label: 'Tasks/min',
                            data: [],
                            borderColor: '#2ecc71',
                            backgroundColor: 'rgba(46, 204, 113, 0.1)',
                            tension: 0.4,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { intersect: false },
                    scales: {
                        y: { beginAtZero: true, max: 100 },
                        y1: { type: 'linear', display: true, position: 'right', beginAtZero: true }
                    }
                }
            });
            
            // Resource chart
            const resCtx = document.getElementById('resourceChart').getContext('2d');
            resourceChart = new Chart(resCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Used', 'Available'],
                    datasets: [{
                        data: [0, 100],
                        backgroundColor: ['#e74c3c', '#ecf0f1'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }
        
        function connectWebSocket() {
            const wsUrl = `ws://${window.location.host}/ws/dashboard`;
            wsConnection = new WebSocket(wsUrl);
            
            wsConnection.onopen = function() {
                console.log('WebSocket connected');
            };
            
            wsConnection.onmessage = function(event) {
                const data = JSON.parse(event.data);
                updateDashboard(data);
                showRefreshIndicator();
            };
            
            wsConnection.onclose = function() {
                console.log('WebSocket disconnected, attempting to reconnect...');
                setTimeout(connectWebSocket, 5000);
            };
            
            wsConnection.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
        }
        
        async function fetchDashboardData() {
            try {
                const response = await fetch('/api/v1/dashboard/data');
                const data = await response.json();
                updateDashboard(data);
            } catch (error) {
                console.error('Error fetching dashboard data:', error);
            }
        }
        
        function updateDashboard(data) {
            if (!data || data.error) {
                console.error('Invalid dashboard data:', data);
                return;
            }
            
            updateSystemHealth(data.system_health);
            updateTaskStatistics(data.performance_report);
            updateAgentPerformance(data.agent_performance);
            updateAlerts(data.alerts);
            updateCharts(data.real_time_metrics);
            
            lastUpdateTime = Date.now();
        }
        
        function updateSystemHealth(healthData) {
            if (!healthData) return;
            
            const healthCircle = document.getElementById('healthCircle');
            const healthStatus = document.getElementById('healthStatus');
            
            const score = healthData.overall_score || 0;
            const status = healthData.status || 'unknown';
            
            healthCircle.textContent = Math.round(score);
            healthStatus.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            
            // Update circle color based on health status
            healthCircle.className = 'health-circle health-' + status;
        }
        
        function updateTaskStatistics(performanceReport) {
            if (!performanceReport) return;
            
            const baseStats = performanceReport.base_statistics || {};
            const queueMetrics = performanceReport.queue_metrics || {};
            
            document.getElementById('tasksCompleted').textContent = baseStats.tasks_completed || 0;
            document.getElementById('tasksFailed').textContent = baseStats.tasks_failed || 0;
            document.getElementById('avgExecutionTime').textContent = 
                (baseStats.avg_execution_time || 0).toFixed(2);
            document.getElementById('taskThroughput').textContent = 
                (queueMetrics.throughput_per_minute || 0).toFixed(1);
        }
        
        function updateAgentPerformance(agentData) {
            const agentList = document.getElementById('agentList');
            
            if (!agentData || agentData.length === 0) {
                agentList.innerHTML = '<div class="loading">No agent data available</div>';
                return;
            }
            
            let html = '';
            agentData.forEach(agent => {
                const isRunning = agent.health_status?.is_running || false;
                const efficiency = agent.resource_efficiency_score || 0;
                
                html += `
                    <div class="agent-item">
                        <div>
                            <strong>${agent.agent_id}</strong>
                            <div style="font-size: 12px; color: #7f8c8d;">
                                Efficiency: ${(efficiency * 100).toFixed(1)}%
                            </div>
                        </div>
                        <span class="agent-status ${isRunning ? 'status-running' : 'status-stopped'}">
                            ${isRunning ? 'Running' : 'Stopped'}
                        </span>
                    </div>
                `;
            });
            
            agentList.innerHTML = html;
        }
        
        function updateAlerts(alerts) {
            const alertsList = document.getElementById('alertsList');
            
            if (!alerts || alerts.length === 0) {
                alertsList.innerHTML = '<div style="color: #2ecc71; text-align: center;">✓ No active alerts</div>';
                return;
            }
            
            let html = '';
            alerts.forEach(alert => {
                const alertClass = alert.severity === 'error' ? 'alert-error' : 
                                 alert.severity === 'warning' ? 'alert-warning' : 'alert-info';
                
                html += `
                    <div class="alert ${alertClass}">
                        <strong>${alert.title}</strong><br>
                        ${alert.message}
                    </div>
                `;
            });
            
            alertsList.innerHTML = html;
        }
        
        function updateCharts(realTimeMetrics) {
            if (!realTimeMetrics) return;
            
            // Update performance chart
            const cpuData = realTimeMetrics.cpu_usage || [];
            const throughputData = realTimeMetrics.task_throughput || [];
            
            if (cpuData.length > 0) {
                const labels = cpuData.map(point => 
                    new Date(point.timestamp * 1000).toLocaleTimeString()
                ).slice(-20); // Last 20 points
                
                performanceChart.data.labels = labels;
                performanceChart.data.datasets[0].data = cpuData.map(p => p.value).slice(-20);
                performanceChart.data.datasets[1].data = throughputData.map(p => p.value).slice(-20);
                performanceChart.update('none');
            }
            
            // Update resource chart (memory usage)
            const memoryData = realTimeMetrics.memory_usage || [];
            if (memoryData.length > 0) {
                const latestMemory = memoryData[memoryData.length - 1].value;
                resourceChart.data.datasets[0].data = [latestMemory, 100 - latestMemory];
                resourceChart.update('none');
            }
        }
        
        function showRefreshIndicator() {
            const indicator = document.getElementById('refreshIndicator');
            indicator.classList.add('show');
            setTimeout(() => {
                indicator.classList.remove('show');
            }, 1000);
        }
    </script>
</body>
</html>
"""


def run_enhanced_dashboard(orchestrator: Optional[MonitoredOrchestrator] = None,
                         metrics_service: Optional[MetricsService] = None,
                         port: int = 8080, open_browser: bool = True):
    """Run the enhanced dashboard"""
    if not FASTAPI_AVAILABLE:
        raise ImportError("FastAPI is required for enhanced dashboard")
    
    # Set orchestrator and metrics service
    enhanced_dashboard_data.orchestrator = orchestrator
    enhanced_dashboard_data.metrics_service = metrics_service
    
    # Create and run app
    app = create_enhanced_dashboard_app()
    
    if open_browser:
        import webbrowser
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "metrics-1", "content": "Create Prometheus metrics exporter module with comprehensive performance metrics", "status": "completed", "priority": "high"}, {"id": "metrics-2", "content": "Implement performance monitoring middleware for orchestrator and agents", "status": "completed", "priority": "high"}, {"id": "metrics-3", "content": "Add detailed task execution timing and resource utilization tracking", "status": "completed", "priority": "high"}, {"id": "metrics-4", "content": "Create metrics collection service with API endpoints", "status": "completed", "priority": "high"}, {"id": "metrics-5", "content": "Implement distributed tracing and correlation ID system", "status": "completed", "priority": "medium"}, {"id": "metrics-6", "content": "Add queue performance metrics and backlog tracking", "status": "completed", "priority": "medium"}, {"id": "metrics-7", "content": "Create comprehensive error categorization and pattern analysis", "status": "completed", "priority": "medium"}, {"id": "metrics-8", "content": "Integrate monitoring with existing dashboard and add new performance views", "status": "completed", "priority": "low"}]