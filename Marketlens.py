# app.py
# SPX PROPHET — Ultimate Professional Trading Platform
# Advanced dual-anchor system with manual live price tracking
# Built for serious institutional traders

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List, Dict, Tuple, Optional

APP_NAME = "SPX PROPHET"
APP_VERSION = "Ultimate Pro 4.0"
APP_TAGLINE = "Professional Market Projection Platform"

# ===============================
# CONFIGURATION
# ===============================

CT = pytz.timezone("America/Chicago")
ASC_SLOPE = 0.5412
DESC_SLOPE = -0.5412

# ===============================
# TIME & CALCULATIONS
# ===============================

def rth_slots_ct_dt(proj_date: date, start="08:30", end="14:00") -> List[datetime]:
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    start_dt = CT.localize(datetime.combine(proj_date, dtime(h1, m1)))
    end_dt = CT.localize(datetime.combine(proj_date, dtime(h2, m2)))
    idx = pd.date_range(start=start_dt, end=end_dt, freq="30min", tz=CT)
    return list(idx.to_pydatetime())

def count_blocks_with_maintenance_skip(start_dt: datetime, end_dt: datetime) -> int:
    """Count 30-minute blocks from start to end, skipping 4:00pm and 4:30pm maintenance"""
    blocks = 0
    current = start_dt
    
    while current < end_dt:
        # Skip BOTH 4:00pm and 4:30pm slots (maintenance window)
        if current.hour == 16 and current.minute in [0, 30]:
            current += timedelta(minutes=30)
            continue
        
        blocks += 1
        current += timedelta(minutes=30)
    
    return blocks

def project_line(anchor_price: float, anchor_time_ct: datetime, slope_per_block: float, rth_slots_ct: List[datetime]) -> pd.DataFrame:
    """Project prices from anchor point across RTH slots"""
    minute = 0 if anchor_time_ct.minute < 30 else 30
    anchor_aligned = anchor_time_ct.replace(minute=minute, second=0, microsecond=0)
    rows = []
    for dt in rth_slots_ct:
        blocks = count_blocks_with_maintenance_skip(anchor_aligned, dt)
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
    
    sorted_prices = sorted([final_resistance, mid_support, mid_resistance, final_support])
    
    if price >= max(sorted_prices):
        return "🔴 BREAKOUT ZONE", "Above all projections - Strong bullish breakout", "error"
    elif price <= min(sorted_prices):
        return "🔵 BREAKDOWN ZONE", "Below all projections - Strong bearish breakdown", "info"
    elif price >= final_resistance - 2:
        return "🟢 FINAL RESISTANCE ZONE", "SELL ZONE - Expect reversal down", "success"
    elif price <= final_support + 2:
        return "🟢 FINAL SUPPORT ZONE", "BUY ZONE - Expect reversal up", "success"
    elif price >= mid_resistance - 2:
        return "🟡 MID RESISTANCE ZONE", "Near resistance - Watch for rejection or breakout", "warning"
    elif price <= mid_support + 2:
        return "🟡 MID SUPPORT ZONE", "Near support - Watch for bounce or breakdown", "warning"
    else:
        return "⚪ NEUTRAL ZONE", "Between mid levels - Wait for direction", "info"

def calculate_distances(price: float, projections: Dict[str, float]) -> Dict[str, float]:
    """Calculate distance from current price to each projection"""
    return {
        name: round(price - proj_price, 2)  # Positive = above, negative = below
        for name, proj_price in projections.items()
    }

def get_playbook(zone_name: str, projections: Dict[str, float]) -> str:
    """Generate trading playbook based on zone"""
    if "FINAL SUPPORT" in zone_name:
        return f"📈 **BUY** from Final Support (${projections['Final Support']:.2f}) → Target Mid Resistance (${projections['Mid Resistance']:.2f}) or Final Resistance (${projections['Final Resistance']:.2f})"
    elif "FINAL RESISTANCE" in zone_name:
        return f"📉 **SELL** from Final Resistance (${projections['Final Resistance']:.2f}) → Target Mid Support (${projections['Mid Support']:.2f}) or Final Support (${projections['Final Support']:.2f})"
    elif "MID SUPPORT" in zone_name:
        return f"📉 **SHORT** to Final Support (${projections['Final Support']:.2f}), then **BUY** to Mid Resistance (${projections['Mid Resistance']:.2f})"
    elif "MID RESISTANCE" in zone_name:
        return f"📈 **BUY** to Final Resistance (${projections['Final Resistance']:.2f}), then **SELL** to Mid Support (${projections['Mid Support']:.2f})"
    elif "NEUTRAL" in zone_name:
        return f"⚖️ **WAIT** for directional move. BUY at ${projections['Mid Support']:.2f} or SELL at ${projections['Mid Resistance']:.2f}"
    elif "BREAKOUT" in zone_name:
        return f"🚀 **STRONG BULL** - Continuation likely. Trail stops, target higher prices"
    elif "BREAKDOWN" in zone_name:
        return f"💥 **STRONG BEAR** - Continuation likely. Trail stops, target lower prices"
    return "Monitor price action"

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
    
    section[data-testid="stSidebar"] {{ background: {c['surface']} !important; border-right: 1px solid {c['border']} !important; padding: 2rem 1.5rem !important; }}
    section[data-testid="stSidebar"] label {{ color: {c['secondary']} !important; font-weight: 700 !important; font-size: 0.75rem !important; text-transform: uppercase !important; letter-spacing: 0.05em !important; }}
    
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
    .metric-box {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; padding: 1.5rem; text-align: center; transition: all 0.2s; }}
    .metric-box:hover {{ border-color: {c['primary']}; box-shadow: 0 4px 16px {c['primary']}15; }}
    .metric-label {{ font-size: 0.7rem; font-weight: 800; color: {c['muted']}; text-transform: uppercase; margin-bottom: 0.75rem; letter-spacing: 0.05em; }}
    .metric-value {{ font-size: 1.875rem; font-weight: 900; font-family: 'JetBrains Mono'; color: {c['text']}; }}
    .metric-sub {{ font-size: 0.813rem; color: {c['secondary']}; margin-top: 0.5rem; }}
    
    .distance-item {{ display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.5rem; background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; margin: 0.5rem 0; }}
    .distance-name {{ font-weight: 700; color: {c['text']}; }}
    .distance-value {{ font-family: 'JetBrains Mono'; font-weight: 700; }}
    .distance-value.above {{ color: {c['success']}; }}
    .distance-value.below {{ color: {c['error']}; }}
    
    .playbook {{ background: linear-gradient(135deg, {c['primary']}12, {c['accent']}12); border: 2px solid {c['primary']}40; border-radius: 14px; padding: 1.75rem 2rem; margin: 1.5rem 0; }}
    .playbook-title {{ font-size: 1.25rem; font-weight: 800; margin-bottom: 1rem; }}
    
    .anchor-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin: 1.5rem 0; }}
    .anchor-box {{ background: {c['surface']}; border: 2px solid {c['border']}; border-radius: 14px; padding: 1.75rem; transition: all 0.3s; }}
    .anchor-box:hover {{ border-color: {c['primary']}; box-shadow: 0 0 20px {c['primary']}15; }}
    
    .stDataFrame {{ border: 1px solid {c['border']}; border-radius: 12px; overflow: hidden; }}
    .stDataFrame table {{ font-family: 'JetBrains Mono' !important; }}
    .stDataFrame thead th {{ background: {c['surface']} !important; color: {c['muted']} !important; font-weight: 900 !important; text-transform: uppercase !important; padding: 1.25rem !important; }}
    .stDataFrame tbody td {{ padding: 1rem 1.25rem !important; }}
    
    .stButton button, .stDownloadButton button {{ 
        background: linear-gradient(135deg, {c['primary']}, {c['accent']}) !important; 
        color: #000 !important; 
        border: none !important; 
        border-radius: 12px !important; 
        padding: 1rem 2rem !important; 
        font-weight: 800 !important; 
        text-transform: uppercase !important; 
        transition: all 0.3s !important; 
    }}
    .stButton button:hover, .stDownloadButton button:hover {{ transform: translateY(-2px) !important; box-shadow: 0 8px 24px {c['primary']}40 !important; }}
    
    .stNumberInput input, .stDateInput input, .stTimeInput input, .stTextInput input {{
        background: {c['elevated']} !important;
        border: 1.5px solid {c['border']} !important;
        border-radius: 10px !important;
        padding: 1rem !important;
        font-weight: 600 !important;
        font-family: 'JetBrains Mono' !important;
        color: {c['text']} !important;
    }}
    .stNumberInput input:focus, .stDateInput input:focus, .stTimeInput input:focus, .stTextInput input:focus {{
        border-color: {c['primary']} !important;
        box-shadow: 0 0 0 3px {c['primary']}20 !important;
    }}
    
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
        st.markdown("### 📊 Slope Config")
        st.info(f"**Ascending:** +{ASC_SLOPE}")
        st.info(f"**Descending:** {DESC_SLOPE}")
        
        st.markdown("---")
        st.markdown("### ℹ️ System Info")
        st.caption("🕐 Central Time (CT)")
        st.caption("📊 RTH: 8:30 AM - 2:00 PM")
        st.caption("⚠️ Excludes 4-5 PM maintenance")
        st.caption("🎯 Dual anchor system")
        st.caption("📈 4 projection lines")
        
        st.markdown("---")
        st.markdown("### 📖 Line Definitions")
        st.caption("**Final Resistance** = Ultimate sell zone")
        st.caption("**Mid Resistance** = Intermediate resistance")
        st.caption("**Mid Support** = Intermediate support")
        st.caption("**Final Support** = Ultimate buy zone")
    
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
    st.markdown('<div class="card"><div class="card-header"><div class="card-title"><span>⚙️</span> Anchor Configuration</div></div><div class="card-body">', unsafe_allow_html=True)
    
    proj_day = st.date_input("📅 Projection Date (CT)", value=datetime.now(CT).date())
    
    st.markdown('<div class="anchor-grid">', unsafe_allow_html=True)
    
    # Skyline
    st.markdown('<div class="anchor-box">', unsafe_allow_html=True)
    st.markdown("#### ☁️ SKYLINE (Upper Anchor)")
    skyline_name = st.text_input("Custom Name", value="Skyline", key="sky_name")
    skyline_date = st.date_input("Anchor Date", value=proj_day - timedelta(days=1), key="sky_date")
    skyline_price = st.number_input("Anchor Price ($)", value=6634.70, step=0.01, key="sky_price", format="%.2f")
    skyline_time = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="sky_time")
    st.caption("Final Resistance (sell zone) + Mid Support")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Baseline
    st.markdown('<div class="anchor-box">', unsafe_allow_html=True)
    st.markdown("#### ⚓ BASELINE (Lower Anchor)")
    baseline_name = st.text_input("Custom Name", value="Baseline", key="base_name")
    baseline_date = st.date_input("Anchor Date", value=proj_day - timedelta(days=1), key="base_date")
    baseline_price = st.number_input("Anchor Price ($)", value=6600.00, step=0.01, key="base_price", format="%.2f")
    baseline_time = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="base_time")
    st.caption("Final Support (buy zone) + Mid Resistance")
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
    
    # Live Price Input (Optional)
    st.markdown('<div class="card"><div class="card-header"><div class="card-title"><span>📊</span> Live Price Analysis (Optional)</div></div><div class="card-body">', unsafe_allow_html=True)
    
    st.markdown("Enter current SPX price to see live trading zones and analysis:")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        live_price = st.number_input("Current SPX Price ($)", value=0.00, step=0.01, key="live_price", format="%.2f")
    with col2:
        current_time_str = st.selectbox("At Time", merged["Time (CT)"].tolist(), index=0)
    
    if live_price > 0:
        st.markdown(f"""
            <div class="live-ticker">
                <div class="ticker-label">📊 CURRENT SPX PRICE</div>
                <div class="ticker-price">${live_price:.2f}</div>
                <div class="ticker-label">Analysis Time: {current_time_str}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Get projections for selected time
        current_row = merged[merged["Time (CT)"] == current_time_str].iloc[0]
        current_projections = {
            "Final Resistance": current_row["Final Resistance"],
            "Mid Support": current_row["Mid Support"],
            "Mid Resistance": current_row["Mid Resistance"],
            "Final Support": current_row["Final Support"]
        }
        
        # Trading zone
        zone_name, zone_desc, zone_type = get_trading_zone(live_price, current_projections)
        st.markdown(f"""
            <div class="zone-alert {zone_type}">
                <div class="zone-title">{zone_name}</div>
                <div class="zone-desc">{zone_desc}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Distances
        st.markdown("### 📏 Distance to Key Levels")
        distances = calculate_distances(live_price, current_projections)
        for name, dist in sorted(distances.items(), key=lambda x: abs(x[1])):
            direction = "above" if dist > 0 else "below"
            st.markdown(f"""
                <div class="distance-item">
                    <span class="distance-name">{name}</span>
                    <span class="distance-value {direction}">{dist:+.2f} pts</span>
                </div>
            """, unsafe_allow_html=True)
        
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
        if live_price > max(all_proj):
            deviation = live_price - max(all_proj)
            st.error(f"🚨 **BREAKOUT ALERT:** Price is {deviation:.2f} points ABOVE all projections!")
        elif live_price < min(all_proj):
            deviation = min(all_proj) - live_price
            st.error(f"🚨 **BREAKDOWN ALERT:** Price is {deviation:.2f} points BELOW all projections!")
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # Opening Analysis
    st.markdown('<div class="card"><div class="card-header"><div class="card-title"><span>📊</span> Market Open Analysis</div></div><div class="card-body">', unsafe_allow_html=True)
    
    open_row = merged[merged["Time (CT)"] == "08:30 AM"].iloc[0]
    
    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
    for col_name in ["Final Resistance", "Mid Resistance", "Mid Support", "Final Support"]:
        price = open_row[col_name]
        st.markdown(f"""
            <div class="metric-box">
                <div class="metric-label">{col_name}</div>
                <div class="metric-value">${price:.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # Expected Range
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
    
    # Results Table
    st.markdown('<div class="card"><div class="card-header"><div class="card-title"><span>📊</span> Complete Projection Matrix</div></div><div class="card-body">', unsafe_allow_html=True)
    st.dataframe(merged, use_container_width=True, hide_index=True, height=500)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Export
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.download_button("💾 Complete Dataset", merged.to_csv(index=False).encode(), "spx_prophet_complete.csv", "text/csv", use_container_width=True)
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
            <strong>{APP_NAME}</strong> · {APP_VERSION} · © 2025
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()