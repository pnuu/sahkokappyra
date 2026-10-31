"""ENTSO-E Transparency Platform day-ahead prices (document type A44)."""
import datetime as dt
import logging
import re
import xml.etree.ElementTree as ET

import requests

LOG = logging.getLogger(__name__)
SOURCE = "entsoe"
UTC = dt.timezone.utc


class EntsoeError(RuntimeError):
    pass


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _children(elem, name):
    return [c for c in elem if _local(c.tag) == name]


def _child(elem, name):
    for c in elem:
        if _local(c.tag) == name:
            return c
    return None


def _parse_time(value):
    return dt.datetime.strptime(value, "%Y-%m-%dT%H:%MZ").replace(tzinfo=UTC)


def _parse_resolution(value):
    match = re.fullmatch(r"PT(\d+)M", value)
    if not match:
        raise EntsoeError(f"Unsupported resolution {value}")
    return int(match.group(1))


def parse(xml_text):
    """Parse an A44 document to sorted (ts, resolution_min, eur_mwh) rows.

    Points with the same price as the previous one may be left out of the
    document (curve type A03); they are filled in here.
    """
    root = ET.fromstring(xml_text)
    if _local(root.tag) == "Acknowledgement_MarketDocument":
        reason = root.find(".//{*}Reason/{*}text")
        text = reason.text if reason is not None else "unknown"
        if "No matching data" in text:
            return []
        raise EntsoeError(text)
    rows = {}
    for series in _children(root, "TimeSeries"):
        for period in _children(series, "Period"):
            interval = _child(period, "timeInterval")
            start = _parse_time(_child(interval, "start").text)
            end = _parse_time(_child(interval, "end").text)
            resolution = _parse_resolution(_child(period, "resolution").text)
            step = dt.timedelta(minutes=resolution)
            count = int((end - start) / step)
            points = {}
            for point in _children(period, "Point"):
                pos = int(_child(point, "position").text)
                points[pos] = float(_child(point, "price.amount").text)
            last = None
            for pos in range(1, count + 1):
                last = points.get(pos, last)
                if last is None:
                    continue
                ts = int((start + (pos - 1) * step).timestamp())
                rows.setdefault((ts, resolution), last)
    return sorted((ts, res, price) for (ts, res), price in rows.items())


def fetch(cfg, start, end, session=None):
    """Fetch day-ahead prices for start <= t < end (aware datetimes)."""
    ecfg = cfg["prices"]["entsoe"]
    if not ecfg.get("token"):
        raise EntsoeError("ENTSO-E token not configured")
    params = {
        "securityToken": ecfg["token"],
        "documentType": "A44",
        "in_Domain": ecfg["area"],
        "out_Domain": ecfg["area"],
        "periodStart": start.astimezone(UTC).strftime("%Y%m%d%H%M"),
        "periodEnd": end.astimezone(UTC).strftime("%Y%m%d%H%M"),
    }
    session = session or requests.Session()
    LOG.info("ENTSO-E: fetching %s - %s", params["periodStart"], params["periodEnd"])
    resp = session.get(ecfg["url"], params=params, timeout=cfg["http"]["timeout"],
                       headers={"User-Agent": cfg["http"]["user_agent"]})
    if resp.status_code not in (200, 400):
        # 400 is used for "no data" acknowledgements
        raise EntsoeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    return parse(resp.text)
