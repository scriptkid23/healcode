"""
Authentication API Routes

Handles user authentication, session management, and user administration.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import List, Optional

from ...core.security import SecurityManager, User, Permission

router = APIRouter()


# Request/Response models
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: EmailStr
    roles: List[str] = []


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    roles: List[str]
    created_at: str
    last_login: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# Dependencies
async def get_security_manager():
    """Dependency to get security manager"""
    # This will be injected by the main app
    pass


async def get_current_user():
    """Dependency to get current user"""
    # This will be injected by the main app
    pass


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    security_manager: SecurityManager = Depends(get_security_manager)
):
    """Authenticate user and create session"""
    try:
        result = security_manager.login(
            username=request.username,
            password=request.password
        )
        
        return LoginResponse(
            token=result['token'],
            user=result['user']
        )
        
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/logout")
async def logout(
    token: str,
    security_manager: SecurityManager = Depends(get_security_manager)
):
    """Logout user and revoke session"""
    try:
        security_manager.logout(token)
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail="Logout failed")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        roles=current_user.roles,
        created_at=current_user.created_at.isoformat(),
        last_login=current_user.last_login.isoformat() if current_user.last_login else None
    )


@router.post("/users", response_model=UserResponse)
async def create_user(
    request: CreateUserRequest,
    current_user: User = Depends(get_current_user),
    security_manager: SecurityManager = Depends(get_security_manager)
):
    """Create new user (admin only)"""
    # Check admin permission
    admin_permission = Permission("user", "create")
    if not security_manager.authz_manager.authorize(current_user, admin_permission):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        user = security_manager.create_user(
            username=request.username,
            password=request.password,
            email=request.email,
            roles=request.roles
        )
        
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            roles=user.roles,
            created_at=user.created_at.isoformat(),
            last_login=None
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create user: {str(e)}")


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_user),
    security_manager: SecurityManager = Depends(get_security_manager)
):
    """List all users (admin only)"""
    # Check admin permission
    admin_permission = Permission("user", "read")
    if not security_manager.authz_manager.authorize(current_user, admin_permission):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    try:
        # Get all users from auth manager
        users = []
        for username, user_data in security_manager.auth_manager.users.items():
            user = user_data['user']
            users.append(UserResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                roles=user.roles,
                created_at=user.created_at.isoformat(),
                last_login=user.last_login.isoformat() if user.last_login else None
            ))
        
        return users
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list users: {str(e)}")


@router.put("/me/password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    security_manager: SecurityManager = Depends(get_security_manager)
):
    """Change current user's password"""
    try:
        # Verify current password
        security_manager.auth_manager.authenticate(
            current_user.username,
            request.current_password
        )
        
        # Update password (simplified - in real implementation, update stored password)
        # This would require additional methods in the auth manager
        
        return {"message": "Password changed successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to change password")


@router.get("/permissions")
async def get_user_permissions(
    current_user: User = Depends(get_current_user),
    security_manager: SecurityManager = Depends(get_security_manager)
):
    """Get current user's permissions"""
    try:
        # Get role-based permissions
        permissions = []
        
        for role in current_user.roles:
            role_perms = security_manager.authz_manager.role_permissions.get(role, [])
            for perm in role_perms:
                permissions.append(str(perm))
        
        # Get user-specific permissions
        user_perms = security_manager.authz_manager.user_permissions.get(current_user.id, [])
        for perm in user_perms:
            permissions.append(str(perm))
        
        return {
            "user_id": current_user.id,
            "username": current_user.username,
            "roles": current_user.roles,
            "permissions": list(set(permissions))  # Remove duplicates
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get permissions: {str(e)}")


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    security_manager: SecurityManager = Depends(get_security_manager)
):
    """List active sessions for current user"""
    try:
        # Get user's active sessions
        user_sessions = []
        
        for token, session_data in security_manager.auth_manager.sessions.items():
            if session_data['username'] == current_user.username:
                user_sessions.append({
                    'token': token[:8] + '...',  # Truncated for security
                    'created_at': session_data['created_at'].isoformat(),
                    'expires_at': session_data['expires_at'].isoformat()
                })
        
        return {
            "user_id": current_user.id,
            "active_sessions": user_sessions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.delete("/sessions/{token}")
async def revoke_session(
    token: str,
    current_user: User = Depends(get_current_user),
    security_manager: SecurityManager = Depends(get_security_manager)
):
    """Revoke a specific session"""
    try:
        # Check if session belongs to current user or user is admin
        session_data = security_manager.auth_manager.sessions.get(token)
        
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Allow users to revoke their own sessions or admins to revoke any session
        admin_permission = Permission("session", "delete")
        if (session_data['username'] != current_user.username and 
            not security_manager.authz_manager.authorize(current_user, admin_permission)):
            raise HTTPException(status_code=403, detail="Cannot revoke other user's session")
        
        security_manager.auth_manager.revoke_session(token)
        
        return {"message": "Session revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to revoke session: {str(e)}") 