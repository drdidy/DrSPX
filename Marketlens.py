# app.py
# SPX PROPHET — Ultimate Institutional Trading Platform
# Advanced dual-anchor projection system with professional analytics
# Built for serious traders who demand precision and profitability

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List, Dict, Tuple
import numpy as np

APP_NAME = "SPX PROPHET"
APP_VERSION = "Ultimate Edition 3.0"
APP_TAGLINE = "Institutional Market Intelligence Platform"

# ===============================
# CONFIGURATION
# ===============================

CT = pytz.timezone("America/Chicago")
ASC_SLOPE = 0.5412
DESC_SLOPE = -0.5412

# ===============================
# CORE CALCULATIONS
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

def calculate_analytics(df: pd.DataFrame, anchor_names: Dict) -> Dict:
    """Calculate advanced trading analytics"""
    analytics = {}
    
    # Get all projection columns
    proj_cols = [col for col in df.columns if col != "Time (CT)"]
    
    # Price range analysis
    all_prices = df[proj_cols].values.flatten()
    analytics['overall_range'] = {
        'high': float(np.max(all_prices)),
        'low': float(np.min(all_prices)),
        'mid': float(np.mean(all_prices)),
        'range': float(np.max(all_prices) - np.min(all_prices))
    }
    
    # Opening analysis (8:30 AM)
    open_row = df[df["Time (CT)"] == "08:30 AM"]
    if not open_row.empty:
        analytics['market_open'] = {
            col: float(open_row[col].iloc[0]) for col in proj_cols
        }
        open_prices = [float(open_row[col].iloc[0]) for col in proj_cols]
        analytics['open_range'] = {
            'high': max(open_prices),
            'low': min(open_prices),
            'spread': max(open_prices) - min(open_prices)
        }
    
    # Closing analysis (2:00 PM)
    close_row = df[df["Time (CT)"] == "02:00 PM"]
    if not close_row.empty:
        analytics['market_close'] = {
            col: float(close_row[col].iloc[0]) for col in proj_cols
        }
        close_prices = [float(close_row[col].iloc[0]) for col in proj_cols]
        analytics['close_range'] = {
            'high': max(close_prices),
            'low': min(close_prices),
            'spread': max(close_prices) - min(close_prices)
        }
    
    # Key levels (psychological levels, round numbers)
    min_price = int(analytics['overall_range']['low'] / 10) * 10
    max_price = int(analytics['overall_range']['high'] / 10) * 10 + 10
    analytics['key_levels'] = list(range(min_price, max_price + 1, 10))
    
    # Confluence zones (where projections are close)
    confluence_zones = []
    for idx, row in df.iterrows():
        prices = [row[col] for col in proj_cols]
        # Check if any two prices are within 5 points
        for i in range(len(prices)):
            for j in range(i+1, len(prices)):
                if abs(prices[i] - prices[j]) <= 5:
                    confluence_zones.append({
                        'time': row["Time (CT)"],
                        'price': (prices[i] + prices[j]) / 2,
                        'lines': [proj_cols[i], proj_cols[j]]
                    })
    analytics['confluence_zones'] = confluence_zones
    
    return analytics

# ===============================
# THEME
# ===============================

def get_theme_css(mode: str) -> str:
    if mode == "🌙 Dark Mode":
        colors = {
            "bg": "#000000",
            "bg_secondary": "#0a0a0a",
            "surface": "#0f0f0f",
            "surface_elevated": "#1a1a1a",
            "surface_hover": "#252525",
            "text": "#ffffff",
            "text_secondary": "#a3a3a3",
            "text_muted": "#666666",
            "primary": "#00ff88",
            "primary_hover": "#00cc6a",
            "accent": "#00d4ff",
            "accent_hover": "#00a8cc",
            "success": "#10b981",
            "error": "#ef4444",
            "warning": "#f59e0b",
            "border": "#1f1f1f",
            "border_accent": "#333333",
        }
    else:
        colors = {
            "bg": "#ffffff",
            "bg_secondary": "#fafafa",
            "surface": "#f5f5f5",
            "surface_elevated": "#ffffff",
            "surface_hover": "#f0f0f0",
            "text": "#0a0a0a",
            "text_secondary": "#525252",
            "text_muted": "#a3a3a3",
            "primary": "#00b366",
            "primary_hover": "#008f51",
            "accent": "#0099cc",
            "accent_hover": "#007aa3",
            "success": "#10b981",
            "error": "#ef4444",
            "warning": "#f59e0b",
            "border": "#e5e5e5",
            "border_accent": "#d4d4d4",
        }
    
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700;800&display=swap');
    
    :root {{
        --bg: {colors['bg']};
        --surface: {colors['surface']};
        --text: {colors['text']};
        --primary: {colors['primary']};
        --accent: {colors['accent']};
    }}
    
    * {{
        font-family: 'Inter', -apple-system, sans-serif;
    }}
    
    html, body, [class*="st-"] {{
        background: {colors['bg']} !important;
        color: {colors['text']} !important;
    }}
    
    /* Sidebar visible and styled */
    section[data-testid="stSidebar"] {{
        background: {colors['surface']} !important;
        border-right: 1px solid {colors['border']} !important;
        padding: 2rem 1.5rem !important;
    }}
    
    section[data-testid="stSidebar"] > div {{
        background: {colors['surface']} !important;
    }}
    
    /* Make sidebar controls visible */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        gap: 1.5rem;
    }}
    
    section[data-testid="stSidebar"] label {{
        color: {colors['text_secondary']} !important;
        font-weight: 700 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
    }}
    
    section[data-testid="stSidebar"] .stRadio > div {{
        background: {colors['surface_elevated']} !important;
        border: 1px solid {colors['border']} !important;
        border-radius: 12px !important;
        padding: 1rem !important;
    }}
    
    /* Header */
    .app-header {{
        text-align: center;
        padding: 4rem 0 3rem 0;
        background: radial-gradient(ellipse at center, {colors['primary']}08 0%, transparent 70%);
    }}
    
    .app-logo {{
        font-size: 5rem;
        font-weight: 900;
        letter-spacing: 0.1em;
        background: linear-gradient(135deg, {colors['primary']}, {colors['accent']});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        line-height: 1;
    }}
    
    .app-separator {{
        width: 150px;
        height: 4px;
        background: linear-gradient(90deg, transparent, {colors['primary']}, {colors['accent']}, transparent);
        margin: 1.5rem auto;
        border-radius: 2px;
    }}
    
    .app-tagline {{
        font-size: 1.25rem;
        color: {colors['text_secondary']};
        font-weight: 500;
    }}
    
    /* Cards */
    .premium-card {{
        background: {colors['surface_elevated']};
        border: 1px solid {colors['border']};
        border-radius: 20px;
        margin: 2rem 0;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        transition: all 0.3s ease;
    }}
    
    .premium-card:hover {{
        box-shadow: 0 8px 40px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }}
    
    .card-header {{
        background: {colors['surface']};
        border-bottom: 1px solid {colors['border']};
        padding: 2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    
    .card-title {{
        font-size: 1.75rem;
        font-weight: 800;
        color: {colors['text']};
        display: flex;
        align-items: center;
        gap: 1rem;
    }}
    
    .card-icon {{
        font-size: 2.25rem;
    }}
    
    .card-badge {{
        padding: 0.75rem 1.5rem;
        background: linear-gradient(135deg, {colors['primary']}15, {colors['accent']}15);
        border: 1px solid {colors['border_accent']};
        border-radius: 100px;
        font-size: 0.75rem;
        font-weight: 800;
        color: {colors['primary']};
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }}
    
    .card-body {{
        padding: 2.5rem;
    }}
    
    /* Anchor boxes */
    .anchor-grid {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 2rem;
        margin: 2rem 0;
    }}
    
    .anchor-box {{
        background: {colors['surface']};
        border: 2px solid {colors['border']};
        border-radius: 16px;
        padding: 2rem;
        transition: all 0.3s ease;
        position: relative;
    }}
    
    .anchor-box::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, {colors['primary']}, {colors['accent']});
        opacity: 0;
        transition: opacity 0.3s;
    }}
    
    .anchor-box:hover {{
        border-color: {colors['primary']};
        box-shadow: 0 0 0 4px {colors['primary']}15;
    }}
    
    .anchor-box:hover::before {{
        opacity: 1;
    }}
    
    .anchor-header {{
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 2rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid {colors['border']};
    }}
    
    .anchor-badge {{
        width: 60px;
        height: 60px;
        border-radius: 14px;
        background: linear-gradient(135deg, {colors['primary']}, {colors['accent']});
        color: #000;
        font-size: 2rem;
        font-weight: 900;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 16px {colors['primary']}40;
    }}
    
    .anchor-name {{
        flex: 1;
    }}
    
    .anchor-label {{
        font-size: 0.75rem;
        font-weight: 700;
        color: {colors['text_muted']};
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }}
    
    .anchor-title {{
        font-size: 1.5rem;
        font-weight: 800;
        color: {colors['text']};
        margin-top: 0.25rem;
    }}
    
    .projection-tags {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.75rem;
        margin-top: 1.5rem;
        padding-top: 1.5rem;
        border-top: 1px solid {colors['border']};
    }}
    
    .proj-tag {{
        padding: 1rem;
        border-radius: 10px;
        font-size: 0.875rem;
        font-weight: 700;
        text-align: center;
    }}
    
    .proj-tag.bull {{
        background: linear-gradient(135deg, {colors['success']}18, {colors['success']}08);
        color: {colors['success']};
        border: 1px solid {colors['success']}40;
    }}
    
    .proj-tag.bear {{
        background: linear-gradient(135deg, {colors['error']}18, {colors['error']}08);
        color: {colors['error']};
        border: 1px solid {colors['error']}40;
    }}
    
    /* Stats grid */
    .stats-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.5rem;
        margin: 2rem 0;
    }}
    
    .stat-card {{
        background: {colors['surface']};
        border: 1px solid {colors['border']};
        border-radius: 14px;
        padding: 1.75rem;
        text-align: center;
        transition: all 0.2s;
    }}
    
    .stat-card:hover {{
        border-color: {colors['primary']};
        box-shadow: 0 4px 20px {colors['primary']}15;
        transform: translateY(-2px);
    }}
    
    .stat-label {{
        font-size: 0.7rem;
        font-weight: 800;
        color: {colors['text_muted']};
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.75rem;
    }}
    
    .stat-value {{
        font-size: 2rem;
        font-weight: 900;
        font-family: 'JetBrains Mono', monospace;
        color: {colors['text']};
        margin-bottom: 0.5rem;
    }}
    
    .stat-change {{
        font-size: 0.875rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }}
    
    .positive {{ color: {colors['success']}; }}
    .negative {{ color: {colors['error']}; }}
    
    /* Analytics sections */
    .analytics-section {{
        background: {colors['surface']};
        border: 1px solid {colors['border']};
        border-radius: 14px;
        padding: 2rem;
        margin: 1.5rem 0;
    }}
    
    .section-title {{
        font-size: 1.25rem;
        font-weight: 800;
        color: {colors['text']};
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }}
    
    .level-badge {{
        display: inline-block;
        padding: 0.5rem 1rem;
        background: {colors['surface_elevated']};
        border: 1px solid {colors['border']};
        border-radius: 8px;
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        font-size: 0.938rem;
        margin: 0.5rem;
    }}
    
    .confluence-item {{
        background: {colors['surface_elevated']};
        border-left: 3px solid {colors['warning']};
        padding: 1rem 1.5rem;
        margin: 0.75rem 0;
        border-radius: 8px;
    }}
    
    /* Table styling */
    .stDataFrame {{
        border: 1px solid {colors['border']};
        border-radius: 14px;
        overflow: hidden;
    }}
    
    .stDataFrame table {{
        font-family: 'JetBrains Mono', monospace !important;
    }}
    
    .stDataFrame thead th {{
        background: {colors['surface']} !important;
        color: {colors['text_muted']} !important;
        font-weight: 900 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
        padding: 1.25rem 1.5rem !important;
        border-bottom: 2px solid {colors['border']} !important;
    }}
    
    .stDataFrame tbody td {{
        padding: 1.125rem 1.5rem !important;
        font-weight: 600 !important;
        border-bottom: 1px solid {colors['border']} !important;
    }}
    
    /* Input fields */
    .stNumberInput input,
    .stDateInput input,
    .stTimeInput input,
    .stTextInput input {{
        background: {colors['surface_elevated']} !important;
        border: 1.5px solid {colors['border']} !important;
        border-radius: 10px !important;
        padding: 1rem 1.125rem !important;
        font-size: 1.063rem !important;
        font-weight: 700 !important;
        font-family: 'JetBrains Mono', monospace !important;
        color: {colors['text']} !important;
    }}
    
    .stNumberInput input:focus,
    .stDateInput input:focus,
    .stTimeInput input:focus,
    .stTextInput input:focus {{
        border-color: {colors['primary']} !important;
        box-shadow: 0 0 0 3px {colors['primary']}20 !important;
    }}
    
    /* Buttons */
    .stButton button,
    .stDownloadButton button {{
        background: linear-gradient(135deg, {colors['primary']}, {colors['accent']}) !important;
        color: #000 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 1.125rem 2rem !important;
        font-weight: 900 !important;
        font-size: 0.938rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        transition: all 0.3s !important;
    }}
    
    .stButton button:hover,
    .stDownloadButton button:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 32px {colors['primary']}40 !important;
    }}
    
    /* Alert banner */
    .alert-banner {{
        background: linear-gradient(135deg, {colors['primary']}10, {colors['accent']}10);
        border: 1px solid {colors['border']};
        border-left: 4px solid {colors['primary']};
        border-radius: 14px;
        padding: 1.75rem 2.25rem;
        margin: 2.5rem 0;
        display: flex;
        gap: 1.5rem;
    }}
    
    .alert-icon {{
        font-size: 2rem;
    }}
    
    .alert-title {{
        font-weight: 800;
        font-size: 1.125rem;
        color: {colors['text']};
        margin-bottom: 0.5rem;
    }}
    
    .alert-text {{
        color: {colors['text_secondary']};
        line-height: 1.7;
    }}
    
    /* Footer */
    .app-footer {{
        text-align: center;
        padding: 3.5rem 0;
        margin-top: 5rem;
        border-top: 1px solid {colors['border']};
        color: {colors['text_muted']};
        font-size: 0.875rem;
    }}
    
    /* Utilities */
    .gradient-text {{
        background: linear-gradient(135deg, {colors['primary']}, {colors['accent']});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    
    .mono {{ font-family: 'JetBrains Mono', monospace; }}
    
    </style>
    """

# ===============================
# MAIN APP
# ===============================

def main():
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Sidebar configuration
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        theme_mode = st.radio(
            "Display Mode",
            ["☀️ Light Mode", "🌙 Dark Mode"],
            index=0,
            key="theme_selector"
        )
        
        st.markdown("---")
        st.markdown("### 📊 Slope Configuration")
        st.info(f"**Ascending:** +{ASC_SLOPE}")
        st.info(f"**Descending:** {DESC_SLOPE}")
        
        st.markdown("---")
        st.markdown("### ℹ️ System Info")
        st.caption("🕐 Central Time (CT)")
        st.caption("📊 RTH: 8:30 AM - 2:00 PM")
        st.caption("⚠️ Excludes 4:00-5:00 PM maintenance")
        st.caption("🎯 Dual anchor system")
        st.caption("📈 4 projection lines")
        
        st.markdown("---")
        st.markdown("### 📖 Quick Guide")
        st.caption("1. Set projection date")
        st.caption("2. Configure Skyline anchor")
        st.caption("3. Configure Baseline anchor")
        st.caption("4. Review analytics & projections")
        st.caption("5. Export data as needed")
    
    # Apply theme
    st.markdown(get_theme_css(theme_mode), unsafe_allow_html=True)
    
    # Header
    st.markdown(f"""
        <div class="app-header">
            <div class="app-logo">{APP_NAME}</div>
            <div class="app-separator"></div>
            <div class="app-tagline">{APP_TAGLINE}</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Alert banner
    st.markdown("""
        <div class="alert-banner">
            <div class="alert-icon">🎯</div>
            <div>
                <div class="alert-title">Advanced Dual-Anchor Projection System</div>
                <div class="alert-text">
                    Configure two independent anchor points (Skyline & Baseline) from the previous trading session. Each anchor automatically generates both bullish and bearish projections across the RTH session. The platform provides comprehensive analytics including confluence zones, key price levels, and risk analysis to maximize your trading edge.
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Configuration Card
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown("""
        <div class="card-header">
            <div class="card-title">
                <span class="card-icon">⚙️</span>
                <span>Anchor Configuration</span>
            </div>
            <div class="card-badge">⚡ Dual System</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    
    # Projection date
    proj_day = st.date_input(
        "📅 Projection Date (CT)",
        value=datetime.now(CT).date(),
        key="proj_date"
    )
    
    # Anchor inputs
    st.markdown('<div class="anchor-grid">', unsafe_allow_html=True)
    
    # Skyline Anchor
    st.markdown("""
        <div class="anchor-box">
            <div class="anchor-header">
                <div class="anchor-badge">☁️</div>
                <div class="anchor-name">
                    <div class="anchor-label">Upper Resistance</div>
                    <div class="anchor-title">SKYLINE</div>
                </div>
            </div>
    """, unsafe_allow_html=True)
    
    skyline_name = st.text_input("Custom Name (Optional)", value="Skyline", key="skyline_name")
    skyline_date = st.date_input("Anchor Date", value=datetime.now(CT).date() - timedelta(days=1), key="skyline_date")
    skyline_price = st.number_input("Anchor Price ($)", value=6634.70, step=0.01, key="skyline_price", format="%.2f")
    skyline_time = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="skyline_time")
    
    st.markdown("""
            <div class="projection-tags">
                <div class="proj-tag bull">📈 Bull Projection</div>
                <div class="proj-tag bear">📉 Bear Projection</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Baseline Anchor
    st.markdown("""
        <div class="anchor-box">
            <div class="anchor-header">
                <div class="anchor-badge">⚓</div>
                <div class="anchor-name">
                    <div class="anchor-label">Lower Support</div>
                    <div class="anchor-title">BASELINE</div>
                </div>
            </div>
    """, unsafe_allow_html=True)
    
    baseline_name = st.text_input("Custom Name (Optional)", value="Baseline", key="baseline_name")
    baseline_date = st.date_input("Anchor Date", value=datetime.now(CT).date() - timedelta(days=1), key="baseline_date")
    baseline_price = st.number_input("Anchor Price ($)", value=6600.00, step=0.01, key="baseline_price", format="%.2f")
    baseline_time = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="baseline_time")
    
    st.markdown("""
            <div class="projection-tags">
                <div class="proj-tag bull">📈 Bull Projection</div>
                <div class="proj-tag bear">📉 Bear Projection</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Calculate projections
    slots = rth_slots_ct_dt(proj_day, "08:30", "14:00")
    
    skyline_dt = CT.localize(datetime.combine(skyline_date, skyline_time))
    baseline_dt = CT.localize(datetime.combine(baseline_date, baseline_time))
    
    df_sky_bull = project_line(skyline_price, skyline_dt, ASC_SLOPE, slots)
    df_sky_bear = project_line(skyline_price, skyline_dt, DESC_SLOPE, slots)
    df_base_bull = project_line(baseline_price, baseline_dt, ASC_SLOPE, slots)
    df_base_bear = project_line(baseline_price, baseline_dt, DESC_SLOPE, slots)
    
    # Create merged dataframe with custom names
    merged = pd.DataFrame({"Time (CT)": [dt.strftime("%I:%M %p") for dt in slots]})
    merged[f"{skyline_name} Bull 📈"] = df_sky_bull["Price"]
    merged[f"{skyline_name} Bear 📉"] = df_sky_bear["Price"]
    merged[f"{baseline_name} Bull 📈"] = df_base_bull["Price"]
    merged[f"{baseline_name} Bear 📉"] = df_base_bear["Price"]
    
    # Calculate analytics
    anchor_names = {
        f"{skyline_name} Bull 📈": "skyline_bull",
        f"{skyline_name} Bear 📉": "skyline_bear",
        f"{baseline_name} Bull 📈": "baseline_bull",
        f"{baseline_name} Bear 📉": "baseline_bear"
    }
    analytics = calculate_analytics(merged, anchor_names)
    
    # Market Open Summary
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown("""
        <div class="card-header">
            <div class="card-title">
                <span class="card-icon">📈</span>
                <span>Market Open Analysis</span>
            </div>
            <div class="card-badge">🕐 8:30 AM CT</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    st.markdown('<div class="stats-grid">', unsafe_allow_html=True)
    
    if 'market_open' in analytics:
        for col_name in merged.columns[1:]:
            val = analytics['market_open'][col_name]
            anchor_price = skyline_price if skyline_name in col_name else baseline_price
            change = val - anchor_price
            change_class = "positive" if change > 0 else "negative"
            change_symbol = "+" if change > 0 else ""
            
            st.markdown(f"""
                <div class='stat-card'>
                    <div class='stat-label'>{col_name}</div>
                    <div class='stat-value'>${val:.2f}</div>
                    <div class='stat-change {change_class}'>{change_symbol}{change:.2f}</div>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Open range analysis
    if 'open_range' in analytics:
        st.markdown("### 🎯 Opening Range Metrics")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Open High", f"${analytics['open_range']['high']:.2f}")
        with col2:
            st.metric("Open Low", f"${analytics['open_range']['low']:.2f}")
        with col3:
            st.metric("Open Spread", f"${analytics['open_range']['spread']:.2f}")
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # Advanced Analytics
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown("""
        <div class="card-header">
            <div class="card-title">
                <span class="card-icon">🧠</span>
                <span>Advanced Market Intelligence</span>
            </div>
            <div class="card-badge">💡 AI Analytics</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="analytics-section">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🎯 Key Price Levels</div>', unsafe_allow_html=True)
        st.markdown("Round number psychological levels within projection range:")
        for level in analytics['key_levels'][:10]:
            st.markdown(f'<span class="level-badge">${level}</span>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="analytics-section">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">📊 Range Analysis</div>', unsafe_allow_html=True)
        st.metric("Overall High", f"${analytics['overall_range']['high']:.2f}")
        st.metric("Overall Low", f"${analytics['overall_range']['low']:.2f}")
        st.metric("Total Range", f"${analytics['overall_range']['range']:.2f}")
        st.metric("Midpoint", f"${analytics['overall_range']['mid']:.2f}")
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Confluence zones
    if analytics['confluence_zones']:
        st.markdown('<div class="analytics-section">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">⚡ Confluence Zones (High Probability Areas)</div>', unsafe_allow_html=True)
        st.markdown("Times when multiple projections converge (within $5):")
        for zone in analytics['confluence_zones'][:5]:
            st.markdown(f"""
                <div class="confluence-item">
                    <strong>{zone['time']}</strong> — Price: ${zone['price']:.2f}<br>
                    <small>Converging: {', '.join(zone['lines'])}</small>
                </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # Results table
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown("""
        <div class="card-header">
            <div class="card-title">
                <span class="card-icon">📊</span>
                <span>Complete Projection Matrix</span>
            </div>
            <div class="card-badge">📋 RTH Session</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    st.dataframe(merged, use_container_width=True, hide_index=True, height=550)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Export buttons
    st.markdown("### 📥 Export Options")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.download_button(
            "💾 Complete Dataset",
            merged.to_csv(index=False).encode(),
            "spx_prophet_complete.csv",
            "text/csv",
            use_container_width=True
        )
    
    with col2:
        skyline_data = merged[["Time (CT)", f"{skyline_name} Bull 📈", f"{skyline_name} Bear 📉"]]
        st.download_button(
            f"☁️ {skyline_name} Data",
            skyline_data.to_csv(index=False).encode(),
            f"spx_prophet_{skyline_name.lower()}.csv",
            "text/csv",
            use_container_width=True
        )
    
    with col3:
        baseline_data = merged[["Time (CT)", f"{baseline_name} Bull 📈", f"{baseline_name} Bear 📉"]]
        st.download_button(
            f"⚓ {baseline_name} Data",
            baseline_data.to_csv(index=False).encode(),
            f"spx_prophet_{baseline_name.lower()}.csv",
            "text/csv",
            use_container_width=True
        )
    
    with col4:
        # Analytics export
        analytics_df = pd.DataFrame({
            'Metric': ['Overall High', 'Overall Low', 'Total Range', 'Midpoint', 'Open High', 'Open Low', 'Open Spread'],
            'Value': [
                analytics['overall_range']['high'],
                analytics['overall_range']['low'],
                analytics['overall_range']['range'],
                analytics['overall_range']['mid'],
                analytics.get('open_range', {}).get('high', 0),
                analytics.get('open_range', {}).get('low', 0),
                analytics.get('open_range', {}).get('spread', 0)
            ]
        })
        st.download_button(
            "🧠 Analytics Report",
            analytics_df.to_csv(index=False).encode(),
            "spx_prophet_analytics.csv",
            "text/csv",
            use_container_width=True
        )
    
    st.markdown('</div></div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown(f"""
        <div class="app-footer">
            <strong>{APP_NAME}</strong> · {APP_VERSION}<br>
            {APP_TAGLINE} · © 2025<br>
            Built for serious traders who demand precision and profitability
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()