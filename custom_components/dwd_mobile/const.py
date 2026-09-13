"""Constants for DWD Mobile."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "dwd_mobile"
NAME = "DWD Mobile"
VERSION = "0.1.0"

CONF_LOCATION_MODE = "location_mode"
CONF_LOCATION_ENTITY = "location_entity"
CONF_FIXED_LOCATION = "fixed_location"
CONF_DATA_TYPE = "data_type"
CONF_INTERPOLATE = "interpolate"
CONF_HOURLY_UPDATE = "hourly_update"
CONF_ENABLE_RADAR = "enable_radar"
CONF_ENABLE_AIRQUALITY = "enable_airquality"
CONF_ADDITIONAL_FORECAST_ATTRIBUTES = "additional_forecast_attributes"
CONF_SENSOR_FORECAST_STEPS = "sensor_forecast_steps"
CONF_WIND_DIRECTION_TYPE = "wind_direction_type"
CONF_DAILY_TEMP_HIGH_PRECISION = "daily_temp_high_precision"
CONF_STATION_HYSTERESIS_KM = "station_hysteresis_km"
CONF_MAX_STATION_DISTANCE_KM = "max_station_distance_km"
CONF_LAST_KNOWN_LOCATION_MAX_AGE_MIN = "last_known_location_max_age_min"

LOCATION_MODE_HOME = "home"
LOCATION_MODE_ENTITY = "entity"
LOCATION_MODE_FIXED = "fixed"

DATA_TYPE_FORECAST = "forecast"
DATA_TYPE_MIXED = "mixed"
DATA_TYPE_REPORT = "report"

WIND_DIRECTION_DEGREES = "degrees"
WIND_DIRECTION_CARDINAL = "cardinal"

DEFAULT_DATA_TYPE = DATA_TYPE_MIXED
DEFAULT_INTERPOLATE = True
DEFAULT_HOURLY_UPDATE = False
DEFAULT_ENABLE_RADAR = True
DEFAULT_ENABLE_AIRQUALITY = True
DEFAULT_ADDITIONAL_FORECAST_ATTRIBUTES = True
DEFAULT_SENSOR_FORECAST_STEPS = 250
DEFAULT_WIND_DIRECTION_TYPE = WIND_DIRECTION_DEGREES
DEFAULT_DAILY_TEMP_HIGH_PRECISION = True
DEFAULT_STATION_HYSTERESIS_KM = 0.0
# MOSMIX stations are worldwide. This guard only protects against choosing a
# very distant station in remote/offshore areas. Set to 0 to disable.
DEFAULT_MAX_STATION_DISTANCE_KM = 250.0
# Maximum age of the last valid position used when the configured location
# source temporarily becomes unavailable. 0 disables expiry.
DEFAULT_LAST_KNOWN_LOCATION_MAX_AGE_MIN = 60

COORDINATOR_INTERVAL = timedelta(minutes=1)
WEATHER_REFRESH_INTERVAL = timedelta(minutes=10)
STATION_SWITCH_RETRY_INTERVAL = timedelta(minutes=10)
RADAR_REFRESH_INTERVAL = timedelta(minutes=5)
AIRQUALITY_REFRESH_INTERVAL = timedelta(hours=1)

ATTR_STATION_ID = "station_id"
ATTR_STATION_NAME = "station_name"
ATTR_STATION_DISTANCE_KM = "station_distance_km"
ATTR_STATION_LATITUDE = "station_latitude"
ATTR_STATION_LONGITUDE = "station_longitude"
ATTR_LOCATION_LATITUDE = "location_latitude"
ATTR_LOCATION_LONGITUDE = "location_longitude"
ATTR_LATEST_UPDATE = "latest_update"
ATTR_FORECAST_ISSUE_TIME = "forecast_issue_time"
ATTR_REPORT_ISSUE_TIME = "report_issue_time"
ATTR_LOCATION_STATUS = "location_status"
ATTR_COVERAGE_STATUS = "coverage_status"
ATTR_COVERAGE_MESSAGE = "coverage_message"
ATTR_LOCATION_ERROR = "location_error"
ATTR_WEATHER_UPDATED_AT = "weather_updated_at"
ATTR_RADAR_LAST_SUCCESS = "radar_last_success"
ATTR_RADAR_LATITUDE = "radar_latitude"
ATTR_RADAR_LONGITUDE = "radar_longitude"
ATTR_AIRQUALITY_STATION_ID = "airquality_station_id"
ATTR_AIRQUALITY_STATION_NAME = "airquality_station_name"

# Keys for extra forecast attributes. Home Assistant ignores unknown keys in a
# forecast response, but they are useful to automations that consume the raw
# service response.
ATTR_FORECAST_HUMIDITY_ABSOLUTE = "humidity_absolute"
ATTR_FORECAST_PRECIPITATION_DURATION = "precipitation_duration"
ATTR_FORECAST_SUN_DURATION = "sun_duration"
ATTR_FORECAST_SUN_IRRADIANCE = "sun_irradiance"
ATTR_FORECAST_FOG_PROBABILITY = "fog_probability"
ATTR_FORECAST_VISIBILITY = "visibility"
ATTR_FORECAST_EVAPORATION = "evaporation"
ATTR_FORECAST_AIRQUALITY_NO2 = "airquality_no2"
ATTR_FORECAST_AIRQUALITY_OZONE = "airquality_ozone"
ATTR_FORECAST_AIRQUALITY_PM25 = "airquality_pm2_5"
ATTR_FORECAST_AIRQUALITY_PM10 = "airquality_pm10"
