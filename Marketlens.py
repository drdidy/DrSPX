# app.py
# ═══════════════════════════════════════════════════════════════════════════════
# 🔮 SPX PROPHET — Premium Glassmorphism Edition
# Ultra-modern UI with advanced animations, glassmorphism, and stunning visuals
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, date, time, timedelta
from typing import List, Tuple

# ───────────────────────────────────────────────────────────────────────────────
# CONFIG & PAGE SETUP
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SPX Prophet - Premium Trading Analytics", 
    page_icon="🔮", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'bc_result' not in st.session_state:
    st.session_state.bc_result = None
if 'rejection_result' not in st.session_state:
    st.session_state.rejection_result = None
if 'show_help' not in st.session_state:
    st.session_state.show_help = False

CT = pytz.timezone("America/Chicago")

SLOPE_SPX = 0.25                 
SLOPE_CONTRACT_DEFAULT = -0.33   

RTH_START = time(8, 30)
RTH_END   = time(14, 30)

DEFAULT_ANCHOR = 6400.00
DEFAULT_CONTRACT_3PM = 20.00

# ───────────────────────────────────────────────────────────────────────────────
# PREMIUM GLASSMORPHISM STYLING
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');
    @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
    
    :root {
        /* Premium Color Palette */
        --primary: #6366f1;
        --primary-light: #818cf8;
        --primary-dark: #4f46e5;
        --secondary: #06b6d4;
        --accent: #f59e0b;
        --success: #10b981;
        --warning: #f59e0b;
        --error: #ef4444;
        
        /* Glassmorphism Colors */
        --glass-bg: rgba(255, 255, 255, 0.15);
        --glass-border: rgba(255, 255, 255, 0.2);
        --glass-shadow: rgba(31, 38, 135, 0.15);
        --glass-hover: rgba(255, 255, 255, 0.25);
        
        /* Surface Colors */
        --surface: rgba(255, 255, 255, 0.95);
        --surface-glass: rgba(255, 255, 255, 0.1);
        --surface-elevated: rgba(255, 255, 255, 0.8);
        
        /* Text Colors */
        --text-primary: #1e293b;
        --text-secondary: #475569;
        --text-muted: #64748b;
        --text-light: rgba(255, 255, 255, 0.9);
        
        /* Shadows */
        --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.06);
        --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.08);
        --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.12);
        --shadow-xl: 0 16px 64px rgba(0, 0, 0, 0.16);
        --shadow-glow: 0 0 40px rgba(99, 102, 241, 0.3);
        --shadow-inner: inset 0 2px 4px rgba(0, 0, 0, 0.06);
    }
    
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        min-height: 100vh;
    }
    
    .main > div {
        padding: 2rem;
        background: transparent;
    }
    
    /* Animated Background */
    body::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: 
            radial-gradient(circle at 20% 50%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, rgba(255, 119, 198, 0.3) 0%, transparent 50%),
            radial-gradient(circle at 40% 80%, rgba(120, 199, 255, 0.3) 0%, transparent 50%);
        animation: backgroundFloat 20s ease-in-out infinite;
        pointer-events: none;
        z-index: -1;
    }
    
    @keyframes backgroundFloat {
        0%, 100% { opacity: 1; transform: translateY(0px); }
        50% { opacity: 0.8; transform: translateY(-20px); }
    }
    
    /* Premium Glass Cards */
    .glass-card {
        background: var(--glass-bg);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--glass-border);
        border-radius: 24px;
        padding: 2rem;
        box-shadow: var(--shadow-lg);
        position: relative;
        overflow: hidden;
        transition: all 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
        animation: slideInUp 0.6s ease-out;
    }
    
    .glass-card:hover {
        transform: translateY(-8px);
        box-shadow: var(--shadow-xl), var(--shadow-glow);
        background: var(--glass-hover);
        border-color: rgba(255, 255, 255, 0.3);
    }
    
    .glass-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
    }
    
    /* Metric Cards with Large Icons */
    .metric-glass-card {
        background: var(--glass-bg);
        backdrop-filter: blur(25px);
        -webkit-backdrop-filter: blur(25px);
        border: 1px solid var(--glass-border);
        border-radius: 20px;
        padding: 2rem;
        box-shadow: var(--shadow-md);
        position: relative;
        overflow: hidden;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
        animation: fadeInScale 0.5s ease-out;
    }
    
    .metric-glass-card:hover {
        transform: translateY(-4px) scale(1.02);
        box-shadow: var(--shadow-xl);
        background: var(--glass-hover);
        border-color: var(--primary-light);
    }
    
    .metric-icon {
        font-size: 3rem;
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 1rem;
        display: block;
        text-align: center;
        animation: iconFloat 3s ease-in-out infinite;
    }
    
    @keyframes iconFloat {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-5px); }
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: var(--text-primary);
        text-align: center;
        margin: 1rem 0;
        background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: textGlow 2s ease-in-out infinite alternate;
    }
    
    @keyframes textGlow {
        from { opacity: 0.8; }
        to { opacity: 1; }
    }
    
    .metric-label {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    
    .metric-sub {
        font-size: 0.8rem;
        color: var(--text-muted);
        text-align: center;
        line-height: 1.6;
        margin-top: 1rem;
    }
    
    /* Hero Header with Floating Elements */
    .hero-header {
        background: linear-gradient(135deg, 
            rgba(99, 102, 241, 0.9) 0%, 
            rgba(139, 92, 246, 0.9) 50%, 
            rgba(59, 130, 246, 0.9) 100%);
        backdrop-filter: blur(30px);
        -webkit-backdrop-filter: blur(30px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 32px;
        padding: 4rem 2rem;
        margin-bottom: 3rem;
        position: relative;
        overflow: hidden;
        text-align: center;
        box-shadow: var(--shadow-xl);
        animation: heroEntrance 1s ease-out;
    }
    
    .hero-header::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: conic-gradient(
            from 0deg,
            rgba(255, 255, 255, 0) 0deg,
            rgba(255, 255, 255, 0.1) 60deg,
            rgba(255, 255, 255, 0.2) 120deg,
            rgba(255, 255, 255, 0) 180deg
        );
        animation: rotate 20s linear infinite;
    }
    
    @keyframes rotate {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    @keyframes heroEntrance {
        0% { opacity: 0; transform: translateY(30px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    
    .hero-title {
        font-size: 4rem;
        font-weight: 900;
        color: var(--text-light);
        margin-bottom: 1rem;
        position: relative;
        z-index: 2;
        text-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        animation: titlePulse 3s ease-in-out infinite;
    }
    
    @keyframes titlePulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.02); }
    }
    
    .hero-subtitle {
        font-size: 1.4rem;
        color: rgba(255, 255, 255, 0.85);
        position: relative;
        z-index: 2;
        font-weight: 500;
    }
    
    .hero-icon {
        font-size: 5rem;
        color: rgba(255, 255, 255, 0.2);
        position: absolute;
        animation: floatingIcon 4s ease-in-out infinite;
    }
    
    .hero-icon.icon-1 { top: 20%; left: 10%; animation-delay: 0s; }
    .hero-icon.icon-2 { top: 60%; right: 15%; animation-delay: 1s; }
    .hero-icon.icon-3 { bottom: 20%; left: 20%; animation-delay: 2s; }
    
    @keyframes floatingIcon {
        0%, 100% { transform: translateY(0px) rotate(0deg); opacity: 0.2; }
        50% { transform: translateY(-20px) rotate(5deg); opacity: 0.4; }
    }
    
    /* Enhanced Form Styling */
    .premium-form {
        background: var(--glass-bg);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--glass-border);
        border-radius: 24px;
        padding: 2.5rem;
        margin: 2rem 0;
        box-shadow: var(--shadow-lg);
        animation: slideInLeft 0.6s ease-out;
    }
    
    .form-section {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
        transition: all 0.3s ease;
    }
    
    .form-section:hover {
        background: rgba(255, 255, 255, 0.12);
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }
    
    .bounce-section {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(34, 197, 94, 0.1));
        border: 2px solid rgba(16, 185, 129, 0.3);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .bounce-section::before {
        content: '🎯';
        position: absolute;
        top: 1rem;
        right: 1rem;
        font-size: 1.5rem;
        opacity: 0.3;
        animation: pulse 2s infinite;
    }
    
    .rejection-section {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(220, 38, 38, 0.1));
        border: 2px solid rgba(239, 68, 68, 0.3);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .rejection-section::before {
        content: '🚫';
        position: absolute;
        top: 1rem;
        right: 1rem;
        font-size: 1.5rem;
        opacity: 0.3;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 0.3; transform: scale(1); }
        50% { opacity: 0.6; transform: scale(1.1); }
    }
    
    /* Premium Buttons */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%) !important;
        border: none !important;
        border-radius: 16px !important;
        padding: 1rem 2rem !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        color: white !important;
        box-shadow: var(--shadow-md) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        position: relative !important;
        overflow: hidden !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-3px) scale(1.02) !important;
        box-shadow: var(--shadow-xl), 0 0 30px rgba(99, 102, 241, 0.4) !important;
        background: linear-gradient(135deg, var(--primary-light) 0%, var(--secondary) 100%) !important;
    }
    
    .stButton > button::before {
        content: '' !important;
        position: absolute !important;
        top: 0 !important;
        left: -100% !important;
        width: 100% !important;
        height: 100% !important;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent) !important;
        transition: left 0.5s ease !important;
    }
    
    .stButton > button:hover::before {
        left: 100% !important;
    }
    
    /* Enhanced Tables */
    .dataframe {
        background: rgba(255, 255, 255, 0.95) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border-radius: 16px !important;
        overflow: hidden !important;
        box-shadow: var(--shadow-lg) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        animation: tableSlideIn 0.5s ease-out;
    }
    
    @keyframes tableSlideIn {
        0% { opacity: 0; transform: translateY(20px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    
    .dataframe th {
        background: linear-gradient(135deg, var(--primary), var(--primary-light)) !important;
        color: white !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        padding: 1.2rem !important;
        text-align: center !important;
        border: none !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
    }
    
    .dataframe td {
        padding: 1rem !important;
        border-bottom: 1px solid rgba(0, 0, 0, 0.05) !important;
        text-align: center !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    
    .dataframe tr:hover td {
        background: rgba(99, 102, 241, 0.05) !important;
        transform: scale(1.01) !important;
    }
    
    /* Info Boxes with Glassmorphism */
    .premium-info-box {
        background: var(--glass-bg);
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border: 1px solid var(--glass-border);
        border-left: 4px solid var(--primary);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        box-shadow: var(--shadow-md);
        animation: boxSlideIn 0.4s ease-out;
        position: relative;
        overflow: hidden;
    }
    
    .premium-info-box::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--primary), var(--secondary), var(--primary));
        animation: shimmer 2s ease-in-out infinite;
    }
    
    @keyframes shimmer {
        0%, 100% { opacity: 0.5; }
        50% { opacity: 1; }
    }
    
    .premium-success-box {
        background: var(--glass-bg);
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border: 1px solid rgba(16, 185, 129, 0.3);
        border-left: 4px solid var(--success);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        box-shadow: var(--shadow-md);
        animation: successPulse 0.6s ease-out;
    }
    
    @keyframes successPulse {
        0% { opacity: 0; transform: scale(0.95); }
        50% { transform: scale(1.02); }
        100% { opacity: 1; transform: scale(1); }
    }
    
    .premium-warning-box {
        background: var(--glass-bg);
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border: 1px solid rgba(245, 158, 11, 0.3);
        border-left: 4px solid var(--warning);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1.5rem 0;
        box-shadow: var(--shadow-md);
        animation: warningShake 0.5s ease-out;
    }
    
    @keyframes warningShake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-2px); }
        75% { transform: translateX(2px); }
    }
    
    /* Sidebar Enhancements */
    .css-1d391kg {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-right: 1px solid var(--glass-border) !important;
    }
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--glass-bg);
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border-radius: 20px;
        padding: 8px;
        gap: 4px;
        border: 1px solid var(--glass-border);
        box-shadow: var(--shadow-md);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 16px;
        padding: 1rem 2rem;
        transition: all 0.3s ease;
        color: var(--text-secondary);
        font-weight: 500;
        position: relative;
        overflow: hidden;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--primary), var(--primary-light)) !important;
        color: white !important;
        box-shadow: var(--shadow-md);
        transform: scale(1.02);
    }
    
    .stTabs [data-baseweb="tab"]:hover:not([aria-selected="true"]) {
        background: rgba(99, 102, 241, 0.1);
        transform: translateY(-1px);
    }
    
    /* Animations */
    @keyframes slideInUp {
        0% { opacity: 0; transform: translateY(30px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    
    @keyframes slideInLeft {
        0% { opacity: 0; transform: translateX(-30px); }
        100% { opacity: 1; transform: translateX(0); }
    }
    
    @keyframes fadeInScale {
        0% { opacity: 0; transform: scale(0.9); }
        100% { opacity: 1; transform: scale(1); }
    }
    
    @keyframes boxSlideIn {
        0% { opacity: 0; transform: translateY(10px); }
        100% { opacity: 1; transform: translateY(0); }
    }
    
    /* Responsive Design */
    @media (max-width: 768px) {
        .hero-title { font-size: 2.5rem; }
        .metric-glass-card { padding: 1.5rem; }
        .glass-card { padding: 1.5rem; }
        .premium-form { padding: 1.5rem; }
    }
    
    /* Loading Animation */
    .loading-shimmer {
        background: linear-gradient(90deg, 
            rgba(255, 255, 255, 0.1) 0%, 
            rgba(255, 255, 255, 0.3) 50%, 
            rgba(255, 255, 255, 0.1) 100%);
        background-size: 200% 100%;
        animation: shimmerLoad 1.5s infinite;
    }
    
    @keyframes shimmerLoad {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    
    /* Status Indicators */
    .status-indicator {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 0.5rem;
        animation: statusPulse 2s ease-in-out infinite;
    }
    
    .status-active { background: var(--success); box-shadow: 0 0 10px rgba(16, 185, 129, 0.5); }
    .status-inactive { background: var(--text-muted); }
    .status-warning { background: var(--warning); box-shadow: 0 0 10px rgba(245, 158, 11, 0.5); }
    
    @keyframes statusPulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.7; transform: scale(1.1); }
    }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# TIME / BLOCK HELPERS (Same as before)
# ───────────────────────────────────────────────────────────────────────────────
def fmt_ct(dt: datetime) -> datetime:
    if dt.tzinfo is None: return CT.localize(dt)
    return dt.astimezone(CT)

def rth_slots_ct(day: date) -> List[datetime]:
    start = fmt_ct(datetime.combine(day, RTH_START))
    end   = fmt_ct(datetime.combine(day, RTH_END))
    out, cur = [], start
    while cur <= end:
        out.append(cur)
        cur += timedelta(minutes=30)
    return out

def is_maintenance(dt: datetime) -> bool:
    return dt.hour == 16

def in_weekend_gap(dt: datetime) -> bool:
    wd = dt.weekday()
    if wd == 5: return True
    if wd == 6 and dt.hour < 17: return True
    if wd == 4 and dt.hour >= 17: return True
    return False

def count_blocks_spx(t0: datetime, t1: datetime) -> int:
    t0 = fmt_ct(t0); t1 = fmt_ct(t1)
    if t1 <= t0: return 0
    t, blocks = t0, 0
    while t < t1:
        t_next = t + timedelta(minutes=30)
        if not is_maintenance(t_next) and not in_weekend_gap(t_next):
            blocks += 1
        t = t_next
    return blocks

def count_blocks_contract(anchor_day: date, target_dt: datetime) -> int:
    target_dt = fmt_ct(target_dt)
    anchor_3pm   = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    anchor_330pm = fmt_ct(datetime.combine(anchor_day, time(15, 30)))
    anchor_7pm   = fmt_ct(datetime.combine(anchor_day, time(19, 0)))
    if target_dt <= anchor_3pm: return 0
    blocks = 1 if target_dt >= anchor_330pm else 0
    if target_dt > anchor_7pm:
        delta_min = int((target_dt - anchor_7pm).total_seconds() // 60)
        blocks += delta_min // 30
    return blocks

def blocks_simple_30m(d1: datetime, d2: datetime) -> int:
    d1 = fmt_ct(d1); d2 = fmt_ct(d2)
    if d2 <= d1: return 0
    return int((d2 - d1).total_seconds() // (30*60))

def fan_levels_for_slot(anchor_close: float, anchor_time: datetime, slot_dt: datetime) -> Tuple[float,float]:
    blocks = count_blocks_spx(anchor_time, slot_dt)
    top = round(anchor_close + SLOPE_SPX * blocks, 2)
    bot = round(anchor_close - SLOPE_SPX * blocks, 2)
    return top, bot

def sigma_bands_at_830(anchor_close: float, anchor_day: date) -> Tuple[float, float, int]:
    anchor_3pm = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    next_830   = fmt_ct(datetime.combine(anchor_day + timedelta(days=1), time(8, 30)))
    blocks_830 = count_blocks_spx(anchor_3pm, next_830)
    move = SLOPE_SPX * blocks_830
    return round(move, 2), round(2*move, 2), blocks_830

def calculate_rejection_exit(rejection_dt1: datetime, rejection_dt2: datetime, 
                           contract_r1: float, contract_r2: float, target_dt: datetime) -> float:
    if rejection_dt2 <= rejection_dt1:
        return 0.0
    
    rejection_blocks = blocks_simple_30m(rejection_dt1, rejection_dt2)
    if rejection_blocks <= 0:
        return 0.0
    
    rejection_slope = (contract_r2 - contract_r1) / rejection_blocks
    target_blocks = blocks_simple_30m(rejection_dt2, target_dt)
    exit_level = contract_r2 + (rejection_slope * target_blocks)
    
    return round(exit_level, 2)

# ───────────────────────────────────────────────────────────────────────────────
# PREMIUM HERO HEADER
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class='hero-header'>
    <i class="fas fa-chart-line hero-icon icon-1"></i>
    <i class="fas fa-crystal-ball hero-icon icon-2"></i>
    <i class="fas fa-rocket hero-icon icon-3"></i>
    <div class='hero-title'>🔮 SPX Prophet</div>
    <div class='hero-subtitle'>Premium Trading Analytics</div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# PREMIUM SIDEBAR
# ───────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Premium Configuration")
    
    # Enhanced buttons with icons
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("❓ Help", key="help_toggle"):
            st.session_state.show_help = not st.session_state.show_help
    with col2:
        if st.button("🔄 Reset", key="reset_data"):
            st.session_state.bc_result = None
            st.session_state.rejection_result = None
            st.rerun()
    
    if st.session_state.show_help:
        st.markdown("""
        <div class='premium-info-box'>
            <strong><i class="fas fa-lightbulb"></i> Premium Guide:</strong><br>
            • Configure SPX anchor and key levels<br>
            • Use advanced BC Forecast system<br>
            • Monitor glassmorphism analytics<br>
            • Execute with premium trading plan
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Date Configuration with enhanced styling
    st.markdown("#### 📅 Trading Session")
    today_ct = fmt_ct(datetime.now()).date()
    prev_day = st.date_input("Previous Trading Day", value=today_ct - timedelta(days=1))
    proj_day = st.date_input("Projection Day", value=prev_day + timedelta(days=1))
    
    st.markdown("#### 💰 Market Data")
    
    anchor_close = st.number_input(
        "SPX Anchor (≤ 3:00 PM CT Close)", 
        value=float(DEFAULT_ANCHOR), 
        step=0.25, 
        format="%.2f"
    )
    
    contract_3pm = st.number_input(
        "Contract Price @ 3:00 PM", 
        value=float(DEFAULT_CONTRACT_3PM), 
        step=0.05, 
        format="%.2f"
    )
    
    st.markdown("#### 📊 Key Levels")
    
    col1, col2 = st.columns(2)
    with col1:
        pdh = st.number_input("PDH", value=anchor_close + 10.0, step=0.25, format="%.2f")
    with col2:
        pdl = st.number_input("PDL", value=anchor_close - 10.0, step=0.25, format="%.2f")
    
    use_on = st.checkbox("Include Overnight High/Low", value=False)
    
    if use_on:
        col1, col2 = st.columns(2)
        with col1:
            onh = st.number_input("ONH", value=anchor_close + 5.0, step=0.25, format="%.2f")
        with col2:
            onl = st.number_input("ONL", value=anchor_close - 5.0, step=0.25, format="%.2f")
    else:
        onh = anchor_close + 5.0
        onl = anchor_close - 5.0
    
    # Premium Status Section
    st.markdown("---")
    st.markdown("#### 📈 System Status")
    
    current_time = fmt_ct(datetime.now())
    market_status = "🔴 Closed"
    status_class = "status-inactive"
    if RTH_START <= current_time.time() <= RTH_END and current_time.weekday() < 5:
        market_status = "🟢 Open"
        status_class = "status-active"
    elif current_time.time() < RTH_START and current_time.weekday() < 5:
        market_status = "🟡 Pre-Market"
        status_class = "status-warning"
    
    st.markdown(f"<span class='status-indicator {status_class}'></span>**Market:** {market_status}", unsafe_allow_html=True)
    st.markdown(f"**Time:** {current_time.strftime('%H:%M CT')}")
    
    sigma1, sigma2, spx_blocks_to_830 = sigma_bands_at_830(anchor_close, prev_day)
    st.markdown(f"**Blocks to 8:30:** {spx_blocks_to_830}")
    st.markdown(f"**1σ Band:** ±{sigma1:.2f}")

# ───────────────────────────────────────────────────────────────────────────────
# PREMIUM METRIC CARDS WITH LARGE ICONS
# ───────────────────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class='metric-glass-card'>
        <i class="fas fa-anchor metric-icon"></i>
        <div class='metric-label'>SPX Anchor</div>
        <div class='metric-value'>{anchor_close:.2f}</div>
        <div class='metric-sub'>≤ 3:00 PM CT Close</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class='metric-glass-card'>
        <i class="fas fa-wave-square metric-icon"></i>
        <div class='metric-label'>Sigma Bands @ 8:30</div>
        <div class='metric-value'>±{sigma1:.2f} / ±{sigma2:.2f}</div>
        <div class='metric-sub'>{spx_blocks_to_830} blocks @ {SLOPE_SPX:.2f}/30m</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    mag_to_830 = abs(SLOPE_CONTRACT_DEFAULT)*28
    st.markdown(f"""
    <div class='metric-glass-card'>
        <i class="fas fa-chart-area metric-icon"></i>
        <div class='metric-label'>Contract Projection</div>
        <div class='metric-value'>±{mag_to_830:.2f}</div>
        <div class='metric-sub'>28 blocks @ {SLOPE_CONTRACT_DEFAULT:.2f}/30m</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    rejection_status = "✅ Active" if st.session_state.get("rejection_result") else "⚪ Not Set"
    on_text = f"ONH/ONL: {onh:.2f}/{onl:.2f}" if use_on else "Not tracked"
    st.markdown(f"""
    <div class='metric-glass-card'>
        <i class="fas fa-layer-group metric-icon"></i>
        <div class='metric-label'>Key Levels</div>
        <div class='metric-value'>{pdh:.2f} / {pdl:.2f}</div>
        <div class='metric-sub'>{on_text} • Exits: {rejection_status}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# PREMIUM TABS
# ───────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 SPX Anchors", "🎯 BC Forecast", "📋 Trading Plan"])

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 1 — Premium SPX Anchors                                                 ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab1:
    st.markdown("""
    <div class='glass-card'>
        <h2><i class="fas fa-crosshairs"></i> SPX Anchor Levels - Premium Entry/Exit System</h2>
        <p>Real-time glassmorphism analytics for 30-minute intervals from 8:30 AM to 2:30 PM CT</p>
    </div>
    """, unsafe_allow_html=True)
    
    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))

    bc = st.session_state.get("bc_result", None)
    rejection_result = st.session_state.get("rejection_result", None)
    
    contract_slope = SLOPE_CONTRACT_DEFAULT
    contract_ref_dt = fmt_ct(datetime.combine(prev_day, time(15, 0)))
    contract_ref_px = float(contract_3pm)
    
    if bc and "contract" in bc:
        contract_slope = float(bc["contract"]["slope"])
        contract_ref_dt = bc["contract"]["ref_dt"]
        contract_ref_px = float(bc["contract"]["ref_price"])
        
        status_msg = "✅ BC Forecast Active"
        if rejection_result:
            status_msg += " + Exit Projections Enabled"
        
        st.markdown(f"""
        <div class='premium-success-box'>
            <strong><i class="fas fa-check-circle"></i> {status_msg}</strong><br>
            Advanced projections below include BC-fitted slopes and rejection-based exit levels.
        </div>
        """, unsafe_allow_html=True)

    def contract_proj_for_slot(slot_dt: datetime) -> float:
        dt_830 = fmt_ct(datetime.combine(proj_day, time(8,30)))
        if contract_ref_dt.time() == time(15,0) and contract_ref_dt.date() == prev_day:
            base_blocks = count_blocks_contract(prev_day, min(slot_dt, dt_830))
            if slot_dt <= dt_830:
                total_blocks = base_blocks
            else:
                total_blocks = base_blocks + blocks_simple_30m(dt_830, slot_dt)
        else:
            total_blocks = blocks_simple_30m(contract_ref_dt, slot_dt)
        return round(contract_ref_px + contract_slope * total_blocks, 2)

    # Build enhanced tables
    rows_close = []
    key_times = ["08:30", "10:00", "12:00", "13:30", "14:30"]
    
    for slot in rth_slots_ct(proj_day):
        tlabel = slot.strftime("%H:%M")
        top, bot = fan_levels_for_slot(anchor_close, anchor_time, slot)
        is_key = tlabel in key_times
        
        spx_proj_val = ""
        if bc and "table" in bc:
            try:
                spx_proj_val = float(bc["table"].loc[bc["table"]["Time"]==tlabel, "SPX Entry"].iloc[0])
            except Exception:
                spx_proj_val = ""

        c_proj = contract_proj_for_slot(slot)
        
        c_exit = ""
        if rejection_result:
            c_exit_val = calculate_rejection_exit(
                rejection_result['r1_dt'], rejection_result['r2_dt'],
                rejection_result['c_r1'], rejection_result['c_r2'], slot
            )
            if c_exit_val:
                c_exit = f"{c_exit_val:.2f}"
        
        entry_exit_spread = ""
        if c_exit and c_exit != "":
            try:
                spread = c_proj - float(c_exit)
                entry_exit_spread = f"{spread:.2f}"
            except:
                entry_exit_spread = "—"
        
        rows_close.append({
            "🎯": "🎯" if is_key else ("⭐" if tlabel=="08:30" else ""),
            "Time": tlabel,
            "Top Level": f"{top:.2f}",
            "Bottom Level": f"{bot:.2f}",
            "SPX Entry": f"{spx_proj_val:.2f}" if spx_proj_val else "—",
            "Contract Entry": f"{c_proj:.2f}",
            "Contract Exit": c_exit if c_exit else "—",
            "Profit Spread": entry_exit_spread if entry_exit_spread else "—",
            "Range Width": f"{top - bot:.2f}"
        })

    st.markdown("### 📈 Complete Premium Projections")
    df_close = pd.DataFrame(rows_close)
    st.dataframe(df_close, use_container_width=True, hide_index=True)
    
    # Premium analytics section
    st.markdown("""
    <div class='glass-card'>
        <h3><i class="fas fa-analytics"></i> Premium Analytics Dashboard</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        morning_range = fan_levels_for_slot(anchor_close, anchor_time, fmt_ct(datetime.combine(proj_day, time(8, 30))))
        morning_width = morning_range[0] - morning_range[1]
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-sun metric-icon"></i>
            <div class='metric-label'>Morning Range</div>
            <div class='metric-value'>{morning_width:.2f}</div>
            <div class='metric-sub'>8:30 AM Width</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        close_range = fan_levels_for_slot(anchor_close, anchor_time, fmt_ct(datetime.combine(proj_day, time(14, 30))))
        close_width = close_range[0] - close_range[1]
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-moon metric-icon"></i>
            <div class='metric-label'>Close Range</div>
            <div class='metric-value'>{close_width:.2f}</div>
            <div class='metric-sub'>2:30 PM Width</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        expansion = close_width - morning_width
        if morning_width > 0:
            expansion_pct = f"{(expansion/morning_width)*100:.1f}%"
        else:
            expansion_pct = "N/A"
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-expand-arrows-alt metric-icon"></i>
            <div class='metric-label'>Range Expansion</div>
            <div class='metric-value'>{expansion:.2f}</div>
            <div class='metric-sub'>{expansion_pct}</div>
        </div>
        """, unsafe_allow_html=True)

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 2 — Premium BC Forecast                                                 ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab2:
    st.markdown("""
    <div class='glass-card'>
        <h2><i class="fas fa-magic"></i> Advanced BC Forecast - Premium Entry/Exit System</h2>
        <p>Configure sophisticated bounce-rejection pairs with glassmorphism interface</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='premium-info-box'>
        <strong><i class="fas fa-lightbulb"></i> Premium Trading System:</strong><br>
        • Configure elegant bounce-rejection pairs for complete projections<br>
        • Advanced glassmorphism interface with smooth animations<br>
        • Real-time calculations with premium visual feedback<br>
        • Time window: 3:30 PM (previous day) → 8:00 AM (projection day)
    </div>
    """, unsafe_allow_html=True)

    # Build time slots
    start_bounces = fmt_ct(datetime.combine(prev_day, time(15, 30)))
    end_bounces   = fmt_ct(datetime.combine(proj_day, time(8, 0)))
    tmp_slots, cur = [], start_bounces
    while cur <= end_bounces:
        tmp_slots.append(cur)
        cur += timedelta(minutes=30)
    
    bounce_slots = [dt.strftime("%Y-%m-%d %H:%M") for dt in tmp_slots]
    bounce_display = [f"{dt.strftime('%a %m/%d %H:%M')} CT" for dt in tmp_slots]

    # Premium form with glassmorphism
    with st.form("premium_bc_form", clear_on_submit=False):
        
        st.markdown("""
        <div class='premium-form'>
            <h3><i class="fas fa-cogs"></i> Premium Bounce-Rejection Configuration</h3>
            <p>Set up sophisticated trading pairs with advanced analytics</p>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        # LEFT COLUMN: First Pair
        with col1:
            st.markdown("""
            <div class='glass-card'>
                <h4><i class="fas fa-play-circle"></i> First Bounce-Rejection Pair</h4>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class='bounce-section'>
                <h5><i class="fas fa-arrow-up"></i> First Bounce (Entry)</h5>
            </div>
            """, unsafe_allow_html=True)
            
            b1_idx = st.selectbox(
                "Time Slot", 
                range(len(bounce_slots)), 
                format_func=lambda x: bounce_display[x], 
                index=0, 
                key="bc_b1"
            )
            col_b1_1, col_b1_2 = st.columns(2)
            with col_b1_1:
                spx_b1 = st.number_input("SPX Price", value=anchor_close, step=0.25, format="%.2f", key="spx_b1")
            with col_b1_2:
                c_b1 = st.number_input("Contract Price", value=contract_3pm, step=0.05, format="%.2f", key="c_b1")
            
            st.markdown("""
            <div class='rejection-section'>
                <h5><i class="fas fa-times-circle"></i> First Rejection (Exit)</h5>
            </div>
            """, unsafe_allow_html=True)
            
            r1_idx = st.selectbox(
                "Time Slot", 
                range(len(bounce_slots)), 
                format_func=lambda x: bounce_display[x], 
                index=min(5, len(bounce_slots)-1), 
                key="rej_r1"
            )
            col_r1_1, col_r1_2 = st.columns(2)
            with col_r1_1:
                spx_r1 = st.number_input("SPX Price", value=anchor_close + 5.0, step=0.25, format="%.2f", key="spx_r1")
            with col_r1_2:
                c_r1 = st.number_input("Contract Price", value=contract_3pm + 2.0, step=0.05, format="%.2f", key="c_r1")
            
            st.markdown("</div>", unsafe_allow_html=True)
            
        # RIGHT COLUMN: Second Pair    
        with col2:
            st.markdown("""
            <div class='glass-card'>
                <h4><i class="fas fa-forward"></i> Second Bounce-Rejection Pair</h4>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class='bounce-section'>
                <h5><i class="fas fa-arrow-up"></i> Second Bounce (Entry)</h5>
            </div>
            """, unsafe_allow_html=True)
            
            default_b2 = min(10, len(bounce_slots)-1)
            b2_idx = st.selectbox(
                "Time Slot", 
                range(len(bounce_slots)), 
                format_func=lambda x: bounce_display[x], 
                index=default_b2, 
                key="bc_b2"
            )
            col_b2_1, col_b2_2 = st.columns(2)
            with col_b2_1:
                spx_b2 = st.number_input("SPX Price", value=anchor_close, step=0.25, format="%.2f", key="spx_b2")
            with col_b2_2:
                c_b2 = st.number_input("Contract Price", value=contract_3pm, step=0.05, format="%.2f", key="c_b2")
            
            st.markdown("""
            <div class='rejection-section'>
                <h5><i class="fas fa-times-circle"></i> Second Rejection (Exit)</h5>
            </div>
            """, unsafe_allow_html=True)
            
            r2_idx = st.selectbox(
                "Time Slot", 
                range(len(bounce_slots)), 
                format_func=lambda x: bounce_display[x], 
                index=min(15, len(bounce_slots)-1), 
                key="rej_r2"
            )
            col_r2_1, col_r2_2 = st.columns(2)
            with col_r2_1:
                spx_r2 = st.number_input("SPX Price", value=anchor_close + 7.0, step=0.25, format="%.2f", key="spx_r2")
            with col_r2_2:
                c_r2 = st.number_input("Contract Price", value=contract_3pm + 3.0, step=0.05, format="%.2f", key="c_r2")
            
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
        
        skip_rejections = st.checkbox("Skip rejection calculations (entries only)", value=False)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submitted = st.form_submit_button("🚀 Generate Premium Forecast")

    if submitted:
        # Show loading animation
        with st.spinner("🔮 Calculating Premium Entry/Exit Forecast..."):
            try:
                b1_dt = fmt_ct(datetime.strptime(bounce_slots[b1_idx], "%Y-%m-%d %H:%M"))
                b2_dt = fmt_ct(datetime.strptime(bounce_slots[b2_idx], "%Y-%m-%d %H:%M"))
                
                if b2_dt <= b1_dt:
                    st.markdown("""
                    <div class='premium-warning-box'>
                        <strong><i class="fas fa-exclamation-triangle"></i> Configuration Error</strong><br>
                        Second bounce must occur after first bounce.
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # Calculate slopes
                    spx_blocks = count_blocks_spx(b1_dt, b2_dt)
                    if spx_blocks <= 0:
                        st.markdown("""
                        <div class='premium-warning-box'>
                            <strong><i class="fas fa-exclamation-triangle"></i> Timing Error</strong><br>
                            Bounces must be at least 30 minutes apart with valid blocks.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        spx_slope = (float(spx_b2) - float(spx_b1)) / spx_blocks
                        
                        bounce_blocks = blocks_simple_30m(b1_dt, b2_dt)
                        contract_slope = SLOPE_CONTRACT_DEFAULT
                        if bounce_blocks > 0 and (c_b2 != c_b1):
                            contract_slope = float((float(c_b2) - float(c_b1)) / bounce_blocks)

                        # Calculate rejections
                        rejection_data = None
                        if not skip_rejections:
                            try:
                                r1_dt = fmt_ct(datetime.strptime(bounce_slots[r1_idx], "%Y-%m-%d %H:%M"))
                                r2_dt = fmt_ct(datetime.strptime(bounce_slots[r2_idx], "%Y-%m-%d %H:%M"))
                                
                                if r2_dt > r1_dt:
                                    rejection_blocks = blocks_simple_30m(r1_dt, r2_dt)
                                    if rejection_blocks > 0:
                                        spx_rej_slope = (float(spx_r2) - float(spx_r1)) / rejection_blocks
                                        contract_rej_slope = (float(c_r2) - float(c_r1)) / rejection_blocks if c_r2 != c_r1 else 0
                                        
                                        rejection_data = {
                                            'r1_dt': r1_dt, 'r2_dt': r2_dt,
                                            'spx_r1': float(spx_r1), 'spx_r2': float(spx_r2),
                                            'c_r1': float(c_r1), 'c_r2': float(c_r2),
                                            'spx_rej_slope': spx_rej_slope,
                                            'contract_rej_slope': contract_rej_slope
                                        }
                            except Exception as e:
                                st.markdown(f"""
                                <div class='premium-warning-box'>
                                    <strong><i class="fas fa-exclamation-triangle"></i> Rejection Warning</strong><br>
                                    {e}. Entry projections will proceed.
                                </div>
                                """, unsafe_allow_html=True)

                        # Build projection table
                        rows = []
                        anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
                        
                        for slot in rth_slots_ct(proj_day):
                            top, bot = fan_levels_for_slot(anchor_close, anchor_time, slot)
                            spx_proj = round(float(spx_b2) + spx_slope * count_blocks_spx(b2_dt, slot), 2)
                            blocks_from_b2 = blocks_simple_30m(b2_dt, slot)
                            c_proj = round(float(c_b2) + contract_slope * blocks_from_b2, 2)
                            
                            c_exit = ""
                            spx_exit = ""
                            entry_exit_spread = ""
                            
                            if rejection_data:
                                c_exit_val = calculate_rejection_exit(
                                    rejection_data['r1_dt'], rejection_data['r2_dt'],
                                    rejection_data['c_r1'], rejection_data['c_r2'], slot
                                )
                                if c_exit_val:
                                    c_exit = f"{c_exit_val:.2f}"
                                    entry_exit_spread = f"{c_proj - c_exit_val:.2f}"
                                
                                exit_blocks = blocks_simple_30m(rejection_data['r2_dt'], slot)
                                spx_exit = round(rejection_data['spx_r2'] + rejection_data['spx_rej_slope'] * exit_blocks, 2)
                            
                            rows.append({
                                "🎯": "🎯" if slot.strftime("%H:%M") in ["08:30", "10:00", "12:00", "14:30"] else "",
                                "Time": slot.strftime("%H:%M"),
                                "Top": top, 
                                "Bottom": bot,
                                "SPX Entry": spx_proj,
                                "Contract Entry": c_proj,
                                "SPX Exit": spx_exit if spx_exit else "—",
                                "Contract Exit": c_exit if c_exit else "—",
                                "Entry/Exit Spread": entry_exit_spread if entry_exit_spread else "—"
                            })
                        
                        out_df = pd.DataFrame(rows)
                        
                        # Success message
                        success_msg = "🎉 Premium Entry/Exit Forecast Generated!"
                        if rejection_data:
                            success_msg += " Complete entry and exit projections calculated."
                        else:
                            success_msg += " Entry projections calculated."
                        
                        st.markdown(f"""
                        <div class='premium-success-box'>
                            <strong><i class="fas fa-check-circle"></i> {success_msg}</strong><br>
                            Review your premium glassmorphism projections below.
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Premium metrics display
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.markdown(f"""
                            <div class='metric-glass-card'>
                                <i class="fas fa-chart-line metric-icon"></i>
                                <div class='metric-label'>SPX Entry Slope</div>
                                <div class='metric-value'>{spx_slope:.3f}</div>
                                <div class='metric-sub'>per 30m block</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            st.markdown(f"""
                            <div class='metric-glass-card'>
                                <i class="fas fa-coins metric-icon"></i>
                                <div class='metric-label'>Contract Entry</div>
                                <div class='metric-value'>{contract_slope:.3f}</div>
                                <div class='metric-sub'>per 30m block</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col3:
                            if rejection_data:
                                st.markdown(f"""
                                <div class='metric-glass-card'>
                                    <i class="fas fa-chart-line-down metric-icon"></i>
                                    <div class='metric-label'>SPX Exit Slope</div>
                                    <div class='metric-value'>{rejection_data['spx_rej_slope']:.3f}</div>
                                    <div class='metric-sub'>per 30m block</div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div class='metric-glass-card'>
                                    <i class="fas fa-question-circle metric-icon"></i>
                                    <div class='metric-label'>SPX Exit Slope</div>
                                    <div class='metric-value'>—</div>
                                    <div class='metric-sub'>Not configured</div>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        with col4:
                            if rejection_data:
                                st.markdown(f"""
                                <div class='metric-glass-card'>
                                    <i class="fas fa-coins metric-icon"></i>
                                    <div class='metric-label'>Contract Exit</div>
                                    <div class='metric-value'>{rejection_data['contract_rej_slope']:.3f}</div>
                                    <div class='metric-sub'>per 30m block</div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div class='metric-glass-card'>
                                    <i class="fas fa-question-circle metric-icon"></i>
                                    <div class='metric-label'>Contract Exit</div>
                                    <div class='metric-value'>—</div>
                                    <div class='metric-sub'>Not configured</div>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        # Main table
                        st.markdown("### 📊 Premium RTH Projections")
                        st.dataframe(out_df, use_container_width=True, hide_index=True)
                        
                        # Store results
                        st.session_state["bc_result"] = {
                            "table": out_df,
                            "spx_slope": spx_slope,
                            "b2_dt": b2_dt,
                            "spx_b2": float(spx_b2),
                            "contract": {"slope": contract_slope, "ref_price": float(c_b2), "ref_dt": b2_dt},
                        }
                        
                        if rejection_data:
                            st.session_state["rejection_result"] = rejection_data
                        else:
                            st.session_state["rejection_result"] = None
                        
                        st.markdown("""
                        <div class='premium-success-box'>
                            <strong><i class="fas fa-sync-alt"></i> System Updated!</strong><br>
                            Check other tabs for enhanced projections with your premium data.
                        </div>
                        """, unsafe_allow_html=True)

            except Exception as e:
                st.markdown(f"""
                <div class='premium-warning-box'>
                    <strong><i class="fas fa-exclamation-triangle"></i> Generation Failed</strong><br>
                    {e}
                </div>
                """, unsafe_allow_html=True)

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 3 — Premium Trading Plan                                                ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab3:
    st.markdown("""
    <div class='glass-card'>
        <h2><i class="fas fa-chess"></i> Premium Trading Plan - Complete Strategy</h2>
        <p>Your advanced glassmorphism trading dashboard ready by 8:00 AM</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Status check with premium styling
    current_ct = fmt_ct(datetime.now())
    plan_ready_time = fmt_ct(datetime.combine(proj_day, time(8, 0)))
    
    if current_ct >= plan_ready_time:
        status_msg = "🟢 Plan Active - Ready for premium trading"
        status_class = "premium-success-box"
    elif current_ct >= plan_ready_time - timedelta(hours=1):
        status_msg = "🟡 Plan Preparation - Final premium setup"
        status_class = "premium-warning-box"
    else:
        status_msg = "🔵 Plan Preview - Premium configuration in progress"
        status_class = "premium-info-box"
    
    st.markdown(f"""
    <div class='{status_class}'>
        <strong><i class="fas fa-info-circle"></i> {status_msg}</strong>
    </div>
    """, unsafe_allow_html=True)

    # Calculate key levels
    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
    slot_830    = fmt_ct(datetime.combine(proj_day, time(8, 30)))
    top_830, bot_830 = fan_levels_for_slot(anchor_close, anchor_time, slot_830)

    bc = st.session_state.get("bc_result", None)

    # Premium strategy cards
    col1, col2 = st.columns(2)
    
    with col1:
        on_display = f"<br>ONH/ONL: {onh:.2f} / {onl:.2f}" if use_on else ""
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-foundation metric-icon"></i>
            <div class='metric-label'>Market Foundation</div>
            <div class='metric-value'>{anchor_close:.2f}</div>
            <div class='metric-sub'>
                8:30 Fan: {top_830:.2f} (top) • {bot_830:.2f} (bottom)<br>
                Bands: ±{sigma1:.2f} (1σ) • ±{sigma2:.2f} (2σ)<br>
                PDH/PDL: {pdh:.2f} / {pdl:.2f}{on_display}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if bc and "contract" in bc:
            c_slope = float(bc["contract"]["slope"])
            c_ref_dt = bc["contract"]["ref_dt"]
            c_ref_px = float(bc["contract"]["ref_price"])
            blocks = blocks_simple_30m(c_ref_dt, slot_830)
            c_830 = round(c_ref_px + c_slope * blocks, 2)
            slope_used = c_slope
            source = "BC-fitted"
        else:
            c_830 = round(float(contract_3pm) + SLOPE_CONTRACT_DEFAULT * 28, 2)
            slope_used = SLOPE_CONTRACT_DEFAULT
            source = "default"

        slope_direction = "📈 Ascending" if slope_used > 0 else "📉 Descending"
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-file-contract metric-icon"></i>
            <div class='metric-label'>Contract Analysis</div>
            <div class='metric-value'>{float(contract_3pm):.2f} → {c_830:.2f}</div>
            <div class='metric-sub'>
                Slope: {slope_used:.3f}/30m ({source})<br>
                Direction: {slope_direction}<br>
                Change: {c_830 - float(contract_3pm):.2f}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Premium action levels
    col1, col2 = st.columns(2)
    
    with col1:
        sell_level = max(top_830, pdh, onh if use_on else 0)
        buy_level = min(bot_830, pdl, onl if use_on else float('inf'))
        
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-bullseye metric-icon"></i>
            <div class='metric-label'>Premium Action Levels</div>
            <div class='metric-value' style='font-size: 1.4rem;'>
                Sell: {sell_level:.2f}<br>
                Buy: {buy_level:.2f}
            </div>
            <div class='metric-sub'>
                Stop: 2-3 points beyond<br>
                Target: Opposite edge<br>
                Stretch: PDH/PDL if closer
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        range_width = sell_level - buy_level
        suggested_stop = round(range_width * 0.15, 2)
        
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-shield-alt metric-icon"></i>
            <div class='metric-label'>Risk Management</div>
            <div class='metric-value' style='font-size: 1.4rem;'>
                Range: {range_width:.2f}<br>
                Stop: {suggested_stop:.2f}
            </div>
            <div class='metric-sub'>
                Size: Based on stop<br>
                Max Risk: 1-2% account<br>
                Avoid: 11:30-12:30 chop
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Premium projections table
    st.markdown("""
    <div class='glass-card'>
        <h3><i class="fas fa-clock"></i> Premium Time Projections</h3>
    </div>
    """, unsafe_allow_html=True)
    
    key_times = ["08:30", "09:00", "10:00", "11:00", "12:00", "13:00", "13:30", "14:30"]
    proj_rows = []
    
    bc = st.session_state.get("bc_result", None)
    rejection_result = st.session_state.get("rejection_result", None)
    
    for time_str in key_times:
        slot_time = fmt_ct(datetime.combine(proj_day, datetime.strptime(time_str, "%H:%M").time()))
        top, bot = fan_levels_for_slot(anchor_close, anchor_time, slot_time)
        
        spx_entry = contract_entry = contract_exit = entry_exit_spread = ""
        
        if bc and "table" in bc:
            try:
                bc_row = bc["table"][bc["table"]["Time"] == time_str]
                if not bc_row.empty:
                    spx_entry = f"{float(bc_row.iloc[0]['SPX Entry']):.2f}"
                    contract_entry = f"{float(bc_row.iloc[0]['Contract Entry']):.2f}"
                    
                    exit_val = bc_row.iloc[0]['Contract Exit']
                    if exit_val != "—" and exit_val:
                        contract_exit = f"{float(exit_val):.2f}"
                    
                    spread_val = bc_row.iloc[0]['Entry/Exit Spread']
                    if spread_val != "—" and spread_val:
                        entry_exit_spread = spread_val
            except:
                pass
        
        hour = int(time_str.split(":")[0])
        if hour == 8:
            session_context = "🚀 Open"
        elif 9 <= hour <= 10:
            session_context = "📈 Morning"
        elif 11 <= hour <= 12:
            session_context = "😴 Lunch"
        elif 13 <= hour <= 14:
            session_context = "🏁 Close"
        else:
            session_context = "📊 Active"
        
        proj_rows.append({
            "Time": time_str,
            "Session": session_context,
            "Top": f"{top:.2f}",
            "Bottom": f"{bot:.2f}",
            "SPX Entry": spx_entry or "—",
            "Contract Entry": contract_entry or "—",
            "Contract Exit": contract_exit or "—",
            "Profit Spread": entry_exit_spread or "—"
        })
    
    df_plan = pd.DataFrame(proj_rows)
    st.dataframe(df_plan, use_container_width=True, hide_index=True)
    
    # Premium trading guide
    st.markdown("""
    <div class='glass-card'>
        <h3><i class="fas fa-graduation-cap"></i> Premium Trading Guide</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-sign-in-alt metric-icon"></i>
            <div class='metric-label'>Entry Excellence</div>
            <div class='metric-sub' style='margin-top: 0;'>
                • Wait for premium levels<br>
                • Confirm with volume<br>
                • Enter on pullbacks<br>
                • Use limit orders<br>
                • Size based on stops
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        exit_status = "Available" if st.session_state.get("rejection_result") else "Configure rejections"
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-sign-out-alt metric-icon"></i>
            <div class='metric-label'>Exit Mastery</div>
            <div class='metric-sub' style='margin-top: 0;'>
                • Monitor exit projections<br>
                • Use rejection touches<br>
                • Scale at resistance<br>
                • Status: {exit_status}<br>
                • Trail trending moves
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-clock metric-icon"></i>
            <div class='metric-label'>Timing Precision</div>
            <div class='metric-sub' style='margin-top: 0;'>
                • Best: 8:30-9:30, 13:00-14:30<br>
                • Avoid: 11:30-12:30 lunch<br>
                • Maximum: 3 trades/session<br>
                • Review after close<br>
                • Plan next session
            </div>
        </div>
        """, unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# PREMIUM FOOTER
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(f"""
<div class='glass-card' style='text-align: center; padding: 2rem;'>
    <h4><i class="fas fa-gem"></i> SPX Prophet Premium v3.0</h4>
    <p style='margin: 0; opacity: 0.8;'>
        Glassmorphism Trading Analytics • Last Updated: {fmt_ct(datetime.now()).strftime('%H:%M CT')}
    </p>
</div>
""", unsafe_allow_html=True)