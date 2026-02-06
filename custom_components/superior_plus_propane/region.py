"""Region configuration for Superior Plus Propane."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegionConfig:
    """Configuration for a specific region."""

    region: str
    name: str
    manufacturer: str

    # Volume units (for tank capacity, current volume sensors)
    volume_unit: str

    # Energy units (for consumption tracking — HA Energy Dashboard)
    energy_unit: str
    volume_to_energy_factor: float

    # Display units for sensors
    consumption_display_unit: str
    consumption_display_factor: float
    rate_display_unit: str
    rate_display_factor: float
    price_unit: str

    # Thresholds and validation bounds (in native volume units)
    default_update_interval: int
    default_min_threshold: float
    default_max_threshold: float
    absolute_min_consumption: float
    absolute_max_consumption: float
    tank_size_min: float
    tank_size_max: float

    # Retry configuration
    max_api_retries: int
    retry_delay_seconds: int
    retry_interval: int
    auth_settle_delay: int

    # Entity naming
    has_entity_name: bool


US_REGION_CONFIG = RegionConfig(
    region="us",
    name="United States",
    manufacturer="Superior Plus Propane",
    volume_unit="gal",
    energy_unit="ft³",
    volume_to_energy_factor=36.39,
    consumption_display_unit="ft³",
    consumption_display_factor=1.0,
    rate_display_unit="ft³/h",
    rate_display_factor=1.0,
    price_unit="USD/ft³",
    default_update_interval=3600,
    default_min_threshold=0.01,
    default_max_threshold=25.0,
    absolute_min_consumption=0.01,
    absolute_max_consumption=50.0,
    tank_size_min=20.0,
    tank_size_max=2000.0,
    max_api_retries=2,
    retry_delay_seconds=5,
    retry_interval=300,
    auth_settle_delay=0,
    has_entity_name=False,
)

CA_REGION_CONFIG = RegionConfig(
    region="ca",
    name="Canada",
    manufacturer="Superior Propane",
    volume_unit="L",
    energy_unit="m³",
    volume_to_energy_factor=0.272297,
    consumption_display_unit="L",
    consumption_display_factor=3.6724,
    rate_display_unit="L/h",
    rate_display_factor=3.6724,
    price_unit="CAD/L",
    default_update_interval=7200,
    default_min_threshold=0.01,
    default_max_threshold=25.0,
    absolute_min_consumption=0.01,
    absolute_max_consumption=50.0,
    tank_size_min=18.0,
    tank_size_max=227125.0,
    max_api_retries=4,
    retry_delay_seconds=60,
    retry_interval=300,
    auth_settle_delay=8,
    has_entity_name=True,
)

REGION_CONFIGS: dict[str, RegionConfig] = {
    "us": US_REGION_CONFIG,
    "ca": CA_REGION_CONFIG,
}


def get_region_config(region: str) -> RegionConfig:
    """Get RegionConfig for a given region code."""
    config = REGION_CONFIGS.get(region)
    if config is None:
        msg = f"Unknown region: {region}"
        raise ValueError(msg)
    return config
