# app.py
# SPX PROPHET — Clean, functional trading platform with Fibonacci tools

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List, Dict, Tuple

APP_NAME = "SPX PROPHET"

CT = pytz.timezone("America/Chicago")
ASC_SLOPE = 0.493
DESC_SLOPE = -0.493

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

def calculate_fibonacci_retracements(high: float, low: float) -> Dict[str, float]:
    """Calculate Fibonacci retracement levels from contract high/low"""
    range_size = high - low
    return {
        "0.618": round(high - (range_size * 0.618), 2),
        "0.786": round(high - (range_size * 0.786), 2),
        "0.500": round(high - (range_size * 0.500), 2),
        "0.382": round(high - (range_size * 0.382), 2),
        "0.236": round(high - (range_size * 0.236), 2)
    }

# ===============================
# MAIN APP
# ===============================

def main():
    st.set_page_config(page_title=APP_NAME, page_icon="📊", layout="wide")
    
    # Simple CSS
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
    
    .fib-result {
        background: #1a1a1a;
        border: 2px solid #00ff88;
        border-radius: 12px;
        padding: 20px 30px;
        margin: 15px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .fib-label {
        font-size: 18px;
        font-weight: 700;
        color: #FFFFFF !important;
    }
    
    .fib-value {
        font-size: 28px;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        color: #00ff88 !important;
    }
    
    .bias-indicator {
        background: #1a1a1a;
        border: 3px solid;
        border-radius: 16px;
        padding: 30px;
        margin: 20px 0;
        text-align: center;
    }
    
    .bias-indicator.bullish {
        border-color: #00ff88;
    }
    
    .bias-indicator.bearish {
        border-color: #ff4444;
    }
    
    .bias-title {
        font-size: 36px;
        font-weight: 900;
        margin-bottom: 10px;
    }
    
    .bias-title.bullish {
        color: #00ff88 !important;
    }
    
    .bias-title.bearish {
        color: #ff4444 !important;
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
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: #1a1a1a !important;
        border: 2px solid #333 !important;
        border-radius: 10px !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        padding: 12px 24px !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: #00ff88 !important;
        color: #000000 !important;
        border-color: #00ff88 !important;
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
        st.markdown("---")
        st.markdown("### 📖 Line Definitions")
        st.caption("🔴 **Bull Target** = Extreme upside")
        st.caption("🟠 **Resistance Pivot** = Key resistance")
        st.caption("🟡 **Support Pivot** = Key support")
        st.caption("🟢 **Bear Target** = Extreme downside")
        st.markdown("---")
        st.markdown("### 🎯 Bias Rules")
        st.caption("Above both ascending lines = **BULLISH**")
        st.caption("Below both ascending lines = **BEARISH**")
    
    # Tabs
    tab1, tab2 = st.tabs(["📊 Projection Calculator", "📐 Fibonacci Tool"])
    
    with tab1:
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
        merged["🔴 Bull Target"] = df_sky_bull["Price"]
        merged["🟡 Support Pivot"] = df_sky_bear["Price"]
        merged["🟠 Resistance Pivot"] = df_base_bull["Price"]
        merged["🟢 Bear Target"] = df_base_bear["Price"]
        
        # Market Open
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🌅 Market Open (8:30 AM)</div>', unsafe_allow_html=True)
        
        open_row = merged[merged["Time (CT)"] == "08:30 AM"].iloc[0]
        
        st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
        for col_name in ["🔴 Bull Target", "🟠 Resistance Pivot", "🟡 Support Pivot", "🟢 Bear Target"]:
            price = open_row[col_name]
            st.markdown(f'<div class="metric-card"><div class="metric-label">{col_name}</div><div class="metric-value">${price:.2f}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Bias Indicator
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🎯 Daily Bias Indicator</div>', unsafe_allow_html=True)
        
        st.markdown("Enter current price to determine market bias:")
        current_price = st.number_input("💵 Current SPX Price", value=0.00, step=0.01, key="current_price", format="%.2f")
        
        if current_price > 0:
            # Get the two ascending lines at current time (use market open for simplicity)
            bull_target = open_row["🔴 Bull Target"]
            resistance_pivot = open_row["🟠 Resistance Pivot"]
            
            # Check if above both ascending lines
            if current_price > bull_target and current_price > resistance_pivot:
                st.markdown(f'''
                    <div class="bias-indicator bullish">
                        <div class="bias-title bullish">🚀 BULLISH BIAS</div>
                        <div style="color: #FFFFFF; font-size: 18px;">Price ${current_price:.2f} is ABOVE both ascending lines</div>
                        <div style="color: #00ff88; font-size: 16px; margin-top: 10px;">Bull Target: ${bull_target:.2f} | Resistance Pivot: ${resistance_pivot:.2f}</div>
                    </div>
                ''', unsafe_allow_html=True)
            elif current_price < bull_target and current_price < resistance_pivot:
                st.markdown(f'''
                    <div class="bias-indicator bearish">
                        <div class="bias-title bearish">💥 BEARISH BIAS</div>
                        <div style="color: #FFFFFF; font-size: 18px;">Price ${current_price:.2f} is BELOW both ascending lines</div>
                        <div style="color: #ff4444; font-size: 16px; margin-top: 10px;">Bull Target: ${bull_target:.2f} | Resistance Pivot: ${resistance_pivot:.2f}</div>
                    </div>
                ''', unsafe_allow_html=True)
            else:
                st.markdown(f'''
                    <div class="bias-indicator" style="border-color: #ffaa00;">
                        <div class="bias-title" style="color: #ffaa00 !important;">⚠️ NEUTRAL/MIXED</div>
                        <div style="color: #FFFFFF; font-size: 18px;">Price ${current_price:.2f} is between the ascending lines</div>
                        <div style="color: #ffaa00; font-size: 16px; margin-top: 10px;">Bull Target: ${bull_target:.2f} | Resistance Pivot: ${resistance_pivot:.2f}</div>
                    </div>
                ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Expected Range
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📈 Expected Range</div>', unsafe_allow_html=True)
        
        all_prices = merged[["🔴 Bull Target", "🟡 Support Pivot", "🟠 Resistance Pivot", "🟢 Bear Target"]].values.flatten()
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
        
        # TABLE
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📊 Complete Projection Matrix</div>', unsafe_allow_html=True)
        
        st.dataframe(merged, use_container_width=True, hide_index=True, height=500)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Export
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.download_button("💾 Complete", merged.to_csv(index=False).encode(), "spx_complete.csv", "text/csv", use_container_width=True)
        with col2:
            st.download_button(f"☁️ {skyline_name}", merged[["Time (CT)", "🔴 Bull Target", "🟡 Support Pivot"]].to_csv(index=False).encode(), f"{skyline_name.lower()}.csv", "text/csv", use_container_width=True)
        with col3:
            st.download_button(f"⚓ {baseline_name}", merged[["Time (CT)", "🟠 Resistance Pivot", "🟢 Bear Target"]].to_csv(index=False).encode(), f"{baseline_name.lower()}.csv", "text/csv", use_container_width=True)
        with col4:
            st.download_button("📊 Analytics", pd.DataFrame({'Metric': ['High', 'Low', 'Range', 'Mid'], 'Value': [expected_high, expected_low, expected_range, expected_mid]}).to_csv(index=False).encode(), "analytics.csv", "text/csv", use_container_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        # Fibonacci Calculator
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📐 Fibonacci Retracement Calculator</div>', unsafe_allow_html=True)
        
        st.markdown("Enter the contract high and low to calculate key Fibonacci retracement entry levels:")
        
        col1, col2 = st.columns(2)
        with col1:
            fib_high = st.number_input("📈 Contract High ($)", value=0.00, step=0.01, key="fib_high", format="%.2f")
        with col2:
            fib_low = st.number_input("📉 Contract Low ($)", value=0.00, step=0.01, key="fib_low", format="%.2f")
        
        if fib_high > 0 and fib_low > 0 and fib_high > fib_low:
            fib_levels = calculate_fibonacci_retracements(fib_high, fib_low)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 🎯 Key Entry Levels")
            
            # Highlight the main entry levels
            st.markdown(f'''
                <div class="fib-result" style="border-width: 3px;">
                    <div>
                        <div class="fib-label">🎯 0.618 Retracement (Primary Entry)</div>
                        <div style="color: #999; font-size: 14px; margin-top: 5px;">Golden ratio - Strongest support/resistance</div>
                    </div>
                    <div class="fib-value">${fib_levels['0.618']}</div>
                </div>
            ''', unsafe_allow_html=True)
            
            st.markdown(f'''
                <div class="fib-result" style="border-width: 3px;">
                    <div>
                        <div class="fib-label">🎯 0.786 Retracement (Secondary Entry)</div>
                        <div style="color: #999; font-size: 14px; margin-top: 5px;">Deep retracement - Last line of defense</div>
                    </div>
                    <div class="fib-value">${fib_levels['0.786']}</div>
                </div>
            ''', unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 📊 All Fibonacci Levels")
            
            # Show all levels
            for level, price in fib_levels.items():
                st.markdown(f'''
                    <div class="fib-result">
                        <div class="fib-label">{level} Level</div>
                        <div class="fib-value">${price}</div>
                    </div>
                ''', unsafe_allow_html=True)
            
            # Summary
            st.markdown("<br>", unsafe_allow_html=True)
            st.info(f"📊 **Range:** ${fib_high:.2f} - ${fib_low:.2f} = ${fib_high - fib_low:.2f}")
            
        elif fib_high > 0 and fib_low > 0 and fib_high <= fib_low:
            st.error("⚠️ Contract High must be greater than Contract Low")
        
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()