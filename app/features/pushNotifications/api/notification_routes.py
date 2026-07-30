from fastapi import APIRouter, HTTPException
from firebase_admin import messaging

from app.features.pushNotifications.data.push_notification_model import PushNotificationRequestDto

router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])

@router.post("/send")
def send_push_notification(payload: PushNotificationRequestDto):
    """
    Triggers an FCM push notification using an existing company/layoff model object.
    """
    try:
        comp = payload.company

        # All values inside FCM data payload MUST be strings for Android parsing
        data_payload = {
            "company_id": str(comp.id) if hasattr(comp, "id") and comp.id else "",
            "company_name": str(comp.company_name),
            "status": str(comp.status),
            "impact_count": str(comp.impact_count) if comp.impact_count is not None else "0",
            "logo_url": str(comp.logo_url or ""),
            "location": str(comp.location or ""),
            "trend_direction": str(getattr(comp, "trend_direction", "stable")),
            "news_url": "https://google.com"
        }

        # PURE DATA MESSAGE (No notification objects anywhere)
        message = messaging.Message(
            data=data_payload,
            android=messaging.AndroidConfig(
                priority="high"  # High priority wakes device up from Doze mode
            ),
            token=payload.target_token if payload.target_token else None,
            topic=payload.topic if not payload.target_token else None
        )

        response = messaging.send(message)
        return {
            "status": "success",
            "message_id": response,
            "target": payload.target_token if payload.target_token else f"topic:{payload.topic}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send push notification: {str(e)}")