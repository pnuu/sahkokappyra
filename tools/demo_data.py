"""Fill a database with simulated prices and forecast runs for testing the web page.

    python tools/demo_data.py demo.sqlite
    spotprice-export -c config.yaml   # with database: demo.sqlite
"""
import argparse
import datetime as dt
import math
import random
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spotprice.collect import local_midnight  # noqa: E402
from spotprice.db import Database  # noqa: E402
from spotprice.sources import npf  # noqa: E402

HEL = ZoneInfo("Europe/Helsinki")
UTC = dt.timezone.utc


def profile(hour):
    return (0.55 + 0.55 * math.exp(-((hour - 8.5) ** 2) / 3.0) + 0.75 * math.exp(-((hour - 18.5) ** 2) / 4.0)
            - 0.25 * math.exp(-((hour - 3.5) ** 2) / 4.0))


def truth(start, end, rng):
    """Simulated 15 min prices in EUR/MWh (VAT 0) for start <= t < end."""
    levels = {}
    out = {}
    ar = 0.0
    t = start
    while t < end:
        loc = dt.datetime.fromtimestamp(t, HEL)
        day = loc.date()
        if day not in levels:
            levels[day] = rng.choice([8, 15, 25, 40, 60, 90, 150])
        ar = 0.92 * ar + rng.gauss(0, 0.09)
        price = levels[day] * profile(loc.hour + loc.minute / 60) * (1 + ar)
        if loc.weekday() == 6 and loc.hour < 6 and levels[day] <= 15:
            price -= 12
        out[t] = round(price + (loc.minute / 15 - 1.5) * 0.04 * levels[day], 2)
        t += 900
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("database")
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument("--no-tomorrow", action="store_true", help="simulate the time before the day-ahead result")
    args = parser.parse_args(argv)
    rng = random.Random(args.seed)
    now = dt.datetime.now(UTC)
    today = now.astimezone(HEL).date()
    start = int(local_midnight(today - dt.timedelta(days=40), HEL).timestamp())
    end = int(local_midnight(today + dt.timedelta(days=10), HEL).timestamp())
    prices = truth(start, end, rng)
    confirmed_end = int(local_midnight(today + dt.timedelta(days=1 if args.no_tomorrow else 2), HEL).timestamp())

    with Database(args.database) as db:
        db.store_prices([(t, 15, p) for t, p in prices.items() if t < confirmed_end], "entsoe", int(now.timestamp()))
        # forecast runs at 01, 07, 10, 13 and 19 UTC
        n = 0
        for day in range(35, -1, -1):
            for hour in (1, 7, 10, 13, 19):
                issued = dt.datetime.combine(now.date() - dt.timedelta(days=day), dt.time(hour, 3), tzinfo=UTC)
                if issued > now:
                    continue
                its = int(issued.timestamp())
                rows = []
                bias = rng.gauss(0, 0.12)
                for t in range(its - its % 3600 - 2 * 86400, its + 7 * 86400, 3600):
                    q = [prices.get(t + k * 900) for k in range(4)]
                    if None in q:
                        continue
                    lead = max(0, t - its) / 86400
                    err = rng.gauss(0, 0.06 + 0.05 * lead)
                    rows.append((t, 60, round(sum(q) / 4 * (1 + bias * min(lead, 2) + err), 2)))
                if db.store_forecast_run(npf.SOURCE, its, npf.content_hash(rows), rows):
                    n += 1
    print(f"Stored {len(prices)} prices and {n} forecast runs to {args.database}")


if __name__ == "__main__":
    main()
