"""Custom integration to integrate Superior Plus Propane with Home Assistant."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import (
    SuperiorPlusPropaneApiClientError,
    create_api_client,
)
from .const import CONF_INCLUDE_UNMONITORED, CONF_REGION, LOGGER
from .coordinator import SuperiorPlusPropaneDataUpdateCoordinator
from .data import SuperiorPlusPropaneData
from .region import get_region_config

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import SuperiorPlusPropaneConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_migrate_entry(
    hass: HomeAssistant,
    config_entry: SuperiorPlusPropaneConfigEntry,
) -> bool:
    """Migrate config entry to a new version."""
    if config_entry.version == 1:
        LOGGER.info("Migrating config entry from v1 to v2")
        new_data = {**config_entry.data}
        if CONF_REGION not in new_data:
            new_data[CONF_REGION] = "us"
        if CONF_INCLUDE_UNMONITORED not in new_data:
            new_data[CONF_INCLUDE_UNMONITORED] = False

        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
        LOGGER.info("Migration to v2 successful")

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SuperiorPlusPropaneConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    region = entry.data.get(CONF_REGION, "us")
    region_config = get_region_config(region)

    client = create_api_client(
        region=region,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=async_create_clientsession(hass),
        region_config=region_config,
    )

    coordinator = SuperiorPlusPropaneDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        region_config=region_config,
    )

    entry.runtime_data = SuperiorPlusPropaneData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
        region_config=region_config,
    )

    # Load stored consumption data before first refresh
    await coordinator.async_load_consumption_data()

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        raise
    except SuperiorPlusPropaneApiClientError as exc:
        msg = f"Failed to set up {entry.domain}: {exc}"
        raise ConfigEntryNotReady(msg) from exc

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: SuperiorPlusPropaneConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    if entry.runtime_data and entry.runtime_data.client:
        await entry.runtime_data.client.async_close()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: SuperiorPlusPropaneConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
