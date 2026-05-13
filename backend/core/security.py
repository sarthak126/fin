"""
Security module for verifying Clerk JWT tokens and resolving the
authenticated application context.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable
import json

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from jwt.algorithms import RSAAlgorithm
from prisma import Prisma

from core.config import get_settings
from core.database import get_db, is_database_unavailable_error
from models import UserRole

settings = get_settings()


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str, **kwargs):
        super().__init__(status_code=401, detail=detail, **kwargs)


class ForbiddenException(HTTPException):
    def __init__(self, detail: str, **kwargs):
        super().__init__(status_code=403, detail=detail, **kwargs)


class AuthConfigurationException(HTTPException):
    def __init__(self, detail: str, **kwargs):
        super().__init__(status_code=503, detail=detail, **kwargs)


@dataclass(frozen=True)
class AuthenticatedContext:
    user_id: str
    org_id: str
    email: str
    name: str
    role: str
    token_payload: dict[str, Any]


MUTATION_ROLES = frozenset({UserRole.ADMIN.value, UserRole.ANALYST.value})


def _normalize_role(role: str | None) -> str:
    return str(role or "").strip().lower()


def require_role(
    auth_context: AuthenticatedContext,
    allowed_roles: Iterable[str],
    *,
    detail: str = "Insufficient permissions",
) -> None:
    normalized_allowed_roles = {_normalize_role(role) for role in allowed_roles}
    if _normalize_role(auth_context.role) not in normalized_allowed_roles:
        raise ForbiddenException(detail)


def require_mutation_role(auth_context: AuthenticatedContext) -> None:
    require_role(
        auth_context,
        MUTATION_ROLES,
        detail="This action requires an admin or analyst role",
    )


def _strip_trailing_slash(value: str) -> str:
    return value.rstrip("/")


def _allowed_authorized_parties() -> set[str]:
    allowed = {_strip_trailing_slash(settings.FRONTEND_URL)}
    if settings.APP_ENV != "production":
        allowed.update(
            {
                "http://localhost:3000",
                "http://127.0.0.1:3000",
                "http://localhost:3001",
                "http://127.0.0.1:3001",
            }
        )
    return {party for party in allowed if party}


def _normalize_audiences(audience_claim: Any) -> list[str]:
    if isinstance(audience_claim, str) and audience_claim.strip():
        return [audience_claim.strip()]
    if isinstance(audience_claim, list):
        return [str(item).strip() for item in audience_claim if str(item).strip()]
    return []


def _validate_token_target(payload: dict[str, Any]) -> None:
    configured_audience = settings.CLERK_JWT_AUDIENCE.strip()
    token_audiences = _normalize_audiences(payload.get("aud"))

    if configured_audience:
        if configured_audience not in token_audiences:
            raise UnauthorizedException("Token audience mismatch")
        return

    authorized_party = _strip_trailing_slash(str(payload.get("azp") or ""))
    if not authorized_party:
        raise UnauthorizedException("Token is missing an authorized party claim")
    if authorized_party not in _allowed_authorized_parties():
        raise UnauthorizedException("Token was not issued for this frontend")


def _require_string_claim(payload: dict[str, Any], key: str, detail: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise UnauthorizedException(detail)
    return value


def _personal_org_id(user_id: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in user_id)
    return f"personal_{normalized}"


def _extract_org_id(payload: dict[str, Any], user_id: str) -> str:
    direct_org_id = str(payload.get("org_id") or "").strip()
    if direct_org_id:
        return direct_org_id

    org_claim = payload.get("o")
    if isinstance(org_claim, dict):
        nested_org_id = str(org_claim.get("id") or "").strip()
        if nested_org_id:
            return nested_org_id

    return _personal_org_id(user_id)


def _extract_email(payload: dict[str, Any], user_id: str) -> str:
    for key in ("email", "email_address", "primary_email_address"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return f"{user_id}@users.clerk.local"


def _extract_name(payload: dict[str, Any]) -> str:
    explicit_name = str(payload.get("name") or "").strip()
    if explicit_name:
        return explicit_name

    first_name = str(payload.get("first_name") or "").strip()
    last_name = str(payload.get("last_name") or "").strip()
    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    return full_name or "Authenticated User"


def _extract_org_name(payload: dict[str, Any], org_id: str, name: str = "") -> str:
    for key in ("org_name", "organization_name", "org_slug"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value

    org_claim = payload.get("o")
    if isinstance(org_claim, dict):
        for key in ("slg", "id"):
            value = str(org_claim.get(key) or "").strip()
            if value:
                return value

    if org_id.startswith("personal_"):
        owner_name = name.strip()
        if owner_name:
            suffix = "'" if owner_name.endswith("s") else "'s"
            return f"{owner_name}{suffix} Workspace"
        return "Personal Workspace"

    return f"Organization {org_id[:8]}"


def _validate_session_status(payload: dict[str, Any]) -> None:
    if str(payload.get("sts") or "").strip().lower() == "pending":
        raise UnauthorizedException("Session is pending organization activation")


def _jwt_leeway_seconds() -> int:
    return max(0, int(settings.CLERK_JWT_LEEWAY_SECONDS))


def _allows_degraded_auth() -> bool:
    return settings.APP_ENV == "development"


def _allows_local_auth_bypass() -> bool:
    return settings.APP_ENV == "development" and settings.CODEX_E2E_AUTH_BYPASS


def _local_auth_bypass_payload() -> dict[str, Any]:
    return {
        "sub": "codex_e2e_user",
        "org_id": "codex_e2e_org",
        "email": "codex-e2e@example.local",
        "name": "Codex E2E User",
        "azp": _strip_trailing_slash(settings.FRONTEND_URL),
    }


def _context_from_claims(
    token_payload: dict[str, Any],
    *,
    role: str = UserRole.ADMIN.value,
) -> AuthenticatedContext:
    user_id = _require_string_claim(token_payload, "sub", "User ID not found in token")
    return AuthenticatedContext(
        user_id=user_id,
        org_id=_extract_org_id(token_payload, user_id),
        email=_extract_email(token_payload, user_id),
        name=_extract_name(token_payload),
        role=role,
        token_payload=token_payload,
    )


def _raise_auth_database_unavailable(exc: BaseException) -> None:
    raise AuthConfigurationException(
        "Authentication sync is unavailable because the database connection is unavailable. "
        "Check DATABASE_URL/DIRECT_URL and restart the backend."
    ) from exc


def _handle_auth_database_unavailable(
    exc: BaseException,
    token_payload: dict[str, Any],
) -> AuthenticatedContext:
    if _allows_degraded_auth():
        return _context_from_claims(token_payload)
    _raise_auth_database_unavailable(exc)


@lru_cache(maxsize=1)
def get_jwks() -> dict[str, Any]:
    """Fetch the Clerk JWKS used to verify session JWTs."""
    if not settings.CLERK_SECRET_KEY:
        raise AuthConfigurationException("CLERK_SECRET_KEY is not configured")

    response = httpx.get(
        settings.CLERK_JWKS_URL,
        headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
        timeout=10.0,
    )
    response.raise_for_status()
    return response.json()


def _get_rsa_key(kid: str) -> dict[str, str]:
    for refresh in (False, True):
        if refresh:
            get_jwks.cache_clear()

        jwks = get_jwks()
        keys = jwks.get("keys", [])

        for key in keys:
            if key.get("kid") == kid:
                return {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }

    raise UnauthorizedException("Unable to find the token signing key")


async def verify_token(request: Request) -> dict[str, Any]:
    """
    Verify the Clerk JWT from the Authorization header.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedException("Missing or invalid Authorization header")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise UnauthorizedException("Missing bearer token")
    if token == "codex-e2e-auth-bypass":
        if _allows_local_auth_bypass():
            return _local_auth_bypass_payload()
        raise UnauthorizedException("Local auth bypass is only available in development when explicitly enabled")

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = str(unverified_header.get("kid") or "").strip()
        if not kid:
            raise UnauthorizedException("Invalid token header")

        rsa_key = _get_rsa_key(kid)
        public_key = RSAAlgorithm.from_jwk(json.dumps(rsa_key))

        decode_kwargs: dict[str, Any] = {
            "jwt": token,
            "key": public_key,
            "algorithms": ["RS256"],
            "leeway": _jwt_leeway_seconds(),
        }
        if settings.CLERK_JWT_AUDIENCE:
            decode_kwargs["audience"] = settings.CLERK_JWT_AUDIENCE
        else:
            decode_kwargs["options"] = {"verify_aud": False}
        if settings.CLERK_JWT_ISSUER:
            decode_kwargs["issuer"] = settings.CLERK_JWT_ISSUER

        payload = jwt.decode(**decode_kwargs)
        _validate_token_target(payload)
        _validate_session_status(payload)
        return payload
    except AuthConfigurationException:
        raise
    except UnauthorizedException:
        raise
    except httpx.HTTPError as exc:
        raise AuthConfigurationException(f"Unable to fetch Clerk JWKS: {exc}") from exc
    except jwt.exceptions.ExpiredSignatureError as exc:
        raise UnauthorizedException("Token expired") from exc
    except jwt.exceptions.InvalidTokenError as exc:
        raise UnauthorizedException(f"Invalid token claims: {exc}") from exc
    except Exception as exc:
        raise UnauthorizedException(f"Invalid token: {exc}") from exc


async def get_auth_context(
    db: Prisma = Depends(get_db),
    token_payload: dict[str, Any] = Depends(verify_token),
) -> AuthenticatedContext:
    """Resolve the verified token into an existing local application identity."""
    claim_context = _context_from_claims(token_payload, role=UserRole.ANALYST.value)

    try:
        organization = await db.organization.find_unique(where={"id": claim_context.org_id})
        if not organization:
            raise ForbiddenException("Authenticated organization has not been provisioned")

        user = await db.user.find_unique(where={"id": claim_context.user_id})
        if not user:
            raise ForbiddenException("Authenticated user has not been provisioned")
        if user.org_id != claim_context.org_id:
            raise ForbiddenException("Authenticated user is not assigned to this organization")
    except HTTPException:
        raise
    except Exception as exc:
        if is_database_unavailable_error(exc):
            return _handle_auth_database_unavailable(exc, token_payload)
        raise

    return AuthenticatedContext(
        user_id=claim_context.user_id,
        org_id=claim_context.org_id,
        email=claim_context.email,
        name=claim_context.name,
        role=str(getattr(user, "role", "analyst") or "analyst"),
        token_payload=token_payload,
    )


async def get_current_user(auth_context: AuthenticatedContext = Depends(get_auth_context)) -> str:
    """Returns the current user ID."""
    return auth_context.user_id


async def sync_auth_context(
    db: Prisma = Depends(get_db),
    token_payload: dict[str, Any] = Depends(verify_token),
) -> AuthenticatedContext:
    """Create or refresh the local principal mapping from verified Clerk claims."""
    claim_context = _context_from_claims(token_payload, role=UserRole.ANALYST.value)

    try:
        organization = await db.organization.find_unique(where={"id": claim_context.org_id})
        if not organization:
            await db.organization.create(
                data={
                    "id": claim_context.org_id,
                    "name": _extract_org_name(token_payload, claim_context.org_id, claim_context.name),
                }
            )

        user = await db.user.find_unique(where={"id": claim_context.user_id})
        if user:
            if user.org_id != claim_context.org_id:
                raise ForbiddenException("Authenticated user is not assigned to this organization")

            update_data: dict[str, Any] = {}
            if user.email != claim_context.email:
                existing_email_owner = await db.user.find_unique(where={"email": claim_context.email})
                if existing_email_owner and existing_email_owner.id != claim_context.user_id:
                    raise ForbiddenException("Authenticated email is already assigned to another account")
                update_data["email"] = claim_context.email
            if user.name != claim_context.name:
                update_data["name"] = claim_context.name
            if update_data:
                await db.user.update(where={"id": claim_context.user_id}, data=update_data)
        else:
            existing_email_owner = await db.user.find_unique(where={"email": claim_context.email})
            if existing_email_owner and existing_email_owner.id != claim_context.user_id:
                raise ForbiddenException("Authenticated email is already assigned to another account")

            await db.user.create(
                data={
                    "id": claim_context.user_id,
                    "email": claim_context.email,
                    "name": claim_context.name,
                    "org_id": claim_context.org_id,
                }
            )
    except HTTPException:
        raise
    except Exception as exc:
        if is_database_unavailable_error(exc):
            return _handle_auth_database_unavailable(exc, token_payload)
        raise

    return AuthenticatedContext(
        user_id=claim_context.user_id,
        org_id=claim_context.org_id,
        email=claim_context.email,
        name=claim_context.name,
        role=str(getattr(user, "role", "analyst") or "analyst"),
        token_payload=token_payload,
    )
