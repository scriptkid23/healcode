"""
Core components of the Git Plugin system
"""

from .git_operations import GitOperationsEngine
from .credentials import CredentialsManager

__all__ = [
    "GitOperationsEngine",
    "CredentialsManager"
] 