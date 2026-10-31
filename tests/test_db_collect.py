import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from spotprice import collect, config
from spotprice.db import Database

HEL = ZoneInfo("Europe/Helsinki")


@pytest.fixture
def db(tmp_path):
    with Database(tmp_path / "test.sqlite") as database:
        yield database


def test_higher_priority_source_wins(db):
    db.store_prices([(0, 15, 1.0)], "spot-hinta.fi", 10)
    db.store_prices([(0, 15, 2.0)], "entsoe", 11)
    assert db.store_prices([(0, 15, 3.0)], "spot-hinta.fi", 12) == 0
    assert db.prices(0, 1) == [(0, 15, 2.0)]
    assert db.prices_end() == 900


def test_duplicate_forecast_run_is_ignored(db):
    rows = [(0, 60, 1.0)]
    assert db.store_forecast_run("x", 100, "hash", rows) is not None
    assert db.store_forecast_run("x", 200, "hash", rows) is None
    assert len(db.forecast_runs("x")) == 1


@pytest.mark.parametrize("local_time, days", [(dt.time(13, 0), 1), (dt.time(14, 0), 2)])
def test_target_end(local_time, days):
    now = dt.datetime.combine(dt.date(2026, 10, 30), local_time, tzinfo=HEL)
    end = collect.target_end(now, HEL, dt.time(13, 30))
    assert end == dt.datetime.combine(dt.date(2026, 10, 30) + dt.timedelta(days=days), dt.time(0), tzinfo=HEL)


def test_target_end_over_dst_change():
    now = dt.datetime(2026, 10, 24, 15, tzinfo=HEL)
    end = collect.target_end(now, HEL, dt.time(13, 30))
    assert end.utcoffset() == dt.timedelta(hours=2)
    assert end == dt.datetime(2026, 10, 26, tzinfo=HEL)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status
        self.headers = {}

    def json(self):
        return self.payload

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return FakeResponse(self.payload)


def test_collect_prices_uses_fallback_without_token(db):
    cfg = config.load()
    cfg["prices"]["entsoe"]["token"] = ""
    now = dt.datetime(2026, 10, 30, 15, tzinfo=HEL)
    start = dt.datetime(2026, 10, 30, tzinfo=HEL)
    payload = [{"DateTime": (start + dt.timedelta(minutes=15 * i)).isoformat(), "PriceNoTax": 0.05}
               for i in range(2 * 96)]
    session = FakeSession(payload)
    assert collect.collect_prices(cfg, db, now, session) == []
    assert db.prices_end() == int(dt.datetime(2026, 11, 1, tzinfo=HEL).timestamp())
    # up to date: nothing is fetched
    collect.collect_prices(cfg, db, now, session)
    assert session.calls == 1
