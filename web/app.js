/* Finnish spot price page. Shows only what the exported JSON contains. */
'use strict';

// ---- Adjustable constants -------------------------------------------------

// Price level limits in c/kWh. The level is computed from the spot price as
// displayed (with VAT when the VAT toggle is on), without margin and fees.
const LIMITS = [0, 5, 10, 20, 30];
const LEVEL_COLORS = {
  light: ['#2a78d6', '#16a061', '#d9a800', '#e8603c', '#b8213b', '#6a2c91'],
  dark: ['#3987e5', '#199e70', '#c49800', '#e8603c', '#d03a52', '#9a5ad0'],
};
const VAT_RATE = 0.255;
const DATA_URL = 'data/spot.json';
const REFRESH_MS = 5 * 60 * 1000;
const TZ = 'Europe/Helsinki';
const COOKIE = 'spotprice_settings';
const NARROW = 720; // px, mobile layout below this

const DEFAULTS = {
  res: '60', vat: true, lang: 'fi', theme: 'auto', priceMode: 'spot',
  showRapid: true, showDaily: true, showBand: true, showEarlier: false,
  margin: 0, tax: 0, transferDay: 0, transferNight: 0, dayStart: 7, dayEnd: 22, dayWeekdaysOnly: false,
};
const NUMERIC = ['margin', 'tax', 'transferDay', 'transferNight', 'dayStart', 'dayEnd'];

const I18N = {
  fi: {
    title: 'Pörssisähkö', subtitleVat: 'Suomi · hinta c/kWh sis. ALV 25,5 %', subtitleNoVat: 'Suomi · hinta c/kWh ilman ALV:tä',
    resolution: 'Aikaresoluutio', vat: 'ALV', vatLong: 'ALV 25,5 %', vatNote: 'Negatiivisiin hintoihin ei lisätä ALV:tä',
    settings: 'Asetukset', close: 'Sulje', theme: 'Teema', themeAuto: 'Auto', themeLight: 'Vaalea', themeDark: 'Tumma',
    forecasts: 'Ennusteet', rapidLong: 'Pikaennuste (päivittyy useita kertoja päivässä)', dailyLong: 'Vuorokausiennuste',
    band: 'Epävarmuusvyö', showEarlier: 'Näytä aiemmat ennusteet', extras: 'Hinnan lisät (valinnainen)',
    extrasNote: 'Syötä hinnat ALV:n sisältävinä kuten laskussa. Näytetään kokonaishinta-näkymässä.',
    margin: 'Sopimuksen marginaali', tax: 'Sähkövero', transferDay: 'Siirtomaksu, päivä', transferNight: 'Siirtomaksu, yö',
    dayStart: 'alkaa klo', dayEnd: 'päättyy klo', weekdaysOnly: 'Päivähinta vain arkipäivinä (kausisähkö)',
    cookieNote: 'Tallennetaan evästeeseen vain, jos asetukset poikkeavat oletuksista.', reset: 'Palauta oletukset',
    spot: 'Spot', total: 'Kokonaishinta', heatmapTitle: 'Tuntihinnat päivittäin',
    levels: ['negatiivinen', 'edullinen', 'keskitaso', 'kallis', 'erittäin kallis', 'äärimmäinen'],
    priceNow: 'Hinta nyt', today: 'Tänään min / ka / max', tomorrowAvg: 'Huomenna keskihinta',
    cheapest3Tomorrow: 'Halvin 3 h huomenna', cheapest3Today: 'Halvin 3 h tänään', dearest3Fc: 'Kallein 3 h ennusteessa',
    avg: 'ka', at: 'klo', todayWord: 'tänään', tomorrowWord: 'huomenna', now: 'nyt', forecastZone: 'ennuste',
    rapid: 'pikaennuste', daily: 'vuorokausiennuste', earlier: 'aiemmat ennusteet', fees: 'marginaali + vero + siirto',
    totalLine: 'kokonaishinta', confirmed: 'vahvistettu hinta', cheapWin: 'halvin 3 h', dearWin: 'kallein 3 h (ennuste)',
    forecastIssued: 'ennuste', updated: 'Päivitetty', pricesFrom: 'Hinnat', forecastFrom: 'Ennuste',
    noData: 'Hintatietoja ei ole saatavilla.', loadError: 'Tietojen lataus epäonnistui',
    formula: 'Kokonaishinta = spot + {parts} c/kWh', marginShort: 'marginaali', taxShort: 'vero', transferShort: 'siirto',
    weekdays: ['su', 'ma', 'ti', 'ke', 'to', 'pe', 'la'], hourAbbr: 'klo',
  },
  en: {
    title: 'Spot electricity', subtitleVat: 'Finland · price c/kWh incl. VAT 25.5 %', subtitleNoVat: 'Finland · price c/kWh excl. VAT',
    resolution: 'Resolution', vat: 'VAT', vatLong: 'VAT 25.5 %', vatNote: 'No VAT is added to negative prices',
    settings: 'Settings', close: 'Close', theme: 'Theme', themeAuto: 'Auto', themeLight: 'Light', themeDark: 'Dark',
    forecasts: 'Forecasts', rapidLong: 'Rapid forecast (updated several times a day)', dailyLong: 'Daily forecast',
    band: 'Uncertainty band', showEarlier: 'Show earlier forecasts', extras: 'Price extras (optional)',
    extrasNote: 'Enter prices including VAT as on your bill. Shown in the total price view.',
    margin: 'Contract margin', tax: 'Electricity tax', transferDay: 'Transfer fee, day', transferNight: 'Transfer fee, night',
    dayStart: 'starts at', dayEnd: 'ends at', weekdaysOnly: 'Day rate on weekdays only (seasonal tariff)',
    cookieNote: 'Saved to a cookie only when the settings differ from the defaults.', reset: 'Reset to defaults',
    spot: 'Spot', total: 'Total price', heatmapTitle: 'Hourly prices by day',
    levels: ['negative', 'low', 'average', 'high', 'very high', 'extreme'],
    priceNow: 'Price now', today: 'Today min / avg / max', tomorrowAvg: 'Tomorrow average',
    cheapest3Tomorrow: 'Cheapest 3 h tomorrow', cheapest3Today: 'Cheapest 3 h today', dearest3Fc: 'Most expensive 3 h in forecast',
    avg: 'avg', at: 'at', todayWord: 'today', tomorrowWord: 'tomorrow', now: 'now', forecastZone: 'forecast',
    rapid: 'rapid forecast', daily: 'daily forecast', earlier: 'earlier forecasts', fees: 'margin + tax + transfer',
    totalLine: 'total price', confirmed: 'confirmed price', cheapWin: 'cheapest 3 h', dearWin: 'most expensive 3 h (forecast)',
    forecastIssued: 'forecast', updated: 'Updated', pricesFrom: 'Prices', forecastFrom: 'Forecast',
    noData: 'No price data available.', loadError: 'Loading data failed',
    formula: 'Total = spot + {parts} c/kWh', marginShort: 'margin', taxShort: 'tax', transferShort: 'transfer',
    weekdays: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'], hourAbbr: '',
  },
};
const SOURCE_NAMES = {
  'entsoe': 'ENTSO-E', 'spot-hinta.fi': 'spot-hinta.fi',
  'nordpool-predict-fi': 'nordpool-predict-fi (Sähkövatkain)',
};

// ---- State -----------------------------------------------------------------

const state = { data: null, settings: loadSettings(), chart: null, heatmap: null, zoom: null, lastGenerated: null };
const t = (key) => I18N[state.settings.lang][key] ?? I18N.fi[key];

// ---- Settings & cookie -----------------------------------------------------

function loadSettings() {
  const s = { ...DEFAULTS };
  try {
    const raw = document.cookie.split('; ').find((c) => c.startsWith(COOKIE + '='));
    if (raw) {
      const saved = JSON.parse(decodeURIComponent(raw.slice(COOKIE.length + 1)));
      for (const k of Object.keys(DEFAULTS)) {
        if (k in saved && typeof saved[k] === typeof DEFAULTS[k]) s[k] = saved[k];
      }
    }
  } catch (e) { /* ignore a broken cookie */ }
  return s;
}

function saveSettings() {
  const diff = {};
  for (const [k, v] of Object.entries(state.settings)) {
    if (v !== DEFAULTS[k]) diff[k] = v;
  }
  const secure = location.protocol === 'https:' ? '; Secure' : '';
  if (Object.keys(diff).length) {
    const value = encodeURIComponent(JSON.stringify(diff));
    document.cookie = `${COOKIE}=${value}; Max-Age=${365 * 86400}; Path=/; SameSite=Lax${secure}`;
  } else {
    document.cookie = `${COOKIE}=; Max-Age=0; Path=/; SameSite=Lax${secure}`;
  }
}

function setSetting(key, value) {
  if (state.settings[key] === value) return;
  state.settings[key] = value;
  saveSettings();
  if (key === 'res') state.zoom = null;
  applyTheme();
  render();
}

// ---- Time helpers (always Europe/Helsinki) ---------------------------------

const partsFmt = new Intl.DateTimeFormat('en-GB', {
  timeZone: TZ, year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric',
  hourCycle: 'h23', weekday: 'short',
});
const WD = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };

function parts(ms) {
  const p = {};
  for (const { type, value } of partsFmt.formatToParts(new Date(ms))) p[type] = value;
  return { y: +p.year, mo: +p.month, d: +p.day, h: +p.hour, mi: +p.minute, wd: WD[p.weekday] };
}

function dayStart(ms) {
  // local midnight; corrected twice to handle the DST change days
  ms -= ((ms % 60000) + 60000) % 60000;
  let c = ms - (parts(ms).h * 60 + parts(ms).mi) * 60000;
  for (let i = 0; i < 2; i++) {
    const h = parts(c).h;
    if (h === 0) break;
    c += h >= 12 ? (24 - h) * 3600000 : -h * 3600000;
  }
  return c;
}
const nextDay = (ms) => dayStart(dayStart(ms) + 26 * 3600000);
const dayKey = (ms) => { const p = parts(ms); return `${p.y}-${p.mo}-${p.d}`; };
const pad = (n) => String(n).padStart(2, '0');
const hhmm = (ms) => { const p = parts(ms); return `${pad(p.h)}:${pad(p.mi)}`; };

function dayLabel(ms, now) {
  if (dayKey(ms) === dayKey(now)) return t('todayWord');
  if (dayKey(ms) === dayKey(nextDay(now))) return t('tomorrowWord');
  const p = parts(ms);
  return `${t('weekdays')[p.wd]} ${p.d}.${p.mo}.`;
}

// ---- Numbers & prices ------------------------------------------------------

function fmt(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return '–';
  return new Intl.NumberFormat(state.settings.lang === 'fi' ? 'fi-FI' : 'en-GB', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  }).format(v);
}

function parseNum(text) {
  const v = parseFloat(String(text).replace(',', '.').replace(/\s/g, ''));
  return Number.isFinite(v) ? v : 0;
}

/** EUR/MWh (VAT 0) -> displayed c/kWh. */
function spotC(eurMwh) {
  if (eurMwh === null || eurMwh === undefined) return null;
  let c = eurMwh / 10;
  if (state.settings.vat && c > 0) c *= 1 + VAT_RATE;
  return c;
}

const hasFees = () => ['margin', 'tax', 'transferDay', 'transferNight'].some((k) => state.settings[k] !== 0);
const totalMode = () => state.settings.priceMode === 'total' && hasFees();

/** Margin, tax and transfer at the given time in c/kWh. Entered with VAT. */
function feesAt(ms) {
  const s = state.settings;
  const p = parts(ms);
  const weekday = p.wd >= 1 && p.wd <= 5;
  const inDay = s.dayStart <= s.dayEnd ? p.h >= s.dayStart && p.h < s.dayEnd : p.h >= s.dayStart || p.h < s.dayEnd;
  const isDay = inDay && (!s.dayWeekdaysOnly || weekday);
  const fee = s.margin + s.tax + (isDay ? s.transferDay : s.transferNight);
  return s.vat ? fee : fee / (1 + VAT_RATE);
}

/** Displayed price: spot, or spot + fees in total mode. */
const shown = (ms, eurMwh) => (eurMwh === null ? null : spotC(eurMwh) + (totalMode() ? feesAt(ms) : 0));

function level(c) {
  let i = 0;
  while (i < LIMITS.length && c >= LIMITS[i]) i++;
  return i;
}

function themeName() {
  const th = state.settings.theme;
  if (th !== 'auto') return th;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}
const levelColor = (i) => LEVEL_COLORS[themeName()][i];
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// ---- Data ------------------------------------------------------------------

function activeRes() {
  const p = state.data.prices;
  if (p[state.settings.res]) return state.settings.res;
  return p['60'] ? '60' : '15';
}

function series(res) {
  return (state.data.prices[res] || []).map(([ms, v]) => ({ t: ms, v }));
}

function forecast(kind) {
  const f = state.data.forecasts?.[kind];
  if (!f || !f.values.length) return null;
  // the daily forecast is the same run as the rapid one until a newer run arrives
  if (kind === 'daily' && state.data.forecasts.rapid?.issued_at === f.issued_at) return null;
  return f;
}

/** Start of the shown period: the window start, or the first day with prices. */
function viewStart(d) {
  const firsts = Object.values(d.prices || {}).filter((s) => s.length).map((s) => s[0][0]);
  return firsts.length ? Math.max(d.window.start, dayStart(Math.min(...firsts))) : d.window.start;
}

const hasBand = (f) => f && f.values.some((v) => v.length >= 4 && v[2] !== null);

/** Best 3 h window of an hourly [{t, v}] list (contiguous hours only). */
function window3(points, cmp) {
  let best = null;
  for (let i = 0; i + 2 < points.length; i++) {
    if (points[i + 2].t - points[i].t !== 2 * 3600000) continue;
    const avg = (points[i].v + points[i + 1].v + points[i + 2].v) / 3;
    if (!best || cmp(avg, best.avg)) best = { start: points[i].t, end: points[i].t + 3 * 3600000, avg };
  }
  return best;
}

async function load() {
  try {
    const resp = await fetch(DATA_URL, { cache: 'no-cache' });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    if (data.generated_at === state.lastGenerated) return;
    state.lastGenerated = data.generated_at;
    state.data = data;
    render();
  } catch (err) {
    if (!state.data) showStatus(`${t('loadError')}: ${err.message}`);
    console.error(err);
  }
}

function showStatus(text) {
  const el = document.getElementById('status');
  el.textContent = text;
  el.hidden = !text;
}

// ---- Rendering -------------------------------------------------------------

function applyTheme() {
  const th = state.settings.theme;
  if (th === 'auto') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', th);
  document.documentElement.lang = state.settings.lang;
}

function render() {
  renderStatic();
  if (!state.data) return;
  const hasPrices = Object.keys(state.data.prices || {}).length > 0;
  showStatus(hasPrices ? '' : t('noData'));
  document.getElementById('chart-card').hidden = !hasPrices;
  document.getElementById('heatmap-card').hidden = !state.data.prices?.['60'];
  if (!hasPrices) return;
  renderTiles();
  renderChart();
  renderLegend();
  renderHeatmap();
  renderFooter();
}

function renderStatic() {
  const s = state.settings;
  document.title = t('title');
  for (const el of document.querySelectorAll('[data-i18n]')) el.textContent = t(el.dataset.i18n);
  for (const el of document.querySelectorAll('[data-i18n-aria]')) el.setAttribute('aria-label', t(el.dataset.i18nAria));
  document.getElementById('subtitle').textContent = s.vat ? t('subtitleVat') : t('subtitleNoVat');

  const d = state.data;
  const avail = {
    rapid: !!(d && forecast('rapid')),
    daily: !!(d && forecast('daily')),
    band: !!(d && (hasBand(forecast('rapid')) || hasBand(forecast('daily')))),
    earlier: !!(d && d.earlier_forecasts?.length),
  };
  for (const el of document.querySelectorAll('[data-requires]')) el.hidden = !avail[el.dataset.requires];
  document.getElementById('forecast-settings').hidden = !Object.values(avail).some(Boolean);
  document.getElementById('earlier-switch').hidden = !avail.earlier;
  document.getElementById('price-mode').hidden = !hasFees();

  // sync controls
  for (const group of document.querySelectorAll('.seg[data-setting]')) {
    const key = group.dataset.setting;
    for (const b of group.querySelectorAll('button')) {
      b.setAttribute('aria-checked', String(b.value === String(s[key])));
      if (key === 'res') b.disabled = !!d && !d.prices?.[b.value];
    }
  }
  for (const input of document.querySelectorAll('input[data-setting]')) {
    const key = input.dataset.setting;
    if (input.type === 'checkbox') input.checked = !!s[key];
    else if (document.activeElement !== input) input.value = s[key] === 0 && !['dayStart', 'dayEnd'].includes(key) ? '' : String(s[key]).replace('.', s.lang === 'fi' ? ',' : '.');
  }
  const formula = document.getElementById('formula');
  formula.hidden = !totalMode();
  if (totalMode()) {
    const parts_ = [];
    if (s.margin) parts_.push(`${t('marginShort')} ${fmt(s.margin)}`);
    if (s.tax) parts_.push(`${t('taxShort')} ${fmt(s.tax)}`);
    if (s.transferDay || s.transferNight) {
      parts_.push(`${t('transferShort')} ${fmt(s.transferDay)} (${pad(s.dayStart)}–${pad(s.dayEnd)}) / ${fmt(s.transferNight)}`);
    }
    formula.textContent = t('formula').replace('{parts}', parts_.join(' + '));
  }
}

function tile(label, value, unit, opts = {}) {
  const el = document.createElement('div');
  el.className = 'tile';
  el.innerHTML = `<div class="lbl"></div><div class="val"></div>`;
  el.querySelector('.lbl').textContent = label;
  const val = el.querySelector('.val');
  const main = document.createElement('span');
  main.className = 'main';
  if (opts.mark) {
    const m = document.createElement('span');
    m.className = 'mark';
    m.style.background = opts.mark;
    main.append(m);
  }
  main.append(value);
  val.append(main, ' ');
  if (unit) {
    const u = document.createElement('span');
    u.className = 'unit';
    u.textContent = unit;
    val.append(u);
  }
  if (opts.level !== undefined) {
    const p = document.createElement('span');
    p.className = 'pill';
    p.textContent = t('levels')[opts.level];
    p.style.background = levelColor(opts.level);
    if (opts.level === 2) p.style.color = '#0b0b0b';
    val.append(p);
  }
  return el;
}

function renderTiles() {
  const box = document.getElementById('tiles');
  box.replaceChildren();
  const now = Date.now();
  const res = activeRes();
  const step = res === '15' ? 900000 : 3600000;
  const pts = series(res);
  const unit = 'c/kWh';

  const cur = pts.find((p) => p.t <= now && now < p.t + step);
  if (cur) {
    box.append(tile(t('priceNow'), fmt(shown(cur.t, cur.v)), unit, { level: level(spotC(cur.v)) }));
  }
  const today0 = dayStart(now);
  const tomorrow0 = nextDay(now);
  const after0 = nextDay(tomorrow0);
  const today = pts.filter((p) => p.t >= today0 && p.t < tomorrow0).map((p) => shown(p.t, p.v));
  if (today.length) {
    const avg = today.reduce((a, b) => a + b, 0) / today.length;
    box.append(tile(t('today'), `${fmt(Math.min(...today), 1)} / ${fmt(avg, 1)} / ${fmt(Math.max(...today), 1)}`, ''));
  }
  const tomorrowSpot = pts.filter((p) => p.t >= tomorrow0 && p.t < after0);
  const tomorrowComplete = tomorrowSpot.length && tomorrowSpot[tomorrowSpot.length - 1].t + step >= after0;
  if (tomorrowComplete) {
    const vals = tomorrowSpot.map((p) => shown(p.t, p.v));
    const spotAvg = tomorrowSpot.reduce((a, p) => a + spotC(p.v), 0) / tomorrowSpot.length;
    box.append(tile(t('tomorrowAvg'), fmt(vals.reduce((a, b) => a + b, 0) / vals.length), unit, { level: level(spotAvg) }));
  }
  const { cheap, dear, cheapTomorrow } = windows();
  if (cheap) {
    box.append(tile(cheapTomorrow ? t('cheapest3Tomorrow') : t('cheapest3Today'),
      `${t('hourAbbr')} ${pad(parts(cheap.start).h)}–${pad(parts(cheap.end).h)}`.trim(), `${t('avg')} ${fmt(cheap.avg)}`,
      { mark: css('--cheap') }));
  }
  if (dear) {
    box.append(tile(t('dearest3Fc'),
      `${dayLabel(dear.start, now)} ${pad(parts(dear.start).h)}–${pad(parts(dear.end).h)}`, `${t('avg')} ${fmt(dear.avg)}`,
      { mark: css('--dear') }));
  }
}

/**
 * Cheapest confirmed 3 h (tomorrow when known, otherwise the rest of today)
 * and the most expensive 3 h of the forecast, using the displayed prices.
 */
function windows() {
  const now = Date.now();
  const tomorrow0 = nextDay(now);
  const after0 = nextDay(tomorrow0);
  const hourly = series('60').map((p) => ({ t: p.t, v: shown(p.t, p.v) }));
  const cheapTomorrow = hourly.length > 0 && hourly[hourly.length - 1].t + 3600000 >= after0;
  const cheapPts = cheapTomorrow
    ? hourly.filter((p) => p.t >= tomorrow0 && p.t < after0)
    : hourly.filter((p) => p.t + 3600000 > now && p.t < tomorrow0);
  const f = forecast('rapid') || forecast('daily');
  const dear = f ? window3(f.values.map(([ms, v]) => ({ t: ms, v: shown(ms, v) })), (a, b) => a > b) : null;
  return { cheap: window3(cheapPts, (a, b) => a < b), cheapTomorrow, dear };
}

function isNarrow() {
  return window.innerWidth < NARROW;
}

function plotWidth() {
  return document.getElementById('chart').clientWidth - (isNarrow() ? 42 : 62);
}

/** Axis ticks at local whole hours, as dense as the visible span allows. */
function tickValues(start, end) {
  const pxPerHour = plotWidth() / Math.max(1, (end - start) / 3600000);
  const stepH = [1, 3, 6, 12, 24].find((h) => h * pxPerHour >= 28) || 24;
  const out = [];
  for (let d = dayStart(start); d < end; d = nextDay(d)) {
    const next = nextDay(d);
    for (let ms = d; ms < next; ms += 3600000) {
      if (parts(ms).h % stepH === 0 && ms >= start && ms <= end) out.push(ms);
    }
  }
  return out;
}

function zoomRange(d) {
  if (state.zoom) return state.zoom;
  const now = Date.now();
  // mobile: start from yesterday; desktop: the whole window
  if (isNarrow()) return [Math.max(viewStart(d), dayStart(dayStart(now) - 3600000)), d.window.end];
  return [viewStart(d), d.window.end];
}

function renderChart() {
  const d = state.data;
  const s = state.settings;
  const el = document.getElementById('chart');
  if (!state.chart) {
    state.chart = echarts.init(el, null, { renderer: 'canvas' });
    let zoomTimer;
    state.chart.on('datazoom', () => {
      const dz = state.chart.getOption().dataZoom[0];
      state.zoom = [dz.startValue, dz.endValue];
      updateTicks();
      // day labels depend on the zoom; redraw when zooming stops
      clearTimeout(zoomTimer);
      zoomTimer = setTimeout(renderChart, 250);
    });
  }
  const now = Date.now();
  const res = activeRes();
  const step = res === '15' ? 900000 : 3600000;
  const pts = series(res);
  const ink2 = css('--ink-2');
  const muted = css('--muted');
  const grid = css('--grid');
  const axis = css('--axis');
  const total = totalMode();
  const confirmedEnd = d.confirmed_until || (pts.length ? pts[pts.length - 1].t + step : now);
  const out = [];

  // confirmed bars: spot coloured by level (+ fees stacked in total mode)
  out.push({
    name: t('confirmed'), type: 'bar', stack: total ? 'price' : undefined, barWidth: '78%', barGap: '-100%',
    data: pts.map((p) => {
      const c = spotC(p.v);
      return { value: [p.t + step / 2, c], itemStyle: { color: levelColor(level(c)), borderRadius: c >= 0 ? [2, 2, 0, 0] : [0, 0, 2, 2] } };
    }),
    emphasis: { disabled: true }, z: 2,
  });
  if (total) {
    out.push({
      name: t('fees'), type: 'bar', stack: 'price', barWidth: '78%',
      data: pts.map((p) => [p.t + step / 2, feesAt(p.t)]),
      itemStyle: { color: css('--fees'), decal: { symbol: 'rect', dashArrayX: [1, 0], dashArrayY: [2, 3], rotation: -Math.PI / 4, color: 'rgba(0,0,0,0.12)' } },
      emphasis: { disabled: true }, z: 2,
    });
  }
  // the same as a step line
  if (pts.length) {
    const line = pts.map((p) => [p.t, shown(p.t, p.v)]);
    line.push([pts[pts.length - 1].t + step, line[line.length - 1][1]]);
    out.push({
      name: total ? t('totalLine') : t('confirmed'), type: 'line', step: 'end', data: line, symbol: 'none',
      lineStyle: { color: total ? css('--ink') : ink2, width: total ? 1.4 : 1 }, z: 3, silent: true,
    });
  }

  // forecasts
  const fcLine = (f, name, color, extra = {}) => {
    const v = f.values.map(([ms, p]) => [ms, shown(ms, p)]);
    v.push([v[v.length - 1][0] + 3600000, v[v.length - 1][1]]);
    return { name, type: 'line', step: 'end', data: v, symbol: 'none', lineStyle: { color, width: 2, ...extra }, z: 4, silent: true };
  };
  const rapid = forecast('rapid');
  const daily = forecast('daily');
  const bandSrc = s.showBand ? [rapid && s.showRapid ? rapid : null, daily && s.showDaily ? daily : null].find(hasBand) : null;
  if (bandSrc) {
    const lo = [], diff = [];
    for (const [ms, p, l, h] of bandSrc.values) {
      if (l === null || l === undefined) continue;
      const a = shown(ms, l), b = shown(ms, h);
      lo.push([ms, a]);
      diff.push([ms, b - a]);
    }
    if (lo.length) {
      lo.push([lo[lo.length - 1][0] + 3600000, lo[lo.length - 1][1]]);
      diff.push([diff[diff.length - 1][0] + 3600000, diff[diff.length - 1][1]]);
      out.push({ type: 'line', step: 'end', stack: 'band', stackStrategy: 'all', data: lo, symbol: 'none', lineStyle: { opacity: 0 }, silent: true, z: 1 });
      out.push({ type: 'line', step: 'end', stack: 'band', stackStrategy: 'all', data: diff, symbol: 'none', lineStyle: { opacity: 0 },
        areaStyle: { color: css('--rapid'), opacity: 0.14 }, silent: true, z: 1 });
    }
  }
  if (daily && s.showDaily) out.push(fcLine(daily, t('daily'), css('--daily'), { type: [4, 3], width: 1.6 }));
  if (rapid && s.showRapid) out.push(fcLine(rapid, t('rapid'), css('--rapid')));
  if (s.showEarlier) {
    for (const f of d.earlier_forecasts || []) {
      const p = parts(f.issued_at);
      const line = fcLine(f, `${t('forecastIssued')} ${p.d}.${p.mo}. ${pad(p.h)}:${pad(p.mi)}`, css('--earlier'), { width: 1.6 });
      line.z = 2.5;
      out.push(line);
    }
  }

  // helper series for day labels, zones, the now line and the 3 h windows
  const days = [];
  for (let ms = viewStart(d); ms < d.window.end; ms = nextDay(ms)) days.push(ms);
  const [z0, z1] = zoomRange(d);
  const pxPerMs = plotWidth() / Math.max(1, z1 - z0);
  const markAreas = days.map((ms) => [{
    xAxis: ms, itemStyle: { color: 'transparent' },
    label: {
      // only label days with enough visible room
      show: (Math.min(nextDay(ms), z1) - Math.max(ms, z0)) * pxPerMs >= (isNarrow() ? 56 : 64), position: 'top', formatter: dayLabel(ms, now), color: [t('todayWord'), t('tomorrowWord')].includes(dayLabel(ms, now)) ? css('--ink') : ink2,
      fontWeight: [t('todayWord'), t('tomorrowWord')].includes(dayLabel(ms, now)) ? 'bold' : 'normal', fontSize: isNarrow() ? 10 : 12,
    },
  }, { xAxis: Math.min(nextDay(ms), d.window.end) }]);
  if ((rapid && s.showRapid) || (daily && s.showDaily)) {
    markAreas.push([{ xAxis: confirmedEnd, itemStyle: { color: css('--fc-zone') },
      label: { show: true, position: 'insideTopLeft', formatter: t('forecastZone'), color: ink2, fontStyle: 'italic' } },
    { xAxis: d.window.end }]);
  }
  const { cheap, dear } = windows();
  for (const [win, color] of [[cheap, css('--cheap')], [dear, css('--dear')]]) {
    if (!win) continue;
    markAreas.push([{ xAxis: win.start, itemStyle: { color, opacity: 0.1, borderColor: color, borderWidth: 1, borderType: 'dashed' } },
      { xAxis: win.end }]);
  }
  const markLines = days.slice(1).map((ms) => ({ xAxis: ms, lineStyle: { color: axis, type: 'solid', width: 1 }, label: { show: false } }));
  if (now >= d.window.start && now < d.window.end) {
    markLines.push({ xAxis: now, lineStyle: { color: css('--ink'), type: 'solid', width: 1.4 },
      label: { show: true, formatter: `${t('now')} ${hhmm(now)}`, position: 'insideEndTop', color: css('--ink'), fontSize: 11 } });
  }
  for (const lim of LIMITS.slice(1)) {
    markLines.push({ yAxis: lim, lineStyle: { color: grid, type: 'solid', width: 1 }, label: { show: false } });
  }
  out.push({
    type: 'line', data: [], silent: true,
    markArea: { silent: true, data: markAreas },
    markLine: { silent: true, symbol: 'none', data: markLines, animation: false },
  });

  state.chart.setOption({
    animation: false,
    backgroundColor: 'transparent',
    textStyle: { fontFamily: getComputedStyle(document.body).fontFamily },
    grid: { left: isNarrow() ? 34 : 46, right: isNarrow() ? 8 : 16, top: 30, bottom: isNarrow() ? 74 : 70 },
    tooltip: {
      trigger: 'axis', confine: true, axisPointer: { type: 'line', lineStyle: { color: muted } },
      backgroundColor: css('--surface'), borderColor: css('--border'), textStyle: { color: css('--ink'), fontSize: 12 },
      formatter: (params) => tooltipHtml(params[0]?.axisValue, res, step),
    },
    xAxis: {
      type: 'time', min: viewStart(d), max: d.window.end,
      axisLine: { show: false }, splitLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: muted, fontSize: 11, hideOverlap: true, formatter: (v) => pad(parts(v).h), customValues: tickValues(z0, z1) },
    },
    yAxis: {
      type: 'value', name: 'c/kWh', nameTextStyle: { color: muted, fontSize: 11, align: 'right' }, nameGap: 10,
      min: (v) => Math.min(0, Math.floor(v.min)), max: (v) => Math.ceil(Math.max(v.max, LIMITS[2]) / 5) * 5,
      splitLine: { show: false }, axisLabel: { color: muted, fontSize: 11 },
    },
    dataZoom: [
      { type: 'inside', startValue: z0, endValue: z1, minValueSpan: 6 * 3600000, filterMode: 'none' },
      { type: 'slider', startValue: z0, endValue: z1, height: 26, bottom: 10, filterMode: 'none', borderColor: css('--border'),
        fillerColor: 'rgba(31,95,139,0.12)', handleStyle: { color: css('--surface'), borderColor: css('--accent') },
        dataBackground: { lineStyle: { color: axis }, areaStyle: { color: axis } }, textStyle: { color: muted }, labelFormatter: (v) => `${dayLabel(v, now)} ${hhmm(v)}` },
    ],
    series: out,
  }, { notMerge: true });
  el.setAttribute('aria-label', `${t('title')}: ${dayLabel(viewStart(d), now)} – ${dayLabel(d.window.end - 1, now)}`);
}

function updateTicks() {
  if (!state.zoom) return;
  const [z0, z1] = state.zoom;
  state.chart.setOption({ xAxis: { axisLabel: { customValues: tickValues(z0, z1) } } });
}

function lookup(points, ms, step) {
  // points: [[t, v, ...]], sorted; value whose interval contains ms
  let lo = 0, hi = points.length - 1, found = null;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (points[mid][0] <= ms) { found = mid; lo = mid + 1; } else hi = mid - 1;
  }
  if (found === null || ms >= points[found][0] + step) return null;
  return points[found];
}

function tooltipHtml(ms, res, step) {
  if (ms === undefined) return '';
  const d = state.data;
  const s = state.settings;
  const rows = [];
  const esc = (x) => String(x).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
  const row = (color, label, value, dashed) => rows.push(
    `<div style="display:flex;gap:8px;align-items:center;justify-content:space-between"><span><i style="display:inline-block;width:10px;height:${dashed === 'line' ? 0 : 10}px;border-top:${dashed === 'line' ? '2px solid ' + color : '0'};background:${dashed === 'line' ? 'none' : color};border-radius:2px;margin-right:6px"></i>${esc(label)}</span><b>${esc(value)}</b></div>`);
  const p = lookup(d.prices[res] || [], ms, step);
  let start = Math.floor(ms / step) * step;
  if (p) {
    start = p[0];
    const c = spotC(p[1]);
    row(levelColor(level(c)), `${t('spot')} · ${t('levels')[level(c)]}`, `${fmt(c)} c/kWh`);
    if (totalMode()) {
      row(css('--fees'), t('fees'), `${fmt(feesAt(p[0]))} c/kWh`);
      row(css('--ink'), t('totalLine'), `${fmt(shown(p[0], p[1]))} c/kWh`, 'line');
    }
  } else {
    start = Math.floor(ms / 3600000) * 3600000;
  }
  const fcRow = (f, label, color) => {
    const v = lookup(f.values, ms, 3600000);
    if (!v) return;
    let txt = `${fmt(shown(v[0], v[1]))} c/kWh`;
    if (s.showBand && v.length >= 4 && v[2] !== null) txt += ` (${fmt(shown(v[0], v[2]), 1)}–${fmt(shown(v[0], v[3]), 1)})`;
    row(color, label, txt, 'line');
  };
  const rapid = forecast('rapid');
  const daily = forecast('daily');
  if (rapid && s.showRapid) fcRow(rapid, t('rapid'), css('--rapid'));
  if (daily && s.showDaily) fcRow(daily, t('daily'), css('--daily'));
  if (s.showEarlier) {
    for (const f of d.earlier_forecasts || []) {
      const ip = parts(f.issued_at);
      fcRow(f, `${t('forecastIssued')} ${ip.d}.${ip.mo}. ${pad(ip.h)}:${pad(ip.mi)}`, css('--earlier'));
    }
  }
  if (!rows.length) return '';
  const len = p ? step : 3600000;
  const head = `${dayLabel(start, Date.now())} ${hhmm(start)}–${hhmm(start + len)}`;
  return `<div style="font-weight:600;margin-bottom:4px">${esc(head)}</div>${rows.join('')}`;
}

function renderLegend() {
  const s = state.settings;
  const box = document.getElementById('legend');
  box.replaceChildren();
  const add = (cls, style, label) => {
    const span = document.createElement('span');
    const i = document.createElement('i');
    if (cls) i.className = cls;
    Object.assign(i.style, style);
    span.append(i, label);
    box.append(span);
  };
  const narrow = isNarrow();
  const ranges = ['< 0', '0–5', '5–10', '10–20', '20–30', '> 30'];
  LIMITS.concat([Infinity]).forEach((_, i) => {
    add('', { background: levelColor(i) }, narrow ? ranges[i] : `${t('levels')[i]} ${ranges[i]}`);
  });
  if (totalMode()) {
    add('hatch', {}, t('fees'));
    add('line', { borderColor: css('--ink') }, t('totalLine'));
  }
  if (forecast('rapid') && s.showRapid) add('line', { borderColor: css('--rapid') }, t('rapid'));
  if (forecast('daily') && s.showDaily) add('line dash', { borderColor: css('--daily') }, t('daily'));
  if (s.showEarlier && state.data.earlier_forecasts?.length) add('line', { borderColor: css('--earlier') }, t('earlier'));
  const { cheap, dear } = windows();
  if (cheap) add('zone', { background: css('--cheap') + '22', borderColor: css('--cheap') }, t('cheapWin'));
  if (dear) add('zone', { background: css('--dear') + '22', borderColor: css('--dear') }, t('dearWin'));
}

function renderHeatmap() {
  const d = state.data;
  if (!d.prices['60']) return;
  const el = document.getElementById('heatmap');
  if (!state.heatmap) state.heatmap = echarts.init(el, null, { renderer: 'canvas' });
  const now = Date.now();
  const s = state.settings;
  // rows: days in the window; columns: local hours. The repeated hour of the
  // DST change day is shown as the mean of the two hours.
  const days = [];
  for (let ms = viewStart(d); ms < d.window.end; ms = nextDay(ms)) days.push(ms);
  const cells = new Map();
  const put = (ms, v, fc) => {
    const p = parts(ms);
    const key = `${dayKey(ms)}|${p.h}`;
    const c = cells.get(key) || { sum: 0, n: 0, fc, day: dayKey(ms), h: p.h, raw: [] };
    c.sum += v; c.n += 1; c.raw.push([ms, v]);
    cells.set(key, c);
  };
  for (const [ms, v] of d.prices['60']) put(ms, shown(ms, v), false);
  const f = (s.showRapid && forecast('rapid')) || (s.showDaily && forecast('daily'));
  const confirmedEnd = d.confirmed_until || 0;
  if (f) for (const [ms, v] of f.values) if (ms >= confirmedEnd) put(ms, shown(ms, v), true);
  const dayIdx = new Map(days.map((ms, i) => [dayKey(ms), i]));
  const conf = [], fc = [];
  for (const c of cells.values()) {
    if (!dayIdx.has(c.day)) continue;
    const v = c.sum / c.n;
    const spot = totalMode() ? v - feesAt(c.raw[0][0]) : v;
    const item = { value: [c.h, dayIdx.get(c.day), v], raw: c.raw, itemStyle: { color: levelColor(level(spot)) } };
    (c.fc ? fc : conf).push(item);
  }
  const narrow = isNarrow();
  const cellW = (el.clientWidth - (narrow ? 70 : 120)) / 24;
  const labelShow = cellW >= 22;
  const ylabels = days.map((ms) => {
    const p = parts(ms);
    const base = `${t('weekdays')[p.wd]} ${p.d}.${p.mo}.`;
    return dayKey(ms) === dayKey(now) ? `{b|${base}}` : base;
  });
  const lbl = (dark) => ({
    show: labelShow, fontSize: 10, formatter: (prm) => fmt(prm.value[2], 0),
    color: dark ? css('--ink-2') : '#fff', fontStyle: dark ? 'italic' : 'normal',
  });
  el.style.height = `${Math.max(220, days.length * (narrow ? 26 : 32) + 50)}px`;
  state.heatmap.resize();
  state.heatmap.setOption({
    animation: false,
    textStyle: { fontFamily: getComputedStyle(document.body).fontFamily },
    grid: { left: narrow ? 62 : 110, right: 8, top: 4, bottom: 24 },
    tooltip: {
      confine: true, backgroundColor: css('--surface'), borderColor: css('--border'), textStyle: { color: css('--ink'), fontSize: 12 },
      formatter: (prm) => {
        const rows = prm.data.raw.map(([ms, v]) => `${hhmm(ms)}–${hhmm(ms + 3600000)} <b>${fmt(v)}</b> c/kWh`);
        const tag = prm.seriesIndex === 1 ? ` (${t('forecastZone')})` : '';
        return `${dayLabel(prm.data.raw[0][0], now)}${tag}<br>${rows.join('<br>')}`;
      },
    },
    xAxis: { type: 'category', data: Array.from({ length: 24 }, (_, h) => pad(h)), position: 'bottom',
      axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: css('--muted'), fontSize: 10, interval: narrow ? 2 : 0 }, splitArea: { show: false } },
    yAxis: { type: 'category', data: ylabels, inverse: true, axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: css('--ink-2'), fontSize: narrow ? 10 : 12, rich: { b: { fontWeight: 'bold', color: css('--ink') } } } },
    series: [
      { type: 'heatmap', data: conf, label: lbl(false), itemStyle: { borderColor: css('--surface'), borderWidth: 2, borderRadius: 2 }, emphasis: { disabled: true } },
      { type: 'heatmap', data: fc, label: lbl(true), itemStyle: { borderColor: css('--surface'), borderWidth: 2, borderRadius: 2, opacity: 0.4 }, emphasis: { disabled: true } },
    ],
  }, { notMerge: true });
}

function renderFooter() {
  const d = state.data;
  const g = parts(d.generated_at);
  const bits = [`${t('updated')} ${g.d}.${g.mo}. ${pad(g.h)}:${pad(g.mi)}`];
  if (d.sources?.prices?.length) bits.push(`${t('pricesFrom')}: ${d.sources.prices.map((x) => SOURCE_NAMES[x] || x).join(', ')}`);
  if (d.sources?.forecasts?.length) bits.push(`${t('forecastFrom')}: ${d.sources.forecasts.map((x) => SOURCE_NAMES[x] || x).join(', ')}`);
  document.getElementById('footer').textContent = bits.join(' · ');
}

// ---- Events ----------------------------------------------------------------

function bindControls() {
  for (const group of document.querySelectorAll('.seg[data-setting]')) {
    group.addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (b && !b.disabled) setSetting(group.dataset.setting, b.value);
    });
  }
  for (const input of document.querySelectorAll('input[data-setting]')) {
    const key = input.dataset.setting;
    if (input.type === 'checkbox') {
      input.addEventListener('change', () => setSetting(key, input.checked));
    } else {
      input.addEventListener('change', () => {
        let v = parseNum(input.value);
        if (key === 'dayStart' || key === 'dayEnd') v = Math.max(0, Math.min(key === 'dayEnd' ? 24 : 23, Math.round(v)));
        setSetting(key, NUMERIC.includes(key) ? v : input.value);
        if (!hasFees() && state.settings.priceMode !== 'spot') setSetting('priceMode', 'spot');
      });
    }
  }
  const dialog = document.getElementById('settings');
  document.getElementById('open-settings').addEventListener('click', () => dialog.showModal());
  dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });
  document.getElementById('reset-settings').addEventListener('click', () => {
    state.settings = { ...DEFAULTS };
    state.zoom = null;
    saveSettings();
    applyTheme();
    render();
  });
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      state.chart?.resize();
      if (state.data) render();
    }, 150);
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => render());
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
}

applyTheme();
bindControls();
renderStatic();
load();
setInterval(load, REFRESH_MS);
setInterval(() => { if (state.data && !document.hidden) render(); }, 60 * 1000);
