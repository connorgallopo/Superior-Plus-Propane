"""Sensor platform for Superior Plus Propane."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTime,
)

from .const import CONF_INCLUDE_UNMONITORED, DOMAIN, LOGGER
from .entity import SuperiorPlusPropaneEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import SuperiorPlusPropaneDataUpdateCoordinator
    from .data import SuperiorPlusPropaneConfigEntry
    from .region import RegionConfig


def _build_unique_id(tank_data: dict[str, Any], suffix: str) -> str:
    """Build a unique ID for a sensor, including customer_number for CA."""
    customer_number = tank_data.get("customer_number", "unknown")
    tank_id = tank_data["tank_id"]
    if customer_number != "unknown":
        return f"{DOMAIN}_{customer_number}_{tank_id}_{suffix}"
    return f"{DOMAIN}_{tank_id}_{suffix}"


def _build_sensor_name(
    region_config: RegionConfig, tank_data: dict[str, Any], label: str
) -> str:
    """Build a sensor name, using full address for US or short label for CA."""
    if region_config.has_entity_name:
        return label
    return f"{tank_data['address']} {label}"


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SuperiorPlusPropaneConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator
    region_config = coordinator.region_config

    if not coordinator.data:
        LOGGER.warning("No tank data available during sensor setup")
        return

    tanks = coordinator.data.get("tanks", [])
    include_unmonitored = entry.data.get(CONF_INCLUDE_UNMONITORED, False)

    entities: list[SensorEntity] = []

    for tank_data in tanks:
        if not isinstance(tank_data, dict):
            continue

        tank_id = tank_data.get("tank_id")
        address = tank_data.get("address")

        if not tank_id or not address:
            continue

        if not include_unmonitored and not tank_data.get("is_on_delivery_plan", True):
            LOGGER.debug("Skipping unmonitored tank: %s", tank_id)
            continue

        entities.extend(
            [
                SuperiorPlusPropaneLevelSensor(coordinator, tank_data, region_config),
                SuperiorPlusPropaneVolumeSensor(coordinator, tank_data, region_config),
                SuperiorPlusPropaneCapacitySensor(
                    coordinator, tank_data, region_config
                ),
                SuperiorPlusPropaneReadingDateSensor(
                    coordinator, tank_data, region_config
                ),
                SuperiorPlusPropaneLastDeliverySensor(
                    coordinator, tank_data, region_config
                ),
                SuperiorPlusPropaneDaysSinceDeliverySensor(
                    coordinator, tank_data, region_config
                ),
                SuperiorPlusPropaneConsumptionTotalSensor(
                    coordinator, tank_data, region_config
                ),
                SuperiorPlusPropaneConsumptionRateSensor(
                    coordinator, tank_data, region_config
                ),
                SuperiorPlusPropaneDataQualitySensor(
                    coordinator, tank_data, region_config
                ),
            ]
        )

        if region_config.has_per_tank_price:
            entities.append(
                SuperiorPlusPropanePriceSensor(coordinator, tank_data, region_config)
            )

    # Add average price sensor (reads from orders data, one per integration)
    if tanks:
        entities.append(
            SuperiorPlusPropaneAveragePriceSensor(coordinator, tanks[0], region_config)
        )

    async_add_entities(entities)


class SuperiorPlusPropaneLevelSensor(SuperiorPlusPropaneEntity, SensorEntity):
    """Tank level percentage sensor."""

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
        region_config: RegionConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = _build_unique_id(tank_data, "level")
        self._attr_name = _build_sensor_name(region_config, tank_data, "Level")
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:gauge"

    @property
    def native_value(self) -> float | None:
        """Return the current tank level percentage."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        level_str = tank_data.get("level", "unknown")
        if level_str == "unknown":
            return None

        try:
            return float(level_str)
        except (ValueError, TypeError):
            return None


class SuperiorPlusPropaneVolumeSensor(SuperiorPlusPropaneEntity, SensorEntity):
    """Current volume sensor."""

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
        region_config: RegionConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = _build_unique_id(tank_data, "volume")
        self._attr_name = _build_sensor_name(region_config, tank_data, "Current Volume")
        self._attr_native_unit_of_measurement = region_config.volume_unit
        self._attr_device_class = SensorDeviceClass.VOLUME
        self._attr_state_class = None
        self._attr_icon = "mdi:propane-tank"

    @property
    def native_value(self) -> float | None:
        """Return the current volume in tank."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        volume_str = tank_data.get("current_volume", "unknown")
        if volume_str == "unknown":
            return None

        try:
            return float(volume_str)
        except (ValueError, TypeError):
            return None


class SuperiorPlusPropaneCapacitySensor(SuperiorPlusPropaneEntity, SensorEntity):
    """Tank capacity sensor."""

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
        region_config: RegionConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = _build_unique_id(tank_data, "capacity")
        self._attr_name = _build_sensor_name(region_config, tank_data, "Capacity")
        self._attr_native_unit_of_measurement = region_config.volume_unit
        self._attr_device_class = SensorDeviceClass.VOLUME
        self._attr_state_class = None
        self._attr_icon = "mdi:propane-tank-outline"

    @property
    def native_value(self) -> float | None:
        """Return the tank capacity."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        capacity_str = tank_data.get("tank_size", "unknown")
        if capacity_str == "unknown":
            return None

        try:
            return float(capacity_str)
        except (ValueError, TypeError):
            return None


class SuperiorPlusPropaneReadingDateSensor(SuperiorPlusPropaneEntity, SensorEntity):
    """Reading date sensor."""

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
        region_config: RegionConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = _build_unique_id(tank_data, "reading_date")
        self._attr_name = _build_sensor_name(region_config, tank_data, "Reading Date")
        self._attr_device_class = None
        self._attr_icon = "mdi:calendar-clock"

    @property
    def native_value(self) -> str | None:
        """Return the reading date."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        reading_date = tank_data.get("reading_date", "unknown")
        return None if reading_date == "unknown" else reading_date


class SuperiorPlusPropaneLastDeliverySensor(SuperiorPlusPropaneEntity, SensorEntity):
    """Last delivery date sensor."""

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
        region_config: RegionConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = _build_unique_id(tank_data, "last_delivery")
        self._attr_name = _build_sensor_name(region_config, tank_data, "Last Delivery")
        self._attr_device_class = None
        self._attr_icon = "mdi:truck-delivery"

    @property
    def native_value(self) -> str | None:
        """Return the last delivery date."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        delivery_date = tank_data.get("last_delivery", "unknown")
        return None if delivery_date == "unknown" else delivery_date


class SuperiorPlusPropanePriceSensor(SuperiorPlusPropaneEntity, SensorEntity):
    """Price per unit sensor."""

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
        region_config: RegionConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = _build_unique_id(tank_data, "price")
        self._attr_name = _build_sensor_name(region_config, tank_data, "Price per Unit")
        self._attr_native_unit_of_measurement = region_config.price_unit
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = None
        self._attr_icon = "mdi:currency-usd"

    @property
    def native_value(self) -> float | None:
        """Return the price per unit."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        price_str = tank_data.get("price_per_unit", "unknown")
        if price_str == "unknown":
            return None

        try:
            return round(float(price_str), 4)
        except (ValueError, TypeError):
            return None


class SuperiorPlusPropaneDaysSinceDeliverySensor(
    SuperiorPlusPropaneEntity, SensorEntity
):
    """Days since last delivery sensor."""

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
        region_config: RegionConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = _build_unique_id(tank_data, "days_since_delivery")
        self._attr_name = _build_sensor_name(
            region_config, tank_data, "Days Since Delivery"
        )
        self._attr_native_unit_of_measurement = UnitOfTime.DAYS
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:calendar-today"

    @property
    def native_value(self) -> int | None:
        """Return days since last delivery."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        days_since = tank_data.get("days_since_delivery", "unknown")
        if days_since == "unknown":
            return None

        try:
            return int(days_since)
        except (ValueError, TypeError):
            return None


class SuperiorPlusPropaneConsumptionTotalSensor(
    SuperiorPlusPropaneEntity, SensorEntity
):
    """Total consumption sensor for energy dashboard."""

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
        region_config: RegionConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = _build_unique_id(tank_data, "consumption_total")
        self._attr_name = _build_sensor_name(
            region_config, tank_data, "Total Consumption"
        )
        self._attr_native_unit_of_measurement = region_config.consumption_display_unit
        self._attr_device_class = SensorDeviceClass.GAS
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:fire"
        self._display_factor = region_config.consumption_display_factor

    @property
    def native_value(self) -> float | None:
        """Return total consumption in display units."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        return tank_data.get("consumption_total", 0.0) * self._display_factor


class SuperiorPlusPropaneConsumptionRateSensor(SuperiorPlusPropaneEntity, SensorEntity):
    """Consumption rate sensor showing current hourly usage."""

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
        region_config: RegionConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = _build_unique_id(tank_data, "consumption_rate")
        self._attr_name = _build_sensor_name(
            region_config, tank_data, "Consumption Rate"
        )
        self._attr_native_unit_of_measurement = region_config.rate_display_unit
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:speedometer"
        self._display_factor = region_config.rate_display_factor

    @property
    def native_value(self) -> float | None:
        """Return consumption rate in display units per hour."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        return tank_data.get("consumption_rate", 0.0) * self._display_factor


class SuperiorPlusPropaneDataQualitySensor(SuperiorPlusPropaneEntity, SensorEntity):
    """Data quality indicator sensor."""

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
        region_config: RegionConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = _build_unique_id(tank_data, "data_quality")
        self._attr_name = _build_sensor_name(region_config, tank_data, "Data Quality")
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_icon = "mdi:shield-check"

    @property
    def native_value(self) -> str | None:
        """Return the data quality status."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return None

        return tank_data.get("data_quality", "Unknown")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return {}

        attrs: dict[str, Any] = {}
        if tank_data.get("consumption_anomaly"):
            attrs["consumption_anomaly"] = True
            attrs["anomaly_reason"] = "Consumption exceeded expected threshold"
        if tank_data.get("refill_detected"):
            attrs["refill_detected"] = True
            attrs["refill_reason"] = "Tank level increased since last reading"

        return attrs

    @property
    def icon(self) -> str:
        """Return dynamic icon based on quality."""
        tank_data = self._get_tank_data()
        if not tank_data:
            return "mdi:shield-off"

        quality = tank_data.get("data_quality", "Unknown")

        if quality == "Good":
            return "mdi:shield-check"
        if quality == "Inconsistent Values":
            return "mdi:shield-alert"
        if quality in ("Invalid Level", "Invalid Tank Size", "Calculation Error"):
            return "mdi:shield-off"
        return "mdi:shield-outline"


class SuperiorPlusPropaneAveragePriceSensor(SuperiorPlusPropaneEntity, SensorEntity):
    """Average price sensor from orders data."""

    def __init__(
        self,
        coordinator: SuperiorPlusPropaneDataUpdateCoordinator,
        tank_data: dict[str, Any],
        region_config: RegionConfig,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, tank_data)
        self._attr_unique_id = _build_unique_id(tank_data, "average_price")
        self._attr_name = _build_sensor_name(region_config, tank_data, "Average Price")
        self._attr_native_unit_of_measurement = region_config.price_unit
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = None
        self._attr_icon = "mdi:cash-multiple"

    @property
    def native_value(self) -> float | None:
        """Return the average price from orders data."""
        if not self.coordinator.data:
            return None

        orders = self.coordinator.data.get("orders", {})
        if not orders:
            return None

        avg_price = orders.get("average_price")
        if avg_price is None:
            return None

        try:
            return round(float(avg_price), 4)
        except (ValueError, TypeError):
            return None
