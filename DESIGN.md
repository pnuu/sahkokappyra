# Finnish spot price page – design decisions

Status: implemented (see README.md). Mockups in `mockups/` (regenerate with `python mockups/render.py mockups`);
chosen direction: G1/G4 (traffic-light colours, bars + lines), G5 heatmap, G6 total price, O1/O2 settings.
Screenshots of the implementation from simulated data in `mockups/screenshots/`.

## Architecture

```
collector (python, cron/systemd)  ->  sqlite (private)  ->  export script  ->  static JSON  ->  web server (static HTML+JS)
```

- Web server only receives the exported JSON (and the static page). It never sees the database.
- Python 3.11+, `requests`, stdlib `sqlite3` / `xml.etree` / `zoneinfo`; `pyproject.toml`, pytest, TOML config.
- Times stored in UTC, displayed in Europe/Helsinki (23 h / 25 h DST days handled).

## Data

| What | Source | Notes |
|---|---|---|
| Confirmed day-ahead prices | ENTSO-E Transparency API (token) | 15 min since 1.10.2025, hourly before |
| Fallback for confirmed prices | spot-hinta.fi (no key) | used if ENTSO-E fails / is late |
| Rapid forecast | nordpool-predict-fi `deploy/prediction.json` (MIT) | hourly, c/kWh **incl. VAT 25.5 %**, ~7–9 days; updated ~5×/day (seen ~01, 07–08, 10, 13, 19 UTC) |
| Once-a-day forecast | none found as a free feed | first nordpool-predict-fi run after 09:30 UTC each day |

- 1 h price = mean of the four 15 min prices.
- Every forecast run is archived with its issue time (for the "earlier forecasts" toggle).
- All history kept; page shows 7 days back + forecast 1–2 days beyond the last confirmed price.

## Presentation

- Units c/kWh; VAT toggle (25.5 %, default on; no VAT on negative prices).
- Fixed level limits in one constant (`LIMITS` in `web/app.js`, c/kWh): `< 0` negative, `0–5` low, `5–10` average,
  `10–20` high, `20–30` very high, `> 30` extreme. Applied to the spot price as displayed (VAT per toggle),
  never to margin/fees.
- Tiles: price now, today min/avg/max, tomorrow average, cheapest 3 h (tomorrow, or rest of today), most
  expensive 3 h of the forecast. The two 3 h windows are also boxed in the chart.
- Fees are entered including VAT, as on the bill. A monthly basic fee was left out (it has no per-kWh effect).
- Confirmed prices as bars + line, forecasts as lines (+ uncertainty band). Earlier forecasts in lighter tones.
- ECharts (vendored). Languages FI (default) / EN.
- Optional contract margin and day/night transfer fees (with hours).
- Settings in a cookie, written only when they differ from the defaults.

## Polling (documentation only)

Every 15 min, or more often between 13:45 and 15:00 Finnish time when the day-ahead result is published.
The collector is idempotent and only fetches what's missing.
