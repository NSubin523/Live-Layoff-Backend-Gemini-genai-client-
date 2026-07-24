from typing import Optional

from pydantic import BaseModel

from app.features.feed.data.dto.layoff_feed_response import LayoffFeedResponse


class PushNotificationRequestDto(BaseModel):
    company: LayoffFeedResponse
    target_token: Optional[str] = None
    topic: Optional[str] = "all_users" # all users subscribed for now