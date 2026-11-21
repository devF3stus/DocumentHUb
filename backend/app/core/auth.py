from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from app.core.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    """Verified user identity extracted from a Supabase JWT."""

    id: str
    email: str | None = None


def get_supabase_admin_client() -> Client | None:
    """Return a Supabase client using the server-side service role key, if configured."""
    if not settings.supabase_configured:
        return None
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedUser | None:
    """Allow guest requests (no token) while strictly verifying any provided Bearer JWT."""
    if credentials is None:
        return None

    client = get_supabase_admin_client()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured on this server.",
        )

    try:
        user_response = client.auth.get_user(credentials.credentials)
        user = getattr(user_response, "user", None)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token.",
            )
        return AuthenticatedUser(id=str(user.id), email=getattr(user, "email", None))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        ) from exc


async def require_authenticated_user(
    user: AuthenticatedUser | None = Depends(get_current_user_optional),
) -> AuthenticatedUser:
    """Require a valid authenticated user for protected routes."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication is required for this operation.",
        )
    return user
