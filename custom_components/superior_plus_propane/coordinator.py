"""DataUpdateCoordinator for Superior Plus Propane."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    SuperiorPlusPropaneApiClientAuthenticationError,
    SuperiorPlusPropaneApiClientCommunicationError,
    SuperiorPlusPropaneApiClientError,
)
from .const import (
    DATA_VALIDATION_TOLERANCE,
    LOGGER,
    MAX_CONSUMPTION_PERCENTAGE,
    MAX_STALE_DATA_HOURS,
    MIN_CONSUMPTION_PERCENTAGE,
    PERCENT_MULTIPLIER,
    SECONDS_PER_HOUR,
)

STORAGE_VERSION = 1
STORAGE_KEY = "superior_plus_propane_consumption"

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import SuperiorPlusPropaneConfigEntry
    from .region import RegionConfig


class SuperiorPlusPropaneDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: SuperiorPlusPropaneConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SuperiorPlusPropaneConfigEntry,
        region_config: RegionConfig,
    ) -> None:
        """Initialize the coordinator."""
        self.region_config = region_config
        self._normal_interval = timedelta(
            seconds=config_entry.data.get(
                "update_interval", region_config.default_update_interval
            )
        )
        self._retry_interval = timedelta(seconds=region_config.retry_interval)
        super().__init__(
            hass,
            LOGGER,
            name="Superior Plus Propane",
            update_interval=self._normal_interval,
        )
        self.config_entry = config_entry
        self._previous_readings: dict[str, float] = {}
        self._consumption_totals: dict[str, float] = {}
        self._store = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}_{config_entry.entry_id}"
        )
        self._data_quality_flags: dict[str, str] = {}
        self._use_dynamic_thresholds = config_entry.data.get(
            "adaptive_thresholds", True
        )
        self._min_threshold_override = config_entry.data.get(
            "min_consumption_threshold"
        )
        self._max_threshold_override = config_entry.data.get(
            "max_consumption_threshold"
        )
        self.last_successful_update_time: datetime | None = None

    async def async_load_consumption_data(self) -> None:
        """Load consumption data from storage."""
        stored_data = await self._store.async_load()
        if stored_data:
            self._consumption_totals = stored_data.get("consumption_totals", {})
            self._previous_readings = stored_data.get("previous_readings", {})
            LOGGER.debug("Loaded consumption data: %s", self._consumption_totals)

    async def async_save_consumption_data(self) -> None:
        """Save consumption data to storage."""
        data = {
            "version": STORAGE_VERSION,
            "consumption_totals": self._consumption_totals,
            "previous_readings": self._previous_readings,
            "last_updated": datetime.now(UTC).isoformat(),
        }
        await self._store.async_save(data)
        LOGGER.debug("Saved consumption data: %s", self._consumption_totals)

    def _is_data_fresh(self) -> bool:
        """Check if existing data is fresh enough to serve as stale fallback."""
        if not self.last_successful_update_time:
            return False
        age = datetime.now(UTC) - self.last_successful_update_time
        return age < timedelta(hours=MAX_STALE_DATA_HOURS)

    def _calculate_dynamic_thresholds(
        self, tank_size: float, update_interval_hours: float
    ) -> tuple[float, float]:
        """Calculate dynamic consumption thresholds."""
        rc = self.region_config

        if (
            self._min_threshold_override is not None
            and self._max_threshold_override is not None
        ):
            return self._min_threshold_override, self._max_threshold_override

        if (
            self._min_threshold_override is not None
            or self._max_threshold_override is not None
        ):
            if self._use_dynamic_thresholds:
                min_dynamic = (
                    tank_size * MIN_CONSUMPTION_PERCENTAGE * update_interval_hours
                )
                max_dynamic = (
                    tank_size * MAX_CONSUMPTION_PERCENTAGE * update_interval_hours
                )
                min_dynamic = max(rc.absolute_min_consumption, min_dynamic)
                max_dynamic = min(rc.absolute_max_consumption, max_dynamic)
                min_threshold = (
                    self._min_threshold_override
                    if self._min_threshold_override is not None
                    else min_dynamic
                )
                max_threshold = (
                    self._max_threshold_override
                    if self._max_threshold_override is not None
                    else max_dynamic
                )
                return min_threshold, max_threshold
            return (
                (
                    self._min_threshold_override
                    if self._min_threshold_override is not None
                    else rc.default_min_threshold
                ),
                (
                    self._max_threshold_override
                    if self._max_threshold_override is not None
                    else rc.default_max_threshold
                ),
            )

        if not self._use_dynamic_thresholds:
            return rc.default_min_threshold, rc.default_max_threshold

        min_consumption = tank_size * MIN_CONSUMPTION_PERCENTAGE * update_interval_hours
        max_consumption = tank_size * MAX_CONSUMPTION_PERCENTAGE * update_interval_hours

        min_consumption = max(rc.absolute_min_consumption, min_consumption)
        max_consumption = min(rc.absolute_max_consumption, max_consumption)

        return min_consumption, max_consumption

    def _validate_tank_data(self, tank: dict[str, Any]) -> bool:  # noqa: PLR0911
        """Validate tank data consistency and set quality flags."""
        tank_id = tank.get("tank_id", "unknown")
        rc = self.region_config

        try:
            tank_size = float(tank.get("tank_size", 0))
            if not (rc.tank_size_min <= tank_size <= rc.tank_size_max):
                LOGGER.warning(
                    "Tank %s has unrealistic size: %s",
                    tank_id,
                    tank_size,
                )
                self._data_quality_flags[tank_id] = "Invalid Tank Size"
                return False
        except (ValueError, TypeError):
            self._data_quality_flags[tank_id] = "Invalid Tank Size"
            return False

        try:
            level = float(tank.get("level", -1))
            max_level_percent = 100
            if not (0 <= level <= max_level_percent):
                LOGGER.warning(
                    "Tank %s has invalid level: %s%%",
                    tank_id,
                    level,
                )
                self._data_quality_flags[tank_id] = "Invalid Level"
                return False
        except (ValueError, TypeError):
            self._data_quality_flags[tank_id] = "Invalid Level"
            return False

        try:
            current_volume = float(tank.get("current_volume", 0))
            expected_volume = (
                (level * tank_size) / PERCENT_MULTIPLIER if tank_size > 0 else 0
            )

            if tank_size > 0 and expected_volume > 0:
                variance = abs(current_volume - expected_volume) / expected_volume
                if variance > DATA_VALIDATION_TOLERANCE:
                    variance_pct = variance * PERCENT_MULTIPLIER
                    LOGGER.warning(
                        "Tank %s data inconsistency: Level %s%% suggests %.1f, "
                        "but reported value is %.1f (tank: %.0f, var: %.1f%%)",
                        tank_id,
                        level,
                        expected_volume,
                        current_volume,
                        tank_size,
                        variance_pct,
                    )
                    self._data_quality_flags[tank_id] = "Inconsistent Values"
                    return False
                self._data_quality_flags[tank_id] = "Good"
        except (ValueError, TypeError, ZeroDivisionError, ArithmeticError):
            self._data_quality_flags[tank_id] = "Calculation Error"
            return False

        if tank_id not in self._data_quality_flags:
            self._data_quality_flags[tank_id] = "Good"

        return True

    def _process_tank_consumption(  # noqa: PLR0912, PLR0915
        self, tank: dict[str, Any]
    ) -> None:
        """Process consumption tracking for a single tank."""
        tank_id = tank.get("tank_id")
        if not tank_id:
            LOGGER.warning("Tank data missing tank_id, skipping consumption processing")
            return

        tank["refill_detected"] = False
        tank["consumption_anomaly"] = False

        if not self._validate_tank_data(tank):
            LOGGER.debug("Tank %s data validation failed", tank_id)
            tank["consumption_total"] = self._consumption_totals.get(tank_id, 0.0)
            tank["consumption_rate"] = 0.0
            tank["data_quality"] = self._data_quality_flags.get(tank_id, "Unknown")
            return

        try:
            current_volume = float(tank.get("current_volume", "0"))
            tank_size = float(tank.get("tank_size", 500))
        except (ValueError, TypeError):
            tank["consumption_total"] = self._consumption_totals.get(tank_id, 0.0)
            tank["consumption_rate"] = 0.0
            tank["data_quality"] = "Unknown"
            return

        rc = self.region_config
        interval = self.update_interval or self._normal_interval
        update_interval_hours = max(0.001, interval.total_seconds() / SECONDS_PER_HOUR)
        min_threshold, max_threshold = self._calculate_dynamic_thresholds(
            tank_size, update_interval_hours
        )

        if tank_id in self._previous_readings:
            previous_volume = self._previous_readings[tank_id]
            consumption_volume = previous_volume - current_volume

            if consumption_volume < 0:
                LOGGER.info(
                    "Tank %s was refilled: %.2f -> %.2f",
                    tank_id,
                    previous_volume,
                    current_volume,
                )
                tank["refill_detected"] = True
            elif consumption_volume > 0:
                consumption_energy = consumption_volume * rc.volume_to_energy_factor

                if tank_id not in self._consumption_totals:
                    self._consumption_totals[tank_id] = 0.0

                if consumption_volume < min_threshold:
                    LOGGER.info(
                        "Tank %s low consumption: %.3f [below threshold: %.3f]",
                        tank_id,
                        consumption_volume,
                        min_threshold,
                    )
                    self._consumption_totals[tank_id] += consumption_energy
                elif consumption_volume > max_threshold:
                    LOGGER.warning(
                        "Tank %s high consumption: %.2f [above threshold: %.2f]",
                        tank_id,
                        consumption_volume,
                        max_threshold,
                    )
                    self._consumption_totals[tank_id] += consumption_energy
                    tank["consumption_anomaly"] = True
                else:
                    self._consumption_totals[tank_id] += consumption_energy
                    LOGGER.debug(
                        "Tank %s consumed %.2f. Total energy: %.3f",
                        tank_id,
                        consumption_volume,
                        self._consumption_totals[tank_id],
                    )

        actual_previous = self._previous_readings.get(tank_id)
        self._previous_readings[tank_id] = current_volume

        tank["consumption_total"] = self._consumption_totals.get(tank_id, 0.0)

        if actual_previous is not None and update_interval_hours > 0:
            consumption_volume = actual_previous - current_volume
            if consumption_volume > 0:
                consumption_energy = consumption_volume * rc.volume_to_energy_factor
                tank["consumption_rate"] = round(
                    consumption_energy / update_interval_hours, 4
                )
            else:
                tank["consumption_rate"] = 0.0
        else:
            tank["consumption_rate"] = 0.0

        tank["data_quality"] = self._data_quality_flags.get(tank_id, "Unknown")

        last_delivery = tank.get("last_delivery", "unknown")
        if last_delivery != "unknown":
            try:
                delivery_date = datetime.strptime(last_delivery, "%Y-%m-%d").replace(
                    tzinfo=UTC
                )
                days_since = (datetime.now(UTC) - delivery_date).days
                tank["days_since_delivery"] = days_since
            except (ValueError, TypeError):
                tank["days_since_delivery"] = "unknown"
        else:
            tank["days_since_delivery"] = "unknown"

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        try:
            client = self.config_entry.runtime_data.client
            tanks_data = await client.async_get_tanks_data()
            orders_data = await client.async_get_orders_data()

            for tank in tanks_data:
                try:
                    self._process_tank_consumption(tank)

                    tank_id = tank.get("tank_id")
                    if tank_id and self._data_quality_flags.get(tank_id) != "Good":
                        LOGGER.info(
                            "Tank %s data quality: %s",
                            tank_id,
                            self._data_quality_flags.get(tank_id, "Unknown"),
                        )
                except Exception:  # noqa: BLE001
                    LOGGER.exception("Error processing tank data — continuing")

            try:
                await self.async_save_consumption_data()
            except Exception:  # noqa: BLE001
                LOGGER.warning("Failed to save consumption data", exc_info=True)

        except SuperiorPlusPropaneApiClientAuthenticationError as exc:
            msg = f"Authentication failed: {exc}"
            raise ConfigEntryAuthFailed(msg) from exc

        except SuperiorPlusPropaneApiClientCommunicationError as exc:
            if "maintenance" in str(exc).lower():
                self.update_interval = timedelta(hours=1)
            else:
                self.update_interval = self._retry_interval
            if self.data and self._is_data_fresh():
                LOGGER.debug("Returning stale data due to communication error")
                return self.data
            msg = f"Communication error: {exc}"
            raise UpdateFailed(msg) from exc

        except SuperiorPlusPropaneApiClientError as exc:
            self.update_interval = self._retry_interval
            msg = f"API error: {exc}"
            raise UpdateFailed(msg) from exc
        else:
            self.update_interval = self._normal_interval
            self.last_successful_update_time = datetime.now(UTC)
            return {"tanks": tanks_data, "orders": orders_data}
