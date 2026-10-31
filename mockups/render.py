"""Render PNG mockups of the spot price page from simulated data."""
import datetime as dt
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.textpath import TextPath

import simdata as sd

OUT = Path(sys.argv[1])
(OUT / "graphs").mkdir(parents=True, exist_ok=True)
(OUT / "options").mkdir(parents=True, exist_ok=True)

C = dict(page="#f9f9f7", surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781",
         grid="#e1e0d9", axis="#c3c2b7", border="#dddcd5", fcshade="#f1f0ec",
         rapid="#1f5f8b", daily="#52514e", accent="#1f5f8b")
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "timezone": "Europe/Helsinki",
                     "axes.edgecolor": C["axis"], "xtick.color": C["muted"], "ytick.color": C["muted"]})
WD = ["ma", "ti", "ke", "to", "pe", "la", "su"]
D = sd.build()
UTC = dt.timezone.utc


def fmt(v, n=2):
    return f"{v:.{n}f}".replace(".", ",")


def tw(s, size=10, weight="normal"):
    """Text width in px (figure dpi 100)."""
    return TextPath((0, 0), s, size=size, prop=FontProperties(family="DejaVu Sans", weight=weight)).get_extents().width * 100 / 72


# ---------- tiny UI kit (pixel coordinates from top-left) ----------
class Canvas:
    def __init__(self, w, h, bg=C["page"]):
        self.w, self.h = w, h
        self.fig = plt.figure(figsize=(w / 100, h / 100), dpi=100, facecolor=bg)

    def _r(self, x, y, w, h):
        return x / self.w, 1 - (y + h) / self.h, w / self.w, h / self.h

    def box(self, x, y, w, h, fc=C["surface"], ec=C["border"], r=10, lw=1, z=1):
        # inches from bottom-left; rounding in inches keeps corners circular
        r = min(r, w / 2, h / 2)
        self.fig.patches.append(FancyBboxPatch((x / 100, (self.h - y - h) / 100), w / 100, h / 100,
                                               boxstyle=f"round,pad=0,rounding_size={r / 100}",
                                               transform=self.fig.dpi_scale_trans, fc=fc, ec=ec, lw=lw, zorder=z))

    def text(self, x, y, s, size=10, color=C["ink"], weight="normal", ha="left", va="top", **kw):
        self.fig.text(x / self.w, 1 - y / self.h, s, size=size, color=color, weight=weight, ha=ha, va=va, **kw)

    @staticmethod
    def seg_w(items, pad=14, size=9.5):
        return sum(tw(s, size, "bold") + 2 * pad for s in items) + 6

    def seg(self, x, y, items, active, h=30, pad=14, size=9.5):
        widths = [tw(s, size, "bold") + 2 * pad for s in items]
        self.box(x, y, sum(widths) + 6, h, fc="#efeee9", ec="none", r=8)
        cx = x + 3
        for i, (s, w) in enumerate(zip(items, widths)):
            if i == active:
                self.box(cx, y + 3, w, h - 6, fc="#ffffff", ec=C["border"], r=6, z=2)
            self.text(cx + w / 2, y + h / 2, s, size=size, ha="center", va="center",
                      color=C["ink"] if i == active else C["ink2"], weight="bold" if i == active else "normal")
            cx += w
        return x + sum(widths) + 6

    def toggle(self, x, y, on, label=None, size=9.5):
        self.box(x, y, 36, 20, fc=C["accent"] if on else "#d6d5cf", ec="none", r=10, z=2)
        self.box(x + (18 if on else 2), y + 2, 16, 16, fc="#ffffff", ec="none", r=8, z=3)
        if label:
            self.text(x + 44, y + 10, label, size=size, va="center", color=C["ink"])

    def chip(self, x, y, color, label, size=8.5):
        self.box(x, y + 2, 12, 12, fc=color, ec="none", r=3)
        self.text(x + 17, y + 8, label, size=size, va="center", color=C["ink2"])
        return x + 17 + tw(label, size) + 16

    def field(self, x, y, w, value, unit=None, label=None):
        if label:
            self.text(x, y - 6, label, size=8.5, color=C["ink2"], va="bottom")
        self.box(x, y, w, 30, fc="#ffffff", ec=C["axis"], r=6)
        self.text(x + 10, y + 15, value, size=10, va="center", color=C["ink"] if value[0].isdigit() else C["muted"])
        if unit:
            self.text(x + w - 8, y + 15, unit, size=8.5, va="center", ha="right", color=C["muted"])

    def line(self, x0, x1, y, color, ls="-", lw=2):
        from matplotlib.lines import Line2D
        self.fig.lines.append(Line2D([x0 / self.w, x1 / self.w], [1 - y / self.h] * 2, transform=self.fig.transFigure,
                                     color=color, ls=ls, lw=lw))

    def axes(self, x, y, w, h):
        return self.fig.add_axes(self._r(x, y, w, h), zorder=5)

    def save(self, name):
        self.fig.savefig(OUT / name, dpi=200, facecolor=self.fig.get_facecolor())
        plt.close(self.fig)


# ---------- chart ----------
def level_colors(vals, pal):
    return [pal[sd.level(v)] for v in vals]


def draw_chart(ax, res="1h", pal=sd.TRAFFIC, bars_from=None, line_by_level=False, earlier=False,
               xlim=None, compact=False, fees=None, show_daily=True):
    t, p, conf = (D["t1"], D["p1"], D["conf1"]) if res == "1h" else (D["t15"], D["p15"], D["conf15"])
    step = dt.timedelta(hours=1 if res == "1h" else 0.25)
    tn = mdates.date2num(t)
    w = (mdates.date2num(t[0] + step) - tn[0])
    ax.set_facecolor(C["surface"])
    x0 = sd.START if xlim is None else xlim[0]
    x1 = sd.FC_END if xlim is None else xlim[1]
    # forecast zone
    ax.axvspan(mdates.date2num(sd.CONFIRMED_END), mdates.date2num(x1), color=C["fcshade"], lw=0, zorder=0)
    # confirmed bars
    ci = np.where(conf)[0]
    bi = ci if bars_from is None else [i for i in ci if t[i] >= bars_from.astimezone(UTC)]
    gap = 0.18 if res == "1h" else 0.22
    if fees:
        spot = p[bi]
        extra = np.array([fees(t[i]) for i in bi])
        ax.bar(tn[bi], spot, width=w * (1 - gap), align="edge", color=level_colors(spot, pal), lw=0, zorder=2)
        ax.bar(tn[bi], extra, bottom=np.maximum(spot, 0), width=w * (1 - gap), align="edge",
               color="#c9c8c1", lw=0, zorder=2, hatch="////", edgecolor="#b3b2aa")
        tot = spot + extra
        ax.step(tn[bi], tot, where="post", color=C["ink"], lw=1.2, zorder=4)
    else:
        ax.bar(tn[bi], p[bi], width=w * (1 - gap), align="edge", color=level_colors(p[bi], pal), lw=0, zorder=2)
    # confirmed line (step: the price is constant within the interval)
    if not fees:
        xs = np.append(tn[ci], tn[ci[-1]] + w)
        ys = np.append(p[ci], p[ci[-1]])
        if line_by_level:
            segs, cols = [], []
            for i in range(len(ci)):
                segs.append([(xs[i], ys[i]), (xs[i + 1], ys[i])])
                if i + 1 < len(ci):
                    segs.append([(xs[i + 1], ys[i]), (xs[i + 1], ys[i + 1])])
                    cols.append(pal[sd.level(ys[i])])
                cols.append(pal[sd.level(ys[i])])
            cols = cols[:len(segs)]
            ax.add_collection(LineCollection(segs, colors=cols, lw=1.8, zorder=3, capstyle="butt"))
        else:
            ax.step(xs, ys, where="post", color=C["ink2"], lw=1.0, zorder=3)
    # earlier forecasts (lighter tones)
    if earlier:
        tones = ["#9fbcd3", "#b8cddd", "#cfdde8"][::-1]
        for k, (issued, tt, f) in enumerate(D["earlier"]):
            ax.step(mdates.date2num(tt), f, where="post", color=tones[k], lw=1.6, zorder=2.5)
            ax.text(mdates.date2num(tt[len(tt) // 2]), -1.6,
                    f"ennuste {issued.day}.{issued.month}. klo {issued.hour}", size=7.5, color="#6f8fa8",
                    ha="center", va="center", zorder=5)
    # forecasts
    ft = mdates.date2num(D["fct"])
    fx = np.append(ft, ft[-1] + mdates.date2num(D["fct"][0] + dt.timedelta(hours=1)) - ft[0])
    f, lo, hi = D["rapid"]
    fd = D["daily"][0]
    if fees:
        add = np.array([fees(t) for t in D["fct"]])
        f, lo, hi, fd = f + add, lo + add, hi + add, fd + add
    ax.fill_between(fx, np.append(lo, lo[-1]), np.append(hi, hi[-1]), step="post", color=C["rapid"], alpha=0.12,
                    lw=0, zorder=1)
    if line_by_level:
        ax.step(fx, np.append(f, f[-1]), where="post", color=C["rapid"], lw=1.8, zorder=3, ls=(0, (4, 2)))
    else:
        ax.step(fx, np.append(f, f[-1]), where="post", color=C["rapid"], lw=1.8, zorder=3)
    if show_daily:
        ax.step(fx, np.append(fd, fd[-1]), where="post", color=C["daily"], lw=1.4, zorder=3, ls=(0, (2, 2)))
    # thresholds
    ymax = 40 if not fees else 48
    ymin = -3
    for lim in sd.LIMITS[1:]:
        ax.axhline(lim, color=C["grid"], lw=0.8, zorder=0.5)
    ax.axhline(0, color=C["axis"], lw=1, zorder=0.6)
    # days
    d = x0
    while d < x1:
        dn = mdates.date2num(d)
        ax.axvline(dn, color=C["axis"] if d.hour == 0 else C["grid"], lw=0.8, zorder=0.4)
        nxt = (d + dt.timedelta(days=1, hours=2)).replace(hour=0, minute=0)
        mid = mdates.date2num(d) + (mdates.date2num(nxt) - dn) / 2
        lbl = f"{WD[d.weekday()]} {d.day}.{d.month}."
        if d.date() == sd.NOW.date():
            lbl = "tänään"
        elif d.date() == (sd.NOW + dt.timedelta(days=1)).date():
            lbl = "huomenna"
        ax.text(mid, ymax - 0.8, lbl, ha="center", va="top", size=7.5 if compact else 8.5,
                color=C["ink"] if lbl in ("tänään", "huomenna") else C["ink2"],
                weight="bold" if lbl in ("tänään", "huomenna") else "normal", zorder=6)
        d = nxt
    # now
    nn = mdates.date2num(sd.NOW)
    ax.axvline(nn, color=C["ink"], lw=1.2, zorder=5)
    ax.text(nn, ymax - (3.6 if not compact else 3.8), f" nyt {sd.NOW:%H:%M}", size=7.5, color=C["ink"],
            zorder=6, bbox=dict(fc=C["surface"], ec="none", pad=0.5))
    ax.text(mdates.date2num(sd.CONFIRMED_END), ymax - (6.2 if not compact else 6.6), " ennuste", size=7.5,
            color=C["ink2"], style="italic", zorder=6)
    ax.set_xlim(mdates.date2num(x0), mdates.date2num(x1))
    ax.set_ylim(ymin, ymax)
    ax.set_yticks([0, 5, 10, 20, 30] if not compact else [0, 10, 20, 30])
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}")
    ax.tick_params(axis="y", length=0, labelsize=8)
    ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 6, 12, 18] if not compact else [0, 12]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H"))
    ax.tick_params(axis="x", length=0, labelsize=7.5)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.text(-0.005, ymax - 0.5, "c/kWh", transform=ax.get_yaxis_transform(), ha="right", va="top", size=7.5, color=C["muted"])


def header(cv, x, y, w, res_active=1, vat=True, lang=0, mobile=False):
    cv.text(x, y, "Pörssisähkö", size=17 if not mobile else 15, weight="bold")
    cv.text(x, y + (27 if not mobile else 24), "Suomi · hinta c/kWh sis. ALV 25,5 %" if vat else
            "Suomi · hinta c/kWh ilman ALV:tä", size=9, color=C["ink2"])
    if mobile:
        cv.box(x + w - 34, y - 2, 34, 34, fc="#ffffff", ec=C["border"], r=8)
        cv.text(x + w - 17, y + 15, "⚙", size=14, ha="center", va="center", color=C["ink2"])
        return
    xe = cv.seg(x + w - 470, y, ["15 min", "1 h"], res_active)
    cv.toggle(xe + 16, y + 5, vat, "ALV")
    cv.seg(x + w - 200, y, ["FI", "EN"], lang, pad=10)
    cv.box(x + w - 112, y, 112, 30, fc="#ffffff", ec=C["border"], r=8)
    cv.text(x + w - 56, y + 15, "⚙  Asetukset", size=9.5, ha="center", va="center", color=C["ink"])


def tiles(cv, x, y, w, cols=4, h=74, gap=12):
    p1 = D["p1"]
    now_i = max(i for i, t in enumerate(D["t1"]) if t <= sd.NOW.astimezone(UTC))
    today = [i for i, t in enumerate(D["t1"]) if t.astimezone(sd.HEL).date() == sd.NOW.date()]
    tom = [i for i, t in enumerate(D["t1"]) if t.astimezone(sd.HEL).date() == (sd.NOW + dt.timedelta(days=1)).date()]
    roll = np.convolve(p1[tom], np.ones(3) / 3, mode="valid")
    k = int(np.argmin(roll))
    ts = D["t1"][tom[k]].astimezone(sd.HEL)
    data = [("Hinta nyt", fmt(p1[now_i]), "c/kWh", sd.level(p1[now_i])),
            ("Tänään  min / ka / max", f"{fmt(p1[today].min(), 1)} / {fmt(p1[today].mean(), 1)} / {fmt(p1[today].max(), 1)}", "", None),
            ("Huomenna keskihinta", fmt(p1[tom].mean()), "c/kWh", sd.level(p1[tom].mean())),
            ("Halvin 3 h huomenna", f"klo {ts.hour:02d}–{ts.hour + 3:02d}", f"ka {fmt(roll[k])}", None)]
    rows = int(np.ceil(len(data) / cols))
    tile_w = (w - gap * (cols - 1)) / cols
    for n, (lbl, val, unit, lev) in enumerate(data):
        cx, cy = x + (n % cols) * (tile_w + gap), y + (n // cols) * (h + gap)
        cv.box(cx, cy, tile_w, h, fc=C["surface"], ec=C["border"], r=10)
        cv.text(cx + 12, cy + 12, lbl, size=8.5, color=C["ink2"])
        cv.text(cx + 12, cy + 34, val, size=15 if len(val) < 10 else 12.5, weight="bold")
        if unit:
            cv.text(cx + 12 + tw(val, 15 if len(val) < 10 else 12.5, "bold") + 6, cy + 40, unit, size=8.5, color=C["ink2"])
        if lev is not None:
            px, py = (cx + tile_w - 92, cy + 12) if cols > 2 else (cx + 12, cy + h - 26)
            cv.box(px, py, 80, 18, fc=sd.TRAFFIC[lev], ec="none", r=9)
            cv.text(px + 40, py + 9, sd.LEVELS[lev], size=7.5, color="#ffffff" if lev != 2 else C["ink"],
                    ha="center", va="center", weight="bold")
    return y + rows * (h + gap)


def legend(cv, x, y, w, pal=sd.TRAFFIC, forecasts=True, mobile=False, extra=None):
    cx, cy = x, y
    for c, l, r in zip(pal, sd.LEVELS, sd.LEVEL_LABELS):
        lab = f"{l} {r}" if not mobile else r
        need = 17 + tw(lab, 8.5) + 16
        if cx + need > x + w:
            cx, cy = x, cy + 20
        cx = cv.chip(cx, cy, c, lab)
    if forecasts:
        items = [("-", C["rapid"], "pikaennuste ~5×/vrk"), ((0, (2, 2)), C["daily"], "vuorokausiennuste")]
        if extra:
            items += extra
        if mobile:
            cx, cy = x, cy + 22
        for sym, col, lab in items:
            need = 18 + tw(lab, 8.5) + 22
            if cx + need > x + w:
                cx, cy = x, cy + 20
            cv.line(cx, cx + 14, cy + 8, col, ls=sym)
            cv.text(cx + 18, cy + 8, lab, size=8.5, color=C["ink2"], va="center")
            cx += need
    return cy + 20


def footer(cv, x, y, s="Päivitetty 30.10. klo 14:05 · Hinnat: ENTSO-E (varalla spot-hinta.fi) · "
                        "Ennuste: Sähkövatkain (nordpool-predict-fi)"):
    cv.text(x, y, s, size=8, color=C["muted"])


def caption(cv, s, y=None):
    cv.box(0, cv.h - 34, cv.w, 34, fc="#26251f", ec="none", r=0)
    cv.text(16, cv.h - 17, s, size=9, color="#f0efec", va="center")


# ---------- G1: desktop, 1 h, traffic colours ----------
def g1():
    cv = Canvas(1200, 760)
    header(cv, 32, 24, 1136)
    y = tiles(cv, 32, 92, 1136)
    cv.box(32, y, 1136, 470, fc=C["surface"], ec=C["border"], r=12)
    ax = cv.axes(80, y + 20, 1068, 390)
    draw_chart(ax, "1h")
    legend(cv, 80, y + 432, 1080)
    footer(cv, 32, y + 486)
    caption(cv, "G1 · Työpöytä, 1 h · liikennevalovärit · pylväät + viiva vahvistetuille, ennusteet viivoina + "
                "epävarmuusvyö")
    cv.save("graphs/G1_desktop_1h_traffic.png")


# ---------- G2: desktop, 15 min, ordinal ramp, bars only today+tomorrow ----------
def g2():
    cv = Canvas(1200, 760)
    header(cv, 32, 24, 1136, res_active=0)
    y = tiles(cv, 32, 92, 1136)
    cv.box(32, y, 1136, 470, fc=C["surface"], ec=C["border"], r=12)
    ax = cv.axes(80, y + 20, 1068, 390)
    draw_chart(ax, "15min", pal=sd.ORDINAL, bars_from=sd.NOW.replace(hour=0, minute=0), line_by_level=True)
    legend(cv, 80, y + 432, 1080, pal=sd.ORDINAL)
    footer(cv, 32, y + 486)
    caption(cv, "G2 · Työpöytä, 15 min · yksisävyinen asteikko · pylväät vain tänään+huomenna, viikko tasovärjättynä "
                "viivana")
    cv.save("graphs/G2_desktop_15min_ordinal.png")


# ---------- G3: earlier forecasts toggle on ----------
def g3():
    cv = Canvas(1200, 640)
    header(cv, 32, 24, 1136)
    y = 84
    cv.box(32, y, 1136, 470, fc=C["surface"], ec=C["border"], r=12)
    cv.toggle(900, y + 14, True, "Näytä aiemmat ennusteet")
    ax = cv.axes(80, y + 46, 1068, 364)
    draw_chart(ax, "1h", earlier=True)
    legend(cv, 80, y + 432, 1080, extra=[("-", "#9fbcd3", "aiemmat ennusteet")])
    footer(cv, 32, y + 486)
    caption(cv, "G3 · 'Aiemmat ennusteet' päällä: arkistoidut ajot vaaleina sävyinä näytetyn jakson päällä "
                "(ennuste vs. toteuma)")
    cv.save("graphs/G3_desktop_earlier_forecasts.png")


# ---------- G4: mobile ----------
def g4():
    cv = Canvas(390, 900)
    header(cv, 16, 18, 358, mobile=True)
    cv.seg(16, 70, ["15 min", "1 h"], 1, h=28, pad=12, size=9)
    cv.toggle(160, 74, True, "ALV")
    y = tiles(cv, 16, 112, 358, cols=2, h=92, gap=8)
    cv.box(8, y, 374, 470, fc=C["surface"], ec=C["border"], r=12)
    ax = cv.axes(40, y + 14, 334, 300)
    draw_chart(ax, "1h", xlim=(sd.NOW.replace(hour=0, minute=0) - dt.timedelta(days=1), sd.FC_END), compact=True)
    # overview / zoom slider (ECharts dataZoom)
    ax2 = cv.axes(40, y + 338, 334, 34)
    ax2.set_facecolor("#f1f0ec")
    tt = mdates.date2num(D["t1"])
    ax2.fill_between(tt[D["conf1"]], D["p1"][D["conf1"]], color="#b7b6ae", lw=0, step="post")
    ax2.fill_between(mdates.date2num(D["fct"]), D["rapid"][0], color="#a9c0d3", lw=0, step="post")
    lo = mdates.date2num(sd.NOW.replace(hour=0, minute=0) - dt.timedelta(days=1))
    ax2.add_patch(Rectangle((lo, -5), tt[-1] - lo + 0.05, 60, fc=C["rapid"], alpha=0.12, ec=C["rapid"], lw=1.2))
    ax2.set_xlim(tt[0], tt[-1] + 1 / 24)
    ax2.set_ylim(-3, 40)
    ax2.axis("off")
    cv.text(40, y + 380, "◀ vedä nähdäksesi koko viikon", size=7.5, color=C["muted"])
    legend(cv, 20, y + 398, 350, mobile=True)
    footer(cv, 16, y + 482, "Päivitetty 30.10. 14:05 · ENTSO-E · Sähkövatkain")
    caption(cv, "G4 · Mobiili: eilinen→ennuste, viikko liukusäätimellä")
    cv.save("graphs/G4_mobile_1h.png")


# ---------- G5: day × hour heat strip (optional extra view) ----------
def g5():
    cv = Canvas(1200, 540)
    header(cv, 32, 24, 1136)
    cv.box(32, 84, 1136, 410, fc=C["surface"], ec=C["border"], r=12)
    ax = cv.axes(190, 110, 950, 310)
    days = sorted({t.astimezone(sd.HEL).date() for t in D["t1"]})
    for r, day in enumerate(days):
        rows = [(t.astimezone(sd.HEL), p, c) for t, p, c in zip(D["t1"], D["p1"], D["conf1"])
                if t.astimezone(sd.HEL).date() == day]
        hours = [loc.hour for loc, _, _ in rows]
        seen = set()
        for loc, p, conf in rows:
            # the repeated hour on the DST day gets two half cells
            dup = hours.count(loc.hour) > 1
            h = loc.hour + (0.5 if loc.hour in seen else 0)
            cw = 0.45 if dup else 0.9
            seen.add(loc.hour)
            if conf:
                ax.add_patch(Rectangle((h + 0.05, r + 0.08), cw, 0.84, fc=sd.TRAFFIC[sd.level(p)], lw=0))
                ax.text(h + 0.05 + cw / 2, r + 0.5, f"{p:.0f}", ha="center", va="center", size=7 if not dup else 6,
                        color=C["ink"] if sd.level(p) == 2 else "#ffffff")
        if day >= sd.CONFIRMED_END.date():
            fl = [(t.astimezone(sd.HEL), v) for t, v in zip(D["fct"], D["rapid"][0]) if t.astimezone(sd.HEL).date() == day]
            for loc, v in fl:
                ax.add_patch(Rectangle((loc.hour + 0.05, r + 0.08), 0.9, 0.84, fc=sd.TRAFFIC[sd.level(v)], lw=0, alpha=0.35))
                ax.text(loc.hour + 0.5, r + 0.5, f"{v:.0f}", ha="center", va="center", size=7, color=C["ink2"],
                        style="italic")
        lbl = f"{WD[day.weekday()]} {day.day}.{day.month}."
        if day >= sd.CONFIRMED_END.date():
            lbl += "  (ennuste)"
        ax.text(-0.3, r + 0.5, lbl, ha="right", va="center", size=8.5,
                color=C["ink"] if day == sd.NOW.date() else C["ink2"], weight="bold" if day == sd.NOW.date() else "normal")
    ax.set_xlim(0, 24)
    ax.set_ylim(len(days), 0)
    ax.set_xticks(np.arange(24) + 0.5, [f"{h:02d}" for h in range(24)])
    ax.tick_params(length=0, labelsize=8)
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    legend(cv, 190, 456, 950, forecasts=False)
    caption(cv, "G5 · Lisänäkymä (valinnainen): päivä × tunti -lämpökartta, ennustepäivät haaleina; "
                "25-tuntinen DST-päivä 25.10. näkyy")
    cv.save("graphs/G5_desktop_heatmap.png")


# ---------- G6: total price with margin + transfer ----------
def g6():
    def fees(t):
        loc = t.astimezone(sd.HEL)
        transfer = 4.10 if 7 <= loc.hour < 22 else 2.40
        return 0.49 + transfer
    cv = Canvas(1200, 640)
    header(cv, 32, 24, 1136)
    cv.box(32, 84, 1136, 470, fc=C["surface"], ec=C["border"], r=12)
    seg_x = cv.seg(780, 98, ["Spot", "Kokonaishinta"], 1, h=28, pad=12, size=9)
    ax = cv.axes(80, 140, 1068, 330)
    draw_chart(ax, "1h", xlim=(sd.NOW.replace(hour=0, minute=0) - dt.timedelta(days=2), sd.FC_END), fees=fees)
    cv.text(80, 100, "Kokonaishinta = spot + marginaali 0,49 + siirto 4,10 (07–22) / 2,40 (22–07) c/kWh",
            size=9, color=C["ink2"])
    x = legend(cv, 80, 504, 1080, forecasts=False)
    cv.box(80, 528, 12, 12, fc="#c9c8c1", ec="#b3b2aa", r=2)
    cv.text(97, 534, "marginaali + siirtomaksu (päivä/yö)", size=8.5, color=C["ink2"], va="center")
    cv.text(330, 534, "— kokonaishinta", size=8.5, color=C["ink"], va="center")
    caption(cv, "G6 · Kun maksut on syötetty: pino = spot (tasoväri) + lisät (harmaa viivoitus); "
                "tasoväri lasketaan spot-hinnasta")
    cv.save("graphs/G6_desktop_total_price.png")


# ---------- O1: desktop settings panel ----------
def settings_body(cv, x, y, w, mobile=False):
    def row(yy, label, sub=None):
        cv.text(x, yy, label, size=10, weight="bold")
        if sub:
            cv.text(x, yy + 22, sub, size=8.5, color=C["ink2"])

    col2 = x + (w * 0.48 if not mobile else 0)
    yy = y
    row(yy, "Aikaresoluutio")
    cv.seg(x + w - cv.seg_w(["15 min", "1 h"], 12, 9) if mobile else x + 170, yy - 6, ["15 min", "1 h"], 1, h=28, pad=12, size=9)
    yy += 46
    row(yy, "ALV 25,5 %", "Negatiivisiin hintoihin ei lisätä ALV:tä")
    cv.toggle(x + w - 40 if mobile else x + 170, yy - 4, True)
    yy += 52
    row(yy, "Kieli / Language")
    cv.seg(x + w - cv.seg_w(["Suomi", "English"], 10, 9) if mobile else x + 170, yy - 6, ["Suomi", "English"], 0, h=28, pad=10, size=9)
    yy += 46
    row(yy, "Teema")
    cv.seg(x + w - cv.seg_w(["Auto", "Vaalea", "Tumma"], 10, 9) if mobile else x + 170, yy - 6, ["Auto", "Vaalea", "Tumma"], 0, h=28, pad=10, size=9)
    yy += 46
    row(yy, "Väritys")
    cv.seg(x + w - cv.seg_w(["Liikennevalo", "Asteikko"], 10, 9) if mobile else x + 170, yy - 6, ["Liikennevalo", "Asteikko"], 0, h=28, pad=10, size=9)
    yy += 52
    row(yy, "Ennusteet")
    yy += 24
    for lab, on in [("Pikaennuste (~5×/vrk)", True), ("Vuorokausiennuste", True), ("Epävarmuusvyö", True),
                    ("Näytä aiemmat ennusteet", False)]:
        cv.toggle(x, yy, on, lab)
        yy += 30
    if not mobile:
        x2, yy2 = col2 + 20, y
    else:
        x2, yy2 = x, yy + 16
    cv.text(x2, yy2, "Hinnan lisät (valinnainen)", size=10, weight="bold")
    cv.text(x2, yy2 + 17, "Näytetään kokonaishinta-näkymässä (spot + lisät)", size=8.5, color=C["ink2"])
    fy = yy2 + 58
    fw = (w * 0.52 - 20) if not mobile else w
    cv.field(x2, fy, fw * 0.48, "0,49", "c/kWh", "Sopimuksen marginaali")
    cv.field(x2 + fw * 0.52, fy, fw * 0.48, "0,00", "€/kk", "Perusmaksu (ei kuvaajaan)")
    fy += 62
    cv.field(x2, fy, fw * 0.48, "4,10", "c/kWh", "Siirtomaksu, päivä")
    cv.field(x2 + fw * 0.52, fy, fw * 0.22, "07", None, "alkaa klo")
    cv.field(x2 + fw * 0.78, fy, fw * 0.22, "22", None, "päättyy klo")
    fy += 62
    cv.field(x2, fy, fw * 0.48, "2,40", "c/kWh", "Siirtomaksu, yö")
    cv.field(x2 + fw * 0.52, fy, fw * 0.48, "2,79", "c/kWh", "Sähkövero (luokka I)")
    fy += 44
    cv.toggle(x2, fy, False, "Vain arkipäivinä päivähinta (kausisähkö)", size=9)
    return max(yy, fy + 30)


def o1():
    cv = Canvas(1200, 700)
    header(cv, 32, 24, 1136)
    # dim chart behind
    cv.box(32, 84, 1136, 560, fc="#efeee9", ec=C["border"], r=12, z=0.5)
    cv.box(300, 60, 860, 600, fc="#ffffff", ec=C["border"], r=14, z=1)
    cv.text(324, 80, "Asetukset", size=14, weight="bold")
    cv.text(1136, 84, "✕", size=13, ha="right", color=C["ink2"])
    end = settings_body(cv, 324, 124, 812)
    cv.box(300, 600, 860, 1, fc=C["border"], ec="none", r=0)
    cv.text(324, 628, "Tallennetaan evästeeseen vain, jos asetukset poikkeavat oletuksista.", size=8.5,
            color=C["ink2"], va="center")
    cv.box(1010, 614, 130, 30, fc="#ffffff", ec=C["axis"], r=8)
    cv.text(1075, 629, "Palauta oletukset", size=9, ha="center", va="center")
    cv.text(48, 104, "(kaavio taustalla)", size=10, color=C["muted"])
    caption(cv, "O1 · Työpöytä: yleisimmät valinnat yläpalkissa, kaikki asetukset sivupaneelissa (2 saraketta)")
    cv.save("options/O1_desktop_settings_panel.png")


def o2():
    cv = Canvas(390, 980)
    header(cv, 16, 18, 358, mobile=True)
    cv.box(0, 60, 390, 920, fc="#d9d8d2", ec="none", r=0)
    cv.box(0, 84, 390, 900, fc="#ffffff", ec=C["border"], r=18)
    cv.box(175, 92, 40, 4, fc="#c3c2b7", ec="none", r=2)
    cv.text(20, 108, "Asetukset", size=14, weight="bold")
    cv.text(370, 110, "✕", size=13, ha="right", color=C["ink2"])
    end = settings_body(cv, 20, 150, 350, mobile=True)
    cv.text(20, end + 4, "Tallennetaan evästeeseen vain, jos\nasetukset poikkeavat oletuksista.", size=8.5,
            color=C["ink2"])
    cv.box(20, end + 40, 350, 36, fc="#ffffff", ec=C["axis"], r=8)
    cv.text(195, end + 58, "Palauta oletukset", size=9.5, ha="center", va="center")
    caption(cv, "O2 · Mobiili: alhaalta nouseva paneeli ⚙-painikkeesta")
    cv.save("options/O2_mobile_settings_sheet.png")


def o3():
    cv = Canvas(1200, 260)
    cv.text(32, 20, "O3 · Vaihtoehto: kaikki valinnat kompaktina rivinä kaavion yläpuolella (ei erillistä paneelia)",
            size=11, weight="bold")
    y = 64
    cv.box(32, y, 1136, 54, fc=C["surface"], ec=C["border"], r=10)
    x = cv.seg(46, y + 12, ["15 min", "1 h"], 1, h=30)
    cv.toggle(x + 14, y + 17, True, "ALV")
    x = cv.seg(x + 96, y + 12, ["Spot", "Kokonaishinta"], 0, h=30, pad=10)
    cv.toggle(x + 14, y + 17, True, "Ennusteet")
    cv.toggle(x + 130, y + 17, False, "Aiemmat ennusteet")
    cv.seg(1010, y + 12, ["FI", "EN"], 0, h=30, pad=10)
    cv.box(1096, y + 12, 60, 30, fc="#ffffff", ec=C["border"], r=8)
    cv.text(1126, y + 27, "⚙ ▾", size=10, ha="center", va="center", color=C["ink2"])
    cv.text(32, y + 76, "• Hinnan lisät (marginaali, siirtomaksut, vero), teema ja väritys ⚙-valikon takana.\n"
                         "• Mobiilissa rivi rivittyy kahdelle riville tai vierii vaakasuunnassa (chip-rivi).",
            size=9.5, color=C["ink2"])
    cv.save("options/O3_inline_toolbar.png")


for f in (g1, g2, g3, g4, g5, g6, o1, o2, o3):
    f()
print("ok")
