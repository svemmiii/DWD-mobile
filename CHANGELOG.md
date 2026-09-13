# Changelog

## 0.1.0

### Pre-release hardening

- Lowered the declared minimum supported Home Assistant version from 2026.9.0 to **2026.6.0** and added a CI compatibility matrix that runs the full regression suite against both Home Assistant 2026.6.0 and 2026.9.1.
- Fixed all regression failures exposed by the first fully-running Home Assistant test suite: legacy last-location fallback without a timestamp, redundant refresh scheduling after a recent success, atomic-refresh test state, defensive missing forecast attributes, and failed-update retention before coordinator data has been published.
- A failed switch to a newly-nearest station no longer advances the regular weather-attempt clock; the still-working old station therefore continues to receive normal refreshes while the new station is on its own retry throttle.
- Sunrise/sunset and day/night calculations now follow the exact configured mobile coordinates even when the selected DWD station does not change.
- Corrected the Home Assistant device configuration URL to the DWD Mobile repository.
- Fixed pytest 9 / pytest-asyncio configuration for the Home Assistant test harness (`asyncio_mode = auto`, function-scoped async fixtures).
- Fixed apparent temperature: `simple_dwd_weatherforecast` already returns this value in °C, so no Kelvin conversion is applied.
- Normal 10-minute refreshes now clone the active DWD state transactionally while preserving `issue_time`, forecast data and ETags instead of constructing a virgin `Weather()` object.
- Added separate weather-attempt and station-switch-attempt throttles so failed DWD requests are not retried every one-minute coordinator cycle; a failed station switch also cannot trigger a second regular weather request in the same cycle.
- Added configurable last-known-location expiry (60 minutes default, 0 disables) so stale GPS fallback data is not treated as current indefinitely.
- Made weather-station switching atomic: a failed download no longer destroys the last working station/data.
- Made normal weather refreshes atomic for the same reason.
- Added last-valid-position fallback for short GPS/location-entity outages.
- Added Home Assistant weather forecast listener pushes after successful forecast changes.
- Limited DWD air-quality attempts to at most once per hour while the endpoint is unavailable.
- Preserve last valid radar values on request errors; expose last-success time and radar source coordinates.
- Fixed sunrise/sunset checks to compare complete times (including minutes), not only the hour.
- Added a configurable maximum nearest-MOSMIX-station distance (250 km default, 0 disables). MOSMIX itself is worldwide, so this is a remote-location guard rather than a Germany-border restriction.
- Added diagnostic location/coverage status entities and automated tests/validation.

### Initial feature set

- Initial DWD Mobile release.
- Dynamic location source: current Home Assistant location, location entity, or fixed coordinates.
- Automatic nearest DWD weather-station selection with stable Home Assistant entity IDs.
- Weather, current values, hourly/daily forecasts and extended forecast data.
- Radar precipitation nowcast tied to the actual configured location.
- DWD air-quality entities (NO₂, O₃, PM2.5, PM10) retained even while the upstream endpoint is unavailable.
- Diagnostic entities for active station, distance and currently used coordinates.
