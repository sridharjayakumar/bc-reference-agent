"""Adobe IMS token validation service."""

import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings


@dataclass
class IMSUserInfo:
    """Validated IMS user information."""

    user_id: str
    email: str
    expires_at: datetime
    org_id: str | None = None


class IMSValidationError(Exception):
    """Raised when IMS token validation fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class IMSTokenValidator:
    """
    Validates Adobe IMS access tokens via the userinfo endpoint.

    Implements caching to reduce calls to IMS. Cache keys are hashed
    tokens (never store raw tokens in cache).
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[IMSUserInfo, float]] = {}
        self._cache_ttl = settings.ims_validation_cache_ttl

    async def validate_token(self, token: str) -> IMSUserInfo:
        """
        Validate an IMS access token.

        Args:
            token: The IMS access token to validate

        Returns:
            IMSUserInfo with validated user information

        Raises:
            IMSValidationError: If token is invalid or expired
        """
        # Check cache first
        cache_key = self._hash_token(token)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached

        # Call IMS userinfo endpoint
        user_info = await self._call_ims_userinfo(token)

        # Cache the result
        self._add_to_cache(cache_key, user_info)

        return user_info

    async def _call_ims_userinfo(self, token: str) -> IMSUserInfo:
        """Call IMS userinfo/v2 endpoint to validate token."""
        url = f"{settings.ims_base_url}/ims/userinfo/v2"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        if settings.ims_client_id:
            headers["X-Api-Key"] = settings.ims_client_id

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=10.0)
            except httpx.RequestError as e:
                raise IMSValidationError(f"Failed to contact IMS: {str(e)}") from e

            if response.status_code == 401:
                raise IMSValidationError("Invalid or expired token", status_code=401)
            elif response.status_code == 403:
                raise IMSValidationError("Token lacks required permissions", status_code=403)
            elif response.status_code != 200:
                raise IMSValidationError(
                    f"IMS validation failed with status {response.status_code}",
                    status_code=response.status_code,
                )

            data = response.json()
            return self._parse_userinfo_response(data)

    def _parse_userinfo_response(self, data: dict[str, Any]) -> IMSUserInfo:
        """Parse IMS userinfo response into IMSUserInfo."""
        from datetime import timedelta

        user_id = data.get("sub") or data.get("userId")
        if not user_id:
            raise IMSValidationError("Missing user ID in IMS response")

        email = data.get("email", "")

        # Parse expiry - handle different formats
        if "expires_in" in data:
            expires_at = datetime.now(UTC) + timedelta(seconds=data["expires_in"])
        elif "exp" in data:
            expires_at = datetime.fromtimestamp(data["exp"], tz=UTC)
        else:
            # Default to 1 hour expiry
            expires_at = datetime.now(UTC) + timedelta(hours=1)

        org_id = data.get("companyId") or data.get("org_id")

        return IMSUserInfo(
            user_id=user_id,
            email=email,
            expires_at=expires_at,
            org_id=org_id,
        )

    def _hash_token(self, token: str) -> str:
        """Hash token for use as cache key. Never store raw tokens."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _get_from_cache(self, cache_key: str) -> IMSUserInfo | None:
        """Get user info from cache if valid."""
        if cache_key not in self._cache:
            return None

        user_info, cached_at = self._cache[cache_key]

        # Check if cache entry has expired
        if time.time() - cached_at > self._cache_ttl:
            del self._cache[cache_key]
            return None

        # Check if token itself has expired
        if user_info.expires_at < datetime.now(UTC):
            del self._cache[cache_key]
            return None

        return user_info

    def _add_to_cache(self, cache_key: str, user_info: IMSUserInfo) -> None:
        """Add user info to cache."""
        self._cache[cache_key] = (user_info, time.time())

    def clear_cache(self) -> None:
        """Clear the validation cache."""
        self._cache.clear()


# Global validator instance
ims_validator = IMSTokenValidator()
