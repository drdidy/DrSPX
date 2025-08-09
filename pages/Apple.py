# pages/Apple.py
from __future__ import annotations
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import io, zipfile, textwrap
import pandas as pd
import streamlit as st

# ───────────────────────── App Meta / Timezones ─────────────────────────
APP_NAME = "MarketLens"
PAGE_NAME = "Apple"
CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

SLOPE_PER_BLOCK = 0.03545                 # fixed ascending slope per 30-min
RTH_START, RTH_END = time(8,30), time(14,30)  # CT trading window

# ────────────────────────── Minimal Professional UI ──────────────────────────
st.markdown("""
<style>
:root{
  --surface:#F7F8FA; --card:#FFFFFF; --border:#E6E9EF; --text:#0F172A; --muted:#62708A;
  --accent:#2A6CFB; --good:#16A34A; --bad:#DC2626; --neutral:#334155;
  --radius:14px; --shadow:0 10px 26px rgba(16,24,40,.06);
}
html,body,.stApp{font-family:Inter,-apple-system,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
.stApp{background:var(--surface); color:var(--text);} #MainMenu, footer, .stDeployButton{display:none!important;}

.header-wrap{position:sticky; top:0; z-index:10; background:linear-gradient(180deg,#fff,#FFFFFFEE);
             border-bottom:1px solid var(--border); margin-bottom:12px;}
.hero{display:flex; align-items:center; gap:12px; padding:12px 8px; max-width:1200px; margin:0 auto;}
.logo{width:34px; height:34px; border-radius:10px; display:flex; align-items:center; justify-content:center;
      background:#0F172A; color:#FFFFFF; font-size:20px; font-weight:800; box-shadow:var(--shadow);}
.brand{font-weight:800; font-size:1.2rem; letter-spacing:.2px}
.tag{color:var(--muted); font-size:.95rem}

.card{ background:var(--card); border:1px solid var(--border); border-radius:14px;
       box-shadow:var(--shadow); padding:14px; margin:12px 0;}
.hline{height:1px; background:#EEF1F6; margin:8px 0 12px 0}
.section{font-weight:700}

.tilegrid{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.tile{border:1px solid var(--border);border-radius:16px;padding:12px 14px;background:linear-gradient(180deg,#fff,#F7F8FA)}
.tl{font-size:.9rem;color:var(--muted)} .tv{font-size:1.6rem;font-weight:800}

.badge{display:inline-flex;align-items:center;gap:.5rem;border-radius:999px;padding:.35rem .7rem;
       font-weight:700;font-size:.9rem; border:1px solid;}
.badge.strong{background:#ECFDF5;border-color:#16A34A33;color:#0A7F36}
.badge.weak{background:#FEF2F2;border-color:#DC262633;color:#B42318}
.badge.neutral{background:#EEF2FF;border-color:#93C5FD66;color:#1E3A8A}

.pill{display:inline-flex;gap:.6rem;border:1px solid var(--border);border-radius:999px;padding:.35rem .7rem;background:#fff;font-weight:600;}
.small{font-size:.9rem;color:var(--muted)}
.note{font-size:.9rem;color:#475569}
.kbadge{display:inline-flex;align-items:center;gap:.4rem;border:1px solid var(--border);
        background:#fff;border-radius:999px;padding:.2rem .55rem;font-weight:650;font-size:.85rem;}
.kbadge.good{border-color:#16A34A33;background:#ECFDF5;color:#0A7F36}
.kbadge.warn{border-color:#F59E0B33;background:#FFFBEB;color:#B45309}
a.minilink{font-size:.9rem; color:#2A6CFB; text-decoration:none; margin-left:.5rem}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────── Data: Alpaca 1m ───────────────────────────
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

def _alpaca_client():
    return StockHistoricalDataClient(
        api_key=st.secrets["alpaca"]["key"],
        secret_key=st.secrets["alpaca"]["secret"]
    )

@st.cache_data(ttl=300)
def fetch_history_1m(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    client = _alpaca_client()
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,
        start=start_dt.astimezone(ET),
        end=end_dt.astimezone(ET),
        limit=10_000
    )
    bars = client.get_stock_bars(req)
    df = bars.df.reset_index()
    if df.empty:
        return pd.DataFrame()
    if "symbol" in df.columns:
        df = df[df["symbol"] == symbol]
    df.rename(columns={"timestamp":"dt","open":"Open","high":"High","low":"Low","close":"Close","volume":"Volume"}, inplace=True)
    df["dt"] = pd.to_datetime(df["dt"], utc=True).dt.tz_convert(CT)
    return df[["dt","Open","High","Low","Close","Volume"]].sort_values("dt")

def restrict_rth_30m(df_1m: pd.DataFrame) -> pd.DataFrame:
    if df_1m.empty: return df_1m
    df = df_1m.set_index("dt").sort_index()
    ohlc = df[["Open","High","Low","Close","Volume"]].resample("30min", label="right", closed="right").agg({
        "Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"
    }).dropna(subset=["Open","High","Low","Close"]).reset_index()
    ohlc["Time"] = ohlc["dt"].dt.strftime("%H:%M")
    ohlc = ohlc[(ohlc["Time"] >= "08:30") & (ohlc["Time"] <= "14:30")].copy()
    return ohlc

@st.cache_data(ttl=180)
def fetch_day_open(symbol: str, d: date) -> float | None:
    start_dt = datetime.combine(d, time(7,0), tzinfo=CT)
    end_dt   = datetime.combine(d, time(15,0), tzinfo=CT)
    df = fetch_history_1m(symbol, start_dt, end_dt)
    if df.empty: return None
    df = df.set_index("dt").sort_index()
    try:
        bar = df.loc[df.index.indexer_between_time("08:30","08:30")]
        if bar.empty: return None
        return float(bar.iloc[0]["Open"])
    except Exception:
        return None

# ─────────────────────────── Helpers ───────────────────────────
def make_slots(start: time, end: time, step_min: int = 30) -> list[str]:
    cur = datetime(2025,1,1,start.hour,start.minute)
    stop = datetime(2025,1,1,end.hour,end.minute)
    out=[]
    while cur <= stop:
        out.append(cur.strftime("%H:%M")); cur += timedelta(minutes=step_min)
    return out

SLOTS = make_slots(RTH_START, RTH_END)

def blocks_between(t1: datetime, t2: datetime) -> int:
    if t2 < t1: t1, t2 = t2, t1
    blocks, cur = 0, t1
    while cur < t2:
        if cur.hour != 16:
            blocks += 1
        cur += timedelta(minutes=30)
    return blocks

def project_line(base_price: float, base_dt: datetime, target_dt: datetime) -> float:
    return base_price + SLOPE_PER_BLOCK * blocks_between(base_dt, target_dt)

def week_mon_tue_fri_for(forecast: date) -> tuple[date, date, date]:
    mon = forecast - timedelta(days=forecast.weekday())
    tue = mon + timedelta(days=1)
    fri = mon + timedelta(days=4)
    if tue >= forecast:
        mon -= timedelta(days=7); tue -= timedelta(days=7); fri -= timedelta(days=7)
    return mon, tue, fri

@st.cache_data(ttl=600)
def compute_weekly_anchors(forecast: date):
    """Upper = max(Mon High, Tue High). Lower = min(Mon Low, Tue Low)."""
    mon, tue, _ = week_mon_tue_fri_for(forecast)
    start_dt = datetime.combine(mon, time(7,0), tzinfo=CT)
    end_dt   = datetime.combine(tue + timedelta(days=1), time(7,0), tzinfo=CT)
    raw = fetch_history_1m("AAPL", start_dt, end_dt)
    if raw.empty: return None
    raw["D"] = raw["dt"].dt.date
    mon_df = restrict_rth_30m(raw[raw["D"] == mon])
    tue_df = restrict_rth_30m(raw[raw["D"] == tue])
    if mon_df.empty or tue_df.empty: return None

    midx_hi = mon_df["High"].idxmax(); midx_lo = mon_df["Low"].idxmin()
    MonHigh = float(mon_df.loc[midx_hi,"High"]); MonLow = float(mon_df.loc[midx_lo,"Low"])
    MonHigh_t = mon_df.loc[midx_hi,"dt"].to_pydatetime(); MonLow_t = mon_df.loc[midx_lo,"dt"].to_pydatetime()

    tidx_hi = tue_df["High"].idxmax(); tidx_lo = tue_df["Low"].idxmin()
    TueHigh = float(tue_df.loc[tidx_hi,"High"]); TueLow = float(tue_df.loc[tidx_lo,"Low"])
    TueHigh_t = tue_df.loc[tidx_hi,"dt"].to_pydatetime(); TueLow_t = tue_df.loc[tidx_lo,"dt"].to_pydatetime()

    if TueHigh >= MonHigh:
        upper_price, upper_time = TueHigh, TueHigh_t
    else:
        upper_price, upper_time = MonHigh, MonHigh_t

    if TueLow <= MonLow:
        lower_price, lower_time = TueLow, TueLow_t
    else:
        lower_price, lower_time = MonLow, MonLow_t

    return {
        "mon_date": mon, "tue_date": tue,
        "MonHigh": MonHigh, "MonLow": MonLow, "TueHigh": TueHigh, "TueLow": TueLow,
        "upper_base_price": upper_price, "upper_base_time": upper_time,
        "lower_base_price": lower_price, "lower_base_time": lower_time,
    }

def channel_for_day(day: date, anchors: dict) -> pd.DataFrame:
    rows=[]
    for slot in SLOTS:
        h, m = map(int, slot.split(":"))
        tdt = datetime.combine(day, time(h,m), tzinfo=CT)
        up = project_line(anchors["upper_base_price"], anchors["upper_base_time"], tdt)
        lo = project_line(anchors["lower_base_price"], anchors["lower_base_time"], tdt)
        rows.append({"Time": slot, "UpperLine": round(up,2), "LowerLine": round(lo,2)})
    return pd.DataFrame(rows)

@st.cache_data(ttl=180)
def fetch_intraday_day_30m(symbol: str, d: date) -> pd.DataFrame:
    start_dt = datetime.combine(d, time(7,0), tzinfo=CT)
    end_dt   = datetime.combine(d, time(16,0), tzinfo=CT)
    df1m = fetch_history_1m(symbol, start_dt, end_dt)
    if df1m.empty: return pd.DataFrame()
    df30 = restrict_rth_30m(df1m)[["dt","Open","High","Low","Close","Volume"]].copy()
    df30["Time"] = df30["dt"].dt.strftime("%H:%M")
    return df30

# ───────────────────────── Sticky Header ─────────────────────────
st.markdown(
    f"""
<div class="header-wrap">
  <div class="hero">
    <div class="logo"></div>
    <div>
      <div class="brand">{APP_NAME} — {PAGE_NAME}</div>
      <div class="tag">Professional AAPL intraday prep</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# ───────────────────────── Sidebar ─────────────────────────
with st.sidebar:
    st.subheader("Session")
    forecast_date = st.date_input("Target session", value=date.today() + timedelta(days=1))
    colA, colB = st.columns(2)
    if colA.button("Today"):
        forecast_date = date.today()
    if colB.button("Next trading day"):
        wd = date.today().weekday()
        delta = 1 if wd < 4 else (7 - wd)
        forecast_date = date.today() + timedelta(days=delta)

    st.subheader("Detection")
    tol = st.slider("Touch tolerance (Δ vs line, $)", 0.01, 0.60, 0.05, 0.01)

# ─────────────────────── Anchors & Open Status ───────────────────────
wk = compute_weekly_anchors(forecast_date)
if not wk:
    st.warning("Could not compute Monday/Tuesday anchors for AAPL. Try another date.")
    st.stop()

st.markdown(
    f"""
<div class="card">
  <div class="tilegrid">
    <div class="tile">
      <div class="tl">Monday High / Low</div>
      <div class="tv" style="color:#16A34A">{wk['MonHigh']:.2f}</div>
      <div class="small">Low: {wk['MonLow']:.2f} • {wk['mon_date']}</div>
    </div>
    <div class="tile">
      <div class="tl">Tuesday High / Low</div>
      <div class="tv" style="color:#2A6CFB">{wk['TueHigh']:.2f}</div>
      <div class="small">Low: {wk['TueLow']:.2f} • {wk['tue_date']}</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

channel_df = channel_for_day(forecast_date, wk)

open_px = fetch_day_open("AAPL", forecast_date)
badge_html = '<span class="badge neutral">Open: Neutral</span>'
if open_px is not None and "08:30" in set(channel_df["Time"]):
    lower0830 = float(channel_df.loc[channel_df["Time"]=="08:30","LowerLine"].iloc[0])
    upper0830 = float(channel_df.loc[channel_df["Time"]=="08:30","UpperLine"].iloc[0])
    if open_px < lower0830:
        badge_html = '<span class="badge weak">Open: Weak (below channel)</span>'
    elif open_px > upper0830:
        badge_html = '<span class="badge strong">Open: Strong (above channel)</span>'
    else:
        badge_html = '<span class="badge neutral">Open: Neutral (inside channel)</span>'

def next_slot_label() -> str:
    now = datetime.now(tz=CT).strftime("%H:%M")
    for s in SLOTS:
        if s >= now:
            return s
    return SLOTS[0]

ns = next_slot_label()
ns_row = channel_df.loc[channel_df["Time"] == ns].iloc[0] if ns in set(channel_df["Time"]) else None
pill = ""
if ns_row is not None:
    pill = f'<span class="pill">Next {ns} → Lower {ns_row["LowerLine"]:.2f} • Upper {ns_row["UpperLine"]:.2f}</span>'

st.markdown(
    f"""
<div class="card">
  <div class="section">Session Status</div>
  <div class="hline"></div>
  {badge_html}
  <div style="margin-top:8px">{pill}</div>
</div>
""",
    unsafe_allow_html=True,
)

# ───────────── Soft pre-close alert: approaching a line (no streaming) ─────────────
def approaching_alert_for_current_bar(d: date, anchors: dict, tolerance: float) -> str | None:
    now_ct = datetime.now(tz=CT)
    if now_ct.date() != d: return None
    if not (RTH_START <= now_ct.time() <= RTH_END): return None
    # in last ~3 minutes of the current 30-min bar
    if now_ct.minute % 30 < 27: return None

    # Determine current slot end (the right-closed bar)
    minute_bucket = 30 if now_ct.minute >= 30 else 0
    slot_end = now_ct.replace(minute=30 if minute_bucket==30 else 0, second=0, microsecond=0)
    # If we're in the last minutes leading to the *next* slot end, preview that slot’s line values
    if now_ct.minute >= 27:
        # For preview, use the upcoming slot end (ceil to next :00/:30)
        add = 30 - (now_ct.minute % 30)
        slot_end = now_ct + timedelta(minutes=add)
        slot_end = slot_end.replace(second=0, microsecond=0)

    # Build line levels for that slot
    up = project_line(anchors["upper_base_price"], anchors["upper_base_time"], slot_end)
    lo = project_line(anchors["lower_base_price"], anchors["lower_base_time"], slot_end)

    # Pull last 1m price to approximate near-close
    start_dt = now_ct - timedelta(minutes=5)
    df = fetch_history_1m("AAPL", start_dt, now_ct + timedelta(minutes=1))
    if df.empty: return None
    px = float(df.iloc[-1]["Close"])

    note = []
    if abs(px - lo) <= tolerance:
        note.append(f"near Lower {lo:.2f} (Δ {px - lo:+.2f})")
    if abs(px - up) <= tolerance:
        note.append(f"near Upper {up:.2f} (Δ {px - up:+.2f})")
    if not note: return None
    return f'<span class="kbadge warn">Approaching: {" • ".join(note)}</span>'

alert_html = approaching_alert_for_current_bar(forecast_date, wk, tol)
if alert_html:
    st.markdown(f'<div class="card">{alert_html} <span class="small">— provisional; confirms on bar close</span></div>', unsafe_allow_html=True)

# ─────────────────────── Signals Table (Mon–Fri) ───────────────────────
def first_touch_close_above(day: date, anchors: dict, tolerance: float):
    """Return first event where bar touches a line AND closes above it.
       Touch: Low<=Line<=High ± tol. Close condition: Close>=Line."""
    intr = fetch_intraday_day_30m("AAPL", day)
    if intr.empty:
        return {"Day": day, "Time":"—", "Line":"—", "Close":"—", "Line Px":"—", "Δ":"—"}

    ch = channel_for_day(day, anchors)
    merged = pd.merge(intr, ch, on="Time", how="inner")

    for _, r in merged.iterrows():
        lo_line = r["LowerLine"]; hi_line = r["UpperLine"]
        lo, hi, close = r["Low"], r["High"], r["Close"]

        # Lower line: touch + close above
        if (lo - tolerance) <= lo_line <= (hi + tolerance) and close >= lo_line - 1e-9:
            delta = round(float(close - lo_line), 2)
            return {"Day": day, "Time": r["Time"], "Line": "Lower",
                    "Close": round(float(close),2), "Line Px": round(float(lo_line),2), "Δ": delta}

        # Upper line: touch + close above (breakout)
        if (lo - tolerance) <= hi_line <= (hi + tolerance) and close >= hi_line - 1e-9:
            delta = round(float(close - hi_line), 2)
            return {"Day": day, "Time": r["Time"], "Line": "Upper",
                    "Close": round(float(close),2), "Line Px": round(float(hi_line),2), "Δ": delta}

    return {"Day": day, "Time":"—", "Line":"—", "Close":"—", "Line Px":"—", "Δ":"—"}

def signals_mon_to_fri(forecast: date, anchors: dict, tolerance: float) -> pd.DataFrame:
    mon, _, _ = week_mon_tue_fri_for(forecast)
    days = [mon + timedelta(days=i) for i in range(5)]
    rows = [first_touch_close_above(d, anchors, tolerance) for d in days]
    df = pd.DataFrame(rows)
    df["Day"] = df["Day"].apply(lambda d: d.strftime("%a %Y-%m-%d") if isinstance(d, date) else d)
    return df

st.markdown('<div class="card"><div class="section">Signals (Mon–Fri): Touch + Close Above</div><div class="hline"></div>', unsafe_allow_html=True)
signals_df = signals_mon_to_fri(forecast_date, wk, tol)

def style_delta(s: pd.Series):
    styled=[]
    for v in s:
        if isinstance(v,(int,float)) and v == v:  # not NaN
            styled.append("color:#16A34A")  # positive = green; by definition close>=line
        else:
            styled.append("color:#334155")
    return styled

styled = signals_df.style.apply(style_delta, subset=["Δ"])
st.dataframe(styled, use_container_width=True, hide_index=True)

buf_sig = io.StringIO(); signals_df.to_csv(buf_sig, index=False)
st.download_button("Download Signals (CSV)", data=buf_sig.getvalue(),
                   file_name=f"AAPL_Signals_{wk['mon_date']}_{wk['tue_date']}.csv", mime="text/csv")
st.markdown('</div>', unsafe_allow_html=True)

# ───────────────────── Daily Line Schedule + Export ─────────────────────
st.markdown('<div class="card"><div class="section">Daily Line Schedule</div><div class="hline"></div>', unsafe_allow_html=True)
st.dataframe(channel_df[["Time","LowerLine","UpperLine"]], use_container_width=True, hide_index=True)

zipbuf = io.BytesIO()
with zipfile.ZipFile(zipbuf, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(f"AAPL_Channel_{forecast_date}.csv", channel_df.to_csv(index=False))
    intraday30 = fetch_intraday_day_30m("AAPL", forecast_date)
    if not intraday30.empty:
        zf.writestr(f"AAPL_Intraday30_{forecast_date}.csv", intraday30.to_csv(index=False))
    zf.writestr(f"AAPL_Signals_{wk['mon_date']}_{wk['tue_date']}.csv", signals_df.to_csv(index=False))
st.download_button("Download CSV Bundle (.zip)", data=zipbuf.getvalue(),
                   file_name=f"AAPL_{forecast_date}_exports.zip", mime="application/zip",
                   use_container_width=True)

# ───────────────────────── Daily Note Export ─────────────────────────
def daily_note() -> str:
    lines = [f"# {APP_NAME} — {PAGE_NAME}  ({forecast_date})","",
             f"- Monday High/Low: {wk['MonHigh']:.2f} / {wk['MonLow']:.2f}",
             f"- Tuesday High/Low: {wk['TueHigh']:.2f} / {wk['TueLow']:.2f}", ""]
    if open_px is not None:
        lines.append(f"**Open:** " + ("Strong (above channel)" if "strong" in badge_html else "Weak (below channel)" if "weak" in badge_html else "Neutral (inside)"))
    lines.append("")
    lines.append("## Signals (Mon–Fri) — Touch + Close Above")
    for _, r in signals_df.iterrows():
        lines.append(f"- {r['Day']}: {r['Line']} @ {r['Time']} | Close={r['Close']} Line={r['Line Px']} Δ={r['Δ']}")
    return "\n".join(lines)

st.download_button("Export Daily Note (.md)",
                   data=daily_note(),
                   file_name=f"MarketLens_Apple_{forecast_date}.md",
                   mime="text/markdown",
                   use_container_width=True)