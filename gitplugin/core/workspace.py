"""
Workspace Management System

Handles workspace allocation, cleanup, and file operations for Git repositories.
"""

import os
import shutil
import tempfile
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from pathlib import Path
import uuid


class WorkspaceException(Exception):
    """Workspace management exception"""
    pass


class Workspace:
    """Represents a workspace for a job"""
    
    def __init__(self, workspace_id: str, job_id: str, base_path: str):
        self.id = workspace_id
        self.job_id = job_id
        self.base_path = Path(base_path)
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.size_bytes = 0
        self.status = "allocated"
        self.cleanup_scheduled = False
    
    @property
    def path(self) -> str:
        """Get workspace path as string"""
        return str(self.base_path)
    
    def update_access(self):
        """Update last accessed time"""
        self.last_accessed = datetime.now()
    
    def calculate_size(self) -> int:
        """Calculate workspace size in bytes"""
        total_size = 0
        if self.base_path.exists():
            for dirpath, dirnames, filenames in os.walk(self.base_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, FileNotFoundError):
                        # Handle broken symlinks or permission issues
                        pass
        self.size_bytes = total_size
        return total_size
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert workspace to dictionary"""
        return {
            'id': self.id,
            'job_id': self.job_id,
            'path': self.path,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'size_bytes': self.size_bytes,
            'status': self.status,
            'cleanup_scheduled': self.cleanup_scheduled
        }


class WorkspaceManager:
    """Manages workspaces for Git operations"""
    
    def __init__(self, base_workspace_dir: str = "/tmp/git_plugin_workspaces", 
                 max_workspace_age_hours: int = 24, max_total_size_gb: float = 10.0):
        self.base_workspace_dir = Path(base_workspace_dir)
        self.max_workspace_age = timedelta(hours=max_workspace_age_hours)
        self.max_total_size_bytes = int(max_total_size_gb * 1024 * 1024 * 1024)
        self.workspaces: Dict[str, Workspace] = {}
        self.logger = logging.getLogger(__name__)
        
        # Create base directory if it doesn't exist
        self.base_workspace_dir.mkdir(parents=True, exist_ok=True)
        
        # Start cleanup task
        self._cleanup_task = None
        self._start_cleanup_task()
    
    async def allocate_workspace(self, job_id: str, workspace_id: Optional[str] = None) -> str:
        """Allocate a workspace for a job"""
        try:
            if workspace_id is None:
                workspace_id = self._generate_workspace_id()
            
            # Check if workspace already exists
            if workspace_id in self.workspaces:
                workspace = self.workspaces[workspace_id]
                workspace.update_access()
                return workspace.path
            
            # Create workspace directory
            workspace_path = self.base_workspace_dir / workspace_id
            workspace_path.mkdir(parents=True, exist_ok=True)
            
            # Create workspace object
            workspace = Workspace(workspace_id, job_id, str(workspace_path))
            self.workspaces[workspace_id] = workspace
            
            self.logger.info(f"Workspace allocated: {workspace_id} for job {job_id}")
            
            # Check if we need to cleanup old workspaces
            await self._check_and_cleanup()
            
            return workspace.path
            
        except Exception as e:
            self.logger.error(f"Failed to allocate workspace for job {job_id}: {e}")
            raise WorkspaceException(f"Failed to allocate workspace: {e}")
    
    async def cleanup_workspace(self, workspace_id: str):
        """Cleanup a specific workspace"""
        try:
            if workspace_id not in self.workspaces:
                self.logger.warning(f"Workspace not found for cleanup: {workspace_id}")
                return
            
            workspace = self.workspaces[workspace_id]
            
            # Remove directory
            if workspace.base_path.exists():
                shutil.rmtree(workspace.base_path, ignore_errors=True)
            
            # Remove from tracking
            del self.workspaces[workspace_id]
            
            self.logger.info(f"Workspace cleaned up: {workspace_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup workspace {workspace_id}: {e}")
            raise WorkspaceException(f"Failed to cleanup workspace: {e}")
    
    async def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get workspace by ID"""
        workspace = self.workspaces.get(workspace_id)
        if workspace:
            workspace.update_access()
        return workspace
    
    async def list_workspaces(self, job_id: Optional[str] = None) -> List[Workspace]:
        """List workspaces, optionally filtered by job ID"""
        workspaces = []
        for workspace in self.workspaces.values():
            if job_id is None or workspace.job_id == job_id:
                workspaces.append(workspace)
        return workspaces
    
    async def get_workspace_stats(self) -> Dict[str, Any]:
        """Get workspace statistics"""
        total_workspaces = len(self.workspaces)
        total_size = 0
        oldest_workspace = None
        newest_workspace = None
        
        for workspace in self.workspaces.values():
            workspace.calculate_size()
            total_size += workspace.size_bytes
            
            if oldest_workspace is None or workspace.created_at < oldest_workspace.created_at:
                oldest_workspace = workspace
            
            if newest_workspace is None or workspace.created_at > newest_workspace.created_at:
                newest_workspace = workspace
        
        return {
            'total_workspaces': total_workspaces,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'max_size_gb': self.max_total_size_bytes / (1024 * 1024 * 1024),
            'usage_percentage': round((total_size / self.max_total_size_bytes) * 100, 2),
            'oldest_workspace': oldest_workspace.to_dict() if oldest_workspace else None,
            'newest_workspace': newest_workspace.to_dict() if newest_workspace else None
        }
    
    def _generate_workspace_id(self) -> str:
        """Generate unique workspace ID"""
        return f"ws_{uuid.uuid4().hex[:16]}"
    
    def _start_cleanup_task(self):
        """Start background cleanup task"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Background cleanup loop"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._check_and_cleanup()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Cleanup loop error: {e}")
    
    async def _check_and_cleanup(self):
        """Check and cleanup old or large workspaces"""
        try:
            current_time = datetime.now()
            workspaces_to_cleanup = []
            total_size = 0
            
            # Calculate total size and identify old workspaces
            for workspace_id, workspace in self.workspaces.items():
                workspace.calculate_size()
                total_size += workspace.size_bytes
                
                # Check if workspace is too old
                if current_time - workspace.created_at > self.max_workspace_age:
                    workspaces_to_cleanup.append(workspace_id)
                    self.logger.info(f"Workspace {workspace_id} marked for cleanup: too old")
            
            # If total size exceeds limit, cleanup least recently used workspaces
            if total_size > self.max_total_size_bytes:
                sorted_workspaces = sorted(
                    self.workspaces.items(),
                    key=lambda x: x[1].last_accessed
                )
                
                for workspace_id, workspace in sorted_workspaces:
                    if total_size <= self.max_total_size_bytes:
                        break
                    if workspace_id not in workspaces_to_cleanup:
                        workspaces_to_cleanup.append(workspace_id)
                        total_size -= workspace.size_bytes
                        self.logger.info(f"Workspace {workspace_id} marked for cleanup: size limit")
            
            # Cleanup identified workspaces
            for workspace_id in workspaces_to_cleanup:
                await self.cleanup_workspace(workspace_id)
            
            if workspaces_to_cleanup:
                self.logger.info(f"Cleaned up {len(workspaces_to_cleanup)} workspaces")
                
        except Exception as e:
            self.logger.error(f"Workspace cleanup check failed: {e}")
    
    async def create_temp_file(self, workspace_id: str, content: str, 
                              filename: Optional[str] = None) -> str:
        """Create temporary file in workspace"""
        workspace = await self.get_workspace(workspace_id)
        if not workspace:
            raise WorkspaceException(f"Workspace not found: {workspace_id}")
        
        if filename is None:
            filename = f"temp_{uuid.uuid4().hex[:8]}.txt"
        
        file_path = workspace.base_path / filename
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.logger.debug(f"Temporary file created: {file_path}")
            return str(file_path)
            
        except Exception as e:
            self.logger.error(f"Failed to create temp file in workspace {workspace_id}: {e}")
            raise WorkspaceException(f"Failed to create temp file: {e}")
    
    async def read_file(self, workspace_id: str, filename: str) -> str:
        """Read file from workspace"""
        workspace = await self.get_workspace(workspace_id)
        if not workspace:
            raise WorkspaceException(f"Workspace not found: {workspace_id}")
        
        file_path = workspace.base_path / filename
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return content
            
        except FileNotFoundError:
            raise WorkspaceException(f"File not found: {filename}")
        except Exception as e:
            self.logger.error(f"Failed to read file {filename} from workspace {workspace_id}: {e}")
            raise WorkspaceException(f"Failed to read file: {e}")
    
    async def list_files(self, workspace_id: str, pattern: Optional[str] = None) -> List[str]:
        """List files in workspace"""
        workspace = await self.get_workspace(workspace_id)
        if not workspace:
            raise WorkspaceException(f"Workspace not found: {workspace_id}")
        
        try:
            files = []
            if workspace.base_path.exists():
                if pattern:
                    files = [str(p.relative_to(workspace.base_path)) 
                            for p in workspace.base_path.rglob(pattern)]
                else:
                    files = [str(p.relative_to(workspace.base_path)) 
                            for p in workspace.base_path.rglob('*') if p.is_file()]
            
            return sorted(files)
            
        except Exception as e:
            self.logger.error(f"Failed to list files in workspace {workspace_id}: {e}")
            raise WorkspaceException(f"Failed to list files: {e}")
    
    async def copy_file(self, source_workspace_id: str, dest_workspace_id: str, 
                       filename: str) -> str:
        """Copy file between workspaces"""
        source_workspace = await self.get_workspace(source_workspace_id)
        dest_workspace = await self.get_workspace(dest_workspace_id)
        
        if not source_workspace:
            raise WorkspaceException(f"Source workspace not found: {source_workspace_id}")
        
        if not dest_workspace:
            raise WorkspaceException(f"Destination workspace not found: {dest_workspace_id}")
        
        source_path = source_workspace.base_path / filename
        dest_path = dest_workspace.base_path / filename
        
        try:
            # Create destination directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            
            self.logger.debug(f"File copied: {source_path} -> {dest_path}")
            return str(dest_path)
            
        except FileNotFoundError:
            raise WorkspaceException(f"Source file not found: {filename}")
        except Exception as e:
            self.logger.error(f"Failed to copy file {filename}: {e}")
            raise WorkspaceException(f"Failed to copy file: {e}")
    
    async def archive_workspace(self, workspace_id: str, archive_path: str) -> str:
        """Archive workspace to tar.gz file"""
        workspace = await self.get_workspace(workspace_id)
        if not workspace:
            raise WorkspaceException(f"Workspace not found: {workspace_id}")
        
        try:
            import tarfile
            
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(workspace.base_path, arcname=workspace_id)
            
            self.logger.info(f"Workspace archived: {workspace_id} -> {archive_path}")
            return archive_path
            
        except Exception as e:
            self.logger.error(f"Failed to archive workspace {workspace_id}: {e}")
            raise WorkspaceException(f"Failed to archive workspace: {e}")
    
    async def restore_workspace(self, workspace_id: str, archive_path: str) -> str:
        """Restore workspace from tar.gz file"""
        try:
            import tarfile
            
            # Allocate new workspace
            workspace_path = await self.allocate_workspace("restore", workspace_id)
            
            # Extract archive
            with tarfile.open(archive_path, 'r:gz') as tar:
                tar.extractall(path=self.base_workspace_dir)
            
            self.logger.info(f"Workspace restored: {archive_path} -> {workspace_id}")
            return workspace_path
            
        except Exception as e:
            self.logger.error(f"Failed to restore workspace from {archive_path}: {e}")
            raise WorkspaceException(f"Failed to restore workspace: {e}")
    
    async def cleanup_all(self):
        """Cleanup all workspaces"""
        workspace_ids = list(self.workspaces.keys())
        for workspace_id in workspace_ids:
            await self.cleanup_workspace(workspace_id)
        
        self.logger.info(f"All {len(workspace_ids)} workspaces cleaned up")
    
    def __del__(self):
        """Cleanup on deletion"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel() 