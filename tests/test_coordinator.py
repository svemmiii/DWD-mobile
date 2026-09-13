"""Regression tests for mobile/robust coordinator behaviour."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.dwd_mobile.const import DOMAIN
from custom_components.dwd_mobile.coordinator import DwdMobileCoordinator


class _BrokenWeather:
    def update(self, **kwargs):
        raise OSError("network down")


class _RadarBrokenWeather:
    def get_radar_precipitation_forecast(self, **kwargs):
        raise OSError("radar down")

    def get_radar_next_precipitation(self, **kwargs):
        raise OSError("radar down")


class _Sun:
    def riseutc(self, when):
        return when.replace(hour=6, minute=30, second=0, microsecond=0)

    def setutc(self, when):
        return when.replace(hour=19, minute=12, second=0, microsecond=0)


@pytest.mark.asyncio
async def test_failed_station_switch_keeps_old_station(hass, monkeypatch):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)

    old_weather = object()
    coordinator.weather = old_weather
    coordinator.station_id = "OLD"
    coordinator.station = {"name": "Old", "lat": 50.0, "lon": 7.0, "elev": 10}

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.get_stations_sorted_by_distance",
        lambda lat, lon: [["NEW", 1.0]],
    )
    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.load_station_id",
        lambda station_id: {"name": "New", "lat": 50.1, "lon": 7.1, "elev": 20},
    )
    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.Weather",
        lambda station_id: _BrokenWeather(),
    )

    changed = await coordinator._async_select_station(
        50.1, 7.1, datetime.now(timezone.utc)
    )

    assert changed is False
    assert coordinator.station_id == "OLD"
    assert coordinator.weather is old_weather
    assert coordinator.station["name"] == "Old"


@pytest.mark.asyncio
async def test_radar_error_keeps_last_valid_values(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    coordinator.weather = _RadarBrokenWeather()
    old_forecast = {datetime(2026, 9, 13, tzinfo=timezone.utc): 1.2}
    old_next = {"start": datetime(2026, 9, 13, 18, tzinfo=timezone.utc)}
    coordinator._radar_forecast = old_forecast
    coordinator._radar_next = old_next

    await coordinator._async_update_radar(50.0, 7.0)

    assert coordinator._radar_forecast is old_forecast
    assert coordinator._radar_next is old_next


def test_daylight_check_uses_minutes(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    coordinator.sun = _Sun()

    assert coordinator._is_daytime(datetime(2026, 9, 13, 19, 0, tzinfo=timezone.utc)) is True
    assert coordinator._is_daytime(datetime(2026, 9, 13, 19, 30, tzinfo=timezone.utc)) is False


@pytest.mark.asyncio
async def test_max_station_distance_marks_out_of_range(hass, monkeypatch):
    entry = MockConfigEntry(domain=DOMAIN, data={"max_station_distance_km": 250})
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.get_stations_sorted_by_distance",
        lambda lat, lon: [["FAR", 300.0]],
    )
    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.load_station_id",
        lambda station_id: {"name": "Far", "lat": 0.0, "lon": 0.0, "elev": 0},
    )

    changed = await coordinator._async_select_station(
        10.0, 10.0, datetime.now(timezone.utc)
    )

    assert changed is False
    assert coordinator._coverage_status == "out_of_range"
    assert coordinator.weather is None

@pytest.mark.asyncio
async def test_short_gps_outage_uses_last_valid_position(hass, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"enable_radar": False, "enable_airquality": False},
    )
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    coordinator._last_valid_location = (50.0, 7.0)
    coordinator._last_weather_refresh = datetime.now(timezone.utc)
    coordinator.weather = object()
    coordinator.station_id = "OLD"
    coordinator.station = {"name": "Old", "lat": 50.0, "lon": 7.0, "elev": 10}

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.resolve_location",
        lambda hass, entry: (_ for _ in ()).throw(ValueError("gps gone")),
    )

    async def _select(lat, lon, now):
        return False

    coordinator._async_select_station = _select
    coordinator._build_snapshot = lambda lat, lon, now: (lat, lon, coordinator._location_status)

    result = await coordinator._async_update_data()

    assert result == (50.0, 7.0, "last_known")


@pytest.mark.asyncio
async def test_broken_airquality_is_not_retried_every_minute(hass, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"enable_radar": False, "enable_airquality": True},
    )
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    coordinator._last_weather_refresh = datetime.now(timezone.utc)
    coordinator.weather = object()
    coordinator.station_id = "OLD"
    coordinator.station = {"name": "Old", "lat": 50.0, "lon": 7.0, "elev": 10}

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.resolve_location",
        lambda hass, entry: (50.0, 7.0),
    )

    async def _select(lat, lon, now):
        return False

    calls = 0

    async def _aq(lat, lon):
        nonlocal calls
        calls += 1
        return False

    coordinator._async_select_station = _select
    coordinator._async_update_airquality = _aq
    coordinator._build_snapshot = lambda lat, lon, now: (lat, lon)

    await coordinator._async_update_data()
    await coordinator._async_update_data()

    assert calls == 1

@pytest.mark.asyncio
async def test_failed_regular_weather_refresh_keeps_old_object(hass, monkeypatch):
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    old_weather = _BrokenWeather()
    coordinator.weather = old_weather
    coordinator.station_id = "OLD"
    coordinator.station = {"name": "Old", "lat": 50.0, "lon": 7.0, "elev": 10}

    with pytest.raises(OSError):
        await coordinator._async_refresh_current_weather(datetime.now(timezone.utc))

    assert coordinator.weather is old_weather


def test_apparent_temperature_is_already_celsius(hass, monkeypatch):
    """Regression: upstream apparent temperature must not be Kelvin-converted twice."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)

    class _ApparentWeather:
        @staticmethod
        def supports_apparent_temperature():
            return True

        @staticmethod
        def get_apparent_temperature(shouldUpdate=False):
            return 16.0

        @staticmethod
        def get_uv_index(days_from_today=0, shouldUpdate=False):
            return None

    coordinator.weather = _ApparentWeather()
    monkeypatch.setattr(coordinator, "_raw_weather_value", lambda kind, now: None)
    monkeypatch.setattr(coordinator, "_condition", lambda now: "cloudy")

    values = coordinator._current_values(datetime.now(timezone.utc))

    assert values["apparent_temperature"] == 16.0


@pytest.mark.asyncio
async def test_regular_refresh_preserves_upstream_cache_state(hass, monkeypatch):
    """Normal refresh clones the active object instead of creating a virgin Weather()."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)

    class _CachedWeather:
        def __init__(self):
            self.issue_time = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
            self.etags = {"forecast": "etag-123"}
            self.forecast_data = {"cached": {"TTT": 289.15}}
            self.report_data = {"cached": True}
            self.weather_report = "cached report"
            self.uv_reports = {"cached": 3}
            self.apparent_temperature_data = {"cached": 16.0}
            self.airquality_daily = None
            self.airquality_hourly = None

    old_weather = _CachedWeather()
    coordinator.weather = old_weather

    # If _async_refresh_current_weather regresses to Weather(self.station_id), fail loudly.
    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.Weather",
        lambda station_id: (_ for _ in ()).throw(AssertionError("virgin Weather() created")),
    )

    seen = {}

    def _update(candidate):
        seen["candidate"] = candidate
        assert candidate is not old_weather
        assert candidate.issue_time == old_weather.issue_time
        assert candidate.etags == old_weather.etags
        assert candidate.etags is not old_weather.etags
        assert candidate.forecast_data == old_weather.forecast_data
        assert candidate.forecast_data is not old_weather.forecast_data
        candidate.etags["forecast"] = "etag-456"

    monkeypatch.setattr(coordinator, "_update_weather_object", _update)
    now = datetime.now(timezone.utc)
    await coordinator._async_refresh_current_weather(now)

    assert coordinator.weather is seen["candidate"]
    assert coordinator.weather.etags["forecast"] == "etag-456"
    assert old_weather.etags["forecast"] == "etag-123"
    assert coordinator._last_weather_refresh == now


@pytest.mark.asyncio
async def test_failed_weather_attempt_is_throttled(hass, monkeypatch):
    """A DWD outage must not cause a weather download attempt every coordinator minute."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"enable_radar": False, "enable_airquality": False},
    )
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    coordinator.weather = object()
    coordinator.station_id = "OLD"
    coordinator.station = {"name": "Old", "lat": 50.0, "lon": 7.0, "elev": 10}
    coordinator._last_weather_refresh = datetime.now(timezone.utc) - timedelta(minutes=11)

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.resolve_location",
        lambda hass, entry: (50.0, 7.0),
    )

    async def _select(lat, lon, now):
        return False

    calls = 0

    async def _refresh(now):
        nonlocal calls
        calls += 1
        raise OSError("DWD down")

    coordinator._async_select_station = _select
    coordinator._async_refresh_current_weather = _refresh
    coordinator._build_snapshot = lambda lat, lon, now: (lat, lon)

    await coordinator._async_update_data()
    await coordinator._async_update_data()

    assert calls == 1
    assert coordinator._last_weather_attempt is not None


@pytest.mark.asyncio
async def test_recent_success_prevents_redundant_weather_refresh(hass, monkeypatch):
    """A recent successful refresh also throttles the next regular attempt."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"enable_radar": False, "enable_airquality": False},
    )
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    coordinator.weather = object()
    coordinator.station_id = "OLD"
    coordinator.station = {"name": "Old", "lat": 50.0, "lon": 7.0, "elev": 10}
    coordinator._last_weather_refresh = datetime.now(timezone.utc)

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.resolve_location",
        lambda hass, entry: (50.0, 7.0),
    )

    async def _select(lat, lon, now):
        return False

    calls = 0

    async def _refresh(now):
        nonlocal calls
        calls += 1

    coordinator._async_select_station = _select
    coordinator._async_refresh_current_weather = _refresh
    coordinator._build_snapshot = lambda lat, lon, now: (lat, lon)

    await coordinator._async_update_data()

    assert calls == 0


@pytest.mark.asyncio
async def test_last_known_location_without_timestamp_uses_weather_refresh_anchor(hass, monkeypatch):
    """Partial legacy runtime state still survives a short GPS outage."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"enable_radar": False, "enable_airquality": False},
    )
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    anchor = datetime.now(timezone.utc)
    coordinator._last_valid_location = (50.0, 7.0)
    coordinator._last_weather_refresh = anchor
    coordinator.weather = object()
    coordinator.station_id = "OLD"
    coordinator.station = {"name": "Old", "lat": 50.0, "lon": 7.0, "elev": 10}

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.resolve_location",
        lambda hass, entry: (_ for _ in ()).throw(ValueError("gps gone")),
    )

    async def _select(lat, lon, now):
        return False

    coordinator._async_select_station = _select
    coordinator._build_snapshot = lambda lat, lon, now: (lat, lon, coordinator._location_status)

    result = await coordinator._async_update_data()

    assert result == (50.0, 7.0, "last_known")
    assert coordinator._last_valid_location_at == anchor


@pytest.mark.asyncio
async def test_failed_station_switch_is_throttled(hass, monkeypatch):
    """A failed candidate station is not retried every one-minute coordinator cycle."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    coordinator.weather = object()
    coordinator.station_id = "OLD"
    coordinator.station = {"name": "Old", "lat": 50.0, "lon": 7.0, "elev": 10}

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.get_stations_sorted_by_distance",
        lambda lat, lon: [["NEW", 1.0]],
    )
    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.load_station_id",
        lambda station_id: {"name": "New", "lat": 50.1, "lon": 7.1, "elev": 20},
    )

    constructions = 0

    def _new_weather(station_id):
        nonlocal constructions
        constructions += 1
        return _BrokenWeather()

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.Weather", _new_weather
    )

    now = datetime.now(timezone.utc)
    assert await coordinator._async_select_station(50.1, 7.1, now) is False
    assert await coordinator._async_select_station(50.1, 7.1, now) is False

    assert constructions == 1
    assert coordinator.station_id == "OLD"


@pytest.mark.asyncio
async def test_last_known_location_expires(hass, monkeypatch):
    """Stale mobile coordinates eventually stop masquerading as the current location."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "enable_radar": False,
            "enable_airquality": False,
            "last_known_location_max_age_min": 60,
        },
    )
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    coordinator._last_valid_location = (50.0, 7.0)
    coordinator._last_valid_location_at = datetime.now(timezone.utc) - timedelta(minutes=61)

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.resolve_location",
        lambda hass, entry: (_ for _ in ()).throw(ValueError("gps gone")),
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator._location_status == "expired"


@pytest.mark.asyncio
async def test_failed_station_switch_does_not_starve_current_station_refresh(hass, monkeypatch):
    """A broken new station must not postpone refreshes of the working old station."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"enable_radar": False, "enable_airquality": False},
    )
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    coordinator.weather = object()
    coordinator.station_id = "OLD"
    coordinator.station = {"name": "Old", "lat": 50.0, "lon": 7.0, "elev": 10}
    coordinator._last_weather_refresh = datetime.now(timezone.utc) - timedelta(minutes=11)

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.get_stations_sorted_by_distance",
        lambda lat, lon: [["NEW", 1.0]],
    )
    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.load_station_id",
        lambda station_id: {"name": "New", "lat": 50.1, "lon": 7.1, "elev": 20},
    )
    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.dwdforecast.Weather",
        lambda station_id: _BrokenWeather(),
    )

    first = datetime.now(timezone.utc)
    assert await coordinator._async_select_station(50.1, 7.1, first) is False
    assert coordinator._last_weather_attempt is None
    assert coordinator.station_id == "OLD"

    # The candidate switch is now throttled. On the next coordinator cycle the
    # still-active old station must therefore be allowed to perform its regular
    # refresh instead of being starved by the failed NEW candidate.
    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.resolve_location",
        lambda hass, entry: (50.1, 7.1),
    )
    refresh_calls = 0

    async def _refresh(now):
        nonlocal refresh_calls
        refresh_calls += 1
        coordinator._last_weather_refresh = now

    coordinator._async_refresh_current_weather = _refresh
    coordinator._build_snapshot = lambda lat, lon, now: (lat, lon)

    await coordinator._async_update_data()

    assert refresh_calls == 1
    assert coordinator.station_id == "OLD"


@pytest.mark.asyncio
async def test_sun_calculation_follows_exact_mobile_location(hass, monkeypatch):
    """Sunrise/sunset follows GPS/Home coordinates, not station coordinates."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"enable_radar": False, "enable_airquality": False},
    )
    entry.add_to_hass(hass)
    coordinator = DwdMobileCoordinator(hass, entry)
    coordinator.weather = object()
    coordinator.station_id = "OLD"
    coordinator.station = {"name": "Old", "lat": 50.0, "lon": 7.0, "elev": 123}
    coordinator._last_weather_refresh = datetime.now(timezone.utc)

    monkeypatch.setattr(
        "custom_components.dwd_mobile.coordinator.resolve_location",
        lambda hass, entry: (51.2345, 8.6789),
    )

    async def _select(lat, lon, now):
        return False

    coordinator._async_select_station = _select
    seen = {}
    marker = object()

    def _sun(lat, lon, elev):
        seen.update(lat=lat, lon=lon, elev=elev)
        return marker

    coordinator._create_sun = _sun
    coordinator._build_snapshot = lambda lat, lon, now: (lat, lon)

    result = await coordinator._async_update_data()

    assert result == (51.2345, 8.6789)
    assert seen == {"lat": 51.2345, "lon": 8.6789, "elev": 123.0}
    assert coordinator.sun is marker
