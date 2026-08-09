from fastapi import APIRouter, Depends, status, HTTPException, Response

from app.features.auth.service.auth_deps import get_current_user_id
from app.features.telemetry.data.dto.telemetry_event_dto import TelemetryRequestDto
from app.features.telemetry.service.telemetry_service import TelemetryService
from app.features.telemetry.service.telemetry_service_dependency import get_telemetry_service

router = APIRouter(prefix="/api/v1/telemetry", tags=["Telemetry"])

@router.post("/batch", status_code=status.HTTP_201_CREATED, response_class=Response)
async def log_telemetry_batch(
    payload: TelemetryRequestDto,
    user_id: str = Depends(get_current_user_id),
    service: TelemetryService = Depends(get_telemetry_service)
):
    try:
        for event in payload.events:
            event.user_id = user_id

        await service.insert_batch_telemetry(payload.events)
        return Response(status_code=status.HTTP_201_CREATED)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )