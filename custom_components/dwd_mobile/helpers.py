"""Helper functions for DWD Mobile."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_FIXED_LOCATION,
    CONF_LOCATION_ENTITY,
    CONF_LOCATION_MODE,
    LOCATION_MODE_ENTITY,
    LOCATION_MODE_FIXED,
    LOCATION_MODE_HOME,
    WIND_DIRECTION_CARDINAL,
)


def get_entry_value(entry, key: str, default: Any = None) -> Any:
    """Return an option value, falling back to config entry data."""
    if key in entry.options:
        return entry.options[key]
    return entry.data.get(key, default)


def resolve_location(hass: HomeAssistant, entry) -> tuple[float, float]:
    """Resolve the currently configured location.

    Home mode intentionally reads hass.config on every coordinator refresh. This
    makes the integration follow homeassistant.set_location without a reload.
    """
    mode = get_entry_value(entry, CONF_LOCATION_MODE, LOCATION_MODE_HOME)

    if mode == LOCATION_MODE_HOME:
        return float(hass.config.latitude), float(hass.config.longitude)

    if mode == LOCATION_MODE_FIXED:
        location = get_entry_value(entry, CONF_FIXED_LOCATION)
        if not isinstance(location, dict):
            raise ValueError("Fixed location is missing")
        return _validate_coordinates(location.get("latitude"), location.get("longitude"))

    if mode == LOCATION_MODE_ENTITY:
        entity_id = get_entry_value(entry, CONF_LOCATION_ENTITY)
        if not entity_id:
            raise ValueError("Location entity is missing")
        state = hass.states.get(entity_id)
        if state is None:
            raise ValueError(f"Location entity {entity_id} does not exist")

        lat = state.attributes.get("latitude")
        lon = state.attributes.get("longitude")
        if lat is not None and lon is not None:
            return _validate_coordinates(lat, lon)

        # Persons and some trackers can report a zone as their state. Resolve
        # the zone as a useful fallback if exact GPS attributes are absent.
        state_name = str(state.state).strip().lower().replace(" ", "_")
        if state_name == "home":
            zone_state = hass.states.get("zone.home")
        elif state_name not in ("unknown", "unavailable", "not_home", ""):
            zone_state = hass.states.get(f"zone.{state_name}")
        else:
            zone_state = None

        if zone_state is not None:
            return _validate_coordinates(
                zone_state.attributes.get("latitude"),
                zone_state.attributes.get("longitude"),
            )

        raise ValueError(
            f"Location entity {entity_id} has no usable latitude/longitude attributes"
        )

    raise ValueError(f"Unknown location mode: {mode}")


def _validate_coordinates(latitude: Any, longitude: Any) -> tuple[float, float]:
    if latitude is None or longitude is None:
        raise ValueError("Latitude or longitude missing")
    lat = float(latitude)
    lon = float(longitude)
    if not -90 <= lat <= 90:
        raise ValueError("Latitude out of range")
    if not -180 <= lon <= 180:
        raise ValueError("Longitude out of range")
    return lat, lon


def absolute_humidity(temperature_c: float | None, humidity_pct: float | None) -> float | None:
    """Calculate absolute humidity in g/m³."""
    if temperature_c is None or humidity_pct is None:
        return None
    mw = 18.016
    r = 0.083143
    return round(
        (
            6.112
            * math.exp((17.67 * temperature_c) / (temperature_c + 243.5))
            * humidity_pct
            * mw
        )
        / ((273.15 + temperature_c) * r * 100),
        1,
    )


def cardinal_direction(value: float | None) -> str | None:
    if value is None:
        return None
    value = float(value) % 360
    directions = ("N", "NO", "O", "SO", "S", "SW", "W", "NW")
    return directions[int((value + 22.5) // 45) % 8]


def convert_value(data_type, value: Any, wind_direction_type: str = "degrees") -> Any:
    """Convert raw simple_dwd_weatherforecast units into Home Assistant units."""
    if value is None:
        return None

    # Import lazily to keep helper tests independent from the optional library.
    from simple_dwd_weatherforecast.dwdforecast import WeatherDataType

    mapping = {
        WeatherDataType.TEMPERATURE: lambda x: round(float(x) - 273.15, 1),
        WeatherDataType.DEWPOINT: lambda x: round(float(x) - 273.15, 1),
        WeatherDataType.PRESSURE: lambda x: round(float(x) / 100, 1),
        WeatherDataType.WIND_SPEED: lambda x: round(float(x) * 3.6, 1),
        WeatherDataType.WIND_GUSTS: lambda x: round(float(x) * 3.6, 1),
        WeatherDataType.PRECIPITATION: lambda x: round(float(x), 1),
        WeatherDataType.PRECIPITATION_PROBABILITY: lambda x: round(float(x), 0),
        WeatherDataType.PRECIPITATION_DURATION: lambda x: round(float(x), 0),
        WeatherDataType.CLOUD_COVERAGE: lambda x: round(float(x), 0),
        WeatherDataType.VISIBILITY: lambda x: round(float(x) / 1000, 1),
        WeatherDataType.SUN_DURATION: lambda x: round(float(x), 0),
        WeatherDataType.SUN_IRRADIANCE: lambda x: round(float(x) / 3.6, 0),
        WeatherDataType.FOG_PROBABILITY: lambda x: round(float(x), 0),
        WeatherDataType.HUMIDITY: lambda x: round(float(x), 1),
    }

    if data_type == WeatherDataType.WIND_DIRECTION:
        degrees = round(float(value), 0)
        return cardinal_direction(degrees) if wind_direction_type == WIND_DIRECTION_CARDINAL else degrees

    converter = mapping.get(data_type)
    return converter(value) if converter else value
