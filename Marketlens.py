# app.py
# SPX PROPHET — Ultimate Professional Trading Platform
# Beautiful UI with manual live price tracking and intelligent analytics

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List, Dict, Tuple

APP_NAME = "SPX PROPHET"
APP_VERSION = "v4.0 Ultimate"

# ===============================
# CONFIGURATION
# ===============================

CT = pytz.timezone("America/Chicago")
ASC_SLOPE = 0.5412
DESC_SLOPE = -0.5412

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

def get_trading_zone(price: float, projections: Dict[str, float]) -> Tuple[str, str, str]:
    final_resistance = projections['Final Resistance']
    mid_support = projections['Mid Support']
    mid_resistance = projections['Mid Resistance']
    final_support = projections['Final Support']
    
    sorted_prices = sorted([final_resistance, mid_support, mid_resistance, final_support])
    
    if price >= max(sorted_prices):
        return "🚀 BREAKOUT ZONE", "Above all projections - Strong bullish breakout", "error"
    elif price <= min(sorted_prices):
        return "💥 BREAKDOWN ZONE", "Below all projections - Strong bearish breakdown", "info"
    elif price >= final_resistance - 2:
        return "🔴 FINAL RESISTANCE", "SELL ZONE - Expect reversal down", "success"
    elif price <= final_support + 2:
        return "🟢 FINAL SUPPORT", "BUY ZONE - Expect reversal up", "success"
    elif price >= mid_resistance - 2:
        return "🟠 MID RESISTANCE", "Watch for rejection or breakout", "warning"
    elif price <= mid_support + 2:
        return "🟡 MID SUPPORT", "Watch for bounce or breakdown", "warning"
    else:
        return "⚪ NEUTRAL ZONE", "Between levels - Wait for direction", "info"

def calculate_distances(price: float, projections: Dict[str, float]) -> Dict[str, float]:
    return {name: round(price - proj_price, 2) for name, proj_price in projections.items()}

def get_playbook(zone_name: str, projections: Dict[str, float]) -> str:
    if "FINAL SUPPORT" in zone_name:
        return f"💰 **BUY Strategy:** Enter at ${projections['Final Support']:.2f} → Target ${projections['Mid Resistance']:.2f} (first) → ${projections['Final Resistance']:.2f} (extended)"
    elif "FINAL RESISTANCE" in zone_name:
        return f"💰 **SELL Strategy:** Enter at ${projections['Final Resistance']:.2f} → Target ${projections['Mid Support']:.2f} (first) → ${projections['Final Support']:.2f} (extended)"
    elif "MID SUPPORT" in zone_name:
        return f"📉 **Strategy:** SHORT to ${projections['Final Support']:.2f}, then REVERSE LONG to ${projections['Mid Resistance']:.2f}"
    elif "MID RESISTANCE" in zone_name:
        return f"📈 **Strategy:** LONG to ${projections['Final Resistance']:.2f}, then REVERSE SHORT to ${projections['Mid Support']:.2f}"
    elif "NEUTRAL" in zone_name:
        return f"⏸️ **Wait Mode:** Enter LONG at ${projections['Mid Support']:.2f} OR SHORT at ${projections['Mid Resistance']:.2f}"
    elif "BREAKOUT" in zone_name:
        return f"🎯 **Momentum Play:** Strong bullish continuation - Trail stops higher, ride the trend"
    elif "BREAKDOWN" in zone_name:
        return f"🎯 **Momentum Play:** Strong bearish continuation - Trail stops lower, ride the trend"
    return "Monitor price action"

# ===============================
# BEAUTIFUL THEME
# ===============================

def get_theme_css(mode: str) -> str:
    if mode == "🌙 Dark":
        return """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap');
        
        * { font-family: 'Space Grotesk', sans-serif; }
        
        html, body, [class*="st"], .main, .block-container {
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
            color: #f1f5f9 !important;
        }
        
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
            border-right: 1px solid #334155 !important;
        }
        
        section[data-testid="stSidebar"] * {
            color: #f1f5f9 !important;
        }
        
        .header-container {
            text-align: center;
            padding: 3rem 0 2rem 0;
            background: radial-gradient(ellipse at top, rgba(59, 130, 246, 0.15), transparent);
            border-radius: 24px;
            margin-bottom: 2rem;
        }
        
        .main-title {
            font-size: 4.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 50%, #ec4899 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 0.05em;
            margin: 0;
            text-shadow: 0 0 80px rgba(59, 130, 246, 0.5);
        }
        
        .subtitle {
            font-size: 1.25rem;
            color: #94a3b8;
            margin-top: 1rem;
            font-weight: 500;
        }
        
        .divider {
            height: 3px;
            background: linear-gradient(90deg, transparent, #3b82f6, #8b5cf6, #ec4899, transparent);
            margin: 1.5rem auto;
            width: 200px;
            border-radius: 10px;
        }
        
        .premium-card {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9)) !important;
            border: 1px solid #334155 !important;
            border-radius: 20px !important;
            padding: 0 !important;
            margin: 2rem 0 !important;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4), 0 0 40px rgba(59, 130, 246, 0.1) !important;
            backdrop-filter: blur(10px) !important;
        }
        
        .card-header {
            background: linear-gradient(135deg, #1e293b, #0f172a) !important;
            border-bottom: 1px solid #334155 !important;
            padding: 1.5rem 2rem !important;
            border-radius: 20px 20px 0 0 !important;
        }
        
        .card-title {
            font-size: 1.75rem !important;
            font-weight: 700 !important;
            color: #f1f5f9 !important;
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .card-body {
            padding: 2rem !important;
        }
        
        .icon-large {
            font-size: 2.5rem;
            filter: drop-shadow(0 4px 12px rgba(59, 130, 246, 0.4));
        }
        
        .live-price-box {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(139, 92, 246, 0.2));
            border: 2px solid #3b82f6;
            border-radius: 20px;
            padding: 2.5rem;
            text-align: center;
            margin: 2rem 0;
            box-shadow: 0 0 60px rgba(59, 130, 246, 0.3), inset 0 0 40px rgba(59, 130, 246, 0.1);
        }
        
        .price-display {
            font-size: 4.5rem;
            font-weight: 900;
            font-family: 'JetBrains Mono', monospace;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6, #ec4899);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 40px rgba(59, 130, 246, 0.5);
        }
        
        .price-label {
            font-size: 0.875rem;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-weight: 600;
            margin-top: 1rem;
        }
        
        .zone-alert {
            padding: 1.5rem 2rem;
            border-radius: 16px;
            margin: 1.5rem 0;
            border-left: 4px solid;
            backdrop-filter: blur(10px);
        }
        
        .zone-alert.success {
            background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(34, 197, 94, 0.05));
            border-color: #22c55e;
            box-shadow: 0 0 30px rgba(34, 197, 94, 0.2);
        }
        
        .zone-alert.error {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 0.05));
            border-color: #ef4444;
            box-shadow: 0 0 30px rgba(239, 68, 68, 0.2);
        }
        
        .zone-alert.warning {
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(245, 158, 11, 0.05));
            border-color: #f59e0b;
            box-shadow: 0 0 30px rgba(245, 158, 11, 0.2);
        }
        
        .zone-alert.info {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(59, 130, 246, 0.05));
            border-color: #3b82f6;
            box-shadow: 0 0 30px rgba(59, 130, 246, 0.2);
        }
        
        .zone-title {
            font-size: 1.75rem;
            font-weight: 800;
            margin-bottom: 0.5rem;
            color: #f1f5f9;
        }
        
        .zone-desc {
            font-size: 1.125rem;
            color: #cbd5e1;
        }
        
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin: 1.5rem 0;
        }
        
        .metric-card {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.8));
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 1.75rem;
            text-align: center;
            transition: all 0.3s ease;
        }
        
        .metric-card:hover {
            border-color: #3b82f6;
            box-shadow: 0 0 30px rgba(59, 130, 246, 0.3);
            transform: translateY(-4px);
        }
        
        .metric-label {
            font-size: 0.75rem;
            font-weight: 700;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 1rem;
        }
        
        .metric-value {
            font-size: 2.25rem;
            font-weight: 900;
            font-family: 'JetBrains Mono', monospace;
            color: #f1f5f9;
        }
        
        .distance-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.25rem 1.5rem;
            background: rgba(30, 41, 59, 0.6);
            border: 1px solid #334155;
            border-radius: 12px;
            margin: 0.75rem 0;
            transition: all 0.3s ease;
        }
        
        .distance-row:hover {
            background: rgba(30, 41, 59, 0.9);
            border-color: #3b82f6;
            transform: translateX(4px);
        }
        
        .distance-name {
            font-weight: 700;
            font-size: 1.125rem;
            color: #f1f5f9;
        }
        
        .distance-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 1.25rem;
        }
        
        .distance-value.above { color: #22c55e; }
        .distance-value.below { color: #ef4444; }
        
        .playbook-box {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(139, 92, 246, 0.15));
            border: 2px solid #3b82f6;
            border-radius: 16px;
            padding: 2rem 2.5rem;
            margin: 2rem 0;
            box-shadow: 0 0 40px rgba(59, 130, 246, 0.2);
        }
        
        .playbook-title {
            font-size: 1.5rem;
            font-weight: 800;
            color: #f1f5f9;
            margin-bottom: 1rem;
        }
        
        .playbook-content {
            font-size: 1.125rem;
            color: #cbd5e1;
            line-height: 1.7;
        }
        
        .anchor-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin: 2rem 0;
        }
        
        .anchor-box {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.8));
            border: 2px solid #334155;
            border-radius: 16px;
            padding: 2rem;
            transition: all 0.3s ease;
        }
        
        .anchor-box:hover {
            border-color: #3b82f6;
            box-shadow: 0 0 40px rgba(59, 130, 246, 0.2);
            transform: translateY(-4px);
        }
        
        .anchor-header {
            font-size: 1.5rem;
            font-weight: 800;
            color: #f1f5f9;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        /* FIX: Make dataframe text VISIBLE */
        .stDataFrame {
            border: 1px solid #334155 !important;
            border-radius: 16px !important;
            overflow: hidden !important;
        }
        
        .stDataFrame table {
            font-family: 'JetBrains Mono', monospace !important;
            color: #f1f5f9 !important;
        }
        
        .stDataFrame thead th {
            background: linear-gradient(135deg, #1e293b, #0f172a) !important;
            color: #94a3b8 !important;
            font-weight: 900 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.1em !important;
            padding: 1.25rem 1.5rem !important;
            border-bottom: 2px solid #334155 !important;
            font-size: 0.875rem !important;
        }
        
        .stDataFrame tbody td {
            background: rgba(30, 41, 59, 0.4) !important;
            color: #f1f5f9 !important;
            padding: 1rem 1.5rem !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
            border-bottom: 1px solid #334155 !important;
        }
        
        .stDataFrame tbody tr:hover td {
            background: rgba(59, 130, 246, 0.2) !important;
        }
        
        /* Input styling */
        .stNumberInput input, .stDateInput input, .stTimeInput input, .stTextInput input {
            background: rgba(30, 41, 59, 0.8) !important;
            border: 2px solid #334155 !important;
            border-radius: 12px !important;
            padding: 1rem 1.25rem !important;
            color: #f1f5f9 !important;
            font-weight: 600 !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 1.125rem !important;
        }
        
        .stNumberInput input:focus, .stDateInput input:focus, .stTimeInput input:focus, .stTextInput input:focus {
            border-color: #3b82f6 !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.3) !important;
        }
        
        .stNumberInput label, .stDateInput label, .stTimeInput label, .stTextInput label, .stSelectbox label {
            color: #94a3b8 !important;
            font-weight: 700 !important;
            font-size: 0.875rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            margin-bottom: 0.75rem !important;
        }
        
        /* Buttons */
        .stButton button, .stDownloadButton button {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 1rem 2rem !important;
            font-weight: 800 !important;
            font-size: 1rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 10px 30px rgba(59, 130, 246, 0.4) !important;
        }
        
        .stButton button:hover, .stDownloadButton button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 15px 40px rgba(59, 130, 246, 0.6) !important;
        }
        
        /* Selectbox */
        .stSelectbox div[data-baseweb="select"] {
            background: rgba(30, 41, 59, 0.8) !important;
            border: 2px solid #334155 !important;
            border-radius: 12px !important;
        }
        
        .stSelectbox div[data-baseweb="select"]:hover {
            border-color: #3b82f6 !important;
        }
        
        /* Sidebar specific */
        section[data-testid="stSidebar"] label {
            color: #94a3b8 !important;
        }
        
        section[data-testid="stSidebar"] .stRadio label {
            font-weight: 700 !important;
            text-transform: uppercase !important;
        }
        
        </style>
        """
    else:  # Light mode
        return """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap');
        
        * { font-family: 'Space Grotesk', sans-serif; }
        
        html, body, [class*="st"], .main, .block-container {
            background: linear-gradient(135deg, #f8fafc 0%, #e0e7ff 100%) !important;
            color: #0f172a !important;
        }
        
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%) !important;
            border-right: 1px solid #cbd5e1 !important;
        }
        
        section[data-testid="stSidebar"] * {
            color: #0f172a !important;
        }
        
        .header-container {
            text-align: center;
            padding: 3rem 0 2rem 0;
            background: radial-gradient(ellipse at top, rgba(59, 130, 246, 0.1), transparent);
            border-radius: 24px;
            margin-bottom: 2rem;
        }
        
        .main-title {
            font-size: 4.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #2563eb 0%, #7c3aed 50%, #db2777 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 0.05em;
            margin: 0;
        }
        
        .subtitle {
            font-size: 1.25rem;
            color: #475569;
            margin-top: 1rem;
            font-weight: 500;
        }
        
        .divider {
            height: 3px;
            background: linear-gradient(90deg, transparent, #2563eb, #7c3aed, #db2777, transparent);
            margin: 1.5rem auto;
            width: 200px;
            border-radius: 10px;
        }
        
        .premium-card {
            background: rgba(255, 255, 255, 0.95) !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 20px !important;
            padding: 0 !important;
            margin: 2rem 0 !important;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.08), 0 0 40px rgba(59, 130, 246, 0.05) !important;
        }
        
        .card-header {
            background: linear-gradient(135deg, #f1f5f9, #e0e7ff) !important;
            border-bottom: 1px solid #cbd5e1 !important;
            padding: 1.5rem 2rem !important;
            border-radius: 20px 20px 0 0 !important;
        }
        
        .card-title {
            font-size: 1.75rem !important;
            font-weight: 700 !important;
            color: #0f172a !important;
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        .card-body {
            padding: 2rem !important;
        }
        
        .icon-large {
            font-size: 2.5rem;
            filter: drop-shadow(0 4px 12px rgba(59, 130, 246, 0.3));
        }
        
        .live-price-box {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1));
            border: 2px solid #2563eb;
            border-radius: 20px;
            padding: 2.5rem;
            text-align: center;
            margin: 2rem 0;
            box-shadow: 0 0 40px rgba(59, 130, 246, 0.15);
        }
        
        .price-display {
            font-size: 4.5rem;
            font-weight: 900;
            font-family: 'JetBrains Mono', monospace;
            background: linear-gradient(135deg, #2563eb, #7c3aed, #db2777);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .price-label {
            font-size: 0.875rem;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-weight: 600;
            margin-top: 1rem;
        }
        
        .zone-alert {
            padding: 1.5rem 2rem;
            border-radius: 16px;
            margin: 1.5rem 0;
            border-left: 4px solid;
        }
        
        .zone-alert.success {
            background: linear-gradient(135deg, rgba(34, 197, 94, 0.15), rgba(34, 197, 94, 0.05));
            border-color: #22c55e;
            color: #0f172a;
        }
        
        .zone-alert.error {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(239, 68, 68, 0.05));
            border-color: #ef4444;
            color: #0f172a;
        }
        
        .zone-alert.warning {
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(245, 158, 11, 0.05));
            border-color: #f59e0b;
            color: #0f172a;
        }
        
        .zone-alert.info {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(59, 130, 246, 0.05));
            border-color: #2563eb;
            color: #0f172a;
        }
        
        .zone-title {
            font-size: 1.75rem;
            font-weight: 800;
            margin-bottom: 0.5rem;
            color: #0f172a;
        }
        
        .zone-desc {
            font-size: 1.125rem;
            color: #334155;
        }
        
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin: 1.5rem 0;
        }
        
        .metric-card {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid #cbd5e1;
            border-radius: 16px;
            padding: 1.75rem;
            text-align: center;
            transition: all 0.3s ease;
        }
        
        .metric-card:hover {
            border-color: #2563eb;
            box-shadow: 0 0 30px rgba(59, 130, 246, 0.2);
            transform: translateY(-4px);
        }
        
        .metric-label {
            font-size: 0.75rem;
            font-weight: 700;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            margin-bottom: 1rem;
        }
        
        .metric-value {
            font-size: 2.25rem;
            font-weight: 900;
            font-family: 'JetBrains Mono', monospace;
            color: #0f172a;
        }
        
        .distance-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1.25rem 1.5rem;
            background: rgba(255, 255, 255, 0.8);
            border: 1px solid #cbd5e1;
            border-radius: 12px;
            margin: 0.75rem 0;
            transition: all 0.3s ease;
        }
        
        .distance-row:hover {
            background: rgba(255, 255, 255, 1);
            border-color: #2563eb;
            transform: translateX(4px);
        }
        
        .distance-name {
            font-weight: 700;
            font-size: 1.125rem;
            color: #0f172a;
        }
        
        .distance-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 1.25rem;
        }
        
        .distance-value.above { color: #22c55e; }
        .distance-value.below { color: #ef4444; }
        
        .playbook-box {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1));
            border: 2px solid #2563eb;
            border-radius: 16px;
            padding: 2rem 2.5rem;
            margin: 2rem 0;
        }
        
        .playbook-title {
            font-size: 1.5rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 1rem;
        }
        
        .playbook-content {
            font-size: 1.125rem;
            color: #334155;
            line-height: 1.7;
        }
        
        .anchor-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin: 2rem 0;
        }
        
        .anchor-box {
            background: rgba(255, 255, 255, 0.9);
            border: 2px solid #cbd5e1;
            border-radius: 16px;
            padding: 2rem;
            transition: all 0.3s ease;
        }
        
        .anchor-box:hover {
            border-color: #2563eb;
            box-shadow: 0 0 30px rgba(59, 130, 246, 0.15);
            transform: translateY(-4px);
        }
        
        .anchor-header {
            font-size: 1.5rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 1rem;
        }
        
        /* FIX: Make dataframe text VISIBLE */
        .stDataFrame {
            border: 1px solid #cbd5e1 !important;
            border-radius: 16px !important;
            overflow: hidden !important;
        }
        
        .stDataFrame table {
            font-family: 'JetBrains Mono', monospace !important;
            color: #0f172a !important;
        }
        
        .stDataFrame thead th {
            background: linear-gradient(135deg, #f1f5f9, #e0e7ff) !important;
            color: #475569 !important;
            font-weight: 900 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.1em !important;
            padding: 1.25rem 1.5rem !important;
            border-bottom: 2px solid #cbd5e1 !important;
            font-size: 0.875rem !important;
        }
        
        .stDataFrame tbody td {
            background: rgba(255, 255, 255, 0.6) !important;
            color: #0f172a !important;
            padding: 1rem 1.5rem !important;
            font-weight: 600 !important;
            font-size: 1rem !important;
            border-bottom: 1px solid #e0e7ff !important;
        }
        
        .stDataFrame tbody tr:hover td {
            background: rgba(59, 130, 246, 0.1) !important;
        }
        
        /* Input styling */
        .stNumberInput input, .stDateInput input, .stTimeInput input, .stTextInput input {
            background: rgba(255, 255, 255, 0.9) !important;
            border: 2px solid #cbd5e1 !important;
            border-radius: 12px !important;
            padding: 1rem 1.25rem !important;
            color: #0f172a !important;
            font-weight: 600 !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 1.125rem !important;
        }
        
        .stNumberInput input:focus, .stDateInput input:focus, .stTimeInput input:focus, .stTextInput input:focus {
            border-color: #2563eb !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2) !important;
        }
        
        .stNumberInput label, .stDateInput label, .stTimeInput label, .stTextInput label, .stSelectbox label {
            color: #475569 !important;
            font-weight: 700 !important;
            font-size: 0.875rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            margin-bottom: 0.75rem !important;
        }
        
        /* Buttons */
        .stButton button, .stDownloadButton button {
            background: linear-gradient(135deg, #2563eb, #7c3aed) !important;
            color: #ffffff !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 1rem 2rem !important;
            font-weight: 800 !important;
            font-size: 1rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.05em !important;
            transition: all 0.3s ease !important;
            box-shadow: 0 10px 30px rgba(59, 130, 246, 0.3) !important;
        }
        
        .stButton button:hover, .stDownloadButton button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 15px 40px rgba(59, 130, 246, 0.5) !important;
        }
        
        /* Selectbox */
        .stSelectbox div[data-baseweb="select"] {
            background: rgba(255, 255, 255, 0.9) !important;
            border: 2px solid #cbd5e1 !important;
            border-radius: 12px !important;
        }
        
        .stSelectbox div[data-baseweb="select"]:hover {
            border-color: #2563eb !important;
        }
        
        /* Sidebar specific */
        section[data-testid="stSidebar"] label {
            color: #475569 !important;
        }
        
        section[data-testid="stSidebar"] .stRadio label {
            font-weight: 700 !important;
            text-transform: uppercase !important;
        }
        
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
        theme_mode = st.radio("Theme", ["☀️ Light", "🌙 Dark"], index=1)
        
        st.markdown("---")
        st.markdown("### 📊 Slope Configuration")
        st.info(f"**⬆️ Ascending:** +{ASC_SLOPE}")
        st.info(f"**⬇️ Descending:** {DESC_SLOPE}")
        
        st.markdown("---")
        st.markdown("### ℹ️ System Info")
        st.caption("🕐 Central Time (CT)")
        st.caption("📊 RTH: 8:30 AM - 2:00 PM")
        st.caption("⚠️ Skips 4-5 PM maintenance")
        st.caption("🎯 Dual anchor system")
        st.caption("📈 4 projection lines")
        
        st.markdown("---")
        st.markdown("### 🎓 Line Definitions")
        st.caption("🔴 **Final Resistance** = Ultimate sell")
        st.caption("🟠 **Mid Resistance** = Intermediate")
        st.caption("🟡 **Mid Support** = Intermediate")
        st.caption("🟢 **Final Support** = Ultimate buy")
    
    st.markdown(get_theme_css(theme_mode), unsafe_allow_html=True)
    
    # Header
    st.markdown("""
        <div class="header-container">
            <div class="main-title">📊 SPX PROPHET</div>
            <div class="divider"></div>
            <div class="subtitle">🎯 Professional Market Projection Platform</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Configuration
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header"><div class="card-title"><span class="icon-large">⚙️</span> Anchor Configuration</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    
    proj_day = st.date_input("📅 Projection Date (CT)", value=datetime.now(CT).date())
    
    st.markdown('<div class="anchor-grid">', unsafe_allow_html=True)
    
    # Skyline
    st.markdown('<div class="anchor-box">', unsafe_allow_html=True)
    st.markdown('<div class="anchor-header">☁️ SKYLINE (Upper Anchor)</div>', unsafe_allow_html=True)
    skyline_name = st.text_input("Custom Name", value="Skyline", key="sky_name")
    skyline_date = st.date_input("Anchor Date", value=proj_day - timedelta(days=1), key="sky_date")
    skyline_price = st.number_input("Anchor Price ($)", value=6634.70, step=0.01, key="sky_price", format="%.2f")
    skyline_time = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="sky_time")
    st.caption("🔴 Final Resistance + 🟡 Mid Support")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Baseline
    st.markdown('<div class="anchor-box">', unsafe_allow_html=True)
    st.markdown('<div class="anchor-header">⚓ BASELINE (Lower Anchor)</div>', unsafe_allow_html=True)
    baseline_name = st.text_input("Custom Name", value="Baseline", key="base_name")
    baseline_date = st.date_input("Anchor Date", value=proj_day - timedelta(days=1), key="base_date")
    baseline_price = st.number_input("Anchor Price ($)", value=6600.00, step=0.01, key="base_price", format="%.2f")
    baseline_time = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="base_time")
    st.caption("🟢 Final Support + 🟠 Mid Resistance")
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div></div></div>', unsafe_allow_html=True)
    
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
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header"><div class="card-title"><span class="icon-large">📊</span> Live Price Analysis</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        live_price = st.number_input("💵 Current SPX Price ($)", value=0.00, step=0.01, key="live_price", format="%.2f")
    with col2:
        current_time_str = st.selectbox("🕐 At Time", merged["Time (CT)"].tolist(), index=0)
    
    if live_price > 0:
        st.markdown(f"""
            <div class="live-price-box">
                <div class="price-label">💵 LIVE SPX PRICE</div>
                <div class="price-display">${live_price:.2f}</div>
                <div class="price-label">Analysis Time: {current_time_str}</div>
            </div>
        """, unsafe_allow_html=True)
        
        current_row = merged[merged["Time (CT)"] == current_time_str].iloc[0]
        current_projections = {
            "Final Resistance": current_row["🔴 Final Resistance"],
            "Mid Support": current_row["🟡 Mid Support"],
            "Mid Resistance": current_row["🟠 Mid Resistance"],
            "Final Support": current_row["🟢 Final Support"]
        }
        
        zone_name, zone_desc, zone_type = get_trading_zone(live_price, current_projections)
        st.markdown(f"""
            <div class="zone-alert {zone_type}">
                <div class="zone-title">{zone_name}</div>
                <div class="zone-desc">{zone_desc}</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 📏 Distance to Key Levels")
        distances = calculate_distances(live_price, current_projections)
        for name, dist in sorted(distances.items(), key=lambda x: abs(x[1])):
            direction = "above" if dist > 0 else "below"
            icon = "🔴" if "Final Resistance" in name else "🟡" if "Mid Support" in name else "🟠" if "Mid Resistance" in name else "🟢"
            st.markdown(f"""
                <div class="distance-row">
                    <span class="distance-name">{icon} {name}</span>
                    <span class="distance-value {direction}">{dist:+.2f} pts</span>
                </div>
            """, unsafe_allow_html=True)
        
        playbook = get_playbook(zone_name, current_projections)
        st.markdown(f"""
            <div class="playbook-box">
                <div class="playbook-title">📋 Trading Playbook</div>
                <div class="playbook-content">{playbook}</div>
            </div>
        """, unsafe_allow_html=True)
        
        all_proj = list(current_projections.values())
        if live_price > max(all_proj):
            deviation = live_price - max(all_proj)
            st.error(f"🚨 **BREAKOUT:** Price is {deviation:.2f} pts ABOVE all projections!")
        elif live_price < min(all_proj):
            deviation = min(all_proj) - live_price
            st.error(f"🚨 **BREAKDOWN:** Price is {deviation:.2f} pts BELOW all projections!")
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # Market Open
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header"><div class="card-title"><span class="icon-large">🌅</span> Market Open (8:30 AM)</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    
    open_row = merged[merged["Time (CT)"] == "08:30 AM"].iloc[0]
    
    st.markdown('<div class="metric-grid">', unsafe_allow_html=True)
    icons = ["🔴", "🟠", "🟡", "🟢"]
    for idx, col_name in enumerate(["🔴 Final Resistance", "🟠 Mid Resistance", "🟡 Mid Support", "🟢 Final Support"]):
        price = open_row[col_name]
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{icons[idx]} {col_name.replace(icons[idx], '').strip()}</div>
                <div class="metric-value">${price:.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # Expected Range
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header"><div class="card-title"><span class="icon-large">📈</span> Expected Trading Range</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    
    all_prices = merged[["🔴 Final Resistance", "🟡 Mid Support", "🟠 Mid Resistance", "🟢 Final Support"]].values.flatten()
    expected_high = np.max(all_prices)
    expected_low = np.min(all_prices)
    expected_range = expected_high - expected_low
    expected_mid = (expected_high + expected_low) / 2
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("⬆️ Expected High", f"${expected_high:.2f}")
    col2.metric("⬇️ Expected Low", f"${expected_low:.2f}")
    col3.metric("📊 Range", f"${expected_range:.2f}")
    col4.metric("🎯 Midpoint", f"${expected_mid:.2f}")
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # Table
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-header"><div class="card-title"><span class="icon-large">📊</span> Complete Projection Matrix</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    
    st.dataframe(merged, use_container_width=True, hide_index=True, height=500)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Export
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.download_button("💾 Complete", merged.to_csv(index=False).encode(), "spx_prophet_complete.csv", "text/csv", use_container_width=True)
    with col2:
        st.download_button(f"☁️ {skyline_name}", merged[["Time (CT)", "🔴 Final Resistance", "🟡 Mid Support"]].to_csv(index=False).encode(), f"{skyline_name.lower()}.csv", "text/csv", use_container_width=True)
    with col3:
        st.download_button(f"⚓ {baseline_name}", merged[["Time (CT)", "🟠 Mid Resistance", "🟢 Final Support"]].to_csv(index=False).encode(), f"{baseline_name.lower()}.csv", "text/csv", use_container_width=True)
    with col4:
        st.download_button("📊 Analytics", pd.DataFrame({'Metric': ['High', 'Low', 'Range', 'Mid'], 'Value': [expected_high, expected_low, expected_range, expected_mid]}).to_csv(index=False).encode(), "analytics.csv", "text/csv", use_container_width=True)
    
    st.markdown('</div></div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()