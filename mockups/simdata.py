"""Simulated Finnish spot price data for the mockups."""
import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np

HEL = ZoneInfo("Europe/Helsinki")
UTC = dt.timezone.utc
VAT = 1.255

NOW = dt.datetime(2026, 10, 30, 15, 20, tzinfo=HEL)
START = dt.datetime(2026, 10, 24, 0, 0, tzinfo=HEL)      # 7 days back (contains DST change 25.10.)
CONFIRMED_END = dt.datetime(2026, 11, 1, 0, 0, tzinfo=HEL)  # tomorrow confirmed (day-ahead published)
FC_END = dt.datetime(2026, 11, 3, 0, 0, tzinfo=HEL)        # forecast 2 days beyond confirmed

# Fixed limits, c/kWh incl. VAT (easily adjustable in the code)
LIMITS = [0, 5, 10, 20, 30]
LEVELS = ["negatiivinen", "edullinen", "keskitaso", "kallis", "erittäin kallis", "äärimmäinen"]
LEVEL_LABELS = ["< 0", "0–5", "5–10", "10–20", "20–30", "> 30"]

# Validated (light mode) palettes
TRAFFIC = ["#2a78d6", "#16a061", "#d9a800", "#e8603c", "#b8213b", "#6a2c91"]
ORDINAL = ["#2a78d6", "#eca46a", "#de7c3c", "#c4561f", "#963a14", "#5f230b"]


def level(p):
    return int(np.searchsorted(LIMITS, p, side="right"))


def utc_range(start, end, minutes):
    t, out = start.astimezone(UTC), []
    end = end.astimezone(UTC)
    while t < end:
        out.append(t)
        t += dt.timedelta(minutes=minutes)
    return out


def _profile(local_hour):
    h = local_hour
    return (0.55 + 0.55 * np.exp(-((h - 8.5) ** 2) / 3.0) + 0.75 * np.exp(-((h - 18.5) ** 2) / 4.0)
            - 0.25 * np.exp(-((h - 3.5) ** 2) / 4.0))


DAY_LEVEL = {  # VAT0 c/kWh daily scale (wind-driven)
    "2026-10-24": 3.0, "2026-10-25": 0.9, "2026-10-26": 4.5, "2026-10-27": 7.5,
    "2026-10-28": 11.0, "2026-10-29": 19.0, "2026-10-30": 8.0, "2026-10-31": 4.0,
    "2026-11-01": 3.2, "2026-11-02": 9.0,
}


def true_price_15(times, seed=4):
    rng = np.random.default_rng(seed)
    ar, out = 0.0, []
    for t in times:
        loc = t.astimezone(HEL)
        h = loc.hour + loc.minute / 60
        ar = 0.92 * ar + rng.normal(0, 0.09)
        base = DAY_LEVEL[loc.date().isoformat()]
        p = base * _profile(h) * (1 + ar)
        if loc.date().isoformat() == "2026-10-25" and loc.hour < 6:
            p -= 1.4  # negative prices on a windy Sunday night
        p += (loc.minute / 15 - 1.5) * 0.04 * base  # quarter-hour sawtooth
        out.append(p * VAT if p > 0 else p)  # no VAT on negative prices
    return np.array(out)


def hourly_mean(times15, p15):
    """1 h price = mean of the four 15 min prices."""
    times = times15[::4]
    return times, p15.reshape(-1, 4).mean(axis=1)


def forecast(times, truth, lead_hours, seed, bias=0.0):
    rng = np.random.default_rng(seed)
    err = rng.normal(0, 1, len(times)).cumsum() * 0.03
    sigma = 0.08 + 0.006 * np.asarray(lead_hours)
    fc = truth * (1 + bias + err + rng.normal(0, 0.05, len(times)))
    s = np.convolve(fc, np.ones(5) / 5, mode="same")
    return fc, s * (1 - sigma * 1.6), s * (1 + sigma * 2.2)


def build():
    t15 = utc_range(START, FC_END, 15)
    p15 = true_price_15(t15)
    t1, p1 = hourly_mean(t15, p15)
    conf15 = np.array([t < CONFIRMED_END.astimezone(UTC) for t in t15])
    conf1 = np.array([t < CONFIRMED_END.astimezone(UTC) for t in t1])
    fct = [t for t in t1 if t >= CONFIRMED_END.astimezone(UTC)]
    truth_fc = p1[~conf1]
    lead = [(t - NOW.astimezone(UTC)).total_seconds() / 3600 for t in fct]
    rapid = forecast(fct, truth_fc, lead, seed=11)
    daily = forecast(fct, truth_fc, [x + 6 for x in lead], seed=23, bias=0.07)
    # earlier forecast runs covering the shown period (for the "earlier forecasts" toggle)
    earlier = []
    for k, issued in enumerate([dt.datetime(2026, 10, 26, 10, tzinfo=HEL), dt.datetime(2026, 10, 27, 22, tzinfo=HEL),
                                dt.datetime(2026, 10, 29, 4, tzinfo=HEL)]):
        lo = issued + dt.timedelta(hours=10)
        hi = issued + dt.timedelta(hours=58)
        idx = [i for i, t in enumerate(t1) if lo.astimezone(UTC) <= t < hi.astimezone(UTC)]
        tt = [t1[i] for i in idx]
        ld = [(t - issued.astimezone(UTC)).total_seconds() / 3600 for t in tt]
        f, _, _ = forecast(tt, p1[idx], ld, seed=40 + k, bias=[-0.12, 0.15, -0.2][k])
        earlier.append((issued, tt, f))
    return dict(t15=t15, p15=p15, conf15=conf15, t1=t1, p1=p1, conf1=conf1,
                fct=fct, rapid=rapid, daily=daily, earlier=earlier)
