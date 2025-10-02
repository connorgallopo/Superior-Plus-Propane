"""
Custom integration to integrate Superior Plus Propane with Home Assistant.

For more details about this integration, please refer to
https://github.com/connorgallopo/Superior-Plus-Propane
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform

from .const import CONF_REGION
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import SuperiorPlusPropaneApiClient
from .coordinator import SuperiorPlusPropaneDataUpdateCoordinator
from .data import SuperiorPlusPropaneData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import SuperiorPlusPropaneConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperiorPlusPropaneConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = SuperiorPlusPropaneDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
    )

    entry.runtime_data = SuperiorPlusPropaneData(
        client=SuperiorPlusPropaneApiClient(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=async_create_clientsession(hass),
            region=entry.data.get(CONF_REGION, "US"),
        ),
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # Load stored consumption data before first refresh
    await coordinator.async_load_consumption_data()

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: SuperiorPlusPropaneConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    # Close the dedicated session to clean up resources
    if entry.runtime_data and entry.runtime_data.client:
        session = getattr(entry.runtime_data.client, "_session", None)
        if session and hasattr(session, "close"):
            await session.close()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: SuperiorPlusPropaneConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
