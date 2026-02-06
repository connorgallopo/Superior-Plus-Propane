"""Superior Plus Propane API Client — base class, exceptions, factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import aiohttp

    from .region import RegionConfig

# HTTP Status Codes
HTTP_OK = 200

# Error messages
SESSION_EXPIRED_MSG = "Session expired"


class SuperiorPlusPropaneApiClientError(Exception):
    """Exception to indicate a general API error."""


class SuperiorPlusPropaneApiClientCommunicationError(
    SuperiorPlusPropaneApiClientError,
):
    """Exception to indicate a communication error."""


class SuperiorPlusPropaneApiClientAuthenticationError(
    SuperiorPlusPropaneApiClientError,
):
    """Exception to indicate an authentication error."""


class SuperiorPropaneApiBase(ABC):
    """Abstract base for region-specific API clients."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        region_config: RegionConfig,
    ) -> None:
        """Initialize the API client."""
        self._username = username
        self._password = password
        self._session = session
        self._region_config = region_config
        self._authenticated = False
        self._auth_in_progress = False

    @abstractmethod
    async def async_get_tanks_data(self) -> list[dict[str, Any]]:
        """Get tank data from the portal. Must return normalized tank dicts."""

    async def async_get_orders_data(self) -> dict[str, Any]:
        """Get orders data. Override in subclasses that support it."""
        return {}

    async def async_test_connection(self) -> bool:
        """Test connection by fetching tanks."""
        try:
            tanks = await self.async_get_tanks_data()
        except SuperiorPlusPropaneApiClientAuthenticationError:
            return False
        except SuperiorPlusPropaneApiClientError:
            return False
        else:
            return len(tanks) > 0

    async def async_close(self) -> None:
        """Close the API client session."""
        if self._session and not self._session.closed:
            await self._session.close()


def create_api_client(
    region: str,
    username: str,
    password: str,
    session: aiohttp.ClientSession,
    region_config: RegionConfig,
) -> SuperiorPropaneApiBase:
    """Create the appropriate API client for the given region."""
    if region == "ca":
        from .api_ca import SuperiorPropaneCAApiClient

        return SuperiorPropaneCAApiClient(username, password, session, region_config)

    from .api_us import SuperiorPropaneUSApiClient

    return SuperiorPropaneUSApiClient(username, password, session, region_config)
