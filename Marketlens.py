# ================================
# === PART 1 — CORE & HELPERS ===
# ================================
# MarketLens Pro (ES→SPX scaffolding)
# - Uses ES=F for the 5:00 PM CT anchor bar (17:00–17:29, bar end at ~17:30)
# - Projects simple up/down lines from that bar's High/Low
# - No volume, minimal deps, robust yfinance handling

import warnings
warnings.filterwarnings("ignore")

import textwrap
from datetime import datetime, date, time, timedelta, timezone

import pandas as pd
import yfinance as yf
import streamlit as st

# ---------- App constants ----------
APP_NAME = "MarketLens Pro"
COMPANY = "Quantum Trading Systems"
VERSION = "5.0.0"

# Time zones
CT = timezone(timedelta(hours=-6))   # America/Chicago (fixed offset; fine for intraday scaffolding)
ET = timezone(timedelta(hours=-5))   # America/New_York (fixed offset)

# RTH window for display (CT)
RTH_START, RTH_END = time(8, 30), time(14, 30)

# Default slopes (user-tweakable in UI later)
DEFAULT_SLOPE_UP = 0.3171   # per 30m block from 5pm High
DEFAULT_SLOPE_DN = -0.3171  # per 30m block from 5pm Low

# ---------- Premium minimal CSS (no banners, no volume) ----------
BASE_CSS = """
<style>
#MainMenu, footer, header[data-testid="stHeader"]{display:none!important;}
:root{
  --primary:#007AFF; --secondary:#5AC8FA;
  --success:#34C759; --warning:#FF9500; --error:#FF3B30;
  --bg:#FFFFFF; --panel:#FFFFFF; --border:rgba(0,0,0,0.08);
  --text:#0B0B0C; --muted:#60636B;
  --radius:16px; --shadow:0 10px 20px rgba(0,0,0,0.06);
}
.stApp{background:linear-gradient(135deg,#fff 0%, #F2F2F7 100%);}
.card{background:var(--panel); border:1px solid var(--border); border-radius:var(--radius);
      padding:18px; box-shadow:var(--shadow);}
.kpi{display:grid;gap:4px;}
.kpi .v{font:700 28px/1.1 ui-sans-serif,system-ui;letter-spacing:-0.02em}
.kpi .l{color:var(--muted);font-size:12px;text-transform:uppercase;}
.section{font:700 20px/1.2 ui-sans-serif,system-ui;margin:8px 0 12px;border-bottom:2px solid var(--primary);padding-bottom:6px;}
.hero{border-radius:24px;padding:26px;text-align:center;background:
      linear-gradient(135deg,#171A20 0%,#33363B 100%); color:#fff; box-shadow:var(--shadow);}
.hero .t{font-weight:800;font-size:28px;letter-spacing:-0.02em}
.hero .s{opacity:.8}
.badge{display:inline-block;padding:6px 10px;border-radius:999px;border:1px solid var(--border);}
</style>
"""

# ---------- Streamlit page config ----------
st.set_page_config(
    page_title=f"{APP_NAME} — ES Anchors",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(BASE_CSS, unsafe_allow_html=True)

# ---------- Small time helpers ----------
def dt_ct(d: date, t: time) -> datetime:
    return datetime(d.year, d.month, d.day, t.hour, t.minute, tzinfo=CT)

def blocks_between_30m(a: datetime, b: datetime) -> int:
    if b < a:
        a, b = b, a
    blocks, cur = 0, a
    while cur < b:
        blocks += 1
        cur += timedelta(minutes=30)
    return blocks

def make_slots(start: time = RTH_START, end: time = RTH_END, step_min: int = 30) -> list[str]:
    cur = datetime(2025, 1, 1, start.hour, start.minute)
    stop = datetime(2025, 1, 1, end.hour, end.minute)
    out = []
    while cur <= stop:
        out.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=step_min)
    return out

SLOTS_30 = make_slots()

# ---------- Robust yfinance pull (handles MultiIndex) ----------
@st.cache_data(ttl=180)
def yf_intraday(symbol: str, start_dt_ct: datetime, end_dt_ct: datetime, interval: str = "1m") -> pd.DataFrame:
    """
    Returns minute data with columns: Dt(CT tz), Open, High, Low, Close
    """
    start_utc = start_dt_ct.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_dt_ct.astimezone(timezone.utc).replace(tzinfo=None)

    df = yf.download(
        symbol,
        start=start_utc,
        end=end_utc,
        interval=interval,
        auto_adjust=False,
        prepost=True,
        progress=False,
        threads=True,
    )
    if df is None or df.empty:
        return pd.DataFrame(columns=["Dt", "Open", "High", "Low", "Close"])

    # Flatten MultiIndex if any
    if isinstance(df.columns, pd.MultiIndex):
        # Drop the last level (ticker) – we fetch one ticker per call
        df = df.droplevel(-1, axis=1)

    # Normalize names
    df = df.rename(columns={c: c.title() for c in df.columns})
    need = {"Open", "High", "Low", "Close"}
    if not need.issubset(set(df.columns)):
        return pd.DataFrame(columns=["Dt", "Open", "High", "Low", "Close"])

    if df.index.tz is None:
        df.index = df.index.tz_localize(timezone.utc)
    df.index = df.index.tz_convert(CT)

    out = df.reset_index().rename(columns={"Datetime": "Dt"})
    return out[["Dt", "Open", "High", "Low", "Close"]].sort_values("Dt")

def resample_30m(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    Right-closed 30m. Returns Dt(bar end, CT), Time, OHLC.
    """
    if df_1m is None or df_1m.empty:
        return pd.DataFrame(columns=["Dt", "Time", "Open", "High", "Low", "Close"])
    df = df_1m.copy()
    df["Dt"] = pd.to_datetime(df["Dt"])
    df = df.set_index("Dt")
    if df.index.tz is None:
        df.index = df.index.tz_localize(CT)

    g = df[["Open", "High", "Low", "Close"]].resample(
        "30min", label="right", closed="right"
    ).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last"})
    g = g.dropna(subset=["Open", "High", "Low", "Close"]).reset_index()
    g["Time"] = g["Dt"].dt.strftime("%H:%M")
    return g

@st.cache_data(ttl=300)
def es_get_5pm_anchor(forecast: date) -> dict | None:
    """
    Pick the bar covering 17:00–17:29 CT on the calendar day before forecast (bar end ~17:30).
    If exact 17:30 not present, take nearest 17:00–17:45 bar end.
    """
    d_prev = forecast - timedelta(days=1)
    start_ct = dt_ct(d_prev, time(16, 30))
    end_ct = dt_ct(d_prev, time(18, 30))

    raw = yf_intraday("ES=F", start_ct, end_ct, interval="1m")
    if raw.empty:
        return None
    bars30 = resample_30m(raw)
    if bars30.empty:
        return None

    pick = bars30[bars30["Time"] == "17:30"]
    if pick.empty:
        subset = bars30[bars30["Dt"].dt.hour == 17].copy()
        if subset.empty:
            subset = bars30.copy()
        subset["_diff"] = (subset["Dt"] - subset["Dt"].dt.normalize() - pd.Timedelta(hours=17, minutes=30)).abs()
        subset = subset.sort_values("_diff")
        pick = subset.iloc[:1]
    row = pick.iloc[0]
    return {
        "anchor_dt": row["Dt"],          # bar end (~17:30 CT)
        "anchor_high": float(row["High"]),
        "anchor_low": float(row["Low"]),
    }

# Simple projection helpers (no SPX conversion visible; ES drives the geometry)
def project_from_base(base_price: float, base_dt: datetime, target_dt: datetime, slope_per_30m: float) -> float:
    blocks = blocks_between_30m(base_dt, target_dt)
    return base_price + slope_per_30m * blocks

def project_day_lines(forecast: date, slope_up: float, slope_dn: float) -> tuple[pd.DataFrame, dict] | tuple[pd.DataFrame, None]:
    anchors = es_get_5pm_anchor(forecast)
    if not anchors:
        return pd.DataFrame(), None

    rows = []
    for s in SLOTS_30:
        hh, mm = map(int, s.split(":"))
        tdt = dt_ct(forecast, time(hh, mm))
        up = project_from_base(anchors["anchor_high"], anchors["anchor_dt"], tdt, slope_up)
        dn = project_from_base(anchors["anchor_low"], anchors["anchor_dt"], tdt, slope_dn)
        rows.append({"Time": s, "Lower": round(dn, 2), "Upper": round(up, 2)})

    meta = {
        "anchor_dt": anchors["anchor_dt"],
        "anchor_high": anchors["anchor_high"],
        "anchor_low": anchors["anchor_low"],
        "slope_up": slope_up,
        "slope_dn": slope_dn,
    }
    return pd.DataFrame(rows), meta

# ================================
# === PART 2 — LAYOUT & NAV  ====
# ================================

# Sidebar navigation and shared inputs (kept minimal & professional)

with st.sidebar:
    st.markdown(f"<div class='section'>Navigation</div>", unsafe_allow_html=True)
    page = st.radio(
        " ",
        options=["Overview", "Anchors", "Forecasts"],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown(f"<div class='section'>Session</div>", unsafe_allow_html=True)
    forecast_date = st.date_input(
        "Target session (CT)",
        value=date.today() + timedelta(days=1),
        help="Pick the RTH day to analyze (08:30–14:30 CT).",
    )

    st.markdown(f"<div class='section'>Slopes</div>", unsafe_allow_html=True)
    slope_up = st.number_input(
        "Slope ↑ per 30m",
        value=DEFAULT_SLOPE_UP,
        step=0.001,
        format="%.4f",
        help="Applied from the 5:00 PM CT bar HIGH."
    )
    slope_dn = st.number_input(
        "Slope ↓ per 30m",
        value=DEFAULT_SLOPE_DN,
        step=0.001,
        format="%.4f",
        help="Applied from the 5:00 PM CT bar LOW."
    )

# Hero
st.markdown(
    f"""
    <div class="hero">
      <div class="t">{APP_NAME}</div>
      <div class="s">Professional ES-anchored geometry for SPX workflows • v{VERSION}</div>
      <div class="s" style="margin-top:6px;opacity:.7">{COMPANY}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Overview page
if page == "Overview":
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("<div class='card kpi'><div class='v'>ES=F</div><div class='l'>Anchor Source</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='card kpi'><div class='v'>{forecast_date.strftime('%a %b %d')}</div><div class='l'>Session (CT)</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='card kpi'><div class='v'>{slope_up:+.4f}</div><div class='l'>Slope ↑ per 30m</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='section'>Notes</div>", unsafe_allow_html=True)
    st.markdown(
        textwrap.dedent("""
        - ES 5:00 PM CT (bar ending ~17:30) acts as the weekly anchor.
        - We project a simple **Upper** line from the anchor **High** and a **Lower** line from the anchor **Low**.
        - Slopes are per 30-minute block and user-tweakable.
        """).strip()
    )

# Helper to compute once for Anchors / Forecasts
def _ensure_projection(forecast_date: date, slope_up: float, slope_dn: float):
    table, meta = project_day_lines(forecast_date, slope_up, slope_dn)
    return table, meta

# ================================
# === PART 3 — PAGES (ES)     ===
# ================================

if page == "Anchors":
    st.markdown("<div class='section'>5:00 PM CT Anchor (Prior Day)</div>", unsafe_allow_html=True)
    table, meta = _ensure_projection(forecast_date, slope_up, slope_dn)
    if not meta:
        st.warning("Could not retrieve the ES 5:00 PM CT anchor. Try a different session date (or ensure data is recent).")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"<div class='card kpi'><div class='v'>{meta['anchor_dt'].strftime('%Y-%m-%d %H:%M')}</div><div class='l'>Anchor DT (CT)</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='card kpi'><div class='v'>{meta['anchor_high']:.2f}</div><div class='l'>Anchor High</div></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='card kpi'><div class='v'>{meta['anchor_low']:.2f}</div><div class='l'>Anchor Low</div></div>", unsafe_allow_html=True)

        st.markdown("<div class='card' style='margin-top:10px;'>The anchor bar is the 30-minute bar ending ~17:30 CT on the calendar day **before** the selected session.</div>", unsafe_allow_html=True)

elif page == "Forecasts":
    st.markdown("<div class='section'>Projected Lines (RTH 30-min)</div>", unsafe_allow_html=True)
    table, meta = _ensure_projection(forecast_date, slope_up, slope_dn)
    if table.empty or not meta:
        st.info("No projection available. Try a nearby date.")
    else:
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Time": st.column_config.TextColumn("Time", width="small"),
                "Lower": st.column_config.NumberColumn("Lower (ES-geom)", format="%.2f"),
                "Upper": st.column_config.NumberColumn("Upper (ES-geom)", format="%.2f"),
            },
        )

        rng = table["Upper"].max() - table["Lower"].min()
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"<div class='card kpi'><div class='v'>{rng:.2f}</div><div class='l'>Range</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='card kpi'><div class='v'>{meta['slope_up']:+.4f}</div><div class='l'>Slope ↑ / 30m</div></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='card kpi'><div class='v'>{meta['slope_dn']:+.4f}</div><div class='l'>Slope ↓ / 30m</div></div>", unsafe_allow_html=True)
