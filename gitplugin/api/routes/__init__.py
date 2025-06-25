"""
API Routes for Git Plugin System
"""

# Import route modules to make them available
from . import auth, credentials, repositories, webhooks, jobs, health

__all__ = ["auth", "credentials", "repositories", "webhooks", "jobs", "health"] 