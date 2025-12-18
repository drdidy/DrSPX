"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           SPX PROPHET v2.1                                    ║
║                    Where Structure Becomes Foresight                          ║
║                         LEGENDARY EDITION                                     ║
║                                                                               ║
║                         100% Native Streamlit                                 ║
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
- VIX can spike above resistance, but if it CLOSES below/on it → VIX drops → SPX RISES
- VIX can spike below support, but if it CLOSES above/on it → VIX rises → SPX DROPS

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
VIX_ZONE_SIZE = 0.15  # VIX moves in 0.15 increments

# Cone Rail Slopes (pts per 30-min block)
SLOPE_ASCENDING = 0.45
SLOPE_DESCENDING = 0.45

# Trading Parameters
MIN_CONE_WIDTH = 18.0  # Minimum cone width to trade (pts)

AT_RAIL_THRESHOLD = 8.0  
# ^ Maximum distance from rail to be considered "at rail" for entry
# If SPX is within 8 pts of a rail → Ready to trade
# If SPX is more than 8 pts away → Wait for price to reach rail

STOP_LOSS_PTS = 6.0  
# ^ Stop loss distance in SPX points
# If entry is 6050, stop is 6044 for CALLS or 6056 for PUTS

STRIKE_OFFSET = 17.5  
# ^ How far OTM to buy the option (in SPX points)
# CALLS: Strike = Entry - 17.5 (e.g., Entry 6050 → Strike 6032 → round to 6030)
# PUTS: Strike = Entry + 17.5 (e.g., Entry 6080 → Strike 6098 → round to 6100)
# This gives roughly 0.35 delta - good balance of cost vs leverage

# Time filter
POWER_HOUR_START = time(14, 0)  # Highs after 2pm are less reliable pivots

# RTH Time blocks for session table
RTH_TIME_BLOCKS = [
    ("8:30 AM", time(8, 30), True, False),    # (label, time, is_open, is_target)
    ("9:00 AM", time(9, 0), False, False),
    ("9:30 AM", time(9, 30), False, False),
    ("10:00 AM", time(10, 0), False, True),   # Primary target
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
    """Get current time in Central timezone."""
    return datetime.now(CT_TZ)

def get_time_block_index(dt: datetime, base_time: time = time(8, 30)) -> int:
    """
    Calculate 30-minute block index from base time (8:30am).
    Block 0 = 8:30-9:00am
    Block 1 = 9:00-9:30am
    Block 2 = 9:30-10:00am
    Block 3 = 10:00-10:30am
    """
    base = dt.replace(hour=base_time.hour, minute=base_time.minute, second=0, microsecond=0)
    if dt < base:
        return 0
    diff = (dt - base).total_seconds()
    return int(diff // 1800)  # 1800 seconds = 30 minutes

def get_delta_estimate(otm_distance: float) -> float:
    """
    Estimate option delta based on distance OTM.
    This is approximate - real delta depends on IV, time to expiry, etc.
    """
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
    """
    Convert ES futures price to SPX equivalent.
    
    Args:
        es_price: ES futures price
        es_offset: ES minus SPX difference (can be positive or negative)
    
    Returns:
        SPX equivalent price
    
    Example:
        ES = 6055, offset = +5 (ES is 5 pts above SPX)
        SPX = 6055 - 5 = 6050
    """
    return es_price - es_offset

def format_currency(value: float) -> str:
    """Format value as currency."""
    return f"${value:,.0f}"

def format_price(value: float) -> str:
    """Format value as price."""
    return f"{value:,.2f}"

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Pivot:
    """A price pivot from prior session."""
    price: float
    time: datetime
    name: str  # 'High', 'Low', 'Close', 'Gap Low', 'Gap High'

@dataclass
class Cone:
    """A cone projected from a pivot with two rails."""
    pivot: Pivot
    name: str
    ascending_rail: float   # Rail going up over time (normally = resistance)
    descending_rail: float  # Rail going down over time (normally = support)
    
@dataclass 
class VIXZone:
    """VIX zone structure with support/resistance and extended levels."""
    support: float          # Zone bottom (overnight low)
    resistance: float       # Zone top (overnight high)
    zone_size: float        # Should be ~0.15 for single zone
    current: float          # Current VIX 30-min CLOSE (not wick!)
    position_pct: float     # Where current is in zone (0%=support, 100%=resistance)
    trade_bias: str         # 'CALLS', 'PUTS', or 'NEUTRAL'
    levels_above: List[float]  # Extended resistance levels (+0.15 each)
    levels_below: List[float]  # Extended support levels (-0.15 each)

@dataclass
class TradeSetup:
    """Complete trade setup with entry, target, stop, and P/L calculations."""
    direction: str          # 'CALLS' or 'PUTS'
    entry_price: float      # SPX price to enter
    target_price: float     # SPX price target (opposite rail)
    stop_price: float       # Stop loss price
    cone_name: str          # Which cone this is from
    rail_type: str          # 'descending' or 'ascending'
    risk_pts: float         # Points risked
    reward_pts: float       # Points to target
    rr_ratio: float         # Reward/Risk ratio
    strike: float           # Option strike to buy
    delta: float            # Estimated delta
    expected_profit: float  # Expected $ profit per contract at target
    max_loss: float         # Max $ loss per contract at stop
    vix_condition: str      # Required VIX condition for this trade

@dataclass
class GapAnalysis:
    """Analysis of gap conditions for the session."""
    is_gap_up: bool         # True if opened above High cone ascending rail
    is_gap_down: bool       # True if opened below Low cone descending rail
    gap_type: str           # 'GAP_UP', 'GAP_DOWN', or 'NORMAL'
    overnight_pivot: Optional[float]  # SPX value of overnight pivot (if gap day)
    overnight_pivot_name: str  # 'Gap Low' or 'Gap High'

# ============================================================================
# VIX ZONE CALCULATIONS
# ============================================================================

def calculate_vix_zones(support: float, resistance: float, current: float) -> VIXZone:
    """
    Calculate VIX zone structure and trade bias.
    
    CRITICAL: 'current' should be the 30-minute CLOSE, not the wick/spike!
    
    The logic (remember VIX and SPX are INVERSE):
    - VIX CLOSES at resistance (80%+) → VIX will drop → SPX rises → CALLS
    - VIX CLOSES at support (20% or below) → VIX will rise → SPX drops → PUTS
    - VIX CLOSES in middle → No clear signal → NEUTRAL
    """
    zone_size = resistance - support
    
    # Calculate position within zone as percentage
    if zone_size > 0 and current > 0:
        position_pct = ((current - support) / zone_size) * 100
        position_pct = max(-100, min(200, position_pct))
    else:
        position_pct = 50
    
    # Determine trade bias based on 30-min CLOSE position
    if current <= 0:
        trade_bias = "ENTER VIX"
    elif position_pct >= 80:
        # VIX at resistance → VIX will drop → SPX RISES → CALLS
        trade_bias = "CALLS"
    elif position_pct <= 20:
        # VIX at support → VIX will rise → SPX DROPS → PUTS
        trade_bias = "PUTS"
    else:
        trade_bias = "NEUTRAL"
    
    # Calculate extended levels for breakouts
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
    """
    Get human-readable zone status and trade guidance.
    """
    if vix_zone.current <= 0:
        return "Enter VIX 30-min close", "N/A", "N/A"
    
    current = vix_zone.current
    
    # Breakout above resistance
    if current > vix_zone.resistance + 0.02:
        zones_above = (current - vix_zone.resistance) / VIX_ZONE_SIZE
        target_zone = min(int(zones_above) + 1, 4)
        return (
            f"⚠️ VIX BREAKOUT UP → PUTS targets extend",
            f"Target: {vix_zone.levels_above[target_zone-1]:.2f}",
            "Hold PUTS / Extend targets"
        )
    
    # Breakdown below support
    if current < vix_zone.support - 0.02:
        zones_below = (vix_zone.support - current) / VIX_ZONE_SIZE
        target_zone = min(int(zones_below) + 1, 4)
        return (
            f"⚠️ VIX BREAKDOWN → CALLS targets extend",
            f"Target: {vix_zone.levels_below[target_zone-1]:.2f}",
            "Hold CALLS / Extend targets"
        )
    
    # Within zone
    if vix_zone.position_pct >= 80:
        return (
            "🟢 VIX at RESISTANCE → CALLS",
            "VIX will drop → SPX rises",
            "Enter CALLS at descending rail"
        )
    elif vix_zone.position_pct <= 20:
        return (
            "🔴 VIX at SUPPORT → PUTS",
            "VIX will rise → SPX drops",
            "Enter PUTS at ascending rail"
        )
    else:
        return (
            "🟡 VIX MID-ZONE → WAIT",
            "No clear signal",
            "Wait for 30-min close at extremes"
        )

# ============================================================================
# GAP ANALYSIS
# ============================================================================

def analyze_gap(open_price: float, high_cone: Cone, low_cone: Cone,
                overnight_high_spx: float, overnight_low_spx: float) -> GapAnalysis:
    """
    Analyze if today is a gap day and determine appropriate pivots.
    
    GAP UP: SPX opens ABOVE the High Cone's ascending rail
    - Use overnight LOW as new pivot (ascending rail becomes support for CALLS)
    
    GAP DOWN: SPX opens BELOW the Low Cone's descending rail  
    - Use overnight HIGH as new pivot (descending rail becomes resistance for PUTS)
    """
    # Check for gap up (open above high cone ascending rail)
    if open_price > high_cone.ascending_rail:
        return GapAnalysis(
            is_gap_up=True,
            is_gap_down=False,
            gap_type='GAP_UP',
            overnight_pivot=overnight_low_spx,
            overnight_pivot_name='Gap Low'
        )
    
    # Check for gap down (open below low cone descending rail)
    if open_price < low_cone.descending_rail:
        return GapAnalysis(
            is_gap_up=False,
            is_gap_down=True,
            gap_type='GAP_DOWN',
            overnight_pivot=overnight_high_spx,
            overnight_pivot_name='Gap High'
        )
    
    # Normal day
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
    """
    Calculate rail price at a target time.
    Rails move ±0.45 pts per 30-minute block from the pivot.
    """
    blocks = get_time_block_index(target_time) - get_time_block_index(pivot_time)
    slope = SLOPE_ASCENDING if is_ascending else -SLOPE_DESCENDING
    return pivot_price + (slope * blocks)

def create_cone(pivot: Pivot, target_time: datetime) -> Cone:
    """
    Create a cone from a pivot, calculating both rails at target time.
    """
    ascending = calculate_rail_price(pivot.price, pivot.time, target_time, True)
    descending = calculate_rail_price(pivot.price, pivot.time, target_time, False)
    return Cone(
        pivot=pivot, 
        name=pivot.name, 
        ascending_rail=ascending, 
        descending_rail=descending
    )

def find_nearest_rail(price: float, cones: List[Cone]) -> Tuple[Optional[Cone], str, float]:
    """
    Find the nearest rail to current price across all cones.
    
    Returns:
        Tuple of (nearest_cone, rail_type, distance)
        rail_type is 'ascending' or 'descending'
    """
    nearest_cone = None
    nearest_type = ''
    nearest_distance = float('inf')
    
    for cone in cones:
        # Check descending rail (normally = support for CALLS)
        dist_desc = abs(price - cone.descending_rail)
        if dist_desc < nearest_distance:
            nearest_distance = dist_desc
            nearest_cone = cone
            nearest_type = 'descending'
        
        # Check ascending rail (normally = resistance for PUTS)
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
    """
    Fetch prior session pivot data from Yahoo Finance.
    """
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
    """Fetch current SPX price."""
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
    """
    Generate all possible trade setups from cones.
    
    NORMAL DAY LOGIC:
    - CALLS: Entry at DESCENDING rail (support) + VIX at resistance
    - PUTS: Entry at ASCENDING rail (resistance) + VIX at support
    
    GAP UP DAY (ascending rail becomes support):
    - CALLS: Entry at ASCENDING rail from gap low + VIX at resistance
    
    GAP DOWN DAY (descending rail becomes resistance):
    - PUTS: Entry at DESCENDING rail from gap high + VIX at support
    """
    setups = []
    
    for cone in cones:
        cone_width = abs(cone.ascending_rail - cone.descending_rail)
        
        if cone_width < MIN_CONE_WIDTH:
            continue
        
        # Determine if this is a gap day cone
        is_gap_cone = cone.name in ['Gap Low', 'Gap High']
        
        # ============================================
        # CALLS SETUP
        # ============================================
        # Normal: Entry at DESCENDING rail (support)
        # Gap Up: Entry at ASCENDING rail from Gap Low (support)
        
        if is_gap_cone and cone.name == 'Gap Low':
            # Gap up day - ascending rail is support
            calls_entry = cone.ascending_rail
            calls_target = cone.ascending_rail + cone_width  # Project up
            calls_rail_type = 'ascending'
        else:
            # Normal day - descending rail is support
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
        
        # ============================================
        # PUTS SETUP
        # ============================================
        # Normal: Entry at ASCENDING rail (resistance)
        # Gap Down: Entry at DESCENDING rail from Gap High (resistance)
        
        if is_gap_cone and cone.name == 'Gap High':
            # Gap down day - descending rail is resistance
            puts_entry = cone.descending_rail
            puts_target = cone.descending_rail - cone_width  # Project down
            puts_rail_type = 'descending'
        else:
            # Normal day - ascending rail is resistance
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
    """
    Check if VIX + SPX confluence exists for a trade setup.
    
    BOTH conditions must be met in the same 30-min candle:
    1. VIX 30-min closes at the required zone extreme
    2. SPX is at the required rail
    
    Returns:
        Tuple of (is_valid, reason)
    """
    if vix_zone is None or vix_zone.current <= 0:
        return False, "Enter VIX data"
    
    # Check if SPX is at rail
    distance_to_entry = abs(spx_price - trade_setup.entry_price)
    spx_at_rail = distance_to_entry <= AT_RAIL_THRESHOLD
    
    if not spx_at_rail:
        return False, f"SPX {distance_to_entry:.1f} pts from rail"
    
    # Check VIX condition
    if trade_setup.direction == 'CALLS':
        # CALLS need VIX at resistance (will drop → SPX rises)
        vix_aligned = vix_zone.trade_bias == 'CALLS'
        if not vix_aligned:
            return False, f"VIX at {vix_zone.position_pct:.0f}% (need 80%+)"
    else:
        # PUTS need VIX at support (will rise → SPX drops)
        vix_aligned = vix_zone.trade_bias == 'PUTS'
        if not vix_aligned:
            return False, f"VIX at {vix_zone.position_pct:.0f}% (need ≤20%)"
    
    return True, "✅ CONFLUENCE"

# ============================================================================
# RTH SESSION TABLE DATA
# ============================================================================

def generate_rth_table_data(cones: List[Cone], current_price: float, session_date: datetime) -> pd.DataFrame:
    """
    Generate RTH session table with rail prices at each 30-min block.
    """
    rows = []
    
    for time_label, time_val, is_open, is_target in RTH_TIME_BLOCKS:
        target_dt = CT_TZ.localize(datetime.combine(session_date, time_val))
        
        row = {
            'Time': time_label,
            'Highlight': '🔵 OPEN' if is_open else ('🟢 TARGET' if is_target else '')
        }
        
        for cone in cones:
            asc_price = calculate_rail_price(cone.pivot.price, cone.pivot.time, target_dt, True)
            desc_price = calculate_rail_price(cone.pivot.price, cone.pivot.time, target_dt, False)
            
            # Format with direction indicators
            row[f'{cone.name} ▲'] = f"{asc_price:.2f}"
            row[f'{cone.name} ▼'] = f"{desc_price:.2f}"
        
        rows.append(row)
    
    return pd.DataFrame(rows)

# ============================================================================
# VIX ZONE LADDER DATA
# ============================================================================

def generate_vix_ladder_data(vix_zone: VIXZone) -> pd.DataFrame:
    """
    Generate VIX zone ladder as a DataFrame.
    """
    rows = []
    
    # Levels above (PUTS extend) - reverse order so +4 is at top
    for i in range(3, -1, -1):
        rows.append({
            'Level': f'+{i+1}',
            'VIX Price': f"{vix_zone.levels_above[i]:.2f}",
            'Action': '🔴 PUTS extend',
            'Type': 'extend_up'
        })
    
    # Resistance
    rows.append({
        'Level': '⭐ RES',
        'VIX Price': f"{vix_zone.resistance:.2f}",
        'Action': '🟢 CALLS Entry',
        'Type': 'resistance'
    })
    
    # Current (if in zone)
    if vix_zone.support - 0.05 <= vix_zone.current <= vix_zone.resistance + 0.05:
        rows.append({
            'Level': f'→ NOW',
            'VIX Price': f"{vix_zone.current:.2f}",
            'Action': f'{vix_zone.position_pct:.0f}%',
            'Type': 'current'
        })
    
    # Support
    rows.append({
        'Level': '⭐ SUP',
        'VIX Price': f"{vix_zone.support:.2f}",
        'Action': '🔴 PUTS Entry',
        'Type': 'support'
    })
    
    # Levels below (CALLS extend)
    for i in range(4):
        rows.append({
            'Level': f'-{i+1}',
            'VIX Price': f"{vix_zone.levels_below[i]:.2f}",
            'Action': '🟢 CALLS extend',
            'Type': 'extend_down'
        })
    
    return pd.DataFrame(rows)


# ============================================================================
# ============================================================================
#
#                        PART 2: UI COMPONENTS (100% NATIVE STREAMLIT)
#
#                        No HTML. No CSS. Just Pure Streamlit Magic.
#
# ============================================================================
# ============================================================================

# ============================================================================
# COLOR & EMOJI CONSTANTS
# ============================================================================

# Direction Colors (for reference in styling)
CALLS_EMOJI = "🟢"
PUTS_EMOJI = "🔴"
NEUTRAL_EMOJI = "🟡"
WARNING_EMOJI = "⚠️"
TARGET_EMOJI = "🎯"
CHECK_EMOJI = "✅"
CROSS_EMOJI = "❌"
FIRE_EMOJI = "🔥"
ROCKET_EMOJI = "🚀"
CHART_EMOJI = "📊"
COMPASS_EMOJI = "🧭"
CLOCK_EMOJI = "🕐"

# ============================================================================
# HEADER COMPONENT
# ============================================================================

def render_header():
    """Render the main application header."""
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        st.markdown(
            "<h1 style='text-align: center; color: #1e40af;'>🎯 SPX PROPHET</h1>", 
            unsafe_allow_html=True
        )
        st.markdown(
            "<p style='text-align: center; color: #64748b; letter-spacing: 3px;'>WHERE STRUCTURE BECOMES FORESIGHT</p>", 
            unsafe_allow_html=True
        )
    
    st.markdown("---")

# ============================================================================
# METRICS DISPLAY
# ============================================================================

def render_metrics_row(current_price: float, vix_zone: Optional[VIXZone], 
                       nearest_distance: float, cone_width: float,
                       nearest_cone: Optional[Cone], nearest_rail_type: str):
    """Render the top metrics row using native st.metric components."""
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💹 SPX Price",
            value=f"{current_price:,.2f}",
            delta=None
        )
    
    with col2:
        if vix_zone and vix_zone.current > 0:
            bias_indicator = ""
            if vix_zone.trade_bias == "CALLS":
                bias_indicator = "🟢"
            elif vix_zone.trade_bias == "PUTS":
                bias_indicator = "🔴"
            else:
                bias_indicator = "🟡"
            
            st.metric(
                label=f"📊 VIX 30m Close {bias_indicator}",
                value=f"{vix_zone.current:.2f}",
                delta=f"{vix_zone.position_pct:.0f}% in zone"
            )
        else:
            st.metric(
                label="📊 VIX 30m Close",
                value="—",
                delta="Enter data"
            )
    
    with col3:
        if nearest_distance <= AT_RAIL_THRESHOLD:
            st.metric(
                label="📍 Distance to Rail",
                value=f"{nearest_distance:.1f} pts",
                delta="🎯 AT RAIL",
                delta_color="normal"
            )
        else:
            st.metric(
                label="📍 Distance to Rail",
                value=f"{nearest_distance:.1f} pts",
                delta="Waiting...",
                delta_color="off"
            )
    
    with col4:
        if cone_width >= 25:
            width_status = "✅ Wide"
        elif cone_width >= MIN_CONE_WIDTH:
            width_status = "⚠️ OK"
        else:
            width_status = "❌ Narrow"
        
        st.metric(
            label="📐 Cone Width",
            value=f"{cone_width:.0f} pts",
            delta=width_status,
            delta_color="normal" if cone_width >= MIN_CONE_WIDTH else "inverse"
        )

# ============================================================================
# GAP DAY BANNER
# ============================================================================

def render_gap_banner(gap_analysis: GapAnalysis):
    """Render gap day alert banner."""
    
    if gap_analysis.gap_type == 'NORMAL':
        return
    
    if gap_analysis.gap_type == 'GAP_UP':
        st.success(f"""
        🚀 **GAP UP DAY DETECTED**
        
        SPX opened above High Cone's ascending rail.
        
        **New Pivot:** Overnight Low @ **{gap_analysis.overnight_pivot:.2f}** (SPX)
        
        **Rule:** Ascending rail from Gap Low acts as **SUPPORT** → CALLS entry when VIX at resistance
        """)
    else:
        st.error(f"""
        📉 **GAP DOWN DAY DETECTED**
        
        SPX opened below Low Cone's descending rail.
        
        **New Pivot:** Overnight High @ **{gap_analysis.overnight_pivot:.2f}** (SPX)
        
        **Rule:** Descending rail from Gap High acts as **RESISTANCE** → PUTS entry when VIX at support
        """)

# ============================================================================
# VIX ZONE PANEL
# ============================================================================

def render_vix_zone_panel(vix_zone: VIXZone):
    """Render the VIX Zone Analysis panel with ladder."""
    
    # Get status
    status, detail1, detail2 = get_vix_zone_status(vix_zone)
    
    # Header with trade bias
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🧭 VIX Trade Compass")
        
        if vix_zone.trade_bias == "CALLS":
            st.success(f"**{status}**")
        elif vix_zone.trade_bias == "PUTS":
            st.error(f"**{status}**")
        else:
            st.warning(f"**{status}**")
        
        st.caption(f"{detail1} | {detail2}")
    
    with col2:
        st.metric(
            label="Zone Size",
            value=f"{vix_zone.zone_size:.2f}",
            delta="Valid" if 0.13 <= vix_zone.zone_size <= 0.17 else f"~{round(vix_zone.zone_size/0.15)} zones"
        )
    
    st.markdown("---")
    
    # VIX Zone Ladder
    st.markdown("**📊 VIX Zone Ladder (0.15 increments)**")
    
    # Create columns for the ladder
    ladder_data = generate_vix_ladder_data(vix_zone)
    
    # Display as styled dataframe
    st.dataframe(
        ladder_data[['Level', 'VIX Price', 'Action']],
        use_container_width=True,
        hide_index=True,
        height=450
    )
    
    # Zone position indicator
    st.markdown("---")
    
    # Visual position bar
    position = max(0, min(100, vix_zone.position_pct))
    
    col1, col2, col3 = st.columns([1, 8, 1])
    with col1:
        st.caption("SUP")
    with col2:
        st.progress(position / 100)
    with col3:
        st.caption("RES")
    
    st.caption(f"Current Position: **{vix_zone.position_pct:.1f}%** | 80%+ = CALLS | 20%- = PUTS")

# ============================================================================
# TRADE CARD COMPONENT
# ============================================================================

def render_trade_card(setup: TradeSetup, current_price: float, vix_zone: Optional[VIXZone]):
    """Render a single trade setup card."""
    
    distance = abs(current_price - setup.entry_price)
    is_near = distance <= AT_RAIL_THRESHOLD
    
    # Check confluence
    confluence_ok = False
    confluence_msg = "Enter VIX data"
    if vix_zone and vix_zone.current > 0:
        confluence_ok, confluence_msg = check_confluence(setup, vix_zone, current_price)
    
    # Card container
    if setup.direction == "CALLS":
        if confluence_ok:
            st.success(f"### 🟢 CALLS — {setup.cone_name} Cone")
        else:
            st.info(f"### 🟢 CALLS — {setup.cone_name} Cone")
    else:
        if confluence_ok:
            st.error(f"### 🔴 PUTS — {setup.cone_name} Cone")
        else:
            st.info(f"### 🔴 PUTS — {setup.cone_name} Cone")
    
    # Distance status
    if is_near:
        st.success(f"🎯 **AT RAIL** — {distance:.1f} pts away")
    else:
        st.warning(f"⏳ **WAITING** — {distance:.1f} pts to entry")
    
    # Price levels row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Entry",
            value=f"{setup.entry_price:.2f}",
            delta=f"{setup.rail_type.upper()} rail"
        )
    
    with col2:
        st.metric(
            label="Target",
            value=f"{setup.target_price:.2f}",
            delta=f"+{setup.reward_pts:.0f} pts"
        )
    
    with col3:
        st.metric(
            label="Stop Loss",
            value=f"{setup.stop_price:.2f}",
            delta=f"-{setup.risk_pts:.0f} pts",
            delta_color="inverse"
        )
    
    with col4:
        st.metric(
            label="Strike",
            value=f"{setup.strike:.0f}",
            delta=f"Δ {setup.delta:.2f}"
        )
    
    # Profit/Loss row
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="💰 Expected Profit",
            value=f"+${setup.expected_profit:.0f}",
            delta="per contract",
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            label="⚠️ Max Loss",
            value=f"-${setup.max_loss:.0f}",
            delta="per contract",
            delta_color="inverse"
        )
    
    with col3:
        rr_status = "✅ Good" if setup.rr_ratio >= 3 else ("⚠️ OK" if setup.rr_ratio >= 2 else "❌ Low")
        st.metric(
            label="📊 Risk:Reward",
            value=f"{setup.rr_ratio:.1f}:1",
            delta=rr_status,
            delta_color="normal" if setup.rr_ratio >= 2 else "inverse"
        )
    
    # Confluence status
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**Required:** {setup.vix_condition}")
    
    with col2:
        if confluence_ok:
            st.success(f"**{confluence_msg}**")
        else:
            st.warning(f"**{confluence_msg}**")
    
    st.markdown("---")

# ============================================================================
# CHECKLIST COMPONENT
# ============================================================================

def render_checklist(cones: List[Cone], current_price: float, vix_zone: Optional[VIXZone]):
    """Render the trade validation checklist."""
    
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    cone_width = abs(nearest_cone.ascending_rail - nearest_cone.descending_rail) if nearest_cone else 0
    
    # Determine expected direction
    if nearest_rail_type == 'descending':
        expected_direction = 'CALLS'
        expected_vix = 'CALLS'
    else:
        expected_direction = 'PUTS'
        expected_vix = 'PUTS'
    
    st.subheader("📋 Trade Checklist")
    
    checks_passed = 0
    total_checks = 4
    
    # Check 1: At Rail
    at_rail_ok = nearest_distance <= AT_RAIL_THRESHOLD
    if at_rail_ok:
        st.success(f"✅ **At Rail** — {nearest_distance:.1f} pts (within {AT_RAIL_THRESHOLD} pts)")
        checks_passed += 1
    else:
        st.error(f"❌ **Not at Rail** — {nearest_distance:.1f} pts away (need ≤{AT_RAIL_THRESHOLD} pts)")
    
    # Check 2: Structure
    structure_ok = cone_width >= MIN_CONE_WIDTH
    if structure_ok:
        st.success(f"✅ **Structure OK** — {cone_width:.0f} pts width (min {MIN_CONE_WIDTH} pts)")
        checks_passed += 1
    else:
        st.error(f"❌ **Structure Weak** — Only {cone_width:.0f} pts (need ≥{MIN_CONE_WIDTH} pts)")
    
    # Check 3: Active Cone
    if nearest_cone:
        st.success(f"✅ **Active Cone** — {nearest_cone.name} cone, {nearest_rail_type} rail")
        checks_passed += 1
    else:
        st.error("❌ **No Active Cone** — No valid cone detected")
    
    # Check 4: VIX Confluence
    if vix_zone and vix_zone.current > 0:
        vix_ok = vix_zone.trade_bias == expected_vix
        if vix_ok:
            st.success(f"✅ **VIX Confluence** — {vix_zone.trade_bias} bias ({vix_zone.position_pct:.0f}%)")
            checks_passed += 1
        else:
            st.error(f"❌ **No VIX Confluence** — VIX says {vix_zone.trade_bias}, need {expected_vix}")
    else:
        st.warning(f"⚠️ **VIX Unknown** — Enter VIX data (need {expected_vix})")
    
    st.markdown("---")
    
    # Overall Status
    if checks_passed == 4:
        st.success(f"""
        ## 🟢 CONFLUENCE — GO!
        
        **{checks_passed}/{total_checks}** checks passed
        
        All conditions met for **{expected_direction}** entry!
        """)
    elif checks_passed >= 3 and at_rail_ok:
        st.success(f"""
        ## 🟢 STRONG SETUP
        
        **{checks_passed}/{total_checks}** checks passed
        
        Good setup for **{expected_direction}**, minor caution advised.
        """)
    elif not at_rail_ok:
        st.warning(f"""
        ## 🟡 WAIT — Not at Rail
        
        **{checks_passed}/{total_checks}** checks passed
        
        Wait for SPX to reach the {nearest_rail_type} rail.
        """)
    elif not structure_ok:
        st.error(f"""
        ## 🔴 SKIP — Bad Structure
        
        **{checks_passed}/{total_checks}** checks passed
        
        Cone too narrow for reliable trade.
        """)
    else:
        st.warning(f"""
        ## 🟡 CAUTION
        
        **{checks_passed}/{total_checks}** checks passed
        
        Wait for better conditions.
        """)
    
    st.markdown("---")
    
    # Trade Direction Box
    if expected_direction == "CALLS":
        st.success(f"""
        ### 🎯 Trade Direction: CALLS
        
        **{nearest_cone.name if nearest_cone else 'N/A'}** cone, **{nearest_rail_type}** rail
        
        ▼ Descending rail = Support → Buy CALLS
        """)
    else:
        st.error(f"""
        ### 🎯 Trade Direction: PUTS
        
        **{nearest_cone.name if nearest_cone else 'N/A'}** cone, **{nearest_rail_type}** rail
        
        ▲ Ascending rail = Resistance → Buy PUTS
        """)

# ============================================================================
# RTH SESSION TABLE
# ============================================================================

def render_rth_session_table(cones: List[Cone], current_price: float, session_date):
    """Render the RTH session table with rail prices."""
    
    st.subheader("📊 RTH Session Rails")
    
    # Legend
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.info("🔵 **8:30 AM** = Market Open")
    with col2:
        st.success("🟢 **10:00 AM** = Primary Target")
    with col3:
        st.caption("▲ ASC = PUTS entry (resistance)")
    with col4:
        st.caption("▼ DESC = CALLS entry (support)")
    
    st.markdown("---")
    
    # Generate table data
    df = generate_rth_table_data(cones, current_price, session_date)
    
    # Style the dataframe
    def highlight_rows(row):
        if '🔵 OPEN' in str(row.get('Highlight', '')):
            return ['background-color: #dbeafe'] * len(row)
        elif '🟢 TARGET' in str(row.get('Highlight', '')):
            return ['background-color: #d1fae5'] * len(row)
        return [''] * len(row)
    
    styled_df = df.style.apply(highlight_rows, axis=1)
    
    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
        height=530
    )
    
    # Current price reference
    st.caption(f"Current SPX: **{current_price:.2f}** | Cells highlight when price is within {AT_RAIL_THRESHOLD} pts of rail")

# ============================================================================
# PRIOR SESSION PIVOTS PANEL
# ============================================================================

def render_pivots_panel(high_price: float, low_price: float, close_price: float, prior_date):
    """Render prior session pivots."""
    
    st.subheader("📍 Prior Session Pivots")
    
    date_str = prior_date.strftime('%b %d, %Y') if hasattr(prior_date, 'strftime') else str(prior_date)
    st.caption(f"Session: **{date_str}**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="🔴 High (Wick)",
            value=f"{high_price:.2f}",
            delta="Rejection level"
        )
    
    with col2:
        st.metric(
            label="🟢 Low (Close)",
            value=f"{low_price:.2f}",
            delta="Commitment level"
        )
    
    with col3:
        st.metric(
            label="🟡 Close",
            value=f"{close_price:.2f}",
            delta="Settlement"
        )

# ============================================================================
# 10AM RAILS PANEL
# ============================================================================

def render_rails_panel(cones: List[Cone]):
    """Render 10:00 AM rail prices for all cones."""
    
    st.subheader("📐 10:00 AM Rail Prices")
    
    for cone in cones:
        with st.container():
            st.markdown(f"**{cone.name} Cone**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    label="▲ Ascending (PUTS)",
                    value=f"{cone.ascending_rail:.2f}",
                    delta="Resistance",
                    delta_color="inverse"
                )
            
            with col2:
                st.metric(
                    label="▼ Descending (CALLS)",
                    value=f"{cone.descending_rail:.2f}",
                    delta="Support",
                    delta_color="normal"
                )
            
            st.markdown("---")

# ============================================================================
# VIX-SPX LEGEND
# ============================================================================

def render_legend():
    """Render the VIX-SPX confluence rules legend."""
    
    st.subheader("📚 VIX-SPX Confluence Rules")
    
    with st.expander("🟢 CALLS Entry Rules", expanded=False):
        st.markdown("""
        **Conditions Required:**
        1. VIX 30-min candle **CLOSES at RESISTANCE** (80%+ in zone)
        2. SPX is at **DESCENDING rail** (support)
        
        **Why it works:**
        - VIX at resistance → VIX will drop
        - VIX drops → SPX rises
        - Descending rail acts as support
        - SPX bounces UP off support → CALLS profit
        
        **Entry:** Descending rail
        **Target:** Ascending rail (opposite)
        **Stop:** 6 pts below entry
        """)
    
    with st.expander("🔴 PUTS Entry Rules", expanded=False):
        st.markdown("""
        **Conditions Required:**
        1. VIX 30-min candle **CLOSES at SUPPORT** (20% or below in zone)
        2. SPX is at **ASCENDING rail** (resistance)
        
        **Why it works:**
        - VIX at support → VIX will rise
        - VIX rises → SPX drops
        - Ascending rail acts as resistance
        - SPX rejected DOWN at resistance → PUTS profit
        
        **Entry:** Ascending rail
        **Target:** Descending rail (opposite)
        **Stop:** 6 pts above entry
        """)
    
    with st.expander("⚠️ Breakout Rules", expanded=False):
        st.markdown("""
        **VIX Breaks ABOVE Resistance:**
        - VIX continuing up → SPX continuing DOWN
        - PUTS targets extend by +0.15 per zone
        - Levels: +1, +2, +3, +4 (each +0.15)
        
        **VIX Breaks BELOW Support:**
        - VIX continuing down → SPX continuing UP
        - CALLS targets extend by -0.15 per zone
        - Levels: -1, -2, -3, -4 (each -0.15)
        """)
    
    with st.expander("🚀 Gap Day Rules", expanded=False):
        st.markdown("""
        **GAP UP Day (SPX opens above High Cone ascending rail):**
        - Use overnight LOW as new pivot
        - Ascending rail from gap low = SUPPORT
        - CALLS entry at ascending rail + VIX at resistance
        
        **GAP DOWN Day (SPX opens below Low Cone descending rail):**
        - Use overnight HIGH as new pivot
        - Descending rail from gap high = RESISTANCE
        - PUTS entry at descending rail + VIX at support
        """)
    
    with st.expander("⏰ Critical Reminders", expanded=False):
        st.markdown("""
        **The 30-Minute Close Rule:**
        - It's the **CLOSE** that matters, not the wick!
        - VIX can spike above resistance, but if it closes below → VIX drops → SPX rises
        - VIX can spike below support, but if it closes above → VIX rises → SPX drops
        - Always wait for the 30-min candle to **CLOSE** before entry
        
        **Confluence is Key:**
        - BOTH conditions must be met in the SAME 30-min window
        - VIX at zone extreme + SPX at corresponding rail = SIGNAL
        - Without both → WAIT
        
        **Zone Size:**
        - Standard zone = 0.15
        - Valid single zone = 0.13 to 0.17
        - Larger zones = multiple 0.15 increments
        """)

# ============================================================================
# SIDEBAR COMPONENTS
# ============================================================================

def render_sidebar_quick_reference():
    """Render quick reference guide in sidebar."""
    
    st.markdown("## 📖 Quick Reference")
    
    st.markdown("""
    **🟢 CALLS Entry:**
    - VIX closes at RESISTANCE (80%+)
    - SPX at DESCENDING rail
    - VIX drops → SPX rises
    
    **🔴 PUTS Entry:**
    - VIX closes at SUPPORT (≤20%)
    - SPX at ASCENDING rail
    - VIX rises → SPX drops
    
    **Rail Logic:**
    - ▼ Descending = Support → CALLS
    - ▲ Ascending = Resistance → PUTS
    
    **Gap Days:**
    - Gap UP: ASC from overnight low = Support
    - Gap DOWN: DESC from overnight high = Resistance
    
    **Key Numbers:**
    - Zone Size: 0.15
    - At Rail: ≤8 pts
    - Min Width: 18 pts
    - Stop Loss: 6 pts
    - Strike Offset: 17.5 pts
    """)

def render_sidebar_status(vix_zone: Optional[VIXZone], nearest_distance: float, 
                          nearest_rail_type: str, cone_width: float):
    """Render current status summary in sidebar."""
    
    st.markdown("## 📡 Current Status")
    
    # VIX Status
    if vix_zone and vix_zone.current > 0:
        if vix_zone.trade_bias == "CALLS":
            st.success(f"**VIX: CALLS** ({vix_zone.position_pct:.0f}%)")
        elif vix_zone.trade_bias == "PUTS":
            st.error(f"**VIX: PUTS** ({vix_zone.position_pct:.0f}%)")
        else:
            st.warning(f"**VIX: NEUTRAL** ({vix_zone.position_pct:.0f}%)")
    else:
        st.info("**VIX:** Enter data")
    
    # Rail Status
    if nearest_distance <= AT_RAIL_THRESHOLD:
        st.success(f"**Rail: AT RAIL** ({nearest_distance:.1f} pts)")
    else:
        st.warning(f"**Rail: WAITING** ({nearest_distance:.1f} pts)")
    
    # Expected Direction
    expected = "CALLS" if nearest_rail_type == 'descending' else "PUTS"
    if expected == "CALLS":
        st.success(f"**Direction: {expected}**")
    else:
        st.error(f"**Direction: {expected}**")
    
    # Structure
    if cone_width >= MIN_CONE_WIDTH:
        st.success(f"**Structure: OK** ({cone_width:.0f} pts)")
    else:
        st.error(f"**Structure: WEAK** ({cone_width:.0f} pts)")

# ============================================================================
# ============================================================================
#
#                        PART 3: MAIN APPLICATION LOGIC
#
#                               The Final Piece
#
# ============================================================================
# ============================================================================

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point."""
    
    # ========================================================================
    # PAGE CONFIGURATION
    # ========================================================================
    st.set_page_config(
        page_title="SPX Prophet v2.1",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # ========================================================================
    # HEADER
    # ========================================================================
    render_header()
    
    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        
        # ====================================================================
        # SESSION DATE
        # ====================================================================
        st.markdown("## 📅 Session Date")
        
        session_date = st.date_input(
            "Trading Date",
            value=get_ct_now().date(),
            help="Select the trading session date"
        )
        
        # Convert to datetime with timezone
        session_date_dt = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        
        # Current time display
        ct_now = get_ct_now()
        st.info(f"🕐 **{ct_now.strftime('%I:%M %p CT')}** | {ct_now.strftime('%A, %b %d, %Y')}")
        
        st.markdown("---")
        
        # ====================================================================
        # VIX ZONE INPUT
        # ====================================================================
        st.markdown("## 🧭 VIX Zone Setup")
        st.caption("From overnight session (5pm-2am CT)")
        
        st.warning("⚠️ **Use 30-min CLOSE prices, not wicks!**")
        
        # Initialize session state for VIX inputs
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
            
            # Zone size validation
            zone_size = vix_resistance - vix_support
            if 0.13 <= zone_size <= 0.17:
                st.success(f"✅ Valid 1-zone: **{zone_size:.2f}**")
            elif zone_size > 0:
                num_zones = round(zone_size / 0.15)
                st.info(f"📊 ~{num_zones} zones ({zone_size:.2f})")
            
            # Trade bias display
            st.markdown("### Current Bias:")
            if vix_zone.trade_bias == "CALLS":
                st.success(f"🟢 **CALLS** — VIX at resistance ({vix_zone.position_pct:.0f}%)")
                st.caption("VIX will drop → SPX rises")
            elif vix_zone.trade_bias == "PUTS":
                st.error(f"🔴 **PUTS** — VIX at support ({vix_zone.position_pct:.0f}%)")
                st.caption("VIX will rise → SPX drops")
            else:
                st.warning(f"🟡 **NEUTRAL** — VIX mid-zone ({vix_zone.position_pct:.0f}%)")
                st.caption("Wait for VIX to reach extremes")
        
        st.markdown("---")
        
        # ====================================================================
        # ES-SPX OFFSET
        # ====================================================================
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
            st.info(f"ES is **{es_offset:.2f}** pts **ABOVE** SPX")
        else:
            st.info(f"ES is **{abs(es_offset):.2f}** pts **BELOW** SPX")
        
        st.markdown("---")
        
        # ====================================================================
        # OVERNIGHT PIVOTS (for gap days)
        # ====================================================================
        st.markdown("## 🌙 Overnight ES Pivots")
        st.caption("For gap day detection — Enter ES values")
        
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
        
        # Show SPX conversions
        if overnight_es_high > 0:
            overnight_spx_high = convert_es_to_spx(overnight_es_high, es_offset)
            st.caption(f"SPX High: **{overnight_spx_high:.2f}**")
        
        if overnight_es_low > 0:
            overnight_spx_low = convert_es_to_spx(overnight_es_low, es_offset)
            st.caption(f"SPX Low: **{overnight_spx_low:.2f}**")
        
        st.markdown("---")
        
        # ====================================================================
        # MANUAL PIVOTS OVERRIDE
        # ====================================================================
        st.markdown("## 📍 Manual Pivots")
        
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
                format="%.2f",
                help="Prior session high (wick)"
            )
            
            st.session_state.manual_low = st.number_input(
                "Low (Close-based)",
                min_value=0.0,
                max_value=10000.0,
                value=st.session_state.manual_low,
                format="%.2f",
                help="Prior session low (close, not wick)"
            )
            
            st.session_state.manual_close = st.number_input(
                "Close",
                min_value=0.0,
                max_value=10000.0,
                value=st.session_state.manual_close,
                format="%.2f",
                help="Prior session close"
            )
        
        st.markdown("---")
        
        # ====================================================================
        # QUICK REFERENCE
        # ====================================================================
        render_sidebar_quick_reference()
    
    # ========================================================================
    # MAIN CONTENT AREA
    # ========================================================================
    
    # Fetch data
    prior_session = fetch_prior_session_data(session_date_dt)
    current_price = fetch_current_spx()
    
    # Handle missing price
    if current_price is None:
        current_price = 6000.0
        st.warning("⚠️ Could not fetch live SPX price. Using placeholder value.")
    
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
        st.error("⚠️ Could not fetch prior session data. Please enable **Manual Pivots** in the sidebar.")
        st.stop()
    
    # Create target time (10:00am)
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
    
    # Create cones from pivots
    cones = [create_cone(p, target_time) for p in pivots]
    
    # ========================================================================
    # GAP DAY DETECTION
    # ========================================================================
    gap_analysis = None
    
    if overnight_es_high > 0 and overnight_es_low > 0:
        overnight_spx_high = convert_es_to_spx(overnight_es_high, es_offset)
        overnight_spx_low = convert_es_to_spx(overnight_es_low, es_offset)
        
        # Find high and low cones
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
            
            # Add gap day pivot if applicable
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
    
    # Find nearest rail
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    
    # Calculate cone width
    if nearest_cone:
        cone_width = abs(nearest_cone.ascending_rail - nearest_cone.descending_rail)
    else:
        cone_width = 0
    
    # Generate trade setups
    trade_setups = generate_trade_setups(cones, current_price, gap_analysis)
    
    # ========================================================================
    # RENDER METRICS ROW
    # ========================================================================
    render_metrics_row(
        current_price=current_price,
        vix_zone=vix_zone,
        nearest_distance=nearest_distance,
        cone_width=cone_width,
        nearest_cone=nearest_cone,
        nearest_rail_type=nearest_rail_type
    )
    
    st.markdown("---")
    
    # ========================================================================
    # GAP DAY BANNER
    # ========================================================================
    if gap_analysis and gap_analysis.gap_type != 'NORMAL':
        render_gap_banner(gap_analysis)
        st.markdown("---")
    
    # ========================================================================
    # SIDEBAR STATUS (after calculations)
    # ========================================================================
    with st.sidebar:
        st.markdown("---")
        render_sidebar_status(vix_zone, nearest_distance, nearest_rail_type, cone_width)
    
    # ========================================================================
    # MAIN LAYOUT — TWO COLUMNS
    # ========================================================================
    left_col, right_col = st.columns([2, 1])
    
    # ========================================================================
    # LEFT COLUMN
    # ========================================================================
    with left_col:
        
        # ====================================================================
        # VIX ZONE PANEL
        # ====================================================================
        if vix_zone and vix_zone.support > 0:
            with st.container():
                render_vix_zone_panel(vix_zone)
            st.markdown("---")
        
        # ====================================================================
        # TRADE SETUPS
        # ====================================================================
        st.subheader("🎯 Trade Setups")
        
        # Sort setups by distance to entry
        calls_setups = sorted(
            [s for s in trade_setups if s.direction == 'CALLS'],
            key=lambda x: abs(current_price - x.entry_price)
        )
        puts_setups = sorted(
            [s for s in trade_setups if s.direction == 'PUTS'],
            key=lambda x: abs(current_price - x.entry_price)
        )
        
        # Tabs for CALLS and PUTS
        tab_calls, tab_puts = st.tabs([
            f"🟢 CALLS — Descending Rail = Support ({len(calls_setups)})",
            f"🔴 PUTS — Ascending Rail = Resistance ({len(puts_setups)})"
        ])
        
        with tab_calls:
            if calls_setups:
                for setup in calls_setups[:4]:
                    with st.container():
                        render_trade_card(setup, current_price, vix_zone)
            else:
                st.info("No CALLS setups available. Cones may be too narrow (need ≥18 pts width).")
        
        with tab_puts:
            if puts_setups:
                for setup in puts_setups[:4]:
                    with st.container():
                        render_trade_card(setup, current_price, vix_zone)
            else:
                st.info("No PUTS setups available. Cones may be too narrow (need ≥18 pts width).")
        
        st.markdown("---")
        
        # ====================================================================
        # RTH SESSION TABLE
        # ====================================================================
        with st.container():
            render_rth_session_table(cones, current_price, session_date)
    
    # ========================================================================
    # RIGHT COLUMN
    # ========================================================================
    with right_col:
        
        # ====================================================================
        # CHECKLIST
        # ====================================================================
        with st.container():
            render_checklist(cones, current_price, vix_zone)
        
        st.markdown("---")
        
        # ====================================================================
        # PRIOR SESSION PIVOTS
        # ====================================================================
        with st.container():
            render_pivots_panel(high_price, low_price, close_price, prior_date)
        
        st.markdown("---")
        
        # ====================================================================
        # 10AM RAIL PRICES
        # ====================================================================
        with st.container():
            render_rails_panel(cones)
        
        # ====================================================================
        # LEGEND
        # ====================================================================
        with st.container():
            render_legend()
    
    # ========================================================================
    # FOOTER
    # ========================================================================
    st.markdown("---")
    
    footer_col1, footer_col2, footer_col3 = st.columns(3)
    
    with footer_col1:
        st.caption("**SPX Prophet v2.1** — Where Structure Becomes Foresight")
    
    with footer_col2:
        st.caption(f"Last updated: {get_ct_now().strftime('%I:%M:%S %p CT')}")
    
    with footer_col3:
        st.caption("Remember: 30-min CLOSE is everything! 🎯")


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    main()