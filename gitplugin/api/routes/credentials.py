"""
Credentials API Routes

Handles credential management operations.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_credentials():
    """List credentials"""
    return {"message": "Credentials endpoint - not implemented yet"} 