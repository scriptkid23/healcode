"""
FastAPI application for code fix service
"""

import hashlib
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
import os
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .models import BusinessLogicError, FixRequest, TaskStatus
from .queue_manager import QueueManager
from .task_processor import TaskProcessor
from .database import create_repositorie, fetchdata, get_local_path_by_id, get_or_create_user, get_username_by_id
from .call_api import base_api, apis
import uuid

import jwt
from datetime import datetime, timedelta
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET", "")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 518400

security = HTTPBearer()

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_uuid: str = payload.get("uuid")
        if user_uuid is None:
            raise BusinessLogicError(code=401, message="Invalid token")
        return user_uuid
    except jwt.ExpiredSignatureError:
        raise BusinessLogicError(code=401, message="The token has expired")
    except jwt.PyJWTError:
        raise BusinessLogicError(code=401, message="Information cannot be verified.")
    

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global queue manager
queue_manager: Optional[QueueManager] = None
task_processor: Optional[TaskProcessor] = None

# Define where you want to store the repos locally
LOCAL_STORAGE_PATH = "./cloned_repos"



def api_response(data: Any = None, code: int = 200, status: bool = True, message: Optional[str] = None):
    response = {"status": status, "code": code, "data": data}
    if message is not None:
        response["message"] = message
    return response

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
    app = FastAPI(
        title="Code Fix Service",
        description="API for automated code fixing using AI",
        version="1.0.0",
        lifespan=lifespan
    )
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.exception_handler(BusinessLogicError)
    async def business_logic_exception_handler(request: Request, exc: BusinessLogicError):
        logging.warning(f"Business error at {request.url}: {exc.message}")
        return JSONResponse(
            status_code=exc.code,
            content=api_response(data=None, code=exc.code, status=False, message=exc.message)
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logging.warning(f"HTTP error at {request.url}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content=api_response(
                data=None,
                code=exc.status_code,
                status=False,
                message=str(exc.detail)
            )
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logging.error(f"Unhandled exception at {request.url}: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=api_response(
                data=None,
                code=500,
                status=False,
                message="An internal system error occurred."
            )
        )    
    return app


app = create_app()

class RepoRequest(BaseModel):
    url: str
    branch: Optional[str] = "main"
class CredentialRequest(BaseModel):
    provider_id: str = "telegram"
    username: str = "duongess"

class TokenResquest(BaseModel):
    token: str
class FixRequestModel(BaseModel):
    """API model for fix requests"""
    repo_url: str = Field(..., description="Repository url")
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
    fetchdata()
    """Root endpoint"""
    return api_response({"app": "Code Fix Service API", "version": "1.0.0"})


@app.get("/health", tags=["Health"])
async def health():
    """Health check endpoint"""
    return api_response({"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"})


@app.post("/api/credential", tags=["Credential"])
async def credential (
    body: CredentialRequest
):
    user = get_or_create_user(body.provider_id, body.username)
    access_token = create_access_token(data={"uuid": user["id"]}) # type: ignore


    response = {
        "access_token": access_token,
        "token_type": "bearer"
    }
    return api_response(response)

@app.post("/api/credential/token", tags=['Credential'])
async def credential_token(body: TokenResquest, user_uuid: str = Depends(get_current_user)):
    data = {
        "name": user_uuid, # type: ignore
        "type": "token",
        "token": body.token,
        "username": get_username_by_id(user_uuid), # type: ignore
        "password": "string"
    }
    base_api(apis["gitplugin"]["credentials"]["create"], body=data)
    return api_response(user_uuid)

@app.get("/api/credential/me", tags=["Credential"])
async def profile(user_uuid: str = Depends(get_current_user)):
    return api_response({})

@app.post("/api/repo", tags=["Git"])
async def repo(request: RepoRequest, user_uuid: str = Depends(get_current_user)):
    repo_hash = hashlib.md5(request.url.encode()).hexdigest()
    workspace_path = f"codebase/{user_uuid}/{repo_hash}"
    print(user_uuid)
    try:
        base_api(
            apis["gitplugin"]["git"]["status"], 
            params={"workspace_path": workspace_path}
        )

        logger.info(f"Repository exists at {workspace_path}. Pulling changes...")
        base_api(
            apis["gitplugin"]["git"]["pull"], 
            params={"workspace_path": workspace_path}
        )
    
    except:
        logger.info(f"Repository not found. Setting up new repo from {request.url}...")
        setup_data = {
            "repo_url": request.url,
            "credential_name": user_uuid,
            "workspace_path": workspace_path
        }
        base_api(apis["gitplugin"]["git"]["setup"], body=setup_data)
        create_repositorie(user_uuid, request.url, workspace_path)

    if request.branch:
        try:
            switch_data = {
                "workspace_path": workspace_path,
                "branch_name": request.branch
            }
            base_api(apis["gitplugin"]["git"]["branch_switch"], body=switch_data)
            
        except Exception:
            raise BusinessLogicError(
                code=404, 
                message=f"Branch '{request.branch}' does not exist or is not accessible."
            )

    response = {
        "message": f"Repository synchronized successfully and switched to branch {request.branch or 'default'}.",
        "local_path": workspace_path
    }
    return api_response(response)

@app.get("/api/status", tags=["Git"])
async def status(queue_mgr: QueueManager = Depends(get_queue_manager), user_uuid: str = Depends(get_current_user)):
    """
    Returns the status of repositories currently held in local storage (has bug, fixing, update).
    """
    # 1. Check if storage directory exists
    if not os.path.exists(LOCAL_STORAGE_PATH):
        return api_response({"repos": [], "storage_root": None})

    # 2. Get list of physical folders (repositories)
    repo_dirs = [d for d in os.listdir(LOCAL_STORAGE_PATH) 
                 if os.path.isdir(os.path.join(LOCAL_STORAGE_PATH, d))]
    
    # 3. Get all tasks to cross-reference status
    all_tasks = queue_mgr.get_all_tasks()
    
    # Helper to find the latest status for a specific repo
    def get_repo_status(repo_name):
        # Filter tasks for this repo
        repo_tasks = [t for t in all_tasks if t.repo_name == repo_name]
        
        if not repo_tasks:
            return "idle" # No tasks ever run for this repo
            
        # Get the most recent task
        latest_task = sorted(repo_tasks, key=lambda x: x.created_at, reverse=True)[0]
        
        # Map TaskStatus to your requested terms
        if latest_task.status.value == "processing":
            return "fixing"
        elif latest_task.status.value == "pending":
            return "has bug" # It is in queue waiting to be fixed
        elif latest_task.status.value == "completed":
            return "update" # Fix completed, repo is updated
        elif latest_task.status.value == "failed":
            return "has bug" # Fix failed, likely still has bug
        else:
            return latest_task.status.value

    # 4. Build the result list
    results = []
    for repo in repo_dirs:
        results.append({
            "name": repo,
            "status": get_repo_status(repo),
            "path": os.path.abspath(os.path.join(LOCAL_STORAGE_PATH, repo))
        })

    return api_response({
        "count": len(results),
        "repos": results,
        "storage_root": os.path.abspath(LOCAL_STORAGE_PATH)
    })

@app.post("/api/fix/{repo}", tags=["Fix"])
async def submit_fix_request(
    repo: str,
    request: FixRequestModel,
    trace_error: str,
    queue_mgr: QueueManager = Depends(get_queue_manager),
    user_uuid: str = Depends(get_current_user)
) -> Dict[str, Any]:
    if request: 
        request.trace_error = trace_error
    """
    Submit a code fix request
    """
    workspace_path = get_local_path_by_id(user_uuid, request.repo_url)
    if not workspace_path:
        raise HTTPException(status_code=400, detail="User id Invalid or workspace not found")

    branche = str(uuid.uuid4())
    
    # Get current status to keep the original branch
    git_status = base_api(
        apis["gitplugin"]["git"]["status"], 
        params={"workspace_path": workspace_path}
    )
    original_branch = git_status.get("branch", "main")
    
    # Pull the latest code from the current branch
    base_api(
        apis["gitplugin"]["git"]["pull"], 
        params={"workspace_path": workspace_path}
    )
    
    # Create a new branch and switch to it
    base_api(
        apis["gitplugin"]["git"]["branch_create"], 
        body={
            "workspace_path": workspace_path, 
            "branch_name": branche, 
            "checkout": True
        }
    )
    
    # Create FixRequest from API model
    fix_request = FixRequest(
        repo_name=repo,
        path=workspace_path, # type: ignore
        trace_error=request.trace_error,
        priority=request.priority,
        metadata=request.metadata or {}
    )
    
    # Submit to queue
    response = await queue_mgr.submit_task(fix_request)
    print(response)
    if response.status == TaskStatus.COMPLETED:
        # Commit modified files
        base_api(
            apis["gitplugin"]["git"]["commit"], 
            body={
                "workspace_path": workspace_path,
                "message": "Automated fix applied",
                "files": ["*"] # Commit all changes
            }
        )
        base_api(
            apis["gitplugin"]["git"]["push"], 
            body={
                "workspace_path": workspace_path,
                "branch": branche
            }
        )
        # Create pull request
        base_api(
            apis["gitplugin"]["git"]["pull_request"], 
            body={
                "repo_url": request.repo_url,
                "credential_name": user_uuid,
                "source_branch": branche,
                "target_branch": original_branch,
                "title": f"Auto-fix for {repo}",
                "description": f"Automated fix for error:\n{trace_error}"
            }
        )

    base_api(
        apis["gitplugin"]["git"]["branch_switch"], 
        body={
            "workspace_path": workspace_path,
            "branch_name": original_branch
        }
    )
    
    payload = FixResponseModel(
        request_id=response.request_id,
        status=response.status.value,
        message=response.message,
        result=response.result,
        error=response.error,
        started_at=response.started_at.isoformat() if response.started_at else None,
        completed_at=response.completed_at.isoformat() if response.completed_at else None,
        execution_time_ms=response.execution_time_ms
    )
    return api_response(payload.model_dump())


@app.get("/api/fix/{repo}/status/{request_id}", tags=["Fix"])
async def get_fix_status(
    repo: str,
    request_id: str,
    queue_mgr: QueueManager = Depends(get_queue_manager),
    user_uuid: str = Depends(get_current_user)
) -> Dict[str, Any]:
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
    
    payload = FixResponseModel(
        request_id=response.request_id,
        status=response.status.value,
        message=response.message,
        result=response.result,
        error=response.error,
        started_at=response.started_at.isoformat() if response.started_at else None,
        completed_at=response.completed_at.isoformat() if response.completed_at else None,
        execution_time_ms=response.execution_time_ms
    )
    return api_response(payload.model_dump())


@app.delete("/api/fix/{repo}/cancel/{request_id}", tags=["Fix"])
async def cancel_fix_request(
    repo: str,
    request_id: str,
    queue_mgr: QueueManager = Depends(get_queue_manager),
    user_uuid: str = Depends(get_current_user),
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
    
    return api_response({"message": "Request cancelled successfully", "request_id": request_id})


@app.get("/api/queue/stats", tags=["Queue"])
async def get_queue_stats(
    queue_mgr: QueueManager = Depends(get_queue_manager),
    user_uuid: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get queue statistics"""
    stats = queue_mgr.get_queue_stats()
    
    return api_response({
        "total_tasks": stats.total_tasks,
        "pending_tasks": stats.pending_tasks,
        "processing_tasks": stats.processing_tasks,
        "completed_tasks": stats.completed_tasks,
        "failed_tasks": stats.failed_tasks,
        "active_workers": stats.active_workers,
        "average_processing_time_ms": stats.average_processing_time_ms
    })


@app.get("/api/queue/tasks", tags=["Queue"])
async def get_all_tasks(
    status: Optional[str] = None,
    queue_mgr: QueueManager = Depends(get_queue_manager),
    user_uuid: str = Depends(get_current_user),
) -> Dict[str, Any]:
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
    
    return api_response(result)


@app.get("/api/repos/{repo}/tasks", tags=["Repository"])
async def get_repo_tasks(
    repo: str,
    status: Optional[str] = None,
    queue_mgr: QueueManager = Depends(get_queue_manager),
    user_uuid: str = Depends(get_current_user),
) -> Dict[str, Any]:
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
    
    return api_response(result)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
