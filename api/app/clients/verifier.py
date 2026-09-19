"""Identity verification, behind a protocol.

The API must verify identity on its own — Clerk hands the browser a JWT and we
check it against Clerk's JWKS rather than calling back into the frontend. The
protocol is the seam the default test suite swaps, exactly like `build_clients`.

Deliberately no `DEV_AUTH`-style bypass: an env var that disables auth is one
misconfigured variable away from an open API, and the failure is silent because
everything still works. The injected fake gives tests the same ergonomics with
no bypass present in shipped code.
"""

import asyncio
import logging
from typing import Protocol

log = logging.getLogger(__name__)


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> str | None:
        """Return the token's subject claim, or None if it does not verify."""
        ...


class ClerkVerifier:
    """Verifies an RS256 JWT against Clerk's JWKS endpoint."""

    def __init__(self, jwks_url: str | None = None, issuer: str | None = None) -> None:
        import jwt

        from app.config import get_settings

        settings = get_settings()
        self._issuer = issuer or settings.clerk_issuer or None
        # PyJWKClient caches keys, so the JWKS fetch is once per key rotation.
        self._jwks = jwt.PyJWKClient(jwks_url or settings.clerk_jwks_url, cache_keys=True)

    def _verify_sync(self, token: str) -> str | None:
        import jwt

        try:
            key = self._jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self._issuer,
                # Clerk session tokens carry no `aud` by default.
                options={"verify_aud": False},
            )
        except Exception as exc:  # noqa: BLE001 — any failure is "not authenticated"
            log.info("token verification failed: %s", exc)
            return None
        return claims.get("sub")

    async def verify(self, token: str) -> str | None:
        # PyJWKClient does blocking HTTP on a cache miss; off the event loop it
        # would stall every concurrent request behind one key fetch.
        return await asyncio.to_thread(self._verify_sync, token)
