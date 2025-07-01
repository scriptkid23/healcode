"""
Queue manager for handling task queuing and distribution
"""

import asyncio
import heapq
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from concurrent.futures import ThreadPoolExecutor
import threading
import logging

from .models import FixRequest, FixResponse, TaskInfo, TaskStatus, QueueStats, WorkerInfo

logger = logging.getLogger(__name__)


class PriorityQueue:
    """Thread-safe priority queue for tasks"""
    
    def __init__(self):
        self._queue = []
        self._index = 0
        self._lock = threading.Lock()
    
    def put(self, item: TaskInfo):
        """Add task to queue with priority"""
        with self._lock:
            # Use negative priority for max heap (lower number = higher priority)
            heapq.heappush(self._queue, (-item.priority, self._index, item))
            self._index += 1
    
    def get(self) -> Optional[TaskInfo]:
        """Get highest priority task from queue"""
        with self._lock:
            if self._queue:
                _, _, item = heapq.heappop(self._queue)
                return item
            return None
    
    def peek(self) -> Optional[TaskInfo]:
        """Peek at highest priority task without removing it"""
        with self._lock:
            if self._queue:
                _, _, item = self._queue[0]
                return item
            return None
    
    def size(self) -> int:
        """Get queue size"""
        with self._lock:
            return len(self._queue)
    
    def empty(self) -> bool:
        """Check if queue is empty"""
        with self._lock:
            return len(self._queue) == 0


class QueueManager:
    """Manages task queuing and worker coordination"""
    
    def __init__(self, max_workers: int = 4, max_queue_size: int = 1000):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        
        # Task storage
        self._pending_queue = PriorityQueue()
        self._tasks: Dict[str, TaskInfo] = {}  # request_id -> TaskInfo
        self._task_responses: Dict[str, FixResponse] = {}  # request_id -> FixResponse
        
        # Worker management
        self._workers: Dict[str, WorkerInfo] = {}
        self._worker_executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running = False
        self._dispatcher_task: Optional[asyncio.Task] = None
        
        # Statistics
        self._stats = QueueStats()
        self._lock = threading.Lock()
        
        # Callbacks
        self._task_handlers: List[Callable[[TaskInfo], Any]] = []
    
    def add_task_handler(self, handler: Callable[[TaskInfo], Any]):
        """Add a task handler function"""
        self._task_handlers.append(handler)
    
    async def start(self):
        """Start the queue manager"""
        if self._running:
            return
        
        self._running = True
        self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())
        logger.info(f"Queue manager started with {self.max_workers} workers")
    
    async def stop(self):
        """Stop the queue manager"""
        if not self._running:
            return
        
        self._running = False
        
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass
        
        self._worker_executor.shutdown(wait=True)
        logger.info("Queue manager stopped")
    
    async def submit_task(self, request: FixRequest) -> FixResponse:
        """Submit a new task to the queue"""
        if self._pending_queue.size() >= self.max_queue_size:
            return FixResponse.failed(
                request.request_id,
                "Queue is full. Please try again later."
            )
        
        # Create task info
        task_info = TaskInfo(
            request_id=request.request_id,
            repo_name=request.repo_name,
            trace_error=request.trace_error,
            status=TaskStatus.PENDING,
            created_at=request.created_at,
            priority=request.priority,
            metadata=request.metadata
        )
        
        # Store task and add to queue
        with self._lock:
            self._tasks[request.request_id] = task_info
            self._stats.total_tasks += 1
            self._stats.pending_tasks += 1
        
        self._pending_queue.put(task_info)
        
        # Create pending response
        response = FixResponse.pending(request.request_id)
        self._task_responses[request.request_id] = response
        
        logger.info(f"Task {request.request_id} submitted for repo {request.repo_name}")
        return response
    
    def get_task_status(self, request_id: str) -> Optional[FixResponse]:
        """Get status of a specific task"""
        return self._task_responses.get(request_id)
    
    def get_queue_stats(self) -> QueueStats:
        """Get current queue statistics"""
        with self._lock:
            # Update active workers count
            active_workers = sum(1 for w in self._workers.values() if w.status == 'busy')
            self._stats.active_workers = active_workers
            return self._stats
    
    def get_all_tasks(self) -> List[TaskInfo]:
        """Get all tasks"""
        with self._lock:
            return list(self._tasks.values())
    
    def cancel_task(self, request_id: str) -> bool:
        """Cancel a pending task"""
        with self._lock:
            task = self._tasks.get(request_id)
            if task and task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                self._stats.pending_tasks -= 1
                
                response = FixResponse(
                    request_id=request_id,
                    status=TaskStatus.CANCELLED,
                    message="Task cancelled by user",
                    completed_at=datetime.now()
                )
                self._task_responses[request_id] = response
                return True
        return False
    
    async def _dispatcher_loop(self):
        """Main dispatcher loop"""
        while self._running:
            try:
                # Get next task from queue
                task = self._pending_queue.get()
                if task is None:
                    await asyncio.sleep(0.1)
                    continue
                
                # Skip cancelled tasks
                if task.status == TaskStatus.CANCELLED:
                    continue
                
                # Find available worker or wait
                worker_id = self._get_available_worker()
                if worker_id is None:
                    # No workers available, put task back
                    self._pending_queue.put(task)
                    await asyncio.sleep(0.5)
                    continue
                
                # Assign task to worker
                await self._assign_task_to_worker(task, worker_id)
                
            except Exception as e:
                logger.error(f"Error in dispatcher loop: {e}")
                await asyncio.sleep(1)
    
    def _get_available_worker(self) -> Optional[str]:
        """Get an available worker ID"""
        # Find idle worker
        for worker_id, worker in self._workers.items():
            if worker.status == 'idle':
                return worker_id
        
        # Create new worker if under limit
        if len(self._workers) < self.max_workers:
            worker_id = f"worker_{len(self._workers) + 1}"
            worker = WorkerInfo(
                worker_id=worker_id,
                status='idle'
            )
            self._workers[worker_id] = worker
            return worker_id
        
        return None
    
    async def _assign_task_to_worker(self, task: TaskInfo, worker_id: str):
        """Assign task to a specific worker"""
        # Update task status
        with self._lock:
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now()
            task.worker_id = worker_id
            
            self._stats.pending_tasks -= 1
            self._stats.processing_tasks += 1
        
        # Update worker status
        worker = self._workers[worker_id]
        worker.status = 'busy'
        worker.current_task = task.request_id
        worker.last_heartbeat = datetime.now()
        
        # Update response
        response = FixResponse.processing(task.request_id)
        self._task_responses[task.request_id] = response
        
        # Submit to thread pool
        future = self._worker_executor.submit(self._process_task, task, worker_id)
        
        # Handle completion asynchronously
        asyncio.create_task(self._handle_task_completion(future, task, worker_id))
        
        logger.info(f"Task {task.request_id} assigned to {worker_id}")
    
    def _process_task(self, task: TaskInfo, worker_id: str) -> Dict[str, Any]:
        """Process task in thread pool"""
        start_time = time.time()
        
        try:
            # Call registered task handlers
            result = {}
            for handler in self._task_handlers:
                handler_result = handler(task)
                if isinstance(handler_result, dict):
                    result.update(handler_result)
            
            # If no handlers, simulate processing
            if not self._task_handlers:
                time.sleep(2)  # Simulate work
                result = {
                    'repo_name': task.repo_name,
                    'fixes_applied': ['simulated_fix_1', 'simulated_fix_2'],
                    'files_modified': 3,
                    'message': 'Simulated fix completed'
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing task {task.request_id}: {e}")
            raise
        finally:
            execution_time = (time.time() - start_time) * 1000
            logger.info(f"Task {task.request_id} processed in {execution_time:.2f}ms")
    
    async def _handle_task_completion(self, future, task: TaskInfo, worker_id: str):
        """Handle task completion"""
        try:
            result = await asyncio.get_event_loop().run_in_executor(None, future.result)
            
            # Calculate execution time
            execution_time = 0.0
            if task.started_at:
                execution_time = (datetime.now() - task.started_at).total_seconds() * 1000
            
            # Update task status
            with self._lock:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                
                self._stats.processing_tasks -= 1
                self._stats.completed_tasks += 1
                
                # Update average processing time
                total_completed = self._stats.completed_tasks
                current_avg = self._stats.average_processing_time_ms
                self._stats.average_processing_time_ms = (
                    (current_avg * (total_completed - 1) + execution_time) / total_completed
                )
            
            # Create success response
            response = FixResponse.completed(task.request_id, result, execution_time)
            self._task_responses[task.request_id] = response
            
            logger.info(f"Task {task.request_id} completed successfully")
            
        except Exception as e:
            # Handle task failure
            with self._lock:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                
                self._stats.processing_tasks -= 1
                self._stats.failed_tasks += 1
            
            # Create error response
            response = FixResponse.failed(task.request_id, str(e))
            self._task_responses[task.request_id] = response
            
            logger.error(f"Task {task.request_id} failed: {e}")
        
        finally:
            # Free up worker
            worker = self._workers.get(worker_id)
            if worker:
                worker.status = 'idle'
                worker.current_task = None
                worker.tasks_processed += 1
                worker.last_heartbeat = datetime.now() 