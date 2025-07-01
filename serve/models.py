"""
Data models for API requests and responses
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import uuid


class TaskStatus(Enum):
    """Status of a fix task"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class FixRequest:
    """Request model for code fix operations"""
    repo_name: str
    trace_error: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    priority: int = 1  # 1 = highest, 5 = lowest
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate request after initialization"""
        if not self.repo_name:
            raise ValueError("repo_name cannot be empty")
        if not self.trace_error:
            raise ValueError("trace_error cannot be empty")
        if not isinstance(self.priority, int) or self.priority < 1 or self.priority > 5:
            raise ValueError("priority must be an integer between 1 and 5")


@dataclass
class FixResponse:
    """Response model for fix operations"""
    request_id: str
    status: TaskStatus
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[float] = None
    
    @classmethod
    def pending(cls, request_id: str) -> 'FixResponse':
        """Create a pending response"""
        return cls(
            request_id=request_id,
            status=TaskStatus.PENDING,
            message="Task queued for processing"
        )
    
    @classmethod
    def processing(cls, request_id: str) -> 'FixResponse':
        """Create a processing response"""
        return cls(
            request_id=request_id,
            status=TaskStatus.PROCESSING,
            message="Task is being processed",
            started_at=datetime.now()
        )
    
    @classmethod
    def completed(cls, request_id: str, result: Dict[str, Any], 
                  execution_time_ms: float) -> 'FixResponse':
        """Create a completed response"""
        return cls(
            request_id=request_id,
            status=TaskStatus.COMPLETED,
            message="Task completed successfully",
            result=result,
            completed_at=datetime.now(),
            execution_time_ms=execution_time_ms
        )
    
    @classmethod
    def failed(cls, request_id: str, error: str) -> 'FixResponse':
        """Create a failed response"""
        return cls(
            request_id=request_id,
            status=TaskStatus.FAILED,
            message="Task failed",
            error=error,
            completed_at=datetime.now()
        )


@dataclass
class TaskInfo:
    """Information about a queued task"""
    request_id: str
    repo_name: str
    trace_error: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    priority: int = 1
    retry_count: int = 0
    max_retries: int = 3
    worker_id: Optional[str] = None
    progress: float = 0.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QueueStats:
    """Queue statistics"""
    total_tasks: int = 0
    pending_tasks: int = 0
    processing_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    active_workers: int = 0
    average_processing_time_ms: float = 0.0
    
    
@dataclass
class WorkerInfo:
    """Information about a task worker"""
    worker_id: str
    status: str  # idle, busy, stopped
    current_task: Optional[str] = None
    tasks_processed: int = 0
    last_heartbeat: Optional[datetime] = None
    started_at: datetime = field(default_factory=datetime.now) 