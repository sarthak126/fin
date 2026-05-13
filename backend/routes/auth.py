"""
Authentication routes for Clerk-backed sessions.
"""

from typing import Literal

from fastapi import APIRouter, Depends, status

from core.security import AuthenticatedContext, sync_auth_context
from schemas.auth import ClerkManagedAuthResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _clerk_managed_response(action: Literal["sign_in", "sign_up"]) -> ClerkManagedAuthResponse:
    next_step = {
        "sign_up": "Create the account through the Clerk-managed frontend flow, then call /api/v1/auth/me after sign-in to sync the session.",
        "sign_in": "Authenticate through the Clerk-managed frontend flow, then call /api/v1/auth/me to sync the session.",
    }[action]

    return ClerkManagedAuthResponse(
        status="external_provider_required",
        provider="clerk",
        action=action,
        message="This backend does not accept direct credential submission because authentication is handled by Clerk on the frontend.",
        next_step=next_step,
        session_sync_endpoint="/api/v1/auth/me",
    )


@router.post(
    "/signup",
    response_model=ClerkManagedAuthResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def signup():
    """Account creation is handled by Clerk, not by direct backend credentials."""
    return _clerk_managed_response("sign_up")


@router.post(
    "/login",
    response_model=ClerkManagedAuthResponse,
    status_code=status.HTTP_501_NOT_IMPLEMENTED,
)
async def login():
    """Session creation is handled by Clerk, not by direct backend credentials."""
    return _clerk_managed_response("sign_in")


@router.get("/me")
async def get_current_user(auth_context: AuthenticatedContext = Depends(sync_auth_context)):
    """
    Validate the Clerk JWT, sync the authenticated principal, and return
    basic user info for the current session.
    """
    return {
        "id": auth_context.user_id,
        "email": auth_context.email,
        "name": auth_context.name,
        "role": auth_context.role,
        "org_id": auth_context.org_id,
    }
