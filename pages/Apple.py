# pages/Apple.py
from __future__ import annotations

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import io, zipfile, textwrap
import pandas as pd
import streamlit as st
import yfinance as yf

# ── APP META / CONFIG ────────────────────────────────────────────────
APP_NAME = "MarketLens"
PAGE_NAME = "Apple"

CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")

SLOPE_PER_BLOCK = 0.03545                 # fixed ascending slope per 30-min
RTH_START, RTH_END = time(8,30), time(14,30)  # CT

# ── LIGHT UI (compact) ───────────────────────────────────────────────
st.markdown("""
<style>
:root{--surface:#F7F8FA;--card:#FFFFFF;--border:#E6E9EF;--text:#0F172A;--muted:#62708A;
--accent:#2A6CFB;--good:#16A34A;--bad:#DC2626;--radius:14px;--shadow:0 8px 24px rgba(16,24,40,.06);}
html,body,.stApp{font-family:Inter,-apple-system,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
.stApp{background:var(--surface);color:var(--text);}#MainMenu,footer,.stDeployButton{display:none!important;}
.hero{ text-align:center; padding:18px 12px; border:1px solid var(--border); border-radius:18px;
       background:var(--card); box-shadow:var(--shadow); margin-bottom:12px;}
.brand{font-weight:800; font-size:1.8rem;}
.tag{color:var(--muted);} .meta{color:var(--muted); font-size:.9rem}
.card{ background:var(--card); border:1px solid var(--border); border-radius:14px;
       box-shadow:var(--shadow); padding:14px; margin:12px 0;}
.hline{height:1px; background:#EEF1F6; margin:8px 0 12px 0}
.section{font-weight:700}
.chip{display:inline-flex;align-items:center;gap:.5rem;border:1px solid var(--border);border-radius:999px;
      padding:.35rem .7rem;background:#fff;font-weight:600;font-size:.9rem}
.chip.warn{border-color:#F59E0B33;background:#FFFBEB}
.chip.bad{border-color:#DC262633;background:#FEF2F2}
.tilegrid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;}
.tile{border:1px solid var(--border);border-radius:16px;padding:12px 14px;background:linear-gradient(180deg,#fff,#F7F8FA)}
.tl{font-size:.9rem;color:var(--muted)} .tv{font-size:1.8rem;font-weight:800}
.small{font-size:.9rem;color:var(--muted)}
</style>
""", unsafe_allow_html=True)

# ── HELPERS ──────────────────────────────────────────────────────────
def make_slots(start: time, end: time, step_min: int = 30) -> list[str]:
    cur = datetime(2025,1,1,start.hour,start.minute)
    stop = datetime(2025,1,1,end.hour,end.minute)
    out=[]
    while cur <= stop:
        out.append(cur.strftime("%H:%M")); cur += timedelta(minutes=step_min)
    return out

SLOTS = make_slots(RTH_START, RTH_END)  # 13 slots 08:30→14:30 CT

def blocks_between(t1: datetime, t2: datetime) -> int:
    if t2 < t1: t1, t2 = t2, t1
    blocks, cur = 0, t1
    while cur < t2:
        if cur.hour != 16:  # mirrors your SPX skip behavior; not hit inside 08:30–14:30
            blocks += 1
        cur += timedelta(minutes=30)
    return blocks

def project_line(base_price: float, base_dt: datetime, target_dt: datetime) -> float:
    return base_price + SLOPE_PER_BLOCK * blocks_between(base_dt, target_dt)

# ── DATA (cached) ────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_history_1m(symbol: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    t = yf.Ticker(symbol)
    df = t.history(start=start_dt.astimezone(ET), end=end_dt.astimezone(ET),
                   interval="1m", auto_adjust=False)
    if df is None or df.empty: return pd.DataFrame()
    df = df.reset_index()
    col0 = "Datetime" if "Datetime" in df.columns else df.columns[0]
    df.rename(columns={col0:"dt"}, inplace=True)
    if df["dt"].dt.tz is None:
        df["dt"] = df["dt"].dt.tz_localize(ET)
    df["dt"] = df["dt"].dt.tz_convert(CT)
    return df

def restrict_rth_30m(df_1m: pd.DataFrame) -> pd.DataFrame:
    if df_1m.empty: return df_1m
    df = df_1m.set_index("dt").sort_index()
    ohlc = df[["Open","High","Low","Close","Volume"]].resample("30min", label="right", closed="right").agg({
        "Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"
    }).dropna(subset=["Open","High","Low","Close"]).reset_index()
    ohlc["Time"] = ohlc["dt"].dt.strftime("%H:%M")
    ohlc = ohlc[(ohlc["Time"] >= "08:30") & (ohlc["Time"] <= "14:30")].copy()
    return ohlc

def week_monday_tuesday_for(forecast: date) -> tuple[date, date, date]:
    """Return (Mon, Tue, Fri) for the week containing `forecast`,
       ensuring Mon/Tue are strictly before `forecast` (CT)."""
    week_mon = forecast - timedelta(days=forecast.weekday())
    week_tue = week_mon + timedelta(days=1)
    week_fri = week_mon + timedelta(days=4)
    if week_tue >= forecast:
        week_mon -= timedelta(days=7); week_tue -= timedelta(days=7); week_fri -= timedelta(days=7)
    return week_mon, week_tue, week_fri

@st.cache_data(ttl=600)
def compute_week_anchors_aapl(forecast: date):
    mon_date, tue_date, _ = week_monday_tuesday_for(forecast)
    start_dt = datetime.combine(mon_date, time(7,0), tzinfo=CT)
    end_dt   = datetime.combine(tue_date + timedelta(days=1), time(7,0), tzinfo=CT)
    raw = fetch_history_1m("AAPL", start_dt, end_dt)
    if raw.empty: return None
    raw["D"] = raw["dt"].dt.date

    mon_df = restrict_rth_30m(raw[raw["D"] == mon_date])
    tue_df = restrict_rth_30m(raw[raw["D"] == tue_date])
    if mon_df.empty or tue_df.empty: return None

    # extremes
    MonHigh_i = mon_df["High"].idxmax(); MonLow_i = mon_df["Low"].idxmin()
    TueHigh_i = tue_df["High"].idxmax(); TueLow_i = tue_df["Low"].idxmin()

    MonHigh = float(mon_df.loc[MonHigh_i,"High"]); MonLow = float(mon_df.loc[MonLow_i,"Low"])
    TueHigh = float(tue_df.loc[TueHigh_i,"High"]); TueLow = float(tue_df.loc[TueLow_i,"Low"])
    MonHigh_t = mon_df.loc[MonHigh_i,"dt"].to_pydatetime(); MonLow_t = mon_df.loc[MonLow_i,"dt"].to_pydatetime()
    TueHigh_t = tue_df.loc[TueHigh_i,"dt"].to_pydatetime(); TueLow_t = tue_df.loc[TueLow_i,"dt"].to_pydatetime()

    # Two ascending lines rule
    up_driven = TueHigh >= MonHigh
    if up_driven:
        lower_base_price, lower_base_time = MonLow,  MonLow_t
        upper_base_price, upper_base_time = TueHigh, TueHigh_t
        swing_low, swing_high = MonLow, TueHigh
        swing_label = "Up-driven (Mon Low → Tue High)"
    else:
        lower_base_price, lower_base_time = TueLow,  TueLow_t
        upper_base_price, upper_base_time = MonHigh, MonHigh_t
        swing_low, swing_high = TueLow, MonHigh
        swing_label = "Down-driven (Tue Low → Mon High)"

    return {
        "mon_date": mon_date, "tue_date": tue_date,
        "MonHigh": MonHigh, "MonLow": MonLow, "TueHigh": TueHigh, "TueLow": TueLow,
        "MonHigh_t": MonHigh_t, "MonLow_t": MonLow_t, "TueHigh_t": TueHigh_t, "TueLow_t": TueLow_t,
        "up_driven": up_driven,
        "lower_base_price": lower_base_price, "lower_base_time": lower_base_time,
        "upper_base_price": upper_base_price, "upper_base_time": upper_base_time,
        "swing_low": swing_low, "swing_high": swing_high, "swing_label": swing_label
    }

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

@st.cache_data(ttl=180)
def fetch_intraday_day_30m(symbol: str, d: date) -> pd.DataFrame:
    start_dt = datetime.combine(d, time(7,0), tzinfo=CT)
    end_dt   = datetime.combine(d, time(16,0), tzinfo=CT)
    df1m = fetch_history_1m(symbol, start_dt, end_dt)
    if df1m.empty: return pd.DataFrame()
    df30 = restrict_rth_30m(df1m)[["dt","Open","High","Low","Close","Volume"]].copy()
    df30["Time"] = df30["dt"].dt.strftime("%H:%M")
    return df30

# ── HEADER ───────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
  <div class="brand">{APP_NAME} — {PAGE_NAME}</div>
  <div class="tag">AAPL Weekly Ascending Channel • Fixed slope +0.03545 per 30-min</div>
  <div class="meta">{date.today().strftime('%Y-%m-%d')}</div>
</div>
""", unsafe_allow_html=True)

# ── SIDEBAR ──────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Session")
    forecast_date = st.date_input("Target session", value=date.today() + timedelta(days=1))
    st.caption("This week’s Mon/Tue (strictly before date) define the channel (CT).")
    st.subheader("Detection")
    tolerance = st.slider("Entry tolerance (Δ vs line, $)", 0.01, 0.50, 0.05, 0.01)

# ── WEEK SETUP ───────────────────────────────────────────────────────
wk = compute_week_anchors_aapl(forecast_date)
if not wk:
    st.warning("Unable to compute AAPL Mon/Tue anchors. Try another date.")
    st.stop()

# ── SUMMARY TILES ────────────────────────────────────────────────────
st.markdown(f"""
<div class="card"><div class="tilegrid">
  <div class="tile"><div class="tl">Monday High / Low</div><div class="tv" style="color:#16A34A">{wk['MonHigh']:.2f}</div>
  <div class="small">Low: {wk['MonLow']:.2f} • {wk['mon_date']}</div></div>
  <div class="tile"><div class="tl">Tuesday High / Low</div><div class="tv" style="color:#2A6CFB">{wk['TueHigh']:.2f}</div>
  <div class="small">Low: {wk['TueLow']:.2f} • {wk['tue_date']}</div></div>
  <div class="tile"><div class="tl">Weekly Swing</div><div class="tv">{wk['swing_high']:.2f}</div>
  <div class="small">{wk['swing_label']}</div></div>
</div></div>
""", unsafe_allow_html=True)

# ── CHANNEL VALUES FOR SELECTED DAY ──────────────────────────────────
def channel_for_day(day: date, wkinfo: dict) -> pd.DataFrame:
    rows=[]
    for slot in SLOTS:
        h, m = map(int, slot.split(":"))
        tdt = datetime.combine(day, time(h,m), tzinfo=CT)
        rows.append({
            "Time": slot,
            "LowerLine": round(project_line(wkinfo["lower_base_price"], wkinfo["lower_base_time"], tdt), 2),
            "UpperLine": round(project_line(wkinfo["upper_base_price"], wkinfo["upper_base_time"], tdt), 2)
        })
    return pd.DataFrame(rows)

channel_df = channel_for_day(forecast_date, wk)

# ── OPEN SIGNAL ──────────────────────────────────────────────────────
open_px = fetch_day_open("AAPL", forecast_date)
signal_html = '<span class="chip">Open unavailable</span>'
if open_px is not None:
    lower0830 = float(channel_df.loc[channel_df["Time"]=="08:30","LowerLine"].iloc[0])
    upper0830 = float(channel_df.loc[channel_df["Time"]=="08:30","UpperLine"].iloc[0])
    if open_px < lower0830:
        signal_html = '<span class="chip bad">Below channel at open → expect tag of lower first</span>'
    elif open_px > upper0830:
        signal_html = '<span class="chip warn">Above channel at open → expect drop to upper first</span>'
    else:
        signal_html = '<span class="chip">Inside channel at open → watch first tag</span>'

st.markdown(f"""
<div class="card">
  <div class="section">Open Signal (08:30 CT)</div><div class="hline"></div>
  {signal_html}
</div>
""", unsafe_allow_html=True)

# ── ENTRY DETECTION (Wed–Fri) ───────────────────────────────────────
def first_tag_entries_for_days(anchor_day: date, wkinfo: dict, tol: float) -> pd.DataFrame:
    wd = anchor_day.weekday()
    wed = anchor_day - timedelta(days=wd - 2) if wd >= 2 else anchor_day + timedelta(days=2 - wd)
    days = [wed, wed+timedelta(days=1), wed+timedelta(days=2)]
    out=[]
    for d in days:
        ch = channel_for_day(d, wkinfo)
        intr = fetch_intraday_day_30m("AAPL", d)
        if intr.empty:
            out.append({"Day": d, "Time":"—", "Line":"—", "AAPL Price":"—", "Line Px":"—", "Δ":"—", "Note":"No data"})
            continue
        merged = pd.merge(intr[["Time","Close","Volume"]],
                          ch[["Time","LowerLine","UpperLine"]], on="Time", how="inner")
        merged["toLower"] = (merged["Close"] - merged["LowerLine"]).abs()
        merged["toUpper"] = (merged["Close"] - merged["UpperLine"]).abs()
        cand = []
        for _, r in merged.iterrows():
            if r["toLower"] <= tol: cand.append(("Lower", r["Time"], r["Close"], r["LowerLine"], r["toLower"]))
            if r["toUpper"] <= tol: cand.append(("Upper", r["Time"], r["Close"], r["UpperLine"], r["toUpper"]))
            if cand: break
        if cand:
            line, tm, px, line_px, delta = sorted(cand, key=lambda x: x[4])[0]
            idx = merged.index[merged["Time"]==tm][0]
            vol = merged.iloc[idx]["Volume"]; avg_so_far = merged.iloc[:idx+1]["Volume"].mean()
            note = "Vol>avg" if vol >= avg_so_far else "Vol<avg"
            out.append({"Day": d, "Time": tm, "Line": line,
                        "AAPL Price": round(px,2), "Line Px": round(float(line_px),2),
                        "Δ": round(float(delta),2), "Note": note})
        else:
            out.append({"Day": d, "Time":"—", "Line":"—", "AAPL Price":"—", "Line Px":"—", "Δ":"—", "Note":"No entry"})
    return pd.DataFrame(out)

st.markdown('<div class="card"><div class="section">Auto-Detected Entries (Wed–Fri)</div><div class="hline"></div>', unsafe_allow_html=True)
entries_df = first_tag_entries_for_days(forecast_date, wk, tolerance)
show_df = entries_df.copy()
show_df["Day"] = show_df["Day"].apply(lambda d: d.strftime("%a %Y-%m-%d") if isinstance(d, date) else d)
st.dataframe(show_df, use_container_width=True, hide_index=True)

buf_entries = io.StringIO(); entries_df.to_csv(buf_entries, index=False)
st.download_button("Download Entries (CSV)", data=buf_entries.getvalue(),
                   file_name=f"AAPL_Entries_{wk['mon_date']}_{wk['tue_date']}.csv",
                   mime="text/csv")

st.markdown('</div>', unsafe_allow_html=True)

# ── CHANNEL TABLE + BUNDLE EXPORT ────────────────────────────────────
st.markdown('<div class="card"><div class="section">Channel Table (Selected Day)</div><div class="hline"></div>', unsafe_allow_html=True)
st.dataframe(channel_df[["Time","LowerLine","UpperLine"]], use_container_width=True, hide_index=True)

zipbuf = io.BytesIO()
with zipfile.ZipFile(zipbuf, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(f"AAPL_Channel_{forecast_date}.csv", channel_df.to_csv(index=False))
    intraday30 = fetch_intraday_day_30m("AAPL", forecast_date)
    if not intraday30.empty:
        zf.writestr(f"AAPL_Intraday30_{forecast_date}.csv", intraday30.to_csv(index=False))
    zf.writestr(f"AAPL_Entries_{wk['mon_date']}_{wk['tue_date']}.csv", entries_df.to_csv(index=False))
st.download_button("Download CSV Bundle (.zip)", data=zipbuf.getvalue(),
                   file_name=f"AAPL_{forecast_date}_exports.zip", mime="application/zip",
                   use_container_width=True)

# ── DAILY NOTE EXPORT ────────────────────────────────────────────────
def daily_note() -> str:
    lines = [f"# {APP_NAME} — {PAGE_NAME}  ({forecast_date})","",
             f"**Week:** {wk['mon_date']} to {wk['tue_date']}",
             f"- Mon High/Low: {wk['MonHigh']:.2f} / {wk['MonLow']:.2f}",
             f"- Tue High/Low: {wk['TueHigh']:.2f} / {wk['TueLow']:.2f}",
             f"- Swing: {wk['swing_label']}", "", "## Open Signal",
             f"- {textwrap.shorten(signal_html, width=120, placeholder='...')}", "",
             "## Entries (Wed–Fri)"]
    for _, r in entries_df.iterrows():
        day_txt = r['Day'].strftime('%Y-%m-%d') if isinstance(r['Day'], date) else str(r['Day'])
        lines.append(f"- {day_txt}: {r['Line']} @ {r['Time']} | Px={r['AAPL Price']} Line={r['Line Px']} Δ={r['Δ']} Note={r['Note']}")
    return "\n".join(lines)

st.download_button("Export Daily Note (.md)",
                   data=daily_note(),
                   file_name=f"MarketLens_Apple_{forecast_date}.md",
                   mime="text/markdown",
                   use_container_width=True)