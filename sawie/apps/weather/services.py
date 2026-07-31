"""Weather integration. Default provider is Open-Meteo, which needs no API key."""
from __future__ import annotations

import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import WeatherData

logger = logging.getLogger("sawie.weather")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 12

# WMO weather interpretation codes used by Open-Meteo.
WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Dense drizzle", 56: "Freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain",
    67: "Heavy freezing rain", 71: "Slight snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Rain showers", 81: "Heavy rain showers",
    82: "Violent rain showers", 85: "Snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Severe thunderstorm with hail",
}


def describe(code: int | None) -> str:
    return WMO_CODES.get(code, "Unknown")


def fetch_open_meteo(latitude: float, longitude: float) -> dict:
    """Call the provider and return the raw payload."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join([
            "temperature_2m", "apparent_temperature", "relative_humidity_2m",
            "precipitation", "weather_code", "wind_speed_10m", "wind_direction_10m",
        ]),
        "hourly": "uv_index",
        "daily": ",".join([
            "weather_code", "temperature_2m_max", "temperature_2m_min",
            "precipitation_sum", "precipitation_probability_max",
            "wind_speed_10m_max", "uv_index_max",
        ]),
        "timezone": settings.TIME_ZONE,
        "forecast_days": 7,
        "wind_speed_unit": "kmh",
    }
    response = requests.get(OPEN_METEO_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def parse_payload(payload: dict) -> dict:
    """Flatten the provider payload into WeatherData fields."""
    current = payload.get("current", {}) or {}
    daily = payload.get("daily", {}) or {}
    hourly = payload.get("hourly", {}) or {}

    uv_series = hourly.get("uv_index") or []
    uv_now = max(uv_series[:24], default=None) if uv_series else None

    forecast = []
    for index, day in enumerate(daily.get("time", [])):
        forecast.append({
            "date": day,
            "code": (daily.get("weather_code") or [None])[index],
            "condition": describe((daily.get("weather_code") or [None])[index]),
            "temp_max": (daily.get("temperature_2m_max") or [None])[index],
            "temp_min": (daily.get("temperature_2m_min") or [None])[index],
            "rain_mm": (daily.get("precipitation_sum") or [None])[index],
            "rain_probability": (daily.get("precipitation_probability_max") or [None])[index],
            "wind_max": (daily.get("wind_speed_10m_max") or [None])[index],
            "uv_max": (daily.get("uv_index_max") or [None])[index],
        })

    code = current.get("weather_code")
    return {
        "observed_at": parse_datetime(current.get("time", "")) if current.get("time") else None,
        "temperature_c": current.get("temperature_2m"),
        "feels_like_c": current.get("apparent_temperature"),
        "humidity_pct": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "rain_probability_pct": forecast[0]["rain_probability"] if forecast else None,
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "wind_direction_deg": current.get("wind_direction_10m"),
        "uv_index": uv_now,
        "condition_code": code,
        "condition_text": describe(code),
        "forecast": forecast,
        "source": settings.WEATHER_PROVIDER,
    }


def get_weather_for_field(field, *, force: bool = False) -> WeatherData | None:
    """Return a cached record when it is fresh, otherwise call the provider."""
    cutoff = timezone.now() - timedelta(minutes=settings.WEATHER_CACHE_MINUTES)
    latest = field.weather_records.first()
    if latest and not force and latest.fetched_at >= cutoff:
        return latest

    try:
        payload = fetch_open_meteo(float(field.latitude), float(field.longitude))
        data = parse_payload(payload)
    except (requests.RequestException, ValueError, KeyError, IndexError):
        logger.warning("Weather lookup failed for field %s", field.code, exc_info=True)
        return latest

    return WeatherData.objects.create(field=field, **data)


def advisory_for(record: WeatherData | None) -> list[dict]:
    """Turn the forecast into short agronomy prompts."""
    if record is None:
        return []
    notes: list[dict] = []
    if (record.rain_probability_pct or 0) >= 60:
        notes.append({"level": "warning", "text":
                      "Rain likely in the next 24 hours. Hold off on spraying and irrigation."})
    if (record.temperature_c or 0) >= 40:
        notes.append({"level": "critical", "text":
                      "Heat stress risk. Irrigate early morning or after sunset."})
    if (record.wind_speed_kmh or 0) >= 25:
        notes.append({"level": "warning", "text":
                      "Wind above 25 km/h. Spray drift risk is high."})
    if (record.uv_index or 0) >= 8:
        notes.append({"level": "info", "text":
                      "Very high UV. Schedule field labour outside midday."})
    if (record.humidity_pct or 0) >= 85:
        notes.append({"level": "info", "text":
                      "High humidity favours fungal disease. Scout for leaf spot."})
    if not notes:
        notes.append({"level": "success", "text": "Conditions are within normal operating range."})
    return notes
