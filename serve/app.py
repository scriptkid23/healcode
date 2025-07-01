"""
FastAPI application for code fix service
"""

import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .models import FixRequest, FixResponse, TaskStatus, QueueStats, TaskInfo
from .queue_manager import QueueManager
from .task_processor import TaskProcessor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global queue manager
queue_manager: Optional[QueueManager] = None
task_processor: Optional[TaskProcessor] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    global queue_manager, task_processor
    
    # Startup
    logger.info("Starting code fix service...")
    
    # Initialize queue manager
    queue_manager = QueueManager(max_workers=4, max_queue_size=1000)
    
    # Initialize task processor
    task_processor = TaskProcessor()
    
    # Register task processor with queue manager
    queue_manager.add_task_handler(task_processor.process_fix_request)
    
    # Start queue manager
    await queue_manager.start()
    
    logger.info("Code fix service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down code fix service...")
    
    if queue_manager:
        await queue_manager.stop()
    
    logger.info("Code fix service stopped")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="Code Fix Service",
        description="API for automated code fixing using AI",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure as needed
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app


app = create_app()


# Pydantic models for API
class FixRequestModel(BaseModel):
    """API model for fix requests"""
    repo_name: str = Field(..., description="Repository name")
    trace_error: str = Field(..., description="Error trace to fix")
    priority: int = Field(1, ge=1, le=5, description="Priority (1=highest, 5=lowest)")
    metadata: Optional[Dict] = Field(default_factory=dict, description="Additional metadata")


class FixResponseModel(BaseModel):
    """API model for fix responses"""
    request_id: str
    status: str
    message: str
    result: Optional[Dict] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time_ms: Optional[float] = None


def get_queue_manager() -> QueueManager:
    """Dependency to get queue manager"""
    if queue_manager is None:
        raise HTTPException(status_code=500, detail="Queue manager not initialized")
    return queue_manager


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint"""
    return {"message": "Code Fix Service API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}


@app.post("/api/fix/{repo}", response_model=FixResponseModel, tags=["Fix"])
async def submit_fix_request(
    repo: str,
    request: FixRequestModel,
    queue_mgr: QueueManager = Depends(get_queue_manager)
) -> FixResponseModel:
    """
    Submit a code fix request
    
    Args:
        repo: Repository name (path parameter)
        request: Fix request details
        
    Returns:
        Fix response with request ID and status
    """
    try:
        # Create FixRequest from API model
        fix_request = FixRequest(
            repo_name=repo,
            trace_error=request.trace_error,
            priority=request.priority,
            metadata=request.metadata or {}
        )
        
        # Submit to queue
        response = await queue_mgr.submit_task(fix_request)
        
        # Convert to API model
        return FixResponseModel(
            request_id=response.request_id,
            status=response.status.value,
            message=response.message,
            result=response.result,
            error=response.error,
            started_at=response.started_at.isoformat() if response.started_at else None,
            completed_at=response.completed_at.isoformat() if response.completed_at else None,
            execution_time_ms=response.execution_time_ms
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting fix request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/fix/{repo}/status/{request_id}", response_model=FixResponseModel, tags=["Fix"])
async def get_fix_status(
    repo: str,
    request_id: str,
    queue_mgr: QueueManager = Depends(get_queue_manager)
) -> FixResponseModel:
    """
    Get status of a fix request
    
    Args:
        repo: Repository name
        request_id: Request ID
        
    Returns:
        Current status of the fix request
    """
    response = queue_mgr.get_task_status(request_id)
    
    if response is None:
        raise HTTPException(status_code=404, detail="Request not found")
    
    return FixResponseModel(
        request_id=response.request_id,
        status=response.status.value,
        message=response.message,
        result=response.result,
        error=response.error,
        started_at=response.started_at.isoformat() if response.started_at else None,
        completed_at=response.completed_at.isoformat() if response.completed_at else None,
        execution_time_ms=response.execution_time_ms
    )


@app.delete("/api/fix/{repo}/cancel/{request_id}", tags=["Fix"])
async def cancel_fix_request(
    repo: str,
    request_id: str,
    queue_mgr: QueueManager = Depends(get_queue_manager)
):
    """
    Cancel a pending fix request
    
    Args:
        repo: Repository name
        request_id: Request ID to cancel
        
    Returns:
        Cancellation result
    """
    success = queue_mgr.cancel_task(request_id)
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail="Cannot cancel request (not found or not pending)"
        )
    
    return {"message": "Request cancelled successfully", "request_id": request_id}


@app.get("/api/queue/stats", tags=["Queue"])
async def get_queue_stats(
    queue_mgr: QueueManager = Depends(get_queue_manager)
) -> Dict:
    """Get queue statistics"""
    stats = queue_mgr.get_queue_stats()
    
    return {
        "total_tasks": stats.total_tasks,
        "pending_tasks": stats.pending_tasks,
        "processing_tasks": stats.processing_tasks,
        "completed_tasks": stats.completed_tasks,
        "failed_tasks": stats.failed_tasks,
        "active_workers": stats.active_workers,
        "average_processing_time_ms": stats.average_processing_time_ms
    }


@app.get("/api/queue/tasks", tags=["Queue"])
async def get_all_tasks(
    status: Optional[str] = None,
    queue_mgr: QueueManager = Depends(get_queue_manager)
) -> List[Dict]:
    """
    Get all tasks, optionally filtered by status
    
    Args:
        status: Optional status filter (pending, processing, completed, failed)
        
    Returns:
        List of tasks
    """
    tasks = queue_mgr.get_all_tasks()
    
    # Filter by status if provided
    if status:
        try:
            status_enum = TaskStatus(status.lower())
            tasks = [task for task in tasks if task.status == status_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    # Convert to dict for JSON response
    result = []
    for task in tasks:
        result.append({
            "request_id": task.request_id,
            "repo_name": task.repo_name,
            "status": task.status.value,
            "priority": task.priority,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "worker_id": task.worker_id,
            "retry_count": task.retry_count,
            "progress": task.progress
        })
    
    return result


@app.get("/api/repos/{repo}/tasks", tags=["Repository"])
async def get_repo_tasks(
    repo: str,
    status: Optional[str] = None,
    queue_mgr: QueueManager = Depends(get_queue_manager)
) -> List[Dict]:
    """
    Get tasks for a specific repository
    
    Args:
        repo: Repository name
        status: Optional status filter
        
    Returns:
        List of tasks for the repository
    """
    all_tasks = queue_mgr.get_all_tasks()
    
    # Filter by repo
    repo_tasks = [task for task in all_tasks if task.repo_name == repo]
    
    # Filter by status if provided
    if status:
        try:
            status_enum = TaskStatus(status.lower())
            repo_tasks = [task for task in repo_tasks if task.status == status_enum]
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    # Convert to dict for JSON response
    result = []
    for task in repo_tasks:
        result.append({
            "request_id": task.request_id,
            "status": task.status.value,
            "priority": task.priority,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "worker_id": task.worker_id,
            "retry_count": task.retry_count,
            "progress": task.progress,
            "trace_error": task.trace_error[:200] + "..." if len(task.trace_error) > 200 else task.trace_error
        })
    
    return result


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "status_code": 500}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 