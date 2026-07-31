from typing import List
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.telemetry.data.dto.telemetry_event_dto import TelemetryEventCreate
from app.features.telemetry.data.model.telemetry import Telemetry

logger = logging.getLogger(__name__)

class TelemetryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def insert_batch_telemetry(self, events: List[TelemetryEventCreate]) -> None:
        if not events:
            return

        data = [
            Telemetry(
                user_id=event.user_id,
                event_name=event.event_name,
                event_payload=event.event_payload
            )
            for event in events
        ]

        try:
            self.db.add_all(data)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to log batch events: {}".format(e), exc_info=True)
            raise e