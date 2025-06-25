"""
Security Framework for Git Plugin System

Provides authentication, authorization, encryption, and audit logging capabilities.
"""

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os


class SecurityException(Exception):
    """Base security exception"""
    pass


class UnauthorizedException(SecurityException):
    """Raised when user is not authorized"""
    pass


class AuthenticationFailedException(SecurityException):
    """Raised when authentication fails"""
    pass


class EncryptionService:
    """Encryption service for sensitive data"""
    
    def __init__(self, master_key: Optional[str] = None):
        if master_key:
            self._key = master_key.encode()
        else:
            self._key = os.urandom(32)
        
        # Derive encryption key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'git_plugin_salt',
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self._key))
        self.fernet = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data"""
        if isinstance(data, str):
            data = data.encode()
        encrypted = self.fernet.encrypt(data)
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data"""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            raise SecurityException(f"Decryption failed: {e}")


class User:
    """User model"""
    
    def __init__(self, user_id: str, username: str, email: str, roles: List[str] = None):
        self.id = user_id
        self.username = username
        self.email = email
        self.roles = roles or []
        self.created_at = datetime.now()
        self.last_login = None
    
    def has_role(self, role: str) -> bool:
        """Check if user has specific role"""
        return role in self.roles
    
    def has_any_role(self, roles: List[str]) -> bool:
        """Check if user has any of the specified roles"""
        return any(role in self.roles for role in roles)


class AuthenticationManager:
    """Handles user authentication"""
    
    def __init__(self, encryption_service: EncryptionService):
        self.encryption = encryption_service
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.logger = logging.getLogger(__name__)
    
    def create_user(self, username: str, password: str, email: str, roles: List[str] = None) -> User:
        """Create a new user"""
        user_id = self._generate_user_id()
        password_hash = self._hash_password(password)
        
        user = User(user_id, username, email, roles)
        self.users[username] = {
            'user': user,
            'password_hash': password_hash
        }
        
        self.logger.info(f"User created: {username}")
        return user
    
    def authenticate(self, username: str, password: str) -> User:
        """Authenticate user with username/password"""
        if username not in self.users:
            raise AuthenticationFailedException("Invalid credentials")
        
        user_data = self.users[username]
        password_hash = self._hash_password(password)
        
        if not hmac.compare_digest(user_data['password_hash'], password_hash):
            raise AuthenticationFailedException("Invalid credentials")
        
        user = user_data['user']
        user.last_login = datetime.now()
        
        self.logger.info(f"User authenticated: {username}")
        return user
    
    def authenticate_token(self, token: str) -> User:
        """Authenticate user with session token"""
        session = self.sessions.get(token)
        if not session:
            raise AuthenticationFailedException("Invalid token")
        
        if session['expires_at'] < datetime.now():
            del self.sessions[token]
            raise AuthenticationFailedException("Token expired")
        
        username = session['username']
        user = self.users[username]['user']
        
        return user
    
    def create_session(self, user: User, expires_in_hours: int = 24) -> str:
        """Create session token for user"""
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=expires_in_hours)
        
        self.sessions[token] = {
            'username': user.username,
            'user_id': user.id,
            'created_at': datetime.now(),
            'expires_at': expires_at
        }
        
        return token
    
    def revoke_session(self, token: str):
        """Revoke session token"""
        if token in self.sessions:
            del self.sessions[token]
    
    def _generate_user_id(self) -> str:
        """Generate unique user ID"""
        return secrets.token_urlsafe(16)
    
    def _hash_password(self, password: str) -> str:
        """Hash password with salt"""
        salt = b'git_plugin_salt'
        return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000).hex()


class Permission:
    """Permission model"""
    
    def __init__(self, resource: str, action: str):
        self.resource = resource
        self.action = action
    
    def __str__(self):
        return f"{self.resource}:{self.action}"
    
    def __eq__(self, other):
        return self.resource == other.resource and self.action == other.action
    
    def __hash__(self):
        return hash((self.resource, self.action))


class AuthorizationManager:
    """Handles user authorization and permissions"""
    
    def __init__(self):
        self.role_permissions: Dict[str, List[Permission]] = {}
        self.user_permissions: Dict[str, List[Permission]] = {}
        self.logger = logging.getLogger(__name__)
        
        # Setup default roles
        self._setup_default_roles()
    
    def _setup_default_roles(self):
        """Setup default roles and permissions"""
        # Admin role - full access
        self.role_permissions['admin'] = [
            Permission('*', '*')
        ]
        
        # Developer role - repository and build access
        self.role_permissions['developer'] = [
            Permission('repository', 'read'),
            Permission('repository', 'write'),
            Permission('build', 'trigger'),
            Permission('build', 'read'),
            Permission('webhook', 'receive')
        ]
        
        # Viewer role - read-only access
        self.role_permissions['viewer'] = [
            Permission('repository', 'read'),
            Permission('build', 'read'),
            Permission('job', 'read')
        ]
    
    def authorize(self, user: User, required_permission: Permission) -> bool:
        """Check if user has required permission"""
        # Check if user has admin role (full access)
        if user.has_role('admin'):
            return True
        
        # Check role-based permissions
        for role in user.roles:
            role_perms = self.role_permissions.get(role, [])
            if self._has_permission(role_perms, required_permission):
                return True
        
        # Check user-specific permissions
        user_perms = self.user_permissions.get(user.id, [])
        if self._has_permission(user_perms, required_permission):
            return True
        
        self.logger.warning(f"Authorization denied for user {user.username}: {required_permission}")
        return False
    
    def _has_permission(self, permissions: List[Permission], required: Permission) -> bool:
        """Check if permission list contains required permission"""
        for perm in permissions:
            if (perm.resource == '*' or perm.resource == required.resource) and \
               (perm.action == '*' or perm.action == required.action):
                return True
        return False
    
    def grant_permission(self, user_id: str, permission: Permission):
        """Grant specific permission to user"""
        if user_id not in self.user_permissions:
            self.user_permissions[user_id] = []
        
        if permission not in self.user_permissions[user_id]:
            self.user_permissions[user_id].append(permission)
    
    def revoke_permission(self, user_id: str, permission: Permission):
        """Revoke specific permission from user"""
        if user_id in self.user_permissions:
            if permission in self.user_permissions[user_id]:
                self.user_permissions[user_id].remove(permission)


class AuditLogger:
    """Audit logging for security events"""
    
    def __init__(self):
        self.logger = logging.getLogger('security.audit')
        
        # Setup audit log handler
        handler = logging.FileHandler('logs/security_audit.log')
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_authentication(self, username: str, success: bool, ip_address: str = None):
        """Log authentication attempt"""
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(
            f"AUTH_{status} - User: {username} - IP: {ip_address or 'unknown'}"
        )
    
    def log_authorization(self, username: str, resource: str, action: str, success: bool):
        """Log authorization attempt"""
        status = "GRANTED" if success else "DENIED"
        self.logger.info(
            f"AUTHZ_{status} - User: {username} - Resource: {resource} - Action: {action}"
        )
    
    def log_credential_created(self, credential_id: str, user: User):
        """Log credential creation"""
        self.logger.info(
            f"CREDENTIAL_CREATED - ID: {credential_id} - User: {user.username}"
        )
    
    def log_credential_accessed(self, credential_id: str, user: User):
        """Log credential access"""
        self.logger.info(
            f"CREDENTIAL_ACCESSED - ID: {credential_id} - User: {user.username}"
        )
    
    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Log general security event"""
        self.logger.info(f"{event_type} - {details}")


class SecurityManager:
    """Central security management"""
    
    def __init__(self, master_key: Optional[str] = None):
        self.encryption = EncryptionService(master_key)
        self.auth_manager = AuthenticationManager(self.encryption)
        self.authz_manager = AuthorizationManager()
        self.audit = AuditLogger()
        self.logger = logging.getLogger(__name__)
    
    def validate_request(self, token: str, required_permission: Permission) -> User:
        """Validate request with authentication and authorization"""
        try:
            # Authenticate user
            user = self.auth_manager.authenticate_token(token)
            
            # Check authorization
            if not self.authz_manager.authorize(user, required_permission):
                self.audit.log_authorization(
                    user.username, 
                    required_permission.resource, 
                    required_permission.action, 
                    False
                )
                raise UnauthorizedException(f"Insufficient permissions: {required_permission}")
            
            self.audit.log_authorization(
                user.username, 
                required_permission.resource, 
                required_permission.action, 
                True
            )
            
            return user
            
        except AuthenticationFailedException as e:
            self.audit.log_authentication("unknown", False)
            raise
        except Exception as e:
            self.logger.error(f"Security validation failed: {e}")
            raise SecurityException(f"Security validation failed: {e}")
    
    def login(self, username: str, password: str, ip_address: str = None) -> Dict[str, Any]:
        """Login user and create session"""
        try:
            user = self.auth_manager.authenticate(username, password)
            token = self.auth_manager.create_session(user)
            
            self.audit.log_authentication(username, True, ip_address)
            
            return {
                'token': token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'roles': user.roles
                }
            }
            
        except AuthenticationFailedException as e:
            self.audit.log_authentication(username, False, ip_address)
            raise
    
    def logout(self, token: str):
        """Logout user and revoke session"""
        self.auth_manager.revoke_session(token)
    
    def create_user(self, username: str, password: str, email: str, roles: List[str] = None) -> User:
        """Create new user"""
        return self.auth_manager.create_user(username, password, email, roles) 