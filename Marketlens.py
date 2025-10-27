# app.py
# SPX PROPHET - Professional Trading Platform
# 4-Anchor Channel System + Dynamic Channel Trader

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
        if current.weekday() >= 5:
            current += timedelta(minutes=30)
            continue
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

def calculate_dynamic_slope(price1: float, time1: datetime, price2: float, time2: datetime) -> float:
    """Calculate slope in points per 30-min block between two points"""
    blocks = count_blocks_with_maintenance_skip(time1, time2)
    if blocks == 0:
        return 0.0
    slope = (price2 - price1) / blocks
    return slope

def project_dynamic_channel(point1_price: float, point1_time: datetime, 
                           point2_price: float, point2_time: datetime,
                           point3_price: float, point3_time: datetime,
                           slots: List[datetime]) -> Tuple[pd.DataFrame, float, float]:
    """
    Project dynamic channel based on three anchor points.
    Primary line goes through point1 and point2.
    Parallel line goes through point3.
    Returns: DataFrame with projections, slope, channel_width
    """
    # Calculate slope from point1 to point2
    slope = calculate_dynamic_slope(point1_price, point1_time, point2_price, point2_time)
    
    # Align times to 30-min boundaries
    minute1 = 0 if point1_time.minute < 30 else 30
    minute3 = 0 if point3_time.minute < 30 else 30
    anchor1_aligned = point1_time.replace(minute=minute1, second=0, microsecond=0)
    anchor3_aligned = point3_time.replace(minute=minute3, second=0, microsecond=0)
    
    # Project primary line
    primary_line = []
    for dt in slots:
        blocks = count_blocks_with_maintenance_skip(anchor1_aligned, dt)
        price = point1_price + (slope * blocks)
        primary_line.append(price)
    
    # Calculate parallel line offset at point3's time
    blocks_to_point3 = count_blocks_with_maintenance_skip(anchor1_aligned, anchor3_aligned)
    primary_at_point3 = point1_price + (slope * blocks_to_point3)
    channel_width = point3_price - primary_at_point3
    
    # Project parallel line
    parallel_line = []
    for dt in slots:
        blocks = count_blocks_with_maintenance_skip(anchor1_aligned, dt)
        price = point1_price + (slope * blocks) + channel_width
        parallel_line.append(price)
    
    # Create DataFrame
    df = pd.DataFrame({
        "Time (CT)": [dt.strftime("%I:%M %p") for dt in slots],
        "Primary Line": [round(p, 2) for p in primary_line],
        "Parallel Line": [round(p, 2) for p in parallel_line],
        "Channel Width": [round(abs(channel_width), 2) for _ in slots]
    })
    
    return df, slope, channel_width

def calculate_targets(bull_pivot: float, breakout: float, bear_pivot: float, breakdown: float) -> Dict:
    skyline_channel_width = breakout - bull_pivot
    baseline_channel_width = bear_pivot - breakdown
    extension = breakout + skyline_channel_width
    capitulation = breakdown - baseline_channel_width
    
    return {
        "extension": extension,
        "capitulation": capitulation,
        "skyline_channel": skyline_channel_width,
        "baseline_channel": baseline_channel_width,
        "total_range": extension - capitulation
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

def get_market_zone(price: float, levels: Dict) -> Tuple[str, str, str]:
    if price >= levels['extension']:
        return "🔥 EXTENSION ZONE", "Extreme bullish territory - profit taking likely", "#22c55e"
    elif price >= levels['breakout']:
        return "🚀 BREAKOUT ZONE", "Strong momentum - watch for extension", "#10b981"
    elif price >= levels['bull_pivot']:
        return "📈 BULL CHANNEL", "Bullish bias - momentum building", "#84cc16"
    elif price >= levels['bear_pivot']:
        return "⚖️ PIVOT ZONE", "Neutral - key decision area", "#f59e0b"
    elif price >= levels['breakdown']:
        return "📉 BEAR CHANNEL", "Bearish bias - pressure building", "#ef4444"
    elif price >= levels['capitulation']:
        return "💥 BREAKDOWN ZONE", "Strong selling - watch for capitulation", "#dc2626"
    else:
        return "🔥 CAPITULATION ZONE", "Extreme bearish territory - bounce likely", "#b91c1c"

def calculate_risk_reward(entry: float, target: float, stop: float) -> float:
    risk = abs(entry - stop)
    reward = abs(target - entry)
    return round(reward / risk, 2) if risk > 0 else 0

def get_trade_setups(price: float, levels: Dict) -> List[Dict]:
    setups = []
    
    # Bullish setups
    if price <= levels['bull_pivot']:
        setups.append({
            "type": "LONG",
            "entry": price,
            "target": levels['breakout'],
            "stop": levels['bear_pivot'],
            "rr": calculate_risk_reward(price, levels['breakout'], levels['bear_pivot']),
            "confidence": "High" if price < levels['bull_pivot'] * 0.998 else "Medium"
        })
    
    # Bearish setups
    if price >= levels['bear_pivot']:
        setups.append({
            "type": "SHORT",
            "entry": price,
            "target": levels['breakdown'],
            "stop": levels['bull_pivot'],
            "rr": calculate_risk_reward(price, levels['breakdown'], levels['bull_pivot']),
            "confidence": "High" if price > levels['bear_pivot'] * 1.002 else "Medium"
        })
    
    return setups

def main():
    st.set_page_config(page_title=APP_NAME, page_icon="◈", layout="wide", initial_sidebar_state="expanded")
    
    # Enhanced CSS with animations and professional styling
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');
    
    * {
        font-family: 'Outfit', sans-serif;
        letter-spacing: -0.01em;
    }
    
    html, body, .main, .block-container {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1f2e 50%, #0f1419 100%);
        color: #e8eaed;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1f2e 50%, #0f1419 100%);
    }
    
    h1, h2, h3, h4, h5, h6, p, div, span, label {
        color: #e8eaed;
    }
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes pulse {
        0%, 100% {
            opacity: 1;
        }
        50% {
            opacity: 0.7;
        }
    }
    
    @keyframes shimmer {
        0% {
            background-position: -1000px 0;
        }
        100% {
            background-position: 1000px 0;
        }
    }
    
    .prophet-header {
        position: relative;
        text-align: center;
        padding: 80px 40px 60px 40px;
        margin-bottom: 40px;
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.08) 0%, rgba(100, 149, 237, 0.08) 100%);
        border-radius: 32px;
        border: 2px solid rgba(218, 165, 32, 0.15);
        backdrop-filter: blur(20px);
        box-shadow: 0 30px 80px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.1);
        animation: fadeInUp 0.8s ease-out;
        overflow: hidden;
    }
    
    .prophet-header::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(45deg, transparent, rgba(218, 165, 32, 0.03), transparent);
        animation: shimmer 3s infinite;
    }
    
    .prophet-logo {
        font-size: 72px;
        font-weight: 900;
        background: linear-gradient(135deg, #daa520 0%, #ffd700 50%, #6495ed 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 0.08em;
        margin: 0;
        text-shadow: 0 0 40px rgba(218, 165, 32, 0.3);
        animation: pulse 3s ease-in-out infinite;
    }
    
    .prophet-subtitle {
        font-size: 16px;
        font-weight: 700;
        color: #7d8590;
        text-transform: uppercase;
        letter-spacing: 0.3em;
        margin-top: 20px;
    }
    
    .prophet-tagline {
        font-size: 20px;
        font-weight: 700;
        background: linear-gradient(135deg, #daa520, #ffd700);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-top: 16px;
        letter-spacing: 0.05em;
    }
    
    .premium-card {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.9) 0%, rgba(15, 20, 25, 0.95) 100%);
        border: 1.5px solid rgba(218, 165, 32, 0.2);
        border-radius: 24px;
        padding: 36px;
        margin: 28px 0;
        backdrop-filter: blur(20px);
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.05);
        transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        animation: fadeInUp 0.6s ease-out;
    }
    
    .premium-card:hover {
        transform: translateY(-6px) scale(1.01);
        border-color: rgba(218, 165, 32, 0.4);
        box-shadow: 0 25px 70px rgba(0, 0, 0, 0.7), 0 0 60px rgba(218, 165, 32, 0.2);
    }
    
    .card-title {
        font-size: 24px;
        font-weight: 800;
        color: #daa520;
        margin-bottom: 28px;
        display: flex;
        align-items: center;
        gap: 14px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .anchor-section {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.05), rgba(100, 149, 237, 0.05));
        border: 1px solid rgba(218, 165, 32, 0.2);
        border-radius: 20px;
        padding: 28px;
        margin: 20px 0;
    }
    
    .anchor-label {
        font-size: 14px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 16px;
        padding: 10px 16px;
        border-radius: 8px;
        display: inline-block;
    }
    
    .anchor-label.skyline1 {
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(34, 197, 94, 0.1));
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.3);
    }
    
    .anchor-label.skyline2 {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0.1));
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .anchor-label.baseline1 {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 0.1));
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    .anchor-label.baseline2 {
        background: linear-gradient(135deg, rgba(220, 38, 38, 0.2), rgba(220, 38, 38, 0.1));
        color: #dc2626;
        border: 1px solid rgba(220, 38, 38, 0.3);
    }
    
    .metrics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 20px;
        margin: 28px 0;
    }
    
    .metric-card {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.08) 0%, rgba(100, 149, 237, 0.08) 100%);
        border: 1.5px solid rgba(218, 165, 32, 0.2);
        border-radius: 18px;
        padding: 28px 24px;
        text-align: center;
        backdrop-filter: blur(15px);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(218, 165, 32, 0.1), transparent);
        transition: left 0.5s;
    }
    
    .metric-card:hover::before {
        left: 100%;
    }
    
    .metric-card:hover {
        transform: translateY(-4px) scale(1.05);
        border-color: rgba(218, 165, 32, 0.4);
        box-shadow: 0 12px 40px rgba(218, 165, 32, 0.25);
    }
    
    .metric-label {
        font-size: 12px;
        font-weight: 800;
        color: #7d8590;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        margin-bottom: 14px;
    }
    
    .metric-value {
        font-size: 32px;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #daa520, #ffd700, #6495ed);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .channel-analysis {
        background: linear-gradient(135deg, rgba(100, 149, 237, 0.1), rgba(100, 149, 237, 0.05));
        border: 2px solid rgba(100, 149, 237, 0.3);
        border-radius: 20px;
        padding: 32px;
        margin: 24px 0;
    }
    
    .channel-title {
        font-size: 20px;
        font-weight: 800;
        color: #6495ed;
        margin-bottom: 20px;
        text-transform: uppercase;
    }
    
    .channel-metric {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 24px;
        background: rgba(15, 20, 25, 0.5);
        border-radius: 12px;
        margin: 12px 0;
        border: 1px solid rgba(100, 149, 237, 0.2);
    }
    
    .zone-indicator {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.15), rgba(218, 165, 32, 0.05));
        border: 2px solid;
        border-radius: 20px;
        padding: 32px;
        margin: 24px 0;
        text-align: center;
        backdrop-filter: blur(10px);
        animation: fadeInUp 0.5s ease-out;
    }
    
    .zone-name {
        font-size: 36px;
        font-weight: 900;
        margin-bottom: 12px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .zone-description {
        font-size: 16px;
        color: #cbd5e1;
        margin-top: 12px;
    }
    
    .distance-item {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.7) 0%, rgba(15, 20, 25, 0.9) 100%);
        border: 1.5px solid rgba(218, 165, 32, 0.25);
        border-radius: 14px;
        padding: 18px 28px;
        margin: 10px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }
    
    .distance-item:hover {
        transform: translateX(8px) scale(1.02);
        border-color: rgba(218, 165, 32, 0.5);
        box-shadow: 0 6px 25px rgba(218, 165, 32, 0.2);
    }
    
    .distance-item.current {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.25) 0%, rgba(100, 149, 237, 0.25) 100%);
        border: 2px solid rgba(218, 165, 32, 0.6);
        font-size: 20px;
        font-weight: 900;
        box-shadow: 0 8px 30px rgba(218, 165, 32, 0.3);
    }
    
    .distance-label {
        font-size: 16px;
        font-weight: 700;
        color: #e8eaed;
    }
    
    .distance-value {
        font-size: 22px;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .distance-value.up {
        color: #22c55e;
    }
    
    .distance-value.down {
        color: #ef4444;
    }
    
    .trade-setup-card {
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.1), rgba(34, 197, 94, 0.05));
        border: 2px solid rgba(34, 197, 94, 0.3);
        border-radius: 18px;
        padding: 28px;
        margin: 16px 0;
        transition: all 0.4s ease;
    }
    
    .trade-setup-card.short {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(239, 68, 68, 0.05));
        border-color: rgba(239, 68, 68, 0.3);
    }
    
    .trade-setup-card:hover {
        transform: scale(1.03);
        box-shadow: 0 12px 40px rgba(34, 197, 94, 0.3);
    }
    
    .setup-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    
    .setup-type {
        font-size: 24px;
        font-weight: 900;
        color: #22c55e;
    }
    
    .setup-type.short {
        color: #ef4444;
    }
    
    .confidence-badge {
        padding: 6px 16px;
        border-radius: 8px;
        font-size: 12px;
        font-weight: 800;
        text-transform: uppercase;
    }
    
    .confidence-badge.high {
        background: rgba(34, 197, 94, 0.2);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.4);
    }
    
    .confidence-badge.medium {
        background: rgba(245, 158, 11, 0.2);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.4);
    }
    
    .setup-details {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 16px;
        margin-top: 16px;
    }
    
    .setup-item {
        padding: 12px;
        background: rgba(15, 20, 25, 0.5);
        border-radius: 10px;
        border: 1px solid rgba(218, 165, 32, 0.2);
    }
    
    .setup-label {
        font-size: 11px;
        font-weight: 700;
        color: #7d8590;
        text-transform: uppercase;
        margin-bottom: 6px;
    }
    
    .setup-value {
        font-size: 20px;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: #daa520;
    }
    
    .rr-badge {
        display: inline-block;
        padding: 8px 20px;
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.2), rgba(218, 165, 32, 0.1));
        border: 2px solid rgba(218, 165, 32, 0.4);
        border-radius: 12px;
        font-size: 18px;
        font-weight: 900;
        color: #daa520;
        margin-top: 12px;
    }
    
    .fib-result {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.7) 0%, rgba(15, 20, 25, 0.9) 100%);
        border: 1.5px solid rgba(218, 165, 32, 0.25);
        border-radius: 14px;
        padding: 22px 32px;
        margin: 14px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.4s ease;
    }
    
    .fib-result:hover {
        transform: translateX(6px);
        border-color: rgba(218, 165, 32, 0.5);
    }
    
    .fib-result.primary {
        border-width: 2px;
        border-color: rgba(218, 165, 32, 0.5);
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.15) 0%, rgba(100, 149, 237, 0.15) 100%);
    }
    
    .fib-label {
        font-size: 16px;
        font-weight: 700;
        color: #e8eaed;
    }
    
    .fib-value {
        font-size: 26px;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        color: #daa520;
    }
    
    .mode-selector {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin: 24px 0;
    }
    
    .mode-card {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.7) 0%, rgba(15, 20, 25, 0.9) 100%);
        border: 2px solid rgba(218, 165, 32, 0.25);
        border-radius: 18px;
        padding: 28px;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .mode-card:hover {
        transform: scale(1.05);
        border-color: rgba(218, 165, 32, 0.5);
    }
    
    .mode-card.selected {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.2) 0%, rgba(100, 149, 237, 0.2) 100%);
        border-color: rgba(218, 165, 32, 0.6);
        box-shadow: 0 8px 30px rgba(218, 165, 32, 0.4);
    }
    
    .dynamic-point-card {
        background: linear-gradient(135deg, rgba(100, 149, 237, 0.08), rgba(100, 149, 237, 0.05));
        border: 1.5px solid rgba(100, 149, 237, 0.3);
        border-radius: 18px;
        padding: 24px;
        margin: 16px 0;
    }
    
    .dynamic-point-card.primary {
        border-color: rgba(218, 165, 32, 0.4);
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.12), rgba(218, 165, 32, 0.06));
    }
    
    .point-label {
        font-size: 16px;
        font-weight: 800;
        color: #daa520;
        margin-bottom: 16px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    
    .stDataFrame {
        border: 1.5px solid rgba(218, 165, 32, 0.25);
        border-radius: 18px;
        overflow: hidden;
    }
    
    .stDataFrame table {
        font-family: 'JetBrains Mono', monospace;
    }
    
    .stDataFrame thead th {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.2), rgba(100, 149, 237, 0.2)) !important;
        color: #daa520 !important;
        font-weight: 900 !important;
        font-size: 13px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.12em !important;
        padding: 20px 18px !important;
        border-bottom: 2px solid rgba(218, 165, 32, 0.4) !important;
    }
    
    .stDataFrame tbody td {
        background: rgba(15, 20, 25, 0.5) !important;
        color: #e8eaed !important;
        font-weight: 700 !important;
        font-size: 16px !important;
        padding: 18px !important;
        border-bottom: 1px solid rgba(218, 165, 32, 0.15) !important;
    }
    
    .stDataFrame tbody tr:hover td {
        background: rgba(218, 165, 32, 0.12) !important;
    }
    
    .stNumberInput input, .stDateInput input, .stTimeInput input, .stTextInput input {
        background: rgba(15, 20, 25, 0.7) !important;
        border: 2px solid rgba(218, 165, 32, 0.25) !important;
        border-radius: 12px !important;
        color: #e8eaed !important;
        font-weight: 700 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 16px !important;
        padding: 14px 18px !important;
        transition: all 0.3s ease !important;
    }
    
    .stNumberInput input:focus, .stDateInput input:focus, .stTimeInput input:focus, .stTextInput input:focus {
        border-color: rgba(218, 165, 32, 0.6) !important;
        box-shadow: 0 0 0 4px rgba(218, 165, 32, 0.15) !important;
    }
    
    .stNumberInput label, .stDateInput label, .stTimeInput label, .stTextInput label {
        color: #7d8590 !important;
        font-weight: 800 !important;
        font-size: 13px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
    }
    
    .stButton button, .stDownloadButton button {
        background: linear-gradient(135deg, #daa520, #ffd700, #6495ed) !important;
        color: #0a0e27 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 16px 36px !important;
        font-weight: 900 !important;
        font-size: 14px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        transition: all 0.4s ease !important;
        box-shadow: 0 8px 25px rgba(218, 165, 32, 0.4) !important;
    }
    
    .stButton button:hover, .stDownloadButton button:hover {
        transform: translateY(-3px) scale(1.05);
        box-shadow: 0 15px 40px rgba(218, 165, 32, 0.6) !important;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background: transparent;
        border-bottom: 2px solid rgba(218, 165, 32, 0.25);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border: none;
        color: #7d8590;
        font-weight: 700;
        font-size: 15px;
        padding: 14px 28px;
        transition: all 0.3s ease;
    }
    
    .stTabs [aria-selected="true"] {
        color: #daa520;
        border-bottom: 3px solid #daa520;
        background: rgba(218, 165, 32, 0.1);
    }
    
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(10, 14, 39, 0.98) 0%, rgba(26, 31, 46, 0.98) 100%);
        border-right: 2px solid rgba(218, 165, 32, 0.2);
        backdrop-filter: blur(30px);
    }
    
    section[data-testid="stSidebar"] * {
        color: #e8eaed;
    }
    
    .stats-bar {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
        margin: 24px 0;
    }
    
    .stat-item {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.1), rgba(100, 149, 237, 0.1));
        border: 1px solid rgba(218, 165, 32, 0.3);
        border-radius: 14px;
        padding: 20px;
        text-align: center;
    }
    
    .stat-label {
        font-size: 11px;
        font-weight: 800;
        color: #7d8590;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    
    .stat-value {
        font-size: 26px;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #daa520, #6495ed);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .stRadio > div {
        background: transparent !important;
    }
    
    .stRadio label {
        background: linear-gradient(135deg, rgba(26, 31, 46, 0.7) 0%, rgba(15, 20, 25, 0.9) 100%) !important;
        border: 2px solid rgba(218, 165, 32, 0.25) !important;
        border-radius: 12px !important;
        padding: 16px 24px !important;
        margin: 8px 0 !important;
        transition: all 0.3s ease !important;
    }
    
    .stRadio label:hover {
        border-color: rgba(218, 165, 32, 0.5) !important;
        transform: scale(1.02) !important;
    }
    
    .stRadio [data-checked="true"] {
        background: linear-gradient(135deg, rgba(218, 165, 32, 0.2) 0%, rgba(100, 149, 237, 0.2) 100%) !important;
        border-color: rgba(218, 165, 32, 0.6) !important;
    }
    
    </style>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.markdown("### ⚙️ CONFIGURATION")
        st.info(f"**Ascending:** +{ASC_SLOPE}")
        st.info(f"**Descending:** {DESC_SLOPE}")
        st.markdown("---")
        st.markdown("### 🕐 SYSTEM INFO")
        st.caption("**Timezone:** Central Time (CT)")
        st.caption("**RTH Hours:** 8:30 AM - 2:00 PM")
        st.caption("**Maintenance:** 4-5 PM (excluded)")
        st.caption("**Weekends:** Auto-skipped")
        st.markdown("---")
        st.markdown("### 📊 6 KEY LEVELS")
        st.caption("☁️ **Extension Target**")
        st.caption("🚀 **Breakout Momentum**")
        st.caption("📈 **Bull Pivot**")
        st.caption("📉 **Bear Pivot**")
        st.caption("💥 **Breakdown Gravity**")
        st.caption("🔥 **Capitulation Target**")
        st.markdown("---")
        st.markdown("### 📈 CHANNEL SYSTEM")
        st.caption("**Skyline Channel:** Bull → Breakout")
        st.caption("**Baseline Channel:** Bear → Breakdown")
        st.markdown("---")
        st.markdown("### 🎯 DYNAMIC CHANNELS")
        st.caption("**Variable slope** adapts daily")
        st.caption("**Parallel channels** from 3 points")
        st.caption("**Real-time** entry/exit signals")
        st.markdown("---")
        current_time_ct = datetime.now(CT)
        st.markdown(f"### 🕐 CURRENT TIME")
        st.caption(f"**{current_time_ct.strftime('%I:%M %p CT')}**")
        st.caption(f"{current_time_ct.strftime('%A, %B %d, %Y')}")
    
    st.markdown("""
        <div class="prophet-header">
            <div class="prophet-logo">◈ SPX PROPHET</div>
            <div class="prophet-subtitle">Professional Trading Platform</div>
            <div class="prophet-tagline">Predicting Market Irrationality Accurately</div>
        </div>
    """, unsafe_allow_html=True)
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 PROJECTION SYSTEM", "🎯 TRADE ANALYZER", "📐 FIBONACCI CALCULATOR", "📈 DYNAMIC CHANNEL TRADER"])
    
    with tab1:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">⚙️ 4-ANCHOR CONFIGURATION</div>', unsafe_allow_html=True)
        
        proj_day = st.date_input("📅 Projection Date", value=datetime.now(CT).date())
        
        st.markdown("---")
        
        # Skyline Channel
        st.markdown('<div class="anchor-section">', unsafe_allow_html=True)
        st.markdown("### 📈 SKYLINE CHANNEL (Ascending +0.475)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="anchor-label skyline1">📈 SKYLINE 1 (Lower) → Bull Pivot</div>', unsafe_allow_html=True)
            skyline1_date = st.date_input("Date", value=proj_day - timedelta(days=1), key="sky1_date")
            skyline1_price = st.number_input("Price ($)", value=6610.00, step=0.01, key="sky1_price", format="%.2f")
            skyline1_time = st.time_input("Time (CT)", value=dtime(14, 30), step=1800, key="sky1_time")
        
        with col2:
            st.markdown('<div class="anchor-label skyline2">🚀 SKYLINE 2 (Higher) → Breakout Momentum</div>', unsafe_allow_html=True)
            skyline2_date = st.date_input("Date", value=proj_day - timedelta(days=1), key="sky2_date")
            skyline2_price = st.number_input("Price ($)", value=6634.70, step=0.01, key="sky2_price", format="%.2f")
            skyline2_time = st.time_input("Time (CT)", value=dtime(14, 30), step=1800, key="sky2_time")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Baseline Channel
        st.markdown('<div class="anchor-section">', unsafe_allow_html=True)
        st.markdown("### 📉 BASELINE CHANNEL (Descending -0.475)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="anchor-label baseline1">📉 BASELINE 1 (Higher) → Bear Pivot</div>', unsafe_allow_html=True)
            baseline1_date = st.date_input("Date", value=proj_day - timedelta(days=1), key="base1_date")
            baseline1_price = st.number_input("Price ($)", value=6625.00, step=0.01, key="base1_price", format="%.2f")
            baseline1_time = st.time_input("Time (CT)", value=dtime(14, 30), step=1800, key="base1_time")
        
        with col2:
            st.markdown('<div class="anchor-label baseline2">💥 BASELINE 2 (Lower) → Breakdown Gravity</div>', unsafe_allow_html=True)
            baseline2_date = st.date_input("Date", value=proj_day - timedelta(days=1), key="base2_date")
            baseline2_price = st.number_input("Price ($)", value=6600.00, step=0.01, key="base2_price", format="%.2f")
            baseline2_time = st.time_input("Time (CT)", value=dtime(14, 30), step=1800, key="base2_time")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Calculate projections
        slots = rth_slots_ct_dt(proj_day, "08:30", "14:00")
        
        sky1_dt = CT.localize(datetime.combine(skyline1_date, skyline1_time))
        sky2_dt = CT.localize(datetime.combine(skyline2_date, skyline2_time))
        base1_dt = CT.localize(datetime.combine(baseline1_date, baseline1_time))
        base2_dt = CT.localize(datetime.combine(baseline2_date, baseline2_time))
        
        df_bull_pivot = project_line(skyline1_price, sky1_dt, ASC_SLOPE, slots)
        df_breakout = project_line(skyline2_price, sky2_dt, ASC_SLOPE, slots)
        df_bear_pivot = project_line(baseline1_price, base1_dt, DESC_SLOPE, slots)
        df_breakdown = project_line(baseline2_price, base2_dt, DESC_SLOPE, slots)
        
        merged = pd.DataFrame({"Time (CT)": [dt.strftime("%I:%M %p") for dt in slots]})
        merged["📈 Bull Pivot"] = df_bull_pivot["Price"]
        merged["🚀 Breakout Momentum"] = df_breakout["Price"]
        merged["📉 Bear Pivot"] = df_bear_pivot["Price"]
        merged["💥 Breakdown Gravity"] = df_breakdown["Price"]
        
        # Get 8:30 AM values
        open_row = merged[merged["Time (CT)"] == "08:30 AM"].iloc[0]
        bull_pivot = open_row["📈 Bull Pivot"]
        breakout = open_row["🚀 Breakout Momentum"]
        bear_pivot = open_row["📉 Bear Pivot"]
        breakdown = open_row["💥 Breakdown Gravity"]
        
        # Calculate targets
        targets = calculate_targets(bull_pivot, breakout, bear_pivot, breakdown)
        extension = targets['extension']
        capitulation = targets['capitulation']
        skyline_channel = targets['skyline_channel']
        baseline_channel = targets['baseline_channel']
        total_range = targets['total_range']
        
        # Display Market Open Levels
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🌅 MARKET OPEN (8:30 AM) - KEY LEVELS</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="metrics-grid">', unsafe_allow_html=True)
        levels = [
            ("☁️ Extension Target", extension),
            ("🚀 Breakout Momentum", breakout),
            ("📈 Bull Pivot", bull_pivot),
            ("📉 Bear Pivot", bear_pivot),
            ("💥 Breakdown Gravity", breakdown),
            ("🔥 Capitulation Target", capitulation)
        ]
        for name, price in levels:
            st.markdown(f'<div class="metric-card"><div class="metric-label">{name}</div><div class="metric-value">${price:.2f}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Channel Analysis
        st.markdown('<div class="channel-analysis">', unsafe_allow_html=True)
        st.markdown('<div class="channel-title">📊 CHANNEL ANALYSIS</div>', unsafe_allow_html=True)
        
        st.markdown(f'''
            <div class="channel-metric">
                <span style="font-weight: 700; color: #22c55e;">📈 Skyline Channel Width</span>
                <span style="font-weight: 900; font-family: 'JetBrains Mono', monospace; font-size: 24px; color: #22c55e;">{skyline_channel:.2f} pts</span>
            </div>
            <div class="channel-metric">
                <span style="font-weight: 700; color: #ef4444;">📉 Baseline Channel Width</span>
                <span style="font-weight: 900; font-family: 'JetBrains Mono', monospace; font-size: 24px; color: #ef4444;">{baseline_channel:.2f} pts</span>
            </div>
            <div class="channel-metric">
                <span style="font-weight: 700; color: #daa520;">📏 Total Range (Ext → Cap)</span>
                <span style="font-weight: 900; font-family: 'JetBrains Mono', monospace; font-size: 24px; color: #daa520;">{total_range:.2f} pts</span>
            </div>
        ''', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Stats Bar
        st.markdown('<div class="stats-bar">', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-item"><div class="stat-label">Max Upside Potential</div><div class="stat-value">{extension - bear_pivot:.2f} pts</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-item"><div class="stat-label">Max Downside Risk</div><div class="stat-value">{bull_pivot - capitulation:.2f} pts</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-item"><div class="stat-label">Pivot Zone Width</div><div class="stat-value">{abs(bull_pivot - bear_pivot):.2f} pts</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Live Price Analysis
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🎯 LIVE MARKET ANALYSIS</div>', unsafe_allow_html=True)
        
        current_price = st.number_input("💵 Current SPX Price", value=0.00, step=0.01, key="current_price", format="%.2f", min_value=0.0)
        
        if current_price > 0:
            levels_dict = {
                'extension': extension,
                'breakout': breakout,
                'bull_pivot': bull_pivot,
                'bear_pivot': bear_pivot,
                'breakdown': breakdown,
                'capitulation': capitulation
            }
            
            zone_name, zone_desc, zone_color = get_market_zone(current_price, levels_dict)
            
            st.markdown(f'''
                <div class="zone-indicator" style="border-color: {zone_color};">
                    <div class="zone-name" style="color: {zone_color};">{zone_name}</div>
                    <div class="zone-description">{zone_desc}</div>
                    <div style="margin-top: 20px; font-size: 48px; font-weight: 900; font-family: 'JetBrains Mono', monospace; color: {zone_color};">
                        ${current_price:.2f}
                    </div>
                </div>
            ''', unsafe_allow_html=True)
            
            st.markdown('<div class="card-title" style="margin-top: 32px;">📏 DISTANCE TO ALL LEVELS</div>', unsafe_allow_html=True)
            
            distances = [
                ("☁️ Extension Target", extension, current_price - extension),
                ("🚀 Breakout Momentum", breakout, current_price - breakout),
                ("📈 Bull Pivot", bull_pivot, current_price - bull_pivot),
                ("📉 Bear Pivot", bear_pivot, current_price - bear_pivot),
                ("💥 Breakdown Gravity", breakdown, current_price - breakdown),
                ("🔥 Capitulation Target", capitulation, current_price - capitulation)
            ]
            
            for name, level, dist in distances:
                if abs(dist) < 0.01:
                    st.markdown(f'<div class="distance-item current"><div class="distance-label">🎯 AT {name}</div><div class="distance-value">${current_price:.2f}</div></div>', unsafe_allow_html=True)
                else:
                    direction = "up" if dist < 0 else "down"
                    arrow = "⬆️" if dist < 0 else "⬇️"
                    st.markdown(f'<div class="distance-item"><div class="distance-label">{name} ${level:.2f}</div><div class="distance-value {direction}">{arrow} {abs(dist):.2f} pts</div></div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Projection Matrix
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📊 COMPLETE PROJECTION MATRIX</div>', unsafe_allow_html=True)
        st.dataframe(merged, use_container_width=True, hide_index=True, height=500)
        st.markdown("<br>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button("📥 COMPLETE DATASET", merged.to_csv(index=False).encode(), "spx_4anchor_complete.csv", "text/csv", use_container_width=True)
        with col2:
            st.download_button("📥 SKYLINE CHANNEL", merged[["Time (CT)", "📈 Bull Pivot", "🚀 Breakout Momentum"]].to_csv(index=False).encode(), "skyline_channel.csv", "text/csv", use_container_width=True)
        with col3:
            st.download_button("📥 BASELINE CHANNEL", merged[["Time (CT)", "📉 Bear Pivot", "💥 Breakdown Gravity"]].to_csv(index=False).encode(), "baseline_channel.csv", "text/csv", use_container_width=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab2:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">🎯 INTELLIGENT TRADE ANALYZER</div>', unsafe_allow_html=True)
        
        analyze_price = st.number_input("💵 Entry Price for Analysis", value=0.00, step=0.01, key="analyze_price", format="%.2f", min_value=0.0)
        
        if analyze_price > 0:
            levels_dict = {
                'extension': extension,
                'breakout': breakout,
                'bull_pivot': bull_pivot,
                'bear_pivot': bear_pivot,
                'breakdown': breakdown,
                'capitulation': capitulation
            }
            
            zone_name, zone_desc, zone_color = get_market_zone(analyze_price, levels_dict)
            
            st.markdown(f'''
                <div class="zone-indicator" style="border-color: {zone_color};">
                    <div style="font-size: 18px; font-weight: 700; color: #7d8590; margin-bottom: 12px;">CURRENT MARKET ZONE</div>
                    <div class="zone-name" style="color: {zone_color};">{zone_name}</div>
                    <div class="zone-description">{zone_desc}</div>
                </div>
            ''', unsafe_allow_html=True)
            
            trade_setups = get_trade_setups(analyze_price, levels_dict)
            
            if trade_setups:
                st.markdown('<div class="card-title" style="margin-top: 32px;">💡 RECOMMENDED TRADE SETUPS</div>', unsafe_allow_html=True)
                
                for setup in trade_setups:
                    setup_class = "short" if setup['type'] == "SHORT" else ""
                    st.markdown(f'<div class="trade-setup-card {setup_class}">', unsafe_allow_html=True)
                    
                    st.markdown(f'''
                        <div class="setup-header">
                            <div class="setup-type {setup_class.lower()}">{setup['type']} SETUP</div>
                            <div class="confidence-badge {setup['confidence'].lower()}">{setup['confidence']} CONFIDENCE</div>
                        </div>
                    ''', unsafe_allow_html=True)
                    
                    st.markdown('<div class="setup-details">', unsafe_allow_html=True)
                    st.markdown(f'''
                        <div class="setup-item">
                            <div class="setup-label">Entry Price</div>
                            <div class="setup-value">${setup['entry']:.2f}</div>
                        </div>
                        <div class="setup-item">
                            <div class="setup-label">Target Price</div>
                            <div class="setup-value">${setup['target']:.2f}</div>
                        </div>
                        <div class="setup-item">
                            <div class="setup-label">Stop Loss</div>
                            <div class="setup-value">${setup['stop']:.2f}</div>
                        </div>
                        <div class="setup-item">
                            <div class="setup-label">Potential Reward</div>
                            <div class="setup-value">{abs(setup['target'] - setup['entry']):.2f} pts</div>
                        </div>
                    ''', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
                    st.markdown(f'<div class="rr-badge">RISK/REWARD: {setup["rr"]}:1</div>', unsafe_allow_html=True)
                    
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.info("🔍 No optimal trade setups identified at current price level. Wait for better positioning.")
        
        else:
            st.info("💡 Enter a price to analyze potential trade setups with calculated risk/reward ratios.")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab3:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📐 FIBONACCI RETRACEMENT CALCULATOR</div>', unsafe_allow_html=True)
        
        st.markdown("### Calculate key retracement levels for precise entries")
        
        col1, col2 = st.columns(2)
        with col1:
            fib_high = st.number_input("📈 Contract High ($)", value=0.00, step=0.01, key="fib_high", format="%.2f", min_value=0.0)
        with col2:
            fib_low = st.number_input("📉 Contract Low ($)", value=0.00, step=0.01, key="fib_low", format="%.2f", min_value=0.0)
        
        if fib_high > 0 and fib_low > 0 and fib_high > fib_low:
            fib_levels = calculate_fibonacci(fib_high, fib_low)
            
            st.markdown('<div style="margin-top: 32px;">', unsafe_allow_html=True)
            
            st.markdown(f'''
                <div class="fib-result primary">
                    <div>
                        <div class="fib-label">🎯 0.618 Retracement (GOLDEN RATIO)</div>
                        <div style="color: #7d8590; font-size: 13px; margin-top: 6px;">Primary entry zone - highest probability</div>
                    </div>
                    <div class="fib-value">${fib_levels['0.618']}</div>
                </div>
            ''', unsafe_allow_html=True)
            
            st.markdown(f'''
                <div class="fib-result primary">
                    <div>
                        <div class="fib-label">🎯 0.786 Retracement (DEEP)</div>
                        <div style="color: #7d8590; font-size: 13px; margin-top: 6px;">Secondary entry - strong support/resistance</div>
                    </div>
                    <div class="fib-value">${fib_levels['0.786']}</div>
                </div>
            ''', unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="card-title">📊 ALL FIBONACCI LEVELS</div>', unsafe_allow_html=True)
            
            for level, price in fib_levels.items():
                st.markdown(f'<div class="fib-result"><div class="fib-label">{level}</div><div class="fib-value">${price}</div></div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.success(f"✅ Range Analyzed: ${fib_high:.2f} - ${fib_low:.2f} = **{fib_high - fib_low:.2f} points**")
        
        elif fib_high > 0 and fib_low > 0:
            st.error("❌ Contract High must be greater than Contract Low")
        else:
            st.info("💡 Enter high and low values to calculate Fibonacci retracement levels for optimal entry points.")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with tab4:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">📈 DYNAMIC CHANNEL TRADER</div>', unsafe_allow_html=True)
        
        st.markdown("""
        ### 🎯 Adaptive Daily Channel System
        Construct **parallel channels** from actual market structure using 3 anchor points.  
        The channel **adapts to daily price action** with variable slope.
        """)
        
        st.markdown("---")
        
        # Projection Date
        dynamic_proj_date = st.date_input("📅 Projection Date (RTH)", value=datetime.now(CT).date(), key="dynamic_proj_date")
        
        st.markdown("---")
        
        # Channel Mode Selection
        st.markdown('<div class="card-title">🎚️ SELECT CHANNEL MODE</div>', unsafe_allow_html=True)
        
        channel_mode = st.radio(
            "Choose construction method:",
            ["🔴 Mode A: Two Highs + One Low (Resistance First)", 
             "🟢 Mode B: Two Lows + One High (Support First)"],
            key="channel_mode"
        )
        
        mode_a = channel_mode.startswith("🔴")
        
        if mode_a:
            st.info("**Mode A:** Connect 2 high points to form upper trendline, then draw parallel line through 1 low point.")
        else:
            st.info("**Mode B:** Connect 2 low points to form lower trendline, then draw parallel line through 1 high point.")
        
        st.markdown("---")
        
        # Three Anchor Points
        st.markdown('<div class="card-title">📍 DEFINE 3 ANCHOR POINTS</div>', unsafe_allow_html=True)
        
        if mode_a:
            point_labels = ["🔴 HIGH POINT 1 (Primary Line)", "🔴 HIGH POINT 2 (Primary Line)", "🟢 LOW POINT (Parallel Line)"]
        else:
            point_labels = ["🟢 LOW POINT 1 (Primary Line)", "🟢 LOW POINT 2 (Primary Line)", "🔴 HIGH POINT (Parallel Line)"]
        
        points_data = []
        
        for i, label in enumerate(point_labels):
            st.markdown(f'<div class="dynamic-point-card {"primary" if i < 2 else ""}">', unsafe_allow_html=True)
            st.markdown(f'<div class="point-label">{label}</div>', unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                point_date = st.date_input("Date", value=dynamic_proj_date - timedelta(days=1), key=f"dyn_p{i+1}_date")
            with col2:
                point_time = st.time_input("Time (CT)", value=dtime(17, 0) if i == 0 else (dtime(1, 0) if i == 1 else dtime(3, 30)), step=1800, key=f"dyn_p{i+1}_time")
            with col3:
                default_prices = [6861.10, 6856.90, 6845.30] if mode_a else [6845.30, 6840.00, 6861.10]
                point_price = st.number_input("Price ($)", value=default_prices[i], step=0.01, key=f"dyn_p{i+1}_price", format="%.2f")
            
            points_data.append({
                'date': point_date,
                'time': point_time,
                'price': point_price,
                'datetime': CT.localize(datetime.combine(point_date, point_time))
            })
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Calculate and Display Channel
        if st.button("🚀 CALCULATE DYNAMIC CHANNEL", use_container_width=True):
            # Get RTH slots
            dynamic_slots = rth_slots_ct_dt(dynamic_proj_date, "08:30", "14:00")
            
            # Project the dynamic channel
            df_dynamic, slope, channel_width = project_dynamic_channel(
                points_data[0]['price'], points_data[0]['datetime'],
                points_data[1]['price'], points_data[1]['datetime'],
                points_data[2]['price'], points_data[2]['datetime'],
                dynamic_slots
            )
            
            # Determine line names based on mode
            if mode_a:
                upper_name = "🔴 Resistance (Upper)"
                lower_name = "🟢 Support (Lower)"
                df_dynamic_display = df_dynamic.rename(columns={
                    "Primary Line": upper_name,
                    "Parallel Line": lower_name
                })
            else:
                upper_name = "🔴 Resistance (Upper)"
                lower_name = "🟢 Support (Lower)"
                df_dynamic_display = df_dynamic.rename(columns={
                    "Parallel Line": upper_name,
                    "Primary Line": lower_name
                })
            
            # Display Channel Metrics
            st.markdown('<div class="premium-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">📊 CHANNEL METRICS</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="stats-bar">', unsafe_allow_html=True)
            st.markdown(f'''
                <div class="stat-item">
                    <div class="stat-label">Slope (pts/30min)</div>
                    <div class="stat-value">{slope:+.4f}</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Channel Width</div>
                    <div class="stat-value">{abs(channel_width):.2f} pts</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">Direction</div>
                    <div class="stat-value">{"📈 UP" if slope > 0 else "📉 DOWN" if slope < 0 else "⚖️ FLAT"}</div>
                </div>
            ''', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Display Projection Table
            st.markdown('<div class="premium-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">📊 RTH PROJECTION TABLE (8:30 AM - 2:00 PM)</div>', unsafe_allow_html=True)
            
            st.dataframe(df_dynamic_display, use_container_width=True, hide_index=True, height=500)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Download Button
            st.download_button(
                "📥 DOWNLOAD CHANNEL DATA",
                df_dynamic_display.to_csv(index=False).encode(),
                f"dynamic_channel_{dynamic_proj_date}.csv",
                "text/csv",
                use_container_width=True
            )
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Entry/Exit Analysis
            st.markdown('<div class="premium-card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">🎯 ENTRY/EXIT ANALYSIS</div>', unsafe_allow_html=True)
            
            # Get upper and lower values
            if mode_a:
                upper_line = df_dynamic["Primary Line"].values
                lower_line = df_dynamic["Parallel Line"].values
            else:
                upper_line = df_dynamic["Parallel Line"].values
                lower_line = df_dynamic["Primary Line"].values
            
            st.markdown(f"""
            ### 📈 Trading Strategy
            
            **BUY SETUP:**
            - ✅ **Entry Zone:** Price touches **{lower_name}** (Support)
            - 🎯 **Target:** **{upper_name}** (Resistance)
            - 🛑 **Stop Loss:** Below support channel
            
            **SELL SETUP:**
            - ✅ **Entry Zone:** Price touches **{upper_name}** (Resistance)
            - 🎯 **Target:** **{lower_name}** (Support)
            - 🛑 **Stop Loss:** Above resistance channel
            
            **Channel Width:** {abs(channel_width):.2f} points = **Profit Potential** per trade
            """)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.success("✅ Dynamic channel calculated successfully! Use the table to identify entry/exit points throughout RTH.")
        
        else:
            st.info("💡 Configure your 3 anchor points above, then click **CALCULATE DYNAMIC CHANNEL** to generate projections.")
        
        st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()