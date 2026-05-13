"""
Pydantic schemas for authentication route responses.
"""

from typing import Literal

from pydantic import BaseModel


class ClerkManagedAuthResponse(BaseModel):
    status: Literal["external_provider_required"]
    provider: Literal["clerk"]
    action: Literal["sign_in", "sign_up"]
    message: str
    next_step: str
    session_sync_endpoint: str
