# spx_prophet_stunning.py
# SPX Prophet — STUNNING LIGHT MODE EDITION

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."
SLOPE_MAG = 0.475          # SPX rail slope per 30 mins
CONTRACT_FACTOR = 0.3      # fraction of channel height used for contract TP
BASE_DATE = datetime(2000, 1, 1, 15, 0)


# ===============================
# STUNNING LIGHT MODE UI
# ===============================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800;900&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');
    
    /* === FOUNDATION === */
    html, body, [data-testid="stAppViewContainer"] {
        background:
          radial-gradient(ellipse 1800px 1200px at 20% 10%, rgba(99, 102, 241, 0.08), transparent 60%),
          radial-gradient(ellipse 1600px 1400px at 80% 90%, rgba(59, 130, 246, 0.08), transparent 60%),
          radial-gradient(circle 1200px at 50% 50%, rgba(167, 139, 250, 0.05), transparent),
          linear-gradient(180deg, #ffffff 0%, #f8fafc 30%, #f1f5f9 60%, #f8fafc 100%);
        background-attachment: fixed;
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    
    .block-container {
        padding-top: 3.5rem;
        padding-bottom: 4rem;
        max-width: 1400px;
    }
    
    /* === STUNNING SIDEBAR === */
    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.08), transparent 70%),
            linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
        border-right: 2px solid rgba(99, 102, 241, 0.15);
        box-shadow: 
            8px 0 40px rgba(99, 102, 241, 0.08),
            4px 0 20px rgba(0, 0, 0, 0.03);
    }
    
    [data-testid="stSidebar"] h3 {
        font-size: 2rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #6366f1 0%, #3b82f6 50%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.5rem;
        letter-spacing: -0.04em;
    }
    
    [data-testid="stSidebar"] hr {
        margin: 2rem 0;
        border: none;
        height: 2px;
        background: linear-gradient(90deg, 
            transparent 0%, 
            rgba(99, 102, 241, 0.3) 20%, 
            rgba(59, 130, 246, 0.5) 50%, 
            rgba(99, 102, 241, 0.3) 80%, 
            transparent 100%);
        box-shadow: 0 2px 8px rgba(99, 102, 241, 0.15);
    }
    
    [data-testid="stSidebar"] h4 {
        color: #6366f1;
        font-size: 0.95rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    
    /* === EPIC HERO HEADER === */
    .hero-header {
        position: relative;
        background:
            radial-gradient(ellipse at top left, rgba(99, 102, 241, 0.12), transparent 60%),
            radial-gradient(ellipse at bottom right, rgba(59, 130, 246, 0.12), transparent 60%),
            linear-gradient(135deg, #ffffff, #fafbff);
        border-radius: 32px;
        padding: 48px 56px;
        margin-bottom: 48px;
        border: 2px solid rgba(99, 102, 241, 0.2);
        box-shadow:
            0 32px 80px -12px rgba(99, 102, 241, 0.15),
            0 16px 40px -8px rgba(0, 0, 0, 0.08),
            inset 0 2px 4px rgba(255, 255, 255, 0.9),
            inset 0 -2px 4px rgba(99, 102, 241, 0.05);
        overflow: hidden;
        animation: heroGlow 6s ease-in-out infinite;
        text-align: center;
    }
    
    @keyframes heroGlow {
        0%, 100% { box-shadow: 0 32px 80px -12px rgba(99, 102, 241, 0.15), 0 16px 40px -8px rgba(0, 0, 0, 0.08); }
        50% { box-shadow: 0 32px 80px -12px rgba(99, 102, 241, 0.25), 0 16px 40px -8px rgba(99, 102, 241, 0.12); }
    }
    
    .hero-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #6366f1, #3b82f6, #06b6d4, #3b82f6, #6366f1);
        background-size: 200% 100%;
        animation: shimmer 4s linear infinite;
    }
    
    @keyframes shimmer {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    
    .hero-title {
        font-size: 3.3rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 40%, #3b82f6 70%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        letter-spacing: -0.05em;
        line-height: 1.1;
        animation: titleFloat 3s ease-in-out infinite;
    }
    
    @keyframes titleFloat {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-4px); }
    }
    
    .hero-subtitle {
        font-size: 1.3rem;
        color: #64748b;
        margin-top: 12px;
        font-weight: 500;
        font-family: 'Poppins', sans-serif;
    }
    
    /* === ANIMATED STATUS INDICATOR === */
    .status-indicator {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 10px 20px;
        border-radius: 100px;
        background: 
            linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(5, 150, 105, 0.12)),
            #ffffff;
        border: 2px solid rgba(16, 185, 129, 0.3);
        font-size: 0.9rem;
        font-weight: 700;
        color: #059669;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        box-shadow: 
            0 8px 24px rgba(16, 185, 129, 0.15),
            inset 0 1px 2px rgba(255, 255, 255, 0.8);
        margin-bottom: 20px;
        animation: statusPulse 2s ease-in-out infinite;
        justify-content: center;
    }
    
    @keyframes statusPulse {
        0%, 100% { transform: scale(1); box-shadow: 0 8px 24px rgba(16, 185, 129, 0.15); }
        50% { transform: scale(1.03); box-shadow: 0 12px 32px rgba(16, 185, 129, 0.25); }
    }
    
    .status-indicator::before {
        content: '';
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: #10b981;
        box-shadow: 0 0 12px rgba(16, 185, 129, 0.6);
        animation: pulse 2s ease-in-out infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.7; transform: scale(0.85); }
    }
    
    /* === EPIC CARDS === */
    .spx-card {
        position: relative;
        background:
            radial-gradient(circle at 8% 8%, rgba(99, 102, 241, 0.08), transparent 50%),
            radial-gradient(circle at 92% 92%, rgba(59, 130, 246, 0.08), transparent 50%),
            linear-gradient(135deg, #ffffff, #fefeff);
        border-radius: 32px;
        border: 2px solid rgba(99, 102, 241, 0.2);
        box-shadow:
            0 32px 80px -12px rgba(99, 102, 241, 0.12),
            0 16px 40px -8px rgba(0, 0, 0, 0.06),
            inset 0 2px 4px rgba(255, 255, 255, 0.9),
            inset 0 -2px 4px rgba(99, 102, 241, 0.05);
        padding: 40px 44px;
        margin-bottom: 40px;
        transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        overflow: hidden;
    }
    
    .spx-card::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, 
            transparent, 
            rgba(99, 102, 241, 0.08), 
            transparent);
        transition: left 0.8s ease;
    }
    
    .spx-card:hover {
        transform: translateY(-8px) scale(1.01);
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow:
            0 48px 100px -12px rgba(99, 102, 241, 0.2),
            0 24px 60px -8px rgba(99, 102, 241, 0.15),
            inset 0 2px 6px rgba(255, 255, 255, 1),
            inset 0 -2px 6px rgba(99, 102, 241, 0.1);
    }
    
    .spx-card:hover::after {
        left: 100%;
    }
    
    .spx-card h4 {
        font-size: 2rem;
        font-weight: 900;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 12px 0;
        letter-spacing: -0.03em;
    }
    
    /* === LARGE ICONS === */
    .icon-large {
        font-size: 4rem;
        background: linear-gradient(135deg, #6366f1, #3b82f6, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 16px;
        display: block;
        text-shadow: 0 8px 24px rgba(99, 102, 241, 0.3);
        animation: iconBounce 3s ease-in-out infinite;
    }
    
    @keyframes iconBounce {
        0%, 100% { transform: translateY(0) rotate(0deg); }
        50% { transform: translateY(-6px) rotate(2deg); }
    }
    
    /* === PREMIUM BADGES === */
    .spx-pill {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 10px 24px;
        border-radius: 100px;
        border: 2px solid rgba(99, 102, 241, 0.3);
        background: 
            linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(59, 130, 246, 0.12)),
            #ffffff;
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: #6366f1;
        text-transform: uppercase;
        box-shadow: 
            0 8px 24px rgba(99, 102, 241, 0.15),
            inset 0 1px 2px rgba(255, 255, 255, 0.8);
        margin-bottom: 16px;
        transition: all 0.4s ease;
    }
    
    .spx-pill:hover {
        transform: scale(1.08) translateY(-2px);
        box-shadow: 
            0 12px 36px rgba(99, 102, 241, 0.25),
            inset 0 1px 3px rgba(255, 255, 255, 1);
        border-color: rgba(99, 102, 241, 0.5);
    }
    
    .spx-pill::before {
        content: '◆';
        font-size: 0.9rem;
        color: #6366f1;
        animation: badgeGlow 2s ease-in-out infinite;
    }
    
    @keyframes badgeGlow {
        0%, 100% { filter: brightness(1); }
        50% { filter: brightness(1.5); }
    }
    
    .spx-sub {
        color: #475569;
        font-size: 1.05rem;
        line-height: 1.7;
        font-weight: 400;
    }
    
    /* === STUNNING SECTION HEADERS === */
    .section-header {
        font-size: 1.8rem;
        font-weight: 800;
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 3rem 0 1.5rem 0;
        padding-bottom: 1rem;
        border-bottom: 3px solid transparent;
        border-image: linear-gradient(90deg, #6366f1, #3b82f6, transparent) 1;
        display: flex;
        align-items: center;
        gap: 14px;
        position: relative;
    }
    
    .section-header::before {
        content: '';
        width: 14px;
        height: 14px;
        border-radius: 999px;
        background: linear-gradient(135deg, #6366f1, #3b82f6);
        box-shadow: 
            0 0 20px rgba(99, 102, 241, 0.6),
            0 4px 12px rgba(99, 102, 241, 0.3);
        animation: headerPulse 2s ease-in-out infinite;
    }
    
    @keyframes headerPulse {
        0%, 100% { transform: scale(1); box-shadow: 0 0 20px rgba(99, 102, 241, 0.6); }
        50% { transform: scale(1.2); box-shadow: 0 0 30px rgba(99, 102, 241, 0.9); }
    }
    
    /* === DRAMATIC METRICS === */
    .spx-metric {
        position: relative;
        padding: 32px 28px;
        border-radius: 24px;
        background: 
            radial-gradient(circle at top left, rgba(99, 102, 241, 0.12), transparent 70%),
            linear-gradient(135deg, #ffffff, #fefeff);
        border: 2px solid rgba(99, 102, 241, 0.25);
        box-shadow: 
            0 24px 60px rgba(99, 102, 241, 0.12),
            0 12px 30px rgba(0, 0, 0, 0.05),
            inset 0 2px 4px rgba(255, 255, 255, 0.9);
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
        background: linear-gradient(90deg, #6366f1, #3b82f6, #06b6d4);
        transform: scaleX(0);
        transform-origin: left;
        transition: transform 0.6s ease;
    }
    
    .spx-metric:hover {
        transform: translateY(-6px) scale(1.02);
        border-color: rgba(99, 102, 241, 0.5);
        box-shadow: 
            0 36px 80px rgba(99, 102, 241, 0.2),
            0 18px 40px rgba(99, 102, 241, 0.12),
            inset 0 2px 6px rgba(255, 255, 255, 1);
    }
    
    .spx-metric:hover::before {
        transform: scaleX(1);
    }
    
    .spx-metric-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        color: #64748b;
        font-weight: 700;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .spx-metric-label::before {
        content: '●';
        color: #6366f1;
        font-size: 0.6rem;
        text-shadow: 0 0 8px rgba(99, 102, 241, 0.8);
    }
    
    .spx-metric-value {
        font-size: 2.2rem;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #1e293b 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.03em;
    }
    
    /* === EPIC BUTTONS === */
    .stButton>button, .stDownloadButton>button {
        background: linear-gradient(135deg, #6366f1 0%, #3b82f6 50%, #06b6d4 100%);
        color: #ffffff;
        border-radius: 100px;
        border: none;
        padding: 16px 36px;
        font-weight: 800;
        font-size: 1rem;
        letter-spacing: 0.08em;
        box-shadow: 
            0 16px 40px rgba(99, 102, 241, 0.3),
            0 8px 20px rgba(0, 0, 0, 0.1),
            inset 0 1px 2px rgba(255, 255, 255, 0.3);
        cursor: pointer;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        text-transform: uppercase;
        position: relative;
        overflow: hidden;
    }
    
    .stButton>button::before, .stDownloadButton>button::before {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 0;
        height: 0;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.3);
        transform: translate(-50%, -50%);
        transition: width 0.6s, height 0.6s;
    }
    
    .stButton>button:hover::before, .stDownloadButton>button:hover::before {
        width: 400px;
        height: 400px;
    }
    
    .stButton>button:hover, .stDownloadButton>button:hover {
        transform: translateY(-4px) scale(1.05);
        box-shadow: 
            0 24px 56px rgba(99, 102, 241, 0.4),
            0 12px 28px rgba(99, 102, 241, 0.2),
            inset 0 1px 3px rgba(255, 255, 255, 0.4);
    }
    
    .stButton>button:active, .stDownloadButton>button:active {
        transform: translateY(-2px) scale(1.03);
    }
    
    /* === BEAUTIFUL INPUTS === */
    .stNumberInput>div>div>input,
    .stTimeInput>div>div>input {
        background: #ffffff !important;
        border: 2px solid rgba(99, 102, 241, 0.25) !important;
        border-radius: 16px !important;
        color: #0f172a !important;
        padding: 14px 18px !important;
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        font-family: 'JetBrains Mono', monospace !important;
        box-shadow: 
            0 4px 16px rgba(99, 102, 241, 0.08),
            inset 0 1px 2px rgba(255, 255, 255, 0.8) !important;
        transition: all 0.3s ease !important;
    }
    
    .stNumberInput>div>div>input:focus,
    .stTimeInput>div>div>input:focus {
        border-color: #6366f1 !important;
        box-shadow: 
            0 0 0 4px rgba(99, 102, 241, 0.15),
            0 8px 24px rgba(99, 102, 241, 0.2) !important;
        background: #fefeff !important;
    }
    
    /* === STUNNING RADIO === */
    .stRadio>div {
        gap: 16px;
    }
    
    .stRadio>div>label {
        background: #ffffff;
        padding: 14px 28px;
        border-radius: 100px;
        border: 2px solid rgba(99, 102, 241, 0.25);
        font-size: 1rem;
        font-weight: 600;
        color: #475569;
        box-shadow: 0 4px 16px rgba(99, 102, 241, 0.08);
        transition: all 0.3s ease;
    }
    
    .stRadio>div>label:hover {
        background: #fefeff;
        border-color: rgba(99, 102, 241, 0.4);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(99, 102, 241, 0.15);
    }
    
    .stRadio>div>label[data-selected="true"] {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(59, 130, 246, 0.12));
        border-color: #6366f1;
        color: #6366f1;
        box-shadow: 
            0 8px 32px rgba(99, 102, 241, 0.2),
            inset 0 1px 2px rgba(255, 255, 255, 0.8);
        transform: translateY(-2px);
    }
    
    /* === PREMIUM TABS === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background: 
            linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(250, 250, 255, 0.95));
        padding: 10px;
        border-radius: 100px;
        border: 2px solid rgba(99, 102, 241, 0.2);
        box-shadow: 
            0 12px 36px rgba(99, 102, 241, 0.1),
            inset 0 1px 2px rgba(255, 255, 255, 0.8);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 100px;
        color: #64748b;
        font-weight: 700;
        font-size: 1rem;
        padding: 12px 28px;
        border: none;
        transition: all 0.3s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(99, 102, 241, 0.08);
        color: #6366f1;
        transform: translateY(-2px);
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #6366f1, #3b82f6);
        color: #ffffff;
        box-shadow: 
            0 8px 24px rgba(99, 102, 241, 0.3),
            inset 0 1px 2px rgba(255, 255, 255, 0.3);
        transform: translateY(-2px);
    }
    
    /* === STUNNING DATAFRAMES === */
    .stDataFrame {
        border-radius: 24px;
        overflow: hidden;
        box-shadow:
            0 24px 60px rgba(99, 102, 241, 0.12),
            0 12px 30px rgba(0, 0, 0, 0.05);
        border: 2px solid rgba(99, 102, 241, 0.2);
    }
    
    .stDataFrame div[data-testid="StyledTable"] {
        font-variant-numeric: tabular-nums;
        font-size: 0.98rem;
        font-family: 'JetBrains Mono', monospace;
        background: #ffffff;
    }
    
    .stDataFrame thead tr th {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.12), rgba(59, 130, 246, 0.12)) !important;
        color: #6366f1 !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        font-size: 0.8rem !important;
        padding: 16px 12px !important;
        border-bottom: 2px solid rgba(99, 102, 241, 0.3) !important;
    }
    
    .stDataFrame tbody tr {
        transition: all 0.2s ease;
    }
    
    .stDataFrame tbody tr:hover {
        background: rgba(99, 102, 241, 0.05) !important;
        transform: scale(1.01);
    }
    
    .stDataFrame tbody tr td {
        padding: 14px 12px !important;
        border-bottom: 1px solid rgba(226, 232, 240, 0.8) !important;
        color: #1e293b !important;
        font-weight: 500 !important;
    }
    
    /* === COLORFUL MESSAGES === */
    .stSuccess {
        background: 
            linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(5, 150, 105, 0.10)),
            #ffffff;
        border-radius: 20px;
        border: 2px solid rgba(16, 185, 129, 0.3);
        padding: 20px 28px;
        color: #047857;
        font-size: 1rem;
        font-weight: 500;
        box-shadow: 
            0 12px 36px rgba(16, 185, 129, 0.12),
            inset 0 1px 2px rgba(255, 255, 255, 0.8);
    }
    
    .stWarning {
        background: 
            linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(217, 119, 6, 0.10)),
            #ffffff;
        border-radius: 20px;
        border: 2px solid rgba(245, 158, 11, 0.3);
        padding: 20px 28px;
        color: #d97706;
        font-size: 1rem;
        font-weight: 500;
        box-shadow: 
            0 12px 36px rgba(245, 158, 11, 0.12),
            inset 0 1px 2px rgba(255, 255, 255, 0.8);
    }
    
    .stInfo {
        background: 
            linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(37, 99, 235, 0.10)),
            #ffffff;
        border-radius: 20px;
        border: 2px solid rgba(59, 130, 246, 0.3);
        padding: 20px 28px;
        color: #2563eb;
        font-size: 1rem;
        font-weight: 500;
        box-shadow: 
            0 12px 36px rgba(59, 130, 246, 0.12),
            inset 0 1px 2px rgba(255, 255, 255, 0.8);
    }
    
    .muted {
        color: #475569;
        font-size: 1rem;
        line-height: 1.7;
        padding: 20px 24px;
        background: 
            linear-gradient(135deg, rgba(148, 163, 184, 0.08), rgba(100, 116, 139, 0.06)),
            #ffffff;
        border-left: 4px solid #6366f1;
        border-radius: 12px;
        margin: 20px 0;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.03);
    }
    
    /* === SELECTBOX === */
    .stSelectbox>div>div {
        background: #ffffff;
        border: 2px solid rgba(99, 102, 241, 0.25);
        border-radius: 16px;
        box-shadow: 0 4px 16px rgba(99, 102, 241, 0.08);
        font-size: 1.05rem;
        transition: all 0.3s ease;
    }
    
    .stSelectbox>div>div:hover {
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 8px 24px rgba(99, 102, 241, 0.15);
    }
    
    /* === LABELS === */
    label {
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        color: #475569 !important;
        margin-bottom: 6px !important;
    }
    
    /* === SCROLLBAR === */
    ::-webkit-scrollbar {
        width: 12px;
        height: 12px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(241, 245, 249, 0.8);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #6366f1, #3b82f6);
        border-radius: 10px;
        border: 2px solid rgba(241, 245, 249, 0.8);
        box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #4f46e5, #2563eb);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }
    
    /* === FOOTER === */
    .app-footer {
        margin-top: 4rem;
        padding-top: 2rem;
        border-top: 2px solid rgba(99, 102, 241, 0.2);
        text-align: center;
        color: #64748b;
        font-size: 1rem;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def hero():
    st.markdown(
        f"""
        <div class="hero-header">
            <div class="status-indicator">System Active ✓</div>
            <h1 class="hero-title">{APP_NAME}</h1>
            <p class="hero-subtitle">{TAGLINE}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


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


def metric_card(label: str, value: str):
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
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Top Rail": round(top, 4),
                "Bottom Rail": round(bottom, 4),
            }
        )
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
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Contract Reference": round(price, 4),
            }
        )
    df = pd.DataFrame(rows)
    return df, round(slope, 6)


# ===============================
# DAILY FORESIGHT HELPERS
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

    with st.sidebar:
        st.markdown(f"### {APP_NAME}")
        st.markdown(
            f"<span class='spx-sub' style='font-size:1.05rem;'>{TAGLINE}</span>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        st.markdown("#### ⚡ Core Slope")
        st.write(f"SPX rail slope magnitude: **{SLOPE_MAG} pts / 30 min**")
        st.write(f"Contract factor (TP): **{CONTRACT_FACTOR:.2f} × channel height**")
        st.caption("All calculations use a uniform 30-minute grid.")

        st.markdown("---")
        st.markdown("#### 📋 Notes")
        st.caption(
            "Underlying maintenance: 16:00–17:00 CT\n\n"
            "Contracts maintenance: 16:00–19:00 CT\n\n"
            "RTH projection window: 08:30–14:30 CT."
        )

    hero()

    tabs = st.tabs(
        [
            "🧱 SPX Channel Setup",
            "📐 Contract Slope Setup",
            "🔮 Daily Foresight Card",
            "ℹ️ About",
        ]
    )

    # TAB 1 — CHANNEL SETUP
    with tabs[0]:
        card(
            "SPX Channel Setup",
            "Define your engulfing pivots, pick the channel direction, and project parallel rails across the session.",
            badge="Rails Engine",
            icon="🧱",
        )

        section_header("⚙️ Pivots Configuration")
        st.markdown(
            "<p class='spx-sub' style='margin-bottom:24px;'>"
            "Choose the highest and lowest engulfing reversals you trust between 15:00 and 07:30 CT."
            "</p>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("#### 📈 High Pivot")
            high_price = st.number_input(
                "High pivot price",
                value=5200.0,
                step=0.25,
                key="pivot_high_price",
            )
            high_time = st.time_input(
                "High pivot time (CT)",
                value=dtime(19, 30),
                step=1800,
                key="pivot_high_time",
            )
        with c2:
            st.markdown("#### 📉 Low Pivot")
            low_price = st.number_input(
                "Low pivot price",
                value=5100.0,
                step=0.25,
                key="pivot_low_price",
            )
            low_time = st.time_input(
                "Low pivot time (CT)",
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
            if st.button(
                "⚡ Build Channel",
                key="build_channel_btn",
                use_container_width=True,
            ):
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

                st.success(
                    "✨ Channel generated successfully! Review the tables and the Daily Foresight tab."
                )

        df_asc = st.session_state.get("channel_asc_df")
        df_desc = st.session_state.get("channel_desc_df")
        h_asc = st.session_state.get("channel_asc_height")
        h_desc = st.session_state.get("channel_desc_height")

        section_header("📊 Channel Projections • RTH 08:30–14:30 CT")

        if df_asc is None and df_desc is None:
            st.info("📊 Build at least one channel to view projections.")
        else:
            if df_asc is not None:
                st.markdown(
                    "<h4 style='font-size:1.4rem; margin:20px 0;'>📈 Ascending Channel</h4>",
                    unsafe_allow_html=True,
                )
                c_top = st.columns([3, 1], gap="large")
                with c_top[0]:
                    st.dataframe(
                        df_asc,
                        use_container_width=True,
                        hide_index=True,
                        height=400,
                    )
                with c_top[1]:
                    st.markdown(
                        metric_card("Channel Height", f"{h_asc:.2f} pts"),
                        unsafe_allow_html=True,
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "📥 Download CSV",
                        df_asc.to_csv(index=False).encode(),
                        "spx_ascending_rails.csv",
                        "text/csv",
                        key="dl_asc_channel",
                        use_container_width=True,
                    )

            if df_desc is not None:
                st.markdown(
                    "<h4 style='font-size:1.4rem; margin:28px 0 20px;'>📉 Descending Channel</h4>",
                    unsafe_allow_html=True,
                )
                c_bot = st.columns([3, 1], gap="large")
                with c_bot[0]:
                    st.dataframe(
                        df_desc,
                        use_container_width=True,
                        hide_index=True,
                        height=400,
                    )
                with c_bot[1]:
                    st.markdown(
                        metric_card("Channel Height", f"{h_desc:.2f} pts"),
                        unsafe_allow_html=True,
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.download_button(
                        "📥 Download CSV",
                        df_desc.to_csv(index=False).encode(),
                        "spx_descending_rails.csv",
                        "text/csv",
                        key="dl_desc_channel",
                        use_container_width=True,
                    )

        end_card()

    # TAB 2 — CONTRACT SLOPE SETUP
    with tabs[1]:
        card(
            "Contract Slope Setup",
            "Use two contract prices to define a simple line on the same time grid as the rails.",
            badge="Contract Engine",
            icon="📐",
        )

        ph_time: dtime = st.session_state.get("pivot_high_time", dtime(15, 0))
        pl_time: dtime = st.session_state.get("pivot_low_time", dtime(3, 0))

        section_header("⚓ Anchor A — Contract Origin")
        anchor_a_source = st.radio(
            "Use which time for Anchor A",
            ["High pivot time", "Low pivot time", "Custom time"],
            index=0,
            key="contract_anchor_a_source",
            horizontal=True,
        )

        if anchor_a_source == "High pivot time":
            anchor_a_time = ph_time
            st.markdown(
                f"<div class='muted'>✓ Anchor A time set to high pivot time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT</div>",
                unsafe_allow_html=True,
            )
        elif anchor_a_source == "Low pivot time":
            anchor_a_time = pl_time
            st.markdown(
                f"<div class='muted'>✓ Anchor A time set to low pivot time: <b>{anchor_a_time.strftime('%H:%M')}</b> CT</div>",
                unsafe_allow_html=True,
            )
        else:
            anchor_a_time = st.time_input(
                "Custom Anchor A time (CT)",
                value=dtime(1, 0),
                step=1800,
                key="contract_anchor_a_time_custom",
            )

        anchor_a_price = st.number_input(
            "Contract price at Anchor A time",
            value=10.0,
            step=0.1,
            key="contract_anchor_a_price",
        )

        section_header("⚓ Anchor B — Second Contract Point")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            anchor_b_time = st.time_input(
                "Anchor B time (CT)",
                value=dtime(7, 30),
                step=1800,
                key="contract_anchor_b_time",
            )
        with c2:
            anchor_b_price = st.number_input(
                "Contract price at Anchor B time",
                value=8.0,
                step=0.1,
                key="contract_anchor_b_price",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        col_btn = st.columns([1, 3])[0]
        with col_btn:
            if st.button(
                "⚡ Build Contract",
                key="build_contract_btn",
                use_container_width=True,
            ):
                try:
                    df_contract, slope_contract = build_contract_projection(
                        anchor_a_time=anchor_a_time,
                        anchor_a_price=anchor_a_price,
                        anchor_b_time=anchor_b_time,
                        anchor_b_price=anchor_b_price,
                    )
                    st.session_state["contract_df"] = df_contract
                    st.session_state["contract_slope"] = slope_contract
                    st.success(
                        "✨ Contract projection generated successfully! Review the table and Daily Foresight tab."
                    )
                except Exception as e:
                    st.error(f"Error generating contract projection: {e}")

        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        section_header("📊 Contract Projection • RTH 08:30–14:30 CT")

        if df_contract is None:
            st.info("📊 Build a contract projection to see projected prices.")
        else:
            c_top = st.columns([3, 1], gap="large")
            with c_top[0]:
                st.dataframe(
                    df_contract,
                    use_container_width=True,
                    hide_index=True,
                    height=400,
                )
            with c_top[1]:
                st.markdown(
                    metric_card("Contract Slope", f"{slope_contract:+.4f} / 30m"),
                    unsafe_allow_html=True,
                )
                st.markdown("<br>", unsafe_allow_html=True)
                st.download_button(
                    "📥 Download CSV",
                    df_contract.to_csv(index=False).encode(),
                    "contract_projection.csv",
                    "text/csv",
                    key="dl_contract",
                    use_container_width=True,
                )

        end_card()

    # TAB 3 — DAILY FORESIGHT CARD
    with tabs[2]:
        card(
            "Daily Foresight Card",
            "Rails and contract line combined into a simple time-based playbook.",
            badge="Foresight",
            icon="🔮",
        )

        df_mode, df_ch, h_ch = get_active_channel()
        df_contract = st.session_state.get("contract_df")
        slope_contract = st.session_state.get("contract_slope")

        if df_ch is None or h_ch is None:
            st.warning(
                "⚠️ No active channel found. Build a channel in the SPX Channel Setup tab first."
            )
            end_card()
        elif df_contract is None or slope_contract is None:
            st.warning(
                "⚠️ No contract projection found. Build one in the Contract Slope Setup tab first."
            )
            end_card()
        else:
            # Merge channel and contract on time
            merged = df_ch.merge(df_contract, on="Time", how="left")

            # Factor-based expectation
            target_contract_move = CONTRACT_FACTOR * h_ch

            # Add panoramic columns
            merged["Channel Height"] = round(h_ch, 2)
            merged["Expected Contract Move"] = round(target_contract_move, 2)
            merged["Long TP Contract"] = merged["Contract Reference"] + target_contract_move
            merged["Short TP Contract"] = merged["Contract Reference"] - target_contract_move

            section_header("📊 Structure Summary")
            c1, c2, c3 = st.columns(3, gap="large")
            with c1:
                st.markdown(
                    metric_card("Active Channel", df_mode or "Not set"),
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    metric_card("Channel Height", f"{h_ch:.2f} pts"),
                    unsafe_allow_html=True,
                )
            with c3:
                st.markdown(
                    metric_card(
                        "Target Contract Move", f"{target_contract_move:.2f} units"
                    ),
                    unsafe_allow_html=True,
                )

            section_header("📈 Inside Channel Play")
            st.markdown(
                f"""
                <div class='spx-sub' style='font-size:1.05rem; line-height:1.8;'>
                  <p><strong style='color:#6366f1; font-size:1.15rem;'>🟢 Long Idea</strong> → Buy at the lower rail, exit at the upper rail</p>
                  <ul style='margin-left:24px;'>
                    <li>Underlying move: about <strong style='color:#10b981;'>{h_ch:.2f} points</strong> in your favor</li>
                    <li>Conservative contract target for that full swing: about <strong style='color:#10b981;'>{target_contract_move:.2f} units</strong> from the entry level</li>
                  </ul>

                  <p><strong style='color:#6366f1; font-size:1.15rem;'>🔴 Short Idea</strong> → Buy a put at the upper rail, exit at the lower rail</p>
                  <ul style='margin-left:24px;'>
                    <li>Underlying move: about <strong style='color:#ef4444;'>{h_ch:.2f} points</strong> in your favor, opposite direction</li>
                    <li>Same structural contract move size, in the opposite direction</li>
                  </ul>

                  <p style='margin-top:16px; color:#64748b;'><em>The factor {CONTRACT_FACTOR:.2f} is a structural take-profit guide. Real option moves can be larger because of volatility and time, but this keeps you disciplined.</em></p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("💥 Breakout and Breakdown Ideas")
            st.markdown(
                f"""
                <div class='spx-sub' style='font-size:1.05rem; line-height:1.8;'>
                  <p><strong style='color:#6366f1; font-size:1.15rem;'>🚀 Breakout Above Upper Rail</strong></p>
                  <ul style='margin-left:24px;'>
                    <li>Entry on clean retest of the upper rail from above</li>
                    <li>Continuation target on SPX: roughly one additional channel height beyond that rail</li>
                    <li>Contract TP: your entry price on the breakout plus about <strong>{target_contract_move:.2f}</strong> units</li>
                  </ul>

                  <p><strong style='color:#6366f1; font-size:1.15rem;'>⬇️ Breakdown Below Lower Rail</strong></p>
                  <ul style='margin-left:24px;'>
                    <li>Entry on clean retest of the lower rail from below</li>
                    <li>Continuation target on SPX: roughly one additional channel height below that rail</li>
                    <li>Contract TP: your entry price on the breakdown minus about <strong>{target_contract_move:.2f}</strong> units</li>
                  </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

            section_header("🧮 Contract Trade Estimator")

            times = merged["Time"].tolist()
            if times:
                col_e, col_x = st.columns(2, gap="large")
                with col_e:
                    entry_time = st.selectbox(
                        "Entry time when the rail is touched",
                        times,
                        index=0,
                        key="foresight_entry_time",
                    )
                with col_x:
                    exit_time = st.selectbox(
                        "Exit time",
                        times,
                        index=min(len(times) - 1, 4),
                        key="foresight_exit_time",
                    )

                entry_row = merged[merged["Time"] == entry_time].iloc[0]
                exit_row = merged[merged["Time"] == exit_time].iloc[0]
                entry_contract = float(entry_row["Contract Reference"])
                exit_contract = float(exit_row["Contract Reference"])
                pnl_contract = exit_contract - entry_contract

                c1_est, c2_est, c3_est = st.columns(3, gap="large")
                with c1_est:
                    st.markdown(
                        metric_card("Entry Contract (structural)", f"{entry_contract:.2f}"),
                        unsafe_allow_html=True,
                    )
                with c2_est:
                    st.markdown(
                        metric_card("Exit Contract (structural)", f"{exit_contract:.2f}"),
                        unsafe_allow_html=True,
                    )
                with c3_est:
                    st.markdown(
                        metric_card("Projected P&L", f"{pnl_contract:+.2f} units"),
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    "<div class='muted'><strong>💡 How to use this estimator:</strong> "
                    "Pick the time you expect the rail touch to happen as your entry, "
                    "pick your planned exit time, and compare this projected contract move with what the market actually gave you. "
                    "The difference is your volatility and skew bonus for that day.</div>",
                    unsafe_allow_html=True,
                )

            section_header("🗺️ Time-Aligned Map")
            st.caption(
                "Every row is a 30-minute slot in RTH. If SPX tags a rail at that time, this table shows the structural contract level and take-profit bands."
            )

            # Order columns for panoramic view
            cols_order = [
                "Time",
                "Top Rail",
                "Bottom Rail",
                "Contract Reference",
                "Long TP Contract",
                "Short TP Contract",
                "Channel Height",
                "Expected Contract Move",
            ]
            existing_cols = [c for c in cols_order if c in merged.columns]
            st.dataframe(
                merged[existing_cols],
                use_container_width=True,
                hide_index=True,
                height=480,
            )

            st.markdown(
                "<div class='muted'><strong>📖 Reading the map:</strong> "
                "The grid does not tell you <em>when</em> the tag will happen. "
                "It tells you what your structure expects the contract to be worth "
                "and where a disciplined TP should sit if the tag happens at a given time.</div>",
                unsafe_allow_html=True,
            )

            end_card()

    # TAB 4 — ABOUT
    with tabs[3]:
        card("About SPX Prophet", TAGLINE, badge="Version • Rails + Foresight", icon="ℹ️")
        st.markdown(
            f"""
            <div class='spx-sub' style='font-size:1.08rem; line-height:1.8;'>
            <p>SPX Prophet is built on a simple idea:</p>

            <p style='font-size:1.2rem; color:#6366f1; font-weight:600; margin:20px 0;'>
            Two pivots define the rails and the slope carries that structure into the session.
            </p>

            <ul style='margin-left:24px; font-size:1.05rem;'>
                <li>Rails are projected with a <strong style='color:#6366f1;'>uniform slope of ±{SLOPE_MAG} points per 30 minutes</strong></li>
                <li>Pivots are <strong style='color:#6366f1;'>engulfing reversals</strong> chosen by you between 15:00 and 07:30 CT</li>
                <li>Channels can be viewed as <strong style='color:#6366f1;'>ascending, descending, or inspected both ways</strong></li>
                <li>Contracts follow a straight line defined by <strong style='color:#6366f1;'>two anchor prices</strong> on the same time grid</li>
                <li>Take profit on the option is normalised with a <strong style='color:#6366f1;'>contract factor of {CONTRACT_FACTOR:.2f} × channel height</strong></li>
            </ul>

            <p style='margin-top:24px;'>
            The app is not trying to be a full options model. It gives you a clean structural map so that 
            when price returns to your rails, you already know where the contract <em>should</em> be and where you will take profit.
            </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='muted'><strong>🔧 Maintenance windows:</strong> "
            "SPX 16:00–17:00 CT. Contracts 16:00–19:00 CT.</div>",
            unsafe_allow_html=True,
        )
        end_card()

    st.markdown(
        "<div class='app-footer'>© 2025 SPX Prophet • Where Structure Becomes Foresight.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()