"""Constants for superior_plus_propane."""

from __future__ import annotations

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "superior_plus_propane"
ATTRIBUTION = "Data provided by Superior Plus Propane"

# Default update interval (seconds) — used as fallback, prefer RegionConfig
DEFAULT_UPDATE_INTERVAL = 3600  # 1 hour

# Configuration options
CONF_REGION = "region"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_MIN_THRESHOLD = "min_consumption_threshold"
CONF_MAX_THRESHOLD = "max_consumption_threshold"
CONF_ADAPTIVE_THRESHOLDS = "adaptive_thresholds"
CONF_INCLUDE_UNMONITORED = "include_unmonitored_tanks"

# Consumption threshold defaults (percentages of tank capacity per hour)
MIN_CONSUMPTION_PERCENTAGE = 0.0001  # 0.01% of tank per hour (pilot lights)
MAX_CONSUMPTION_PERCENTAGE = 0.05  # 5% of tank per hour (extreme usage)

# Data validation
DATA_VALIDATION_TOLERANCE = 0.10  # 10% tolerance for volume vs percentage validation

# Unit conversions
SECONDS_PER_HOUR = 3600
PERCENT_MULTIPLIER = 100.0

# Staleness limit for returning stale data on communication errors
MAX_STALE_DATA_HOURS = 4
