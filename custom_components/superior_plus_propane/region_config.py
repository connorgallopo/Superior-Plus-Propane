"""Region-specific configuration for Superior Plus Propane integration.

This module provides a type-safe, extensible configuration system for handling
regional differences in the Superior Plus Propane authentication and scraping logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Literal


class Region(StrEnum):
    """Supported regions for Superior Plus Propane."""

    US = "US"
    CA = "CA"


class AuthMethod(StrEnum):
    """Authentication method types."""

    POST = "POST"
    AJAX = "AJAX"


@dataclass(frozen=True, slots=True)
class AuthFieldNames:
    """Field names used in authentication forms.

    Attributes:
        email: Name of the email/username field
        password: Name of the password field
        remember_me: Name of the remember me field (None if not used)
        language: Name of the language field (None if not used)
        csrf_token: Name of the CSRF token field
    """

    email: str
    password: str
    remember_me: str | None = None
    language: str | None = None
    csrf_token: str = "__RequestVerificationToken"


@dataclass(frozen=True, slots=True)
class UrlConfig:
    """URL configuration for a region.

    Attributes:
        base_domain: Base domain for the region
        login_page: Relative path to login page
        login_endpoint: Relative path to login endpoint (may differ for AJAX)
        home: Relative path to home page
        customers: Relative path to customers page
        tank: Relative path to tank data page
    """

    base_domain: str
    login_page: str = "/Account/Login?ReturnUrl=%2F"
    login_endpoint: str = "/Account/Login?ReturnUrl=%2F"
    home: str = "/"
    customers: str = "/Customers"
    tank: str = "/Tank"

    @property
    def login_page_url(self) -> str:
        """Full URL to login page."""
        return f"https://{self.base_domain}{self.login_page}"

    @property
    def login_url(self) -> str:
        """Full URL to login endpoint."""
        return f"https://{self.base_domain}{self.login_endpoint}"

    @property
    def home_url(self) -> str:
        """Full URL to home page."""
        return f"https://{self.base_domain}{self.home}"

    @property
    def customers_url(self) -> str:
        """Full URL to customers page."""
        return f"https://{self.base_domain}{self.customers}"

    @property
    def tank_url(self) -> str:
        """Full URL to tank page."""
        return f"https://{self.base_domain}{self.tank}"


@dataclass(frozen=True, slots=True)
class SelectorConfig:
    """CSS selectors for scraping tank data.

    Attributes:
        tank_row: Selector for tank row containers
        address: Selector for address within tank row
        tank_info: Selector for tank size/type info
        progress_bar: Selector for level progress bar
        csrf_input: Selector for CSRF token input field
        login_form: Selector for login form (to detect session expiry)
    """

    tank_row: str = "div.tank-row"
    address: str = ".col-md-2"
    tank_info: str = ".col-md-3"
    progress_bar: str = "div.progress-bar"
    csrf_input: str = 'input[name="__RequestVerificationToken"]'
    login_form: str = 'form[action="/Account/Login"]'


@dataclass(frozen=True, slots=True)
class PatternConfig:
    """Regex patterns for extracting data from scraped pages.

    Attributes:
        tank_size: Pattern to extract tank size in gallons
        gallons_in_tank: Pattern to extract current gallons
        reading_date: Pattern to extract reading date
        last_delivery: Pattern to extract last delivery date
        price_per_gallon: Pattern to extract price
    """

    tank_size: str = r"(\d+)\s*gal\."
    gallons_in_tank: str = r"Approximately (\d+) gallons in tank"
    reading_date: str = r"Reading Date:\s*(\d{1,2}/\d{1,2}/\d{4})"
    last_delivery: str = r"Last Delivery:\s*(\d{1,2}/\d{1,2}/\d{4})"
    price_per_gallon: str = r"\$(\d+\.\d+)"


@dataclass(frozen=True, slots=True)
class RegionConfig:
    """Complete configuration for a specific region.

    Attributes:
        region: Region identifier
        auth_method: Authentication method to use
        auth_fields: Field names for authentication
        urls: URL configuration
        selectors: CSS selectors for scraping
        patterns: Regex patterns for data extraction
        timeout_login: Timeout for login requests (seconds)
        timeout_navigation: Timeout for page navigation (seconds)
        timeout_data: Timeout for data retrieval (seconds)
    """

    region: Region
    auth_method: AuthMethod
    auth_fields: AuthFieldNames
    urls: UrlConfig
    selectors: SelectorConfig = field(default_factory=SelectorConfig)
    patterns: PatternConfig = field(default_factory=PatternConfig)
    timeout_login: int = 30
    timeout_navigation: int = 60
    timeout_data: int = 10

    def build_login_payload(
        self,
        username: str,
        password: str,
        csrf_token: str,
        *,
        language: str | None = None,
    ) -> dict[str, str]:
        """Build login payload for this region.

        Args:
            username: User's email address
            password: User's password
            csrf_token: CSRF token from login page
            language: Language selection (for regions that require it)

        Returns:
            Dictionary of form data ready to POST
        """
        payload: dict[str, str] = {
            self.auth_fields.csrf_token: csrf_token,
            self.auth_fields.email: username,
            self.auth_fields.password: password,
        }

        if self.auth_fields.remember_me is not None:
            payload[self.auth_fields.remember_me] = "true"

        if self.auth_fields.language is not None:
            if language is None:
                msg = f"Language required for {self.region} region but not provided"
                raise ValueError(msg)
            payload[self.auth_fields.language] = language

        return payload


# US Configuration
US_CONFIG: Final[RegionConfig] = RegionConfig(
    region=Region.US,
    auth_method=AuthMethod.POST,
    auth_fields=AuthFieldNames(
        email="EmailAddress",
        password="Password",
        remember_me="RememberMe",
        language=None,
    ),
    urls=UrlConfig(
        base_domain="mysuperioraccountlogin.com",
    ),
)


# Canadian Configuration (placeholder - requires validation)
# TODO: Verify these settings with actual Canadian Superior Plus portal
CA_CONFIG: Final[RegionConfig] = RegionConfig(
    region=Region.CA,
    auth_method=AuthMethod.AJAX,  # TODO: Verify if AJAX or POST
    auth_fields=AuthFieldNames(
        email="LoginEmail",  # TODO: Verify actual field name
        password="Password",  # TODO: Verify actual field name
        remember_me=None,  # TODO: Verify if this field exists
        language="Language",  # TODO: Verify actual field name and if required
    ),
    urls=UrlConfig(
        base_domain="mysuperioraccountlogin.ca",  # TODO: Verify actual Canadian domain
        login_page="/Account/Login?ReturnUrl=%2F",  # TODO: Verify path
        login_endpoint="/Account/Login?ReturnUrl=%2F",  # TODO: Verify endpoint
    ),
    # TODO: Verify if selectors differ from US
    # TODO: Verify if patterns differ from US
    # TODO: Verify appropriate timeouts for Canadian infrastructure
)


class RegionRegistry:
    """Registry for accessing region-specific configurations.

    This class provides a centralized way to retrieve and validate
    region configurations at runtime.
    """

    _configs: Final[dict[Region, RegionConfig]] = {
        Region.US: US_CONFIG,
        Region.CA: CA_CONFIG,
    }

    @classmethod
    def get(cls, region: Region | str) -> RegionConfig:
        """Get configuration for a specific region.

        Args:
            region: Region enum or string ("US", "CA")

        Returns:
            RegionConfig for the specified region

        Raises:
            ValueError: If region is not supported
        """
        if isinstance(region, str):
            try:
                region = Region(region.upper())
            except ValueError as exc:
                supported = ", ".join(r.value for r in Region)
                msg = f"Unsupported region: {region}. Supported: {supported}"
                raise ValueError(msg) from exc

        config = cls._configs.get(region)
        if config is None:
            supported = ", ".join(r.value for r in Region)
            msg = f"No configuration found for region: {region}. Supported: {supported}"
            raise ValueError(msg)

        return config

    @classmethod
    def validate_config(cls, config: RegionConfig) -> list[str]:
        """Validate a region configuration and return warnings.

        Args:
            config: Configuration to validate

        Returns:
            List of warning messages (empty if no warnings)
        """
        warnings: list[str] = []

        # Check for TODO markers in critical fields
        if "TODO" in config.urls.base_domain:
            warnings.append(f"{config.region}: Base domain contains TODO")

        # Validate timeout values
        if config.timeout_login < 5:
            warnings.append(
                f"{config.region}: Login timeout ({config.timeout_login}s) "
                "may be too short"
            )
        if config.timeout_navigation < 10:
            warnings.append(
                f"{config.region}: Navigation timeout ({config.timeout_navigation}s) "
                "may be too short"
            )

        # Check for language field consistency
        if config.auth_fields.language is not None:
            if config.auth_method == AuthMethod.POST:
                warnings.append(
                    f"{config.region}: Language field with POST auth may need verification"
                )

        return warnings

    @classmethod
    def get_all_regions(cls) -> list[Region]:
        """Get list of all supported regions.

        Returns:
            List of Region enum values
        """
        return list(cls._configs.keys())

    @classmethod
    def validate_all(cls) -> dict[Region, list[str]]:
        """Validate all registered configurations.

        Returns:
            Dictionary mapping regions to their validation warnings
        """
        return {
            region: cls.validate_config(config)
            for region, config in cls._configs.items()
        }


# Convenience function for backward compatibility
def get_region_config(region: Region | str = Region.US) -> RegionConfig:
    """Get region configuration (convenience wrapper).

    Args:
        region: Region to get config for (defaults to US)

    Returns:
        RegionConfig for the specified region
    """
    return RegionRegistry.get(region)
