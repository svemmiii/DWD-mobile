"""Config flow for DWD Mobile."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    LocationSelector,
    NumberSelector,
    SelectSelector,
)

from .const import (
    CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
    CONF_DAILY_TEMP_HIGH_PRECISION,
    CONF_DATA_TYPE,
    CONF_ENABLE_AIRQUALITY,
    CONF_ENABLE_RADAR,
    CONF_FIXED_LOCATION,
    CONF_HOURLY_UPDATE,
    CONF_INTERPOLATE,
    CONF_LOCATION_ENTITY,
    CONF_LOCATION_MODE,
    CONF_MAX_STATION_DISTANCE_KM,
    CONF_LAST_KNOWN_LOCATION_MAX_AGE_MIN,
    CONF_SENSOR_FORECAST_STEPS,
    CONF_STATION_HYSTERESIS_KM,
    CONF_WIND_DIRECTION_TYPE,
    DATA_TYPE_FORECAST,
    DATA_TYPE_MIXED,
    DATA_TYPE_REPORT,
    DEFAULT_ADDITIONAL_FORECAST_ATTRIBUTES,
    DEFAULT_DAILY_TEMP_HIGH_PRECISION,
    DEFAULT_DATA_TYPE,
    DEFAULT_ENABLE_AIRQUALITY,
    DEFAULT_ENABLE_RADAR,
    DEFAULT_HOURLY_UPDATE,
    DEFAULT_INTERPOLATE,
    DEFAULT_MAX_STATION_DISTANCE_KM,
    DEFAULT_LAST_KNOWN_LOCATION_MAX_AGE_MIN,
    DEFAULT_SENSOR_FORECAST_STEPS,
    DEFAULT_STATION_HYSTERESIS_KM,
    DEFAULT_WIND_DIRECTION_TYPE,
    DOMAIN,
    LOCATION_MODE_ENTITY,
    LOCATION_MODE_FIXED,
    LOCATION_MODE_HOME,
    NAME,
    WIND_DIRECTION_CARDINAL,
    WIND_DIRECTION_DEGREES,
)


def _select(options: list[str], translation_key: str) -> SelectSelector:
    return SelectSelector(
        {
            "options": options,
            "mode": "list",
            "translation_key": translation_key,
        }
    )


def _settings_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_DATA_TYPE, default=d.get(CONF_DATA_TYPE, DEFAULT_DATA_TYPE)
            ): _select(
                [DATA_TYPE_MIXED, DATA_TYPE_FORECAST, DATA_TYPE_REPORT], "data_type"
            ),
            vol.Required(
                CONF_INTERPOLATE, default=d.get(CONF_INTERPOLATE, DEFAULT_INTERPOLATE)
            ): BooleanSelector({}),
            vol.Required(
                CONF_HOURLY_UPDATE,
                default=d.get(CONF_HOURLY_UPDATE, DEFAULT_HOURLY_UPDATE),
            ): BooleanSelector({}),
            vol.Required(
                CONF_ENABLE_RADAR,
                default=d.get(CONF_ENABLE_RADAR, DEFAULT_ENABLE_RADAR),
            ): BooleanSelector({}),
            vol.Required(
                CONF_ENABLE_AIRQUALITY,
                default=d.get(CONF_ENABLE_AIRQUALITY, DEFAULT_ENABLE_AIRQUALITY),
            ): BooleanSelector({}),
            vol.Required(
                CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
                default=d.get(
                    CONF_ADDITIONAL_FORECAST_ATTRIBUTES,
                    DEFAULT_ADDITIONAL_FORECAST_ATTRIBUTES,
                ),
            ): BooleanSelector({}),
            vol.Required(
                CONF_SENSOR_FORECAST_STEPS,
                default=d.get(CONF_SENSOR_FORECAST_STEPS, DEFAULT_SENSOR_FORECAST_STEPS),
            ): NumberSelector({"min": 1, "max": 250, "step": 1, "mode": "box"}),
            vol.Required(
                CONF_WIND_DIRECTION_TYPE,
                default=d.get(CONF_WIND_DIRECTION_TYPE, DEFAULT_WIND_DIRECTION_TYPE),
            ): _select(
                [WIND_DIRECTION_DEGREES, WIND_DIRECTION_CARDINAL],
                "wind_direction_type",
            ),
            vol.Required(
                CONF_DAILY_TEMP_HIGH_PRECISION,
                default=d.get(
                    CONF_DAILY_TEMP_HIGH_PRECISION, DEFAULT_DAILY_TEMP_HIGH_PRECISION
                ),
            ): BooleanSelector({}),
            vol.Required(
                CONF_STATION_HYSTERESIS_KM,
                default=d.get(CONF_STATION_HYSTERESIS_KM, DEFAULT_STATION_HYSTERESIS_KM),
            ): NumberSelector({"min": 0, "max": 25, "step": 0.5, "mode": "box"}),
            vol.Required(
                CONF_MAX_STATION_DISTANCE_KM,
                default=d.get(
                    CONF_MAX_STATION_DISTANCE_KM, DEFAULT_MAX_STATION_DISTANCE_KM
                ),
            ): NumberSelector({"min": 0, "max": 1000, "step": 10, "mode": "box"}),
            vol.Required(
                CONF_LAST_KNOWN_LOCATION_MAX_AGE_MIN,
                default=d.get(
                    CONF_LAST_KNOWN_LOCATION_MAX_AGE_MIN,
                    DEFAULT_LAST_KNOWN_LOCATION_MAX_AGE_MIN,
                ),
            ): NumberSelector({"min": 0, "max": 1440, "step": 5, "mode": "box"}),
        }
    )


class DwdMobileConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle DWD Mobile config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            mode = user_input[CONF_LOCATION_MODE]
            self._data.update(user_input)
            if mode == LOCATION_MODE_ENTITY:
                return await self.async_step_entity()
            if mode == LOCATION_MODE_FIXED:
                return await self.async_step_fixed()
            return await self.async_step_settings()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_LOCATION_MODE, default=LOCATION_MODE_HOME): _select(
                        [LOCATION_MODE_HOME, LOCATION_MODE_ENTITY, LOCATION_MODE_FIXED],
                        "location_mode",
                    )
                }
            ),
        )

    async def async_step_entity(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            entity_id = user_input[CONF_LOCATION_ENTITY]
            state = self.hass.states.get(entity_id)
            if state is None:
                errors[CONF_LOCATION_ENTITY] = "entity_not_found"
            else:
                lat = state.attributes.get("latitude")
                lon = state.attributes.get("longitude")
                state_name = str(state.state).strip().lower().replace(" ", "_")
                zone_fallback = state_name == "home" or self.hass.states.get(
                    f"zone.{state_name}"
                ) is not None
                if (lat is None or lon is None) and not zone_fallback:
                    errors[CONF_LOCATION_ENTITY] = "no_coordinates"
            if not errors:
                self._data.update(user_input)
                return await self.async_step_settings()

        return self.async_show_form(
            step_id="entity",
            data_schema=vol.Schema(
                {vol.Required(CONF_LOCATION_ENTITY): EntitySelector({})}
            ),
            errors=errors,
        )

    async def async_step_fixed(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_settings()

        return self.async_show_form(
            step_id="fixed",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_FIXED_LOCATION,
                        default={
                            "latitude": self.hass.config.latitude,
                            "longitude": self.hass.config.longitude,
                        },
                    ): LocationSelector({})
                }
            ),
        )

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title=NAME, data=self._data)

        return self.async_show_form(step_id="settings", data_schema=_settings_schema())

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "DwdMobileOptionsFlow":
        return DwdMobileOptionsFlow()


class DwdMobileOptionsFlow(OptionsFlowWithReload):
    """Allow all important location/settings to be changed later."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current = {**self.config_entry.data, **self.config_entry.options}
        errors: dict[str, str] = {}
        if user_input is not None:
            mode = user_input[CONF_LOCATION_MODE]
            if mode == LOCATION_MODE_ENTITY:
                entity_id = user_input.get(CONF_LOCATION_ENTITY)
                state = self.hass.states.get(entity_id) if entity_id else None
                if state is None:
                    errors[CONF_LOCATION_ENTITY] = "entity_not_found"
                else:
                    lat = state.attributes.get("latitude")
                    lon = state.attributes.get("longitude")
                    state_name = str(state.state).strip().lower().replace(" ", "_")
                    zone_fallback = state_name == "home" or self.hass.states.get(
                        f"zone.{state_name}"
                    ) is not None
                    if (lat is None or lon is None) and not zone_fallback:
                        errors[CONF_LOCATION_ENTITY] = "no_coordinates"
            elif mode == LOCATION_MODE_FIXED and not user_input.get(CONF_FIXED_LOCATION):
                errors[CONF_FIXED_LOCATION] = "fixed_location_required"

            if not errors:
                return self.async_create_entry(data=user_input)

        entity_field = vol.Optional(CONF_LOCATION_ENTITY)
        if current.get(CONF_LOCATION_ENTITY):
            entity_field = vol.Optional(
                CONF_LOCATION_ENTITY,
                description={"suggested_value": current[CONF_LOCATION_ENTITY]},
            )

        schema_dict: dict[Any, Any] = {
            vol.Required(
                CONF_LOCATION_MODE,
                default=current.get(CONF_LOCATION_MODE, LOCATION_MODE_HOME),
            ): _select(
                [LOCATION_MODE_HOME, LOCATION_MODE_ENTITY, LOCATION_MODE_FIXED],
                "location_mode",
            ),
            entity_field: EntitySelector({}),
            vol.Optional(
                CONF_FIXED_LOCATION,
                default=current.get(
                    CONF_FIXED_LOCATION,
                    {
                        "latitude": self.hass.config.latitude,
                        "longitude": self.hass.config.longitude,
                    },
                ),
            ): LocationSelector({}),
        }
        schema_dict.update(_settings_schema(current).schema)
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(schema_dict), errors=errors
        )
