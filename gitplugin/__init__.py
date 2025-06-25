"""
Git Plugin System - A simple Git integration system

This package provides basic Git repository integration capabilities
including credential management and Git operations.
"""

__version__ = "1.0.0"
__author__ = "Git Plugin Team"
__email__ = "team@gitplugin.com"

from .core.git_operations import GitOperationsEngine
from .core.credentials import CredentialsManager

__all__ = [
    "GitOperationsEngine",
    "CredentialsManager"
] 