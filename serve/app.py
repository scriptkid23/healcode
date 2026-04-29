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
from .database import (
    create_repositorie,
    fetchdata,
    get_local_path_by_id,
    get_or_create_user,
    get_repo_by_id,
    get_repo_by_id_and_url,
    get_repo_current,
    get_username_by_id,
    set_repo_current,
)
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


class GitRepoSelectionRequest(BaseModel):
    git_url: str


class GitBranchSwitchRequest(BaseModel):
    branch: str


class FixRequestModel(BaseModel):
    """API model for fix requests"""
    trace_error: str = Field(..., description="Error trace to fix")
    priority: int = Field(1, ge=1, le=5, description="Priority (1=highest, 5=lowest)")
    metadata: Optional[Dict] = Field(default_factory=dict, description="Additional metadata")


class FixResponseModel(BaseModel):
    """API model for fix responses"""
    request_id: str
    branche: str
    pr_url: str
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

@app.get("/api/credential/token", tags=['Credential'])
async def get_credential_token(user_uuid: str = Depends(get_current_user)):
    # Goi API lay credentials (tra ve dang hash map / dict)
    credentials = await base_api(apis["gitplugin"]["credentials"]["list"])
    print(credentials)
    
    user_token = None
    if isinstance(credentials, dict):
        # Truong hop 1: Key cua hash map chinh la name (user_uuid)
        if user_uuid in credentials:
            user_token = credentials[user_uuid]
        else:
            # Truong hop 2: Key la id ngau nhien, nam trong value
            for value in credentials.values():
                if isinstance(value, dict) and value.get("name") == user_uuid:
                    user_token = value
                    break
                    
    if not user_token:
        raise BusinessLogicError(code=404, message="Khong tim thay token cho nguoi dung nay")
        
    return api_response(user_token)


@app.post("/api/credential/token", tags=['Credential'])
async def credential_token(body: TokenResquest, user_uuid: str = Depends(get_current_user)):
    # 1. Goi api xoa credential hien tai truoc (truyen path_params)
    try:
        await base_api(
            apis["gitplugin"]["credentials"]["delete"], 
            path_params={"name": user_uuid}
        )
    except Exception:
        # Neu tai khoan chua tung tao token, api xoa co the tra ve loi -> Bo qua
        pass

    # 2. Tao credential moi
    data = {
        "name": user_uuid, # type: ignore
        "type": "token",
        "token": body.token,
        "username": get_username_by_id(user_uuid), # type: ignore
        "password": "string"
    }
    
    await base_api(apis["gitplugin"]["credentials"]["create"], body=data)
    return api_response(user_uuid)

@app.get("/api/credential/me", tags=["Credential"])
async def profile(user_uuid: str = Depends(get_current_user)):
    return api_response({})

@app.post("/api/git/repo", tags=["Git"])
async def repo(request: RepoRequest, user_uuid: str = Depends(get_current_user)):
    # 1. Chuan hoa URL de tranh trung lap (bo .git va khoang trang)
    url = request.url.removesuffix(".git")
    
    # 2. Kiem tra xem DB da luu repo nay cho user nay chua
    # Gia su ban co ham get_repo_by_url trong database.py
    existing_repo = get_repo_by_id_and_url(user_uuid, url)

    if existing_repo:
        # Neu da ton tai trong DB, lay luon path cu
        workspace_path = existing_repo['local_path']
        logger.info(f"Repo found in DB: {url}")
    else:
        # Neu chua co, moi tao hash va path moi
        repo_hash = hashlib.md5(url.encode()).hexdigest()
        workspace_path = f"codebase/{user_uuid}/{repo_hash}"
    
    try:
        # 3. Kiem tra trang thai vat ly cua repo[cite: 5]
        await base_api(
            apis["gitplugin"]["git"]["status"], 
            params={"workspace_path": workspace_path}
        )
        
        logger.info(f"Repository physical files exist. Pulling changes...")
        await base_api(
            apis["gitplugin"]["git"]["pull"], 
            params={"workspace_path": workspace_path}
        )
    
    except Exception:
        # 4. Neu khong thay file vat ly, tien hanh setup moi
        logger.info(f"Physical files not found. Setting up at {workspace_path}...")
        setup_data = {
            "repo_url": url,
            "credential_name": user_uuid,
            "workspace_path": workspace_path
        }
        await base_api(apis["gitplugin"]["git"]["setup"], body=setup_data)
        
        # 5. Chi luu vao DB neu truoc do chua co ban ghi
        if not existing_repo:
            create_repositorie(user_uuid, url, workspace_path) #[cite: 4]

    # 6. Thuc hien switch branch neu co yeu cau
    if request.branch:
        try:
            await base_api(
                apis["gitplugin"]["git"]["branch_switch"], 
                body={"workspace_path": workspace_path, "branch_name": request.branch}
            )
        except Exception:
            raise BusinessLogicError(
                code=404, 
                message=f"Branch '{request.branch}' does not exist."
            )

    set_repo_current(user_uuid, url) # Luu trang thai repo dang lam viec[cite: 4]
    return api_response({
        "message": "Repository synchronized successfully.",
        "local_path": workspace_path
    })

@app.get("/api/git/repo", tags=["Git"])
async def list_repos(user_uuid: str = Depends(get_current_user)):
    return api_response(get_repo_by_id(user_uuid))


@app.put("/api/git/repo", tags=["Git"])
async def update_current_repos(
    body: GitRepoSelectionRequest,
    user_uuid: str = Depends(get_current_user)
) -> Dict[str, Any]:
    current_repo = set_repo_current(user_uuid, body.git_url.removesuffix(".git"))
    if not current_repo:
        raise BusinessLogicError(code=400, message="Unable to update current repository.")

    return api_response(
        data = body.git_url.removesuffix(".git"),
        message="Current repository updated successfully"
    )

@app.put("/api/git/branche", tags=["Git"])
async def switch_git_branch(
    body: GitBranchSwitchRequest,
    user_uuid: str = Depends(get_current_user)
) -> Dict[str, Any]:
    selected_git_url = get_repo_current(user_uuid)
    workspace_path = get_local_path_by_id(user_uuid)
    if not selected_git_url or not workspace_path:
        raise BusinessLogicError(
            code=400,
            message="No current repository selected. Call PUT /api/git/repo first."
        )
    try:
        checkout = await base_api(
            apis["gitplugin"]["git"]["branch_switch"],
            body={"workspace_path": workspace_path, "branch_name": body.branch}
        )
        print(checkout)
    except Exception:
        raise BusinessLogicError(
            code=404,
            message=f"Branch '{body.branch}' does not exist or is not accessible."
        )

    git_status = await base_api(
        apis["gitplugin"]["git"]["status"],
        params={"workspace_path": workspace_path}
    )

    return api_response(
        data = {
            "git_url": selected_git_url.removesuffix(".git"),
            "branch": git_status.get("branch", body.branch)
        },
        message = "Branch switched successfully"
    )


@app.get("/api/git/status", tags=["Git"])
async def git_where(
    user_uuid: str = Depends(get_current_user)
) -> Dict[str, Any]:
    selected_git_url = get_repo_current(user_uuid)
    workspace_path = get_local_path_by_id(user_uuid)

    if not selected_git_url or not workspace_path:
        raise BusinessLogicError(
            code=400,
            message="No current repository selected. Call PUT /api/git/repo first."
        )

    git_status = await base_api(
        apis["gitplugin"]["git"]["status"],
        params={"workspace_path": workspace_path}
    )

    return api_response(
        {
            "git_url": selected_git_url.removesuffix(".git"),
            "branch": git_status.get("branch", "unknown"),
            "commit": git_status.get("commit", "No commited"),
            "message": git_status.get("commit_message", "No message"),
        }
    )

@app.post("/api/fix", tags=["Fix"])
async def submit_fix_request(
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
    current_repo_url = get_repo_current(user_uuid)
    workspace_path = get_local_path_by_id(user_uuid)
    print(workspace_path)
    if not workspace_path:
        raise HTTPException(status_code=400, detail="Current repo is invalid or workspace not found")
    if not current_repo_url:
        raise HTTPException(status_code=400, detail="Current repo is not selected")

    branche = str(uuid.uuid4())
    
    # Get current status to keep the original branch
    git_status = await base_api(
        apis["gitplugin"]["git"]["status"], 
        params={"workspace_path": workspace_path}
    )
    original_branch = git_status.get("branch", "main")
    
    # Pull the latest code from the current branch
    await base_api(
        apis["gitplugin"]["git"]["pull"], 
        params={"workspace_path": workspace_path}
    )
    
    # Create a new branch and switch to it
    await base_api(
        apis["gitplugin"]["git"]["branch_create"], 
        body={
            "workspace_path": workspace_path, 
            "branch_name": branche, 
            "checkout": True
        }
    )
    
    # Create FixRequest from API model
    fix_request = FixRequest(
        user_id=user_uuid,
        repo_name=current_repo_url, # type: ignore
        path=workspace_path, # type: ignore
        trace_error=request.trace_error,
        priority=request.priority,
        metadata=request.metadata or {}
    )
    
    # Submit to queue
    response = await queue_mgr.submit_task(fix_request)
    pr = {}
    if response.status == TaskStatus.COMPLETED:
        # Commit modified files
        await base_api(
            apis["gitplugin"]["git"]["commit"], 
            body={
                "workspace_path": workspace_path,
                "message": "Automated fix applied",
                "files": ["*"] # Commit all changes
            }
        )
        await base_api(
            apis["gitplugin"]["git"]["push"], 
            body={
                "workspace_path": workspace_path,
                "branch": branche
            }
        )
        # Create pull request
        pr = await base_api(
            apis["gitplugin"]["git"]["pull_request"], 
            body={
                "repo_url": current_repo_url,
                "credential_name": user_uuid,
                "source_branch": branche,
                "target_branch": original_branch,
                "title": f"Auto-fix for {current_repo_url}",
                "description": f"Automated fix for error:\n{trace_error}"
            }
        )

    print(pr)
    await base_api(
        apis["gitplugin"]["git"]["branch_switch"], 
        body={
            "workspace_path": workspace_path,
            "branch_name": original_branch
        }
    )
    queue_mgr.update_response(response.request_id, pr.get("pr_url", ""), branche)
    
    payload = FixResponseModel(
        request_id=response.request_id,
        branche=branche,
        pr_url=pr.get("pr_url", ""),
        status=response.status.value,
        message=response.message,
        result=response.result,
        error=response.error,
        started_at=response.started_at.isoformat() if response.started_at else None,
        completed_at=response.completed_at.isoformat() if response.completed_at else None,
        execution_time_ms=response.execution_time_ms
    )
    return api_response(payload.model_dump())


@app.get("/api/fix/status/{request_id}", tags=["Fix"])
async def get_fix_status(
    request_id: str,
    queue_mgr: QueueManager = Depends(get_queue_manager),
    user_uuid: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get status of a fix request
    
    Args:
        request_id: Request ID
        
    Returns:
        Current status of the fix request
    """
    response = queue_mgr.get_task_status(request_id)
    
    if response is None:
        raise HTTPException(status_code=404, detail="Request not found")
    
    payload = FixResponseModel(
        request_id=response.request_id,
        branche=response.branche,
        pr_url=response.pr_url,
        status=response.status.value,
        message=response.message,
        result=response.result,
        error=response.error,
        started_at=response.started_at.isoformat() if response.started_at else None,
        completed_at=response.completed_at.isoformat() if response.completed_at else None,
        execution_time_ms=response.execution_time_ms
    )
    return api_response(payload.model_dump())

@app.delete("/api/fix/cancel/{request_id}", tags=["Fix"])
async def cancel_fix_request(
    request_id: str,
    queue_mgr: QueueManager = Depends(get_queue_manager),
    user_uuid: str = Depends(get_current_user),
):
    """
    Cancel a pending fix request
    
    Args:
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
            tasks = [task for task in tasks if task.status == status_enum and task.user_id == user_uuid]
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


@app.get("/api/repos/tasks", tags=["Repository"])
async def get_repo_tasks(
    status: Optional[str] = None,
    queue_mgr: QueueManager = Depends(get_queue_manager),
    user_uuid: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get tasks for a specific repository
    
    Args:
        status: Optional status filter
        
    Returns:
        List of tasks for the repository
    """
    all_tasks = queue_mgr.get_all_tasks()
    
    current_repo_url = get_repo_current(user_uuid)
    if not current_repo_url:
        raise HTTPException(status_code=400, detail="Current repo is not selected")

    # Filter by current repo
    repo_tasks = [task for task in all_tasks if task.repo_name == current_repo_url]
    
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
