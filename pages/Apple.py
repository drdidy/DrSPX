# pages/Apple.py
from __future__ import annotations

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import io, zipfile, math, textwrap
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from math import log, sqrt, erf


# ── CONFIG ───────────────────────────────────────────────────────────
APP_NAME = "MarketLens"
PAGE_NAME = "Apple"
CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")
SLOPE_PER_BLOCK = 0.03545            # fixed ascending slope per 30-min block
RTH_START, RTH_END = time(8,30), time(14,30)  # CT
BASELINE_DATE_STR = "2000-01-01"     # neutral x-axis date for intraday plots

# ── LIGHT UI (compact CSS) ───────────────────────────────────────────
st.markdown("""
<style>
:root{--surface:#F7F8FA;--card:#FFFFFF;--border:#E6E9EF;--text:#0F172A;--muted:#62708A;
--accent:#2A6CFB;--good:#16A34A;--bad:#DC2626;--radius:14px;--shadow:0 8px 24px rgba(16,24,40,.06);}
html,body,.stApp{font-family:Inter,-apple-system,system-ui,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}
.stApp{background:var(--surface);color:var(--text);}#MainMenu,footer,.stDeployButton{display:none!important;}
.hero{ text-align:center; padding:18px 12px; border:1px solid var(--border); border-radius:18px;
background:var(--card); box-shadow:var(--shadow); margin-bottom:12px;}
.brand{font-weight:800; font-size:1.75rem;} .tag{color:var(--muted);} .meta{color:var(--muted);font-size:.9rem}
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

def fib_level(low: float, high: float, ratio: float) -> float:
    return high - ratio * (high - low)

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

def week_monday_tuesday_for(forecast: date) -> tuple[date, date]:
    week_mon = forecast - timedelta(days=forecast.weekday())
    week_tue = week_mon + timedelta(days=1)
    if week_tue >= forecast:  # ensure Mon/Tue are strictly before forecast date
        week_mon -= timedelta(days=7)
        week_tue -= timedelta(days=7)
    return week_mon, week_tue

@st.cache_data(ttl=600)
def compute_week_anchors_aapl(forecast: date):
    mon_date, tue_date = week_monday_tuesday_for(forecast)
    start_dt = datetime.combine(mon_date, time(7,0), tzinfo=CT)
    end_dt   = datetime.combine(tue_date + timedelta(days=1), time(7,0), tzinfo=CT)
    raw = fetch_history_1m("AAPL", start_dt, end_dt)
    if raw.empty: return None
    raw["D"] = raw["dt"].dt.date

    mon_df = restrict_rth_30m(raw[raw["D"] == mon_date])
    tue_df = restrict_rth_30m(raw[raw["D"] == tue_date])
    if mon_df.empty or tue_df.empty: return None

    # Mon extremes
    MonHigh_i = mon_df["High"].idxmax(); MonLow_i = mon_df["Low"].idxmin()
    MonHigh = float(mon_df.loc[MonHigh_i,"High"]); MonHigh_t = mon_df.loc[MonHigh_i,"dt"].to_pydatetime()
    MonLow  = float(mon_df.loc[MonLow_i,"Low"]);   MonLow_t  = mon_df.loc[MonLow_i, "dt"].to_pydatetime()
    # Tue extremes
    TueHigh_i = tue_df["High"].idxmax(); TueLow_i = tue_df["Low"].idxmin()
    TueHigh = float(tue_df.loc[TueHigh_i,"High"]); TueHigh_t = tue_df.loc[TueHigh_i,"dt"].to_pydatetime()
    TueLow  = float(tue_df.loc[TueLow_i,"Low"]);   TueLow_t  = tue_df.loc[TueLow_i, "dt"].to_pydatetime()

    # Rule: if Tue High >= Mon High → lower from Mon Low, upper from Tue High; else lower from Tue Low, upper from Mon High
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
    df30["TS"] = pd.to_datetime(BASELINE_DATE_STR + " " + df30["dt"].dt.strftime("%H:%M"))
    df30["Time"] = df30["dt"].dt.strftime("%H:%M")
    return df30

# ── HEADER ───────────────────────────────────────────────────────────
st.markdown(f"""
<div class="hero">
  <div class="brand">{APP_NAME} — {PAGE_NAME}</div>
  <div class="tag">AAPL Weekly Channel • Uniform Ascending Slope (+0.03545 / 30m)</div>
  <div class="meta">{date.today().strftime('%Y-%m-%d')}</div>
</div>
""", unsafe_allow_html=True)

# ── SIDEBAR ──────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("Session")
    forecast_date = st.date_input("Target session", value=date.today() + timedelta(days=1))
    st.caption("Mon/Tue of the same week strictly before this date define the channel (CT).")
    st.subheader("Detection")
    tolerance = st.slider("Entry tolerance (Δ vs line, $)", 0.01, 0.50, 0.05, 0.01)
    st.subheader("Options")
    if "risk_free_rate" not in st.session_state: st.session_state.risk_free_rate = 0.04
    r_default = st.number_input("Risk-free rate (annual)", value=float(st.session_state.risk_free_rate),
                                step=0.005, min_value=0.0, max_value=0.25)
    st.session_state.risk_free_rate = r_default

# ── WEEK SETUP & MEMORY ──────────────────────────────────────────────
wk = compute_week_anchors_aapl(forecast_date)
if not wk:
    st.warning("Unable to compute AAPL Mon/Tue anchors. Try another date.")
    st.stop()

if "aapl_iv_by_week" not in st.session_state: st.session_state.aapl_iv_by_week = {}
if "aapl_default_iv" not in st.session_state: st.session_state.aapl_default_iv = 0.30
week_key = f"{wk['mon_date']}_{wk['tue_date']}"
if week_key in st.session_state.aapl_iv_by_week:
    st.session_state.aapl_default_iv = float(st.session_state.aapl_iv_by_week[week_key])

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
    df = pd.DataFrame(rows)
    df["TS"] = pd.to_datetime(BASELINE_DATE_STR + " " + df["Time"])
    return df

channel_df = channel_for_day(forecast_date, wk)

# ── OPEN SIGNAL + 0.786 FIB ─────────────────────────────────────────
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

fib0786 = round(fib_level(wk["swing_low"], wk["swing_high"], 0.786), 2)
if open_px is not None:
    diff = min(abs(fib0786 - lower0830), abs(fib0786 - upper0830))
    pct = (diff / fib0786 * 100.0) if fib0786 else float("inf")
    grade = "Strong" if pct <= 0.30 else ("Moderate" if pct <= 1.00 else "Weak")
    fib_html = f"Fib 0.786 = <b>${fib0786:.2f}</b> • Δ to nearest line: ${diff:.2f} ({pct:.2f}%) • <b>{grade}</b>"
else:
    fib_html = "Fib 0.786 = —"

st.markdown(f"""
<div class="card">
  <div class="section">Open Signal (08:30 CT)</div><div class="hline"></div>
  {signal_html}
</div>
<div class="card">
  <div class="section">0.786 Confluence at Open</div><div class="hline"></div>
  <div>{fib_html}</div>
</div>
""", unsafe_allow_html=True)

# ── PLOTLY CHART (Channel + Intraday) ───────────────────────────────
intraday30 = fetch_intraday_day_30m("AAPL", forecast_date)
fig = go.Figure()
fig.add_trace(go.Scatter(x=channel_df["TS"], y=channel_df["UpperLine"], name="Upper line (+0.03545/30m)",
                         line=dict(width=2, color="#16A34A"),
                         hovertemplate="Time=%{x|%H:%M}<br>Upper=%{y:.2f}<extra></extra>"))
fig.add_trace(go.Scatter(x=channel_df["TS"], y=channel_df["LowerLine"], name="Lower line (+0.03545/30m)",
                         line=dict(width=2, color="#EF4444"),
                         hovertemplate="Time=%{x|%H:%M}<br>Lower=%{y:.2f}<extra></extra>"))
if not intraday30.empty:
    fig.add_trace(go.Scatter(x=intraday30["TS"], y=intraday30["Close"], name="AAPL",
                             line=dict(width=2, color="#2563EB"),
                             hovertemplate="Time=%{x|%H:%M}<br>AAPL=%{y:.2f}<extra></extra>"))
fig.update_layout(title="AAPL — Weekly Channel vs Intraday", height=390,
                  margin=dict(l=10,r=10,t=50,b=10),
                  legend=dict(orientation="h", y=1.02, x=0), dragmode="pan")
fig.update_xaxes(rangeslider_visible=True, showgrid=False)
fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")
st.plotly_chart(fig, use_container_width=True)

# PNG export (optional, works if kaleido is available)
try:
    png = fig.to_image(format="png", width=1200, height=500, scale=2)
    st.download_button("Download Chart (PNG)", data=png,
                       file_name=f"AAPL_Channel_{forecast_date}.png",
                       mime="image/png", use_container_width=True)
except Exception:
    pass

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
    if not intraday30.empty:
        zf.writestr(f"AAPL_Intraday30_{forecast_date}.csv", intraday30.to_csv(index=False))
    zf.writestr(f"AAPL_Entries_{wk['mon_date']}_{wk['tue_date']}.csv", entries_df.to_csv(index=False))
st.download_button("Download CSV Bundle (.zip)", data=zipbuf.getvalue(),
                   file_name=f"AAPL_{forecast_date}_exports.zip", mime="application/zip",
                   use_container_width=True)

# ── BLACK–SCHOLES / IV ───────────────────────────────────────────────
def norm_cdf(x: float) -> float: return 0.5*(1.0 + erf(x / sqrt(2.0)))

def bs_price_greeks(S: float, K: float, T: float, r: float, sigma: float, is_call: bool):
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return *(float("nan"),)*6
    d1 = (log(S/K) + (r + 0.5*sigma*sigma)*T) / (sigma*sqrt(T))
    d2 = d1 - sigma*sqrt(T)
    Nd1, Nd2 = norm_cdf(d1), norm_cdf(d2)
    n_d1 = (1.0/sqrt(2.0*math.pi)) * math.exp(-0.5*d1*d1)
    if is_call:
        price = S*Nd1 - K*math.exp(-r*T)*Nd2; delta = Nd1; rho = K*T*math.exp(-r*T)*Nd2/100.0
    else:
        price = K*math.exp(-r*T)*norm_cdf(-d2) - S*norm_cdf(-d1); delta = Nd1 - 1.0; rho = -K*T*math.exp(-r*T)*norm_cdf(-d2)/100.0
    gamma = n_d1/(S*sigma*sqrt(T)); vega = S*n_d1*sqrt(T)/100.0; theta = (-(S*n_d1*sigma)/(2*sqrt(T)) - (r*K*math.exp(-r*T)*(Nd2 if is_call else norm_cdf(-d2))))/365.0
    return price, delta, gamma, theta, vega, rho

def year_fraction(t0: datetime, t1: datetime) -> float:
    return max((t1 - t0).total_seconds(), 0.0) / (365.0*24*3600.0)

def implied_vol(target_price, S, K, T, r, is_call, sigma_lo=1e-4, sigma_hi=5.0, tol=1e-6, max_iter=120):
    def p(sig): return bs_price_greeks(S,K,T,r,sig,is_call)[0]
    lo, hi = sigma_lo, sigma_hi
    p_lo, p_hi = p(lo), p(hi)
    if math.isnan(p_lo) or math.isnan(p_hi): return None
    for _ in range(40):
        if p_lo > target_price: lo *= 0.5; p_lo = p(lo)
        if p_hi < target_price: hi *= 2.0; p_hi = p(hi)
        if p_lo <= target_price <= p_hi: break
    if not (p_lo <= target_price <= p_hi): return None
    for _ in range(max_iter):
        mid = 0.5*(lo+hi); pm = p(mid)
        if abs(pm - target_price) < tol: return mid
        if pm < target_price: lo = mid
        else: hi = mid
    return 0.5*(lo+hi)

def calibrate_iv_single(obs_price, S, K, t_obs: datetime, t_exp: datetime, r, is_call):
    T = year_fraction(t_obs, t_exp);  return None if T<=0 else implied_vol(obs_price,S,K,T,r,is_call)

def calibrate_iv_two_points(obs1: tuple, obs2: tuple, r: float, is_call: bool):
    price1,S1,t1,K1,texp = obs1; price2,S2,t2,K2,_ = obs2
    def sse(sig):
        T1, T2 = year_fraction(t1, texp), year_fraction(t2, texp)
        if T1<=0 or T2<=0: return float("inf")
        p1 = bs_price_greeks(S1,K1,T1,r,sig,is_call)[0]
        p2 = bs_price_greeks(S2,K2,T2,r,sig,is_call)[0]
        return (p1-price1)**2 + (p2-price2)**2
    grid = np.geomspace(0.02, 2.0, 60)
    best = min(grid, key=sse); lo, hi = max(best*0.5,1e-4), min(best*1.5,5.0)
    for _ in range(60):
        m = 0.5*(lo+hi)
        if sse(lo) < sse(hi): hi = m
        else: lo = m
    return 0.5*(lo+hi)

# ── OPTION CALCULATOR UI ─────────────────────────────────────────────
st.markdown('<div class="card"><div class="section">AAPL Option Calculator</div><div class="hline"></div>', unsafe_allow_html=True)
st.caption(f"Active IV (seed): {st.session_state.aapl_default_iv:.4f} • Week: {week_key}")
colL, colR = st.columns(2)

with colL:
    opt_type = st.selectbox("Type", ["Call","Put"], index=0); is_call = opt_type=="Call"
    strike  = st.number_input("Strike", value=210.0, step=0.5, min_value=0.0)
    days_to_fri = (4 - forecast_date.weekday()) % 7
    exp_date = st.date_input("Expiration date", value=forecast_date + timedelta(days=days_to_fri))
    exp_time = st.time_input("Expiration time (CT)", value=time(15,0), step=300)
    r_rate   = float(st.session_state.risk_free_rate)

    slot = st.selectbox("Use channel @ time", SLOTS, index=0)
    h, m = map(int, slot.split(":")); tdt = datetime.combine(forecast_date, time(h,m), tzinfo=CT)
    lower_px = float(channel_df.loc[channel_df["Time"]==slot,"LowerLine"].iloc[0])
    upper_px = float(channel_df.loc[channel_df["Time"]==slot,"UpperLine"].iloc[0])
    src = st.radio("Underlying source", ["Upper line","Mid (avg)","Lower line"], index=1, horizontal=True)
    auto_S = upper_px if src=="Upper line" else lower_px if src=="Lower line" else 0.5*(upper_px+lower_px)
    S_input = st.number_input("Underlying @ time (auto-filled; editable)", value=round(auto_S,2), step=0.01, min_value=0.0)
    iv_input = st.number_input("IV (annualized)", value=float(st.session_state.aapl_default_iv), step=0.01, min_value=0.01, max_value=5.0)

with colR:
    t_exp = datetime.combine(exp_date, exp_time, tzinfo=CT)
    T = year_fraction(tdt, t_exp)
    price, delta, gamma, theta, vega, rho = bs_price_greeks(S_input, strike, T, r_rate, iv_input, is_call)
    if price == price:
        st.write(f"**Theo** ${price:.3f}")
        st.write(f"Δ {delta:.4f} • Γ {gamma:.6f} • Θ/day {theta:.4f} • Vega/1% {vega:.4f} • Rho/1% {rho:.4f}")
    else:
        st.write("Theo/Greeks: —")

    opp_val = upper_px if src=="Lower line" else lower_px if src=="Upper line" else upper_px
    opp_theo, *_ = bs_price_greeks(opp_val, strike, T, r_rate, iv_input, is_call)
    c1, c2 = st.columns(2)
    with c1: stop_price = st.number_input("Your stop ($)", value=(round(price*0.6,2) if price==price else 0.50), step=0.05, min_value=0.0)
    with c2: target_price = st.number_input("Target ($)", value=(round(opp_theo,2) if opp_theo==opp_theo else round(price*1.5,2)), step=0.05, min_value=0.0)
    if price==price and stop_price>0:
        rr = (target_price - price) / max(price - stop_price, 1e-9)
        st.write(f"R:R ≈ **{rr:.2f}**  • Opposite-line theo: {opp_theo:.3f}")

st.markdown("</div>", unsafe_allow_html=True)

# ── CALIBRATE IV (persist for week) ──────────────────────────────────
with st.expander("Calibrate IV from observations"):
    cL, cR = st.columns(2)
    with cL:
        obs1_date = st.date_input("Obs #1 date", value=date(2025,7,14))
        obs1_time = st.time_input("Obs #1 time (CT)", value=time(9,0), step=300)
        obs1_S    = st.number_input("Obs #1 underlying S", value=207.54, step=0.01)
        obs1_K    = st.number_input("Obs #1 strike K", value=210.0, step=0.5)
        obs1_P    = st.number_input("Obs #1 option price", value=1.46, step=0.01)
    with cR:
        use2      = st.checkbox("Use second observation", value=True)
        obs2_date = st.date_input("Obs #2 date", value=date(2025,7,15))
        obs2_time = st.time_input("Obs #2 time (CT)", value=time(10,30), step=300)
        obs2_S    = st.number_input("Obs #2 underlying S", value=211.89, step=0.01)
        obs2_K    = st.number_input("Obs #2 strike K", value=210.0, step=0.5)
        obs2_P    = st.number_input("Obs #2 option price", value=3.35, step=0.01)

    exp_d_cal = st.date_input("Expiration date (for obs)", value=exp_date)
    exp_t_cal = st.time_input("Expiration time (CT)", value=exp_time, step=300)
    typ_cal   = st.selectbox("Type for calibration", ["Call","Put"], index=0) == "Call"
    r_cal     = st.number_input("Risk-free (calibration)", value=r_rate, step=0.005, min_value=0.0, max_value=0.2)

    if st.button("Calibrate IV", type="primary"):
        texp = datetime.combine(exp_d_cal, exp_t_cal, tzinfo=CT)
        iv_est = None
        try:
            t1 = datetime.combine(obs1_date, obs1_time, tzinfo=CT)
            if use2:
                t2 = datetime.combine(obs2_date, obs2_time, tzinfo=CT)
                iv_est = calibrate_iv_two_points((obs1_P, obs1_S, t1, obs1_K, texp),
                                                 (obs2_P, obs2_S, t2, obs2_K, texp),
                                                 r_cal, typ_cal)
            else:
                iv_est = calibrate_iv_single(obs1_P, obs1_S, obs1_K, t1, texp, r_cal, typ_cal)
        except Exception:
            iv_est = None

        if iv_est and iv_est == iv_est and iv_est > 0:
            st.session_state.aapl_default_iv = float(iv_est)
            st.session_state.aapl_iv_by_week[week_key] = float(iv_est)
            st.success(f"Calibrated IV = **{iv_est:.4f}** saved for week {week_key}")
            # show fit error
            rows=[]
            def modeled(S,K,t_obs): return bs_price_greeks(S,K,year_fraction(t_obs,texp),r_cal,iv_est,typ_cal)[0]
            m1 = modeled(obs1_S,obs1_K,t1); err1=(m1-obs1_P); err1p=(err1/obs1_P*100.0) if obs1_P else float("nan")
            rows.append({"Obs":"#1","S":obs1_S,"K":obs1_K,"Actual":obs1_P,"Model":round(m1,4),"Err":round(err1,4),"Err%":round(err1p,2)})
            if use2:
                m2 = modeled(obs2_S,obs2_K,t2); err2=(m2-obs2_P); err2p=(err2/obs2_P*100.0) if obs2_P else float("nan")
                rows.append({"Obs":"#2","S":obs2_S,"K":obs2_K,"Actual":obs2_P,"Model":round(m2,4),"Err":round(err2,4),"Err%":round(err2p,2)})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.error("Could not calibrate IV. Check inputs/expiry.")

# ── DAILY NOTE EXPORT ────────────────────────────────────────────────
def daily_note() -> str:
    lines = [f"# {APP_NAME} — {PAGE_NAME}  ({forecast_date})","",
             f"**Week:** {week_key}",
             f"- Mon High/Low: {wk['MonHigh']:.2f} / {wk['MonLow']:.2f}",
             f"- Tue High/Low: {wk['TueHigh']:.2f} / {wk['TueLow']:.2f}",
             f"- Swing: {wk['swing_label']}", "", "## Open Signal",
             f"- {textwrap.shorten(signal_html, width=120, placeholder='...')}", "",
             "## 0.786 Confluence", f"- Fib 0.786: ${fib0786:.2f}", "",
             "## Entries (Wed–Fri)"]
    for _, r in entries_df.iterrows():
        day_txt = r['Day'].strftime('%Y-%m-%d') if isinstance(r['Day'], date) else str(r['Day'])
        lines.append(f"- {day_txt}: {r['Line']} @ {r['Time']} | Px={r['AAPL Price']} Line={r['Line Px']} Δ={r['Δ']} Note={r['Note']}")
    lines += ["","## Option Snapshot",
              f"- Type: {'Call' if opt_type=='Call' else 'Put'}  Strike: {strike}  Exp: {exp_date} {exp_time}  IV: {iv_input:.4f}"]
    if (price == price):
        lines.append(f"- Theo ${price:.3f}  Δ {delta:.4f}  Γ {gamma:.6f}  Θ/day {theta:.4f}  Vega/1% {vega:.4f}  Rho/1% {rho:.4f}")
    return "\n".join(lines)

md = daily_note()
st.download_button("Export Daily Note (.md)", data=md,
                   file_name=f"MarketLens_Apple_{forecast_date}.md",
                   mime="text/markdown", use_container_width=True)
