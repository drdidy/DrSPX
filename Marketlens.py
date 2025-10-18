# app.py
# Spx Prophet — Enterprise SPX Projection Platform
# Inputs: Skyline/Baseline anchors (time + price). Fixed slopes: +0.52 / -0.52 per 30m.
# Output: 08:30–14:30 CT projections as tables + CSV downloads.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List

APP_NAME = "Spx Prophet"
APP_TAGLINE = "Enterprise SPX Projection Platform"

# ===============================
# THEME — Enterprise Glassmorphism
# ===============================

def theme_css(mode: str):
    dark = {
        "bg": "#0a0f1c",
        "panel": "rgba(16,22,39,0.6)",
        "panelSolid": "#0f1627",
        "text": "#E9EEF7",
        "muted": "#AAB4C8",
        "accent": "#7cc8ff",
        "accent2": "#7cf6c5",
        "border": "rgba(255,255,255,0.12)",
        "shadow": "0 20px 60px rgba(0,0,0,0.55)",
        "glow": "0 0 90px rgba(124,200,255,0.12), 0 0 130px rgba(124,246,197,0.08)"
    }
    light = {
        "bg": "#f8faff",
        "panel": "rgba(255,255,255,0.85)",
        "panelSolid": "#ffffff",
        "text": "#1a2332",
        "muted": "#64748b",
        "accent": "#2563eb",
        "accent2": "#0891b2",
        "border": "rgba(15,23,42,0.08)",
        "shadow": "0 20px 50px rgba(15,23,42,0.08), 0 4px 16px rgba(15,23,42,0.04)",
        "glow": "0 0 100px rgba(37,99,235,0.08), 0 0 140px rgba(8,145,178,0.06)"
    }
    p = dark if mode == "Dark" else light
    
    if mode == "Light":
        grad = (
            "radial-gradient(1400px 900px at 20% 8%, rgba(37,99,235,0.06), transparent 70%),"
            "radial-gradient(1200px 800px at 80% 12%, rgba(8,145,178,0.05), transparent 65%),"
            f"linear-gradient(135deg, {p['bg']} 0%, #ffffff 100%)"
        )
        particles = (
            "radial-gradient(2px 2px at 25% 20%, rgba(37,99,235,0.08), transparent 50%),"
            "radial-gradient(3px 3px at 70% 40%, rgba(8,145,178,0.06), transparent 55%),"
            "radial-gradient(2px 2px at 50% 80%, rgba(37,99,235,0.05), transparent 50%)"
        )
    else:
        grad = (
            "radial-gradient(1100px 700px at 15% 5%, rgba(124,200,255,0.10), transparent 55%),"
            "radial-gradient(900px 600px at 85% 15%, rgba(124,246,197,0.10), transparent 60%),"
            f"linear-gradient(160deg, {p['bg']} 0%, {p['bg']} 100%)"
        )
        particles = (
            "radial-gradient(3px 3px at 30% 25%, rgba(255,255,255,0.06), transparent 60%),"
            "radial-gradient(2px 2px at 65% 35%, rgba(255,255,255,0.05), transparent 60%)"
        )
    
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {{
      background: {grad}, {particles};
      background-attachment: fixed;
      font-family: 'Inter', -apple-system, system-ui, sans-serif;
    }}
    
    [data-testid="stSidebar"] {{
      background: {p['panel']};
      border-right: 1px solid {p['border']};
      backdrop-filter: blur(20px) saturate(180%);
      box-shadow: {p['shadow']};
    }}
    
    [data-testid="stSidebar"] .block-container {{
      padding-top: 2rem;
    }}
    
    .ml-card {{
      background: {p['panel']};
      border: 1px solid {p['border']};
      border-radius: 24px;
      box-shadow: {p['shadow']};
      padding: 32px 36px;
      transition: all .3s cubic-bezier(0.4, 0, 0.2, 1);
      backdrop-filter: blur(16px) saturate(180%);
      position: relative;
      overflow: hidden;
    }}
    
    .ml-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 1px;
      background: linear-gradient(90deg, transparent, {p['accent']}40, transparent);
      opacity: 0;
      transition: opacity .3s ease;
    }}
    
    .ml-card:hover {{ 
      transform: translateY(-4px); 
      border-color: {p['accent']}60; 
      box-shadow: {p['glow']};
    }}
    
    .ml-card:hover::before {{
      opacity: 1;
    }}
    
    .ml-header {{
      display: flex;
      align-items: center;
      gap: 20px;
      margin-bottom: 8px;
    }}
    
    .ml-icon {{
      font-size: 56px;
      line-height: 1;
      filter: drop-shadow(0 4px 12px {p['accent']}30);
    }}
    
    .ml-badge {{
      display: inline-flex; 
      align-items: center; 
      gap: 8px; 
      padding: 8px 18px; 
      border-radius: 999px;
      border: 1px solid {p['border']}; 
      background: linear-gradient(135deg, {p['accent']}15, {p['accent2']}10); 
      font-weight: 700; 
      font-size: .95rem; 
      color: {p['accent']};
      box-shadow: 0 4px 12px {p['accent']}10;
      backdrop-filter: blur(10px);
    }}
    
    .ml-badge-icon {{
      font-size: 1.2rem;
    }}
    
    .ml-title {{
      font-size: 2.8rem;
      font-weight: 800;
      background: linear-gradient(135deg, {p['accent']}, {p['accent2']});
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin: 0;
      letter-spacing: -0.02em;
    }}
    
    .ml-subtitle {{
      color: {p['muted']}; 
      font-size: 1.1rem; 
      font-weight: 500;
      margin-top: 4px;
    }}
    
    .ml-section-title {{
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 1.4rem;
      font-weight: 700;
      color: {p['text']};
      margin: 0 0 16px 0;
    }}
    
    .ml-section-icon {{
      font-size: 1.8rem;
    }}
    
    .input-icon {{
      font-size: 1.5rem;
      margin-right: 8px;
    }}
    
    h1,h2,h3,h4,h5,h6,label,p,span,div {{ 
      color: {p['text']}; 
      font-family: 'Inter', -apple-system, system-ui, sans-serif;
    }}
    
    .stDataFrame div[data-testid="StyledTable"] {{ 
      font-variant-numeric: tabular-nums;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: {p['shadow']};
    }}
    
    .stDownloadButton button, .stButton>button {{
      background: linear-gradient(135deg, {p['accent']}, {p['accent2']});
      color: #ffffff; 
      border: 0; 
      border-radius: 16px; 
      padding: 14px 28px; 
      font-weight: 700;
      font-size: 1rem;
      box-shadow: 0 8px 24px {p['accent']}30;
      transition: all .3s cubic-bezier(0.4, 0, 0.2, 1);
      font-family: 'Inter', sans-serif;
    }}
    
    .stButton>button:hover, .stDownloadButton>button:hover {{ 
      transform: translateY(-2px); 
      box-shadow: 0 12px 32px {p['accent']}40;
    }}
    
    .muted {{ 
      color: {p['muted']}; 
      font-size: .95rem;
    }}
    
    .info-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin: 20px 0;
    }}
    
    .info-box {{
      background: {p['panelSolid']};
      border: 1px solid {p['border']};
      border-radius: 16px;
      padding: 20px;
      text-align: center;
      backdrop-filter: blur(10px);
    }}
    
    .info-box-icon {{
      font-size: 2.5rem;
      margin-bottom: 8px;
    }}
    
    .info-box-label {{
      font-size: .85rem;
      color: {p['muted']};
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    
    .info-box-value {{
      font-size: 1.5rem;
      font-weight: 700;
      color: {p['accent']};
      margin-top: 4px;
    }}
    
    /* Enhanced sidebar styling */
    [data-testid="stSidebar"] h3 {{
      font-size: 1.1rem;
      font-weight: 700;
      margin-top: 24px;
      margin-bottom: 12px;
    }}
    
    [data-testid="stSidebar"] .stRadio > label {{
      font-weight: 600;
      font-size: 1rem;
    }}
    
    /* Input field enhancements */
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input,
    .stTimeInput > div > div > input {{
      border-radius: 12px;
      border: 1px solid {p['border']};
      padding: 12px;
      font-size: 1rem;
      font-weight: 500;
      transition: all .2s ease;
    }}
    
    .stNumberInput > div > div > input:focus,
    .stDateInput > div > div > input:focus,
    .stTimeInput > div > div > input:focus {{
      border-color: {p['accent']};
      box-shadow: 0 0 0 3px {p['accent']}20;
    }}
    
    /* Footer */
    .footer {{
      text-align: center;
      padding: 32px;
      margin-top: 48px;
      border-top: 1px solid {p['border']};
      color: {p['muted']};
      font-size: .9rem;
    }}
    
    .footer-icon {{
      font-size: 1.2rem;
      margin: 0 4px;
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

ASC_SLOPE = 0.52   # per 30-min block
DESC_SLOPE = -0.52 # per 30-min block

def project_line(anchor_price: float, anchor_time_ct: datetime, slope_per_block: float, rth_slots_ct: List[datetime]) -> pd.DataFrame:
    """Align anchor to nearest 30-min boundary and project across RTH slots."""
    minute = 0 if anchor_time_ct.minute < 30 else 30
    anchor_aligned = anchor_time_ct.replace(minute=minute, second=0, microsecond=0)
    rows = []
    for dt in rth_slots_ct:
        blocks = int(round((dt - anchor_aligned).total_seconds() / 1800.0))
        rows.append({"Time (CT)": dt.strftime("%H:%M"), "Price": round(anchor_price + slope_per_block * blocks, 4)})
    return pd.DataFrame(rows)

# ===============================
# UI primitive
# ===============================

def card(title, sub=None, body_fn=None, badge=None, icon=None):
    st.markdown('<div class="ml-card">', unsafe_allow_html=True)
    
    if badge or icon:
        st.markdown('<div class="ml-header">', unsafe_allow_html=True)
        if icon:
            st.markdown(f"<div class='ml-icon'>{icon}</div>", unsafe_allow_html=True)
        st.markdown('<div>', unsafe_allow_html=True)
        if badge:
            st.markdown(f"<div class='ml-badge'><span class='ml-badge-icon'>📊</span>{badge}</div>", unsafe_allow_html=True)
        st.markdown(f"<h4 style='margin:8px 0 2px 0; font-size: 1.6rem; font-weight: 700;'>{title}</h4>", unsafe_allow_html=True)
        if sub: 
            st.markdown(f"<div class='ml-subtitle'>{sub}</div>", unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f"<h4 style='margin:6px 0 2px 0; font-size: 1.6rem; font-weight: 700;'>{title}</h4>", unsafe_allow_html=True)
        if sub: 
            st.markdown(f"<div class='ml-subtitle'>{sub}</div>", unsafe_allow_html=True)
    
    if body_fn:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        body_fn()
    st.markdown("</div>", unsafe_allow_html=True)

# ===============================
# Main App
# ===============================

def main():
    st.set_page_config(
        page_title=APP_NAME, 
        page_icon="📈", 
        layout="wide", 
        initial_sidebar_state="expanded"
    )

    # Sidebar
    with st.sidebar:
        st.markdown(f"<h1 class='ml-title' style='font-size: 2rem;'>⚡ {APP_NAME}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p class='ml-subtitle' style='margin-bottom: 24px;'>{APP_TAGLINE}</p>", unsafe_allow_html=True)
        
        mode = st.radio("🎨 Theme", ["Light", "Dark"], index=0, key="ui_theme")
        inject_theme(mode)
        
        st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)
        st.markdown("### ⚙️ Configuration")
        
        st.markdown("<div class='info-box'>", unsafe_allow_html=True)
        st.markdown("<div class='info-box-icon'>📈</div>", unsafe_allow_html=True)
        st.markdown("<div class='info-box-label'>Ascending Slope</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='info-box-value'>+{ASC_SLOPE:.2f}</div>", unsafe_allow_html=True)
        st.markdown("<div class='muted' style='font-size: 0.8rem; margin-top: 4px;'>per 30-min block</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
        
        st.markdown("<div class='info-box'>", unsafe_allow_html=True)
        st.markdown("<div class='info-box-icon'>📉</div>", unsafe_allow_html=True)
        st.markdown("<div class='info-box-label'>Descending Slope</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='info-box-value'>{DESC_SLOPE:.2f}</div>", unsafe_allow_html=True)
        st.markdown("<div class='muted' style='font-size: 0.8rem; margin-top: 4px;'>per 30-min block</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)
        st.caption("🔒 Slopes are fixed for this edition")

    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"<h1 class='ml-title'>📈 {APP_NAME}</h1>", unsafe_allow_html=True)
        st.markdown(f"<p class='ml-subtitle'>{APP_TAGLINE}</p>", unsafe_allow_html=True)
    
    st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='background: rgba(37,99,235,0.08); border-left: 4px solid #2563eb; padding: 16px 20px; border-radius: 12px; margin-bottom: 32px;'>"
        "<span style='font-size: 1.3rem; margin-right: 8px;'>🕐</span>"
        "<strong>Central Time (CT)</strong> — All inputs and outputs use CT timezone. "
        "Projections span <strong>08:30 to 14:30 CT</strong> in 30-minute intervals."
        "</div>",
        unsafe_allow_html=True
    )

    # Single SPX Anchor Tool
    def body():
        # Projection Day
        st.markdown("<div class='ml-section-title'><span class='ml-section-icon'>📅</span>Projection Date</div>", unsafe_allow_html=True)
        proj_day = st.date_input(
            "Select projection day (Central Time)", 
            value=datetime.now(CT).date(), 
            key="spx_proj_day",
            label_visibility="collapsed"
        )

        st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)

        # Anchor Inputs
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(
                "<div style='background: linear-gradient(135deg, rgba(37,99,235,0.1), rgba(8,145,178,0.08)); "
                "border: 1px solid rgba(37,99,235,0.2); border-radius: 16px; padding: 24px; margin-bottom: 16px;'>",
                unsafe_allow_html=True
            )
            st.markdown(
                "<div class='ml-section-title' style='margin-bottom: 20px;'>"
                "<span class='ml-section-icon'>📈</span>Skyline Anchor</div>",
                unsafe_allow_html=True
            )
            st.markdown("<div class='muted' style='margin-bottom: 16px;'>Ascending projection (+0.52 per 30-min)</div>", unsafe_allow_html=True)
            sky_price = st.number_input("💰 Anchor Price", value=5000.00, step=0.25, key="sky_price")
            sky_time  = st.time_input("🕐 Anchor Time (CT)", value=dtime(17, 0), step=1800, key="sky_time")
            st.markdown("</div>", unsafe_allow_html=True)
            
        with col2:
            st.markdown(
                "<div style='background: linear-gradient(135deg, rgba(8,145,178,0.1), rgba(37,99,235,0.08)); "
                "border: 1px solid rgba(8,145,178,0.2); border-radius: 16px; padding: 24px; margin-bottom: 16px;'>",
                unsafe_allow_html=True
            )
            st.markdown(
                "<div class='ml-section-title' style='margin-bottom: 20px;'>"
                "<span class='ml-section-icon'>📉</span>Baseline Anchor</div>",
                unsafe_allow_html=True
            )
            st.markdown("<div class='muted' style='margin-bottom: 16px;'>Descending projection (−0.52 per 30-min)</div>", unsafe_allow_html=True)
            base_price = st.number_input("💰 Anchor Price", value=4900.00, step=0.25, key="base_price")
            base_time  = st.time_input("🕐 Anchor Time (CT)", value=dtime(17, 0), step=1800, key="base_time")
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height: 32px'></div>", unsafe_allow_html=True)

        # Build slot index
        slots = rth_slots_ct_dt(proj_day, "08:30", "14:30")

        # Compose CT datetimes for anchors
        sky_dt  = CT.localize(datetime.combine(proj_day, sky_time))
        base_dt = CT.localize(datetime.combine(proj_day, base_time))

        # Projections
        df_sky  = project_line(sky_price,  sky_dt,  ASC_SLOPE,  slots)
        df_base = project_line(base_price, base_dt, DESC_SLOPE, slots)

        # Merge view
        merged = pd.DataFrame({"Time (CT)": [dt.strftime("%H:%M") for dt in slots]})
        merged = merged.merge(df_sky.rename(columns={"Price":"Skyline (+0.52)"}), on="Time (CT)", how="left")
        merged = merged.merge(df_base.rename(columns={"Price":"Baseline (−0.52)"}), on="Time (CT)", how="left")

        st.markdown("<div class='ml-section-title'><span class='ml-section-icon'>📊</span>Projection Results</div>", unsafe_allow_html=True)
        st.dataframe(merged, use_container_width=True, hide_index=True)

        st.markdown("<div style='height: 24px'></div>", unsafe_allow_html=True)

        col3, col4 = st.columns(2)
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

        st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='background: rgba(100,116,139,0.08); border-radius: 12px; padding: 16px; text-align: center;'>"
            "<span style='font-size: 1.2rem; margin-right: 8px;'>ℹ️</span>"
            "<span class='muted'>Anchors are automatically aligned to the nearest 30-minute mark before projection calculation</span>"
            "</div>",
            unsafe_allow_html=True
        )

    card(
        "SPX Anchor Projection Tool", 
        "Configure your Skyline and Baseline anchors to generate precise RTH projections",
        body_fn=body, 
        badge="SPX Analysis",
        icon="🎯"
    )

    # Footer
    st.markdown(
        "<div class='footer'>"
        "<span class='footer-icon'>⚡</span> "
        f"<strong>{APP_NAME}</strong> © 2025 • Enterprise Edition • "
        "Fixed slopes: +0.52 / −0.52 per 30-minute block "
        "<span class='footer-icon'>📊</span>"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()