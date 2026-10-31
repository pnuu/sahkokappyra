import datetime as dt
import json
from zoneinfo import ZoneInfo

import pytest

from spotprice import config, export
from spotprice.db import Database
from spotprice.sources import npf

HEL = ZoneInfo("Europe/Helsinki")
NOW = dt.datetime(2026, 10, 30, 15, 20, tzinfo=HEL)


def ts(*args):
    return int(dt.datetime(*args, tzinfo=HEL).timestamp())


@pytest.fixture
def cfg(tmp_path):
    c = config.load()
    c["database"] = str(tmp_path / "db.sqlite")
    c["export"]["band"]["min_samples"] = 5
    return c


@pytest.fixture
def db(cfg):
    with Database(cfg["database"]) as database:
        yield database


def fill_prices(db, start, end, price=lambda t: 40.0):
    rows = [(t, 15, price(t)) for t in range(start, end, 900)]
    db.store_prices(rows, "entsoe", 0)


def test_hourly_from_quarters_needs_complete_hours():
    quarters = {0: 1.0, 900: 2.0, 1800: 3.0, 2700: 6.0, 3600: 1.0}
    assert export.hourly_from_quarters(quarters) == {0: 3.0}


def test_quantile():
    assert export.quantile([3, 1, 2], 0.5) == 2
    assert export.quantile([0, 10], 0.1) == pytest.approx(1)


def test_daily_runs_picks_first_run_after_time():
    utc = dt.timezone.utc
    t = lambda d, h: int(dt.datetime(2026, 10, d, h, tzinfo=utc).timestamp())
    runs = [(1, t(28, 7)), (2, t(28, 10)), (3, t(28, 13)), (4, t(29, 1)), (5, t(29, 13))]
    assert export.daily_runs(runs, dt.time(9, 30)) == [(2, t(28, 10)), (5, t(29, 13))]


def test_build_window_and_prices(cfg, db):
    fill_prices(db, ts(2026, 10, 20), ts(2026, 11, 1), price=lambda t: (t // 900) % 4 * 10.0)
    out = export.build(cfg, db, NOW)
    assert out["window"]["start"] == ts(2026, 10, 23) * 1000
    # confirmed until end of tomorrow, forecast 2 more days
    assert out["confirmed_until"] == ts(2026, 11, 1) * 1000
    assert out["window"]["end"] == ts(2026, 11, 3) * 1000
    assert out["prices"]["15"][0] == [ts(2026, 10, 23) * 1000, 0.0]
    # hourly = mean of the quarters (0, 10, 20, 30)
    assert all(v == 15.0 for _, v in out["prices"]["60"])
    # 7 days back + today + tomorrow, one of them 25 h long (DST change 25.10.)
    assert len(out["prices"]["60"]) == 9 * 24 + 1
    assert out["forecasts"] == {}
    assert out["earlier_forecasts"] == []
    json.dumps(out)


def test_build_forecasts(cfg, db):
    fill_prices(db, ts(2026, 10, 20), ts(2026, 11, 1))
    # one run per day at 12 UTC predicting 4 days ahead, always 10 EUR/MWh too low
    for day in range(23, 31):
        issued = int(dt.datetime(2026, 10, day, 12, tzinfo=dt.timezone.utc).timestamp())
        rows = [(t, 60, 30.0) for t in range(issued - issued % 3600, issued + 4 * 86400, 3600)]
        db.store_forecast_run(npf.SOURCE, issued, f"h{day}", rows)
    out = export.build(cfg, db, NOW)
    rapid = out["forecasts"]["rapid"]
    assert rapid["values"][0][0] == ts(2026, 11, 1) * 1000
    assert rapid["values"][-1][0] < out["window"]["end"]
    # band from the archived errors: actual 40 - forecast 30 = +10
    t, value, lo, hi = rapid["values"][0]
    assert (value, lo, hi) == (30.0, 40.0, 40.0)
    assert out["forecasts"]["daily"]["issued_at"] == rapid["issued_at"]
    assert out["earlier_forecasts"]
    for entry in out["earlier_forecasts"]:
        assert entry["values"][0][0] >= entry["issued_at"] - 3600 * 1000
        assert len(entry["values"][0]) == 2
    assert out["sources"]["forecasts"] == [npf.SOURCE]


def test_write_atomic(tmp_path):
    path = tmp_path / "sub" / "spot.json"
    export.write_atomic({"a": 1}, path)
    assert json.loads(path.read_text()) == {"a": 1}
