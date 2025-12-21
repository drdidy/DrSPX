"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                           SPX PROPHET v4.0                                    ║
║                    The Complete 0DTE Trading System                           ║
║                                                                               ║
║  Integrates:                                                                  ║
║  • VIX 0.15 Zone System (with breakout timing logic)                         ║
║  • SPX Structural Cones (High, Low, Close + Secondary Pivots)                ║
║  • 30-Minute Candle Close Confirmation                                        ║
║  • Profit Targets, Strike Selection, R:R Calculations                        ║
║  • Choppy Day Detection                                                       ║
║  • Beautiful Light Theme UI                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta, time
import pytz
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
import streamlit.components.v1 as components

# ============================================================================
# CONFIGURATION - All times in CT (Chicago Time)
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')

# VIX Zone Constants
VIX_ZONE_SIZE = 0.15  # Default, but actual size calculated from inputs
VIX_ZONE_ESTABLISHMENT_START = time(17, 0)   # 5:00 PM CT
VIX_ZONE_ESTABLISHMENT_END = time(6, 0)       # 6:00 AM CT (next day)
VIX_RELIABLE_BREAKOUT_START = time(6, 0)      # 6:00 AM CT
VIX_RELIABLE_BREAKOUT_END = time(6, 30)       # 6:30 AM CT
VIX_DANGER_ZONE_START = time(6, 30)           # 6:30 AM CT
VIX_DANGER_ZONE_END = time(9, 30)             # 9:30 AM CT

# VIX Zone Size → Expected SPX Move (based on empirical data)
# Zone Size : (Min SPX pts, Max SPX pts)
VIX_TO_SPX_MOVE = {
    0.10: (35, 40),
    0.15: (40, 45),
    0.20: (45, 50),
    0.25: (50, 55),
    0.30: (55, 60),
}

# Cone Constants
SLOPE_PER_30MIN = 0.45  # Points per 30-min block
MIN_CONE_WIDTH = 18.0   # Minimum tradeable width
CONFLUENCE_THRESHOLD = 5.0

# Trade Constants
STOP_LOSS_PTS = 6.0
STRIKE_OTM_DISTANCE = 17.5    # OTM distance for ~0.33 delta
DELTA = 0.33                   # Contract moves $0.33 for every $1 SPX moves
CONTRACT_MULTIPLIER = 100      # Options multiplier

# Choppy Day Thresholds
LOW_VIX_THRESHOLD = 13.0
NARROW_CONE_THRESHOLD = 25.0

def get_ct_now() -> datetime:
    return datetime.now(CT_TZ)

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Pivot:
    price: float              # Main price (highest high for High pivot, lowest close for Low pivot)
    time: datetime
    name: str
    is_secondary: bool = False
    price_for_ascending: float = 0.0   # Price used for ascending rail
    price_for_descending: float = 0.0  # Price used for descending rail
    
    def __post_init__(self):
        # If specific prices not set, use main price
        if self.price_for_ascending == 0.0:
            self.price_for_ascending = self.price
        if self.price_for_descending == 0.0:
            self.price_for_descending = self.price

@dataclass
class Cone:
    name: str
    pivot: Pivot
    ascending_rail: float
    descending_rail: float
    width: float
    blocks: int

@dataclass
class VIXZone:
    bottom: float
    top: float
    current: float
    position_pct: float
    status: str  # CONTAINED, BREAKOUT_UP, BREAKOUT_DOWN
    bias: str    # CALLS, PUTS, WAIT, UNKNOWN
    breakout_time: str  # RELIABLE, DANGER, RTH, NONE
    zones_above: List[float]
    zones_below: List[float]
    zone_size: float = 0.15  # Actual zone size
    expected_move: tuple = (40, 45)  # Expected SPX move range in points

@dataclass
class TradeSetup:
    direction: str
    cone_name: str
    cone_width: float
    entry: float
    stop: float
    target_12: float      # 12.5% of cone
    target_25: float      # 25% of cone
    target_50: float      # 50% of cone (realistic max)
    strike: int
    # SPX points at each target
    spx_pts_12: float     # SPX points gained at 12.5%
    spx_pts_25: float     # SPX points gained at 25%
    spx_pts_50: float     # SPX points gained at 50%
    # Estimated profits per contract (SPX move × 0.33 delta × $100)
    profit_12: float
    profit_25: float
    profit_50: float
    risk_per_contract: float
    rr_ratio: float
    distance: float
    is_active: bool = False

@dataclass
class DayAssessment:
    tradeable: bool
    score: int  # 0-100
    reasons: List[str]
    warnings: List[str]
    recommendation: str  # FULL, REDUCED, SKIP

# ============================================================================
# VIX ZONE ANALYSIS
# ============================================================================

def analyze_vix(bottom: float, top: float, current: float, breakout_hour: int = None) -> VIXZone:
    """
    Analyze VIX position and determine bias.
    
    IMPORTANT: Zone size is whatever is established between 5pm-6am CT.
    Could be 0.10, 0.15, 0.20, 0.25, 0.30, etc. - calculated from bottom/top inputs.
    Extension zones are MULTIPLES of that same zone size.
    
    Zone size indicates expected SPX move:
    - 0.10 = 35-40 pts
    - 0.15 = 40-45 pts
    - 0.20 = 45-50 pts
    - 0.25 = 50-55 pts
    - 0.30 = 55-60 pts
    """
    
    # Calculate zone size from inputs (NOT fixed!)
    zone_size = round(top - bottom, 2) if (top > 0 and bottom > 0 and top > bottom) else 0.15
    
    # Determine expected SPX move based on zone size
    if zone_size <= 0.10:
        expected_move = (35, 40)
    elif zone_size <= 0.15:
        expected_move = (40, 45)
    elif zone_size <= 0.20:
        expected_move = (45, 50)
    elif zone_size <= 0.25:
        expected_move = (50, 55)
    else:
        expected_move = (55, 60)
    
    # Extension zones are multiples of the SAME zone size
    zones_above = [round(top + (i * zone_size), 2) for i in range(1, 5)]
    zones_below = [round(bottom - (i * zone_size), 2) for i in range(1, 5)]
    
    # Default values
    if bottom <= 0 or top <= 0:
        return VIXZone(
            bottom=0, top=0, current=current,
            position_pct=0, status='NO_DATA', bias='UNKNOWN',
            breakout_time='NONE', zones_above=zones_above, zones_below=zones_below,
            zone_size=zone_size, expected_move=expected_move
        )
    
    if current <= 0:
        return VIXZone(
            bottom=bottom, top=top, current=0,
            position_pct=0, status='WAITING', bias='UNKNOWN',
            breakout_time='NONE', zones_above=zones_above, zones_below=zones_below,
            zone_size=zone_size, expected_move=expected_move
        )
    
    # Calculate position percentage
    if zone_size > 0:
        position_pct = ((current - bottom) / zone_size) * 100
    else:
        position_pct = 50
    
    # Determine breakout timing reliability
    ct_now = get_ct_now()
    current_time = ct_now.time()
    
    if time(6, 0) <= current_time < time(6, 30):
        breakout_time = 'RELIABLE'
    elif time(6, 30) <= current_time < time(9, 30):
        breakout_time = 'DANGER'
    else:
        breakout_time = 'RTH'
    
    # Determine status and bias
    if current > top:
        status = 'BREAKOUT_UP'
        bias = 'PUTS'  # VIX up = SPX down
        position_pct = 100 + ((current - top) / zone_size * 50) if zone_size > 0 else 100
    elif current < bottom:
        status = 'BREAKOUT_DOWN'
        bias = 'CALLS'  # VIX down = SPX up
        position_pct = -((bottom - current) / zone_size * 50) if zone_size > 0 else 0
    else:
        status = 'CONTAINED'
        if position_pct >= 75:
            bias = 'CALLS'  # VIX at top, will fall = SPX up
        elif position_pct <= 25:
            bias = 'PUTS'   # VIX at bottom, will rise = SPX down
        else:
            bias = 'WAIT'   # Mid-zone, no edge
    
    return VIXZone(
        bottom=bottom, top=top, current=current,
        position_pct=position_pct, status=status, bias=bias,
        breakout_time=breakout_time, zones_above=zones_above, zones_below=zones_below,
        zone_size=zone_size, expected_move=expected_move
    )

# ============================================================================
# CONE CALCULATIONS
# ============================================================================

def count_blocks(start: datetime, end: datetime) -> int:
    """
    Count 30-minute blocks between two times, SKIPPING WEEKENDS.
    
    Market schedule:
    - Friday: Market closes 4pm CT, futures resume Sunday 5pm CT
    - Saturday/Sunday before 5pm: DOES NOT COUNT
    - Sunday 5pm CT onwards: Counts as continuation from Friday 4pm
    
    So Friday 4pm → Sunday 5pm is treated as NO TIME PASSED.
    Monday is the next trading day after Friday.
    """
    if end <= start:
        return 1
    
    # Get day of week (0=Monday, 4=Friday, 5=Saturday, 6=Sunday)
    start_dow = start.weekday()
    end_dow = end.weekday()
    
    # If same day or no weekend in between, simple calculation
    if start_dow <= 4 and end_dow <= 4 and (end - start).days < 2:
        # Check if we cross a weekend
        if end_dow >= start_dow or (end - start).days == 0:
            diff = (end - start).total_seconds()
            blocks = int(diff // 1800)
            return max(blocks, 1)
    
    # Weekend handling: Friday → Monday calculation
    # We need to subtract the dead time (Friday 4pm to Sunday 5pm = 49 hours)
    
    total_seconds = (end - start).total_seconds()
    
    # Count how many weekends are in between
    days_between = (end.date() - start.date()).days
    
    # Calculate weekend hours to subtract
    weekend_hours = 0
    
    current = start
    while current.date() < end.date():
        current_dow = current.weekday()
        
        # If Friday, we skip to Sunday 5pm
        if current_dow == 4:  # Friday
            # Friday 4pm to Sunday 5pm = 49 hours of dead time
            friday_4pm = current.replace(hour=16, minute=0, second=0, microsecond=0)
            if current <= friday_4pm:
                weekend_hours += 49  # Skip Fri 4pm to Sun 5pm
        
        current = current + timedelta(days=1)
    
    # Subtract weekend dead time
    adjusted_seconds = total_seconds - (weekend_hours * 3600)
    adjusted_seconds = max(adjusted_seconds, 1800)  # At least 1 block
    
    blocks = int(adjusted_seconds // 1800)
    return max(blocks, 1)

def count_blocks_v2(pivot_time: datetime, eval_time: datetime) -> int:
    """
    Simplified block counting for trading days.
    
    For Monday eval with Friday pivot:
    - Count blocks from pivot to Friday 4pm (market close)
    - Add blocks from Sunday 5pm to Monday eval time
    - Skip Saturday and Sunday before 5pm entirely
    """
    if eval_time <= pivot_time:
        return 1
    
    pivot_dow = pivot_time.weekday()
    eval_dow = eval_time.weekday()
    
    # Same day - simple calculation
    if pivot_time.date() == eval_time.date():
        diff = (eval_time - pivot_time).total_seconds()
        return max(int(diff // 1800), 1)
    
    # Check if we're spanning a weekend (Friday pivot, Monday eval)
    # or any case where pivot is Fri or earlier and eval is Mon or later
    
    total_blocks = 0
    
    # If pivot is on Friday (4) or earlier, and eval is Monday (0) or later
    # AND there's a weekend between them
    spans_weekend = False
    
    if pivot_dow <= 4:  # Pivot is Mon-Fri
        # Check if eval is after the weekend
        days_diff = (eval_time.date() - pivot_time.date()).days
        if days_diff >= 2:
            # Could span weekend - check if Friday and Monday are involved
            temp = pivot_time
            while temp.date() < eval_time.date():
                if temp.weekday() == 4:  # Found a Friday
                    spans_weekend = True
                    break
                temp = temp + timedelta(days=1)
    
    if spans_weekend:
        # Find the Friday in between
        friday = pivot_time
        while friday.weekday() != 4:
            friday = friday + timedelta(days=1)
        
        # Friday 4pm CT (market close)
        friday_close = friday.replace(hour=16, minute=0, second=0, microsecond=0)
        if friday_close.tzinfo is None:
            friday_close = CT_TZ.localize(friday_close)
        
        # Sunday 5pm CT (futures reopen)
        sunday_open = friday + timedelta(days=2)
        sunday_open = sunday_open.replace(hour=17, minute=0, second=0, microsecond=0)
        if sunday_open.tzinfo is None:
            sunday_open = CT_TZ.localize(sunday_open)
        
        # Blocks from pivot to Friday close
        if pivot_time < friday_close:
            blocks_to_friday = (friday_close - pivot_time).total_seconds() // 1800
            total_blocks += int(blocks_to_friday)
        
        # Blocks from Sunday open to eval
        if eval_time > sunday_open:
            blocks_from_sunday = (eval_time - sunday_open).total_seconds() // 1800
            total_blocks += int(blocks_from_sunday)
        
        return max(total_blocks, 1)
    
    else:
        # No weekend - simple calculation
        diff = (eval_time - pivot_time).total_seconds()
        return max(int(diff // 1800), 1)

def build_cones(pivots: List[Pivot], eval_time: datetime) -> List[Cone]:
    """
    Build cones from pivots at evaluation time.
    
    IMPORTANT: 
    - Pivot candle is NOT counted - blocks start from the NEXT candle
    - High pivot: Ascending uses high price, Descending uses high close
    - Low pivot: Both rails use lowest close (no wicks)
    - Close pivot: Both rails use close price
    """
    cones = []
    for pivot in pivots:
        # Add 30 minutes to pivot time to skip the pivot candle itself
        # Counting starts from the NEXT candle after the pivot
        start_time = pivot.time + timedelta(minutes=30)
        
        blocks = count_blocks_v2(start_time, eval_time)
        
        # Use specific prices for each rail
        ascending = pivot.price_for_ascending + (blocks * SLOPE_PER_30MIN)
        descending = pivot.price_for_descending - (blocks * SLOPE_PER_30MIN)
        width = ascending - descending
        
        cones.append(Cone(
            name=pivot.name,
            pivot=pivot,
            ascending_rail=round(ascending, 2),
            descending_rail=round(descending, 2),
            width=round(width, 2),
            blocks=blocks
        ))
    return cones

def find_nearest(price: float, cones: List[Cone]) -> Tuple[Cone, str, float]:
    """Find nearest rail to current price."""
    nearest = None
    rail_type = ""
    min_dist = float('inf')
    
    for cone in cones:
        d_asc = abs(price - cone.ascending_rail)
        d_desc = abs(price - cone.descending_rail)
        
        if d_asc < min_dist:
            min_dist = d_asc
            nearest = cone
            rail_type = "ascending"
        if d_desc < min_dist:
            min_dist = d_desc
            nearest = cone
            rail_type = "descending"
    
    return nearest, rail_type, round(min_dist, 2)

def find_active_cone(price: float, cones: List[Cone]) -> Dict:
    """
    Determine which cone the current price is inside of, or nearest to.
    
    Returns dict with:
    - inside_cone: The cone price is currently inside (between rails), or None
    - nearest_cone: Nearest cone if not inside any
    - nearest_rail: 'ascending' or 'descending'
    - distance: Distance to nearest rail
    - position: 'inside', 'above_all', 'below_all', 'between_cones'
    """
    result = {
        'inside_cone': None,
        'nearest_cone': None,
        'nearest_rail': None,
        'distance': 0,
        'position': 'unknown',
        'at_rail': False,
        'rail_type': None
    }
    
    if not cones:
        return result
    
    # Check if price is inside any cone
    for cone in cones:
        if cone.descending_rail <= price <= cone.ascending_rail:
            result['inside_cone'] = cone
            result['position'] = 'inside'
            
            # Check how close to each rail
            dist_to_asc = cone.ascending_rail - price
            dist_to_desc = price - cone.descending_rail
            
            # Within 3 points of a rail = "at rail"
            if dist_to_asc <= 3:
                result['at_rail'] = True
                result['rail_type'] = 'ascending'
                result['distance'] = round(dist_to_asc, 2)
            elif dist_to_desc <= 3:
                result['at_rail'] = True
                result['rail_type'] = 'descending'
                result['distance'] = round(dist_to_desc, 2)
            else:
                # In middle of cone
                result['distance'] = round(min(dist_to_asc, dist_to_desc), 2)
            
            return result
    
    # Not inside any cone - find nearest
    nearest, rail_type, min_dist = find_nearest(price, cones)
    result['nearest_cone'] = nearest
    result['nearest_rail'] = rail_type
    result['distance'] = min_dist
    
    # Determine if above all or below all
    all_ascending = [c.ascending_rail for c in cones]
    all_descending = [c.descending_rail for c in cones]
    
    if price > max(all_ascending):
        result['position'] = 'above_all'
    elif price < min(all_descending):
        result['position'] = 'below_all'
    else:
        result['position'] = 'between_cones'
    
    return result

# ============================================================================
# TRADE SETUP GENERATION
# ============================================================================

def generate_setups(cones: List[Cone], current_price: float, vix_bias: str) -> List[TradeSetup]:
    """
    Generate trade setups with realistic targets and profit estimates.
    
    TARGETS: 12.5%, 25%, 50% of cone width (realistic - SPX rarely does full cone)
    
    PROFIT CALCULATION:
    - SPX move × Delta (0.33) × $100 = Estimated profit per contract
    
    Example (40pt cone, 50% target = 20pt SPX move):
    - 20 pts × 0.33 × 100 = $660/contract estimated profit
    """
    setups = []
    
    for cone in cones:
        if cone.width < MIN_CONE_WIDTH:
            continue
        
        # ========== CALLS SETUP (Enter at Descending Rail) ==========
        entry_c = cone.descending_rail
        dist_c = abs(current_price - entry_c)
        
        # SPX points at each target level
        spx_pts_12_c = cone.width * 0.125  # 12.5%
        spx_pts_25_c = cone.width * 0.25   # 25%
        spx_pts_50_c = cone.width * 0.50   # 50%
        
        # Target prices
        target_12_c = round(entry_c + spx_pts_12_c, 2)
        target_25_c = round(entry_c + spx_pts_25_c, 2)
        target_50_c = round(entry_c + spx_pts_50_c, 2)
        
        # Strike: ~17.5 pts OTM from entry for ~0.33 delta
        strike_c = int(entry_c + STRIKE_OTM_DISTANCE)
        strike_c = ((strike_c + 4) // 5) * 5  # Round to nearest 5
        
        # Estimated profits: SPX move × delta × $100
        profit_12_c = round(spx_pts_12_c * DELTA * CONTRACT_MULTIPLIER, 0)
        profit_25_c = round(spx_pts_25_c * DELTA * CONTRACT_MULTIPLIER, 0)
        profit_50_c = round(spx_pts_50_c * DELTA * CONTRACT_MULTIPLIER, 0)
        risk_c = round(STOP_LOSS_PTS * DELTA * CONTRACT_MULTIPLIER, 0)
        
        # R:R ratio (12.5% profit vs risk - most conservative)
        rr_c = round(profit_12_c / risk_c, 1) if risk_c > 0 else 0
        
        setups.append(TradeSetup(
            direction='CALLS',
            cone_name=cone.name,
            cone_width=cone.width,
            entry=entry_c,
            stop=round(entry_c - STOP_LOSS_PTS, 2),
            target_12=target_12_c,
            target_25=target_25_c,
            target_50=target_50_c,
            strike=strike_c,
            spx_pts_12=round(spx_pts_12_c, 1),
            spx_pts_25=round(spx_pts_25_c, 1),
            spx_pts_50=round(spx_pts_50_c, 1),
            profit_12=profit_12_c,
            profit_25=profit_25_c,
            profit_50=profit_50_c,
            risk_per_contract=risk_c,
            rr_ratio=rr_c,
            distance=round(dist_c, 2),
            is_active=(dist_c <= 5 and vix_bias == 'CALLS')
        ))
        
        # ========== PUTS SETUP (Enter at Ascending Rail) ==========
        entry_p = cone.ascending_rail
        dist_p = abs(current_price - entry_p)
        
        # SPX points at each target level
        spx_pts_12_p = cone.width * 0.125  # 12.5%
        spx_pts_25_p = cone.width * 0.25   # 25%
        spx_pts_50_p = cone.width * 0.50   # 50%
        
        # Target prices (going DOWN for puts)
        target_12_p = round(entry_p - spx_pts_12_p, 2)
        target_25_p = round(entry_p - spx_pts_25_p, 2)
        target_50_p = round(entry_p - spx_pts_50_p, 2)
        
        # Strike: ~17.5 pts OTM from entry for ~0.33 delta
        strike_p = int(entry_p - STRIKE_OTM_DISTANCE)
        strike_p = (strike_p // 5) * 5  # Round to nearest 5
        
        # Estimated profits: SPX move × delta × $100
        profit_12_p = round(spx_pts_12_p * DELTA * CONTRACT_MULTIPLIER, 0)
        profit_25_p = round(spx_pts_25_p * DELTA * CONTRACT_MULTIPLIER, 0)
        profit_50_p = round(spx_pts_50_p * DELTA * CONTRACT_MULTIPLIER, 0)
        risk_p = round(STOP_LOSS_PTS * DELTA * CONTRACT_MULTIPLIER, 0)
        
        rr_p = round(profit_12_p / risk_p, 1) if risk_p > 0 else 0
        
        setups.append(TradeSetup(
            direction='PUTS',
            cone_name=cone.name,
            cone_width=cone.width,
            entry=entry_p,
            stop=round(entry_p + STOP_LOSS_PTS, 2),
            target_12=target_12_p,
            target_25=target_25_p,
            target_50=target_50_p,
            strike=strike_p,
            spx_pts_12=round(spx_pts_12_p, 1),
            spx_pts_25=round(spx_pts_25_p, 1),
            spx_pts_50=round(spx_pts_50_p, 1),
            profit_12=profit_12_p,
            profit_25=profit_25_p,
            profit_50=profit_50_p,
            risk_per_contract=risk_p,
            rr_ratio=rr_p,
            distance=round(dist_p, 2),
            is_active=(dist_p <= 5 and vix_bias == 'PUTS')
        ))
    
    # Sort by distance to current price
    setups.sort(key=lambda s: s.distance)
    return setups

# ============================================================================
# CHOPPY DAY DETECTION
# ============================================================================

def assess_day(vix: VIXZone, cones: List[Cone], current_price: float) -> DayAssessment:
    """Assess if today is tradeable or choppy."""
    score = 100
    reasons = []
    warnings = []
    
    # Check VIX position
    if vix.bias == 'WAIT':
        score -= 40
        warnings.append("VIX mid-zone (40-60%) - no clear edge")
    elif vix.bias in ['CALLS', 'PUTS']:
        reasons.append(f"VIX at edge ({vix.position_pct:.0f}%) - clear {vix.bias} bias")
    
    # Check breakout timing
    if vix.status in ['BREAKOUT_UP', 'BREAKOUT_DOWN']:
        if vix.breakout_time == 'RELIABLE':
            reasons.append("VIX breakout in reliable window (2-6:30am CT)")
        elif vix.breakout_time == 'DANGER':
            score -= 25
            warnings.append("⚠️ VIX breakout in DANGER window (6:30-9:30am) - reversal risk!")
    
    # Check cone widths
    if cones:
        max_width = max(c.width for c in cones)
        avg_width = sum(c.width for c in cones) / len(cones)
        
        if max_width < NARROW_CONE_THRESHOLD:
            score -= 30
            warnings.append(f"Narrow cones (max {max_width:.0f} pts) - limited profit potential")
        else:
            reasons.append(f"Good cone width ({max_width:.0f} pts)")
    
    # Check overall VIX level
    if vix.current > 0 and vix.current < LOW_VIX_THRESHOLD:
        score -= 15
        warnings.append(f"Low VIX ({vix.current:.2f}) - expect smaller moves")
    
    # Determine recommendation
    if score >= 70:
        tradeable = True
        recommendation = 'FULL'
    elif score >= 50:
        tradeable = True
        recommendation = 'REDUCED'
    else:
        tradeable = False
        recommendation = 'SKIP'
    
    return DayAssessment(
        tradeable=tradeable,
        score=max(0, score),
        reasons=reasons,
        warnings=warnings,
        recommendation=recommendation
    )

# ============================================================================
# HISTORICAL TRACKING - What Actually Happened
# ============================================================================

@st.cache_data(ttl=300)
def fetch_session_candles(session_date: datetime) -> Optional[pd.DataFrame]:
    """Fetch intraday candles for a session to analyze what happened."""
    try:
        spx = yf.Ticker("^GSPC")
        
        # Need to fetch a range that includes the session date
        start = session_date
        end = session_date + timedelta(days=1)
        
        df = spx.history(start=start, end=end, interval='5m')
        
        if df.empty:
            return None
        
        df.index = df.index.tz_convert(CT_TZ)
        
        # Filter to RTH only (8:30 AM - 3:00 PM CT)
        rth_start = time(8, 30)
        rth_end = time(15, 0)
        df = df[(df.index.time >= rth_start) & (df.index.time <= rth_end)]
        
        return df
    except:
        return None

@dataclass
class TradeResult:
    setup: TradeSetup
    triggered: bool
    trigger_time: Optional[str]
    trigger_price: Optional[float]
    outcome: str  # 'WIN_12', 'WIN_25', 'WIN_50', 'STOPPED', 'OPEN', 'NO_TRIGGER'
    exit_time: Optional[str]
    exit_price: Optional[float]
    profit: float
    max_favorable: float  # Best price reached in our direction
    max_adverse: float    # Worst price reached against us

def analyze_historical_trades(setups: List[TradeSetup], candles: pd.DataFrame, vix_bias: str) -> List[TradeResult]:
    """
    Analyze what actually happened to each setup on a historical date.
    
    IMPORTANT LOGIC (using new 12.5%, 25%, 50% targets):
    - If price hits 12.5% target FIRST → WIN (we take profit)
    - If price hits STOP FIRST (before 12.5%) → LOSS
    - We track the BEST target reached (12.5%, 25%, or 50%)
    """
    results = []
    
    if candles is None or candles.empty:
        return results
    
    session_high = candles['High'].max()
    session_low = candles['Low'].min()
    
    for setup in setups:
        triggered = False
        trigger_time = None
        trigger_price = None
        outcome = 'NO_TRIGGER'
        exit_time = None
        exit_price = None
        profit = 0.0
        max_favorable = 0.0
        max_adverse = 0.0
        
        if setup.direction == 'CALLS':
            # CALLS: Entry at descending rail (buy when price drops to entry)
            if session_low <= setup.entry:
                triggered = True
                
                # Find when it triggered
                for idx, row in candles.iterrows():
                    if row['Low'] <= setup.entry:
                        trigger_time = idx.strftime('%H:%M')
                        trigger_price = setup.entry
                        break
                
                if triggered:
                    trigger_found = False
                    highest_after = setup.entry
                    lowest_after = setup.entry
                    best_target_hit = None  # Track best target reached
                    
                    for idx, row in candles.iterrows():
                        if not trigger_found:
                            if row['Low'] <= setup.entry:
                                trigger_found = True
                            continue
                        
                        highest_after = max(highest_after, row['High'])
                        lowest_after = min(lowest_after, row['Low'])
                        
                        # Check targets FIRST (12.5% is a win!)
                        if row['High'] >= setup.target_50:
                            best_target_hit = '50'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_50
                        elif row['High'] >= setup.target_25 and best_target_hit != '50':
                            best_target_hit = '25'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_25
                        elif row['High'] >= setup.target_12 and best_target_hit not in ['25', '50']:
                            best_target_hit = '12'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_12
                        
                        # Check stop ONLY if no target hit yet
                        if best_target_hit is None and row['Low'] <= setup.stop:
                            outcome = 'STOPPED'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.stop
                            profit = -setup.risk_per_contract
                            break
                    
                    # Set outcome based on best target hit
                    if best_target_hit == '50':
                        outcome = 'WIN_50'
                        profit = setup.profit_50
                    elif best_target_hit == '25':
                        outcome = 'WIN_25'
                        profit = setup.profit_25
                    elif best_target_hit == '12':
                        outcome = 'WIN_12'
                        profit = setup.profit_12
                    elif outcome != 'STOPPED':
                        outcome = 'OPEN'  # Triggered but no target or stop hit
                    
                    max_favorable = highest_after - setup.entry
                    max_adverse = setup.entry - lowest_after
        
        else:  # PUTS
            # PUTS: Entry at ascending rail (buy when price rises to entry)
            if session_high >= setup.entry:
                triggered = True
                
                # Find when it triggered
                for idx, row in candles.iterrows():
                    if row['High'] >= setup.entry:
                        trigger_time = idx.strftime('%H:%M')
                        trigger_price = setup.entry
                        break
                
                if triggered:
                    trigger_found = False
                    lowest_after = setup.entry
                    highest_after = setup.entry
                    best_target_hit = None
                    
                    for idx, row in candles.iterrows():
                        if not trigger_found:
                            if row['High'] >= setup.entry:
                                trigger_found = True
                            continue
                        
                        lowest_after = min(lowest_after, row['Low'])
                        highest_after = max(highest_after, row['High'])
                        
                        # Check targets FIRST (12.5% is a win!)
                        if row['Low'] <= setup.target_50:
                            best_target_hit = '50'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_50
                        elif row['Low'] <= setup.target_25 and best_target_hit != '50':
                            best_target_hit = '25'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_25
                        elif row['Low'] <= setup.target_12 and best_target_hit not in ['25', '50']:
                            best_target_hit = '12'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_12
                        
                        # Check stop ONLY if no target hit yet
                        if best_target_hit is None and row['High'] >= setup.stop:
                            outcome = 'STOPPED'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.stop
                            profit = -setup.risk_per_contract
                            break
                    
                    # Set outcome based on best target hit
                        # Check stop ONLY if no target hit yet
                        if best_target_hit is None and row['High'] >= setup.stop:
                            outcome = 'STOPPED'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.stop
                            profit = -setup.risk_per_contract
                            break
                    
                    # Set outcome based on best target hit
                    if best_target_hit == '50':
                        outcome = 'WIN_50'
                        profit = setup.profit_50
                    elif best_target_hit == '25':
                        outcome = 'WIN_25'
                        profit = setup.profit_25
                    elif best_target_hit == '12':
                        outcome = 'WIN_12'
                        profit = setup.profit_12
                    elif outcome != 'STOPPED':
                        outcome = 'OPEN'
                    
                    max_favorable = setup.entry - lowest_after
                    max_adverse = highest_after - setup.entry
        
        results.append(TradeResult(
            setup=setup,
            triggered=triggered,
            trigger_time=trigger_time,
            trigger_price=trigger_price,
            outcome=outcome,
            exit_time=exit_time,
            exit_price=exit_price,
            profit=profit,
            max_favorable=max_favorable,
            max_adverse=max_adverse
        ))
    
    return results

@st.cache_data(ttl=300)
def fetch_prior_session(session_date: datetime) -> Optional[Dict]:
    """
    Fetch prior session High, Low, Close with specific prices for rails.
    
    HIGH PIVOT:
    - Ascending rail uses: Highest PRICE (including wick)
    - Descending rail uses: Highest 30-min CLOSE
    
    LOW PIVOT:
    - Ascending rail uses: Lowest 30-min CLOSE (no wicks)
    - Descending rail uses: Lowest 30-min CLOSE (no wicks)
    
    NOTE: For Monday, this returns FRIDAY's data since market is closed Sat/Sun.
    """
    try:
        spx = yf.Ticker("^GSPC")
        end = session_date
        start = end - timedelta(days=10)
        
        df_daily = spx.history(start=start, end=end, interval='1d')
        if len(df_daily) < 1:
            return None
        
        last = df_daily.iloc[-1]
        prior_date = df_daily.index[-1]
        
        # Get intraday 30-min data for pivot times and close prices
        df_intra = spx.history(start=start, end=end, interval='30m')
        
        # Default values
        high_price = float(last['High'])      # Highest price (with wick)
        high_close = float(last['High'])      # Will be updated to highest close
        low_price = float(last['Low'])        # Lowest price (with wick) - not used
        low_close = float(last['Low'])        # Lowest close - used for both rails
        
        high_time = CT_TZ.localize(datetime.combine(prior_date.date(), time(12, 0)))
        low_time = CT_TZ.localize(datetime.combine(prior_date.date(), time(12, 0)))
        
        if not df_intra.empty:
            df_intra.index = df_intra.index.tz_convert(CT_TZ)
            day_data = df_intra[df_intra.index.date == prior_date.date()]
            
            if not day_data.empty:
                # HIGH PIVOT
                # - Time of highest HIGH (wick included)
                high_time = day_data['High'].idxmax()
                high_price = float(day_data['High'].max())
                # - Highest CLOSE for descending rail
                high_close = float(day_data['Close'].max())
                
                # LOW PIVOT
                # - Time of lowest CLOSE (we use close, not low wick)
                low_close_idx = day_data['Close'].idxmin()
                low_time = low_close_idx
                low_close = float(day_data['Close'].min())
        
        return {
            'high': high_price,           # Highest price (for ascending rail of High pivot)
            'high_close': high_close,     # Highest close (for descending rail of High pivot)
            'low': low_close,             # Lowest close (for both rails of Low pivot)
            'low_close': low_close,       # Same as low - both rails use close
            'close': float(last['Close']),
            'date': prior_date,
            'high_time': high_time,
            'low_time': low_time
        }
    except:
        return None

@st.cache_data(ttl=60)
def fetch_current_spx() -> float:
    """Fetch current SPX price."""
    try:
        spx = yf.Ticker("^GSPC")
        data = spx.history(period='1d', interval='1m')
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    return 0.0

def render_active_cone_banner(active_cone_info: Dict, spx: float) -> str:
    """Render the active cone status banner."""
    if not active_cone_info:
        return ''
    
    inside = active_cone_info.get('inside_cone')
    nearest = active_cone_info.get('nearest_cone')
    at_rail = active_cone_info.get('at_rail', False)
    rail_type = active_cone_info.get('rail_type')
    distance = active_cone_info.get('distance', 0)
    position = active_cone_info.get('position', 'unknown')
    
    if inside:
        cone_name = inside.name
        if at_rail:
            # At a rail - potential entry!
            if rail_type == 'ascending':
                icon = '🎯'
                color = '#dc2626'
                bg = '#fef2f2'
                border = '#ef4444'
                text = f"AT {cone_name} ASCENDING RAIL (PUTS entry zone)"
                subtext = f"SPX {spx:,.2f} is {distance:.1f} pts from rail at {inside.ascending_rail:.2f}"
            else:
                icon = '🎯'
                color = '#059669'
                bg = '#ecfdf5'
                border = '#10b981'
                text = f"AT {cone_name} DESCENDING RAIL (CALLS entry zone)"
                subtext = f"SPX {spx:,.2f} is {distance:.1f} pts from rail at {inside.descending_rail:.2f}"
        else:
            # Inside cone but not at rail
            icon = '📍'
            color = '#6b7280'
            bg = '#f9fafb'
            border = '#d1d5db'
            text = f"INSIDE {cone_name} CONE"
            subtext = f"SPX {spx:,.2f} — Rails: ▲{inside.ascending_rail:.2f} / ▼{inside.descending_rail:.2f}"
    elif nearest:
        # Outside all cones
        cone_name = nearest.name
        nearest_rail = active_cone_info.get('nearest_rail')
        
        if position == 'above_all':
            icon = '⬆️'
            text = f"ABOVE ALL CONES — Nearest: {cone_name} ascending"
        elif position == 'below_all':
            icon = '⬇️'
            text = f"BELOW ALL CONES — Nearest: {cone_name} descending"
        else:
            icon = '↔️'
            text = f"BETWEEN CONES — Nearest: {cone_name} {nearest_rail}"
        
        color = '#d97706'
        bg = '#fffbeb'
        border = '#f59e0b'
        
        if nearest_rail == 'ascending':
            subtext = f"SPX {spx:,.2f} is {distance:.1f} pts from {cone_name} ascending rail at {nearest.ascending_rail:.2f}"
        else:
            subtext = f"SPX {spx:,.2f} is {distance:.1f} pts from {cone_name} descending rail at {nearest.descending_rail:.2f}"
    else:
        return ''
    
    return f'''
    <div style="background:{bg};border:2px solid {border};border-radius:12px;padding:16px 20px;margin-bottom:20px;display:flex;align-items:center;gap:16px;">
        <div style="font-size:32px;">{icon}</div>
        <div>
            <div style="font-weight:700;font-size:16px;color:{color};">{text}</div>
            <div style="font-size:13px;color:#6b7280;margin-top:4px;">{subtext}</div>
        </div>
    </div>
    '''

def render_entry_checklist(vix: 'VIXZone', active_cone_info: Dict, setups: List, spx: float) -> str:
    """Render the premium 4-point entry checklist."""
    
    # Calculate checklist status
    # 1. VIX Position
    vix_check = vix.bias in ['CALLS', 'PUTS']
    if vix_check:
        if vix.bias == 'CALLS':
            vix_detail = f"VIX at {vix.position_pct:.0f}% (TOP of zone) → CALLS bias confirmed"
        else:
            vix_detail = f"VIX at {vix.position_pct:.0f}% (BOTTOM of zone) → PUTS bias confirmed"
    else:
        vix_detail = f"VIX at {vix.position_pct:.0f}% (MID-ZONE) → No directional bias"
    
    # 2. 30-Min Candle Close
    candle_check = False  # We can't know this in real-time without live data
    candle_detail = "Waiting for candle to CLOSE at zone edge (not just wick)"
    
    # 3. Price at Rail
    rail_check = False
    rail_detail = "Price not near any entry rail"
    nearest_setup = None
    
    if active_cone_info:
        at_rail = active_cone_info.get('at_rail', False)
        inside = active_cone_info.get('inside_cone')
        distance = active_cone_info.get('distance', 0)
        rail_type = active_cone_info.get('rail_type')
        
        if at_rail and inside:
            rail_check = True
            if rail_type == 'descending':
                rail_detail = f"SPX {spx:,.2f} is {distance:.1f} pts from {inside.name} descending rail ({inside.descending_rail:.2f})"
            else:
                rail_detail = f"SPX {spx:,.2f} is {distance:.1f} pts from {inside.name} ascending rail ({inside.ascending_rail:.2f})"
            
            # Find matching setup
            for s in setups:
                if s.cone_name == inside.name:
                    if rail_type == 'descending' and s.direction == 'CALLS':
                        nearest_setup = s
                        break
                    elif rail_type == 'ascending' and s.direction == 'PUTS':
                        nearest_setup = s
                        break
        elif inside:
            dist_to_desc = spx - inside.descending_rail
            dist_to_asc = inside.ascending_rail - spx
            min_dist = min(dist_to_desc, dist_to_asc)
            nearest_rail_name = 'descending' if dist_to_desc < dist_to_asc else 'ascending'
            rail_detail = f"SPX {spx:,.2f} is {min_dist:.1f} pts from nearest rail ({inside.name} {nearest_rail_name})"
    
    # 4. Direction Alignment
    align_check = False
    align_detail = "No alignment to check (need VIX bias + price at rail)"
    
    if vix_check and active_cone_info:
        rail_type = active_cone_info.get('rail_type')
        at_rail = active_cone_info.get('at_rail', False)
        
        if at_rail and rail_type:
            if (vix.bias == 'CALLS' and rail_type == 'descending') or (vix.bias == 'PUTS' and rail_type == 'ascending'):
                align_check = True
                align_detail = f"VIX bias ({vix.bias}) matches entry rail ({rail_type} = {vix.bias})"
            else:
                align_detail = f"VIX bias ({vix.bias}) does NOT match rail ({rail_type})"
    
    # Count confirmed
    confirmed = sum([vix_check, candle_check, rail_check, align_check])
    
    # Helper for check styling
    def check_style(passed: bool, waiting: bool = False):
        if passed:
            return ('#059669', '#ecfdf5', '#10b981', '✓')
        elif waiting:
            return ('#d97706', '#fffbeb', '#f59e0b', '⏳')
        else:
            return ('#dc2626', '#fef2f2', '#ef4444', '✗')
    
    v_color, v_bg, v_border, v_icon = check_style(vix_check, not vix_check)
    c_color, c_bg, c_border, c_icon = check_style(candle_check, True)  # Always waiting
    r_color, r_bg, r_border, r_icon = check_style(rail_check, not rail_check)
    a_color, a_bg, a_border, a_icon = check_style(align_check, not align_check and vix_check)
    
    # Build action summary
    if confirmed >= 3 and nearest_setup:
        s = nearest_setup
        action_html = f'''
        <div style="margin-top:20px;padding:20px;background:linear-gradient(135deg,#059669,#047857);border-radius:12px;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">
                <span style="font-size:24px;">🎯</span>
                <span style="font-size:18px;font-weight:700;color:#f8fafc;">READY TO ENTER: {s.cone_name.upper()} CONE {s.direction}</span>
            </div>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">
                <div style="background:rgba(255,255,255,0.15);padding:12px;border-radius:8px;text-align:center;">
                    <div style="font-size:10px;color:#a7f3d0;text-transform:uppercase;margin-bottom:4px;">Entry</div>
                    <div style="font-family:'DM Mono',monospace;font-size:18px;font-weight:700;color:#f8fafc;">{s.entry:.2f}</div>
                </div>
                <div style="background:rgba(255,255,255,0.15);padding:12px;border-radius:8px;text-align:center;">
                    <div style="font-size:10px;color:#a7f3d0;text-transform:uppercase;margin-bottom:4px;">Stop</div>
                    <div style="font-family:'DM Mono',monospace;font-size:18px;font-weight:700;color:#fca5a5;">{s.stop:.2f}</div>
                </div>
                <div style="background:rgba(255,255,255,0.15);padding:12px;border-radius:8px;text-align:center;">
                    <div style="font-size:10px;color:#a7f3d0;text-transform:uppercase;margin-bottom:4px;">Target (50%)</div>
                    <div style="font-family:'DM Mono',monospace;font-size:18px;font-weight:700;color:#f8fafc;">{s.target_50:.2f}</div>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:12px;">
                <div style="background:rgba(255,255,255,0.1);padding:10px;border-radius:8px;text-align:center;">
                    <div style="font-size:10px;color:#a7f3d0;">Strike</div>
                    <div style="font-family:'DM Mono',monospace;font-size:14px;font-weight:600;color:#f8fafc;">{s.strike}{'C' if s.direction == 'CALLS' else 'P'}</div>
                </div>
                <div style="background:rgba(255,255,255,0.1);padding:10px;border-radius:8px;text-align:center;">
                    <div style="font-size:10px;color:#a7f3d0;">Risk</div>
                    <div style="font-family:'DM Mono',monospace;font-size:14px;font-weight:600;color:#fca5a5;">${s.risk_per_contract:.0f}</div>
                </div>
                <div style="background:rgba(255,255,255,0.1);padding:10px;border-radius:8px;text-align:center;">
                    <div style="font-size:10px;color:#a7f3d0;">Reward (50%)</div>
                    <div style="font-family:'DM Mono',monospace;font-size:14px;font-weight:600;color:#f8fafc;">${s.profit_50:.0f}</div>
                </div>
            </div>
        </div>
        '''
    else:
        # Not ready
        missing = []
        if not vix_check:
            missing.append("VIX mid-zone (no directional bias)")
        if not rail_check:
            missing.append("Price not at entry rail")
        if not align_check and vix_check:
            missing.append("Direction misaligned with rail")
        
        missing_html = ''.join([f'<div style="font-size:13px;color:#fca5a5;">• {m}</div>' for m in missing[:3]])
        
        action_html = f'''
        <div style="margin-top:20px;padding:20px;background:linear-gradient(135deg,#1e293b,#334155);border-radius:12px;border:1px solid #475569;">
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                <span style="font-size:24px;">⏸️</span>
                <span style="font-size:18px;font-weight:700;color:#f8fafc;">WAIT — {4 - confirmed} condition{'s' if 4 - confirmed > 1 else ''} not met</span>
            </div>
            {missing_html}
        </div>
        '''
    
    return f'''
    <div style="background:linear-gradient(135deg,#0f172a,#1e293b);border-radius:16px;padding:24px;margin-top:20px;box-shadow:0 10px 30px rgba(0,0,0,0.15);">
        <!-- Header -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;">
            <div style="display:flex;align-items:center;gap:12px;">
                <span style="font-size:24px;">⚡</span>
                <span style="font-size:18px;font-weight:700;color:#f8fafc;">ENTRY CHECKLIST</span>
            </div>
            <div style="background:{'#059669' if confirmed >= 3 else '#d97706' if confirmed >= 2 else '#475569'};padding:6px 14px;border-radius:20px;">
                <span style="font-size:13px;font-weight:600;color:#f8fafc;">{confirmed}/4 Confirmed</span>
            </div>
        </div>
        
        <!-- 4 Checks -->
        <div style="display:grid;gap:12px;">
            <!-- 1. VIX Position -->
            <div style="background:{v_bg};border:1px solid {v_border};border-radius:10px;padding:14px 18px;display:flex;align-items:center;gap:14px;">
                <div style="width:32px;height:32px;background:{v_color};border-radius:8px;display:flex;align-items:center;justify-content:center;color:white;font-weight:700;">1</div>
                <div style="flex:1;">
                    <div style="font-weight:600;font-size:14px;color:{v_color};">VIX POSITION</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:2px;">{vix_detail}</div>
                </div>
                <div style="font-size:20px;">{v_icon}</div>
            </div>
            
            <!-- 2. 30-Min Candle Close -->
            <div style="background:{c_bg};border:1px solid {c_border};border-radius:10px;padding:14px 18px;display:flex;align-items:center;gap:14px;">
                <div style="width:32px;height:32px;background:{c_color};border-radius:8px;display:flex;align-items:center;justify-content:center;color:white;font-weight:700;">2</div>
                <div style="flex:1;">
                    <div style="font-weight:600;font-size:14px;color:{c_color};">30-MIN CANDLE CLOSE</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:2px;">{candle_detail}</div>
                </div>
                <div style="font-size:20px;">{c_icon}</div>
            </div>
            
            <!-- 3. Price at Rail -->
            <div style="background:{r_bg};border:1px solid {r_border};border-radius:10px;padding:14px 18px;display:flex;align-items:center;gap:14px;">
                <div style="width:32px;height:32px;background:{r_color};border-radius:8px;display:flex;align-items:center;justify-content:center;color:white;font-weight:700;">3</div>
                <div style="flex:1;">
                    <div style="font-weight:600;font-size:14px;color:{r_color};">PRICE AT RAIL</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:2px;">{rail_detail}</div>
                </div>
                <div style="font-size:20px;">{r_icon}</div>
            </div>
            
            <!-- 4. Direction Alignment -->
            <div style="background:{a_bg};border:1px solid {a_border};border-radius:10px;padding:14px 18px;display:flex;align-items:center;gap:14px;">
                <div style="width:32px;height:32px;background:{a_color};border-radius:8px;display:flex;align-items:center;justify-content:center;color:white;font-weight:700;">4</div>
                <div style="flex:1;">
                    <div style="font-weight:600;font-size:14px;color:{a_color};">DIRECTION ALIGNMENT</div>
                    <div style="font-size:12px;color:#6b7280;margin-top:2px;">{align_detail}</div>
                </div>
                <div style="font-size:20px;">{a_icon}</div>
            </div>
        </div>
        
        <!-- Action Summary -->
        {action_html}
    </div>
    '''

# ============================================================================
# BEAUTIFUL UI RENDERING
# ============================================================================

def render_dashboard(
    spx: float,
    vix: VIXZone,
    cones: List[Cone],
    setups: List[TradeSetup],
    assessment: DayAssessment,
    prior: Dict,
    historical_results: List = None,
    session_data: Dict = None,
    is_historical: bool = False,
    dark_mode: bool = False,
    active_cone_info: Dict = None
) -> str:
    """Render the complete dashboard HTML."""
    
    ct_now = get_ct_now()
    
    # Color scheme
    if vix.bias == 'CALLS':
        bias_color = '#059669'
        bias_bg = '#ecfdf5'
        bias_icon = '🟢'
        bias_border = '#10b981'
    elif vix.bias == 'PUTS':
        bias_color = '#dc2626'
        bias_bg = '#fef2f2'
        bias_icon = '🔴'
        bias_border = '#ef4444'
    elif vix.bias == 'WAIT':
        bias_color = '#d97706'
        bias_bg = '#fffbeb'
        bias_icon = '🟡'
        bias_border = '#f59e0b'
    else:
        bias_color = '#6b7280'
        bias_bg = '#f9fafb'
        bias_icon = '⏳'
        bias_border = '#9ca3af'
    
    # Expected SPX Move indicator
    move_min, move_max = vix.expected_move
    move_text = f'Expected SPX Move: {move_min}-{move_max} pts'
    move_color = '#059669'
    move_bg = '#ecfdf5'
    
    # VIX action text
    if vix.bias == 'CALLS':
        vix_action = f"VIX at TOP ({vix.position_pct:.0f}%) → Expect VIX to fall → SPX UP"
    elif vix.bias == 'PUTS':
        vix_action = f"VIX at BOTTOM ({vix.position_pct:.0f}%) → Expect VIX to rise → SPX DOWN"
    elif vix.status == 'BREAKOUT_UP':
        vix_action = f"VIX BROKE UP → Extended PUTS targets"
    elif vix.status == 'BREAKOUT_DOWN':
        vix_action = f"VIX BROKE DOWN → Extended CALLS targets"
    else:
        vix_action = "VIX mid-zone → Wait for edge"
    
    # Build setups HTML
    calls_setups = [s for s in setups if s.direction == 'CALLS'][:4]
    puts_setups = [s for s in setups if s.direction == 'PUTS'][:4]
    
    def setup_html(s: TradeSetup) -> str:
        active_badge = '<span style="background:#059669;color:white;padding:2px 8px;border-radius:4px;font-size:11px;margin-left:8px;">ACTIVE</span>' if s.is_active else ''
        dir_color = '#059669' if s.direction == 'CALLS' else '#dc2626'
        arrow = '▼' if s.direction == 'CALLS' else '▲'
        return f'''
        <div style="background:white;border-radius:12px;padding:16px;margin-bottom:12px;border:1px solid #e5e7eb;box-shadow:0 1px 3px rgba(0,0,0,0.05);">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                <div>
                    <span style="font-weight:700;font-size:15px;color:#1f2937;">{s.cone_name} {arrow}</span>
                    {active_badge}
                </div>
                <div style="text-align:right;">
                    <div style="font-size:12px;color:#6b7280;">{s.distance:.0f} pts away</div>
                    <div style="font-size:11px;color:#9ca3af;">Width: {s.cone_width:.0f} pts</div>
                </div>
            </div>
            
            <!-- Entry/Stop/Target/Strike -->
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px;padding:12px;background:#f9fafb;border-radius:8px;">
                <div>
                    <div style="font-size:10px;color:#6b7280;text-transform:uppercase;">Entry</div>
                    <div style="font-family:'DM Mono',monospace;font-size:14px;font-weight:600;color:#1f2937;">{s.entry:.2f}</div>
                </div>
                <div>
                    <div style="font-size:10px;color:#6b7280;text-transform:uppercase;">Stop</div>
                    <div style="font-family:'DM Mono',monospace;font-size:14px;font-weight:600;color:#dc2626;">{s.stop:.2f}</div>
                </div>
                <div>
                    <div style="font-size:10px;color:#6b7280;text-transform:uppercase;">50% Target</div>
                    <div style="font-family:'DM Mono',monospace;font-size:14px;font-weight:600;color:#059669;">{s.target_50:.2f}</div>
                </div>
                <div>
                    <div style="font-size:10px;color:#6b7280;text-transform:uppercase;">Strike</div>
                    <div style="font-family:'DM Mono',monospace;font-size:14px;font-weight:600;color:{dir_color};">{s.strike}{'C' if s.direction == 'CALLS' else 'P'}</div>
                </div>
            </div>
            
            <!-- SPX Points Info -->
            <div style="font-size:11px;color:#6b7280;margin-bottom:8px;padding:0 4px;">
                12.5%: +{s.spx_pts_12:.1f}pts | 25%: +{s.spx_pts_25:.1f}pts | 50%: +{s.spx_pts_50:.1f}pts SPX
            </div>
            
            <!-- Estimated Profits Per Contract -->
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding-top:12px;border-top:1px solid #e5e7eb;">
                <div style="text-align:center;">
                    <div style="font-size:10px;color:#6b7280;">12.5%</div>
                    <div style="font-family:'DM Mono',monospace;font-size:15px;font-weight:700;color:#059669;">${s.profit_12:,.0f}</div>
                    <div style="font-size:9px;color:#9ca3af;">/contract</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:10px;color:#6b7280;">25%</div>
                    <div style="font-family:'DM Mono',monospace;font-size:15px;font-weight:700;color:#059669;">${s.profit_25:,.0f}</div>
                    <div style="font-size:9px;color:#9ca3af;">/contract</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:10px;color:#6b7280;">50%</div>
                    <div style="font-family:'DM Mono',monospace;font-size:15px;font-weight:700;color:#059669;">${s.profit_50:,.0f}</div>
                    <div style="font-size:9px;color:#9ca3af;">/contract</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:10px;color:#6b7280;">Risk | R:R</div>
                    <div style="font-family:'DM Mono',monospace;font-size:15px;font-weight:700;color:#dc2626;">${s.risk_per_contract:.0f}</div>
                    <div style="font-size:9px;color:#1f2937;font-weight:600;">{s.rr_ratio}:1</div>
                </div>
            </div>
        </div>
        '''
    
    calls_html = ''.join([setup_html(s) for s in calls_setups]) if calls_setups else '<div style="color:#6b7280;text-align:center;padding:20px;">No CALLS setups with sufficient width</div>'
    puts_html = ''.join([setup_html(s) for s in puts_setups]) if puts_setups else '<div style="color:#6b7280;text-align:center;padding:20px;">No PUTS setups with sufficient width</div>'
    
    # Cone rails table
    rails_html = ''
    for c in cones:
        rails_html += f'''
        <tr>
            <td style="padding:10px 12px;font-weight:500;">{c.name}{'²' if c.pivot.is_secondary else ''}</td>
            <td style="padding:10px 12px;font-family:'SF Mono',monospace;color:#059669;font-weight:600;">{c.ascending_rail:.2f}</td>
            <td style="padding:10px 12px;font-family:'SF Mono',monospace;color:#dc2626;font-weight:600;">{c.descending_rail:.2f}</td>
            <td style="padding:10px 12px;font-family:'SF Mono',monospace;">{c.width:.1f}</td>
        </tr>
        '''
    
    # VIX zones ladder
    vix_ladder_html = ''
    for i, z in enumerate(reversed(vix.zones_above)):
        vix_ladder_html += f'<div style="font-family:\'SF Mono\',monospace;font-size:12px;color:#6b7280;">+{4-i}: {z:.2f}</div>'
    
    vix_ladder_below_html = ''
    for i, z in enumerate(vix.zones_below):
        vix_ladder_below_html += f'<div style="font-family:\'SF Mono\',monospace;font-size:12px;color:#6b7280;">-{i+1}: {z:.2f}</div>'
    
    # Theme colors based on dark_mode
    if dark_mode:
        theme = {
            'bg': '#0f172a',
            'card_bg': '#1e293b',
            'card_border': '#334155',
            'text': '#f8fafc',
            'text_muted': '#94a3b8',
            'text_secondary': '#cbd5e1',
            'header_bg': 'linear-gradient(135deg,#0f172a 0%,#1e293b 100%)',
            'table_header_bg': '#334155',
            'table_row_hover': '#334155',
            'input_bg': '#334155',
            'zone_current_bg': '#334155',
        }
    else:
        theme = {
            'bg': '#f8fafc',
            'card_bg': 'white',
            'card_border': '#e5e7eb',
            'text': '#1f2937',
            'text_muted': '#6b7280',
            'text_secondary': '#4b5563',
            'header_bg': 'linear-gradient(135deg,#1e293b 0%,#334155 100%)',
            'table_header_bg': '#f9fafb',
            'table_row_hover': '#f9fafb',
            'input_bg': '#f9fafb',
            'zone_current_bg': '#334155',
        }
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; font-family:'DM Sans',system-ui,sans-serif; }}
            body {{ background:{theme['bg']}; color:{theme['text']}; }}
            
            .dashboard {{ max-width:1400px; margin:0 auto; padding:20px; }}
            
            /* Header */
            .header {{
                background:{theme['header_bg']};
                border-radius:16px;
                padding:24px 32px;
                margin-bottom:20px;
                display:flex;
                justify-content:space-between;
                align-items:center;
                flex-wrap:wrap;
                gap:20px;
            }}
            .logo {{ display:flex; align-items:center; gap:16px; }}
            .logo-icon {{
                width:56px; height:56px;
                background:linear-gradient(135deg,#fbbf24,#f59e0b);
                border-radius:14px;
                display:flex; align-items:center; justify-content:center;
                font-size:28px;
                box-shadow:0 4px 12px rgba(251,191,36,0.3);
            }}
            .logo-text {{ color:#f8fafc; }}
            .logo-title {{ font-size:28px; font-weight:700; letter-spacing:-0.5px; }}
            .logo-sub {{ font-size:12px; color:#94a3b8; letter-spacing:1px; text-transform:uppercase; margin-top:2px; }}
            .header-stats {{ display:flex; gap:40px; }}
            .stat {{ text-align:center; }}
            .stat-label {{ font-size:11px; color:#94a3b8; text-transform:uppercase; letter-spacing:1px; }}
            .stat-value {{ font-family:'DM Mono',monospace; font-size:24px; font-weight:600; color:#f8fafc; margin-top:4px; }}
            
            /* Cards */
            .card {{
                background:{theme['card_bg']};
                border-radius:16px;
                border:1px solid {theme['card_border']};
                overflow:hidden;
                box-shadow:0 1px 3px rgba(0,0,0,0.04);
            }}
            .card-header {{
                padding:16px 20px;
                border-bottom:1px solid {theme['card_border']};
                font-weight:600;
                font-size:14px;
                color:{theme['text']};
                background:{theme['table_header_bg']};
                display:flex;
                align-items:center;
                gap:8px;
            }}
            .card-body {{ padding:20px; }}
            
            /* Grid */
            .grid {{ display:grid; gap:20px; }}
            .grid-2 {{ grid-template-columns:1fr 1fr; }}
            .grid-3 {{ grid-template-columns:1fr 1fr 1fr; }}
            @media (max-width:900px) {{
                .grid-2, .grid-3 {{ grid-template-columns:1fr; }}
                .header {{ flex-direction:column; text-align:center; }}
                .header-stats {{ justify-content:center; }}
            }}
            
            /* Signal Box */
            .signal {{
                background:{bias_bg};
                border:2px solid {bias_border};
                border-radius:16px;
                padding:24px;
                text-align:center;
            }}
            .signal-icon {{ font-size:48px; margin-bottom:8px; }}
            .signal-title {{ font-size:32px; font-weight:700; color:{bias_color}; }}
            .signal-action {{ font-size:14px; color:{theme['text_secondary']}; margin-top:8px; line-height:1.5; }}
            
            /* VIX Zone */
            .vix-zone {{ margin-top:16px; }}
            .zone-box {{
                border-radius:12px;
                padding:14px;
                text-align:center;
                margin-bottom:8px;
            }}
            .zone-top {{ background:linear-gradient(135deg,#ecfdf5,#d1fae5); border:2px solid #10b981; }}
            .zone-current {{ background:{theme['zone_current_bg']}; }}
            .zone-bottom {{ background:linear-gradient(135deg,#fef2f2,#fee2e2); border:2px solid #ef4444; }}
            .zone-label {{ font-size:11px; text-transform:uppercase; letter-spacing:0.5px; font-weight:600; }}
            .zone-value {{ font-family:'DM Mono',monospace; font-size:24px; font-weight:700; margin:6px 0; }}
            .zone-hint {{ font-size:11px; }}
            
            /* Table */
            table {{ width:100%; border-collapse:collapse; }}
            th {{ text-align:left; padding:12px; background:{theme['table_header_bg']}; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; color:{theme['text_muted']}; font-weight:600; }}
            td {{ padding:10px 12px; border-bottom:1px solid {theme['card_border']}; font-size:14px; color:{theme['text']}; }}
            
            /* Warning Banner */
            .warning-banner {{
                background:#fffbeb;
                border:1px solid #f59e0b;
                border-radius:12px;
                padding:14px 20px;
                margin-bottom:20px;
                display:flex;
                align-items:center;
                gap:12px;
            }}
            .warning-icon {{ font-size:24px; }}
            .warning-text {{ font-size:13px; color:#92400e; }}
            .warning-text strong {{ color:#78350f; }}
            
            /* Checklist */
            .checklist {{ display:flex; flex-direction:column; gap:8px; margin-top:16px; }}
            .check-item {{
                display:flex;
                align-items:center;
                gap:10px;
                padding:10px 14px;
                border-radius:8px;
                font-size:13px;
            }}
            .check-pass {{ background:#ecfdf5; color:#065f46; }}
            .check-wait {{ background:{theme['table_header_bg']}; color:{theme['text_muted']}; }}
            .check-fail {{ background:#fef2f2; color:#991b1b; }}
        </style>
    </head>
    <body>
        <div class="dashboard">
            <!-- Premium Header -->
            <div style="background:linear-gradient(135deg,#0f172a 0%,#1e293b 50%,#334155 100%);border-radius:20px;padding:32px 40px;margin-bottom:24px;position:relative;overflow:hidden;box-shadow:0 20px 40px rgba(0,0,0,0.15);">
                <!-- Subtle gradient overlay -->
                <div style="position:absolute;top:0;right:0;width:400px;height:100%;background:linear-gradient(90deg,transparent,rgba(251,191,36,0.08));pointer-events:none;"></div>
                
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:24px;position:relative;z-index:1;">
                    <!-- Logo & Tagline -->
                    <div style="display:flex;align-items:center;gap:20px;">
                        <div style="width:64px;height:64px;background:linear-gradient(135deg,#fbbf24 0%,#f59e0b 50%,#d97706 100%);border-radius:16px;display:flex;align-items:center;justify-content:center;font-size:32px;box-shadow:0 8px 24px rgba(251,191,36,0.35);">📈</div>
                        <div>
                            <div style="font-size:32px;font-weight:800;color:#f8fafc;letter-spacing:-1px;text-shadow:0 2px 4px rgba(0,0,0,0.2);">SPX PROPHET</div>
                            <div style="font-size:13px;color:#fbbf24;letter-spacing:2px;text-transform:uppercase;font-weight:500;margin-top:4px;">Where Structure Becomes Foresight</div>
                        </div>
                    </div>
                    
                    <!-- Live Stats -->
                    <div style="display:flex;gap:48px;">
                        <div style="text-align:center;">
                            <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">S&P 500</div>
                            <div style="font-family:'DM Mono',monospace;font-size:28px;font-weight:700;color:#f8fafc;margin-top:4px;">{spx:,.2f}</div>
                        </div>
                        <div style="width:1px;background:linear-gradient(180deg,transparent,#475569,transparent);"></div>
                        <div style="text-align:center;">
                            <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">VIX</div>
                            <div style="font-family:'DM Mono',monospace;font-size:28px;font-weight:700;color:#fbbf24;margin-top:4px;">{f'{vix.current:.2f}' if vix.current > 0 else '—'}</div>
                        </div>
                        <div style="width:1px;background:linear-gradient(180deg,transparent,#475569,transparent);"></div>
                        <div style="text-align:center;">
                            <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">{ct_now.strftime('%b %d, %Y')}</div>
                            <div style="font-family:'DM Mono',monospace;font-size:28px;font-weight:700;color:#f8fafc;margin-top:4px;">{ct_now.strftime('%H:%M')} <span style="font-size:14px;color:#64748b;font-weight:400;">CT</span></div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Refined Info Banner -->
            <div style="background:linear-gradient(90deg,#1e293b,#334155);border-radius:12px;padding:14px 24px;margin-bottom:20px;display:flex;align-items:center;gap:16px;border-left:4px solid #fbbf24;">
                <div style="font-size:20px;">⏱️</div>
                <div style="font-size:13px;color:#cbd5e1;">
                    <span style="color:#fbbf24;font-weight:600;">30-MIN CANDLE CLOSE RULE:</span>
                    <span style="color:#94a3b8;">VIX wicks can pierce levels — always wait for the candle to <strong style="color:#f8fafc;">CLOSE</strong> before confirming signal.</span>
                </div>
            </div>
            
            {render_active_cone_banner(active_cone_info, spx) if active_cone_info and not is_historical else ''}
            
            <!-- Main Grid -->
            <div class="grid grid-3">
                <!-- Left: Signal & VIX -->
                <div>
                    <div class="card">
                        <div class="card-header">🎯 Today's Bias</div>
                        <div class="card-body">
                            <div class="signal">
                                <div class="signal-icon">{bias_icon}</div>
                                <div class="signal-title">{vix.bias}</div>
                                <div class="signal-action">{vix_action}</div>
                            </div>
                            
                            <div class="vix-zone">
                                <div class="zone-box zone-top">
                                    <div class="zone-label" style="color:#047857;">Zone Top</div>
                                    <div class="zone-value" style="color:#047857;">{f'{vix.top:.2f}' if vix.top > 0 else '—'}</div>
                                    <div class="zone-hint" style="color:#065f46;">VIX closes here → CALLS</div>
                                </div>
                                <div class="zone-box zone-current">
                                    <div class="zone-label" style="color:#94a3b8;">Current VIX</div>
                                    <div class="zone-value" style="color:#f8fafc;">{f'{vix.current:.2f}' if vix.current > 0 else '—'}</div>
                                    <div class="zone-hint" style="color:#94a3b8;">{vix.position_pct:.0f}% in zone</div>
                                </div>
                                <div class="zone-box zone-bottom">
                                    <div class="zone-label" style="color:#b91c1c;">Zone Bottom</div>
                                    <div class="zone-value" style="color:#b91c1c;">{f'{vix.bottom:.2f}' if vix.bottom > 0 else '—'}</div>
                                    <div class="zone-hint" style="color:#7f1d1d;">VIX closes here → PUTS</div>
                                </div>
                            </div>
                            
                            <!-- Expected SPX Move Indicator -->
                            <div style="margin-top:16px;padding:12px 16px;background:{move_bg};border-radius:10px;border:1px solid {move_color}20;">
                                <div style="display:flex;align-items:center;gap:8px;">
                                    <span style="font-size:20px;">📊</span>
                                    <div>
                                        <div style="font-weight:600;font-size:14px;color:{move_color};">{move_text}</div>
                                        <div style="font-size:11px;color:#6b7280;">VIX Zone: {vix.zone_size:.2f}</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Cone Rails -->
                    <div class="card" style="margin-top:20px;">
                        <div class="card-header">📐 Cone Rails @ 10:00 AM</div>
                        <div class="card-body" style="padding:0;">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Cone</th>
                                        <th>▲ Ascending</th>
                                        <th>▼ Descending</th>
                                        <th>Width</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rails_html if rails_html else '<tr><td colspan="4" style="text-align:center;color:#6b7280;padding:20px;">Enter prior session data</td></tr>'}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                
                <!-- Middle: CALLS Setups -->
                <div>
                    <div class="card" style="height:100%;">
                        <div class="card-header" style="color:#059669;">🟢 CALLS Setups</div>
                        <div class="card-body" style="background:#fafffe;">
                            {calls_html}
                        </div>
                    </div>
                </div>
                
                <!-- Right: PUTS Setups -->
                <div>
                    <div class="card" style="height:100%;">
                        <div class="card-header" style="color:#dc2626;">🔴 PUTS Setups</div>
                        <div class="card-body" style="background:#fffafa;">
                            {puts_html}
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Premium Entry Checklist -->
            {render_entry_checklist(vix, active_cone_info, setups, spx)}
            
            {'<!-- Historical Results -->' + render_historical_section(historical_results, session_data) if is_historical and historical_results else ''}
        </div>
    </body>
    </html>
    '''
    
    return html

def render_historical_section(results: List, session_data: Dict) -> str:
    """Render simplified historical view - just show what levels existed and session range."""
    if not session_data:
        return ''
    
    session_high = session_data.get('high', 0)
    session_low = session_data.get('low', 0)
    session_range = session_high - session_low
    
    # Build simple level check for each setup
    levels_html = ''
    
    if results:
        for r in results:
            entry = r.setup.entry
            target = r.setup.target_100
            stop = r.setup.stop
            direction = r.setup.direction
            cone = r.setup.cone_name
            arrow = '▼' if direction == 'CALLS' else '▲'
            
            # Did price reach entry?
            if direction == 'CALLS':
                entry_reached = session_low <= entry
                target_reached = session_high >= target
                stop_reached = session_low <= stop
            else:
                entry_reached = session_high >= entry
                target_reached = session_low <= target
                stop_reached = session_high >= stop
            
            entry_icon = '✓' if entry_reached else '✗'
            entry_color = '#059669' if entry_reached else '#dc2626'
            target_icon = '✓' if target_reached else '✗'
            stop_icon = '✓' if stop_reached else '✗'
            
            dir_color = '#059669' if direction == 'CALLS' else '#dc2626'
            
            levels_html += f'''
            <tr>
                <td style="padding:10px 12px;font-weight:500;color:{dir_color};">{cone} {arrow} {direction}</td>
                <td style="padding:10px 12px;font-family:'DM Mono',monospace;text-align:center;">
                    <span style="color:{entry_color};">{entry_icon}</span> {entry:.2f}
                </td>
                <td style="padding:10px 12px;font-family:'DM Mono',monospace;text-align:center;">
                    <span style="color:{'#059669' if target_reached else '#6b7280'};">{target_icon}</span> {target:.2f}
                </td>
                <td style="padding:10px 12px;font-family:'DM Mono',monospace;text-align:center;">
                    <span style="color:{'#dc2626' if stop_reached else '#6b7280'};">{stop_icon}</span> {stop:.2f}
                </td>
            </tr>
            '''
    
    return f'''
    <div class="card" style="margin-top:20px;">
        <div class="card-header" style="background:#1e293b;color:#f8fafc;">📊 HISTORICAL - Session Range & Levels</div>
        <div class="card-body">
            <!-- Session Stats -->
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:20px;padding:20px;background:#f8fafc;border-radius:10px;">
                <div style="text-align:center;">
                    <div style="font-size:11px;color:#6b7280;text-transform:uppercase;margin-bottom:4px;">Session High</div>
                    <div style="font-family:'DM Mono',monospace;font-size:24px;font-weight:700;color:#059669;">{session_high:,.2f}</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:11px;color:#6b7280;text-transform:uppercase;margin-bottom:4px;">Session Low</div>
                    <div style="font-family:'DM Mono',monospace;font-size:24px;font-weight:700;color:#dc2626;">{session_low:,.2f}</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:11px;color:#6b7280;text-transform:uppercase;margin-bottom:4px;">Range</div>
                    <div style="font-family:'DM Mono',monospace;font-size:24px;font-weight:700;color:#1f2937;">{session_range:,.1f} pts</div>
                </div>
            </div>
            
            <!-- Levels Table -->
            <div style="font-size:13px;color:#6b7280;margin-bottom:12px;">
                ✓ = Price reached this level during session &nbsp;&nbsp; ✗ = Price did not reach
            </div>
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr style="background:#f9fafb;">
                        <th style="padding:12px;text-align:left;font-size:11px;text-transform:uppercase;color:#6b7280;">Setup</th>
                        <th style="padding:12px;text-align:center;font-size:11px;text-transform:uppercase;color:#6b7280;">Entry</th>
                        <th style="padding:12px;text-align:center;font-size:11px;text-transform:uppercase;color:#6b7280;">Target (100%)</th>
                        <th style="padding:12px;text-align:center;font-size:11px;text-transform:uppercase;color:#6b7280;">Stop</th>
                    </tr>
                </thead>
                <tbody>
                    {levels_html if levels_html else '<tr><td colspan="4" style="text-align:center;padding:20px;color:#6b7280;">No setups to display</td></tr>'}
                </tbody>
            </table>
            
            <div style="margin-top:16px;padding:12px 16px;background:#fffbeb;border-radius:8px;font-size:12px;color:#92400e;">
                <strong>Note:</strong> This shows IF price levels were reached, not IF the trade was valid per your VIX rules. 
                Check your VIX notes to confirm if entries were valid that day.
            </div>
        </div>
    </div>
    '''

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for Streamlit
    st.markdown("""
    <style>
    #MainMenu, footer { visibility: hidden; }
    header { visibility: visible !important; }
    [data-testid="stSidebar"] { background: #f8fafc; }
    [data-testid="stSidebar"] * { font-size: 14px !important; }
    [data-testid="stSidebar"] h3 { font-size: 16px !important; font-weight: 600 !important; color: #1f2937 !important; margin-top: 16px !important; }
    [data-testid="stSidebar"] label { font-size: 13px !important; color: #374151 !important; }
    [data-testid="stSidebar"] .stNumberInput input { font-size: 14px !important; }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state - each variable independently
    if 'vix_bottom' not in st.session_state:
        st.session_state.vix_bottom = 0.0
    if 'vix_top' not in st.session_state:
        st.session_state.vix_top = 0.0
    if 'vix_current' not in st.session_state:
        st.session_state.vix_current = 0.0
    if 'sec_high' not in st.session_state:
        st.session_state.sec_high = 0.0
    if 'sec_high_time' not in st.session_state:
        st.session_state.sec_high_time = "12:00"
    if 'sec_low' not in st.session_state:
        st.session_state.sec_low = 0.0
    if 'sec_low_time' not in st.session_state:
        st.session_state.sec_low_time = "12:00"
    if 'use_sec_high' not in st.session_state:
        st.session_state.use_sec_high = False
    if 'use_sec_low' not in st.session_state:
        st.session_state.use_sec_low = False
    if 'manual_high' not in st.session_state:
        st.session_state.manual_high = 0.0
    if 'manual_high_time' not in st.session_state:
        st.session_state.manual_high_time = "10:30"
    if 'manual_low' not in st.session_state:
        st.session_state.manual_low = 0.0
    if 'manual_low_time' not in st.session_state:
        st.session_state.manual_low_time = "14:00"
    if 'manual_close' not in st.session_state:
        st.session_state.manual_close = 0.0
    if 'use_manual_pivots' not in st.session_state:
        st.session_state.use_manual_pivots = False
    if 'dark_mode' not in st.session_state:
        st.session_state.dark_mode = False  # Default to light mode
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 📅 Session")
        session_date = st.date_input("Date", value=datetime.now().date())
        session_dt = datetime.combine(session_date, time(0, 0))
        
        st.markdown("### 📊 VIX Zone (5pm-6am CT)")
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.vix_bottom = st.number_input("Bottom", min_value=0.0, max_value=100.0, value=st.session_state.vix_bottom, step=0.01, format="%.2f")
        with col2:
            st.session_state.vix_top = st.number_input("Top", min_value=0.0, max_value=100.0, value=st.session_state.vix_top, step=0.01, format="%.2f")
        
        st.session_state.vix_current = st.number_input("Current VIX", min_value=0.0, max_value=100.0, value=st.session_state.vix_current, step=0.01, format="%.2f")
        
        st.markdown("### 📈 Prior Day Pivots")
        st.session_state.use_manual_pivots = st.checkbox("Manual Input", value=st.session_state.use_manual_pivots, help="Override auto-fetched data")
        
        if st.session_state.use_manual_pivots:
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.manual_high = st.number_input("High", min_value=0.0, max_value=10000.0, value=st.session_state.manual_high, step=0.25, format="%.2f", key="man_h")
            with col2:
                st.session_state.manual_high_time = st.text_input("High Time (CT)", value=st.session_state.manual_high_time, key="man_ht")
            
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.manual_low = st.number_input("Low", min_value=0.0, max_value=10000.0, value=st.session_state.manual_low, step=0.25, format="%.2f", key="man_l")
            with col2:
                st.session_state.manual_low_time = st.text_input("Low Time (CT)", value=st.session_state.manual_low_time, key="man_lt")
            
            st.session_state.manual_close = st.number_input("Close", min_value=0.0, max_value=10000.0, value=st.session_state.manual_close, step=0.25, format="%.2f", key="man_c")
        
        st.markdown("### 📐 Secondary Pivots")
        
        # High² - Independent
        st.session_state.use_sec_high = st.checkbox("Enable High²", value=st.session_state.use_sec_high)
        if st.session_state.use_sec_high:
            c1, c2 = st.columns(2)
            with c1:
                st.session_state.sec_high = st.number_input("High² Price", min_value=0.0, max_value=10000.0, value=st.session_state.sec_high, step=0.25, format="%.2f", key="sh")
            with c2:
                st.session_state.sec_high_time = st.text_input("Time (CT)", value=st.session_state.sec_high_time, key="sht")
        
        # Low² - Independent
        st.session_state.use_sec_low = st.checkbox("Enable Low²", value=st.session_state.use_sec_low)
        if st.session_state.use_sec_low:
            c1, c2 = st.columns(2)
            with c1:
                st.session_state.sec_low = st.number_input("Low² Price", min_value=0.0, max_value=10000.0, value=st.session_state.sec_low, step=0.25, format="%.2f", key="sl")
            with c2:
                st.session_state.sec_low_time = st.text_input("Time (CT)", value=st.session_state.sec_low_time, key="slt")
        
        st.markdown("---")
        
        # Theme toggle
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🔄 Refresh", use_container_width=True):
                st.cache_data.clear()
                st.rerun()
        with col2:
            theme_label = "🌙 Dark" if not st.session_state.dark_mode else "☀️ Light"
            if st.button(theme_label, use_container_width=True):
                st.session_state.dark_mode = not st.session_state.dark_mode
                st.rerun()
    
    # Fetch data
    prior = fetch_prior_session(session_dt)
    
    # Use manual pivots if enabled, otherwise use fetched data
    if st.session_state.use_manual_pivots and st.session_state.manual_high > 0:
        prior_high = st.session_state.manual_high
        prior_low = st.session_state.manual_low
        prior_close = st.session_state.manual_close
        # Parse manual times
        try:
            h, m = map(int, st.session_state.manual_high_time.split(':'))
            high_time = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(h, m)))
        except:
            high_time = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(10, 30)))
        try:
            h, m = map(int, st.session_state.manual_low_time.split(':'))
            low_time = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(h, m)))
        except:
            low_time = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(14, 0)))
    elif prior:
        prior_high = prior['high']
        prior_low = prior['low']
        prior_close = prior['close']
        high_time = prior['high_time']
        low_time = prior['low_time']
    else:
        prior_high = 0
        prior_low = 0
        prior_close = 0
        high_time = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(12, 0)))
        low_time = high_time
    
    spx = fetch_current_spx() or prior_close or 6000
    
    # Build pivots with correct prices for ascending/descending rails
    # HIGH PIVOT: Ascending = high price (with wick), Descending = high close
    # LOW PIVOT: Both rails use lowest close (no wicks)
    # CLOSE PIVOT: Both rails use close price
    pivots = []
    if prior_high > 0:
        # Get high_close from prior data if available
        high_close = prior.get('high_close', prior_high) if prior else prior_high
        
        pivots = [
            Pivot(
                price=prior_high,
                time=high_time,
                name='High',
                is_secondary=False,
                price_for_ascending=prior_high,      # Use highest HIGH (with wick)
                price_for_descending=high_close      # Use highest CLOSE
            ),
            Pivot(
                price=prior_low,
                time=low_time,
                name='Low',
                is_secondary=False,
                price_for_ascending=prior_low,       # Use lowest CLOSE
                price_for_descending=prior_low       # Use lowest CLOSE (both same)
            ),
            Pivot(
                price=prior_close,
                time=CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(15, 0))),
                name='Close',
                is_secondary=False,
                price_for_ascending=prior_close,     # Close price
                price_for_descending=prior_close     # Close price
            ),
        ]
        
        # Add High² if enabled (independent) - same rules as High
        if st.session_state.use_sec_high and st.session_state.sec_high > 0:
            try:
                h, m = map(int, st.session_state.sec_high_time.split(':'))
                t = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(h, m)))
                # For secondary high, user enters one price - use it for both
                # In real usage, they should enter the high price (ascending uses it, descending should use close)
                pivots.append(Pivot(
                    price=st.session_state.sec_high,
                    time=t,
                    name='High²',
                    is_secondary=True,
                    price_for_ascending=st.session_state.sec_high,
                    price_for_descending=st.session_state.sec_high  # User should enter close ideally
                ))
            except:
                pass
        
        # Add Low² if enabled (independent) - same rules as Low (both use close)
        if st.session_state.use_sec_low and st.session_state.sec_low > 0:
            try:
                h, m = map(int, st.session_state.sec_low_time.split(':'))
                t = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(h, m)))
                pivots.append(Pivot(
                    price=st.session_state.sec_low,
                    time=t,
                    name='Low²',
                    is_secondary=True,
                    price_for_ascending=st.session_state.sec_low,   # Use close
                    price_for_descending=st.session_state.sec_low   # Use close
                ))
            except:
                pass
    
    # Build cones at 10:00 AM
    eval_time = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
    cones = build_cones(pivots, eval_time) if pivots else []
    
    # Analyze VIX
    vix = analyze_vix(st.session_state.vix_bottom, st.session_state.vix_top, st.session_state.vix_current)
    
    # Generate setups
    setups = generate_setups(cones, spx, vix.bias) if cones else []
    
    # Assess day
    assessment = assess_day(vix, cones, spx)
    
    # Check if this is a historical date (not today)
    ct_now = get_ct_now()
    is_historical = session_date < ct_now.date()
    
    historical_results = None
    session_data = None
    
    if is_historical and setups:
        # Fetch intraday candles for the selected date
        candles = fetch_session_candles(session_dt)
        
        if candles is not None and not candles.empty:
            # Filter setups by VIX bias - ONLY analyze valid entries
            if vix.bias in ['CALLS', 'PUTS']:
                valid_setups = [s for s in setups if s.direction == vix.bias]
            else:
                # No VIX data or WAIT - analyze all but mark as unfiltered
                valid_setups = setups
            
            # Analyze what happened
            historical_results = analyze_historical_trades(valid_setups, candles, vix.bias)
            session_data = {
                'high': candles['High'].max(),
                'low': candles['Low'].min(),
                'close': candles['Close'].iloc[-1] if not candles.empty else 0,
                'vix_bias': vix.bias,
                'vix_filtered': vix.bias in ['CALLS', 'PUTS']
            }
    
    # Find which cone we're in (for RTH display)
    active_cone_info = find_active_cone(spx, cones) if cones else None
    
    # Render
    html = render_dashboard(
        spx, vix, cones, setups, assessment, prior,
        historical_results=historical_results,
        session_data=session_data,
        is_historical=is_historical,
        dark_mode=st.session_state.dark_mode,
        active_cone_info=active_cone_info
    )
    
    # Adjust height based on historical content
    height = 1800 if is_historical and historical_results else 1500
    components.html(html, height=height, scrolling=True)

if __name__ == "__main__":
    main()