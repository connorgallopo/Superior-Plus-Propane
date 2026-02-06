"""Superior Plus Propane Canadian API Client."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup

from .api import (
    HTTP_OK,
    SuperiorPlusPropaneApiClientAuthenticationError,
    SuperiorPlusPropaneApiClientCommunicationError,
    SuperiorPlusPropaneApiClientError,
    SuperiorPropaneApiBase,
)
from .const import LOGGER

if TYPE_CHECKING:
    import aiohttp

    from .region import RegionConfig

# CA Portal URLs
_DASHBOARD_URL = "https://mysuperior.superiorpropane.com/dashboard"
_LOGIN_PAGE_URL = "https://mysuperior.superiorpropane.com/account/individualLogin"
_LOGIN_URL = "https://mysuperior.superiorpropane.com/account/loginFirst"
_ORDERS_URL = "https://mysuperior.superiorpropane.com/myaccount/getAllOrders"
_TANK_DATA_URL = "https://mysuperior.superiorpropane.com/myaccount/readTanks"

# Pagination
_TANK_PAGE_SIZE = 10

# Magic number threshold for order columns
_ORDER_COLUMN_COUNT = 5


class SuperiorPropaneCAApiClient(SuperiorPropaneApiBase):
    """Canadian Superior Propane API Client — JSON + HTML endpoints."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        region_config: RegionConfig,
    ) -> None:
        """Initialize the CA API client."""
        super().__init__(username, password, session, region_config)
        self._headers = {
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            ),
            "accept-language": "en-US,en;q=0.9,fr-CA;q=0.8",
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "origin": "https://mysuperior.superiorpropane.com",
            "sec-ch-ua": (
                '"Chromium";v="129", "Not=A?Brand";v="8", "Google Chrome";v="129"'
            ),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/129.0.0.0 Safari/537.36"
            ),
        }

    async def async_get_tanks_data(self) -> list[dict[str, Any]]:
        """Get tank data — clears cookies and re-auths every call."""
        self._session.cookie_jar.clear()
        self._authenticated = False
        await self._ensure_authenticated()
        return await self._get_tanks_from_api()

    async def async_get_orders_data(self) -> dict[str, Any]:
        """Get orders data from the CA portal."""
        return await self._get_orders_totals()

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authenticated session."""
        if self._authenticated:
            try:
                async with asyncio.timeout(60):
                    response = await self._session.get(
                        _DASHBOARD_URL,
                        headers=self._headers,
                        allow_redirects=True,
                    )
                    if "individualLogin" in str(response.url):
                        LOGGER.debug("Redirected to login, re-authenticating")
                        self._authenticated = False
                    if response.status != HTTP_OK:
                        LOGGER.debug("HTTP failed, re-authenticating")
                        self._authenticated = False
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Error validating CA session: %s", exc)
                self._authenticated = False

        if not self._authenticated:
            await self._authenticate()
            if self._region_config.auth_settle_delay > 0:
                await asyncio.sleep(self._region_config.auth_settle_delay)

    async def _authenticate(self) -> None:
        """Perform CA authentication sequence."""
        if self._auth_in_progress:
            return

        self._auth_in_progress = True
        try:
            LOGGER.debug("Starting CA authentication sequence")

            async with asyncio.timeout(60):
                response = await self._session.get(
                    _LOGIN_PAGE_URL,
                    headers=self._headers,
                    allow_redirects=True,
                )
                if "maintenance" in str(response.url):
                    msg = "Site under scheduled maintenance"
                    raise SuperiorPlusPropaneApiClientCommunicationError(msg)  # noqa: TRY301
                if response.status != HTTP_OK:
                    msg = f"Login page returned {response.status}"
                    raise SuperiorPlusPropaneApiClientCommunicationError(msg)  # noqa: TRY301
                await response.text()

            csrf_token = await self._get_csrf_token()
            if not csrf_token:
                msg = "CSRF token not found in login page"
                raise SuperiorPlusPropaneApiClientAuthenticationError(msg)  # noqa: TRY301

            await self._login(csrf_token)

            self._authenticated = True
            LOGGER.debug("CA authentication successful")

        except (
            SuperiorPlusPropaneApiClientAuthenticationError,
            SuperiorPlusPropaneApiClientCommunicationError,
            TimeoutError,
        ):
            self._authenticated = False
            raise
        except Exception as exc:
            self._authenticated = False
            msg = f"Authentication failed: {exc}"
            raise SuperiorPlusPropaneApiClientAuthenticationError(msg) from exc
        finally:
            self._auth_in_progress = False

    async def _get_csrf_token(self) -> str | None:
        """Get CSRF token from cookies ('csrf_cookie_name')."""
        for cookie in self._session.cookie_jar:
            if cookie.key == "csrf_cookie_name":
                LOGGER.debug("Found CSRF token in cookie")
                return cookie.value

        LOGGER.debug("CSRF cookie not found — fetching login page")
        retries = self._region_config.max_api_retries
        for attempt in range(1, retries + 1):
            try:
                async with asyncio.timeout(60):
                    response = await self._session.get(
                        _LOGIN_PAGE_URL, headers=self._headers
                    )
                    if response.status != HTTP_OK:
                        msg = f"Failed to get login page: {response.status}"
                        raise SuperiorPlusPropaneApiClientCommunicationError(msg)  # noqa: TRY301

                for cookie in self._session.cookie_jar:
                    if cookie.key == "csrf_cookie_name":
                        LOGGER.debug("CSRF token obtained after page load")
                        return cookie.value

                LOGGER.warning("CSRF token still not found (attempt %d)", attempt)
                if attempt == retries:
                    msg = "CSRF cookie 'csrf_cookie_name' not found"
                    raise SuperiorPlusPropaneApiClientAuthenticationError(msg)

                await asyncio.sleep(3 + (attempt * 2))

            except (
                TimeoutError,
                SuperiorPlusPropaneApiClientCommunicationError,
            ) as exc:
                LOGGER.warning(
                    "Timeout getting CSRF token (attempt %d): %s",
                    attempt,
                    exc,
                )
                if attempt == retries:
                    msg = "Timeout getting CSRF token after retries"
                    raise SuperiorPlusPropaneApiClientCommunicationError(msg) from exc

        return None

    async def _login(self, csrf_token: str) -> None:
        """Perform CA login with CSRF token."""
        payload = {
            "csrf_superior_token": csrf_token,
            "login_email": self._username,
            "login_password": self._password,
        }

        login_headers = self._headers.copy()
        login_headers.update(
            {
                "content-type": "application/x-www-form-urlencoded",
                "referer": _LOGIN_PAGE_URL,
                "x-requested-with": "XMLHttpRequest",
            }
        )

        retries = self._region_config.max_api_retries
        for attempt in range(1, retries + 1):
            try:
                async with asyncio.timeout(60):
                    response = await self._session.post(
                        _LOGIN_URL,
                        headers=login_headers,
                        data=payload,
                        allow_redirects=True,
                    )

                if "dashboard" in str(response.url):
                    LOGGER.debug("CA login successful — redirected to dashboard")
                    return

                if "individualLogin" in str(response.url):
                    msg = "Login failed — redirected to login"
                    raise SuperiorPlusPropaneApiClientAuthenticationError(msg)  # noqa: TRY301

                data_html = await response.text()
                msg = f"Unexpected login response: {data_html[:200]}"
                raise SuperiorPlusPropaneApiClientError(msg)

            except TimeoutError as exc:
                LOGGER.warning("Timeout during CA login (attempt %d): %s", attempt, exc)
                if attempt == retries:
                    msg = "Login timeout after retries"
                    raise SuperiorPlusPropaneApiClientCommunicationError(msg) from exc
                await asyncio.sleep(3 + (attempt * 2))

            except SuperiorPlusPropaneApiClientAuthenticationError:
                if attempt == retries:
                    raise
                await asyncio.sleep(3 + (attempt * 2))

    async def _get_tanks_from_api(self) -> list[dict[str, Any]]:  # noqa: PLR0912, PLR0915
        """Get tank data from the CA JSON API (paginated)."""
        tanks_data: list[dict[str, Any]] = []
        offset = 0
        finished = False

        while not finished:
            retries = self._region_config.max_api_retries
            for attempt in range(1, retries + 1):
                try:
                    csrf_token = await self._get_csrf_token()
                    payload = {
                        "csrf_superior_token": csrf_token,
                        "limit": str(_TANK_PAGE_SIZE),
                        "offset": str(offset),
                        "firstRun": "true" if offset == 0 else "false",
                        "listIndex": str(offset + 1),
                    }

                    api_headers = self._headers.copy()
                    api_headers.update(
                        {
                            "content-type": ("application/x-www-form-urlencoded"),
                            "referer": _DASHBOARD_URL,
                            "x-requested-with": "XMLHttpRequest",
                        }
                    )

                    async with asyncio.timeout(60):
                        response = await self._session.post(
                            _TANK_DATA_URL,
                            headers=api_headers,
                            data=payload,
                        )

                        if response.status != HTTP_OK:
                            msg = f"Failed to get tank data: {response.status}"
                            raise SuperiorPlusPropaneApiClientCommunicationError(msg)  # noqa: TRY301

                        data_html = await response.text()
                        response_json = json.loads(data_html)
                        tank_list = json.loads(response_json.get("data", "[]"))

                        if not response_json.get("status"):
                            if tanks_data and not tank_list:
                                LOGGER.debug(
                                    "API returned status=false with empty list"
                                    " — all tanks retrieved"
                                )
                                finished = True
                                break
                            msg = (
                                "Tank API error: "
                                f"{response_json.get('message', 'Unknown')}"
                            )
                            raise SuperiorPlusPropaneApiClientError(msg)

                        if not tank_list:
                            LOGGER.debug("Empty tank list — all retrieved")
                            finished = True
                            break

                        tanks_in_batch = 0
                        for idx, tank in enumerate(tank_list, offset + 1):
                            tank_data = self._parse_tank_json(tank, idx)
                            if tank_data:
                                tanks_data.append(tank_data)
                                tanks_in_batch += 1

                        finished = response_json.get("finished", True)

                        if tanks_in_batch < _TANK_PAGE_SIZE:
                            finished = True

                        offset += _TANK_PAGE_SIZE
                        break

                except json.JSONDecodeError as exc:
                    LOGGER.debug(
                        "JSON parse error (attempt %d): %s",
                        attempt,
                        exc,
                    )
                    if attempt == retries:
                        if tanks_data:
                            LOGGER.warning(
                                "JSON error but returning %d tanks collected",
                                len(tanks_data),
                            )
                            return tanks_data
                        msg = "Failed to get valid JSON after retries"
                        raise SuperiorPlusPropaneApiClientError(msg) from exc
                    await asyncio.sleep(
                        self._region_config.retry_delay_seconds + (attempt * 10)
                    )

                except (
                    TimeoutError,
                    SuperiorPlusPropaneApiClientCommunicationError,
                ) as exc:
                    LOGGER.debug(
                        "Error getting tanks (attempt %d): %s",
                        attempt,
                        exc,
                    )
                    if attempt == retries:
                        if tanks_data:
                            LOGGER.warning(
                                "API error but returning %d tanks collected",
                                len(tanks_data),
                            )
                            return tanks_data
                        msg = "Tank API timeout after retries"
                        raise SuperiorPlusPropaneApiClientCommunicationError(
                            msg
                        ) from exc
                    await asyncio.sleep(
                        self._region_config.retry_delay_seconds + (attempt * 10)
                    )

                except SuperiorPlusPropaneApiClientAuthenticationError:
                    raise

        LOGGER.debug("Parsed %d CA tanks total", len(tanks_data))
        return tanks_data

    async def _get_orders_totals(self) -> dict[str, Any]:
        """Get orders history and compute totals from HTML response."""
        orders_totals: dict[str, Any] = {
            "total_volume": 0,
            "total_cost": 0.0,
            "average_price": 0.0,
        }

        retries = self._region_config.max_api_retries
        for attempt in range(1, retries + 1):
            try:
                csrf_token = await self._get_csrf_token()
                payload = {
                    "csrf_superior_token": csrf_token,
                    "firstRun": "true",
                }

                api_headers = self._headers.copy()
                api_headers.update(
                    {
                        "content-type": "application/x-www-form-urlencoded",
                        "referer": _DASHBOARD_URL,
                        "x-requested-with": "XMLHttpRequest",
                    }
                )

                async with asyncio.timeout(60):
                    response = await self._session.post(
                        _ORDERS_URL,
                        headers=api_headers,
                        data=payload,
                    )

                    if response.status != HTTP_OK:
                        msg = f"Failed to get orders: {response.status}"
                        raise SuperiorPlusPropaneApiClientCommunicationError(msg)  # noqa: TRY301

                    data_html = await response.text()
                    soup = BeautifulSoup(data_html, "html.parser")
                    rows = soup.find_all("div", class_="orders__row cf")

                    for row in rows:
                        cols = row.find_all("div")
                        if len(cols) == _ORDER_COLUMN_COUNT:
                            product = cols[2].text.strip().upper()
                            if "PROPANE" in product:
                                try:
                                    amount_str = (
                                        cols[3].text.strip().split()[0].replace(",", "")
                                    )
                                    price_str = (
                                        cols[4]
                                        .text.strip()
                                        .lstrip("$")
                                        .replace(",", "")
                                    )
                                    litres = int(float(amount_str))
                                    cost = round(float(price_str), 2)
                                    orders_totals["total_volume"] += litres
                                    orders_totals["total_cost"] = round(
                                        orders_totals["total_cost"] + cost, 2
                                    )
                                except ValueError as exc:
                                    LOGGER.warning(
                                        "Invalid order data: %s | Error: %s",
                                        row.text.strip(),
                                        exc,
                                    )

                    total_vol = orders_totals["total_volume"]
                    total_cost = orders_totals["total_cost"]
                    if total_vol > 0:
                        orders_totals["average_price"] = round(
                            total_cost / total_vol, 4
                        )

                    LOGGER.debug(
                        "CA orders: %d L, $%.2f",
                        total_vol,
                        total_cost,
                    )
                    return orders_totals

            except (
                TimeoutError,
                SuperiorPlusPropaneApiClientCommunicationError,
            ) as exc:
                LOGGER.debug("Error getting orders (attempt %d): %s", attempt, exc)
                if attempt == retries:
                    msg = "Failed to get orders after retries"
                    raise SuperiorPlusPropaneApiClientCommunicationError(msg) from exc
                await asyncio.sleep(
                    self._region_config.retry_delay_seconds + (attempt * 10)
                )

            except SuperiorPlusPropaneApiClientAuthenticationError:
                raise

        return orders_totals

    @staticmethod
    def _parse_tank_json(
        tank: dict[str, Any], tank_number: int
    ) -> dict[str, Any] | None:
        """Parse a single CA tank from JSON into normalized common format."""
        try:
            last_fill = tank.get("adds_last_fill", "unknown")
            if last_fill != "unknown" and " " in last_fill:
                last_fill = last_fill.split(" ")[0]

            return {
                # Common normalized fields
                "tank_id": str(tank.get("adds_tank_id", "unknown")),
                "tank_number": tank_number,
                "address": tank.get("adds_location", "Unknown"),
                "tank_name": tank.get("tank_name", "Unknown"),
                "tank_size": str(tank.get("adds_tank_size", "unknown")),
                "tank_type": "Propane",
                "serial_number": str(tank.get("adds_serial_number", "unknown")).strip(),
                "customer_number": str(tank.get("adds_customer_number", "unknown")),
                "level": str(tank.get("adds_fill_percentage", "unknown")),
                "current_volume": str(tank.get("adds_fill", "unknown")),
                "reading_date": str(tank.get("adds_last_reading", "unknown")),
                "last_delivery": last_fill,
                "price_per_unit": "unknown",
                "is_on_delivery_plan": tank.get("isOnDeliveryPlan") == "1",
            }
        except (AttributeError, ValueError, TypeError) as exc:
            LOGGER.warning("Error parsing CA tank JSON %d: %s", tank_number, exc)
            return None
