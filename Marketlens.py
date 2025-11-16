# spx_prophet_v7_ultimate.py
# SPX Prophet v7.0 — ULTIMATE PREMIUM EDITION
# The most beautiful trading app you've ever seen

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

APP_NAME = "SPX Prophet v7.0"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475
BASE_DATE = datetime(2000, 1, 1, 15, 0)


# ===============================
# ULTIMATE PREMIUM UI SYSTEM
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    /* === FOUNDATION === */
    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 2000px 1200px at 20% 10%, rgba(0, 255, 255, 0.15), transparent 50%),
          radial-gradient(ellipse 1800px 1400px at 80% 90%, rgba(0, 255, 135, 0.12), transparent 50%),
          radial-gradient(circle 1000px at 50% 50%, rgba(138, 43, 226, 0.08), transparent),
          linear-gradient(180deg, #000510 0%, #010920 50%, #000510 100%);
        background-attachment: fixed;
        color: #FFFFFF;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
    }
    
    /* === PREMIUM SIDEBAR === */
    [data-testid="stSidebar"] {
        background: 
            radial-gradient(circle at 50% 0%, rgba(0,255,255,0.12), transparent 60%),
            linear-gradient(180deg, rgba(5,15,40,0.98) 0%, rgba(10,20,50,0.98) 100%);
        border-right: 2px solid rgba(0,255,200,0.25);
        backdrop-filter: blur(40px) saturate(180%);
        box-shadow: 8px 0 80px rgba(0,255,255,0.1);
    }
    
    [data-testid="stSidebar"] h3 {
        font-size: 2rem;
        font-weight: 900;
        background: linear-gradient(135deg, #00FFE5 0%, #00FF9D 50%, #7FFF00 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        letter-spacing: -0.03em;
        text-shadow: 0 0 40px rgba(0,255,255,0.3);
    }
    
    [data-testid="stSidebar"] hr {
        margin: 2rem 0;
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent, rgba(0,255,200,0.5), transparent);
        box-shadow: 0 0 20px rgba(0,255,200,0.3);
    }
    
    /* === HERO HEADER === */
    .hero-header {
        background: 
            radial-gradient(ellipse at top, rgba(0,255,255,0.15), transparent 60%),
            linear-gradient(135deg, rgba(20,30,80,0.4), rgba(10,20,60,0.6));
        border-radius: 32px;
        padding: 48px;
        margin-bottom: 48px;
        border: 2px solid rgba(0,255,200,0.3);
        box-shadow: 
            0 32px 120px rgba(0,0,0,0.8),
            0 0 100px rgba(0,255,255,0.15),
            inset 0 2px 4px rgba(255,255,255,0.1);
        position: relative;
        overflow: hidden;
    }
    
    .hero-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #00FFE5, #00FF9D, #7FFF00, #00FF9D, #00FFE5);
        background-size: 200% 100%;
        animation: shimmer 3s linear infinite;
    }
    
    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    
    .hero-title {
        font-size: 3.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #FFFFFF 0%, #00FFE5 50%, #00FF9D 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        letter-spacing: -0.04em;
        text-shadow: 0 0 60px rgba(0,255,255,0.4);
    }
    
    .hero-subtitle {
        font-size: 1.5rem;
        color: #8FA8D0;
        margin-top: 12px;
        font-weight: 400;
    }
    
    /* === MASSIVE PREMIUM CARDS === */
    .spx-card {
        position: relative;
        background: 
            radial-gradient(circle at 10% 10%, rgba(0,255,255,0.12), transparent 50%),
            radial-gradient(circle at 90% 90%, rgba(0,255,135,0.10), transparent 50%),
            linear-gradient(135deg, rgba(25,35,70,0.6), rgba(15,25,55,0.8));
        border-radius: 32px;
        border: 2px solid rgba(0,255,200,0.25);
        box-shadow:
          0 40px 100px rgba(0,0,0,0.9),
          0 20px 60px rgba(0,0,0,0.7),
          inset 0 2px 4px rgba(255,255,255,0.05),
          0 0 0 1px rgba(0,255,255,0.1);
        padding: 48px;
        margin-bottom: 40px;
        backdrop-filter: blur(30px) saturate(180%);
        transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }
    
    .spx-card::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 100%;
        background: linear-gradient(180deg, rgba(0,255,255,0.05), transparent);
        pointer-events: none;
        opacity: 0;
        transition: opacity 0.5s ease;
    }
    
    .spx-card:hover {
        transform: translateY(-8px) scale(1.01);
        border-color: rgba(0,255,255,0.5);
        box-shadow:
          0 60px 140px rgba(0,0,0,1),
          0 30px 80px rgba(0,255,255,0.2),
          inset 0 2px 6px rgba(255,255,255,0.1),
          0 0 0 2px rgba(0,255,255,0.2),
          0 0 120px rgba(0,255,255,0.15);
    }
    
    .spx-card:hover::after {
        opacity: 1;
    }
    
    .spx-card h4 {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #FFFFFF 0%, #00FFE5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0 0 16px 0;
        letter-spacing: -0.02em;
    }
    
    /* === MASSIVE ICON BADGES === */
    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 12px;
        padding: 12px 28px;
        border-radius: 100px;
        border: 2px solid rgba(0,255,200,0.4);
        background: 
            linear-gradient(135deg, rgba(0,255,200,0.25), rgba(0,255,135,0.20)),
            rgba(0,40,40,0.6);
        font-size: 1rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        color: #00FFE5;
        box-shadow: 
            0 8px 32px rgba(0,255,255,0.25),
            inset 0 2px 4px rgba(255,255,255,0.2);
        margin-bottom: 24px;
        transition: all 0.4s ease;
    }
    
    .spx-pill:hover {
        transform: scale(1.08);
        box-shadow: 
            0 12px 48px rgba(0,255,255,0.4),
            inset 0 2px 6px rgba(255,255,255,0.3);
        border-color: rgba(0,255,200,0.7);
    }
    
    .spx-pill::before {
        content: '◆';
        font-size: 1.2rem;
        color: #00FFE5;
        text-shadow: 0 0 20px rgba(0,255,255,0.8);
    }
    
    /* === ICON SYSTEM === */
    .icon-large {
        font-size: 4rem;
        background: linear-gradient(135deg, #00FFE5, #00FF9D);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 40px rgba(0,255,255,0.5);
        margin-bottom: 24px;
        display: block;
    }
    
    .icon-medium {
        font-size: 2.5rem;
        margin-right: 16px;
    }
    
    /* === SUBTITLE === */
    .spx-sub {
        color: #A8C0E8;
        font-size: 1.15rem;
        line-height: 1.6;
        font-weight: 400;
    }
    
    /* === SECTION HEADERS WITH ICONS === */
    .section-header {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #FFFFFF 0%, #00FFE5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 3rem 0 2rem 0;
        padding-bottom: 1rem;
        border-bottom: 3px solid rgba(0,255,200,0.3);
        display: flex;
        align-items: center;
        gap: 16px;
    }
    
    .section-header::before {
        content: '▸';
        color: #00FFE5;
        font-size: 2.5rem;
        text-shadow: 0 0 30px rgba(0,255,255,0.8);
    }
    
    /* === MASSIVE METRICS CARDS === */
    .spx-metric {
        position: relative;
        padding: 36px 32px;
        border-radius: 24px;
        background: 
            radial-gradient(circle at top left, rgba(0,255,255,0.18), transparent 70%),
            linear-gradient(135deg, rgba(30,45,90,0.8), rgba(20,35,75,0.9));
        border: 2px solid rgba(0,255,255,0.3);
        box-shadow: 
            0 20px 60px rgba(0,0,0,0.6),
            inset 0 2px 4px rgba(255,255,255,0.1),
            0 0 60px rgba(0,255,255,0.15);
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }
    
    .spx-metric::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #00FFE5, #00FF9D, #7FFF00);
        transform: scaleX(0);
        transform-origin: left;
        transition: transform 0.6s ease;
    }
    
    .spx-metric:hover {
        transform: translateY(-6px) scale(1.03);
        border-color: rgba(0,255,255,0.6);
        box-shadow: 
            0 32px 80px rgba(0,0,0,0.8),
            0 0 100px rgba(0,255,255,0.25),
            inset 0 2px 6px rgba(255,255,255,0.15);
    }
    
    .spx-metric:hover::before {
        transform: scaleX(1);
    }
    
    .spx-metric-label {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        color: #8FA8D0;
        font-weight: 700;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .spx-metric-label::before {
        content: '●';
        color: #00FFE5;
        font-size: 0.6rem;
        text-shadow: 0 0 10px rgba(0,255,255,0.8);
    }
    
    .spx-metric-value {
        font-size: 2.5rem;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #FFFFFF 0%, #00FFE5 50%, #00FF9D 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.02em;
        text-shadow: 0 0 40px rgba(0,255,255,0.3);
    }
    
    /* === EPIC BUTTONS === */
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #00E5FF 0%, #00FF9D 50%, #7FFF00 100%);
        color: #001a1a;
        border-radius: 16px;
        border: none;
        padding: 20px 40px;
        font-weight: 800;
        font-size: 1.1rem;
        letter-spacing: 0.05em;
        box-shadow: 
            0 16px 48px rgba(0,230,255,0.4),
            0 8px 24px rgba(0,0,0,0.5),
            inset 0 2px 4px rgba(255,255,255,0.4);
        cursor: pointer;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
        text-transform: uppercase;
    }
    
    .stButton>button::before, .stDownloadButton>button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
        transition: left 0.6s ease;
    }
    
    .stButton>button:hover::before, .stDownloadButton>button:hover::before {
        left: 100%;
    }
    
    .stButton>button:hover, .stDownloadButton>button:hover {
        transform: translateY(-4px) scale(1.05);
        box-shadow: 
            0 24px 64px rgba(0,230,255,0.5),
            0 12px 32px rgba(0,0,0,0.6),
            inset 0 2px 6px rgba(255,255,255,0.5);
    }
    
    .stButton>button:active, .stDownloadButton>button:active {
        transform: translateY(-2px) scale(1.03);
    }
    
    /* === PREMIUM INPUTS === */
    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        background: rgba(20,35,70,0.8) !important;
        border: 2px solid rgba(0,255,200,0.3) !important;
        border-radius: 16px !important;
        color: #FFFFFF !important;
        padding: 16px 20px !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        font-family: 'JetBrains Mono', monospace !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3) !important;
    }
    
    .stNumberInput>div>div>input:focus,
    .stTimeInput>div>div>input:focus {
        border-color: rgba(0,255,255,0.7) !important;
        box-shadow: 
            0 0 0 4px rgba(0,255,255,0.15),
            0 8px 24px rgba(0,255,255,0.25) !important;
        background: rgba(30,45,85,0.9) !important;
    }
    
    /* === PREMIUM RADIO === */
    .stRadio>div {
        gap: 20px;
    }
    
    .stRadio>div>label {
        background: 
            radial-gradient(circle at top, rgba(0,255,255,0.1), transparent),
            rgba(20,35,70,0.7);
        padding: 18px 32px;
        border-radius: 16px;
        border: 2px solid rgba(0,255,200,0.25);
        transition: all 0.3s ease;
        cursor: pointer;
        font-weight: 600;
        font-size: 1.05rem;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3);
    }
    
    .stRadio>div>label:hover {
        background: 
            radial-gradient(circle at top, rgba(0,255,255,0.15), transparent),
            rgba(30,45,85,0.8);
        border-color: rgba(0,255,200,0.5);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(0,255,255,0.2);
    }
    
    .stRadio>div>label[data-selected="true"] {
        background: 
            linear-gradient(135deg, rgba(0,255,255,0.25), rgba(0,255,135,0.20)),
            rgba(30,45,85,0.9);
        border-color: rgba(0,255,200,0.7);
        box-shadow: 
            0 8px 32px rgba(0,255,255,0.3),
            inset 0 2px 4px rgba(255,255,255,0.1);
        transform: translateY(-2px);
    }
    
    /* === STUNNING TABS === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 16px;
        background: 
            radial-gradient(circle at center, rgba(0,255,255,0.08), transparent),
            rgba(10,20,45,0.8);
        padding: 16px;
        border-radius: 24px;
        border: 2px solid rgba(0,255,200,0.2);
        box-shadow: 
            0 8px 32px rgba(0,0,0,0.5),
            inset 0 2px 4px rgba(255,255,255,0.05);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 16px;
        color: #8FA8D0;
        font-weight: 700;
        font-size: 1.05rem;
        padding: 16px 32px;
        transition: all 0.3s ease;
        border: 2px solid transparent;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(0,255,200,0.12);
        color: #00FFE5;
        transform: translateY(-2px);
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: 
            linear-gradient(135deg, rgba(0,255,255,0.25), rgba(0,255,135,0.20)),
            rgba(30,45,85,0.6);
        color: #00FFE5;
        border-color: rgba(0,255,200,0.5);
        box-shadow: 
            0 8px 32px rgba(0,255,255,0.25),
            inset 0 2px 4px rgba(255,255,255,0.1);
        transform: translateY(-2px);
    }
    
    /* === EPIC DATAFRAMES === */
    .stDataFrame {
        border-radius: 20px;
        overflow: hidden;
        box-shadow: 
            0 20px 60px rgba(0,0,0,0.6),
            0 0 60px rgba(0,255,255,0.1);
        border: 2px solid rgba(0,255,200,0.2);
    }
    
    .stDataFrame div[data-testid="StyledTable"] {
        font-variant-numeric: tabular-nums;
        font-size: 1rem;
        font-family: 'JetBrains Mono', monospace;
        background: rgba(15,25,55,0.9);
    }
    
    .stDataFrame thead tr th {
        background: linear-gradient(135deg, rgba(0,255,255,0.25), rgba(0,255,135,0.20)) !important;
        color: #00FFE5 !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.12em !important;
        font-size: 0.9rem !important;
        padding: 20px 16px !important;
        border-bottom: 3px solid rgba(0,255,200,0.5) !important;
        box-shadow: inset 0 -2px 4px rgba(0,255,255,0.2) !important;
    }
    
    .stDataFrame tbody tr {
        transition: all 0.2s ease;
    }
    
    .stDataFrame tbody tr:hover {
        background: rgba(0,255,255,0.1) !important;
        transform: scale(1.01);
    }
    
    .stDataFrame tbody tr td {
        padding: 16px !important;
        border-bottom: 1px solid rgba(0,255,200,0.15) !important;
        color: #E8F0FF !important;
        font-weight: 500 !important;
    }
    
    /* === MESSAGES === */
    .stSuccess {
        background: 
            linear-gradient(135deg, rgba(0,255,135,0.25), rgba(0,255,200,0.20)),
            rgba(0,50,40,0.8);
        border-radius: 20px;
        border: 2px solid rgba(0,255,135,0.5);
        padding: 24px 32px;
        backdrop-filter: blur(20px);
        box-shadow: 
            0 12px 48px rgba(0,255,135,0.2),
            inset 0 2px 4px rgba(255,255,255,0.1);
        font-size: 1.1rem;
    }
    
    .stWarning {
        background: 
            linear-gradient(135deg, rgba(255,200,0,0.25), rgba(255,150,0,0.20)),
            rgba(50,40,0,0.8);
        border-radius: 20px;
        border: 2px solid rgba(255,200,0,0.5);
        padding: 24px 32px;
        backdrop-filter: blur(20px);
        box-shadow: 
            0 12px 48px rgba(255,200,0,0.2),
            inset 0 2px 4px rgba(255,255,255,0.1);
        font-size: 1.1rem;
    }
    
    .stInfo {
        background: 
            linear-gradient(135deg, rgba(0,200,255,0.25), rgba(0,150,255,0.20)),
            rgba(0,40,50,0.8);
        border-radius: 20px;
        border: 2px solid rgba(0,200,255,0.5);
        padding: 24px 32px;
        backdrop-filter: blur(20px);
        box-shadow: 
            0 12px 48px rgba(0,200,255,0.2),
            inset 0 2px 4px rgba(255,255,255,0.1);
        font-size: 1.1rem;
    }
    
    /* === SELECTBOX === */
    .stSelectbox>div>div {
        background: rgba(20,35,70,0.8);
        border: 2px solid rgba(0,255,200,0.3);
        border-radius: 16px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3);
        font-size: 1.05rem;
    }
    
    .stSelectbox>div>div:hover {
        border-color: rgba(0,255,200,0.6);
        background: rgba(30,45,85,0.9);
        box-shadow: 0 8px 24px rgba(0,255,255,0.2);
    }
    
    /* === MUTED TEXT === */
    .muted {
        color: #8FA8D0;
        font-size: 1rem;
        line-height: 1.7;
        padding: 20px 24px;
        background: 
            linear-gradient(135deg, rgba(0,100,150,0.15), rgba(0,80,120,0.12)),
            rgba(15,25,50,0.6);
        border-left: 4px solid rgba(0,255,200,0.4);
        border-radius: 12px;
        margin: 20px 0;
        box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    }
    
    /* === STUNNING SCROLLBAR === */
    ::-webkit-scrollbar {
        width: 14px;
        height: 14px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(10,20,45,0.6);
        border-radius: 10px;
        border: 1px solid rgba(0,255,200,0.1);
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, rgba(0,255,255,0.4), rgba(0,255,135,0.4));
        border-radius: 10px;
        border: 2px solid rgba(10,20,45,0.6);
        box-shadow: 
            inset 0 1px 2px rgba(255,255,255,0.2),
            0 0 20px rgba(0,255,255,0.2);
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, rgba(0,255,255,0.6), rgba(0,255,135,0.6));
        box-shadow: 
            inset 0 1px 2px rgba(255,255,255,0.3),
            0 0 30px rgba(0,255,255,0.4);
    }
    
    /* === SPACING === */
    .block-container {
        padding-top: 4rem;
        padding-bottom: 4rem;
        max-width: 1600px;
    }
    
    /* === STATUS INDICATOR === */
    .status-indicator {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 10px 20px;
        border-radius: 100px;
        background: rgba(0,255,135,0.2);
        border: 2px solid rgba(0,255,135,0.4);
        font-size: 0.9rem;
        font-weight: 700;
        color: #00FF9D;
        box-shadow: 0 4px 16px rgba(0,255,135,0.2);
    }
    
    .status-indicator::before {
        content: '●';
        color: #00FF9D;
        font-size: 1.2rem;
        animation: pulse 2s ease infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(0.8); }
    }
    
    /* === FOOTER === */
    .app-footer {
        margin-top: 5rem;
        padding-top: 3rem;
        border-top: 2px solid rgba(0,255,200,0.2);
        text-align: center;
        color: #6A7A98;
        font-size: 1rem;
    }
    
    /* === INPUT LABELS === */
    label {
        font-size: 1rem !important;
        font-weight: 600 !important;
        color: #A8C0E8 !important;
        margin-bottom: 8px !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def hero():
    """Epic hero section"""
    st.markdown("""
    <div class="hero-header">
        <div class="status-indicator">System Active</div>
        <h1 class="hero-title">SPX Prophet v7.0</h1>
        <p class="hero-subtitle">Where Structure Becomes Foresight</p>
    </div>
    """, unsafe_allow_html=True)


def card(title: str, sub: Optional[str] = None, badge: Optional[str] = None, icon: str = ""):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    if icon:
        st.markdown(f"<span class='icon-large'>{icon}</span>", unsafe_allow_html=True)
    if badge:
        st.markdown(f"<div class='spx-pill'>{badge}</div>", unsafe_allow_html=True)
    st.markdown(f"<h4>{title}</h4>", unsafe_allow_html=True)
    if sub:
        st.markdown(f"<div class='spx-sub'>{sub}</div>", unsafe_allow_html=True)


def end_card():
    st.markdown("</div>", unsafe_allow_html=True)


def metric_card(label: str, value: str, icon: str = "●"):
    return f"""
    <div class='spx-metric'>
        <div class='spx-metric-label'>{label}</div>
        <div class='spx-metric-value'>{value}</div>
    </div>
    """


def section_header(text: str):
    st.markdown(f"<h3 class='section-header'>{text}</h3>", unsafe_allow_html=True)


# ===============================
# TIME / BLOCK HELPERS
# ===============================

def make_dt_from_time(t: dtime) -> datetime:
    if t.hour >= 15:
        return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    else:
        next_day = BASE_DATE.date() + timedelta(days=1)
        return datetime(next_day.year, next_day.month, next_day.day, t.hour, t.minute)


def align_30min(dt: datetime) -> datetime:
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    next_day = BASE_DATE.date() + timedelta(days=1)
    start = datetime(next_day.year, next_day.month, next_day.day, 8, 30)
    end = datetime(next_day.year, next_day.month, next_day.day, 14, 30)
    return pd.date_range(start=start, end=end, freq="30min")


# ===============================
# CHANNEL ENGINE
# ===============================

def build_channel(
    high_price: float,
    high_time: dtime,
    low_price: float,
    low_time: dtime,
    slope_sign: int,
) -> Tuple[pd.DataFrame, float]:
    s = slope_sign * SLOPE_MAG
    dt_hi = align_30min(make_dt_from_time(high_time))
    dt_lo = align_30min(make_dt_from_time(low_time))
    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)
    b_top = high_price - s * k_hi
    b_bottom = low_price - s * k_lo
    channel_height = b_top - b_bottom
    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        top = s * k + b_top
        bottom = s * k + b_bottom
        rows.append({
            "Time": dt.strftime("%H:%M"),
            "Top Rail": round(top, 4),
            "Bottom Rail": round(bottom, 4),
        })
    df = pd.DataFrame(rows)
    return df, round(channel_height, 4)


# ===============================
# CONTRACT ENGINE
# ===============================

def build_contract_projection(
    anchor_a_time: dtime,
    anchor_a_price: float,
    anchor_b_time: dtime,
    anchor_b_price: float,
) -> Tuple[pd.DataFrame, float]:
    dt_a = align_30min(make_dt_from_time(anchor_a_time))
    dt_b = align_30min(make_dt_from_time(anchor_b_time))
    k_a = blocks_from_base(dt_a)
    k_b = blocks_from_base(dt_b)
    if k_a == k_b:
        slope = 0.0
    else:
        slope = (anchor_b_price - anchor_a_price) / (k_b - k_a)
    b_contract = anchor_a_price - slope * k_a
    slots = rth_slots()
    rows = []
    for dt in slots:
        k = blocks_from_base(dt)
        price = slope * k + b_contract
        rows.append({
            "Time": dt.strftime("%H:%M"),
            "Contract Price": round(price, 4),
        })
    df = pd.DataFrame(rows)
    return df, round(slope, 6)


# ===============================
# DAILY FORESIGHT CARD LOGIC
# ===============================

def get_active_channel() -> Tuple[Optional[str], Optional[pd.DataFrame], Optional[float]]:
    mode = st.session_state.get("channel_mode")
    df_asc = st.session_state.get("channel_asc_df")
    df_desc = st.session_state.get("channel_desc_df")
    h_asc = st.session_state.get("channel_asc_height")
    h_desc = st.session_state.get("channel_desc_height")

    if mode == "Ascending":
        return "Ascending", df_asc, h_asc
    if mode == "Descending":
        return "Descending", df_desc, h_desc
    if mode == "Both":
        scenario = st.selectbox(
            "Active scenario for Foresight",
            ["Ascending", "Descending"],
            index=0,
            key="foresight_scenario",
        )
        if scenario == "Ascending":
            return "Ascending", df_asc, h_asc
        else:
            return "Descending", df_desc, h_desc
    return None, None, None


# ===============================
# MAIN APP
# ===============================

def main():
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    # EPIC Sidebar
    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.markdown(f"<span class='spx-sub'>{TAGLINE}</span>", unsafe_allow_html=True)
        st.markdown("---")
        
        st.markdown("#### ⚡ Core Slope")
        st.write(f"SPX rail slope magnitude: **{SLOPE_MAG} pts / 30 min**")
        st.caption("All calculations use a uniform per-block slope. Time grid = 30-minute candles.")
        
        st.markdown("---")
        st.markdown("#### 📋 Notes")
        st.caption(
            "Underlying maintenance: 16:00–17:00 CT\n\n"
            "Contracts maintenance: 16:00–19:00 CT\n\n"
            "RTH projection window: 08:30–14:30 CT."
        )

    # Hero Section
    hero()

    tabs = st.tabs([
        "🧱 SPX Channel Setup",
        "📐 Contract Slope Setup",
        "🔮 Daily Foresight Card",
        "ℹ️ About",
    ])

    # ==========================
    # TAB 1 — CHANNEL SETUP
    # ==========================
    with tabs[0]:
        card(
            "SPX Channel Setup",
            "Define your high and low pivots, choose the channel regime, and project parallel rails across RTH.",
            badge="Rails Engine",
            icon="🧱"
        )

        section_header("⚙️ Pivots Configuration")
        st.markdown("<p style='font-size:1.05rem; color:#A8C0E8; margin-bottom:24px;'>3:00 PM to 7:30 AM, manual</p>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("#### 📈 High Pivot")
            high_price = st.number_input(
                "High Pivot Price",
                value=5200.0,
                step=0.25,
                key="pivot_high_price",
            )
            high_time = st.time_input(
                "High Pivot Time (CT)",
                value=dtime(15, 0),
                step=1800,
                key="pivot_high_time",
            )
        with c2:
            st.markdown("#### 📉 Low Pivot")
            low_price = st.number_input(
                "Low Pivot Price",
                value=5100.0,
                step=0.25,
                key="pivot_low_price",
            )
            low_time = st.time_input(
                "Low Pivot Time (CT)",
                value=dtime(3, 0),
                step=1800,
                key="pivot_low_time",
            )

        section_header("📊 Channel Regime")
        mode = st.radio(
            "Select your channel mode",
            ["Ascending", "Descending", "Both"],
            index=0,
            key="channel_mode",
            horizontal=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button("⚡ BUILD CHANNEL", key="build_channel_btn", use_container_width=True):
                if mode in ("Ascending", "Both"):
                    df_asc, h_asc = build_channel(
                        high_price=high_price,
                        high_time=high_time,
                        low_price=low_price,
                        low_time=low_time,
                        slope_sign=+1,
                    )
                    st.session_state["channel_asc_df"] = df_asc
                    st.session_state["channel_asc_height"] = h_asc
                else:
                    st.session_state["channel_asc_df"] = None
                    st.session_state["channel_asc_height"] = None

                if mode in ("Descending", "Both"):
                    df_desc, h_desc = build_channel(
                        high_price=high_price,
                        high_time=high_time,
                        low_price=low_price,
                        low_time=low_time,
                        slope_sign=-1,
                    )
                    st.session_state["channel_desc_df"] = df_desc
                    st.session_state["channel_desc_height"] = h_desc
                else:
                    st.session_state["channel_desc_df"] = None
                    st.session_state["channel_desc_height"] = None

                st.success("✨ Channel(s) generated successfully! Check tables below and the Daily Foresight Card tab.")

        df_asc = st.session_state.get("channel_asc_df")
        df_desc = st.session_state.get("channel_desc_df")
        h_asc = st.session_state.get("channel_asc_height")
        h_desc = st.session_state.get("channel_desc_height")

        section_header("📊 Channel Projections • RTH 08:30–14:30 CT")
        
        if df_asc is None and df_desc is None:
            st.info("📊 Build a channel to view projections.")
        else:
            if df_asc is not None:
                st.markdown("<br><h4 style='font-size:1.8rem; margin-bottom:24px;'>📈 Ascending Channel</h4>", unsafe_allow_html=True)
                c_top = st.columns([3, 1], gap="large")
                with c_top[0]:
                    st.dataframe(df_asc, use_container_width=True, hide_index=True, height=400)
                with c_top[1]:
                    st.markdown(metric_card("Channel Height", f"{h_asc:.2f} pts"), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "📥 DOWNLOAD CSV",
                        df_asc.to_csv(index=False).encode(),
                        "spx_ascending_rails.csv",
                        "text/csv",
                        key="dl_asc_channel",
                        use_container_width=True,
                    )

            if df_desc is not None:
                st.markdown("<br><h4 style='font-size:1.8rem; margin-bottom:24px;'>📉 Descending Channel</h4>", unsafe_allow_html=True)
                c_bot = st.columns([3, 1], gap="large")
                with c_bot[0]:
                    st.dataframe(df_desc, use_container_width=True, hide_index=True, height=400)
                with c_bot[1]:
                    st.markdown(metric_card("Channel Height", f"{h_desc:.2f} pts"), unsafe_allow_html=True)
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "📥 DOWNLOAD CSV",
                        df_desc.to_csv(index=False).encode(),
                        "spx_descending_rails.csv",
                        "text/csv",
                        key="dl_desc_channel",
                        use_container_width=True,
                    )

        end_card()

    # ==========================
    # TAB 2 — CONTRACT SLOPE
    # ==========================
    with tabs[1]:
        card(
            "Contract Slope Setup",
            "Anchor your contract line to a pivot or custom time, define a second point, and project value across RTH.",
            badge="Contract Engine",
            icon="📐"
        )

        ph_time: dtime = st.session_state.get("pivot_high_time", dtime(15, 0))
        pl_time: dtime = st.session_state.get("pivot_low_time", dtime(3, 0))

        section_header("⚓ Anchor A — Contract Origin")
        anchor_a_source = st.radio(
            "Use which time for Anchor A?",
            ["High Pivot Time", "Low Pivot Time", "Custom Time"],
            index=0,
            key="contract_anchor_a_source",
            horizontal=True,
        )

        if anchor_a_source == "High Pivot Time":
            anchor_a_time = ph_time
            st.markdown(
                f"<div class='muted'>✓ Anchor A time set to High Pivot Time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT</div>",
                unsafe_allow_html=True,
            )
        elif anchor_a_source == "Low Pivot Time":
            anchor_a_time = pl_time
            st.markdown(
                f"<div class='muted'>✓ Anchor A time set to Low Pivot Time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT</div>",
                unsafe_allow_html=True,
            )
        else:
            anchor_a_time = st.time_input(
                "Custom Anchor A Time (CT)",
                value=dtime(1, 0),
                step=1800,
                key="contract_anchor_a_time_custom",
            )

        anchor_a_price = st.number_input(
            "Contract Price at Anchor A Time",
            value=10.0,
            step=0.1,
            key="contract_anchor_a_price",
        )

        section_header("⚓ Anchor B — Second Contract Point")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            anchor_b_time = st.time_input(
                "Anchor B Time (CT)",
                value=dtime(7, 30),
                step=1800,
                key="contract_anchor_b_time",
            )
        with c2:
            anchor_b_price = st.number_input(
                "Contract Price at Anchor B Time",
                value=8.0,
                step=0.1,
                key="contract_anchor_b_price",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button("⚡ BUILD CONTRACT", key="build_contract_btn", use_container_width=True):
                df_contract, slope_contract = build_contract_projection(
                    anchor_a_time=anchor_a_time,
                    anchor_a_price=anchor_a_price,
                    anchor_b_time=anchor_b_time,
                    anchor_b_price=anchor_b_price,
                )
                # ONLY store derived objects, not widget-controlled values
                st.session_state["contract_df"] = df_contract
                st.session_state["contract_slope"] = slope_contract
                st.success("✨ Contract projection generated successfully! Check the table below and the Daily Foresight Card tab.")

        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        section_header("📊 Contract Projection • RTH 08:30–14:30 CT")
        
        if df_contract is None:
            st.info("📊 Build a contract projection to view projected contract prices.")
        else:
            c_top = st.columns([3, 1], gap="large")
            with c_top[0]:
                st.dataframe(df_contract, use_container_width=True, hide_index=True, height=400)
            with c_top[1]:
                st.markdown(metric_card("Contract Slope", f"{slope_contract:+.4f} / 30m"), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "📥 DOWNLOAD CSV",
                    df_contract.to_csv(index=False).encode(),
                    "contract_projection.csv",
                    "text/csv",
                    key="dl_contract",
                    use_container_width=True,
                )

        end_card()

    # ==========================
    # TAB 3 — DAILY FORESIGHT
    # ==========================
    with tabs[2]:
        card(
            "Daily Foresight Card",
            "Channel structure + contract slope combined into a simple playbook for the session.",
            badge="Foresight",
            icon="🔮"
        )

        mode = st.session_state.get("channel_mode")
        df_mode, df_ch, h_ch = get_active_channel()
        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        if df_ch is None or h_ch is None:
            st.warning("⚠️ No active channel found. Build a channel in the SPX Channel Setup tab first.")
            end_card()
        elif df_contract is None or slope_contract is None:
            st.warning("⚠️ No contract projection found. Build one in the Contract Slope Setup tab first.")
            end_card()
        else:
            merged = df_ch.merge(df_contract, on="Time", how="left")
            blocks_for_channel = h_ch / SLOPE_MAG if SLOPE_MAG != 0 else 0
            contract_move_per_channel = slope_contract * blocks_for_channel if blocks_for_channel != 0 else 0

            section_header("📊 Structure Summary")
            c1, c2, c3 = st.columns(3, gap="large")
            with c1:
                st.markdown(metric_card("Active Channel", df_mode), unsafe_allow_html=True)
            with c2:
                st.markdown(metric_card("Channel Height", f"{h_ch:.2f} pts"), unsafe_allow_html=True)
            with c3:
                st.markdown(metric_card("Contract Move", f"{contract_move_per_channel:+.2f} units"), unsafe_allow_html=True)

            section_header("📈 Inside-Channel Play")
            st.markdown(f"""
            <div style='font-size:1.1rem; line-height:1.8;'>
            <p><strong style='color:#00FFE5; font-size:1.2rem;'>🟢 LONG PLAY</strong> → Buy at bottom rail, exit at top rail</p>
            <ul style='margin-left:32px;'>
                <li>Underlying reward ≈ <strong style='color:#00FF9D;'>+{h_ch:.2f} pts</strong></li>
                <li>Contract expectation ≈ <strong style='color:#00FF9D;'>{contract_move_per_channel:+.2f} units</strong></li>
            </ul>
            
            <p><strong style='color:#FF6B6B; font-size:1.2rem;'>🔴 SHORT PLAY</strong> → Sell at top rail, exit at bottom rail</p>
            <ul style='margin-left:32px;'>
                <li>Underlying reward ≈ <strong style='color:#FF6B6B;'>-{h_ch:.2f} pts</strong></li>
                <li>Contract expectation ≈ <strong style='color:#FF6B6B;'>{(-contract_move_per_channel):+.2f} units</strong></li>
            </ul>
            </div>
            """, unsafe_allow_html=True)

            section_header("💥 Breakout / Breakdown Play")
            st.markdown(f"""
            <div style='font-size:1.1rem; line-height:1.8;'>
            <p><strong style='color:#00FFE5; font-size:1.2rem;'>🚀 BULLISH BREAKOUT</strong></p>
            <ul style='margin-left:32px;'>
                <li>Entry on retest of top rail from above</li>
                <li>Underlying continuation target ≈ <strong style='color:#00FF9D;'>Top Rail + {h_ch:.2f} pts</strong></li>
                <li>Contract expectation per full channel move ≈ <strong style='color:#00FF9D;'>{contract_move_per_channel:+.2f} units</strong></li>
            </ul>
            
            <p><strong style='color:#FF6B6B; font-size:1.2rem;'>⬇️ BEARISH BREAKDOWN</strong></p>
            <ul style='margin-left:32px;'>
                <li>Entry on retest of bottom rail from below</li>
                <li>Underlying continuation target ≈ <strong style='color:#FF6B6B;'>Bottom Rail − {h_ch:.2f} pts</strong></li>
                <li>Contract expectation per full channel move ≈ <strong style='color:#FF6B6B;'>{contract_move_per_channel:+.2f} units</strong></li>
            </ul>
            </div>
            """, unsafe_allow_html=True)

            section_header("🗺️ Time-Aligned Map")
            st.caption("Each row is a 30-minute slot in RTH. Use this as a conditional map: if price tags a rail at that time, this is the expected contract level.")
            st.dataframe(merged, use_container_width=True, hide_index=True, height=500)

            st.markdown(
                "<div class='muted'><strong>💡 Interpretation:</strong> "
                "The map does not predict exactly <em>when</em> SPX will hit a rail. "
                "It tells you what the contract should roughly be worth <em>if</em> that touch happens at a given time.</div>",
                unsafe_allow_html=True,
            )

            end_card()

    # ==========================
    # TAB 4 — ABOUT
    # ==========================
    with tabs[3]:
        card("About SPX Prophet v7.0", TAGLINE, badge="Version 7.0", icon="ℹ️")
        st.markdown(
            """
            <div style='font-size:1.15rem; line-height:1.8;'>
            <p><strong>SPX Prophet v7.0</strong> is built around a single idea:</p>

            <blockquote style='border-left:4px solid #00FFE5; padding-left:24px; margin:32px 0; font-size:1.3rem; font-style:italic; color:#00FFE5;'>
            Two pivots define the rails. The slope defines the future.
            </blockquote>

            <ul style='margin-left:32px; font-size:1.1rem;'>
                <li>Rails are projected using a <strong style='color:#00FFE5;'>uniform slope</strong> of <strong>±0.475 pts per 30 minutes</strong></li>
                <li>Pivots are <strong style='color:#00FFE5;'>engulfing reversals</strong> chosen between <strong>15:00 and 07:30 CT</strong></li>
                <li>Channels can be <strong style='color:#00FFE5;'>ascending, descending, or inspected both ways</strong></li>
                <li>Contracts are projected from <strong style='color:#00FFE5;'>two anchor prices</strong> on the same 30-minute grid</li>
            </ul>

            <p style='margin-top:32px; font-size:1.2rem;'>The app does not guess volatility, gamma, or implied pricing.<br>
            It respects one thing: <strong style='color:#00FFE5;'>structure</strong>.</p>

            <p style='margin-top:24px; font-size:1.2rem; color:#00FF9D;'>
            When the market returns to your rails, you are no longer surprised.<br>
            <strong>You are prepared.</strong>
            </p>
            </div>
            """.strip(), unsafe_allow_html=True
        )
        st.markdown("<div class='muted'><strong>🔧 Maintenance windows:</strong> SPX 16:00–17:00 CT, contracts 16:00–19:00 CT.</div>", unsafe_allow_html=True)
        end_card()

    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet v7.0 • Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()