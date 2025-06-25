"""
Webhooks API Routes

Handles webhook processing from Git providers.
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/github")
async def github_webhook():
    """GitHub webhook endpoint"""
    return {"message": "GitHub webhook endpoint - not implemented yet"}


@router.post("/gitlab")
async def gitlab_webhook():
    """GitLab webhook endpoint"""
    return {"message": "GitLab webhook endpoint - not implemented yet"} 