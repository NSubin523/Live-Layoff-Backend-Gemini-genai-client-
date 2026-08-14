from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
import logging

logger = logging.getLogger(__name__)

# auto_error=False ensures requests without a Bearer header won't fail automatically
# (This allows guest / "Non-User" calls to proceed smoothly)
security = HTTPBearer(auto_error=False)

async def get_current_user_id(
        credentials: HTTPAuthorizationCredentials | None = Depends(security)
) -> str:
    """
    Dependency that inspects the request's Authorization header:
    - If no Bearer token is provided -> returns "Non-User" (Guest)
    - If a valid Firebase ID token is provided -> returns the user's Firebase UID
    - If token is invalid or expired -> raises 401 Unauthorized
    """
    if not credentials or not credentials.credentials:
        logger.error("[AUTH DEPS] No Authorization header detected -> Defaulting to Non-User")
        return "Non-User"

    token = credentials.credentials
    try:
        # Decrypt & verify the Firebase ID token using Firebase Admin SDK
        decoded_token = auth.verify_id_token(token)
        return decoded_token.get("uid", "Non-User")

    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase authorization token has expired"
        )
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase authorization token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication error: {str(e)}"
        )