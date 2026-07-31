from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.features.telemetry.service.telemetry_service import TelemetryService
from config.database.dbsession import get_db


def get_telemetry_service(db: AsyncSession = Depends(get_db)) -> TelemetryService:
    return TelemetryService(db)