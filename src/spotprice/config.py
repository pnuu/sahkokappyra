"""Configuration loading."""
import copy
import datetime as dt
import os
from pathlib import Path

import yaml

DEFAULTS = {
    "database": "spotprice.sqlite",
    "timezone": "Europe/Helsinki",
    "http": {"timeout": 30, "user_agent": "spotprice-collector/0.1"},
    "prices": {
        "publish_after": "13:30",
        "backfill_days": 14,
        "entsoe": {"enabled": True, "token": "", "url": "https://web-api.tp.entsoe.eu/api",
                   "area": "10YFI-1--------U"},
        "spothinta": {"enabled": True, "url": "https://api.spot-hinta.fi/TodayAndDayForward"},
    },
    "forecasts": {
        "nordpool_predict_fi": {
            "enabled": True,
            "url": "https://raw.githubusercontent.com/vividfog/nordpool-predict-fi/main/deploy/prediction.json",
            "vat_rate": 0.255,
            "daily_run_after_utc": "09:30",
        },
    },
    "export": {
        "output": "web/data/spot.json",
        "days_back": 7,
        "forecast_days": 2,
        "earlier_forecasts": {"enabled": True, "horizon_hours": 48},
        "band": {"enabled": True, "history_days": 30, "quantiles": [0.1, 0.9], "min_samples": 48},
    },
}


def _merge(base, override):
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def parse_hhmm(value):
    """Parse "HH:MM" to a datetime.time."""
    hour, minute = str(value).split(":")
    return dt.time(int(hour), int(minute))


def load(path=None):
    """Load the YAML config, fill in defaults and resolve relative paths."""
    raw = {}
    base_dir = Path.cwd()
    if path is not None:
        path = Path(path)
        with path.open(encoding="utf-8") as fid:
            raw = yaml.safe_load(fid) or {}
        base_dir = path.resolve().parent
    cfg = _merge(DEFAULTS, raw)
    cfg["database"] = str(base_dir / cfg["database"])
    cfg["export"]["output"] = str(base_dir / cfg["export"]["output"])
    token = os.environ.get("ENTSOE_TOKEN")
    if token:
        cfg["prices"]["entsoe"]["token"] = token
    return cfg
