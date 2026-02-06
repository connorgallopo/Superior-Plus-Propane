"""SuperiorPlusPropaneEntity class."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import SuperiorPlusPropaneDataUpdateCoordinator


class SuperiorPlusPropaneEntity(
    CoordinatorEntity[SuperiorPlusPropaneDataUpdateCoordinator],
):
    """SuperiorPlusPropaneEntity class."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._tank_id = tank_data["tank_id"]
        self._tank_address = tank_data["address"]

        region_config = coordinator.region_config
        self._attr_has_entity_name = region_config.has_entity_name

        # Build device info
        tank_size = tank_data.get("tank_size", "unknown")
        volume_unit = region_config.volume_unit
        model = (
            f"{tank_size} {volume_unit} Tank"
            if tank_size != "unknown"
            else "Propane Tank"
        )

        serial_number = tank_data.get("serial_number", "unknown")

        device_info_kwargs: dict[str, Any] = {
            "identifiers": {(DOMAIN, f"tank_{self._tank_id}")},
            "name": (
                f"Propane Tank - {self._tank_address}"
                if not region_config.has_entity_name
                else tank_data.get("tank_name", self._tank_address)
            ),
            "manufacturer": region_config.manufacturer,
            "model": model,
        }
        if serial_number != "unknown":
            device_info_kwargs["serial_number"] = serial_number

        self._attr_device_info = DeviceInfo(**device_info_kwargs)

    def _get_tank_data(self) -> dict[str, Any] | None:
        """Get current tank data from coordinator."""
        if not self.coordinator.data:
            return None

        tanks = self.coordinator.data.get("tanks", [])
        for tank in tanks:
            if isinstance(tank, dict) and tank.get("tank_id") == self._tank_id:
                return tank
        return None
