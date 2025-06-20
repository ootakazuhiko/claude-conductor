#!/usr/bin/env python3
"""
Redis backend integration for Claude Conductor
Provides persistence and scalability through Redis-backed data structures
"""

import json
import pickle
import time
import uuid
from typing import Dict, List, Optional, Any, Union
from dataclasses import asdict
import redis
import logging
from concurrent.futures import ThreadPoolExecutor
import threading

from .agent import Task, TaskResult
from .exceptions import ConductorError

logger = logging.getLogger(__name__)

class RedisConnectionError(ConductorError):
    """Redis connection related errors"""
    pass

class RedisBackend:
    """Redis backend for Claude Conductor persistence and scalability"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.connection_pool = None
        self.redis_client = None
        self._initialize_connection()
        
        # Key prefixes for different data types
        self.key_prefixes = {
            'task_queue': 'conductor:queue:',
            'task_result': 'conductor:result:',
            'agent_state': 'conductor:agent:',
            'session': 'conductor:session:',
            'stats': 'conductor:stats:',
            'coordination': 'conductor:coord:',
            'metrics': 'conductor:metrics:',
            'locks': 'conductor:locks:',
            'counters': 'conductor:counters:'
        }
        
        # TTL settings (in seconds)
        self.ttl_settings = {
            'task_result': config.get('result_ttl', 3600),     # 1 hour
            'agent_state': config.get('agent_ttl', 300),       # 5 minutes
            'session': config.get('session_ttl', 86400),       # 24 hours
            'stats': config.get('stats_ttl', 3600),            # 1 hour
            'metrics': config.get('metrics_ttl', 1800),        # 30 minutes
            'locks': config.get('lock_ttl', 60),               # 1 minute
            'coordination': config.get('coordination_ttl', 1800)  # 30 minutes
        }
        
        # Health check thread
        self._health_check_thread = None
        self._stop_health_check = threading.Event()
        self._start_health_check()
        
    def _initialize_connection(self):
        """Initialize Redis connection with retry logic"""
        try:
            # Create connection pool
            self.connection_pool = redis.ConnectionPool(
                host=self.config.get('host', 'localhost'),
                port=self.config.get('port', 6379),
                db=self.config.get('database', 0),
                password=self.config.get('password'),
                socket_timeout=self.config.get('timeout', 5),
                socket_connect_timeout=self.config.get('connect_timeout', 5),
                retry_on_timeout=True,
                health_check_interval=self.config.get('health_check_interval', 30),
                max_connections=self.config.get('max_connections', 20)
            )
            
            self.redis_client = redis.Redis(
                connection_pool=self.connection_pool,
                decode_responses=False  # Handle binary data
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("Redis backend initialized successfully")
            
        except Exception as e:
            raise RedisConnectionError(f"Failed to connect to Redis: {e}")
    
    def _start_health_check(self):
        """Start background health check thread"""
        if self.config.get('health_check_enabled', True):
            self._health_check_thread = threading.Thread(
                target=self._health_check_loop,
                daemon=True
            )
            self._health_check_thread.start()
    
    def _health_check_loop(self):
        """Health check loop for Redis connection"""
        while not self._stop_health_check.wait(30):  # Check every 30 seconds
            try:
                self.redis_client.ping()
            except Exception as e:
                logger.warning(f"Redis health check failed: {e}")
                try:
                    self._initialize_connection()
                    logger.info("Redis connection restored")
                except Exception as reconnect_error:
                    logger.error(f"Failed to restore Redis connection: {reconnect_error}")
    
    def is_healthy(self) -> bool:
        """Check if Redis connection is healthy"""
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False
    
    def close(self):
        """Close Redis connection and cleanup"""
        if self._health_check_thread:
            self._stop_health_check.set()
            self._health_check_thread.join(timeout=5)
        
        if self.connection_pool:
            self.connection_pool.disconnect()

class RedisTaskQueue:
    """Redis-backed priority task queue with high availability"""
    
    def __init__(self, redis_backend: RedisBackend):
        self.redis = redis_backend.redis_client
        self.backend = redis_backend
        self.queue_key = redis_backend.key_prefixes['task_queue'] + 'priority'
        self.task_data_key = redis_backend.key_prefixes['task_queue'] + 'data:'
        self.processing_key = redis_backend.key_prefixes['task_queue'] + 'processing:'
        self.failed_key = redis_backend.key_prefixes['task_queue'] + 'failed'
        
        # Queue statistics
        self.stats_key = redis_backend.key_prefixes['stats'] + 'queue'
        
    def enqueue(self, task: Task) -> None:
        """Add task to priority queue with reliability"""
        try:
            # Store task data with TTL
            task_key = f"{self.task_data_key}{task.task_id}"
            task_data = pickle.dumps(task)
            
            pipe = self.redis.pipeline()
            pipe.setex(task_key, 3600, task_data)  # 1 hour TTL
            pipe.zadd(self.queue_key, {task.task_id: task.priority})
            
            # Update statistics
            pipe.hincrby(self.stats_key, 'enqueued', 1)
            pipe.hincrby(self.stats_key, f'priority_{task.priority}', 1)
            pipe.hset(self.stats_key, 'last_enqueue', int(time.time()))
            
            pipe.execute()
            
            logger.debug(f"Task {task.task_id} enqueued with priority {task.priority}")
            
        except Exception as e:
            logger.error(f"Failed to enqueue task {task.task_id}: {e}")
            raise
    
    def dequeue(self, timeout: int = 0) -> Optional[Task]:
        """Get highest priority task with optional blocking"""
        try:
            if timeout > 0:
                # Blocking pop with timeout
                result = self.redis.bzpopmax(self.queue_key, timeout=timeout)
                if not result:
                    return None
                _, task_id, priority = result
            else:
                # Non-blocking pop
                result = self.redis.zpopmax(self.queue_key)
                if not result:
                    return None
                task_id, priority = result[0]
            
            task_id = task_id.decode('utf-8')
            
            # Get task data
            task_key = f"{self.task_data_key}{task_id}"
            task_data = self.redis.get(task_key)
            
            if task_data:
                # Mark as processing
                processing_key = f"{self.processing_key}{task_id}"
                self.redis.setex(processing_key, 300, int(time.time()))  # 5 minutes TTL
                
                # Clean up task data
                self.redis.delete(task_key)
                
                # Update statistics
                self.redis.hincrby(self.stats_key, 'dequeued', 1)
                self.redis.hset(self.stats_key, 'last_dequeue', int(time.time()))
                
                task = pickle.loads(task_data)
                logger.debug(f"Task {task_id} dequeued")
                return task
            else:
                logger.warning(f"Task {task_id} found in queue but data missing")
                return None
                
        except Exception as e:
            logger.error(f"Failed to dequeue task: {e}")
            return None
    
    def complete_task(self, task_id: str) -> None:
        """Mark task as completed and clean up processing state"""
        try:
            processing_key = f"{self.processing_key}{task_id}"
            self.redis.delete(processing_key)
            
            # Update statistics
            self.redis.hincrby(self.stats_key, 'completed', 1)
            
        except Exception as e:
            logger.error(f"Failed to complete task {task_id}: {e}")
    
    def fail_task(self, task_id: str, error: str) -> None:
        """Mark task as failed and add to failed queue"""
        try:
            processing_key = f"{self.processing_key}{task_id}"
            self.redis.delete(processing_key)
            
            # Add to failed queue with error info
            failed_info = {
                'task_id': task_id,
                'error': error,
                'timestamp': time.time()
            }
            self.redis.lpush(self.failed_key, json.dumps(failed_info))
            
            # Update statistics
            self.redis.hincrby(self.stats_key, 'failed', 1)
            
        except Exception as e:
            logger.error(f"Failed to mark task {task_id} as failed: {e}")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics"""
        try:
            stats = self.redis.hgetall(self.stats_key)
            stats = {k.decode(): int(v) for k, v in stats.items()}
            
            # Add current queue lengths
            stats['pending'] = self.redis.zcard(self.queue_key)
            stats['processing'] = len(self.redis.keys(f"{self.processing_key}*"))
            stats['failed'] = self.redis.llen(self.failed_key)
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {}
    
    def cleanup_stale_processing(self, timeout: int = 300) -> int:
        """Clean up stale processing tasks (default 5 minutes)"""
        try:
            current_time = int(time.time())
            stale_count = 0
            
            processing_keys = self.redis.keys(f"{self.processing_key}*")
            for key in processing_keys:
                start_time = self.redis.get(key)
                if start_time and current_time - int(start_time) > timeout:
                    self.redis.delete(key)
                    stale_count += 1
            
            if stale_count > 0:
                logger.info(f"Cleaned up {stale_count} stale processing tasks")
            
            return stale_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup stale processing tasks: {e}")
            return 0

class RedisResultStore:
    """Redis-backed result storage with search capabilities"""
    
    def __init__(self, redis_backend: RedisBackend):
        self.redis = redis_backend.redis_client
        self.backend = redis_backend
        self.key_prefix = redis_backend.key_prefixes['task_result']
        self.search_prefix = self.key_prefix + 'search:'
        self.index_prefix = self.key_prefix + 'index:'
        self.ttl = redis_backend.ttl_settings['task_result']
        
    def set(self, task_id: str, result: TaskResult) -> None:
        """Store task result with indexing for search"""
        try:
            # Store full result
            key = f"{self.key_prefix}{task_id}"
            data = pickle.dumps(result)
            
            # Store searchable metadata
            search_key = f"{self.search_prefix}{task_id}"
            search_data = {
                'task_id': result.task_id,
                'agent_id': result.agent_id,
                'status': result.status,
                'timestamp': result.timestamp,
                'execution_time': result.execution_time,
                'task_type': getattr(result, 'task_type', 'unknown')
            }
            
            pipe = self.redis.pipeline()
            pipe.setex(key, self.ttl, data)
            pipe.setex(search_key, self.ttl, json.dumps(search_data))
            
            # Create indexes
            status_index = f"{self.index_prefix}status:{result.status}"
            agent_index = f"{self.index_prefix}agent:{result.agent_id}"
            
            pipe.sadd(status_index, task_id)
            pipe.expire(status_index, self.ttl)
            pipe.sadd(agent_index, task_id)
            pipe.expire(agent_index, self.ttl)
            
            pipe.execute()
            
        except Exception as e:
            logger.error(f"Failed to store result for task {task_id}: {e}")
            raise
    
    def get(self, task_id: str) -> Optional[TaskResult]:
        """Get task result by ID"""
        try:
            key = f"{self.key_prefix}{task_id}"
            data = self.redis.get(key)
            return pickle.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get result for task {task_id}: {e}")
            return None
    
    def search(self, status: Optional[str] = None, 
               agent_id: Optional[str] = None,
               limit: int = 100,
               offset: int = 0) -> List[TaskResult]:
        """Search results by criteria with pagination"""
        try:
            task_ids = set()
            
            if status:
                status_index = f"{self.index_prefix}status:{status}"
                task_ids.update(self.redis.smembers(status_index))
            
            if agent_id:
                agent_index = f"{self.index_prefix}agent:{agent_id}"
                if task_ids:
                    # Intersection
                    task_ids &= self.redis.smembers(agent_index)
                else:
                    task_ids.update(self.redis.smembers(agent_index))
            
            # If no filters, get all search keys
            if not status and not agent_id:
                pattern = f"{self.search_prefix}*"
                keys = self.redis.keys(pattern)
                task_ids = {key.decode().split(':')[-1] for key in keys}
            
            # Convert to list and paginate
            task_ids = list(task_ids)
            paginated_ids = task_ids[offset:offset + limit]
            
            # Get full results
            results = []
            for task_id in paginated_ids:
                if isinstance(task_id, bytes):
                    task_id = task_id.decode()
                result = self.get(task_id)
                if result:
                    results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search results: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get result store statistics"""
        try:
            # Count by status
            status_counts = {}
            status_keys = self.redis.keys(f"{self.index_prefix}status:*")
            for key in status_keys:
                status = key.decode().split(':')[-1]
                count = self.redis.scard(key)
                status_counts[status] = count
            
            # Count by agent
            agent_counts = {}
            agent_keys = self.redis.keys(f"{self.index_prefix}agent:*")
            for key in agent_keys:
                agent = key.decode().split(':')[-1]
                count = self.redis.scard(key)
                agent_counts[agent] = count
            
            # Total results
            total_results = len(self.redis.keys(f"{self.key_prefix}*"))
            
            return {
                'total_results': total_results,
                'status_counts': status_counts,
                'agent_counts': agent_counts
            }
            
        except Exception as e:
            logger.error(f"Failed to get result statistics: {e}")
            return {}

class RedisMetricsCollector:
    """Redis-based metrics collection with time-series data"""
    
    def __init__(self, redis_backend: RedisBackend):
        self.redis = redis_backend.redis_client
        self.backend = redis_backend
        self.key_prefix = redis_backend.key_prefixes['metrics']
        self.ttl = redis_backend.ttl_settings['metrics']
        
    def record_task_execution(self, result: TaskResult) -> None:
        """Record task execution metrics with time-series data"""
        try:
            timestamp = int(time.time())
            minute_bucket = timestamp // 60 * 60  # Round to minute
            
            pipe = self.redis.pipeline()
            
            # Time-series metrics
            base_key = f"{self.key_prefix}ts:"
            
            # Task completion metrics
            if result.status == 'success':
                pipe.incr(f"{base_key}tasks:completed:{minute_bucket}")
                pipe.expire(f"{base_key}tasks:completed:{minute_bucket}", self.ttl)
            else:
                pipe.incr(f"{base_key}tasks:failed:{minute_bucket}")
                pipe.expire(f"{base_key}tasks:failed:{minute_bucket}", self.ttl)
            
            # Execution time metrics
            pipe.lpush(f"{base_key}execution_times:{minute_bucket}", result.execution_time)
            pipe.expire(f"{base_key}execution_times:{minute_bucket}", self.ttl)
            pipe.ltrim(f"{base_key}execution_times:{minute_bucket}", 0, 999)  # Keep last 1000
            
            # Agent metrics
            agent_key = f"{base_key}agents:{result.agent_id}:{minute_bucket}"
            pipe.incr(agent_key)
            pipe.expire(agent_key, self.ttl)
            
            # Task type metrics
            task_type = getattr(result, 'task_type', 'unknown')
            type_key = f"{base_key}task_types:{task_type}:{minute_bucket}"
            pipe.incr(type_key)
            pipe.expire(type_key, self.ttl)
            
            pipe.execute()
            
        except Exception as e:
            logger.error(f"Failed to record task execution metrics: {e}")
    
    def get_metrics_summary(self, timeframe: int = 3600) -> Dict[str, Any]:
        """Get metrics summary for specified timeframe"""
        try:
            end_time = int(time.time())
            start_time = end_time - timeframe
            
            # Generate minute buckets for timeframe
            buckets = []
            current = start_time // 60 * 60
            while current <= end_time:
                buckets.append(current)
                current += 60
            
            # Aggregate metrics
            completed_total = 0
            failed_total = 0
            execution_times = []
            
            for bucket in buckets:
                completed_key = f"{self.key_prefix}ts:tasks:completed:{bucket}"
                failed_key = f"{self.key_prefix}ts:tasks:failed:{bucket}"
                times_key = f"{self.key_prefix}ts:execution_times:{bucket}"
                
                completed_total += int(self.redis.get(completed_key) or 0)
                failed_total += int(self.redis.get(failed_key) or 0)
                
                bucket_times = self.redis.lrange(times_key, 0, -1)
                execution_times.extend([float(t) for t in bucket_times])
            
            # Calculate statistics
            total_tasks = completed_total + failed_total
            success_rate = completed_total / max(total_tasks, 1)
            avg_execution_time = sum(execution_times) / max(len(execution_times), 1)
            
            return {
                'timeframe': timeframe,
                'completed_tasks': completed_total,
                'failed_tasks': failed_total,
                'total_tasks': total_tasks,
                'success_rate': success_rate,
                'avg_execution_time': avg_execution_time,
                'throughput': total_tasks / (timeframe / 60),  # tasks per minute
                'execution_times': execution_times[-100:] if execution_times else []  # Last 100
            }
            
        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            return {}

class RedisSessionManager:
    """Redis-based session management for orchestrator instances"""
    
    def __init__(self, redis_backend: RedisBackend):
        self.redis = redis_backend.redis_client
        self.backend = redis_backend
        self.key_prefix = redis_backend.key_prefixes['session']
        self.ttl = redis_backend.ttl_settings['session']
        self.session_id = str(uuid.uuid4())
        
    def register_session(self, orchestrator_info: Dict[str, Any]) -> str:
        """Register new orchestrator session"""
        try:
            session_key = f"{self.key_prefix}{self.session_id}"
            session_data = {
                'session_id': self.session_id,
                'start_time': time.time(),
                'orchestrator_info': orchestrator_info,
                'last_heartbeat': time.time()
            }
            
            self.redis.setex(session_key, self.ttl, json.dumps(session_data))
            
            # Add to active sessions set
            active_key = f"{self.key_prefix}active"
            self.redis.sadd(active_key, self.session_id)
            self.redis.expire(active_key, self.ttl)
            
            logger.info(f"Registered orchestrator session {self.session_id}")
            return self.session_id
            
        except Exception as e:
            logger.error(f"Failed to register session: {e}")
            raise
    
    def update_heartbeat(self) -> None:
        """Update session heartbeat"""
        try:
            session_key = f"{self.key_prefix}{self.session_id}"
            data = self.redis.get(session_key)
            
            if data:
                session_data = json.loads(data)
                session_data['last_heartbeat'] = time.time()
                self.redis.setex(session_key, self.ttl, json.dumps(session_data))
                
        except Exception as e:
            logger.error(f"Failed to update heartbeat: {e}")
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all active orchestrator sessions"""
        try:
            active_key = f"{self.key_prefix}active"
            session_ids = self.redis.smembers(active_key)
            
            sessions = []
            for session_id in session_ids:
                if isinstance(session_id, bytes):
                    session_id = session_id.decode()
                
                session_key = f"{self.key_prefix}{session_id}"
                data = self.redis.get(session_key)
                
                if data:
                    session_data = json.loads(data)
                    sessions.append(session_data)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get active sessions: {e}")
            return []
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions"""
        try:
            active_key = f"{self.key_prefix}active"
            session_ids = self.redis.smembers(active_key)
            
            expired_count = 0
            for session_id in session_ids:
                if isinstance(session_id, bytes):
                    session_id = session_id.decode()
                
                session_key = f"{self.key_prefix}{session_id}"
                if not self.redis.exists(session_key):
                    self.redis.srem(active_key, session_id)
                    expired_count += 1
            
            return expired_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0

class RedisDistributedLock:
    """Redis-based distributed lock for coordination"""
    
    def __init__(self, redis_backend: RedisBackend, lock_name: str, timeout: int = 60):
        self.redis = redis_backend.redis_client
        self.lock_name = lock_name
        self.timeout = timeout
        self.key = f"{redis_backend.key_prefixes['locks']}{lock_name}"
        self.identifier = str(uuid.uuid4())
        
    def acquire(self, blocking: bool = True, blocking_timeout: Optional[int] = None) -> bool:
        """Acquire distributed lock"""
        try:
            end_time = time.time() + (blocking_timeout or 0) if blocking_timeout else None
            
            while True:
                # Try to acquire lock
                if self.redis.set(self.key, self.identifier, nx=True, ex=self.timeout):
                    return True
                
                if not blocking:
                    return False
                
                if end_time and time.time() > end_time:
                    return False
                
                time.sleep(0.1)  # Wait a bit before retrying
                
        except Exception as e:
            logger.error(f"Failed to acquire lock {self.lock_name}: {e}")
            return False
    
    def release(self) -> bool:
        """Release distributed lock"""
        try:
            # Lua script to ensure we only release our own lock
            lua_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("DEL", KEYS[1])
            else
                return 0
            end
            """
            result = self.redis.eval(lua_script, 1, self.key, self.identifier)
            return bool(result)
            
        except Exception as e:
            logger.error(f"Failed to release lock {self.lock_name}: {e}")
            return False
    
    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"Could not acquire lock {self.lock_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()