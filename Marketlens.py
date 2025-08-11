# ─────────────────────────────────────────────────────────────────────────────
# PART 1/3 — APP SHELL, THEME, NAVIGATION (ES-based SPX dashboard)
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import os
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf

# --- App identity ---
APP_NAME = "MarketLens Pro"
COMPANY = "Quantum Trading Systems"
VERSION = "4.2.0"

# --- Timezones ---
CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

# --- Trading clock (RTH for SPX cash display) ---
RTH_START, RTH_END = time(8, 30), time(15, 0)  # CT (08:30–15:00) shown on forecast table

# --- Futures anchor bar (daily Globex reopen) ---
ANCHOR_CT = time(17, 0)  # 5:00 PM CT (resumption)
ANCHOR_WINDOW_MIN = 30   # use the 30-minute bar starting at 17:00 CT

# --- Slopes (per 30-minute block) ---
SLOPE_UP_PER_BLOCK = +0.3171   # from 5pm high
SLOPE_DOWN_PER_BLOCK = -0.3171 # from 5pm low

# --- UI: minimal professional CSS ---
BASE_CSS = """
<style>
/* Minimal pro theme */
html, body, .stApp { background: #0B0D11; color: #E6E8EB; }
:root {
  --primary:#4DA3FF; --secondary:#7BD1FF; --success:#34C759; --warn:#FFB020; --error:#FF5A5F;
  --surface:#12161C; --card:#0F1318; --border:rgba(255,255,255,0.08);
  --r:14px; --pad:16px;
}
#MainMenu, header[data-testid="stHeader"], footer { display:none; }
.block-container { padding-top: 1.2rem; }
.h-hero {
  background: linear-gradient(90deg, #0F1318, #12161C);
  border:1px solid var(--border); border-radius:18px; padding:28px 20px; margin-bottom:20px;
}
.h-title { font-weight:800; font-size:1.4rem; color:#fff; letter-spacing:-0.01em; }
.h-sub { color:#A7B0BB; font-size:0.95rem; margin-top:4px; }
.card {
  background:var(--card); border:1px solid var(--border); border-radius:16px; padding:18px; margin:10px 0;
}
.kpi { display:flex; gap:8px; align-items:baseline; }
.kpi .v { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
          font-size:1.15rem; font-weight:700; color:#fff; }
.kpi .l { color:#9AA4AE; font-size:0.85rem; }
.badge { display:inline-block; padding:6px 10px; border-radius:24px; font-weight:600; font-size:0.85rem; }
.badge.ok { background:rgba(52,199,89,0.1); color:#34C759; border:1px solid rgba(52,199,89,0.25); }
.badge.neu { background:rgba(125,138,150,0.12); color:#B4BEC9; border:1px solid rgba(180,190,201,0.18); }
.grid { display:grid; gap:12px; }
@media (min-width: 980px) { .grid.cols-2 { grid-template-columns: 1fr 1fr; } .grid.cols-3 { grid-template-columns: 1fr 1fr 1fr; } }
.table-note { color:#9AA4AE; font-size:0.85rem; margin-top:8px; }
</style>
"""

st.set_page_config(
    page_title=f"{APP_NAME} — SPX",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(BASE_CSS, unsafe_allow_html=True)

# ---------------- Sidebar: Navigation only ----------------
with st.sidebar:
    st.markdown("### Navigation")
    page = st.radio(
        " ",
        ["SPX (via ES futures)", "AAPL", "META", "NVDA", "More (coming soon)"],
        label_visibility="collapsed",
        index=0,
    )

# ---------------- Hero ----------------
st.markdown(
    f"""
<div class="h-hero">
  <div class="h-title">{APP_NAME}</div>
  <div class="h-sub">Professional SPX (cash-aligned) using ES futures 5:00 PM CT anchor • v{VERSION}</div>
</div>
""",
    unsafe_allow_html=True,
)

# Router hint — the SPX page renders in Part 3 below.
# AAPL/META/NVDA are placeholders for now (we’ll wire them in later parts).
if page != "SPX (via ES futures)":
    st.info("Stock dashboards will be added after we lock SPX/ES. Use the sidebar to return to SPX.")
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# PART 2/3 — DATA LAYER (yfinance), TIME SLOTS, ANCHOR + SPX ALIGNMENT
# ─────────────────────────────────────────────────────────────────────────────

# ----- time helpers -----
def _dt_ct(d: date, t: time) -> datetime:
    return datetime.combine(d, t).replace(tzinfo=CT)

def make_slots(start: time, end: time, step_min: int = 30) -> list[str]:
    cur = _dt_ct(date(2025, 1, 1), start)
    stop = _dt_ct(date(2025, 1, 1), end)
    out: list[str] = []
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return out

RTH_SLOTS = make_slots(RTH_START, RTH_END)  # for display

def blocks_between_30m(t1: datetime, t2: datetime) -> int:
    """Number of 30-min blocks between t1 -> t2, right-open. Times must be tz-aware CT."""
    if t2 < t1:
        t1, t2 = t2, t1
    delta = t2 - t1
    return int(np.floor(delta.total_seconds() / 1800.0 + 1e-9))


# ----- yfinance fetches (ES=F, ^GSPC) -----
@st.cache_data(ttl=180)
def yf_intraday(symbol: str, start_dt_ct: datetime, end_dt_ct: datetime, interval: str = "1m") -> pd.DataFrame:
    """
    Minute data from yfinance (last 7 days supported for 1m). Returns CT tz.
    """
    # yfinance expects naive UTC or aware UTC. Convert CT -> UTC-naive for download, then re-tz to CT.
    start_utc = start_dt_ct.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_dt_ct.astimezone(timezone.utc).replace(tzinfo=None)

    df = yf.download(
        symbol,
        start=start_utc,
        end=end_utc,
        interval=interval,
        progress=False,
        auto_adjust=False,
        prepost=True,
        threads=True,
    )
    if df is None or df.empty:
        return pd.DataFrame()

    # yfinance index is tz-aware UTC; ensure and convert
    if df.index.tz is None:
        df.index = df.index.tz_localize(timezone.utc)

    df.index = df.index.tz_convert(CT)
    df = df.rename(columns=str.title).reset_index().rename(columns={"Datetime": "Dt"})
    # Keep only essential OHLC
    keep = [c for c in ["Dt", "Open", "High", "Low", "Close"] if c in df.columns]
    return df[keep].sort_values("Dt")


def resample_30m(df_1m: pd.DataFrame) -> pd.DataFrame:
    if df_1m.empty:
        return df_1m
    g = df_1m.set_index("Dt")[["Open", "High", "Low", "Close"]].resample("30min", label="right", closed="right").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    )
    g = g.dropna(subset=["Open", "High", "Low", "Close"]).reset_index()
    g["Time"] = g["Dt"].dt.strftime("%H:%M")
    return g


@st.cache_data(ttl=60)
def latest_quotes_es_spx() -> dict:
    """
    Get the latest ES and SPX prints to infer a live cash alignment offset (SPX - ES).
    """
    now = datetime.now(tz=CT)
    start = now - timedelta(minutes=90)
    es = yf_intraday("ES=F", start, now, interval="1m")
    spx = yf_intraday("^GSPC", start, now, interval="1m")
    es_last = float(es["Close"].iloc[-1]) if not es.empty else np.nan
    spx_last = float(spx["Close"].iloc[-1]) if not spx.empty else np.nan
    spread = spx_last - es_last if (np.isfinite(es_last) and np.isfinite(spx_last)) else 0.0
    return {"es_last": es_last, "spx_last": spx_last, "spread": spread}


# ----- ES 5:00 PM CT anchor bar (17:00–17:29) -----
@st.cache_data(ttl=180)
def es_get_5pm_anchor(forecast: date) -> dict | None:
    """
    Use the ES=F 30-min bar that STARTS at 17:00 CT of the calendar day BEFORE the forecast session.
    That bar’s High (anchor_up) and Low (anchor_dn) are used.
    """
    # For a forecast session D (cash RTH next morning), we want the 17:00 CT bar on D-1.
    d_prev = forecast - timedelta(days=1)
    start_ct = _dt_ct(d_prev, time(16, 30))
    end_ct = _dt_ct(d_prev, time(18, 30))

    raw = yf_intraday("ES=F", start_ct, end_ct, interval="1m")
    if raw.empty:
        return None

    bars30 = resample_30m(raw)
    # pick the bar whose Dt hour/min == 17:30 close, meaning it covers 17:00–17:29 (right-closed at 17:30)
    # safer: choose row where Dt is between 17:30 exclusive boundary? We check Time == "17:30"
    bar = bars30[bars30["Time"] == "17:30"]
    if bar.empty:
        # fallback: nearest between 17:00–17:45
        mask = (bars30["Dt"].dt.hour == 17)
        bar = bars30[mask].iloc[-1:] if mask.any() else pd.DataFrame()

    if bar.empty:
        return None

    row = bar.iloc[0]
    return {
        "anchor_dt": row["Dt"],      # 17:30 close time of 17:00–17:29 bar
        "anchor_high": float(row["High"]),
        "anchor_low": float(row["Low"]),
    }


# ----- Project lines in SPX cash-aligned space -----
def project_spx_lines(forecast: date, slope_up: float, slope_dn: float) -> tuple[pd.DataFrame, dict] | tuple[None, None]:
    """
    Build RTH slots for the forecast session; project Upper from 5pm High using +slope_up,
    and Lower from 5pm Low using slope_dn (negative).
    Then add a live spread so values are in **SPX cash-aligned** space.
    """
    anchors = es_get_5pm_anchor(forecast)
    if not anchors:
        return None, None

    live = latest_quotes_es_spx()
    spread = live.get("spread", 0.0) or 0.0

    # Anchor base times: the bar closed at ~17:30 for the 17:00–17:29 window; use the bar START time for blocks
    base_dt = anchors["anchor_dt"] - timedelta(minutes=30)  # 17:00 CT start

    rows = []
    for s in RTH_SLOTS:
        hh, mm = map(int, s.split(":"))
        target_dt = _dt_ct(forecast, time(hh, mm))
        b = blocks_between_30m(base_dt, target_dt)

        upper = anchors["anchor_high"] + slope_up * b
        lower = anchors["anchor_low"] + slope_dn * b

        # Cash align silently
        upper_spx = upper + spread
        lower_spx = lower + spread

        rows.append({"Time": s, "Lower": round(lower_spx, 2), "Upper": round(upper_spx, 2), "Blocks": b})

    df = pd.DataFrame(rows)
    meta = {
        "anchor_start": base_dt,
        "anchor_high": anchors["anchor_high"],
        "anchor_low": anchors["anchor_low"],
        "spread_used": spread,
        "es_last": latest_quotes_es_spx().get("es_last"),
        "spx_last": latest_quotes_es_spx().get("spx_last"),
    }
    return df, meta


# ─────────────────────────────────────────────────────────────────────────────
# PART 3/3 — SPX (via ES) PAGE: ANCHORS + FORECAST TABLE
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("#### SPX (cash-aligned) via ES Futures — 5:00 PM CT Anchor")

# Controls (top of page)
colA, colB, colC = st.columns([1, 1, 1])
with colA:
    forecast_date = st.date_input("Target Session (SPX RTH)", value=date.today(), help="Choose the cash session to project.")
with colB:
    slope_up = st.number_input("Slope from 5PM High (per 30m)", value=SLOPE_UP_PER_BLOCK, step=0.001, format="%.4f")
with colC:
    slope_dn = st.number_input("Slope from 5PM Low (per 30m)", value=SLOPE_DOWN_PER_BLOCK, step=0.001, format="%.4f")

# Build forecast now
with st.spinner("Computing anchors and projections…"):
    table, meta = project_spx_lines(forecast_date, slope_up, slope_dn)

if table is None or table.empty:
    st.warning("Couldn’t build the 5:00 PM CT anchor from ES. Try another date (or verify yfinance is reachable).")
    st.stop()

# Anchor Tiles
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("**5:00 PM CT Bar**")
    st.markdown(
        f"""<div class="kpi"><div class="v">{meta['anchor_start'].strftime('%b %d, %Y • %H:%M CT')}</div>
             <div class="l">Anchor Start</div></div>""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("**Anchor High / Low (ES)**")
    st.markdown(
        f"""<div class="kpi"><div class="v">{meta['anchor_high']:.2f}</div><div class="l">High</div></div>
            <div class="kpi"><div class="v">{meta['anchor_low']:.2f}</div><div class="l">Low</div></div>""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

with col3:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("**Cash Alignment**")
    sp = meta.get("spread_used", 0.0)
    badge = "ok" if abs(sp) < 10 else "neu"
    st.markdown(
        f"""<div class="kpi"><div class="v">{sp:+.2f}</div><div class="l">SPX − ES</div></div>
             <div class="badge {badge}">Applied silently to lines</div>""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

# Forecast table (SPX cash-aligned)
st.markdown("### Forecast Lines (SPX cash-aligned)")
st.dataframe(
    table[["Time", "Lower", "Upper"]],
    use_container_width=True,
    hide_index=True,
    column_config={
        "Time": st.column_config.TextColumn("Time"),
        "Lower": st.column_config.NumberColumn("Lower ($)", format="$%.2f"),
        "Upper": st.column_config.NumberColumn("Upper ($)", format="$%.2f"),
    },
)
st.markdown(
    '<div class="table-note">Values are projected from ES 5:00 PM CT bar and offset to current SPX cash.</div>',
    unsafe_allow_html=True,
)

# Lightweight RTH open status (optional)
open_row = table.loc[table["Time"] == "08:30"]
if not open_row.empty:
    lo, up = float(open_row["Lower"].iloc[0]), float(open_row["Upper"].iloc[0])
    colx, coly = st.columns([1, 1])
    with colx:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**08:30 CT Opening Channel**")
        st.markdown(
            f"""<div class="kpi"><div class="v">${lo:.2f} — ${up:.2f}</div><div class="l">Lower — Upper</div></div>""",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
    with coly:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Blocks to Close**")
        last_row = table.iloc[-1]
        blocks_to_close = int(last_row["Blocks"]) - int(open_row["Blocks"].iloc[0])
        st.markdown(
            f"""<div class="kpi"><div class="v">{blocks_to_close}</div><div class="l">x 30-min blocks</div></div>""",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
