"""Export the shown period from the database to a static JSON file for the web page."""
import argparse
import datetime as dt
import json
import logging
import os
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

from spotprice import config as config_mod
from spotprice.collect import local_midnight
from spotprice.db import Database
from spotprice.sources import npf

LOG = logging.getLogger("spotprice.export")
UTC = dt.timezone.utc
FORMAT_VERSION = 1


def hourly_from_quarters(quarters):
    """Hourly means of {ts: price} 15 min prices. Only complete hours are returned."""
    groups = defaultdict(list)
    for ts, price in quarters.items():
        groups[ts - ts % 3600].append(price)
    return {ts: sum(v) / 4 for ts, v in groups.items() if len(v) == 4}


def quantile(values, q):
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def daily_runs(runs, after):
    """Pick the first run issued after `after` (UTC time) on each UTC day."""
    picked = {}
    for run_id, issued in runs:
        t = dt.datetime.fromtimestamp(issued, UTC)
        if t.time() >= after and t.date() not in picked:
            picked[t.date()] = (run_id, issued)
    return [picked[d] for d in sorted(picked)]


def error_band(db, hourly, now_ts, bcfg):
    """Quantiles of (actual - forecast) per 24 h lead time bucket.

    Returns {bucket: (low, high)} for the buckets with enough samples.
    """
    since = now_ts - bcfg["history_days"] * 86400
    errors = defaultdict(list)
    for run_id, issued in db.forecast_runs(npf.SOURCE, since=since, until=now_ts):
        for ts, _res, price in db.forecast_values(run_id, start=issued):
            if ts in hourly:
                errors[(ts - issued) // 86400].append(hourly[ts] - price)
    q_lo, q_hi = bcfg["quantiles"]
    return {bucket: (quantile(errs, q_lo), quantile(errs, q_hi))
            for bucket, errs in errors.items() if len(errs) >= bcfg["min_samples"]}


def _ms(ts):
    return int(ts) * 1000


def _r(value):
    return None if value is None else round(value, 2)


def forecast_entry(db, run_id, issued, start, end, band=None):
    values = []
    for ts, _res, price in db.forecast_values(run_id, start=start, end=end):
        if ts < issued - issued % 3600:
            continue  # values before the issue time are not forecasts
        item = [_ms(ts), _r(price)]
        if band is not None:
            lo_hi = band.get(max(0, ts - issued) // 86400)
            if lo_hi is not None:
                item += [_r(price + lo_hi[0]), _r(price + lo_hi[1])]
        values.append(item)
    if not values:
        return None
    return {"source": npf.SOURCE, "issued_at": _ms(issued), "resolution": 60, "values": values}


def build(cfg, db, now):
    tz = ZoneInfo(cfg["timezone"])
    ecfg = cfg["export"]
    now_ts = int(now.timestamp())
    today = now.astimezone(tz).date()
    start = local_midnight(today - dt.timedelta(days=ecfg["days_back"]), tz)
    start_ts = int(start.timestamp())

    # all prices from the start of the window (the band needs history too)
    band_cfg = ecfg["band"]
    hist_start = min(start_ts, now_ts - band_cfg["history_days"] * 86400)
    quarters, native_hours = {}, {}
    for ts, res, price in db.prices(hist_start, now_ts + 7 * 86400):
        if res == 15:
            quarters[ts] = price
        elif res == 60:
            native_hours[ts] = price
    hourly = dict(native_hours)
    hourly.update(hourly_from_quarters(quarters))  # 1 h price = mean of the four 15 min prices

    ends = [ts + 900 for ts in quarters] + [ts + 3600 for ts in hourly]
    confirmed_until = max(ends) if ends else None

    last_day = dt.datetime.fromtimestamp((confirmed_until or now_ts) - 1, tz).date()
    fc_end = local_midnight(last_day + dt.timedelta(days=1 + ecfg["forecast_days"]), tz)
    fc_end_ts = int(fc_end.timestamp())

    out = {
        "version": FORMAT_VERSION,
        "generated_at": _ms(now_ts),
        "timezone": cfg["timezone"],
        "unit": "EUR/MWh",
        "vat_included": False,
        "window": {"start": _ms(start_ts), "end": _ms(fc_end_ts)},
        "confirmed_until": None if confirmed_until is None else _ms(confirmed_until),
        "prices": {},
        "forecasts": {},
        "earlier_forecasts": [],
        "sources": {"prices": db.sources(start_ts, fc_end_ts), "forecasts": []},
    }
    for key, series in (("15", quarters), ("60", hourly)):
        values = [[_ms(ts), _r(series[ts])] for ts in sorted(series) if ts >= start_ts]
        if values:
            out["prices"][key] = values

    fcfg = cfg["forecasts"]["nordpool_predict_fi"]
    if fcfg["enabled"]:
        runs = db.forecast_runs(npf.SOURCE, until=now_ts + 1)
        band = error_band(db, hourly, now_ts, band_cfg) if band_cfg["enabled"] else None
        fc_start = confirmed_until or now_ts
        if runs:
            entry = forecast_entry(db, *runs[-1], fc_start, fc_end_ts, band)
            if entry:
                out["forecasts"]["rapid"] = entry
        dailies = daily_runs(runs, config_mod.parse_hhmm(fcfg["daily_run_after_utc"]))
        if dailies:
            entry = forecast_entry(db, *dailies[-1], fc_start, fc_end_ts, band)
            if entry:
                out["forecasts"]["daily"] = entry
        efcfg = ecfg["earlier_forecasts"]
        if efcfg["enabled"]:
            horizon = efcfg["horizon_hours"] * 3600
            for run_id, issued in dailies[:-1]:
                if issued + horizon <= start_ts:
                    continue
                entry = forecast_entry(db, run_id, issued, max(start_ts, issued),
                                       min(fc_end_ts, issued + horizon))
                if entry:
                    out["earlier_forecasts"].append(entry)
        if out["forecasts"] or out["earlier_forecasts"]:
            out["sources"]["forecasts"].append(npf.SOURCE)
    return out


def write_atomic(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".spot-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fid:
            json.dump(data, fid, separators=(",", ":"))
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", help="configuration YAML file")
    parser.add_argument("-o", "--output", help="output JSON file (overrides the configuration)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = config_mod.load(args.config)
    output = args.output or cfg["export"]["output"]
    with Database(cfg["database"]) as db:
        data = build(cfg, db, dt.datetime.now(UTC))
    write_atomic(data, output)
    LOG.info("Wrote %s", output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
