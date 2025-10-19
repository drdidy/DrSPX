# app.py
# SPX PROPHET — Ultimate Professional Trading Platform
# Advanced dual-anchor system with live price tracking and intelligent trading zones
# Built for serious institutional traders

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List, Dict, Tuple, Optional
import yfinance as yf

APP_NAME = "SPX PROPHET"
APP_VERSION = "Ultimate Pro 4.0"
APP_TAGLINE = "Live Market Intelligence & Projection Platform"

# ===============================
# CONFIGURATION
# ===============================

CT = pytz.timezone("America/Chicago")
ET = pytz.timezone("America/New_York")
ASC_SLOPE = 0.5412
DESC_SLOPE = -0.5412

# Line naming (strategic)
LINE_NAMES = {
    "skyline_bull": "Final Resistance",
    "skyline_bear": "Mid Support",
    "baseline_bull": "Mid Resistance",
    "baseline_bear": "Final Support"
}

# ===============================
# LIVE DATA FUNCTIONS
# ===============================

@st.cache_data(ttl=60)
def get_live_es_price() -> Optional[float]:
    """Fetch live ES futures price"""
    try:
        es = yf.Ticker("ES=F")
        data = es.history(period="1d", interval="1m")
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    return None

def calculate_spx_es_offset(reference_date: date) -> float:
    """Calculate SPX-ES offset from 2pm CT on reference date"""
    try:
        # Get SPX close at 2pm CT (3pm ET)
        spx = yf.Ticker("^GSPC")
        spx_data = spx.history(start=reference_date, end=reference_date + timedelta(days=1), interval="1h")
        
        # Get ES close at same time
        es = yf.Ticker("ES=F")
        es_data = es.history(start=reference_date, end=reference_date + timedelta(days=1), interval="1h")
        
        if not spx_data.empty and not es_data.empty:
            # Try to get 2pm CT (3pm ET) values
            spx_2pm = spx_data['Close'].iloc[-2] if len(spx_data) >= 2 else spx_data['Close'].iloc[-1]
            es_2pm = es_data['Close'].iloc[-2] if len(es_data) >= 2 else es_data['Close'].iloc[-1]
            return float(spx_2pm - es_2pm)
    except:
        pass
    return 0.0

def get_spx_equivalent_price(offset: float) -> Optional[float]:
    """Get SPX equivalent price (ES - offset)"""
    es_price = get_live_es_price()
    if es_price:
        return es_price - offset
    return None

def get_previous_day_ohlc(reference_date: date) -> Optional[Dict]:
    """Get previous trading day OHLC for anchor validation"""
    try:
        spx = yf.Ticker("^GSPC")
        # Get a few days to ensure we catch previous trading day
        start = reference_date - timedelta(days=7)
        data = spx.history(start=start, end=reference_date)
        if not data.empty:
            last_day = data.iloc[-1]
            return {
                'open': float(last_day['Open']),
                'high': float(last_day['High']),
                'low': float(last_day['Low']),
                'close': float(last_day['Close']),
                'date': data.index[-1].date()
            }
    except:
        pass
    return None

# ===============================
# TIME & CALCULATIONS
# ===============================

def is_weekend_gap(dt: datetime) -> bool:
    """Check if datetime falls in weekend gap (Friday 3:30pm - Sunday 5:00pm CT)"""
    if dt.weekday() == 4:  # Friday
        return dt.hour >= 15 and dt.minute >= 30
    elif dt.weekday() == 5:  # Saturday
        return True
    elif dt.weekday() == 6:  # Sunday
        return dt.hour < 17
    return False

def rth_slots_ct_dt(proj_date: date, start="08:30", end="14:00") -> List[datetime]:
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    start_dt = CT.localize(datetime.combine(proj_date, dtime(h1, m1)))
    end_dt = CT.localize(datetime.combine(proj_date, dtime(h2, m2)))
    idx = pd.date_range(start=start_dt, end=end_dt, freq="30min", tz=CT)
    return list(idx.to_pydatetime())

def count_blocks_with_gaps(start_dt: datetime, end_dt: datetime) -> int:
    """Count blocks skipping maintenance (4:00-5:00pm) and weekend gaps"""
    blocks = 0
    current = start_dt
    
    while current < end_dt:
        # Skip maintenance window
        if current.hour == 16 and current.minute in [0, 30]:
            current += timedelta(minutes=30)
            continue
        
        # Skip weekend gap
        if is_weekend_gap(current):
            current += timedelta(minutes=30)
            continue
        
        blocks += 1
        current += timedelta(minutes=30)
    
    return blocks

def project_line(anchor_price: float, anchor_time_ct: datetime, slope_per_block: float, rth_slots_ct: List[datetime]) -> pd.DataFrame:
    minute = 0 if anchor_time_ct.minute < 30 else 30
    anchor_aligned = anchor_time_ct.replace(minute=minute, second=0, microsecond=0)
    rows = []
    for dt in rth_slots_ct:
        blocks = count_blocks_with_gaps(anchor_aligned, dt)
        price = anchor_price + (slope_per_block * blocks)
        rows.append({"Time": dt.strftime("%I:%M %p"), "Price": round(price, 2)})
    return pd.DataFrame(rows)

# ===============================
# ANALYTICS
# ===============================

def get_trading_zone(price: float, projections: Dict[str, float]) -> Tuple[str, str, str]:
    """Determine which trading zone price is in"""
    final_resistance = projections['Final Resistance']
    mid_support = projections['Mid Support']
    mid_resistance = projections['Mid Resistance']
    final_support = projections['Final Support']
    
    # Sort to get boundaries
    sorted_prices = sorted([final_resistance, mid_support, mid_resistance, final_support])
    
    if price >= max(sorted_prices):
        return "🔴 BREAKOUT ZONE", "Above all projections - Strong bullish breakout", "error"
    elif price <= min(sorted_prices):
        return "🔵 BREAKDOWN ZONE", "Below all projections - Strong bearish breakdown", "info"
    elif price >= final_resistance:
        return "🟢 FINAL RESISTANCE ZONE", "SELL ZONE - Expect reversal down", "success"
    elif price <= final_support:
        return "🟢 FINAL SUPPORT ZONE", "BUY ZONE - Expect reversal up", "success"
    elif price >= mid_resistance:
        return "🟡 MID RESISTANCE ZONE", "Near resistance - Watch for rejection or breakout", "warning"
    elif price <= mid_support:
        return "🟡 MID SUPPORT ZONE", "Near support - Watch for bounce or breakdown", "warning"
    else:
        return "⚪ NEUTRAL ZONE", "Between mid levels - Wait for direction", "info"

def calculate_distances(price: float, projections: Dict[str, float]) -> Dict[str, float]:
    """Calculate distance from current price to each projection"""
    return {
        name: round(abs(price - proj_price), 2)
        for name, proj_price in projections.items()
    }

def get_playbook(open_zone: str, projections: Dict[str, float]) -> str:
    """Generate trading playbook based on opening zone"""
    if "FINAL SUPPORT" in open_zone:
        return f"📈 **BUY** from Final Support (${projections['Final Support']:.2f}) → Target Mid Resistance (${projections['Mid Resistance']:.2f}) or Final Resistance (${projections['Final Resistance']:.2f})"
    elif "FINAL RESISTANCE" in open_zone:
        return f"📉 **SELL** from Final Resistance (${projections['Final Resistance']:.2f}) → Target Mid Support (${projections['Mid Support']:.2f}) or Final Support (${projections['Final Support']:.2f})"
    elif "MID SUPPORT" in open_zone:
        return f"📉 **SHORT** to Final Support (${projections['Final Support']:.2f}), then **BUY** to Mid Resistance (${projections['Mid Resistance']:.2f})"
    elif "MID RESISTANCE" in open_zone:
        return f"📈 **BUY** to Final Resistance (${projections['Final Resistance']:.2f}), then **SELL** to Mid Support (${projections['Mid Support']:.2f})"
    elif "NEUTRAL" in open_zone:
        return f"⚖️ **WAIT** for directional move. BUY at ${projections['Mid Support']:.2f} or SELL at ${projections['Mid Resistance']:.2f}"
    elif "BREAKOUT" in open_zone:
        return f"🚀 **STRONG BULL** - Continuation likely. Trail stops, target continuation"
    elif "BREAKDOWN" in open_zone:
        return f"💥 **STRONG BEAR** - Continuation likely. Trail stops, target continuation"
    return "Monitor price action"

def validate_anchor(anchor_price: float, anchor_name: str, prev_ohlc: Dict) -> Tuple[str, str]:
    """Validate anchor quality against previous day OHLC"""
    if not prev_ohlc:
        return "⚪", "No historical data available"
    
    high = prev_ohlc['high']
    low = prev_ohlc['low']
    close = prev_ohlc['close']
    
    if "Skyline" in anchor_name or "SKYLINE" in anchor_name:
        # Upper anchor should be near high
        if abs(anchor_price - high) < 5:
            return "🟢", f"EXCELLENT - Near previous high (${high:.2f})"
        elif abs(anchor_price - close) < 5:
            return "🟡", f"GOOD - Near previous close (${close:.2f})"
        else:
            return "🟠", f"CAUTION - Prev high: ${high:.2f}, close: ${close:.2f}"
    else:
        # Lower anchor should be near low
        if abs(anchor_price - low) < 5:
            return "🟢", f"EXCELLENT - Near previous low (${low:.2f})"
        elif abs(anchor_price - close) < 5:
            return "🟡", f"GOOD - Near previous close (${close:.2f})"
        else:
            return "🟠", f"CAUTION - Prev low: ${low:.2f}, close: ${close:.2f}"

# ===============================
# THEME
# ===============================

def get_theme_css(mode: str) -> str:
    if mode == "🌙 Dark":
        c = {
            "bg": "#000", "surface": "#0a0a0a", "elevated": "#1a1a1a", "text": "#fff",
            "secondary": "#a3a3a3", "muted": "#666", "primary": "#00ff88", "accent": "#00d4ff",
            "success": "#10b981", "error": "#ef4444", "warning": "#f59e0b", "border": "#1f1f1f"
        }
    else:
        c = {
            "bg": "#fff", "surface": "#fafafa", "elevated": "#fff", "text": "#0a0a0a",
            "secondary": "#525252", "muted": "#a3a3a3", "primary": "#00b366", "accent": "#0099cc",
            "success": "#10b981", "error": "#ef4444", "warning": "#f59e0b", "border": "#e5e5e5"
        }
    
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;600;700&display=swap');
    
    * {{ font-family: 'Inter', sans-serif; }}
    html, body, [class*="st"] {{ background: {c['bg']} !important; color: {c['text']} !important; }}
    
    section[data-testid="stSidebar"] {{ background: {c['surface']} !important; border-right: 1px solid {c['border']} !important; }}
    section[data-testid="stSidebar"] label {{ color: {c['secondary']} !important; font-weight: 700 !important; font-size: 0.75rem !important; text-transform: uppercase !important; }}
    
    .app-header {{ text-align: center; padding: 3.5rem 0 2.5rem; background: radial-gradient(ellipse, {c['primary']}08, transparent); }}
    .app-logo {{ font-size: 4.5rem; font-weight: 900; letter-spacing: 0.1em; background: linear-gradient(135deg, {c['primary']}, {c['accent']}); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    .app-sep {{ width: 140px; height: 4px; background: linear-gradient(90deg, transparent, {c['primary']}, {c['accent']}, transparent); margin: 1.25rem auto; }}
    .app-tag {{ font-size: 1.125rem; color: {c['secondary']}; font-weight: 500; }}
    
    .live-ticker {{ background: {c['elevated']}; border: 2px solid {c['primary']}; border-radius: 16px; padding: 2rem; margin: 2rem 0; box-shadow: 0 0 30px {c['primary']}20; }}
    .ticker-price {{ font-size: 3.5rem; font-weight: 900; font-family: 'JetBrains Mono'; background: linear-gradient(135deg, {c['primary']}, {c['accent']}); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }}
    .ticker-label {{ text-align: center; font-size: 0.875rem; color: {c['muted']}; text-transform: uppercase; font-weight: 700; margin-top: 0.5rem; }}
    
    .zone-alert {{ padding: 1.5rem 2rem; border-radius: 14px; margin: 1.5rem 0; border-left: 4px solid; }}
    .zone-alert.success {{ background: {c['success']}15; border-color: {c['success']}; }}
    .zone-alert.error {{ background: {c['error']}15; border-color: {c['error']}; }}
    .zone-alert.warning {{ background: {c['warning']}15; border-color: {c['warning']}; }}
    .zone-alert.info {{ background: {c['accent']}15; border-color: {c['accent']}; }}
    .zone-title {{ font-size: 1.5rem; font-weight: 800; margin-bottom: 0.5rem; }}
    .zone-desc {{ font-size: 1rem; color: {c['secondary']}; }}
    
    .card {{ background: {c['elevated']}; border: 1px solid {c['border']}; border-radius: 16px; margin: 1.5rem 0; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.04); }}
    .card-header {{ background: {c['surface']}; border-bottom: 1px solid {c['border']}; padding: 1.5rem 2rem; display: flex; justify-content: space-between; align-items: center; }}
    .card-title {{ font-size: 1.5rem; font-weight: 800; display: flex; align-items: center; gap: 0.75rem; }}
    .card-body {{ padding: 2rem; }}
    
    .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin: 1.5rem 0; }}
    .metric-box {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; padding: 1.5rem; text-align: center; }}
    .metric-label {{ font-size: 0.7rem; font-weight: 800; color: {c['muted']}; text-transform: uppercase; margin-bottom: 0.75rem; }}
    .metric-value {{ font-size: 1.875rem; font-weight: 900; font-family: 'JetBrains Mono'; color: {c['text']}; }}
    .metric-sub {{ font-size: 0.813rem; color: {c['secondary']}; margin-top: 0.5rem; }}
    
    .distance-item {{ display: flex; justify-content: space-between; padding: 0.875rem 1.25rem; background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; margin: 0.5rem 0; }}
    .distance-name {{ font-weight: 700; color: {c['text']}; }}
    .distance-value {{ font-family: 'JetBrains Mono'; font-weight: 700; color: {c['primary']}; }}
    
    .playbook {{ background: linear-gradient(135deg, {c['primary']}12, {c['accent']}12); border: 2px solid {c['primary']}40; border-radius: 14px; padding: 1.75rem 2rem; margin: 1.5rem 0; }}
    .playbook-title {{ font-size: 1.25rem; font-weight: 800; margin-bottom: 1rem; }}
    
    .anchor-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin: 1.5rem 0; }}
    .anchor-box {{ background: {c['surface']}; border: 2px solid {c['border']}; border-radius: 14px; padding: 1.75rem; }}
    .anchor-box:hover {{ border-color: {c['primary']}; box-shadow: 0 0 20px {c['primary']}15; }}
    
    .validation-badge {{ display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; font-size: 0.813rem; font-weight: 600; margin: 0.5rem 0; }}
    
    .stDataFrame {{ border: 1px solid {c['border']}; border-radius: 12px; overflow: hidden; }}
    .stDataFrame table {{ font-family: 'JetBrains Mono' !important; }}
    .stDataFrame thead th {{ background: {c['surface']} !important; color: {c['muted']} !important; font-weight: 900 !important; text-transform: uppercase !important; }}
    
    .performance-row {{ display: flex; justify-content: space-between; padding: 0.75rem 1.25rem; background: {c['surface']}; border-radius: 8px; margin: 0.5rem 0; }}
    .perf-time {{ font-weight: 700; font-family: 'JetBrains Mono'; }}
    .perf-expected {{ color: {c['muted']}; font-family: 'JetBrains Mono'; }}
    .perf-actual {{ font-weight: 700; font-family: 'JetBrains Mono'; }}
    .perf-status {{ font-weight: 700; }}
    .perf-status.hit {{ color: {c['success']}; }}
    .perf-status.miss {{ color: {c['error']}; }}
    
    </style>
    """

# ===============================
# MAIN APP
# ===============================

def main():
    st.set_page_config(page_title=APP_NAME, page_icon="📊", layout="wide", initial_sidebar_state="expanded")
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        theme_mode = st.radio("Theme", ["☀️ Light", "🌙 Dark"], index=0)
        
        st.markdown("---")
        st.markdown("### 📊 Configuration")
        st.info(f"**Ascending:** +{ASC_SLOPE}")
        st.info(f"**Descending:** {DESC_SLOPE}")
        
        st.markdown("---")
        st.markdown("### ℹ️ System")
        st.caption("🕐 Central Time (CT)")
        st.caption("📊 RTH: 8:30 AM - 2:00 PM")
        st.caption("⚠️ Excludes 4-5 PM maintenance")
        st.caption("📅 Weekend gap handling")
        st.caption("📡 Live ES futures data")
        
        st.markdown("---")
        auto_refresh = st.checkbox("🔄 Auto-refresh (60s)", value=False)
        if auto_refresh:
            st_autorefresh = st.empty()
            import time
            time.sleep(60)
            st.rerun()
    
    st.markdown(get_theme_css(theme_mode), unsafe_allow_html=True)
    
    # Header
    st.markdown(f"""
        <div class="app-header">
            <div class="app-logo">{APP_NAME}</div>
            <div class="app-sep"></div>
            <div class="app-tag">{APP_TAGLINE}</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Configuration
    st.markdown('<div class="card"><div class="card-header"><div class="card-title"><span>⚙️</span> Configuration</div></div><div class="card-body">', unsafe_allow_html=True)
    
    proj_day = st.date_input("📅 Projection Date", value=datetime.now(CT).date())
    
    # Get previous day OHLC for validation
    prev_ohlc = get_previous_day_ohlc(proj_day)
    if prev_ohlc:
        st.info(f"📊 Previous Session ({prev_ohlc['date']}): High ${prev_ohlc['high']:.2f} | Low ${prev_ohlc['low']:.2f} | Close ${prev_ohlc['close']:.2f}")
    
    st.markdown('<div class="anchor-grid">', unsafe_allow_html=True)
    
    # Skyline
    st.markdown('<div class="anchor-box">', unsafe_allow_html=True)
    st.markdown("#### ☁️ SKYLINE (Upper Anchor)")
    skyline_name = st.text_input("Custom Name", value="Skyline", key="sky_name")
    skyline_date = st.date_input("Date", value=proj_day - timedelta(days=1), key="sky_date")
    skyline_price = st.number_input("Price ($)", value=6634.70, step=0.01, key="sky_price", format="%.2f")
    skyline_time = st.time_input("Time (CT)", value=dtime(14, 30), step=1800, key="sky_time")
    
    # Validate
    val_status, val_msg = validate_anchor(skyline_price, skyline_name, prev_ohlc)
    st.markdown(f'<div class="validation-badge">{val_status} {val_msg}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Baseline
    st.markdown('<div class="anchor-box">', unsafe_allow_html=True)
    st.markdown("#### ⚓ BASELINE (Lower Anchor)")
    baseline_name = st.text_input("Custom Name", value="Baseline", key="base_name")
    baseline_date = st.date_input("Date", value=proj_day - timedelta(days=1), key="base_date")
    baseline_price = st.number_input("Price ($)", value=6600.00, step=0.01, key="base_price", format="%.2f")
    baseline_time = st.time_input("Time (CT)", value=dtime(14, 30), step=1800, key="base_time")
    
    val_status, val_msg = validate_anchor(baseline_price, baseline_name, prev_ohlc)
    st.markdown(f'<div class="validation-badge">{val_status} {val_msg}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div></div></div>', unsafe_allow_html=True)
    
    # Calculate projections
    slots = rth_slots_ct_dt(proj_day, "08:30", "14:00")
    
    sky_dt = CT.localize(datetime.combine(skyline_date, skyline_time))
    base_dt = CT.localize(datetime.combine(baseline_date, baseline_time))
    
    df_sky_bull = project_line(skyline_price, sky_dt, ASC_SLOPE, slots)
    df_sky_bear = project_line(skyline_price, sky_dt, DESC_SLOPE, slots)
    df_base_bull = project_line(baseline_price, base_dt, ASC_SLOPE, slots)
    df_base_bear = project_line(baseline_price, base_dt, DESC_SLOPE, slots)
    
    merged = pd.DataFrame({"Time (CT)": [dt.strftime("%I:%M %p") for dt in slots]})
    merged["Final Resistance"] = df_sky_bull["Price"]
    merged["Mid Support"] = df_sky_bear["Price"]
    merged["Mid Resistance"] = df_base_bull["Price"]
    merged["Final Support"] = df_base_bear["Price"]
    
    # Live Price Section
    spx_es_offset = calculate_spx_es_offset(skyline_date)
    live_spx = get_spx_equivalent_price(spx_es_offset)
    
    if live_spx:
        st.markdown(f"""
            <div class="live-ticker">
                <div class="ticker-label">📡 LIVE SPX EQUIVALENT PRICE</div>
                <div class="ticker-price">${live_spx:.2f}</div>
                <div class="ticker-label">ES Offset: {spx_es_offset:+.2f} | Updated: {datetime.now(CT).strftime('%I:%M:%S %p CT')}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Get current projections (find closest time or use opening)
        current_time = datetime.now(CT).strftime("%I:%M %p")
        if current_time in merged["Time (CT)"].values:
            current_row = merged[merged["Time (CT)"] == current_time].iloc[0]
        else:
            current_row = merged.iloc[0]  # Use market open
        
        current_projections = {
            "Final Resistance": current_row["Final Resistance"],
            "Mid Support": current_row["Mid Support"],
            "Mid Resistance": current_row["Mid Resistance"],
            "Final Support": current_row["Final Support"]
        }
        
        # Trading zone
        zone_name, zone_desc, zone_type = get_trading_zone(live_spx, current_projections)
        st.markdown(f"""
            <div class="zone-alert {zone_type}">
                <div class="zone-title">{zone_name}</div>
                <div class="zone-desc">{zone_desc}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Distances
        st.markdown('<div class="card"><div class="card-header"><div class="card-title"><span>📏</span> Distance to Key Levels</div></div><div class="card-body">', unsafe_allow_html=True)
        distances = calculate_distances(live_spx, current_projections)
        for name, dist in sorted(distances.items(), key=lambda x: x[1]):
            st.markdown(f'<div class="distance-item"><span class="distance-name">{name}</span><span class="distance-value">{dist:.2f} pts</span></div>', unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)
        
        # Playbook
        playbook = get_playbook(zone_name, current_projections)
        st.markdown(f"""
            <div class="playbook">
                <div class="playbook-title">📋 Trading Playbook</div>
                <div>{playbook}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Deviation alert
        all_proj = list(current_projections.values())
        if live_spx > max(all_proj):
            deviation = live_spx - max(all_proj)
            st.error(f"🚨 **BREAKOUT ALERT:** Price is {deviation:.2f} points ABOVE all projections!")
        elif live_spx < min(all_proj):
            deviation = min(all_proj) - live_spx
            st.error(f"🚨 **BREAKDOWN ALERT:** Price is {deviation:.2f} points BELOW all projections!")
    
    # Opening Gap Analysis
    st.markdown('<div class="card"><div class="card-header"><div class="card-title"><span>📊</span> Opening Gap Analysis</div></div><div class="card-body">', unsafe_allow_html=True)
    
    open_row = merged[merged["Time (CT)"] == "08:30 AM"].iloc[0]
    open_projections = {
        "Final Resistance": open_row["Final Resistance"],
        "Mid Support": open_row["Mid Support"],
        "Mid Resistance": open_row["Mid Resistance"],
        "Final Support": open_row["Final Support"]
    }
    
    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
    for name, price in open_projections.items():
        st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">{name}</div>
                <div class="metric-value">${price:.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    if live_spx:
        open_zone, _, _ = get_trading_zone(live_spx, open_projections)
        st.info(f"**Market opened in:** {open_zone}")
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # Expected Trading Range
    st.markdown('<div class="card"><div class="card-header"><div class="card-title"><span>📈</span> Expected Trading Range</div></div><div class="card-body">', unsafe_allow_html=True)
    
    all_prices = merged[["Final Resistance", "Mid Support", "Mid Resistance", "Final Support"]].values.flatten()
    expected_high = np.max(all_prices)
    expected_low = np.min(all_prices)
    expected_range = expected_high - expected_low
    expected_mid = (expected_high + expected_low) / 2
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Expected High", f"${expected_high:.2f}")
    col2.metric("Expected Low", f"${expected_low:.2f}")
    col3.metric("Range", f"${expected_range:.2f}")
    col4.metric("Midpoint", f"${expected_mid:.2f}")
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # Session Breakdown
    st.markdown('<div class="card"><div class="card-header"><div class="card-title"><span>⏰</span> Session Breakdown</div></div><div class="card-body">', unsafe_allow_html=True)
    
    st.markdown("#### 🌙 Pre-Market (Previous Day 2:00 PM - Today 8:30 AM)")
    st.caption("Anchors set during this period. Weekend gaps automatically handled.")
    
    st.markdown("#### 🔔 RTH Session (8:30 AM - 2:00 PM CT)")
    st.caption("Primary trading window. All projections displayed below.")
    
    st.markdown("#### 🌆 After Hours (2:00 PM - 4:00 PM CT)")
    st.caption("Extended session. Projections end at 2:00 PM.")
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # Results Table
    st.markdown('<div class="card"><div class="card-header"><div class="card-title"><span>📊</span> Complete Projection Matrix</div></div><div class="card-body">', unsafe_allow_html=True)
    st.dataframe(merged, use_container_width=True, hide_index=True, height=500)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Export
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.download_button("💾 Complete", merged.to_csv(index=False).encode(), "spx_prophet_complete.csv", "text/csv", use_container_width=True)
    with col2:
        st.download_button(f"☁️ {skyline_name}", merged[["Time (CT)", "Final Resistance", "Mid Support"]].to_csv(index=False).encode(), f"{skyline_name.lower()}.csv", "text/csv", use_container_width=True)
    with col3:
        st.download_button(f"⚓ {baseline_name}", merged[["Time (CT)", "Mid Resistance", "Final Support"]].to_csv(index=False).encode(), f"{baseline_name.lower()}.csv", "text/csv", use_container_width=True)
    with col4:
        analytics_export = pd.DataFrame({
            'Metric': ['Expected High', 'Expected Low', 'Range', 'Midpoint'],
            'Value': [expected_high, expected_low, expected_range, expected_mid]
        })
        st.download_button("📊 Analytics", analytics_export.to_csv(index=False).encode(), "analytics.csv", "text/csv", use_container_width=True)
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    st.markdown(f"""
        <div style="text-align: center; padding: 3rem 0; margin-top: 3rem; border-top: 1px solid #333; color: #666;">
            <strong>{APP_NAME}</strong> · {APP_VERSION} · © 2025<br>
            Built for institutional traders who demand precision
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()