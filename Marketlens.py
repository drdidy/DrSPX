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
VIX_ZONE_ESTABLISHMENT_END = time(2, 0)       # 2:00 AM CT (next day)
VIX_RELIABLE_BREAKOUT_START = time(2, 0)      # 2:00 AM CT
VIX_RELIABLE_BREAKOUT_END = time(6, 30)       # 6:30 AM CT
VIX_DANGER_ZONE_START = time(6, 30)           # 6:30 AM CT
VIX_DANGER_ZONE_END = time(9, 30)             # 9:30 AM CT

# VIX Zone Size Thresholds (determines expected SPX move)
VIX_ZONE_NARROW = 0.20    # Small moves expected
VIX_ZONE_NORMAL = 0.30    # Normal moves
VIX_ZONE_WIDE = 0.45      # Big moves expected

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
    price: float
    time: datetime
    name: str
    is_secondary: bool = False

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
    move_potential: str = 'NORMAL'  # NARROW, NORMAL, WIDE

@dataclass
class TradeSetup:
    direction: str
    cone_name: str
    cone_width: float
    entry: float
    stop: float
    target_50: float
    target_75: float
    target_100: float
    strike: int
    # Contract pricing
    contract_entry_est: float    # Estimated entry price (e.g., $4.00)
    contract_move_50: float      # Contract price move at 50%
    contract_move_75: float      # Contract price move at 75%
    contract_move_100: float     # Contract price move at 100%
    # Profits per contract
    profit_50: float
    profit_75: float
    profit_100: float
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
    
    IMPORTANT: Zone size is whatever is established between 5pm-2am CT.
    Could be 0.15, 0.30, 0.45, etc. - calculated from bottom/top inputs.
    Extension zones are MULTIPLES of that same zone size.
    
    Zone size also indicates expected SPX move:
    - Narrow (< 0.20): Small moves, reduce size or skip
    - Normal (0.20-0.40): Good setups
    - Wide (> 0.40): Big moves expected, high potential
    """
    
    # Calculate zone size from inputs (NOT fixed at 0.15!)
    zone_size = top - bottom if (top > 0 and bottom > 0 and top > bottom) else 0.15
    
    # Determine move potential based on zone size
    if zone_size < VIX_ZONE_NARROW:
        move_potential = 'NARROW'
    elif zone_size >= VIX_ZONE_WIDE:
        move_potential = 'WIDE'
    else:
        move_potential = 'NORMAL'
    
    # Extension zones are multiples of the SAME zone size
    zones_above = [top + (i * zone_size) for i in range(1, 5)]
    zones_below = [bottom - (i * zone_size) for i in range(1, 5)]
    
    # Default values
    if bottom <= 0 or top <= 0:
        return VIXZone(
            bottom=0, top=0, current=current,
            position_pct=0, status='NO_DATA', bias='UNKNOWN',
            breakout_time='NONE', zones_above=zones_above, zones_below=zones_below,
            zone_size=zone_size, move_potential=move_potential
        )
    
    if current <= 0:
        return VIXZone(
            bottom=bottom, top=top, current=0,
            position_pct=0, status='WAITING', bias='UNKNOWN',
            breakout_time='NONE', zones_above=zones_above, zones_below=zones_below,
            zone_size=zone_size, move_potential=move_potential
        )
    
    # Calculate position percentage
    if zone_size > 0:
        position_pct = ((current - bottom) / zone_size) * 100
    else:
        position_pct = 50
    
    # Determine breakout timing reliability
    ct_now = get_ct_now()
    current_time = ct_now.time()
    
    if time(2, 0) <= current_time < time(6, 30):
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
        zone_size=zone_size, move_potential=move_potential
    )

# ============================================================================
# CONE CALCULATIONS
# ============================================================================

def count_blocks(start: datetime, end: datetime) -> int:
    """Count 30-minute blocks between two times."""
    if end <= start:
        return 1
    diff = (end - start).total_seconds()
    blocks = int(diff // 1800)
    return max(blocks, 1)

def build_cones(pivots: List[Pivot], eval_time: datetime) -> List[Cone]:
    """Build cones from pivots at evaluation time."""
    cones = []
    for pivot in pivots:
        blocks = count_blocks(pivot.time, eval_time)
        ascending = pivot.price + (blocks * SLOPE_PER_30MIN)
        descending = pivot.price - (blocks * SLOPE_PER_30MIN)
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

# ============================================================================
# TRADE SETUP GENERATION
# ============================================================================

def generate_setups(cones: List[Cone], current_price: float, vix_bias: str) -> List[TradeSetup]:
    """
    Generate trade setups with CORRECT profit calculations.
    
    The Math:
    - Delta = 0.33 (contract moves $0.33 for every $1 SPX moves)
    - Cone width = potential SPX move (rail to rail)
    - Contract move = Cone width × Delta
    - Profit = Contract move × $100 (options multiplier)
    
    Example:
    - Cone width: 27 pts
    - Contract move: 27 × 0.33 = 8.91 pts (~$9)
    - If entry at $4.00, exit at $13.00
    - Profit: $9.00 × 100 = $900 per contract
    """
    setups = []
    
    for cone in cones:
        if cone.width < MIN_CONE_WIDTH:
            continue
        
        # ========== CALLS SETUP (Enter at Descending Rail) ==========
        entry_c = cone.descending_rail
        target_c = cone.ascending_rail
        spx_move_c = cone.width  # Full rail-to-rail move
        dist_c = abs(current_price - entry_c)
        
        # Strike: ~17.5 pts OTM from entry for ~0.33 delta
        strike_c = int(entry_c + STRIKE_OTM_DISTANCE)
        strike_c = ((strike_c + 4) // 5) * 5  # Round to nearest 5
        
        # Contract price moves (based on delta)
        contract_move_100_c = spx_move_c * DELTA           # Full move
        contract_move_75_c = spx_move_c * 0.75 * DELTA     # 75% move
        contract_move_50_c = spx_move_c * 0.50 * DELTA     # 50% move
        contract_loss_c = STOP_LOSS_PTS * DELTA            # Stop loss move
        
        # Estimated contract entry price (rough estimate based on OTM distance)
        # This is approximate - real price depends on IV, time, etc.
        contract_entry_c = 4.00  # Typical entry for 15-20pt OTM 0DTE
        
        # Profits per contract (contract move × $100 multiplier)
        profit_100_c = round(contract_move_100_c * CONTRACT_MULTIPLIER, 0)
        profit_75_c = round(contract_move_75_c * CONTRACT_MULTIPLIER, 0)
        profit_50_c = round(contract_move_50_c * CONTRACT_MULTIPLIER, 0)
        risk_c = round(contract_loss_c * CONTRACT_MULTIPLIER, 0)
        
        # R:R ratio (50% profit vs risk)
        rr_c = round(profit_50_c / risk_c, 1) if risk_c > 0 else 0
        
        setups.append(TradeSetup(
            direction='CALLS',
            cone_name=cone.name,
            cone_width=cone.width,
            entry=entry_c,
            stop=round(entry_c - STOP_LOSS_PTS, 2),
            target_50=round(entry_c + spx_move_c * 0.5, 2),
            target_75=round(entry_c + spx_move_c * 0.75, 2),
            target_100=target_c,
            strike=strike_c,
            contract_entry_est=contract_entry_c,
            contract_move_50=round(contract_move_50_c, 2),
            contract_move_75=round(contract_move_75_c, 2),
            contract_move_100=round(contract_move_100_c, 2),
            profit_50=profit_50_c,
            profit_75=profit_75_c,
            profit_100=profit_100_c,
            risk_per_contract=risk_c,
            rr_ratio=rr_c,
            distance=round(dist_c, 2),
            is_active=(dist_c <= 5 and vix_bias == 'CALLS')
        ))
        
        # ========== PUTS SETUP (Enter at Ascending Rail) ==========
        entry_p = cone.ascending_rail
        target_p = cone.descending_rail
        spx_move_p = cone.width  # Full rail-to-rail move
        dist_p = abs(current_price - entry_p)
        
        # Strike: ~17.5 pts OTM from entry for ~0.33 delta
        strike_p = int(entry_p - STRIKE_OTM_DISTANCE)
        strike_p = (strike_p // 5) * 5  # Round to nearest 5
        
        # Contract price moves (based on delta)
        contract_move_100_p = spx_move_p * DELTA
        contract_move_75_p = spx_move_p * 0.75 * DELTA
        contract_move_50_p = spx_move_p * 0.50 * DELTA
        contract_loss_p = STOP_LOSS_PTS * DELTA
        
        contract_entry_p = 4.00
        
        # Profits per contract
        profit_100_p = round(contract_move_100_p * CONTRACT_MULTIPLIER, 0)
        profit_75_p = round(contract_move_75_p * CONTRACT_MULTIPLIER, 0)
        profit_50_p = round(contract_move_50_p * CONTRACT_MULTIPLIER, 0)
        risk_p = round(contract_loss_p * CONTRACT_MULTIPLIER, 0)
        
        rr_p = round(profit_50_p / risk_p, 1) if risk_p > 0 else 0
        
        setups.append(TradeSetup(
            direction='PUTS',
            cone_name=cone.name,
            cone_width=cone.width,
            entry=entry_p,
            stop=round(entry_p + STOP_LOSS_PTS, 2),
            target_50=round(entry_p - spx_move_p * 0.5, 2),
            target_75=round(entry_p - spx_move_p * 0.75, 2),
            target_100=target_p,
            strike=strike_p,
            contract_entry_est=contract_entry_p,
            contract_move_50=round(contract_move_50_p, 2),
            contract_move_75=round(contract_move_75_p, 2),
            contract_move_100=round(contract_move_100_p, 2),
            profit_50=profit_50_p,
            profit_75=profit_75_p,
            profit_100=profit_100_p,
            risk_per_contract=risk_p,
            rr_ratio=rr_p,
            distance=round(dist_p, 2),
            is_active=(dist_p <= 5 and vix_bias == 'PUTS')
        ))
    
    # Sort by distance from current price
    setups.sort(key=lambda x: x.distance)
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
    outcome: str  # 'WIN_50', 'WIN_75', 'WIN_100', 'STOPPED', 'OPEN', 'NO_TRIGGER'
    exit_time: Optional[str]
    exit_price: Optional[float]
    profit: float
    max_favorable: float  # Best price reached in our direction
    max_adverse: float    # Worst price reached against us

def analyze_historical_trades(setups: List[TradeSetup], candles: pd.DataFrame, vix_bias: str) -> List[TradeResult]:
    """
    Analyze what actually happened to each setup on a historical date.
    
    IMPORTANT LOGIC:
    - If price hits 50% target FIRST → WIN (we take profit)
    - If price hits STOP FIRST (before 50%) → LOSS
    - We track the BEST target reached (50%, 75%, or 100%)
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
                        
                        # Check targets FIRST (50% is a win!)
                        if row['High'] >= setup.target_100:
                            best_target_hit = '100'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_100
                            # Don't break yet - want to track full price action
                        elif row['High'] >= setup.target_75 and best_target_hit != '100':
                            best_target_hit = '75'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_75
                        elif row['High'] >= setup.target_50 and best_target_hit not in ['75', '100']:
                            best_target_hit = '50'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_50
                        
                        # Check stop ONLY if no target hit yet
                        if best_target_hit is None and row['Low'] <= setup.stop:
                            outcome = 'STOPPED'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.stop
                            profit = -setup.risk_per_contract
                            break
                    
                    # Set outcome based on best target hit
                    if best_target_hit == '100':
                        outcome = 'WIN_100'
                        profit = setup.profit_100
                    elif best_target_hit == '75':
                        outcome = 'WIN_75'
                        profit = setup.profit_75
                    elif best_target_hit == '50':
                        outcome = 'WIN_50'
                        profit = setup.profit_50
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
                        
                        # Check targets FIRST (50% is a win!)
                        if row['Low'] <= setup.target_100:
                            best_target_hit = '100'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_100
                        elif row['Low'] <= setup.target_75 and best_target_hit != '100':
                            best_target_hit = '75'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_75
                        elif row['Low'] <= setup.target_50 and best_target_hit not in ['75', '100']:
                            best_target_hit = '50'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.target_50
                        
                        # Check stop ONLY if no target hit yet
                        if best_target_hit is None and row['High'] >= setup.stop:
                            outcome = 'STOPPED'
                            exit_time = idx.strftime('%H:%M')
                            exit_price = setup.stop
                            profit = -setup.risk_per_contract
                            break
                    
                    # Set outcome based on best target hit
                    if best_target_hit == '100':
                        outcome = 'WIN_100'
                        profit = setup.profit_100
                    elif best_target_hit == '75':
                        outcome = 'WIN_75'
                        profit = setup.profit_75
                    elif best_target_hit == '50':
                        outcome = 'WIN_50'
                        profit = setup.profit_50
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
    """Fetch prior session High, Low, Close."""
    try:
        spx = yf.Ticker("^GSPC")
        end = session_date
        start = end - timedelta(days=10)
        
        df_daily = spx.history(start=start, end=end, interval='1d')
        if len(df_daily) < 1:
            return None
        
        last = df_daily.iloc[-1]
        prior_date = df_daily.index[-1]
        
        # Get intraday for pivot times
        df_intra = spx.history(start=start, end=end, interval='30m')
        high_time = CT_TZ.localize(datetime.combine(prior_date.date(), time(12, 0)))
        low_time = CT_TZ.localize(datetime.combine(prior_date.date(), time(12, 0)))
        
        if not df_intra.empty:
            df_intra.index = df_intra.index.tz_convert(CT_TZ)
            day_data = df_intra[df_intra.index.date == prior_date.date()]
            if not day_data.empty:
                high_time = day_data['High'].idxmax()
                low_time = day_data['Low'].idxmin()
        
        return {
            'high': float(last['High']),
            'low': float(last['Low']),
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
    is_historical: bool = False
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
    
    # Move potential indicator
    if vix.move_potential == 'WIDE':
        move_icon = '🔥'
        move_text = f'HIGH POTENTIAL (Zone: {vix.zone_size:.2f})'
        move_color = '#059669'
        move_bg = '#ecfdf5'
    elif vix.move_potential == 'NARROW':
        move_icon = '⚠️'
        move_text = f'LOW POTENTIAL (Zone: {vix.zone_size:.2f})'
        move_color = '#d97706'
        move_bg = '#fffbeb'
    else:
        move_icon = '✓'
        move_text = f'NORMAL (Zone: {vix.zone_size:.2f})'
        move_color = '#6b7280'
        move_bg = '#f9fafb'
    
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
                    <div style="font-size:10px;color:#6b7280;text-transform:uppercase;">Target</div>
                    <div style="font-family:'DM Mono',monospace;font-size:14px;font-weight:600;color:#059669;">{s.target_100:.2f}</div>
                </div>
                <div>
                    <div style="font-size:10px;color:#6b7280;text-transform:uppercase;">Strike</div>
                    <div style="font-family:'DM Mono',monospace;font-size:14px;font-weight:600;color:{dir_color};">{s.strike}{'C' if s.direction == 'CALLS' else 'P'}</div>
                </div>
            </div>
            
            <!-- Contract Move Info -->
            <div style="font-size:11px;color:#6b7280;margin-bottom:8px;padding:0 4px;">
                Contract moves ~${s.contract_move_100:.2f} on full rail-to-rail ({s.cone_width:.0f} × 0.33 delta)
            </div>
            
            <!-- Profits Per Contract -->
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding-top:12px;border-top:1px solid #e5e7eb;">
                <div style="text-align:center;">
                    <div style="font-size:10px;color:#6b7280;">50% Move</div>
                    <div style="font-family:'DM Mono',monospace;font-size:15px;font-weight:700;color:#059669;">${s.profit_50:,.0f}</div>
                    <div style="font-size:9px;color:#9ca3af;">/contract</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:10px;color:#6b7280;">75% Move</div>
                    <div style="font-family:'DM Mono',monospace;font-size:15px;font-weight:700;color:#059669;">${s.profit_75:,.0f}</div>
                    <div style="font-size:9px;color:#9ca3af;">/contract</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:10px;color:#6b7280;">100% Move</div>
                    <div style="font-family:'DM Mono',monospace;font-size:15px;font-weight:700;color:#059669;">${s.profit_100:,.0f}</div>
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
    
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            * {{ margin:0; padding:0; box-sizing:border-box; font-family:'DM Sans',system-ui,sans-serif; }}
            body {{ background:#f8fafc; color:#1f2937; }}
            
            .dashboard {{ max-width:1400px; margin:0 auto; padding:20px; }}
            
            /* Header */
            .header {{
                background:linear-gradient(135deg,#1e293b 0%,#334155 100%);
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
                background:white;
                border-radius:16px;
                border:1px solid #e5e7eb;
                overflow:hidden;
                box-shadow:0 1px 3px rgba(0,0,0,0.04);
            }}
            .card-header {{
                padding:16px 20px;
                border-bottom:1px solid #f3f4f6;
                font-weight:600;
                font-size:14px;
                color:#374151;
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
            .signal-action {{ font-size:14px; color:#4b5563; margin-top:8px; line-height:1.5; }}
            
            /* VIX Zone */
            .vix-zone {{ margin-top:16px; }}
            .zone-box {{
                border-radius:12px;
                padding:14px;
                text-align:center;
                margin-bottom:8px;
            }}
            .zone-top {{ background:linear-gradient(135deg,#ecfdf5,#d1fae5); border:2px solid #10b981; }}
            .zone-current {{ background:#1e293b; }}
            .zone-bottom {{ background:linear-gradient(135deg,#fef2f2,#fee2e2); border:2px solid #ef4444; }}
            .zone-label {{ font-size:11px; text-transform:uppercase; letter-spacing:0.5px; font-weight:600; }}
            .zone-value {{ font-family:'DM Mono',monospace; font-size:24px; font-weight:700; margin:6px 0; }}
            .zone-hint {{ font-size:11px; }}
            
            /* Table */
            table {{ width:100%; border-collapse:collapse; }}
            th {{ text-align:left; padding:12px; background:#f9fafb; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; color:#6b7280; font-weight:600; }}
            td {{ padding:10px 12px; border-bottom:1px solid #f3f4f6; font-size:14px; }}
            
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
            .check-wait {{ background:#f9fafb; color:#6b7280; }}
            .check-fail {{ background:#fef2f2; color:#991b1b; }}
        </style>
    </head>
    <body>
        <div class="dashboard">
            <!-- Header -->
            <div class="header">
                <div class="logo">
                    <div class="logo-icon">📈</div>
                    <div class="logo-text">
                        <div class="logo-title">SPX PROPHET</div>
                        <div class="logo-sub">Daily Trading Plan • {ct_now.strftime('%b %d, %Y')}</div>
                    </div>
                </div>
                <div class="header-stats">
                    <div class="stat">
                        <div class="stat-label">SPX</div>
                        <div class="stat-value">{spx:,.2f}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">VIX</div>
                        <div class="stat-value">{f'{vix.current:.2f}' if vix.current > 0 else '—'}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Time CT</div>
                        <div class="stat-value">{ct_now.strftime('%H:%M')}</div>
                    </div>
                </div>
            </div>
            
            <!-- Warning Banner -->
            <div class="warning-banner">
                <div class="warning-icon">⏱️</div>
                <div class="warning-text">
                    <strong>30-MINUTE CANDLE CLOSE MATTERS:</strong> VIX wicks can pierce levels — always wait for the candle to CLOSE before confirming signal.
                </div>
            </div>
            
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
                            
                            <!-- Move Potential Indicator -->
                            <div style="margin-top:16px;padding:12px 16px;background:{move_bg};border-radius:10px;border:1px solid {move_color}20;">
                                <div style="display:flex;align-items:center;gap:8px;">
                                    <span style="font-size:20px;">{move_icon}</span>
                                    <div>
                                        <div style="font-weight:600;font-size:13px;color:{move_color};">{move_text}</div>
                                        <div style="font-size:11px;color:#6b7280;">Wider zone = Bigger SPX moves expected</div>
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
            
            <!-- Checklist -->
            <div class="card" style="margin-top:20px;">
                <div class="card-header">📋 Entry Checklist</div>
                <div class="card-body">
                    <div class="grid grid-2">
                        <div class="checklist">
                            <div class="check-item {'check-pass' if vix.bias in ['CALLS','PUTS'] else 'check-wait'}">
                                {'✓' if vix.bias in ['CALLS','PUTS'] else '⏳'} VIX at zone edge (clear bias)
                            </div>
                            <div class="check-item {'check-pass' if vix.breakout_time == 'RELIABLE' else 'check-fail' if vix.breakout_time == 'DANGER' else 'check-wait'}">
                                {'✓' if vix.breakout_time == 'RELIABLE' else '⚠️' if vix.breakout_time == 'DANGER' else '⏳'} Breakout timing ({'Reliable window ✓' if vix.breakout_time == 'RELIABLE' else 'DANGER window - reversal risk!' if vix.breakout_time == 'DANGER' else 'RTH - use 30-min close'})
                            </div>
                        </div>
                        <div class="checklist">
                            <div class="check-item check-wait">
                                ⏳ Price at rail entry (check distance)
                            </div>
                            <div class="check-item check-wait">
                                ⏳ 30-min candle CLOSED (not just wick)
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
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
    
    # Initialize session state
    if 'vix_bottom' not in st.session_state:
        st.session_state.vix_bottom = 0.0
        st.session_state.vix_top = 0.0
        st.session_state.vix_current = 0.0
        st.session_state.sec_high = 0.0
        st.session_state.sec_high_time = "12:00"
        st.session_state.sec_low = 0.0
        st.session_state.sec_low_time = "12:00"
        st.session_state.use_sec_high = False
        st.session_state.use_sec_low = False
        st.session_state.manual_high = 0.0
        st.session_state.manual_low = 0.0
        st.session_state.manual_close = 0.0
        st.session_state.use_manual_pivots = False
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 📅 Session")
        session_date = st.date_input("Date", value=datetime.now().date())
        session_dt = datetime.combine(session_date, time(0, 0))
        
        st.markdown("### 📊 VIX Zone (5pm-2am CT)")
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.vix_bottom = st.number_input("Bottom", min_value=0.0, max_value=100.0, value=st.session_state.vix_bottom, step=0.01, format="%.2f")
        with col2:
            st.session_state.vix_top = st.number_input("Top", min_value=0.0, max_value=100.0, value=st.session_state.vix_top, step=0.01, format="%.2f")
        
        st.session_state.vix_current = st.number_input("Current VIX", min_value=0.0, max_value=100.0, value=st.session_state.vix_current, step=0.01, format="%.2f")
        
        st.markdown("### 📈 Prior Day Pivots")
        st.session_state.use_manual_pivots = st.checkbox("Manual Input", value=st.session_state.use_manual_pivots, help="Override auto-fetched data")
        
        if st.session_state.use_manual_pivots:
            st.session_state.manual_high = st.number_input("High", min_value=0.0, max_value=10000.0, value=st.session_state.manual_high, step=0.25, format="%.2f", key="man_h")
            st.session_state.manual_low = st.number_input("Low", min_value=0.0, max_value=10000.0, value=st.session_state.manual_low, step=0.25, format="%.2f", key="man_l")
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
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Fetch data
    prior = fetch_prior_session(session_dt)
    
    # Use manual pivots if enabled, otherwise use fetched data
    if st.session_state.use_manual_pivots and st.session_state.manual_high > 0:
        prior_high = st.session_state.manual_high
        prior_low = st.session_state.manual_low
        prior_close = st.session_state.manual_close
        # Use noon as default time for manual pivots
        high_time = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(12, 0)))
        low_time = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(12, 0)))
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
    
    # Build pivots
    pivots = []
    if prior_high > 0:
        pivots = [
            Pivot(prior_high, high_time, 'High'),
            Pivot(prior_low, low_time, 'Low'),
            Pivot(prior_close, CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(15, 0))), 'Close'),
        ]
        
        # Add High² if enabled (independent)
        if st.session_state.use_sec_high and st.session_state.sec_high > 0:
            try:
                h, m = map(int, st.session_state.sec_high_time.split(':'))
                t = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(h, m)))
                pivots.append(Pivot(st.session_state.sec_high, t, 'High²', True))
            except:
                pass
        
        # Add Low² if enabled (independent)
        if st.session_state.use_sec_low and st.session_state.sec_low > 0:
            try:
                h, m = map(int, st.session_state.sec_low_time.split(':'))
                t = CT_TZ.localize(datetime.combine(session_date - timedelta(days=1), time(h, m)))
                pivots.append(Pivot(st.session_state.sec_low, t, 'Low²', True))
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
    
    # Render
    html = render_dashboard(
        spx, vix, cones, setups, assessment, prior,
        historical_results=historical_results,
        session_data=session_data,
        is_historical=is_historical
    )
    
    # Adjust height based on historical content
    height = 1800 if is_historical and historical_results else 1400
    components.html(html, height=height, scrolling=True)

if __name__ == "__main__":
    main()
