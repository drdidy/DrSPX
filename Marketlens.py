# app.py
# SPX PROPHET — Clean, functional trading platform that WORKS

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List, Dict, Tuple

APP_NAME = "SPX PROPHET"

CT = pytz.timezone("America/Chicago")
ASC_SLOPE = 0.5
DESC_SLOPE = -0.5

# ===============================
# CALCULATIONS
# ===============================

def rth_slots_ct_dt(proj_date: date, start="08:30", end="14:00") -> List[datetime]:
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    start_dt = CT.localize(datetime.combine(proj_date, dtime(h1, m1)))
    end_dt = CT.localize(datetime.combine(proj_date, dtime(h2, m2)))
    idx = pd.date_range(start=start_dt, end=end_dt, freq="30min", tz=CT)
    return list(idx.to_pydatetime())

def count_blocks_with_maintenance_skip(start_dt: datetime, end_dt: datetime) -> int:
    blocks = 0
    current = start_dt
    while current < end_dt:
        if current.hour == 16 and current.minute in [0, 30]:
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
        blocks = count_blocks_with_maintenance_skip(anchor_aligned, dt)
        price = anchor_price + (slope_per_block * blocks)
        rows.append({"Time": dt.strftime("%I:%M %p"), "Price": round(price, 2)})
    return pd.DataFrame(rows)

def get_trading_zone(price: float, projections: Dict[str, float]) -> Tuple[str, str]:
    final_resistance = projections['Final Resistance']
    mid_support = projections['Mid Support']
    mid_resistance = projections['Mid Resistance']
    final_support = projections['Final Support']
    
    sorted_prices = sorted([final_resistance, mid_support, mid_resistance, final_support])
    
    if price >= max(sorted_prices):
        return "🚀 BREAKOUT", "Above all projections - Strong bull"
    elif price <= min(sorted_prices):
        return "💥 BREAKDOWN", "Below all projections - Strong bear"
    elif price >= final_resistance - 2:
        return "🔴 FINAL RESISTANCE", "SELL ZONE - Expect reversal"
    elif price <= final_support + 2:
        return "🟢 FINAL SUPPORT", "BUY ZONE - Expect reversal"
    elif price >= mid_resistance - 2:
        return "🟠 MID RESISTANCE", "Watch for rejection"
    elif price <= mid_support + 2:
        return "🟡 MID SUPPORT", "Watch for bounce"
    else:
        return "⚪ NEUTRAL", "Between levels - Wait"

def calculate_distances(price: float, projections: Dict[str, float]) -> Dict[str, float]:
    return {name: round(price - proj_price, 2) for name, proj_price in projections.items()}

# ===============================
# MAIN APP
# ===============================

def main():
    st.set_page_config(page_title=APP_NAME, page_icon="📊", layout="wide")
    
    # Simple CSS - FOCUS ON TABLE VISIBILITY
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* CRITICAL: Make table text VISIBLE */
    .stDataFrame, .stDataFrame * {
        color: #FFFFFF !important;
        background-color: transparent !important;
    }
    
    .stDataFrame table {
        background-color: #1a1a1a !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 16px !important;
    }
    
    .stDataFrame thead th {
        background-color: #2a2a2a !important;
        color: #00ff88 !important;
        font-weight: 800 !important;
        font-size: 14px !important;
        padding: 16px !important;
        text-transform: uppercase !important;
        border-bottom: 2px solid #00ff88 !important;
    }
    
    .stDataFrame tbody td {
        background-color: #1a1a1a !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        padding: 14px !important;
        border-bottom: 1px solid #333333 !important;
    }
    
    .stDataFrame tbody tr:hover td {
        background-color: #2a2a2a !important;
        color: #00ff88 !important;
    }
    
    /* Rest of app styling */
    html, body, .main, .block-container {
        background: #0a0a0a !important;
        color: #FFFFFF !important;
    }
    
    h1, h2, h3, h4, h5, h6, p, div, span, label {
        color: #FFFFFF !important;
    }
    
    .main-header {
        text-align: center;
        padding: 40px 0;
        background: linear-gradient(135deg, #00ff88 0%, #00d4ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 60px;
        font-weight: 900;
        margin-bottom: 40px;
    }
    
    .card {
        background: #1a1a1a;
        border: 2px solid #333;
        border-radius: 16px;
        padding: 30px;
        margin: 20px 0;
    }
    
    .card:hover {
        border-color: #00ff88;
    }
    
    .card-title {
        font-size: 24px;
        font-weight: 800;
        color: #00ff88 !important;
        margin-bottom: 20px;
    }
    
    .price-box {
        background: #1a1a1a;
        border: 3px solid #00ff88;
        border-radius: 16px;
        padding: 40px;
        text-align: center;
        margin: 20px 0;
    }
    
    .price-display {
        font-size: 72px;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        color: #00ff88 !important;
    }
    
    .zone-box {
        background: #1a1a1a;
        border-left: 4px solid #00ff88;
        border-radius: 12px;
        padding: 24px;
        margin: 20px 0;
    }
    
    .zone-title {
        font-size: 28px;
        font-weight: 800;
        color: #00ff88 !important;
        margin-bottom: 10px;
    }
    
    .distance-item {
        background: #1a1a1a;
        border: 1px solid #333;
        border-radius: 10px;
        padding: 16px 24px;
        margin: 10px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .distance-item:hover {
        background: #2a2a2a;
        border-color: #00ff88;
    }
    
    .distance-name {
        font-size: 18px;
        font-weight: 700;
        color: #FFFFFF !important;
    }
    
    .distance-value {
        font-size: 20px;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .distance-value.above {
        color: #00ff88 !important;
    }
    
    .distance-value.below {
        color: #ff4444 !important;
    }
    
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 20px;
        margin: 20px 0;
    }
    
    .metric-card {
        background: #1a1a1a;
        border: 1px solid #333;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
    }
    
    .metric-card:hover {
        border-color: #00ff88;
    }
    
    .metric-label {
        font-size: 12px;
        font-weight: 700;
        color: #999 !important;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    
    .metric-value {
        font-size: 32px;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        color: #00ff88 !important;
    }
    
    /* Input fields */
    .stNumberInput input, .stDateInput input, .stTimeInput input, .stTextInput input, .stSelectbox select {
        background: #1a1a1a !important;
        border: 2px solid #333 !important;
        border-radius: 10px !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 16px !important;
        padding: 12px !important;
    }
    
    .stNumberInput input:focus, .stDateInput input:focus, .stTimeInput input:focus, .stTextInput input:focus {
        border-color: #00ff88 !important;
    }
    
    .stNumberInput label, .stDateInput label, .stTimeInput label, .stTextInput label, .stSelectbox label {
        color: #999 !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        text-transform: uppercase !important;
    }
    
    /* Buttons */
    .stButton button, .stDownloadButton button {
        background: linear-gradient(135deg, #00ff88, #00d4ff) !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 14px 28px !important;
        font-weight: 800 !important;
        font-size: 14px !important;
        text-transform: uppercase !important;
    }
    
    .stButton button:hover, .stDownloadButton button:hover {
        transform: translateY(-2px);
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #0a0a0a !important;
        border-right: 1px solid #333 !important;
    }
    
    section[data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }
    
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown('<div class="main-header">📊 SPX PROPHET</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        st.info(f"⬆️ Ascending: +{ASC_SLOPE}")
        st.info(f"⬇️ Descending: {DESC_SLOPE}")
        st.markdown("---")
        st.markdown("### ℹ️ Info")
        st.caption("🕐 Central Time (CT)")
        st.caption("📊 RTH: 8:30 AM - 2:00 PM")
        st.caption("⚠️ Skips 4-5 PM maintenance")
    
    # Configuration
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">⚙️ Anchor Configuration</div>', unsafe_allow_html=True)
    
    proj_day = st.date_input("📅 Projection Date", value=datetime.now(CT).date())
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### ☁️ SKYLINE (Upper)")
        skyline_name = st.text_input("Name", value="Skyline", key="sky_name")
        skyline_date = st.date_input("Date", value=proj_day - timedelta(days=1), key="sky_date")
        skyline_price = st.number_input("Price ($)", value=6634.70, step=0.01, key="sky_price", format="%.2f")
        skyline_time = st.time_input("Time (CT)", value=dtime(14, 30), step=1800, key="sky_time")
    
    with col2:
        st.markdown("#### ⚓ BASELINE (Lower)")
        baseline_name = st.text_input("Name", value="Baseline", key="base_name")
        baseline_date = st.date_input("Date", value=proj_day - timedelta(days=1), key="base_date")
        baseline_price = st.number_input("Price ($)", value=6600.00, step=0.01, key="base_price", format="%.2f")
        baseline_time = st.time_input("Time (CT)", value=dtime(14, 30), step=1800, key="base_time")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Calculate
    slots = rth_slots_ct_dt(proj_day, "08:30", "14:00")
    sky_dt = CT.localize(datetime.combine(skyline_date, skyline_time))
    base_dt = CT.localize(datetime.combine(baseline_date, baseline_time))
    
    df_sky_bull = project_line(skyline_price, sky_dt, ASC_SLOPE, slots)
    df_sky_bear = project_line(skyline_price, sky_dt, DESC_SLOPE, slots)
    df_base_bull = project_line(baseline_price, base_dt, ASC_SLOPE, slots)
    df_base_bear = project_line(baseline_price, base_dt, DESC_SLOPE, slots)
    
    merged = pd.DataFrame({"Time (CT)": [dt.strftime("%I:%M %p") for dt in slots]})
    merged["🔴 Final Resistance"] = df_sky_bull["Price"]
    merged["🟡 Mid Support"] = df_sky_bear["Price"]
    merged["🟠 Mid Resistance"] = df_base_bull["Price"]
    merged["🟢 Final Support"] = df_base_bear["Price"]
    
    # Live Price
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📊 Live Price Analysis</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        live_price = st.number_input("💵 Current SPX Price", value=0.00, step=0.01, key="live_price", format="%.2f")
    with col2:
        current_time_str = st.selectbox("Time", merged["Time (CT)"].tolist(), index=0)
    
    if live_price > 0:
        st.markdown(f'<div class="price-box"><div class="price-display">${live_price:.2f}</div><div style="margin-top: 10px; color: #999;">at {current_time_str}</div></div>', unsafe_allow_html=True)
        
        current_row = merged[merged["Time (CT)"] == current_time_str].iloc[0]
        current_projections = {
            "Final Resistance": current_row["🔴 Final Resistance"],
            "Mid Support": current_row["🟡 Mid Support"],
            "Mid Resistance": current_row["🟠 Mid Resistance"],
            "Final Support": current_row["🟢 Final Support"]
        }
        
        zone_name, zone_desc = get_trading_zone(live_price, current_projections)
        st.markdown(f'<div class="zone-box"><div class="zone-title">{zone_name}</div><div style="color: #ccc; font-size: 18px;">{zone_desc}</div></div>', unsafe_allow_html=True)
        
        st.markdown("### 📏 Distance to Levels")
        distances = calculate_distances(live_price, current_projections)
        for name, dist in sorted(distances.items(), key=lambda x: abs(x[1])):
            direction = "above" if dist > 0 else "below"
            icon = "🔴" if "Final Resistance" in name else "🟡" if "Mid Support" in name else "🟠" if "Mid Resistance" in name else "🟢"
            st.markdown(f'<div class="distance-item"><span class="distance-name">{icon} {name}</span><span class="distance-value {direction}">{dist:+.2f} pts</span></div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Market Open
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🌅 Market Open (8:30 AM)</div>', unsafe_allow_html=True)
    
    open_row = merged[merged["Time (CT)"] == "08:30 AM"].iloc[0]
    
    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
    for col_name in ["🔴 Final Resistance", "🟠 Mid Resistance", "🟡 Mid Support", "🟢 Final Support"]:
        price = open_row[col_name]
        st.markdown(f'<div class="metric-card"><div class="metric-label">{col_name}</div><div class="metric-value">${price:.2f}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Expected Range
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📈 Expected Range</div>', unsafe_allow_html=True)
    
    all_prices = merged[["🔴 Final Resistance", "🟡 Mid Support", "🟠 Mid Resistance", "🟢 Final Support"]].values.flatten()
    expected_high = np.max(all_prices)
    expected_low = np.min(all_prices)
    expected_range = expected_high - expected_low
    expected_mid = (expected_high + expected_low) / 2
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("High", f"${expected_high:.2f}")
    col2.metric("Low", f"${expected_low:.2f}")
    col3.metric("Range", f"${expected_range:.2f}")
    col4.metric("Mid", f"${expected_mid:.2f}")
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # TABLE - THE CRITICAL PART
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📊 Complete Projection Matrix</div>', unsafe_allow_html=True)
    
    st.dataframe(merged, use_container_width=True, hide_index=True, height=500)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Export
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.download_button("💾 Complete", merged.to_csv(index=False).encode(), "spx_complete.csv", "text/csv", use_container_width=True)
    with col2:
        st.download_button(f"☁️ {skyline_name}", merged[["Time (CT)", "🔴 Final Resistance", "🟡 Mid Support"]].to_csv(index=False).encode(), f"{skyline_name.lower()}.csv", "text/csv", use_container_width=True)
    with col3:
        st.download_button(f"⚓ {baseline_name}", merged[["Time (CT)", "🟠 Mid Resistance", "🟢 Final Support"]].to_csv(index=False).encode(), f"{baseline_name.lower()}.csv", "text/csv", use_container_width=True)
    with col4:
        st.download_button("📊 Analytics", pd.DataFrame({'Metric': ['High', 'Low', 'Range', 'Mid'], 'Value': [expected_high, expected_low, expected_range, expected_mid]}).to_csv(index=False).encode(), "analytics.csv", "text/csv", use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()