# app.py
# SPX Prophet — Institutional-Grade SPX Projection Platform
# Dual anchor system with bidirectional projections
# Slopes: ±0.5412 per 30-min block

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List

APP_NAME = "SPX PROPHET"
APP_VERSION = "Professional Edition v2.0"

# ===============================
# THEME — Institutional Grade
# ===============================

def theme_css(mode: str):
    if mode == "Dark":
        p = {
            "bg": "#000000",
            "bgGradient": "linear-gradient(180deg, #000000 0%, #0a0a0a 100%)",
            "surface": "#0f0f0f",
            "surfaceElevated": "#1a1a1a",
            "text": "#ffffff",
            "textPrimary": "#f0f0f0",
            "textSecondary": "#999999",
            "textMuted": "#666666",
            "primary": "#00ff88",
            "primaryGlow": "rgba(0, 255, 136, 0.2)",
            "accent": "#00d4ff",
            "accentGlow": "rgba(0, 212, 255, 0.2)",
            "border": "#222222",
            "borderSubtle": "#1a1a1a",
            "success": "#00ff88",
            "error": "#ff3366",
            "warning": "#ffaa00",
            "chart1": "#00ff88",
            "chart2": "#00d4ff",
            "chart3": "#ff3366",
            "chart4": "#ffaa00",
        }
    else:
        p = {
            "bg": "#fafbfc",
            "bgGradient": "linear-gradient(180deg, #ffffff 0%, #f5f7fa 100%)",
            "surface": "#ffffff",
            "surfaceElevated": "#ffffff",
            "text": "#0a0a0a",
            "textPrimary": "#1a1a1a",
            "textSecondary": "#4a5568",
            "textMuted": "#718096",
            "primary": "#00b366",
            "primaryGlow": "rgba(0, 179, 102, 0.15)",
            "accent": "#0099cc",
            "accentGlow": "rgba(0, 153, 204, 0.15)",
            "border": "#e2e8f0",
            "borderSubtle": "#edf2f7",
            "success": "#00b366",
            "error": "#e53e3e",
            "warning": "#dd6b20",
            "chart1": "#00b366",
            "chart2": "#0099cc",
            "chart3": "#e53e3e",
            "chart4": "#dd6b20",
        }
    
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    * {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }}
    
    html, body, [data-testid="stAppViewContainer"] {{
        background: {p['bgGradient']};
        color: {p['text']};
    }}
    
    /* Hide Streamlit elements */
    #MainMenu, footer, header {{visibility: hidden;}}
    
    /* Sidebar */
    [data-testid="stSidebar"] {{
        background: {p['surface']};
        border-right: 1px solid {p['border']};
        box-shadow: 4px 0 24px rgba(0, 0, 0, 0.03);
    }}
    
    [data-testid="stSidebar"] > div {{
        padding-top: 2rem;
    }}
    
    /* Main Header */
    .prophet-masthead {{
        text-align: center;
        padding: 60px 0 48px 0;
        margin-bottom: 48px;
        border-bottom: 2px solid {p['border']};
        position: relative;
    }}
    
    .prophet-logo {{
        font-size: 4rem;
        font-weight: 900;
        letter-spacing: 0.05em;
        background: linear-gradient(135deg, {p['primary']} 0%, {p['accent']} 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        line-height: 1;
        text-transform: uppercase;
    }}
    
    .prophet-version {{
        font-size: 0.75rem;
        color: {p['textMuted']};
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        margin-top: 12px;
    }}
    
    .prophet-separator {{
        width: 120px;
        height: 3px;
        background: linear-gradient(90deg, transparent, {p['primary']}, transparent);
        margin: 20px auto;
    }}
    
    /* Cards */
    .prophet-card {{
        background: {p['surface']};
        border: 1px solid {p['border']};
        border-radius: 20px;
        padding: 0;
        margin-bottom: 32px;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04);
        overflow: hidden;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    
    .prophet-card:hover {{
        box-shadow: 0 8px 40px rgba(0, 0, 0, 0.08);
        transform: translateY(-2px);
    }}
    
    .card-header {{
        background: {p['surfaceElevated']};
        border-bottom: 1px solid {p['border']};
        padding: 24px 32px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    
    .card-title {{
        font-size: 1.375rem;
        font-weight: 700;
        color: {p['textPrimary']};
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }}
    
    .card-icon {{
        font-size: 1.75rem;
    }}
    
    .card-badge {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        background: {p['bg']};
        border: 1px solid {p['border']};
        border-radius: 100px;
        font-size: 0.75rem;
        font-weight: 700;
        color: {p['primary']};
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    
    .card-body {{
        padding: 32px;
    }}
    
    /* Anchor Input Sections */
    .anchor-section {{
        background: {p['surfaceElevated']};
        border: 2px solid {p['border']};
        border-radius: 16px;
        padding: 28px;
        margin-bottom: 24px;
        transition: all 0.3s ease;
        position: relative;
    }}
    
    .anchor-section:hover {{
        border-color: {p['primary']};
        box-shadow: 0 0 0 4px {p['primaryGlow']};
    }}
    
    .anchor-section.accent:hover {{
        border-color: {p['accent']};
        box-shadow: 0 0 0 4px {p['accentGlow']};
    }}
    
    .anchor-header {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 24px;
        padding-bottom: 16px;
        border-bottom: 1px solid {p['borderSubtle']};
    }}
    
    .anchor-number {{
        width: 48px;
        height: 48px;
        border-radius: 12px;
        background: linear-gradient(135deg, {p['primary']}, {p['accent']});
        color: #000000;
        font-size: 1.5rem;
        font-weight: 900;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    
    .anchor-title {{
        font-size: 1.25rem;
        font-weight: 700;
        color: {p['textPrimary']};
        margin: 0;
    }}
    
    .anchor-subtitle {{
        font-size: 0.875rem;
        color: {p['textSecondary']};
        margin-top: 4px;
    }}
    
    .projection-info {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        margin-top: 20px;
        padding-top: 20px;
        border-top: 1px solid {p['borderSubtle']};
    }}
    
    .projection-badge {{
        padding: 10px 16px;
        border-radius: 10px;
        font-size: 0.813rem;
        font-weight: 600;
        text-align: center;
    }}
    
    .projection-badge.ascending {{
        background: linear-gradient(135deg, {p['success']}15, {p['success']}08);
        color: {p['success']};
        border: 1px solid {p['success']}30;
    }}
    
    .projection-badge.descending {{
        background: linear-gradient(135deg, {p['error']}15, {p['error']}08);
        color: {p['error']};
        border: 1px solid {p['error']}30;
    }}
    
    /* Stat Grid */
    .stat-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 16px;
        margin-bottom: 32px;
    }}
    
    .stat-card {{
        background: {p['surfaceElevated']};
        border: 1px solid {p['border']};
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        transition: all 0.2s ease;
    }}
    
    .stat-card:hover {{
        border-color: {p['primary']};
        box-shadow: 0 4px 16px {p['primaryGlow']};
    }}
    
    .stat-icon {{
        font-size: 2rem;
        margin-bottom: 8px;
        filter: grayscale(20%);
    }}
    
    .stat-value {{
        font-size: 1.75rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        margin: 8px 0 4px 0;
        line-height: 1;
    }}
    
    .stat-value.primary {{
        color: {p['primary']};
    }}
    
    .stat-value.accent {{
        color: {p['accent']};
    }}
    
    .stat-label {{
        font-size: 0.688rem;
        font-weight: 700;
        color: {p['textMuted']};
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}
    
    .stat-sublabel {{
        font-size: 0.625rem;
        color: {p['textSecondary']};
        margin-top: 4px;
    }}
    
    /* Input Fields */
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input,
    .stTimeInput > div > div > input {{
        background: {p['bg']};
        border: 1.5px solid {p['border']};
        border-radius: 10px;
        padding: 14px 16px;
        font-size: 1rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
        color: {p['textPrimary']};
        transition: all 0.2s ease;
    }}
    
    .stNumberInput > div > div > input:focus,
    .stDateInput > div > div > input:focus,
    .stTimeInput > div > div > input:focus {{
        border-color: {p['primary']};
        box-shadow: 0 0 0 3px {p['primaryGlow']};
        outline: none;
    }}
    
    .stNumberInput label,
    .stDateInput label,
    .stTimeInput label {{
        font-size: 0.75rem;
        font-weight: 700;
        color: {p['textMuted']};
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 8px;
    }}
    
    /* Buttons */
    .stButton > button,
    .stDownloadButton > button {{
        background: linear-gradient(135deg, {p['primary']}, {p['accent']});
        color: #000000;
        border: none;
        border-radius: 12px;
        padding: 16px 32px;
        font-weight: 800;
        font-size: 0.938rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        width: 100%;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 16px {p['primaryGlow']};
    }}
    
    .stButton > button:hover,
    .stDownloadButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 24px {p['primaryGlow']}, 0 0 48px {p['primaryGlow']};
    }}
    
    /* Data Table */
    .dataframe-container {{
        border: 1px solid {p['border']};
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
    }}
    
    .stDataFrame {{
        font-family: 'JetBrains Mono', monospace;
    }}
    
    .stDataFrame [data-testid="StyledTable"] {{
        font-variant-numeric: tabular-nums;
    }}
    
    .stDataFrame thead tr th {{
        background: {p['surfaceElevated']};
        color: {p['textMuted']};
        font-weight: 800;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 16px 20px;
        border-bottom: 2px solid {p['border']};
    }}
    
    .stDataFrame tbody tr td {{
        padding: 14px 20px;
        font-weight: 600;
        font-size: 0.938rem;
        border-bottom: 1px solid {p['borderSubtle']};
    }}
    
    .stDataFrame tbody tr:hover td {{
        background: {p['surfaceElevated']};
    }}
    
    .stDataFrame tbody tr:last-child td {{
        border-bottom: none;
    }}
    
    /* Alert Box */
    .info-banner {{
        background: linear-gradient(135deg, {p['primary']}10, {p['accent']}10);
        border: 1px solid {p['border']};
        border-left: 4px solid {p['primary']};
        border-radius: 12px;
        padding: 20px 28px;
        margin-bottom: 40px;
        display: flex;
        align-items: flex-start;
        gap: 16px;
    }}
    
    .info-icon {{
        font-size: 1.5rem;
        margin-top: 2px;
    }}
    
    .info-content {{
        flex: 1;
    }}
    
    .info-title {{
        font-weight: 700;
        font-size: 1rem;
        color: {p['textPrimary']};
        margin-bottom: 6px;
    }}
    
    .info-text {{
        font-size: 0.875rem;
        color: {p['textSecondary']};
        line-height: 1.6;
    }}
    
    /* Sidebar Styling */
    .sidebar-section {{
        margin-bottom: 32px;
    }}
    
    .sidebar-title {{
        font-size: 0.75rem;
        font-weight: 800;
        color: {p['textMuted']};
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 1px solid {p['border']};
    }}
    
    [data-testid="stSidebar"] .stRadio > label {{
        font-size: 0.75rem;
        font-weight: 700;
        color: {p['textMuted']};
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}
    
    /* Results Section */
    .results-summary {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 32px;
    }}
    
    .summary-card {{
        background: {p['surfaceElevated']};
        border: 1px solid {p['border']};
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }}
    
    .summary-label {{
        font-size: 0.688rem;
        font-weight: 700;
        color: {p['textMuted']};
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 8px;
    }}
    
    .summary-value {{
        font-size: 1.5rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        color: {p['textPrimary']};
    }}
    
    .summary-change {{
        font-size: 0.75rem;
        font-weight: 600;
        margin-top: 4px;
    }}
    
    .summary-change.positive {{
        color: {p['success']};
    }}
    
    .summary-change.negative {{
        color: {p['error']};
    }}
    
    /* Color coding for columns */
    .col-anchor1-asc {{ color: {p['chart1']}; }}
    .col-anchor1-desc {{ color: {p['chart2']}; }}
    .col-anchor2-asc {{ color: {p['chart3']}; }}
    .col-anchor2-desc {{ color: {p['chart4']}; }}
    
    /* Footer */
    .prophet-footer {{
        text-align: center;
        padding: 48px 0;
        margin-top: 80px;
        border-top: 1px solid {p['border']};
        color: {p['textMuted']};
        font-size: 0.813rem;
    }}
    
    .footer-brand {{
        font-weight: 700;
        color: {p['textPrimary']};
    }}
    
    /* Spacing */
    .block-container {{
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }}
    
    /* Smooth scrolling */
    html {{
        scroll-behavior: smooth;
    }}
    </style>
    """

def inject_theme(mode: str):
    st.markdown(theme_css(mode), unsafe_allow_html=True)

# ===============================
# TIME — CT helpers & slots
# ===============================

CT = pytz.timezone("America/Chicago")

def rth_slots_ct_dt(proj_date: date, start="08:30", end="14:00") -> List[datetime]:
    h1, m1 = map(int, start.split(":"))
    h2, m2 = map(int, end.split(":"))
    start_dt = CT.localize(datetime.combine(proj_date, dtime(h1, m1)))
    end_dt   = CT.localize(datetime.combine(proj_date, dtime(h2, m2)))
    idx = pd.date_range(start=start_dt, end=end_dt, freq="30min", tz=CT)
    return list(idx.to_pydatetime())

# ===============================
# Projection logic
# ===============================

ASC_SLOPE = 0.5412
DESC_SLOPE = -0.5412

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
        rows.append({"Time (CT)": dt.strftime("%I:%M %p"), "Price": round(price, 2)})
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
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-title">⚙️ Settings</div>', unsafe_allow_html=True)
        mode = st.radio("Theme", ["Light", "Dark"], index=0, key="ui_theme")
        inject_theme(mode)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-title">📊 Slope Configuration</div>', unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class='stat-card'>
                <div class='stat-icon'>📈</div>
                <div class='stat-label'>Ascending</div>
                <div class='stat-value primary'>+{ASC_SLOPE}</div>
                <div class='stat-sublabel'>per 30-min block</div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class='stat-card'>
                <div class='stat-icon'>📉</div>
                <div class='stat-label'>Descending</div>
                <div class='stat-value accent'>{DESC_SLOPE}</div>
                <div class='stat-sublabel'>per 30-min block</div>
            </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-title">ℹ️ Information</div>', unsafe_allow_html=True)
        st.caption("🕐 All times in Central Time (CT)")
        st.caption("⚠️ Excludes 4:00pm & 4:30pm maintenance")
        st.caption("📊 RTH Session: 8:30am - 2:00pm")
        st.caption("🎯 Each anchor generates ±0.5412 projections")
        st.markdown('</div>', unsafe_allow_html=True)

    # Header
    st.markdown(f"""
        <div class="prophet-masthead">
            <div class="prophet-logo">{APP_NAME}</div>
            <div class="prophet-separator"></div>
            <div class="prophet-version">{APP_VERSION}</div>
        </div>
    """, unsafe_allow_html=True)
    
    # Info Banner
    st.markdown("""
        <div class="info-banner">
            <div class="info-icon">💡</div>
            <div class="info-content">
                <div class="info-title">Dual Anchor Projection System</div>
                <div class="info-text">
                    Configure two anchor points from the previous trading session. Each anchor automatically generates both ascending (+0.5412) and descending (−0.5412) projections for the RTH session (8:30 AM - 2:00 PM CT). Maintenance window automatically excluded from calculations.
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Configuration Card
    st.markdown('<div class="prophet-card">', unsafe_allow_html=True)
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
    
    # Projection Day
    st.markdown("<div style='margin-bottom: 32px;'>", unsafe_allow_html=True)
    st.markdown("<div class='stat-label' style='margin-bottom: 12px;'>📅 PROJECTION DATE</div>", unsafe_allow_html=True)
    proj_day = st.date_input(
        "projection_date", 
        value=datetime.now(CT).date(), 
        key="spx_proj_day",
        label_visibility="collapsed"
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # Anchor inputs
    col1, col2 = st.columns(2, gap="large")
    
    with col1:
        st.markdown("""
            <div class='anchor-section'>
                <div class='anchor-header'>
                    <div class='anchor-number'>1</div>
                    <div>
                        <div class='anchor-title'>Primary Anchor</div>
                        <div class='anchor-subtitle'>Generates ascending & descending projections</div>
                    </div>
                </div>
        """, unsafe_allow_html=True)
        
        anchor1_date = st.date_input(
            "Anchor Date", 
            value=datetime.now(CT).date() - timedelta(days=1), 
            key="anchor1_date"
        )
        anchor1_price = st.number_input("Anchor Price ($)", value=6634.70, step=0.01, key="anchor1_price", format="%.2f")
        anchor1_time = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="anchor1_time")
        
        st.markdown("""
                <div class='projection-info'>
                    <div class='projection-badge ascending'>↗ Ascending +0.5412</div>
                    <div class='projection-badge descending'>↘ Descending −0.5412</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
    with col2:
        st.markdown("""
            <div class='anchor-section accent'>
                <div class='anchor-header'>
                    <div class='anchor-number'>2</div>
                    <div>
                        <div class='anchor-title'>Secondary Anchor</div>
                        <div class='anchor-subtitle'>Generates ascending & descending projections</div>
                    </div>
                </div>
        """, unsafe_allow_html=True)
        
        anchor2_date = st.date_input(
            "Anchor Date", 
            value=datetime.now(CT).date() - timedelta(days=1), 
            key="anchor2_date"
        )
        anchor2_price = st.number_input("Anchor Price ($)", value=6600.00, step=0.01, key="anchor2_price", format="%.2f")
        anchor2_time = st.time_input("Anchor Time (CT)", value=dtime(14, 30), step=1800, key="anchor2_time")
        
        st.markdown("""
                <div class='projection-info'>
                    <div class='projection-badge ascending'>↗ Ascending +0.5412</div>
                    <div class='projection-badge descending'>↘ Descending −0.5412</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("<div style='height: 40px'></div>", unsafe_allow_html=True)

    # Calculate projections
    slots = rth_slots_ct_dt(proj_day, "08:30", "14:00")
    
    anchor1_dt = CT.localize(datetime.combine(anchor1_date, anchor1_time))
    anchor2_dt = CT.localize(datetime.combine(anchor2_date, anchor2_time))
    
    # Generate 4 projections
    df_a1_asc = project_line(anchor1_price, anchor1_dt, ASC_SLOPE, slots)
    df_a1_desc = project_line(anchor1_price, anchor1_dt, DESC_SLOPE, slots)
    df_a2_asc = project_line(anchor2_price, anchor2_dt, ASC_SLOPE, slots)
    df_a2_desc = project_line(anchor2_price, anchor2_dt, DESC_SLOPE, slots)
    
    # Merge all projections
    merged = pd.DataFrame({"Time (CT)": [dt.strftime("%I:%M %p") for dt in slots]})
    merged = merged.merge(df_a1_asc.rename(columns={"Price": "Anchor 1 ↗"}), on="Time (CT)", how="left")
    merged = merged.merge(df_a1_desc.rename(columns={"Price": "Anchor 1 ↘"}), on="Time (CT)", how="left")
    merged = merged.merge(df_a2_asc.rename(columns={"Price": "Anchor 2 ↗"}), on="Time (CT)", how="left")
    merged = merged.merge(df_a2_desc.rename(columns={"Price": "Anchor 2 ↘"}), on="Time (CT)", how="left")

    # Summary stats
    st.markdown('<div class="prophet-card">', unsafe_allow_html=True)
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
    st.markdown('<div class="results-summary">', unsafe_allow_html=True)
    
    # Get 8:30am values
    open_vals = merged[merged["Time (CT)"] == "08:30 AM"].iloc[0]
    
    for col_name, label in [
        ("Anchor 1 ↗", "Anchor 1 Ascending"),
        ("Anchor 1 ↘", "Anchor 1 Descending"),
        ("Anchor 2 ↗", "Anchor 2 Ascending"),
        ("Anchor 2 ↘", "Anchor 2 Descending")
    ]:
        val = open_vals[col_name]
        change = val - (anchor1_price if "Anchor 1" in col_name else anchor2_price)
        change_class = "positive" if change > 0 else "negative"
        change_symbol = "+" if change > 0 else ""
        
        st.markdown(f"""
            <div class='summary-card'>
                <div class='summary-label'>{label}</div>
                <div class='summary-value'>${val:.2f}</div>
                <div class='summary-change {change_class}'>{change_symbol}{change:.2f}</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Results Table
    st.markdown('<div class="prophet-card">', unsafe_allow_html=True)
    st.markdown("""
        <div class="card-header">
            <div class="card-title">
                <span class="card-icon">📊</span>
                <span>Complete Projection Results</span>
            </div>
            <div class="card-badge">
                <span>📋</span>
                <span>RTH Session</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="card-body">', unsafe_allow_html=True)
    st.markdown('<div class="dataframe-container">', unsafe_allow_html=True)
    st.dataframe(merged, use_container_width=True, hide_index=True, height=500)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)

    # Export buttons
    st.markdown("<div class='stat-label' style='margin-bottom: 16px;'>📥 EXPORT DATA</div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3, gap="medium")
    
    with col1:
        st.download_button(
            "💾 Download Complete Dataset",
            merged.to_csv(index=False).encode(),
            "spx_prophet_complete_projections.csv",
            "text/csv",
            key="dl_all",
            use_container_width=True
        )
    
    with col2:
        anchor1_data = merged[["Time (CT)", "Anchor 1 ↗", "Anchor 1 ↘"]]
        st.download_button(
            "📊 Download Anchor 1 Data",
            anchor1_data.to_csv(index=False).encode(),
            "spx_prophet_anchor1.csv",
            "text/csv",
            key="dl_a1",
            use_container_width=True
        )
    
    with col3:
        anchor2_data = merged[["Time (CT)", "Anchor 2 ↗", "Anchor 2 ↘"]]
        st.download_button(
            "📊 Download Anchor 2 Data",
            anchor2_data.to_csv(index=False).encode(),
            "spx_prophet_anchor2.csv",
            "text/csv",
            key="dl_a2",
            use_container_width=True
        )

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Footer
    st.markdown(f"""
        <div class="prophet-footer">
            <span class="footer-brand">{APP_NAME}</span> · {APP_VERSION}<br>
            Institutional-Grade Market Projection Platform · © 2025
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
