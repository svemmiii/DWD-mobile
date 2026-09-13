# DWD Mobile for Home Assistant

**DWD Mobile** is a custom Home Assistant integration for mobile installations such as campers, caravans and boats. It uses the DWD data stack from `simple_dwd_weatherforecast` and automatically selects the nearest DWD forecast station for the configured location.

> This is a community project and is **not affiliated with or endorsed by Deutscher Wetterdienst (DWD)**. Weather data is provided by DWD Open Data. The integration is inspired by and intentionally compatible in spirit with the excellent `FL550/dwd_weather` integration.

## Compatibility

- **Minimum supported Home Assistant version: 2026.6.0**.
- HACS uses this value from `hacs.json`, so older Home Assistant installations will not be offered this release.
- CI runs the integration tests against both **Home Assistant 2026.6.0** and the current supported test baseline (**2026.9.1** at the time of v0.1.0 hardening).

## What makes it mobile?

The location is resolved again on every coordinator cycle. You can choose one of three sources:

1. **Current Home Assistant location** — ideal when `homeassistant.set_location` moves your Home zone from GPS.
2. **Location entity** — a `device_tracker`, `person`, `zone`, or another entity exposing `latitude` and `longitude`.
3. **Fixed location** — choose coordinates directly on the Home Assistant map selector.

For each resolved position, DWD Mobile asks `simple_dwd_weatherforecast` for the nearest DWD MOSMIX station. If the nearest station changes, the new station is downloaded **atomically**: the old working station/data remain active until the new station has loaded successfully. All Home Assistant entity IDs stay stable.

## Update behavior

- Position / nearest-station check: **every 1 minute**.
- DWD weather refresh attempt: **at most every 10 minutes**, and immediately after a station switch. Failed attempts are throttled too, so a DWD outage is not retried every minute.
- DWD radar nowcast: **every 5 minutes**, using the configured position itself rather than the weather-station coordinates.
- DWD air-quality attempt: **at most once per hour**. Failed endpoints are not hammered every minute.

If your Home Assistant Home location is already throttled to one GPS update every five minutes, DWD Mobile follows that automatically; no second GPS automation is required.

### Mobile robustness

- A short GPS/entity outage keeps using the **last valid position** instead of immediately making the integration unavailable. The diagnostic `Location status` sensor shows `last_known` while this fallback is active. The fallback expires after **60 minutes by default** (configurable; `0` disables expiry).
- Failed weather downloads keep the **last valid weather object**. This applies to normal refreshes and station switches. Normal refreshes preserve the upstream `Weather` cache/ETag state instead of creating a fresh downloader every ten minutes.
- Failed radar requests keep the last valid radar data and expose its last-success timestamp and source coordinates.
- Weather forecast subscribers are explicitly notified after a successful weather refresh/station switch.
- Failed switches to a newly-nearest station have their own retry throttle and **do not postpone regular refreshes of the still-working old station**.
- Sunrise/sunset and day/night are calculated for the **actual configured mobile position**, not for the coordinates of the selected DWD station.
- A configurable maximum distance to the nearest MOSMIX station prevents obviously irrelevant data at very remote/offshore locations. The default is 250 km; `0` disables this guard.

**MOSMIX is not limited to Germany.** DWD publishes MOSMIX forecast points worldwide, so the distance guard is intentionally not a Germany-border check.

## Entities and data

The integration creates one `weather` entity plus separate sensors. Current values include, where DWD provides them:

- Weather condition
- Temperature and apparent temperature
- Dew point
- Relative and calculated absolute humidity
- Pressure
- Wind speed, direction and gusts
- Precipitation, probability and duration
- Cloud coverage
- Visibility
- Sunshine duration, sunshine duration today and solar irradiance
- Fog probability
- UV index
- Evaporation
- DWD weather report
- Radar precipitation now and next precipitation
- Active DWD station, station distance and currently used coordinates
- Hourly and daily weather forecasts

The weather entity additionally exposes the non-standard current outdoor values as attributes so an automation or another custom integration can use one stable `weather.*` entity as its outdoor source.

### Air quality

The following DWD air-quality entities are always created:

- Nitrogen dioxide (NO₂)
- Ozone (O₃)
- PM2.5
- PM10

The DWD endpoint used by the upstream library is currently unavailable. While that remains the case, these entities show `unknown`. They are intentionally retained, and DWD Mobile retries the DWD source periodically so they can become populated again if DWD restores a compatible endpoint.

There is no DWD CO₂ entity in this data source.

## Recommended setup for a camper

If an automation already calls `homeassistant.set_location` from the vehicle GPS, choose **Current Home Assistant location** during DWD Mobile setup. This is the cleanest mode: your GPS moves Home, and DWD Mobile follows Home and changes to the nearest DWD station when needed.

## Installation through HACS as a custom repository

1. Put the contents of this repository in a **public GitHub repository**.
2. In HACS open **Custom repositories**.
3. Add the GitHub repository URL and choose category **Integration**.
4. Install **DWD Mobile**.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration** and search for **DWD Mobile**.
7. Choose the location source and DWD settings.

The integration uses the unique domain `dwd_mobile`, so it can coexist with `FL550/dwd_weather` during testing.

## Important first-test note

This v0.1.0 includes pre-release hardening for atomic station switching, cache-preserving weather refreshes, independent retry throttles, expiring GPS fallback, forecast listener updates, air-quality retry throttling, radar cache retention, apparent-temperature unit correctness, full-time sunrise/sunset comparisons and exact-location sun calculations. Python/JSON validation and repository regression tests are included. Keep your existing DWD integration installed in parallel for the first real Home Assistant comparison before replacing it.

## Credits and license

- Weather data: Deutscher Wetterdienst (DWD) Open Data
- Python data library: `FL550/simple_dwd_weatherforecast`
- Reference integration and behavior: `FL550/dwd_weather`

Licensed under **GNU GPL v3.0**. See `LICENSE`.
