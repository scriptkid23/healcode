"""
Editor interfaces and data models
"""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Union, Optional, List, Dict, Any
from pathlib import Path


class EditOperationType(Enum):
    """Types of edit operations"""
    LINE = "line"
    RANGE = "range"
    PATTERN = "pattern"
    AST = "ast"
    APPEND = "append"  # New operation type for appending content


@dataclass
class EditOptions:
    """Configuration options for edit operations"""
    create_backup: bool = True
    validate_syntax: bool = True
    encoding: str = "utf-8"
    timeout_seconds: int = 30
    preserve_permissions: bool = True
    atomic_operation: bool = True


@dataclass
class EditRequest:
    """Request model for file editing operations"""
    file_path: str
    operation_type: EditOperationType
    target: Union[int, range, str, None]  # line number, range, pattern, or None for append
    content: str
    options: EditOptions = field(default_factory=EditOptions)
    
    def __post_init__(self):
        """Validate request after initialization"""
        if not self.file_path:
            raise ValueError("file_path cannot be empty")
        
        # Special logic for batch edit: target is tuple (line_numbers, new_contents)
        if self.operation_type == EditOperationType.LINE:
            if isinstance(self.target, tuple):
                line_numbers, new_contents = self.target
                if not line_numbers or not new_contents or len(line_numbers) != len(new_contents):
                    raise ValueError("For batch edit, line_numbers and new_contents must be non-empty and same length")
            else:
                if not isinstance(self.target, int) or self.target < 1:
                    raise ValueError("Line number must be a positive integer")
                if not self.content:
                    raise ValueError("content cannot be empty for non-pattern operations")
        elif self.operation_type == EditOperationType.RANGE:
            if not isinstance(self.target, range):
                raise ValueError("Range target must be a range object")
            if not self.content:
                raise ValueError("content cannot be empty for non-pattern operations")
        elif self.operation_type == EditOperationType.PATTERN:
            if not isinstance(self.target, str):
                raise ValueError("Pattern target must be a string")
        elif self.operation_type == EditOperationType.APPEND:
            if self.target is not None:
                raise ValueError("Append operation should not have a target")
            if not self.content:
                raise ValueError("content cannot be empty for append operation")


@dataclass
class EditResult:
    """Result of an edit operation"""
    success: bool
    operation_id: str
    file_path: str
    operation_type: EditOperationType
    diff: Optional[str] = None
    backup_path: Optional[str] = None
    lines_changed: int = 0
    bytes_changed: int = 0
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success_result(cls, operation_id: str, file_path: str, 
                      operation_type: EditOperationType, **kwargs) -> 'EditResult':
        """Create a successful edit result"""
        return cls(
            success=True,
            operation_id=operation_id,
            file_path=file_path,
            operation_type=operation_type,
            **kwargs
        )
    
    @classmethod
    def error_result(cls, operation_id: str, file_path: str, 
                    operation_type: EditOperationType, error: str, **kwargs) -> 'EditResult':
        """Create an error edit result"""
        return cls(
            success=False,
            operation_id=operation_id,
            file_path=file_path,
            operation_type=operation_type,
            error=error,
            **kwargs
        )


@dataclass
class RollbackRequest:
    """Request to rollback a previous operation"""
    operation_id: str
    force: bool = False  # Force rollback even if file has been modified since


@dataclass
class RollbackResult:
    """Result of a rollback operation"""
    success: bool
    operation_id: str
    file_path: str
    error: Optional[str] = None
    restored_from_backup: Optional[str] = None
    
    @classmethod
    def success_result(cls, operation_id: str, file_path: str, **kwargs) -> 'RollbackResult':
        """Create a successful rollback result"""
        return cls(
            success=True,
            operation_id=operation_id,
            file_path=file_path,
            **kwargs
        )
    
    @classmethod
    def error_result(cls, operation_id: str, file_path: str, error: str) -> 'RollbackResult':
        """Create an error rollback result"""
        return cls(
            success=False,
            operation_id=operation_id,
            file_path=file_path,
            error=error
        )


class EditorInterface(ABC):
    """Abstract interface for file editors"""
    
    @abstractmethod
    async def edit(self, request: EditRequest) -> EditResult:
        """Edit a file according to the request"""
        pass
    
    @abstractmethod
    def supports_operation(self, operation_type: EditOperationType) -> bool:
        """Check if this editor supports the given operation type"""
        pass
    
    @abstractmethod
    async def validate_request(self, request: EditRequest) -> bool:
        """Validate if the request can be processed"""
        pass


@dataclass
class BackupInfo:
    """Information about a backup file"""
    backup_path: str
    original_path: str
    operation_id: str
    created_at: float  # timestamp
    file_size: int
    checksum: str


@dataclass
class OperationMetadata:
    """Metadata for tracking operations"""
    operation_id: str
    file_path: str
    operation_type: EditOperationType
    started_at: float
    completed_at: Optional[float] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    backup_info: Optional[BackupInfo] = None
    
    @staticmethod
    def generate_operation_id() -> str:
        """Generate a unique operation ID"""
        return str(uuid.uuid4())


class EditorException(Exception):
    """Base exception for editor operations"""
    pass


class FileNotFoundException(EditorException):
    """Raised when target file is not found"""
    pass


class FilePermissionException(EditorException):
    """Raised when insufficient permissions for file operation"""
    pass


class FileLockedException(EditorException):
    """Raised when file is locked by another process"""
    pass


class ValidationException(EditorException):
    """Raised when validation fails"""
    pass


class BackupException(EditorException):
    """Raised when backup operations fail"""
    pass


class SyntaxValidationException(EditorException):
    """Raised when syntax validation fails after edit"""
    pass 