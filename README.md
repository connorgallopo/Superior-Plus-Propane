# Superior Plus Propane Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/release/connorgallopo/Superior-Plus-Propane.svg)](https://github.com/connorgallopo/Superior-Plus-Propane/releases)

A custom Home Assistant integration for monitoring propane tanks via the mySuperior customer portals. Supports both **Superior Plus Propane** (United States) and **Superior Propane** (Canada) with automatic consumption tracking for the Energy Dashboard.

## Supported Regions

| Region | Provider | Portal | Units |
|--------|----------|--------|-------|
| United States | [Superior Plus Propane](https://www.superiorpluspropane.com/) | [mysuperioraccountlogin.com](https://mysuperioraccountlogin.com/) | Gallons, ft³ |
| Canada | [Superior Propane](https://www.superiorpropane.com/) | [mysuperior.superiorpropane.com](https://mysuperior.superiorpropane.com/) | Litres, m³ |

Both providers operate under the Superior Plus LP umbrella. Each has its own customer portal with separate login credentials.

## Features

- **US and Canadian Support**: Works with both Superior Plus Propane (US) and Superior Propane (CA) accounts
- **Multi-Tank Support**: Automatically discovers and monitors all tanks on your account
- **Energy Dashboard Integration**: Consumption tracking with `state_class: total_increasing` for Home Assistant's Energy Dashboard
- **Consumption Tracking**: Monitors usage between readings, detects refills, flags anomalies
- **Configurable Thresholds**: Dynamic consumption thresholds that adapt to tank size and polling interval, or set your own
- **Persistent Totals**: Consumption data survives Home Assistant restarts
- **HACS Compatible**: Install and update through HACS

## Tank Data Tracked

For each propane tank on your account, the integration creates the following sensors:

### Primary Metrics

| Sensor | US Unit | CA Unit | Description |
|--------|---------|---------|-------------|
| Tank Level | % | % | Current fill percentage |
| Current Volume | gal | L | Volume currently in tank |
| Tank Capacity | gal | L | Total tank size |

### Delivery & Service

| Sensor | Description |
|--------|-------------|
| Reading Date | When the level was last measured |
| Last Delivery | Date of most recent propane delivery |
| Days Since Delivery | Calculated days since last fill |
| Price per Unit | Current pricing in USD/ft³ (US only) |
| Average Price | Average price paid from order history (CAD/L for CA, USD/ft³ for US) |

### Energy Dashboard Sensors

| Sensor | US Unit | CA Unit | State Class | Description |
|--------|---------|---------|-------------|-------------|
| Total Consumption | ft³ | L | `total_increasing` | Cumulative gas usage |
| Consumption Rate | ft³/h | L/h | `measurement` | Current usage rate |

### Data Quality

| Sensor | Description |
|--------|-------------|
| Data Quality | Validation status: Good, Invalid Tank Size, Invalid Level, Inconsistent Values, or Calculation Error |

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots menu, then "Custom repositories"
4. Add this repository URL: `https://github.com/connorgallopo/Superior-Plus-Propane`
5. Category: "Integration"
6. Install "Superior Plus Propane" from HACS
7. Restart Home Assistant
8. Go to Settings, then Devices & Services, then Add Integration
9. Search for "Superior Plus Propane"

### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/connorgallopo/Superior-Plus-Propane/releases)
2. Copy the `custom_components/superior_plus_propane` folder to your Home Assistant `custom_components` directory
3. Restart Home Assistant
4. Add the integration through Settings, then Devices & Services, then Add Integration

## Configuration

### Prerequisites

- An active account with one of:
  - **US**: [Superior Plus Propane mySuperior portal](https://mysuperioraccountlogin.com/)
  - **Canada**: [Superior Propane mySuperior portal](https://mysuperior.superiorpropane.com/)
- Email address and password for your portal account

### Setup Steps

1. **Add Integration**: Settings, then Devices & Services, then Add Integration
2. **Search**: Look for "Superior Plus Propane"
3. **Select Region**: Choose United States or Canada
4. **Enter Credentials**: Your mySuperior portal email and password
5. **Configure Options**: Update interval, threshold settings, unmonitored tank visibility
6. **Done**: The integration discovers all tanks on your account

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| Update Interval | 3600s (US) / 7200s (CA) | How often to poll for new data (300-86400 seconds) |
| Include Unmonitored Tanks | Off | Show tanks not on a delivery plan |
| Dynamic Consumption Thresholds | On | Automatically adjust thresholds based on tank size. Recommended for most users. |
| Min Consumption Threshold | 0.01 | Per-reading minimum (only used when dynamic thresholds are off) |
| Max Consumption Threshold | 25.0 | Per-reading maximum (only used when dynamic thresholds are off) |

All options can be changed after setup through the integration's "Configure" button in Settings, then Devices & Services.

## Entity Naming

### United States

US entities use the full integration domain and tank address:

```
sensor.superior_plus_propane_123_main_street_level
sensor.superior_plus_propane_123_main_street_current_volume
sensor.superior_plus_propane_123_main_street_capacity
sensor.superior_plus_propane_123_main_street_reading_date
sensor.superior_plus_propane_123_main_street_last_delivery
sensor.superior_plus_propane_123_main_street_price_per_unit
sensor.superior_plus_propane_123_main_street_days_since_delivery
sensor.superior_plus_propane_123_main_street_total_consumption
sensor.superior_plus_propane_123_main_street_consumption_rate
sensor.superior_plus_propane_123_main_street_data_quality
sensor.superior_plus_propane_123_main_street_average_price
```

### Canada

CA entities use Home Assistant's `has_entity_name` convention with shorter sensor labels under the device:

```
sensor.propane_tank_123_main_street_level
sensor.propane_tank_123_main_street_current_volume
sensor.propane_tank_123_main_street_capacity
sensor.propane_tank_123_main_street_reading_date
sensor.propane_tank_123_main_street_last_delivery
sensor.propane_tank_123_main_street_days_since_delivery
sensor.propane_tank_123_main_street_total_consumption
sensor.propane_tank_123_main_street_consumption_rate
sensor.propane_tank_123_main_street_data_quality
sensor.propane_tank_123_main_street_average_price
```

## Energy Dashboard Integration

The integration creates consumption sensors compatible with Home Assistant's Energy Dashboard:

1. Go to Settings, then Dashboards, then Energy
2. Add a Gas source
3. Select your tank's "Total Consumption" sensor
4. View your propane usage alongside other energy sources

How consumption tracking works:

- Compares volume readings between polls to calculate usage
- Converts to the appropriate energy unit (ft³ for US, litres for CA)
- Detects refills (volume increase) and excludes them from totals
- Validates consumption against configurable thresholds
- Persists totals to Home Assistant storage so they survive restarts

## Device Organization

Each propane tank appears as a separate device in Home Assistant:

| Field | US | CA |
|-------|----|----|
| Device Name | Propane Tank - [Address] | Propane Tank - [Address] |
| Manufacturer | Superior Plus Propane | Superior Propane |
| Model | e.g. "500 Gallon Tank" | e.g. "1000 Litre Tank" |

All sensors for a tank are grouped under its device.

## Automation Examples

Replace the entity IDs below with your actual entity IDs from Settings > Devices & Services.

### Low Tank Alert (US)
```yaml
automation:
  - alias: "Propane Tank Low"
    trigger:
      - platform: numeric_state
        entity_id: sensor.superior_plus_propane_123_main_street_level
        below: 20
    action:
      - service: notify.mobile_app
        data:
          message: "Propane tank is at {{ states('sensor.superior_plus_propane_123_main_street_level') }}%"
```

### Low Tank Alert (Canada)
```yaml
automation:
  - alias: "Propane Tank Low"
    trigger:
      - platform: numeric_state
        entity_id: sensor.propane_tank_123_main_street_level
        below: 20
    action:
      - service: notify.mobile_app
        data:
          message: "Propane tank is at {{ states('sensor.propane_tank_123_main_street_level') }}%"
```

### Delivery Reminder
```yaml
automation:
  - alias: "Propane Delivery Overdue"
    trigger:
      - platform: numeric_state
        entity_id: sensor.superior_plus_propane_123_main_street_days_since_delivery
        # For CA, use: sensor.propane_tank_123_main_street_days_since_delivery
        above: 365
    action:
      - service: persistent_notification.create
        data:
          message: "It's been over a year since your last propane delivery."
```

## Troubleshooting

### Authentication Issues

- **US customers**: Verify your credentials at [mysuperioraccountlogin.com](https://mysuperioraccountlogin.com/)
- **CA customers**: Verify your credentials at [mysuperior.superiorpropane.com](https://mysuperior.superiorpropane.com/)
- Make sure you selected the correct region during setup
- Check for account restrictions or two-factor authentication

### No Tank Data

- Confirm your tanks appear when you log into the mySuperior portal directly
- Verify you have active propane service
- Check that tank monitoring is enabled on your account

### Missing Sensors

- Check Home Assistant logs: Settings, then System, then Logs
- If the integration loaded without errors but shows no sensors, try removing and re-adding it
- CA accounts may need a longer update interval (the default 7200s is recommended)

### Update Issues

- Check your internet connection
- Verify the mySuperior portal is accessible in your browser
- The integration backs off automatically on connection errors and retries at a shorter interval
- If the portal is under maintenance, the integration returns cached data for up to 4 hours

## Technical Details

### Architecture

- Fully async — runs on Home Assistant's event loop with `aiohttp` for HTTP
- Region-specific API clients handle authentication and HTML parsing for each portal
- A shared `DataUpdateCoordinator` manages polling, consumption calculation, and threshold validation
- Persistent storage via Home Assistant's `Store` for consumption totals across restarts

### Privacy & Security

- Credentials are stored using Home Assistant's config entry storage
- No data is sent to third parties
- All communication goes directly to the respective mySuperior portal servers

## Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run linting: `scripts/lint`
5. Commit and push
6. Open a Pull Request

### Development Setup

```bash
git clone https://github.com/connorgallopo/Superior-Plus-Propane.git
cd Superior-Plus-Propane
pip install -r requirements.txt
scripts/lint
```

## Support

- **Issues**: [GitHub Issues](https://github.com/connorgallopo/Superior-Plus-Propane/issues)
- **Discussions**: [GitHub Discussions](https://github.com/connorgallopo/Superior-Plus-Propane/discussions)
- **US Account Issues**: [Contact Superior Plus Propane](https://www.superiorpluspropane.com/)
- **CA Account Issues**: [Contact Superior Propane](https://www.superiorpropane.com/)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not affiliated with, endorsed by, or officially supported by Superior Plus Propane or Superior Propane. It is an independent project that interfaces with customer portal data. Use at your own risk.

**Superior Plus Propane**, **Superior Propane**, and **mySuperior** are trademarks of Superior Plus LP.

---

### Keywords for Discovery
*propane, propane tank, propane monitoring, Superior Plus, Superior Plus Propane, Superior Propane, mySuperior, tank level, propane delivery, energy dashboard, home assistant, propane automation, tank monitoring, fuel monitoring, propane sensor, Canada propane, US propane*
