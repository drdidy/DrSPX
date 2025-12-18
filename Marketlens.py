"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           SPX PROPHET v2.1                                    ║
║                    Where Structure Becomes Foresight                          ║
║                         MOBILE-FRIENDLY EDITION                               ║
╚══════════════════════════════════════════════════════════════════════════════╝

VIX-SPX CONFLUENCE SYSTEM:
==========================
- VIX at RESISTANCE (80%+) + SPX at DESCENDING rail = CALLS
- VIX at SUPPORT (20%-) + SPX at ASCENDING rail = PUTS
- It's the 30-minute CLOSE that matters, not the wick!

RAIL LOGIC:
===========
- Descending rail = SUPPORT → CALLS entry
- Ascending rail = RESISTANCE → PUTS entry

GAP DAYS:
=========
- Gap UP: Ascending from overnight low = Support → CALLS
- Gap DOWN: Descending from overnight high = Resistance → PUTS
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
STOP_LOSS_PTS = 6.0
STRIKE_OFFSET = 17.5
POWER_HOUR_START = time(14, 0)

RTH_TIME_BLOCKS = [
    ("8:30", time(8, 30), True, False),
    ("9:00", time(9, 0), False, False),
    ("9:30", time(9, 30), False, False),
    ("10:00", time(10, 0), False, True),
    ("10:30", time(10, 30), False, False),
    ("11:00", time(11, 0), False, False),
    ("11:30", time(11, 30), False, False),
    ("12:00", time(12, 0), False, False),
    ("12:30", time(12, 30), False, False),
    ("1:00", time(13, 0), False, False),
    ("1:30", time(13, 30), False, False),
    ("2:00", time(14, 0), False, False),
    ("2:30", time(14, 30), False, False),
    ("3:00", time(15, 0), False, False),
]

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
    if otm_distance <= 5:
        return 0.48
    elif otm_distance <= 10:
        return 0.42
    elif otm_distance <= 15:
        return 0.35
    elif otm_distance <= 20:
        return 0.30
    elif otm_distance <= 25:
        return 0.25
    else:
        return 0.20

def convert_es_to_spx(es_price: float, es_offset: float) -> float:
    return es_price - es_offset

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
    vix_condition: str

@dataclass
class GapAnalysis:
    is_gap_up: bool
    is_gap_down: bool
    gap_type: str
    overnight_pivot: Optional[float]
    overnight_pivot_name: str

# ============================================================================
# VIX ZONE CALCULATIONS
# ============================================================================

def calculate_vix_zones(support: float, resistance: float, current: float) -> VIXZone:
    zone_size = resistance - support
    
    if zone_size > 0 and current > 0:
        position_pct = ((current - support) / zone_size) * 100
        position_pct = max(-100, min(200, position_pct))
    else:
        position_pct = 50
    
    if current <= 0:
        trade_bias = "ENTER VIX"
    elif position_pct >= 80:
        trade_bias = "CALLS"
    elif position_pct <= 20:
        trade_bias = "PUTS"
    else:
        trade_bias = "NEUTRAL"
    
    levels_above = [round(resistance + (VIX_ZONE_SIZE * i), 2) for i in range(1, 5)]
    levels_below = [round(support - (VIX_ZONE_SIZE * i), 2) for i in range(1, 5)]
    
    return VIXZone(
        support=support,
        resistance=resistance,
        zone_size=zone_size,
        current=current,
        position_pct=position_pct,
        trade_bias=trade_bias,
        levels_above=levels_above,
        levels_below=levels_below
    )

def get_vix_zone_status(vix_zone: VIXZone) -> Tuple[str, str]:
    if vix_zone.current <= 0:
        return "Enter VIX data", ""
    
    current = vix_zone.current
    
    if current > vix_zone.resistance + 0.02:
        return "⚠️ BREAKOUT UP", "PUTS targets extend"
    
    if current < vix_zone.support - 0.02:
        return "⚠️ BREAKDOWN", "CALLS targets extend"
    
    if vix_zone.position_pct >= 80:
        return "🟢 VIX at RESISTANCE", "CALLS entry"
    elif vix_zone.position_pct <= 20:
        return "🔴 VIX at SUPPORT", "PUTS entry"
    else:
        return "🟡 VIX MID-ZONE", "Wait for extremes"

# ============================================================================
# GAP ANALYSIS
# ============================================================================

def analyze_gap(open_price: float, high_cone: Cone, low_cone: Cone,
                overnight_high_spx: float, overnight_low_spx: float) -> GapAnalysis:
    
    if open_price > high_cone.ascending_rail:
        return GapAnalysis(
            is_gap_up=True,
            is_gap_down=False,
            gap_type='GAP_UP',
            overnight_pivot=overnight_low_spx,
            overnight_pivot_name='Gap Low'
        )
    
    if open_price < low_cone.descending_rail:
        return GapAnalysis(
            is_gap_up=False,
            is_gap_down=True,
            gap_type='GAP_DOWN',
            overnight_pivot=overnight_high_spx,
            overnight_pivot_name='Gap High'
        )
    
    return GapAnalysis(
        is_gap_up=False,
        is_gap_down=False,
        gap_type='NORMAL',
        overnight_pivot=None,
        overnight_pivot_name=''
    )

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
    return Cone(
        pivot=pivot,
        name=pivot.name,
        ascending_rail=ascending,
        descending_rail=descending
    )

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
            return {
                'date': prior_date,
                'high': row['High'],
                'high_time': close_time,
                'low': row['Low'],
                'low_time': close_time,
                'close': row['Close']
            }
        
        df.index = df.index.tz_convert(CT_TZ)
        
        df_before_power = df[df.index.time < POWER_HOUR_START]
        if not df_before_power.empty:
            high_idx = df_before_power['High'].idxmax()
        else:
            high_idx = df['High'].idxmax()
        
        low_close_idx = df['Close'].idxmin()
        
        return {
            'date': prior_date,
            'high': df.loc[high_idx, 'High'],
            'high_time': high_idx,
            'low': df.loc[low_close_idx, 'Close'],
            'low_time': low_close_idx,
            'close': df['Close'].iloc[-1]
        }
    except Exception as e:
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

def generate_trade_setups(cones: List[Cone], current_price: float,
                          gap_analysis: Optional[GapAnalysis] = None) -> List[TradeSetup]:
    setups = []
    
    for cone in cones:
        cone_width = abs(cone.ascending_rail - cone.descending_rail)
        
        if cone_width < MIN_CONE_WIDTH:
            continue
        
        is_gap_cone = cone.name in ['Gap Low', 'Gap High']
        
        # CALLS SETUP
        if is_gap_cone and cone.name == 'Gap Low':
            calls_entry = cone.ascending_rail
            calls_target = cone.ascending_rail + cone_width
            calls_rail_type = 'ascending'
        else:
            calls_entry = cone.descending_rail
            calls_target = cone.ascending_rail
            calls_rail_type = 'descending'
        
        calls_stop = calls_entry - STOP_LOSS_PTS
        calls_reward = abs(calls_target - calls_entry)
        calls_strike = round(calls_entry - STRIKE_OFFSET, 0)
        calls_delta = get_delta_estimate(STRIKE_OFFSET)
        
        setups.append(TradeSetup(
            direction='CALLS',
            entry_price=calls_entry,
            target_price=calls_target,
            stop_price=calls_stop,
            cone_name=cone.name,
            rail_type=calls_rail_type,
            risk_pts=STOP_LOSS_PTS,
            reward_pts=calls_reward,
            rr_ratio=calls_reward / STOP_LOSS_PTS,
            strike=calls_strike,
            delta=calls_delta,
            expected_profit=calls_reward * calls_delta * 100,
            max_loss=STOP_LOSS_PTS * calls_delta * 100,
            vix_condition="VIX at RESISTANCE"
        ))
        
        # PUTS SETUP
        if is_gap_cone and cone.name == 'Gap High':
            puts_entry = cone.descending_rail
            puts_target = cone.descending_rail - cone_width
            puts_rail_type = 'descending'
        else:
            puts_entry = cone.ascending_rail
            puts_target = cone.descending_rail
            puts_rail_type = 'ascending'
        
        puts_stop = puts_entry + STOP_LOSS_PTS
        puts_reward = abs(puts_entry - puts_target)
        puts_strike = round(puts_entry + STRIKE_OFFSET, 0)
        puts_delta = get_delta_estimate(STRIKE_OFFSET)
        
        setups.append(TradeSetup(
            direction='PUTS',
            entry_price=puts_entry,
            target_price=puts_target,
            stop_price=puts_stop,
            cone_name=cone.name,
            rail_type=puts_rail_type,
            risk_pts=STOP_LOSS_PTS,
            reward_pts=puts_reward,
            rr_ratio=puts_reward / STOP_LOSS_PTS,
            strike=puts_strike,
            delta=puts_delta,
            expected_profit=puts_reward * puts_delta * 100,
            max_loss=STOP_LOSS_PTS * puts_delta * 100,
            vix_condition="VIX at SUPPORT"
        ))
    
    return setups

def check_confluence(trade_setup: TradeSetup, vix_zone: VIXZone,
                     spx_price: float) -> Tuple[bool, str]:
    if vix_zone is None or vix_zone.current <= 0:
        return False, "Enter VIX"
    
    distance_to_entry = abs(spx_price - trade_setup.entry_price)
    spx_at_rail = distance_to_entry <= AT_RAIL_THRESHOLD
    
    if not spx_at_rail:
        return False, f"{distance_to_entry:.1f} pts away"
    
    if trade_setup.direction == 'CALLS':
        vix_aligned = vix_zone.trade_bias == 'CALLS'
        if not vix_aligned:
            return False, f"VIX {vix_zone.position_pct:.0f}%"
    else:
        vix_aligned = vix_zone.trade_bias == 'PUTS'
        if not vix_aligned:
            return False, f"VIX {vix_zone.position_pct:.0f}%"
    
    return True, "✅ GO!"

# ============================================================================
# ============================================================================
#
#                        PART 2: CLEAN CSS STYLES
#
#                        ★ MOBILE-FRIENDLY ★
#
#               All fonts sized properly - nothing cut off
#               Tested for phone and desktop viewing
#
# ============================================================================
# ============================================================================

def inject_premium_css():
    """
    Inject clean, mobile-friendly CSS.
    All font sizes carefully tested to prevent cutoff.
    """
    
    st.markdown(
        """
        <style>
        
        /* ================================================================
           GLOBAL STYLES
           ================================================================ */
        
        .stApp {
            background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
        }
        
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%);
            border-right: 1px solid #e2e8f0;
        }
        
        /* ================================================================
           HEADER - Sized for mobile
           ================================================================ */
        
        .prophet-header {
            background: linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #0ea5e9 100%);
            border-radius: 16px;
            padding: 24px 16px;
            margin-bottom: 20px;
            text-align: center;
            box-shadow: 0 8px 24px rgba(30, 64, 175, 0.2);
        }
        
        .prophet-title {
            font-size: 1.5rem;
            font-weight: 800;
            color: white;
            margin: 0;
            letter-spacing: 3px;
        }
        
        .prophet-subtitle {
            color: rgba(255, 255, 255, 0.9);
            font-size: 0.75rem;
            letter-spacing: 2px;
            margin-top: 8px;
            font-weight: 500;
        }
        
        .prophet-version {
            display: inline-block;
            background: rgba(255, 255, 255, 0.2);
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.65rem;
            letter-spacing: 1px;
            margin-top: 12px;
            color: white;
        }
        
        /* ================================================================
           STATUS CARDS - Compact for mobile
           ================================================================ */
        
        .status-card {
            background: white;
            border-radius: 12px;
            padding: 12px 16px;
            margin-bottom: 12px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        }
        
        .status-label {
            font-size: 0.7rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
            margin-bottom: 4px;
        }
        
        .status-value {
            font-size: 1.1rem;
            font-weight: 700;
            color: #1e293b;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace;
        }
        
        .status-value-small {
            font-size: 0.95rem;
            font-weight: 700;
            color: #1e293b;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace;
        }
        
        .status-delta {
            font-size: 0.7rem;
            padding: 2px 8px;
            border-radius: 8px;
            display: inline-block;
            margin-top: 4px;
            font-weight: 600;
        }
        
        .delta-green {
            background: #dcfce7;
            color: #16a34a;
        }
        
        .delta-red {
            background: #fee2e2;
            color: #dc2626;
        }
        
        .delta-yellow {
            background: #fef9c3;
            color: #b45309;
        }
        
        .delta-blue {
            background: #dbeafe;
            color: #2563eb;
        }
        
        /* ================================================================
           VIX ZONE PANEL
           ================================================================ */
        
        .vix-panel {
            background: white;
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 16px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        }
        
        .vix-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            padding-bottom: 12px;
            border-bottom: 1px solid #f1f5f9;
        }
        
        .vix-title {
            font-size: 0.9rem;
            font-weight: 700;
            color: #1e293b;
        }
        
        .vix-badge {
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 700;
            color: white;
        }
        
        .badge-calls {
            background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
        }
        
        .badge-puts {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        }
        
        .badge-neutral {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        }
        
        /* VIX Ladder */
        .zone-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            margin: 4px 0;
            border-radius: 8px;
            font-size: 0.8rem;
        }
        
        .zone-extend-up {
            background: linear-gradient(90deg, #fee2e2 0%, #fff 100%);
            border-left: 3px solid #f87171;
        }
        
        .zone-extend-down {
            background: linear-gradient(90deg, #dcfce7 0%, #fff 100%);
            border-left: 3px solid #4ade80;
        }
        
        .zone-resistance {
            background: linear-gradient(90deg, #fecaca 0%, #fee2e2 100%);
            border: 1px solid #ef4444;
        }
        
        .zone-support {
            background: linear-gradient(90deg, #bbf7d0 0%, #dcfce7 100%);
            border: 1px solid #22c55e;
        }
        
        .zone-current {
            background: linear-gradient(90deg, #bfdbfe 0%, #dbeafe 100%);
            border: 1px solid #3b82f6;
        }
        
        .zone-label {
            font-weight: 700;
            font-size: 0.75rem;
            min-width: 45px;
        }
        
        .zone-price {
            font-weight: 600;
            font-size: 0.85rem;
            font-family: -apple-system, BlinkMacSystemFont, monospace;
            color: #1e293b;
        }
        
        .zone-action {
            font-size: 0.7rem;
            color: #64748b;
        }
        
        /* ================================================================
           TRADE CARDS - Compact and readable
           ================================================================ */
        
        .trade-card {
            background: white;
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 16px;
            border-left: 4px solid;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        }
        
        .trade-card-calls {
            border-left-color: #22c55e;
        }
        
        .trade-card-puts {
            border-left-color: #ef4444;
        }
        
        .trade-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        
        .trade-direction {
            font-size: 0.9rem;
            font-weight: 800;
            letter-spacing: 1px;
        }
        
        .trade-calls {
            color: #16a34a;
        }
        
        .trade-puts {
            color: #dc2626;
        }
        
        .trade-cone {
            font-size: 0.75rem;
            color: #64748b;
            font-weight: 500;
        }
        
        .trade-status {
            font-size: 0.7rem;
            padding: 4px 10px;
            border-radius: 10px;
            font-weight: 600;
        }
        
        .status-at-rail {
            background: #dcfce7;
            color: #16a34a;
        }
        
        .status-waiting {
            background: #f1f5f9;
            color: #64748b;
        }
        
        /* Trade Grid */
        .trade-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin-bottom: 12px;
        }
        
        .trade-stat {
            background: #f8fafc;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 0.95rem;
            font-weight: 700;
            font-family: -apple-system, BlinkMacSystemFont, monospace;
            margin-bottom: 2px;
        }
        
        .stat-entry { color: #2563eb; }
        .stat-target { color: #ca8a04; }
        .stat-stop { color: #dc2626; }
        .stat-strike { color: #7c3aed; }
        
        .stat-label {
            font-size: 0.65rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 600;
        }
        
        /* P/L Row */
        .pnl-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            padding-top: 12px;
            border-top: 1px solid #f1f5f9;
        }
        
        .pnl-box {
            border-radius: 8px;
            padding: 8px;
            text-align: center;
        }
        
        .pnl-profit {
            background: #dcfce7;
        }
        
        .pnl-loss {
            background: #fee2e2;
        }
        
        .pnl-rr {
            background: #dbeafe;
        }
        
        .pnl-value {
            font-size: 0.85rem;
            font-weight: 700;
            font-family: -apple-system, BlinkMacSystemFont, monospace;
        }
        
        .pnl-green { color: #16a34a; }
        .pnl-red { color: #dc2626; }
        .pnl-blue { color: #2563eb; }
        
        .pnl-label {
            font-size: 0.6rem;
            color: #64748b;
            text-transform: uppercase;
            margin-top: 2px;
        }
        
        /* Confluence */
        .confluence-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #f1f5f9;
            font-size: 0.75rem;
        }
        
        .confluence-label {
            color: #64748b;
        }
        
        .confluence-status {
            padding: 4px 10px;
            border-radius: 10px;
            font-weight: 700;
        }
        
        .confluence-go {
            background: #dcfce7;
            color: #16a34a;
        }
        
        .confluence-wait {
            background: #f1f5f9;
            color: #64748b;
        }
        
        /* ================================================================
           GAP BANNER
           ================================================================ */
        
        .gap-banner {
            border-radius: 12px;
            padding: 12px 16px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .gap-up {
            background: linear-gradient(90deg, #dcfce7 0%, #f0fdf4 100%);
            border: 1px solid #86efac;
        }
        
        .gap-down {
            background: linear-gradient(90deg, #fee2e2 0%, #fef2f2 100%);
            border: 1px solid #fca5a5;
        }
        
        .gap-icon {
            font-size: 1.5rem;
        }
        
        .gap-title {
            font-size: 0.85rem;
            font-weight: 700;
            color: #1e293b;
        }
        
        .gap-detail {
            font-size: 0.75rem;
            color: #64748b;
        }
        
        .gap-pivot {
            font-weight: 700;
            color: #ca8a04;
            font-family: monospace;
        }
        
        /* ================================================================
           CHECKLIST
           ================================================================ */
        
        .check-item {
            display: flex;
            align-items: center;
            padding: 10px 12px;
            margin: 6px 0;
            border-radius: 8px;
            font-size: 0.8rem;
        }
        
        .check-pass {
            background: linear-gradient(90deg, #dcfce7 0%, #fff 100%);
            border-left: 3px solid #22c55e;
        }
        
        .check-fail {
            background: linear-gradient(90deg, #fee2e2 0%, #fff 100%);
            border-left: 3px solid #ef4444;
        }
        
        .check-icon {
            font-size: 1rem;
            margin-right: 10px;
        }
        
        .check-label {
            flex: 1;
            font-weight: 600;
            color: #1e293b;
        }
        
        .check-value {
            font-size: 0.75rem;
            color: #64748b;
            font-family: monospace;
        }
        
        /* Direction Box */
        .direction-box {
            text-align: center;
            padding: 16px;
            border-radius: 12px;
            margin-top: 12px;
        }
        
        .direction-calls {
            background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
            border: 1px solid #22c55e;
        }
        
        .direction-puts {
            background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
            border: 1px solid #ef4444;
        }
        
        .direction-label {
            font-size: 0.7rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }
        
        .direction-value {
            font-size: 1.3rem;
            font-weight: 800;
            letter-spacing: 2px;
        }
        
        .direction-green { color: #16a34a; }
        .direction-red { color: #dc2626; }
        
        .direction-detail {
            font-size: 0.7rem;
            color: #64748b;
            margin-top: 4px;
        }
        
        /* ================================================================
           INFO PANELS
           ================================================================ */
        
        .info-panel {
            background: white;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            border: 1px solid #e2e8f0;
        }
        
        .info-title {
            font-size: 0.75rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
            font-weight: 700;
        }
        
        .info-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #f1f5f9;
            font-size: 0.8rem;
        }
        
        .info-row:last-child {
            border-bottom: none;
        }
        
        .info-label {
            color: #64748b;
        }
        
        .info-value {
            font-weight: 600;
            font-family: -apple-system, BlinkMacSystemFont, monospace;
            color: #1e293b;
        }
        
        /* ================================================================
           LEGEND
           ================================================================ */
        
        .legend-item {
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            background: #f8fafc;
            border-left: 3px solid;
        }
        
        .legend-calls { border-left-color: #22c55e; }
        .legend-puts { border-left-color: #ef4444; }
        .legend-breakout { border-left-color: #f59e0b; }
        
        .legend-title {
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 4px;
            font-size: 0.8rem;
        }
        
        .legend-text {
            font-size: 0.75rem;
            color: #64748b;
            line-height: 1.5;
        }
        
        /* ================================================================
           FOOTER
           ================================================================ */
        
        .footer {
            text-align: center;
            padding: 16px;
            margin-top: 24px;
            border-top: 1px solid #e2e8f0;
            font-size: 0.7rem;
            color: #64748b;
        }
        
        .footer-brand {
            font-weight: 700;
            color: #3b82f6;
        }
        
        /* ================================================================
           TABS STYLING
           ================================================================ */
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background: white;
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: 600;
            font-size: 0.8rem;
            color: #64748b;
            border: 1px solid #e2e8f0;
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
            border-color: transparent;
        }
        
        /* ================================================================
           RESPONSIVE OVERRIDES
           ================================================================ */
        
        @media (max-width: 768px) {
            .prophet-title {
                font-size: 1.3rem;
                letter-spacing: 2px;
            }
            
            .prophet-subtitle {
                font-size: 0.65rem;
            }
            
            .trade-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .pnl-grid {
                grid-template-columns: repeat(3, 1fr);
            }
            
            .stat-value {
                font-size: 0.85rem;
            }
            
            .pnl-value {
                font-size: 0.75rem;
            }
        }
        
        </style>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# ============================================================================
#
#                        PART 3: UI COMPONENTS
#
#                   ★ BEAUTIFUL + RELIABLE HYBRID ★
#
#           Beautiful HTML for: Header, Trade Cards, VIX Panel
#           Native Streamlit for: Checklist, Legend, Tables
#
# ============================================================================
# ============================================================================


# ============================================================================
# SECTION 3.1: HEADER - Beautiful HTML
# ============================================================================

def render_header():
    """Render the stunning header."""
    
    st.markdown("""
    <div class="prophet-header">
        <div class="prophet-title">SPX PROPHET</div>
        <div class="prophet-subtitle">Where Structure Becomes Foresight</div>
        <div class="prophet-version">v2.1 • Legendary Edition</div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# SECTION 3.2: METRICS ROW - Beautiful HTML
# ============================================================================

def render_metrics_row(current_price: float, vix_zone: Optional[VIXZone],
                       nearest_distance: float, cone_width: float):
    """Render metrics with beautiful styling."""
    
    # SPX Card
    spx_html = f"""
    <div class="status-card">
        <div class="status-label">💹 SPX Price</div>
        <div class="status-value">{current_price:,.2f}</div>
    </div>
    """
    
    # VIX Card
    if vix_zone and vix_zone.current > 0:
        if vix_zone.trade_bias == "CALLS":
            delta_class = "delta-green"
        elif vix_zone.trade_bias == "PUTS":
            delta_class = "delta-red"
        else:
            delta_class = "delta-yellow"
        
        vix_html = f"""
        <div class="status-card">
            <div class="status-label">📊 VIX 30m Close</div>
            <div class="status-value">{vix_zone.current:.2f}</div>
            <div class="status-delta {delta_class}">{vix_zone.trade_bias} ({vix_zone.position_pct:.0f}%)</div>
        </div>
        """
    else:
        vix_html = """
        <div class="status-card">
            <div class="status-label">📊 VIX 30m Close</div>
            <div class="status-value">—</div>
            <div class="status-delta delta-blue">Enter Data</div>
        </div>
        """
    
    # Distance Card
    if nearest_distance <= AT_RAIL_THRESHOLD:
        dist_delta = "delta-green"
        dist_text = "🎯 AT RAIL"
    else:
        dist_delta = "delta-yellow"
        dist_text = "Waiting"
    
    dist_html = f"""
    <div class="status-card">
        <div class="status-label">📍 To Rail</div>
        <div class="status-value">{nearest_distance:.1f} pts</div>
        <div class="status-delta {dist_delta}">{dist_text}</div>
    </div>
    """
    
    # Width Card
    if cone_width >= 25:
        width_delta = "delta-green"
        width_text = "✅ Wide"
    elif cone_width >= MIN_CONE_WIDTH:
        width_delta = "delta-yellow"
        width_text = "⚠️ OK"
    else:
        width_delta = "delta-red"
        width_text = "❌ Narrow"
    
    width_html = f"""
    <div class="status-card">
        <div class="status-label">📐 Cone Width</div>
        <div class="status-value">{cone_width:.0f} pts</div>
        <div class="status-delta {width_delta}">{width_text}</div>
    </div>
    """
    
    # Render in 2x2 grid
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(spx_html, unsafe_allow_html=True)
        st.markdown(dist_html, unsafe_allow_html=True)
    with col2:
        st.markdown(vix_html, unsafe_allow_html=True)
        st.markdown(width_html, unsafe_allow_html=True)


# ============================================================================
# SECTION 3.3: GAP BANNER - Beautiful HTML
# ============================================================================

def render_gap_banner(gap_analysis: GapAnalysis):
    """Render gap day alert with beautiful styling."""
    
    if gap_analysis.gap_type == 'NORMAL':
        return
    
    if gap_analysis.gap_type == 'GAP_UP':
        gap_html = f"""
        <div class="gap-banner gap-up">
            <div class="gap-icon">🚀</div>
            <div>
                <div class="gap-title">GAP UP — Ascending = Support</div>
                <div class="gap-detail">Pivot: <span class="gap-pivot">{gap_analysis.overnight_pivot:.2f}</span> → CALLS at ascending rail</div>
            </div>
        </div>
        """
    else:
        gap_html = f"""
        <div class="gap-banner gap-down">
            <div class="gap-icon">📉</div>
            <div>
                <div class="gap-title">GAP DOWN — Descending = Resistance</div>
                <div class="gap-detail">Pivot: <span class="gap-pivot">{gap_analysis.overnight_pivot:.2f}</span> → PUTS at descending rail</div>
            </div>
        </div>
        """
    
    st.markdown(gap_html, unsafe_allow_html=True)


# ============================================================================
# SECTION 3.4: VIX ZONE PANEL - Beautiful HTML
# ============================================================================

def render_vix_zone_panel(vix_zone: VIXZone):
    """Render VIX Zone with beautiful ladder."""
    
    status, action = get_vix_zone_status(vix_zone)
    
    # Badge class
    if vix_zone.trade_bias == "CALLS":
        badge_class = "badge-calls"
    elif vix_zone.trade_bias == "PUTS":
        badge_class = "badge-puts"
    else:
        badge_class = "badge-neutral"
    
    # Build ladder HTML
    ladder_html = ""
    
    # Levels above (from +4 to +1)
    for i in range(3, -1, -1):
        ladder_html += f"""
        <div class="zone-row zone-extend-up">
            <span class="zone-label" style="color:#dc2626;">+{i+1}</span>
            <span class="zone-price">{vix_zone.levels_above[i]:.2f}</span>
            <span class="zone-action">🔴 PUTS extend</span>
        </div>
        """
    
    # Resistance
    ladder_html += f"""
    <div class="zone-row zone-resistance">
        <span class="zone-label" style="color:#dc2626;">RES</span>
        <span class="zone-price">{vix_zone.resistance:.2f}</span>
        <span class="zone-action" style="color:#16a34a;font-weight:700;">🟢 CALLS</span>
    </div>
    """
    
    # Current
    if vix_zone.current > 0:
        ladder_html += f"""
        <div class="zone-row zone-current">
            <span class="zone-label" style="color:#2563eb;">NOW</span>
            <span class="zone-price">{vix_zone.current:.2f}</span>
            <span class="zone-action" style="color:#2563eb;font-weight:700;">{vix_zone.position_pct:.0f}%</span>
        </div>
        """
    
    # Support
    ladder_html += f"""
    <div class="zone-row zone-support">
        <span class="zone-label" style="color:#16a34a;">SUP</span>
        <span class="zone-price">{vix_zone.support:.2f}</span>
        <span class="zone-action" style="color:#dc2626;font-weight:700;">🔴 PUTS</span>
    </div>
    """
    
    # Levels below (from -1 to -4)
    for i in range(4):
        ladder_html += f"""
        <div class="zone-row zone-extend-down">
            <span class="zone-label" style="color:#16a34a;">-{i+1}</span>
            <span class="zone-price">{vix_zone.levels_below[i]:.2f}</span>
            <span class="zone-action">🟢 CALLS extend</span>
        </div>
        """
    
    # Full panel
    panel_html = f"""
    <div class="vix-panel">
        <div class="vix-header">
            <div class="vix-title">🧭 VIX Trade Compass</div>
            <div class="vix-badge {badge_class}">{vix_zone.trade_bias}</div>
        </div>
        <div style="background:#f8fafc;border-radius:8px;padding:10px 12px;margin-bottom:12px;">
            <div style="font-weight:600;color:#1e293b;font-size:0.85rem;">{status}</div>
            <div style="color:#64748b;font-size:0.75rem;">{action}</div>
        </div>
        {ladder_html}
        <div style="text-align:center;padding-top:12px;border-top:1px solid #f1f5f9;margin-top:12px;">
            <span style="font-size:0.7rem;color:#64748b;">Zone: {vix_zone.zone_size:.2f} | 80%+ = CALLS | 20%- = PUTS</span>
        </div>
    </div>
    """
    
    st.markdown(panel_html, unsafe_allow_html=True)


# ============================================================================
# SECTION 3.5: TRADE CARD - Beautiful HTML
# ============================================================================

def render_trade_card(setup: TradeSetup, current_price: float, vix_zone: Optional[VIXZone]):
    """Render beautiful trade card."""
    
    distance = abs(current_price - setup.entry_price)
    is_near = distance <= AT_RAIL_THRESHOLD
    
    # Classes
    if setup.direction == "CALLS":
        card_class = "trade-card-calls"
        dir_class = "trade-calls"
    else:
        card_class = "trade-card-puts"
        dir_class = "trade-puts"
    
    # Status
    if is_near:
        status_class = "status-at-rail"
        status_text = f"🎯 AT RAIL ({distance:.1f})"
    else:
        status_class = "status-waiting"
        status_text = f"⏳ {distance:.1f} pts away"
    
    # Confluence
    confluence_ok = False
    confluence_text = "Enter VIX"
    if vix_zone and vix_zone.current > 0:
        confluence_ok, confluence_text = check_confluence(setup, vix_zone, current_price)
    
    confluence_class = "confluence-go" if confluence_ok else "confluence-wait"
    
    card_html = f"""
    <div class="trade-card {card_class}">
        <div class="trade-header">
            <div>
                <span class="trade-direction {dir_class}">{setup.direction}</span>
                <span class="trade-cone">{setup.cone_name} • {setup.rail_type.upper()}</span>
            </div>
            <div class="trade-status {status_class}">{status_text}</div>
        </div>
        <div class="trade-grid">
            <div class="trade-stat">
                <div class="stat-value stat-entry">{setup.entry_price:.2f}</div>
                <div class="stat-label">Entry</div>
            </div>
            <div class="trade-stat">
                <div class="stat-value stat-target">{setup.target_price:.2f}</div>
                <div class="stat-label">Target</div>
            </div>
            <div class="trade-stat">
                <div class="stat-value stat-stop">{setup.stop_price:.2f}</div>
                <div class="stat-label">Stop</div>
            </div>
            <div class="trade-stat">
                <div class="stat-value stat-strike">{setup.strike:.0f}</div>
                <div class="stat-label">Strike Δ{setup.delta:.2f}</div>
            </div>
        </div>
        <div class="pnl-grid">
            <div class="pnl-box pnl-profit">
                <div class="pnl-value pnl-green">+${setup.expected_profit:.0f}</div>
                <div class="pnl-label">Profit</div>
            </div>
            <div class="pnl-box pnl-loss">
                <div class="pnl-value pnl-red">-${setup.max_loss:.0f}</div>
                <div class="pnl-label">Max Loss</div>
            </div>
            <div class="pnl-box pnl-rr">
                <div class="pnl-value pnl-blue">{setup.rr_ratio:.1f}:1</div>
                <div class="pnl-label">R:R</div>
            </div>
        </div>
        <div class="confluence-row">
            <span class="confluence-label">Req: {setup.vix_condition}</span>
            <span class="confluence-status {confluence_class}">{confluence_text}</span>
        </div>
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)


# ============================================================================
# SECTION 3.6: CHECKLIST - Native Streamlit (Reliable)
# ============================================================================

def render_checklist(cones: List[Cone], current_price: float, vix_zone: Optional[VIXZone]):
    """Render checklist using native Streamlit for reliability."""
    
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    cone_width = abs(nearest_cone.ascending_rail - nearest_cone.descending_rail) if nearest_cone else 0
    
    # Expected direction
    if nearest_rail_type == 'descending':
        expected_direction = 'CALLS'
        expected_vix = 'CALLS'
    else:
        expected_direction = 'PUTS'
        expected_vix = 'PUTS'
    
    # Checks
    at_rail_ok = nearest_distance <= AT_RAIL_THRESHOLD
    structure_ok = cone_width >= MIN_CONE_WIDTH
    cone_ok = nearest_cone is not None
    
    if vix_zone and vix_zone.current > 0:
        vix_ok = vix_zone.trade_bias == expected_vix
        vix_detail = f"{vix_zone.trade_bias} ({vix_zone.position_pct:.0f}%)"
    else:
        vix_ok = False
        vix_detail = "Enter data"
    
    passed = sum([at_rail_ok, structure_ok, cone_ok, vix_ok])
    
    # Header
    st.markdown("### 📋 Checklist")
    
    if passed == 4:
        st.success(f"**🟢 CONFLUENCE — GO!** ({passed}/4)")
    elif passed >= 3 and at_rail_ok:
        st.success(f"**🟢 STRONG** ({passed}/4)")
    elif not at_rail_ok:
        st.warning(f"**🟡 WAIT** ({passed}/4)")
    else:
        st.error(f"**🔴 SKIP** ({passed}/4)")
    
    # Checks
    if at_rail_ok:
        st.success(f"✅ At Rail — {nearest_distance:.1f}")
    else:
        st.error(f"❌ At Rail — {nearest_distance:.1f}")
    
    if structure_ok:
        st.success(f"✅ Structure — {cone_width:.0f}")
    else:
        st.error(f"❌ Structure — {cone_width:.0f}")
    
    if cone_ok:
        st.success(f"✅ Cone — {nearest_cone.name}")
    else:
        st.error(f"❌ Cone — None")
    
    if vix_ok:
        st.success(f"✅ VIX — {vix_detail}")
    else:
        st.error(f"❌ VIX — {vix_detail}")
    
    # Direction
    if expected_direction == "CALLS":
        st.success(f"**🎯 CALLS** | {nearest_cone.name if nearest_cone else 'N/A'} | {nearest_rail_type}")
    else:
        st.error(f"**🎯 PUTS** | {nearest_cone.name if nearest_cone else 'N/A'} | {nearest_rail_type}")


# ============================================================================
# SECTION 3.7: RTH TABLE - Native Streamlit DataFrame
# ============================================================================

def render_rth_table(cones: List[Cone], current_price: float, session_date):
    """Render RTH table using DataFrame."""
    
    st.markdown("### 📊 RTH Rails")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("🔵 8:30 = Open")
    with col2:
        st.success("🟢 10:00 = Target")
    
    # Build table
    ct_now = get_ct_now()
    rows = []
    
    for time_label, time_val, is_open, is_target in RTH_TIME_BLOCKS:
        target_dt = ct_now.replace(hour=time_val.hour, minute=time_val.minute, second=0, microsecond=0)
        
        if is_open:
            t = f"🔵{time_label}"
        elif is_target:
            t = f"🟢{time_label}"
        else:
            t = time_label
        
        row = {"Time": t}
        
        for cone in cones:
            asc = calculate_rail_price(cone.pivot.price, cone.pivot.time, target_dt, True)
            desc = calculate_rail_price(cone.pivot.price, cone.pivot.time, target_dt, False)
            row[f"{cone.name}▲"] = f"{asc:.2f}"
            row[f"{cone.name}▼"] = f"{desc:.2f}"
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, height=530)


# ============================================================================
# SECTION 3.8: PIVOTS PANEL - Beautiful HTML
# ============================================================================

def render_pivots_panel(high_price: float, low_price: float, close_price: float, prior_date):
    """Render pivots with beautiful styling."""
    
    date_str = prior_date.strftime('%b %d') if hasattr(prior_date, 'strftime') else str(prior_date)
    
    panel_html = f"""
    <div class="info-panel">
        <div class="info-title">📍 Prior Session ({date_str})</div>
        <div class="info-row">
            <span class="info-label">🔴 High (Wick)</span>
            <span class="info-value" style="color:#dc2626;">{high_price:.2f}</span>
        </div>
        <div class="info-row">
            <span class="info-label">🟢 Low (Close)</span>
            <span class="info-value" style="color:#16a34a;">{low_price:.2f}</span>
        </div>
        <div class="info-row">
            <span class="info-label">🟡 Close</span>
            <span class="info-value" style="color:#ca8a04;">{close_price:.2f}</span>
        </div>
    </div>
    """
    
    st.markdown(panel_html, unsafe_allow_html=True)


# ============================================================================
# SECTION 3.9: RAILS PANEL - Beautiful HTML
# ============================================================================

def render_rails_panel(cones: List[Cone]):
    """Render 10am rails with beautiful styling."""
    
    rows_html = ""
    for cone in cones:
        rows_html += f"""
        <div class="info-row">
            <span class="info-label">{cone.name}</span>
            <span>
                <span style="color:#dc2626;font-weight:600;">▲{cone.ascending_rail:.2f}</span>
                <span style="margin:0 8px;color:#cbd5e1;">|</span>
                <span style="color:#16a34a;font-weight:600;">▼{cone.descending_rail:.2f}</span>
            </span>
        </div>
        """
    
    panel_html = f"""
    <div class="info-panel">
        <div class="info-title">📐 10:00 AM Rails</div>
        <div style="font-size:0.7rem;color:#64748b;margin-bottom:8px;">▲ ASC=PUTS | ▼ DESC=CALLS</div>
        {rows_html}
    </div>
    """
    
    st.markdown(panel_html, unsafe_allow_html=True)


# ============================================================================
# SECTION 3.10: LEGEND - Native Streamlit Expanders
# ============================================================================

def render_legend():
    """Render trading rules using expanders."""
    
    st.markdown("### 📚 Rules")
    
    with st.expander("🟢 CALLS", expanded=False):
        st.markdown("""
**Required:**
- VIX closes at **RESISTANCE** (80%+)
- SPX at **DESCENDING** rail

VIX drops → SPX rises
        """)
    
    with st.expander("🔴 PUTS", expanded=False):
        st.markdown("""
**Required:**
- VIX closes at **SUPPORT** (≤20%)
- SPX at **ASCENDING** rail

VIX rises → SPX drops
        """)
    
    with st.expander("⚠️ Breakouts", expanded=False):
        st.markdown("""
- Above resistance → PUTS extend
- Below support → CALLS extend
        """)
    
    with st.expander("🚀 Gap Days", expanded=False):
        st.markdown("""
**Gap UP:** Ascending = Support → CALLS
**Gap DOWN:** Descending = Resistance → PUTS
        """)
    
    st.warning("⏰ **30-min CLOSE matters!**")


# ============================================================================
# SECTION 3.11: FOOTER
# ============================================================================

def render_footer():
    """Render footer."""
    ct_now = get_ct_now()
    
    footer_html = f"""
    <div class="footer">
        <span class="footer-brand">SPX PROPHET v2.1</span> | {ct_now.strftime('%I:%M %p CT')} | 30-min CLOSE is everything! 🎯
    </div>
    """
    
    st.markdown(footer_html, unsafe_allow_html=True)


# ============================================================================
# SECTION 3.12: SIDEBAR STATUS - Native Streamlit
# ============================================================================

def render_sidebar_status(vix_zone: Optional[VIXZone], nearest_distance: float,
                          nearest_rail_type: str, cone_width: float):
    """Render sidebar status."""
    
    st.markdown("### 📡 Status")
    
    if vix_zone and vix_zone.current > 0:
        if vix_zone.trade_bias == "CALLS":
            st.success(f"VIX: **CALLS** ({vix_zone.position_pct:.0f}%)")
        elif vix_zone.trade_bias == "PUTS":
            st.error(f"VIX: **PUTS** ({vix_zone.position_pct:.0f}%)")
        else:
            st.warning(f"VIX: **WAIT** ({vix_zone.position_pct:.0f}%)")
    else:
        st.info("VIX: Enter data")
    
    if nearest_distance <= AT_RAIL_THRESHOLD:
        st.success(f"Rail: **AT RAIL** ({nearest_distance:.1f})")
    else:
        st.warning(f"Rail: {nearest_distance:.1f} pts")
    
    expected_dir = "CALLS" if nearest_rail_type == 'descending' else "PUTS"
    if expected_dir == "CALLS":
        st.success(f"Dir: **{expected_dir}**")
    else:
        st.error(f"Dir: **{expected_dir}**")


# ============================================================================
# SECTION 3.13: SECTION HEADER
# ============================================================================

def render_section_header(icon: str, title: str):
    """Simple section header."""
    st.markdown(f"## {icon} {title}")

# ============================================================================
# ============================================================================
#
#                        PART 4: MAIN APPLICATION
#
#                   ★ BRINGING IT ALL TOGETHER ★
#
#           Sidebar Controls • Main Layout • Full Integration
#
# ============================================================================
# ============================================================================

def main():
    """Main application entry point."""
    
    # ========================================================================
    # PAGE CONFIG
    # ========================================================================
    st.set_page_config(
        page_title="SPX Prophet v2.1",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # ========================================================================
    # INJECT CSS
    # ========================================================================
    inject_premium_css()
    
    # ========================================================================
    # HEADER
    # ========================================================================
    render_header()
    
    # ========================================================================
    # SIDEBAR CONTROLS
    # ========================================================================
    with st.sidebar:
        st.markdown("## ⚙️ Controls")
        
        # --------------------------------------------------------------------
        # SESSION DATE
        # --------------------------------------------------------------------
        st.markdown("### 📅 Session")
        session_date = st.date_input(
            "Date",
            value=get_ct_now().date(),
            help="Trading session date"
        )
        session_date_dt = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        
        ct_now = get_ct_now()
        st.caption(f"🕐 {ct_now.strftime('%I:%M %p CT')} | {ct_now.strftime('%a %b %d')}")
        
        st.markdown("---")
        
        # --------------------------------------------------------------------
        # VIX ZONE
        # --------------------------------------------------------------------
        st.markdown("### 🧭 VIX Zone")
        st.caption("From overnight (5pm-2am CT)")
        
        if 'vix_support' not in st.session_state:
            st.session_state.vix_support = 0.0
        if 'vix_resistance' not in st.session_state:
            st.session_state.vix_resistance = 0.0
        if 'vix_current' not in st.session_state:
            st.session_state.vix_current = 0.0
        
        vix_support = st.number_input(
            "Support (Bottom)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_support,
            step=0.01,
            format="%.2f",
            help="Overnight low CLOSE"
        )
        st.session_state.vix_support = vix_support
        
        vix_resistance = st.number_input(
            "Resistance (Top)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_resistance,
            step=0.01,
            format="%.2f",
            help="Overnight high CLOSE"
        )
        st.session_state.vix_resistance = vix_resistance
        
        vix_current = st.number_input(
            "Current (30m Close)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_current,
            step=0.01,
            format="%.2f",
            help="Latest 30-min CLOSE"
        )
        st.session_state.vix_current = vix_current
        
        # Calculate VIX zone
        vix_zone = None
        if vix_support > 0 and vix_resistance > 0:
            vix_zone = calculate_vix_zones(vix_support, vix_resistance, vix_current)
            
            zone_size = vix_resistance - vix_support
            if 0.13 <= zone_size <= 0.17:
                st.success(f"✅ Valid zone: {zone_size:.2f}")
            elif zone_size > 0:
                st.info(f"📊 Zone: {zone_size:.2f}")
            
            if vix_zone.trade_bias == "CALLS":
                st.success(f"🟢 **CALLS** ({vix_zone.position_pct:.0f}%)")
            elif vix_zone.trade_bias == "PUTS":
                st.error(f"🔴 **PUTS** ({vix_zone.position_pct:.0f}%)")
            elif vix_zone.current > 0:
                st.warning(f"🟡 **WAIT** ({vix_zone.position_pct:.0f}%)")
        
        st.markdown("---")
        
        # --------------------------------------------------------------------
        # ES-SPX OFFSET
        # --------------------------------------------------------------------
        st.markdown("### 📊 ES-SPX Offset")
        
        if 'es_offset' not in st.session_state:
            st.session_state.es_offset = 0.0
        
        es_offset = st.number_input(
            "ES minus SPX",
            min_value=-100.0,
            max_value=100.0,
            value=st.session_state.es_offset,
            step=0.25,
            format="%.2f",
            help="Positive if ES > SPX"
        )
        st.session_state.es_offset = es_offset
        
        if es_offset >= 0:
            st.caption(f"ES is {es_offset:.2f} ABOVE SPX")
        else:
            st.caption(f"ES is {abs(es_offset):.2f} BELOW SPX")
        
        st.markdown("---")
        
        # --------------------------------------------------------------------
        # OVERNIGHT PIVOTS
        # --------------------------------------------------------------------
        st.markdown("### 🌙 Overnight ES")
        st.caption("For gap detection")
        
        if 'overnight_es_high' not in st.session_state:
            st.session_state.overnight_es_high = 0.0
        if 'overnight_es_low' not in st.session_state:
            st.session_state.overnight_es_low = 0.0
        
        overnight_es_high = st.number_input(
            "ES High",
            min_value=0.0,
            max_value=10000.0,
            value=st.session_state.overnight_es_high,
            step=0.25,
            format="%.2f"
        )
        st.session_state.overnight_es_high = overnight_es_high
        
        overnight_es_low = st.number_input(
            "ES Low",
            min_value=0.0,
            max_value=10000.0,
            value=st.session_state.overnight_es_low,
            step=0.25,
            format="%.2f"
        )
        st.session_state.overnight_es_low = overnight_es_low
        
        if overnight_es_high > 0:
            spx_high = convert_es_to_spx(overnight_es_high, es_offset)
            st.caption(f"SPX High: {spx_high:.2f}")
        
        if overnight_es_low > 0:
            spx_low = convert_es_to_spx(overnight_es_low, es_offset)
            st.caption(f"SPX Low: {spx_low:.2f}")
        
        st.markdown("---")
        
        # --------------------------------------------------------------------
        # MANUAL PIVOTS
        # --------------------------------------------------------------------
        st.markdown("### 📍 Manual Pivots")
        
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
                min_value=0.0,
                max_value=10000.0,
                value=st.session_state.manual_high,
                format="%.2f"
            )
            st.session_state.manual_low = st.number_input(
                "Low (Close)",
                min_value=0.0,
                max_value=10000.0,
                value=st.session_state.manual_low,
                format="%.2f"
            )
            st.session_state.manual_close = st.number_input(
                "Close",
                min_value=0.0,
                max_value=10000.0,
                value=st.session_state.manual_close,
                format="%.2f"
            )
        
        st.markdown("---")
        
        # --------------------------------------------------------------------
        # QUICK REFERENCE
        # --------------------------------------------------------------------
        with st.expander("📖 Quick Reference", expanded=False):
            st.markdown("""
**CALLS:**
- VIX at RESISTANCE (80%+)
- SPX at DESCENDING rail
- VIX drops → SPX rises

**PUTS:**
- VIX at SUPPORT (≤20%)
- SPX at ASCENDING rail
- VIX rises → SPX drops

**Rails:**
- ▼ DESC = Support → CALLS
- ▲ ASC = Resistance → PUTS

**Key Numbers:**
- Zone: 0.15
- Rail: ≤8 pts
- Width: ≥18 pts
- Stop: 6 pts
            """)
    
    # ========================================================================
    # MAIN CONTENT - FETCH DATA
    # ========================================================================
    
    prior_session = fetch_prior_session_data(session_date_dt)
    current_price = fetch_current_spx()
    
    if current_price is None:
        current_price = 6000.0
        st.warning("⚠️ Could not fetch SPX. Using placeholder.")
    
    # Determine pivots
    if use_manual and st.session_state.manual_high > 0:
        high_price = st.session_state.manual_high
        low_price = st.session_state.manual_low
        close_price = st.session_state.manual_close
        high_time = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(12, 0)))
        low_time = high_time
        prior_date = session_date - timedelta(days=1)
    elif prior_session:
        high_price = prior_session['high']
        low_price = prior_session['low']
        close_price = prior_session['close']
        high_time = prior_session['high_time']
        low_time = prior_session['low_time']
        prior_date = prior_session['date']
    else:
        st.error("⚠️ No data. Enable Manual Pivots.")
        st.stop()
    
    # Target time
    target_time = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
    
    # Create pivots
    pivots = [
        Pivot(price=high_price, time=high_time, name='High'),
        Pivot(price=low_price, time=low_time, name='Low'),
        Pivot(price=close_price, time=CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(15, 0))), name='Close'),
    ]
    
    # Create cones
    cones = [create_cone(p, target_time) for p in pivots]
    
    # ========================================================================
    # GAP DETECTION
    # ========================================================================
    gap_analysis = None
    
    if overnight_es_high > 0 and overnight_es_low > 0:
        overnight_spx_high = convert_es_to_spx(overnight_es_high, es_offset)
        overnight_spx_low = convert_es_to_spx(overnight_es_low, es_offset)
        
        high_cone = next((c for c in cones if c.name == 'High'), None)
        low_cone = next((c for c in cones if c.name == 'Low'), None)
        
        if high_cone and low_cone:
            gap_analysis = analyze_gap(
                current_price,
                high_cone,
                low_cone,
                overnight_spx_high,
                overnight_spx_low
            )
            
            if gap_analysis.gap_type == 'GAP_UP' and gap_analysis.overnight_pivot:
                gap_pivot = Pivot(
                    price=gap_analysis.overnight_pivot,
                    time=CT_TZ.localize(datetime.combine(session_date, time(8, 30))),
                    name='Gap Low'
                )
                cones.append(create_cone(gap_pivot, target_time))
            
            elif gap_analysis.gap_type == 'GAP_DOWN' and gap_analysis.overnight_pivot:
                gap_pivot = Pivot(
                    price=gap_analysis.overnight_pivot,
                    time=CT_TZ.localize(datetime.combine(session_date, time(8, 30))),
                    name='Gap High'
                )
                cones.append(create_cone(gap_pivot, target_time))
    
    # ========================================================================
    # CALCULATE METRICS
    # ========================================================================
    
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    cone_width = abs(nearest_cone.ascending_rail - nearest_cone.descending_rail) if nearest_cone else 0
    
    trade_setups = generate_trade_setups(cones, current_price, gap_analysis)
    
    # ========================================================================
    # RENDER METRICS ROW
    # ========================================================================
    render_metrics_row(current_price, vix_zone, nearest_distance, cone_width)
    
    # ========================================================================
    # GAP BANNER
    # ========================================================================
    if gap_analysis and gap_analysis.gap_type != 'NORMAL':
        render_gap_banner(gap_analysis)
    
    # ========================================================================
    # SIDEBAR STATUS (after calculations)
    # ========================================================================
    with st.sidebar:
        st.markdown("---")
        render_sidebar_status(vix_zone, nearest_distance, nearest_rail_type, cone_width)
    
    # ========================================================================
    # MAIN LAYOUT
    # ========================================================================
    
    # VIX Panel (full width on mobile)
    if vix_zone and vix_zone.support > 0:
        render_vix_zone_panel(vix_zone)
    
    # Trade Setups
    st.markdown("## 🎯 Trade Setups")
    
    calls_setups = sorted(
        [s for s in trade_setups if s.direction == 'CALLS'],
        key=lambda x: abs(current_price - x.entry_price)
    )
    puts_setups = sorted(
        [s for s in trade_setups if s.direction == 'PUTS'],
        key=lambda x: abs(current_price - x.entry_price)
    )
    
    tab_calls, tab_puts = st.tabs([
        f"🟢 CALLS ({len(calls_setups)})",
        f"🔴 PUTS ({len(puts_setups)})"
    ])
    
    with tab_calls:
        if calls_setups:
            for setup in calls_setups[:4]:
                render_trade_card(setup, current_price, vix_zone)
        else:
            st.info("No CALLS setups. Cones may be too narrow.")
    
    with tab_puts:
        if puts_setups:
            for setup in puts_setups[:4]:
                render_trade_card(setup, current_price, vix_zone)
        else:
            st.info("No PUTS setups. Cones may be too narrow.")
    
    # Two columns for desktop, stacks on mobile
    col1, col2 = st.columns([1, 1])
    
    with col1:
        render_checklist(cones, current_price, vix_zone)
        render_pivots_panel(high_price, low_price, close_price, prior_date)
    
    with col2:
        render_rails_panel(cones)
        render_legend()
    
    # RTH Table (full width)
    render_rth_table(cones, current_price, session_date)
    
    # Footer
    render_footer()


# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    main()