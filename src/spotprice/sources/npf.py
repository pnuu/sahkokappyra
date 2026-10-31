"""nordpool-predict-fi price forecast (https://github.com/vividfog/nordpool-predict-fi).

prediction.json is a list of [epoch_ms, c/kWh incl. VAT] pairs at hourly
resolution. The file is updated several times a day.
"""
import hashlib
import logging

import requests

LOG = logging.getLogger(__name__)
SOURCE = "nordpool-predict-fi"


def parse(items, vat_rate):
    """Parse to (ts, resolution_min, eur_mwh) rows without VAT."""
    rows = []
    for ms, value in items:
        if value is None:
            continue
        price = value * 10  # c/kWh -> EUR/MWh
        if price > 0:
            price /= 1 + vat_rate  # no VAT on negative prices
        rows.append((int(ms // 1000), 60, round(price, 3)))
    return sorted(rows)


def content_hash(rows):
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def fetch(cfg, etag=None, session=None):
    """Return (rows, etag); rows is None when the file has not changed."""
    fcfg = cfg["forecasts"]["nordpool_predict_fi"]
    session = session or requests.Session()
    headers = {"User-Agent": cfg["http"]["user_agent"]}
    if etag:
        headers["If-None-Match"] = etag
    resp = session.get(fcfg["url"], timeout=cfg["http"]["timeout"], headers=headers)
    if resp.status_code == 304:
        LOG.info("nordpool-predict-fi: not modified")
        return None, etag
    resp.raise_for_status()
    return parse(resp.json(), fcfg["vat_rate"]), resp.headers.get("ETag")
