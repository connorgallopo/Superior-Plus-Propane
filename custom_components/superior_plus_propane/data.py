"""Custom types for Superior Plus Propane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import SuperiorPropaneApiBase
    from .coordinator import SuperiorPlusPropaneDataUpdateCoordinator
    from .region import RegionConfig


type SuperiorPlusPropaneConfigEntry = ConfigEntry[SuperiorPlusPropaneData]


@dataclass
class SuperiorPlusPropaneData:
    """Data for the Superior Plus Propane integration."""

    client: SuperiorPropaneApiBase
    coordinator: SuperiorPlusPropaneDataUpdateCoordinator
    integration: Integration
    region_config: RegionConfig
