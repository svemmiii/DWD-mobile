"""Weather platform for DWD Mobile."""

from __future__ import annotations

from typing import Any

from homeassistant.components.weather import Forecast, WeatherEntity
from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DwdMobileCoordinator
from .entity import DwdMobileEntity

_STANDARD_FORECAST_KEYS = {
    "datetime",
    "condition",
    "native_temperature",
    "native_templow",
    "native_apparent_temperature",
    "native_dew_point",
    "native_precipitation",
    "precipitation_probability",
    "native_pressure",
    "native_wind_speed",
    "native_wind_gust_speed",
    "wind_bearing",
    "humidity",
    "cloud_coverage",
    "uv_index",
    "is_daytime",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: DwdMobileCoordinator = entry.runtime_data
    async_add_entities([DwdMobileWeather(coordinator)])


class DwdMobileWeather(DwdMobileEntity, WeatherEntity):
    """Mobile weather entity that keeps a stable ID while DWD stations change."""

    _attr_translation_key = "weather"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_native_precipitation_unit = UnitOfLength.MILLIMETERS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_HOURLY | WeatherEntityFeature.FORECAST_DAILY
    )

    def __init__(self, coordinator: DwdMobileCoordinator) -> None:
        DwdMobileEntity.__init__(self, coordinator, "weather")
        data = coordinator.data
        self._forecast_token = (
            (data.station_id, data.weather_updated_at) if data is not None else None
        )

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        return (
            super().available
            and data is not None
            and data.coverage_status == "ok"
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        token = (data.station_id, data.weather_updated_at) if data is not None else None
        if token != self._forecast_token:
            self._forecast_token = token
            self.hass.async_create_task(
                self.async_update_listeners(("daily", "hourly")),
                "DWD Mobile forecast listener update",
            )
        super()._handle_coordinator_update()

    def _get(self, key: str) -> Any:
        data = self.coordinator.data
        return data.values.get(key) if data else None

    @property
    def condition(self) -> str | None:
        return self._get("condition")

    @property
    def native_temperature(self) -> float | None:
        return self._get("temperature")

    @property
    def native_apparent_temperature(self) -> float | None:
        return self._get("apparent_temperature")

    @property
    def native_dew_point(self) -> float | None:
        return self._get("dewpoint")

    @property
    def native_pressure(self) -> float | None:
        return self._get("pressure")

    @property
    def humidity(self) -> float | None:
        return self._get("humidity")

    @property
    def cloud_coverage(self) -> int | None:
        value = self._get("cloud_coverage")
        return int(value) if value is not None else None

    @property
    def native_wind_speed(self) -> float | None:
        return self._get("wind_speed")

    @property
    def native_wind_gust_speed(self) -> float | None:
        return self._get("wind_gusts")

    @property
    def wind_bearing(self) -> float | str | None:
        return self._get("wind_direction")

    @property
    def native_visibility(self) -> float | None:
        return self._get("visibility")

    @property
    def uv_index(self) -> float | None:
        return self._get("uv_index")

    @property
    def ozone(self) -> float | None:
        return self._get("airquality_ozone")

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        data = self.coordinator.data
        if not data:
            return None
        return [
            {key: value for key, value in item.items() if key in _STANDARD_FORECAST_KEYS}
            for item in data.hourly_forecast
        ]

    async def async_forecast_daily(self) -> list[Forecast] | None:
        data = self.coordinator.data
        if not data:
            return None
        return [
            {key: value for key, value in item.items() if key in _STANDARD_FORECAST_KEYS}
            for item in data.daily_forecast
        ]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = dict(super().extra_state_attributes or {})
        data = self.coordinator.data
        if data is None:
            return attrs

        # Put the full current outdoor picture on the weather entity as custom
        # attributes, so automations can use one stable weather.* entity even
        # though Home Assistant's standard WeatherEntity model has no fields
        # for PM2.5, absolute humidity, radar nowcast, etc.
        attrs.update(
            {
                "absolute_humidity": data.values.get("humidity_absolute"),
                "precipitation": data.values.get("precipitation"),
                "precipitation_probability": data.values.get("precipitation_probability"),
                "precipitation_duration": data.values.get("precipitation_duration"),
                "sun_duration": data.values.get("sun_duration"),
                "sun_duration_today": data.values.get("sun_duration_today"),
                "sun_irradiance": data.values.get("sun_irradiance"),
                "fog_probability": data.values.get("fog_probability"),
                "evaporation": data.values.get("evaporation"),
                "airquality_no2": data.values.get("airquality_no2"),
                "airquality_pm2_5": data.values.get("airquality_pm2_5"),
                "airquality_pm10": data.values.get("airquality_pm10"),
                "airquality_ozone": data.values.get("airquality_ozone"),
                "radar_precipitation_now": data.radar_now,
                "radar_next_precipitation": data.radar_next_start,
                "radar_last_success": data.radar_last_success,
                "radar_source_latitude": data.radar_latitude,
                "radar_source_longitude": data.radar_longitude,
            }
        )
        attrs.update(self.coordinator.airquality_device_attributes())
        return attrs
