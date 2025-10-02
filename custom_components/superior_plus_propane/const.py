"""Constants for superior_plus_propane."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "superior_plus_propane"
ATTRIBUTION = "Data provided by Superior Plus Propane"

# URLs
LOGIN_PAGE_URL = "https://mysuperioraccountlogin.com/Account/Login?ReturnUrl=%2F"
LOGIN_URL = "https://mysuperioraccountlogin.com/Account/Login?ReturnUrl=%2F"
HOME_URL = "https://mysuperioraccountlogin.com/"
CUSTOMERS_URL = "https://mysuperioraccountlogin.com/Customers"
TANK_URL = "https://mysuperioraccountlogin.com/Tank"

# Default update interval (seconds)
DEFAULT_UPDATE_INTERVAL = 3600  # 1 hour

# Configuration options
CONF_REGION = "region"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_MIN_THRESHOLD = "min_consumption_threshold"
CONF_MAX_THRESHOLD = "max_consumption_threshold"
CONF_ADAPTIVE_THRESHOLDS = "adaptive_thresholds"

# Consumption threshold defaults
# These are percentages of tank capacity per hour
MIN_CONSUMPTION_PERCENTAGE = 0.0001  # 0.01% of tank per hour (pilot lights)
MAX_CONSUMPTION_PERCENTAGE = 0.05    # 5% of tank per hour (extreme usage)

# Absolute bounds for safety
ABSOLUTE_MIN_CONSUMPTION = 0.01  # Minimum 0.01 gallons
ABSOLUTE_MAX_CONSUMPTION = 50.0  # Maximum 50 gallons per reading

# Default static thresholds (for backwards compatibility)
DEFAULT_MIN_CONSUMPTION_GALLONS = 0.01  # Lowered from 0.5
DEFAULT_MAX_CONSUMPTION_GALLONS = 25.0  # Raised from 10.0

# Data validation
DATA_VALIDATION_TOLERANCE = 0.10  # 10% tolerance for gallons vs percentage validation
TANK_SIZE_MIN = 20.0   # Minimum reasonable tank size
TANK_SIZE_MAX = 2000.0 # Maximum reasonable tank size

# Unit conversions
# 1 gallon of liquid propane = ~36 cubic feet of propane gas (at 60°F, 14.73 psi)
# This is the standard conversion factor used in the propane industry
GALLONS_TO_CUBIC_FEET = 36.39  # Propane gallon to cubic feet conversion (at STP)
SECONDS_PER_HOUR = 3600  # Seconds in an hour
PERCENT_MULTIPLIER = 100.0  # For percentage calculations
