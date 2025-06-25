"""
Optimized Git Operations with GitPython

Enhanced Git operations leveraging GitPython for better performance and reliability:
- Efficient repository handling
- Better error management  
- Advanced Git features
"""

import os
import asyncio
import logging
from typing import Dict, Optional, Any, List
from pathlib import Path

try:
    from git import Repo, GitCommandError, InvalidGitRepositoryError, RemoteProgress
    from git.remote import PushInfo, FetchInfo
    HAS_GITPYTHON = True
except ImportError:
    HAS_GITPYTHON = False
    # Define dummy classes for type hints
    class Repo: pass
    class GitCommandError(Exception): pass
    class InvalidGitRepositoryError(Exception): pass


class GitProgress(RemoteProgress):
    """Custom progress handler for Git operations"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def update(self, op_code, cur_count, max_count=None, message=''):
        """Update progress callback"""
        if max_count:
            percentage = int((cur_count / max_count) * 100)
            self.logger.info(f"Git operation: {percentage}% - {message}")


class GitOperationsEngine:
    """Optimized Git operations engine using GitPython"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.repositories: Dict[str, Repo] = {}
        
        if not HAS_GITPYTHON:
            raise ImportError("GitPython is required for optimized Git operations")
    
    async def setup_repository(self, repo_url: str, credential: Dict[str, str], 
                              workspace_path: str) -> str:
        """Setup repository with optimized GitPython"""
        try:
            workspace_path = Path(workspace_path).resolve()
            workspace_path.mkdir(parents=True, exist_ok=True)
            
            # Prepare authenticated URL (only if credentials provided)
            if credential and credential.get('type') and credential.get('type') != 'none':
                auth_url = self._prepare_auth_url(repo_url, credential)
            else:
                # No credentials - try as public repository
                auth_url = repo_url
            
            # Check if repository already exists
            if (workspace_path / '.git').exists():
                try:
                    repo = Repo(workspace_path)
                    # Update remote URL with new credentials
                    if auth_url != repo_url:  # Only update if we have credentials
                        repo.remotes.origin.set_url(auth_url)
                    self.logger.info(f"Updated existing repository: {repo_url}")
                except InvalidGitRepositoryError:
                    # Directory exists but not a Git repo, remove and clone fresh
                    import shutil
                    shutil.rmtree(workspace_path)
                    workspace_path.mkdir(parents=True, exist_ok=True)
                    repo = self._clone_repository(auth_url, workspace_path)
            else:
                # Clone new repository
                repo = self._clone_repository(auth_url, workspace_path)
            
            # Store repository reference
            self.repositories[str(workspace_path)] = repo
            
            # Get repository info
            repo_info = self._get_repository_info(repo)
            self.logger.info(f"Repository setup completed: {repo_info}")
            
            return str(workspace_path)
            
        except Exception as e:
            self.logger.error(f"Repository setup failed: {e}")
            raise
    
    def _clone_repository(self, auth_url: str, workspace_path: Path) -> Repo:
        """Clone repository with progress tracking"""
        try:
            progress = GitProgress()
            
            # Log the clone operation (without exposing credentials)
            safe_url = auth_url.split('@')[-1] if '@' in auth_url else auth_url
            self.logger.info(f"Cloning repository from {safe_url} to {workspace_path}")
            
            repo = Repo.clone_from(
                auth_url,
                workspace_path,
                progress=progress,
                recursive=True  # Clone submodules if any
            )
            
            self.logger.info(f"Repository cloned successfully to {workspace_path}")
            return repo
            
        except GitCommandError as e:
            # Provide more specific error messages
            error_msg = str(e)
            self.logger.error(f"Git clone command failed: {error_msg}")
            
            if "authentication failed" in error_msg.lower() or "invalid username or password" in error_msg.lower():
                raise ValueError("Authentication failed. Please check your credentials.")
            elif "repository not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                raise ValueError("Repository not found. Please check the repository URL.")
            elif "permission denied" in error_msg.lower():
                raise ValueError("Permission denied. Please check your access permissions.")
            elif "could not resolve host" in error_msg.lower():
                raise ValueError("Network error. Please check your internet connection.")
            elif "exit code(128)" in error_msg:
                # Generic git error - try to extract more info
                if "fatal:" in error_msg:
                    fatal_msg = error_msg.split("fatal:")[-1].strip()
                    raise ValueError(f"Git error: {fatal_msg}")
                else:
                    raise ValueError(f"Git clone failed. Error: {error_msg}")
            else:
                raise ValueError(f"Clone failed: {error_msg}")
        except Exception as e:
            self.logger.error(f"Unexpected clone error: {str(e)}")
            raise ValueError(f"Unexpected error during clone: {str(e)}")
    
    async def pull_changes(self, workspace_path: str, credential: Dict[str, str] = None) -> Dict[str, Any]:
        """Pull latest changes with detailed information and credential support"""
        try:
            repo = self._get_repository(workspace_path)
            
            # Update remote URL with credentials if provided (for private repos)
            if credential and credential.get('type') and credential.get('type') != 'none':
                try:
                    current_url = repo.remotes.origin.url
                    # Check if URL already has auth (contains @)
                    if '@' not in current_url:
                        auth_url = self._prepare_auth_url(current_url, credential)
                        repo.remotes.origin.set_url(auth_url)
                        self.logger.info("Updated remote URL with credentials for pull")
                except Exception as e:
                    self.logger.warning(f"Could not update remote URL: {e}")
            
            # Get current commit for comparison
            old_commit = repo.head.commit.hexsha
            
            # Fetch and pull with better error handling
            try:
                origin = repo.remotes.origin
                self.logger.info("Fetching changes from remote...")
                fetch_info = origin.fetch()
                
                self.logger.info("Pulling changes...")
                pull_info = origin.pull()
                
            except GitCommandError as git_e:
                error_msg = str(git_e)
                if "authentication failed" in error_msg.lower():
                    return {
                        "status": "error", 
                        "message": "Authentication failed during pull. Please check your credentials."
                    }
                elif "permission denied" in error_msg.lower():
                    return {
                        "status": "error",
                        "message": "Permission denied. You may not have access to this repository."
                    }
                else:
                    return {"status": "error", "message": f"Git pull failed: {error_msg}"}
            
            # Get new commit
            new_commit = repo.head.commit.hexsha
            has_changes = old_commit != new_commit
            
            # Parse pull information
            pull_details = []
            for info in pull_info:
                pull_details.append({
                    'ref': str(info.ref),
                    'old_commit': old_commit,
                    'new_commit': str(info.commit),
                    'flags': info.flags
                })
            
            # Get changed files if there are changes
            changed_files = []
            if has_changes:
                try:
                    diff = repo.git.diff('--name-only', f'{old_commit}..{new_commit}')
                    changed_files = diff.split('\n') if diff else []
                except:
                    pass
            
            return {
                "status": "success",
                "message": "Changes pulled successfully",
                "has_changes": has_changes,
                "old_commit": old_commit[:8],
                "new_commit": new_commit[:8],
                "changed_files": changed_files,
                "details": pull_details
            }
            
        except Exception as e:
            self.logger.error(f"Pull failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def commit_changes(self, workspace_path: str, message: str, 
                           files: Optional[List[str]] = None) -> Dict[str, Any]:
        """Commit changes with enhanced file handling"""
        try:
            repo = self._get_repository(workspace_path)
            
            # Check if there are any changes to commit
            if not repo.is_dirty(untracked_files=True):
                return {
                    "status": "success",
                    "message": "No changes to commit",
                    "commit_hash": repo.head.commit.hexsha[:8]
                }
            
            # Add files
            if files:
                # Add specific files
                for file_path in files:
                    repo.index.add([file_path])
            else:
                # Add all changes (including untracked files)
                repo.git.add(A=True)
            
            # Check if index has changes after adding
            if not repo.index.diff("HEAD"):
                return {
                    "status": "success", 
                    "message": "No staged changes to commit",
                    "commit_hash": repo.head.commit.hexsha[:8]
                }
            
            # Get staged files info
            staged_files = [item.a_path for item in repo.index.diff("HEAD")]
            
            # Commit changes
            commit = repo.index.commit(message)
            
            # Get commit stats
            stats = commit.stats.total
            
            return {
                "status": "success",
                "message": "Changes committed successfully",
                "commit_hash": commit.hexsha[:8],
                "commit_message": message,
                "staged_files": staged_files,
                "stats": {
                    "files_changed": len(staged_files),
                    "insertions": stats['insertions'],
                    "deletions": stats['deletions']
                },
                "author": f"{commit.author.name} <{commit.author.email}>",
                "timestamp": commit.committed_datetime.isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Commit failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def push_changes(self, workspace_path: str, branch: str = None) -> Dict[str, Any]:
        """Push changes with detailed feedback"""
        try:
            repo = self._get_repository(workspace_path)
            
            # Use current branch if not specified
            if not branch:
                branch = repo.active_branch.name
            
            # Check if there are commits to push
            try:
                commits_ahead = list(repo.iter_commits(f'origin/{branch}..{branch}'))
                if not commits_ahead:
                    return {
                        "status": "success",
                        "message": "No commits to push",
                        "branch": branch
                    }
            except:
                # Branch might not exist on remote yet
                pass
            
            # Push changes
            origin = repo.remotes.origin
            push_info = origin.push(branch)
            
            # Parse push results
            push_results = []
            for info in push_info:
                push_results.append({
                    'local_ref': str(info.local_ref),
                    'remote_ref': str(info.remote_ref),
                    'flags': info.flags,
                    'summary': info.summary
                })
            
            return {
                "status": "success",
                "message": f"Changes pushed to {branch}",
                "branch": branch,
                "push_results": push_results
            }
            
        except Exception as e:
            self.logger.error(f"Push failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def get_repository_status(self, workspace_path: str) -> Dict[str, Any]:
        """Get comprehensive repository status"""
        try:
            repo = self._get_repository(workspace_path)
            
            # Basic repository info
            status = {
                "branch": repo.active_branch.name,
                "commit": repo.head.commit.hexsha[:8],
                "commit_message": repo.head.commit.message.strip(),
                "is_dirty": repo.is_dirty(untracked_files=True),
                "untracked_files": repo.untracked_files,
                "modified_files": [item.a_path for item in repo.index.diff(None)],
                "staged_files": [item.a_path for item in repo.index.diff("HEAD")]
            }
            
            # Remote tracking info
            try:
                active_branch = repo.active_branch
                if active_branch.tracking_branch():
                    tracking_branch = active_branch.tracking_branch()
                    commits_ahead = list(repo.iter_commits(f'{tracking_branch}..{active_branch}'))
                    commits_behind = list(repo.iter_commits(f'{active_branch}..{tracking_branch}'))
                    
                    status.update({
                        "tracking_branch": str(tracking_branch),
                        "commits_ahead": len(commits_ahead),
                        "commits_behind": len(commits_behind)
                    })
            except:
                pass
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to get repository status: {e}")
            raise
    
    async def create_branch(self, workspace_path: str, branch_name: str, 
                           checkout: bool = True) -> Dict[str, Any]:
        """Create new branch"""
        try:
            repo = self._get_repository(workspace_path)
            
            # Check if branch already exists
            if branch_name in [b.name for b in repo.branches]:
                return {
                    "status": "error",
                    "message": f"Branch '{branch_name}' already exists"
                }
            
            # Create new branch
            new_branch = repo.create_head(branch_name)
            
            if checkout:
                new_branch.checkout()
            
            return {
                "status": "success",
                "message": f"Branch '{branch_name}' created successfully",
                "branch": branch_name,
                "checked_out": checkout
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create branch: {e}")
            return {"status": "error", "message": str(e)}
    
    async def switch_branch(self, workspace_path: str, branch_name: str) -> Dict[str, Any]:
        """Switch to existing branch"""
        try:
            repo = self._get_repository(workspace_path)
            
            # Check if branch exists locally
            if branch_name in [b.name for b in repo.branches]:
                repo.git.checkout(branch_name)
            else:
                # Try to checkout remote branch
                try:
                    repo.git.checkout('-b', branch_name, f'origin/{branch_name}')
                except GitCommandError:
                    return {
                        "status": "error",
                        "message": f"Branch '{branch_name}' not found locally or remotely"
                    }
            
            return {
                "status": "success",
                "message": f"Switched to branch '{branch_name}'",
                "branch": branch_name
            }
            
        except Exception as e:
            self.logger.error(f"Failed to switch branch: {e}")
            return {"status": "error", "message": str(e)}
    
    async def create_pull_request(self, repo_url: str, credential: Dict[str, str],
                                 source_branch: str, target_branch: str = "main",
                                 title: str = "", description: str = "") -> Dict[str, Any]:
        """Create pull request using GitHub/GitLab API"""
        try:
            # Determine provider (GitHub, GitLab, etc.)
            if "github.com" in repo_url:
                return await self._create_github_pr(repo_url, credential, source_branch, 
                                                  target_branch, title, description)
            elif "gitlab.com" in repo_url:
                return await self._create_gitlab_pr(repo_url, credential, source_branch,
                                                  target_branch, title, description)
            else:
                return {"status": "error", "message": "Unsupported Git provider"}
                
        except Exception as e:
            self.logger.error(f"Create PR failed: {e}")
            return {"status": "error", "message": str(e)}
    
    def _get_repository(self, workspace_path: str) -> Repo:
        """Get repository instance with caching"""
        workspace_path = str(Path(workspace_path).resolve())
        
        if workspace_path not in self.repositories:
            try:
                repo = Repo(workspace_path)
                self.repositories[workspace_path] = repo
            except InvalidGitRepositoryError:
                raise ValueError(f"No Git repository found at: {workspace_path}")
        
        return self.repositories[workspace_path]
    
    def _get_repository_info(self, repo: Repo) -> Dict[str, str]:
        """Get basic repository information"""
        try:
            return {
                "url": repo.remotes.origin.url,
                "branch": repo.active_branch.name,
                "commit": repo.head.commit.hexsha[:8],
                "message": repo.head.commit.message.strip()
            }
        except:
            return {"status": "Repository info unavailable"}
    
    def _prepare_auth_url(self, repo_url: str, credential: Dict[str, str]) -> str:
        """Prepare authenticated repository URL with enhanced error handling"""
        try:
            if not credential or not credential.get("type"):
                return repo_url
                
            if credential.get("type") == "token":
                token = credential.get('token', '').strip()
                if not token:
                    raise ValueError("Token is empty or missing")
                    
                # For token authentication (GitHub, GitLab)
                if repo_url.startswith("https://"):
                    if "github.com" in repo_url:
                        # GitHub supports multiple token formats, try the most compatible
                        # Format: https://x-access-token:TOKEN@github.com/...
                        return repo_url.replace("https://", f"https://x-access-token:{token}@")
                    elif "gitlab.com" in repo_url:
                        # GitLab uses oauth2 prefix
                        return repo_url.replace("https://", f"https://oauth2:{token}@")
                    else:
                        # Generic Git provider with token
                        return repo_url.replace("https://", f"https://{token}@")
                        
            elif credential.get("type") == "username_password":
                username = credential.get('username', '').strip()
                password = credential.get('password', '').strip()
                
                if not username or not password:
                    raise ValueError("Username or password is empty")
                
                # For username/password authentication
                if repo_url.startswith("https://"):
                    # URL encode username and password to handle special characters
                    import urllib.parse
                    username = urllib.parse.quote(username, safe='')
                    password = urllib.parse.quote(password, safe='')
                    return repo_url.replace("https://", f"https://{username}:{password}@")
            
            # If we get here, return original URL
            self.logger.warning(f"Unsupported credential type: {credential.get('type')}")
            return repo_url
            
        except Exception as e:
            self.logger.error(f"Failed to prepare auth URL: {e}")
            raise ValueError(f"Authentication URL preparation failed: {str(e)}")
    
    async def _create_github_pr(self, repo_url: str, credential: Dict[str, str],
                               source_branch: str, target_branch: str,
                               title: str, description: str) -> Dict[str, Any]:
        """Create GitHub pull request"""
        try:
            import httpx
            
            # Extract owner and repo from URL
            parts = repo_url.replace("https://github.com/", "").replace(".git", "").split("/")
            owner, repo = parts[0], parts[1]
            
            # GitHub API endpoint
            api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
            
            # Request payload
            payload = {
                "title": title or f"Pull request from {source_branch}",
                "head": source_branch,
                "base": target_branch,
                "body": description or f"Automated pull request from {source_branch} to {target_branch}"
            }
            
            # Headers
            headers = {
                "Authorization": f"token {credential['token']}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(api_url, json=payload, headers=headers)
                
                if response.status_code == 201:
                    pr_data = response.json()
                    return {
                        "status": "success",
                        "message": "Pull request created successfully",
                        "pr_url": pr_data["html_url"],
                        "pr_number": pr_data["number"]
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"GitHub API error: {response.status_code}",
                        "details": response.text
                    }
                    
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def _create_gitlab_pr(self, repo_url: str, credential: Dict[str, str],
                               source_branch: str, target_branch: str,
                               title: str, description: str) -> Dict[str, Any]:
        """Create GitLab merge request"""
        try:
            import httpx
            
            # Extract project path from URL
            project_path = repo_url.replace("https://gitlab.com/", "").replace(".git", "")
            
            # GitLab API endpoint (URL encode the project path)
            import urllib.parse
            encoded_path = urllib.parse.quote_plus(project_path)
            api_url = f"https://gitlab.com/api/v4/projects/{encoded_path}/merge_requests"
            
            # Request payload
            payload = {
                "title": title or f"Merge request from {source_branch}",
                "source_branch": source_branch,
                "target_branch": target_branch,
                "description": description or f"Automated merge request from {source_branch} to {target_branch}"
            }
            
            # Headers
            headers = {
                "Authorization": f"Bearer {credential['token']}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(api_url, json=payload, headers=headers)
                
                if response.status_code == 201:
                    mr_data = response.json()
                    return {
                        "status": "success",
                        "message": "Merge request created successfully",
                        "pr_url": mr_data["web_url"],
                        "pr_number": mr_data["iid"]
                    }
                else:
                    return {
                        "status": "error",
                        "message": f"GitLab API error: {response.status_code}",
                        "details": response.text
                    }
                    
        except Exception as e:
            return {"status": "error", "message": str(e)} 