# app.py
# ═══════════════════════════════════════════════════════════════════════════════
# 🔮 SPX PROPHET — Complete Entry/Exit Trading System
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, date, time, timedelta
from typing import List, Tuple

# ───────────────────────────────────────────────────────────────────────────────
# CONFIG & PAGE SETUP
# ───────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SPX Prophet - Professional Trading Analytics", 
    page_icon="📈", 
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

CT = pytz.timezone("America/Chicago")

SLOPE_SPX = 0.25                 # per 30m, fixed
SLOPE_CONTRACT_DEFAULT = -0.33   # per 30m, default descending

RTH_START = time(8, 30)
RTH_END   = time(14, 30)

DEFAULT_ANCHOR = 6400.00
DEFAULT_CONTRACT_3PM = 20.00

# ───────────────────────────────────────────────────────────────────────────────
# ENHANCED STYLING
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    :root {
        --primary: #1e40af;
        --primary-light: #3b82f6;
        --secondary: #059669;
        --accent: #dc2626;
        --surface: #ffffff;
        --surface-2: #f8fafc;
        --surface-3: #f1f5f9;
        --text-primary: #0f172a;
        --text-secondary: #475569;
        --text-muted: #64748b;
        --border: #e2e8f0;
        --border-light: #f1f5f9;
        --success: #10b981;
        --warning: #f59e0b;
        --error: #ef4444;
        --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
        --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
    }
    
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .main > div {
        padding: 2rem 1rem 1rem 1rem;
        background: var(--surface-2);
    }
    
    /* Enhanced Cards */
    .metric-card {
        background: linear-gradient(135deg, var(--surface) 0%, var(--surface-2) 100%);
        border: 1px solid var(--border-light);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: var(--shadow-md);
        transition: all 0.2s ease;
        position: relative;
        overflow: hidden;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
        border-color: var(--primary-light);
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--primary), var(--primary-light));
    }
    
    .metric-value {
        font-size: 1.875rem;
        font-weight: 700;
        color: var(--text-primary);
        margin: 0.5rem 0;
        line-height: 1.2;
    }
    
    .metric-label {
        font-size: 0.875rem;
        font-weight: 500;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.25rem;
    }
    
    .metric-sub {
        font-size: 0.75rem;
        color: var(--text-muted);
        margin-top: 0.5rem;
        line-height: 1.4;
    }
    
    /* Alert/Info Boxes */
    .info-box {
        background: linear-gradient(135deg, #dbeafe 0%, #e0f2fe 100%);
        border-left: 4px solid var(--primary);
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .success-box {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        border-left: 4px solid var(--success);
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border-left: 4px solid var(--warning);
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    /* Main Header */
    .main-header {
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
        color: white;
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    
    .header-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        position: relative;
        z-index: 1;
    }
    
    .header-subtitle {
        font-size: 1.125rem;
        opacity: 0.9;
        position: relative;
        z-index: 1;
    }
    
    /* Enhanced Tables */
    .dataframe {
        border-radius: 8px !important;
        overflow: hidden !important;
        box-shadow: var(--shadow-sm) !important;
        border: 1px solid var(--border) !important;
    }
    
    .dataframe th {
        background: var(--surface-3) !important;
        color: var(--text-secondary) !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        padding: 0.75rem !important;
        border-bottom: 1px solid var(--border) !important;
    }
    
    .dataframe td {
        padding: 0.75rem !important;
        border-bottom: 1px solid var(--border-light) !important;
        font-family: 'Inter', monospace !important;
    }
    
    /* Button Enhancements */
    .stButton > button {
        border-radius: 8px !important;
        border: none !important;
        background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%) !important;
        color: white !important;
        font-weight: 500 !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.2s ease !important;
        box-shadow: var(--shadow-sm) !important;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px) !important;
        box-shadow: var(--shadow-md) !important;
    }
    
    /* Form Section */
    .form-section {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: var(--shadow-sm);
    }
    
    .pair-section {
        background: var(--surface);
        border: 2px solid var(--border-light);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }
    
    .bounce-section {
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        border: 1px solid #10b981;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    .rejection-section {
        background: linear-gradient(135deg, #fef2f2 0%, #fecaca 100%);
        border: 1px solid #ef4444;
        border-radius: 8px;
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# TIME / BLOCK HELPERS
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
    return dt.hour == 16  # CME maintenance 4–5 PM CT

def in_weekend_gap(dt: datetime) -> bool:
    wd = dt.weekday()  # Mon=0..Sun=6
    if wd == 5: return True
    if wd == 6 and dt.hour < 17: return True
    if wd == 4 and dt.hour >= 17: return True
    return False

def count_blocks_spx(t0: datetime, t1: datetime) -> int:
    """SPX 30m blocks, skipping 4–5 PM + weekend gap (count if block END is valid)."""
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
    """Contract valid blocks from 3 PM anchor-day to target: Count 3:00→3:30 PM = 1, Skip 3:30→7:00 PM, Count 7:00 PM → target in 30m steps (3 PM → 8:30 AM = 28 blocks)"""
    target_dt = fmt_ct(target_dt)
    anchor_3pm   = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    anchor_330pm = fmt_ct(datetime.combine(anchor_day, time(15, 30)))
    anchor_7pm   = fmt_ct(datetime.combine(anchor_day, time(19, 0)))
    if target_dt <= anchor_3pm: return 0
    blocks = 1 if target_dt >= anchor_330pm else 0  # 3:00→3:30
    if target_dt > anchor_7pm:
        delta_min = int((target_dt - anchor_7pm).total_seconds() // 60)
        blocks += delta_min // 30
    return blocks

def blocks_simple_30m(d1: datetime, d2: datetime) -> int:
    """Plain 30m step count (used between two overnight bounces and after 8:30)."""
    d1 = fmt_ct(d1); d2 = fmt_ct(d2)
    if d2 <= d1: return 0
    return int((d2 - d1).total_seconds() // (30*60))

# ───────────────────────────────────────────────────────────────────────────────
# FAN & PROJECTIONS
# ───────────────────────────────────────────────────────────────────────────────
def fan_levels_for_slot(anchor_close: float, anchor_time: datetime, slot_dt: datetime) -> Tuple[float,float]:
    blocks = count_blocks_spx(anchor_time, slot_dt)
    top = round(anchor_close + SLOPE_SPX * blocks, 2)
    bot = round(anchor_close - SLOPE_SPX * blocks, 2)
    return top, bot

def sigma_bands_at_830(anchor_close: float, anchor_day: date) -> Tuple[float, float, int]:
    anchor_3pm = fmt_ct(datetime.combine(anchor_day, time(15, 0)))
    next_830   = fmt_ct(datetime.combine(anchor_day + timedelta(days=1), time(8, 30)))
    blocks_830 = count_blocks_spx(anchor_3pm, next_830)  # ≈34
    move = SLOPE_SPX * blocks_830
    return round(move, 2), round(2*move, 2), blocks_830  # ±move, ±2*move

def calculate_rejection_exit(rejection_dt1: datetime, rejection_dt2: datetime, 
                           contract_r1: float, contract_r2: float, target_dt: datetime) -> float:
    """Calculate contract exit level based on rejection line extended to target time"""
    if rejection_dt2 <= rejection_dt1:
        return 0.0
    
    # Calculate rejection slope using simple 30m blocks (overnight rejections)
    rejection_blocks = blocks_simple_30m(rejection_dt1, rejection_dt2)
    if rejection_blocks <= 0:
        return 0.0
    
    rejection_slope = (contract_r2 - contract_r1) / rejection_blocks
    
    # Project from second rejection point to target time
    target_blocks = blocks_simple_30m(rejection_dt2, target_dt)
    exit_level = contract_r2 + (rejection_slope * target_blocks)
    
    return round(exit_level, 2)

# ───────────────────────────────────────────────────────────────────────────────
# MAIN HEADER
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class='main-header'>
    <div class='header-title'>🔮 SPX Prophet</div>
    <div class='header-subtitle'>Complete Entry/Exit Trading Analytics System</div>
</div>
""", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# ENHANCED SIDEBAR
# ───────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    # Help and Reset buttons
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("❓ Help", key="help_toggle"):
            st.session_state.show_help = not st.session_state.show_help
    with col2:
        if st.button("🔄 Reset", key="reset_data"):
            st.session_state.bc_result = None
            st.session_state.rejection_result = None
            st.rerun()
    
    if st.session_state.show_help:
        st.markdown("""
        <div class='info-box'>
            <strong>Complete System Guide:</strong><br>
            • Set SPX anchor (≤3:00 PM close)<br>
            • Configure PDH/PDL key levels<br>
            • Use BC Forecast for bounce-rejection pairs<br>
            • Review Plan Card for complete strategy
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Date Configuration
    st.markdown("#### 📅 Trading Session")
    today_ct = fmt_ct(datetime.now()).date()
    prev_day = st.date_input("Previous Trading Day", value=today_ct - timedelta(days=1), help="The day of your SPX anchor close")
    proj_day = st.date_input("Projection Day", value=prev_day + timedelta(days=1), help="The day you're projecting for")
    
    st.markdown("#### 💰 Market Data")
    
    # Main inputs
    anchor_close = st.number_input(
        "SPX Anchor (≤ 3:00 PM CT Close)", 
        value=float(DEFAULT_ANCHOR), 
        step=0.25, 
        format="%.2f",
        help="SPX closing price at or before 3:00 PM CT on previous trading day"
    )
    
    contract_3pm = st.number_input(
        "Contract Price @ 3:00 PM", 
        value=float(DEFAULT_CONTRACT_3PM), 
        step=0.05, 
        format="%.2f",
        help="Contract price at 3:00 PM CT on previous trading day"
    )
    
    st.markdown("#### 📊 Key Levels")
    
    # PDH/PDL
    col1, col2 = st.columns(2)
    with col1:
        pdh = st.number_input("PDH", value=anchor_close + 10.0, step=0.25, format="%.2f", help="Previous Day High")
    with col2:
        pdl = st.number_input("PDL", value=anchor_close - 10.0, step=0.25, format="%.2f", help="Previous Day Low")
    
    # Overnight levels (optional)
    use_on = st.checkbox("Include Overnight High/Low", value=False, help="Track ONH/ONL if available")
    
    if use_on:
        col1, col2 = st.columns(2)
        with col1:
            onh = st.number_input("ONH", value=anchor_close + 5.0, step=0.25, format="%.2f", help="Overnight High")
        with col2:
            onl = st.number_input("ONL", value=anchor_close - 5.0, step=0.25, format="%.2f", help="Overnight Low")
    else:
        onh = anchor_close + 5.0
        onl = anchor_close - 5.0
    
    # Status information
    st.markdown("---")
    st.markdown("#### 📈 System Status")
    
    current_time = fmt_ct(datetime.now())
    market_status = "🔴 Closed"
    if RTH_START <= current_time.time() <= RTH_END and current_time.weekday() < 5:
        market_status = "🟢 Open"
    elif current_time.time() < RTH_START and current_time.weekday() < 5:
        market_status = "🟡 Pre-Market"
    
    st.markdown(f"**Market:** {market_status}")
    st.markdown(f"**Time:** {current_time.strftime('%H:%M CT')}")
    
    # Quick stats
    sigma1, sigma2, spx_blocks_to_830 = sigma_bands_at_830(anchor_close, prev_day)
    st.markdown(f"**Blocks to 8:30:** {spx_blocks_to_830}")
    st.markdown(f"**1σ Band:** ±{sigma1:.2f}")

# ───────────────────────────────────────────────────────────────────────────────
# ENHANCED HEADER METRICS
# ───────────────────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-label'>SPX Anchor</div>
        <div class='metric-value'>💠 {anchor_close:.2f}</div>
        <div class='metric-sub'>≤ 3:00 PM CT Close</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-label'>Sigma Bands @ 8:30</div>
        <div class='metric-value'>±{sigma1:.2f} / ±{sigma2:.2f}</div>
        <div class='metric-sub'>{spx_blocks_to_830} blocks @ {SLOPE_SPX:.2f}/30m</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    mag_to_830 = abs(SLOPE_CONTRACT_DEFAULT)*28
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-label'>Contract Projection</div>
        <div class='metric-value'>≈ ±{mag_to_830:.2f}</div>
        <div class='metric-sub'>28 blocks @ {SLOPE_CONTRACT_DEFAULT:.2f}/30m</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    rejection_status = "✅ Active" if st.session_state.get("rejection_result") else "⚪ Not Set"
    on_text = f"ONH/ONL: {onh:.2f}/{onl:.2f}" if use_on else "ONH/ONL: Not tracked"
    st.markdown(f"""
    <div class='metric-card'>
        <div class='metric-label'>Key Levels</div>
        <div class='metric-value'>{pdh:.2f} / {pdl:.2f}</div>
        <div class='metric-sub'>{on_text} • Exits: {rejection_status}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────────
# ENHANCED TABS
# ───────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 SPX Anchors", "🎯 BC Forecast", "📋 Trading Plan"])

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 1 — Enhanced SPX Anchors with Entry/Exit                                ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab1:
    st.markdown("### 📊 SPX Anchor Levels - Complete Entry/Exit Projections")
    st.markdown("Real-time anchor levels and contract entry/exit projections for 30-minute intervals from 8:30 AM to 2:30 PM CT")
    
    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))

    # Use BC result if available
    bc = st.session_state.get("bc_result", None)
    rejection_result = st.session_state.get("rejection_result", None)
    
    contract_slope = SLOPE_CONTRACT_DEFAULT
    contract_ref_dt = fmt_ct(datetime.combine(prev_day, time(15, 0)))
    contract_ref_px = float(contract_3pm)
    
    if bc and "contract" in bc:
        contract_slope = float(bc["contract"]["slope"])
        contract_ref_dt = bc["contract"]["ref_dt"]
        contract_ref_px = float(bc["contract"]["ref_price"])
        
        status_msg = "✅ BC Forecast Active"
        if rejection_result:
            status_msg += " + Exit Projections Enabled"
        
        st.markdown(f"""
        <div class='success-box'>
            <strong>{status_msg}</strong><br>
            Projections below include BC-fitted slopes and rejection-based exit levels.
        </div>
        """, unsafe_allow_html=True)

    def contract_proj_for_slot(slot_dt: datetime) -> float:
        """Enhanced contract projection with clear logic"""
        dt_830 = fmt_ct(datetime.combine(proj_day, time(8,30)))
        if contract_ref_dt.time() == time(15,0) and contract_ref_dt.date() == prev_day:
            base_blocks = count_blocks_contract(prev_day, min(slot_dt, dt_830))
            if slot_dt <= dt_830:
                total_blocks = base_blocks
            else:
                total_blocks = base_blocks + blocks_simple_30m(dt_830, slot_dt)
        else:
            total_blocks = blocks_simple_30m(contract_ref_dt, slot_dt)
        return round(contract_ref_px + contract_slope * total_blocks, 2)

    # Build tables with enhanced formatting including exits
    rows_close, rows_high, rows_low = [], [], []
    key_times = ["08:30", "10:00", "12:00", "13:30", "14:30"]
    
    for slot in rth_slots_ct(proj_day):
        tlabel = slot.strftime("%H:%M")
        top, bot = fan_levels_for_slot(anchor_close, anchor_time, slot)
        is_key = tlabel in key_times
        
        # SPX projection from BC
        spx_proj_val = ""
        if bc and "table" in bc:
            try:
                spx_proj_val = float(bc["table"].loc[bc["table"]["Time"]==tlabel, "SPX Entry"].iloc[0])
            except Exception:
                spx_proj_val = ""

        # Contract entry projection
        c_proj = contract_proj_for_slot(slot)
        
        # Contract exit projection
        c_exit = ""
        if rejection_result:
            c_exit_val = calculate_rejection_exit(
                rejection_result['r1_dt'], rejection_result['r2_dt'],
                rejection_result['c_r1'], rejection_result['c_r2'], slot
            )
            if c_exit_val:
                c_exit = f"{c_exit_val:.2f}"
        
        # Calculate entry/exit spread
        entry_exit_spread = ""
        if c_exit and c_exit != "":
            try:
                spread = c_proj - float(c_exit)
                entry_exit_spread = f"{spread:.2f}"
            except:
                entry_exit_spread = "—"
        
        # Enhanced row data
        row_base = {
            "⭐": "🎯" if is_key else ("⭐" if tlabel=="08:30" else ""),
            "Time": tlabel,
            "Top": f"{top:.2f}",
            "Bottom": f"{bot:.2f}",
            "SPX Entry": f"{spx_proj_val:.2f}" if spx_proj_val else "—",
            "Contract Entry": f"{c_proj:.2f}",
            "Contract Exit": c_exit if c_exit else "—",
            "Entry/Exit Spread": entry_exit_spread if entry_exit_spread else "—",
            "Range": f"{top - bot:.2f}"
        }
        
        rows_close.append(row_base.copy())
        
        # For high/low tables, remove irrelevant columns
        high_row = {k: v for k, v in row_base.items() if k not in ["Bottom"]}
        low_row = {k: v for k, v in row_base.items() if k not in ["Top"]}
        
        rows_high.append(high_row)
        rows_low.append(low_row)

    # Display tables with better organization
    tab_col1, tab_col2, tab_col3 = st.tabs(["📈 Complete Entry/Exit", "⬆️ High/Resistance Levels", "⬇️ Low/Support Levels"])
    
    with tab_col1:
        st.markdown("**Complete projection table with entry/exit levels and spreads**")
        df_close = pd.DataFrame(rows_close)
        st.dataframe(df_close, use_container_width=True, hide_index=True)
    
    with tab_col2:
        st.markdown("**Focus on resistance/high levels and entries**")
        df_high = pd.DataFrame(rows_high)
        st.dataframe(df_high, use_container_width=True, hide_index=True)
    
    with tab_col3:
        st.markdown("**Focus on support/low levels and entries**")
        df_low = pd.DataFrame(rows_low)
        st.dataframe(df_low, use_container_width=True, hide_index=True)
    
    # Quick analysis
    st.markdown("### 📊 Quick Analysis")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        morning_range = fan_levels_for_slot(anchor_close, anchor_time, fmt_ct(datetime.combine(proj_day, time(8, 30))))
        morning_width = morning_range[0] - morning_range[1]
        st.metric("8:30 AM Range Width", f"{morning_width:.2f}", help="Distance between top and bottom levels at market open")
    
    with col2:
        close_range = fan_levels_for_slot(anchor_close, anchor_time, fmt_ct(datetime.combine(proj_day, time(14, 30))))
        close_width = close_range[0] - close_range[1]
        st.metric("2:30 PM Range Width", f"{close_width:.2f}", help="Expected range width at market close")
    
    with col3:
        expansion = close_width - morning_width
        if morning_width > 0:
            expansion_pct = f"{(expansion/morning_width)*100:.1f}%"
        else:
            expansion_pct = "N/A"
        st.metric("Range Expansion", f"{expansion:.2f}", delta=expansion_pct)

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 2 — Complete BC Forecast with Bounce-Rejection Pairs                   ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab2:
    st.markdown("### 🎯 BC Forecast - Complete Entry/Exit System")
    
    st.markdown("""
    <div class='info-box'>
        <strong>Complete Trading System Setup:</strong><br>
        • Configure bounce-rejection pairs for complete entry/exit projections<br>
        • Each bounce provides entry calculations, each rejection provides exit calculations<br>
        • System projects both entry and exit levels through all RTH periods<br>
        • Time window: 3:30 PM (previous day) → 8:00 AM (projection day)
    </div>
    """, unsafe_allow_html=True)

    # Build time window (3:30 PM prev day → 8:00 AM proj day)
    start_bounces = fmt_ct(datetime.combine(prev_day, time(15, 30)))
    end_bounces   = fmt_ct(datetime.combine(proj_day, time(8, 0)))
    tmp_slots, cur = [], start_bounces
    while cur <= end_bounces:
        tmp_slots.append(cur)
        cur += timedelta(minutes=30)
    
    bounce_slots = [dt.strftime("%Y-%m-%d %H:%M") for dt in tmp_slots]
    bounce_display = [f"{dt.strftime('%a %m/%d %H:%M')} CT" for dt in tmp_slots]

    # Enhanced form with bounce-rejection pairs
    with st.form("complete_bc_form", clear_on_submit=False):
        
        st.markdown("#### 🔄 Configure Bounce-Rejection Pairs")
        st.markdown("*Set up each bounce with its corresponding rejection for complete entry/exit system*")
        
        col1, col2 = st.columns(2)
        
        # LEFT COLUMN: First Bounce → First Rejection Pair
        with col1:
            st.markdown("""
            <div class='pair-section'>
                <h4>🔵 First Bounce-Rejection Pair</h4>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class='bounce-section'>
                <strong>🟢 First Bounce (Entry Calculation)</strong>
            </div>
            """, unsafe_allow_html=True)
            
            b1_idx = st.selectbox(
                "Time Slot", 
                range(len(bounce_slots)), 
                format_func=lambda x: bounce_display[x], 
                index=0, 
                key="bc_b1",
                help="When the first bounce occurred"
            )
            col_b1_1, col_b1_2 = st.columns(2)
            with col_b1_1:
                spx_b1 = st.number_input("SPX Price", value=anchor_close, step=0.25, format="%.2f", key="spx_b1")
            with col_b1_2:
                c_b1 = st.number_input("Contract Price", value=contract_3pm, step=0.05, format="%.2f", key="c_b1")
            
            st.markdown("""
            <div class='rejection-section'>
                <strong>🔴 First Rejection (Exit Calculation)</strong>
            </div>
            """, unsafe_allow_html=True)
            
            r1_idx = st.selectbox(
                "Time Slot", 
                range(len(bounce_slots)), 
                format_func=lambda x: bounce_display[x], 
                index=min(5, len(bounce_slots)-1), 
                key="rej_r1",
                help="When the first rejection occurred (should be AFTER first bounce)"
            )
            col_r1_1, col_r1_2 = st.columns(2)
            with col_r1_1:
                spx_r1 = st.number_input("SPX Price", value=anchor_close + 5.0, step=0.25, format="%.2f", key="spx_r1")
            with col_r1_2:
                c_r1 = st.number_input("Contract Price", value=contract_3pm + 2.0, step=0.05, format="%.2f", key="c_r1")
            
            st.markdown("</div>", unsafe_allow_html=True)
            
        # RIGHT COLUMN: Second Bounce → Second Rejection Pair    
        with col2:
            st.markdown("""
            <div class='pair-section'>
                <h4>🔵 Second Bounce-Rejection Pair</h4>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <div class='bounce-section'>
                <strong>🟢 Second Bounce (Entry Calculation)</strong>
            </div>
            """, unsafe_allow_html=True)
            
            default_b2 = min(10, len(bounce_slots)-1)
            b2_idx = st.selectbox(
                "Time Slot", 
                range(len(bounce_slots)), 
                format_func=lambda x: bounce_display[x], 
                index=default_b2, 
                key="bc_b2",
                help="When the second bounce occurred"
            )
            col_b2_1, col_b2_2 = st.columns(2)
            with col_b2_1:
                spx_b2 = st.number_input("SPX Price", value=anchor_close, step=0.25, format="%.2f", key="spx_b2")
            with col_b2_2:
                c_b2 = st.number_input("Contract Price", value=contract_3pm, step=0.05, format="%.2f", key="c_b2")
            
            st.markdown("""
            <div class='rejection-section'>
                <strong>🔴 Second Rejection (Exit Calculation)</strong>
            </div>
            """, unsafe_allow_html=True)
            
            r2_idx = st.selectbox(
                "Time Slot", 
                range(len(bounce_slots)), 
                format_func=lambda x: bounce_display[x], 
                index=min(15, len(bounce_slots)-1), 
                key="rej_r2",
                help="When the second rejection occurred (should be AFTER second bounce)"
            )
            col_r2_1, col_r2_2 = st.columns(2)
            with col_r2_1:
                spx_r2 = st.number_input("SPX Price", value=anchor_close + 7.0, step=0.25, format="%.2f", key="spx_r2")
            with col_r2_2:
                c_r2 = st.number_input("Contract Price", value=contract_3pm + 3.0, step=0.05, format="%.2f", key="c_r2")
            
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")
        
        # Optional: Skip rejections checkbox
        skip_rejections = st.checkbox("Skip rejection calculations (entries only)", value=False, help="Check this if you only want entry projections without exits")

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            submitted = st.form_submit_button("🚀 Generate Complete Entry/Exit Forecast", use_container_width=True)

    if submitted:
        with st.spinner("Calculating Complete Entry/Exit Forecast..."):
            try:
                b1_dt = fmt_ct(datetime.strptime(bounce_slots[b1_idx], "%Y-%m-%d %H:%M"))
                b2_dt = fmt_ct(datetime.strptime(bounce_slots[b2_idx], "%Y-%m-%d %H:%M"))
                
                if b2_dt <= b1_dt:
                    st.error("⚠️ Second bounce must be after first bounce.")
                else:
                    # Calculate bounce slopes (entry system)
                    spx_blocks = count_blocks_spx(b1_dt, b2_dt)
                    if spx_blocks <= 0:
                        st.error("⚠️ Bounces must be at least 30 minutes apart with valid blocks.")
                    else:
                        spx_slope = (float(spx_b2) - float(spx_b1)) / spx_blocks
                        
                        # Contract slope for bounces
                        bounce_blocks = blocks_simple_30m(b1_dt, b2_dt)
                        contract_slope = SLOPE_CONTRACT_DEFAULT
                        if bounce_blocks > 0 and (c_b2 != c_b1):
                            contract_slope = float((float(c_b2) - float(c_b1)) / bounce_blocks)

                        # Calculate rejection slopes if NOT skipped
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
                                else:
                                    st.warning("⚠️ Second rejection must be after first rejection. Exit projections disabled.")
                            except Exception as e:
                                st.warning(f"⚠️ Rejection calculation error: {e}. Entry projections will proceed.")

                        # Build comprehensive projection table
                        rows = []
                        anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
                        
                        for slot in rth_slots_ct(proj_day):
                            top, bot = fan_levels_for_slot(anchor_close, anchor_time, slot)
                            spx_proj = round(float(spx_b2) + spx_slope * count_blocks_spx(b2_dt, slot), 2)
                            blocks_from_b2 = blocks_simple_30m(b2_dt, slot)
                            c_proj = round(float(c_b2) + contract_slope * blocks_from_b2, 2)
                            
                            # Calculate exit levels if rejections are configured
                            c_exit = ""
                            spx_exit = ""
                            entry_exit_spread = ""
                            
                            if rejection_data:
                                c_exit_val = calculate_rejection_exit(
                                    rejection_data['r1_dt'], rejection_data['r2_dt'],
                                    rejection_data['c_r1'], rejection_data['c_r2'], slot
                                )
                                if c_exit_val:
                                    c_exit = f"{c_exit_val:.2f}"
                                    entry_exit_spread = f"{c_proj - c_exit_val:.2f}"
                                
                                # SPX exit projection
                                exit_blocks = blocks_simple_30m(rejection_data['r2_dt'], slot)
                                spx_exit = round(rejection_data['spx_r2'] + rejection_data['spx_rej_slope'] * exit_blocks, 2)
                            
                            rows.append({
                                "⭐": "🎯" if slot.strftime("%H:%M") in ["08:30", "10:00", "12:00", "14:30"] else "",
                                "Time": slot.strftime("%H:%M"),
                                "Top": top, 
                                "Bottom": bot,
                                "SPX Entry": spx_proj,
                                "Contract Entry": c_proj,
                                "SPX Exit": spx_exit if spx_exit else "—",
                                "Contract Exit": c_exit if c_exit else "—",
                                "Entry/Exit Spread": entry_exit_spread if entry_exit_spread else "—"
                            })
                        
                        out_df = pd.DataFrame(rows)
                        
                        # Success message with key stats
                        success_msg = "✅ Complete Entry/Exit Forecast Generated!"
                        if rejection_data:
                            success_msg += " Both entry and exit projections calculated."
                        else:
                            success_msg += " Entry projections calculated (exits skipped)."
                        
                        st.markdown(f"""
                        <div class='success-box'>
                            <strong>{success_msg}</strong><br>
                            Review comprehensive projections below.
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Display enhanced metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("SPX Entry Slope", f"{spx_slope:.3f}", help="SPX entry slope per 30-minute block")
                        with col2:
                            st.metric("Contract Entry Slope", f"{contract_slope:.3f}", help="Contract entry slope per 30-minute block")
                        with col3:
                            if rejection_data:
                                st.metric("SPX Exit Slope", f"{rejection_data['spx_rej_slope']:.3f}", help="SPX exit slope per 30-minute block")
                            else:
                                st.metric("SPX Exit Slope", "—", help="No rejection data")
                        with col4:
                            if rejection_data:
                                st.metric("Contract Exit Slope", f"{rejection_data['contract_rej_slope']:.3f}", help="Contract exit slope per 30-minute block")
                            else:
                                st.metric("Contract Exit Slope", "—", help="No rejection data")
                        
                        # Direction analysis
                        col1, col2 = st.columns(2)
                        with col1:
                            entry_direction = "📈 Bullish Entry" if spx_slope > 0 else "📉 Bearish Entry"
                            st.markdown(f"**Entry Bias:** {entry_direction}")
                        with col2:
                            if rejection_data:
                                exit_direction = "📈 Rising Exits" if rejection_data['spx_rej_slope'] > 0 else "📉 Falling Exits"
                                st.markdown(f"**Exit Pattern:** {exit_direction}")
                            else:
                                st.markdown("**Exit Pattern:** Not configured")
                        
                        # Main comprehensive projection table
                        st.markdown("### 📊 Complete RTH Projections (Entries + Exits)")
                        st.dataframe(out_df, use_container_width=True, hide_index=True)
                        
                        # Enhanced band analysis
                        spx_band = sigma1
                        c_band_28 = round(abs(contract_slope) * 28, 2)
                        c_exit_band = round(abs(rejection_data['contract_rej_slope']) * 28, 2) if rejection_data else 0
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown(f"""
                            <div class='metric-card'>
                                <div class='metric-label'>SPX Overnight Band</div>
                                <div class='metric-value'>±{spx_band:.2f}</div>
                                <div class='metric-sub'>1σ: ±{sigma1:.2f} • 2σ: ±{sigma2:.2f}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            st.markdown(f"""
                            <div class='metric-card'>
                                <div class='metric-label'>Contract Entry Band</div>
                                <div class='metric-value'>±{c_band_28:.2f}</div>
                                <div class='metric-sub'>28 blocks @ {contract_slope:.3f}/30m</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col3:
                            if c_exit_band:
                                st.markdown(f"""
                                <div class='metric-card'>
                                    <div class='metric-label'>Contract Exit Band</div>
                                    <div class='metric-value'>±{c_exit_band:.2f}</div>
                                    <div class='metric-sub'>28 blocks @ {rejection_data['contract_rej_slope']:.3f}/30m</div>
                                </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.markdown(f"""
                                <div class='metric-card'>
                                    <div class='metric-label'>Contract Exit Band</div>
                                    <div class='metric-value'>—</div>
                                    <div class='metric-sub'>No rejection data</div>
                                </div>
                                """, unsafe_allow_html=True)

                        # Store in session state
                        st.session_state["bc_result"] = {
                            "table": out_df,
                            "spx_slope": spx_slope,
                            "b2_dt": b2_dt,
                            "spx_b2": float(spx_b2),
                            "contract": {"slope": contract_slope, "ref_price": float(c_b2), "ref_dt": b2_dt},
                        }
                        
                        # Store rejection data separately
                        if rejection_data:
                            st.session_state["rejection_result"] = rejection_data
                        else:
                            st.session_state["rejection_result"] = None
                        
                        # Auto-refresh other tabs
                        st.success("🔄 Complete system updated! Check other tabs for enhanced projections with entries and exits.")

            except Exception as e:
                st.error(f"❌ Forecast generation failed: {e}")
                st.markdown("""
                <div class='warning-box'>
                    <strong>Troubleshooting Tips:</strong><br>
                    • Ensure all times are in correct chronological order<br>
                    • Check that SPX and contract prices are reasonable<br>
                    • Verify rejection points occur after bounce points<br>
                    • Make sure time slots are at least 30 minutes apart
                </div>
                """, unsafe_allow_html=True)

# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║ TAB 3 — Complete Trading Plan                                               ║
# ╚═════════════════════════════════════════════════════════════════════════════╝
with tab3:
    st.markdown("### 📋 Complete Trading Plan - Entry & Exit Strategy (Ready by 8:00 AM)")
    
    # Quick status check
    current_ct = fmt_ct(datetime.now())
    plan_ready_time = fmt_ct(datetime.combine(proj_day, time(8, 0)))
    
    if current_ct >= plan_ready_time:
        status_msg = "🟢 **Plan Active** - Ready for complete trading session"
        status_class = "success-box"
    elif current_ct >= plan_ready_time - timedelta(hours=1):
        status_msg = "🟡 **Plan Preparation** - Final setup in progress"
        status_class = "warning-box"
    else:
        status_msg = "🔵 **Plan Preview** - Preliminary configuration"
        status_class = "info-box"
    
    st.markdown(f"""
    <div class='{status_class}'>
        {status_msg}
    </div>
    """, unsafe_allow_html=True)

    # Calculate key levels
    anchor_time = fmt_ct(datetime.combine(prev_day, time(15, 0)))
    slot_830    = fmt_ct(datetime.combine(proj_day, time(8, 30)))
    top_830, bot_830 = fan_levels_for_slot(anchor_close, anchor_time, slot_830)

    bc = st.session_state.get("bc_result", None)

    # Enhanced plan cards
    col1, col2 = st.columns(2)
    
    with col1:
        on_display = f"<br>ONH/ONL: {onh:.2f} / {onl:.2f}" if use_on else ""
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>📊 Market Foundation</div>
            <div class='metric-value'>Anchor: {anchor_close:.2f}</div>
            <div class='metric-sub'>
                8:30 Fan: {top_830:.2f} (top) • {bot_830:.2f} (bottom)<br>
                Bands: ±{sigma1:.2f} (1σ) • ±{sigma2:.2f} (2σ)<br>
                PDH/PDL: {pdh:.2f} / {pdl:.2f}{on_display}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Contract projection
        if bc and "contract" in bc:
            c_slope = float(bc["contract"]["slope"])
            c_ref_dt = bc["contract"]["ref_dt"]
            c_ref_px = float(bc["contract"]["ref_price"])
            blocks = blocks_simple_30m(c_ref_dt, slot_830)
            c_830 = round(c_ref_px + c_slope * blocks, 2)
            slope_used = c_slope
            source = "BC-fitted"
        else:
            c_830 = round(float(contract_3pm) + SLOPE_CONTRACT_DEFAULT * 28, 2)
            slope_used = SLOPE_CONTRACT_DEFAULT
            source = "default"

        slope_direction = "📈 Ascending" if slope_used > 0 else "📉 Descending"
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>💼 Contract Analysis</div>
            <div class='metric-value'>3PM: {float(contract_3pm):.2f} → 8:30: {c_830:.2f}</div>
            <div class='metric-sub'>
                Slope: {slope_used:.3f}/30m ({source})<br>
                Direction: {slope_direction}<br>
                Change: {c_830 - float(contract_3pm):.2f}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Trading strategy cards
    col1, col2 = st.columns(2)
    
    with col1:
        # Determine optimal sell level
        sell_level = max(top_830, pdh) if use_on else max(top_830, pdh, onh) if use_on else top_830
        buy_level = min(bot_830, pdl) if use_on else min(bot_830, pdl, onl) if use_on else bot_830
        
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>🎯 Action Levels</div>
            <div class='metric-value' style='font-size: 1.2rem;'>
                Sell Zone: {sell_level:.2f}<br>
                Buy Zone: {buy_level:.2f}
            </div>
            <div class='metric-sub'>
                Stop Loss: 2-3 points beyond level<br>
                First Target: Opposite edge<br>
                Stretch Target: PDH/PDL if closer
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Risk management
        range_width = sell_level - buy_level
        suggested_stop = round(range_width * 0.15, 2)  # 15% of range
        
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-label'>⚡ Risk Management</div>
            <div class='metric-value' style='font-size: 1.2rem;'>
                Range: {range_width:.2f}<br>
                Suggested Stop: {suggested_stop:.2f}
            </div>
            <div class='metric-sub'>
                Position Size: Based on stop distance<br>
                Max Risk: 1-2% of account<br>
                Time Stops: Avoid 11:30-12:30 chop
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Key time projections table with entry/exit
    st.markdown("### ⏰ Key Time Projections (Entry/Exit System)")
    
    key_times = ["08:30", "09:00", "10:00", "11:00", "12:00", "13:00", "13:30", "14:30"]
    proj_rows = []
    
    # Get both BC and rejection results
    bc = st.session_state.get("bc_result", None)
    rejection_result = st.session_state.get("rejection_result", None)
    
    for time_str in key_times:
        slot_time = fmt_ct(datetime.combine(proj_day, datetime.strptime(time_str, "%H:%M").time()))
        top, bot = fan_levels_for_slot(anchor_close, anchor_time, slot_time)
        
        # Get BC projection if available
        spx_entry = ""
        contract_entry = ""
        spx_exit = ""
        contract_exit = ""
        entry_exit_spread = ""
        
        if bc and "table" in bc:
            try:
                bc_row = bc["table"][bc["table"]["Time"] == time_str]
                if not bc_row.empty:
                    spx_entry = f"{float(bc_row.iloc[0]['SPX Entry']):.2f}"
                    contract_entry = f"{float(bc_row.iloc[0]['Contract Entry']):.2f}"
                    
                    # Get exit data if available
                    exit_val = bc_row.iloc[0]['Contract Exit']
                    if exit_val != "—" and exit_val:
                        contract_exit = f"{float(exit_val):.2f}"
                    
                    spx_exit_val = bc_row.iloc[0]['SPX Exit']
                    if spx_exit_val != "—" and spx_exit_val:
                        spx_exit = f"{float(spx_exit_val):.2f}"
                    
                    # Get spread
                    spread_val = bc_row.iloc[0]['Entry/Exit Spread']
                    if spread_val != "—" and spread_val:
                        entry_exit_spread = spread_val
            except:
                pass
        
        # Market session context
        session_context = ""
        hour = int(time_str.split(":")[0])
        if hour == 8:
            session_context = "🚀 Open"
        elif 9 <= hour <= 10:
            session_context = "📈 Morning"
        elif 11 <= hour <= 12:
            session_context = "😴 Lunch"
        elif 13 <= hour <= 14:
            session_context = "🏁 Close"
        
        proj_rows.append({
            "Time": time_str,
            "Session": session_context,
            "Top": f"{top:.2f}",
            "Bottom": f"{bot:.2f}",
            "SPX Entry": spx_entry or "—",
            "Contract Entry": contract_entry or "—",
            "Contract Exit": contract_exit or "—",
            "Entry/Exit Spread": entry_exit_spread or "—"
        })
    
    df_plan = pd.DataFrame(proj_rows)
    st.dataframe(df_plan, use_container_width=True, hide_index=True)
    
    # Final trading reminders with exit system
    st.markdown("### 💡 Complete Trading System Guide")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **🎯 Entry Rules**
        - Wait for price to reach entry levels
        - Confirm with volume/momentum
        - Enter on pullbacks, not breakouts
        - Use limit orders near levels
        - Size based on stop distance
        """)
    
    with col2:
        exit_status = "Exit levels available" if st.session_state.get("rejection_result") else "Configure rejections for exits"
        st.markdown(f"""
        **🚪 Exit Strategy**
        - Monitor contract exit projections
        - Exit on rejection line touches
        - Scale out at resistance levels
        - **Status:** {exit_status}
        - Use trailing stops in trending moves
        """)
    
    with col3:
        st.markdown("""
        **⚡ Risk & Time Management**
        - Set stops immediately on entry
        - Maximum 3 trades per session
        - Best hours: 8:30-9:30, 13:00-14:30
        - Avoid: 11:30-12:30 lunch chop
        - Review performance after close
        """)

# ───────────────────────────────────────────────────────────────────────────────
# FOOTER
# ───────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: var(--text-muted); font-size: 0.875rem; padding: 1rem;'>"
    "🔮 SPX Prophet v2.1 - Complete Entry/Exit System | "
    f"Last Updated: {fmt_ct(datetime.now()).strftime('%H:%M CT')}"
    "</div>", 
    unsafe_allow_html=True
)