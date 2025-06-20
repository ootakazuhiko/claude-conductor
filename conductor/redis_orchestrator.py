#!/usr/bin/env python3
"""
Redis-enhanced orchestrator for Claude Conductor
Provides persistence, scalability and distributed coordination through Redis
"""

import os
import time
import json
import uuid
import asyncio
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, Future
import logging
from datetime import datetime

from .orchestrator import Orchestrator, Task, TaskResult, create_task
from .redis_backend import (
    RedisBackend, RedisTaskQueue, RedisResultStore, 
    RedisMetricsCollector, RedisSessionManager, RedisDistributedLock,
    RedisConnectionError
)
from .exceptions import (
    ConfigurationError, AgentStartupError, CommunicationError,
    TaskExecutionError, TaskValidationError, TaskTimeoutError, ResourceError
)
from .error_handler import ErrorHandler, retry, CircuitBreaker

logger = logging.getLogger(__name__)

@dataclass
class RedisConfig:
    """Redis configuration settings"""
    enabled: bool = False
    host: str = "localhost"
    port: int = 6379
    database: int = 0
    password: Optional[str] = None
    timeout: int = 5
    connect_timeout: int = 5
    max_connections: int = 20
    health_check_interval: int = 30
    health_check_enabled: bool = True
    
    # TTL settings
    result_ttl: int = 3600        # 1 hour
    agent_ttl: int = 300          # 5 minutes
    session_ttl: int = 86400      # 24 hours
    stats_ttl: int = 3600         # 1 hour
    metrics_ttl: int = 1800       # 30 minutes
    coordination_ttl: int = 1800  # 30 minutes
    lock_ttl: int = 60            # 1 minute

class RedisOrchestrator(Orchestrator):
    """Redis-enhanced orchestrator with persistence and scalability"""
    
    def __init__(self, config_path: Optional[str] = None, redis_config: Optional[RedisConfig] = None):
        # Initialize parent orchestrator
        super().__init__(config_path)
        
        # Set up Redis configuration
        self.redis_config = redis_config or self._load_redis_config()
        self.redis_backend = None
        self.use_redis = self.redis_config.enabled
        
        # Redis-backed components
        self.redis_task_queue = None
        self.redis_result_store = None
        self.redis_metrics = None
        self.redis_session_manager = None
        
        # Distributed coordination
        self.distributed_locks = {}
        self.is_leader = False
        self.leader_election_enabled = self.config.get('leader_election_enabled', False)
        self.instance_id = str(uuid.uuid4())
        
        # Background threads
        self._heartbeat_thread = None
        self._cleanup_thread = None
        self._stop_background_tasks = threading.Event()
        
        # Performance tracking
        self.redis_performance_stats = {
            'redis_operations': 0,
            'redis_errors': 0,
            'average_redis_latency': 0.0,
            'last_redis_error': None
        }
        
        if self.use_redis:
            self._initialize_redis()
        
    def _load_redis_config(self) -> RedisConfig:
        """Load Redis configuration from config file or environment"""
        redis_settings = self.config.get('redis', {})
        
        # Override with environment variables
        env_overrides = {
            'host': os.getenv('REDIS_HOST'),
            'port': int(os.getenv('REDIS_PORT', 0)) or None,
            'database': int(os.getenv('REDIS_DB', 0)) or None,
            'password': os.getenv('REDIS_PASSWORD'),
            'enabled': os.getenv('REDIS_ENABLED', '').lower() in ('true', '1', 'yes')
        }
        
        # Apply non-None overrides
        for key, value in env_overrides.items():
            if value is not None:
                redis_settings[key] = value
        
        return RedisConfig(**redis_settings)
    
    def _initialize_redis(self):
        """Initialize Redis backend and components"""
        try:
            logger.info("Initializing Redis backend for orchestrator")
            
            # Create Redis backend
            config_dict = {
                'host': self.redis_config.host,
                'port': self.redis_config.port,
                'database': self.redis_config.database,
                'password': self.redis_config.password,
                'timeout': self.redis_config.timeout,
                'connect_timeout': self.redis_config.connect_timeout,
                'max_connections': self.redis_config.max_connections,
                'health_check_interval': self.redis_config.health_check_interval,
                'health_check_enabled': self.redis_config.health_check_enabled,
                'result_ttl': self.redis_config.result_ttl,
                'agent_ttl': self.redis_config.agent_ttl,
                'session_ttl': self.redis_config.session_ttl,
                'stats_ttl': self.redis_config.stats_ttl,
                'metrics_ttl': self.redis_config.metrics_ttl,
                'coordination_ttl': self.redis_config.coordination_ttl,
                'lock_ttl': self.redis_config.lock_ttl
            }
            
            self.redis_backend = RedisBackend(config_dict)
            
            # Initialize Redis-backed components
            self.redis_task_queue = RedisTaskQueue(self.redis_backend)
            self.redis_result_store = RedisResultStore(self.redis_backend)
            self.redis_metrics = RedisMetricsCollector(self.redis_backend)
            self.redis_session_manager = RedisSessionManager(self.redis_backend)
            
            # Override parent's data structures with Redis-backed versions
            self.task_queue = RedisTaskQueueAdapter(self.redis_task_queue)
            self.results = RedisResultStoreAdapter(self.redis_result_store)
            
            logger.info("Redis backend initialized successfully")
            
        except RedisConnectionError as e:
            logger.error(f"Failed to initialize Redis backend: {e}")
            if self.config.get('redis_required', False):
                raise
            else:
                logger.warning("Falling back to in-memory mode")
                self.use_redis = False
        except Exception as e:
            logger.error(f"Unexpected error initializing Redis: {e}")
            self.use_redis = False
    
    def start(self):
        """Start orchestrator with Redis enhancements"""
        try:
            if self.use_redis:
                # Register session
                orchestrator_info = {
                    'instance_id': self.instance_id,
                    'version': '2.0.0',
                    'num_agents': self.config['num_agents'],
                    'leader_election_enabled': self.leader_election_enabled
                }
                session_id = self.redis_session_manager.register_session(orchestrator_info)
                logger.info(f"Registered Redis session: {session_id}")
                
                # Start background tasks
                self._start_background_tasks()
                
                # Leader election if enabled
                if self.leader_election_enabled:
                    self._perform_leader_election()
            
            # Start parent orchestrator
            super().start()
            
            logger.info(f"Redis orchestrator started with instance ID: {self.instance_id}")
            
        except Exception as e:
            self.error_handler.handle_error(
                "redis_orchestrator_start",
                e,
                context={'instance_id': self.instance_id},
                reraise=True
            )
    
    def stop(self):
        """Stop orchestrator with proper Redis cleanup"""
        try:
            logger.info("Stopping Redis orchestrator")
            
            # Stop background tasks
            self._stop_background_tasks.set()
            
            if self._heartbeat_thread:
                self._heartbeat_thread.join(timeout=5)
            if self._cleanup_thread:
                self._cleanup_thread.join(timeout=5)
            
            # Release any held locks
            for lock_name, lock in self.distributed_locks.items():
                try:
                    lock.release()
                    logger.debug(f"Released distributed lock: {lock_name}")
                except Exception as e:
                    logger.warning(f"Failed to release lock {lock_name}: {e}")
            
            # Close Redis backend
            if self.redis_backend:
                self.redis_backend.close()
            
            # Stop parent orchestrator
            super().stop()
            
            logger.info("Redis orchestrator stopped")
            
        except Exception as e:
            logger.error(f"Error stopping Redis orchestrator: {e}")
    
    def execute_task(self, task: Task) -> TaskResult:
        """Execute task with Redis persistence and metrics"""
        start_time = time.time()
        correlation_id = str(uuid.uuid4())
        
        try:
            # Add Redis-specific tracking
            if self.use_redis:
                # Track task in Redis queue
                self.redis_task_queue.enqueue(task)
                
                # Record metrics start
                self._record_redis_operation("task_enqueue")
            
            # Execute task using parent implementation
            result = super().execute_task(task)
            
            if self.use_redis:
                # Store result in Redis
                self.redis_result_store.set(task.task_id, result)
                
                # Record completion metrics
                self.redis_metrics.record_task_execution(result)
                
                # Mark task as completed in queue
                if result.status == 'success':
                    self.redis_task_queue.complete_task(task.task_id)
                else:
                    self.redis_task_queue.fail_task(task.task_id, result.error or "Unknown error")
                
                self._record_redis_operation("task_complete")
            
            return result
            
        except Exception as e:
            if self.use_redis:
                # Record failure metrics
                self.redis_task_queue.fail_task(task.task_id, str(e))
                self._record_redis_operation("task_failure", error=str(e))
            
            raise
        finally:
            execution_time = time.time() - start_time
            if self.use_redis:
                self._update_redis_performance_stats(execution_time)
    
    def get_enhanced_statistics(self) -> Dict[str, Any]:
        """Get enhanced statistics including Redis metrics"""
        stats = super().get_statistics()
        
        if self.use_redis and self.redis_backend.is_healthy():
            try:
                # Add Redis-specific statistics
                redis_stats = {
                    'redis_enabled': True,
                    'redis_healthy': True,
                    'instance_id': self.instance_id,
                    'is_leader': self.is_leader,
                    'redis_performance': self.redis_performance_stats.copy()
                }
                
                # Queue statistics
                if self.redis_task_queue:
                    redis_stats['queue_stats'] = self.redis_task_queue.get_queue_stats()
                
                # Result store statistics
                if self.redis_result_store:
                    redis_stats['result_stats'] = self.redis_result_store.get_statistics()
                
                # Metrics summary
                if self.redis_metrics:
                    redis_stats['metrics_summary'] = self.redis_metrics.get_metrics_summary()
                
                # Active sessions
                if self.redis_session_manager:
                    redis_stats['active_sessions'] = len(self.redis_session_manager.get_active_sessions())
                
                stats['redis'] = redis_stats
                
            except Exception as e:
                logger.error(f"Failed to get Redis statistics: {e}")
                stats['redis'] = {'redis_enabled': True, 'redis_healthy': False, 'error': str(e)}
        else:
            stats['redis'] = {'redis_enabled': False}
        
        return stats
    
    def get_distributed_state(self) -> Dict[str, Any]:
        """Get distributed orchestrator state information"""
        if not self.use_redis:
            return {'distributed_mode': False}
        
        try:
            active_sessions = self.redis_session_manager.get_active_sessions()
            
            return {
                'distributed_mode': True,
                'instance_id': self.instance_id,
                'is_leader': self.is_leader,
                'leader_election_enabled': self.leader_election_enabled,
                'active_instances': len(active_sessions),
                'session_details': active_sessions,
                'distributed_locks': list(self.distributed_locks.keys())
            }
            
        except Exception as e:
            logger.error(f"Failed to get distributed state: {e}")
            return {'distributed_mode': True, 'error': str(e)}
    
    def acquire_distributed_lock(self, lock_name: str, timeout: int = 60) -> bool:
        """Acquire a distributed lock across all orchestrator instances"""
        if not self.use_redis:
            logger.warning("Distributed locks require Redis backend")
            return False
        
        try:
            lock = RedisDistributedLock(self.redis_backend, lock_name, timeout)
            if lock.acquire():
                self.distributed_locks[lock_name] = lock
                logger.info(f"Acquired distributed lock: {lock_name}")
                return True
            else:
                logger.warning(f"Failed to acquire distributed lock: {lock_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error acquiring distributed lock {lock_name}: {e}")
            return False
    
    def release_distributed_lock(self, lock_name: str) -> bool:
        """Release a distributed lock"""
        if lock_name not in self.distributed_locks:
            return False
        
        try:
            lock = self.distributed_locks.pop(lock_name)
            result = lock.release()
            if result:
                logger.info(f"Released distributed lock: {lock_name}")
            return result
            
        except Exception as e:
            logger.error(f"Error releasing distributed lock {lock_name}: {e}")
            return False
    
    def _perform_leader_election(self):
        """Perform leader election among orchestrator instances"""
        if not self.use_redis:
            return
        
        try:
            leader_lock = RedisDistributedLock(self.redis_backend, "orchestrator_leader", 300)  # 5 minutes
            if leader_lock.acquire(blocking=False):
                self.is_leader = True
                self.distributed_locks["orchestrator_leader"] = leader_lock
                logger.info(f"Instance {self.instance_id} elected as leader")
                
                # Start leader-specific tasks
                self._start_leader_tasks()
            else:
                self.is_leader = False
                logger.info(f"Instance {self.instance_id} is follower")
                
        except Exception as e:
            logger.error(f"Error in leader election: {e}")
            self.is_leader = False
    
    def _start_leader_tasks(self):
        """Start tasks that only the leader should perform"""
        if not self.is_leader:
            return
        
        logger.info("Starting leader-specific tasks")
        
        # Add leader-specific responsibilities here
        # For example: cleanup tasks, global coordination, etc.
    
    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        if not self.use_redis:
            return
        
        # Heartbeat thread
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True
        )
        self._heartbeat_thread.start()
        
        # Cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self._cleanup_thread.start()
    
    def _heartbeat_loop(self):
        """Background heartbeat to maintain session"""
        while not self._stop_background_tasks.wait(30):  # Every 30 seconds
            try:
                if self.redis_session_manager:
                    self.redis_session_manager.update_heartbeat()
                    
                # Refresh leader lock if we're the leader
                if self.is_leader and "orchestrator_leader" in self.distributed_locks:
                    # The lock will auto-refresh through Redis TTL
                    pass
                    
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
    
    def _cleanup_loop(self):
        """Background cleanup tasks"""
        while not self._stop_background_tasks.wait(300):  # Every 5 minutes
            try:
                if self.is_leader:  # Only leader performs cleanup
                    self._perform_cleanup_tasks()
                    
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    def _perform_cleanup_tasks(self):
        """Perform periodic cleanup tasks (leader only)"""
        try:
            # Clean up stale processing tasks
            if self.redis_task_queue:
                stale_count = self.redis_task_queue.cleanup_stale_processing()
                if stale_count > 0:
                    logger.info(f"Cleaned up {stale_count} stale processing tasks")
            
            # Clean up expired sessions
            if self.redis_session_manager:
                expired_count = self.redis_session_manager.cleanup_expired_sessions()
                if expired_count > 0:
                    logger.info(f"Cleaned up {expired_count} expired sessions")
            
        except Exception as e:
            logger.error(f"Error in cleanup tasks: {e}")
    
    def _record_redis_operation(self, operation: str, error: Optional[str] = None):
        """Record Redis operation for performance tracking"""
        self.redis_performance_stats['redis_operations'] += 1
        
        if error:
            self.redis_performance_stats['redis_errors'] += 1
            self.redis_performance_stats['last_redis_error'] = error
    
    def _update_redis_performance_stats(self, operation_time: float):
        """Update Redis performance statistics"""
        current_avg = self.redis_performance_stats['average_redis_latency']
        total_ops = self.redis_performance_stats['redis_operations']
        
        # Calculate new average
        new_avg = ((current_avg * (total_ops - 1)) + operation_time) / total_ops
        self.redis_performance_stats['average_redis_latency'] = new_avg

class RedisTaskQueueAdapter:
    """Adapter to make RedisTaskQueue compatible with list interface"""
    
    def __init__(self, redis_queue: RedisTaskQueue):
        self.redis_queue = redis_queue
    
    def append(self, task: Task):
        """Add task to queue"""
        self.redis_queue.enqueue(task)
    
    def sort(self, key=None, reverse=False):
        """No-op for Redis queue (priority handled internally)"""
        pass
    
    def __len__(self):
        """Get queue length"""
        return self.redis_queue.get_queue_stats().get('pending', 0)
    
    def __iter__(self):
        """Iterator over tasks (for compatibility)"""
        return iter([])  # Redis queue doesn't support iteration
    
    def pop(self, index=0):
        """Remove and return task"""
        return self.redis_queue.dequeue()

class RedisResultStoreAdapter:
    """Adapter to make RedisResultStore compatible with dict interface"""
    
    def __init__(self, redis_store: RedisResultStore):
        self.redis_store = redis_store
    
    def __setitem__(self, key: str, value: TaskResult):
        """Store result"""
        self.redis_store.set(key, value)
    
    def __getitem__(self, key: str) -> TaskResult:
        """Get result"""
        result = self.redis_store.get(key)
        if result is None:
            raise KeyError(key)
        return result
    
    def get(self, key: str, default=None):
        """Get result with default"""
        return self.redis_store.get(key) or default
    
    def __contains__(self, key: str) -> bool:
        """Check if result exists"""
        return self.redis_store.get(key) is not None
    
    def keys(self):
        """Get all result keys (limited implementation)"""
        return []  # Redis store doesn't support key iteration
    
    def values(self):
        """Get all results (limited implementation)"""
        return []  # Redis store doesn't support value iteration
    
    def items(self):
        """Get all items (limited implementation)"""
        return []  # Redis store doesn't support item iteration

def create_redis_orchestrator(
    config_path: Optional[str] = None,
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_db: int = 0,
    redis_password: Optional[str] = None,
    enable_leader_election: bool = False
) -> RedisOrchestrator:
    """Factory function to create Redis orchestrator with common settings"""
    
    redis_config = RedisConfig(
        enabled=True,
        host=redis_host,
        port=redis_port,
        database=redis_db,
        password=redis_password
    )
    
    orchestrator = RedisOrchestrator(config_path, redis_config)
    
    if enable_leader_election:
        orchestrator.leader_election_enabled = True
    
    return orchestrator