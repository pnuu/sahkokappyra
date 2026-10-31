# spotprice – Finnish spot electricity prices

Two parts:

1. **Python collector** (`spotprice-collect`) stores day-ahead prices and price
   forecasts in SQLite. **Exporter** (`spotprice-export`) writes the shown period
   to one static JSON file.
2. **Static web page** (`web/`) reads only that JSON. The web server never needs
   access to the database.

```
spotprice-collect ─▶ SQLite ─▶ spotprice-export ─▶ spot.json ─▶ web server (web/)
```

## Data sources

| Data | Source | Notes |
|---|---|---|
| Confirmed day-ahead prices | [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/) | Needs a free API token. 15 min resolution since 1.10.2025. |
| Fallback | [spot-hinta.fi](https://spot-hinta.fi/) | No key. Today and tomorrow only. Used when ENTSO-E is not configured, fails or is late. ENTSO-E data replaces it when available. |
| Forecast | [nordpool-predict-fi](https://github.com/vividfog/nordpool-predict-fi) (Sähkövatkain, MIT) | Hourly, ~7 days, updated several times a day. Every changed version is stored as a forecast run. |

No free once-a-day price forecast was found, so the *daily forecast* is the
first nordpool-predict-fi run seen after `daily_run_after_utc` (default 09:30
UTC, i.e. before the day-ahead auction) each day. The *rapid forecast* is the
latest run. Until the next day's daily run exists they can be the same run, in
which case the page only shows the rapid one.

The uncertainty band is computed from the archived runs: quantiles (default
10 % / 90 %) of the forecast error per 24 h lead time. It appears once there is
enough history (`min_samples`).

All prices are stored as EUR/MWh without VAT and times as UTC. The 1 h price
is the mean of the four 15 min prices.

## Installation

```sh
python3 -m venv /opt/spotprice/venv
/opt/spotprice/venv/bin/pip install .
cp config.example.yaml /etc/spotprice/config.yaml   # and edit
```

Python 3.11+ with `requests` and `PyYAML`. Run the tests with
`pip install .[test] && pytest`.

## Configuration

See [`config.example.yaml`](config.example.yaml). The essentials:

- `database`: SQLite file (relative paths are relative to the config file)
- `prices.entsoe.token`: ENTSO-E token, or the `ENTSOE_TOKEN` environment variable
- `export.output`: where the JSON goes, e.g. the web server's `data/spot.json`
- `export.days_back`, `export.forecast_days`: shown period

## Running

```sh
spotprice-collect -c config.yaml -v      # fetch what is missing
spotprice-export  -c config.yaml -v      # write the JSON
spotprice-collect -c config.yaml --backfill 30   # refetch 30 days from ENTSO-E
```

The collector is idempotent: prices are fetched only when they are missing, and
the forecast file is requested with `If-None-Match`, so running it often is cheap.

### Suggested polling

- Every 15 minutes in general. This catches each forecast update
  (seen at roughly 01, 07–08, 10, 13 and 19 UTC).
- Every 5 minutes between 13:40 and 15:00 Finnish time, when the day-ahead
  result is published (usually around 13:45–14:00, sometimes later).
- Run the exporter after every collection, even if a source failed.

Examples: [`deploy/spotprice.service`](deploy/spotprice.service) +
[`deploy/spotprice.timer`](deploy/spotprice.timer), or
[`deploy/crontab.example`](deploy/crontab.example).

## Web page

Copy `web/` to the web server and make the exporter write to
`<web root>/data/spot.json`. Everything is static, and ECharts is vendored in
`web/vendor/` (5.6.0, Apache-2.0), so no CDN is needed.

- The page shows only what is in the JSON. Missing resolutions, forecasts,
  the band and earlier runs hide their controls, and the view starts from the
  first day with prices.
- Price level limits are in `LIMITS` at the top of [`web/app.js`](web/app.js)
  (c/kWh, applied to the spot price with VAT when VAT is on).
- Settings are stored in a cookie only when they differ from the defaults.
- The data is reloaded every 5 minutes.

### JSON format (version 1)

```jsonc
{
  "version": 1,
  "generated_at": 1793400308000,           // all times: UTC epoch milliseconds
  "timezone": "Europe/Helsinki",
  "unit": "EUR/MWh", "vat_included": false,
  "window": {"start": ..., "end": ...},    // shown period
  "confirmed_until": ...,                  // end of the last confirmed price
  "prices": {"15": [[t, price], ...], "60": [[t, price], ...]},   // only present resolutions
  "forecasts": {                           // only present kinds
    "rapid": {"source": "...", "issued_at": t, "resolution": 60, "values": [[t, price, low, high], ...]},
    "daily": {...}                         // low/high only when the band exists
  },
  "earlier_forecasts": [{"source": "...", "issued_at": t, "resolution": 60, "values": [[t, price], ...]}],
  "sources": {"prices": ["entsoe"], "forecasts": ["nordpool-predict-fi"]}
}
```

## Demo data

```sh
python tools/demo_data.py /tmp/demo.sqlite
printf 'database: /tmp/demo.sqlite\nexport:\n  output: %s/web/data/spot.json\n' "$PWD" > /tmp/demo.yaml
PYTHONPATH=src python -m spotprice.export -c /tmp/demo.yaml
cd web && python -m http.server 8000
```
