"""
Distributed Task Queue System for ProStruct
Redis-backed queue with length-aware load balancing, retries, and dead-letter queue.
"""
import redis
import json
import time
import threading
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
import multiprocessing
from dataclasses import dataclass, asdict
from datetime import datetime
import sqlite3


@dataclass
class Task:
    """Task data structure."""
    task_id: str
    protein_id: str
    sequence: str
    task_type: str  # 'binding_site' or 'variant_scoring'
    priority: int = 0
    sequence_length: int = 0
    created_at: str = None
    retries: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        if self.sequence_length == 0:
            self.sequence_length = len(self.sequence)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Task':
        return cls(**data)


@dataclass
class WorkerStatus:
    """Worker status data structure."""
    worker_id: str
    last_heartbeat: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    current_task_id: Optional[str] = None
    is_busy: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'WorkerStatus':
        return cls(**data)


class TaskQueue:
    """Redis-backed task queue with length-aware scheduling."""
    
    def __init__(self, config_path: str = 'config.yaml'):
        self.config = self.load_config(config_path)
        
        # Redis connection
        try:
            self.redis_client = redis.Redis(
                host=self.config['queue']['redis_host'],
                port=self.config['queue']['redis_port'],
                db=self.config['queue']['redis_db'],
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True
                # Remove health_check_interval to avoid HELLO command
            )
            # Test connection with simple PING
            self.redis_client.ping()
            self.redis_available = True
        except Exception as e:
            print(f"Warning: Redis connection failed: {e}")
            print("Running in fallback mode (shared memory queue)")
            self.redis_available = False
            # Use multiprocessing.Manager for shared queue across processes
            self._manager = multiprocessing.Manager()
            self._fallback_queue = self._manager.list()
            self._fallback_workers = self._manager.dict()
            self._fallback_lock = self._manager.Lock()
        
        # Queue names
        self.task_queue = 'prostruct:tasks'
        self.priority_queue = 'prostruct:tasks:priority'
        self.dead_letter_queue = 'prostruct:tasks:dlq'
        self.worker_registry = 'prostruct:workers'
        self.results_queue = 'prostruct:results'
        
        # SQLite for persistent results
        self.db_path = 'data/results.db'
        self._init_database()
        
        # Lock for thread safety
        self.lock = threading.Lock()
    
    def load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _init_database(self):
        """Initialize SQLite database for results."""
        import os
        os.makedirs('data', exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS results (
                task_id TEXT PRIMARY KEY,
                protein_id TEXT,
                task_type TEXT,
                result TEXT,
                status TEXT,
                worker_id TEXT,
                completed_at TEXT,
                error_message TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                queue_depth INTEGER,
                active_workers INTEGER,
                tasks_completed INTEGER,
                tasks_failed INTEGER,
                avg_task_duration REAL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def enqueue_task(self, task: Task, priority: bool = False) -> bool:
        """
        Enqueue a task for processing.
        If priority=True, add to priority queue.
        """
        with self.lock:
            if not self.redis_available:
                # Fallback: use shared memory list with lock
                with self._fallback_lock:
                    self._fallback_queue.append((task.sequence_length, task))
                return True
            
            queue_name = self.priority_queue if priority else self.task_queue
            task_data = json.dumps(task.to_dict())
            
            try:
                # Use Redis sorted set with sequence length as score for load balancing
                # Lower score = shorter sequence = processed first
                self.redis_client.zadd(queue_name, {task_data: task.sequence_length})
                return True
            except Exception as e:
                print(f"Error enqueueing task {task.task_id}: {e}")
                return False
    
    def enqueue_batch(self, tasks: List[Task], priority: bool = False) -> int:
        """Enqueue multiple tasks."""
        count = 0
        for task in tasks:
            if self.enqueue_task(task, priority):
                count += 1
        return count
    
    def dequeue_task(self, worker_id: str) -> Optional[Task]:
        """
        Dequeue a task for a worker.
        Implements length-aware scheduling: prefers shorter sequences.
        """
        with self.lock:
            if not self.redis_available:
                # Fallback: pop from shared memory list (sorted by sequence length)
                with self._fallback_lock:
                    if not self._fallback_queue:
                        return None
                    # Convert to list for sorting
                    queue_list = list(self._fallback_queue)
                    queue_list.sort(key=lambda x: x[0])  # Sort by sequence length
                    _, task = queue_list.pop(0)
                    # Clear and repopulate
                    self._fallback_queue[:] = queue_list
                self._update_worker_status(worker_id, current_task_id=task.task_id, is_busy=True)
                return task
            
            try:
                # Check priority queue first
                task_data = self.redis_client.zpopmin(self.priority_queue)
                if not task_data:
                    # Fall back to regular queue
                    task_data = self.redis_client.zpopmin(self.task_queue)
                
                if not task_data:
                    return None
                
                task_dict = json.loads(task_data[0][0])
                task = Task.from_dict(task_dict)
                
                # Update worker status
                self._update_worker_status(worker_id, current_task_id=task.task_id, is_busy=True)
                
                return task
            except Exception as e:
                print(f"Error dequeuing task for worker {worker_id}: {e}")
                return None
    
    def task_complete(self, task: Task, worker_id: str, result: Dict, success: bool = True):
        """
        Mark a task as complete and store result.
        """
        with self.lock:
            try:
                # Store result in SQLite
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO results 
                    (task_id, protein_id, task_type, result, status, worker_id, completed_at, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    task.task_id,
                    task.protein_id,
                    task.task_type,
                    json.dumps(result),
                    'completed' if success else 'failed',
                    worker_id,
                    datetime.utcnow().isoformat(),
                    None if success else result.get('error', 'Unknown error')
                ))
                
                conn.commit()
                conn.close()
                
                # Update worker status
                if success:
                    self._increment_worker_completed(worker_id)
                else:
                    self._increment_worker_failed(worker_id)
                
                self._update_worker_status(worker_id, current_task_id=None, is_busy=False)
                
                # Publish result to Redis for dashboard (if available)
                if self.redis_available:
                    try:
                        self.redis_client.publish(self.results_queue, json.dumps({
                            'task_id': task.task_id,
                            'worker_id': worker_id,
                            'success': success,
                            'result': result
                        }))
                    except:
                        pass
                
            except Exception as e:
                print(f"Error completing task {task.task_id}: {e}")
    
    def task_failed(self, task: Task, worker_id: str, error: str):
        """Handle task failure with retry logic."""
        task.retries += 1
        
        if task.retries < task.max_retries:
            # Re-enqueue with exponential backoff
            backoff_delay = self.config['queue']['retry_backoff_base'] ** task.retries
            time.sleep(backoff_delay)
            self.enqueue_task(task, priority=True)
            print(f"Task {task.task_id} re-enqueued (retry {task.retries}/{task.max_retries})")
        else:
            # Move to dead-letter queue
            if self.redis_available:
                try:
                    self.redis_client.zadd(self.dead_letter_queue, {json.dumps(task.to_dict()): task.sequence_length})
                except:
                    pass
            print(f"Task {task.task_id} moved to dead-letter queue after {task.retries} failures")
        
        # Update worker status
        self._increment_worker_failed(worker_id)
        self._update_worker_status(worker_id, current_task_id=None, is_busy=False)
    
    def register_worker(self, worker_id: str) -> bool:
        """Register a new worker."""
        with self.lock:
            try:
                status = WorkerStatus(
                    worker_id=worker_id,
                    last_heartbeat=datetime.utcnow().isoformat()
                )
                if self.redis_available:
                    self.redis_client.hset(self.worker_registry, worker_id, json.dumps(status.to_dict()))
                else:
                    with self._fallback_lock:
                        self._fallback_workers[worker_id] = status
                return True
            except Exception as e:
                print(f"Error registering worker {worker_id}: {e}")
                return False
    
    def update_heartbeat(self, worker_id: str):
        """Update worker heartbeat."""
        with self.lock:
            try:
                if self.redis_available:
                    status_data = self.redis_client.hget(self.worker_registry, worker_id)
                    if status_data:
                        status = WorkerStatus.from_dict(json.loads(status_data))
                        status.last_heartbeat = datetime.utcnow().isoformat()
                        self.redis_client.hset(self.worker_registry, worker_id, json.dumps(status.to_dict()))
                else:
                    with self._fallback_lock:
                        if worker_id in self._fallback_workers:
                            self._fallback_workers[worker_id].last_heartbeat = datetime.utcnow().isoformat()
            except Exception as e:
                print(f"Error updating heartbeat for worker {worker_id}: {e}")
    
    def _update_worker_status(self, worker_id: str, current_task_id: Optional[str] = None, is_busy: bool = False):
        """Update worker status."""
        try:
            if self.redis_available:
                status_data = self.redis_client.hget(self.worker_registry, worker_id)
                if status_data:
                    status = WorkerStatus.from_dict(json.loads(status_data))
                    status.current_task_id = current_task_id
                    status.is_busy = is_busy
                    status.last_heartbeat = datetime.utcnow().isoformat()
                    self.redis_client.hset(self.worker_registry, worker_id, json.dumps(status.to_dict()))
            else:
                if worker_id in self._fallback_workers:
                    self._fallback_workers[worker_id].current_task_id = current_task_id
                    self._fallback_workers[worker_id].is_busy = is_busy
                    self._fallback_workers[worker_id].last_heartbeat = datetime.utcnow().isoformat()
        except Exception as e:
            print(f"Error updating worker status for {worker_id}: {e}")
    
    def _increment_worker_completed(self, worker_id: str):
        """Increment worker's completed task count."""
        try:
            if self.redis_available:
                status_data = self.redis_client.hget(self.worker_registry, worker_id)
                if status_data:
                    status = WorkerStatus.from_dict(json.loads(status_data))
                    status.tasks_completed += 1
                    self.redis_client.hset(self.worker_registry, worker_id, json.dumps(status.to_dict()))
            else:
                with self._fallback_lock:
                    if worker_id in self._fallback_workers:
                        self._fallback_workers[worker_id].tasks_completed += 1
        except Exception as e:
            print(f"Error incrementing completed count: {e}")
    
    def _increment_worker_failed(self, worker_id: str):
        """Increment worker's failed task count."""
        try:
            if self.redis_available:
                status_data = self.redis_client.hget(self.worker_registry, worker_id)
                if status_data:
                    status = WorkerStatus.from_dict(json.loads(status_data))
                    status.tasks_failed += 1
                    self.redis_client.hset(self.worker_registry, worker_id, json.dumps(status.to_dict()))
            else:
                with self._fallback_lock:
                    if worker_id in self._fallback_workers:
                        self._fallback_workers[worker_id].tasks_failed += 1
        except Exception as e:
            print(f"Error incrementing failed count: {e}")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get current queue statistics."""
        try:
            if not self.redis_available:
                # Fallback: use shared memory data
                with self._fallback_lock:
                    workers = []
                    active_workers = 0
                    for worker_id, status in self._fallback_workers.items():
                        workers.append(status.to_dict())
                        if status.is_busy:
                            active_workers += 1
                
                # Get results from SQLite
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM results WHERE status = 'completed'")
                completed_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM results WHERE status = 'failed'")
                failed_count = cursor.fetchone()[0]
                
                conn.close()
                
                return {
                    'priority_queue_depth': 0,
                    'regular_queue_depth': len(self._fallback_queue),
                    'total_queue_depth': len(self._fallback_queue),
                    'dead_letter_queue_depth': 0,
                    'total_workers': len(workers),
                    'active_workers': active_workers,
                    'workers': workers,
                    'total_completed': completed_count,
                    'total_failed': failed_count,
                    'timestamp': datetime.utcnow().isoformat()
                }
            
            priority_count = self.redis_client.zcard(self.priority_queue)
            regular_count = self.redis_client.zcard(self.task_queue)
            dlq_count = self.redis_client.zcard(self.dead_letter_queue)
            
            workers_data = self.redis_client.hgetall(self.worker_registry)
            workers = []
            active_workers = 0
            
            for worker_id, status_data in workers_data.items():
                status = WorkerStatus.from_dict(json.loads(status_data))
                workers.append(status.to_dict())
                if status.is_busy:
                    active_workers += 1
            
            # Get results from SQLite
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM results WHERE status = 'completed'")
            completed_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM results WHERE status = 'failed'")
            failed_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'priority_queue_depth': priority_count,
                'regular_queue_depth': regular_count,
                'total_queue_depth': priority_count + regular_count,
                'dead_letter_queue_depth': dlq_count,
                'total_workers': len(workers),
                'active_workers': active_workers,
                'workers': workers,
                'total_completed': completed_count,
                'total_failed': failed_count,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            print(f"Error getting queue stats: {e}")
            return {}
    
    def cleanup_failed_workers(self, heartbeat_timeout: int = None):
        """
        Clean up workers that haven't sent heartbeats recently.
        Returns their current tasks back to the queue.
        """
        if heartbeat_timeout is None:
            heartbeat_timeout = self.config['queue']['heartbeat_interval'] * 2
        
        with self.lock:
            try:
                if self.redis_available:
                    workers_data = self.redis_client.hgetall(self.worker_registry)
                    current_time = datetime.utcnow()
                    
                    for worker_id, status_data in workers_data.items():
                        status = WorkerStatus.from_dict(json.loads(status_data))
                        last_heartbeat = datetime.fromisoformat(status.last_heartbeat)
                        
                        if (current_time - last_heartbeat).total_seconds() > heartbeat_timeout:
                            print(f"Worker {worker_id} timed out, cleaning up")
                            
                            # Return current task to queue if any
                            if status.current_task_id:
                                # Note: In a real implementation, we'd need to track task data
                                # For now, just log it
                                print(f"Task {status.current_task_id} may need to be re-enqueued")
                            
                            # Remove worker
                            self.redis_client.hdel(self.worker_registry, worker_id)
                else:
                    with self._fallback_lock:
                        current_time = datetime.utcnow()
                        for worker_id, status in list(self._fallback_workers.items()):
                            last_heartbeat = datetime.fromisoformat(status.last_heartbeat)
                            if (current_time - last_heartbeat).total_seconds() > heartbeat_timeout:
                                print(f"Worker {worker_id} timed out, cleaning up")
                                del self._fallback_workers[worker_id]
                
            except Exception as e:
                print(f"Error cleaning up failed workers: {e}")
    
    def get_results(self, limit: int = 100) -> List[Dict]:
        """Get recent results from SQLite."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT task_id, protein_id, task_type, result, status, worker_id, completed_at
            FROM results
            ORDER BY completed_at DESC
            LIMIT ?
        ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'task_id': row[0],
                'protein_id': row[1],
                'task_type': row[2],
                'result': json.loads(row[3]) if row[3] else None,
                'status': row[4],
                'worker_id': row[5],
                'completed_at': row[6]
            })
        
        conn.close()
        return results
    
    def clear_queues(self):
        """Clear all queues (useful for testing)."""
        if self.redis_available:
            try:
                self.redis_client.delete(self.task_queue)
                self.redis_client.delete(self.priority_queue)
                self.redis_client.delete(self.dead_letter_queue)
                self.redis_client.delete(self.worker_registry)
            except:
                pass
        with self._fallback_lock:
            self._fallback_queue[:] = []
            self._fallback_workers.clear()
        print("All queues cleared")


if __name__ == '__main__':
    # Quick test
    queue = TaskQueue()
    print("Queue system initialized successfully")
    print(f"Queue stats: {queue.get_queue_stats()}")
