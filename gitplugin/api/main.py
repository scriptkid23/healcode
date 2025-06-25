"""
Optimized Git Plugin API with Enhanced GitPython Integration

Enhanced FastAPI application with additional Git operations:
- Repository status and management
- Branch operations
- Better error handling
- More detailed responses
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Optional, Any, List

from ..core.credentials import CredentialsManager
from ..core.git_operations import GitOperationsEngine


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global instances
credentials_manager = None
git_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global credentials_manager, git_engine
    
    # Startup
    logger.info("Starting Enhanced Git Plugin API...")
    credentials_manager = CredentialsManager()
    git_engine = GitOperationsEngine()
    logger.info("API started successfully with GitPython optimization")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Git Plugin API...")


# FastAPI app
app = FastAPI(
    title="Enhanced Git Plugin API",
    description="Optimized Git Plugin with advanced GitPython integration",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class CredentialCreate(BaseModel):
    name: str
    type: str  # "token" or "username_password"
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class RepositorySetup(BaseModel):
    repo_url: str
    credential_name: str
    workspace_path: str


class CommitRequest(BaseModel):
    workspace_path: str
    message: str
    files: Optional[List[str]] = None


class PushRequest(BaseModel):
    workspace_path: str
    branch: str = "main"


class PullRequestCreate(BaseModel):
    repo_url: str
    credential_name: str
    source_branch: str
    target_branch: str = "main"
    title: Optional[str] = ""
    description: Optional[str] = ""


class BranchRequest(BaseModel):
    workspace_path: str
    branch_name: str
    checkout: bool = True


class BranchSwitchRequest(BaseModel):
    workspace_path: str
    branch_name: str


# Dependency injection
def get_credentials_manager() -> CredentialsManager:
    return credentials_manager


def get_git_engine() -> GitOperationsEngine:
    return git_engine


# Health check
@app.get("/health")
async def health_check():
    """Enhanced health check endpoint"""
    return {
        "status": "healthy", 
        "message": "Enhanced Git Plugin API is running",
        "version": "2.0.0",
        "features": ["GitPython optimization", "Branch management", "Enhanced status"]
    }


# Credentials endpoints
@app.post("/credentials")
async def create_credential(
    credential: CredentialCreate,
    creds_manager: CredentialsManager = Depends(get_credentials_manager)
):
    """Create new credential"""
    try:
        kwargs = {}
        if credential.token:
            kwargs["token"] = credential.token
        if credential.username:
            kwargs["username"] = credential.username
        if credential.password:
            kwargs["password"] = credential.password
        
        result = creds_manager.add_credential(
            credential.name, 
            credential.type, 
            **kwargs
        )
        
        return {"status": "success", "credential_name": result}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/credentials")
async def list_credentials(
    creds_manager: CredentialsManager = Depends(get_credentials_manager)
):
    """List all credentials"""
    return creds_manager.list_credentials()


@app.delete("/credentials/{name}")
async def delete_credential(
    name: str,
    creds_manager: CredentialsManager = Depends(get_credentials_manager)
):
    """Delete credential"""
    success = creds_manager.remove_credential(name)
    if success:
        return {"status": "success", "message": f"Credential '{name}' deleted"}
    else:
        raise HTTPException(status_code=404, detail="Credential not found")


# Git operations endpoints
@app.post("/git/setup")
async def setup_repository(
    setup: RepositorySetup,
    git_engine: GitOperationsEngine = Depends(get_git_engine),
    creds_manager: CredentialsManager = Depends(get_credentials_manager)
):
    """Setup Git repository with enhanced GitPython"""
    try:
        # Get credential
        credential = creds_manager.get_credential(setup.credential_name)
        if not credential:
            raise HTTPException(status_code=404, detail="Credential not found")
        
        # Setup repository
        workspace_path = await git_engine.setup_repository(
            setup.repo_url, 
            credential, 
            setup.workspace_path
        )
        
        return {
            "status": "success",
            "message": "Repository setup completed with GitPython optimization",
            "workspace_path": workspace_path
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/git/pull")
async def pull_changes(
    workspace_path: str,
    git_engine: GitOperationsEngine = Depends(get_git_engine)
):
    """Pull latest changes with detailed information"""
    try:
        result = await git_engine.pull_changes(workspace_path)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/git/commit")
async def commit_changes(
    commit_req: CommitRequest,
    git_engine: GitOperationsEngine = Depends(get_git_engine)
):
    """Commit changes with enhanced file handling"""
    try:
        result = await git_engine.commit_changes(
            commit_req.workspace_path,
            commit_req.message,
            commit_req.files
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/git/push")
async def push_changes(
    push_req: PushRequest,
    git_engine: GitOperationsEngine = Depends(get_git_engine)
):
    """Push changes with detailed feedback"""
    try:
        result = await git_engine.push_changes(
            push_req.workspace_path,
            push_req.branch
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/git/pull-request")
async def create_pull_request(
    pr_req: PullRequestCreate,
    git_engine: GitOperationsEngine = Depends(get_git_engine),
    creds_manager: CredentialsManager = Depends(get_credentials_manager)
):
    """Create pull request"""
    try:
        # Get credential
        credential = creds_manager.get_credential(pr_req.credential_name)
        if not credential:
            raise HTTPException(status_code=404, detail="Credential not found")
        
        # Create PR
        result = await git_engine.create_pull_request(
            pr_req.repo_url,
            credential,
            pr_req.source_branch,
            pr_req.target_branch,
            pr_req.title,
            pr_req.description
        )
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/git/status")
async def get_repository_status(
    workspace_path: str,
    git_engine: GitOperationsEngine = Depends(get_git_engine)
):
    """Get comprehensive repository status"""
    try:
        result = await git_engine.get_repository_status(workspace_path)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Branch management endpoints
@app.post("/git/branch/create")
async def create_branch(
    branch_req: BranchRequest,
    git_engine: GitOperationsEngine = Depends(get_git_engine)
):
    """Create new branch"""
    try:
        result = await git_engine.create_branch(
            branch_req.workspace_path,
            branch_req.branch_name,
            branch_req.checkout
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/git/branch/switch")
async def switch_branch(
    switch_req: BranchSwitchRequest,
    git_engine: GitOperationsEngine = Depends(get_git_engine)
):
    """Switch to existing branch"""
    try:
        result = await git_engine.switch_branch(
            switch_req.workspace_path,
            switch_req.branch_name
        )
        return result
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Enhanced workflow endpoint
@app.post("/git/workflow/complete")
async def complete_git_workflow(
    repo_url: str,
    credential_name: str,
    workspace_path: str,
    commit_message: str,
    branch_name: str = "feature-branch",
    target_branch: str = "main",
    pr_title: Optional[str] = None,
    pr_description: Optional[str] = None,
    git_engine: GitOperationsEngine = Depends(get_git_engine),
    creds_manager: CredentialsManager = Depends(get_credentials_manager)
):
    """Complete workflow: setup -> create branch -> commit -> push -> create PR"""
    try:
        # Get credential
        credential = creds_manager.get_credential(credential_name)
        if not credential:
            raise HTTPException(status_code=404, detail="Credential not found")
        
        workflow_results = []
        
        # 1. Setup repository
        setup_result = await git_engine.setup_repository(repo_url, credential, workspace_path)
        workflow_results.append({"step": "setup", "result": setup_result})
        
        # 2. Create and switch to feature branch
        branch_result = await git_engine.create_branch(workspace_path, branch_name, True)
        workflow_results.append({"step": "create_branch", "result": branch_result})
        
        # 3. Commit changes (if any)
        commit_result = await git_engine.commit_changes(workspace_path, commit_message)
        workflow_results.append({"step": "commit", "result": commit_result})
        
        # 4. Push changes
        push_result = await git_engine.push_changes(workspace_path, branch_name)
        workflow_results.append({"step": "push", "result": push_result})
        
        # 5. Create Pull Request
        pr_result = await git_engine.create_pull_request(
            repo_url, credential, branch_name, target_branch,
            pr_title or f"Feature: {branch_name}",
            pr_description or f"Automated PR for {branch_name}"
        )
        workflow_results.append({"step": "pull_request", "result": pr_result})
        
        return {
            "status": "success",
            "message": "Complete Git workflow executed successfully",
            "workflow_steps": workflow_results
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


def main():
    """Main entry point for Poetry script"""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main() 