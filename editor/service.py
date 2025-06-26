"""
Main Editor Service that orchestrates all editing strategies
"""

import asyncio
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

try:
    import portalocker
    HAS_PORTALOCKER = True
except ImportError:
    HAS_PORTALOCKER = False

from .interfaces import (
    EditRequest, EditResult, EditOperationType, EditOptions, RollbackRequest, RollbackResult,
    EditorInterface, BackupInfo, OperationMetadata,
    EditorException, FileLockedException, BackupException
)
from .strategies import LineEditor, PatternEditor, ASTEditor


@dataclass
class EditorConfig:
    """Configuration for the editor service"""
    backup_enabled: bool = False  # Disabled by default since Git manages versions
    backup_directory: str = "./backups"
    backup_retention_days: int = 7
    max_backup_size_mb: int = 100
    max_concurrent_operations: int = 10
    lock_timeout_seconds: int = 30
    operation_timeout_seconds: int = 60
    allowed_extensions: List[str] = field(default_factory=lambda: [
        '.py', '.js', '.ts', '.json', '.yaml', '.yml', '.txt', '.md'
    ])
    max_file_size_mb: int = 50
    validate_syntax: bool = True
    allowed_base_paths: List[str] = field(default_factory=list)


class EditorService:
    """Main editor service that orchestrates all editing operations"""
    
    def __init__(self, config: EditorConfig = None):
        self.config = config or EditorConfig()
        
        # Initialize editing strategies
        self.strategies: Dict[EditOperationType, EditorInterface] = {
            EditOperationType.LINE: LineEditor(),
            EditOperationType.RANGE: LineEditor(),
            EditOperationType.PATTERN: PatternEditor(),
            EditOperationType.AST: ASTEditor(),
        }
        
        # Concurrency management
        self.file_locks: Dict[str, asyncio.Lock] = {}
        self.operation_semaphore = asyncio.Semaphore(self.config.max_concurrent_operations)
        
        # Operation tracking
        self.active_operations: Dict[str, OperationMetadata] = {}
        self.operation_history: List[OperationMetadata] = []
        
        # Backup management
        self.backup_manager = BackupManager(self.config)
        
        # Setup backup directory
        backup_dir = Path(self.config.backup_directory)
        backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def edit_file(self, request: EditRequest) -> EditResult:
        """Main entry point for file editing"""
        operation_id = OperationMetadata.generate_operation_id()
        start_time = time.time()
        
        # Create operation metadata
        metadata = OperationMetadata(
            operation_id=operation_id,
            file_path=request.file_path,
            operation_type=request.operation_type,
            started_at=start_time
        )
        
        self.active_operations[operation_id] = metadata
        
        try:
            # Validate request
            await self._validate_request(request)
            
            # Get appropriate strategy
            strategy = self._get_strategy(request.operation_type)
            
            # Execute with concurrency control
            async with self.operation_semaphore:
                result = await self._execute_with_lock(request, strategy, operation_id)
            
            # Update metadata
            metadata.completed_at = time.time()
            self.operation_history.append(metadata)
            
            return result
            
        except Exception as e:
            metadata.completed_at = time.time()
            self.operation_history.append(metadata)
            
            return EditResult.error_result(
                operation_id, request.file_path, request.operation_type, str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
        finally:
            if operation_id in self.active_operations:
                del self.active_operations[operation_id]
    
    async def edit_line(self, file_path: str, line_number: int, 
                       new_content: str, options: EditOptions = None) -> EditResult:
        """Convenience method for line editing"""
        
        request = EditRequest(
            file_path=file_path,
            operation_type=EditOperationType.LINE,
            target=line_number,
            content=new_content,
            options=options or EditOptions()
        )
        return await self.edit_file(request)
    
    async def edit_range(self, file_path: str, start_line: int, end_line: int,
                        new_content: str, options: EditOptions = None) -> EditResult:
        """Convenience method for range editing"""
        
        request = EditRequest(
            file_path=file_path,
            operation_type=EditOperationType.RANGE,
            target=range(start_line, end_line + 1),
            content=new_content,
            options=options or EditOptions()
        )
        return await self.edit_file(request)
    
    async def edit_pattern(self, file_path: str, pattern: str, 
                          replacement: str, options: EditOptions = None) -> EditResult:
        """Convenience method for pattern editing"""
        
        request = EditRequest(
            file_path=file_path,
            operation_type=EditOperationType.PATTERN,
            target=pattern,
            content=replacement,
            options=options or EditOptions()
        )
        return await self.edit_file(request)
    
    async def rollback(self, rollback_request: RollbackRequest) -> RollbackResult:
        """Rollback a previous operation"""
        operation_id = rollback_request.operation_id
        
        # Find the operation in history
        operation = None
        for op in self.operation_history:
            if op.operation_id == operation_id:
                operation = op
                break
        
        if not operation:
            return RollbackResult.error_result(
                operation_id, "", f"Operation {operation_id} not found"
            )
        
        if not operation.backup_info:
            return RollbackResult.error_result(
                operation_id, operation.file_path, "No backup available for this operation"
            )
        
        try:
            # Restore from backup
            success = await self.backup_manager.restore_backup(
                operation.backup_info.backup_path, 
                operation.file_path,
                force=rollback_request.force
            )
            
            if success:
                return RollbackResult.success_result(
                    operation_id, operation.file_path,
                    restored_from_backup=operation.backup_info.backup_path
                )
            else:
                return RollbackResult.error_result(
                    operation_id, operation.file_path, "Failed to restore from backup"
                )
                
        except Exception as e:
            return RollbackResult.error_result(
                operation_id, operation.file_path, str(e)
            )
    
    async def _execute_with_lock(self, request: EditRequest, 
                                strategy: EditorInterface, operation_id: str) -> EditResult:
        """Execute edit operation with file locking"""
        file_path = request.file_path
        
        # Get or create file lock
        if file_path not in self.file_locks:
            self.file_locks[file_path] = asyncio.Lock()
        
        file_lock = self.file_locks[file_path]
        
        # Use system-level file locking if available
        if HAS_PORTALOCKER and request.options.atomic_operation:
            return await self._execute_with_portalocker(request, strategy, operation_id)
        else:
            async with file_lock:
                return await self._execute_edit(request, strategy, operation_id)
    
    async def _execute_with_portalocker(self, request: EditRequest, 
                                       strategy: EditorInterface, operation_id: str) -> EditResult:
        """Execute with portalocker for system-level file locking"""
        import tempfile
        import os
        
        # Create a lock file
        lock_file_path = f"{request.file_path}.lock"
        
        try:
            with open(lock_file_path, 'w') as lock_file:
                # Acquire exclusive lock
                portalocker.lock(lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
                
                try:
                    return await self._execute_edit(request, strategy, operation_id)
                finally:
                    portalocker.unlock(lock_file)
        
        except portalocker.LockException:
            raise FileLockedException(f"File {request.file_path} is locked by another process")
        finally:
            # Clean up lock file
            try:
                os.unlink(lock_file_path)
            except OSError:
                pass
    
    async def _execute_edit(self, request: EditRequest, 
                           strategy: EditorInterface, operation_id: str) -> EditResult:
        """Execute the actual edit operation"""
        backup_info = None
        
        try:
            # Create backup if requested
            if request.options.create_backup and self.config.backup_enabled:
                backup_info = await self.backup_manager.create_backup(
                    request.file_path, operation_id
                )
                
                # Update operation metadata
                if operation_id in self.active_operations:
                    self.active_operations[operation_id].backup_info = backup_info
            
            # Execute the edit
            result = await asyncio.wait_for(
                strategy.edit(request),
                timeout=request.options.timeout_seconds
            )
            
            # Add backup info to result
            if backup_info:
                result.backup_path = backup_info.backup_path
            
            return result
            
        except asyncio.TimeoutError:
            # Restore from backup if edit timed out
            if backup_info:
                await self.backup_manager.restore_backup(
                    backup_info.backup_path, request.file_path
                )
            raise EditorException(f"Edit operation timed out after {request.options.timeout_seconds} seconds")
        
        except Exception as e:
            # Restore from backup if edit failed
            if backup_info:
                await self.backup_manager.restore_backup(
                    backup_info.backup_path, request.file_path
                )
            raise e
    
    async def _validate_request(self, request: EditRequest):
        """Validate edit request"""
        file_path = Path(request.file_path)
        
        # Check if file exists
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {request.file_path}")
        
        # Check file extension
        if file_path.suffix not in self.config.allowed_extensions:
            raise ValidationException(f"File extension {file_path.suffix} not allowed")
        
        # Check file size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.config.max_file_size_mb:
            raise ValidationException(f"File size {file_size_mb:.1f}MB exceeds limit of {self.config.max_file_size_mb}MB")
        
        # Check base path restrictions
        if self.config.allowed_base_paths:
            resolved_path = file_path.resolve()
            allowed = False
            for base_path in self.config.allowed_base_paths:
                try:
                    resolved_path.relative_to(Path(base_path).resolve())
                    allowed = True
                    break
                except ValueError:
                    continue
            
            if not allowed:
                raise ValidationException(f"File path not in allowed base paths: {request.file_path}")
    
    def _get_strategy(self, operation_type: EditOperationType) -> EditorInterface:
        """Get the appropriate editing strategy"""
        if operation_type not in self.strategies:
            raise EditorException(f"Unsupported operation type: {operation_type}")
        
        strategy = self.strategies[operation_type]
        if not strategy.supports_operation(operation_type):
            raise EditorException(f"Strategy does not support operation type: {operation_type}")
        
        return strategy
    
    async def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an operation"""
        # Check active operations
        if operation_id in self.active_operations:
            op = self.active_operations[operation_id]
            return {
                'operation_id': op.operation_id,
                'file_path': op.file_path,
                'operation_type': op.operation_type.value,
                'status': 'active',
                'started_at': op.started_at,
                'duration_seconds': time.time() - op.started_at
            }
        
        # Check completed operations
        for op in self.operation_history:
            if op.operation_id == operation_id:
                return {
                    'operation_id': op.operation_id,
                    'file_path': op.file_path,
                    'operation_type': op.operation_type.value,
                    'status': 'completed',
                    'started_at': op.started_at,
                    'completed_at': op.completed_at,
                    'duration_seconds': op.completed_at - op.started_at if op.completed_at else None,
                    'has_backup': op.backup_info is not None
                }
        
        return None
    
    async def list_active_operations(self) -> List[Dict[str, Any]]:
        """List all active operations"""
        current_time = time.time()
        return [
            {
                'operation_id': op.operation_id,
                'file_path': op.file_path,
                'operation_type': op.operation_type.value,
                'started_at': op.started_at,
                'duration_seconds': current_time - op.started_at
            }
            for op in self.active_operations.values()
        ]
    
    async def cleanup_old_backups(self):
        """Clean up old backup files"""
        await self.backup_manager.cleanup_old_backups()


class BackupManager:
    """Manages backup creation and restoration"""
    
    def __init__(self, config: EditorConfig):
        self.config = config
        self.backup_dir = Path(config.backup_directory)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_backup(self, file_path: str, operation_id: str) -> BackupInfo:
        """Create a backup of the file"""
        source_path = Path(file_path)
        if not source_path.exists():
            raise BackupException(f"Source file does not exist: {file_path}")
        
        # Generate backup filename
        timestamp = int(time.time())
        backup_filename = f"{source_path.stem}_{operation_id}_{timestamp}{source_path.suffix}.bak"
        backup_path = self.backup_dir / backup_filename
        
        try:
            import shutil
            
            # Copy file with metadata
            shutil.copy2(source_path, backup_path)
            
            # Calculate checksum
            checksum = await self._calculate_checksum(source_path)
            
            backup_info = BackupInfo(
                backup_path=str(backup_path),
                original_path=file_path,
                operation_id=operation_id,
                created_at=time.time(),
                file_size=source_path.stat().st_size,
                checksum=checksum
            )
            
            return backup_info
            
        except Exception as e:
            raise BackupException(f"Failed to create backup: {e}")
    
    async def restore_backup(self, backup_path: str, target_path: str, force: bool = False) -> bool:
        """Restore a file from backup"""
        backup_file = Path(backup_path)
        target_file = Path(target_path)
        
        if not backup_file.exists():
            raise BackupException(f"Backup file does not exist: {backup_path}")
        
        # Check if target has been modified since backup (if not force)
        if not force and target_file.exists():
            target_checksum = await self._calculate_checksum(target_file)
            backup_checksum = await self._calculate_checksum(backup_file)
            
            # This is a simple check - in practice, you might want more sophisticated validation
            if target_file.stat().st_mtime > backup_file.stat().st_mtime:
                raise BackupException("Target file has been modified since backup. Use force=True to override.")
        
        try:
            import shutil
            
            # Restore the file
            shutil.copy2(backup_file, target_file)
            return True
            
        except Exception as e:
            raise BackupException(f"Failed to restore backup: {e}")
    
    async def cleanup_old_backups(self):
        """Clean up backup files older than retention period"""
        cutoff_time = time.time() - (self.config.backup_retention_days * 24 * 3600)
        
        for backup_file in self.backup_dir.glob("*.bak"):
            try:
                if backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
            except OSError:
                pass  # File might have been deleted by another process
    
    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file"""
        hash_md5 = hashlib.md5()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest() 