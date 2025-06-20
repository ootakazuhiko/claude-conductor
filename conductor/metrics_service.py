#!/usr/bin/env python3
"""
Metrics Collection Service with HTTP API Endpoints

This module provides a comprehensive HTTP API service for metrics collection,
monitoring endpoints, and performance data access for Claude Conductor.
"""

import json
import time
import threading
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta
import logging
from dataclasses import asdict
import gzip
import io

try:
    from fastapi import FastAPI, HTTPException, Query, Path, Response, Request, Depends
    from fastapi.responses import JSONResponse, PlainTextResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    # Mock classes for when FastAPI is not available
    class FastAPI:
        def __init__(self, *args, **kwargs): pass
        def get(self, *args, **kwargs): return lambda f: f
        def post(self, *args, **kwargs): return lambda f: f
        def add_middleware(self, *args, **kwargs): pass
    
    class HTTPException(Exception): pass
    class JSONResponse: pass
    class PlainTextResponse: pass

try:
    import prometheus_client
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from .metrics import get_metrics_collector, MetricsCollector, start_prometheus_server
from .monitoring import get_tracing_middleware, generate_monitoring_report
from .utils import get_system_stats

logger = logging.getLogger(__name__)


class MetricsAPI:
    """HTTP API for metrics collection and access"""
    
    def __init__(self, metrics_collector: Optional[MetricsCollector] = None,
                 enable_authentication: bool = False):
        self.metrics_collector = metrics_collector or get_metrics_collector()
        self.tracing = get_tracing_middleware()
        self.enable_authentication = enable_authentication
        self.api_key = "claude-conductor-metrics"  # In production, use proper auth
        
        if FASTAPI_AVAILABLE:
            self.app = self._create_fastapi_app()
        else:
            self.app = None
            logger.warning("FastAPI not available, HTTP API disabled")
        
        self.server_thread: Optional[threading.Thread] = None
        self.running = False
    
    def _create_fastapi_app(self) -> FastAPI:
        """Create and configure FastAPI application"""
        app = FastAPI(
            title="Claude Conductor Metrics API",
            description="Performance metrics and monitoring API for Claude Conductor",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Add request timing middleware
        @app.middleware("http")
        async def add_process_time_header(request: Request, call_next):
            start_time = time.time()
            response = await call_next(request)
            process_time = time.time() - start_time
            
            # Record API request metrics
            self.metrics_collector.record_api_request(
                method=request.method,
                endpoint=str(request.url.path),
                status_code=response.status_code,
                duration=process_time
            )
            
            response.headers["X-Process-Time"] = str(process_time)
            return response
        
        # Define all API endpoints
        self._setup_api_endpoints(app)
        
        return app
    
    def _setup_api_endpoints(self, app: FastAPI):
        """Setup all API endpoints"""
        
        # Authentication dependency
        security = HTTPBearer(auto_error=False)
        
        def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
            if self.enable_authentication:
                if not credentials or credentials.credentials != self.api_key:
                    raise HTTPException(status_code=401, detail="Invalid API key")
            return True
        
        @app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "uptime": time.time() - self.metrics_collector.start_time,
                "version": "1.0.0"
            }
        
        @app.get("/metrics")
        async def prometheus_metrics():
            """Prometheus metrics endpoint"""
            if not PROMETHEUS_AVAILABLE:
                raise HTTPException(status_code=501, detail="Prometheus not available")
            
            metrics_data = self.metrics_collector.get_prometheus_metrics()
            return PlainTextResponse(
                content=metrics_data.decode('utf-8'),
                media_type="text/plain"
            )
        
        @app.get("/api/v1/metrics/summary")
        async def get_metrics_summary(authenticated: bool = Depends(verify_api_key)):
            """Get comprehensive metrics summary"""
            try:
                summary = self.metrics_collector.get_metrics_summary()
                return JSONResponse(content=summary)
            except Exception as e:
                logger.error(f"Error getting metrics summary: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/v1/metrics/tasks")
        async def get_task_metrics(
            status: Optional[str] = Query(None, description="Filter by task status"),
            task_type: Optional[str] = Query(None, description="Filter by task type"),
            limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
            authenticated: bool = Depends(verify_api_key)
        ):
            """Get task metrics with optional filtering"""
            try:
                all_tasks = list(self.metrics_collector.task_metrics.values())
                
                # Apply filters
                if status:
                    all_tasks = [t for t in all_tasks if t.status == status]
                if task_type:
                    all_tasks = [t for t in all_tasks if t.task_type == task_type]
                
                # Sort by start time (most recent first)
                all_tasks.sort(key=lambda t: t.start_time, reverse=True)
                
                # Apply limit
                tasks = all_tasks[:limit]
                
                return JSONResponse(content={
                    "tasks": [asdict(task) for task in tasks],
                    "total_count": len(all_tasks),
                    "returned_count": len(tasks),
                    "filters": {"status": status, "task_type": task_type}
                })
                
            except Exception as e:
                logger.error(f"Error getting task metrics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/v1/metrics/agents")
        async def get_agent_metrics(authenticated: bool = Depends(verify_api_key)):
            """Get agent performance metrics"""
            try:
                agent_states = dict(self.metrics_collector._agent_states)
                return JSONResponse(content={
                    "agents": agent_states,
                    "summary": {
                        "total_agents": len(agent_states),
                        "active_agents": len([a for a in agent_states.values() if a.get('is_running', False)]),
                        "agents_with_tasks": len([a for a in agent_states.values() if a.get('current_tasks', 0) > 0]),
                        "total_health_failures": sum(a.get('health_failures', 0) for a in agent_states.values())
                    }
                })
            except Exception as e:
                logger.error(f"Error getting agent metrics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/v1/metrics/system")
        async def get_system_metrics(authenticated: bool = Depends(verify_api_key)):
            """Get system resource metrics"""
            try:
                system_stats = get_system_stats()
                return JSONResponse(content=system_stats)
            except Exception as e:
                logger.error(f"Error getting system metrics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/v1/metrics/errors")
        async def get_error_metrics(
            limit: int = Query(50, ge=1, le=500, description="Maximum number of error types"),
            authenticated: bool = Depends(verify_api_key)
        ):
            """Get error pattern analysis"""
            try:
                error_patterns = dict(self.metrics_collector._error_patterns)
                
                # Sort by frequency
                sorted_errors = sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)
                
                return JSONResponse(content={
                    "error_patterns": sorted_errors[:limit],
                    "total_error_types": len(error_patterns),
                    "total_errors": sum(error_patterns.values()),
                    "top_errors": sorted_errors[:10]
                })
            except Exception as e:
                logger.error(f"Error getting error metrics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/v1/metrics/performance/snapshots")
        async def get_performance_snapshots(
            hours: int = Query(24, ge=1, le=168, description="Number of hours to look back"),
            limit: int = Query(100, ge=1, le=1000, description="Maximum number of snapshots"),
            authenticated: bool = Depends(verify_api_key)
        ):
            """Get performance snapshots"""
            try:
                cutoff_time = time.time() - (hours * 3600)
                snapshots = [
                    s for s in self.metrics_collector.performance_snapshots
                    if s.timestamp >= cutoff_time
                ]
                
                # Sort by timestamp (most recent first)
                snapshots.sort(key=lambda s: s.timestamp, reverse=True)
                
                return JSONResponse(content={
                    "snapshots": [asdict(snapshot) for snapshot in snapshots[:limit]],
                    "total_count": len(snapshots),
                    "time_range_hours": hours
                })
            except Exception as e:
                logger.error(f"Error getting performance snapshots: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/v1/metrics/traces")
        async def get_trace_data(
            active_only: bool = Query(False, description="Return only active traces"),
            limit: int = Query(100, ge=1, le=1000, description="Maximum number of traces"),
            authenticated: bool = Depends(verify_api_key)
        ):
            """Get distributed tracing data"""
            try:
                if active_only:
                    traces = list(self.tracing.active_traces.values())
                else:
                    traces = list(self.tracing.completed_traces)
                
                # Sort by start time (most recent first)
                traces.sort(key=lambda t: t.start_time, reverse=True)
                
                return JSONResponse(content={
                    "traces": [asdict(trace) for trace in traces[:limit]],
                    "total_count": len(traces),
                    "active_traces": len(self.tracing.active_traces),
                    "completed_traces": len(self.tracing.completed_traces),
                    "active_only": active_only
                })
            except Exception as e:
                logger.error(f"Error getting trace data: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/v1/metrics/queue")
        async def get_queue_metrics(authenticated: bool = Depends(verify_api_key)):
            """Get task queue performance metrics"""
            try:
                queue_metrics = dict(self.metrics_collector._queue_metrics)
                
                # Calculate queue statistics
                stats = {}
                for queue_type, timestamps in queue_metrics.items():
                    if timestamps:
                        recent_timestamps = [t for t in timestamps if time.time() - t < 3600]  # Last hour
                        stats[queue_type] = {
                            "total_entries": len(timestamps),
                            "recent_entries": len(recent_timestamps),
                            "entries_per_hour": len(recent_timestamps),
                            "latest_timestamp": max(timestamps) if timestamps else None
                        }
                
                return JSONResponse(content={
                    "queue_statistics": stats,
                    "summary": {
                        "total_queue_types": len(queue_metrics),
                        "total_entries": sum(len(timestamps) for timestamps in queue_metrics.values())
                    }
                })
            except Exception as e:
                logger.error(f"Error getting queue metrics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/v1/metrics/export")
        async def export_metrics(
            format: str = Query("json", enum=["json", "prometheus"], description="Export format"),
            compress: bool = Query(False, description="Compress response with gzip"),
            authenticated: bool = Depends(verify_api_key)
        ):
            """Export all metrics in various formats"""
            try:
                if format == "prometheus":
                    if not PROMETHEUS_AVAILABLE:
                        raise HTTPException(status_code=501, detail="Prometheus not available")
                    
                    content = self.metrics_collector.get_prometheus_metrics()
                    media_type = "text/plain"
                else:
                    # JSON format
                    export_data = {
                        "export_timestamp": datetime.now().isoformat(),
                        "metrics_summary": self.metrics_collector.get_metrics_summary(),
                        "task_metrics": [asdict(task) for task in self.metrics_collector.task_metrics.values()],
                        "agent_states": dict(self.metrics_collector._agent_states),
                        "error_patterns": dict(self.metrics_collector._error_patterns),
                        "performance_snapshots": [asdict(s) for s in self.metrics_collector.performance_snapshots],
                        "trace_summary": self.tracing.get_trace_summary(),
                        "system_stats": get_system_stats()
                    }
                    content = json.dumps(export_data, indent=2, default=str).encode('utf-8')
                    media_type = "application/json"
                
                if compress:
                    # Compress with gzip
                    buffer = io.BytesIO()
                    with gzip.GzipFile(fileobj=buffer, mode='wb') as gz_file:
                        gz_file.write(content)
                    content = buffer.getvalue()
                    
                    return Response(
                        content=content,
                        media_type=media_type,
                        headers={
                            "Content-Encoding": "gzip",
                            "Content-Disposition": f"attachment; filename=metrics_export_{int(time.time())}.{format}.gz"
                        }
                    )
                else:
                    return Response(
                        content=content,
                        media_type=media_type,
                        headers={
                            "Content-Disposition": f"attachment; filename=metrics_export_{int(time.time())}.{format}"
                        }
                    )
                    
            except Exception as e:
                logger.error(f"Error exporting metrics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/api/v1/metrics/cleanup")
        async def cleanup_old_metrics(
            max_age_hours: int = Query(24, ge=1, le=168, description="Maximum age in hours"),
            authenticated: bool = Depends(verify_api_key)
        ):
            """Clean up old metrics data"""
            try:
                self.metrics_collector.cleanup_old_metrics(max_age_hours)
                return JSONResponse(content={
                    "success": True,
                    "message": f"Cleaned up metrics older than {max_age_hours} hours",
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Error cleaning up metrics: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/api/v1/monitoring/report")
        async def get_monitoring_report(authenticated: bool = Depends(verify_api_key)):
            """Generate comprehensive monitoring report"""
            try:
                report = generate_monitoring_report(self.metrics_collector)
                return JSONResponse(content=json.loads(report))
            except Exception as e:
                logger.error(f"Error generating monitoring report: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def start_server(self, host: str = "0.0.0.0", port: int = 8080):
        """Start the metrics API server"""
        if not FASTAPI_AVAILABLE:
            logger.error("Cannot start metrics API server: FastAPI not available")
            return False
        
        if self.running:
            logger.warning("Metrics API server is already running")
            return True
        
        def run_server():
            try:
                uvicorn.run(
                    self.app,
                    host=host,
                    port=port,
                    log_level="info",
                    access_log=True
                )
            except Exception as e:
                logger.error(f"Error running metrics API server: {e}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.running = True
        
        logger.info(f"Metrics API server started on http://{host}:{port}")
        logger.info(f"API documentation available at http://{host}:{port}/docs")
        
        return True
    
    def stop_server(self):
        """Stop the metrics API server"""
        if not self.running:
            return
        
        self.running = False
        if self.server_thread:
            # Note: uvicorn doesn't provide a clean shutdown mechanism in this setup
            # In production, you would use uvicorn.Server with proper lifecycle management
            logger.info("Metrics API server stop requested")


class MetricsService:
    """Complete metrics service with both Prometheus and HTTP API"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.metrics_collector = get_metrics_collector(
            enable_prometheus=self.config.get('prometheus', {}).get('enabled', True)
        )
        
        self.prometheus_server = None
        self.api_server = None
        
        # Initialize components
        if self.config.get('prometheus', {}).get('enabled', True):
            self._setup_prometheus()
        
        if self.config.get('api', {}).get('enabled', True):
            self._setup_api()
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'prometheus': {
                'enabled': True,
                'port': 8000,
                'push_gateway': None
            },
            'api': {
                'enabled': True,
                'host': '0.0.0.0',
                'port': 8080,
                'authentication': False
            },
            'monitoring': {
                'update_interval': 30,
                'cleanup_interval': 3600,
                'max_metrics_age_hours': 24
            }
        }
    
    def _setup_prometheus(self):
        """Setup Prometheus metrics server"""
        prometheus_config = self.config.get('prometheus', {})
        if prometheus_config.get('enabled', True):
            port = prometheus_config.get('port', 8000)
            self.prometheus_server = start_prometheus_server(port, self.metrics_collector)
    
    def _setup_api(self):
        """Setup HTTP API server"""
        api_config = self.config.get('api', {})
        if api_config.get('enabled', True):
            self.api_server = MetricsAPI(
                self.metrics_collector,
                enable_authentication=api_config.get('authentication', False)
            )
    
    def start(self):
        """Start all metrics services"""
        logger.info("Starting metrics service")
        
        # Start API server
        if self.api_server:
            api_config = self.config.get('api', {})
            host = api_config.get('host', '0.0.0.0')
            port = api_config.get('port', 8080)
            self.api_server.start_server(host, port)
        
        # Prometheus server is started in _setup_prometheus
        
        logger.info("Metrics service started successfully")
        
        return {
            'prometheus_port': self.config.get('prometheus', {}).get('port'),
            'api_port': self.config.get('api', {}).get('port'),
            'endpoints': self._get_endpoints()
        }
    
    def stop(self):
        """Stop all metrics services"""
        logger.info("Stopping metrics service")
        
        if self.api_server:
            self.api_server.stop_server()
        
        # Note: Prometheus server doesn't have a clean stop method in prometheus_client
        
        logger.info("Metrics service stopped")
    
    def _get_endpoints(self) -> Dict[str, str]:
        """Get available endpoints"""
        endpoints = {}
        
        if self.config.get('prometheus', {}).get('enabled'):
            port = self.config.get('prometheus', {}).get('port', 8000)
            endpoints['prometheus'] = f"http://localhost:{port}/metrics"
        
        if self.config.get('api', {}).get('enabled'):
            port = self.config.get('api', {}).get('port', 8080)
            endpoints.update({
                'api_docs': f"http://localhost:{port}/docs",
                'health': f"http://localhost:{port}/health",
                'metrics_summary': f"http://localhost:{port}/api/v1/metrics/summary",
                'task_metrics': f"http://localhost:{port}/api/v1/metrics/tasks",
                'agent_metrics': f"http://localhost:{port}/api/v1/metrics/agents",
                'system_metrics': f"http://localhost:{port}/api/v1/metrics/system",
                'monitoring_report': f"http://localhost:{port}/api/v1/monitoring/report"
            })
        
        return endpoints
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            'service_running': True,
            'prometheus_enabled': self.config.get('prometheus', {}).get('enabled', False),
            'api_enabled': self.config.get('api', {}).get('enabled', False),
            'metrics_collector_available': self.metrics_collector is not None,
            'endpoints': self._get_endpoints(),
            'config': self.config
        }


# Factory function for easy service creation
def create_metrics_service(config: Optional[Dict[str, Any]] = None) -> MetricsService:
    """Create and configure a metrics service"""
    return MetricsService(config)


# Example usage and testing functions
def example_usage():
    """Example of how to use the metrics service"""
    
    # Create and start metrics service
    service = create_metrics_service()
    status = service.start()
    
    print("Metrics service started:")
    print(json.dumps(status, indent=2))
    
    # Simulate some metrics
    collector = service.metrics_collector
    
    # Record some sample tasks
    for i in range(5):
        task_id = f"test_task_{i}"
        collector.record_task_start(task_id, "test", f"agent_{i%2}", priority=5)
        time.sleep(0.1)  # Simulate work
        collector.record_task_completion(task_id, "success")
    
    # Get metrics summary
    summary = collector.get_metrics_summary()
    print("\nMetrics Summary:")
    print(json.dumps(summary, indent=2, default=str))
    
    return service


if __name__ == "__main__":
    # Run example
    service = example_usage()
    
    try:
        print("\nMetrics service running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping metrics service...")
        service.stop()