# app.py
# MarketLens Pro — SPX Anchor Edition (Streamlit-only, no external data)
# Inputs: Skyline/Baseline anchors (time + price). Fixed slopes: +0.52 / -0.52 per 30m.
# Output: 08:30–14:30 CT projections as tables + CSV downloads.

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime, date
import pytz
from typing import List

APP_NAME = "MarketLens Pro — SPX Anchor Edition"

# ===============================
# THEME — Glassmorphism (Dark/Light)
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
        "bg": "#f5f8ff",
        "panel": "rgba(255,255,255,0.78)",
        "panelSolid": "#ffffff",
        "text": "#0b1020",
        "muted": "#5d6474",
        "accent": "#0b6cff",
        "accent2": "#0f9d58",
        "border": "rgba(9,16,32,0.12)",
        "shadow": "0 16px 48px rgba(6,11,20,0.14)",
        "glow": "0 0 80px rgba(11,108,255,0.10), 0 0 120px rgba(15,157,88,0.08)"
    }
    p = dark if mode == "Dark" else light
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
    html, body, [data-testid="stAppViewContainer"] {{
      background: {grad}, {particles};
      background-attachment: fixed;
    }}
    [data-testid="stSidebar"] {{
      background: {p['panel']};
      border-right: 1px solid {p['border']};
      backdrop-filter: blur(12px);
    }}
    .ml-card {{
      background: {p['panel']};
      border: 1px solid {p['border']};
      border-radius: 20px;
      box-shadow: {p['shadow']};
      padding: 18px 20px;
      transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
      backdrop-filter: blur(10px);
    }}
    .ml-card:hover {{ transform: translateY(-2px); border-color: {p['accent']}; box-shadow: {p['glow']}; }}
    .ml-pill {{
      display:inline-flex; align-items:center; gap:.45rem; padding: 4px 12px; border-radius: 999px;
      border: 1px solid {p['border']}; background: {p['panelSolid']}; font-weight: 700; font-size: .85rem; color: {p['text']};
    }}
    .ml-sub {{ color: {p['muted']}; font-size: .95rem; }}
    .ml-row {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap:16px; }}
    h1,h2,h3,h4,h5,h6,label,p,span,div {{ color:{p['text']}; font-family: Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto; }}
    .stDataFrame div[data-testid="StyledTable"] {{ font-variant-numeric: tabular-nums; }}
    .stDownloadButton button, .stButton>button {{
      background: linear-gradient(90deg, {p['accent']}, {p['accent2']});
      color: {'#071222' if mode=='Dark' else '#ffffff'}; border: 0; border-radius: 14px; padding: 10px 16px; font-weight: 800;
      box-shadow: {p['shadow']};
    }}
    .stButton>button:hover, .stDownloadButton>button:hover {{ filter:brightness(1.05); transform: translateY(-1px); }}
    .muted {{ color:{p['muted']}; }}
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

def card(title, sub=None, body_fn=None, badge=None):
    st.markdown('<div class="ml-card">', unsafe_allow_html=True)
    if badge:
        st.markdown(f"<div class='ml-pill'>{badge}</div>", unsafe_allow_html=True)
    st.markdown(f"<h4 style='margin:6px 0 2px 0'>{title}</h4>", unsafe_allow_html=True)
    if sub: st.markdown(f"<div class='ml-sub'>{sub}</div>", unsafe_allow_html=True)
    if body_fn:
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        body_fn()
    st.markdown("</div>", unsafe_allow_html=True)

# ===============================
# Main App
# ===============================

def main():
    st.set_page_config(page_title=APP_NAME, page_icon="📈", layout="wide", initial_sidebar_state="expanded")

    # Sidebar
    with st.sidebar:
        mode = st.radio("Theme", ["Dark", "Light"], index=0, key="ui_theme")
        inject_theme(mode)
        st.markdown("### Slopes (per 30-min)")
        st.write(f"**Ascending (Skyline): +{ASC_SLOPE:.2f}**")
        st.write(f"**Descending (Baseline): {DESC_SLOPE:.2f}**")
        st.caption("Slopes are fixed for this edition.")

    st.markdown(f"## {APP_NAME}")
    st.caption("All inputs and outputs use **Central Time (CT)**. Projections are 30-minute blocks from **08:30 to 14:30 CT**.")

    # Single SPX Anchor Tool
    def body():
        # Inputs
        proj_day = st.date_input("Projection Day (CT)", value=datetime.now(CT).date(), key="spx_proj_day")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Skyline Anchor (Ascending)")
            sky_price = st.number_input("Skyline Anchor Price", value=5000.00, step=0.25, key="sky_price")
            sky_time  = st.time_input("Skyline Anchor Time (CT)", value=dtime(17, 0), step=1800, key="sky_time")
        with c2:
            st.markdown("#### Baseline Anchor (Descending)")
            base_price = st.number_input("Baseline Anchor Price", value=4900.00, step=0.25, key="base_price")
            base_time  = st.time_input("Baseline Anchor Time (CT)", value=dtime(17, 0), step=1800, key="base_time")

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

        st.markdown("### Projections")
        st.dataframe(merged, use_container_width=True, hide_index=True)

        c3, c4 = st.columns(2)
        with c3:
            st.download_button(
                "Download Skyline CSV",
                df_sky.to_csv(index=False).encode(),
                "spx_skyline.csv",
                "text/csv",
                key="dl_sky"
            )
        with c4:
            st.download_button(
                "Download Baseline CSV",
                df_base.to_csv(index=False).encode(),
                "spx_baseline.csv",
                "text/csv",
                key="dl_base"
            )

        st.markdown("<div class='muted'>Anchors are aligned to the nearest 30-minute mark before projecting.</div>", unsafe_allow_html=True)

    card("SPX Anchor Projection", "Input your Skyline/Baseline anchors and generate RTH projections (08:30–14:30 CT).", body_fn=body, badge="SPX")

    st.markdown("<div class='muted' style='margin-top:12px'>© 2025 MarketLens Pro • SPX-only edition • Fixed slopes (+0.52 / −0.52) per 30-minute block.</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()