"""
SPX Prophet - Where Structure Becomes Foresight
LEGENDARY EDITION
A professional institutional-grade SPX trading assistant
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
# CONFIGURATION & CONSTANTS
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

# SLOPES - Symmetric ±0.45 pts per 30-min block (calibrated to TradingView)
SLOPE_ASCENDING = 0.45
SLOPE_DESCENDING = 0.45

# CONTRACT FACTOR: A 15-20pt OTM option moves ~0.30-0.35x the underlying
# Using 0.33 as middle estimate. Actual delta varies with time and distance OTM.
CONTRACT_FACTOR = 0.33

# Market hours
MAINTENANCE_START_CT = time(16, 0)
MAINTENANCE_END_CT = time(17, 0)
POWER_HOUR_START = time(14, 0)  # Highs after 2pm are less reliable pivots

# Pre-market window (for detecting pre-market pivots from ES)
PREMARKET_START_CT = time(6, 0)
PREMARKET_END_CT = time(8, 30)

# Secondary Pivot Detection
SECONDARY_PIVOT_MIN_PULLBACK_PCT = 0.003  # 0.3% = ~18 pts on SPX 6000
SECONDARY_PIVOT_MIN_DISTANCE = 5.0  # At least 5 points from primary
SECONDARY_PIVOT_START_TIME = time(13, 0)  # After structure develops

# ============================================================================
# CORE TRADING THRESHOLDS - These directly affect trade decisions
# ============================================================================

# Cone width: Need at least 25 pts to have meaningful 0DTE trade
# Math: 25 pts × 50% target = 12.5 pt move × 0.33 delta × $100 = $412 profit
# This justifies the risk of a $100 stop
MIN_CONE_WIDTH = 25.0

# Entry threshold: Within 5 pts of rail = actionable entry
# Beyond 5 pts = wait for price to come to you
AT_RAIL_THRESHOLD = 5.0

# Stop loss: 3 pts from entry
# Math: 3 pts × 0.33 delta × $100 = ~$100 risk per contract
STOP_LOSS_PTS = 3.0

# Strike offset: 15-20 pts OTM for ~0.30-0.35 delta
STRIKE_OFFSET = 17.5

# Minimum R:R to take a trade: At least 3:1 at 50% target
# Below this, risk doesn't justify reward
MIN_RR_RATIO = 3.0

# Rail touch threshold: Within 2 pts = ES "touched" the rail
RAIL_TOUCH_THRESHOLD = 2.0

# Confluence: Rails within 5 pts of each other = converging
CONFLUENCE_THRESHOLD = 5.0

# ============================================================================
# TIME DECAY (THETA) - Critical for 0DTE
# ============================================================================
# 0DTE options lose value rapidly. These multipliers adjust expected profit
# based on time remaining. Derived from typical theta decay curves.
#
# Morning (8:30-10:00): Full value, theta hasn't kicked in hard yet
# Mid-day (10:00-12:00): ~85% of theoretical value (theta accelerating)
# Afternoon (12:00-14:00): ~65% of theoretical value (theta crushing)
# Late (14:00+): ~40% of theoretical value (avoid new entries)

THETA_MULTIPLIER = {
    'morning': 1.0,      # 8:30-10:00 CT
    'mid_day': 0.85,     # 10:00-12:00 CT  
    'afternoon': 0.65,   # 12:00-14:00 CT
    'late': 0.40,        # 14:00+ CT - generally avoid
}

# Last reasonable entry time for 0DTE
LAST_ENTRY_TIME = time(13, 30)  # After 1:30pm, theta too aggressive

# ============================================================================
# DELTA APPROXIMATION BY DISTANCE OTM
# ============================================================================
# More accurate than fixed 0.33 - delta decreases as you go further OTM
# These are approximate for SPX 0DTE options mid-morning

DELTA_BY_OTM = {
    10: 0.42,   # 10 pts OTM
    15: 0.35,   # 15 pts OTM  
    20: 0.30,   # 20 pts OTM (our target zone)
    25: 0.25,   # 25 pts OTM
    30: 0.20,   # 30 pts OTM
}

def get_delta_estimate(otm_distance: float) -> float:
    """Estimate delta based on distance OTM."""
    if otm_distance <= 10:
        return 0.42
    elif otm_distance <= 15:
        return 0.35
    elif otm_distance <= 20:
        return 0.30
    elif otm_distance <= 25:
        return 0.25
    else:
        return 0.20

def get_theta_multiplier() -> Tuple[float, str]:
    """Get current theta multiplier based on time of day."""
    ct_now = get_ct_now().time()
    
    if ct_now < time(10, 0):
        return THETA_MULTIPLIER['morning'], 'morning'
    elif ct_now < time(12, 0):
        return THETA_MULTIPLIER['mid_day'], 'mid_day'
    elif ct_now < time(14, 0):
        return THETA_MULTIPLIER['afternoon'], 'afternoon'
    else:
        return THETA_MULTIPLIER['late'], 'late'

TIME_BLOCKS = [
    time(8, 30), time(9, 0), time(9, 30), time(10, 0), time(10, 30),
    time(11, 0), time(11, 30), time(12, 0), time(12, 30), time(13, 0),
    time(13, 30), time(14, 0), time(14, 30)
]

HIGHLIGHT_TIMES = [time(8, 30), time(10, 0)]

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
    name: str
    pivot: Pivot
    ascending_rail: float
    descending_rail: float
    width: float
    blocks_from_pivot: int

@dataclass
class ContractExpectation:
    direction: str
    entry_price: float
    entry_rail: str
    target_50_underlying: float
    target_75_underlying: float
    target_100_underlying: float
    stop_underlying: float
    expected_underlying_move_50: float
    expected_underlying_move_100: float
    contract_profit_50: float
    contract_profit_75: float
    contract_profit_100: float
    risk_reward_50: float

@dataclass
class RegimeAnalysis:
    """Simplified regime - only keep what matters for trading decisions."""
    overnight_range: float  # How much ES moved overnight
    overnight_range_pct: float  # As percentage of cone
    overnight_touched_rails: List[str]  # Which rails ES touched
    opening_position: str  # Where price opened relative to cone
    es_spx_offset: float  # Current ES-SPX spread

@dataclass 
class ActionCard:
    direction: str
    active_cone: str
    active_rail: str
    entry_level: float
    target_50: float
    target_75: float
    target_100: float
    stop_level: float
    contract_expectation: Optional[ContractExpectation]
    position_size: str
    confluence_score: int
    warnings: List[str]
    color: str

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_ct_now() -> datetime:
    return datetime.now(CT_TZ)

def to_ct(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = ET_TZ.localize(dt)
    return dt.astimezone(CT_TZ)

def count_30min_blocks(start_time: datetime, end_time: datetime) -> int:
    """
    Count 30-minute blocks between two times, skipping:
    - Daily maintenance window: 4pm-5pm CT (16:00-17:00)
    - Weekend: Friday 4pm CT to Sunday 5pm CT
    
    TradingView behavior: Friday's last candle is 3:30pm, next candle is Sunday 5pm.
    So we skip Friday after 4pm, all of Saturday, and Sunday until 5pm.
    """
    if start_time >= end_time:
        return 0
    
    blocks = 0
    current = start_time
    
    FRIDAY_CUTOFF = time(16, 0)  # Friday stops at 4pm CT
    SUNDAY_RESUME = time(17, 0)  # Sunday resumes at 5pm CT
    
    while current < end_time:
        current_ct = current.astimezone(CT_TZ)
        current_ct_time = current_ct.time()
        current_weekday = current_ct.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        
        # Friday after 4pm - SKIP (weekend started)
        if current_weekday == 4 and current_ct_time >= FRIDAY_CUTOFF:
            current = current + timedelta(minutes=30)
            continue
        
        # Saturday - SKIP entirely
        if current_weekday == 5:
            current = current + timedelta(minutes=30)
            continue
        
        # Sunday before 5pm - SKIP
        if current_weekday == 6 and current_ct_time < SUNDAY_RESUME:
            current = current + timedelta(minutes=30)
            continue
        
        # Daily maintenance window (4pm-5pm CT) on weekdays
        # (Friday after 4pm is already handled above)
        if MAINTENANCE_START_CT <= current_ct_time < MAINTENANCE_END_CT:
            current = current + timedelta(minutes=30)
            continue
        
        blocks += 1
        current = current + timedelta(minutes=30)
    
    return blocks

def project_rail(pivot_price: float, blocks: int, direction: str) -> float:
    if direction == 'ascending':
        return pivot_price + (blocks * SLOPE_ASCENDING)
    else:
        return pivot_price - (blocks * SLOPE_DESCENDING)

def get_position_in_cone(price: float, ascending_rail: float, descending_rail: float) -> Tuple[str, float]:
    """Determine if price is at a rail or in dead zone."""
    cone_width = ascending_rail - descending_rail
    if cone_width <= 0:
        return 'invalid', 0
    
    distance_to_lower = abs(price - descending_rail)
    distance_to_upper = abs(price - ascending_rail)
    
    # At rail = within AT_RAIL_THRESHOLD (5 pts)
    if distance_to_lower <= AT_RAIL_THRESHOLD:
        return 'lower_edge', distance_to_lower
    elif distance_to_upper <= AT_RAIL_THRESHOLD:
        return 'upper_edge', distance_to_upper
    else:
        return 'dead_zone', min(distance_to_upper, distance_to_lower)

# ============================================================================
# DATA FETCHING WITH POWER HOUR FILTER
# ============================================================================

@st.cache_data(ttl=300)
def fetch_prior_session_data(session_date: datetime) -> Optional[Dict]:
    """
    Fetch prior session data with both candlestick (wick) and line chart (close) pivot detection.
    Line chart values are RECOMMENDED as they represent true structure turning points.
    """
    try:
        prior_date = session_date - timedelta(days=1)
        while prior_date.weekday() >= 5:
            prior_date = prior_date - timedelta(days=1)
        
        spx = yf.Ticker("^GSPC")
        start_date = prior_date.strftime('%Y-%m-%d')
        end_date = (prior_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        df_intraday = spx.history(start=start_date, end=end_date, interval='30m')
        
        if df_intraday.empty:
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
                'close': row['Close'],
                'close_time': close_time,
                'open': row['Open'],
                'range': row['High'] - row['Low'],
                'range_pct': (row['High'] - row['Low']) / row['Close'],
                'power_hour_filtered': False,
                'secondary_high': None,
                'secondary_high_time': None,
                'secondary_low': None,
                'secondary_low_time': None,
                # Line chart values
                'high_line': row['Close'],
                'high_line_time': close_time,
                'low_line': row['Close'],
                'low_line_time': close_time,
                'secondary_high_line': None,
                'secondary_high_line_time': None,
                'secondary_low_line': None,
                'secondary_low_line_time': None
            }
        
        # Convert index to CT
        df = df_intraday.copy()
        df.index = df.index.tz_convert(CT_TZ)
        
        # ============================================================
        # CANDLESTICK (WICK) BASED DETECTION
        # ============================================================
        df_before_power = df[df.index.time < POWER_HOUR_START]
        
        power_hour_filtered = False
        if not df_before_power.empty:
            overall_high_idx = df['High'].idxmax()
            if overall_high_idx.time() >= POWER_HOUR_START:
                high_idx = df_before_power['High'].idxmax()
                power_hour_filtered = True
            else:
                high_idx = overall_high_idx
        else:
            high_idx = df['High'].idxmax()
        
        low_idx = df['Low'].idxmin()
        
        high_price = df.loc[high_idx, 'High']
        high_time = high_idx
        low_price = df.loc[low_idx, 'Low']
        low_time = low_idx
        close_price = df['Close'].iloc[-1]
        close_time = CT_TZ.localize(datetime.combine(prior_date, time(15, 0)))
        
        # ============================================================
        # LINE CHART BASED DETECTION (Using Close prices)
        # This is more accurate for structure detection
        # ============================================================
        if not df_before_power.empty:
            overall_high_close_idx = df['Close'].idxmax()
            if overall_high_close_idx.time() >= POWER_HOUR_START:
                high_line_idx = df_before_power['Close'].idxmax()
            else:
                high_line_idx = overall_high_close_idx
        else:
            high_line_idx = df['Close'].idxmax()
        
        low_line_idx = df['Close'].idxmin()
        
        high_line_price = df.loc[high_line_idx, 'Close']
        high_line_time = high_line_idx
        low_line_price = df.loc[low_line_idx, 'Close']
        low_line_time = low_line_idx
        
        # ============================================================
        # SECONDARY HIGH DETECTION - Using LINE CHART (Close prices)
        # Pattern: Primary High -> Drop -> LOCAL PEAK (Secondary High) -> Drop
        # 
        # Key insight: We need to find the FIRST local peak after the high,
        # not the bounce after the absolute low. The secondary high is a
        # failed attempt to make a new high.
        # ============================================================
        secondary_high_line = None
        secondary_high_line_time = None
        
        df_after_high = df[df.index > high_line_idx]
        
        if len(df_after_high) >= 3:
            closes = df_after_high['Close'].values
            indices = df_after_high.index.tolist()
            
            # Look for local peaks: price higher than both neighbors
            for i in range(1, len(closes) - 1):
                prev_close = closes[i - 1]
                curr_close = closes[i]
                next_close = closes[i + 1]
                
                # Is this a local peak? (higher than both neighbors)
                if curr_close > prev_close and curr_close > next_close:
                    # Is it lower than primary high? (required for secondary)
                    if curr_close < high_line_price:
                        # Is it at least 5 points below primary?
                        if (high_line_price - curr_close) >= SECONDARY_PIVOT_MIN_DISTANCE:
                            # Found the first valid secondary high
                            secondary_high_line = curr_close
                            secondary_high_line_time = indices[i]
                            break
        
        # ============================================================
        # SECONDARY LOW DETECTION - Using LINE CHART (Close prices)
        # Pattern: Primary Low -> Rise -> LOCAL TROUGH (Secondary Low) -> Rise
        # 
        # Similar to secondary high, we find the FIRST local trough after
        # the primary low, not the dip after the absolute high.
        # ============================================================
        secondary_low_line = None
        secondary_low_line_time = None
        
        df_after_low = df[df.index > low_line_idx]
        
        # Exclude secondary high candle if it exists
        if secondary_high_line_time is not None:
            df_after_low = df_after_low[df_after_low.index != secondary_high_line_time]
        
        if len(df_after_low) >= 3:
            closes = df_after_low['Close'].values
            indices = df_after_low.index.tolist()
            
            # Look for local troughs: price lower than both neighbors
            for i in range(1, len(closes) - 1):
                prev_close = closes[i - 1]
                curr_close = closes[i]
                next_close = closes[i + 1]
                
                # Is this a local trough? (lower than both neighbors)
                if curr_close < prev_close and curr_close < next_close:
                    # Is it higher than primary low? (required for secondary)
                    if curr_close > low_line_price:
                        # Is it at least 5 points above primary?
                        if (curr_close - low_line_price) >= SECONDARY_PIVOT_MIN_DISTANCE:
                            # Found the first valid secondary low
                            secondary_low_line = curr_close
                            secondary_low_line_time = indices[i]
                            break
        
        # Candlestick secondary detection (for reference) - using same local peak logic
        secondary_high = None
        secondary_high_time = None
        secondary_low = None
        secondary_low_time = None
        
        df_after_high_candle = df[df.index > high_idx]
        if len(df_after_high_candle) >= 3:
            highs = df_after_high_candle['High'].values
            indices_candle = df_after_high_candle.index.tolist()
            
            for i in range(1, len(highs) - 1):
                if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                    if highs[i] < high_price and (high_price - highs[i]) >= SECONDARY_PIVOT_MIN_DISTANCE:
                        secondary_high = highs[i]
                        secondary_high_time = indices_candle[i]
                        break
        
        df_after_low_candle = df[df.index > low_idx]
        if secondary_high_time is not None:
            df_after_low_candle = df_after_low_candle[df_after_low_candle.index != secondary_high_time]
        if len(df_after_low_candle) >= 3:
            lows = df_after_low_candle['Low'].values
            indices_candle = df_after_low_candle.index.tolist()
            
            for i in range(1, len(lows) - 1):
                if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                    if lows[i] > low_price and (lows[i] - low_price) >= SECONDARY_PIVOT_MIN_DISTANCE:
                        secondary_low = lows[i]
                        secondary_low_time = indices_candle[i]
                        break
        
        return {
            'date': prior_date,
            # Candlestick (wick) values
            'high': high_price,
            'high_time': high_time,
            'low': low_price,
            'low_time': low_time,
            'close': close_price,
            'close_time': close_time,
            'open': df['Open'].iloc[0],
            'range': df['High'].max() - df['Low'].min(),
            'range_pct': (df['High'].max() - df['Low'].min()) / close_price,
            'power_hour_filtered': power_hour_filtered,
            'secondary_high': secondary_high,
            'secondary_high_time': secondary_high_time,
            'secondary_low': secondary_low,
            'secondary_low_time': secondary_low_time,
            # LINE CHART values (RECOMMENDED)
            'high_line': high_line_price,
            'high_line_time': high_line_time,
            'low_line': low_line_price,
            'low_line_time': low_line_time,
            'secondary_high_line': secondary_high_line,
            'secondary_high_line_time': secondary_high_line_time,
            'secondary_low_line': secondary_low_line,
            'secondary_low_line_time': secondary_low_line_time
        }
        
    except Exception as e:
        st.error(f"Error fetching SPX data: {e}")
        return None

def fetch_premarket_pivots(session_date: datetime) -> Optional[Dict]:
    """
    Fetch pre-market high/low from the PREVIOUS day's pre-market session (6am-8:30am CT).
    These become pivots for TODAY's trading session.
    Uses ES futures data since SPX doesn't trade pre-market.
    """
    try:
        # Get the prior trading day
        prior_date = session_date - timedelta(days=1)
        while prior_date.weekday() >= 5:  # Skip weekends
            prior_date = prior_date - timedelta(days=1)
        
        # Fetch ES futures data
        es = yf.Ticker("ES=F")
        start_date = prior_date - timedelta(days=1)
        end_date = prior_date + timedelta(days=1)
        
        df = es.history(start=start_date, end=end_date, interval='30m')
        
        if df.empty:
            return None
        
        df.index = df.index.tz_convert(CT_TZ)
        
        # Filter to pre-market window (6am - 8:30am CT) on prior_date
        premarket_start = CT_TZ.localize(datetime.combine(prior_date, PREMARKET_START_CT))
        premarket_end = CT_TZ.localize(datetime.combine(prior_date, PREMARKET_END_CT))
        
        df_premarket = df[(df.index >= premarket_start) & (df.index < premarket_end)]
        
        if df_premarket.empty or len(df_premarket) < 2:
            return None
        
        # Find pre-market high and low
        premarket_high = df_premarket['High'].max()
        premarket_low = df_premarket['Low'].min()
        premarket_high_idx = df_premarket['High'].idxmax()
        premarket_low_idx = df_premarket['Low'].idxmin()
        
        # Get ES-SPX offset to convert ES prices to SPX equivalent
        # We'll use a typical offset of ~60 points, but this will be adjusted by user if needed
        
        return {
            'premarket_high_es': premarket_high,
            'premarket_low_es': premarket_low,
            'premarket_high_time': premarket_high_idx,
            'premarket_low_time': premarket_low_idx,
            'date': prior_date
        }
        
    except Exception as e:
        return None

@st.cache_data(ttl=300)
def fetch_es_overnight_data(session_date: datetime) -> Optional[Dict]:
    try:
        prior_date = session_date - timedelta(days=1)
        while prior_date.weekday() >= 5:
            prior_date = prior_date - timedelta(days=1)
        
        es = yf.Ticker("ES=F")
        spx = yf.Ticker("^GSPC")
        
        start_date = prior_date.strftime('%Y-%m-%d')
        end_date = (session_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        df_es = es.history(start=start_date, end=end_date, interval='5m')
        df_spx = spx.history(start=start_date, end=end_date, interval='30m')
        
        if df_es.empty:
            return {'offset': 0, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0, 'df_overnight': None}
        
        offset = 0
        if not df_spx.empty:
            try:
                spx_close = df_spx['Close'].iloc[-1]
                es_at_time = df_es[df_es.index.tz_convert(CT_TZ).time <= time(14, 30)]
                if not es_at_time.empty:
                    es_price = es_at_time['Close'].iloc[-1]
                    offset = es_price - spx_close
            except:
                offset = 0
        
        overnight_start = CT_TZ.localize(datetime.combine(prior_date, time(17, 0)))
        overnight_end = CT_TZ.localize(datetime.combine(session_date, time(8, 30)))
        
        df_es_tz = df_es.copy()
        df_es_tz.index = df_es_tz.index.tz_convert(CT_TZ)
        
        overnight_mask = (df_es_tz.index >= overnight_start) & (df_es_tz.index <= overnight_end)
        df_overnight = df_es_tz[overnight_mask]
        
        if df_overnight.empty:
            return {'offset': offset, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0, 'df_overnight': None}
        
        overnight_high = df_overnight['High'].max()
        overnight_low = df_overnight['Low'].min()
        
        return {
            'offset': offset,
            'overnight_high': overnight_high,
            'overnight_low': overnight_low,
            'overnight_high_spx': overnight_high - offset,
            'overnight_low_spx': overnight_low - offset,
            'overnight_range': overnight_high - overnight_low,
            'df_overnight': df_overnight
        }
        
    except Exception as e:
        return {'offset': 0, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0, 'df_overnight': None}

def validate_overnight_rails(es_data: Dict, pivots: List[Pivot], secondary_high: float, secondary_high_time: datetime, 
                             secondary_low: float, secondary_low_time: datetime, session_date: datetime) -> Dict:
    """
    Validate which rails overnight ES touched and respected.
    
    Rules:
    - "Touched and rejected" = came within 1 point and bounced
    - If overnight broke secondary but held primary = skip secondary
    - If neither tested = both are candidates
    
    Returns dict with validation status for each structure.
    """
    
    validation = {
        'high_primary_validated': False,
        'high_primary_broken': False,
        'high_secondary_validated': False,
        'high_secondary_broken': False,
        'low_primary_validated': False,
        'low_primary_broken': False,
        'low_secondary_validated': False,
        'low_secondary_broken': False,
        'active_high_structure': None,  # 'primary', 'secondary', 'both', or None
        'active_low_structure': None,   # 'primary', 'secondary', 'both', or None
        'high_structures_to_show': [],
        'low_structures_to_show': [],
        'validation_notes': []
    }
    
    if not es_data or es_data.get('overnight_low_spx') is None:
        validation['active_high_structure'] = 'both'
        validation['active_low_structure'] = 'both'
        validation['high_structures_to_show'] = ['primary', 'secondary'] if secondary_high else ['primary']
        validation['low_structures_to_show'] = ['primary', 'secondary'] if secondary_low else ['primary']
        validation['validation_notes'].append("No overnight data - showing all structures")
        return validation
    
    overnight_low_spx = es_data['overnight_low_spx']
    overnight_high_spx = es_data['overnight_high_spx']
    
    # Get primary pivot prices
    high_pivot = next((p for p in pivots if p.name == 'High'), None)
    low_pivot = next((p for p in pivots if p.name == 'Low'), None)
    
    if not high_pivot or not low_pivot:
        return validation
    
    # Calculate projected rails at a reference time (use 8:30 AM next day)
    eval_time = CT_TZ.localize(datetime.combine(session_date, time(8, 30)))
    
    # Primary High descending rail
    blocks_high = count_30min_blocks(high_pivot.time, eval_time)
    primary_high_desc = project_rail(high_pivot.price, blocks_high, 'descending')
    
    # Primary Low ascending rail  
    blocks_low = count_30min_blocks(low_pivot.time, eval_time)
    primary_low_asc = project_rail(low_pivot.price, blocks_low, 'ascending')
    
    # ========== HIGH STRUCTURE VALIDATION ==========
    # Check if overnight low touched/broke primary high descending rail
    
    touch_threshold = 1.0  # Within 1 point = touched
    
    # Primary High Descending - did overnight low touch it?
    dist_to_primary_high_desc = overnight_low_spx - primary_high_desc
    
    if dist_to_primary_high_desc <= touch_threshold and dist_to_primary_high_desc >= -touch_threshold:
        # Touched within 1 point
        validation['high_primary_validated'] = True
        validation['validation_notes'].append(f"✓ Primary High desc ({primary_high_desc:.2f}) touched and held")
    elif dist_to_primary_high_desc < -touch_threshold:
        # Broke through (overnight low went below the rail)
        validation['high_primary_broken'] = True
        validation['validation_notes'].append(f"✗ Primary High desc ({primary_high_desc:.2f}) was broken")
    
    # Secondary High Descending (if exists)
    if secondary_high is not None and secondary_high_time is not None:
        blocks_sec_high = count_30min_blocks(secondary_high_time, eval_time)
        secondary_high_desc = project_rail(secondary_high, blocks_sec_high, 'descending')
        
        dist_to_secondary_high_desc = overnight_low_spx - secondary_high_desc
        
        if dist_to_secondary_high_desc <= touch_threshold and dist_to_secondary_high_desc >= -touch_threshold:
            validation['high_secondary_validated'] = True
            validation['validation_notes'].append(f"✓ Secondary High² desc ({secondary_high_desc:.2f}) touched and held")
        elif dist_to_secondary_high_desc < -touch_threshold:
            validation['high_secondary_broken'] = True
            validation['validation_notes'].append(f"✗ Secondary High² desc ({secondary_high_desc:.2f}) was broken")
    
    # Determine active HIGH structure
    if secondary_high is not None:
        if validation['high_secondary_broken'] and not validation['high_primary_broken']:
            # Rule 3: Secondary broke, primary held - skip secondary
            validation['active_high_structure'] = 'primary'
            validation['high_structures_to_show'] = ['primary']
            validation['validation_notes'].append("→ Using PRIMARY High only (secondary was broken)")
        elif validation['high_secondary_validated']:
            # Secondary was tested and held
            validation['active_high_structure'] = 'secondary'
            validation['high_structures_to_show'] = ['secondary', 'primary']  # Show both but secondary is active
            validation['validation_notes'].append("→ SECONDARY High² is ACTIVE (touched and held)")
        elif validation['high_primary_validated']:
            # Primary was tested and held
            validation['active_high_structure'] = 'primary'
            validation['high_structures_to_show'] = ['primary', 'secondary']
            validation['validation_notes'].append("→ PRIMARY High is ACTIVE (touched and held)")
        else:
            # Neither tested - show both as candidates
            validation['active_high_structure'] = 'both'
            validation['high_structures_to_show'] = ['primary', 'secondary']
            validation['validation_notes'].append("→ Both High structures are candidates (neither tested overnight)")
    else:
        validation['active_high_structure'] = 'primary'
        validation['high_structures_to_show'] = ['primary']
    
    # ========== LOW STRUCTURE VALIDATION ==========
    # Check if overnight high touched/broke primary low ascending rail
    
    dist_to_primary_low_asc = primary_low_asc - overnight_high_spx
    
    if dist_to_primary_low_asc <= touch_threshold and dist_to_primary_low_asc >= -touch_threshold:
        validation['low_primary_validated'] = True
        validation['validation_notes'].append(f"✓ Primary Low asc ({primary_low_asc:.2f}) touched and held")
    elif dist_to_primary_low_asc < -touch_threshold:
        validation['low_primary_broken'] = True
        validation['validation_notes'].append(f"✗ Primary Low asc ({primary_low_asc:.2f}) was broken")
    
    # Secondary Low Ascending (if exists)
    if secondary_low is not None and secondary_low_time is not None:
        blocks_sec_low = count_30min_blocks(secondary_low_time, eval_time)
        secondary_low_asc = project_rail(secondary_low, blocks_sec_low, 'ascending')
        
        dist_to_secondary_low_asc = secondary_low_asc - overnight_high_spx
        
        if dist_to_secondary_low_asc <= touch_threshold and dist_to_secondary_low_asc >= -touch_threshold:
            validation['low_secondary_validated'] = True
            validation['validation_notes'].append(f"✓ Secondary Low² asc ({secondary_low_asc:.2f}) touched and held")
        elif dist_to_secondary_low_asc < -touch_threshold:
            validation['low_secondary_broken'] = True
            validation['validation_notes'].append(f"✗ Secondary Low² asc ({secondary_low_asc:.2f}) was broken")
    
    # Determine active LOW structure
    if secondary_low is not None:
        if validation['low_secondary_broken'] and not validation['low_primary_broken']:
            validation['active_low_structure'] = 'primary'
            validation['low_structures_to_show'] = ['primary']
            validation['validation_notes'].append("→ Using PRIMARY Low only (secondary was broken)")
        elif validation['low_secondary_validated']:
            validation['active_low_structure'] = 'secondary'
            validation['low_structures_to_show'] = ['secondary', 'primary']
            validation['validation_notes'].append("→ SECONDARY Low² is ACTIVE (touched and held)")
        elif validation['low_primary_validated']:
            validation['active_low_structure'] = 'primary'
            validation['low_structures_to_show'] = ['primary', 'secondary']
            validation['validation_notes'].append("→ PRIMARY Low is ACTIVE (touched and held)")
        else:
            validation['active_low_structure'] = 'both'
            validation['low_structures_to_show'] = ['primary', 'secondary']
            validation['validation_notes'].append("→ Both Low structures are candidates (neither tested overnight)")
    else:
        validation['active_low_structure'] = 'primary'
        validation['low_structures_to_show'] = ['primary']
    
    return validation

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

@st.cache_data(ttl=300)
def fetch_first_30min_bar(session_date: datetime) -> Optional[Dict]:
    try:
        spx = yf.Ticker("^GSPC")
        start_date = session_date.strftime('%Y-%m-%d')
        end_date = (session_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        df = spx.history(start=start_date, end=end_date, interval='30m')
        
        if df.empty:
            return None
        
        first_bar = df.iloc[0]
        bar_range = first_bar['High'] - first_bar['Low']
        bar_body = abs(first_bar['Close'] - first_bar['Open'])
        
        if bar_body > bar_range * 0.6:
            energy = 'strong'
        elif bar_body < bar_range * 0.3:
            energy = 'weak'
        else:
            energy = 'neutral'
        
        return {
            'open': first_bar['Open'],
            'high': first_bar['High'],
            'low': first_bar['Low'],
            'close': first_bar['Close'],
            'range': bar_range,
            'body': bar_body,
            'energy': energy
        }
    except:
        return None

# ============================================================================
# STRUCTURAL ENGINE
# ============================================================================

def build_cones_at_time(pivots: List[Pivot], eval_time: datetime) -> List[Cone]:
    cones = []
    for pivot in pivots:
        blocks = count_30min_blocks(pivot.time, eval_time)
        ascending_rail = project_rail(pivot.price, blocks, 'ascending')
        descending_rail = project_rail(pivot.price, blocks, 'descending')
        
        cones.append(Cone(
            name=pivot.name,
            pivot=pivot,
            ascending_rail=ascending_rail,
            descending_rail=descending_rail,
            width=ascending_rail - descending_rail,
            blocks_from_pivot=blocks
        ))
    return cones

def build_projection_table(pivots: List[Pivot], session_date: datetime) -> pd.DataFrame:
    data = []
    for t in TIME_BLOCKS:
        eval_time = CT_TZ.localize(datetime.combine(session_date, t))
        cones = build_cones_at_time(pivots, eval_time)
        
        row = {'Time': t.strftime('%H:%M')}
        for cone in cones:
            row[f'{cone.name} ▲'] = cone.ascending_rail
            row[f'{cone.name} ▼'] = cone.descending_rail
        data.append(row)
    
    return pd.DataFrame(data)

def find_nearest_rail(price: float, cones: List[Cone]) -> Tuple[Cone, str, float]:
    nearest_cone = None
    nearest_rail_type = None
    nearest_distance = float('inf')
    
    for cone in cones:
        dist_asc = abs(price - cone.ascending_rail)
        if dist_asc < nearest_distance:
            nearest_distance = dist_asc
            nearest_cone = cone
            nearest_rail_type = 'ascending'
        
        dist_desc = abs(price - cone.descending_rail)
        if dist_desc < nearest_distance:
            nearest_distance = dist_desc
            nearest_cone = cone
            nearest_rail_type = 'descending'
    
    return nearest_cone, nearest_rail_type, nearest_distance

def check_overnight_rail_touches(cones: List[Cone], es_data: Dict) -> List[str]:
    touched = []
    if not es_data or es_data.get('overnight_high_spx') is None:
        return touched
    
    for cone in cones:
        if abs(es_data['overnight_high_spx'] - cone.ascending_rail) <= RAIL_TOUCH_THRESHOLD:
            touched.append(f"{cone.name} ▲")
        if abs(es_data['overnight_low_spx'] - cone.descending_rail) <= RAIL_TOUCH_THRESHOLD:
            touched.append(f"{cone.name} ▼")
    
    return touched

def find_confluence_zones(cones: List[Cone], threshold: float = 5.0) -> Dict[str, List[Dict]]:
    """
    Find where multiple cone rails converge.
    Returns separate lists for CALLS zones (descending rails) and PUTS zones (ascending rails).
    """
    calls_zones = []  # Descending rail convergences (support levels)
    puts_zones = []   # Ascending rail convergences (resistance levels)
    
    # Separate ascending and descending rails
    ascending_rails = []  # For PUTS (resistance)
    descending_rails = [] # For CALLS (support)
    
    for cone in cones:
        ascending_rails.append({
            'price': cone.ascending_rail, 
            'name': f"{cone.name} ▲", 
            'cone': cone.name
        })
        descending_rails.append({
            'price': cone.descending_rail, 
            'name': f"{cone.name} ▼", 
            'cone': cone.name
        })
    
    # Find CALLS confluence (descending rails converging = strong support)
    for i, r1 in enumerate(descending_rails):
        for r2 in descending_rails[i+1:]:
            if abs(r1['price'] - r2['price']) <= threshold:
                avg_price = (r1['price'] + r2['price']) / 2
                # Check if this zone already exists
                existing = False
                for zone in calls_zones:
                    if abs(zone['price'] - avg_price) <= threshold:
                        if r1['name'] not in zone['rails']:
                            zone['rails'].append(r1['name'])
                        if r2['name'] not in zone['rails']:
                            zone['rails'].append(r2['name'])
                        zone['price'] = sum([descending_rails[j]['price'] for j in range(len(descending_rails)) 
                                            if descending_rails[j]['name'] in zone['rails']]) / len(zone['rails'])
                        existing = True
                        break
                if not existing:
                    calls_zones.append({
                        'price': avg_price,
                        'rails': [r1['name'], r2['name']],
                        'strength': 2
                    })
    
    # Find PUTS confluence (ascending rails converging = strong resistance)
    for i, r1 in enumerate(ascending_rails):
        for r2 in ascending_rails[i+1:]:
            if abs(r1['price'] - r2['price']) <= threshold:
                avg_price = (r1['price'] + r2['price']) / 2
                # Check if this zone already exists
                existing = False
                for zone in puts_zones:
                    if abs(zone['price'] - avg_price) <= threshold:
                        if r1['name'] not in zone['rails']:
                            zone['rails'].append(r1['name'])
                        if r2['name'] not in zone['rails']:
                            zone['rails'].append(r2['name'])
                        zone['price'] = sum([ascending_rails[j]['price'] for j in range(len(ascending_rails)) 
                                            if ascending_rails[j]['name'] in zone['rails']]) / len(zone['rails'])
                        existing = True
                        break
                if not existing:
                    puts_zones.append({
                        'price': avg_price,
                        'rails': [r1['name'], r2['name']],
                        'strength': 2
                    })
    
    # Update strength based on number of converging rails
    for zone in calls_zones:
        zone['strength'] = len(zone['rails'])
    for zone in puts_zones:
        zone['strength'] = len(zone['rails'])
    
    # Sort by price
    calls_zones.sort(key=lambda x: x['price'])
    puts_zones.sort(key=lambda x: x['price'], reverse=True)
    
    # Also add individual strong levels (all rails) for reference
    all_calls_levels = sorted(descending_rails, key=lambda x: x['price'])
    all_puts_levels = sorted(ascending_rails, key=lambda x: x['price'], reverse=True)
    
    return {
        'calls_confluence': calls_zones,
        'puts_confluence': puts_zones,
        'all_calls_levels': all_calls_levels,
        'all_puts_levels': all_puts_levels
    }

# ============================================================================
# TRADE SETUP GENERATOR - Creates complete trade plans from confluence zones
# ============================================================================

@dataclass
@dataclass
class TradeSetup:
    """Complete trade setup for a confluence zone."""
    direction: str  # CALLS or PUTS
    entry_price: float  # The confluence zone price
    confluence_rails: List[str]  # Which rails form this confluence
    confluence_strength: int  # Number of rails converging
    strike: int  # Recommended option strike
    strike_label: str  # e.g., "SPX 6810C"
    stop_loss: float  # Stop level in underlying
    target_50: float  # 50% target
    target_75: float  # 75% target  
    target_100: float  # 100% target (opposite side of cone)
    profit_50: float  # Expected $ profit at 50% (theoretical)
    profit_75: float  # Expected $ profit at 75% (theoretical)
    profit_100: float  # Expected $ profit at 100% (theoretical)
    profit_50_theta_adjusted: float  # Theta-adjusted profit at 50%
    risk_dollars: float  # Risk in dollars
    rr_ratio: float  # Risk/reward at 50% (theoretical)
    rr_ratio_theta_adjusted: float  # R:R accounting for theta
    cone_width: float  # Width of the trading range
    delta_estimate: float  # Estimated delta for this strike
    theta_period: str  # Time period for theta (morning, mid_day, etc.)
    distance: float = 0.0  # Distance from current price (set dynamically)

def generate_trade_setups(cones: List[Cone], current_price: float = None) -> Dict:
    """
    Generate complete trade setups for all confluence zones.
    
    This is the MAIN function that connects everything:
    - Finds confluence zones
    - Calculates exact entry, stop, targets
    - Recommends specific contract strike
    - Calculates expected profit/risk
    
    Returns dict with 'calls_setups' and 'puts_setups' lists.
    """
    
    confluence_data = find_confluence_zones(cones)
    calls_setups = []
    puts_setups = []
    
    # Get average cone width for target calculation
    avg_cone_width = sum(c.ascending_rail - c.descending_rail for c in cones) / len(cones) if cones else 30
    
    # =========================================================================
    # CALLS SETUPS - From descending rail confluences (support zones)
    # =========================================================================
    for zone in confluence_data.get('calls_confluence', []):
        entry_price = zone['price']
        rails = zone['rails']
        strength = zone.get('strength', len(rails))
        
        # Find the corresponding ascending rail for target (opposite side)
        # Use the average of ascending rails from the cones that form this confluence
        target_prices = []
        for cone in cones:
            for rail in rails:
                if cone.name in rail:
                    target_prices.append(cone.ascending_rail)
                    break
        
        if target_prices:
            target_100 = sum(target_prices) / len(target_prices)
        else:
            target_100 = entry_price + avg_cone_width
        
        cone_width = target_100 - entry_price
        
        # Skip if cone width is too small
        if cone_width < MIN_CONE_WIDTH:
            continue
        
        # Calculate targets
        target_50 = entry_price + (cone_width * 0.50)
        target_75 = entry_price + (cone_width * 0.75)
        stop_loss = entry_price - STOP_LOSS_PTS
        
        # Calculate strike (OTM CALLS = strike ABOVE entry price)
        strike = int(entry_price + STRIKE_OFFSET)
        strike = ((strike + 4) // 5) * 5  # Round UP to nearest 5
        strike_label = f"SPX {strike}C"
        
        # Get accurate delta estimate based on OTM distance
        otm_distance = strike - entry_price
        delta_estimate = get_delta_estimate(otm_distance)
        
        # Calculate profits using accurate delta
        move_50 = cone_width * 0.50
        move_75 = cone_width * 0.75
        move_100 = cone_width
        
        profit_50 = move_50 * delta_estimate * 100
        profit_75 = move_75 * delta_estimate * 100
        profit_100 = move_100 * delta_estimate * 100
        risk_dollars = STOP_LOSS_PTS * delta_estimate * 100
        
        # Apply theta adjustment for realistic profit expectation
        theta_mult, theta_period = get_theta_multiplier()
        profit_50_theta = profit_50 * theta_mult
        
        rr_ratio = profit_50 / risk_dollars if risk_dollars > 0 else 0
        rr_ratio_theta = profit_50_theta / risk_dollars if risk_dollars > 0 else 0
        
        setup = TradeSetup(
            direction='CALLS',
            entry_price=entry_price,
            confluence_rails=rails,
            confluence_strength=strength,
            strike=strike,
            strike_label=strike_label,
            stop_loss=stop_loss,
            target_50=target_50,
            target_75=target_75,
            target_100=target_100,
            profit_50=profit_50,
            profit_75=profit_75,
            profit_100=profit_100,
            profit_50_theta_adjusted=profit_50_theta,
            risk_dollars=risk_dollars,
            rr_ratio=rr_ratio,
            rr_ratio_theta_adjusted=rr_ratio_theta,
            cone_width=cone_width,
            delta_estimate=delta_estimate,
            theta_period=theta_period
        )
        calls_setups.append(setup)
    
    # =========================================================================
    # PUTS SETUPS - From ascending rail confluences (resistance zones)
    # =========================================================================
    for zone in confluence_data.get('puts_confluence', []):
        entry_price = zone['price']
        rails = zone['rails']
        strength = zone.get('strength', len(rails))
        
        # Find the corresponding descending rail for target (opposite side)
        target_prices = []
        for cone in cones:
            for rail in rails:
                if cone.name in rail:
                    target_prices.append(cone.descending_rail)
                    break
        
        if target_prices:
            target_100 = sum(target_prices) / len(target_prices)
        else:
            target_100 = entry_price - avg_cone_width
        
        cone_width = entry_price - target_100
        
        # Skip if cone width is too small
        if cone_width < MIN_CONE_WIDTH:
            continue
        
        # Calculate targets
        target_50 = entry_price - (cone_width * 0.50)
        target_75 = entry_price - (cone_width * 0.75)
        stop_loss = entry_price + STOP_LOSS_PTS
        
        # Calculate strike (OTM PUTS = strike BELOW entry price)
        strike = int(entry_price - STRIKE_OFFSET)
        strike = (strike // 5) * 5  # Round DOWN to nearest 5
        strike_label = f"SPX {strike}P"
        
        # Get accurate delta estimate based on OTM distance
        otm_distance = entry_price - strike
        delta_estimate = get_delta_estimate(otm_distance)
        
        # Calculate profits using accurate delta
        move_50 = cone_width * 0.50
        move_75 = cone_width * 0.75
        move_100 = cone_width
        
        profit_50 = move_50 * delta_estimate * 100
        profit_75 = move_75 * delta_estimate * 100
        profit_100 = move_100 * delta_estimate * 100
        risk_dollars = STOP_LOSS_PTS * delta_estimate * 100
        
        # Apply theta adjustment
        theta_mult, theta_period = get_theta_multiplier()
        profit_50_theta = profit_50 * theta_mult
        
        rr_ratio = profit_50 / risk_dollars if risk_dollars > 0 else 0
        rr_ratio_theta = profit_50_theta / risk_dollars if risk_dollars > 0 else 0
        
        setup = TradeSetup(
            direction='PUTS',
            entry_price=entry_price,
            confluence_rails=rails,
            confluence_strength=strength,
            strike=strike,
            strike_label=strike_label,
            stop_loss=stop_loss,
            target_50=target_50,
            target_75=target_75,
            target_100=target_100,
            profit_50=profit_50,
            profit_75=profit_75,
            profit_100=profit_100,
            profit_50_theta_adjusted=profit_50_theta,
            risk_dollars=risk_dollars,
            rr_ratio=rr_ratio,
            rr_ratio_theta_adjusted=rr_ratio_theta,
            cone_width=cone_width,
            delta_estimate=delta_estimate,
            theta_period=theta_period
        )
        puts_setups.append(setup)
    
    # Sort by R:R (theta-adjusted) - best first
    calls_setups.sort(key=lambda x: x.rr_ratio_theta_adjusted, reverse=True)
    puts_setups.sort(key=lambda x: x.rr_ratio_theta_adjusted, reverse=True)
    
    # Also include single-rail setups for reference (lower priority)
    # These are individual rails without confluence
    single_calls = []
    single_puts = []
    
    for level in confluence_data.get('all_calls_levels', []):
        # Check if this level is already in a confluence
        is_in_confluence = any(
            abs(level['price'] - setup.entry_price) < 5 
            for setup in calls_setups
        )
        if not is_in_confluence:
            single_calls.append({
                'price': level['price'],
                'rail': level['name'],
                'type': 'single'
            })
    
    for level in confluence_data.get('all_puts_levels', []):
        is_in_confluence = any(
            abs(level['price'] - setup.entry_price) < 5 
            for setup in puts_setups
        )
        if not is_in_confluence:
            single_puts.append({
                'price': level['price'],
                'rail': level['name'],
                'type': 'single'
            })
    
    return {
        'calls_setups': calls_setups,
        'puts_setups': puts_setups,
        'single_calls': single_calls,
        'single_puts': single_puts
    }

def render_trade_setup_card(setup: TradeSetup, current_price: float = None):
    """Render a complete trade setup card with GO/NO-GO decision."""
    
    # Determine colors and proximity
    if setup.direction == 'CALLS':
        color = "#22c55e"
        emoji = "🟢"
    else:
        color = "#ef4444"
        emoji = "🔴"
    
    # Calculate distance from current price if provided
    distance_text = ""
    at_entry = False
    if current_price:
        distance = abs(current_price - setup.entry_price)
        if distance <= AT_RAIL_THRESHOLD:
            distance_text = f"🎯 {distance:.1f} pts away - AT ENTRY"
            at_entry = True
        elif distance <= 15:
            distance_text = f"⏳ {distance:.1f} pts away - WATCH"
        else:
            distance_text = f"📍 {distance:.1f} pts away"
    
    # GO/NO-GO Decision based on calculable factors:
    # 1. R:R (theta-adjusted) must be >= 3:1
    # 2. Cone width must be >= 25 pts
    # 3. Must have confluence (2+ rails)
    # 4. Time must be before LAST_ENTRY_TIME
    
    ct_now = get_ct_now().time()
    time_ok = ct_now < LAST_ENTRY_TIME
    rr_ok = setup.rr_ratio_theta_adjusted >= MIN_RR_RATIO
    width_ok = setup.cone_width >= MIN_CONE_WIDTH
    confluence_ok = setup.confluence_strength >= 2
    
    if rr_ok and width_ok and confluence_ok and time_ok:
        decision = "✅ GO"
        decision_color = "#22c55e"
        decision_reason = f"R:R {setup.rr_ratio_theta_adjusted:.1f}:1 (θ-adj), {setup.confluence_strength} rails, Δ≈{setup.delta_estimate:.2f}"
    elif not time_ok:
        decision = "⛔ TOO LATE"
        decision_color = "#ef4444"
        decision_reason = f"After {LAST_ENTRY_TIME.strftime('%H:%M')} - theta decay too aggressive"
    elif not rr_ok:
        decision = "❌ NO-GO"
        decision_color = "#ef4444"
        decision_reason = f"R:R only {setup.rr_ratio_theta_adjusted:.1f}:1 after θ (need {MIN_RR_RATIO}:1)"
    elif not width_ok:
        decision = "❌ NO-GO"
        decision_color = "#ef4444"
        decision_reason = f"Cone only {setup.cone_width:.0f} pts (need {MIN_CONE_WIDTH})"
    else:
        decision = "⚠️ WEAK"
        decision_color = "#f59e0b"
        decision_reason = f"Single rail only - reduced probability"
    
    # Theta period warning
    theta_warning = ""
    if setup.theta_period == 'afternoon':
        theta_warning = "⚠️ Afternoon - profits reduced ~35% by theta"
    elif setup.theta_period == 'late':
        theta_warning = "🛑 Late session - avoid new entries"
    
    # Card header with strike and decision
    if setup.direction == 'CALLS':
        st.success(f"**{emoji} {setup.strike_label}** — {decision}")
    else:
        st.error(f"**{emoji} {setup.strike_label}** — {decision}")
    
    # Confluence info
    st.caption(f"Confluence: {' + '.join(setup.confluence_rails)}")
    
    # Decision reason
    if "GO" in decision:
        st.markdown(f"✅ {decision_reason}")
    elif "NO-GO" in decision or "LATE" in decision:
        st.markdown(f"❌ {decision_reason}")
    else:
        st.markdown(f"⚠️ {decision_reason}")
    
    # Theta warning if applicable
    if theta_warning:
        st.warning(theta_warning)
    
    # Distance from current price
    if distance_text:
        st.info(distance_text)
    
    # Entry and Stop
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Entry", f"{setup.entry_price:.2f}")
    with col2:
        st.metric("Stop", f"{setup.stop_loss:.2f}")
    
    # Targets and Profits - show both theoretical and theta-adjusted
    st.markdown("**Exit Strategy:**")
    theta_mult = THETA_MULTIPLIER.get(setup.theta_period, 1.0)
    target_data = {
        "Exit": ["60% @ 50%", "20% @ 75%", "20% @ 100%"],
        "Level": [f"{setup.target_50:.2f}", f"{setup.target_75:.2f}", f"{setup.target_100:.2f}"],
        "Profit (θ-adj)": [f"+${setup.profit_50_theta_adjusted:.0f}", f"+${setup.profit_75 * theta_mult:.0f}", f"+${setup.profit_100 * theta_mult:.0f}"]
    }
    st.dataframe(target_data, use_container_width=True, hide_index=True)
    
    # Stats - show delta and theta-adjusted R:R
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.metric("Width", f"{setup.cone_width:.0f} pts")
    with col_b:
        st.metric("Delta", f"{setup.delta_estimate:.2f}")
    with col_c:
        st.metric("R:R (θ-adj)", f"{setup.rr_ratio_theta_adjusted:.1f}:1")
    with col_d:
        st.metric("Risk", f"${setup.risk_dollars:.0f}")
    
    st.markdown("---")


def render_institutional_trade_card(setup: TradeSetup, current_price: float):
    """Render a professional institutional-style trade card."""
    
    # Calculate distance
    distance = abs(current_price - setup.entry_price)
    
    # Determine status
    if distance <= AT_RAIL_THRESHOLD:
        status = "ACTIVE"
        status_class = "badge-go"
    elif distance <= 15:
        status = "WATCH"
        status_class = "badge-wait"
    else:
        status = "STANDBY"
        status_class = "badge-nogo"
    
    # Direction styling
    direction_class = "badge-calls" if setup.direction == "CALLS" else "badge-puts"
    
    # GO/NO-GO
    ct_now = get_ct_now().time()
    time_ok = ct_now < LAST_ENTRY_TIME
    rr_ok = setup.rr_ratio_theta_adjusted >= MIN_RR_RATIO
    width_ok = setup.cone_width >= MIN_CONE_WIDTH
    confluence_ok = setup.confluence_strength >= 2
    
    if rr_ok and width_ok and confluence_ok and time_ok:
        decision = "GO"
        decision_class = "badge-go"
    else:
        decision = "NO-GO"
        decision_class = "badge-nogo"
    
    # Theta multiplier for display
    theta_mult = THETA_MULTIPLIER.get(setup.theta_period, 1.0)
    
    st.markdown(f"""
    <div class="trade-panel">
        <div class="trade-panel-header">
            <div style="display: flex; align-items: center; gap: 1rem;">
                <span class="trade-panel-badge {direction_class}">{setup.direction}</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; color: var(--accent-gold); font-weight: 600;">{setup.strike_label}</span>
            </div>
            <div style="display: flex; gap: 0.5rem;">
                <span class="trade-panel-badge {status_class}">{status}</span>
                <span class="trade-panel-badge {decision_class}">{decision}</span>
            </div>
        </div>
        <div class="trade-panel-body">
            <div class="entry-row">
                <div class="entry-item">
                    <div class="entry-label">Entry</div>
                    <div class="entry-value gold">{setup.entry_price:,.2f}</div>
                </div>
                <div class="entry-item">
                    <div class="entry-label">Stop Loss</div>
                    <div class="entry-value red">{setup.stop_loss:,.2f}</div>
                </div>
                <div class="entry-item">
                    <div class="entry-label">Target 50%</div>
                    <div class="entry-value green">{setup.target_50:,.2f}</div>
                </div>
                <div class="entry-item">
                    <div class="entry-label">Target 100%</div>
                    <div class="entry-value green">{setup.target_100:,.2f}</div>
                </div>
            </div>
            <div class="entry-row">
                <div class="entry-item">
                    <div class="entry-label">Distance</div>
                    <div class="entry-value">{distance:.1f} pts</div>
                </div>
                <div class="entry-item">
                    <div class="entry-label">Confluence</div>
                    <div class="entry-value">{setup.confluence_strength} Rails</div>
                </div>
                <div class="entry-item">
                    <div class="entry-label">R:R (θ-adj)</div>
                    <div class="entry-value">{setup.rr_ratio_theta_adjusted:.1f}:1</div>
                </div>
                <div class="entry-item">
                    <div class="entry-label">Delta</div>
                    <div class="entry-value">{setup.delta_estimate:.2f}</div>
                </div>
            </div>
            <div class="entry-row" style="border-bottom: none;">
                <div class="entry-item">
                    <div class="entry-label">Profit @ 50%</div>
                    <div class="entry-value green">+${setup.profit_50_theta_adjusted:,.0f}</div>
                </div>
                <div class="entry-item">
                    <div class="entry-label">Profit @ 75%</div>
                    <div class="entry-value green">+${setup.profit_75 * theta_mult:,.0f}</div>
                </div>
                <div class="entry-item">
                    <div class="entry-label">Profit @ 100%</div>
                    <div class="entry-value green">+${setup.profit_100 * theta_mult:,.0f}</div>
                </div>
                <div class="entry-item">
                    <div class="entry-label">Risk</div>
                    <div class="entry-value red">-${setup.risk_dollars:,.0f}</div>
                </div>
            </div>
            <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border-color); font-size: 0.75rem; color: var(--text-muted);">
                <strong>Sources:</strong> {' + '.join(setup.confluence_rails)}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================================
# CONTRACT EXPECTATION ENGINE
# ============================================================================

def calculate_contract_expectation(
    direction: str,
    entry_rail: float,
    opposite_rail: float,
    cone_name: str,
    rail_type: str
) -> ContractExpectation:
    
    cone_height = abs(opposite_rail - entry_rail)
    
    if direction == 'CALLS':
        target_50 = entry_rail + (cone_height * 0.50)
        target_75 = entry_rail + (cone_height * 0.75)
        target_100 = opposite_rail
        stop = entry_rail - 2
    else:
        target_50 = entry_rail - (cone_height * 0.50)
        target_75 = entry_rail - (cone_height * 0.75)
        target_100 = opposite_rail
        stop = entry_rail + 2
    
    move_50 = abs(target_50 - entry_rail)
    move_100 = abs(target_100 - entry_rail)
    
    contract_move_50 = move_50 * CONTRACT_FACTOR
    contract_move_75 = abs(target_75 - entry_rail) * CONTRACT_FACTOR
    contract_move_100 = move_100 * CONTRACT_FACTOR
    
    profit_50 = contract_move_50 * 100
    profit_75 = contract_move_75 * 100
    profit_100 = contract_move_100 * 100
    
    risk = 2 * CONTRACT_FACTOR * 100
    rr_50 = profit_50 / risk if risk > 0 else 0
    
    return ContractExpectation(
        direction=direction,
        entry_price=entry_rail,
        entry_rail=f"{cone_name} {'▼' if rail_type == 'descending' else '▲'}",
        target_50_underlying=target_50,
        target_75_underlying=target_75,
        target_100_underlying=target_100,
        stop_underlying=stop,
        expected_underlying_move_50=move_50,
        expected_underlying_move_100=move_100,
        contract_profit_50=profit_50,
        contract_profit_75=profit_75,
        contract_profit_100=profit_100,
        risk_reward_50=rr_50
    )

# ============================================================================
# REGIME & SCORING
# ============================================================================

def analyze_regime(cones, es_data, prior_session, first_bar, current_price) -> RegimeAnalysis:
    """Analyze market regime - only factors that matter for trading."""
    nearest_cone, _, _ = find_nearest_rail(current_price, cones)
    
    overnight_range = es_data.get('overnight_range', 0) if es_data else 0
    overnight_range_pct = overnight_range / nearest_cone.width if nearest_cone.width > 0 else 0
    overnight_touched = check_overnight_rail_touches(cones, es_data)
    
    position, _ = get_position_in_cone(current_price, nearest_cone.ascending_rail, nearest_cone.descending_rail)
    
    return RegimeAnalysis(
        overnight_range=overnight_range,
        overnight_range_pct=overnight_range_pct,
        overnight_touched_rails=overnight_touched,
        opening_position=position,
        es_spx_offset=es_data.get('offset', 0) if es_data else 0
    )

def calculate_confluence_score(nearest_distance, regime, cones, current_price, is_10am, 
                                nearest_rail_type=None, overnight_validation=None) -> dict:
    """
    Calculate a principled confluence score based on structural edge factors.
    
    The score represents EDGE QUALITY, not probability. Higher score = more factors align.
    
    SCORING PHILOSOPHY:
    - Base: Start at 50 (neutral - no edge either way)
    - Each factor adds or subtracts based on its importance
    - Maximum theoretical score: 100
    - Minimum practical score: ~20 (many negatives)
    - Trade threshold: 65+ for full size, 50-65 reduced, <50 no trade
    
    FACTOR WEIGHTS (based on structural trading principles):
    1. CONFLUENCE (35 pts max) - Multiple rails agreeing is the core edge
    2. STRUCTURE VALIDATION (20 pts max) - Overnight behavior confirms/denies
    3. DISTANCE TO RAIL (15 pts max) - Tighter entry = better R:R
    4. TIME WINDOW (10 pts max) - Decision windows matter
    5. REGIME QUALITY (10 pts max) - Market conditions
    6. SECONDARY PIVOT ALIGNMENT (10 pts max) - Extra confirmation
    
    Returns dict with score and breakdown for transparency.
    """
    breakdown = {}
    score = 50  # Neutral starting point
    
    # =========================================================================
    # 1. CONFLUENCE - The Core Edge (up to +35 or -10)
    # Multiple rails pointing to same level = structural agreement
    # =========================================================================
    zones_data = find_confluence_zones(cones)
    calls_zones = zones_data.get('calls_confluence', [])
    puts_zones = zones_data.get('puts_confluence', [])
    
    # Check if current price is near a confluence zone
    best_confluence = None
    best_confluence_distance = float('inf')
    
    # For CALLS, check descending rail confluences
    if nearest_rail_type == 'descending':
        for zone in calls_zones:
            dist = abs(current_price - zone['price'])
            if dist < best_confluence_distance:
                best_confluence_distance = dist
                best_confluence = zone
    # For PUTS, check ascending rail confluences
    elif nearest_rail_type == 'ascending':
        for zone in puts_zones:
            dist = abs(current_price - zone['price'])
            if dist < best_confluence_distance:
                best_confluence_distance = dist
                best_confluence = zone
    
    if best_confluence and best_confluence_distance <= 10:
        num_rails = best_confluence.get('strength', len(best_confluence.get('rails', [])))
        if num_rails >= 4:
            confluence_pts = 35  # Exceptional - 4+ rails converge
            breakdown['confluence'] = f"+{confluence_pts} (4+ rails converge!)"
        elif num_rails == 3:
            confluence_pts = 28  # Excellent - 3 rails converge
            breakdown['confluence'] = f"+{confluence_pts} (3 rails converge)"
        elif num_rails == 2:
            confluence_pts = 20  # Good - 2 rails converge
            breakdown['confluence'] = f"+{confluence_pts} (2 rails converge)"
        else:
            confluence_pts = 10
            breakdown['confluence'] = f"+{confluence_pts} (weak confluence)"
        score += confluence_pts
    elif nearest_distance <= 5:
        # At a single rail but no confluence
        confluence_pts = 5
        score += confluence_pts
        breakdown['confluence'] = f"+{confluence_pts} (single rail, no confluence)"
    else:
        confluence_pts = -10
        score += confluence_pts
        breakdown['confluence'] = f"{confluence_pts} (no confluence nearby)"
    
    # =========================================================================
    # 2. STRUCTURE VALIDATION - Overnight Behavior (up to +20 or -15)
    # Did ES respect or violate the structure overnight?
    # =========================================================================
    if overnight_validation:
        validated_rails = overnight_validation.get('validated', [])
        broken_rails = overnight_validation.get('broken', [])
        
        # Check if the rail we're trading was validated
        rail_validated = False
        rail_broken = False
        
        for v in validated_rails:
            if nearest_rail_type == 'descending' and '▼' in v:
                rail_validated = True
            elif nearest_rail_type == 'ascending' and '▲' in v:
                rail_validated = True
        
        for b in broken_rails:
            if nearest_rail_type == 'descending' and '▼' in b:
                rail_broken = True
            elif nearest_rail_type == 'ascending' and '▲' in b:
                rail_broken = True
        
        if rail_validated and not rail_broken:
            validation_pts = 20
            breakdown['validation'] = f"+{validation_pts} (rail validated overnight)"
        elif rail_broken:
            validation_pts = -15
            breakdown['validation'] = f"{validation_pts} (rail BROKEN overnight!)"
        elif len(validated_rails) > 0:
            validation_pts = 10
            breakdown['validation'] = f"+{validation_pts} (other rails validated)"
        else:
            validation_pts = 0
            breakdown['validation'] = f"+{validation_pts} (no overnight validation)"
        
        score += validation_pts
    else:
        breakdown['validation'] = "+0 (no overnight data)"
    
    # =========================================================================
    # 3. DISTANCE TO RAIL (up to +15 or -5)
    # Tighter entry = better risk/reward
    # =========================================================================
    if nearest_distance <= 2:
        distance_pts = 15
        breakdown['distance'] = f"+{distance_pts} (excellent entry <2 pts)"
    elif nearest_distance <= 5:
        distance_pts = 12
        breakdown['distance'] = f"+{distance_pts} (good entry <5 pts)"
    elif nearest_distance <= 10:
        distance_pts = 8
        breakdown['distance'] = f"+{distance_pts} (acceptable <10 pts)"
    elif nearest_distance <= 15:
        distance_pts = 3
        breakdown['distance'] = f"+{distance_pts} (wide entry <15 pts)"
    else:
        distance_pts = -5
        breakdown['distance'] = f"{distance_pts} (too far from rail)"
    score += distance_pts
    
    # =========================================================================
    # 4. TIME WINDOW (up to +10)
    # Decision windows provide cleaner entries
    # =========================================================================
    ct_now = get_ct_now()
    ct_time = ct_now.time()
    
    # Check if within 30 mins of key decision times
    is_830_window = time(8, 15) <= ct_time <= time(9, 0)
    is_1000_window = time(9, 45) <= ct_time <= time(10, 15)
    
    if is_1000_window:
        time_pts = 10
        breakdown['time'] = f"+{time_pts} (10:00 AM decision window)"
    elif is_830_window:
        time_pts = 8
        breakdown['time'] = f"+{time_pts} (8:30 AM open window)"
    elif time(10, 15) < ct_time < time(14, 0):
        time_pts = 3
        breakdown['time'] = f"+{time_pts} (mid-day)"
    else:
        time_pts = 0
        breakdown['time'] = f"+{time_pts} (outside optimal windows)"
    score += time_pts
    
    # =========================================================================
    # 5. OVERNIGHT BEHAVIOR (simple: tight = good, wide = neutral)
    # Only matters if extreme - minor variations don't predict outcome
    # =========================================================================
    if regime.overnight_range_pct < 0.25:
        regime_pts = 5
        breakdown['overnight'] = f"+{regime_pts} (tight overnight - structure respected)"
    elif regime.overnight_range_pct > 0.60:
        regime_pts = -5
        breakdown['overnight'] = f"{regime_pts} (wide overnight - volatile)"
    else:
        regime_pts = 0
        breakdown['overnight'] = f"+{regime_pts} (normal overnight range)"
    score += regime_pts
    
    # =========================================================================
    # 6. SECONDARY PIVOT ALIGNMENT (up to +10)
    # If secondary pivots also project to this level = extra confluence
    # =========================================================================
    secondary_alignment = False
    for cone in cones:
        if 'High²' in cone.name or 'Low²' in cone.name:
            if nearest_rail_type == 'descending':
                if abs(cone.descending_rail - current_price) <= CONFLUENCE_THRESHOLD:
                    secondary_alignment = True
            elif nearest_rail_type == 'ascending':
                if abs(cone.ascending_rail - current_price) <= CONFLUENCE_THRESHOLD:
                    secondary_alignment = True
    
    if secondary_alignment:
        secondary_pts = 10
        breakdown['secondary'] = f"+{secondary_pts} (secondary pivot confirms)"
    else:
        secondary_pts = 0
        breakdown['secondary'] = f"+{secondary_pts} (no secondary confirmation)"
    score += secondary_pts
    
    # =========================================================================
    # FINAL SCORE
    # =========================================================================
    final_score = max(0, min(100, score))
    
    return {
        'score': final_score,
        'breakdown': breakdown,
        'recommendation': get_score_recommendation(final_score)
    }

def get_score_recommendation(score: int) -> str:
    """Convert score to actionable recommendation."""
    if score >= 80:
        return "STRONG SETUP - Full position, high confidence"
    elif score >= 70:
        return "GOOD SETUP - Full position"
    elif score >= 60:
        return "ACCEPTABLE - Reduced position"
    elif score >= 50:
        return "MARGINAL - Small position or wait"
    else:
        return "NO TRADE - Insufficient edge"

def generate_action_card(cones, regime, current_price, is_10am, overnight_validation=None) -> ActionCard:
    """
    Generate trading action based on David's structural methodology:
    
    RULES:
    1. Descending rails = BUY points (CALLS) - price finds support
    2. Ascending rails = SELL points (PUTS) - price finds resistance
    3. EXCEPTION: If price is FAR BELOW all descending rails → could be PUTS (breakdown)
    4. EXCEPTION: If price is FAR ABOVE all ascending rails → could be CALLS (breakout)
    5. Contract 15-20 pts OTM moves ~0.33x the underlying move
    """
    warnings = []
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    
    # Get the new structured confluence score
    score_result = calculate_confluence_score(
        nearest_distance, regime, cones, current_price, is_10am,
        nearest_rail_type=nearest_rail_type, 
        overnight_validation=overnight_validation
    )
    confluence_score = score_result['score']
    score_breakdown = score_result['breakdown']
    score_recommendation = score_result['recommendation']
    
    # ==========================================================================
    # DETERMINE DIRECTION based on David's rules
    # ==========================================================================
    
    # Get ALL rail levels to check for extreme positions
    all_descending = sorted([c.descending_rail for c in cones])
    all_ascending = sorted([c.ascending_rail for c in cones], reverse=True)
    
    lowest_descending = min(all_descending) if all_descending else current_price
    highest_ascending = max(all_ascending) if all_ascending else current_price
    
    # Check for extreme positions (FAR outside all rails)
    far_below_support = current_price < lowest_descending - 15  # More than 15 pts below ALL support
    far_above_resistance = current_price > highest_ascending + 15  # More than 15 pts above ALL resistance
    
    # Cone width for position calculation
    cone_width = nearest_cone.ascending_rail - nearest_cone.descending_rail
    
    # Distance thresholds
    at_rail_threshold = 10  # Within 10 pts = "at the rail"
    
    # Determine position and direction
    if far_below_support:
        # Price broke down below all support - could be PUTS (continuation) or wait
        position = 'breakdown'
        direction = 'PUTS'
        entry_level = current_price
        target_100 = lowest_descending - cone_width  # Project further down
        warnings.append("⚠️ Price below ALL support - breakdown mode")
    elif far_above_resistance:
        # Price broke above all resistance - could be CALLS (continuation) or wait
        position = 'breakout'
        direction = 'CALLS'
        entry_level = current_price
        target_100 = highest_ascending + cone_width  # Project further up
        warnings.append("⚠️ Price above ALL resistance - breakout mode")
    elif nearest_rail_type == 'descending' and nearest_distance <= at_rail_threshold:
        # At a descending rail = support = BUY CALLS
        position = 'at_support'
        direction = 'CALLS'
        entry_level = nearest_cone.descending_rail
        target_100 = nearest_cone.ascending_rail
    elif nearest_rail_type == 'ascending' and nearest_distance <= at_rail_threshold:
        # At an ascending rail = resistance = BUY PUTS
        position = 'at_resistance'
        direction = 'PUTS'
        entry_level = nearest_cone.ascending_rail
        target_100 = nearest_cone.descending_rail
    else:
        # In the middle - determine which rail to target
        dist_to_desc = abs(current_price - nearest_cone.descending_rail)
        dist_to_asc = abs(current_price - nearest_cone.ascending_rail)
        
        if dist_to_desc < dist_to_asc:
            # Closer to support - wait for it or anticipate CALLS
            position = 'approaching_support'
            direction = 'WAIT'
            entry_level = nearest_cone.descending_rail
            target_100 = nearest_cone.ascending_rail
            warnings.append(f"Wait for support at {nearest_cone.descending_rail:.2f} for CALLS")
        else:
            # Closer to resistance - wait for it or anticipate PUTS  
            position = 'approaching_resistance'
            direction = 'WAIT'
            entry_level = nearest_cone.ascending_rail
            target_100 = nearest_cone.descending_rail
            warnings.append(f"Wait for resistance at {nearest_cone.ascending_rail:.2f} for PUTS")
    
    # ==========================================================================
    # CALCULATE CONTRACT EXPECTATION (Always calculate, even for WAIT)
    # ==========================================================================
    
    cone_height = abs(target_100 - entry_level)
    
    if direction == 'CALLS' or (direction == 'WAIT' and position == 'approaching_support'):
        calc_direction = 'CALLS'
        target_50 = entry_level + (cone_height * 0.50)
        target_75 = entry_level + (cone_height * 0.75)
        stop_level = entry_level - 3  # 3 pt stop
        
        # OTM CALLS = strike ABOVE entry (15-20 pts OTM for ~0.33 delta)
        recommended_strike = int(entry_level + 17.5)
        recommended_strike = ((recommended_strike + 4) // 5) * 5  # Round UP to nearest 5
    else:
        calc_direction = 'PUTS'
        target_50 = entry_level - (cone_height * 0.50)
        target_75 = entry_level - (cone_height * 0.75)
        stop_level = entry_level + 3  # 3 pt stop
        
        # OTM PUTS = strike BELOW entry (15-20 pts OTM for ~0.33 delta)
        recommended_strike = int(entry_level - 17.5)
        recommended_strike = (recommended_strike // 5) * 5  # Round DOWN to nearest 5
    
    # Calculate expected contract moves
    move_50 = cone_height * 0.50
    move_75 = cone_height * 0.75
    move_100 = cone_height
    
    contract_move_50 = move_50 * CONTRACT_FACTOR
    contract_move_75 = move_75 * CONTRACT_FACTOR
    contract_move_100 = move_100 * CONTRACT_FACTOR
    
    # Dollar values (assuming $100 per point for SPX options)
    profit_50 = contract_move_50 * 100
    profit_75 = contract_move_75 * 100
    profit_100 = contract_move_100 * 100
    
    # Risk calculation (3 pt stop × 0.33 factor × $100)
    risk_dollars = 3 * CONTRACT_FACTOR * 100  # ~$99 risk
    rr_50 = profit_50 / risk_dollars if risk_dollars > 0 else 0
    
    contract_exp = ContractExpectation(
        direction=calc_direction,
        entry_price=entry_level,
        entry_rail=f"{nearest_cone.name} {'▼' if nearest_rail_type == 'descending' else '▲'}",
        target_50_underlying=target_50,
        target_75_underlying=target_75,
        target_100_underlying=target_100,
        stop_underlying=stop_level,
        expected_underlying_move_50=move_50,
        expected_underlying_move_100=move_100,
        contract_profit_50=profit_50,
        contract_profit_75=profit_75,
        contract_profit_100=profit_100,
        risk_reward_50=rr_50
    )
    
    # Store strike recommendation in warnings for display
    if direction in ['CALLS', 'PUTS']:
        warnings.insert(0, f"📋 Recommended: {calc_direction} @ {recommended_strike} strike")
        warnings.insert(1, f"💰 Expected move: ${contract_move_50:.0f}-${contract_move_100:.0f} per contract")
    
    # ==========================================================================
    # POSITION SIZING based on confluence score
    # ==========================================================================
    
    if direction == 'WAIT':
        color = 'yellow'
        position_size = 'WAIT'
    elif confluence_score >= 70:
        color, position_size = 'green', 'FULL'
    elif confluence_score >= 60:
        color, position_size = 'yellow', 'FULL'
    elif confluence_score >= 50:
        color, position_size = 'yellow', 'REDUCED'
    else:
        color, position_size = 'red', 'SKIP'
        warnings.append("Low confluence - consider skipping")
    
    # ==========================================================================
    # STRUCTURE VALIDATION NOTES
    # ==========================================================================
    
    if overnight_validation:
        validated = overnight_validation.get('validated', [])
        broken = overnight_validation.get('broken', [])
        
        if broken:
            for b in broken:
                if (direction == 'CALLS' and '▼' in b) or (direction == 'PUTS' and '▲' in b):
                    warnings.insert(0, f"⛔ WARNING: {b} was BROKEN overnight")
                    color = 'red'
                    position_size = 'SKIP'
        
        if validated:
            for v in validated:
                if (direction == 'CALLS' and '▼' in v) or (direction == 'PUTS' and '▲' in v):
                    warnings.insert(0, f"✅ {v} VALIDATED overnight")
    
    # Add score info
    warnings.append(f"Score: {confluence_score} - {score_recommendation}")
    
    return ActionCard(
        direction=direction, 
        active_cone=nearest_cone.name, 
        active_rail=nearest_rail_type,
        entry_level=entry_level, 
        target_50=target_50, 
        target_75=target_75, 
        target_100=target_100,
        stop_level=stop_level, 
        contract_expectation=contract_exp, 
        position_size=position_size,
        confluence_score=confluence_score, 
        warnings=warnings, 
        color=color
    )

# ============================================================================
# PREMIUM UI
# ============================================================================

def inject_premium_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    :root {
        --bg-primary: #f8fafc;
        --bg-secondary: #f1f5f9;
        --bg-tertiary: #e2e8f0;
        --bg-card: #ffffff;
        --text-primary: #0f172a;
        --text-secondary: #475569;
        --text-muted: #64748b;
        --accent-gold: #d97706;
        --accent-green: #059669;
        --accent-red: #dc2626;
        --accent-blue: #2563eb;
        --border-color: #cbd5e1;
    }
    
    .stApp {
        background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
    }
    
    /* Override Streamlit defaults for light theme */
    .stApp > header { background: transparent; }
    .stMarkdown, .stText, p, span, label { color: var(--text-primary) !important; }
    h1, h2, h3, h4, h5, h6 { color: var(--text-primary) !important; }
    .stMetric label { color: var(--text-secondary) !important; }
    .stMetric [data-testid="stMetricValue"] { color: var(--text-primary) !important; font-family: 'JetBrains Mono', monospace !important; }
    
    /* INSTITUTIONAL HEADER - dark header on light background */
    .terminal-header {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border: 1px solid #475569;
        border-radius: 8px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .terminal-logo {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .terminal-logo-icon {
        width: 48px;
        height: 48px;
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        font-weight: 800;
        color: #1e293b;
    }
    .terminal-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: #f8fafc;
        letter-spacing: -0.02em;
        font-family: 'Inter', sans-serif;
    }
    .terminal-subtitle {
        font-size: 0.8rem;
        color: #fbbf24;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        font-weight: 500;
    }
    .terminal-status {
        display: flex;
        gap: 2rem;
        align-items: center;
    }
    .status-item {
        text-align: right;
    }
    .status-label {
        font-size: 0.65rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    .status-value {
        font-size: 1.1rem;
        font-weight: 600;
        color: #f8fafc;
        font-family: 'JetBrains Mono', monospace;
    }
    .status-live {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
    }
    .live-dot {
        width: 8px;
        height: 8px;
        background: #10b981;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    /* DATA GRID */
    .data-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    /* METRIC CARDS */
    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 1.25rem;
        transition: all 0.2s ease;
    }
    .metric-card:hover {
        border-color: var(--accent-gold);
        box-shadow: 0 0 20px rgba(245, 158, 11, 0.1);
    }
    .metric-label {
        font-size: 0.7rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        color: var(--text-primary);
    }
    .metric-value.positive { color: var(--accent-green); }
    .metric-value.negative { color: var(--accent-red); }
    .metric-value.gold { color: var(--accent-gold); }
    .metric-delta {
        font-size: 0.8rem;
        color: var(--text-secondary);
        margin-top: 0.25rem;
    }
    
    /* TRADE PANEL */
    .trade-panel {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 1rem;
    }
    .trade-panel-header {
        background: linear-gradient(90deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
        padding: 1rem 1.25rem;
        border-bottom: 1px solid var(--border-color);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .trade-panel-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: var(--text-primary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .trade-panel-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-calls {
        background: rgba(16, 185, 129, 0.2);
        color: var(--accent-green);
        border: 1px solid var(--accent-green);
    }
    .badge-puts {
        background: rgba(239, 68, 68, 0.2);
        color: var(--accent-red);
        border: 1px solid var(--accent-red);
    }
    .badge-go {
        background: rgba(16, 185, 129, 0.2);
        color: var(--accent-green);
        border: 1px solid var(--accent-green);
    }
    .badge-nogo {
        background: rgba(239, 68, 68, 0.2);
        color: var(--accent-red);
        border: 1px solid var(--accent-red);
    }
    .badge-wait {
        background: rgba(245, 158, 11, 0.2);
        color: var(--accent-gold);
        border: 1px solid var(--accent-gold);
    }
    .trade-panel-body {
        padding: 1.25rem;
    }
    
    /* ENTRY ROW */
    .entry-row {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr 1fr;
        gap: 1rem;
        padding: 1rem 0;
        border-bottom: 1px solid var(--border-color);
    }
    .entry-row:last-child { border-bottom: none; }
    .entry-item {
        text-align: center;
    }
    .entry-label {
        font-size: 0.65rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.25rem;
    }
    .entry-value {
        font-size: 1.1rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
        color: var(--text-primary);
    }
    .entry-value.green { color: var(--accent-green); }
    .entry-value.red { color: var(--accent-red); }
    .entry-value.gold { color: var(--accent-gold); }
    
    /* CONTRACT DISPLAY */
    .contract-display {
        background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
        border: 2px solid var(--accent-gold);
        border-radius: 8px;
        padding: 1.5rem;
        text-align: center;
        margin: 1rem 0;
    }
    .contract-strike {
        font-size: 2rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        color: var(--accent-gold);
        letter-spacing: -0.02em;
    }
    .contract-type {
        font-size: 0.8rem;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 0.25rem;
    }
    
    /* TABLE STYLES */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
    }
    .data-table th {
        background: var(--bg-tertiary);
        color: var(--text-muted);
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 0.75rem 1rem;
        text-align: left;
        border-bottom: 1px solid var(--border-color);
    }
    .data-table td {
        padding: 0.75rem 1rem;
        border-bottom: 1px solid var(--border-color);
        color: var(--text-primary);
    }
    .data-table tr:hover { background: rgba(255,255,255,0.02); }
    
    /* SECTION HEADERS */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--border-color);
    }
    .section-icon {
        width: 32px;
        height: 32px;
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
    }
    .section-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* QUICK STATS BAR */
    .stats-bar {
        display: flex;
        gap: 2rem;
        padding: 1rem 1.5rem;
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }
    .stat-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .stat-indicator {
        width: 10px;
        height: 10px;
        border-radius: 2px;
    }
    .stat-indicator.green { background: var(--accent-green); }
    .stat-indicator.red { background: var(--accent-red); }
    .stat-indicator.gold { background: var(--accent-gold); }
    .stat-text {
        font-size: 0.8rem;
        color: var(--text-secondary);
    }
    .stat-text strong {
        color: var(--text-primary);
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* DISTANCE INDICATOR */
    .distance-bar {
        height: 4px;
        background: var(--bg-tertiary);
        border-radius: 2px;
        overflow: hidden;
        margin-top: 0.5rem;
    }
    .distance-fill {
        height: 100%;
        border-radius: 2px;
        transition: width 0.3s ease;
    }
    .distance-fill.close { background: var(--accent-green); }
    .distance-fill.medium { background: var(--accent-gold); }
    .distance-fill.far { background: var(--accent-red); }
    
    /* Hide Streamlit elements */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    
    /* Override Streamlit dataframe */
    .stDataFrame { background: var(--bg-card) !important; border-radius: 8px !important; }
    
    /* SIDEBAR STYLING - Dark sidebar with light text */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
    }
    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] .stMarkdown h4,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stCaption,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] div {
        color: #f8fafc !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stNumberInput label,
    section[data-testid="stSidebar"] .stTextInput label,
    section[data-testid="stSidebar"] .stDateInput label,
    section[data-testid="stSidebar"] .stCheckbox label {
        color: #cbd5e1 !important;
    }
    /* Input fields - dark text on light background */
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] .stTextInput input,
    section[data-testid="stSidebar"] .stNumberInput input {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #475569 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox > div > div {
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] {
        background-color: #ffffff !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="select"] * {
        color: #0f172a !important;
    }
    /* Expander styling in sidebar */
    section[data-testid="stSidebar"] .streamlit-expanderHeader {
        color: #f8fafc !important;
    }
    section[data-testid="stSidebar"] .streamlit-expanderContent {
        color: #e2e8f0 !important;
    }
    /* Metric values in sidebar */
    section[data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #f8fafc !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMetricDelta"] {
        color: #10b981 !important;
    }
    
    /* MAIN AREA - ensure text is visible */
    .main .block-container {
        color: var(--text-primary);
    }
    .stExpander {
        border-color: var(--border-color) !important;
    }
    .streamlit-expanderHeader {
        color: var(--text-primary) !important;
    }
    
    </style>
    """, unsafe_allow_html=True)

def render_header():
    st.markdown("""
    <div class="prophet-header">
        <h1 class="prophet-title">SPX PROPHET</h1>
        <p class="prophet-tagline">WHERE STRUCTURE BECOMES FORESIGHT</p>
    </div>
    """, unsafe_allow_html=True)

def render_score_ring(score: int):
    if score >= 75:
        score_class = "score-high"
    elif score >= 50:
        score_class = "score-medium"
    else:
        score_class = "score-low"
    
    st.markdown(f"""
    <div class="score-container">
        <div class="score-ring {score_class}">
            <span class="score-value">{score}</span>
        </div>
        <div class="score-label">Confluence Score</div>
    </div>
    """, unsafe_allow_html=True)

def render_action_card(action: ActionCard):
    emoji = '🟢' if action.direction == 'CALLS' else ('🔴' if action.direction == 'PUTS' else ('🟡' if action.direction == 'WAIT' else '⛔'))
    card_class = f"action-{action.color}"
    dir_class = f"direction-{action.color}"
    
    st.markdown(f"""
    <div class="action-card {card_class}">
        <div class="direction-label {dir_class}">{emoji} {action.direction}</div>
    </div>
    """, unsafe_allow_html=True)

def render_contract_recommendation(action: ActionCard):
    """Display detailed contract recommendation based on the action."""
    
    if not action.contract_expectation:
        st.warning("No contract data available")
        return
    
    ce = action.contract_expectation
    cone_height = abs(action.target_100 - action.entry_level)
    
    # Calculate recommended strike (15-20 pts OTM)
    if ce.direction == 'CALLS':
        # OTM CALLS = strike ABOVE entry price
        strike = int(action.entry_level + 17.5)
        strike = ((strike + 4) // 5) * 5  # Round UP to nearest 5
        strike_label = f"SPX {strike}C (0DTE)"
        border_color = "#22c55e"
    else:
        # OTM PUTS = strike BELOW entry price
        strike = int(action.entry_level - 17.5)
        strike = (strike // 5) * 5  # Round DOWN to nearest 5
        strike_label = f"SPX {strike}P (0DTE)"
        border_color = "#ef4444"
    
    # Main contract card using native Streamlit
    st.markdown(f"""
    <div style="border: 3px solid {border_color}; border-radius: 12px; padding: 1rem; margin-bottom: 1rem; background: linear-gradient(135deg, {border_color}11, {border_color}22);">
        <h2 style="text-align: center; margin: 0; color: {border_color};">📋 {strike_label}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    # Entry and Stop in columns
    col_entry, col_stop = st.columns(2)
    with col_entry:
        st.metric("🎯 Entry Level", f"{action.entry_level:.2f}")
    with col_stop:
        st.metric("🛑 Stop Loss", f"{action.stop_level:.2f}", delta="-3 pts", delta_color="inverse")
    
    # Exit Strategy
    st.markdown("**📊 Exit Strategy (60/20/20):**")
    
    exit_data = {
        "Exit": ["60% @ 50%", "20% @ 75%", "20% @ 100%"],
        "SPX Level": [f"{action.target_50:.2f}", f"{action.target_75:.2f}", f"{action.target_100:.2f}"],
        "Contract Profit": [f"+${ce.contract_profit_50:.0f}", f"+${ce.contract_profit_75:.0f}", f"+${ce.contract_profit_100:.0f}"]
    }
    st.dataframe(exit_data, use_container_width=True, hide_index=True)
    
    # Stats row
    col_width, col_rr = st.columns(2)
    with col_width:
        st.metric("📏 Cone Width", f"{cone_height:.0f} pts")
    with col_rr:
        st.metric("⚖️ R:R @ 50%", f"{ce.risk_reward_50:.1f}:1")
    
    st.caption("💡 Contract moves ~0.33x underlying (strike 15-20 pts OTM)")

def render_decision_card(title: str, cones: List[Cone]):
    st.markdown(f"""
    <div class="decision-card">
        <div class="decision-time">{title}</div>
    </div>
    """, unsafe_allow_html=True)
    
    for cone in cones:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**{cone.name} Cone**")
        with col2:
            st.write("")
        
        col_puts, col_calls = st.columns(2)
        with col_puts:
            st.metric(
                label="🔴 Puts Entry ▲",
                value=f"{cone.ascending_rail:.2f}"
            )
        with col_calls:
            st.metric(
                label="🟢 Calls Entry ▼", 
                value=f"{cone.descending_rail:.2f}"
            )

def render_proximity_meters(cones: List[Cone], current_price: float):
    st.markdown("#### 📍 Distance to Entry Rails")
    
    for cone in cones:
        dist_asc = abs(current_price - cone.ascending_rail)
        dist_desc = abs(current_price - cone.descending_rail)
        
        # Ascending (Puts)
        pct_asc = min(100, (dist_asc / 50) * 100)
        prox_class_asc = "proximity-close" if dist_asc <= 10 else ("proximity-medium" if dist_asc <= 25 else "proximity-far")
        
        # Descending (Calls)
        pct_desc = min(100, (dist_desc / 50) * 100)
        prox_class_desc = "proximity-close" if dist_desc <= 10 else ("proximity-medium" if dist_desc <= 25 else "proximity-far")
        
        st.markdown(f"""
        <div class="premium-card" style="padding: 1rem;">
            <div style="font-weight: 600; margin-bottom: 0.75rem;">{cone.name} Cone</div>
            <div style="display: flex; gap: 1rem;">
                <div style="flex: 1;">
                    <div style="font-size: 0.75rem; color: #64748b;">To ▲ {cone.ascending_rail:.2f}</div>
                    <div style="font-weight: 600; color: #ef4444;">{dist_asc:.1f} pts</div>
                    <div class="proximity-bar"><div class="proximity-fill {prox_class_asc}" style="width: {100-pct_asc}%;"></div></div>
                </div>
                <div style="flex: 1;">
                    <div style="font-size: 0.75rem; color: #64748b;">To ▼ {cone.descending_rail:.2f}</div>
                    <div style="font-weight: 600; color: #22c55e;">{dist_desc:.1f} pts</div>
                    <div class="proximity-bar"><div class="proximity-fill {prox_class_desc}" style="width: {100-pct_desc}%;"></div></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_checklist(regime: RegimeAnalysis, action: ActionCard, cones: List[Cone], current_price: float, overnight_validation: dict = None):
    """
    Principled Trade Checklist based on Structural Cone Methodology.
    
    FRAMEWORK LOGIC:
    
    1. STRUCTURE INTEGRITY - Is the cone structure valid?
       - Cone width must provide enough room for profit (min 25 pts for 0DTE)
       - Overnight must not have broken the rails you're trading
    
    2. ENTRY QUALITY - Is this a good entry point?
       - Price must be AT a rail (within 5 pts)
       - Confluence (2+ rails) significantly increases edge
    
    3. TIMING - Are we at a decision point?
       - 8:30 AM = React to overnight + open
       - 10:00 AM = Primary decision window (structure has developed)
       - After 12:00 PM = Less time for move to play out (0DTE)
    
    4. RISK/REWARD - Does the math work?
       - Target must be achievable (cone width vs time remaining)
       - Contract move must be worth the risk (min $8-10 expected)
    
    5. CONFIRMATION - Extra factors that boost confidence
       - Overnight validated the rail (ES touched and bounced)
       - Secondary pivot confirms the level
    """
    
    st.markdown("#### 📋 Trade Checklist")
    
    # Get current time
    ct_now = get_ct_now()
    ct_time = ct_now.time()
    
    # Find nearest rail info
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    cone_width = nearest_cone.ascending_rail - nearest_cone.descending_rail if nearest_cone else 0
    
    # Find confluence
    zones_data = find_confluence_zones(cones)
    calls_zones = zones_data.get('calls_confluence', [])
    puts_zones = zones_data.get('puts_confluence', [])
    
    # Check if at confluence
    at_confluence = False
    confluence_strength = 0
    if nearest_rail_type == 'descending':
        for zone in calls_zones:
            if abs(current_price - zone['price']) <= 10:
                at_confluence = True
                confluence_strength = zone.get('strength', len(zone.get('rails', [])))
                break
    elif nearest_rail_type == 'ascending':
        for zone in puts_zones:
            if abs(current_price - zone['price']) <= 10:
                at_confluence = True
                confluence_strength = zone.get('strength', len(zone.get('rails', [])))
                break
    
    # Check overnight validation
    rail_validated = False
    rail_broken = False
    if overnight_validation:
        validated = overnight_validation.get('validated', [])
        broken = overnight_validation.get('broken', [])
        
        for v in validated:
            if nearest_rail_type == 'descending' and '▼' in v:
                rail_validated = True
            elif nearest_rail_type == 'ascending' and '▲' in v:
                rail_validated = True
        
        for b in broken:
            if nearest_rail_type == 'descending' and '▼' in b:
                rail_broken = True
            elif nearest_rail_type == 'ascending' and '▲' in b:
                rail_broken = True
    
    # =========================================================================
    # CHECKLIST ITEMS
    # =========================================================================
    
    checks = []
    
    # 1. STRUCTURE INTEGRITY
    structure_ok = cone_width >= 25 and not rail_broken
    if cone_width >= 35:
        structure_detail = f"Excellent ({cone_width:.0f} pts)"
    elif cone_width >= 25:
        structure_detail = f"Adequate ({cone_width:.0f} pts)"
    else:
        structure_detail = f"Too narrow ({cone_width:.0f} pts) - SKIP"
    
    if rail_broken:
        structure_detail = "Rail BROKEN overnight - SKIP"
        structure_ok = False
    
    checks.append(("1. Structure Intact", structure_ok, structure_detail))
    
    # 2. ENTRY QUALITY
    if nearest_distance <= 3:
        entry_quality = True
        entry_detail = f"Excellent - {nearest_distance:.1f} pts from rail"
    elif nearest_distance <= 5:
        entry_quality = True
        entry_detail = f"Good - {nearest_distance:.1f} pts from rail"
    elif nearest_distance <= 10:
        entry_quality = True
        entry_detail = f"Acceptable - {nearest_distance:.1f} pts from rail"
    else:
        entry_quality = False
        entry_detail = f"Too far - {nearest_distance:.1f} pts (wait for rail)"
    
    checks.append(("2. At Rail", entry_quality, entry_detail))
    
    # 3. CONFLUENCE
    if at_confluence and confluence_strength >= 3:
        confluence_ok = True
        confluence_detail = f"Strong - {confluence_strength} rails converge"
    elif at_confluence:
        confluence_ok = True
        confluence_detail = f"Present - {confluence_strength} rails"
    else:
        confluence_ok = False
        confluence_detail = "None - single rail only"
    
    checks.append(("3. Confluence", confluence_ok, confluence_detail))
    
    # 4. TIMING
    is_830_window = time(8, 15) <= ct_time <= time(9, 0)
    is_1000_window = time(9, 45) <= ct_time <= time(10, 30)
    is_late = ct_time >= time(12, 30)
    
    if is_1000_window:
        timing_ok = True
        timing_detail = "10:00 Decision Window ★"
    elif is_830_window:
        timing_ok = True
        timing_detail = "8:30 Open Window"
    elif is_late:
        timing_ok = False
        timing_detail = "Late (less time for move)"
    else:
        timing_ok = True
        timing_detail = "Mid-session"
    
    checks.append(("4. Timing", timing_ok, timing_detail))
    
    # 5. OVERNIGHT VALIDATION (Bonus)
    if rail_validated:
        validation_ok = True
        validation_detail = "Rail validated overnight ★"
    elif overnight_validation and len(overnight_validation.get('validated', [])) > 0:
        validation_ok = True
        validation_detail = "Other rails validated"
    else:
        validation_ok = False
        validation_detail = "Not tested overnight"
    
    checks.append(("5. Validated", validation_ok, validation_detail))
    
    # 6. R:R CHECK
    if action.contract_expectation:
        expected_profit = action.contract_expectation.contract_profit_50
        if expected_profit >= 15:
            rr_ok = True
            rr_detail = f"Good - ${expected_profit:.0f} @ 50%"
        elif expected_profit >= 8:
            rr_ok = True
            rr_detail = f"Acceptable - ${expected_profit:.0f} @ 50%"
        else:
            rr_ok = False
            rr_detail = f"Weak - ${expected_profit:.0f} @ 50%"
    else:
        rr_ok = False
        rr_detail = "N/A"
    
    checks.append(("6. R:R Worth It", rr_ok, rr_detail))
    
    # =========================================================================
    # RENDER CHECKLIST
    # =========================================================================
    
    passed_count = sum(1 for _, passed, _ in checks if passed)
    total_checks = len(checks)
    
    # Overall assessment
    if passed_count >= 5:
        overall = "🟢 STRONG SETUP"
        overall_color = "#22c55e"
    elif passed_count >= 4:
        overall = "🟡 ACCEPTABLE"
        overall_color = "#eab308"
    elif passed_count >= 3:
        overall = "🟠 MARGINAL"
        overall_color = "#f97316"
    else:
        overall = "🔴 SKIP"
        overall_color = "#ef4444"
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {overall_color}22, {overall_color}11); 
                border-left: 4px solid {overall_color}; padding: 0.75rem; border-radius: 8px; margin-bottom: 1rem;">
        <span style="font-weight: 700; font-size: 1.1rem;">{overall}</span>
        <span style="color: #64748b; margin-left: 0.5rem;">({passed_count}/{total_checks} passed)</span>
    </div>
    """, unsafe_allow_html=True)
    
    for label, passed, detail in checks:
        icon = "✓" if passed else "✗"
        color = "#22c55e" if passed else "#ef4444"
        bg = "#22c55e11" if passed else "#ef444411"
        st.markdown(f"""
        <div style="display: flex; align-items: center; padding: 0.5rem; margin: 0.25rem 0; 
                    background: {bg}; border-radius: 6px;">
            <span style="color: {color}; font-size: 1.1rem; font-weight: bold; width: 1.5rem;">{icon}</span>
            <span style="flex: 1; font-weight: 500;">{label}</span>
            <span style="color: #64748b; font-size: 0.85rem;">{detail}</span>
        </div>
        """, unsafe_allow_html=True)
    
    # KEY INSIGHT
    st.markdown("---")
    st.markdown("**💡 Key Insight:**")
    
    if rail_broken:
        st.error("Rail was broken overnight - structure is compromised. Wait for new setup.")
    elif not entry_quality:
        st.warning(f"Price is {nearest_distance:.1f} pts from nearest rail. Wait for price to reach {nearest_cone.descending_rail:.2f} (calls) or {nearest_cone.ascending_rail:.2f} (puts).")
    elif at_confluence and rail_validated:
        st.success("Strong setup: Confluence + Overnight validation. This is your highest probability trade.")
    elif at_confluence:
        st.info("Confluence present but not validated overnight. Good setup, standard size.")
    elif rail_validated:
        st.info("Rail validated but no confluence. Acceptable setup, consider reduced size.")
    else:
        st.warning("Single rail, no validation. Lower probability - reduce size or skip.")

def highlight_times(row):
    if row['Time'] in ['08:30', '10:00']:
        return ['background: linear-gradient(90deg, #fef3c7, #fde68a); font-weight: 700;'] * len(row)
    return [''] * len(row)

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    inject_premium_css()
    render_header()
    
    # ===== INTRADAY SESSION TRACKING =====
    # Track session high/low to detect triggered entries
    ct_now = get_ct_now()
    today_str = ct_now.strftime('%Y-%m-%d')
    
    # Initialize session state if needed
    if 'session_date' not in st.session_state:
        st.session_state.session_date = today_str
        st.session_state.session_high = None
        st.session_state.session_low = None
    
    # Reset if new trading day
    if st.session_state.session_date != today_str:
        st.session_state.session_date = today_str
        st.session_state.session_high = None
        st.session_state.session_low = None
    
    # ===== SIDEBAR =====
    with st.sidebar:
        st.markdown("### 📅 Session")
        session_date = st.date_input("Trading Date", value=datetime.now().date())
        session_date = datetime.combine(session_date, time(0, 0))
        
        # Fetch data
        prior_session = fetch_prior_session_data(session_date)
        es_data = fetch_es_overnight_data(session_date)
        premarket_data = fetch_premarket_pivots(session_date)
        current_price = fetch_current_spx() or (prior_session['close'] if prior_session else 6000)
        first_bar = fetch_first_30min_bar(session_date)
        
        # Update session high/low tracking (only during market hours for today's session)
        market_open = time(8, 30)
        market_close = time(15, 0)
        is_market_hours = market_open <= ct_now.time() <= market_close
        is_today = session_date.date() == ct_now.date()
        
        if is_today and is_market_hours and current_price:
            if st.session_state.session_high is None or current_price > st.session_state.session_high:
                st.session_state.session_high = current_price
            if st.session_state.session_low is None or current_price < st.session_state.session_low:
                st.session_state.session_low = current_price
        
        # Show session tracking info
        st.markdown("---")
        st.markdown("### 📊 Session Tracker")
        sess_col1, sess_col2 = st.columns(2)
        with sess_col1:
            if st.session_state.session_high:
                st.metric("Session High", f"{st.session_state.session_high:,.2f}")
            else:
                st.metric("Session High", "—")
        with sess_col2:
            if st.session_state.session_low:
                st.metric("Session Low", f"{st.session_state.session_low:,.2f}")
            else:
                st.metric("Session Low", "—")
        
        if not is_market_hours:
            st.caption("Updates during market hours (8:30-3:00 CT)")
        
        st.markdown("---")
        st.markdown("### ⚙️ Parameters")
        col_slope1, col_slope2 = st.columns(2)
        with col_slope1:
            st.metric("Ascending", f"+{SLOPE_ASCENDING}")
        with col_slope2:
            st.metric("Descending", f"-{SLOPE_DESCENDING}")
        
        # ========== PRICE CORRECTION OFFSET ==========
        st.markdown("---")
        st.markdown("### 🔧 Price Correction")
        st.caption("Adjust for Yahoo/TradingView difference")
        price_offset = st.number_input(
            "Price Offset", 
            value=0.0, 
            min_value=-10.0, 
            max_value=10.0, 
            step=0.25,
            format="%.2f",
            help="Subtract this from Yahoo prices to match TradingView. E.g., if Yahoo shows 6052 but TV shows 6050, enter 2.0"
        )
        
        st.markdown("---")
        st.markdown("### 📍 Primary Pivots")
        
        # Initialize secondary pivot variables
        secondary_high_price = None
        secondary_high_time = None
        secondary_low_price = None
        secondary_low_time = None
        
        # Initialize premarket pivot variables
        premarket_high_price = None
        premarket_high_time = None
        premarket_low_price = None
        premarket_low_time = None
        use_premarket_high = False
        use_premarket_low = False
        
        if prior_session:
            st.caption(f"Source: {prior_session['date'].strftime('%Y-%m-%d')}")
            if prior_session.get('power_hour_filtered'):
                st.warning("⚡ High filtered (power hour)")
            
            # ============================================================
            # PIVOT DETECTION METHODOLOGY
            # HIGH pivots (Primary & Secondary) = Use WICKS - rejection points
            #   → Both ascending AND descending rails from High use wick value
            # LOW pivots (Primary & Secondary) = Use CLOSE - commitment points
            #   → Both ascending AND descending rails from Low use close value
            # ============================================================
            st.info("📊 **HIGH pivots** → Wick (rejection) | **LOW pivots** → Close (commitment)")
            
            # HIGH pivot → Use candle HIGH (wick) - both rails project from this
            base_high = prior_session['high']  # Wick high
            base_high_time = prior_session['high_time']
            base_sec_high = prior_session.get('secondary_high')  # Wick-based secondary high
            base_sec_high_time = prior_session.get('secondary_high_time')
            
            # LOW pivot → Use CLOSE - both rails project from this
            base_low = prior_session.get('low_line', prior_session['low'])  # Close-based low
            base_low_time = prior_session.get('low_line_time', prior_session['low_time'])
            base_sec_low = prior_session.get('secondary_low_line')  # Close-based secondary low
            base_sec_low_time = prior_session.get('secondary_low_line_time')
            
            # Apply price offset
            auto_high = base_high - price_offset
            auto_low = base_low - price_offset
            auto_close = prior_session['close'] - price_offset
            
            use_manual = st.checkbox("✏️ Manual Price Override", value=False, help="Enable to enter your TradingView prices directly")
            
            if use_manual:
                st.info("Enter your TradingView prices below")
                high_price = st.number_input("High (Wick)", value=float(auto_high), format="%.2f", help="For ascending rails (resistance)")
                high_time_str = st.text_input("High Time (CT)", value=base_high_time.strftime('%H:%M'))
                low_price = st.number_input("Low (Close)", value=float(auto_low), format="%.2f", help="For descending rails (support)")
                low_time_str = st.text_input("Low Time (CT)", value=base_low_time.strftime('%H:%M'))
                close_price = st.number_input("Close", value=float(auto_close), format="%.2f")
            else:
                # Show corrected values (with offset applied)
                high_price = auto_high
                low_price = auto_low
                close_price = auto_close
                high_time_str = base_high_time.strftime('%H:%M')
                low_time_str = base_low_time.strftime('%H:%M')
                
                st.metric("High (Wick)", f"{high_price:.2f}", f"@ {high_time_str} CT")
                st.metric("Low (Close)", f"{low_price:.2f}", f"@ {low_time_str} CT")
                st.metric("Close", f"{close_price:.2f}")
                
                if price_offset != 0:
                    st.caption(f"📉 Offset applied: -{price_offset:.2f} pts")
            
            # Secondary Pivots Display
            if base_sec_high is not None or base_sec_low is not None:
                st.markdown("---")
                st.markdown("### 📍 Secondary Pivots")
                st.caption("High² = Wick | Low² = Close")
            
            if base_sec_high is not None:
                st.success("🔄 Secondary High Detected!")
                secondary_high_price = base_sec_high - price_offset
                secondary_high_time = base_sec_high_time
                st.metric("2nd High² (Wick)", f"{secondary_high_price:.2f}", f"@ {secondary_high_time.strftime('%H:%M')} CT")
            
            if base_sec_low is not None:
                st.success("🔄 Secondary Low Detected!")
                secondary_low_price = base_sec_low - price_offset
                secondary_low_time = base_sec_low_time
                st.metric("2nd Low² (Close)", f"{secondary_low_price:.2f}", f"@ {secondary_low_time.strftime('%H:%M')} CT")
            
            # ========== PRE-MARKET PIVOTS ==========
            st.markdown("---")
            st.markdown("### 🌅 Pre-Market Pivots")
            st.caption("Previous day's pre-market (6am-8:30am CT)")
            
            if premarket_data:
                # Apply ES-SPX offset if available
                es_spx_offset = es_data.get('offset', 60) if es_data else 60
                premarket_high_spx = premarket_data['premarket_high_es'] - es_spx_offset - price_offset
                premarket_low_spx = premarket_data['premarket_low_es'] - es_spx_offset - price_offset
                
                col_pm1, col_pm2 = st.columns(2)
                with col_pm1:
                    use_premarket_high = st.checkbox("Use PM High", value=False)
                with col_pm2:
                    use_premarket_low = st.checkbox("Use PM Low", value=False)
                
                if use_premarket_high or use_premarket_low:
                    st.info("Pre-market pivots will be added to analysis")
                
                if use_premarket_high:
                    premarket_high_price = st.number_input(
                        "PM High (SPX equiv)", 
                        value=float(premarket_high_spx), 
                        format="%.2f",
                        help="Pre-market high converted to SPX equivalent"
                    )
                    premarket_high_time = premarket_data['premarket_high_time']
                    st.caption(f"@ {premarket_high_time.strftime('%H:%M')} CT")
                
                if use_premarket_low:
                    premarket_low_price = st.number_input(
                        "PM Low (SPX equiv)", 
                        value=float(premarket_low_spx), 
                        format="%.2f",
                        help="Pre-market low converted to SPX equivalent"
                    )
                    premarket_low_time = premarket_data['premarket_low_time']
                    st.caption(f"@ {premarket_low_time.strftime('%H:%M')} CT")
            else:
                st.caption("No pre-market data available")
                use_premarket_high = st.checkbox("Add PM High manually", value=False)
                use_premarket_low = st.checkbox("Add PM Low manually", value=False)
                
                if use_premarket_high:
                    premarket_high_price = st.number_input("PM High", value=6050.0, format="%.2f")
                    pm_high_time_str = st.text_input("PM High Time", value="07:30")
                    try:
                        h, m = map(int, pm_high_time_str.split(':'))
                        prior_date = session_date - timedelta(days=1)
                        while prior_date.weekday() >= 5:
                            prior_date -= timedelta(days=1)
                        premarket_high_time = CT_TZ.localize(datetime.combine(prior_date, time(h, m)))
                    except:
                        premarket_high_time = None
                
                if use_premarket_low:
                    premarket_low_price = st.number_input("PM Low", value=6000.0, format="%.2f")
                    pm_low_time_str = st.text_input("PM Low Time", value="07:30")
                    try:
                        h, m = map(int, pm_low_time_str.split(':'))
                        prior_date = session_date - timedelta(days=1)
                        while prior_date.weekday() >= 5:
                            prior_date -= timedelta(days=1)
                        premarket_low_time = CT_TZ.localize(datetime.combine(prior_date, time(h, m)))
                    except:
                        premarket_low_time = None
            
            # Debug: Show timing info
            with st.expander("🔍 Pivot Timing Details"):
                st.markdown("**Methodology:**")
                st.markdown("- **HIGH pivots** → Use Wick (rejection point)")
                st.markdown("- **LOW pivots** → Use Close (commitment point)")
                st.markdown("- Each pivot projects BOTH ascending & descending rails")
                st.markdown("---")
                st.write(f"**Primary High (Wick):** {high_price:.2f} @ {high_time_str} CT")
                st.write(f"**Primary Low (Close):** {low_price:.2f} @ {low_time_str} CT")
                if secondary_high_price is not None:
                    st.write(f"**Secondary High² (Wick):** {secondary_high_price:.2f} @ {secondary_high_time.strftime('%H:%M')} CT")
                else:
                    st.write("**Secondary High²:** Not detected")
                if secondary_low_price is not None:
                    st.write(f"**Secondary Low² (Close):** {secondary_low_price:.2f} @ {secondary_low_time.strftime('%H:%M')} CT")
                else:
                    st.write("**Secondary Low²:** Not detected")
                if use_premarket_high and premarket_high_price:
                    st.write(f"**Pre-Market High:** {premarket_high_price:.2f} @ {premarket_high_time.strftime('%H:%M')} CT")
                if use_premarket_low and premarket_low_price:
                    st.write(f"**Pre-Market Low:** {premarket_low_price:.2f} @ {premarket_low_time.strftime('%H:%M')} CT")
                
                # Show all raw values for reference
                st.markdown("---")
                st.markdown("**📊 Raw Detected Values (for comparison):**")
                candle_high = prior_session['high']
                candle_high_time = prior_session['high_time']
                line_low = prior_session.get('low_line', prior_session['low'])
                line_low_time = prior_session.get('low_line_time', prior_session['low_time'])
                candle_low = prior_session['low']
                candle_low_time = prior_session['low_time']
                st.write(f"High (Wick): {candle_high - price_offset:.2f} @ {candle_high_time.strftime('%H:%M')} ✓ Used")
                st.write(f"Low (Wick): {candle_low - price_offset:.2f} @ {candle_low_time.strftime('%H:%M')}")
                st.write(f"Low (Close): {line_low - price_offset:.2f} @ {line_low_time.strftime('%H:%M')} ✓ Used")
            
            try:
                h, m = map(int, high_time_str.split(':'))
                high_time = CT_TZ.localize(datetime.combine(prior_session['date'], time(h, m)))
            except:
                high_time = base_high_time
            
            try:
                h, m = map(int, low_time_str.split(':'))
                low_time = CT_TZ.localize(datetime.combine(prior_session['date'], time(h, m)))
            except:
                low_time = base_low_time
            
            close_time = CT_TZ.localize(datetime.combine(prior_session['date'], time(15, 0)))
        else:
            st.error("No data - enter manually")
            high_price = st.number_input("High", value=6050.0, format="%.2f")
            low_price = st.number_input("Low", value=6000.0, format="%.2f")
            close_price = st.number_input("Close", value=6025.0, format="%.2f")
            high_time_str = st.text_input("High Time", value="10:30")
            low_time_str = st.text_input("Low Time", value="13:45")
            
            prior_date = session_date - timedelta(days=1)
            while prior_date.weekday() >= 5:
                prior_date -= timedelta(days=1)
            
            try:
                h, m = map(int, high_time_str.split(':'))
                high_time = CT_TZ.localize(datetime.combine(prior_date, time(h, m)))
            except:
                high_time = CT_TZ.localize(datetime.combine(prior_date, time(10, 30)))
            try:
                h, m = map(int, low_time_str.split(':'))
                low_time = CT_TZ.localize(datetime.combine(prior_date, time(h, m)))
            except:
                low_time = CT_TZ.localize(datetime.combine(prior_date, time(13, 45)))
            close_time = CT_TZ.localize(datetime.combine(prior_date, time(15, 0)))
        
        if es_data and es_data.get('offset'):
            st.markdown("---")
            st.markdown("### 🔄 ES-SPX Offset")
            st.metric("Offset", f"{es_data['offset']:.2f} pts")
    
    # Build PRIMARY pivots
    pivots = [
        Pivot(price=high_price, time=high_time, name='High'),
        Pivot(price=close_price, time=close_time, name='Close'),
        Pivot(price=low_price, time=low_time, name='Low')
    ]
    
    # Add PRE-MARKET pivots if enabled
    if use_premarket_high and premarket_high_price and premarket_high_time:
        pivots.append(Pivot(price=premarket_high_price, time=premarket_high_time, name='PM High'))
    if use_premarket_low and premarket_low_price and premarket_low_time:
        pivots.append(Pivot(price=premarket_low_price, time=premarket_low_time, name='PM Low'))
    
    # ========== OVERNIGHT VALIDATION ==========
    # Validate which structures overnight ES respected
    overnight_validation = validate_overnight_rails(
        es_data=es_data,
        pivots=pivots,
        secondary_high=secondary_high_price,
        secondary_high_time=secondary_high_time,
        secondary_low=secondary_low_price,
        secondary_low_time=secondary_low_time,
        session_date=session_date
    )
    
    # Build SECONDARY pivots only if they should be shown (not broken)
    secondary_pivots = []
    
    # Add secondary high if it should be shown
    if secondary_high_price is not None and secondary_high_time is not None:
        if 'secondary' in overnight_validation.get('high_structures_to_show', []):
            secondary_pivots.append(Pivot(price=secondary_high_price, time=secondary_high_time, name='High²'))
    
    # Add secondary low if it should be shown
    if secondary_low_price is not None and secondary_low_time is not None:
        if 'secondary' in overnight_validation.get('low_structures_to_show', []):
            secondary_pivots.append(Pivot(price=secondary_low_price, time=secondary_low_time, name='Low²'))
    
    # Combine all pivots for analysis
    all_pivots = pivots + secondary_pivots
    
    ct_now = get_ct_now()
    if session_date.date() == ct_now.date():
        eval_time = ct_now
        is_10am = ct_now.time() >= time(10, 0)
    else:
        eval_time = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        is_10am = True
    
    cones = build_cones_at_time(all_pivots, eval_time)
    cones_830 = build_cones_at_time(all_pivots, CT_TZ.localize(datetime.combine(session_date, time(8, 30))))
    cones_1000 = build_cones_at_time(all_pivots, CT_TZ.localize(datetime.combine(session_date, time(10, 0))))
    
    regime = analyze_regime(cones, es_data, prior_session, first_bar, current_price)
    action = generate_action_card(cones, regime, current_price, is_10am, overnight_validation)
    confluence_zones = find_confluence_zones(cones_1000)
    
    # Generate complete trade setups for all confluence zones
    trade_setups_830 = generate_trade_setups(cones_830, current_price)
    trade_setups_1000 = generate_trade_setups(cones_1000, current_price)
    
    # ===== INSTITUTIONAL TERMINAL LAYOUT =====
    
    # Count setups
    num_calls = len(trade_setups_1000.get('calls_setups', []))
    num_puts = len(trade_setups_1000.get('puts_setups', []))
    ct_time = get_ct_now()
    
    # TERMINAL HEADER
    st.markdown(f"""
    <div class="terminal-header">
        <div class="terminal-logo">
            <div class="terminal-logo-icon">SP</div>
            <div>
                <div class="terminal-title">SPX PROPHET</div>
                <div class="terminal-subtitle">Institutional Options Intelligence</div>
            </div>
        </div>
        <div class="terminal-status">
            <div class="status-item">
                <div class="status-label">SPX Index</div>
                <div class="status-value">{current_price:,.2f}</div>
            </div>
            <div class="status-item">
                <div class="status-label">Session</div>
                <div class="status-value status-live">
                    <span class="live-dot"></span>
                    {ct_time.strftime('%H:%M:%S')} CT
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # QUICK STATS BAR
    trading_window = "OPEN" if ct_time.time() < LAST_ENTRY_TIME else "CLOSED"
    window_color = "green" if trading_window == "OPEN" else "red"
    
    st.markdown(f"""
    <div class="stats-bar">
        <div class="stat-item">
            <div class="stat-indicator green"></div>
            <div class="stat-text"><strong>{num_calls}</strong> CALLS Setups</div>
        </div>
        <div class="stat-item">
            <div class="stat-indicator red"></div>
            <div class="stat-text"><strong>{num_puts}</strong> PUTS Setups</div>
        </div>
        <div class="stat-item">
            <div class="stat-indicator {window_color}"></div>
            <div class="stat-text">Trading Window: <strong>{trading_window}</strong></div>
        </div>
        <div class="stat-item">
            <div class="stat-indicator gold"></div>
            <div class="stat-text">Decision: <strong>10:00 AM CT</strong></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ==========================================================================
    # OVERNIGHT ES DATA (shows SPX implied from ES futures)
    # ==========================================================================
    if es_data and es_data.get('current') and es_data.get('offset'):
        es_current = es_data['current']
        es_offset = es_data['offset']
        spx_implied = es_current - es_offset
        
        st.markdown("#### 📊 ES Futures → SPX Implied")
        es_c1, es_c2, es_c3 = st.columns(3)
        with es_c1:
            st.metric("ES Futures", f"{es_current:,.2f}")
        with es_c2:
            st.metric("Offset", f"{es_offset:+.2f}")
        with es_c3:
            st.metric("SPX Implied", f"{spx_implied:,.2f}")
    
    # ==========================================================================
    # ACTIVE TRADE SETUPS
    # ==========================================================================
    
    # CALLS SECTION
    st.markdown("""
    <div class="section-header">
        <div class="section-icon">📈</div>
        <div class="section-title">Calls Entry Levels — Long Positions</div>
    </div>
    """, unsafe_allow_html=True)
    
    if num_calls > 0:
        for setup in trade_setups_1000['calls_setups']:
            render_institutional_trade_card(setup, current_price)
    else:
        st.markdown("""
        <div class="trade-panel">
            <div class="trade-panel-body" style="text-align: center; color: var(--text-muted);">
                No high-probability CALLS entries detected for this session
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # PUTS SECTION
    st.markdown("""
    <div class="section-header">
        <div class="section-icon">📉</div>
        <div class="section-title">Puts Entry Levels — Short Positions</div>
    </div>
    """, unsafe_allow_html=True)
    
    if num_puts > 0:
        for setup in trade_setups_1000['puts_setups']:
            render_institutional_trade_card(setup, current_price)
    else:
        st.markdown("""
        <div class="trade-panel">
            <div class="trade-panel-body" style="text-align: center; color: var(--text-muted);">
                No high-probability PUTS entries detected for this session
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # ==========================================================================
    # POSITION MONITOR
    # ==========================================================================
    
    all_setups = trade_setups_1000.get('calls_setups', []) + trade_setups_1000.get('puts_setups', [])
    
    if all_setups:
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">🎯</div>
            <div class="section-title">Position Monitor — Next Entry</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Get session high/low for trigger detection
        session_high = st.session_state.get('session_high')
        session_low = st.session_state.get('session_low')
        
        # Buffer for "close enough" triggers (accounts for spreads/slippage)
        TRIGGER_BUFFER = 1.0  # 1 point buffer
        
        active_setups = []
        triggered_setups = []
        
        for setup in all_setups:
            setup.distance = abs(current_price - setup.entry_price)
            setup.triggered = False
            
            if setup.direction == "CALLS":
                # CALLS entry triggers when price dips TO or NEAR entry level
                # Check if session low reached within buffer of entry
                if session_low is not None and session_low <= setup.entry_price + TRIGGER_BUFFER:
                    setup.triggered = True
                    triggered_setups.append(setup)
                else:
                    active_setups.append(setup)
            else:  # PUTS
                # PUTS entry triggers when price rises TO or NEAR entry level
                # Check if session high reached within buffer of entry
                if session_high is not None and session_high >= setup.entry_price - TRIGGER_BUFFER:
                    setup.triggered = True
                    triggered_setups.append(setup)
                else:
                    active_setups.append(setup)
        
        # Show next active entry (not yet triggered)
        if active_setups:
            nearest = min(active_setups, key=lambda x: x.distance)
            
            # Determine status
            if nearest.distance <= AT_RAIL_THRESHOLD:
                status = "AT ENTRY"
                status_class = "badge-go"
            elif nearest.distance <= 15:
                status = "APPROACHING"
                status_class = "badge-wait"
            else:
                status = "WAITING"
                status_class = "badge-nogo"
            
            direction_class = "badge-calls" if nearest.direction == "CALLS" else "badge-puts"
            
            st.markdown(f"""
            <div class="trade-panel">
                <div class="trade-panel-header">
                    <div class="trade-panel-title">Priority Target</div>
                    <div>
                        <span class="trade-panel-badge {direction_class}">{nearest.direction}</span>
                        <span class="trade-panel-badge {status_class}">{status}</span>
                    </div>
                </div>
                <div class="trade-panel-body">
                    <div class="contract-display">
                        <div class="contract-strike">{nearest.strike_label}</div>
                        <div class="contract-type">0DTE SPX Option</div>
                    </div>
                    <div class="entry-row">
                        <div class="entry-item">
                            <div class="entry-label">Current Price</div>
                            <div class="entry-value">{current_price:,.2f}</div>
                        </div>
                        <div class="entry-item">
                            <div class="entry-label">Entry Level</div>
                            <div class="entry-value gold">{nearest.entry_price:,.2f}</div>
                        </div>
                        <div class="entry-item">
                            <div class="entry-label">Distance</div>
                            <div class="entry-value">{nearest.distance:.1f} pts</div>
                        </div>
                        <div class="entry-item">
                            <div class="entry-label">Target (50%)</div>
                            <div class="entry-value green">+${nearest.profit_50_theta_adjusted:,.0f}</div>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Show triggered entries (completed trades)
        if triggered_setups:
            st.markdown(f"""
            <div style="margin-top: 0.5rem; padding: 0.75rem 1rem; background: var(--bg-tertiary); border-radius: 6px; border-left: 3px solid var(--accent-green);">
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">✅ TRIGGERED TODAY</div>
                <div style="font-size: 0.85rem; color: var(--text-primary);">
                    {', '.join([f"{s.direction} @ {s.entry_price:.2f}" for s in triggered_setups])}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        if not active_setups:
            st.markdown("""
            <div class="trade-panel">
                <div class="trade-panel-body" style="text-align: center; color: var(--text-muted);">
                    All entries triggered for today — no active setups remaining
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ==========================================================================
    # SECONDARY: Decision Windows Comparison
    # ==========================================================================
    
    with st.expander("🕐 Compare 8:30 AM vs 10:00 AM Setups"):
        col_830_exp, col_1000_exp = st.columns(2)
        
        with col_830_exp:
            st.markdown("**8:30 AM Setups:**")
            if trade_setups_830.get('calls_setups'):
                for s in trade_setups_830['calls_setups']:
                    st.write(f"🟢 {s.strike_label} @ {s.entry_price:.2f}")
            if trade_setups_830.get('puts_setups'):
                for s in trade_setups_830['puts_setups']:
                    st.write(f"🔴 {s.strike_label} @ {s.entry_price:.2f}")
        
        with col_1000_exp:
            st.markdown("**10:00 AM Setups:**")
            if trade_setups_1000.get('calls_setups'):
                for s in trade_setups_1000['calls_setups']:
                    st.write(f"🟢 {s.strike_label} @ {s.entry_price:.2f}")
            if trade_setups_1000.get('puts_setups'):
                for s in trade_setups_1000['puts_setups']:
                    st.write(f"🔴 {s.strike_label} @ {s.entry_price:.2f}")
    
    # ==========================================================================
    # CHECKLIST & VALIDATION INFO
    # ==========================================================================
    
    col_check, col_val = st.columns(2)
    
    with col_check:
        render_checklist(regime, action, cones, current_price, overnight_validation)
    
    with col_val:
        # Overnight Validation Display
        if overnight_validation and overnight_validation.get('validation_notes'):
            st.markdown("#### 🌙 Overnight Validation")
            
            # High structure status
            active_high = overnight_validation.get('active_high_structure', 'primary')
            if active_high == 'secondary':
                st.success("✓ HIGH: Secondary (High²) validated")
            elif overnight_validation.get('high_secondary_broken'):
                st.warning("⚠ HIGH: Secondary broken overnight")
            
            # Low structure status
            active_low = overnight_validation.get('active_low_structure', 'primary')
            if active_low == 'secondary':
                st.success("✓ LOW: Secondary (Low²) validated")
            elif overnight_validation.get('low_secondary_broken'):
                st.warning("⚠ LOW: Secondary broken overnight")
            
            # Validation notes in expander
            with st.expander("📋 Detailed Notes"):
                for note in overnight_validation['validation_notes']:
                    st.write(note)
        else:
            st.info("No overnight validation data available")
    
    st.markdown("---")
    
    # Row: Full Projection Table
    st.markdown("### 📊 Full Cone Projection Table")
    st.caption("💡 Yellow rows = Key decision windows (8:30 AM and 10:00 AM CT) | High²/Low² = Secondary pivots")
    
    df = build_projection_table(all_pivots, session_date)
    
    # Format numbers
    for col in df.columns:
        if col != 'Time':
            df[col] = df[col].apply(lambda x: f"{x:.2f}")
    
    styled = df.style.apply(highlight_times, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)
    
    # Secondary pivot explanation
    if secondary_pivots:
        st.markdown("---")
        st.markdown("### 🔄 Secondary Pivot Analysis")
        st.info("""
        **Secondary pivots detected!** These form when:
        - Price makes a significant pullback (>0.3%) after the primary high/low
        - Then bounces to create a lower high or higher low
        
        **How to use:**
        - Check which structure overnight ES respected
        - If overnight held at the secondary rail → that's likely the active structure
        - Watch for confluence where primary and secondary rails converge
        """)
    
    # Footer insight
    st.markdown("---")
    st.info("💡 **Pro Tip:** Your highest-probability trades occur when price touches a rail at the 10:00 AM CT decision window AND that rail shows confluence with another cone.")

if __name__ == "__main__":
    main()
