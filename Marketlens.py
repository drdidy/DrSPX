# app.py
# SPX PROPHET — Institutional-Grade Market Projection Platform
# Premium dual-anchor projection system with advanced analytics
# Precision: ±0.5412 per 30-min block | RTH: 08:30-14:00 CT

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List, Tuple

APP_NAME = "SPX PROPHET"
APP_VERSION = "Professional Edition 2.0"
APP_TAGLINE = "Institutional Market Projection Platform"

# ===============================
# THEME — Ultra Premium
# ===============================

def theme_css(mode: str):
    if mode == "Dark":
        p = {
            "bg": "#000000",
            "bgPattern": "radial-gradient(circle at 20% 50%, rgba(0, 255, 136, 0.03) 0%, transparent 50%), radial-gradient(circle at 80% 50%, rgba(0, 212, 255, 0.03) 0%, transparent 50%)",
            "surface": "#0a0a0a",
            "surfaceElevated": "#141414",
            "surfaceHover": "#1a1a1a",
            "text": "#ffffff",
            "textPrimary": "#f5f5f5",
            "textSecondary": "#a3a3a3",
            "textTertiary": "#737373",
            "textMuted": "#525252",
            "primary": "#00ff88",
            "primaryDark": "#00cc6a",
            "primaryLight": "#33ffaa",
            "accent": "#00d4ff",
            "accentDark": "#00a8cc",
            "accentLight": "#33ddff",
            "border": "#1f1f1f",
            "borderLight": "#2a2a2a",
            "borderAccent": "#333333",
            "success": "#10b981",
            "error": "#ef4444",
            "warning": "#f59e0b",
            "info": "#3b82f6",
        }
    else:
        p = {
            "bg": "#ffffff",
            "bgPattern": "radial-gradient(circle at 20% 50%, rgba(0, 179, 102, 0.02) 0%, transparent 50%), radial-gradient(circle at 80% 50%, rgba(0, 153, 204, 0.02) 0%, transparent 50%)",
            "surface": "#fafafa",
            "surfaceElevated": "#ffffff",
            "surfaceHover": "#f5f5f5",
            "text": "#0a0a0a",
            "textPrimary": "#171717",
            "textSecondary": "#525252",
            "textTertiary": "#737373",
            "textMuted": "#a3a3a3",
            "primary": "#00b366",
            "primaryDark": "#008f51",
            "primaryLight": "#00d47a",
            "accent": "#0099cc",
            "accentDark": "#007aa3",
            "accentLight": "#00b8e6",
            "border": "#e5e5e5",
            "borderLight": "#f0f0f0",
            "borderAccent": "#d4d4d4",
            "success": "#10b981",
            "error": "#ef4444",
            "warning": "#f59e0b",
            "info": "#3b82f6",
        }
    
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');
    
    * {{
        margin: 0;
        padding: 0;
        box-sizing: border-box;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }}
    
    html, body, [data-testid="stAppViewContainer"] {{
        background: {p['bg']};
        background-image: {p['bgPattern']};
        color: {p['text']};
        font-size: 16px;
    }}
    
    #MainMenu, footer, header {{visibility: hidden;}}
    
    /* ==================== SIDEBAR ==================== */
    [data-testid="stSidebar"] {{
        background: {p['surface']};
        border-right: 1px solid {p['border']};
        box-shadow: 8px 0 40px rgba(0, 0, 0, 0.04);
    }}
    
    [data-testid="stSidebar"] > div {{
        padding: 2.5rem 1.5rem;
    }}
    
    .sidebar-brand {{
        text-align: center;
        padding: 0 0 2rem 0;
        border-bottom: 1px solid {p['border']};
        margin-bottom: 2rem;
    }}
    
    .sidebar-logo {{
        font-size: 1.75rem;
        font-weight: 900;
        background: linear-gradient(135deg, {p['primary']}, {p['accent']});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 0.02em;
    }}
    
    .sidebar-version {{
        font-size: 0.625rem;
        color: {p['textMuted']};
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 0.5rem;
    }}
    
    .sidebar-divider {{
        height: 1px;
        background: linear-gradient(90deg, transparent, {p['border']}, transparent);
        margin: 1.5rem 0;
    }}
    
    .sidebar-section {{
        margin-bottom: 2rem;
    }}
    
    .sidebar-heading {{
        font-size: 0.688rem;
        font-weight: 800;
        color: {p['textTertiary']};
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }}
    
    .metric-card {{
        background: {p['surfaceElevated']};
        border: 1px solid {p['border']};
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 0.75rem;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    
    .metric-card:hover {{
        border-color: {p['primary']};
        box-shadow: 0 0 0 3px {p['primary']}15;
        transform: translateY(-1px);
    }}
    
    .metric-header {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.75rem;
    }}
    
    .metric-icon {{
        font-size: 1.5rem;
    }}
    
    .metric-label {{
        font-size: 0.688rem;
        font-weight: 700;
        color: {p['textTertiary']};
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}
    
    .metric-value {{
        font-size: 1.875rem;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        line-height: 1;
        background: linear-gradient(135deg, {p['primary']}, {p['accent']});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    
    .metric-sublabel {{
        font-size: 0.625rem;
        color: {p['textMuted']};
        margin-top: 0.375rem;
        font-weight: 500;
    }}
    
    .info-item {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.625rem 0;
        font-size: 0.75rem;
        color: {p['textSecondary']};
        border-bottom: 1px solid {p['borderLight']};
    }}
    
    .info-item:last-child {{
        border-bottom: none;
    }}
    
    .info-icon {{
        font-size: 1rem;
    }}
    
    /* ==================== HEADER ==================== */
    .app-header {{
        text-align: center;
        padding: 4rem 0 3rem 0;
        position: relative;
        overflow: hidden;
    }}
    
    .app-header::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 100%;
        height: 100%;
        background: radial-gradient(ellipse at center, {p['primary']}08 0%, transparent 70%);
        pointer-events: none;
    }}
    
    .app-logo {{
        font-size: 4.5rem;
        font-weight: 900;
        letter-spacing: 0.08em;
        background: linear-gradient(135deg, {p['primary']} 0%, {p['accent']} 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        line-height: 1;
        position: relative;
        z-index: 1;
    }}
    
    .app-separator {{
        width: 140px;
        height: 4px;
        background: linear-gradient(90deg, transparent, {p['primary']}, {p['accent']}, transparent);
        margin: 1.5rem auto;
        border-radius: 2px;
    }}
    
    .app-tagline {{
        font-size: 1.125rem;
        color: {p['textSecondary']};
        font-weight: 500;
        letter-spacing: 0.02em;
    }}
    
    .app-version-badge {{
        display: inline-block;
        margin-top: 1rem;
        padding: 0.5rem 1.25rem;
        background: {p['surfaceElevated']};
        border: 1px solid {p['border']};
        border-radius: 100px;
        font-size: 0.688rem;
        font-weight: 700;
        color: {p['textTertiary']};
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }}
    
    /* ==================== CARDS ==================== */
    .premium-card {{
        background: {p['surfaceElevated']};
        border: 1px solid {p['border']};
        border-radius: 20px;
        margin-bottom: 2rem;
        overflow: hidden;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.02);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    
    .premium-card:hover {{
        box-shadow: 0 8px 48px rgba(0, 0, 0, 0.06);
        transform: translateY(-2px);
    }}
    
    .card-header {{
        background: {p['surface']};
        border-bottom: 1px solid {p['border']};
        padding: 1.75rem 2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    
    .card-title {{
        font-size: 1.5rem;
        font-weight: 800;
        color: {p['textPrimary']};
        display: flex;
        align-items: center;
        gap: 0.875rem;
    }}
    
    .card-icon {{
        font-size: 2rem;
        filter: grayscale(30%);
    }}
    
    .card-badge {{
        display: inline-flex;
        align-items: center;
        gap: 0.625rem;
        padding: 0.625rem 1.25rem;
        background: linear-gradient(135deg, {p['primary']}12, {p['accent']}12);
        border: 1px solid {p['borderAccent']};
        border-radius: 100px;
        font-size: 0.75rem;
        font-weight: 800;
        color: {p['primary']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    
    .card-body {{
        padding: 2rem;
    }}
    
    /* ==================== ANCHOR INPUTS ==================== */
    .anchor-container {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 2rem;
        margin-bottom: 2rem;
    }}
    
    .anchor-box {{
        background: {p['surface']};
        border: 2px solid {p['border']};
        border-radius: 16px;
        padding: 2rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }}
    
    .anchor-box::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 4px;
        background: linear-gradient(90deg, {p['primary']}, {p['accent']});
        opacity: 0;
        transition: opacity 0.3s ease;
    }}
    
    .anchor-box:hover {{
        border-color: {p['primary']};
        box-shadow: 0 0 0 4px {p['primary']}12, 0 8px 32px rgba(0, 0, 0, 0.08);
        transform: translateY(-2px);
    }}
    
    .anchor-box:hover::before {{
        opacity: 1;
    }}
    
    .anchor-header {{
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1.75rem;
        padding-bottom: 1.25rem;
        border-bottom: 1px solid {p['borderLight']};
    }}
    
    .anchor-number {{
        width: 56px;
        height: 56px;
        border-radius: 14px;
        background: linear-gradient(135deg, {p['primary']}, {p['accent']});
        color: #000000;
        font-size: 1.75rem;
        font-weight: 900;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 16px {p['primary']}30;
    }}
    
    .anchor-info {{
        flex: 1;
    }}
    
    .anchor-title {{
        font-size: 1.375rem;
        font-weight: 800;
        color: {p['textPrimary']};
        margin: 0 0 0.25rem 0;
    }}
    
    .anchor-subtitle {{
        font-size: 0.813rem;
        color: {p['textSecondary']};
        font-weight: 500;
    }}
    
    .projection-badges {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.75rem;
        margin-top: 1.5rem;
        padding-top: 1.5rem;
        border-top: 1px solid {p['borderLight']};
    }}
    
    .proj-badge {{
        padding: 0.875rem 1rem;
        border-radius: 10px;
        font-size: 0.813rem;
        font-weight: 700;
        text-align: center;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
    }}
    
    .proj-badge.up {{
        background: linear-gradient(135deg, {p['success']}15, {p['success']}08);
        color: {p['success']};
        border: 1px solid {p['success']}30;
    }}
    
    .proj-badge.down {{
        background: linear-gradient(135deg, {p['error']}15, {p['error']}08);
        color: {p['error']};
        border: 1px solid {p['error']}30;
    }}
    
    /* ==================== INPUTS ==================== */
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input,
    .stTimeInput > div > div > input {{
        background: {p['surfaceElevated']};
        border: 1.5px solid {p['border']};
        border-radius: 10px;
        padding: 1rem 1.125rem;
        font-size: 1.063rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        color: {p['textPrimary']};
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    
    .stNumberInput > div > div > input:hover,
    .stDateInput > div > div > input:hover,
    .stTimeInput > div > div > input:hover {{
        border-color: {p['borderAccent']};
        background: {p['surfaceHover']};
    }}
    
    .stNumberInput > div > div > input:focus,
    .stDateInput > div > div > input:focus,
    .stTimeInput > div > div > input:focus {{
        border-color: {p['primary']};
        box-shadow: 0 0 0 3px {p['primary']}15;
        outline: none;
        background: {p['surfaceElevated']};
    }}
    
    .stNumberInput label,
    .stDateInput label,
    .stTimeInput label {{
        font-size: 0.75rem;
        font-weight: 800;
        color: {p['textTertiary']};
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.625rem;
    }}
    
    /* ==================== BUTTONS ==================== */
    .stButton > button,
    .stDownloadButton > button {{
        background: linear-gradient(135deg, {p['primary']}, {p['accent']});
        color: #000000;
        border: none;
        border-radius: 12px;
        padding: 1.125rem 2rem;
        font-weight: 900;
        font-size: 0.938rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        width: 100%;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 16px {p['primary']}25;
        cursor: pointer;
    }}
    
    .stButton > button:hover,
    .stDownloadButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 32px {p['primary']}35, 0 0 64px {p['primary']}20;
    }}
    
    .stButton > button:active,
    .stDownloadButton > button:active {{
        transform: translateY(0);
    }}
    
    /* ==================== ALERT BANNER ==================== */
    .alert-banner {{
        background: linear-gradient(135deg, {p['primary']}08, {p['accent']}08);
        border: 1px solid {p['borderAccent']};
        border-left: 4px solid {p['primary']};
        border-radius: 14px;
        padding: 1.5rem 2rem;
        margin-bottom: 3rem;
        display: flex;
        align-items: flex-start;
        gap: 1.25rem;
    }}
    
    .alert-icon {{
        font-size: 1.75rem;
        margin-top: 0.125rem;
    }}
    
    .alert-content {{
        flex: 1;
    }}
    
    .alert-title {{
        font-weight: 800;
        font-size: 1.063rem;
        color: {p['textPrimary']};
        margin-bottom: 0.5rem;
    }}
    
    .alert-text {{
        font-size: 0.938rem;
        color: {p['textSecondary']};
        line-height: 1.7;
    }}
    
    /* ==================== SUMMARY STATS ==================== */
    .stats-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1.25rem;
        margin-bottom: 2rem;
    }}
    
    .stat-box {{
        background: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: 14px;
        padding: 1.5rem;
        text-align: center;
        transition: all 0.2s ease;
    }}
    
    .stat-box:hover {{
        border-color: {p['borderAccent']};
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
        transform: translateY(-1px);
    }}
    
    .stat-label {{
        font-size: 0.688rem;
        font-weight: 800;
        color: {p['textTertiary']};
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.75rem;
    }}
    
    .stat-value {{
        font-size: 1.875rem;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        color: {p['textPrimary']};
        line-height: 1;
        margin-bottom: 0.5rem;
    }}
    
    .stat-change {{
        font-size: 0.813rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }}
    
    .stat-change.positive {{
        color: {p['success']};
    }}
    
    .stat-change.negative {{
        color: {p['error']};
    }}
    
    /* ==================== DATA TABLE ==================== */
    .table-wrapper {{
        border: 1px solid {p['border']};
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 2px 16px rgba(0, 0, 0, 0.03);
    }}
    
    .stDataFrame {{
        font-family: 'JetBrains Mono', monospace;
    }}
    
    .stDataFrame [data-testid="StyledTable"] {{
        font-variant-numeric: tabular-nums;
    }}
    
    .stDataFrame thead tr th {{
        background: {p['surface']};
        color: {p['textTertiary']};
        font-weight: 900;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        padding: 1.25rem 1.5rem;
        border-bottom: 2px solid {p['border']};
        position: sticky;
        top: 0;
        z-index: 10;
    }}
    
    .stDataFrame tbody tr td {{
        padding: 1.125rem 1.5rem;
        font-weight: 600;
        font-size: 1rem;
        border-bottom: 1px solid {p['borderLight']};
        transition: background 0.15s ease;
    }}
    
    .stDataFrame tbody tr:hover td {{
        background: {p['surfaceHover']};
    }}
    
    .stDataFrame tbody tr:last-child td {{
        border-bottom: none;
    }}
    
    /* ==================== FOOTER ==================== */
    .app-footer {{
        text-align: center;
        padding: 3.5rem 0;
        margin-top: 5rem;
        border-top: 1px solid {p['border']};
        color: {p['textMuted']};
        font-size: 0.813rem;
    }}
    
    .footer-brand {{
        font-weight: 800;
        color: {p['textPrimary']};
        font-size: 0.938rem;
    }}
    
    .footer-divider {{
        display: inline-block;
        margin: 0 0.75rem;
        color: {p['textMuted']};
    }}
    
    /* ==================== RADIO BUTTONS ==================== */
    [data-testid="stSidebar"] .stRadio > label {{
        font-size: 0.75rem;
        font-weight: 800;
        color: {p['textTertiary']};
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}
    
    /* ==================== SPACING ==================== */
    .block-container {{
        padding: 2.5rem 3rem;
        max-width: 1600px;
    }}
    
    /* ==================== RESPONSIVE ==================== */
    @media (max-width: 1200px) {{
        .stats-grid {{
            grid-template-columns: repeat(2, 1fr);
        }}
        
        .anchor-container {{
            grid-template-columns: 1fr;
        }}
    }}
    
    @media (max-width: 768px) {{
        .app-logo {{
            font-size: 3rem;
        }}
        
        .stats-grid {{
            grid-template-columns: 1fr;
        }}
    }}
    
    /* ==================== ANIMATIONS ==================== */
    @keyframes fadeInUp {{
        from {{
            opacity: 0;
            transform: translateY(20px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}
    
    .premium-card {{
        animation: fadeInUp 0.5s ease-out;
    }}
    
    /* ==================== UTILITIES ==================== */
    .gradient-text {{
        background: linear-gradient(135deg, {p['primary']}, {p['accent']});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}
    
    .text-mono {{
        font-family: 'JetBrains Mono', monospace;
    }}
    </style>
    """

def inject_theme(mode: str):
    st.markdown(theme_css(mode), unsafe_allow_html=True)

# ===============================
# TIME & CALCULATIONS
# ===============================

CT = pytz.timezone("America/Chicago")
ASC_SLOPE = 0.5412
DESC_SLOPE = -0.5412

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

# ===============================
# MAIN APPLICATION
# ===============================

def main():
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # ========== SIDEBAR ==========
    with st.sidebar:
        st.markdown(f"""
            <div class="sidebar-brand">
                <div class="sidebar-logo">{APP_NAME}</div>
                <div class="sidebar-version">{APP_VERSION}</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-heading">⚙️ THEME</div>', unsafe_allow_html=True)
        mode = st.radio("", ["Light", "Dark"], index=0, key="theme_mode", label_visibility="collapsed")
        inject_theme(mode)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-heading">📊 SLOPE VALUES</div>', unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-header'>
                    <div class='metric-icon'>📈</div>
                    <div class='metric-label'>Ascending</div>
                </div>
                <div class='metric-value'>+{ASC_SLOPE}</div>
                <div class='metric-sublabel'>per 30-minute block</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class='metric-card'>
                <div class='metric-header'>
                    <div class='metric-icon'>📉</div>
                    <div class='metric-label'>Descending</div>
                </div>
                <div class='metric-value'>{DESC_SLOPE}</div>
                <div class='metric-sublabel'>per 30-minute block</div>
            </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-heading">ℹ️ SYSTEM INFO</div>', unsafe_allow_html=True)
        st.markdown("""
            <div class='info-item'><span class='info-icon'>🕐</span> Central Time (CT) timezone</div>
            <div class='info-item'><span class='info-icon'>📊</span> RTH: 8:30 AM - 2:00 PM</div>
            <div class='info-item'><span class='info-icon'>⚠️</span> Excludes 4:00-5:00 PM maintenance</div>
            <div class='info-item'><span class='info-icon'>🎯</span> Dual anchor projection system</div>
            <div class='info-item'><span class='info-icon'>📈</span> 4 simultaneous projections</div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ========== HEADER ==========
    st.markdown(f"""
        <div class="app-header">
            <div class="app-logo">{APP_NAME}</div>
            <div class="app-separator"></div>
            <div class="app-tagline">{APP_TAGLINE}</div>
            <div class="app-version-badge">{APP_VERSION}</div>
        </div>
    """, unsafe_allow_html=True)
    
    # ========== ALERT BANNER ==========
    st.markdown("""
        <div class="alert-banner">
            <div class="alert-icon">💡</div>
            <div class="alert-content">
                <div class="alert-title">Dual Anchor Projection System</div>
                <div class="alert-text">
                    Configure two independent anchor points from the previous trading session. Each anchor automatically generates both ascending (+0.5412) and descending (−0.5412) projections across the RTH session (8:30 AM - 2:00 PM CT). The system intelligently excludes the 4:00-5:00 PM maintenance window from all calculations, ensuring precision accuracy.
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ========== CONFIGURATION CARD ==========
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown("""
        <div class="card-header">
            <div class="card-title">
                <span class="card-icon">⚙️</span>
                <span>Anchor Configuration</span>
            </div>
            <div class="card-badge">
                <span>⚡</span>
                <span>Dual System</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    
    # Projection Date
    st.markdown("<div style='margin-bottom: 2.5rem;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 0.75rem; font-weight: 800; color: #737373; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 1rem;'>📅 PROJECTION DATE</div>", unsafe_allow_html=True)
    proj_day = st.date_input("", value=datetime.now(CT).date(), key="proj_date", label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    # Anchors
    st.markdown('<div class="anchor-container">', unsafe_allow_html=True)
    
    # Anchor 1
    st.markdown("""
        <div class='anchor-box'>
            <div class='anchor-header'>
                <div class='anchor-number'>1</div>
                <div class='anchor-info'>
                    <div class='anchor-title'>Primary Anchor</div>
                    <div class='anchor-subtitle'>Generates bidirectional projections</div>
                </div>
            </div>
    """, unsafe_allow_html=True)
    
    a1_date = st.date_input("Anchor Date", value=datetime.now(CT).date() - timedelta(days=1), key="a1_date")
    a1_price = st.number_input("Anchor Price ($)", value=6634.70, step=0.01, key="a1_price", format="%.2f")
    a1_time = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="a1_time")
    
    st.markdown("""
            <div class='projection-badges'>
                <div class='proj-badge up'>↗ +0.5412</div>
                <div class='proj-badge down'>↘ −0.5412</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Anchor 2
    st.markdown("""
        <div class='anchor-box'>
            <div class='anchor-header'>
                <div class='anchor-number'>2</div>
                <div class='anchor-info'>
                    <div class='anchor-title'>Secondary Anchor</div>
                    <div class='anchor-subtitle'>Generates bidirectional projections</div>
                </div>
            </div>
    """, unsafe_allow_html=True)
    
    a2_date = st.date_input("Anchor Date", value=datetime.now(CT).date() - timedelta(days=1), key="a2_date")
    a2_price = st.number_input("Anchor Price ($)", value=6600.00, step=0.01, key="a2_price", format="%.2f")
    a2_time = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="a2_time")
    
    st.markdown("""
            <div class='projection-badges'>
                <div class='proj-badge up'>↗ +0.5412</div>
                <div class='proj-badge down'>↘ −0.5412</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # ========== CALCULATE PROJECTIONS ==========
    slots = rth_slots_ct_dt(proj_day, "08:30", "14:00")
    
    a1_dt = CT.localize(datetime.combine(a1_date, a1_time))
    a2_dt = CT.localize(datetime.combine(a2_date, a2_time))
    
    df_a1_asc = project_line(a1_price, a1_dt, ASC_SLOPE, slots)
    df_a1_desc = project_line(a1_price, a1_dt, DESC_SLOPE, slots)
    df_a2_asc = project_line(a2_price, a2_dt, ASC_SLOPE, slots)
    df_a2_desc = project_line(a2_price, a2_dt, DESC_SLOPE, slots)
    
    merged = pd.DataFrame({"Time (CT)": [dt.strftime("%I:%M %p") for dt in slots]})
    merged["Anchor 1 ↗"] = df_a1_asc["Price"]
    merged["Anchor 1 ↘"] = df_a1_desc["Price"]
    merged["Anchor 2 ↗"] = df_a2_asc["Price"]
    merged["Anchor 2 ↘"] = df_a2_desc["Price"]

    # ========== MARKET OPEN SUMMARY ==========
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown("""
        <div class="card-header">
            <div class="card-title">
                <span class="card-icon">📈</span>
                <span>Market Open Summary</span>
            </div>
            <div class="card-badge">
                <span>🕐</span>
                <span>8:30 AM CT</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    st.markdown('<div class="stats-grid">', unsafe_allow_html=True)
    
    open_row = merged[merged["Time (CT)"] == "08:30 AM"].iloc[0]
    
    for col, label, anchor_price in [
        ("Anchor 1 ↗", "Anchor 1 Ascending", a1_price),
        ("Anchor 1 ↘", "Anchor 1 Descending", a1_price),
        ("Anchor 2 ↗", "Anchor 2 Ascending", a2_price),
        ("Anchor 2 ↘", "Anchor 2 Descending", a2_price)
    ]:
        val = open_row[col]
        change = val - anchor_price
        change_class = "positive" if change > 0 else "negative"
        change_symbol = "+" if change > 0 else ""
        
        st.markdown(f"""
            <div class='stat-box'>
                <div class='stat-label'>{label}</div>
                <div class='stat-value'>${val:.2f}</div>
                <div class='stat-change {change_class}'>{change_symbol}{change:.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div></div></div>', unsafe_allow_html=True)

    # ========== RESULTS TABLE ==========
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown("""
        <div class="card-header">
            <div class="card-title">
                <span class="card-icon">📊</span>
                <span>Complete Projection Matrix</span>
            </div>
            <div class="card-badge">
                <span>📋</span>
                <span>RTH Session</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    st.markdown('<div class="table-wrapper">', unsafe_allow_html=True)
    st.dataframe(merged, use_container_width=True, hide_index=True, height=550)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height: 2.5rem'></div>", unsafe_allow_html=True)

    # Export Buttons
    st.markdown("<div style='font-size: 0.75rem; font-weight: 800; color: #737373; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 1.25rem;'>📥 EXPORT OPTIONS</div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3, gap="large")
    
    with col1:
        st.download_button(
            "💾 Complete Dataset",
            merged.to_csv(index=False).encode(),
            "spx_prophet_complete.csv",
            "text/csv",
            key="dl_complete",
            use_container_width=True
        )
    
    with col2:
        a1_data = merged[["Time (CT)", "Anchor 1 ↗", "Anchor 1 ↘"]]
        st.download_button(
            "📊 Anchor 1 Data",
            a1_data.to_csv(index=False).encode(),
            "spx_prophet_anchor1.csv",
            "text/csv",
            key="dl_a1",
            use_container_width=True
        )
    
    with col3:
        a2_data = merged[["Time (CT)", "Anchor 2 ↗", "Anchor 2 ↘"]]
        st.download_button(
            "📊 Anchor 2 Data",
            a2_data.to_csv(index=False).encode(),
            "spx_prophet_anchor2.csv",
            "text/csv",
            key="dl_a2",
            use_container_width=True
        )

    st.markdown('</div></div>', unsafe_allow_html=True)

    # ========== FOOTER ==========
    st.markdown(f"""
        <div class="app-footer">
            <span class="footer-brand">{APP_NAME}</span>
            <span class="footer-divider">·</span>
            <span>{APP_VERSION}</span>
            <span class="footer-divider">·</span>
            <span>Institutional-Grade Market Projection Platform</span>
            <span class="footer-divider">·</span>
            <span>© 2025</span>
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()