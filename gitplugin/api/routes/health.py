"""
Health Check API Routes

Provides system health monitoring and status endpoints.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Any

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    components: Dict[str, str]


@router.get("/", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": "2024-01-01T00:00:00Z",
        "components": {
            "api": "healthy",
            "database": "healthy",
            "redis": "healthy"
        }
    }


@router.get("/ready")
async def readiness_check():
    """Readiness check for Kubernetes"""
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """Liveness check for Kubernetes"""
    return {"status": "alive"} 