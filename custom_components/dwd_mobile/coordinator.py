"""Data coordinator for DWD Mobile."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
import math
import re
from typing import Any

from markdownify import markdownify
from simple_dwd_weatherforecast import dwdforecast
from simple_dwd_weatherforecast.dwdairquality import AirQuality
from simple_dwd_weatherforecast.dwdforecast import WeatherDataType
from suntimes import SunTimes

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    AIRQUALITY_REFRESH_INTERVAL,
    ATTR_AIRQUALITY_STATION_ID,
    ATTR_AIRQUALITY_STATION_NAME,
    ATTR_FORECAST_AIRQUALITY_NO2,
    ATTR_FORECAST_AIRQUALITY_OZONE,
    ATTR_FORECAST_AIRQUALITY_PM10,
    ATTR_FORECAST_AIRQUALITY_PM25,
    ATTR_FORECAST_EVAPORATION,
    ATTR_FORECAST_FOG_PROBABILITY,
    ATTR_FORECAST_HUMIDITY_ABSOLUTE,
    ATTR_FORECAST_PRECIPITATION_DURATION,
    ATTR_FORECAST_SUN_DURATION,
    ATTR_FORECAST_SUN_IRRADIANCE,
    ATTR_FORECAST_VISIBILITY,
    ATTR_FORECAST_ISSUE_TIME,
    ATTR_LATEST_UPDATE,
    ATTR_LOCATION_STATUS,
    ATTR_COVERAGE_STATUS,
    ATTR_COVERAGE_MESSAGE,
    ATTR_LOCATION_ERROR,
    ATTR_WEATHER_UPDATED_AT,
    ATTR_RADAR_LAST_SUCCESS,
    ATTR_RADAR_LATITUDE,
    ATTR_RADAR_LONGITUDE,
    ATTR_LOCATION_LATITUDE,
    ATTR_LOCATION_LONGITUDE,
    ATTR_REPORT_ISSUE_TIME,
    ATTR_STATION_DISTANCE_KM,
    ATTR_STATION_ID,
    ATTR_STATION_LATITUDE,
    ATTR_STATION_LONGITUDE,
    ATTR_STATION_NAME,
    CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
    CONF_DAILY_TEMP_HIGH_PRECISION,
    CONF_DATA_TYPE,
    CONF_ENABLE_AIRQUALITY,
    CONF_ENABLE_RADAR,
    CONF_HOURLY_UPDATE,
    CONF_INTERPOLATE,
    CONF_SENSOR_FORECAST_STEPS,
    CONF_MAX_STATION_DISTANCE_KM,
    CONF_LAST_KNOWN_LOCATION_MAX_AGE_MIN,
    CONF_STATION_HYSTERESIS_KM,
    CONF_WIND_DIRECTION_TYPE,
    COORDINATOR_INTERVAL,
    DATA_TYPE_FORECAST,
    DATA_TYPE_MIXED,
    DATA_TYPE_REPORT,
    DEFAULT_ADDITIONAL_FORECAST_ATTRIBUTES,
    DEFAULT_DAILY_TEMP_HIGH_PRECISION,
    DEFAULT_ENABLE_AIRQUALITY,
    DEFAULT_ENABLE_RADAR,
    DEFAULT_HOURLY_UPDATE,
    DEFAULT_INTERPOLATE,
    DEFAULT_MAX_STATION_DISTANCE_KM,
    DEFAULT_LAST_KNOWN_LOCATION_MAX_AGE_MIN,
    DEFAULT_SENSOR_FORECAST_STEPS,
    DEFAULT_STATION_HYSTERESIS_KM,
    DEFAULT_WIND_DIRECTION_TYPE,
    RADAR_REFRESH_INTERVAL,
    STATION_SWITCH_RETRY_INTERVAL,
    WEATHER_REFRESH_INTERVAL,
)
from .helpers import absolute_humidity, cardinal_direction, convert_value, get_entry_value, resolve_location

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DwdMobileSnapshot:
    """All values exposed by one DWD Mobile config entry."""

    location_latitude: float
    location_longitude: float
    station_id: str
    station_name: str
    station_distance_km: float | None
    station_latitude: float | None
    station_longitude: float | None
    station_elevation: float | None
    values: dict[str, Any] = field(default_factory=dict)
    hourly_forecast: list[dict[str, Any]] = field(default_factory=list)
    daily_forecast: list[dict[str, Any]] = field(default_factory=list)
    hourly_sensor_data: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    airquality_hourly: list[dict[str, Any]] = field(default_factory=list)
    airquality_daily: dict[str, Any] = field(default_factory=dict)
    report_text: str | None = None
    report_time: str | None = None
    radar_now: float | None = None
    radar_next_start: str | None = None
    radar_next_attributes: dict[str, Any] = field(default_factory=dict)
    latest_update: datetime | None = None
    forecast_issue_time: datetime | None = None
    weather_updated_at: datetime | None = None
    radar_last_success: datetime | None = None
    radar_latitude: float | None = None
    radar_longitude: float | None = None
    location_status: str = "live"
    coverage_status: str = "ok"
    coverage_message: str | None = None
    location_error: str | None = None

    @property
    def device_attributes(self) -> dict[str, Any]:
        return {
            ATTR_STATION_ID: self.station_id,
            ATTR_STATION_NAME: self.station_name,
            ATTR_STATION_DISTANCE_KM: self.station_distance_km,
            ATTR_STATION_LATITUDE: self.station_latitude,
            ATTR_STATION_LONGITUDE: self.station_longitude,
            ATTR_LOCATION_LATITUDE: self.location_latitude,
            ATTR_LOCATION_LONGITUDE: self.location_longitude,
            ATTR_LATEST_UPDATE: self.latest_update,
            ATTR_FORECAST_ISSUE_TIME: self.forecast_issue_time,
            ATTR_REPORT_ISSUE_TIME: self.report_time,
            ATTR_LOCATION_STATUS: self.location_status,
            ATTR_COVERAGE_STATUS: self.coverage_status,
            ATTR_COVERAGE_MESSAGE: self.coverage_message,
            ATTR_LOCATION_ERROR: self.location_error,
            ATTR_WEATHER_UPDATED_AT: self.weather_updated_at,
            ATTR_RADAR_LAST_SUCCESS: self.radar_last_success,
            ATTR_RADAR_LATITUDE: self.radar_latitude,
            ATTR_RADAR_LONGITUDE: self.radar_longitude,
        }


class DwdMobileCoordinator(DataUpdateCoordinator[DwdMobileSnapshot]):
    """Poll DWD while dynamically following a configured location."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"DWD Mobile {entry.entry_id}",
            config_entry=entry,
            update_interval=COORDINATOR_INTERVAL,
        )
        self.entry = entry
        self.weather: dwdforecast.Weather | None = None
        self.station_id: str | None = None
        self.station: dict[str, Any] | None = None
        self.sun: SunTimes | None = None
        self._last_weather_refresh: datetime | None = None
        self._last_weather_attempt: datetime | None = None
        self._last_station_switch_attempt: datetime | None = None
        self._last_station_switch_target: str | None = None
        self._station_switch_attempted_this_cycle = False
        self._last_radar_refresh: datetime | None = None
        self._last_airquality_refresh: datetime | None = None
        self._last_airquality_attempt: datetime | None = None
        self._last_radar_success: datetime | None = None
        self._radar_location: tuple[float, float] | None = None
        self._last_valid_location: tuple[float, float] | None = None
        self._last_valid_location_at: datetime | None = None
        self._location_status = "live"
        self._location_error: str | None = None
        self._coverage_status = "ok"
        self._coverage_message: str | None = None
        self._coverage_station: dict[str, Any] | None = None
        self._coverage_station_id: str | None = None
        self._coverage_station_distance: float | None = None
        self._radar_forecast: dict[Any, Any] | None = None
        self._radar_next: dict[str, Any] | None = None
        self._airquality_hourly: AirQuality | None = None
        self._airquality_daily: AirQuality | None = None
        self._airquality_location: tuple[float, float] | None = None
        self._interpolate_values: dict[WeatherDataType, tuple[float, datetime]] = {}

    async def _async_update_data(self) -> DwdMobileSnapshot:
        now = datetime.now(timezone.utc)
        self._station_switch_attempted_this_cycle = False

        try:
            latitude, longitude = resolve_location(self.hass, self.entry)
            self._last_valid_location = (latitude, longitude)
            self._last_valid_location_at = now
            self._location_status = "live"
            self._location_error = None
        except (TypeError, ValueError) as err:
            if self._last_valid_location is None:
                raise UpdateFailed(f"Standort nicht verfügbar: {err}") from err

            # Keep a short GPS/location outage transparent. In normal operation
            # location and timestamp are written together. If an older runtime/test
            # state contains only the coordinates, use the last successful weather
            # refresh as the best age anchor, otherwise start the fallback age now.
            if self._last_valid_location_at is None:
                self._last_valid_location_at = self._last_weather_refresh or now

            max_age_minutes = float(
                get_entry_value(
                    self.entry,
                    CONF_LAST_KNOWN_LOCATION_MAX_AGE_MIN,
                    DEFAULT_LAST_KNOWN_LOCATION_MAX_AGE_MIN,
                )
            )
            location_age = now - self._last_valid_location_at
            if (
                max_age_minutes > 0
                and location_age > timedelta(minutes=max_age_minutes)
            ):
                self._location_status = "expired"
                self._location_error = str(err)
                raise UpdateFailed(
                    "Standort nicht verfügbar und letzte gültige Position ist "
                    f"{location_age.total_seconds() / 60:.0f} Minuten alt "
                    f"(Grenze {max_age_minutes:.0f} Minuten): {err}"
                ) from err

            latitude, longitude = self._last_valid_location
            error_text = str(err)
            first_cached_cycle = self._location_status != "last_known"
            changed_error = self._location_error != error_text
            self._location_status = "last_known"
            self._location_error = error_text
            log = _LOGGER.warning if first_cached_cycle or changed_error else _LOGGER.debug
            log(
                "Standort vorübergehend nicht verfügbar; verwende letzte gültige Position %.5f, %.5f "
                "(%d Minuten alt): %s",
                latitude,
                longitude,
                int(location_age.total_seconds() // 60),
                err,
            )

        try:
            station_changed = await self._async_select_station(latitude, longitude, now)
        except Exception as err:
            if self.weather is None or self.station is None or self.station_id is None:
                raise UpdateFailed(
                    f"Nächste DWD-Wetterstation konnte nicht bestimmt werden: {err}"
                ) from err
            _LOGGER.warning(
                "Stationsauswahl fehlgeschlagen; behalte letzte gültige Station %s: %s",
                self.station_id,
                err,
            )
            station_changed = False

        # A maximum station distance is only a safety guard for remote/offshore
        # positions. DWD MOSMIX itself is worldwide, so this is not a Germany
        # border check. Diagnostic entities stay available while weather values
        # are marked unavailable by the entity layer.
        if self._coverage_status != "ok":
            return self._build_out_of_coverage_snapshot(latitude, longitude, now)

        if self.weather is None or self.station is None or self.station_id is None:
            raise UpdateFailed("DWD-Wetterstation konnte nicht initialisiert werden")

        # Day/night must follow the exact configured position even while the
        # nearest DWD station stays unchanged. Station elevation is used only as
        # a reasonable altitude approximation because HA's location has no
        # standard elevation field here.
        self.sun = self._create_sun(
            latitude, longitude, float(self.station.get("elev", 0) or 0)
        )

        # Station changes are refreshed atomically inside _async_select_station.
        # Normal refreshes also stay atomic, but preserve the active Weather
        # object's DWD cache/ETag state. Attempts (successful or not) are
        # throttled separately from the timestamp of the last successful data.
        if (
            not station_changed
            and not self._station_switch_attempted_this_cycle
            and self._weather_refresh_due(now)
        ):
            self._last_weather_attempt = now
            try:
                await self._async_refresh_current_weather(now)
            except Exception as err:
                # If a previously working station/weather object exists, keep it
                # available even when DataUpdateCoordinator.data has not yet been
                # populated (for example during an early retry after startup).
                if self.weather is None or self.station is None or self.station_id is None:
                    raise UpdateFailed(
                        f"DWD-Wetterdaten konnten nicht geladen werden: {err}"
                    ) from err
                _LOGGER.warning(
                    "DWD-Wetterupdate fehlgeschlagen, behalte letzte gültige Daten; "
                    "nächster regulärer Versuch frühestens in %d Minuten: %s",
                    int(WEATHER_REFRESH_INTERVAL.total_seconds() // 60),
                    err,
                )

        if get_entry_value(self.entry, CONF_ENABLE_RADAR, DEFAULT_ENABLE_RADAR):
            if station_changed or self._due(
                self._last_radar_refresh, RADAR_REFRESH_INTERVAL, now
            ):
                await self._async_update_radar(latitude, longitude)
                self._last_radar_refresh = now

        if get_entry_value(
            self.entry, CONF_ENABLE_AIRQUALITY, DEFAULT_ENABLE_AIRQUALITY
        ) and self._due(
            self._last_airquality_attempt, AIRQUALITY_REFRESH_INTERVAL, now
        ):
            # Set before the network attempt so a broken endpoint cannot trigger
            # another request on the next one-minute coordinator cycle.
            self._last_airquality_attempt = now
            if await self._async_update_airquality(latitude, longitude):
                self._last_airquality_refresh = now

        return self._build_snapshot(latitude, longitude, now)

    @staticmethod
    def _due(last: datetime | None, interval: timedelta, now: datetime) -> bool:
        return last is None or now - last >= interval

    def _weather_refresh_due(self, now: datetime) -> bool:
        """Return whether another regular DWD weather attempt is due.

        A successful refresh is also an attempt. Using the newest of both
        timestamps avoids an unnecessary immediate refresh when only the success
        timestamp is present (for example after migration/reload/test setup).
        """
        anchors = [
            value
            for value in (self._last_weather_attempt, self._last_weather_refresh)
            if value is not None
        ]
        last_activity = max(anchors) if anchors else None
        return self._due(last_activity, WEATHER_REFRESH_INTERVAL, now)

    async def _async_select_station(
        self, latitude: float, longitude: float, now: datetime
    ) -> bool:
        stations = await self.hass.async_add_executor_job(
            dwdforecast.get_stations_sorted_by_distance, latitude, longitude
        )
        if not stations:
            raise ValueError("Keine DWD-MOSMIX-Station gefunden")

        nearest_id = str(stations[0][0])
        nearest_distance = float(stations[0][1])
        station = await self.hass.async_add_executor_job(
            dwdforecast.load_station_id, nearest_id
        )
        if station is None:
            raise ValueError(f"Stations-ID {nearest_id} ist ungültig")

        self._coverage_station = station
        self._coverage_station_id = nearest_id
        self._coverage_station_distance = nearest_distance

        max_distance = float(
            get_entry_value(
                self.entry,
                CONF_MAX_STATION_DISTANCE_KM,
                DEFAULT_MAX_STATION_DISTANCE_KM,
            )
        )
        if max_distance > 0 and nearest_distance > max_distance:
            self._coverage_status = "out_of_range"
            self._coverage_message = (
                f"Nächste DWD-MOSMIX-Station {station.get('name', nearest_id)} "
                f"ist {nearest_distance:.1f} km entfernt "
                f"(Grenze {max_distance:.0f} km)"
            )
            return False

        self._coverage_status = "ok"
        self._coverage_message = None

        if self.station_id == nearest_id:
            return False

        # Optional anti-flapping hysteresis. Default 0 means: always use the
        # actual nearest station, exactly as requested.
        hysteresis = float(
            get_entry_value(
                self.entry, CONF_STATION_HYSTERESIS_KM, DEFAULT_STATION_HYSTERESIS_KM
            )
        )
        if self.station_id and self.station and hysteresis > 0:
            current_distance = self._distance_km(
                latitude,
                longitude,
                float(self.station["lat"]),
                float(self.station["lon"]),
            )
            if current_distance - nearest_distance < hysteresis:
                return False

        # A failed station switch must not be retried every one-minute
        # coordinator cycle. The attempt timestamp is deliberately separate
        # from the last successful weather refresh.
        if (
            self._last_station_switch_target == nearest_id
            and not self._due(
                self._last_station_switch_attempt, STATION_SWITCH_RETRY_INTERVAL, now
            )
        ):
            return False

        self._last_station_switch_attempt = now
        self._last_station_switch_target = nearest_id
        # A station-switch attempt has its own throttle. Do not touch the
        # regular weather-attempt timestamp before the candidate succeeds:
        # otherwise repeated failures of a new station could indefinitely
        # starve refreshes of the still-active last-known-good station.
        self._station_switch_attempted_this_cycle = True

        # Atomic station switch: create and fully update the candidate first.
        # Only then replace the currently working station/weather object.
        candidate_weather = dwdforecast.Weather(nearest_id)
        try:
            await self.hass.async_add_executor_job(
                self._update_weather_object, candidate_weather
            )
        except Exception as err:
            if self.weather is None:
                raise
            _LOGGER.warning(
                "DWD-Stationswechsel zu %s (%s) fehlgeschlagen; "
                "behalte Station %s und deren letzte gültige Daten: %s",
                nearest_id,
                station.get("name"),
                self.station_id,
                err,
            )
            return False

        candidate_sun = self._create_sun(
            latitude, longitude, float(station.get("elev", 0) or 0)
        )
        old_station_id = self.station_id
        self.station_id = nearest_id
        self.station = station
        self.weather = candidate_weather
        self.sun = candidate_sun
        self._interpolate_values.clear()
        self._last_weather_refresh = now
        self._last_weather_attempt = now
        self._last_radar_refresh = None

        _LOGGER.info(
            "DWD Mobile wechselt Wetterstation von %s zu %s (%s, %.1f km)",
            old_station_id,
            nearest_id,
            station.get("name"),
            nearest_distance,
        )
        return True

    async def _async_refresh_current_weather(self, now: datetime) -> None:
        """Refresh current station atomically while preserving DWD caches/ETags."""
        assert self.weather is not None

        # Do not construct a virgin Weather() object here. The upstream library
        # uses state kept on the object (issue_time, forecast data and ETags) to
        # avoid unnecessary MOSMIX downloads. A shallow clone preserves immutable
        # station/radar state; update-mutated caches are deep-copied so a failed
        # candidate refresh cannot damage the active last-known-good object.
        candidate_weather = copy.copy(self.weather)
        for attr in (
            "etags",
            "forecast_data",
            "report_data",
            "weather_report",
            "uv_reports",
            "apparent_temperature_data",
            "airquality_daily",
            "airquality_hourly",
        ):
            if hasattr(self.weather, attr):
                setattr(
                    candidate_weather,
                    attr,
                    copy.deepcopy(getattr(self.weather, attr)),
                )

        await self.hass.async_add_executor_job(
            self._update_weather_object, candidate_weather
        )
        self.weather = candidate_weather
        self._interpolate_values.clear()
        self._last_weather_refresh = now

    def _update_weather_object(self, weather: dwdforecast.Weather) -> None:
        data_type = get_entry_value(self.entry, CONF_DATA_TYPE, DATA_TYPE_MIXED)
        with_measurements = data_type in (DATA_TYPE_MIXED, DATA_TYPE_REPORT)
        force_hourly = bool(
            get_entry_value(self.entry, CONF_HOURLY_UPDATE, DEFAULT_HOURLY_UPDATE)
        )
        supports_apparent = False
        try:
            supports_apparent = bool(weather.supports_apparent_temperature())
        except Exception:
            supports_apparent = False

        weather.update(
            force_hourly=force_hourly,
            with_forecast=True,
            with_measurements=with_measurements,
            with_report=True,
            with_uv=True,
            with_apparent_temperature=supports_apparent,
        )

    @staticmethod
    def _create_sun(
        latitude: float, longitude: float, elevation: float = 0.0
    ) -> SunTimes | None:
        """Create sun calculations for the actual configured location.

        DWD forecast data comes from the nearest MOSMIX station, but sunrise/
        sunset is a property of the user's real location. Using the station
        coordinates would make day/night lag behind a moving camper.
        """
        try:
            return SunTimes(float(longitude), float(latitude), int(float(elevation)))
        except Exception:
            return None

    async def _async_update_radar(self, latitude: float, longitude: float) -> None:
        if self.weather is None:
            return

        def _fetch() -> tuple[bool, dict[Any, Any] | None, bool, dict[str, Any] | None]:
            forecast_ok = False
            next_ok = False
            forecast = None
            next_precip = None
            try:
                forecast = self.weather.get_radar_precipitation_forecast(
                    shouldUpdate=True, lat=latitude, lon=longitude
                )
                forecast_ok = True
            except Exception as err:
                _LOGGER.debug("DWD Radarniederschlag nicht verfügbar: %s", err)
            try:
                next_precip = self.weather.get_radar_next_precipitation(
                    shouldUpdate=False, lat=latitude, lon=longitude
                )
                next_ok = True
            except Exception as err:
                _LOGGER.debug("DWD nächster Radarniederschlag nicht verfügbar: %s", err)
            return forecast_ok, forecast, next_ok, next_precip

        forecast_ok, forecast, next_ok, next_precip = (
            await self.hass.async_add_executor_job(_fetch)
        )

        # Only replace cached radar values when that specific request succeeded.
        # A successful None is meaningful (for example: no upcoming rain), while
        # an exception keeps the last valid value instead of wiping it.
        if forecast_ok:
            self._radar_forecast = forecast
        if next_ok:
            self._radar_next = next_precip
        if forecast_ok or next_ok:
            self._last_radar_success = datetime.now(timezone.utc)
            self._radar_location = (latitude, longitude)

    async def _async_update_airquality(
        self, latitude: float, longitude: float
    ) -> bool:
        """Try the DWD air-quality source at most once per configured interval.

        The upstream DWD endpoint is currently unavailable. Sensor entities are
        deliberately kept present and simply return unknown. If DWD restores the
        endpoint in the same format, the next hourly refresh fills them without
        any config change.
        """
        try:
            if (
                self._airquality_hourly is None
                or self._airquality_location is None
                or self._distance_km(
                    latitude, longitude, *self._airquality_location
                )
                >= 10.0
            ):
                hourly = await AirQuality.get_station_from_location(
                    latitude, longitude, "hourly"
                )
                daily = await AirQuality.create(hourly.station_id, "daily")
                self._airquality_hourly = hourly
                self._airquality_daily = daily
                self._airquality_location = (latitude, longitude)

            if self._airquality_hourly is not None:
                await self.hass.async_add_executor_job(self._airquality_hourly.update)
            if self._airquality_daily is not None:
                await self.hass.async_add_executor_job(
                    self._airquality_daily.update, True
                )
            return True
        except Exception as err:
            # This is expected while DWD's AQ endpoint is unavailable. Weather
            # must keep working independently. The caller already recorded the
            # attempt timestamp, so a failure will not be retried every minute.
            _LOGGER.debug("DWD-Luftqualität derzeit nicht verfügbar: %s", err)
            return False

    def _build_snapshot(
        self, latitude: float, longitude: float, now: datetime
    ) -> DwdMobileSnapshot:
        assert self.weather is not None
        assert self.station is not None
        assert self.station_id is not None

        values = self._current_values(now)
        aq_current = self._airquality_current()
        values.update(
            {
                "airquality_no2": aq_current.get("Stickstoffdioxid"),
                "airquality_ozone": aq_current.get("Ozon"),
                "airquality_pm2_5": aq_current.get("PM2_5"),
                "airquality_pm10": aq_current.get("PM10"),
            }
        )

        report_text, report_time = self._weather_report()
        hourly = self._hourly_forecast(now)
        daily = self._daily_forecast(now)
        hourly_sensor_data = self._hourly_sensor_data(now)
        airquality_hourly = self._airquality_hourly_data()
        airquality_daily = self._airquality_daily_data()
        radar_now = self._radar_now(now)
        radar_next_start, radar_attrs = self._radar_next_data()

        issue_time = getattr(self.weather, "issue_time", None)
        station_distance = self._distance_km(
            latitude,
            longitude,
            float(self.station["lat"]),
            float(self.station["lon"]),
        )

        return DwdMobileSnapshot(
            location_latitude=latitude,
            location_longitude=longitude,
            station_id=self.station_id,
            station_name=str(self.station.get("name", self.station_id)),
            station_distance_km=station_distance,
            station_latitude=float(self.station["lat"]),
            station_longitude=float(self.station["lon"]),
            station_elevation=float(self.station.get("elev", 0)),
            values=values,
            hourly_forecast=hourly,
            daily_forecast=daily,
            hourly_sensor_data=hourly_sensor_data,
            airquality_hourly=airquality_hourly,
            airquality_daily=airquality_daily,
            report_text=report_text,
            report_time=report_time,
            radar_now=radar_now,
            radar_next_start=radar_next_start,
            radar_next_attributes=radar_attrs,
            latest_update=self._last_weather_refresh,
            forecast_issue_time=issue_time,
            weather_updated_at=self._last_weather_refresh,
            radar_last_success=self._last_radar_success,
            radar_latitude=(self._radar_location[0] if self._radar_location else None),
            radar_longitude=(self._radar_location[1] if self._radar_location else None),
            location_status=self._location_status,
            coverage_status=self._coverage_status,
            coverage_message=self._coverage_message,
            location_error=self._location_error,
        )

    def _build_out_of_coverage_snapshot(
        self, latitude: float, longitude: float, now: datetime
    ) -> DwdMobileSnapshot:
        """Return diagnostic data while current location is too far from MOSMIX."""
        # Keep the diagnostic "active station" honest: when we already have a
        # working station, report that one here. The coverage_message names the
        # too-distant nearest candidate. On first setup there is no active station,
        # so the nearest candidate is shown for diagnostics.
        station = self.station or self._coverage_station or {}
        station_id = self.station_id or self._coverage_station_id or "unknown"
        station_name = str(station.get("name", station_id))
        station_lat = station.get("lat")
        station_lon = station.get("lon")
        station_elev = station.get("elev")
        distance = None
        if distance is None and station_lat is not None and station_lon is not None:
            distance = self._distance_km(
                latitude, longitude, float(station_lat), float(station_lon)
            )

        return DwdMobileSnapshot(
            location_latitude=latitude,
            location_longitude=longitude,
            station_id=station_id,
            station_name=station_name,
            station_distance_km=distance,
            station_latitude=float(station_lat) if station_lat is not None else None,
            station_longitude=float(station_lon) if station_lon is not None else None,
            station_elevation=float(station_elev) if station_elev is not None else None,
            values={},
            latest_update=self._last_weather_refresh,
            forecast_issue_time=(
                getattr(self.weather, "issue_time", None) if self.weather is not None else None
            ),
            weather_updated_at=self._last_weather_refresh,
            radar_last_success=self._last_radar_success,
            radar_latitude=(self._radar_location[0] if self._radar_location else None),
            radar_longitude=(self._radar_location[1] if self._radar_location else None),
            location_status=self._location_status,
            coverage_status=self._coverage_status,
            coverage_message=self._coverage_message,
            location_error=self._location_error,
        )

    def _raw_weather_value(self, data_type: WeatherDataType, now: datetime) -> Any:
        assert self.weather is not None
        mode = get_entry_value(self.entry, CONF_DATA_TYPE, DATA_TYPE_MIXED)
        value = None

        if mode in (DATA_TYPE_REPORT, DATA_TYPE_MIXED):
            try:
                value = self.weather.get_reported_weather(data_type, shouldUpdate=False)
            except Exception:
                value = None

        if mode == DATA_TYPE_FORECAST or (mode == DATA_TYPE_MIXED and value is None):
            try:
                value = self.weather.get_forecast_data(data_type, now, shouldUpdate=False)
            except Exception:
                value = None

        if (
            value is not None
            and get_entry_value(self.entry, CONF_INTERPOLATE, DEFAULT_INTERPOLATE)
            and data_type not in (WeatherDataType.CONDITION,)
        ):
            try:
                value = self._interpolate(data_type, float(value), now)
            except (TypeError, ValueError):
                pass
        return value

    def _interpolate(self, data_type: WeatherDataType, value: float, now: datetime) -> float:
        assert self.weather is not None
        previous, previous_time = self._interpolate_values.get(data_type, (value, now))
        next_value = self.weather.get_forecast_data(
            data_type, now + timedelta(hours=1), shouldUpdate=False
        )
        if next_value is None:
            self._interpolate_values[data_type] = (value, now)
            return value

        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        total_seconds = max((next_hour - previous_time).total_seconds(), 1)
        elapsed = max((now - previous_time).total_seconds(), 0)
        fraction = min(max(elapsed / total_seconds, 0), 1)
        interpolated = previous + (float(next_value) - previous) * fraction
        self._interpolate_values[data_type] = (interpolated, now)
        return interpolated

    def _current_values(self, now: datetime) -> dict[str, Any]:
        assert self.weather is not None
        wind_mode = get_entry_value(
            self.entry, CONF_WIND_DIRECTION_TYPE, DEFAULT_WIND_DIRECTION_TYPE
        )

        def cv(kind: WeatherDataType) -> Any:
            return convert_value(kind, self._raw_weather_value(kind, now), wind_mode)

        temperature = cv(WeatherDataType.TEMPERATURE)
        humidity = cv(WeatherDataType.HUMIDITY)
        condition = self._condition(now)

        apparent = None
        try:
            if self.weather.supports_apparent_temperature():
                raw = self.weather.get_apparent_temperature(shouldUpdate=False)
                # simple_dwd_weatherforecast returns apparent temperature in °C.
                apparent = round(float(raw), 1) if raw is not None else None
        except Exception:
            apparent = None

        uv = None
        try:
            uv = self.weather.get_uv_index(days_from_today=0, shouldUpdate=False)
        except Exception:
            pass

        evaporation = None
        try:
            evaporation = self.weather.get_daily_max(
                WeatherDataType.EVAPORATION,
                now + timedelta(days=1),
                False,
            )
        except Exception:
            pass

        return {
            "condition": condition,
            "temperature": temperature,
            "apparent_temperature": apparent,
            "dewpoint": cv(WeatherDataType.DEWPOINT),
            "pressure": cv(WeatherDataType.PRESSURE),
            "wind_speed": cv(WeatherDataType.WIND_SPEED),
            "wind_direction": cv(WeatherDataType.WIND_DIRECTION),
            "wind_gusts": cv(WeatherDataType.WIND_GUSTS),
            "precipitation": cv(WeatherDataType.PRECIPITATION),
            "precipitation_probability": cv(WeatherDataType.PRECIPITATION_PROBABILITY),
            "precipitation_duration": cv(WeatherDataType.PRECIPITATION_DURATION),
            "cloud_coverage": cv(WeatherDataType.CLOUD_COVERAGE),
            "visibility": cv(WeatherDataType.VISIBILITY),
            "sun_duration": cv(WeatherDataType.SUN_DURATION),
            "sun_duration_today": self._sun_duration_today(now),
            "sun_irradiance": cv(WeatherDataType.SUN_IRRADIANCE),
            "fog_probability": cv(WeatherDataType.FOG_PROBABILITY),
            "humidity": humidity,
            "humidity_absolute": absolute_humidity(temperature, humidity),
            "uv_index": uv,
            "evaporation": evaporation,
            "forecast_values_time": getattr(self.weather, "issue_time", None),
            "measured_values_time": self._reported_time(),
        }


    def _sun_duration_today(self, now: datetime) -> float | None:
        """Return forecast sunshine accumulated from local midnight through now."""
        assert self.weather is not None
        forecast_data = getattr(self.weather, "forecast_data", None)
        if not isinstance(forecast_data, dict) or not forecast_data:
            return None
        local_now = dt_util.as_local(now)
        local_day = local_now.date()
        total = 0.0
        found = False
        for timestamp_key, item in forecast_data.items():
            try:
                ts = datetime.strptime(timestamp_key, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if dt_util.as_local(ts).date() != local_day or ts > now:
                continue
            raw = item.get(WeatherDataType.SUN_DURATION.value[0])
            if raw is not None:
                total += float(raw)
                found = True
        return round(total, 1) if found else None

    def _is_daytime(self, when: datetime) -> bool | None:
        """Return whether *when* is between sunrise and sunset using full UTC times."""
        if self.sun is None:
            return None
        try:
            utc_when = (
                when.astimezone(timezone.utc).replace(tzinfo=None)
                if when.tzinfo is not None
                else when
            )
            sunrise = self.sun.riseutc(utc_when)
            sunset = self.sun.setutc(utc_when)
            if isinstance(sunrise, datetime) and isinstance(sunset, datetime):
                return sunrise <= utc_when <= sunset
            # suntimes uses PN/PD for polar night/day.
            code = str(sunrise).upper()
            if code == "PN":
                return False
            if code == "PD":
                return True
        except Exception:
            pass
        return None

    def _condition(self, now: datetime) -> str | None:
        assert self.weather is not None
        try:
            condition = self.weather.get_forecast_condition(now, False)
        except Exception:
            return None
        if condition == "sunny" and self._is_daytime(now) is False:
            return "clear-night"
        return condition

    def _reported_time(self) -> str | None:
        if self.weather is None:
            return None
        report_data = getattr(self.weather, "report_data", None)
        if not isinstance(report_data, dict):
            return None
        try:
            date = str(report_data.get("date", ""))
            time = str(report_data.get("time", ""))
            parts = date.split(".")
            if len(parts) == 3 and time:
                return f"20{parts[2]}-{parts[1]}-{parts[0]}T{time}:00+00:00"
        except Exception:
            return None
        return None

    def _weather_report(self) -> tuple[str | None, str | None]:
        assert self.weather is not None
        try:
            raw = self.weather.get_weather_report(shouldUpdate=False)
        except Exception:
            raw = None
        if not raw:
            return None, None
        text = markdownify(raw, strip=["pre", "br"]).strip()
        match = re.search(r"\w+, \d{2}\.\d{2}\.\d{2}, \d{2}:\d{2}", text)
        return text, match.group() if match else None

    def _hourly_forecast(self, now: datetime) -> list[dict[str, Any]]:
        assert self.weather is not None
        forecast_data = getattr(self.weather, "forecast_data", None)
        if not isinstance(forecast_data, dict) or not forecast_data:
            return []
        result: list[dict[str, Any]] = []
        start = now.replace(minute=0, second=0, microsecond=0)
        steps = min(int(get_entry_value(self.entry, CONF_SENSOR_FORECAST_STEPS, DEFAULT_SENSOR_FORECAST_STEPS)), 216)
        additional = bool(
            get_entry_value(
                self.entry,
                CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
                DEFAULT_ADDITIONAL_FORECAST_ATTRIBUTES,
            )
        )
        wind_mode = get_entry_value(self.entry, CONF_WIND_DIRECTION_TYPE, DEFAULT_WIND_DIRECTION_TYPE)
        aq_hourly = self._airquality_hourly_data()

        for index in range(steps):
            ts = start + timedelta(hours=index)
            if not self.weather.is_in_timerange(ts):
                break
            try:
                condition = self.weather.get_timeframe_condition(ts, 1, False)
                if condition == "sunny" and self._is_daytime(ts) is False:
                    condition = "clear-night"
                temp = self.weather.get_timeframe_max(WeatherDataType.TEMPERATURE, ts, 1, False)
                dew = self.weather.get_timeframe_max(WeatherDataType.DEWPOINT, ts, 1, False)
                pressure = self.weather.get_timeframe_max(WeatherDataType.PRESSURE, ts, 1, False)
                wind = self.weather.get_timeframe_max(WeatherDataType.WIND_SPEED, ts, 1, False)
                gust = self.weather.get_timeframe_max(WeatherDataType.WIND_GUSTS, ts, 1, False)
                bearing = self.weather.get_timeframe_avg(WeatherDataType.WIND_DIRECTION, ts, 1, False)
                precip = self.weather.get_timeframe_sum(WeatherDataType.PRECIPITATION, ts, 1, False)
                precip_prob = self.weather.get_timeframe_max(
                    WeatherDataType.PRECIPITATION_PROBABILITY, ts, 1, False
                )
                humidity = self.weather.get_timeframe_max(WeatherDataType.HUMIDITY, ts, 1, False)
                cloud = self.weather.get_timeframe_max(WeatherDataType.CLOUD_COVERAGE, ts, 1, False)
            except Exception:
                continue

            item: dict[str, Any] = {
                "datetime": ts.strftime("%Y-%m-%dT%H:00:00Z"),
                "condition": condition,
                "native_temperature": round(temp - 273.15, 1) if temp is not None else None,
                "native_dew_point": round(dew - 273.15, 1) if dew is not None else None,
                "native_pressure": round(pressure / 100, 1) if pressure is not None else None,
                "native_wind_speed": round(wind * 3.6, 1) if wind is not None else None,
                "native_wind_gust_speed": round(gust * 3.6, 1) if gust is not None else None,
                "wind_bearing": (
                    cardinal_direction(bearing)
                    if wind_mode != "degrees" and bearing is not None
                    else round(bearing, 0) if bearing is not None else None
                ),
                "native_precipitation": precip,
                "precipitation_probability": int(precip_prob) if precip_prob is not None else None,
                "humidity": humidity,
                "cloud_coverage": cloud,
            }

            try:
                uv = self.weather.get_uv_index((ts.date() - now.date()).days, shouldUpdate=False)
                item["uv_index"] = uv
            except Exception:
                pass

            if additional:
                try:
                    visibility = self.weather.get_timeframe_min(WeatherDataType.VISIBILITY, ts, 1, False)
                    sun_duration = self.weather.get_timeframe_sum(WeatherDataType.SUN_DURATION, ts, 1, False)
                    irradiance = self.weather.get_timeframe_sum(WeatherDataType.SUN_IRRADIANCE, ts, 1, False)
                    fog = self.weather.get_timeframe_max(WeatherDataType.FOG_PROBABILITY, ts, 1, False)
                    precip_duration = self.weather.get_timeframe_max(
                        WeatherDataType.PRECIPITATION_DURATION, ts, 1, False
                    )
                    evaporation = self.weather.get_timeframe_max(WeatherDataType.EVAPORATION, ts, 1, False)
                    temp_c = round(temp - 273.15, 1) if temp is not None else None
                    item.update(
                        {
                            ATTR_FORECAST_VISIBILITY: round(visibility / 1000, 1) if visibility is not None else None,
                            ATTR_FORECAST_SUN_DURATION: sun_duration,
                            ATTR_FORECAST_SUN_IRRADIANCE: round(irradiance / 3.6, 0) if irradiance is not None else None,
                            ATTR_FORECAST_FOG_PROBABILITY: fog,
                            ATTR_FORECAST_PRECIPITATION_DURATION: precip_duration,
                            ATTR_FORECAST_EVAPORATION: evaporation,
                            ATTR_FORECAST_HUMIDITY_ABSOLUTE: absolute_humidity(temp_c, humidity),
                        }
                    )
                except Exception:
                    pass

                if index < len(aq_hourly):
                    aq = aq_hourly[index].get("value")
                    if isinstance(aq, dict):
                        item.update(
                            {
                                ATTR_FORECAST_AIRQUALITY_NO2: aq.get("Stickstoffdioxid"),
                                ATTR_FORECAST_AIRQUALITY_OZONE: aq.get("Ozon"),
                                ATTR_FORECAST_AIRQUALITY_PM25: aq.get("PM2_5"),
                                ATTR_FORECAST_AIRQUALITY_PM10: aq.get("PM10"),
                            }
                        )

            result.append({k: v for k, v in item.items() if v is not None})
        return result

    def _daily_forecast(self, now: datetime) -> list[dict[str, Any]]:
        assert self.weather is not None
        result: list[dict[str, Any]] = []
        start = dt_util.as_local(now).replace(hour=0, minute=0, second=0, microsecond=0)
        precision = 1 if get_entry_value(
            self.entry, CONF_DAILY_TEMP_HIGH_PRECISION, DEFAULT_DAILY_TEMP_HIGH_PRECISION
        ) else 0
        wind_mode = get_entry_value(self.entry, CONF_WIND_DIRECTION_TYPE, DEFAULT_WIND_DIRECTION_TYPE)
        additional = bool(
            get_entry_value(
                self.entry,
                CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
                DEFAULT_ADDITIONAL_FORECAST_ATTRIBUTES,
            )
        )

        for index in range(9):
            ts = start + timedelta(days=index)
            try:
                condition = self.weather.get_daily_condition(ts, False)
                temp_max = self.weather.get_daily_max(WeatherDataType.TEMPERATURE, ts, False)
                temp_min = self.weather.get_daily_min(WeatherDataType.TEMPERATURE, ts, False)
                dew = self.weather.get_daily_max(WeatherDataType.DEWPOINT, ts, False)
                pressure = self.weather.get_daily_max(WeatherDataType.PRESSURE, ts, False)
                wind = self.weather.get_daily_max(WeatherDataType.WIND_SPEED, ts, False)
                gust = self.weather.get_daily_max(WeatherDataType.WIND_GUSTS, ts, False)
                bearing = self.weather.get_daily_avg(WeatherDataType.WIND_DIRECTION, ts, False)
                precip = self.weather.get_daily_sum(WeatherDataType.PRECIPITATION, ts, False)
                precip_prob = self.weather.get_daily_max(
                    WeatherDataType.PRECIPITATION_PROBABILITY, ts, False
                )
                humidity = self.weather.get_daily_max(WeatherDataType.HUMIDITY, ts, False)
                cloud = self.weather.get_daily_max(WeatherDataType.CLOUD_COVERAGE, ts, False)
            except Exception:
                continue

            item: dict[str, Any] = {
                "datetime": ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "condition": condition,
                "native_temperature": round(temp_max - 273.15, precision) if temp_max is not None else None,
                "native_templow": round(temp_min - 273.15, precision) if temp_min is not None else None,
                "native_dew_point": round(dew - 273.15, 1) if dew is not None else None,
                "native_pressure": round(pressure / 100, 1) if pressure is not None else None,
                "native_wind_speed": round(wind * 3.6, 1) if wind is not None else None,
                "native_wind_gust_speed": round(gust * 3.6, 1) if gust is not None else None,
                "wind_bearing": (
                    cardinal_direction(bearing)
                    if wind_mode != "degrees" and bearing is not None
                    else round(bearing, 0) if bearing is not None else None
                ),
                "native_precipitation": precip,
                "precipitation_probability": int(precip_prob) if precip_prob is not None else None,
                "humidity": humidity,
                "cloud_coverage": cloud,
            }
            try:
                if index < 3:
                    item["uv_index"] = self.weather.get_uv_index(index, shouldUpdate=False)
            except Exception:
                pass

            if additional:
                try:
                    visibility = self.weather.get_daily_min(WeatherDataType.VISIBILITY, ts, False)
                    sun_duration = self.weather.get_daily_sum(WeatherDataType.SUN_DURATION, ts, False)
                    irradiance = self.weather.get_daily_sum(WeatherDataType.SUN_IRRADIANCE, ts, False)
                    fog = self.weather.get_daily_max(WeatherDataType.FOG_PROBABILITY, ts, False)
                    precip_duration = self.weather.get_daily_sum(
                        WeatherDataType.PRECIPITATION_DURATION, ts, False
                    )
                    evaporation = self.weather.get_daily_max(WeatherDataType.EVAPORATION, ts, False)
                    temp_c = round(temp_max - 273.15, 1) if temp_max is not None else None
                    item.update(
                        {
                            ATTR_FORECAST_VISIBILITY: round(visibility / 1000, 1) if visibility is not None else None,
                            ATTR_FORECAST_SUN_DURATION: sun_duration,
                            ATTR_FORECAST_SUN_IRRADIANCE: round(irradiance / (3.6 * 24), 0) if irradiance is not None else None,
                            ATTR_FORECAST_FOG_PROBABILITY: fog,
                            ATTR_FORECAST_PRECIPITATION_DURATION: precip_duration,
                            ATTR_FORECAST_EVAPORATION: evaporation,
                            ATTR_FORECAST_HUMIDITY_ABSOLUTE: absolute_humidity(temp_c, humidity),
                        }
                    )
                except Exception:
                    pass

            result.append({k: v for k, v in item.items() if v is not None})
        return result

    def _hourly_sensor_data(self, now: datetime) -> dict[str, list[dict[str, Any]]]:
        """Expose the same useful per-sensor hourly arrays as the upstream integration."""
        data: dict[str, list[dict[str, Any]]] = {}
        mapping = {
            "temperature": WeatherDataType.TEMPERATURE,
            "dewpoint": WeatherDataType.DEWPOINT,
            "pressure": WeatherDataType.PRESSURE,
            "wind_speed": WeatherDataType.WIND_SPEED,
            "wind_direction": WeatherDataType.WIND_DIRECTION,
            "wind_gusts": WeatherDataType.WIND_GUSTS,
            "precipitation": WeatherDataType.PRECIPITATION,
            "precipitation_probability": WeatherDataType.PRECIPITATION_PROBABILITY,
            "precipitation_duration": WeatherDataType.PRECIPITATION_DURATION,
            "cloud_coverage": WeatherDataType.CLOUD_COVERAGE,
            "visibility": WeatherDataType.VISIBILITY,
            "sun_duration": WeatherDataType.SUN_DURATION,
            "sun_irradiance": WeatherDataType.SUN_IRRADIANCE,
            "fog_probability": WeatherDataType.FOG_PROBABILITY,
            "humidity": WeatherDataType.HUMIDITY,
        }
        assert self.weather is not None
        forecast_data = getattr(self.weather, "forecast_data", None)
        if not isinstance(forecast_data, dict) or not forecast_data:
            return data
        steps = int(get_entry_value(self.entry, CONF_SENSOR_FORECAST_STEPS, DEFAULT_SENSOR_FORECAST_STEPS))
        wind_mode = get_entry_value(self.entry, CONF_WIND_DIRECTION_TYPE, DEFAULT_WIND_DIRECTION_TYPE)
        current_hour = now.replace(minute=0, second=0, microsecond=0)

        for key, kind in mapping.items():
            series: list[dict[str, Any]] = []
            for timestamp_key, raw_item in forecast_data.items():
                try:
                    ts = datetime.strptime(timestamp_key, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
                if ts < current_hour:
                    continue
                raw = raw_item.get(kind.value[0])
                value = convert_value(kind, raw, wind_mode) if raw is not None else None
                series.append({"datetime": timestamp_key, "value": value})
                if len(series) >= steps:
                    break
            data[key] = series

        # Derived absolute humidity uses the already converted hourly series.
        abs_series: list[dict[str, Any]] = []
        temps = data.get("temperature", [])
        hums = data.get("humidity", [])
        for temp, hum in zip(temps, hums):
            abs_series.append(
                {
                    "datetime": temp["datetime"],
                    "value": absolute_humidity(temp.get("value"), hum.get("value")),
                }
            )
        data["humidity_absolute"] = abs_series
        return data

    def _airquality_current(self) -> dict[str, Any]:
        aq = self._airquality_hourly
        if aq is None or not isinstance(aq.data, list) or not aq.data:
            return {}
        first = aq.data[0]
        return first if isinstance(first, dict) else {}

    def _airquality_hourly_data(self) -> list[dict[str, Any]]:
        aq = self._airquality_hourly
        if aq is None or not isinstance(aq.data, list):
            return []
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        steps = int(get_entry_value(self.entry, CONF_SENSOR_FORECAST_STEPS, DEFAULT_SENSOR_FORECAST_STEPS))
        result = []
        for index, value in enumerate(aq.data[:steps]):
            result.append(
                {
                    "datetime": (now + timedelta(hours=index)).strftime("%Y-%m-%dT%H:00:00Z"),
                    "value": value,
                }
            )
        return result

    def _airquality_daily_data(self) -> dict[str, Any]:
        aq = self._airquality_daily
        if aq is None or not isinstance(aq.data, dict):
            return {}
        return dict(aq.data)

    def _radar_now(self, now: datetime) -> float | None:
        forecast = self._radar_forecast
        if not isinstance(forecast, dict) or not forecast:
            return None
        items = sorted(forecast.items())
        current = None
        for timestamp, value in items:
            if timestamp <= now:
                current = value
            elif current is not None:
                break
        if current is None:
            current = items[0][1]
        return round(float(current), 1) if current is not None else None

    def _radar_next_data(self) -> tuple[str | None, dict[str, Any]]:
        value = self._radar_next
        if not isinstance(value, dict):
            return None, {}
        start = value.get("start")
        start_str = start.strftime("%Y-%m-%dT%H:%M:%S+00:00") if start is not None else None
        attrs: dict[str, Any] = {}
        end = value.get("end")
        if end is not None:
            attrs["end"] = end.strftime("%Y-%m-%dT%H:%M:%S+00:00")
        length = value.get("length")
        if length is not None:
            attrs["length_minutes"] = int(length.total_seconds() / 60)
        if value.get("max") is not None:
            attrs["max_mm_h"] = round(float(value["max"]), 1)
        if value.get("sum") is not None:
            attrs["sum_mm"] = round(float(value["sum"]), 1)
        return start_str, attrs

    @staticmethod
    def _distance_km(lat: float, lon: float, lat2: float, lon2: float) -> float:
        lon_diff = 111.3 * math.cos((lat + lat2) / 2 * 0.01745) * (lon - lon2)
        lat_diff = 111.3 * (lat - lat2)
        return round(math.sqrt(lon_diff**2 + lat_diff**2), 1)

    def airquality_device_attributes(self) -> dict[str, Any]:
        aq = self._airquality_hourly
        if aq is None:
            return {}
        return {
            ATTR_AIRQUALITY_STATION_ID: getattr(aq, "station_id", None),
            ATTR_AIRQUALITY_STATION_NAME: getattr(aq, "station_name", None),
            "airquality_source_latitude": (
                self._airquality_location[0] if self._airquality_location else None
            ),
            "airquality_source_longitude": (
                self._airquality_location[1] if self._airquality_location else None
            ),
            "airquality_last_attempt": self._last_airquality_attempt,
            "airquality_last_success": self._last_airquality_refresh,
        }
