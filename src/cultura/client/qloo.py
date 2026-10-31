"""
CULTURA: Autonomous Cultural Intelligence & Taste Graph Agent.
Asynchronous Qloo API Client with Transparent Offline Mock Fallback.
Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Union

import httpx

from cultura.agent.tools import (
    AffinityScore,
    CulturalDomain,
    CulturalEntity,
)
from cultura.client.mock_data import (
    CURATED_AFFINITIES,
    ENTITIES_BY_DOMAIN,
    ENTITIES_BY_HUB,
    ENTITIES_BY_ID,
    MOCK_ENTITIES,
    SUPPORTED_HUBS,
    compute_deterministic_affinities,
    find_mock_entities,
    normalize_domain,
    normalize_hub,
)

logger = logging.getLogger("cultura.client.qloo")


# ============================================================================
# Exception Hierarchy
# ============================================================================

class QlooError(Exception):
    """Base exception for all Qloo client operations."""
    pass


class QlooAPIError(QlooError):
    """Raised when live Qloo API returns an HTTP error status (4xx/5xx)."""

    def __init__(self, status_code: int, message: str, body: Optional[str] = None) -> None:
        self.status_code = status_code
        self.message = message
        self.body = body
        super().__init__(f"Qloo API Error [{status_code}]: {message}")


class QlooNetworkError(QlooError):
    """Raised on connection failure, DNS resolution error, or network timeout."""
    pass


class QlooEntityNotFoundError(QlooError):
    """Raised when a requested entity ID does not exist in catalog."""
    pass


class QlooInvalidDomainError(ValueError, QlooError):
    """Raised when an unrecognized cultural domain is specified."""
    pass


class QlooInvalidHubError(ValueError, QlooError):
    """Raised when an unrecognized cultural hub is specified."""
    pass


# ============================================================================
# QlooClient Implementation
# ============================================================================

class QlooClient:
    """Asynchronous client for Qloo Taste AI API with seamless offline mock fallback.

    Parameters
    ----------
    api_key : Optional[str]
        Qloo API key. If not provided, checks QLOO_API_KEY environment variable.
        If still absent, client operates in offline mock mode.
    base_url : Optional[str]
        Base URL for the Qloo API. Defaults to https://api.qloo.com/v2 or QLOO_BASE_URL.
    timeout : float
        Request timeout in seconds (default 10.0s, with 3.0s connect timeout).
    use_mock_fallback : bool
        If True, transparently falls back to mock catalog on network error or missing key.
        If False, re-raises network and API exceptions.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 10.0,
        use_mock_fallback: bool = True,
    ) -> None:
        self.api_key = api_key or os.getenv("QLOO_API_KEY")
        self.base_url = (base_url or os.getenv("QLOO_BASE_URL", "https://api.qloo.com/v2")).rstrip("/")
        self.timeout = timeout
        self.use_mock_fallback = use_mock_fallback

        # Determine offline mode
        self.is_offline = not bool(self.api_key and self.api_key.strip())

        if self.is_offline and not self.use_mock_fallback:
            raise ValueError("API key missing and use_mock_fallback is disabled.")

        self._http_client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "QlooClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Closes the underlying HTTP client session."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily initialize the httpx.AsyncClient on the active event loop."""
        if self._http_client is None or self._http_client.is_closed:
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "CULTURA-Agent/1.0.0 (Qloo-Hackathon)",
            }
            if self.api_key:
                headers["X-Api-Key"] = self.api_key
                headers["Authorization"] = f"Bearer {self.api_key}"

            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout, connect=3.0),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=30.0),
            )
        return self._http_client

    async def health_check(self) -> Dict[str, Any]:
        """Ultra-fast (<5ms) diagnostic check reporting operational mode and catalog status."""
        start_time = time.perf_counter()

        if self.is_offline:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "status": "healthy",
                "mode": "offline_mock",
                "entities_count": len(MOCK_ENTITIES),
                "hubs_count": len(SUPPORTED_HUBS),
                "hubs_available": sorted(list(SUPPORTED_HUBS)),
                "latency_ms": round(elapsed_ms, 3),
            }

        # Live health ping
        try:
            client = await self._get_client()
            response = await client.get("/search", params={"query": "test", "limit": 1})
            if response.status_code >= 400:
                raise QlooAPIError(response.status_code, response.text, response.text)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "status": "healthy",
                "mode": "live",
                "entities_count": len(MOCK_ENTITIES),
                "hubs_count": len(SUPPORTED_HUBS),
                "hubs_available": sorted(list(SUPPORTED_HUBS)),
                "latency_ms": round(elapsed_ms, 3),
            }
        except Exception as exc:
            logger.warning("Live health check failed: %s", exc)
            if self.use_mock_fallback:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return {
                    "status": "healthy",
                    "mode": "offline_mock_fallback",
                    "entities_count": len(MOCK_ENTITIES),
                    "hubs_count": len(SUPPORTED_HUBS),
                    "hubs_available": sorted(list(SUPPORTED_HUBS)),
                    "latency_ms": round(elapsed_ms, 3),
                    "notice": f"Live ping failed ({exc.__class__.__name__}); fallback active.",
                }
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "status": "error",
                "mode": "live",
                "error": str(exc),
                "latency_ms": round(elapsed_ms, 3),
            }

    async def search_entities(
        self,
        query: str,
        domain: Optional[Union[CulturalDomain, str]] = None,
        hub: Optional[str] = None,
        limit: int = 10,
    ) -> List[CulturalEntity]:
        """Search cultural entities across domains and hubs by name, keyword, or vibe tag."""
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        query_clean = query.strip()
        if not query_clean:
            return []

        try:
            resolved_domain = normalize_domain(domain)
        except ValueError as e:
            raise QlooInvalidDomainError(str(e)) from e

        resolved_hub = normalize_hub(hub)

        if not self.is_offline:
            try:
                client = await self._get_client()
                params: Dict[str, Any] = {"query": query_clean, "limit": limit}
                if resolved_domain:
                    params["domain"] = resolved_domain.value
                if resolved_hub:
                    params["hub"] = resolved_hub

                resp = await client.get("/search", params=params)
                if resp.status_code >= 400:
                    error_msg = f"HTTP {resp.status_code}: {resp.text}"
                    if not self.use_mock_fallback:
                        raise QlooAPIError(resp.status_code, error_msg, resp.text)
                    logger.warning("Live search returned HTTP %d. Using fallback.", resp.status_code)
                else:
                    data = resp.json()
                    items = data.get("results", data) if isinstance(data, dict) else data
                    if isinstance(items, list):
                        return [CulturalEntity.model_validate(item) for item in items[:limit]]
            except QlooAPIError:
                raise
            except Exception as exc:
                logger.warning("Live search failed: %s. Using fallback.", exc)
                if not self.use_mock_fallback:
                    if isinstance(exc, httpx.HTTPStatusError):
                        raise QlooAPIError(exc.response.status_code, str(exc), exc.response.text) from exc
                    raise QlooNetworkError(str(exc)) from exc

        # Execute mock fallback
        return find_mock_entities(
            query=query_clean,
            domain=resolved_domain,
            hub=resolved_hub,
            limit=limit,
        )

    async def get_cross_domain_affinities(
        self,
        entity_id: str,
        target_domain: Union[CulturalDomain, str],
        hub: Optional[str] = None,
        limit: int = 5,
    ) -> List[AffinityScore]:
        """Calculate cross-domain affinities from a source entity to entities in a target domain."""
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        try:
            resolved_target_domain = normalize_domain(target_domain)
        except ValueError as e:
            raise QlooInvalidDomainError(str(e)) from e

        if resolved_target_domain is None:
            raise QlooInvalidDomainError(f"Invalid target domain: '{target_domain}'")

        resolved_hub = normalize_hub(hub)

        if not self.is_offline:
            try:
                client = await self._get_client()
                params: Dict[str, Any] = {
                    "entity_id": entity_id,
                    "target_domain": resolved_target_domain.value,
                    "limit": limit,
                }
                if resolved_hub:
                    params["hub"] = resolved_hub

                resp = await client.get("/v2/insights", params=params)
                if resp.status_code >= 400:
                    error_msg = f"HTTP {resp.status_code}: {resp.text}"
                    if not self.use_mock_fallback:
                        raise QlooAPIError(resp.status_code, error_msg, resp.text)
                    logger.warning("Live affinity query returned HTTP %d. Using fallback.", resp.status_code)
                else:
                    data = resp.json()
                    items = data.get("affinities", data) if isinstance(data, dict) else data
                    if isinstance(items, list):
                        return [AffinityScore.model_validate(item) for item in items[:limit]]
            except QlooAPIError:
                raise
            except Exception as exc:
                logger.warning("Live affinity query failed: %s. Using fallback.", exc)
                if not self.use_mock_fallback:
                    if isinstance(exc, httpx.HTTPStatusError):
                        raise QlooAPIError(exc.response.status_code, str(exc), exc.response.text) from exc
                    raise QlooNetworkError(str(exc)) from exc

        # Mock fallback verification
        source_entity = ENTITIES_BY_ID.get(entity_id)
        if source_entity is None:
            raise QlooEntityNotFoundError(f"Entity '{entity_id}' not found in catalog.")

        return compute_deterministic_affinities(
            source_entity=source_entity,
            target_domain=resolved_target_domain,
            hub=resolved_hub,
            limit=limit,
        )

    async def get_entity(self, entity_id: str) -> Optional[CulturalEntity]:
        """Retrieve full metadata for a specific entity by unique ID."""
        if not entity_id or not entity_id.strip():
            return None

        clean_id = entity_id.strip()

        if not self.is_offline:
            try:
                client = await self._get_client()
                resp = await client.get(f"/entities/{clean_id}")
                if resp.status_code == 404:
                    return None
                if resp.status_code >= 400:
                    error_msg = f"HTTP {resp.status_code}: {resp.text}"
                    if not self.use_mock_fallback:
                        raise QlooAPIError(resp.status_code, error_msg, resp.text)
                    logger.warning("Live entity fetch returned HTTP %d. Using fallback.", resp.status_code)
                else:
                    return CulturalEntity.model_validate(resp.json())
            except QlooAPIError:
                raise
            except Exception as exc:
                logger.warning("Live entity fetch failed: %s. Using fallback.", exc)
                if not self.use_mock_fallback:
                    if isinstance(exc, httpx.HTTPStatusError):
                        raise QlooAPIError(exc.response.status_code, str(exc), exc.response.text) from exc
                    raise QlooNetworkError(str(exc)) from exc

        return ENTITIES_BY_ID.get(clean_id)

    async def get_hub_entities(
        self,
        hub: str,
        domain: Optional[Union[CulturalDomain, str]] = None,
    ) -> List[CulturalEntity]:
        """Retrieve cultural entities for a designated hub, optionally filtered by domain."""
        resolved_hub = normalize_hub(hub)
        if not resolved_hub or resolved_hub not in SUPPORTED_HUBS:
            raise QlooInvalidHubError(f"Unsupported cultural hub: '{hub}'. Supported: {sorted(SUPPORTED_HUBS)}")

        try:
            resolved_domain = normalize_domain(domain)
        except ValueError as e:
            raise QlooInvalidDomainError(str(e)) from e

        if not self.is_offline:
            try:
                client = await self._get_client()
                params: Dict[str, Any] = {"hub": resolved_hub}
                if resolved_domain:
                    params["domain"] = resolved_domain.value
                resp = await client.get("/search", params=params)
                if resp.status_code >= 400:
                    error_msg = f"HTTP {resp.status_code}: {resp.text}"
                    if not self.use_mock_fallback:
                        raise QlooAPIError(resp.status_code, error_msg, resp.text)
                    logger.warning("Live hub fetch returned HTTP %d. Using fallback.", resp.status_code)
                else:
                    data = resp.json()
                    items = data.get("results", data) if isinstance(data, dict) else data
                    if isinstance(items, list):
                        return [CulturalEntity.model_validate(item) for item in items]
            except QlooAPIError:
                raise
            except Exception as exc:
                logger.warning("Live hub fetch failed: %s. Using fallback.", exc)
                if not self.use_mock_fallback:
                    if isinstance(exc, httpx.HTTPStatusError):
                        raise QlooAPIError(exc.response.status_code, str(exc), exc.response.text) from exc
                    raise QlooNetworkError(str(exc)) from exc

        # Mock fallback
        hub_entities = ENTITIES_BY_HUB.get(resolved_hub, [])
        if resolved_domain:
            return [e for e in hub_entities if e.domain == resolved_domain]
        return list(hub_entities)
