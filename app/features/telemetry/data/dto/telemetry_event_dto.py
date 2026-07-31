from typing import Optional, Dict, Any, List

from pydantic import BaseModel

class TelemetryEventCreate(BaseModel):
    user_id: str
    event_name: str
    event_payload: Optional[Dict[str, Any]] = None

class TelemetryRequestDto(BaseModel):
    events: List[TelemetryEventCreate]