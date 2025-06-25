"""
Jobs API Routes

Handles job management and build operations.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_jobs():
    """List jobs"""
    return {"message": "Jobs endpoint - not implemented yet"} 