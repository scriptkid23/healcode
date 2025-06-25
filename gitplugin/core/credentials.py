"""
Simplified Credentials Management

Basic credential management for essential Git operations:
- Token-based authentication
- Username/password authentication
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from pathlib import Path


class CredentialsManager:
    """Simplified credentials manager"""
    
    def __init__(self, storage_path: str = "./credentials"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self.credentials: Dict[str, Dict[str, Any]] = {}
        self._load_credentials()
    
    def add_credential(self, name: str, credential_type: str, **kwargs) -> str:
        """Add new credential"""
        try:
            credential = {
                "type": credential_type,
                "name": name,
                **kwargs
            }
            
            # Validate required fields
            if credential_type == "token":
                if "token" not in kwargs:
                    raise ValueError("Token is required for token authentication")
            elif credential_type == "username_password":
                if "username" not in kwargs or "password" not in kwargs:
                    raise ValueError("Username and password are required")
            else:
                raise ValueError(f"Unsupported credential type: {credential_type}")
            
            self.credentials[name] = credential
            self._save_credentials()
            
            self.logger.info(f"Credential added: {name}")
            return name
            
        except Exception as e:
            self.logger.error(f"Failed to add credential: {e}")
            raise
    
    def get_credential(self, name: str) -> Optional[Dict[str, Any]]:
        """Get credential by name"""
        return self.credentials.get(name)
    
    def list_credentials(self) -> Dict[str, str]:
        """List all credentials (without sensitive data)"""
        return {
            name: cred["type"] 
            for name, cred in self.credentials.items()
        }
    
    def remove_credential(self, name: str) -> bool:
        """Remove credential"""
        if name in self.credentials:
            del self.credentials[name]
            self._save_credentials()
            self.logger.info(f"Credential removed: {name}")
            return True
        return False
    
    def _load_credentials(self):
        """Load credentials from storage"""
        try:
            credentials_file = self.storage_path / "credentials.json"
            if credentials_file.exists():
                with open(credentials_file, 'r') as f:
                    self.credentials = json.load(f)
                self.logger.info(f"Loaded {len(self.credentials)} credentials")
        except Exception as e:
            self.logger.error(f"Failed to load credentials: {e}")
            self.credentials = {}
    
    def _save_credentials(self):
        """Save credentials to storage"""
        try:
            credentials_file = self.storage_path / "credentials.json"
            with open(credentials_file, 'w') as f:
                json.dump(self.credentials, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save credentials: {e}")
            raise 