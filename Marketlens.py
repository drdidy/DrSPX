"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           SPX PROPHET v2.1                                    ║
║                    Where Structure Becomes Foresight                          ║
║                         LEGENDARY EDITION                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

THE SYSTEM:
-----------
VIX moves in 0.15 zones set overnight (5pm-2am). These zones map directly to 
SPX cone rails. When VIX touches a zone boundary, SPX touches a rail.

VIX Zone TOP (resistance) → SPX Descending Rail → CALLS entry, PUTS exit
VIX Zone BOTTOM (support) → SPX Ascending Rail → PUTS entry, CALLS exit

================================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta, time
import pytz
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict

# ============================================================================
# CONFIGURATION
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')
VIX_ZONE_SIZE = 0.15

SLOPE_ASCENDING = 0.45
SLOPE_DESCENDING = 0.45

MIN_CONE_WIDTH = 18.0
AT_RAIL_THRESHOLD = 8.0
STOP_LOSS_PTS = 3.0
STRIKE_OFFSET = 17.5
POWER_HOUR_START = time(14, 0)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_ct_now() -> datetime:
    return datetime.now(CT_TZ)

def get_time_block_index(dt: datetime, base_time: time = time(8, 30)) -> int:
    base = dt.replace(hour=base_time.hour, minute=base_time.minute, second=0, microsecond=0)
    if dt < base:
        return 0
    diff = (dt - base).total_seconds()
    return int(diff // 1800)

def get_delta_estimate(otm_distance: float) -> float:
    if otm_distance <= 5: return 0.48
    elif otm_distance <= 10: return 0.42
    elif otm_distance <= 15: return 0.35
    elif otm_distance <= 20: return 0.30
    elif otm_distance <= 25: return 0.25
    else: return 0.20

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Pivot:
    price: float
    time: datetime
    name: str

@dataclass
class Cone:
    pivot: Pivot
    name: str
    ascending_rail: float
    descending_rail: float
    
@dataclass 
class VIXZone:
    support: float
    resistance: float
    zone_size: float
    current: float
    position_pct: float
    trade_bias: str
    levels_above: List[float]
    levels_below: List[float]

@dataclass
class TradeSetup:
    direction: str
    entry_price: float
    target_price: float
    stop_price: float
    cone_name: str
    rail_type: str
    risk_pts: float
    reward_pts: float
    rr_ratio: float
    strike: float
    delta: float
    expected_profit: float
    max_loss: float

# ============================================================================
# VIX ZONE CALCULATIONS
# ============================================================================

def calculate_vix_zones(support: float, resistance: float, current: float) -> VIXZone:
    zone_size = resistance - support
    
    if zone_size > 0 and current > 0:
        position_pct = ((current - support) / zone_size) * 100
        position_pct = max(-50, min(150, position_pct))
    else:
        position_pct = 50
    
    if current <= 0:
        trade_bias = "ENTER VIX"
    elif position_pct >= 70:
        trade_bias = "CALLS"
    elif position_pct <= 30:
        trade_bias = "PUTS"
    else:
        trade_bias = "NEUTRAL"
    
    levels_above = [round(resistance + (VIX_ZONE_SIZE * i), 2) for i in range(1, 5)]
    levels_below = [round(support - (VIX_ZONE_SIZE * i), 2) for i in range(1, 5)]
    
    return VIXZone(support=support, resistance=resistance, zone_size=zone_size,
                   current=current, position_pct=position_pct, trade_bias=trade_bias,
                   levels_above=levels_above, levels_below=levels_below)

def get_vix_zone_status(vix_zone: VIXZone) -> Tuple[str, str, str]:
    if vix_zone.current <= 0:
        return "Enter VIX data", "N/A", "N/A"
    
    current = vix_zone.current
    
    if current > vix_zone.resistance + 0.01:
        zones_above = (current - vix_zone.resistance) / VIX_ZONE_SIZE
        target_zone = min(int(zones_above) + 1, 4)
        return f"⚠️ BREAKOUT UP → Target: {vix_zone.levels_above[target_zone-1]:.2f}", "PUTS extending", "Wait"
    
    if current < vix_zone.support - 0.01:
        zones_below = (vix_zone.support - current) / VIX_ZONE_SIZE
        target_zone = min(int(zones_below) + 1, 4)
        return f"⚠️ BREAKOUT DOWN → Target: {vix_zone.levels_below[target_zone-1]:.2f}", "CALLS extending", "Wait"
    
    if vix_zone.position_pct >= 70:
        return "🟢 At RESISTANCE → CALLS Entry", "Descending (▼)", "Ascending (▲)"
    elif vix_zone.position_pct <= 30:
        return "🔴 At SUPPORT → PUTS Entry", "Ascending (▲)", "Descending (▼)"
    else:
        return "🟡 MID-ZONE → Wait", "Wait", "Wait"

# ============================================================================
# CONE CALCULATIONS
# ============================================================================

def calculate_rail_price(pivot_price: float, pivot_time: datetime, 
                         target_time: datetime, is_ascending: bool) -> float:
    blocks = get_time_block_index(target_time) - get_time_block_index(pivot_time)
    slope = SLOPE_ASCENDING if is_ascending else -SLOPE_DESCENDING
    return pivot_price + (slope * blocks)

def create_cone(pivot: Pivot, target_time: datetime) -> Cone:
    ascending = calculate_rail_price(pivot.price, pivot.time, target_time, True)
    descending = calculate_rail_price(pivot.price, pivot.time, target_time, False)
    return Cone(pivot=pivot, name=pivot.name, ascending_rail=ascending, descending_rail=descending)

def find_nearest_rail(price: float, cones: List[Cone]) -> Tuple[Optional[Cone], str, float]:
    nearest_cone = None
    nearest_type = ''
    nearest_distance = float('inf')
    
    for cone in cones:
        dist_desc = abs(price - cone.descending_rail)
        if dist_desc < nearest_distance:
            nearest_distance = dist_desc
            nearest_cone = cone
            nearest_type = 'descending'
        
        dist_asc = abs(price - cone.ascending_rail)
        if dist_asc < nearest_distance:
            nearest_distance = dist_asc
            nearest_cone = cone
            nearest_type = 'ascending'
    
    return nearest_cone, nearest_type, nearest_distance

# ============================================================================
# DATA FETCHING
# ============================================================================

@st.cache_data(ttl=300)
def fetch_prior_session_data(session_date: datetime) -> Optional[Dict]:
    try:
        prior_date = session_date - timedelta(days=1)
        while prior_date.weekday() >= 5:
            prior_date = prior_date - timedelta(days=1)
        
        spx = yf.Ticker("^GSPC")
        start_date = prior_date.strftime('%Y-%m-%d')
        end_date = (prior_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        df = spx.history(start=start_date, end=end_date, interval='30m')
        
        if df.empty:
            df_daily = spx.history(start=start_date, end=end_date, interval='1d')
            if df_daily.empty:
                return None
            row = df_daily.iloc[0]
            close_time = CT_TZ.localize(datetime.combine(prior_date, time(15, 0)))
            return {'date': prior_date, 'high': row['High'], 'high_time': close_time,
                    'low': row['Low'], 'low_time': close_time, 'close': row['Close']}
        
        df.index = df.index.tz_convert(CT_TZ)
        
        df_before_power = df[df.index.time < POWER_HOUR_START]
        if not df_before_power.empty:
            high_idx = df_before_power['High'].idxmax()
        else:
            high_idx = df['High'].idxmax()
        
        low_close_idx = df['Close'].idxmin()
        
        return {'date': prior_date, 'high': df.loc[high_idx, 'High'], 'high_time': high_idx,
                'low': df.loc[low_close_idx, 'Close'], 'low_time': low_close_idx, 
                'close': df['Close'].iloc[-1]}
    except:
        return None

@st.cache_data(ttl=60)
def fetch_current_spx() -> Optional[float]:
    try:
        spx = yf.Ticker("^GSPC")
        data = spx.history(period='1d', interval='1m')
        if not data.empty:
            return data['Close'].iloc[-1]
        return None
    except:
        return None

# ============================================================================
# TRADE SETUP GENERATION
# ============================================================================

def generate_trade_setups(cones: List[Cone], current_price: float) -> List[TradeSetup]:
    setups = []
    
    for cone in cones:
        cone_width = cone.ascending_rail - cone.descending_rail
        if cone_width < MIN_CONE_WIDTH:
            continue
        
        # CALLS
        calls_entry = cone.descending_rail
        calls_target = cone.ascending_rail
        calls_stop = calls_entry - STOP_LOSS_PTS
        calls_reward = calls_target - calls_entry
        calls_strike = round(calls_entry - STRIKE_OFFSET, 0)
        calls_delta = get_delta_estimate(STRIKE_OFFSET)
        
        setups.append(TradeSetup(
            direction='CALLS', entry_price=calls_entry, target_price=calls_target,
            stop_price=calls_stop, cone_name=cone.name, rail_type='descending',
            risk_pts=STOP_LOSS_PTS, reward_pts=calls_reward,
            rr_ratio=calls_reward / STOP_LOSS_PTS, strike=calls_strike,
            delta=calls_delta, expected_profit=calls_reward * calls_delta * 100,
            max_loss=STOP_LOSS_PTS * calls_delta * 100
        ))
        
        # PUTS
        puts_entry = cone.ascending_rail
        puts_target = cone.descending_rail
        puts_stop = puts_entry + STOP_LOSS_PTS
        puts_reward = puts_entry - puts_target
        puts_strike = round(puts_entry + STRIKE_OFFSET, 0)
        puts_delta = get_delta_estimate(STRIKE_OFFSET)
        
        setups.append(TradeSetup(
            direction='PUTS', entry_price=puts_entry, target_price=puts_target,
            stop_price=puts_stop, cone_name=cone.name, rail_type='ascending',
            risk_pts=STOP_LOSS_PTS, reward_pts=puts_reward,
            rr_ratio=puts_reward / STOP_LOSS_PTS, strike=puts_strike,
            delta=puts_delta, expected_profit=puts_reward * puts_delta * 100,
            max_loss=STOP_LOSS_PTS * puts_delta * 100
        ))
    
    return setups

# ============================================================================
# PREMIUM CSS STYLES
# ============================================================================

def inject_premium_css():
    st.markdown("""
    <style>
    /* ========== GLOBAL STYLES ========== */
    .stApp {
        background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
    }
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%);
        border-right: 2px solid #e2e8f0;
    }
    
    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1rem;
    }
    
    /* ========== HEADER ========== */
    .prophet-header {
        background: linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #0ea5e9 100%);
        border-radius: 16px;
        padding: 32px;
        margin-bottom: 24px;
        text-align: center;
        box-shadow: 0 10px 40px rgba(59, 130, 246, 0.3);
    }
    
    .prophet-title {
        font-size: 2.8rem;
        font-weight: 800;
        color: white;
        margin: 0;
        letter-spacing: 6px;
        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    
    .prophet-subtitle {
        color: rgba(255,255,255,0.9);
        font-size: 0.9rem;
        letter-spacing: 4px;
        margin-top: 8px;
        font-weight: 500;
    }
    
    /* ========== METRICS ROW ========== */
    .metrics-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 24px;
    }
    
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
    }
    
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
        margin-bottom: 4px;
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }
    
    /* ========== VIX ZONE PANEL ========== */
    .vix-panel {
        background: white;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        border: 2px solid #e2e8f0;
    }
    
    .vix-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 2px solid #f1f5f9;
    }
    
    .vix-bias {
        font-size: 2rem;
        font-weight: 800;
    }
    
    .zone-ladder {
        background: #f8fafc;
        border-radius: 12px;
        padding: 16px;
        margin-top: 16px;
    }
    
    .zone-level {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 16px;
        margin: 4px 0;
        border-radius: 8px;
        font-family: 'SF Mono', monospace;
        font-size: 0.9rem;
    }
    
    .zone-extend-up {
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.12) 0%, rgba(239, 68, 68, 0.04) 100%);
        border-left: 4px solid #fca5a5;
    }
    
    .zone-extend-down {
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.12) 0%, rgba(16, 185, 129, 0.04) 100%);
        border-left: 4px solid #6ee7b7;
    }
    
    .zone-resistance {
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.25) 0%, rgba(239, 68, 68, 0.1) 100%);
        border: 2px solid #ef4444;
        font-weight: 700;
    }
    
    .zone-support {
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.25) 0%, rgba(16, 185, 129, 0.1) 100%);
        border: 2px solid #10b981;
        font-weight: 700;
    }
    
    .zone-current {
        background: linear-gradient(90deg, rgba(59, 130, 246, 0.25) 0%, rgba(59, 130, 246, 0.1) 100%);
        border: 2px solid #3b82f6;
        font-weight: 700;
    }
    
    /* ========== TRADE CARDS ========== */
    .trade-card {
        background: white;
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        border-left: 5px solid;
    }
    
    .trade-card-calls {
        border-left-color: #10b981;
    }
    
    .trade-card-puts {
        border-left-color: #ef4444;
    }
    
    .trade-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
    }
    
    .trade-badge {
        display: inline-block;
        padding: 8px 20px;
        border-radius: 25px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 1px;
        color: white;
    }
    
    .badge-calls {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
    }
    
    .badge-puts {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
    }
    
    .trade-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 12px;
        margin-bottom: 16px;
    }
    
    .trade-stat {
        background: #f8fafc;
        border-radius: 10px;
        padding: 14px;
        text-align: center;
    }
    
    .trade-stat-value {
        font-size: 1.15rem;
        font-weight: 700;
        font-family: 'SF Mono', monospace;
    }
    
    .trade-stat-label {
        font-size: 0.7rem;
        color: #64748b;
        text-transform: uppercase;
        margin-top: 4px;
        font-weight: 600;
    }
    
    .profit-row {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
        padding-top: 16px;
        border-top: 2px solid #f1f5f9;
    }
    
    .profit-box {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        border-radius: 10px;
        padding: 14px;
        text-align: center;
    }
    
    .loss-box {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        border-radius: 10px;
        padding: 14px;
        text-align: center;
    }
    
    .rr-box {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
        border-radius: 10px;
        padding: 14px;
        text-align: center;
    }
    
    /* ========== CHECKLIST ========== */
    .checklist-panel {
        background: white;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        margin-bottom: 20px;
    }
    
    .checklist-header {
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 16px;
        text-align: center;
    }
    
    .checklist-go {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        border: 2px solid #10b981;
    }
    
    .checklist-wait {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border: 2px solid #f59e0b;
    }
    
    .checklist-skip {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        border: 2px solid #ef4444;
    }
    
    .checklist-item {
        display: flex;
        align-items: center;
        padding: 14px 16px;
        margin: 8px 0;
        border-radius: 10px;
        background: #f8fafc;
    }
    
    .checklist-pass {
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.15) 0%, #f8fafc 100%);
        border-left: 4px solid #10b981;
    }
    
    .checklist-fail {
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.15) 0%, #f8fafc 100%);
        border-left: 4px solid #ef4444;
    }
    
    .check-icon {
        font-size: 1.3rem;
        font-weight: bold;
        width: 28px;
    }
    
    .check-label {
        flex: 1;
        font-weight: 600;
        color: #1e293b;
        margin-left: 12px;
    }
    
    .check-detail {
        color: #64748b;
        font-size: 0.85rem;
    }
    
    /* ========== SECTION HEADERS ========== */
    .section-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 28px 0 20px 0;
        padding-bottom: 12px;
        border-bottom: 3px solid #3b82f6;
    }
    
    .section-icon {
        font-size: 1.5rem;
    }
    
    .section-title {
        font-size: 1.2rem;
        font-weight: 700;
        color: #1e293b;
        letter-spacing: 0.5px;
    }
    
    /* ========== INFO PANELS ========== */
    .info-panel {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        margin-bottom: 16px;
    }
    
    .info-row {
        display: flex;
        justify-content: space-between;
        padding: 12px 0;
        border-bottom: 1px solid #f1f5f9;
    }
    
    .info-row:last-child {
        border-bottom: none;
    }
    
    .info-label {
        color: #64748b;
        font-weight: 500;
    }
    
    .info-value {
        font-weight: 700;
        font-family: 'SF Mono', monospace;
    }
    
    /* ========== DIRECTION BADGE ========== */
    .direction-box {
        text-align: center;
        padding: 20px;
        border-radius: 12px;
        margin-top: 16px;
    }
    
    .direction-calls {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        border: 2px solid #10b981;
    }
    
    .direction-puts {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        border: 2px solid #ef4444;
    }
    
    /* ========== TABS ========== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: white;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_header():
    st.markdown("""
    <div class="prophet-header">
        <h1 class="prophet-title">SPX PROPHET</h1>
        <p class="prophet-subtitle">WHERE STRUCTURE BECOMES FORESIGHT</p>
    </div>
    """, unsafe_allow_html=True)

def render_metrics_row(current_price: float, vix_zone: Optional[VIXZone], 
                       nearest_distance: float, cone_width: float):
    vix_display = "—"
    vix_color = "#64748b"
    vix_pct = ""
    
    if vix_zone and vix_zone.current > 0:
        vix_display = f"{vix_zone.current:.2f}"
        vix_pct = f" ({vix_zone.position_pct:.0f}%)"
        if vix_zone.trade_bias == "CALLS":
            vix_color = "#10b981"
        elif vix_zone.trade_bias == "PUTS":
            vix_color = "#ef4444"
        else:
            vix_color = "#f59e0b"
    
    dist_color = "#10b981" if nearest_distance <= 5 else "#f59e0b" if nearest_distance <= 10 else "#64748b"
    width_color = "#10b981" if cone_width >= 25 else "#f59e0b" if cone_width >= 18 else "#ef4444"
    
    st.markdown(f"""
    <div class="metrics-row">
        <div class="metric-card">
            <div class="metric-value" style="color: #3b82f6;">{current_price:,.2f}</div>
            <div class="metric-label">SPX Price</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" style="color: {vix_color};">{vix_display}{vix_pct}</div>
            <div class="metric-label">VIX Level</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" style="color: {dist_color};">{nearest_distance:.1f}</div>
            <div class="metric-label">Pts to Rail</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" style="color: {width_color};">{cone_width:.0f}</div>
            <div class="metric-label">Cone Width</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_vix_zone_panel(vix_zone: VIXZone):
    status, entry_rail, exit_rail = get_vix_zone_status(vix_zone)
    
    if vix_zone.trade_bias == "CALLS":
        bias_color = "#10b981"
    elif vix_zone.trade_bias == "PUTS":
        bias_color = "#ef4444"
    else:
        bias_color = "#f59e0b"
    
    # Build zone ladder
    ladder_html = '<div class="zone-ladder">'
    
    # Levels above (PUTS extend targets)
    for i in range(3, -1, -1):
        level = vix_zone.levels_above[i]
        ladder_html += f'''
        <div class="zone-level zone-extend-up">
            <span style="color: #ef4444; font-weight: 600;">+{i+1}</span>
            <span style="color: #1e293b; font-weight: 600;">{level:.2f}</span>
            <span style="color: #64748b; font-size: 0.8rem;">PUTS extend</span>
        </div>'''
    
    # Resistance (CALLS Entry)
    ladder_html += f'''
    <div class="zone-level zone-resistance">
        <span style="color: #ef4444;">RES</span>
        <span style="color: #1e293b;">{vix_zone.resistance:.2f}</span>
        <span style="color: #10b981; font-weight: 600;">CALLS Entry</span>
    </div>'''
    
    # Current VIX (if within zone)
    if vix_zone.support - 0.02 <= vix_zone.current <= vix_zone.resistance + 0.02:
        ladder_html += f'''
        <div class="zone-level zone-current">
            <span style="color: #3b82f6;">NOW</span>
            <span style="color: #1e293b;">{vix_zone.current:.2f}</span>
            <span style="color: #3b82f6; font-weight: 600;">{vix_zone.position_pct:.0f}%</span>
        </div>'''
    
    # Support (PUTS Entry)
    ladder_html += f'''
    <div class="zone-level zone-support">
        <span style="color: #10b981;">SUP</span>
        <span style="color: #1e293b;">{vix_zone.support:.2f}</span>
        <span style="color: #ef4444; font-weight: 600;">PUTS Entry</span>
    </div>'''
    
    # Levels below (CALLS extend targets)
    for i in range(4):
        level = vix_zone.levels_below[i]
        ladder_html += f'''
        <div class="zone-level zone-extend-down">
            <span style="color: #10b981; font-weight: 600;">-{i+1}</span>
            <span style="color: #1e293b; font-weight: 600;">{level:.2f}</span>
            <span style="color: #64748b; font-size: 0.8rem;">CALLS extend</span>
        </div>'''
    
    ladder_html += '</div>'
    
    st.markdown(f"""
    <div class="vix-panel">
        <div class="vix-header">
            <div>
                <div style="font-size: 0.8rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">VIX Trade Compass</div>
                <div class="vix-bias" style="color: {bias_color};">{vix_zone.trade_bias}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.75rem; color: #64748b;">Zone Size</div>
                <div style="font-size: 1.5rem; font-weight: 700; color: #1e293b;">{vix_zone.zone_size:.2f}</div>
            </div>
        </div>
        
        <div style="background: #f1f5f9; border-radius: 10px; padding: 14px; border-left: 4px solid {bias_color}; margin-bottom: 16px;">
            <div style="color: #1e293b; font-weight: 600; font-size: 1rem;">{status}</div>
            <div style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">
                Entry: SPX {entry_rail} → Exit: SPX {exit_rail}
            </div>
        </div>
        
        {ladder_html}
    </div>
    """, unsafe_allow_html=True)

def render_trade_card(setup: TradeSetup, current_price: float, vix_zone: Optional[VIXZone]):
    distance = abs(current_price - setup.entry_price)
    is_near = distance <= AT_RAIL_THRESHOLD
    
    card_class = "trade-card-calls" if setup.direction == "CALLS" else "trade-card-puts"
    badge_class = "badge-calls" if setup.direction == "CALLS" else "badge-puts"
    
    # VIX alignment
    vix_aligned = False
    vix_status = "Enter VIX"
    if vix_zone and vix_zone.current > 0:
        if setup.direction == "CALLS" and vix_zone.trade_bias == "CALLS":
            vix_aligned = True
            vix_status = f"✓ Aligned ({vix_zone.position_pct:.0f}%)"
        elif setup.direction == "PUTS" and vix_zone.trade_bias == "PUTS":
            vix_aligned = True
            vix_status = f"✓ Aligned ({vix_zone.position_pct:.0f}%)"
        elif vix_zone.trade_bias == "NEUTRAL":
            vix_status = f"⚠ Neutral ({vix_zone.position_pct:.0f}%)"
        else:
            vix_status = f"✗ VIX says {vix_zone.trade_bias}"
    
    distance_text = "🎯 AT RAIL" if is_near else f"{distance:.1f} pts away"
    distance_color = "#10b981" if is_near else "#64748b"
    
    entry_color = "#10b981" if setup.direction == "CALLS" else "#ef4444"
    
    st.markdown(f"""
    <div class="trade-card {card_class}">
        <div class="trade-header">
            <div>
                <span class="trade-badge {badge_class}">{setup.direction}</span>
                <span style="color: #64748b; font-size: 0.9rem; margin-left: 12px; font-weight: 500;">{setup.cone_name} Cone</span>
            </div>
            <div style="color: {distance_color}; font-weight: 600;">{distance_text}</div>
        </div>
        
        <div class="trade-grid">
            <div class="trade-stat">
                <div class="trade-stat-value" style="color: {entry_color};">{setup.entry_price:.2f}</div>
                <div class="trade-stat-label">Entry</div>
            </div>
            <div class="trade-stat">
                <div class="trade-stat-value" style="color: #f59e0b;">{setup.target_price:.2f}</div>
                <div class="trade-stat-label">Target</div>
            </div>
            <div class="trade-stat">
                <div class="trade-stat-value" style="color: #ef4444;">{setup.stop_price:.2f}</div>
                <div class="trade-stat-label">Stop</div>
            </div>
            <div class="trade-stat">
                <div class="trade-stat-value" style="color: #3b82f6;">{setup.strike:.0f}</div>
                <div class="trade-stat-label">Strike</div>
            </div>
        </div>
        
        <div class="profit-row">
            <div class="profit-box">
                <div style="font-size: 1.2rem; font-weight: 700; color: #059669;">+${setup.expected_profit:.0f}</div>
                <div style="font-size: 0.7rem; color: #065f46; font-weight: 600;">PROFIT TARGET</div>
            </div>
            <div class="loss-box">
                <div style="font-size: 1.2rem; font-weight: 700; color: #dc2626;">-${setup.max_loss:.0f}</div>
                <div style="font-size: 0.7rem; color: #991b1b; font-weight: 600;">MAX LOSS</div>
            </div>
            <div class="rr-box">
                <div style="font-size: 1.2rem; font-weight: 700; color: #1d4ed8;">{setup.rr_ratio:.1f}:1</div>
                <div style="font-size: 0.7rem; color: #1e40af; font-weight: 600;">RISK:REWARD</div>
            </div>
        </div>
        
        <div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="color: #64748b; font-size: 0.8rem;">Delta: </span>
                <span style="color: #1e293b; font-weight: 600;">{setup.delta:.2f}</span>
                <span style="color: #64748b; font-size: 0.8rem; margin-left: 12px;">Risk: </span>
                <span style="color: #1e293b; font-weight: 600;">{setup.risk_pts:.0f} pts</span>
            </div>
            <div>
                <span style="color: #64748b; font-size: 0.8rem;">VIX: </span>
                <span style="color: {'#10b981' if vix_aligned else '#64748b'}; font-weight: 600;">{vix_status}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_checklist(cones: List[Cone], current_price: float, vix_zone: Optional[VIXZone]):
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    
    cone_width = nearest_cone.ascending_rail - nearest_cone.descending_rail if nearest_cone else 0
    
    checks = []
    
    # 1. At Rail
    at_rail_ok = nearest_distance <= AT_RAIL_THRESHOLD
    at_rail_detail = f"{nearest_distance:.1f} pts" if not at_rail_ok else "✓ In zone"
    checks.append(("At Rail", at_rail_ok, at_rail_detail))
    
    # 2. Structure
    structure_ok = cone_width >= MIN_CONE_WIDTH
    structure_detail = f"{cone_width:.0f} pts" if structure_ok else f"Only {cone_width:.0f} pts"
    checks.append(("Structure", structure_ok, structure_detail))
    
    # 3. Active Cone
    active_ok = nearest_cone is not None
    active_detail = f"{nearest_cone.name}" if nearest_cone else "None"
    checks.append(("Active Cone", active_ok, active_detail))
    
    # 4. VIX Aligned
    if vix_zone and vix_zone.current > 0:
        expected_bias = "CALLS" if nearest_rail_type == 'descending' else "PUTS"
        vix_ok = vix_zone.trade_bias == expected_bias
        vix_detail = vix_zone.trade_bias
    else:
        vix_ok = True
        vix_detail = "Enter data"
    checks.append(("VIX Aligned", vix_ok, vix_detail))
    
    passed = sum(1 for _, ok, _ in checks if ok)
    
    if passed == 4:
        overall = "🟢 GO - Perfect Setup"
        header_class = "checklist-go"
    elif passed >= 3:
        overall = "🟢 GO - Strong Setup"
        header_class = "checklist-go"
    elif not at_rail_ok:
        overall = "🟡 WAIT - Not at Rail"
        header_class = "checklist-wait"
    elif not structure_ok:
        overall = "🔴 SKIP - Bad Structure"
        header_class = "checklist-skip"
    else:
        overall = "🟡 CAUTION"
        header_class = "checklist-wait"
    
    direction = "CALLS" if nearest_rail_type == 'descending' else "PUTS"
    dir_class = "direction-calls" if direction == "CALLS" else "direction-puts"
    dir_color = "#10b981" if direction == "CALLS" else "#ef4444"
    
    st.markdown(f"""
    <div class="checklist-panel">
        <div class="checklist-header {header_class}">
            <div style="font-size: 1.3rem; font-weight: 700; color: #1e293b;">{overall}</div>
            <div style="font-size: 0.85rem; color: #475569; margin-top: 4px;">{passed}/4 checks passed</div>
        </div>
    """, unsafe_allow_html=True)
    
    for label, ok, detail in checks:
        icon = "✓" if ok else "✗"
        icon_color = "#10b981" if ok else "#ef4444"
        item_class = "checklist-pass" if ok else "checklist-fail"
        st.markdown(f"""
        <div class="checklist-item {item_class}">
            <span class="check-icon" style="color: {icon_color};">{icon}</span>
            <span class="check-label">{label}</span>
            <span class="check-detail">{detail}</span>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown(f"""
        <div class="direction-box {dir_class}">
            <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 4px;">TRADE DIRECTION</div>
            <div style="font-size: 1.8rem; font-weight: 800; color: {dir_color};">{direction}</div>
            <div style="font-size: 0.85rem; color: #64748b; margin-top: 4px;">{nearest_cone.name if nearest_cone else 'N/A'} {nearest_rail_type} rail</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_pivots_panel(high_price: float, low_price: float, close_price: float, prior_date):
    date_str = prior_date.strftime('%b %d, %Y') if prior_date else 'N/A'
    st.markdown(f"""
    <div class="info-panel">
        <div style="font-size: 0.8rem; color: #64748b; margin-bottom: 12px; font-weight: 500;">Prior Session: {date_str}</div>
        <div class="info-row">
            <span class="info-label">High (Wick)</span>
            <span class="info-value" style="color: #ef4444;">{high_price:.2f}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Low (Close)</span>
            <span class="info-value" style="color: #10b981;">{low_price:.2f}</span>
        </div>
        <div class="info-row">
            <span class="info-label">Close</span>
            <span class="info-value" style="color: #f59e0b;">{close_price:.2f}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_rails_panel(cones: List[Cone]):
    rails_html = '<div class="info-panel">'
    
    for i, cone in enumerate(cones):
        border = 'border-bottom: 1px solid #f1f5f9; margin-bottom: 12px; padding-bottom: 12px;' if i < len(cones) - 1 else ''
        rails_html += f'''
        <div style="{border}">
            <div style="font-size: 0.8rem; color: #64748b; font-weight: 600; margin-bottom: 8px;">{cone.name} Cone</div>
            <div style="display: flex; justify-content: space-between;">
                <span style="color: #ef4444; font-weight: 600; font-family: monospace;">▲ {cone.ascending_rail:.2f}</span>
                <span style="color: #10b981; font-weight: 600; font-family: monospace;">▼ {cone.descending_rail:.2f}</span>
            </div>
        </div>
        '''
    
    rails_html += '</div>'
    st.markdown(rails_html, unsafe_allow_html=True)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet v2.1",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    inject_premium_css()
    render_header()
    
    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        st.markdown("## 📅 Session Date")
        session_date = st.date_input(
            "Trading Date",
            value=get_ct_now().date(),
            help="Select the trading session date"
        )
        session_date = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        
        ct_now = get_ct_now()
        st.caption(f"🕐 {ct_now.strftime('%I:%M %p CT')} | {ct_now.strftime('%A, %b %d')}")
        
        st.markdown("---")
        
        # VIX ZONE INPUT
        st.markdown("## 🧭 VIX Zone Setup")
        st.caption("From overnight session (5pm-2am)")
        
        if 'vix_support' not in st.session_state:
            st.session_state.vix_support = 0.0
        if 'vix_resistance' not in st.session_state:
            st.session_state.vix_resistance = 0.0
        if 'vix_current' not in st.session_state:
            st.session_state.vix_current = 0.0
        
        vix_support = st.number_input(
            "VIX Support (Zone Bottom)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_support,
            step=0.01,
            format="%.2f",
            help="Overnight low - PUTS entry when VIX here"
        )
        st.session_state.vix_support = vix_support
        
        vix_resistance = st.number_input(
            "VIX Resistance (Zone Top)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_resistance,
            step=0.01,
            format="%.2f",
            help="Overnight high - CALLS entry when VIX here"
        )
        st.session_state.vix_resistance = vix_resistance
        
        vix_current = st.number_input(
            "Current VIX",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_current,
            step=0.01,
            format="%.2f",
            help="Live VIX from TradingView (VX1!)"
        )
        st.session_state.vix_current = vix_current
        
        # Calculate VIX zone
        vix_zone = None
        if vix_support > 0 and vix_resistance > 0:
            vix_zone = calculate_vix_zones(vix_support, vix_resistance, vix_current)
            
            zone_size = vix_resistance - vix_support
            if 0.13 <= zone_size <= 0.17:
                st.success(f"✓ Valid 1-zone: {zone_size:.2f}")
            elif zone_size > 0:
                num_zones = round(zone_size / 0.15)
                st.info(f"~{num_zones} zones ({zone_size:.2f})")
            
            # Show trade bias
            if vix_zone.trade_bias == "CALLS":
                st.markdown("### 🟢 CALLS")
                st.caption("VIX at resistance → SPX descending rail")
            elif vix_zone.trade_bias == "PUTS":
                st.markdown("### 🔴 PUTS")
                st.caption("VIX at support → SPX ascending rail")
            else:
                st.markdown("### 🟡 NEUTRAL")
                st.caption("VIX mid-range → Wait for extremes")
        
        st.markdown("---")
        
        # ES-SPX OFFSET
        st.markdown("## 📊 ES-SPX Offset")
        
        if 'es_offset' not in st.session_state:
            st.session_state.es_offset = 0.0
        
        es_offset = st.number_input(
            "ES minus SPX",
            min_value=-100.0,
            max_value=100.0,
            value=st.session_state.es_offset,
            step=0.25,
            format="%.2f",
            help="Positive if ES > SPX, Negative if ES < SPX"
        )
        st.session_state.es_offset = es_offset
        
        if es_offset >= 0:
            st.caption(f"ES is {es_offset:.2f} pts ABOVE SPX")
        else:
            st.caption(f"ES is {abs(es_offset):.2f} pts BELOW SPX")
        
        st.markdown("---")
        
        # MANUAL PIVOTS
        st.markdown("## 📍 Manual Pivots")
        use_manual = st.checkbox("Override Auto-Pivots", value=False)
        
        if 'manual_high' not in st.session_state:
            st.session_state.manual_high = 0.0
        if 'manual_low' not in st.session_state:
            st.session_state.manual_low = 0.0
        if 'manual_close' not in st.session_state:
            st.session_state.manual_close = 0.0
        
        if use_manual:
            st.session_state.manual_high = st.number_input(
                "High (Wick)",
                value=st.session_state.manual_high,
                format="%.2f"
            )
            st.session_state.manual_low = st.number_input(
                "Low (Close)",
                value=st.session_state.manual_low,
                format="%.2f"
            )
            st.session_state.manual_close = st.number_input(
                "Close",
                value=st.session_state.manual_close,
                format="%.2f"
            )
        
        st.markdown("---")
        
        # QUICK REFERENCE
        st.markdown("## 📖 Quick Reference")
        st.markdown("""
        **VIX → SPX Mapping:**
        - VIX at Resistance → CALLS
        - VIX at Support → PUTS
        - VIX breaks up → PUTS extend
        - VIX breaks down → CALLS extend
        
        **Zone Size:** 0.15 per level
        """)
    
    # ========================================================================
    # MAIN CONTENT
    # ========================================================================
    
    # Fetch data
    prior_session = fetch_prior_session_data(session_date)
    current_price = fetch_current_spx()
    
    if current_price is None:
        current_price = 6000.0
        st.warning("⚠️ Could not fetch live SPX price. Using placeholder.")
    
    # Use manual pivots if enabled
    if use_manual and st.session_state.manual_high > 0:
        high_price = st.session_state.manual_high
        low_price = st.session_state.manual_low
        close_price = st.session_state.manual_close
        high_time = CT_TZ.localize(datetime.combine(session_date.date() - timedelta(days=1), time(12, 0)))
        low_time = high_time
        prior_date = session_date.date() - timedelta(days=1)
    elif prior_session:
        high_price = prior_session['high']
        low_price = prior_session['low']
        close_price = prior_session['close']
        high_time = prior_session['high_time']
        low_time = prior_session['low_time']
        prior_date = prior_session['date']
    else:
        st.error("⚠️ Could not fetch prior session data. Please enable Manual Pivots in the sidebar.")
        return
    
    # Create pivots and cones
    target_time = session_date.replace(hour=10, minute=0)
    
    pivots = [
        Pivot(price=high_price, time=high_time, name='High'),
        Pivot(price=low_price, time=low_time, name='Low'),
        Pivot(price=close_price, 
              time=CT_TZ.localize(datetime.combine(session_date.date() - timedelta(days=1), time(15, 0))), 
              name='Close'),
    ]
    
    cones = [create_cone(p, target_time) for p in pivots]
    
    # Find nearest rail
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    cone_width = nearest_cone.ascending_rail - nearest_cone.descending_rail if nearest_cone else 0
    
    # Generate trade setups
    trade_setups = generate_trade_setups(cones, current_price)
    
    # ========================================================================
    # RENDER MAIN CONTENT
    # ========================================================================
    
    # Metrics Row
    render_metrics_row(current_price, vix_zone, nearest_distance, cone_width)
    
    # Main Layout
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        # VIX Zone Panel
        if vix_zone and vix_zone.support > 0:
            st.markdown("""
            <div class="section-header">
                <div class="section-icon">🧭</div>
                <div class="section-title">VIX Zone Analysis</div>
            </div>
            """, unsafe_allow_html=True)
            render_vix_zone_panel(vix_zone)
        
        # Trade Setups
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">🎯</div>
            <div class="section-title">Trade Setups @ 10:00 AM</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Sort setups by distance
        calls_setups = sorted(
            [s for s in trade_setups if s.direction == 'CALLS'],
            key=lambda x: abs(current_price - x.entry_price)
        )
        puts_setups = sorted(
            [s for s in trade_setups if s.direction == 'PUTS'],
            key=lambda x: abs(current_price - x.entry_price)
        )
        
        tab1, tab2 = st.tabs(["📈 CALLS (Buy Points)", "📉 PUTS (Sell Points)"])
        
        with tab1:
            if calls_setups:
                for setup in calls_setups[:3]:
                    render_trade_card(setup, current_price, vix_zone)
            else:
                st.info("No CALLS setups available (cones may be too narrow)")
        
        with tab2:
            if puts_setups:
                for setup in puts_setups[:3]:
                    render_trade_card(setup, current_price, vix_zone)
            else:
                st.info("No PUTS setups available (cones may be too narrow)")
    
    with right_col:
        # Checklist
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">📋</div>
            <div class="section-title">Trade Checklist</div>
        </div>
        """, unsafe_allow_html=True)
        render_checklist(cones, current_price, vix_zone)
        
        # Prior Session Pivots
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">📍</div>
            <div class="section-title">Prior Session Pivots</div>
        </div>
        """, unsafe_allow_html=True)
        render_pivots_panel(high_price, low_price, close_price, prior_date)
        
        # 10am Rails
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">📐</div>
            <div class="section-title">10:00 AM Rail Prices</div>
        </div>
        """, unsafe_allow_html=True)
        render_rails_panel(cones)
        
        # VIX-SPX Legend
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">📚</div>
            <div class="section-title">VIX-SPX Legend</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="info-panel">
            <div style="margin-bottom: 12px;">
                <div style="font-weight: 700; color: #10b981; margin-bottom: 4px;">🟢 CALLS Entry</div>
                <div style="font-size: 0.85rem; color: #64748b;">VIX at Resistance → SPX at Descending Rail (▼)</div>
            </div>
            <div style="margin-bottom: 12px;">
                <div style="font-weight: 700; color: #ef4444; margin-bottom: 4px;">🔴 PUTS Entry</div>
                <div style="font-size: 0.85rem; color: #64748b;">VIX at Support → SPX at Ascending Rail (▲)</div>
            </div>
            <div style="margin-bottom: 12px;">
                <div style="font-weight: 700; color: #f59e0b; margin-bottom: 4px;">⚠️ Breakout Up</div>
                <div style="font-size: 0.85rem; color: #64748b;">VIX breaks Resistance → PUTS target extends (+0.15 per zone)</div>
            </div>
            <div>
                <div style="font-weight: 700; color: #3b82f6; margin-bottom: 4px;">⚠️ Breakout Down</div>
                <div style="font-size: 0.85rem; color: #64748b;">VIX breaks Support → CALLS target extends (-0.15 per zone)</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    main()