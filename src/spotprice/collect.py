"""Collect spot prices and forecasts to the SQLite database.

Run periodically (e.g. every 15 minutes). Only missing data is fetched.
"""
import argparse
import datetime as dt
import logging
import sys
from zoneinfo import ZoneInfo

import requests

from spotprice import config as config_mod
from spotprice.db import Database
from spotprice.sources import entsoe, npf, spothinta

LOG = logging.getLogger("spotprice.collect")
UTC = dt.timezone.utc


def local_midnight(day, tz):
    return dt.datetime.combine(day, dt.time(0), tzinfo=tz)


def target_end(now, tz, publish_after):
    """End of the period that should have confirmed prices at `now`."""
    local = now.astimezone(tz)
    days = 2 if local.time() >= publish_after else 1
    return local_midnight(local.date() + dt.timedelta(days=days), tz)


def collect_prices(cfg, db, now, session, backfill_days=None):
    """Fetch missing prices. Returns a list of error messages."""
    tz = ZoneInfo(cfg["timezone"])
    pcfg = cfg["prices"]
    end = target_end(now, tz, config_mod.parse_hhmm(pcfg["publish_after"]))
    days = pcfg["backfill_days"] if backfill_days is None else backfill_days
    earliest = local_midnight(now.astimezone(tz).date() - dt.timedelta(days=days), tz)
    errors = []
    fetched_at = int(now.timestamp())

    use_entsoe = pcfg["entsoe"]["enabled"] and pcfg["entsoe"]["token"]
    if use_entsoe:
        have = db.prices_end(entsoe.SOURCE)
        if backfill_days is not None or have is None:
            start = earliest
        else:
            # refetch from the start of the last stored day
            start = local_midnight(dt.datetime.fromtimestamp(have, tz).date(), tz)
            if have >= end.timestamp():
                start = None
        if start is not None:
            try:
                rows = entsoe.fetch(cfg, start, end, session=session)
                n = db.store_prices(rows, entsoe.SOURCE, fetched_at)
                LOG.info("ENTSO-E: %d rows received, %d stored", len(rows), n)
            except (requests.RequestException, entsoe.EntsoeError) as err:
                errors.append(f"ENTSO-E: {err}")
                LOG.warning("ENTSO-E failed: %s", err)
    elif pcfg["entsoe"]["enabled"]:
        LOG.warning("ENTSO-E enabled but no token configured, using the fallback only")

    have = db.prices_end()
    if pcfg["spothinta"]["enabled"] and (have is None or have < end.timestamp()):
        try:
            rows = spothinta.fetch(cfg, session=session)
            n = db.store_prices(rows, spothinta.SOURCE, fetched_at)
            LOG.info("spot-hinta.fi: %d rows received, %d stored", len(rows), n)
        except (requests.RequestException, ValueError, KeyError) as err:
            errors.append(f"spot-hinta.fi: {err}")
            LOG.warning("spot-hinta.fi failed: %s", err)

    have = db.prices_end()
    if have is None or have < end.timestamp():
        LOG.info("Prices available until %s, expecting %s",
                 None if have is None else dt.datetime.fromtimestamp(have, tz), end)
    return errors


def collect_forecasts(cfg, db, now, session):
    """Fetch the forecast and store it as a new run if it has changed."""
    fcfg = cfg["forecasts"]["nordpool_predict_fi"]
    if not fcfg["enabled"]:
        return []
    etag_key = f"etag:{npf.SOURCE}"
    try:
        rows, etag = npf.fetch(cfg, etag=db.get_meta(etag_key), session=session)
    except (requests.RequestException, ValueError, TypeError) as err:
        LOG.warning("nordpool-predict-fi failed: %s", err)
        return [f"nordpool-predict-fi: {err}"]
    if rows is None:
        return []
    if etag:
        db.set_meta(etag_key, etag)
    run_id = db.store_forecast_run(npf.SOURCE, int(now.timestamp()), npf.content_hash(rows), rows)
    if run_id is None:
        LOG.info("nordpool-predict-fi: no new run")
    else:
        LOG.info("nordpool-predict-fi: stored run %d with %d values", run_id, len(rows))
    return []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--config", help="configuration YAML file")
    parser.add_argument("--only", choices=["prices", "forecasts"], help="collect only one kind of data")
    parser.add_argument("--backfill", type=int, metavar="DAYS",
                        help="refetch ENTSO-E prices for this many past days")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = config_mod.load(args.config)
    now = dt.datetime.now(UTC)
    errors = []
    with Database(cfg["database"]) as db, requests.Session() as session:
        if args.only in (None, "prices"):
            errors += collect_prices(cfg, db, now, session, backfill_days=args.backfill)
        if args.only in (None, "forecasts"):
            errors += collect_forecasts(cfg, db, now, session)
    for err in errors:
        print(err, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
