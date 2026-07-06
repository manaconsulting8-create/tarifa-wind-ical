#!/usr/bin/env python3
"""
Generate an iCalendar (.ics) forecast for Tarifa wind sessions.
Data source: Open-Meteo forecast + marine APIs, no API key required.
"""
from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# --- Spot configuration ---
SPOT_NAME = os.getenv("SPOT_NAME", "Tarifa")
LATITUDE = float(os.getenv("LATITUDE", "36.0143"))
LONGITUDE = float(os.getenv("LONGITUDE", "-5.6044"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Madrid")
FORECAST_DAYS = int(os.getenv("FORECAST_DAYS", "7"))
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "tarifa-wind.ics")

# --- Session criteria: adjust these for kite / windsurf / wingfoil ---
MIN_WIND_KT = float(os.getenv("MIN_WIND_KT", "16"))
GOOD_WIND_KT = float(os.getenv("GOOD_WIND_KT", "20"))
EXCELLENT_WIND_KT = float(os.getenv("EXCELLENT_WIND_KT", "25"))
MAX_GUST_KT = float(os.getenv("MAX_GUST_KT", "40"))
MAX_WAVE_M = float(os.getenv("MAX_WAVE_M", "1.8"))
MIN_BLOCK_HOURS = int(os.getenv("MIN_BLOCK_HOURS", "2"))

# Levante roughly E/ENE/ESE, Poniente roughly W/WSW/WNW.
# Set WIND_SECTORS="0-360" to include all wind directions.
WIND_SECTORS = os.getenv("WIND_SECTORS", "60-130,240-300")


def kt(kmh: float | None) -> float | None:
    if kmh is None:
        return None
    return kmh * 0.539957


def parse_sectors(raw: str) -> list[tuple[float, float]]:
    sectors: list[tuple[float, float]] = []
    for part in raw.split(","):
        start, end = part.strip().split("-")
        sectors.append((float(start) % 360, float(end) % 360))
    return sectors


def direction_in_sectors(deg: float | None, sectors: list[tuple[float, float]]) -> bool:
    if deg is None:
        return False
    d = deg % 360
    for start, end in sectors:
        if start <= end and start <= d <= end:
            return True
        if start > end and (d >= start or d <= end):
            return True
    return False


def compass(deg: float | None) -> str:
    if deg is None:
        return "?"
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return dirs[int((deg + 11.25) // 22.5) % 16]


def fetch_json(base_url: str, params: dict[str, str | int | float]) -> dict:
    url = base_url + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_forecast() -> dict:
    return fetch_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "hourly": "wind_speed_10m,wind_gusts_10m,wind_direction_10m",
            "wind_speed_unit": "kmh",
            "timezone": TIMEZONE,
            "forecast_days": FORECAST_DAYS,
        },
    )


def fetch_marine() -> dict:
    return fetch_json(
        "https://marine-api.open-meteo.com/v1/marine",
        {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "hourly": "wave_height,wave_period,wave_direction",
            "timezone": TIMEZONE,
            "forecast_days": min(FORECAST_DAYS, 8),
        },
    )


@dataclass
class Hour:
    time: datetime
    wind_kt: float | None
    gust_kt: float | None
    direction: float | None
    wave_m: float | None
    wave_period: float | None
    wave_direction: float | None


def merge_hours(weather: dict, marine: dict) -> list[Hour]:
    tz = ZoneInfo(TIMEZONE)
    w = weather["hourly"]
    m = marine.get("hourly", {})
    marine_by_time = {t: i for i, t in enumerate(m.get("time", []))}
    out: list[Hour] = []
    for i, t in enumerate(w["time"]):
        mi = marine_by_time.get(t)
        dt = datetime.fromisoformat(t).replace(tzinfo=tz)
        out.append(
            Hour(
                time=dt,
                wind_kt=kt(w.get("wind_speed_10m", [None])[i]),
                gust_kt=kt(w.get("wind_gusts_10m", [None])[i]),
                direction=w.get("wind_direction_10m", [None])[i],
                wave_m=m.get("wave_height", [None] * len(marine_by_time))[mi] if mi is not None else None,
                wave_period=m.get("wave_period", [None] * len(marine_by_time))[mi] if mi is not None else None,
                wave_direction=m.get("wave_direction", [None] * len(marine_by_time))[mi] if mi is not None else None,
            )
        )
    return out


def is_usable(h: Hour) -> bool:
    sectors = parse_sectors(WIND_SECTORS)
    return (
        h.wind_kt is not None
        and h.gust_kt is not None
        and h.wind_kt >= MIN_WIND_KT
        and h.gust_kt <= MAX_GUST_KT
        and direction_in_sectors(h.direction, sectors)
        and (h.wave_m is None or h.wave_m <= MAX_WAVE_M)
    )


def rating(avg_wind: float) -> tuple[str, str]:
    if avg_wind >= EXCELLENT_WIND_KT:
        return "🟢 Excellent", "Excellent"
    if avg_wind >= GOOD_WIND_KT:
        return "🟡 Good", "Good"
    return "⚪ Possible", "Possible"


def build_blocks(hours: list[Hour]) -> list[list[Hour]]:
    blocks: list[list[Hour]] = []
    current: list[Hour] = []
    for h in hours:
        if is_usable(h):
            current.append(h)
        else:
            if len(current) >= MIN_BLOCK_HOURS:
                blocks.append(current)
            current = []
    if len(current) >= MIN_BLOCK_HOURS:
        blocks.append(current)
    return blocks


def ical_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fmt_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def fold_ical_line(line: str) -> str:
    # Conservative character folding. Good enough for ASCII-heavy content.
    max_len = 73
    if len(line) <= max_len:
        return line
    parts = [line[:max_len]]
    line = line[max_len:]
    while line:
        parts.append(" " + line[:max_len])
        line = line[max_len:]
    return "\r\n".join(parts)


def make_calendar(blocks: list[list[Hour]]) -> str:
    now = datetime.now(timezone.utc)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//tarifa-wind-ical//open-meteo//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ical_escape(SPOT_NAME)} wind forecast",
        f"X-WR-TIMEZONE:{TIMEZONE}",
    ]
    for block in blocks:
        start = block[0].time
        end = block[-1].time + timedelta(hours=1)
        avg_wind = sum(h.wind_kt or 0 for h in block) / len(block)
        max_gust = max(h.gust_kt or 0 for h in block)
        avg_dir = sum(h.direction or 0 for h in block) / len(block)
        max_wave = max((h.wave_m or 0) for h in block)
        avg_period = sum((h.wave_period or 0) for h in block) / len(block)
        label, slug = rating(avg_wind)
        title = f"{label} {SPOT_NAME}: {avg_wind:.0f} kt {compass(avg_dir)}, gusts {max_gust:.0f} kt"
        desc = (
            f"Open-Meteo forecast for {SPOT_NAME}.\\n"
            f"Average wind: {avg_wind:.1f} kt ({compass(avg_dir)} / {avg_dir:.0f}°).\\n"
            f"Max gusts: {max_gust:.1f} kt.\\n"
            f"Max wave: {max_wave:.1f} m, period ~{avg_period:.0f} s.\\n"
            f"Criteria: wind ≥ {MIN_WIND_KT:g} kt, gusts ≤ {MAX_GUST_KT:g} kt, waves ≤ {MAX_WAVE_M:g} m, sectors {WIND_SECTORS}."
        )
        uid = f"tarifa-{start.strftime('%Y%m%dT%H%M')}-{slug.lower()}@tarifa-wind-ical"
        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{fmt_dt(now)}",
            f"DTSTART:{fmt_dt(start)}",
            f"DTEND:{fmt_dt(end)}",
            f"SUMMARY:{ical_escape(title)}",
            f"DESCRIPTION:{ical_escape(desc)}",
            f"LOCATION:{ical_escape(SPOT_NAME)}",
            "END:VEVENT",
        ]
        lines.extend(event_lines)
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_ical_line(line) for line in lines) + "\r\n"


def main() -> None:
    weather = fetch_forecast()
    marine = fetch_marine()
    hours = merge_hours(weather, marine)
    blocks = build_blocks(hours)
    calendar = make_calendar(blocks)
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        f.write(calendar)
    print(f"Wrote {OUTPUT_FILE} with {len(blocks)} forecast events")


if __name__ == "__main__":
    main()
