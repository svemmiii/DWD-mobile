"""Sensor platform for DWD Mobile."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfDensity,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import DwdMobileCoordinator
from .entity import DwdMobileEntity


@dataclass(frozen=True, kw_only=True)
class DwdMobileSensorDescription(SensorEntityDescription):
    """Describe a DWD Mobile sensor."""

    value_fn: Callable[[DwdMobileCoordinator], Any]
    forecast_key: str | None = None


def _value(key: str) -> Callable[[DwdMobileCoordinator], Any]:
    return lambda coordinator: coordinator.data.values.get(key) if coordinator.data else None


def _radar_now(coordinator: DwdMobileCoordinator) -> Any:
    return coordinator.data.radar_now if coordinator.data else None


def _radar_next(coordinator: DwdMobileCoordinator) -> Any:
    if not coordinator.data or not coordinator.data.radar_next_start:
        return None
    return dt_util.parse_datetime(coordinator.data.radar_next_start)


def _station_name(coordinator: DwdMobileCoordinator) -> Any:
    return coordinator.data.station_name if coordinator.data else None


def _station_distance(coordinator: DwdMobileCoordinator) -> Any:
    return coordinator.data.station_distance_km if coordinator.data else None


def _location_lat(coordinator: DwdMobileCoordinator) -> Any:
    return coordinator.data.location_latitude if coordinator.data else None


def _location_lon(coordinator: DwdMobileCoordinator) -> Any:
    return coordinator.data.location_longitude if coordinator.data else None


def _location_status(coordinator: DwdMobileCoordinator) -> Any:
    return coordinator.data.location_status if coordinator.data else None


def _coverage_status(coordinator: DwdMobileCoordinator) -> Any:
    return coordinator.data.coverage_status if coordinator.data else None


def _report_state(coordinator: DwdMobileCoordinator) -> Any:
    if not coordinator.data or not coordinator.data.report_text:
        return None
    return coordinator.data.report_time or "Verfügbar"


def _timestamp_value(key: str) -> Callable[[DwdMobileCoordinator], Any]:
    def getter(coordinator: DwdMobileCoordinator) -> Any:
        if not coordinator.data:
            return None
        value = coordinator.data.values.get(key)
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return dt_util.parse_datetime(value)
        return value

    return getter


SENSORS: tuple[DwdMobileSensorDescription, ...] = (
    DwdMobileSensorDescription(
        key="weather_condition",
        translation_key="weather_condition",
        icon="mdi:weather-partly-cloudy",
        value_fn=_value("condition"),
    ),
    DwdMobileSensorDescription(
        key="weather_report",
        translation_key="weather_report",
        icon="mdi:text-box-outline",
        value_fn=_report_state,
    ),
    DwdMobileSensorDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("temperature"),
        forecast_key="temperature",
    ),
    DwdMobileSensorDescription(
        key="apparent_temperature",
        translation_key="apparent_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("apparent_temperature"),
    ),
    DwdMobileSensorDescription(
        key="dewpoint",
        translation_key="dewpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("dewpoint"),
        forecast_key="dewpoint",
    ),
    DwdMobileSensorDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("pressure"),
        forecast_key="pressure",
    ),
    DwdMobileSensorDescription(
        key="wind_speed",
        translation_key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("wind_speed"),
        forecast_key="wind_speed",
    ),
    DwdMobileSensorDescription(
        key="wind_direction",
        translation_key="wind_direction",
        icon="mdi:compass-outline",
        value_fn=_value("wind_direction"),
        forecast_key="wind_direction",
    ),
    DwdMobileSensorDescription(
        key="wind_gusts",
        translation_key="wind_gusts",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("wind_gusts"),
        forecast_key="wind_gusts",
    ),
    DwdMobileSensorDescription(
        key="precipitation",
        translation_key="precipitation",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("precipitation"),
        forecast_key="precipitation",
    ),
    DwdMobileSensorDescription(
        key="precipitation_probability",
        translation_key="precipitation_probability",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-rainy",
        value_fn=_value("precipitation_probability"),
        forecast_key="precipitation_probability",
    ),
    DwdMobileSensorDescription(
        key="precipitation_duration",
        translation_key="precipitation_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("precipitation_duration"),
        forecast_key="precipitation_duration",
    ),
    DwdMobileSensorDescription(
        key="cloud_coverage",
        translation_key="cloud_coverage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:cloud",
        value_fn=_value("cloud_coverage"),
        forecast_key="cloud_coverage",
    ),
    DwdMobileSensorDescription(
        key="visibility",
        translation_key="visibility",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("visibility"),
        forecast_key="visibility",
    ),
    DwdMobileSensorDescription(
        key="sun_duration",
        translation_key="sun_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("sun_duration"),
        forecast_key="sun_duration",
    ),
    DwdMobileSensorDescription(
        key="sun_duration_today",
        translation_key="sun_duration_today",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL,
        value_fn=_value("sun_duration_today"),
    ),
    DwdMobileSensorDescription(
        key="sun_irradiance",
        translation_key="sun_irradiance",
        device_class=SensorDeviceClass.IRRADIANCE,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("sun_irradiance"),
        forecast_key="sun_irradiance",
    ),
    DwdMobileSensorDescription(
        key="fog_probability",
        translation_key="fog_probability",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-fog",
        value_fn=_value("fog_probability"),
        forecast_key="fog_probability",
    ),
    DwdMobileSensorDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("humidity"),
        forecast_key="humidity",
    ),
    DwdMobileSensorDescription(
        key="humidity_absolute",
        translation_key="humidity_absolute",
        device_class=SensorDeviceClass.ABSOLUTE_HUMIDITY,
        native_unit_of_measurement=UnitOfDensity.GRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("humidity_absolute"),
        forecast_key="humidity_absolute",
    ),
    DwdMobileSensorDescription(
        key="uv_index",
        translation_key="uv_index",
        icon="mdi:sun-wireless",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_value("uv_index"),
    ),
    DwdMobileSensorDescription(
        key="evaporation",
        translation_key="evaporation",
        native_unit_of_measurement="kg/m²",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:waves-arrow-up",
        value_fn=_value("evaporation"),
    ),
    DwdMobileSensorDescription(
        key="airquality_no2",
        translation_key="airquality_no2",
        device_class=SensorDeviceClass.NITROGEN_DIOXIDE,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:molecule",
        value_fn=_value("airquality_no2"),
    ),
    DwdMobileSensorDescription(
        key="airquality_ozone",
        translation_key="airquality_ozone",
        device_class=SensorDeviceClass.OZONE,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:molecule",
        value_fn=_value("airquality_ozone"),
    ),
    DwdMobileSensorDescription(
        key="airquality_pm2_5",
        translation_key="airquality_pm2_5",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:blur",
        value_fn=_value("airquality_pm2_5"),
    ),
    DwdMobileSensorDescription(
        key="airquality_pm10",
        translation_key="airquality_pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:blur",
        value_fn=_value("airquality_pm10"),
    ),
    DwdMobileSensorDescription(
        key="radar_precipitation_now",
        translation_key="radar_precipitation_now",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_radar_now,
    ),
    DwdMobileSensorDescription(
        key="radar_next_precipitation",
        translation_key="radar_next_precipitation",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_radar_next,
    ),
    DwdMobileSensorDescription(
        key="forecast_values_time",
        translation_key="forecast_values_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_timestamp_value("forecast_values_time"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DwdMobileSensorDescription(
        key="measured_values_time",
        translation_key="measured_values_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_timestamp_value("measured_values_time"),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DwdMobileSensorDescription(
        key="active_station",
        translation_key="active_station",
        icon="mdi:broadcast-tower",
        value_fn=_station_name,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DwdMobileSensorDescription(
        key="station_distance",
        translation_key="station_distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_station_distance,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DwdMobileSensorDescription(
        key="location_latitude",
        translation_key="location_latitude",
        icon="mdi:latitude",
        value_fn=_location_lat,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DwdMobileSensorDescription(
        key="location_longitude",
        translation_key="location_longitude",
        icon="mdi:longitude",
        value_fn=_location_lon,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DwdMobileSensorDescription(
        key="location_status",
        translation_key="location_status",
        icon="mdi:crosshairs-gps",
        value_fn=_location_status,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DwdMobileSensorDescription(
        key="coverage_status",
        translation_key="coverage_status",
        icon="mdi:map-marker-distance",
        value_fn=_coverage_status,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: DwdMobileCoordinator = entry.runtime_data
    async_add_entities(DwdMobileSensor(coordinator, description) for description in SENSORS)


class DwdMobileSensor(DwdMobileEntity, SensorEntity):
    """Represent one DWD Mobile sensor."""

    entity_description: DwdMobileSensorDescription

    def __init__(
        self,
        coordinator: DwdMobileCoordinator,
        description: DwdMobileSensorDescription,
    ) -> None:
        DwdMobileEntity.__init__(self, coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        if data is None or not self.coordinator.last_update_success:
            return False
        if self.entity_description.key in {
            "active_station",
            "station_distance",
            "location_latitude",
            "location_longitude",
            "location_status",
            "coverage_status",
        }:
            return True
        return data.coverage_status == "ok"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = dict(super().extra_state_attributes or {})
        data = self.coordinator.data
        if data is None:
            return attrs

        key = self.entity_description.key
        forecast_key = self.entity_description.forecast_key
        if forecast_key and forecast_key in data.hourly_sensor_data:
            attrs["forecast"] = data.hourly_sensor_data[forecast_key]

        if key == "weather_report" and data.report_text:
            attrs["data"] = data.report_text

        if key == "radar_next_precipitation":
            attrs.update(data.radar_next_attributes)
            attrs["last_success"] = data.radar_last_success
            attrs["source_latitude"] = data.radar_latitude
            attrs["source_longitude"] = data.radar_longitude

        if key == "radar_precipitation_now":
            attrs["last_success"] = data.radar_last_success
            attrs["source_latitude"] = data.radar_latitude
            attrs["source_longitude"] = data.radar_longitude

        if key.startswith("airquality_"):
            component = {
                "airquality_no2": "Stickstoffdioxid",
                "airquality_ozone": "Ozon",
                "airquality_pm2_5": "PM2_5",
                "airquality_pm10": "PM10",
            }.get(key)
            if component:
                attrs["forecast"] = [
                    {"datetime": item.get("datetime"), "value": item.get("value", {}).get(component)}
                    for item in data.airquality_hourly
                    if isinstance(item.get("value"), dict)
                ]
            attrs.update(self.coordinator.airquality_device_attributes())

        if key == "coverage_status" and data.coverage_message:
            attrs["message"] = data.coverage_message

        if key == "location_status" and data.location_error:
            attrs["last_error"] = data.location_error

        if key == "active_station":
            attrs["station_id"] = data.station_id
            attrs["station_latitude"] = data.station_latitude
            attrs["station_longitude"] = data.station_longitude
            attrs["station_elevation"] = data.station_elevation

        return attrs
