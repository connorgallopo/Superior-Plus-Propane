"""Superior Plus Propane US API Client."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any

from bs4 import BeautifulSoup
from bs4.element import Tag
from slugify import slugify

from .api import (
    HTTP_OK,
    SESSION_EXPIRED_MSG,
    SuperiorPlusPropaneApiClientAuthenticationError,
    SuperiorPlusPropaneApiClientCommunicationError,
    SuperiorPlusPropaneApiClientError,
    SuperiorPropaneApiBase,
)
from .const import LOGGER

if TYPE_CHECKING:
    import aiohttp

    from .region import RegionConfig

# US Portal URLs
_LOGIN_PAGE_URL = "https://mysuperioraccountlogin.com/Account/Login?ReturnUrl=%2F"
_LOGIN_URL = "https://mysuperioraccountlogin.com/Account/Login?ReturnUrl=%2F"
_HOME_URL = "https://mysuperioraccountlogin.com/"
_CUSTOMERS_URL = "https://mysuperioraccountlogin.com/Customers"
_TANK_URL = "https://mysuperioraccountlogin.com/Tank"


class SuperiorPropaneUSApiClient(SuperiorPropaneApiBase):
    """US Superior Plus Propane API Client — HTML scraping."""

    def __init__(
        self,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        region_config: RegionConfig,
    ) -> None:
        """Initialize the US API client."""
        super().__init__(username, password, session, region_config)
        self._headers = {
            "accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8,"
                "application/signed-exchange;v=b3;q=0.7"
            ),
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "max-age=0",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://mysuperioraccountlogin.com",
            "referer": _LOGIN_PAGE_URL,
            "sec-ch-ua": (
                '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"'
            ),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "same-origin",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        }

    async def async_get_tanks_data(self) -> list[dict[str, Any]]:
        """Get tank data from Superior Plus Propane US portal."""
        try:
            await self._ensure_authenticated()
            return await self._get_tanks_from_page()
        except SuperiorPlusPropaneApiClientAuthenticationError:
            LOGGER.debug("Authentication failed, attempting to re-authenticate")
            self._authenticated = False
            await self._ensure_authenticated()
            return await self._get_tanks_from_page()
        except SuperiorPlusPropaneApiClientError:
            raise
        except Exception as exc:
            LOGGER.exception("Error getting tank data: %s", exc)
            msg = f"Failed to get tank data: {exc}"
            raise SuperiorPlusPropaneApiClientError(msg) from exc

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid authenticated session."""
        if self._authenticated:
            try:
                async with asyncio.timeout(10):
                    response = await self._session.get(_HOME_URL, headers=self._headers)
                    if response.status == HTTP_OK and "Login" not in str(response.url):
                        LOGGER.debug("Session still valid")
                        return
                    LOGGER.debug("Session invalid, need to re-authenticate")
                    self._authenticated = False
            except (TimeoutError, Exception) as exc:
                LOGGER.debug("Session validation failed: %s", exc)
                self._authenticated = False
                self._session.cookie_jar.clear()

        if not self._authenticated and not self._auth_in_progress:
            await self._authenticate()

    async def _authenticate(self) -> None:
        """Perform full authentication sequence."""
        if self._auth_in_progress:
            return

        self._auth_in_progress = True
        try:
            LOGGER.debug("Starting US authentication sequence")
            self._session.cookie_jar.clear()

            csrf_token = await self._get_csrf_token()
            await self._login(csrf_token)

            self._authenticated = True
            LOGGER.debug("US authentication completed successfully")
        except Exception:
            self._authenticated = False
            raise
        finally:
            self._auth_in_progress = False

    async def _get_csrf_token(self) -> str:
        """Get CSRF token from login page hidden input."""
        try:
            async with asyncio.timeout(30):
                response = await self._session.get(
                    _LOGIN_PAGE_URL, headers=self._headers
                )
                if response.status != HTTP_OK:
                    msg = f"Failed to get login page: {response.status}"
                    raise SuperiorPlusPropaneApiClientCommunicationError(msg)

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                csrf_element = soup.find(
                    "input", {"name": "__RequestVerificationToken"}
                )
                if not csrf_element or not isinstance(csrf_element, Tag):
                    msg = "CSRF token not found"
                    raise SuperiorPlusPropaneApiClientError(msg)

                csrf_value = csrf_element.get("value")
                if not csrf_value:
                    msg = "CSRF token value not found"
                    raise SuperiorPlusPropaneApiClientError(msg)

                if isinstance(csrf_value, list):
                    csrf_value = csrf_value[0] if csrf_value else None
                    if not csrf_value:
                        msg = "CSRF token value not found"
                        raise SuperiorPlusPropaneApiClientError(msg)

                return str(csrf_value)

        except TimeoutError as exc:
            msg = f"Timeout getting CSRF token: {exc}"
            raise SuperiorPlusPropaneApiClientCommunicationError(msg) from exc

    async def _login(self, csrf_token: str) -> None:
        """Login to Superior Plus Propane US portal."""
        payload = {
            "__RequestVerificationToken": csrf_token,
            "EmailAddress": self._username,
            "Password": self._password,
            "RememberMe": "true",
        }

        try:
            async with asyncio.timeout(30):
                response = await self._session.post(
                    _LOGIN_URL, headers=self._headers, data=payload
                )
                if "Login" in str(response.url) or response.status != HTTP_OK:
                    msg = "Login failed - invalid credentials"
                    raise SuperiorPlusPropaneApiClientAuthenticationError(msg)

            LOGGER.debug("Login successful, navigating to required pages...")

            async with asyncio.timeout(60):
                await self._session.get(_HOME_URL, headers=self._headers)
                await self._session.get(_CUSTOMERS_URL, headers=self._headers)

        except TimeoutError as exc:
            msg = f"Timeout during login: {exc}"
            raise SuperiorPlusPropaneApiClientCommunicationError(msg) from exc

    async def _get_tanks_from_page(self) -> list[dict[str, Any]]:
        """Get tank data from the tank page."""
        try:
            async with asyncio.timeout(10):
                response = await self._session.get(_TANK_URL, headers=self._headers)

                if "Login" in str(response.url):
                    LOGGER.debug("Redirected to login page, session expired")
                    self._authenticated = False
                    raise SuperiorPlusPropaneApiClientAuthenticationError(
                        SESSION_EXPIRED_MSG
                    )

                if response.status != HTTP_OK:
                    msg = f"Failed to get tank page: {response.status}"
                    raise SuperiorPlusPropaneApiClientCommunicationError(msg)

                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")

                login_form = soup.find("form", {"action": "/Account/Login"})
                if login_form:
                    LOGGER.debug("Login form found on tank page")
                    self._authenticated = False
                    raise SuperiorPlusPropaneApiClientAuthenticationError(
                        SESSION_EXPIRED_MSG
                    )

                tank_rows = soup.select("div.tank-row")
                tanks_data = []

                for idx, row in enumerate(tank_rows):
                    tank_data = self._parse_tank_row(row, idx + 1)
                    if tank_data:
                        tanks_data.append(tank_data)

                if not tanks_data:
                    msg = "No tanks found"
                    raise SuperiorPlusPropaneApiClientError(msg)

                return tanks_data

        except TimeoutError as exc:
            msg = f"Timeout getting tank data: {exc}"
            raise SuperiorPlusPropaneApiClientCommunicationError(msg) from exc

    def _parse_tank_row(self, row: Tag, tank_number: int) -> dict[str, Any] | None:
        """Parse a single tank row into normalized common format."""
        try:
            address_info = self._extract_address(row)
            if not address_info:
                return None
            address, tank_id = address_info

            tank_size, tank_type = self._extract_tank_info(row)
            level = self._extract_level(row)
            current_gallons = self._extract_gallons(row)
            reading_date = self._normalize_date(
                self._extract_date(row, "Reading Date:")
            )
            last_delivery = self._normalize_date(
                self._extract_date(row, "Last Delivery:")
            )
            price_per_gallon = self._extract_price(row)

        except (AttributeError, ValueError, TypeError) as exc:
            LOGGER.warning("Error parsing tank row %d: %s", tank_number, exc)
            return None
        else:
            return {
                # Common normalized fields
                "tank_id": tank_id,
                "tank_number": tank_number,
                "address": address,
                "tank_name": address,
                "tank_size": tank_size,
                "tank_type": tank_type,
                "serial_number": "unknown",
                "customer_number": "unknown",
                "level": level,
                "current_volume": current_gallons,
                "reading_date": reading_date,
                "last_delivery": last_delivery,
                "price_per_unit": price_per_gallon,
                "is_on_delivery_plan": True,
            }

    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """Normalize US date format M/D/YYYY to ISO 8601 YYYY-MM-DD."""
        if date_str == "unknown":
            return "unknown"
        try:
            parsed = datetime.strptime(date_str, "%m/%d/%Y")  # noqa: DTZ007
            return parsed.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return date_str

    def _extract_address(self, row: Tag) -> tuple[str, str] | None:
        """Extract and clean address from row."""
        address_element = row.select_one(".col-md-2")
        if not address_element:
            return None

        address_text = address_element.get_text(separator=" ", strip=True)
        address = address_text.split("\n")[0] if "\n" in address_text else address_text
        address = re.sub(r"\s+", " ", address).strip()
        tank_id = slugify(address.lower().replace(" ", "_"))
        return address, tank_id

    def _extract_tank_info(self, row: Tag) -> tuple[str, str]:
        """Extract tank size and type."""
        tank_info_element = row.select_one(".col-md-3")
        tank_size = "unknown"
        tank_type = "unknown"

        if tank_info_element:
            tank_info_text = tank_info_element.get_text()
            size_match = re.search(r"(\d+)\s*gal\.", tank_info_text)
            if size_match:
                tank_size = size_match.group(1)
            if "Propane" in tank_info_text:
                tank_type = "Propane"

        return tank_size, tank_type

    def _extract_level(self, row: Tag) -> str:
        """Extract level percentage from progress bar."""
        progress_bar = row.select_one("div.progress-bar")
        if progress_bar and progress_bar.get("aria-valuenow"):
            value = progress_bar.get("aria-valuenow")
            if isinstance(value, list):
                return value[0] if value else "unknown"
            return str(value) if value else "unknown"
        return "unknown"

    def _extract_gallons(self, row: Tag) -> str:
        """Extract current gallons."""
        gallons_text = row.find(string=re.compile(r"Approximately \d+ gallons in tank"))
        if gallons_text:
            gallons_match = re.search(
                r"Approximately (\d+) gallons in tank", str(gallons_text)
            )
            if gallons_match:
                return gallons_match.group(1)
        return "unknown"

    def _extract_date(self, row: Tag, pattern: str) -> str:
        """Extract date by pattern."""
        date_text = row.find(string=re.compile(pattern))
        if date_text and date_text.parent:
            full_text = date_text.parent.get_text()
            date_match = re.search(
                rf"{pattern}\s*(\d{{1,2}}/\d{{1,2}}/\d{{4}})", full_text
            )
            if date_match:
                return date_match.group(1)
        return "unknown"

    def _extract_price(self, row: Tag) -> str:
        """Extract price per gallon."""
        price_text = row.find(string=re.compile(r"\$\d+\.\d+"))
        if price_text:
            price_match = re.search(r"\$(\d+\.\d+)", str(price_text))
            if price_match:
                return price_match.group(1)
        return "unknown"
