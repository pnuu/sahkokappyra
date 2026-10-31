import datetime as dt
from pathlib import Path

import pytest

from spotprice.sources import entsoe, npf, spothinta

DATA = Path(__file__).parent / "data"
T0 = int(dt.datetime(2026, 10, 29, 22, tzinfo=dt.timezone.utc).timestamp())


def test_entsoe_parse_fills_omitted_points():
    rows = entsoe.parse((DATA / "entsoe_a44.xml").read_text())
    assert rows == [(T0, 15, 41.5), (T0 + 900, 15, 41.5), (T0 + 1800, 15, -1.25), (T0 + 2700, 15, 30.0)]


def test_entsoe_no_data_acknowledgement():
    xml = """<?xml version="1.0"?>
    <Acknowledgement_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-1:acknowledgementdocument:7:0">
      <Reason><code>999</code><text>No matching data found for Data item Day-ahead Prices</text></Reason>
    </Acknowledgement_MarketDocument>"""
    assert entsoe.parse(xml) == []


def test_entsoe_error_acknowledgement():
    xml = """<?xml version="1.0"?>
    <Acknowledgement_MarketDocument xmlns="urn:x">
      <Reason><code>999</code><text>Unauthorized</text></Reason>
    </Acknowledgement_MarketDocument>"""
    with pytest.raises(entsoe.EntsoeError):
        entsoe.parse(xml)


def test_entsoe_fetch_requires_token():
    cfg = {"prices": {"entsoe": {"token": ""}}}
    with pytest.raises(entsoe.EntsoeError):
        entsoe.fetch(cfg, None, None)


def test_spothinta_parse():
    items = [
        {"Rank": 2, "DateTime": "2026-10-30T00:15:00+02:00", "PriceNoTax": 0.01, "PriceWithTax": 0.01255},
        {"Rank": 1, "DateTime": "2026-10-30T00:00:00+02:00", "PriceNoTax": -0.0012, "PriceWithTax": -0.0012},
    ]
    assert spothinta.parse(items) == [(T0, 15, -1.2), (T0 + 900, 15, 10.0)]


def test_npf_parse_removes_vat_from_positive_prices():
    rows = npf.parse([[T0 * 1000.0, 12.55], [(T0 + 3600) * 1000.0, -0.5], [(T0 + 7200) * 1000.0, None]], 0.255)
    assert rows == [(T0, 60, 100.0), (T0 + 3600, 60, -5.0)]


def test_npf_content_hash_changes_with_content():
    assert npf.content_hash([(1, 60, 1.0)]) != npf.content_hash([(1, 60, 2.0)])
