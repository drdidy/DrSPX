"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                                ║
║                           SPX PROPHET v2.1                                     ║
║                    Where Structure Becomes Foresight                           ║
║                                                                                ║
║                         ★ LEGENDARY EDITION ★                                 ║
║                                                                                ║
║                           Professional Grade •                                 ║
║                                HTML/CSS                                        ║
║                                                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

THE VIX-SPX CONFLUENCE SYSTEM:
==============================
This is NOT just a VIX system - it shows how VIX and SPX work IN TANDEM.
You need BOTH to align for a valid signal.

THE INVERSE RELATIONSHIP:
-------------------------
VIX UP   → SPX DOWN
VIX DOWN → SPX UP

THE CONFLUENCE RULE (Both must happen in same 30-min candle):
-------------------------------------------------------------
1. VIX 30-min CLOSES at zone extreme (resistance or support)
2. SPX touches the corresponding rail

NORMAL DAY SIGNALS:
-------------------
┌─────────────────────┬──────────────────────┬─────────────┐
│ VIX 30-min Close    │ SPX Position         │ Trade       │
├─────────────────────┼──────────────────────┼─────────────┤
│ At RESISTANCE (top) │ At DESCENDING rail   │ CALLS       │
│ At SUPPORT (bottom) │ At ASCENDING rail    │ PUTS        │
└─────────────────────┴──────────────────────┴─────────────┘

Why? On normal days:
- Descending rail = SUPPORT (price bounces UP off falling floor) → CALLS
- Ascending rail = RESISTANCE (price rejected DOWN at rising ceiling) → PUTS

GAP DAY EXCEPTIONS:
-------------------
GAP UP DAY (SPX opens ABOVE High Cone's ascending rail):
- New pivot = Overnight LOW (ES converted to SPX)
- Ascending rail from this low acts as SUPPORT
- SPX pulls back to ascending rail + VIX at resistance → CALLS

GAP DOWN DAY (SPX opens BELOW Low Cone's descending rail):
- New pivot = Overnight HIGH (ES converted to SPX)
- Descending rail from this high acts as RESISTANCE
- SPX rallies to descending rail + VIX at support → PUTS

THE CRITICAL RULE: 
------------------
It's the 30-MINUTE CLOSE that matters on VIX, not the wick!

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

# VIX Zone System
VIX_ZONE_SIZE = 0.15

# Cone Rail Slopes (pts per 30-min block)
SLOPE_ASCENDING = 0.45
SLOPE_DESCENDING = 0.45

# Trading Parameters
MIN_CONE_WIDTH = 18.0
AT_RAIL_THRESHOLD = 8.0
STOP_LOSS_PTS = 6.0
STRIKE_OFFSET = 17.5

# Time filter
POWER_HOUR_START = time(14, 0)

# RTH Time blocks
RTH_TIME_BLOCKS = [
    ("8:30 AM", time(8, 30), True, False),
    ("9:00 AM", time(9, 0), False, False),
    ("9:30 AM", time(9, 30), False, False),
    ("10:00 AM", time(10, 0), False, True),
    ("10:30 AM", time(10, 30), False, False),
    ("11:00 AM", time(11, 0), False, False),
    ("11:30 AM", time(11, 30), False, False),
    ("12:00 PM", time(12, 0), False, False),
    ("12:30 PM", time(12, 30), False, False),
    ("1:00 PM", time(13, 0), False, False),
    ("1:30 PM", time(13, 30), False, False),
    ("2:00 PM", time(14, 0), False, False),
    ("2:30 PM", time(14, 30), False, False),
    ("3:00 PM", time(15, 0), False, False),
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

def get_vix_zone_status(vix_zone: VIXZone) -> Tuple[str, str, str]:
    if vix_zone.current <= 0:
        return "Enter VIX 30-min close", "N/A", "N/A"
    
    current = vix_zone.current
    
    if current > vix_zone.resistance + 0.02:
        zones_above = (current - vix_zone.resistance) / VIX_ZONE_SIZE
        target_zone = min(int(zones_above) + 1, 4)
        return (
            f"BREAKOUT UP → PUTS extend",
            f"Target: {vix_zone.levels_above[target_zone-1]:.2f}",
            "Hold PUTS"
        )
    
    if current < vix_zone.support - 0.02:
        zones_below = (vix_zone.support - current) / VIX_ZONE_SIZE
        target_zone = min(int(zones_below) + 1, 4)
        return (
            f"BREAKDOWN → CALLS extend",
            f"Target: {vix_zone.levels_below[target_zone-1]:.2f}",
            "Hold CALLS"
        )
    
    if vix_zone.position_pct >= 80:
        return (
            "VIX at RESISTANCE → CALLS",
            "VIX will drop → SPX rises",
            "Enter at descending rail"
        )
    elif vix_zone.position_pct <= 20:
        return (
            "VIX at SUPPORT → PUTS",
            "VIX will rise → SPX drops",
            "Enter at ascending rail"
        )
    else:
        return (
            "VIX MID-ZONE → WAIT",
            "No clear signal",
            "Wait for extremes"
        )

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
        return False, "Enter VIX data"
    
    distance_to_entry = abs(spx_price - trade_setup.entry_price)
    spx_at_rail = distance_to_entry <= AT_RAIL_THRESHOLD
    
    if not spx_at_rail:
        return False, f"SPX {distance_to_entry:.1f} pts away"
    
    if trade_setup.direction == 'CALLS':
        vix_aligned = vix_zone.trade_bias == 'CALLS'
        if not vix_aligned:
            return False, f"VIX at {vix_zone.position_pct:.0f}%"
    else:
        vix_aligned = vix_zone.trade_bias == 'PUTS'
        if not vix_aligned:
            return False, f"VIX at {vix_zone.position_pct:.0f}%"
    
    return True, "CONFLUENCE ✓"


# ============================================================================
# ============================================================================
#
#                        PART 2: PREMIUM CSS STYLES
#
#                        ★ LIGHT THEME EDITION ★
#
#                            • Professional • 
#                   
#
# ============================================================================
# ============================================================================

def inject_premium_css():
    """
    Inject premium LIGHT THEME CSS styles.
    Professional, clean, institutional-grade design.
    """
    
    st.markdown(
        """
        <style>
        /* ================================================================
           GLOBAL STYLES & BACKGROUND
           ================================================================ */
        
        .stApp {
            background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%);
        }
        
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f1f5f9 100%);
            border-right: 2px solid #e2e8f0;
        }
        
        section[data-testid="stSidebar"] .stMarkdown {
            color: #1e293b;
        }
        
        /* ================================================================
           CUSTOM SCROLLBAR
           ================================================================ */
        
        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        
        ::-webkit-scrollbar-track {
            background: #f1f5f9;
            border-radius: 5px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #94a3b8 0%, #64748b 100%);
            border-radius: 5px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(180deg, #64748b 0%, #475569 100%);
        }
        
        /* ================================================================
           HEADER STYLES
           ================================================================ */
        
        .prophet-header {
            background: linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #0ea5e9 100%);
            border-radius: 24px;
            padding: 48px;
            margin-bottom: 32px;
            text-align: center;
            box-shadow: 0 20px 40px rgba(30, 64, 175, 0.25),
                        0 8px 16px rgba(30, 64, 175, 0.15);
            position: relative;
            overflow: hidden;
        }
        
        .prophet-header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(45deg, transparent 40%, rgba(255,255,255,0.15) 50%, transparent 60%);
            animation: shimmer 3s infinite;
        }
        
        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        
        .prophet-title {
            font-size: 3.5rem;
            font-weight: 900;
            color: white;
            margin: 0;
            letter-spacing: 10px;
            text-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            position: relative;
            z-index: 1;
        }
        
        .prophet-subtitle {
            color: rgba(255, 255, 255, 0.95);
            font-size: 1.1rem;
            letter-spacing: 6px;
            margin-top: 16px;
            font-weight: 500;
            text-transform: uppercase;
            position: relative;
            z-index: 1;
        }
        
        .prophet-badge {
            display: inline-block;
            background: rgba(255, 255, 255, 0.25);
            padding: 8px 20px;
            border-radius: 25px;
            font-size: 0.8rem;
            letter-spacing: 3px;
            margin-top: 20px;
            color: white;
            font-weight: 600;
            position: relative;
            z-index: 1;
        }
        
        /* ================================================================
           METRIC CARDS
           ================================================================ */
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 24px;
            margin-bottom: 32px;
        }
        
        .metric-card {
            background: white;
            border-radius: 20px;
            padding: 28px;
            text-align: center;
            border: 1px solid #e2e8f0;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04),
                        0 1px 3px rgba(0, 0, 0, 0.06);
            transition: all 0.3s ease;
        }
        
        .metric-card:hover {
            transform: translateY(-6px);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08),
                        0 4px 8px rgba(0, 0, 0, 0.06);
            border-color: #3b82f6;
        }
        
        .metric-icon {
            font-size: 1.5rem;
            margin-bottom: 12px;
        }
        
        .metric-value {
            font-size: 2.2rem;
            font-weight: 800;
            font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
            margin-bottom: 6px;
            color: #1e293b;
        }
        
        .metric-value-green { color: #16a34a; }
        .metric-value-red { color: #dc2626; }
        .metric-value-blue { color: #2563eb; }
        .metric-value-yellow { color: #ca8a04; }
        
        .metric-label {
            font-size: 0.8rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 700;
        }
        
        .metric-delta {
            font-size: 0.85rem;
            margin-top: 10px;
            padding: 6px 14px;
            border-radius: 20px;
            display: inline-block;
            font-weight: 600;
        }
        
        .metric-delta-positive {
            background: #dcfce7;
            color: #16a34a;
            border: 1px solid #86efac;
        }
        
        .metric-delta-negative {
            background: #fee2e2;
            color: #dc2626;
            border: 1px solid #fca5a5;
        }
        
        .metric-delta-neutral {
            background: #fef9c3;
            color: #ca8a04;
            border: 1px solid #fde047;
        }
        
        /* ================================================================
           PANEL STYLES
           ================================================================ */
        
        .glass-panel {
            background: white;
            border-radius: 24px;
            padding: 32px;
            margin-bottom: 28px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04),
                        0 1px 3px rgba(0, 0, 0, 0.06);
        }
        
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 28px;
            padding-bottom: 20px;
            border-bottom: 2px solid #f1f5f9;
        }
        
        .panel-title {
            font-size: 1.35rem;
            font-weight: 800;
            color: #1e293b;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .panel-badge {
            padding: 8px 18px;
            border-radius: 25px;
            font-size: 0.9rem;
            font-weight: 700;
            letter-spacing: 1px;
        }
        
        .badge-calls {
            background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
            color: white;
            box-shadow: 0 4px 12px rgba(34, 197, 94, 0.35);
        }
        
        .badge-puts {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.35);
        }
        
        .badge-neutral {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
            box-shadow: 0 4px 12px rgba(245, 158, 11, 0.35);
        }
        
        /* ================================================================
           VIX ZONE LADDER
           ================================================================ */
        
        .zone-ladder {
            background: #f8fafc;
            border-radius: 16px;
            padding: 20px;
            margin-top: 20px;
            border: 1px solid #e2e8f0;
        }
        
        .zone-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 20px;
            margin: 8px 0;
            border-radius: 12px;
            font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
            font-size: 0.95rem;
            transition: all 0.2s ease;
        }
        
        .zone-row:hover {
            transform: translateX(6px);
        }
        
        .zone-extend-up {
            background: linear-gradient(90deg, #fee2e2 0%, #fff 100%);
            border-left: 5px solid #f87171;
        }
        
        .zone-extend-down {
            background: linear-gradient(90deg, #dcfce7 0%, #fff 100%);
            border-left: 5px solid #4ade80;
        }
        
        .zone-resistance {
            background: linear-gradient(90deg, #fecaca 0%, #fee2e2 100%);
            border: 2px solid #ef4444;
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.15);
        }
        
        .zone-support {
            background: linear-gradient(90deg, #bbf7d0 0%, #dcfce7 100%);
            border: 2px solid #22c55e;
            box-shadow: 0 4px 12px rgba(34, 197, 94, 0.15);
        }
        
        .zone-current {
            background: linear-gradient(90deg, #bfdbfe 0%, #dbeafe 100%);
            border: 2px solid #3b82f6;
            box-shadow: 0 4px 16px rgba(59, 130, 246, 0.2);
            animation: pulse-current 2s infinite;
        }
        
        @keyframes pulse-current {
            0%, 100% { box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2); }
            50% { box-shadow: 0 4px 20px rgba(59, 130, 246, 0.35); }
        }
        
        .zone-level-label {
            font-weight: 800;
            min-width: 55px;
            color: #1e293b;
        }
        
        .zone-price {
            font-weight: 700;
            color: #1e293b;
            font-size: 1.05rem;
        }
        
        .zone-action {
            font-size: 0.85rem;
            color: #64748b;
            font-weight: 600;
        }
        
        /* ================================================================
           TRADE CARDS
           ================================================================ */
        
        .trade-card {
            background: white;
            border-radius: 24px;
            padding: 32px;
            margin-bottom: 24px;
            border-left: 6px solid;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04),
                        0 1px 3px rgba(0, 0, 0, 0.06);
            transition: all 0.3s ease;
        }
        
        .trade-card:hover {
            transform: translateX(10px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
        }
        
        .trade-card-calls {
            border-left-color: #22c55e;
        }
        
        .trade-card-calls:hover {
            box-shadow: 0 8px 24px rgba(34, 197, 94, 0.15);
        }
        
        .trade-card-puts {
            border-left-color: #ef4444;
        }
        
        .trade-card-puts:hover {
            box-shadow: 0 8px 24px rgba(239, 68, 68, 0.15);
        }
        
        .trade-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 28px;
        }
        
        .trade-direction {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .trade-direction-badge {
            padding: 12px 28px;
            border-radius: 30px;
            font-weight: 800;
            font-size: 1.05rem;
            letter-spacing: 2px;
            color: white;
        }
        
        .trade-badge-calls {
            background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
            box-shadow: 0 6px 20px rgba(34, 197, 94, 0.4);
        }
        
        .trade-badge-puts {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4);
        }
        
        .trade-cone-name {
            color: #64748b;
            font-size: 1rem;
            font-weight: 600;
        }
        
        .trade-status {
            padding: 10px 20px;
            border-radius: 25px;
            font-size: 0.9rem;
            font-weight: 700;
        }
        
        .status-at-rail {
            background: #dcfce7;
            color: #16a34a;
            border: 2px solid #86efac;
            animation: pulse-rail 2s infinite;
        }
        
        @keyframes pulse-rail {
            0%, 100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); }
            50% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
        }
        
        .status-waiting {
            background: #f1f5f9;
            color: #64748b;
            border: 1px solid #cbd5e1;
        }
        
        .trade-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 24px;
        }
        
        .trade-stat {
            background: #f8fafc;
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            border: 1px solid #e2e8f0;
        }
        
        .trade-stat-value {
            font-size: 1.4rem;
            font-weight: 800;
            font-family: 'SF Mono', monospace;
            margin-bottom: 6px;
        }
        
        .trade-stat-label {
            font-size: 0.75rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            font-weight: 700;
        }
        
        .stat-entry { color: #2563eb; }
        .stat-target { color: #ca8a04; }
        .stat-stop { color: #dc2626; }
        .stat-strike { color: #7c3aed; }
        
        /* ================================================================
           PROFIT/LOSS ROW
           ================================================================ */
        
        .pnl-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            padding-top: 24px;
            border-top: 2px solid #f1f5f9;
            margin-top: 24px;
        }
        
        .pnl-box {
            border-radius: 16px;
            padding: 22px;
            text-align: center;
        }
        
        .pnl-profit {
            background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
            border: 2px solid #86efac;
        }
        
        .pnl-loss {
            background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
            border: 2px solid #fca5a5;
        }
        
        .pnl-rr {
            background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
            border: 2px solid #93c5fd;
        }
        
        .pnl-value {
            font-size: 1.6rem;
            font-weight: 800;
            font-family: 'SF Mono', monospace;
        }
        
        .pnl-value-green { color: #16a34a; }
        .pnl-value-red { color: #dc2626; }
        .pnl-value-blue { color: #2563eb; }
        
        .pnl-label {
            font-size: 0.75rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-top: 8px;
            font-weight: 700;
        }
        
        /* ================================================================
           CONFLUENCE STATUS
           ================================================================ */
        
        .confluence-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 24px;
            padding-top: 20px;
            border-top: 2px solid #f1f5f9;
        }
        
        .confluence-required {
            color: #64748b;
            font-size: 0.95rem;
            font-weight: 600;
        }
        
        .confluence-status {
            padding: 10px 24px;
            border-radius: 25px;
            font-weight: 700;
            font-size: 0.95rem;
        }
        
        .confluence-active {
            background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(34, 197, 94, 0.4);
        }
        
        .confluence-waiting {
            background: #f1f5f9;
            color: #64748b;
            border: 1px solid #cbd5e1;
        }
        
        /* ================================================================
           CHECKLIST PANEL
           ================================================================ */
        
        .checklist-panel {
            background: white;
            border-radius: 24px;
            padding: 32px;
            margin-bottom: 28px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        }
        
        .checklist-header {
            padding: 24px;
            border-radius: 16px;
            text-align: center;
            margin-bottom: 28px;
        }
        
        .checklist-go {
            background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
            border: 2px solid #22c55e;
        }
        
        .checklist-wait {
            background: linear-gradient(135deg, #fef9c3 0%, #fef08a 100%);
            border: 2px solid #eab308;
        }
        
        .checklist-skip {
            background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
            border: 2px solid #ef4444;
        }
        
        .checklist-title {
            font-size: 1.5rem;
            font-weight: 800;
            color: #1e293b;
            margin-bottom: 6px;
        }
        
        .checklist-subtitle {
            font-size: 0.95rem;
            color: #64748b;
            font-weight: 500;
        }
        
        .check-item {
            display: flex;
            align-items: center;
            padding: 18px 20px;
            margin: 12px 0;
            border-radius: 14px;
            transition: all 0.2s ease;
        }
        
        .check-item:hover {
            transform: translateX(6px);
        }
        
        .check-pass {
            background: linear-gradient(90deg, #dcfce7 0%, #fff 100%);
            border-left: 5px solid #22c55e;
        }
        
        .check-fail {
            background: linear-gradient(90deg, #fee2e2 0%, #fff 100%);
            border-left: 5px solid #ef4444;
        }
        
        .check-icon {
            font-size: 1.5rem;
            width: 40px;
        }
        
        .check-label {
            flex: 1;
            font-weight: 700;
            color: #1e293b;
            margin-left: 14px;
            font-size: 1rem;
        }
        
        .check-detail {
            color: #64748b;
            font-size: 0.9rem;
            font-family: 'SF Mono', monospace;
            font-weight: 600;
        }
        
        /* ================================================================
           DIRECTION BOX
           ================================================================ */
        
        .direction-box {
            text-align: center;
            padding: 28px;
            border-radius: 20px;
            margin-top: 24px;
        }
        
        .direction-calls {
            background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
            border: 2px solid #22c55e;
        }
        
        .direction-puts {
            background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
            border: 2px solid #ef4444;
        }
        
        .direction-label {
            font-size: 0.85rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 10px;
            font-weight: 700;
        }
        
        .direction-value {
            font-size: 2.5rem;
            font-weight: 900;
            letter-spacing: 6px;
        }
        
        .direction-value-green { color: #16a34a; }
        .direction-value-red { color: #dc2626; }
        
        .direction-detail {
            font-size: 0.9rem;
            color: #64748b;
            margin-top: 10px;
            font-weight: 500;
        }
        
        /* ================================================================
           INFO PANELS
           ================================================================ */
        
        .info-panel {
            background: white;
            border-radius: 20px;
            padding: 28px;
            margin-bottom: 24px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        }
        
        .info-title {
            font-size: 0.9rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-bottom: 20px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .info-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 0;
            border-bottom: 1px solid #f1f5f9;
        }
        
        .info-row:last-child {
            border-bottom: none;
        }
        
        .info-label {
            color: #64748b;
            font-weight: 600;
        }
        
        .info-value {
            font-weight: 700;
            font-family: 'SF Mono', monospace;
            color: #1e293b;
            font-size: 1.05rem;
        }
        
        .info-value-red { color: #dc2626; }
        .info-value-green { color: #16a34a; }
        .info-value-yellow { color: #ca8a04; }
        
        /* ================================================================
           RTH TABLE
           ================================================================ */
        
        .rth-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0 8px;
            margin-top: 20px;
        }
        
        .rth-table th {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            padding: 16px 14px;
            text-align: center;
            font-weight: 700;
        }
        
        .rth-table th:first-child {
            border-radius: 12px 0 0 12px;
            text-align: left;
        }
        
        .rth-table th:last-child {
            border-radius: 0 12px 12px 0;
        }
        
        .rth-table td {
            background: white;
            padding: 16px 14px;
            text-align: center;
            font-family: 'SF Mono', monospace;
            font-size: 0.95rem;
            color: #1e293b;
            border-top: 1px solid #e2e8f0;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .rth-table td:first-child {
            border-radius: 12px 0 0 12px;
            border-left: 1px solid #e2e8f0;
            text-align: left;
            font-weight: 700;
        }
        
        .rth-table td:last-child {
            border-radius: 0 12px 12px 0;
            border-right: 1px solid #e2e8f0;
        }
        
        .rth-table tr:hover td {
            background: #f8fafc;
        }
        
        .rth-row-open td {
            background: linear-gradient(90deg, #dbeafe 0%, #eff6ff 100%) !important;
            border-color: #93c5fd !important;
        }
        
        .rth-row-target td {
            background: linear-gradient(90deg, #dcfce7 0%, #f0fdf4 100%) !important;
            border-color: #86efac !important;
        }
        
        .rth-time-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 700;
        }
        
        .rth-badge-open {
            background: #3b82f6;
            color: white;
        }
        
        .rth-badge-target {
            background: #22c55e;
            color: white;
        }
        
        .rth-asc { color: #dc2626; font-weight: 700; }
        .rth-desc { color: #16a34a; font-weight: 700; }
        
        /* ================================================================
           GAP BANNER
           ================================================================ */
        
        .gap-banner {
            border-radius: 20px;
            padding: 24px 32px;
            margin-bottom: 28px;
            display: flex;
            align-items: center;
            gap: 24px;
        }
        
        .gap-up {
            background: linear-gradient(90deg, #dcfce7 0%, #f0fdf4 100%);
            border: 2px solid #86efac;
        }
        
        .gap-down {
            background: linear-gradient(90deg, #fee2e2 0%, #fef2f2 100%);
            border: 2px solid #fca5a5;
        }
        
        .gap-icon {
            font-size: 2.8rem;
        }
        
        .gap-content {
            flex: 1;
        }
        
        .gap-title {
            font-size: 1.2rem;
            font-weight: 800;
            color: #1e293b;
            margin-bottom: 6px;
        }
        
        .gap-detail {
            font-size: 0.95rem;
            color: #64748b;
            font-weight: 500;
        }
        
        .gap-pivot {
            font-family: 'SF Mono', monospace;
            font-weight: 800;
            color: #ca8a04;
        }
        
        /* ================================================================
           SECTION HEADERS
           ================================================================ */
        
        .section-header {
            display: flex;
            align-items: center;
            gap: 16px;
            margin: 36px 0 28px 0;
            padding-bottom: 16px;
            border-bottom: 3px solid #3b82f6;
        }
        
        .section-icon {
            font-size: 1.8rem;
        }
        
        .section-title {
            font-size: 1.4rem;
            font-weight: 800;
            color: #1e293b;
            letter-spacing: 0.5px;
        }
        
        /* ================================================================
           TABS OVERRIDE
           ================================================================ */
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            background: transparent;
        }
        
        .stTabs [data-baseweb="tab"] {
            background: white;
            border-radius: 14px;
            padding: 16px 28px;
            font-weight: 700;
            color: #64748b;
            border: 2px solid #e2e8f0;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            border-color: #3b82f6;
            color: #3b82f6;
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
            border-color: transparent;
            box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
        }
        
        /* ================================================================
           LEGEND PANEL
           ================================================================ */
        
        .legend-item {
            padding: 20px;
            border-radius: 14px;
            margin-bottom: 14px;
            background: #f8fafc;
            border-left: 5px solid;
        }
        
        .legend-calls { border-left-color: #22c55e; }
        .legend-puts { border-left-color: #ef4444; }
        .legend-breakout { border-left-color: #f59e0b; }
        
        .legend-title {
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 10px;
            font-size: 1rem;
        }
        
        .legend-text {
            font-size: 0.9rem;
            color: #64748b;
            line-height: 1.7;
        }
        
        /* ================================================================
           FOOTER
           ================================================================ */
        
        .footer {
            text-align: center;
            padding: 28px;
            margin-top: 48px;
            border-top: 2px solid #e2e8f0;
            color: #64748b;
            font-size: 0.9rem;
        }
        
        .footer-brand {
            font-weight: 800;
            color: #3b82f6;
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
#                   Beautiful • Functional • Professional
#                   Every HTML properly formed and closed
#
# ============================================================================
# ============================================================================

# ============================================================================
# HEADER COMPONENT
# ============================================================================

def render_header():
    """Render the stunning header with title and subtitle."""
    
    st.markdown(
        """
        <div class="prophet-header">
            <div class="prophet-title">SPX PROPHET</div>
            <div class="prophet-subtitle">Where Structure Becomes Foresight</div>
            <div class="prophet-badge">★ LEGENDARY EDITION v2.1 ★</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# METRICS ROW
# ============================================================================

def render_metrics_row(current_price: float, vix_zone: Optional[VIXZone],
                       nearest_distance: float, cone_width: float):
    """Render the 4-card metrics row."""
    
    # SPX Price
    spx_html = f"""
        <div class="metric-card">
            <div class="metric-icon">💹</div>
            <div class="metric-value metric-value-blue">{current_price:,.2f}</div>
            <div class="metric-label">SPX Price</div>
        </div>
    """
    
    # VIX Status
    if vix_zone and vix_zone.current > 0:
        if vix_zone.trade_bias == "CALLS":
            vix_color = "metric-value-green"
            vix_delta_class = "metric-delta-positive"
            vix_delta_text = "🟢 CALLS"
        elif vix_zone.trade_bias == "PUTS":
            vix_color = "metric-value-red"
            vix_delta_class = "metric-delta-negative"
            vix_delta_text = "🔴 PUTS"
        else:
            vix_color = "metric-value-yellow"
            vix_delta_class = "metric-delta-neutral"
            vix_delta_text = "🟡 WAIT"
        
        vix_html = f"""
            <div class="metric-card">
                <div class="metric-icon">📊</div>
                <div class="metric-value {vix_color}">{vix_zone.current:.2f}</div>
                <div class="metric-label">VIX 30m Close</div>
                <div class="metric-delta {vix_delta_class}">{vix_delta_text} ({vix_zone.position_pct:.0f}%)</div>
            </div>
        """
    else:
        vix_html = """
            <div class="metric-card">
                <div class="metric-icon">📊</div>
                <div class="metric-value">—</div>
                <div class="metric-label">VIX 30m Close</div>
                <div class="metric-delta metric-delta-neutral">Enter Data</div>
            </div>
        """
    
    # Distance to Rail
    if nearest_distance <= AT_RAIL_THRESHOLD:
        dist_color = "metric-value-green"
        dist_delta_class = "metric-delta-positive"
        dist_delta_text = "🎯 AT RAIL"
    elif nearest_distance <= AT_RAIL_THRESHOLD * 2:
        dist_color = "metric-value-yellow"
        dist_delta_class = "metric-delta-neutral"
        dist_delta_text = "⏳ Close"
    else:
        dist_color = "metric-value"
        dist_delta_class = "metric-delta-neutral"
        dist_delta_text = "Waiting"
    
    dist_html = f"""
        <div class="metric-card">
            <div class="metric-icon">📍</div>
            <div class="metric-value {dist_color}">{nearest_distance:.1f}</div>
            <div class="metric-label">Pts to Rail</div>
            <div class="metric-delta {dist_delta_class}">{dist_delta_text}</div>
        </div>
    """
    
    # Cone Width
    if cone_width >= 25:
        width_color = "metric-value-green"
        width_delta_class = "metric-delta-positive"
        width_delta_text = "✅ Wide"
    elif cone_width >= MIN_CONE_WIDTH:
        width_color = "metric-value-yellow"
        width_delta_class = "metric-delta-neutral"
        width_delta_text = "⚠️ OK"
    else:
        width_color = "metric-value-red"
        width_delta_class = "metric-delta-negative"
        width_delta_text = "❌ Narrow"
    
    width_html = f"""
        <div class="metric-card">
            <div class="metric-icon">📐</div>
            <div class="metric-value {width_color}">{cone_width:.0f}</div>
            <div class="metric-label">Cone Width</div>
            <div class="metric-delta {width_delta_class}">{width_delta_text}</div>
        </div>
    """
    
    # Combine all metrics
    st.markdown(
        f"""
        <div class="metrics-grid">
            {spx_html}
            {vix_html}
            {dist_html}
            {width_html}
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# GAP BANNER
# ============================================================================

def render_gap_banner(gap_analysis: GapAnalysis):
    """Render gap day alert banner."""
    
    if gap_analysis.gap_type == 'NORMAL':
        return
    
    if gap_analysis.gap_type == 'GAP_UP':
        st.markdown(
            f"""
            <div class="gap-banner gap-up">
                <div class="gap-icon">🚀</div>
                <div class="gap-content">
                    <div class="gap-title">GAP UP DAY — Ascending Rail = Support</div>
                    <div class="gap-detail">
                        Overnight Low pivot: <span class="gap-pivot">{gap_analysis.overnight_pivot:.2f}</span> SPX
                        — CALLS entry at ascending rail when VIX at resistance
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            <div class="gap-banner gap-down">
                <div class="gap-icon">📉</div>
                <div class="gap-content">
                    <div class="gap-title">GAP DOWN DAY — Descending Rail = Resistance</div>
                    <div class="gap-detail">
                        Overnight High pivot: <span class="gap-pivot">{gap_analysis.overnight_pivot:.2f}</span> SPX
                        — PUTS entry at descending rail when VIX at support
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# ============================================================================
# VIX ZONE PANEL
# ============================================================================

def render_vix_zone_panel(vix_zone: VIXZone):
    """Render the VIX Zone panel with ladder."""
    
    status, detail1, detail2 = get_vix_zone_status(vix_zone)
    
    # Badge class
    if vix_zone.trade_bias == "CALLS":
        badge_class = "badge-calls"
    elif vix_zone.trade_bias == "PUTS":
        badge_class = "badge-puts"
    else:
        badge_class = "badge-neutral"
    
    # Build ladder rows
    ladder_rows = ""
    
    # Levels above (reverse order - +4 at top)
    for i in range(3, -1, -1):
        ladder_rows += f"""
            <div class="zone-row zone-extend-up">
                <span class="zone-level-label" style="color: #dc2626;">+{i+1}</span>
                <span class="zone-price">{vix_zone.levels_above[i]:.2f}</span>
                <span class="zone-action">🔴 PUTS extend</span>
            </div>
        """
    
    # Resistance
    ladder_rows += f"""
        <div class="zone-row zone-resistance">
            <span class="zone-level-label" style="color: #dc2626;">⭐ RES</span>
            <span class="zone-price">{vix_zone.resistance:.2f}</span>
            <span class="zone-action" style="color: #16a34a; font-weight: 700;">🟢 CALLS Entry</span>
        </div>
    """
    
    # Current (if within range)
    if vix_zone.support - 0.10 <= vix_zone.current <= vix_zone.resistance + 0.10:
        ladder_rows += f"""
            <div class="zone-row zone-current">
                <span class="zone-level-label" style="color: #2563eb;">➤ NOW</span>
                <span class="zone-price">{vix_zone.current:.2f}</span>
                <span class="zone-action" style="color: #2563eb; font-weight: 700;">{vix_zone.position_pct:.0f}% in zone</span>
            </div>
        """
    
    # Support
    ladder_rows += f"""
        <div class="zone-row zone-support">
            <span class="zone-level-label" style="color: #16a34a;">⭐ SUP</span>
            <span class="zone-price">{vix_zone.support:.2f}</span>
            <span class="zone-action" style="color: #dc2626; font-weight: 700;">🔴 PUTS Entry</span>
        </div>
    """
    
    # Levels below
    for i in range(4):
        ladder_rows += f"""
            <div class="zone-row zone-extend-down">
                <span class="zone-level-label" style="color: #16a34a;">-{i+1}</span>
                <span class="zone-price">{vix_zone.levels_below[i]:.2f}</span>
                <span class="zone-action">🟢 CALLS extend</span>
            </div>
        """
    
    st.markdown(
        f"""
        <div class="glass-panel">
            <div class="panel-header">
                <div class="panel-title">🧭 VIX Trade Compass</div>
                <div class="panel-badge {badge_class}">{vix_zone.trade_bias}</div>
            </div>
            <div style="background: #f8fafc; border-radius: 12px; padding: 16px; margin-bottom: 20px; border: 1px solid #e2e8f0;">
                <div style="font-weight: 700; color: #1e293b; font-size: 1.1rem; margin-bottom: 6px;">{status}</div>
                <div style="color: #64748b; font-size: 0.9rem;">{detail1}</div>
                <div style="color: #64748b; font-size: 0.9rem;">{detail2}</div>
            </div>
            <div class="zone-ladder">
                {ladder_rows}
            </div>
            <div style="margin-top: 20px; padding: 12px 16px; background: #f1f5f9; border-radius: 10px; text-align: center;">
                <span style="color: #64748b; font-size: 0.85rem;">Zone Size: </span>
                <span style="color: #1e293b; font-weight: 700; font-family: monospace;">{vix_zone.zone_size:.2f}</span>
                <span style="color: #64748b; font-size: 0.85rem;"> | 80%+ = CALLS | 20%- = PUTS</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# TRADE CARD
# ============================================================================

def render_trade_card(setup: TradeSetup, current_price: float, vix_zone: Optional[VIXZone]):
    """Render a single trade setup card."""
    
    distance = abs(current_price - setup.entry_price)
    is_near = distance <= AT_RAIL_THRESHOLD
    
    # Card classes
    if setup.direction == "CALLS":
        card_class = "trade-card-calls"
        badge_class = "trade-badge-calls"
    else:
        card_class = "trade-card-puts"
        badge_class = "trade-badge-puts"
    
    # Status
    if is_near:
        status_class = "status-at-rail"
        status_text = f"🎯 AT RAIL ({distance:.1f} pts)"
    else:
        status_class = "status-waiting"
        status_text = f"⏳ {distance:.1f} pts away"
    
    # Confluence check
    confluence_ok = False
    confluence_text = "Enter VIX"
    if vix_zone and vix_zone.current > 0:
        confluence_ok, confluence_text = check_confluence(setup, vix_zone, current_price)
    
    confluence_class = "confluence-active" if confluence_ok else "confluence-waiting"
    
    st.markdown(
        f"""
        <div class="trade-card {card_class}">
            <div class="trade-header">
                <div class="trade-direction">
                    <span class="trade-direction-badge {badge_class}">{setup.direction}</span>
                    <span class="trade-cone-name">{setup.cone_name} Cone • {setup.rail_type.upper()} Rail</span>
                </div>
                <div class="trade-status {status_class}">{status_text}</div>
            </div>
            
            <div class="trade-grid">
                <div class="trade-stat">
                    <div class="trade-stat-value stat-entry">{setup.entry_price:.2f}</div>
                    <div class="trade-stat-label">Entry</div>
                </div>
                <div class="trade-stat">
                    <div class="trade-stat-value stat-target">{setup.target_price:.2f}</div>
                    <div class="trade-stat-label">Target</div>
                </div>
                <div class="trade-stat">
                    <div class="trade-stat-value stat-stop">{setup.stop_price:.2f}</div>
                    <div class="trade-stat-label">Stop</div>
                </div>
                <div class="trade-stat">
                    <div class="trade-stat-value stat-strike">{setup.strike:.0f}</div>
                    <div class="trade-stat-label">Strike (Δ{setup.delta:.2f})</div>
                </div>
            </div>
            
            <div class="pnl-row">
                <div class="pnl-box pnl-profit">
                    <div class="pnl-value pnl-value-green">+${setup.expected_profit:.0f}</div>
                    <div class="pnl-label">Expected Profit</div>
                </div>
                <div class="pnl-box pnl-loss">
                    <div class="pnl-value pnl-value-red">-${setup.max_loss:.0f}</div>
                    <div class="pnl-label">Max Loss</div>
                </div>
                <div class="pnl-box pnl-rr">
                    <div class="pnl-value pnl-value-blue">{setup.rr_ratio:.1f}:1</div>
                    <div class="pnl-label">Risk:Reward</div>
                </div>
            </div>
            
            <div class="confluence-row">
                <div class="confluence-required">Required: <strong>{setup.vix_condition}</strong></div>
                <div class="confluence-status {confluence_class}">{confluence_text}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# CHECKLIST
# ============================================================================

def render_checklist(cones: List[Cone], current_price: float, vix_zone: Optional[VIXZone]):
    """Render the 4-point trade checklist."""
    
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    cone_width = abs(nearest_cone.ascending_rail - nearest_cone.descending_rail) if nearest_cone else 0
    
    # Expected direction
    if nearest_rail_type == 'descending':
        expected_direction = 'CALLS'
        expected_vix = 'CALLS'
    else:
        expected_direction = 'PUTS'
        expected_vix = 'PUTS'
    
    checks = []
    
    # Check 1: At Rail
    at_rail_ok = nearest_distance <= AT_RAIL_THRESHOLD
    checks.append(("At Rail (≤8 pts)", at_rail_ok, f"{nearest_distance:.1f} pts"))
    
    # Check 2: Structure
    structure_ok = cone_width >= MIN_CONE_WIDTH
    checks.append(("Structure (≥18 pts)", structure_ok, f"{cone_width:.0f} pts"))
    
    # Check 3: Active Cone
    cone_ok = nearest_cone is not None
    cone_detail = f"{nearest_cone.name}" if nearest_cone else "None"
    checks.append(("Active Cone", cone_ok, cone_detail))
    
    # Check 4: VIX Confluence
    if vix_zone and vix_zone.current > 0:
        vix_ok = vix_zone.trade_bias == expected_vix
        vix_detail = f"{vix_zone.trade_bias} ({vix_zone.position_pct:.0f}%)"
    else:
        vix_ok = False
        vix_detail = "Enter data"
    checks.append((f"VIX Confluence ({expected_vix})", vix_ok, vix_detail))
    
    # Count passed
    passed = sum(1 for _, ok, _ in checks if ok)
    
    # Header status
    if passed == 4:
        header_class = "checklist-go"
        header_title = "🟢 CONFLUENCE — GO!"
        header_sub = "All conditions met"
    elif passed >= 3 and at_rail_ok:
        header_class = "checklist-go"
        header_title = "🟢 STRONG SETUP"
        header_sub = "Good to trade with caution"
    elif not at_rail_ok:
        header_class = "checklist-wait"
        header_title = "🟡 WAIT — Not at Rail"
        header_sub = "Wait for price to reach rail"
    elif not structure_ok:
        header_class = "checklist-skip"
        header_title = "🔴 SKIP — Bad Structure"
        header_sub = "Cone too narrow"
    else:
        header_class = "checklist-wait"
        header_title = "🟡 CAUTION"
        header_sub = "Check conditions"
    
    # Build check items
    check_items = ""
    for label, ok, detail in checks:
        item_class = "check-pass" if ok else "check-fail"
        icon = "✅" if ok else "❌"
        check_items += f"""
            <div class="check-item {item_class}">
                <span class="check-icon">{icon}</span>
                <span class="check-label">{label}</span>
                <span class="check-detail">{detail}</span>
            </div>
        """
    
    # Direction box
    if expected_direction == "CALLS":
        dir_class = "direction-calls"
        dir_value_class = "direction-value-green"
    else:
        dir_class = "direction-puts"
        dir_value_class = "direction-value-red"
    
    st.markdown(
        f"""
        <div class="checklist-panel">
            <div class="checklist-header {header_class}">
                <div class="checklist-title">{header_title}</div>
                <div class="checklist-subtitle">{passed}/4 checks passed — {header_sub}</div>
            </div>
            
            {check_items}
            
            <div class="direction-box {dir_class}">
                <div class="direction-label">Trade Direction</div>
                <div class="direction-value {dir_value_class}">{expected_direction}</div>
                <div class="direction-detail">{nearest_cone.name if nearest_cone else 'N/A'} cone • {nearest_rail_type} rail</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# RTH SESSION TABLE
# ============================================================================

def render_rth_table(cones: List[Cone], current_price: float, session_date):
    """Render the RTH session rails table with highlighted 8:30 and 10:00."""
    
    # Build header
    header_cols = "<th>Time</th>"
    for cone in cones:
        header_cols += f"<th>{cone.name} ▲</th><th>{cone.name} ▼</th>"
    
    # Build rows
    rows_html = ""
    ct_now = get_ct_now()
    
    for time_label, time_val, is_open, is_target in RTH_TIME_BLOCKS:
        target_dt = ct_now.replace(hour=time_val.hour, minute=time_val.minute, second=0, microsecond=0)
        
        # Row class
        if is_open:
            row_class = "rth-row-open"
            time_display = f'<span class="rth-time-badge rth-badge-open">{time_label}</span>'
        elif is_target:
            row_class = "rth-row-target"
            time_display = f'<span class="rth-time-badge rth-badge-target">{time_label}</span>'
        else:
            row_class = ""
            time_display = time_label
        
        # Build cells
        cells = f"<td>{time_display}</td>"
        
        for cone in cones:
            asc_price = calculate_rail_price(cone.pivot.price, cone.pivot.time, target_dt, True)
            desc_price = calculate_rail_price(cone.pivot.price, cone.pivot.time, target_dt, False)
            
            # Highlight if near current price
            asc_near = abs(current_price - asc_price) <= AT_RAIL_THRESHOLD
            desc_near = abs(current_price - desc_price) <= AT_RAIL_THRESHOLD
            
            asc_style = "font-weight: 800; background: #fee2e2; border-radius: 6px; padding: 4px 8px;" if asc_near else ""
            desc_style = "font-weight: 800; background: #dcfce7; border-radius: 6px; padding: 4px 8px;" if desc_near else ""
            
            cells += f'<td><span class="rth-asc" style="{asc_style}">{asc_price:.2f}</span></td>'
            cells += f'<td><span class="rth-desc" style="{desc_style}">{desc_price:.2f}</span></td>'
        
        rows_html += f'<tr class="{row_class}">{cells}</tr>'
    
    st.markdown(
        f"""
        <div class="glass-panel">
            <div class="panel-title" style="margin-bottom: 20px;">📊 RTH Session Rails</div>
            <div style="display: flex; gap: 20px; margin-bottom: 16px; flex-wrap: wrap;">
                <div><span class="rth-time-badge rth-badge-open">8:30 AM</span> Market Open</div>
                <div><span class="rth-time-badge rth-badge-target">10:00 AM</span> Primary Target</div>
                <div><span class="rth-asc">▲ ASC</span> = PUTS (resistance)</div>
                <div><span class="rth-desc">▼ DESC</span> = CALLS (support)</div>
            </div>
            <table class="rth-table">
                <thead>
                    <tr>{header_cols}</tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# PIVOTS PANEL
# ============================================================================

def render_pivots_panel(high_price: float, low_price: float, close_price: float, prior_date):
    """Render prior session pivots."""
    
    date_str = prior_date.strftime('%b %d, %Y') if hasattr(prior_date, 'strftime') else str(prior_date)
    
    st.markdown(
        f"""
        <div class="info-panel">
            <div class="info-title">📍 Prior Session Pivots</div>
            <div style="color: #64748b; font-size: 0.85rem; margin-bottom: 16px;">Session: {date_str}</div>
            <div class="info-row">
                <span class="info-label">🔴 High (Wick)</span>
                <span class="info-value info-value-red">{high_price:.2f}</span>
            </div>
            <div class="info-row">
                <span class="info-label">🟢 Low (Close)</span>
                <span class="info-value info-value-green">{low_price:.2f}</span>
            </div>
            <div class="info-row">
                <span class="info-label">🟡 Close</span>
                <span class="info-value info-value-yellow">{close_price:.2f}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# 10AM RAILS PANEL
# ============================================================================

def render_rails_panel(cones: List[Cone]):
    """Render 10:00 AM rail prices."""
    
    rows_html = ""
    for cone in cones:
        rows_html += f"""
            <div class="info-row">
                <span class="info-label">{cone.name}</span>
                <span style="display: flex; gap: 20px;">
                    <span><span class="rth-asc">▲</span> <span class="info-value">{cone.ascending_rail:.2f}</span></span>
                    <span><span class="rth-desc">▼</span> <span class="info-value">{cone.descending_rail:.2f}</span></span>
                </span>
            </div>
        """
    
    st.markdown(
        f"""
        <div class="info-panel">
            <div class="info-title">📐 10:00 AM Rail Prices</div>
            <div style="color: #64748b; font-size: 0.85rem; margin-bottom: 16px;">
                ▲ ASC = PUTS entry (resistance) | ▼ DESC = CALLS entry (support)
            </div>
            {rows_html}
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# LEGEND PANEL
# ============================================================================

def render_legend():
    """Render the VIX-SPX confluence rules legend."""
    
    st.markdown(
        """
        <div class="info-panel">
            <div class="info-title">📚 VIX-SPX Confluence Rules</div>
            
            <div class="legend-item legend-calls">
                <div class="legend-title">🟢 CALLS Entry</div>
                <div class="legend-text">
                    VIX 30m closes at <strong>RESISTANCE</strong> (80%+)<br>
                    + SPX at <strong>DESCENDING</strong> rail (support)<br>
                    → VIX drops → SPX rises
                </div>
            </div>
            
            <div class="legend-item legend-puts">
                <div class="legend-title">🔴 PUTS Entry</div>
                <div class="legend-text">
                    VIX 30m closes at <strong>SUPPORT</strong> (≤20%)<br>
                    + SPX at <strong>ASCENDING</strong> rail (resistance)<br>
                    → VIX rises → SPX drops
                </div>
            </div>
            
            <div class="legend-item legend-breakout">
                <div class="legend-title">⚠️ Breakouts</div>
                <div class="legend-text">
                    VIX breaks <strong>ABOVE</strong> resistance → PUTS targets extend (+0.15/zone)<br>
                    VIX breaks <strong>BELOW</strong> support → CALLS targets extend (-0.15/zone)
                </div>
            </div>
            
            <div style="margin-top: 16px; padding: 14px; background: #fef9c3; border-radius: 10px; border: 1px solid #fde047;">
                <div style="color: #92400e; font-weight: 700; margin-bottom: 6px;">⏰ Critical Rule</div>
                <div style="color: #78350f; font-size: 0.9rem;">
                    It's the 30-minute <strong>CLOSE</strong> that matters, not the wick!
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# SECTION HEADER
# ============================================================================

def render_section_header(icon: str, title: str):
    """Render a section header."""
    
    st.markdown(
        f"""
        <div class="section-header">
            <span class="section-icon">{icon}</span>
            <span class="section-title">{title}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# FOOTER
# ============================================================================

def render_footer():
    """Render the footer."""
    
    ct_now = get_ct_now()
    
    st.markdown(
        f"""
        <div class="footer">
            <span class="footer-brand">SPX PROPHET v2.1</span> — Where Structure Becomes Foresight<br>
            <span style="font-size: 0.8rem;">Last updated: {ct_now.strftime('%I:%M:%S %p CT')} | Remember: 30-min CLOSE is everything! 🎯</span>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================================
# SIDEBAR COMPONENTS
# ============================================================================

def render_sidebar_status(vix_zone: Optional[VIXZone], nearest_distance: float,
                          nearest_rail_type: str, cone_width: float):
    """Render status summary in sidebar."""
    
    # VIX Status
    if vix_zone and vix_zone.current > 0:
        if vix_zone.trade_bias == "CALLS":
            vix_status = f"🟢 CALLS ({vix_zone.position_pct:.0f}%)"
            vix_bg = "#dcfce7"
            vix_border = "#86efac"
        elif vix_zone.trade_bias == "PUTS":
            vix_status = f"🔴 PUTS ({vix_zone.position_pct:.0f}%)"
            vix_bg = "#fee2e2"
            vix_border = "#fca5a5"
        else:
            vix_status = f"🟡 WAIT ({vix_zone.position_pct:.0f}%)"
            vix_bg = "#fef9c3"
            vix_border = "#fde047"
    else:
        vix_status = "⚪ Enter Data"
        vix_bg = "#f1f5f9"
        vix_border = "#e2e8f0"
    
    # Rail Status
    if nearest_distance <= AT_RAIL_THRESHOLD:
        rail_status = f"🎯 AT RAIL ({nearest_distance:.1f})"
        rail_bg = "#dcfce7"
        rail_border = "#86efac"
    else:
        rail_status = f"⏳ {nearest_distance:.1f} pts"
        rail_bg = "#f1f5f9"
        rail_border = "#e2e8f0"
    
    # Direction
    expected_dir = "CALLS" if nearest_rail_type == 'descending' else "PUTS"
    if expected_dir == "CALLS":
        dir_bg = "#dcfce7"
        dir_border = "#86efac"
    else:
        dir_bg = "#fee2e2"
        dir_border = "#fca5a5"
    
    st.markdown(
        f"""
        <div style="background: white; border-radius: 12px; padding: 16px; margin-bottom: 16px; border: 1px solid #e2e8f0;">
            <div style="font-weight: 700; color: #1e293b; margin-bottom: 12px; font-size: 0.9rem;">📡 LIVE STATUS</div>
            <div style="background: {vix_bg}; border: 1px solid {vix_border}; border-radius: 8px; padding: 10px; margin-bottom: 8px; text-align: center; font-weight: 600; color: #1e293b;">
                VIX: {vix_status}
            </div>
            <div style="background: {rail_bg}; border: 1px solid {rail_border}; border-radius: 8px; padding: 10px; margin-bottom: 8px; text-align: center; font-weight: 600; color: #1e293b;">
                Rail: {rail_status}
            </div>
            <div style="background: {dir_bg}; border: 1px solid {dir_border}; border-radius: 8px; padding: 10px; text-align: center; font-weight: 700; color: #1e293b; font-size: 1.1rem;">
                → {expected_dir}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================================
# ============================================================================
#
#                        PART 4: MAIN APPLICATION
#
#                   The Final Piece — Everything Connected
#                   Sidebar • Main Layout • Full Integration
#
# ============================================================================
# ============================================================================

def main():
    """Main application entry point."""
    
    # ========================================================================
    # PAGE CONFIGURATION
    # ========================================================================
    st.set_page_config(
        page_title="SPX Prophet v2.1 | Legendary Edition",
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
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        
        st.markdown(
            """
            <div style="text-align: center; padding: 10px 0 20px 0;">
                <div style="font-size: 1.5rem; font-weight: 800; color: #1e293b;">⚙️ CONTROL PANEL</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # ====================================================================
        # SESSION DATE
        # ====================================================================
        st.markdown("### 📅 Session Date")
        
        session_date = st.date_input(
            "Trading Date",
            value=get_ct_now().date(),
            help="Select the trading session date"
        )
        
        session_date_dt = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        
        ct_now = get_ct_now()
        st.info(f"🕐 **{ct_now.strftime('%I:%M %p CT')}** | {ct_now.strftime('%A, %b %d')}")
        
        st.markdown("---")
        
        # ====================================================================
        # VIX ZONE INPUT
        # ====================================================================
        st.markdown("### 🧭 VIX Zone Setup")
        st.caption("From overnight session (5pm-2am CT)")
        
        st.warning("⚠️ **Use 30-min CLOSE prices, NOT wicks!**")
        
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
            help="Overnight low CLOSE — PUTS entry when VIX closes here"
        )
        st.session_state.vix_support = vix_support
        
        vix_resistance = st.number_input(
            "VIX Resistance (Zone Top)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_resistance,
            step=0.01,
            format="%.2f",
            help="Overnight high CLOSE — CALLS entry when VIX closes here"
        )
        st.session_state.vix_resistance = vix_resistance
        
        vix_current = st.number_input(
            "Current VIX (30m Close)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_current,
            step=0.01,
            format="%.2f",
            help="Latest 30-min candle CLOSE from TradingView (VX1!)"
        )
        st.session_state.vix_current = vix_current
        
        # Calculate VIX zone
        vix_zone = None
        if vix_support > 0 and vix_resistance > 0:
            vix_zone = calculate_vix_zones(vix_support, vix_resistance, vix_current)
            
            zone_size = vix_resistance - vix_support
            if 0.13 <= zone_size <= 0.17:
                st.success(f"✅ Valid 1-zone: **{zone_size:.2f}**")
            elif zone_size > 0:
                num_zones = round(zone_size / 0.15)
                st.info(f"📊 ~{num_zones} zones ({zone_size:.2f})")
            
            if vix_zone.trade_bias == "CALLS":
                st.success(f"🟢 **CALLS** — VIX at resistance ({vix_zone.position_pct:.0f}%)")
            elif vix_zone.trade_bias == "PUTS":
                st.error(f"🔴 **PUTS** — VIX at support ({vix_zone.position_pct:.0f}%)")
            elif vix_zone.current > 0:
                st.warning(f"🟡 **WAIT** — VIX mid-zone ({vix_zone.position_pct:.0f}%)")
        
        st.markdown("---")
        
        # ====================================================================
        # ES-SPX OFFSET
        # ====================================================================
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
            help="Positive if ES > SPX, Negative if ES < SPX"
        )
        st.session_state.es_offset = es_offset
        
        if es_offset >= 0:
            st.caption(f"ES is **{es_offset:.2f}** pts ABOVE SPX")
        else:
            st.caption(f"ES is **{abs(es_offset):.2f}** pts BELOW SPX")
        
        st.markdown("---")
        
        # ====================================================================
        # OVERNIGHT PIVOTS
        # ====================================================================
        st.markdown("### 🌙 Overnight ES Pivots")
        st.caption("For gap day detection (ES values)")
        
        if 'overnight_es_high' not in st.session_state:
            st.session_state.overnight_es_high = 0.0
        if 'overnight_es_low' not in st.session_state:
            st.session_state.overnight_es_low = 0.0
        
        overnight_es_high = st.number_input(
            "Overnight ES High",
            min_value=0.0,
            max_value=10000.0,
            value=st.session_state.overnight_es_high,
            step=0.25,
            format="%.2f",
            help="Highest ES price overnight (for gap down detection)"
        )
        st.session_state.overnight_es_high = overnight_es_high
        
        overnight_es_low = st.number_input(
            "Overnight ES Low",
            min_value=0.0,
            max_value=10000.0,
            value=st.session_state.overnight_es_low,
            step=0.25,
            format="%.2f",
            help="Lowest ES price overnight (for gap up detection)"
        )
        st.session_state.overnight_es_low = overnight_es_low
        
        if overnight_es_high > 0:
            overnight_spx_high = convert_es_to_spx(overnight_es_high, es_offset)
            st.caption(f"SPX High: **{overnight_spx_high:.2f}**")
        
        if overnight_es_low > 0:
            overnight_spx_low = convert_es_to_spx(overnight_es_low, es_offset)
            st.caption(f"SPX Low: **{overnight_spx_low:.2f}**")
        
        st.markdown("---")
        
        # ====================================================================
        # MANUAL PIVOTS
        # ====================================================================
        st.markdown("### 📍 Manual Pivots")
        
        use_manual = st.checkbox(
            "Override Auto-Pivots",
            value=False,
            help="Manually enter prior session pivots"
        )
        
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
                "Low (Close-based)",
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
        
        # ====================================================================
        # QUICK REFERENCE
        # ====================================================================
        st.markdown("### 📖 Quick Reference")
        
        st.markdown(
            """
            **🟢 CALLS Entry:**
            - VIX closes at RESISTANCE (80%+)
            - SPX at DESCENDING rail
            - VIX drops → SPX rises
            
            **🔴 PUTS Entry:**
            - VIX closes at SUPPORT (≤20%)
            - SPX at ASCENDING rail
            - VIX rises → SPX drops
            
            **Rail Logic:**
            - ▼ DESC = Support → CALLS
            - ▲ ASC = Resistance → PUTS
            
            **Key Numbers:**
            - Zone: 0.15 | Rail: ≤8 pts
            - Width: ≥18 pts | Stop: 6 pts
            """
        )
    
    # ========================================================================
    # MAIN CONTENT - DATA FETCHING
    # ========================================================================
    
    prior_session = fetch_prior_session_data(session_date_dt)
    current_price = fetch_current_spx()
    
    if current_price is None:
        current_price = 6000.0
        st.warning("⚠️ Could not fetch live SPX price. Using placeholder.")
    
    # Determine pivot values
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
        st.error("⚠️ Could not fetch prior session data. Enable **Manual Pivots** in sidebar.")
        st.stop()
    
    # Create target time
    target_time = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
    
    # Create pivots
    pivots = [
        Pivot(price=high_price, time=high_time, name='High'),
        Pivot(price=low_price, time=low_time, name='Low'),
        Pivot(
            price=close_price,
            time=CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(15, 0))),
            name='Close'
        ),
    ]
    
    # Create cones
    cones = [create_cone(p, target_time) for p in pivots]
    
    # ========================================================================
    # GAP DAY DETECTION
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
    # CALCULATE KEY METRICS
    # ========================================================================
    
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    
    if nearest_cone:
        cone_width = abs(nearest_cone.ascending_rail - nearest_cone.descending_rail)
    else:
        cone_width = 0
    
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
    # MAIN LAYOUT - TWO COLUMNS
    # ========================================================================
    left_col, right_col = st.columns([2, 1])
    
    # ========================================================================
    # LEFT COLUMN
    # ========================================================================
    with left_col:
        
        # VIX Zone Panel
        if vix_zone and vix_zone.support > 0:
            render_section_header("🧭", "VIX Zone Analysis")
            render_vix_zone_panel(vix_zone)
        
        # Trade Setups
        render_section_header("🎯", "Trade Setups")
        
        calls_setups = sorted(
            [s for s in trade_setups if s.direction == 'CALLS'],
            key=lambda x: abs(current_price - x.entry_price)
        )
        puts_setups = sorted(
            [s for s in trade_setups if s.direction == 'PUTS'],
            key=lambda x: abs(current_price - x.entry_price)
        )
        
        tab_calls, tab_puts = st.tabs([
            f"🟢 CALLS — Descending Rail = Support ({len(calls_setups)})",
            f"🔴 PUTS — Ascending Rail = Resistance ({len(puts_setups)})"
        ])
        
        with tab_calls:
            if calls_setups:
                for setup in calls_setups[:4]:
                    render_trade_card(setup, current_price, vix_zone)
            else:
                st.info("No CALLS setups available. Cones may be too narrow (need ≥18 pts).")
        
        with tab_puts:
            if puts_setups:
                for setup in puts_setups[:4]:
                    render_trade_card(setup, current_price, vix_zone)
            else:
                st.info("No PUTS setups available. Cones may be too narrow (need ≥18 pts).")
        
        # RTH Table
        render_section_header("📊", "RTH Session Rails")
        render_rth_table(cones, current_price, session_date)
    
    # ========================================================================
    # RIGHT COLUMN
    # ========================================================================
    with right_col:
        
        # Checklist
        render_section_header("📋", "Trade Checklist")
        render_checklist(cones, current_price, vix_zone)
        
        # Pivots
        render_section_header("📍", "Prior Session")
        render_pivots_panel(high_price, low_price, close_price, prior_date)
        
        # 10am Rails
        render_section_header("📐", "10:00 AM Rails")
        render_rails_panel(cones)
        
        # Legend
        render_section_header("📚", "Trading Rules")
        render_legend()
    
    # ========================================================================
    # FOOTER
    # ========================================================================
    render_footer()


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    main()