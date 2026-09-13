"""Weather entity regression checks."""

from pathlib import Path


def test_weather_pushes_forecast_listener_updates():
    source = Path("custom_components/dwd_mobile/weather.py").read_text(encoding="utf-8")
    assert "async_update_listeners" in source
    assert '("daily", "hourly")' in source


def test_device_configuration_url_points_to_dwd_mobile_repository():
    source = Path("custom_components/dwd_mobile/entity.py").read_text(encoding="utf-8")
    assert 'configuration_url="https://github.com/svemmiii/DWD-mobile"' in source
    assert 'configuration_url="https://github.com/FL550/dwd_weather"' not in source
