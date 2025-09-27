# app.py
# ═══════════════════════════════════════════════════════════════════════════════
# 🔮 SPX PROPHET — Premium Glassmorphism Edition
# Ultra-modern UI with advanced animations, glassmorphism, and stunning visuals
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import pytz
import yfinance as yf
from datetime import datetime, date, time, timedelta
from typing import List, Tuple

# ───────────────────────────────────────────────────────────────────────────────
# CONFIG & PAGE SETUP
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SPX Prophet - Professional Trading Analytics", 
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
if 'manual_data' not in st.session_state:
    st.session_state.manual_data = {}

CT = pytz.timezone("America/Chicago")

SLOPE_SPX = 0.25                 # SPX slope per 30-minute block
SLOPE_CONTRACT_DEFAULT = -0.33   

RTH_START = time(8, 30)
RTH_END   = time(14, 30)

DEFAULT_ANCHOR = 6400.00
DEFAULT_CONTRACT_3PM = 20.00

# ───────────────────────────────────────────────────────────────────────────────
# YAHOO FINANCE DATA FETCHING
# ───────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_spx_data(target_date):
    """Fetch SPX high, low, close for given date"""
    try:
        # Convert date to string format for yfinance
        start_date = target_date
        end_date = target_date + timedelta(days=1)
        
        ticker = yf.Ticker("^GSPC")
        data = ticker.history(start=start_date, end=end_date)
        
        if not data.empty:
            return {
                'high': round(float(data['High'].iloc[0]), 2),
                'low': round(float(data['Low'].iloc[0]), 2),
                'close': round(float(data['Close'].iloc[0]), 2)
            }
        else:
            return None
    except Exception as e:
        st.error(f"Error fetching Yahoo Finance data: {e}")
        return None

# ───────────────────────────────────────────────────────────────────────────────
# PREMIUM GLASSMORPHISM STYLING (Same as before but removed sigma band references)
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
        font-size: 2rem;
        background: linear-gradient(135deg, var(--primary), var(--secondary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.8rem;
        display: block;
        text-align: center;
        animation: iconFloat 3s ease-in-out infinite;
    }
    
    @keyframes iconFloat {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-5px); }
    }
    
    .metric-value {
        font-size: 1.6rem;
        font-weight: 800;
        color: var(--text-primary);
        text-align: center;
        margin: 0.8rem 0;
        background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: textGlow 2s ease-in-out infinite alternate;
        line-height: 1.2;
    }
    
    @keyframes textGlow {
        from { opacity: 0.8; }
        to { opacity: 1; }
    }
    
    .metric-label {
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        text-align: center;
        margin-bottom: 0.4rem;
    }
    
    .metric-sub {
        font-size: 0.7rem;
        color: var(--text-muted);
        text-align: center;
        line-height: 1.4;
        margin-top: 0.8rem;
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
        font-size: 3rem;
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
        .hero-title { font-size: 2rem; }
        .hero-subtitle { font-size: 1.1rem; }
        .metric-glass-card { 
            padding: 1.2rem; 
            margin: 0.5rem 0;
        }
        .metric-icon { font-size: 1.5rem; }
        .metric-value { font-size: 1.3rem; }
        .metric-label { font-size: 0.7rem; }
        .metric-sub { font-size: 0.65rem; }
        .glass-card { padding: 1.2rem; }
        .premium-form { padding: 1.2rem; }
    }
    
    @media (max-width: 480px) {
        .hero-title { font-size: 1.8rem; }
        .hero-subtitle { font-size: 1rem; }
        .metric-glass-card { 
            padding: 1rem; 
            margin: 0.4rem 0;
        }
        .metric-icon { font-size: 1.3rem; }
        .metric-value { 
            font-size: 1.1rem; 
            line-height: 1.1;
        }
        .metric-label { font-size: 0.65rem; }
        .metric-sub { 
            font-size: 0.6rem; 
            line-height: 1.3;
        }
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
# TIME / BLOCK HELPERS (Updated slopes and calculations)
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
    top = round(anchor_close + SLOPE_SPX * blocks, 2)  # Now uses 0.26
    bot = round(anchor_close - SLOPE_SPX * blocks, 2)  # Now uses 0.26
    return top, bot

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
    <div class='hero-subtitle'>Professional Trading Analytics & Strategy Platform</div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# PREMIUM SIDEBAR
# ───────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    # Enhanced buttons with icons
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("❓ Help", key="help_toggle"):
            st.session_state.show_help = not st.session_state.show_help
    with col2:
        if st.button("🔄 Reset", key="reset_data"):
            st.session_state.bc_result = None
            st.session_state.rejection_result = None
            st.session_state.manual_data = {}
            st.rerun()
    
    if st.session_state.show_help:
        st.markdown("""
        <div class='premium-info-box'>
            <strong><i class="fas fa-lightbulb"></i> Quick Guide:</strong><br>
            • Configure SPX high/low/close data<br>
            • Use advanced BC Forecast system<br>
            • Monitor real-time analytics<br>
            • Execute with comprehensive trading plan
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Date Configuration with enhanced styling
    st.markdown("#### 📅 Trading Session")
    today_ct = fmt_ct(datetime.now()).date()
    prev_day = st.date_input("Previous Trading Day", value=today_ct - timedelta(days=1))
    proj_day = st.date_input("Projection Day", value=prev_day + timedelta(days=1))
    
    st.markdown("#### 💰 Market Data Source")
    
    # Data source selection
    data_source = st.radio(
        "Data Source",
        ["Auto-fetch from Yahoo Finance", "Manual Input"],
        index=0
    )
    
    # Fetch or get manual data
    spx_data = None
    if data_source == "Auto-fetch from Yahoo Finance":
        with st.spinner("Fetching SPX data..."):
            spx_data = fetch_spx_data(prev_day)
        
        if spx_data:
            st.success(f"✅ Data fetched for {prev_day}")
            st.markdown(f"**High:** {spx_data['high']:.2f}")
            st.markdown(f"**Low:** {spx_data['low']:.2f}")
            st.markdown(f"**Close:** {spx_data['close']:.2f}")
        else:
            st.warning("⚠️ Could not fetch data - use manual input")
            data_source = "Manual Input"
    
    if data_source == "Manual Input" or spx_data is None:
        st.markdown("#### 📊 Manual SPX Data Entry")
        spx_high = st.number_input("SPX High", value=DEFAULT_ANCHOR + 15.0, step=0.25, format="%.2f")
        spx_low = st.number_input("SPX Low", value=DEFAULT_ANCHOR - 15.0, step=0.25, format="%.2f")
        spx_close = st.number_input("SPX Close", value=DEFAULT_ANCHOR, step=0.25, format="%.2f")
        
        spx_data = {
            'high': spx_high,
            'low': spx_low,
            'close': spx_close
        }
    
    contract_3pm = st.number_input(
        "Contract Price @ 3:00 PM", 
        value=float(DEFAULT_CONTRACT_3PM), 
        step=0.05, 
        format="%.2f"
    )
    
    # Status information
    st.markdown("---")
    st.markdown("#### 📈 Market Status")
    
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
    st.markdown(f"**Slope:** {SLOPE_SPX:.2f} per 30min block")

# ───────────────────────────────────────────────────────────────────────────────
# PREMIUM METRIC CARDS WITH LARGE ICONS (Updated without sigma bands)
# ───────────────────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class='metric-glass-card'>
        <i class="fas fa-arrow-up metric-icon"></i>
        <div class='metric-label'>SPX High</div>
        <div class='metric-value'>{spx_data['high']:.2f}</div>
        <div class='metric-sub'>Daily High Level</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class='metric-glass-card'>
        <i class="fas fa-arrow-down metric-icon"></i>
        <div class='metric-label'>SPX Low</div>
        <div class='metric-value'>{spx_data['low']:.2f}</div>
        <div class='metric-sub'>Daily Low Level</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class='metric-glass-card'>
        <i class="fas fa-chart-line metric-icon"></i>
        <div class='metric-label'>SPX Close</div>
        <div class='metric-value'>{spx_data['close']:.2f}</div>
        <div class='metric-sub'>Settlement Price</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    daily_range = spx_data['high'] - spx_data['low']
    st.markdown(f"""
    <div class='metric-glass-card'>
        <i class="fas fa-expand-arrows-alt metric-icon"></i>
        <div class='metric-label'>Daily Range</div>
        <div class='metric-value'>{daily_range:.2f}</div>
        <div class='metric-sub'>High - Low</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# PREMIUM TABS
# ───────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 SPX Fan Levels", "🎯 BC Forecast", "📋 Trading Plan"])

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 1 — Premium SPX Fan Levels (3 Tables: High, Low, Close)                ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab1:
    st.markdown("""
    <div class='glass-card'>
        <h2><i class="fas fa-layer-group"></i> SPX Fan Levels - High, Low, Close Analysis</h2>
        <p>Three separate fan projections based on daily high, low, and close levels</p>
    </div>
    """, unsafe_allow_html=True)
    
    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
    
    def build_fan_table(anchor_value: float, anchor_name: str) -> pd.DataFrame:
        """Build fan level table for given anchor value"""
        rows = []
        key_times = ["08:30", "10:00", "12:00", "13:30", "14:30"]
        
        for slot in rth_slots_ct(proj_day):
            tlabel = slot.strftime("%H:%M")
            top, bot = fan_levels_for_slot(anchor_value, anchor_time, slot)
            is_key = tlabel in key_times
            
            rows.append({
                "🎯": "🎯" if is_key else ("⭐" if tlabel=="08:30" else ""),
                "Time": tlabel,
                "Top Level": f"{top:.2f}",
                "Bottom Level": f"{bot:.2f}",
                "Range": f"{top - bot:.2f}"
            })
        
        return pd.DataFrame(rows)
    
    # Create three tables
    high_table = build_fan_table(spx_data['high'], "High")
    low_table = build_fan_table(spx_data['low'], "Low")
    close_table = build_fan_table(spx_data['close'], "Close")
    
    # Display tables in tabs for better organization
    subtab1, subtab2, subtab3 = st.tabs([f"High Fan ({spx_data['high']:.2f})", 
                                        f"Low Fan ({spx_data['low']:.2f})", 
                                        f"Close Fan ({spx_data['close']:.2f})"])
    
    with subtab1:
        st.markdown("### 📈 High-Based Fan Levels")
        st.markdown(f"""
        <div class='premium-info-box'>
            <strong><i class="fas fa-info-circle"></i> Trading Strategy:</strong><br>
            • <strong>Buy Signal:</strong> Price touches bottom fan level<br>
            • <strong>Sell Target:</strong> Top fan level<br>
            • <strong>Anchor:</strong> {spx_data['high']:.2f} (Daily High)
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(high_table, use_container_width=True, hide_index=True)
    
    with subtab2:
        st.markdown("### 📉 Low-Based Fan Levels")
        st.markdown(f"""
        <div class='premium-info-box'>
            <strong><i class="fas fa-info-circle"></i> Trading Strategy:</strong><br>
            • <strong>Buy Signal:</strong> Price touches bottom fan level<br>
            • <strong>Sell Target:</strong> Top fan level<br>
            • <strong>Anchor:</strong> {spx_data['low']:.2f} (Daily Low)
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(low_table, use_container_width=True, hide_index=True)
    
    with subtab3:
        st.markdown("### 📊 Close-Based Fan Levels")
        st.markdown(f"""
        <div class='premium-info-box'>
            <strong><i class="fas fa-info-circle"></i> Trading Strategy:</strong><br>
            • <strong>Buy Signal:</strong> Price touches bottom fan level<br>
            • <strong>Sell Target:</strong> Top fan level<br>
            • <strong>Anchor:</strong> {spx_data['close']:.2f} (Daily Close)
        </div>
        """, unsafe_allow_html=True)
        st.dataframe(close_table, use_container_width=True, hide_index=True)
    
    # Analytics section
    st.markdown("""
    <div class='glass-card'>
        <h3><i class="fas fa-analytics"></i> Fan Level Analytics</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    # Calculate 8:30 AM ranges for each anchor
    slot_830 = fmt_ct(datetime.combine(proj_day, time(8, 30)))
    
    high_830_top, high_830_bot = fan_levels_for_slot(spx_data['high'], anchor_time, slot_830)
    low_830_top, low_830_bot = fan_levels_for_slot(spx_data['low'], anchor_time, slot_830)
    close_830_top, close_830_bot = fan_levels_for_slot(spx_data['close'], anchor_time, slot_830)
    
    with col1:
        high_range = high_830_top - high_830_bot
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-arrow-up metric-icon"></i>
            <div class='metric-label'>High Fan @ 8:30</div>
            <div class='metric-value'>{high_range:.2f}</div>
            <div class='metric-sub'>{high_830_top:.2f} - {high_830_bot:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        low_range = low_830_top - low_830_bot
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-arrow-down metric-icon"></i>
            <div class='metric-label'>Low Fan @ 8:30</div>
            <div class='metric-value'>{low_range:.2f}</div>
            <div class='metric-sub'>{low_830_top:.2f} - {low_830_bot:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        close_range = close_830_top - close_830_bot
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-chart-line metric-icon"></i>
            <div class='metric-label'>Close Fan @ 8:30</div>
            <div class='metric-value'>{close_range:.2f}</div>
            <div class='metric-sub'>{close_830_top:.2f} - {close_830_bot:.2f}</div>
        </div>
        """, unsafe_allow_html=True)

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 2 — Premium BC Forecast (Same as before)                               ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab2:
    st.markdown("""
    <div class='glass-card'>
        <h2><i class="fas fa-magic"></i> BC Forecast - Advanced Entry/Exit System</h2>
        <p>Configure sophisticated bounce-rejection pairs with intuitive interface</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='premium-info-box'>
        <strong><i class="fas fa-lightbulb"></i> Complete Trading System:</strong><br>
        • Configure bounce-rejection pairs for complete projections<br>
        • Advanced interface with real-time visual feedback<br>
        • Comprehensive calculations with detailed analytics<br>
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
    with st.form("bc_form", clear_on_submit=False):
        
        st.markdown("""
        <div class='premium-form'>
            <h3><i class="fas fa-cogs"></i> Bounce-Rejection Configuration</h3>
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
                spx_b1 = st.number_input("SPX Price", value=spx_data['close'], step=0.25, format="%.2f", key="spx_b1")
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
                spx_r1 = st.number_input("SPX Price", value=spx_data['close'] + 5.0, step=0.25, format="%.2f", key="spx_r1")
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
                spx_b2 = st.number_input("SPX Price", value=spx_data['close'], step=0.25, format="%.2f", key="spx_b2")
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
                spx_r2 = st.number_input("SPX Price", value=spx_data['close'] + 7.0, step=0.25, format="%.2f", key="spx_r2")
            with col_r2_2:
                c_r2 = st.number_input("Contract Price", value=contract_3pm + 3.0, step=0.05, format="%.2f", key="c_r2")
            
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
        
        skip_rejections = st.checkbox("Skip rejection calculations (entries only)", value=False)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submitted = st.form_submit_button("🚀 Generate Complete Forecast")

    if submitted:
        # Show loading animation
        with st.spinner("🔮 Calculating Complete Entry/Exit Forecast..."):
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
                            top, bot = fan_levels_for_slot(spx_data['close'], anchor_time, slot)
                            spx_proj = round(float(spx_b2) + spx_slope * count_blocks_spx(b2_dt, slot), 2)
                            blocks_from_b2 = blocks_simple_30m(b2_dt, slot)
                            c_proj = round(float(c_b2) + contract_slope * blocks_from_b2, 2)
                            
                            c_exit = ""
                            spx_exit = ""
                            
                            if rejection_data:
                                c_exit_val = calculate_rejection_exit(
                                    rejection_data['r1_dt'], rejection_data['r2_dt'],
                                    rejection_data['c_r1'], rejection_data['c_r2'], slot
                                )
                                if c_exit_val:
                                    c_exit = f"{c_exit_val:.2f}"
                                
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
                                "Contract Exit": c_exit if c_exit else "—"
                            })
                        
                        out_df = pd.DataFrame(rows)
                        
                        # Success message
                        success_msg = "🎉 Complete Entry/Exit Forecast Generated!"
                        if rejection_data:
                            success_msg += " Both entry and exit projections calculated."
                        else:
                            success_msg += " Entry projections calculated."
                        
                        st.markdown(f"""
                        <div class='premium-success-box'>
                            <strong><i class="fas fa-check-circle"></i> {success_msg}</strong><br>
                            Review your comprehensive projections below.
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
                        st.markdown("### 📊 Complete RTH Projections")
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
                            Check other tabs for enhanced projections with your complete forecast data.
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
# ║ TAB 3 — Premium Trading Plan (Updated Strategy)                            ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab3:
    st.markdown("""
    <div class='glass-card'>
        <h2><i class="fas fa-chess"></i> Trading Plan - Fan-Based Strategy Dashboard</h2>
        <p>Complete strategy based on high/low/close fan levels for entries and exits</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Status check with professional styling
    current_ct = fmt_ct(datetime.now())
    plan_ready_time = fmt_ct(datetime.combine(proj_day, time(8, 0)))
    
    if current_ct >= plan_ready_time:
        status_msg = "🟢 Plan Active - Ready for trading session"
        status_class = "premium-success-box"
    elif current_ct >= plan_ready_time - timedelta(hours=1):
        status_msg = "🟡 Plan Preparation - Final setup in progress"
        status_class = "premium-warning-box"
    else:
        status_msg = "🔵 Plan Preview - Configuration in progress"
        status_class = "premium-info-box"
    
    st.markdown(f"""
    <div class='{status_class}'>
        <strong><i class="fas fa-info-circle"></i> {status_msg}</strong>
    </div>
    """, unsafe_allow_html=True)

    # Strategy explanation
    st.markdown(f"""
    <div class='premium-info-box'>
        <strong><i class="fas fa-lightbulb"></i> Fan-Based Trading Strategy:</strong><br>
        • <strong>Buy Setup:</strong> Enter long when price touches bottom fan level, exit at top fan level<br>
        • <strong>Sell Setup:</strong> Enter short when price touches top fan level, exit at bottom fan level<br>
        • <strong>Three Anchors:</strong> High ({spx_data['high']:.2f}), Low ({spx_data['low']:.2f}), Close ({spx_data['close']:.2f})<br>
        • <strong>Slope:</strong> {SLOPE_SPX:.2f} points per 30-minute block
    </div>
    """, unsafe_allow_html=True)

    # Key trading levels for 8:30 AM
    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
    slot_830 = fmt_ct(datetime.combine(proj_day, time(8, 30)))
    
    high_830_top, high_830_bot = fan_levels_for_slot(spx_data['high'], anchor_time, slot_830)
    low_830_top, low_830_bot = fan_levels_for_slot(spx_data['low'], anchor_time, slot_830)
    close_830_top, close_830_bot = fan_levels_for_slot(spx_data['close'], anchor_time, slot_830)
    
    # Premium strategy cards for key levels
    st.markdown("### 🎯 Key Trading Levels @ 8:30 AM")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-arrow-up metric-icon"></i>
            <div class='metric-label'>High Fan Strategy</div>
            <div class='metric-value'>
                Buy: {high_830_bot:.2f}<br>
                Sell: {high_830_top:.2f}
            </div>
            <div class='metric-sub'>
                Range: {high_830_top - high_830_bot:.2f} points<br>
                Anchor: {spx_data['high']:.2f}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-arrow-down metric-icon"></i>
            <div class='metric-label'>Low Fan Strategy</div>
            <div class='metric-value'>
                Buy: {low_830_bot:.2f}<br>
                Sell: {low_830_top:.2f}
            </div>
            <div class='metric-sub'>
                Range: {low_830_top - low_830_bot:.2f} points<br>
                Anchor: {spx_data['low']:.2f}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-chart-line metric-icon"></i>
            <div class='metric-label'>Close Fan Strategy</div>
            <div class='metric-value'>
                Buy: {close_830_bot:.2f}<br>
                Sell: {close_830_top:.2f}
            </div>
            <div class='metric-sub'>
                Range: {close_830_top - close_830_bot:.2f} points<br>
                Anchor: {spx_data['close']:.2f}
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Time-based trading opportunities
    st.markdown("### ⏰ Trading Opportunities Throughout The Day")
    
    key_times = ["08:30", "09:00", "10:00", "11:00", "12:00", "13:00", "13:30", "14:30"]
    trading_opportunities = []
    
    for time_str in key_times:
        slot_time = fmt_ct(datetime.combine(proj_day, datetime.strptime(time_str, "%H:%M").time()))
        
        high_top, high_bot = fan_levels_for_slot(spx_data['high'], anchor_time, slot_time)
        low_top, low_bot = fan_levels_for_slot(spx_data['low'], anchor_time, slot_time)
        close_top, close_bot = fan_levels_for_slot(spx_data['close'], anchor_time, slot_time)
        
        # Determine session context
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
        
        # Find the tightest and widest ranges for strategy selection
        ranges = [
            (high_top - high_bot, "High", high_bot, high_top),
            (low_top - low_bot, "Low", low_bot, low_top),
            (close_top - close_bot, "Close", close_bot, close_top)
        ]
        ranges.sort()  # Sort by range width
        
        tightest = ranges[0]  # Smallest range
        widest = ranges[2]    # Largest range
        
        trading_opportunities.append({
            "Time": time_str,
            "Session": session_context,
            "Tightest Range": f"{tightest[1]} ({tightest[0]:.2f})",
            "Buy Level": f"{tightest[2]:.2f}",
            "Sell Level": f"{tightest[3]:.2f}",
            "Widest Range": f"{widest[1]} ({widest[0]:.2f})",
            "Alt Buy": f"{widest[2]:.2f}",
            "Alt Sell": f"{widest[3]:.2f}"
        })
    
    df_opportunities = pd.DataFrame(trading_opportunities)
    st.dataframe(df_opportunities, use_container_width=True, hide_index=True)
    
    # Trading guide
    st.markdown("""
    <div class='glass-card'>
        <h3><i class="fas fa-graduation-cap"></i> Execution Guide</h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-sign-in-alt metric-icon"></i>
            <div class='metric-label'>Entry Rules</div>
            <div class='metric-sub' style='margin-top: 0;'>
                • Price must touch fan level<br>
                • Confirm with volume spike<br>
                • Use limit orders at levels<br>
                • Enter on pullbacks to level<br>
                • Size based on range width
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-sign-out-alt metric-icon"></i>
            <div class='metric-label'>Exit Rules</div>
            <div class='metric-sub' style='margin-top: 0;'>
                • Target opposite fan level<br>
                • Scale out at 50% target<br>
                • Stop 2-3 points beyond entry<br>
                • Time stop at lunch<br>
                • Trail profitable moves
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        avg_range = (high_830_top - high_830_bot + low_830_top - low_830_bot + close_830_top - close_830_bot) / 3
        suggested_size = max(1, int(100 / avg_range))  # Simple position sizing
        
        st.markdown(f"""
        <div class='metric-glass-card'>
            <i class="fas fa-calculator metric-icon"></i>
            <div class='metric-label'>Risk Management</div>
            <div class='metric-sub' style='margin-top: 0;'>
                • Avg Range: {avg_range:.2f} points<br>
                • Suggested Size: {suggested_size} contracts<br>
                • Max Risk: 1-2% of account<br>
                • Best Times: Open & Close<br>
                • Avoid: 11:30-12:30 lunch
            </div>
        </div>
        """, unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# PREMIUM FOOTER
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(f"""
<div class='glass-card' style='text-align: center; padding: 2rem;'>
    <h4><i class="fas fa-crystal-ball"></i> SPX Prophet v3.1</h4>
    <p style='margin: 0; opacity: 0.8;'>
        Professional Trading Analytics • Slope: {SLOPE_SPX:.2f}/30min • Last Updated: {fmt_ct(datetime.now()).strftime('%H:%M CT')}
    </p>
</div>
""", unsafe_allow_html=True)