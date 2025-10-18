# app.py
# SPX Prophet — Enterprise-Grade SPX Projection Platform
# Inputs: Skyline/Baseline anchors (time + price). Fixed slopes: +0.54 / -0.54 per 30m.
# Output: 08:30–14:30 CT projections as tables + CSV downloads.
# Handles overnight anchors and skips 4pm-5pm maintenance window (no 4:00pm or 4:30pm candles)

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List

APP_NAME = "SPX Prophet"
APP_TAGLINE = "Enterprise-Grade Market Projection Platform"

# ===============================
# THEME — Premium Enterprise Design
# ===============================

def theme_css(mode: str):
    dark = {
        "bg": "#0a0e1a",
        "panel": "rgba(20,26,44,0.75)",
        "panelSolid": "#141a2c",
        "cardBg": "rgba(25,32,52,0.85)",
        "text": "#f0f4f8",
        "textSecondary": "#c5cfe0",
        "muted": "#8994a8",
        "accent": "#3b82f6",
        "accentLight": "#60a5fa",
        "accent2": "#06b6d4",
        "success": "#10b981",
        "warning": "#f59e0b",
        "border": "rgba(99,132,186,0.15)",
        "borderLight": "rgba(99,132,186,0.08)",
        "shadow": "0 25px 70px rgba(0,0,0,0.6), 0 10px 30px rgba(0,0,0,0.4)",
        "shadowSm": "0 10px 30px rgba(0,0,0,0.4)",
        "glow": "0 0 120px rgba(59,130,246,0.15), 0 0 80px rgba(6,182,212,0.1)",
        "glowHover": "0 0 140px rgba(59,130,246,0.25), 0 0 100px rgba(6,182,212,0.15)"
    }
    light = {
        "bg": "#f8faffc",
        "panel": "rgba(255,255,255,0.92)",
        "panelSolid": "#ffffff",
        "cardBg": "rgba(255,255,255,0.95)",
        "text": "#0f172a",
        "textSecondary": "#334155",
        "muted": "#64748b",
        "accent": "#2563eb",
        "accentLight": "#3b82f6",
        "accent2": "#0891b2",
        "success": "#059669",
        "warning": "#d97706",
        "border": "rgba(15,23,42,0.12)",
        "borderLight": "rgba(15,23,42,0.06)",
        "shadow": "0 25px 60px rgba(15,23,42,0.12), 0 8px 24px rgba(15,23,42,0.08)",
        "shadowSm": "0 8px 24px rgba(15,23,42,0.06)",
        "glow": "0 0 120px rgba(37,99,235,0.12), 0 0 80px rgba(8,145,178,0.08)",
        "glowHover": "0 0 140px rgba(37,99,235,0.2), 0 0 100px rgba(8,145,178,0.12)"
    }
    p = dark if mode == "Dark" else light
    
    if mode == "Light":
        grad = (
            "radial-gradient(1600px 1000px at 15% 5%, rgba(37,99,235,0.08), transparent 75%),"
            "radial-gradient(1400px 900px at 85% 10%, rgba(8,145,178,0.06), transparent 70%),"
            f"linear-gradient(180deg, #ffffff 0%, {p['bg']} 100%)"
        )
    else:
        grad = (
            "radial-gradient(1400px 900px at 12% 8%, rgba(59,130,246,0.12), transparent 60%),"
            "radial-gradient(1200px 800px at 88% 12%, rgba(6,182,212,0.1), transparent 65%),"
            f"linear-gradient(165deg, {p['bg']} 0%, #050810 100%)"
        )
    
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {{
      background: {grad};
      background-attachment: fixed;
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
      color: {p['text']};
    }}
    
    /* ========== SIDEBAR ========== */
    [data-testid="stSidebar"] {{
      background: {p['panel']};
      border-right: 1px solid {p['border']};
      backdrop-filter: blur(24px) saturate(180%);
      box-shadow: {p['shadowSm']};
    }}
    
    [data-testid="stSidebar"] .block-container {{
      padding-top: 1.5rem;
    }}
    
    /* ========== CARDS ========== */
    .spx-card {{
      background: {p['cardBg']};
      border: 1px solid {p['border']};
      border-radius: 28px;
      box-shadow: {p['shadow']};
      padding: 40px 44px;
      transition: all .4s cubic-bezier(0.22, 0.61, 0.36, 1);
      backdrop-filter: blur(24px) saturate(180%);
      position: relative;
      overflow: hidden;
    }}
    
    .spx-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 2px;
      background: linear-gradient(90deg, transparent, {p['accent']}, {p['accent2']}, transparent);
      opacity: 0;
      transition: opacity .4s ease;
    }}
    
    .spx-card:hover {{ 
      transform: translateY(-6px) scale(1.002); 
      border-color: {p['accent']}50; 
      box-shadow: {p['glowHover']};
    }}
    
    .spx-card:hover::before {{
      opacity: 1;
    }}
    
    /* ========== HEADER ========== */
    .spx-header {{
      display: flex;
      align-items: flex-start;
      gap: 28px;
      margin-bottom: 16px;
    }}
    
    .spx-hero-icon {{
      font-size: 72px;
      line-height: 1;
      filter: drop-shadow(0 8px 20px {p['accent']}40);
      animation: float 3s ease-in-out infinite;
    }}
    
    @keyframes float {{
      0%, 100% {{ transform: translateY(0px); }}
      50% {{ transform: translateY(-8px); }}
    }}
    
    .spx-badge {{
      display: inline-flex; 
      align-items: center; 
      gap: 10px; 
      padding: 10px 22px; 
      border-radius: 999px;
      border: 1px solid {p['border']}; 
      background: linear-gradient(135deg, {p['accent']}18, {p['accent2']}12); 
      font-weight: 800; 
      font-size: 1rem; 
      color: {p['accent']};
      box-shadow: 0 6px 16px {p['accent']}15, inset 0 1px 0 rgba(255,255,255,0.1);
      backdrop-filter: blur(12px);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    
    .spx-badge-icon {{
      font-size: 1.4rem;
      animation: pulse 2s ease-in-out infinite;
    }}
    
    @keyframes pulse {{
      0%, 100% {{ transform: scale(1); }}
      50% {{ transform: scale(1.15); }}
    }}
    
    .spx-title {{
      font-size: 3.5rem;
      font-weight: 900;
      background: linear-gradient(135deg, {p['accent']}, {p['accent2']});
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin: 0;
      letter-spacing: -0.03em;
      line-height: 1.1;
    }}
    
    .spx-subtitle {{
      color: {p['textSecondary']}; 
      font-size: 1.25rem; 
      font-weight: 600;
      margin-top: 8px;
      letter-spacing: -0.01em;
    }}
    
    /* ========== SECTION TITLES ========== */
    .spx-section {{
      display: flex;
      align-items: center;
      gap: 14px;
      font-size: 1.6rem;
      font-weight: 800;
      color: {p['text']};
      margin: 0 0 20px 0;
      letter-spacing: -0.02em;
    }}
    
    .spx-section-icon {{
      font-size: 2.2rem;
      filter: drop-shadow(0 2px 8px {p['accent']}30);
    }}
    
    /* ========== TYPOGRAPHY ========== */
    h1,h2,h3,h4,h5,h6,label,p,span,div {{ 
      color: {p['text']}; 
      font-family: 'Inter', -apple-system, system-ui, sans-serif;
    }}
    
    /* ========== INFO STATS ========== */
    .stat-box {{
      background: linear-gradient(135deg, {p['cardBg']}, {p['panelSolid']});
      border: 1px solid {p['borderLight']};
      border-radius: 20px;
      padding: 28px 24px;
      text-align: center;
      backdrop-filter: blur(16px);
      box-shadow: {p['shadowSm']};
      transition: all .3s cubic-bezier(0.22, 0.61, 0.36, 1);
      position: relative;
      overflow: hidden;
    }}
    
    .stat-box::after {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, {p['accent']}, {p['accent2']});
      opacity: 0.7;
    }}
    
    .stat-box:hover {{
      transform: translateY(-4px);
      box-shadow: 0 16px 40px rgba(59,130,246,0.15);
      border-color: {p['accent']}30;
    }}
    
    .stat-icon {{
      font-size: 3.5rem;
      margin-bottom: 12px;
      filter: drop-shadow(0 4px 12px {p['accent']}25);
    }}
    
    .stat-label {{
      font-size: .9rem;
      color: {p['muted']};
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 8px;
    }}
    
    .stat-value {{
      font-size: 2.2rem;
      font-weight: 900;
      background: linear-gradient(135deg, {p['accent']}, {p['accent2']});
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      font-family: 'JetBrains Mono', monospace;
    }}
    
    /* ========== ANCHOR PANELS ========== */
    .anchor-panel {{
      background: linear-gradient(135deg, {p['cardBg']}, {p['panelSolid']});
      border: 2px solid {p['borderLight']};
      border-radius: 24px;
      padding: 32px 28px;
      margin-bottom: 20px;
      box-shadow: {p['shadowSm']};
      backdrop-filter: blur(16px);
      transition: all .35s cubic-bezier(0.22, 0.61, 0.36, 1);
      position: relative;
      overflow: hidden;
    }}
    
    .anchor-panel.skyline {{
      border-left: 4px solid {p['success']};
      background: linear-gradient(135deg, rgba(16,185,129,0.08), {p['cardBg']});
    }}
    
    .anchor-panel.baseline {{
      border-left: 4px solid {p['warning']};
      background: linear-gradient(135deg, rgba(245,158,11,0.08), {p['cardBg']});
    }}
    
    .anchor-panel:hover {{
      transform: translateX(4px);
      box-shadow: -8px 0 24px rgba(59,130,246,0.12);
    }}
    
    .anchor-header {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
    }}
    
    .anchor-icon {{
      font-size: 2.8rem;
      filter: drop-shadow(0 4px 12px rgba(59,130,246,0.3));
    }}
    
    .anchor-title {{
      font-size: 1.5rem;
      font-weight: 800;
      letter-spacing: -0.02em;
    }}
    
    .anchor-desc {{
      color: {p['muted']};
      font-size: 1rem;
      font-weight: 500;
      margin-bottom: 24px;
      padding-left: 3.6rem;
    }}
    
    /* ========== DATA TABLE ========== */
    .stDataFrame div[data-testid="StyledTable"] {{ 
      font-variant-numeric: tabular-nums;
      border-radius: 20px;
      overflow: hidden;
      box-shadow: {p['shadow']};
      border: 1px solid {p['borderLight']};
    }}
    
    .stDataFrame [data-testid="StyledTable"] thead tr th {{
      background: linear-gradient(180deg, {p['accent']}15, {p['accent']}08);
      color: {p['text']};
      font-weight: 800;
      font-size: 1rem;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      padding: 16px 20px;
      border-bottom: 2px solid {p['accent']}30;
    }}
    
    .stDataFrame [data-testid="StyledTable"] tbody tr td {{
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
      font-size: 1.05rem;
      padding: 14px 20px;
    }}
    
    /* ========== BUTTONS ========== */
    .stDownloadButton button, .stButton>button {{
      background: linear-gradient(135deg, {p['accent']}, {p['accent2']});
      color: #ffffff; 
      border: 0; 
      border-radius: 18px; 
      padding: 16px 32px; 
      font-weight: 800;
      font-size: 1.05rem;
      box-shadow: 0 12px 32px {p['accent']}35, inset 0 1px 0 rgba(255,255,255,0.2);
      transition: all .35s cubic-bezier(0.22, 0.61, 0.36, 1);
      font-family: 'Inter', sans-serif;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }}
    
    .stButton>button:hover, .stDownloadButton>button:hover {{ 
      transform: translateY(-3px) scale(1.02); 
      box-shadow: 0 16px 48px {p['accent']}45;
      filter: brightness(1.1);
    }}
    
    /* ========== INPUTS ========== */
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input,
    .stTimeInput > div > div > input {{
      border-radius: 14px;
      border: 2px solid {p['borderLight']};
      padding: 14px 16px;
      font-size: 1.05rem;
      font-weight: 600;
      font-family: 'JetBrains Mono', monospace;
      transition: all .25s ease;
      background: {p['panelSolid']};
      color: {p['text']};
    }}
    
    .stNumberInput > div > div > input:focus,
    .stDateInput > div > div > input:focus,
    .stTimeInput > div > div > input:focus {{
      border-color: {p['accent']};
      box-shadow: 0 0 0 4px {p['accent']}20, 0 4px 16px {p['accent']}15;
      background: {p['cardBg']};
    }}
    
    .stNumberInput label, .stDateInput label, .stTimeInput label {{
      font-weight: 700;
      font-size: 0.95rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: {p['textSecondary']};
      margin-bottom: 8px;
    }}
    
    /* ========== ALERT BOX ========== */
    .alert-box {{
      background: linear-gradient(135deg, {p['accent']}12, {p['accent2']}08);
      border-left: 5px solid {p['accent']};
      border-radius: 16px;
      padding: 24px 28px;
      margin: 32px 0;
      box-shadow: {p['shadowSm']};
      backdrop-filter: blur(12px);
    }}
    
    .alert-icon {{
      font-size: 1.8rem;
      margin-right: 12px;
    }}
    
    .info-note {{
      background: {p['cardBg']};
      border: 1px solid {p['borderLight']};
      border-radius: 16px;
      padding: 20px 24px;
      text-align: center;
      margin-top: 24px;
      box-shadow: {p['shadowSm']};
    }}
    
    .info-icon {{
      font-size: 1.6rem;
      margin-right: 10px;
    }}
    
    /* ========== FOOTER ========== */
    .footer {{
      text-align: center;
      padding: 40px 20px;
      margin-top: 60px;
      border-top: 1px solid {p['border']};
      color: {p['muted']};
      font-size: 1rem;
      font-weight: 500;
    }}
    
    .footer-highlight {{
      color: {p['accent']};
      font-weight: 800;
    }}
    
    /* ========== SIDEBAR ENHANCEMENTS ========== */
    [data-testid="stSidebar"] h1 {{
      font-size: 2.2rem;
      font-weight: 900;
      margin-bottom: 8px;
    }}
    
    [data-testid="stSidebar"] h3 {{
      font-size: 1.15rem;
      font-weight: 800;
      margin-top: 32px;
      margin-bottom: 16px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    
    [data-testid="stSidebar"] .stRadio > label {{
      font-weight: 700;
      font-size: 1.05rem;
    }}
    
    /* ========== MISC ========== */
    .muted {{ 
      color: {p['muted']}; 
      font-size: 1rem;
      font-weight: 500;
    }}
    
    .mono {{
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
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

ASC_SLOPE = 0.54   # per 30-min block
DESC_SLOPE = -0.54 # per 30-min block

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
        rows.append({"Time (CT)": dt.strftime("%H:%M"), "Price": round(price, 4)})
    
    return pd.DataFrame(rows)

# ===============================
# UI Components
# ===============================

def card(title, sub=None, body_fn=None, badge=None, icon=None):
    st.markdown('<div class="spx-card">', unsafe_allow_html=True)
    
    if badge or icon:
        st.markdown('<div class="spx-header">', unsafe_allow_html=True)
        if icon:
            st.markdown(f"<div class='spx-hero-icon'>{icon}</div>", unsafe_allow_html=True)
        st.markdown('<div style="flex:1">', unsafe_allow_html=True)
        if badge:
            st.markdown(f"<div class='spx-badge'><span class='spx-badge-icon'>📊</span>{badge}</div>", unsafe_allow_html=True)
        st.markdown(f"<h4 style='margin:12px 0 4px 0; font-size: 1.8rem; font-weight: 800;'>{title}</h4>", unsafe_allow_html=True)
        if sub: 
            st.markdown(f"<div class='spx-subtitle'>{sub}</div>", unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f"<h4 style='margin:6px 0 4px 0; font-size: 1.8rem; font-weight: 800;'>{title}</h4>", unsafe_allow_html=True)
        if sub: 
            st.markdown(f"<div class='spx-subtitle'>{sub}</div>", unsafe_allow_html=True)
    
    if body_fn:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        body_fn()
    st.markdown("</div>", unsafe_allow_html=True)

# ===============================
# Main App
# ===============================

def main():
    st.set_page_config(
        page_title=APP_NAME, 
        page_icon="🔮", 
        layout="wide", 
        initial_sidebar_state="expanded"
    )

    # Sidebar
    with st.sidebar:
        st.markdown(f"<h1 class='spx-title' style='font-size: 2.4rem;'>🔮 {APP_NAME}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p class='spx-subtitle' style='margin-bottom: 32px; font-size: 1rem;'>{APP_TAGLINE}</p>", unsafe_allow_html=True)
        
        mode = st.radio("🎨 Theme Mode", ["Light", "Dark"], index=0, key="ui_theme")
        inject_theme(mode)
        
        st.markdown("<div style='height: 40px'></div>", unsafe_allow_html=True)
        st.markdown("### ⚙️ System Configuration")
        
        st.markdown("<div class='stat-box'>", unsafe_allow_html=True)
        st.markdown("<div class='stat-icon'>📈</div>", unsafe_allow_html=True)
        st.markdown("<div class='stat-label'>Skyline Slope</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='stat-value'>+{ASC_SLOPE:.2f}</div>", unsafe_allow_html=True)
        st.markdown("<div class='muted' style='font-size: 0.85rem; margin-top: 8px;'>points per 30-min</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='stat-box'>", unsafe_allow_html=True)
        st.markdown("<div class='stat-icon'>📉</div>", unsafe_allow_html=True)
        st.markdown("<div class='stat-label'>Baseline Slope</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='stat-value'>{DESC_SLOPE:.2f}</div>", unsafe_allow_html=True)
        st.markdown("<div class='muted' style='font-size: 0.85rem; margin-top: 8px;'>points per 30-min</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)
        st.caption("🔒 Fixed slope configuration")
        st.caption("⚠️ Maintenance: 4:00pm & 4:30pm auto-skip")

    # Header
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown(f"<h1 class='spx-title'>🔮 {APP_NAME}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p class='spx-subtitle'>{APP_TAGLINE}</p>", unsafe_allow_html=True)
    
    st.markdown(
        "<div class='alert-box'>"
        "<span class='alert-icon'>🕐</span>"
        "<strong style='font-size: 1.15rem;'>Central Time (CT) Operations</strong>"
        "<div style='margin-top: 8px; line-height: 1.6;'>"
        "All timestamps use <strong>Central Time (CT)</strong> timezone. "
        "RTH projections cover <strong>08:30–14:30 CT</strong> in 30-minute intervals. "
        "Anchors typically set on previous day. System automatically excludes 4pm-5pm maintenance window."
        "</div>"
        "</div>",
        unsafe_allow_html=True
    )

    # Main Projection Tool
    def body():
        # Projection Date
        st.markdown("<div class='spx-section'><span class='spx-section-icon'>📅</span>Projection Date Configuration</div>", unsafe_allow_html=True)
        proj_day = st.date_input(
            "Target Projection Date (CT)", 
            value=datetime.now(CT).date(), 
            key="spx_proj_day"
        )

        st.markdown("<div style='height: 40px'></div>", unsafe_allow_html=True)

        # Anchor Configurations
        col1, col2 = st.columns(2, gap="large")
        
        with col1:
            st.markdown("<div class='anchor-panel skyline'>", unsafe_allow_html=True)
            st.markdown(
                "<div class='anchor-header'>"
                "<span class='anchor-icon'>📈</span>"
                "<div class='anchor-title'>Skyline Anchor</div>"
                "</div>",
                unsafe_allow_html=True
            )
            st.markdown("<div class='anchor-desc'>Ascending projection trajectory (+0.54 points per 30-minute interval)</div>", unsafe_allow_html=True)
            
            sky_anchor_date = st.date_input(
                "📆 Anchor Date", 
                value=datetime.now(CT).date() - timedelta(days=1), 
                key="sky_anchor_date"
            )
            sky_price = st.number_input("💰 Anchor Price Level", value=6634.70, step=0.25, key="sky_price", format="%.2f")
            sky_time  = st.time_input("⏰ Anchor Time (CT)", value=dtime(14, 30), step=1800, key="sky_time")
            st.markdown("</div>", unsafe_allow_html=True)
            
        with col2:
            st.markdown("<div class='anchor-panel baseline'>", unsafe_allow_html=True)
            st.markdown(
                "<div class='anchor-header'>"
                "<span class='anchor-icon'>📉</span>"
                "<div class='anchor-title'>Baseline Anchor</div>"
                "</div>",
                unsafe_allow_html=True
            )
            st.markdown("<div class='anchor-desc'>Descending projection trajectory (−0.54 points per 30-minute interval)</div>", unsafe_allow_html=True)
            
            base_anchor_date = st.date_input(
                "📆 Anchor Date", 
                value=datetime.now(CT).date() - timedelta(days=1), 
                key="base_anchor_date"
            )
            base_price = st.number_input("💰 Anchor Price Level", value=6634.70, step=0.25, key="base_price", format="%.2f")
            base_time  = st.time_input("⏰ Anchor Time (CT)", value=dtime(14, 30), step=1800, key="base_time")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height: 48px'></div>", unsafe_allow_html=True)

        # Generate Projections
        slots = rth_slots_ct_dt(proj_day, "08:30", "14:30")
        sky_dt  = CT.localize(datetime.combine(sky_anchor_date, sky_time))
        base_dt = CT.localize(datetime.combine(base_anchor_date, base_time))

        df_sky  = project_line(sky_price,  sky_dt,  ASC_SLOPE,  slots)
        df_base = project_line(base_price, base_dt, DESC_SLOPE, slots)

        # Merge & Display
        merged = pd.DataFrame({"Time (CT)": [dt.strftime("%H:%M") for dt in slots]})
        merged = merged.merge(df_sky.rename(columns={"Price":"Skyline (+0.54)"}), on="Time (CT)", how="left")
        merged = merged.merge(df_base.rename(columns={"Price":"Baseline (−0.54)"}), on="Time (CT)", how="left")

        st.markdown("<div class='spx-section'><span class='spx-section-icon'>📊</span>RTH Projection Results</div>", unsafe_allow_html=True)
        st.dataframe(merged, use_container_width=True, hide_index=True, height=500)

        st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)

        # Download Buttons
        col3, col4 = st.columns(2, gap="large")
        with col3:
            st.download_button(
                "📥 Export Skyline Data",
                df_sky.to_csv(index=False).encode(),
                f"spx_prophet_skyline_{proj_day}.csv",
                "text/csv",
                key="dl_sky",
                use_container_width=True
            )
        with col4:
            st.download_button(
                "📥 Export Baseline Data",
                df_base.to_csv(index=False).encode(),
                f"spx_prophet_baseline_{proj_day}.csv",
                "text/csv",
                key="dl_base",
                use_container_width=True
            )

        st.markdown(
            "<div class='info-note'>"
            "<span class='info-icon'>ℹ️</span>"
            "<span class='muted'><strong>System Note:</strong> Anchor timestamps auto-aligned to nearest 30-minute boundary. "
            "Block calculations automatically exclude 4:00pm and 4:30pm maintenance periods.</span>"
            "</div>",
            unsafe_allow_html=True
        )

    card(
        "Advanced SPX Projection Engine", 
        "Configure anchor points and generate precision RTH market projections",
        body_fn=body, 
        badge="Market Intelligence",
        icon="🎯"
    )

    # Footer
    st.markdown(
        "<div class='footer'>"
        "⚡ <span class='footer-highlight'>SPX Prophet</span> © 2025 • Enterprise-Grade Platform • "
        "Precision Slopes: <span class='mono'>+0.54 / −0.54</span> per 30-min block 📊"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()