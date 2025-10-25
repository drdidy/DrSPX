# app.py
# SPX PROPHET - Professional Trading Platform

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List, Dict, Tuple

APP_NAME = "SPX PROPHET"
CT = pytz.timezone("America/Chicago")
ASC_SLOPE = 0.475
DESC_SLOPE = -0.475

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

def project_line(anchor_price: float, anchor_time_ct: datetime, slope: float, slots: List[datetime]) -> pd.DataFrame:
    minute = 0 if anchor_time_ct.minute < 30 else 30
    anchor_aligned = anchor_time_ct.replace(minute=minute, second=0, microsecond=0)
    rows = []
    for dt in slots:
        blocks = count_blocks_with_maintenance_skip(anchor_aligned, dt)
        price = anchor_price + (slope * blocks)
        rows.append({"Time": dt.strftime("%I:%M %p"), "Price": round(price, 2)})
    return pd.DataFrame(rows)

def calculate_sd_zones(breakout: float, bull_pivot: float, bear_pivot: float, breakdown: float) -> Dict:
    upper_width = breakout - bull_pivot
    lower_width = bear_pivot - breakdown
    pivot_spread = bull_pivot - bear_pivot
    
    upper_sd_center = breakout + pivot_spread
    lower_sd_center = breakdown - pivot_spread
    
    return {
        "extension_target": upper_sd_center + upper_width,
        "capitulation_target": lower_sd_center - lower_width
    }

def calculate_fibonacci(high: float, low: float) -> Dict[str, float]:
    range_size = high - low
    return {
        "0.618": round(high - (range_size * 0.618), 2),
        "0.786": round(high - (range_size * 0.786), 2),
        "0.500": round(high - (range_size * 0.500), 2),
        "0.382": round(high - (range_size * 0.382), 2),
        "0.236": round(high - (range_size * 0.236), 2)
    }

def main():
    st.set_page_config(page_title=APP_NAME, page_icon="◈", layout="wide")
    
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Outfit', sans-serif;
        letter-spacing: -0.01em;
    }
    
    html, body, .main, .block-container {
        background: linear-gradient(135deg, #0f1419 0%, #1a1f2e 100%);
        color: #e8eaed;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0f1419 0%, #1a1f2e 100%);
    }
    
    h1, h2, h3, h4, h5, h6, p, div, span, label {
        color: #e8eaed;
    }
    
    /* Header */
    .prophet-header {
        position: relative;
        text-align: center;
        padding: 60px 40px 40px 40px;
        margin-bottom: 40px;
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.05) 0%, rgba(100, 149, 237, 0.05) 100%);
        border-radius: 24px;
        border: 1px solid rgba(218, 165, 32, 0.1);
        backdrop-filter: blur(20px);
        box-shadow: 
            0 20px 60px rgba(0, 0, 0, 0.5),
            inset 0 1px 0 rgba(255, 255, 255, 0.1),
            0 0 80px rgba(218, 165, 32, 0.1);
    }
    
    .prophet-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 60%;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(218, 165, 32, 0.5), transparent);
    }
    
    .prophet-logo {
        font-size: 56px;
        font-weight: 900;
        background: linear-gradient(135deg, #daa520 0%, #6495ed 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 40px rgba(218, 165, 32, 0.3);
        letter-spacing: 0.05em;
        margin: 0;
    }
    
    .prophet-subtitle {
        font-size: 14px;
        font-weight: 600;
        color: #7d8590;
        text-transform: uppercase;
        letter-spacing: 0.2em;
        margin-top: 16px;
    }
    
    /* Cards */
    .premium-card {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.8) 0%, rgba(15, 20, 25, 0.9) 100%);
        border: 1px solid rgba(218, 165, 32, 0.15);
        border-radius: 20px;
        padding: 32px;
        margin: 24px 0;
        position: relative;
        backdrop-filter: blur(10px);
        box-shadow: 
            0 10px 40px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 rgba(255, 255, 255, 0.05);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .premium-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(218, 165, 32, 0.3), transparent);
        opacity: 0;
        transition: opacity 0.4s ease;
    }
    
    .premium-card:hover {
        transform: translateY(-4px);
        border-color: rgba(218, 165, 32, 0.3);
        box-shadow: 
            0 20px 60px rgba(0, 0, 0, 0.6),
            inset 0 1px 0 rgba(255, 255, 255, 0.1),
            0 0 40px rgba(218, 165, 32, 0.15);
    }
    
    .premium-card:hover::before {
        opacity: 1;
    }
    
    .card-title {
        font-size: 20px;
        font-weight: 700;
        color: #daa520;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    /* Metrics */
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin: 24px 0;
    }
    
    .metric-card {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.05) 0%, rgba(100, 149, 237, 0.05) 100%);
        border: 1px solid rgba(218, 165, 32, 0.15);
        border-radius: 16px;
        padding: 24px 20px;
        text-align: center;
        position: relative;
        overflow: hidden;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 2px;
        background: linear-gradient(90deg, transparent, rgba(218, 165, 32, 0.5), transparent);
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(218, 165, 32, 0.3);
        box-shadow: 0 8px 32px rgba(218, 165, 32, 0.15);
    }
    
    .metric-card:hover::before {
        opacity: 1;
    }
    
    .metric-label {
        font-size: 11px;
        font-weight: 700;
        color: #7d8590;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 12px;
    }
    
    .metric-value {
        font-size: 28px;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #daa520, #6495ed);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* SD Zones */
    .zone-card {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.08) 0%, rgba(100, 149, 237, 0.08) 100%);
        border: 2px solid rgba(218, 165, 32, 0.2);
        border-radius: 16px;
        padding: 24px;
        margin: 16px 0;
        position: relative;
        backdrop-filter: blur(10px);
        box-shadow: 
            0 8px 32px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.05);
    }
    
    .zone-card.upper {
        border-color: rgba(34, 197, 94, 0.3);
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.08) 0%, rgba(34, 197, 94, 0.03) 100%);
    }
    
    .zone-card.lower {
        border-color: rgba(239, 68, 68, 0.3);
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(239, 68, 68, 0.03) 100%);
    }
    
    .zone-title {
        font-size: 16px;
        font-weight: 700;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .zone-range {
        font-size: 24px;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .zone-range.upper {
        color: #22c55e;
    }
    
    .zone-range.lower {
        color: #ef4444;
    }
    
    /* Bias Indicator */
    .bias-card {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.1) 0%, rgba(100, 149, 237, 0.1) 100%);
        border: 2px solid rgba(218, 165, 32, 0.3);
        border-radius: 20px;
        padding: 32px;
        margin: 24px 0;
        text-align: center;
        backdrop-filter: blur(10px);
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
    }
    
    .bias-card.bullish {
        border-color: rgba(34, 197, 94, 0.4);
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(34, 197, 94, 0.05) 100%);
        box-shadow: 0 10px 40px rgba(34, 197, 94, 0.2);
    }
    
    .bias-card.bearish {
        border-color: rgba(239, 68, 68, 0.4);
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(239, 68, 68, 0.05) 100%);
        box-shadow: 0 10px 40px rgba(239, 68, 68, 0.2);
    }
    
    .bias-title {
        font-size: 32px;
        font-weight: 900;
        margin-bottom: 12px;
    }
    
    .bias-title.bullish {
        color: #22c55e;
        text-shadow: 0 0 20px rgba(34, 197, 94, 0.5);
    }
    
    .bias-title.bearish {
        color: #ef4444;
        text-shadow: 0 0 20px rgba(239, 68, 68, 0.5);
    }
    
    /* Fibonacci */
    .fib-result {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.6) 0%, rgba(15, 20, 25, 0.8) 100%);
        border: 1px solid rgba(218, 165, 32, 0.2);
        border-radius: 12px;
        padding: 20px 28px;
        margin: 12px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }
    
    .fib-result:hover {
        transform: translateX(4px);
        border-color: rgba(218, 165, 32, 0.4);
        box-shadow: 0 4px 20px rgba(218, 165, 32, 0.15);
    }
    
    .fib-result.primary {
        border-width: 2px;
        border-color: rgba(218, 165, 32, 0.4);
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.1) 0%, rgba(100, 149, 237, 0.1) 100%);
    }
    
    .fib-label {
        font-size: 15px;
        font-weight: 600;
        color: #e8eaed;
    }
    
    .fib-value {
        font-size: 24px;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #daa520;
    }
    
    /* Table */
    .stDataFrame {
        border: 1px solid rgba(218, 165, 32, 0.2);
        border-radius: 16px;
        overflow: hidden;
        backdrop-filter: blur(10px);
    }
    
    .stDataFrame table {
        font-family: 'JetBrains Mono', monospace;
        background: transparent;
    }
    
    .stDataFrame thead th {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.15), rgba(100, 149, 237, 0.15)) !important;
        color: #daa520 !important;
        font-weight: 800 !important;
        font-size: 12px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        padding: 18px 16px !important;
        border-bottom: 2px solid rgba(218, 165, 32, 0.3) !important;
    }
    
    .stDataFrame tbody td {
        background: rgba(15, 20, 25, 0.4) !important;
        color: #e8eaed !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        padding: 16px !important;
        border-bottom: 1px solid rgba(218, 165, 32, 0.1) !important;
    }
    
    .stDataFrame tbody tr:hover td {
        background: rgba(218, 165, 32, 0.08) !important;
    }
    
    /* Inputs */
    .stNumberInput input, .stDateInput input, .stTimeInput input, .stTextInput input {
        background: rgba(15, 20, 25, 0.6) !important;
        border: 1.5px solid rgba(218, 165, 32, 0.2) !important;
        border-radius: 10px !important;
        color: #e8eaed !important;
        font-weight: 600 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 15px !important;
        padding: 12px 16px !important;
        transition: all 0.3s ease !important;
    }
    
    .stNumberInput input:focus, .stDateInput input:focus, .stTimeInput input:focus, .stTextInput input:focus {
        border-color: rgba(218, 165, 32, 0.5) !important;
        box-shadow: 0 0 0 3px rgba(218, 165, 32, 0.1) !important;
        background: rgba(15, 20, 25, 0.8) !important;
    }
    
    .stNumberInput label, .stDateInput label, .stTimeInput label, .stTextInput label {
        color: #7d8590 !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    
    /* Buttons */
    .stButton button, .stDownloadButton button {
        background: linear-gradient(135deg, #daa520, #6495ed) !important;
        color: #0f1419 !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 14px 32px !important;
        font-weight: 800 !important;
        font-size: 13px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 6px 20px rgba(218, 165, 32, 0.3) !important;
    }
    
    .stButton button:hover, .stDownloadButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 30px rgba(218, 165, 32, 0.5) !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
        border-bottom: 1px solid rgba(218, 165, 32, 0.2);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border: none;
        color: #7d8590;
        font-weight: 600;
        padding: 12px 24px;
        transition: all 0.3s ease;
    }
    
    .stTabs [aria-selected="true"] {
        color: #daa520;
        border-bottom: 2px solid #daa520;
    }
    
    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(15, 20, 25, 0.95) 0%, rgba(26, 31, 46, 0.95) 100%);
        border-right: 1px solid rgba(218, 165, 32, 0.15);
        backdrop-filter: blur(20px);
    }
    
    section[data-testid="stSidebar"] * {
        color: #e8eaed;
    }
    
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        st.info(f"Ascending: +{ASC_SLOPE}")
        st.info(f"Descending: {DESC_SLOPE}")
        st.markdown("---")
        st.markdown("### ℹ️ System")
        st.caption("Central Time (CT)")
        st.caption("RTH: 8:30 AM - 2:00 PM")
        st.caption("Maintenance: 4-5 PM excluded")
        st.markdown("---")
        st.markdown("### 📊 Lines")
        st.caption("🚀 Breakout Target")
        st.caption("📈 Bull Pivot")
        st.caption("📉 Bear Pivot")
        st.caption("💥 Breakdown Target")
        st.caption("☁️ Extension Target")
        st.caption("🔥 Capitulation Target")
    
    st.markdown("""
        <div class="prophet-header">
            <div class="prophet-logo">◈ SPX PROPHET</div>
            <div class="prophet-subtitle">Professional Trading Platform</div>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📊 Projection System", "📐 Fibonacci Calculator"])
    
    with tab1:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">⚙️ Anchor Configuration</div>', unsafe_allow_html=True)
        
        proj_day = st.date_input("Projection Date", value=datetime.now(CT).date())
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Skyline (Upper)")
            skyline_date = st.date_input("Date", value=proj_day - timedelta(days=1), key="sky_date")
            skyline_price = st.number_input("Price ($)", value=6634.70, step=0.01, key="sky_price", format="%.2f")
            skyline_time = st.time_input("Time (CT)", value=dtime(14, 30), step=1800, key="sky_time")
        
        with col2:
            st.markdown("#### Baseline (Lower)")
            baseline_date = st.date_input("Date", value=proj_day - timedelta(days=1), key="base_date")
            baseline_price = st.number_input("Price ($)", value=6600.00, step=0.01, key="base_price", format="%.2f")
            baseline_time = st.time_input("Time (CT)", value=dtime(14, 30), step=1800, key="base_time")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        slots = rth_slots_ct_dt(proj_day, "08:30", "14:00")
        sky_dt = CT.localize(datetime.combine(skyline_date, skyline_time))
        base_dt = CT.localize(datetime.combine(baseline_date, baseline_time))
        
        df_breakout = project_line(skyline_price, sky_dt, ASC_SLOPE, slots)
        df_support_pivot = project_line(skyline_price, sky_dt, DESC_SLOPE, slots)
        df_bull_pivot = project_line(baseline_price, base_dt, ASC_SLOPE, slots)
        df_breakdown = project_line(baseline_price, base_dt, DESC_SLOPE, slots)
        
        merged = pd.DataFrame({"Time (CT)": [dt.strftime("%I:%M %p") for dt in slots]})
        merged["🚀 Breakout Target"] = df_breakout["Price"]
        merged["📈 Bull Pivot"] = df_bull_pivot["Price"]
        merged["📉 Bear Pivot"] = df_support_pivot["Price"]
        merged["💥 Breakdown Target"] = df_breakdown["Price"]
        
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🌅 Market Open Analysis</div>', unsafe_allow_html=True)
        
        open_row = merged[merged["Time (CT)"] == "08:30 AM"].iloc[0]
        breakout = open_row["🚀 Breakout Target"]
        bull_pivot = open_row["📈 Bull Pivot"]
        bear_pivot = open_row["📉 Bear Pivot"]
        breakdown = open_row["💥 Breakdown Target"]
        
        st.markdown('<div class="metrics-grid">', unsafe_allow_html=True)
        for col_name in ["🚀 Breakout Target", "📈 Bull Pivot", "📉 Bear Pivot", "💥 Breakdown Target"]:
            price = open_row[col_name]
            st.markdown(f'<div class="metric-card"><div class="metric-label">{col_name}</div><div class="metric-value">${price:.2f}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        sd_zones = calculate_sd_zones(breakout, bull_pivot, bear_pivot, breakdown)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f'''
                <div class="zone-card upper">
                    <div class="zone-title">☁️ Extension Target</div>
                    <div class="zone-range upper">${sd_zones['extension_target']:.2f}</div>
                </div>
            ''', unsafe_allow_html=True)
        
        with col2:
            st.markdown(f'''
                <div class="zone-card lower">
                    <div class="zone-title">🔥 Capitulation Target</div>
                    <div class="zone-range lower">${sd_zones['capitulation_target']:.2f}</div>
                </div>
            ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🎯 Daily Bias</div>', unsafe_allow_html=True)
        
        current_price = st.number_input("Current SPX Price", value=0.00, step=0.01, key="current_price", format="%.2f")
        
        if current_price > 0:
            if current_price > breakout and current_price > bull_pivot:
                st.markdown(f'''
                    <div class="bias-card bullish">
                        <div class="bias-title bullish">🚀 BULLISH</div>
                        <div style="color: #e8eaed; font-size: 16px;">Price ${current_price:.2f} above ascending lines</div>
                        <div style="color: #22c55e; font-size: 14px; margin-top: 8px;">Target: Extension Target</div>
                    </div>
                ''', unsafe_allow_html=True)
            elif current_price < breakout and current_price < bull_pivot:
                st.markdown(f'''
                    <div class="bias-card bearish">
                        <div class="bias-title bearish">💥 BEARISH</div>
                        <div style="color: #e8eaed; font-size: 16px;">Price ${current_price:.2f} below ascending lines</div>
                        <div style="color: #ef4444; font-size: 14px; margin-top: 8px;">Target: Capitulation Target</div>
                    </div>
                ''', unsafe_allow_html=True)
            else:
                st.markdown(f'''
                    <div class="bias-card">
                        <div class="bias-title" style="color: #daa520;">⚖️ NEUTRAL</div>
                        <div style="color: #e8eaed; font-size: 16px;">Price ${current_price:.2f} between ascending lines</div>
                    </div>
                ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📊 Complete Projection Matrix</div>', unsafe_allow_html=True)
        st.dataframe(merged, use_container_width=True, hide_index=True, height=500)
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button("Complete Dataset", merged.to_csv(index=False).encode(), "spx_complete.csv", "text/csv", use_container_width=True)
        with col2:
            st.download_button("Skyline Data", merged[["Time (CT)", "🚀 Breakout Target", "📉 Bear Pivot"]].to_csv(index=False).encode(), "skyline.csv", "text/csv", use_container_width=True)
        with col3:
            st.download_button("Baseline Data", merged[["Time (CT)", "📈 Bull Pivot", "💥 Breakdown Target"]].to_csv(index=False).encode(), "baseline.csv", "text/csv", use_container_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📐 Fibonacci Retracement</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            fib_high = st.number_input("Contract High ($)", value=0.00, step=0.01, key="fib_high", format="%.2f")
        with col2:
            fib_low = st.number_input("Contract Low ($)", value=0.00, step=0.01, key="fib_low", format="%.2f")
        
        if fib_high > 0 and fib_low > 0 and fib_high > fib_low:
            fib_levels = calculate_fibonacci(fib_high, fib_low)
            
            st.markdown(f'''
                <div class="fib-result primary">
                    <div>
                        <div class="fib-label">🎯 0.618 Retracement (Primary)</div>
                        <div style="color: #7d8590; font-size: 12px; margin-top: 4px;">Golden ratio entry</div>
                    </div>
                    <div class="fib-value">${fib_levels['0.618']}</div>
                </div>
            ''', unsafe_allow_html=True)
            
            st.markdown(f'''
                <div class="fib-result primary">
                    <div>
                        <div class="fib-label">🎯 0.786 Retracement (Secondary)</div>
                        <div style="color: #7d8590; font-size: 12px; margin-top: 4px;">Deep retracement entry</div>
                    </div>
                    <div class="fib-value">${fib_levels['0.786']}</div>
                </div>
            ''', unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            for level, price in fib_levels.items():
                st.markdown(f'<div class="fib-result"><div class="fib-label">{level}</div><div class="fib-value">${price}</div></div>', unsafe_allow_html=True)
            
            st.info(f"Range: ${fib_high:.2f} - ${fib_low:.2f} = ${fib_high - fib_low:.2f}")
        
        elif fib_high > 0 and fib_low > 0:
            st.error("Contract High must be greater than Contract Low")
        
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()