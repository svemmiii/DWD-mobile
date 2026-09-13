"""Tests for location helpers."""

from types import SimpleNamespace

from custom_components.dwd_mobile.const import (
    CONF_LOCATION_ENTITY,
    CONF_LOCATION_MODE,
    LOCATION_MODE_ENTITY,
    LOCATION_MODE_HOME,
)
from custom_components.dwd_mobile.helpers import resolve_location


class _States:
    def __init__(self, states):
        self._states = states

    def get(self, entity_id):
        return self._states.get(entity_id)


def _entry(data):
    return SimpleNamespace(data=data, options={})


def test_home_location_is_read_live():
    hass = SimpleNamespace(config=SimpleNamespace(latitude=50.0, longitude=7.0))
    entry = _entry({CONF_LOCATION_MODE: LOCATION_MODE_HOME})
    assert resolve_location(hass, entry) == (50.0, 7.0)

    hass.config.latitude = 51.0
    hass.config.longitude = 8.0
    assert resolve_location(hass, entry) == (51.0, 8.0)


def test_entity_location_uses_coordinates():
    state = SimpleNamespace(state="not_home", attributes={"latitude": 50.5, "longitude": 7.5})
    hass = SimpleNamespace(states=_States({"device_tracker.test": state}))
    entry = _entry(
        {
            CONF_LOCATION_MODE: LOCATION_MODE_ENTITY,
            CONF_LOCATION_ENTITY: "device_tracker.test",
        }
    )
    assert resolve_location(hass, entry) == (50.5, 7.5)
