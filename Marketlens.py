"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           SPX PROPHET v2.1                                    ║
║                    Where Structure Becomes Foresight                          ║
║                         LEGENDARY EDITION                                     ║
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
    
    Args:
        open_price: Today's SPX open
        high_cone: High cone from prior session
        low_cone: Low cone from prior session
        overnight_high_spx: Overnight ES high converted to SPX
        overnight_low_spx: Overnight ES low converted to SPX
    
    Returns:
        GapAnalysis with gap type and overnight pivot if applicable
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
            return False, f"VIX at {vix_zone.position_pct:.0f}% (need 20%-)"
    
    return True, "✓ CONFLUENCE - GO!"

# ============================================================================
# ============================================================================
#
#                        PART 2: CSS STYLES & UI COMPONENTS
#
# ============================================================================
# ============================================================================

# ============================================================================
# PREMIUM CSS INJECTION
# ============================================================================

def inject_premium_css():
    """
    Inject premium CSS styles into the Streamlit app.
    Light mode theme with gradients, shadows, and professional styling.
    """
    css = """
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
    
    /* ========== HEADER STYLES ========== */
    .prophet-header {
        background: linear-gradient(135deg, #1e40af 0%, #3b82f6 50%, #0ea5e9 100%);
        border-radius: 16px;
        padding: 32px;
        margin-bottom: 24px;
        text-align: center;
        box-shadow: 0 10px 40px rgba(59, 130, 246, 0.3);
    }
    
    .prophet-header h1 {
        font-size: 2.8rem;
        font-weight: 800;
        color: white;
        margin: 0;
        letter-spacing: 6px;
        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    
    .prophet-header p {
        color: rgba(255,255,255,0.9);
        font-size: 0.9rem;
        letter-spacing: 4px;
        margin-top: 8px;
        font-weight: 500;
    }
    
    /* ========== METRICS ROW ========== */
    .metrics-container {
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
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.12);
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
    
    .vix-title {
        font-size: 0.8rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 4px;
    }
    
    .vix-bias {
        font-size: 2rem;
        font-weight: 800;
    }
    
    .vix-bias-calls { color: #10b981; }
    .vix-bias-puts { color: #ef4444; }
    .vix-bias-neutral { color: #f59e0b; }
    
    /* ========== ZONE LADDER ========== */
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
        font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
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
        transition: transform 0.2s ease;
    }
    
    .trade-card:hover {
        transform: translateX(4px);
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
        font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
    }
    
    .trade-stat-label {
        font-size: 0.7rem;
        color: #64748b;
        text-transform: uppercase;
        margin-top: 4px;
        font-weight: 600;
    }
    
    /* ========== PROFIT/LOSS ROW ========== */
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
        border: 1px solid #6ee7b7;
    }
    
    .profit-value {
        font-size: 1.2rem;
        font-weight: 700;
        color: #059669;
    }
    
    .profit-label {
        font-size: 0.7rem;
        color: #065f46;
        font-weight: 600;
        margin-top: 4px;
    }
    
    .loss-box {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        border-radius: 10px;
        padding: 14px;
        text-align: center;
        border: 1px solid #fca5a5;
    }
    
    .loss-value {
        font-size: 1.2rem;
        font-weight: 700;
        color: #dc2626;
    }
    
    .loss-label {
        font-size: 0.7rem;
        color: #991b1b;
        font-weight: 600;
        margin-top: 4px;
    }
    
    .rr-box {
        background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
        border-radius: 10px;
        padding: 14px;
        text-align: center;
        border: 1px solid #93c5fd;
    }
    
    .rr-value {
        font-size: 1.2rem;
        font-weight: 700;
        color: #1d4ed8;
    }
    
    .rr-label {
        font-size: 0.7rem;
        color: #1e40af;
        font-weight: 600;
        margin-top: 4px;
    }
    
    /* ========== CHECKLIST PANEL ========== */
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
    
    .checklist-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: #1e293b;
    }
    
    .checklist-subtitle {
        font-size: 0.85rem;
        color: #475569;
        margin-top: 4px;
    }
    
    .checklist-item {
        display: flex;
        align-items: center;
        padding: 14px 16px;
        margin: 8px 0;
        border-radius: 10px;
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
    
    /* ========== DIRECTION BOX ========== */
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
    
    .direction-wait {
        background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
        border: 2px solid #f59e0b;
    }
    
    .direction-title {
        font-size: 0.8rem;
        color: #64748b;
        margin-bottom: 4px;
    }
    
    .direction-value {
        font-size: 1.8rem;
        font-weight: 800;
    }
    
    .direction-detail {
        font-size: 0.85rem;
        color: #64748b;
        margin-top: 4px;
    }
    
    /* ========== INFO PANELS ========== */
    .info-panel {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        margin-bottom: 16px;
    }
    
    .info-title {
        font-size: 0.8rem;
        color: #64748b;
        margin-bottom: 12px;
        font-weight: 500;
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
        font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
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
    
    /* ========== CONFLUENCE STATUS ========== */
    .confluence-box {
        padding: 16px;
        border-radius: 12px;
        margin-top: 12px;
        text-align: center;
    }
    
    .confluence-active {
        background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
        border: 2px solid #10b981;
    }
    
    .confluence-inactive {
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
        border: 2px solid #94a3b8;
    }
    
    /* ========== GAP DAY BANNER ========== */
    .gap-banner {
        padding: 12px 20px;
        border-radius: 10px;
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .gap-up {
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.2) 0%, rgba(16, 185, 129, 0.05) 100%);
        border: 1px solid #10b981;
    }
    
    .gap-down {
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.2) 0%, rgba(239, 68, 68, 0.05) 100%);
        border: 1px solid #ef4444;
    }
    
    /* ========== STREAMLIT OVERRIDES ========== */
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
    
    div[data-testid="stExpander"] {
        background: white;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# ============================================================================
# UI COMPONENT FUNCTIONS
# ============================================================================

def render_header():
    """Render the main header with title and subtitle."""
    html = """
    <div class="prophet-header">
        <h1>SPX PROPHET</h1>
        <p>WHERE STRUCTURE BECOMES FORESIGHT</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_metrics_row(current_price: float, vix_zone: Optional[VIXZone], 
                       nearest_distance: float, cone_width: float):
    """Render the top metrics row with 4 cards."""
    
    # VIX display
    vix_display = "—"
    vix_color = "#64748b"
    
    if vix_zone and vix_zone.current > 0:
        vix_display = f"{vix_zone.current:.2f} ({vix_zone.position_pct:.0f}%)"
        if vix_zone.trade_bias == "CALLS":
            vix_color = "#10b981"
        elif vix_zone.trade_bias == "PUTS":
            vix_color = "#ef4444"
        else:
            vix_color = "#f59e0b"
    
    # Distance color
    if nearest_distance <= 5:
        dist_color = "#10b981"
    elif nearest_distance <= AT_RAIL_THRESHOLD:
        dist_color = "#f59e0b"
    else:
        dist_color = "#64748b"
    
    # Width color
    if cone_width >= 25:
        width_color = "#10b981"
    elif cone_width >= MIN_CONE_WIDTH:
        width_color = "#f59e0b"
    else:
        width_color = "#ef4444"
    
    html = f"""
    <div class="metrics-container">
        <div class="metric-card">
            <div class="metric-value" style="color: #3b82f6;">{current_price:,.2f}</div>
            <div class="metric-label">SPX Price</div>
        </div>
        <div class="metric-card">
            <div class="metric-value" style="color: {vix_color};">{vix_display}</div>
            <div class="metric-label">VIX 30m Close</div>
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
    """
    st.markdown(html, unsafe_allow_html=True)


def render_vix_zone_panel(vix_zone: VIXZone):
    """Render the VIX Zone Analysis panel with ladder."""
    
    status, detail1, detail2 = get_vix_zone_status(vix_zone)
    
    # Determine bias class
    if vix_zone.trade_bias == "CALLS":
        bias_class = "vix-bias-calls"
    elif vix_zone.trade_bias == "PUTS":
        bias_class = "vix-bias-puts"
    else:
        bias_class = "vix-bias-neutral"
    
    # Build zone ladder HTML
    ladder_html = '<div class="zone-ladder">'
    
    # Levels above (PUTS extend targets) - show in reverse order (+4 at top)
    for i in range(3, -1, -1):
        level = vix_zone.levels_above[i]
        ladder_html += f'''
        <div class="zone-level zone-extend-up">
            <span style="color: #ef4444; font-weight: 600;">+{i+1}</span>
            <span style="color: #1e293b; font-weight: 600;">{level:.2f}</span>
            <span style="color: #64748b; font-size: 0.8rem;">PUTS extend</span>
        </div>
        '''
    
    # Resistance line (CALLS Entry - VIX rejected here, drops, SPX rises)
    ladder_html += f'''
    <div class="zone-level zone-resistance">
        <span style="color: #ef4444;">RES</span>
        <span style="color: #1e293b;">{vix_zone.resistance:.2f}</span>
        <span style="color: #10b981; font-weight: 600;">→ CALLS</span>
    </div>
    '''
    
    # Current VIX position (if within zone)
    if vix_zone.support - 0.05 <= vix_zone.current <= vix_zone.resistance + 0.05:
        ladder_html += f'''
        <div class="zone-level zone-current">
            <span style="color: #3b82f6;">NOW</span>
            <span style="color: #1e293b;">{vix_zone.current:.2f}</span>
            <span style="color: #3b82f6; font-weight: 600;">{vix_zone.position_pct:.0f}%</span>
        </div>
        '''
    
    # Support line (PUTS Entry - VIX bounces here, rises, SPX drops)
    ladder_html += f'''
    <div class="zone-level zone-support">
        <span style="color: #10b981;">SUP</span>
        <span style="color: #1e293b;">{vix_zone.support:.2f}</span>
        <span style="color: #ef4444; font-weight: 600;">→ PUTS</span>
    </div>
    '''
    
    # Levels below (CALLS extend targets)
    for i in range(4):
        level = vix_zone.levels_below[i]
        ladder_html += f'''
        <div class="zone-level zone-extend-down">
            <span style="color: #10b981; font-weight: 600;">-{i+1}</span>
            <span style="color: #1e293b; font-weight: 600;">{level:.2f}</span>
            <span style="color: #64748b; font-size: 0.8rem;">CALLS extend</span>
        </div>
        '''
    
    ladder_html += '</div>'
    
    # Complete panel HTML
    html = f"""
    <div class="vix-panel">
        <div class="vix-header">
            <div>
                <div class="vix-title">VIX Trade Compass</div>
                <div class="vix-bias {bias_class}">{vix_zone.trade_bias}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.75rem; color: #64748b;">Zone Size</div>
                <div style="font-size: 1.5rem; font-weight: 700; color: #1e293b;">{vix_zone.zone_size:.2f}</div>
            </div>
        </div>
        <div style="background: #f1f5f9; border-radius: 10px; padding: 14px; margin-bottom: 16px;">
            <div style="color: #1e293b; font-weight: 600; font-size: 1rem;">{status}</div>
            <div style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">{detail1}</div>
            <div style="color: #64748b; font-size: 0.85rem;">{detail2}</div>
        </div>
        {ladder_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_trade_card(setup: TradeSetup, current_price: float, vix_zone: Optional[VIXZone]):
    """Render a single trade setup card."""
    
    distance = abs(current_price - setup.entry_price)
    is_near = distance <= AT_RAIL_THRESHOLD
    
    # Card styling based on direction
    if setup.direction == "CALLS":
        card_class = "trade-card-calls"
        badge_class = "badge-calls"
        entry_color = "#10b981"
    else:
        card_class = "trade-card-puts"
        badge_class = "badge-puts"
        entry_color = "#ef4444"
    
    # Distance display
    if is_near:
        distance_html = '<span style="color: #10b981; font-weight: 700;">🎯 AT RAIL</span>'
    else:
        distance_html = f'<span style="color: #64748b;">{distance:.1f} pts away</span>'
    
    # VIX alignment check
    vix_status_html = ""
    if vix_zone and vix_zone.current > 0:
        is_aligned, reason = check_confluence(setup, vix_zone, current_price)
        if is_aligned:
            vix_status_html = f'<span style="color: #10b981; font-weight: 600;">✓ {reason}</span>'
        elif "VIX" in reason:
            vix_status_html = f'<span style="color: #f59e0b; font-weight: 600;">⚠ {reason}</span>'
        else:
            vix_status_html = f'<span style="color: #64748b;">{reason}</span>'
    else:
        vix_status_html = '<span style="color: #64748b;">Enter VIX data</span>'
    
    html = f"""
    <div class="trade-card {card_class}">
        <div class="trade-header">
            <div>
                <span class="trade-badge {badge_class}">{setup.direction}</span>
                <span style="color: #64748b; font-size: 0.9rem; margin-left: 12px; font-weight: 500;">{setup.cone_name} Cone</span>
            </div>
            {distance_html}
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
                <div class="profit-value">+${setup.expected_profit:.0f}</div>
                <div class="profit-label">PROFIT TARGET</div>
            </div>
            <div class="loss-box">
                <div class="loss-value">-${setup.max_loss:.0f}</div>
                <div class="loss-label">MAX LOSS</div>
            </div>
            <div class="rr-box">
                <div class="rr-value">{setup.rr_ratio:.1f}:1</div>
                <div class="rr-label">RISK:REWARD</div>
            </div>
        </div>
        
        <div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;">
            <div>
                <span style="color: #64748b; font-size: 0.8rem;">Rail: </span>
                <span style="color: #1e293b; font-weight: 600;">{setup.rail_type.upper()}</span>
                <span style="color: #64748b; font-size: 0.8rem; margin-left: 12px;">Delta: </span>
                <span style="color: #1e293b; font-weight: 600;">{setup.delta:.2f}</span>
            </div>
            <div>
                {vix_status_html}
            </div>
        </div>
        
        <div style="margin-top: 8px; font-size: 0.8rem; color: #64748b;">
            Required: {setup.vix_condition}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_checklist(cones: List[Cone], current_price: float, vix_zone: Optional[VIXZone]):
    """Render the trade validation checklist."""
    
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    cone_width = abs(nearest_cone.ascending_rail - nearest_cone.descending_rail) if nearest_cone else 0
    
    checks = []
    
    # 1. At Rail Check
    at_rail_ok = nearest_distance <= AT_RAIL_THRESHOLD
    at_rail_detail = "✓ In zone" if at_rail_ok else f"{nearest_distance:.1f} pts away"
    checks.append(("At Rail (≤8 pts)", at_rail_ok, at_rail_detail))
    
    # 2. Structure Check
    structure_ok = cone_width >= MIN_CONE_WIDTH
    structure_detail = f"{cone_width:.0f} pts" if structure_ok else f"Only {cone_width:.0f} pts"
    checks.append(("Structure (≥18 pts)", structure_ok, structure_detail))
    
    # 3. Active Cone Check
    active_ok = nearest_cone is not None
    active_detail = f"{nearest_cone.name}" if nearest_cone else "None"
    checks.append(("Active Cone", active_ok, active_detail))
    
    # 4. VIX Confluence Check
    # Determine expected trade direction based on rail type
    if nearest_rail_type == 'descending':
        expected_bias = 'CALLS'  # Descending rail = support = CALLS
    else:
        expected_bias = 'PUTS'   # Ascending rail = resistance = PUTS
    
    if vix_zone and vix_zone.current > 0:
        vix_ok = vix_zone.trade_bias == expected_bias
        vix_detail = f"{vix_zone.trade_bias} ({vix_zone.position_pct:.0f}%)"
    else:
        vix_ok = False
        vix_detail = "Enter data"
    checks.append((f"VIX Confluence ({expected_bias})", vix_ok, vix_detail))
    
    # Count passed checks
    passed = sum(1 for _, ok, _ in checks if ok)
    
    # Determine overall status
    if passed == 4:
        overall = "🟢 CONFLUENCE - GO!"
        header_class = "checklist-go"
    elif passed >= 3 and at_rail_ok:
        overall = "🟢 STRONG SETUP"
        header_class = "checklist-go"
    elif not at_rail_ok:
        overall = "🟡 WAIT - Not at Rail"
        header_class = "checklist-wait"
    elif not structure_ok:
        overall = "🔴 SKIP - Bad Structure"
        header_class = "checklist-skip"
    elif not vix_ok:
        overall = "🟡 WAIT - No VIX Confluence"
        header_class = "checklist-wait"
    else:
        overall = "🟡 CAUTION"
        header_class = "checklist-wait"
    
    # Determine trade direction
    if nearest_rail_type == 'descending':
        direction = "CALLS"
        dir_class = "direction-calls"
        dir_color = "#10b981"
    else:
        direction = "PUTS"
        dir_class = "direction-puts"
        dir_color = "#ef4444"
    
    # Build checklist items HTML
    items_html = ""
    for label, ok, detail in checks:
        icon = "✓" if ok else "✗"
        icon_color = "#10b981" if ok else "#ef4444"
        item_class = "checklist-pass" if ok else "checklist-fail"
        items_html += f"""
        <div class="checklist-item {item_class}">
            <span class="check-icon" style="color: {icon_color};">{icon}</span>
            <span class="check-label">{label}</span>
            <span class="check-detail">{detail}</span>
        </div>
        """
    
    html = f"""
    <div class="checklist-panel">
        <div class="checklist-header {header_class}">
            <div class="checklist-title">{overall}</div>
            <div class="checklist-subtitle">{passed}/4 checks passed</div>
        </div>
        
        {items_html}
        
        <div class="direction-box {dir_class}">
            <div class="direction-title">TRADE DIRECTION</div>
            <div class="direction-value" style="color: {dir_color};">{direction}</div>
            <div class="direction-detail">{nearest_cone.name if nearest_cone else 'N/A'} {nearest_rail_type} rail</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_pivots_panel(high_price: float, low_price: float, close_price: float, prior_date):
    """Render the prior session pivots panel."""
    
    date_str = prior_date.strftime('%b %d, %Y') if hasattr(prior_date, 'strftime') else str(prior_date)
    
    html = f"""
    <div class="info-panel">
        <div class="info-title">Prior Session: {date_str}</div>
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
    """
    st.markdown(html, unsafe_allow_html=True)


def render_rails_panel(cones: List[Cone]):
    """Render the 10am rail prices panel."""
    
    rails_html = ""
    for i, cone in enumerate(cones):
        border_style = "border-bottom: 1px solid #f1f5f9; margin-bottom: 12px; padding-bottom: 12px;" if i < len(cones) - 1 else ""
        
        # Ascending rail = resistance (PUTS entry), Descending rail = support (CALLS entry)
        asc_rail = cone.ascending_rail
        desc_rail = cone.descending_rail
        
        rails_html += f"""
        <div style="{border_style}">
            <div style="font-size: 0.8rem; color: #64748b; font-weight: 600; margin-bottom: 8px;">{cone.name} Cone</div>
            <div style="display: flex; justify-content: space-between;">
                <div>
                    <span style="color: #ef4444; font-weight: 600;">▲</span>
                    <span style="font-family: monospace; font-weight: 600;">{asc_rail:.2f}</span>
                    <span style="color: #64748b; font-size: 0.7rem;"> PUTS</span>
                </div>
                <div>
                    <span style="color: #10b981; font-weight: 600;">▼</span>
                    <span style="font-family: monospace; font-weight: 600;">{desc_rail:.2f}</span>
                    <span style="color: #64748b; font-size: 0.7rem;"> CALLS</span>
                </div>
            </div>
        </div>
        """
    
    html = f"""
    <div class="info-panel">
        <div class="info-title">10:00 AM Rail Prices</div>
        {rails_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_gap_banner(gap_analysis: GapAnalysis):
    """Render a banner if today is a gap day."""
    
    if gap_analysis.gap_type == 'NORMAL':
        return  # No banner for normal days
    
    if gap_analysis.gap_type == 'GAP_UP':
        banner_class = "gap-up"
        icon = "🚀"
        text = f"GAP UP DAY - Using overnight low as pivot: {gap_analysis.overnight_pivot:.2f}"
        detail = "Ascending rail from gap low acts as SUPPORT → CALLS entry"
    else:
        banner_class = "gap-down"
        icon = "📉"
        text = f"GAP DOWN DAY - Using overnight high as pivot: {gap_analysis.overnight_pivot:.2f}"
        detail = "Descending rail from gap high acts as RESISTANCE → PUTS entry"
    
    html = f"""
    <div class="gap-banner {banner_class}">
        <span style="font-size: 1.5rem;">{icon}</span>
        <div>
            <div style="font-weight: 700; color: #1e293b;">{text}</div>
            <div style="font-size: 0.85rem; color: #64748b;">{detail}</div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_legend():
    """Render the VIX-SPX trading legend."""
    
    html = """
    <div class="info-panel">
        <div class="info-title">VIX-SPX Confluence Rules</div>
        
        <div style="margin-bottom: 16px;">
            <div style="font-weight: 700; color: #10b981; margin-bottom: 4px;">🟢 CALLS Entry</div>
            <div style="font-size: 0.85rem; color: #64748b; padding-left: 24px;">
                VIX 30m closes at RESISTANCE<br>
                + SPX at DESCENDING rail (support)<br>
                → VIX drops, SPX rises
            </div>
        </div>
        
        <div style="margin-bottom: 16px;">
            <div style="font-weight: 700; color: #ef4444; margin-bottom: 4px;">🔴 PUTS Entry</div>
            <div style="font-size: 0.85rem; color: #64748b; padding-left: 24px;">
                VIX 30m closes at SUPPORT<br>
                + SPX at ASCENDING rail (resistance)<br>
                → VIX rises, SPX drops
            </div>
        </div>
        
        <div style="margin-bottom: 16px;">
            <div style="font-weight: 700; color: #f59e0b; margin-bottom: 4px;">⚠️ Breakout Up</div>
            <div style="font-size: 0.85rem; color: #64748b; padding-left: 24px;">
                VIX closes above resistance<br>
                → PUTS targets extend (+0.15/zone)
            </div>
        </div>
        
        <div>
            <div style="font-weight: 700; color: #3b82f6; margin-bottom: 4px;">⚠️ Breakout Down</div>
            <div style="font-size: 0.85rem; color: #64748b; padding-left: 24px;">
                VIX closes below support<br>
                → CALLS targets extend (-0.15/zone)
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_section_header(icon: str, title: str):
    """Render a section header with icon and title."""
    html = f"""
    <div class="section-header">
        <div class="section-icon">{icon}</div>
        <div class="section-title">{title}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

# ============================================================================
# ============================================================================
#
#                        PART 3: MAIN APPLICATION LOGIC
#
# ============================================================================
# ============================================================================

def render_rth_session_table(cones: List[Cone], current_price: float):
    """
    Render the RTH Session table showing rail prices at each 30-min block.
    8:30am and 10:00am rows are highlighted.
    """
    
    # Define time blocks from 8:30am to 3:00pm CT
    time_blocks = [
        ("8:30", time(8, 30)),
        ("9:00", time(9, 0)),
        ("9:30", time(9, 30)),
        ("10:00", time(10, 0)),
        ("10:30", time(10, 30)),
        ("11:00", time(11, 0)),
        ("11:30", time(11, 30)),
        ("12:00", time(12, 0)),
        ("12:30", time(12, 30)),
        ("1:00", time(13, 0)),
        ("1:30", time(13, 30)),
        ("2:00", time(14, 0)),
        ("2:30", time(14, 30)),
        ("3:00", time(15, 0)),
    ]
    
    # Build table header
    header_cells = '<th style="padding: 10px 8px; text-align: left; font-weight: 600; color: #64748b; border-bottom: 2px solid #e2e8f0;">Time</th>'
    for cone in cones:
        header_cells += f'''
        <th style="padding: 10px 8px; text-align: center; font-weight: 600; color: #64748b; border-bottom: 2px solid #e2e8f0;" colspan="2">
            {cone.name}
        </th>
        '''
    
    # Sub-header for Ascending/Descending
    sub_header = '<td></td>'
    for cone in cones:
        sub_header += '''
        <td style="padding: 4px 8px; text-align: center; font-size: 0.7rem; color: #94a3b8; font-weight: 600;">▲ ASC</td>
        <td style="padding: 4px 8px; text-align: center; font-size: 0.7rem; color: #94a3b8; font-weight: 600;">▼ DESC</td>
        '''
    
    # Build table rows
    rows_html = ""
    ct_now = get_ct_now()
    
    for time_label, time_val in time_blocks:
        # Create target datetime for this block
        target_dt = ct_now.replace(hour=time_val.hour, minute=time_val.minute, second=0, microsecond=0)
        
        # Determine if this row should be highlighted
        is_830 = time_val == time(8, 30)
        is_1000 = time_val == time(10, 0)
        
        if is_830:
            row_style = "background: linear-gradient(90deg, rgba(59, 130, 246, 0.15) 0%, rgba(59, 130, 246, 0.05) 100%); font-weight: 600;"
            time_badge = f'<span style="background: #3b82f6; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem;">{time_label}</span>'
        elif is_1000:
            row_style = "background: linear-gradient(90deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%); font-weight: 600;"
            time_badge = f'<span style="background: #10b981; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem;">{time_label}</span>'
        else:
            row_style = ""
            time_badge = f'<span style="color: #475569;">{time_label}</span>'
        
        row_html = f'<tr style="{row_style}"><td style="padding: 10px 8px;">{time_badge}</td>'
        
        for cone in cones:
            # Calculate rail prices at this time
            asc_price = calculate_rail_price(cone.pivot.price, cone.pivot.time, target_dt, True)
            desc_price = calculate_rail_price(cone.pivot.price, cone.pivot.time, target_dt, False)
            
            # Check if current price is near either rail
            near_asc = abs(current_price - asc_price) <= AT_RAIL_THRESHOLD
            near_desc = abs(current_price - desc_price) <= AT_RAIL_THRESHOLD
            
            asc_style = "color: #ef4444; font-weight: 700; background: rgba(239, 68, 68, 0.1); border-radius: 4px;" if near_asc else "color: #ef4444;"
            desc_style = "color: #10b981; font-weight: 700; background: rgba(16, 185, 129, 0.1); border-radius: 4px;" if near_desc else "color: #10b981;"
            
            row_html += f'''
            <td style="padding: 10px 8px; text-align: center; font-family: monospace; {asc_style}">{asc_price:.2f}</td>
            <td style="padding: 10px 8px; text-align: center; font-family: monospace; {desc_style}">{desc_price:.2f}</td>
            '''
        
        row_html += '</tr>'
        rows_html += row_html
    
    # Complete table HTML
    html = f"""
    <div class="info-panel" style="overflow-x: auto;">
        <div class="info-title">RTH Session Rail Prices</div>
        <div style="font-size: 0.75rem; color: #64748b; margin-bottom: 12px;">
            <span style="background: #3b82f6; color: white; padding: 2px 6px; border-radius: 3px; margin-right: 8px;">8:30</span> Market Open
            <span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 3px; margin-left: 12px; margin-right: 8px;">10:00</span> Primary Target
            <span style="color: #ef4444; margin-left: 12px;">▲ ASC = PUTS entry (resistance)</span>
            <span style="color: #10b981; margin-left: 12px;">▼ DESC = CALLS entry (support)</span>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
            <thead>
                <tr>{header_cells}</tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">{sub_header}</tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point."""
    
    # Page configuration
    st.set_page_config(
        page_title="SPX Prophet v2.1",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inject CSS
    inject_premium_css()
    
    # Render header
    render_header()
    
    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        # Session Date
        st.markdown("## 📅 Session Date")
        session_date = st.date_input(
            "Trading Date",
            value=get_ct_now().date(),
            help="Select the trading session date"
        )
        session_date_dt = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        
        ct_now = get_ct_now()
        st.caption(f"🕐 {ct_now.strftime('%I:%M %p CT')} | {ct_now.strftime('%A, %b %d')}")
        
        st.markdown("---")
        
        # ====================================================================
        # VIX ZONE INPUT
        # ====================================================================
        st.markdown("## 🧭 VIX Zone Setup")
        st.caption("From overnight session (5pm-2am)")
        st.caption("⚠️ Enter 30-minute CLOSE prices, not wicks!")
        
        # Initialize session state
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
            help="Overnight low CLOSE - PUTS entry when VIX closes here"
        )
        st.session_state.vix_support = vix_support
        
        vix_resistance = st.number_input(
            "VIX Resistance (Zone Top)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_resistance,
            step=0.01,
            format="%.2f",
            help="Overnight high CLOSE - CALLS entry when VIX closes here"
        )
        st.session_state.vix_resistance = vix_resistance
        
        vix_current = st.number_input(
            "Current VIX (30m Close)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_current,
            step=0.01,
            format="%.2f",
            help="Current 30-minute candle CLOSE from TradingView (VX1!)"
        )
        st.session_state.vix_current = vix_current
        
        # Calculate VIX zone
        vix_zone = None
        if vix_support > 0 and vix_resistance > 0:
            vix_zone = calculate_vix_zones(vix_support, vix_resistance, vix_current)
            
            # Zone size validation
            zone_size = vix_resistance - vix_support
            if 0.13 <= zone_size <= 0.17:
                st.success(f"✓ Valid 1-zone: {zone_size:.2f}")
            elif zone_size > 0:
                num_zones = round(zone_size / 0.15)
                st.info(f"~{num_zones} zones ({zone_size:.2f})")
            
            # Trade bias display
            if vix_zone.trade_bias == "CALLS":
                st.success("🟢 **CALLS** - VIX at resistance, will drop")
            elif vix_zone.trade_bias == "PUTS":
                st.error("🔴 **PUTS** - VIX at support, will rise")
            else:
                st.warning("🟡 **WAIT** - VIX mid-zone")
        
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
            st.caption(f"ES is **{es_offset:.2f}** pts ABOVE SPX")
        else:
            st.caption(f"ES is **{abs(es_offset):.2f}** pts BELOW SPX")
        
        st.markdown("---")
        
        # ====================================================================
        # OVERNIGHT PIVOTS (for gap days)
        # ====================================================================
        st.markdown("## 🌙 Overnight ES Pivots")
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
        
        # Convert to SPX
        if overnight_es_high > 0:
            overnight_spx_high = convert_es_to_spx(overnight_es_high, es_offset)
            st.caption(f"SPX equivalent high: **{overnight_spx_high:.2f}**")
        if overnight_es_low > 0:
            overnight_spx_low = convert_es_to_spx(overnight_es_low, es_offset)
            st.caption(f"SPX equivalent low: **{overnight_spx_low:.2f}**")
        
        st.markdown("---")
        
        # ====================================================================
        # MANUAL PIVOTS OVERRIDE
        # ====================================================================
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
                format="%.2f",
                help="Prior session high (wick)"
            )
            st.session_state.manual_low = st.number_input(
                "Low (Close-based)",
                value=st.session_state.manual_low,
                format="%.2f",
                help="Prior session low (close, not wick)"
            )
            st.session_state.manual_close = st.number_input(
                "Close",
                value=st.session_state.manual_close,
                format="%.2f",
                help="Prior session close"
            )
        
        st.markdown("---")
        
        # ====================================================================
        # QUICK REFERENCE
        # ====================================================================
        st.markdown("## 📖 Quick Reference")
        st.markdown("""
**VIX-SPX Confluence:**

🟢 **CALLS Entry:**
- VIX 30m closes at RESISTANCE
- SPX at DESCENDING rail
- VIX drops → SPX rises

🔴 **PUTS Entry:**
- VIX 30m closes at SUPPORT  
- SPX at ASCENDING rail
- VIX rises → SPX drops

**Rail Logic (Normal Days):**
- ▼ Descending = Support → CALLS
- ▲ Ascending = Resistance → PUTS

**Gap Days:**
- Gap UP: Ascending from overnight low = Support
- Gap DOWN: Descending from overnight high = Resistance

**Zone Size:** 0.15 per level
        """)
    
    # ========================================================================
    # MAIN CONTENT AREA
    # ========================================================================
    
    # Fetch data
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
        st.error("⚠️ Could not fetch prior session data. Please enable Manual Pivots in the sidebar.")
        return
    
    # Create target time (10:00am)
    target_time = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
    
    # Create pivots
    pivots = [
        Pivot(price=high_price, time=high_time, name='High'),
        Pivot(price=low_price, time=low_time, name='Low'),
        Pivot(price=close_price, 
              time=CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(15, 0))), 
              name='Close'),
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
    
    # Find nearest rail
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    cone_width = abs(nearest_cone.ascending_rail - nearest_cone.descending_rail) if nearest_cone else 0
    
    # Generate trade setups
    trade_setups = generate_trade_setups(cones, current_price, gap_analysis)
    
    # ========================================================================
    # RENDER METRICS ROW
    # ========================================================================
    render_metrics_row(current_price, vix_zone, nearest_distance, cone_width)
    
    # ========================================================================
    # GAP DAY BANNER
    # ========================================================================
    if gap_analysis and gap_analysis.gap_type != 'NORMAL':
        render_gap_banner(gap_analysis)
    
    # ========================================================================
    # MAIN LAYOUT - Two Columns
    # ========================================================================
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        # VIX Zone Panel
        if vix_zone and vix_zone.support > 0:
            render_section_header("🧭", "VIX Zone Analysis")
            render_vix_zone_panel(vix_zone)
        
        # Trade Setups
        render_section_header("🎯", "Trade Setups")
        
        # Sort setups by distance to entry
        calls_setups = sorted(
            [s for s in trade_setups if s.direction == 'CALLS'],
            key=lambda x: abs(current_price - x.entry_price)
        )
        puts_setups = sorted(
            [s for s in trade_setups if s.direction == 'PUTS'],
            key=lambda x: abs(current_price - x.entry_price)
        )
        
        tab1, tab2 = st.tabs(["📈 CALLS (Descending Rail = Support)", "📉 PUTS (Ascending Rail = Resistance)"])
        
        with tab1:
            if calls_setups:
                for setup in calls_setups[:4]:
                    render_trade_card(setup, current_price, vix_zone)
            else:
                st.info("No CALLS setups available (cones may be too narrow)")
        
        with tab2:
            if puts_setups:
                for setup in puts_setups[:4]:
                    render_trade_card(setup, current_price, vix_zone)
            else:
                st.info("No PUTS setups available (cones may be too narrow)")
        
        # RTH Session Table
        render_section_header("📊", "RTH Session Rails")
        render_rth_session_table(cones, current_price)
    
    with right_col:
        # Checklist
        render_section_header("📋", "Trade Checklist")
        render_checklist(cones, current_price, vix_zone)
        
        # Prior Session Pivots
        render_section_header("📍", "Prior Session Pivots")
        render_pivots_panel(high_price, low_price, close_price, prior_date)
        
        # 10am Rails
        render_section_header("📐", "10:00 AM Rails")
        render_rails_panel(cones)
        
        # Legend
        render_section_header("📚", "VIX-SPX Legend")
        render_legend()


# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    main()