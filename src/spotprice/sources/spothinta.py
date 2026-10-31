"""spot-hinta.fi API: today's and tomorrow's prices (fallback source)."""
import datetime as dt
import logging

import requests

LOG = logging.getLogger(__name__)
SOURCE = "spot-hinta.fi"


def parse(items):
    """Parse the JSON list to sorted (ts, resolution_min, eur_mwh) rows."""
    times = sorted(dt.datetime.fromisoformat(item["DateTime"]) for item in items)
    if len(times) > 1:
        resolution = int(min(b - a for a, b in zip(times, times[1:])).total_seconds() // 60)
    else:
        resolution = 15
    rows = []
    for item in items:
        ts = int(dt.datetime.fromisoformat(item["DateTime"]).timestamp())
        rows.append((ts, resolution, round(item["PriceNoTax"] * 1000, 3)))  # EUR/kWh -> EUR/MWh
    return sorted(rows)


def fetch(cfg, session=None):
    scfg = cfg["prices"]["spothinta"]
    session = session or requests.Session()
    LOG.info("spot-hinta.fi: fetching %s", scfg["url"])
    resp = session.get(scfg["url"], timeout=cfg["http"]["timeout"],
                       headers={"User-Agent": cfg["http"]["user_agent"]})
    resp.raise_for_status()
    return parse(resp.json())
