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
    """
    Count 30-minute blocks between start and end, excluding:
    - Maintenance hours (4:00-5:00 PM daily)
    - Weekends (Saturday and Sunday)
    """
    blocks = 0
    current = start_dt
    while current < end_dt:
        # Skip weekends (Saturday=5, Sunday=6)
        if current.weekday() >= 5:
            current += timedelta(minutes=30)
            continue
        # Skip maintenance period (4:00-5:00 PM)
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

def calculate_sd_targets(breakout: float, bull_pivot: float, bear_pivot: float, breakdown: float) -> Dict:
    pivot_spread = abs(bull_pivot - bear_pivot)
    extended_spread = 2 * pivot_spread
    extension_target = breakout + extended_spread
    capitulation_target = breakdown - extended_spread
    return {
        "extension_target": extension_target,
        "capitulation_target": capitulation_target,
        "pivot_spread": pivot_spread
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

def get_position_bias(price: float, breakout: float, bull_pivot: float, bear_pivot: float, breakdown: float) -> Tuple[str, str]:
    if price > breakout:
        return "STRONG BULL", "Above Breakout Target - continuation likely"
    elif price > bull_pivot:
        return "BULL ZONE", "Between Bull Pivot and Breakout - watch for extension"
    elif price > bear_pivot:
        return "NEUTRAL", "Between pivots - key zone, watch for direction"
    elif price > breakdown:
        return "BEAR ZONE", "Between Bear Pivot and Breakdown - watch for capitulation"
    else:
        return "STRONG BEAR", "Below Breakdown Target - continuation likely"

def calculate_trade_probability(price: float, extension: float, bull_pivot: float, bear_pivot: float, capitulation: float) -> Dict:
    dist_to_extension = extension - price
    dist_to_capitulation = price - capitulation
    total_range = extension - capitulation
    
    position_pct = (price - capitulation) / total_range
    
    if price > bull_pivot:
        extension_prob = min(95, 50 + (position_pct * 40))
        capitulation_prob = 100 - extension_prob
    elif price < bear_pivot:
        capitulation_prob = min(95, 50 + ((1 - position_pct) * 40))
        extension_prob = 100 - capitulation_prob
    else:
        if price > (bull_pivot + bear_pivot) / 2:
            extension_prob = 55
            capitulation_prob = 45
        else:
            extension_prob = 45
            capitulation_prob = 55
    
    return {
        "extension": round(extension_prob, 1),
        "capitulation": round(capitulation_prob, 1)
    }

def analyze_spread(current_spread: float) -> Dict:
    # Typical pivot spread baseline for SPX (adjust based on your historical data)
    typical_spread = 16.25
    ratio = (current_spread / typical_spread) * 100
    diff = current_spread - typical_spread
    
    if ratio < 80:
        status = "COMPRESSED"
        signal = "High volatility expected - prepare for explosive move"
        color = "warning"
    elif ratio > 120:
        status = "EXPANDED"
        signal = "Mean reversion likely - expect consolidation"
        color = "info"
    else:
        status = "NORMAL"
        signal = "Standard range - normal trading conditions"
        color = "success"
    
    return {
        "status": status,
        "signal": signal,
        "color": color,
        "ratio": ratio,
        "diff": diff,
        "typical_spread": typical_spread
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
    
    .prophet-header {
        position: relative;
        text-align: center;
        padding: 60px 40px 40px 40px;
        margin-bottom: 40px;
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.05) 0%, rgba(100, 149, 237, 0.05) 100%);
        border-radius: 24px;
        border: 1px solid rgba(218, 165, 32, 0.1);
        backdrop-filter: blur(20px);
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
    }
    
    .prophet-logo {
        font-size: 56px;
        font-weight: 900;
        background: linear-gradient(135deg, #daa520 0%, #6495ed 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
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
    
    .premium-card {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.8) 0%, rgba(15, 20, 25, 0.9) 100%);
        border: 1px solid rgba(218, 165, 32, 0.15);
        border-radius: 20px;
        padding: 32px;
        margin: 24px 0;
        backdrop-filter: blur(10px);
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .premium-card:hover {
        transform: translateY(-4px);
        border-color: rgba(218, 165, 32, 0.3);
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), 0 0 40px rgba(218, 165, 32, 0.15);
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
    
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 16px;
        margin: 24px 0;
    }
    
    .metric-card {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.05) 0%, rgba(100, 149, 237, 0.05) 100%);
        border: 1px solid rgba(218, 165, 32, 0.15);
        border-radius: 16px;
        padding: 24px 20px;
        text-align: center;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(218, 165, 32, 0.3);
        box-shadow: 0 8px 32px rgba(218, 165, 32, 0.15);
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
    
    .distance-item {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.6) 0%, rgba(15, 20, 25, 0.8) 100%);
        border: 1px solid rgba(218, 165, 32, 0.2);
        border-radius: 12px;
        padding: 16px 24px;
        margin: 8px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.3s ease;
    }
    
    .distance-item:hover {
        transform: translateX(4px);
        border-color: rgba(218, 165, 32, 0.4);
        box-shadow: 0 4px 20px rgba(218, 165, 32, 0.15);
    }
    
    .distance-item.current {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.2) 0%, rgba(100, 149, 237, 0.2) 100%);
        border: 2px solid rgba(218, 165, 32, 0.5);
        font-size: 18px;
        font-weight: 800;
    }
    
    .distance-label {
        font-size: 15px;
        font-weight: 600;
        color: #e8eaed;
    }
    
    .distance-value {
        font-size: 20px;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .distance-value.up {
        color: #22c55e;
    }
    
    .distance-value.down {
        color: #ef4444;
    }
    
    .probability-card {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.1) 0%, rgba(100, 149, 237, 0.1) 100%);
        border: 2px solid rgba(218, 165, 32, 0.3);
        border-radius: 16px;
        padding: 28px;
        margin: 20px 0;
        backdrop-filter: blur(10px);
    }
    
    .prob-title {
        font-size: 18px;
        font-weight: 700;
        color: #daa520;
        margin-bottom: 20px;
        text-align: center;
    }
    
    .prob-bars {
        display: flex;
        gap: 20px;
        margin-top: 16px;
    }
    
    .prob-bar {
        flex: 1;
        text-align: center;
    }
    
    .prob-label {
        font-size: 13px;
        font-weight: 700;
        color: #7d8590;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    
    .prob-value {
        font-size: 40px;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        margin-bottom: 8px;
    }
    
    .prob-value.bull {
        color: #22c55e;
    }
    
    .prob-value.bear {
        color: #ef4444;
    }
    
    .spread-analysis {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.8) 0%, rgba(15, 20, 25, 0.9) 100%);
        border: 2px solid rgba(218, 165, 32, 0.3);
        border-radius: 16px;
        padding: 28px;
        margin: 20px 0;
        backdrop-filter: blur(10px);
    }
    
    .spread-analysis.compressed {
        border-color: rgba(245, 158, 11, 0.5);
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(245, 158, 11, 0.05) 100%);
    }
    
    .spread-analysis.expanded {
        border-color: rgba(59, 130, 246, 0.5);
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(59, 130, 246, 0.05) 100%);
    }
    
    .spread-title {
        font-size: 18px;
        font-weight: 700;
        margin-bottom: 16px;
    }
    
    .spread-status {
        font-size: 32px;
        font-weight: 900;
        margin: 12px 0;
    }
    
    .spread-status.compressed {
        color: #f59e0b;
    }
    
    .spread-status.expanded {
        color: #3b82f6;
    }
    
    .spread-status.normal {
        color: #22c55e;
    }
    
    .spread-signal {
        font-size: 15px;
        color: #cbd5e1;
        margin-top: 12px;
    }
    
    .spread-metrics {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 16px;
        margin-top: 20px;
        padding-top: 20px;
        border-top: 1px solid rgba(218, 165, 32, 0.2);
    }
    
    .spread-metric {
        text-align: center;
    }
    
    .spread-metric-label {
        font-size: 11px;
        font-weight: 700;
        color: #7d8590;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    
    .spread-metric-value {
        font-size: 24px;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #daa520;
    }
    
    .bias-card {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.1) 0%, rgba(100, 149, 237, 0.1) 100%);
        border: 2px solid rgba(218, 165, 32, 0.3);
        border-radius: 20px;
        padding: 32px;
        margin: 24px 0;
        text-align: center;
        backdrop-filter: blur(10px);
    }
    
    .bias-title {
        font-size: 32px;
        font-weight: 900;
        margin-bottom: 12px;
    }
    
    .opening-context {
        background: linear-gradient(135deg, rgba(100, 149, 237, 0.1) 0%, rgba(100, 149, 237, 0.05) 100%);
        border: 1px solid rgba(100, 149, 237, 0.3);
        border-radius: 16px;
        padding: 24px;
        margin: 20px 0;
    }
    
    .context-title {
        font-size: 16px;
        font-weight: 700;
        color: #6495ed;
        margin-bottom: 12px;
    }
    
    .context-text {
        font-size: 15px;
        color: #cbd5e1;
        line-height: 1.6;
    }
    
    .expected-moves {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
        margin: 20px 0;
    }
    
    .move-card {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.6) 0%, rgba(15, 20, 25, 0.8) 100%);
        border: 1px solid rgba(218, 165, 32, 0.2);
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    
    .move-label {
        font-size: 12px;
        font-weight: 700;
        color: #7d8590;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    
    .move-value {
        font-size: 28px;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #daa520;
    }
    
    .fib-result {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.6) 0%, rgba(15, 20, 25, 0.8) 100%);
        border: 1px solid rgba(218, 165, 32, 0.2);
        border-radius: 12px;
        padding: 20px 28px;
        margin: 12px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.3s ease;
    }
    
    .fib-result:hover {
        transform: translateX(4px);
        border-color: rgba(218, 165, 32, 0.4);
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
    
    .stDataFrame {
        border: 1px solid rgba(218, 165, 32, 0.2);
        border-radius: 16px;
        overflow: hidden;
    }
    
    .stDataFrame table {
        font-family: 'JetBrains Mono', monospace;
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
    }
    
    .stNumberInput label, .stDateInput label, .stTimeInput label, .stTextInput label {
        color: #7d8590 !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    
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
    }
    
    .stTabs [aria-selected="true"] {
        color: #daa520;
        border-bottom: 2px solid #daa520;
    }
    
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
        st.caption("Weekends: Skipped in calculations")
        st.markdown("---")
        st.markdown("### 📊 Lines")
        st.caption("☁️ Extension Target")
        st.caption("🚀 Breakout Target")
        st.caption("📈 Bull Pivot")
        st.caption("📉 Bear Pivot")
        st.caption("💥 Breakdown Target")
        st.caption("🔥 Capitulation Target")
    
    st.markdown("""
        <div class="prophet-header">
            <div class="prophet-logo">◈ SPX PROPHET</div>
            <div class="prophet-subtitle">Professional Trading Platform</div>
            <div style="font-size: 16px; font-weight: 600; color: #daa520; margin-top: 12px; letter-spacing: 0.05em;">
                Predicting Market Irrationality Accurately
            </div>
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
        
        # Standard projections from anchors
        df_breakout = project_line(skyline_price, sky_dt, ASC_SLOPE, slots)
        df_bear_pivot = project_line(skyline_price, sky_dt, DESC_SLOPE, slots)
        df_bull_pivot = project_line(baseline_price, base_dt, ASC_SLOPE, slots)
        df_breakdown = project_line(baseline_price, base_dt, DESC_SLOPE, slots)
        
        merged = pd.DataFrame({"Time (CT)": [dt.strftime("%I:%M %p") for dt in slots]})
        merged["🚀 Breakout Target"] = df_breakout["Price"]
        merged["📈 Bull Pivot"] = df_bull_pivot["Price"]
        merged["📉 Bear Pivot"] = df_bear_pivot["Price"]
        merged["💥 Breakdown Target"] = df_breakdown["Price"]
        
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🌅 Market Open (8:30 AM)</div>', unsafe_allow_html=True)
        
        open_row = merged[merged["Time (CT)"] == "08:30 AM"].iloc[0]
        breakout = open_row["🚀 Breakout Target"]
        bull_pivot = open_row["📈 Bull Pivot"]
        bear_pivot = open_row["📉 Bear Pivot"]
        breakdown = open_row["💥 Breakdown Target"]
        
        sd_results = calculate_sd_targets(breakout, bull_pivot, bear_pivot, breakdown)
        extension = sd_results['extension_target']
        capitulation = sd_results['capitulation_target']
        pivot_spread = sd_results['pivot_spread']
        
        st.markdown('<div class="metrics-grid">', unsafe_allow_html=True)
        levels = [
            ("☁️ Extension Target", extension),
            ("🚀 Breakout Target", breakout),
            ("📈 Bull Pivot", bull_pivot),
            ("📉 Bear Pivot", bear_pivot),
            ("💥 Breakdown Target", breakdown),
            ("🔥 Capitulation Target", capitulation)
        ]
        for name, price in levels:
            st.markdown(f'<div class="metric-card"><div class="metric-label">{name}</div><div class="metric-value">${price:.2f}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Opening Context with user input
        st.markdown('<div class="opening-context">', unsafe_allow_html=True)
        st.markdown('<div class="context-title">📍 Opening Context</div>', unsafe_allow_html=True)
        opening_price = st.number_input("Market Opening Price (Optional)", value=0.00, step=0.01, key="opening_price", format="%.2f", min_value=0.0)
        
        if opening_price > 0:
            if opening_price > breakout:
                context = f"Opened at ${opening_price:.2f} - Above Breakout Target (strong bullish setup)"
            elif opening_price > bull_pivot:
                context = f"Opened at ${opening_price:.2f} - Between Bull Pivot and Breakout (bullish bias)"
            elif opening_price > bear_pivot:
                context = f"Opened at ${opening_price:.2f} - Between pivots (neutral zone - key decision area)"
            elif opening_price > breakdown:
                context = f"Opened at ${opening_price:.2f} - Between Bear Pivot and Breakdown (bearish bias)"
            else:
                context = f"Opened at ${opening_price:.2f} - Below Breakdown Target (strong bearish setup)"
            st.markdown(f'<div class="context-text">{context}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="context-text" style="color: #7d8590;">Enter opening price to see context analysis</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card-title" style="margin-top: 32px;">📏 Expected Move Metrics</div>', unsafe_allow_html=True)
        
        max_upside = extension - bear_pivot
        max_downside = bull_pivot - capitulation
        
        st.markdown('<div class="expected-moves">', unsafe_allow_html=True)
        st.markdown(f'<div class="move-card"><div class="move-label">Max Upside</div><div class="move-value">{max_upside:.2f} pts</div><div style="font-size: 12px; color: #7d8590; margin-top: 8px;">Bear Pivot → Extension</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="move-card"><div class="move-label">Max Downside</div><div class="move-value">{max_downside:.2f} pts</div><div style="font-size: 12px; color: #7d8590; margin-top: 8px;">Bull Pivot → Capitulation</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown(f'<div class="move-card" style="margin-top: 16px;"><div class="move-label">Pivot Spread</div><div class="move-value">{pivot_spread:.2f} pts</div><div style="font-size: 12px; color: #7d8590; margin-top: 8px;">|Bull Pivot - Bear Pivot|</div></div>', unsafe_allow_html=True)
        
        spread_analysis = analyze_spread(pivot_spread)
        
        st.markdown(f'''
            <div class="spread-analysis {spread_analysis['status'].lower()}">
                <div class="spread-title">📊 Spread Analysis</div>
                <div class="spread-status {spread_analysis['status'].lower()}">{spread_analysis['status']}</div>
                <div class="spread-signal">{spread_analysis['signal']}</div>
                <div class="spread-metrics">
                    <div class="spread-metric">
                        <div class="spread-metric-label">Current Spread</div>
                        <div class="spread-metric-value">{pivot_spread:.2f} pts</div>
                    </div>
                    <div class="spread-metric">
                        <div class="spread-metric-label">Typical Spread</div>
                        <div class="spread-metric-value">{spread_analysis['typical_spread']:.2f} pts</div>
                    </div>
                    <div class="spread-metric">
                        <div class="spread-metric-label">Ratio</div>
                        <div class="spread-metric-value">{spread_analysis['ratio']:.0f}%</div>
                    </div>
                </div>
            </div>
        ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🎯 Live Analysis</div>', unsafe_allow_html=True)
        
        current_price = st.number_input("Current SPX Price", value=0.00, step=0.01, key="current_price", format="%.2f", min_value=0.0)
        
        if current_price > 0:
            st.markdown('<div class="card-title" style="margin-top: 24px;">📏 Distance Dashboard</div>', unsafe_allow_html=True)
            
            distances = [
                ("☁️ Extension Target", extension, current_price - extension),
                ("🚀 Breakout Target", breakout, current_price - breakout),
                ("📈 Bull Pivot", bull_pivot, current_price - bull_pivot),
                ("📉 Bear Pivot", bear_pivot, current_price - bear_pivot),
                ("💥 Breakdown Target", breakdown, current_price - breakdown),
                ("🔥 Capitulation Target", capitulation, current_price - capitulation)
            ]
            
            for name, level, dist in distances:
                if abs(dist) < 0.01:  # Essentially at the level
                    st.markdown(f'<div class="distance-item current"><div class="distance-label">🎯 CURRENT PRICE AT {name}</div><div class="distance-value">${current_price:.2f}</div></div>', unsafe_allow_html=True)
                else:
                    direction = "up" if dist < 0 else "down"
                    arrow = "⬆️" if dist < 0 else "⬇️"
                    st.markdown(f'<div class="distance-item"><div class="distance-label">{name} ${level:.2f}</div><div class="distance-value {direction}">{arrow} {abs(dist):.2f} pts</div></div>', unsafe_allow_html=True)
            
            bias_name, bias_desc = get_position_bias(current_price, breakout, bull_pivot, bear_pivot, breakdown)
            st.markdown(f'''
                <div class="bias-card">
                    <div class="bias-title" style="color: #daa520;">{bias_name}</div>
                    <div style="color: #cbd5e1; font-size: 16px;">{bias_desc}</div>
                </div>
            ''', unsafe_allow_html=True)
            
            probabilities = calculate_trade_probability(current_price, extension, bull_pivot, bear_pivot, capitulation)
            
            st.markdown(f'''
                <div class="probability-card">
                    <div class="prob-title">🎲 Trade Probability Analysis</div>
                    <div style="color: #cbd5e1; font-size: 14px; text-align: center; margin-bottom: 20px;">
                        Based on current price position at ${current_price:.2f}
                    </div>
                    <div class="prob-bars">
                        <div class="prob-bar">
                            <div class="prob-label">Extension Target</div>
                            <div class="prob-value bull">{probabilities['extension']}%</div>
                            <div style="font-size: 13px; color: #7d8590; margin-top: 8px;">${extension:.2f}</div>
                        </div>
                        <div class="prob-bar">
                            <div class="prob-label">Capitulation Target</div>
                            <div class="prob-value bear">{probabilities['capitulation']}%</div>
                            <div style="font-size: 13px; color: #7d8590; margin-top: 8px;">${capitulation:.2f}</div>
                        </div>
                    </div>
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
            fib_high = st.number_input("Contract High ($)", value=0.00, step=0.01, key="fib_high", format="%.2f", min_value=0.0)
        with col2:
            fib_low = st.number_input("Contract Low ($)", value=0.00, step=0.01, key="fib_low", format="%.2f", min_value=0.0)
        
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