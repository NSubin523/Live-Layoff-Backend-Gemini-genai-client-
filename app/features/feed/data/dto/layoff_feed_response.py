from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LayoffFeedResponse(BaseModel):
    id: str
    company_name: str
    impact_count: Optional[int]
    status: str
    industry: str
    location: str
    reported_at: datetime
    logo_url: str
    trend_direction: str