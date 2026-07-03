import logging

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def verify_firebase_token(token: str) -> dict:
    """Verify a Firebase ID token using Google's public keys (no service account required)."""
    settings = get_settings()
    request = google_requests.Request()
    try:
        decoded = id_token.verify_firebase_token(
            token,
            request,
            audience=settings.firebase_project_id,
            clock_skew_in_seconds=settings.firebase_token_clock_skew_seconds,
        )
    except ValueError as exc:
        msg = str(exc).lower()
        if "expired" in msg:
            raise ValueError("Token expired") from exc
        raise
    logger.debug("Verified Firebase token for uid=%s", decoded.get("sub") or decoded.get("user_id"))
    return decoded
