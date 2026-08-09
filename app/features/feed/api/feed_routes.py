from typing import List

from fastapi import HTTPException, APIRouter, Depends

from app.features.auth.service.auth_deps import get_current_user_id
from app.features.feed.data.dto.layoff_feed_response import LayoffFeedResponse
from app.features.feed.data.repository.feed_repository import FeedRepository

router = APIRouter(prefix="/api/v1/feed", tags=["Mobile Feed Services"])
repo_instance = FeedRepository()

@router.get("", response_model=List[LayoffFeedResponse])
async def get_splash_feed(
        user_id: str = Depends(get_current_user_id)
):
    try:
        return repo_instance.generate_data_for_layoff_feed()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )