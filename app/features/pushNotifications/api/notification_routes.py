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
            "company_name": comp.company_name,
            "status": comp.status,
            "impact_count": str(comp.impact_count) if comp.impact_count is not None else "0",
            "logo_url": comp.logo_url or "",
            "location": comp.location or "",
            "trend_direction": getattr(comp, "trend_direction", "stable")
        }

        # Title & Body formatted for the notification tray
        notification_title = f"{comp.company_name} Layoff Alert"
        notification_body = f"{comp.company_name} announced layoffs ({comp.status}). Impact: {comp.impact_count or 'N/A'}"

        message = messaging.Message(
            data=data_payload,
            notification=messaging.Notification(
                title=notification_title,
                body=notification_body,
                image=comp.logo_url if comp.logo_url else None
            ),
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    click_action="OPEN_NEWS_DEEPLINK"
                )
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