# app.py
# SPX Prophet — Professional SPX Projection Platform
# Enterprise-grade interface for precision market projections
# Slopes: +0.5412 / -0.5412 per 30-min block

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List

APP_NAME = "SPX Prophet"
APP_TAGLINE = "Professional Market Projection Platform"

# ===============================
# THEME — Professional Enterprise
# ===============================

def theme_css(mode: str):
    if mode == "Dark":
        p = {
            "bg": "#0d0d0d",
            "bgSecondary": "#111111",
            "surface": "#1a1a1a",
            "surfaceHover": "#222222",
            "text": "#ffffff",
            "textSecondary": "#a0a0a0",
            "textMuted": "#707070",
            "primary": "#00d395",
            "primaryHover": "#00f0a8",
            "accent": "#5865f2",
            "accentHover": "#6b77ff",
            "border": "#2a2a2a",
            "borderLight": "#1f1f1f",
            "success": "#00d395",
            "error": "#ff5c5c",
            "warning": "#ffb800",
        }
    else:
        p = {
            "bg": "#ffffff",
            "bgSecondary": "#f8f9fa",
            "surface": "#ffffff",
            "surfaceHover": "#f5f7fa",
            "text": "#0d0d0d",
            "textSecondary": "#5a5a5a",
            "textMuted": "#8a8a8a",
            "primary": "#00c781",
            "primaryHover": "#00d890",
            "accent": "#5865f2",
            "accentHover": "#6b77ff",
            "border": "#e8e8e8",
            "borderLight": "#f0f0f0",
            "success": "#00c781",
            "error": "#ff5c5c",
            "warning": "#ffb800",
        }
    
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
    
    * {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }}
    
    html, body, [data-testid="stAppViewContainer"] {{
        background: {p['bg']};
        color: {p['text']};
    }}
    
    [data-testid="stAppViewContainer"] > div:first-child {{
        background: {p['bg']};
    }}
    
    /* Sidebar */
    [data-testid="stSidebar"] {{
        background: {p['surface']};
        border-right: 1px solid {p['border']};
    }}
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
        padding: 0;
    }}
    
    /* Typography */
    h1, h2, h3, h4, h5, h6 {{
        color: {p['text']};
        font-weight: 700;
        letter-spacing: -0.02em;
    }}
    
    p, span, div, label {{
        color: {p['text']};
    }}
    
    /* Header */
    .prophet-header {{
        padding: 48px 0 32px 0;
        border-bottom: 1px solid {p['border']};
        margin-bottom: 40px;
    }}
    
    .prophet-logo {{
        font-size: 3rem;
        font-weight: 900;
        background: linear-gradient(135deg, {p['primary']}, {p['accent']});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        letter-spacing: -0.03em;
        margin: 0;
        line-height: 1.1;
    }}
    
    .prophet-tagline {{
        font-size: 1.125rem;
        color: {p['textSecondary']};
        font-weight: 500;
        margin-top: 8px;
    }}
    
    /* Cards */
    .prophet-card {{
        background: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: 16px;
        padding: 32px;
        margin-bottom: 24px;
        transition: all 0.2s ease;
    }}
    
    .prophet-card:hover {{
        border-color: {p['primary']};
        box-shadow: 0 8px 32px rgba(0, 211, 149, 0.08);
    }}
    
    .card-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 24px;
        padding-bottom: 16px;
        border-bottom: 1px solid {p['borderLight']};
    }}
    
    .card-title {{
        font-size: 1.5rem;
        font-weight: 700;
        color: {p['text']};
        margin: 0;
    }}
    
    .card-badge {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        background: {p['bgSecondary']};
        border: 1px solid {p['border']};
        border-radius: 20px;
        font-size: 0.813rem;
        font-weight: 600;
        color: {p['primary']};
    }}
    
    /* Input Groups */
    .input-group {{
        background: {p['bgSecondary']};
        border: 1px solid {p['border']};
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        transition: all 0.2s ease;
    }}
    
    .input-group:hover {{
        border-color: {p['primary']};
        background: {p['surfaceHover']};
    }}
    
    .input-label {{
        font-size: 0.813rem;
        font-weight: 600;
        color: {p['textMuted']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 12px;
        display: block;
    }}
    
    .input-title {{
        font-size: 1.25rem;
        font-weight: 700;
        color: {p['text']};
        margin-bottom: 16px;
    }}
    
    /* Stat Cards */
    .stat-card {{
        background: {p['bgSecondary']};
        border: 1px solid {p['border']};
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }}
    
    .stat-value {{
        font-size: 2rem;
        font-weight: 800;
        color: {p['primary']};
        margin: 8px 0 4px 0;
        line-height: 1;
    }}
    
    .stat-label {{
        font-size: 0.75rem;
        font-weight: 600;
        color: {p['textMuted']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    
    .stat-sublabel {{
        font-size: 0.688rem;
        color: {p['textSecondary']};
        margin-top: 4px;
    }}
    
    /* Buttons */
    .stButton > button,
    .stDownloadButton > button {{
        background: {p['primary']};
        color: #000000;
        border: none;
        border-radius: 12px;
        padding: 16px 32px;
        font-weight: 700;
        font-size: 1rem;
        width: 100%;
        transition: all 0.2s ease;
        box-shadow: 0 4px 12px rgba(0, 211, 149, 0.15);
    }}
    
    .stButton > button:hover,
    .stDownloadButton > button:hover {{
        background: {p['primaryHover']};
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(0, 211, 149, 0.25);
    }}
    
    /* Input Fields */
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input,
    .stTimeInput > div > div > input,
    .stTextInput > div > div > input {{
        background: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: 10px;
        padding: 14px 16px;
        font-size: 1rem;
        font-weight: 500;
        color: {p['text']};
        transition: all 0.2s ease;
    }}
    
    .stNumberInput > div > div > input:focus,
    .stDateInput > div > div > input:focus,
    .stTimeInput > div > div > input:focus,
    .stTextInput > div > div > input:focus {{
        border-color: {p['primary']};
        box-shadow: 0 0 0 3px rgba(0, 211, 149, 0.1);
        outline: none;
    }}
    
    /* Data Table */
    .stDataFrame {{
        border: 1px solid {p['border']};
        border-radius: 12px;
        overflow: hidden;
    }}
    
    .stDataFrame [data-testid="StyledTable"] {{
        font-variant-numeric: tabular-nums;
    }}
    
    .stDataFrame thead tr th {{
        background: {p['bgSecondary']};
        color: {p['textMuted']};
        font-weight: 700;
        font-size: 0.813rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 16px;
        border-bottom: 1px solid {p['border']};
    }}
    
    .stDataFrame tbody tr td {{
        padding: 16px;
        font-weight: 500;
        border-bottom: 1px solid {p['borderLight']};
    }}
    
    .stDataFrame tbody tr:last-child td {{
        border-bottom: none;
    }}
    
    /* Alert Box */
    .alert-box {{
        background: linear-gradient(135deg, rgba(0, 211, 149, 0.08), rgba(88, 101, 242, 0.08));
        border: 1px solid {p['border']};
        border-left: 4px solid {p['primary']};
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 32px;
    }}
    
    .alert-title {{
        font-weight: 700;
        font-size: 1rem;
        color: {p['text']};
        margin-bottom: 6px;
    }}
    
    .alert-text {{
        font-size: 0.938rem;
        color: {p['textSecondary']};
        line-height: 1.6;
    }}
    
    /* Sidebar Enhancements */
    [data-testid="stSidebar"] .stat-card {{
        margin-bottom: 12px;
    }}
    
    .sidebar-header {{
        padding: 24px 16px;
        border-bottom: 1px solid {p['border']};
        margin-bottom: 24px;
    }}
    
    .sidebar-title {{
        font-size: 1.5rem;
        font-weight: 800;
        color: {p['text']};
        margin: 0;
    }}
    
    .sidebar-subtitle {{
        font-size: 0.875rem;
        color: {p['textSecondary']};
        margin-top: 4px;
    }}
    
    /* Radio Buttons */
    [data-testid="stSidebar"] .stRadio > label {{
        font-weight: 600;
        font-size: 0.875rem;
        color: {p['textMuted']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    
    /* Results Section */
    .results-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 24px;
    }}
    
    .results-title {{
        font-size: 1.5rem;
        font-weight: 700;
        color: {p['text']};
    }}
    
    /* Footer */
    .prophet-footer {{
        text-align: center;
        padding: 40px 0;
        margin-top: 60px;
        border-top: 1px solid {p['border']};
        color: {p['textMuted']};
        font-size: 0.875rem;
    }}
    
    /* Gradient Accents */
    .gradient-text {{
        background: linear-gradient(135deg, {p['primary']}, {p['accent']});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}
    
    /* Hide Streamlit Branding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    
    /* Spacing */
    .block-container {{
        padding-top: 3rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }}
    </style>
    """

def inject_theme(mode: str):
    st.markdown(theme_css(mode), unsafe_allow_html=True)

# ===============================
# TIME — CT helpers & slots
# ===============================

CT = pytz.timezone("America/Chicago")

def rth_slots_ct_dt(proj_date: date, start="08:30", end="14:30") -> List[datetime]:
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    start_dt = CT.localize(datetime.combine(proj_date, dtime(h1, m1)))
    end_dt   = CT.localize(datetime.combine(proj_date, dtime(h2, m2)))
    idx = pd.date_range(start=start_dt, end=end_dt, freq="30min", tz=CT)
    return list(idx.to_pydatetime())

# ===============================
# Projection logic
# ===============================

ASC_SLOPE = 0.5412   # per 30-min block
DESC_SLOPE = -0.5412 # per 30-min block

def count_blocks_with_maintenance_skip(start_dt: datetime, end_dt: datetime) -> int:
    """
    Count 30-minute blocks from start_dt to end_dt, SKIPPING 4pm-5pm CT maintenance (2 candles).
    The maintenance window is 4pm-5pm CT, so both 4:00pm and 4:30pm candles don't exist.
    """
    blocks = 0
    current = start_dt
    
    while current < end_dt:
        # Skip BOTH 4:00pm and 4:30pm slots (maintenance window)
        if current.hour == 16 and current.minute in [0, 30]:
            current += timedelta(minutes=30)
            continue
        
        blocks += 1
        current += timedelta(minutes=30)
    
    return blocks

def project_line(anchor_price: float, anchor_time_ct: datetime, slope_per_block: float, rth_slots_ct: List[datetime]) -> pd.DataFrame:
    """
    Align anchor to nearest 30-min boundary and project across RTH slots.
    Properly handles overnight anchors and skips 4:00pm & 4:30pm maintenance slots.
    """
    minute = 0 if anchor_time_ct.minute < 30 else 30
    anchor_aligned = anchor_time_ct.replace(minute=minute, second=0, microsecond=0)
    
    rows = []
    for dt in rth_slots_ct:
        blocks = count_blocks_with_maintenance_skip(anchor_aligned, dt)
        price = anchor_price + (slope_per_block * blocks)
        rows.append({"Time (CT)": dt.strftime("%H:%M"), "Price": round(price, 2)})
    
    return pd.DataFrame(rows)

# ===============================
# Main App
# ===============================

def main():
    st.set_page_config(
        page_title=APP_NAME, 
        page_icon="📊", 
        layout="wide", 
        initial_sidebar_state="expanded"
    )

    # Sidebar
    with st.sidebar:
        st.markdown("""
            <div class="sidebar-header">
                <div class="sidebar-title">⚡ SPX Prophet</div>
                <div class="sidebar-subtitle">Professional Platform</div>
            </div>
        """, unsafe_allow_html=True)
        
        mode = st.radio("THEME", ["Light", "Dark"], index=0, key="ui_theme")
        inject_theme(mode)
        
        st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)
        st.markdown("<div class='input-label'>Configuration</div>", unsafe_allow_html=True)
        
        st.markdown("""
            <div class='stat-card'>
                <div class='stat-label'>Ascending Slope</div>
                <div class='stat-value gradient-text'>+0.5412</div>
                <div class='stat-sublabel'>per 30-min block</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
        
        st.markdown("""
            <div class='stat-card'>
                <div class='stat-label'>Descending Slope</div>
                <div class='stat-value gradient-text'>-0.5412</div>
                <div class='stat-sublabel'>per 30-min block</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)
        st.caption("⚠️ Maintenance: 4:00pm & 4:30pm candles excluded")

    # Header
    st.markdown(f"""
        <div class="prophet-header">
            <div class="prophet-logo">{APP_NAME}</div>
            <div class="prophet-tagline">{APP_TAGLINE}</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Alert Box
    st.markdown("""
        <div class="alert-box">
            <div class="alert-title">🕐 Central Time (CT) — All Times</div>
            <div class="alert-text">
                Projections calculated for RTH session: <strong>08:30 AM to 02:30 PM CT</strong>. 
                Anchors typically set from previous trading day. Maintenance window (4:00 PM - 5:00 PM) automatically excluded from calculations.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Main Card
    st.markdown('<div class="prophet-card">', unsafe_allow_html=True)
    
    st.markdown("""
        <div class="card-header">
            <div class="card-title">Anchor Configuration</div>
            <div class="card-badge">
                <span>📊</span>
                <span>SPX Analysis</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Projection Day
    st.markdown("<div class='input-label'>Projection Date</div>", unsafe_allow_html=True)
    proj_day = st.date_input(
        "projection_day", 
        value=datetime.now(CT).date(), 
        key="spx_proj_day",
        label_visibility="collapsed"
    )

    st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)

    # Anchor Inputs
    col1, col2 = st.columns(2, gap="large")
    
    with col1:
        st.markdown("""
            <div class='input-group'>
                <div class='input-title'>📈 Skyline Anchor</div>
                <div style='color: #00c781; font-size: 0.875rem; margin-bottom: 20px;'>
                    Ascending Projection (+0.5412/block)
                </div>
        """, unsafe_allow_html=True)
        
        sky_anchor_date = st.date_input(
            "Anchor Date", 
            value=datetime.now(CT).date() - timedelta(days=1), 
            key="sky_anchor_date"
        )
        sky_price = st.number_input("Anchor Price", value=5000.00, step=0.01, key="sky_price", format="%.2f")
        sky_time  = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="sky_time")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
            <div class='input-group'>
                <div class='input-title'>📉 Baseline Anchor</div>
                <div style='color: #5865f2; font-size: 0.875rem; margin-bottom: 20px;'>
                    Descending Projection (-0.5412/block)
                </div>
        """, unsafe_allow_html=True)
        
        base_anchor_date = st.date_input(
            "Anchor Date", 
            value=datetime.now(CT).date() - timedelta(days=1), 
            key="base_anchor_date"
        )
        base_price = st.number_input("Anchor Price", value=4900.00, step=0.01, key="base_price", format="%.2f")
        base_time  = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="base_time")
        
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)

    # Calculations
    slots = rth_slots_ct_dt(proj_day, "08:30", "14:30")
    sky_dt  = CT.localize(datetime.combine(sky_anchor_date, sky_time))
    base_dt = CT.localize(datetime.combine(base_anchor_date, base_time))
    
    df_sky  = project_line(sky_price,  sky_dt,  ASC_SLOPE,  slots)
    df_base = project_line(base_price, base_dt, DESC_SLOPE, slots)
    
    merged = pd.DataFrame({"Time (CT)": [dt.strftime("%H:%M") for dt in slots]})
    merged = merged.merge(df_sky.rename(columns={"Price":"Skyline"}), on="Time (CT)", how="left")
    merged = merged.merge(df_base.rename(columns={"Price":"Baseline"}), on="Time (CT)", how="left")

    # Results Card
    st.markdown('<div class="prophet-card">', unsafe_allow_html=True)
    
    st.markdown("""
        <div class="results-header">
            <div class="results-title">Projection Results</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.dataframe(merged, use_container_width=True, hide_index=True, height=400)

    st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)

    col3, col4 = st.columns(2, gap="large")
    with col3:
        st.download_button(
            "📥 Download Skyline CSV",
            df_sky.to_csv(index=False).encode(),
            "spx_skyline_projection.csv",
            "text/csv",
            key="dl_sky",
            use_container_width=True
        )
    with col4:
        st.download_button(
            "📥 Download Baseline CSV",
            df_base.to_csv(index=False).encode(),
            "spx_baseline_projection.csv",
            "text/csv",
            key="dl_base",
            use_container_width=True
        )

    st.markdown("</div>", unsafe_allow_html=True)

    # Footer
    st.markdown(f"""
        <div class="prophet-footer">
            <strong>{APP_NAME}</strong> © 2025 · Professional Edition · Precision Market Projections
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()