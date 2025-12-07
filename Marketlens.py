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

# SLOPES - Symmetric ±0.45 pts per 30-min block
SLOPE_ASCENDING = 0.45
SLOPE_DESCENDING = 0.45
CONTRACT_FACTOR = 0.33

MAINTENANCE_START_CT = time(16, 0)
MAINTENANCE_END_CT = time(17, 0)
POWER_HOUR_START = time(14, 0)  # Avoid highs during power hour

# Pre-market window (for detecting pre-market pivots)
PREMARKET_START_CT = time(6, 0)   # Pre-market starts 6am CT
PREMARKET_END_CT = time(8, 30)    # Pre-market ends at SPX open

# Secondary Pivot Detection
SECONDARY_PIVOT_MIN_PULLBACK_PCT = 0.003  # 0.3% pullback required
SECONDARY_PIVOT_MIN_DISTANCE = 5.0  # At least 5 points from primary
SECONDARY_PIVOT_START_TIME = time(13, 0)  # Secondary pivots after 1pm CT

OVERNIGHT_RANGE_MAX_PCT = 0.40
DEAD_ZONE_PCT = 0.40
MIN_CONE_WIDTH_PCT = 0.0045
MIN_PRIOR_DAY_RANGE_PCT = 0.009
MIN_CONTRACT_MOVE = 8.0
RAIL_TOUCH_THRESHOLD = 1.0
EDGE_ZONE_PCT = 0.30

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
    overnight_range: float
    overnight_range_pct: float
    overnight_touched_rails: List[str]
    opening_position: str
    first_bar_energy: str
    cone_width_adequate: bool
    prior_day_range_adequate: bool
    es_spx_offset: float

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
    - Weekend closure: Friday 4pm CT to Sunday 5pm CT
    
    The market treats Monday as the next day after Friday.
    Friday close (4pm CT) → Sunday open (5pm CT) = no blocks counted during weekend
    """
    if start_time >= end_time:
        return 0
    
    blocks = 0
    current = start_time
    
    while current < end_time:
        current_ct = current.astimezone(CT_TZ)
        current_ct_time = current_ct.time()
        current_weekday = current_ct.weekday()  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
        
        # Skip weekend hours
        # Saturday (5) - skip entirely
        # Sunday (6) before 5pm CT - skip
        # Friday (4) after 4pm CT - skip (this is covered by maintenance window)
        
        if current_weekday == 5:  # Saturday
            # Skip to Sunday
            current = current + timedelta(minutes=30)
            continue
        
        if current_weekday == 6:  # Sunday
            if current_ct_time < MAINTENANCE_END_CT:  # Before 5pm CT
                current = current + timedelta(minutes=30)
                continue
        
        # Skip daily maintenance window (4pm-5pm CT) on all days
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
    cone_width = ascending_rail - descending_rail
    if cone_width <= 0:
        return 'invalid', 0
    
    position_pct = (price - descending_rail) / cone_width
    
    if position_pct <= EDGE_ZONE_PCT:
        return 'lower_edge', abs(price - descending_rail)
    elif position_pct >= (1 - EDGE_ZONE_PCT):
        return 'upper_edge', abs(price - ascending_rail)
    else:
        return 'dead_zone', min(abs(price - ascending_rail), abs(price - descending_rail))

# ============================================================================
# DATA FETCHING WITH POWER HOUR FILTER
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
                'secondary_low_time': None
            }
        
        # Convert index to CT for filtering
        df_intraday_ct = df_intraday.copy()
        df_intraday_ct['ct_time'] = df_intraday_ct.index.tz_convert(CT_TZ).time
        df_intraday_ct['ct_datetime'] = df_intraday_ct.index.tz_convert(CT_TZ)
        
        # POWER HOUR FILTER: Find high before 14:00 CT
        df_before_power_hour = df_intraday_ct[df_intraday_ct['ct_time'] < POWER_HOUR_START]
        
        power_hour_filtered = False
        if not df_before_power_hour.empty:
            overall_high_idx = df_intraday['High'].idxmax()
            overall_high_time = to_ct(overall_high_idx.to_pydatetime()).time()
            
            if overall_high_time >= POWER_HOUR_START:
                high_idx = df_before_power_hour['High'].idxmax()
                power_hour_filtered = True
            else:
                high_idx = overall_high_idx
        else:
            high_idx = df_intraday['High'].idxmax()
        
        low_idx = df_intraday['Low'].idxmin()
        
        high_time = to_ct(high_idx.to_pydatetime())
        low_time = to_ct(low_idx.to_pydatetime())
        close_time = CT_TZ.localize(datetime.combine(prior_date, time(15, 0)))
        
        high_price = df_intraday.loc[high_idx, 'High']
        low_price = df_intraday['Low'].min()
        close_price = df_intraday['Close'].iloc[-1]
        
        # ============================================================
        # SECONDARY HIGH DETECTION (Completely Independent)
        # Looking for: Primary High -> Pullback -> Lower High (Secondary High)
        # 
        # IMPORTANT: This detection is independent of where the primary LOW is.
        # The secondary high is about price structure after the primary high,
        # not about the relationship to the low.
        # ============================================================
        secondary_high = None
        secondary_high_time = None
        
        # Get ALL data after primary high
        df_after_high = df_intraday_ct[df_intraday_ct.index > high_idx].copy()
        
        if len(df_after_high) >= 2:  # Need at least 2 bars after high
            # Method: Find local highs after the primary high that are lower than primary
            # A secondary high is a bounce that fails to make a new high
            
            # First, find if there was any significant pullback after the high
            all_lows_after_high = df_after_high['Low'].values
            all_highs_after_high = df_after_high['High'].values
            
            min_after_high = df_after_high['Low'].min()
            pullback_pct = (high_price - min_after_high) / high_price
            
            if pullback_pct >= SECONDARY_PIVOT_MIN_PULLBACK_PCT:
                # There was a significant pullback - now look for a bounce (secondary high)
                
                # Find the index of the minimum low after the primary high
                min_low_idx = df_after_high['Low'].idxmin()
                min_low_position = df_after_high.index.get_loc(min_low_idx)
                
                # Look at bars AFTER the minimum OR INCLUDING the minimum bar
                # (because the same bar could have the low AND the bounce high)
                
                # Check if the bar that made the low also had a high that qualifies as secondary high
                min_bar = df_after_high.loc[min_low_idx]
                bar_high = min_bar['High']
                
                # This bar's high could be the secondary high if:
                # 1. It's lower than primary high by at least 5 points
                # 2. Price dropped after this point
                if (bar_high < high_price and 
                    (high_price - bar_high) >= SECONDARY_PIVOT_MIN_DISTANCE):
                    
                    # Check if there's downward movement after this bar
                    df_after_this_bar = df_after_high[df_after_high.index > min_low_idx]
                    
                    if not df_after_this_bar.empty:
                        # If ANY subsequent bar has a lower low, the secondary high is confirmed
                        subsequent_lows = df_after_this_bar['Low'].min()
                        if subsequent_lows < bar_high:
                            secondary_high = bar_high
                            secondary_high_time = to_ct(min_low_idx.to_pydatetime())
                    else:
                        # Last bar of day - check if it closed lower than its high
                        if min_bar['Close'] < bar_high * 0.999:  # Closed at least 0.1% below high
                            secondary_high = bar_high
                            secondary_high_time = to_ct(min_low_idx.to_pydatetime())
                
                # If we didn't find it on the min bar, look at bars after the minimum
                if secondary_high is None and min_low_position < len(df_after_high) - 1:
                    df_after_min = df_after_high.iloc[min_low_position + 1:]
                    
                    if not df_after_min.empty:
                        # Find the highest high after the minimum low
                        max_high_idx = df_after_min['High'].idxmax()
                        potential_secondary_high = df_after_min.loc[max_high_idx, 'High']
                        
                        if (potential_secondary_high < high_price and 
                            (high_price - potential_secondary_high) >= SECONDARY_PIVOT_MIN_DISTANCE):
                            
                            # Confirm it's a pivot by checking for downward movement after
                            df_after_potential = df_after_min[df_after_min.index > max_high_idx]
                            
                            if not df_after_potential.empty:
                                if df_after_potential['Low'].min() < potential_secondary_high:
                                    secondary_high = potential_secondary_high
                                    secondary_high_time = to_ct(max_high_idx.to_pydatetime())
                            else:
                                # Last bar - accept if closed lower
                                last_bar = df_after_min.loc[max_high_idx]
                                if last_bar['Close'] < potential_secondary_high * 0.999:
                                    secondary_high = potential_secondary_high
                                    secondary_high_time = to_ct(max_high_idx.to_pydatetime())
        
        # ============================================================
        # SECONDARY LOW DETECTION (Completely Independent)
        # Looking for: Primary Low -> Bounce -> Higher Low (Secondary Low)
        # 
        # IMPORTANT: If a secondary high was detected, we should NOT use
        # the same candle for secondary low detection.
        # ============================================================
        secondary_low = None
        secondary_low_time = None
        secondary_high_candle_idx = None  # Track which candle made secondary high
        
        # Store the secondary high candle index for exclusion
        if secondary_high_time is not None:
            # Find the candle index that corresponds to secondary_high_time
            for idx in df_intraday_ct.index:
                if to_ct(idx.to_pydatetime()) == secondary_high_time:
                    secondary_high_candle_idx = idx
                    break
        
        # Get ALL data after primary low
        df_after_low = df_intraday_ct[df_intraday_ct.index > low_idx].copy()
        
        # EXCLUDE the secondary high candle from consideration
        if secondary_high_candle_idx is not None and secondary_high_candle_idx in df_after_low.index:
            df_after_low_filtered = df_after_low[df_after_low.index != secondary_high_candle_idx]
        else:
            df_after_low_filtered = df_after_low
        
        if len(df_after_low_filtered) >= 2:  # Need at least 2 bars after low
            # Find if there was any significant bounce after the low
            max_after_low = df_after_low_filtered['High'].max()
            bounce_pct = (max_after_low - low_price) / low_price
            
            if bounce_pct >= SECONDARY_PIVOT_MIN_PULLBACK_PCT:
                # There was a significant bounce - now look for a pullback (secondary low)
                
                # Find the index of the maximum high after the primary low (excluding secondary high candle)
                max_high_idx = df_after_low_filtered['High'].idxmax()
                max_high_position = df_after_low_filtered.index.get_loc(max_high_idx)
                
                # Look at bars AFTER the bounce high for the secondary low
                if max_high_position < len(df_after_low_filtered) - 1:
                    df_after_max = df_after_low_filtered.iloc[max_high_position + 1:]
                    
                    # Also exclude secondary high candle from this subset
                    if secondary_high_candle_idx is not None and secondary_high_candle_idx in df_after_max.index:
                        df_after_max = df_after_max[df_after_max.index != secondary_high_candle_idx]
                    
                    if not df_after_max.empty:
                        min_low_idx = df_after_max['Low'].idxmin()
                        potential_secondary_low = df_after_max.loc[min_low_idx, 'Low']
                        
                        if (potential_secondary_low > low_price and 
                            (potential_secondary_low - low_price) >= SECONDARY_PIVOT_MIN_DISTANCE):
                            
                            df_after_potential = df_after_max[df_after_max.index > min_low_idx]
                            
                            if not df_after_potential.empty:
                                if df_after_potential['High'].max() > potential_secondary_low:
                                    secondary_low = potential_secondary_low
                                    secondary_low_time = to_ct(min_low_idx.to_pydatetime())
                            else:
                                last_bar = df_after_max.loc[min_low_idx]
                                if last_bar['Close'] > potential_secondary_low * 1.001:
                                    secondary_low = potential_secondary_low
                                    secondary_low_time = to_ct(min_low_idx.to_pydatetime())
        
        return {
            'date': prior_date,
            'high': high_price,
            'high_time': high_time,
            'low': low_price,
            'low_time': low_time,
            'close': close_price,
            'close_time': close_time,
            'open': df_intraday['Open'].iloc[0],
            'range': df_intraday['High'].max() - df_intraday['Low'].min(),
            'range_pct': (df_intraday['High'].max() - df_intraday['Low'].min()) / close_price,
            'power_hour_filtered': power_hour_filtered,
            'secondary_high': secondary_high,
            'secondary_high_time': secondary_high_time,
            'secondary_low': secondary_low,
            'secondary_low_time': secondary_low_time
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
    nearest_cone, _, _ = find_nearest_rail(current_price, cones)
    
    overnight_range = es_data.get('overnight_range', 0) if es_data else 0
    overnight_range_pct = overnight_range / nearest_cone.width if nearest_cone.width > 0 else 0
    overnight_touched = check_overnight_rail_touches(cones, es_data)
    
    position, _ = get_position_in_cone(current_price, nearest_cone.ascending_rail, nearest_cone.descending_rail)
    first_bar_energy = first_bar.get('energy', 'neutral') if first_bar else 'neutral'
    
    cone_width_pct = nearest_cone.width / current_price if current_price > 0 else 0
    prior_range_pct = prior_session.get('range_pct', 0) if prior_session else 0
    
    return RegimeAnalysis(
        overnight_range=overnight_range,
        overnight_range_pct=overnight_range_pct,
        overnight_touched_rails=overnight_touched,
        opening_position=position,
        first_bar_energy=first_bar_energy,
        cone_width_adequate=cone_width_pct >= MIN_CONE_WIDTH_PCT,
        prior_day_range_adequate=prior_range_pct >= MIN_PRIOR_DAY_RANGE_PCT,
        es_spx_offset=es_data.get('offset', 0) if es_data else 0
    )

def calculate_confluence_score(nearest_distance, regime, cones, current_price, is_10am) -> int:
    score = 0
    
    if nearest_distance <= 5: score += 25
    elif nearest_distance <= 10: score += 15
    elif nearest_distance <= 15: score += 8
    
    # Confluence bonus - check both calls and puts zones
    zones_data = find_confluence_zones(cones)
    all_zones = zones_data.get('calls_confluence', []) + zones_data.get('puts_confluence', [])
    for zone in all_zones:
        if abs(current_price - zone['price']) <= 10:
            score += 20
            break
    
    if regime.overnight_touched_rails: score += 15
    if is_10am: score += 15
    
    nearest_cone, _, _ = find_nearest_rail(current_price, cones)
    if nearest_cone and (nearest_cone.width / current_price) > 0.006: score += 10
    if regime.overnight_range_pct < 0.30: score += 10
    if regime.first_bar_energy == 'strong': score += 5
    
    return min(score, 100)

def generate_action_card(cones, regime, current_price, is_10am, overnight_validation=None) -> ActionCard:
    warnings = []
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    confluence_score = calculate_confluence_score(nearest_distance, regime, cones, current_price, is_10am)
    
    # Determine position based on WHICH RAIL is nearest, not position within cone
    # If nearest rail is descending → price is near support → CALLS
    # If nearest rail is ascending → price is near resistance → PUTS
    
    # Check if price is actually close enough to the rail to trade
    # Use a threshold based on cone width
    cone_width = nearest_cone.ascending_rail - nearest_cone.descending_rail
    edge_threshold = cone_width * EDGE_ZONE_PCT  # Within 30% of cone width from rail
    
    if nearest_distance <= edge_threshold:
        if nearest_rail_type == 'descending':
            position = 'lower_edge'  # Near support → CALLS
        else:
            position = 'upper_edge'  # Near resistance → PUTS
    else:
        position = 'dead_zone'  # Too far from any rail
    
    no_trade = False
    
    if regime.overnight_range_pct > OVERNIGHT_RANGE_MAX_PCT:
        warnings.append(f"Overnight range too wide ({regime.overnight_range_pct:.0%})")
        no_trade = True
    if position == 'dead_zone' and nearest_distance > 20:
        warnings.append("Price in dead zone")
        no_trade = True
    if not regime.cone_width_adequate:
        warnings.append("Cone width insufficient")
        no_trade = True
    if not regime.prior_day_range_adequate:
        warnings.append("Prior day range weak")
        no_trade = True
    if regime.overnight_touched_rails:
        warnings.append(f"Overnight touched: {', '.join(regime.overnight_touched_rails)}")
    if regime.first_bar_energy == 'weak':
        warnings.append("Weak first bar energy")
    
    # ========== SMART STRUCTURE VALIDATION ==========
    # Check if we're recommending based on a validated structure
    structure_validated = False
    active_structure_note = ""
    
    if overnight_validation:
        # For CALLS (price near descending rails - support)
        if position == 'lower_edge':
            # Check if this is a High-based cone (descending rail = calls entry)
            if 'High' in nearest_cone.name:
                if nearest_cone.name == 'High²':
                    if overnight_validation.get('high_secondary_validated'):
                        structure_validated = True
                        active_structure_note = "✓ Secondary High² VALIDATED overnight"
                        confluence_score = min(100, confluence_score + 15)  # Boost score
                    elif overnight_validation.get('active_high_structure') == 'both':
                        active_structure_note = "⚠ High² not tested overnight - use caution"
                elif nearest_cone.name == 'High':
                    if overnight_validation.get('high_primary_validated'):
                        structure_validated = True
                        active_structure_note = "✓ Primary High VALIDATED overnight"
                        confluence_score = min(100, confluence_score + 15)
                    elif overnight_validation.get('active_high_structure') == 'both':
                        active_structure_note = "⚠ Primary High not tested overnight - use caution"
        
        # For PUTS (price near ascending rails - resistance)
        elif position == 'upper_edge':
            if 'Low' in nearest_cone.name:
                if nearest_cone.name == 'Low²':
                    if overnight_validation.get('low_secondary_validated'):
                        structure_validated = True
                        active_structure_note = "✓ Secondary Low² VALIDATED overnight"
                        confluence_score = min(100, confluence_score + 15)
                    elif overnight_validation.get('active_low_structure') == 'both':
                        active_structure_note = "⚠ Low² not tested overnight - use caution"
                elif nearest_cone.name == 'Low':
                    if overnight_validation.get('low_primary_validated'):
                        structure_validated = True
                        active_structure_note = "✓ Primary Low VALIDATED overnight"
                        confluence_score = min(100, confluence_score + 15)
                    elif overnight_validation.get('active_low_structure') == 'both':
                        active_structure_note = "⚠ Primary Low not tested overnight - use caution"
            # Also check High cone ascending rails for PUTS
            elif 'High' in nearest_cone.name:
                if overnight_validation.get('high_primary_validated') or overnight_validation.get('high_secondary_validated'):
                    structure_validated = True
                    active_structure_note = "✓ High structure validated - ascending rail resistance"
                    confluence_score = min(100, confluence_score + 10)
    
    if active_structure_note:
        warnings.insert(0, active_structure_note)
    
    contract_exp = None
    
    if no_trade:
        direction, color, position_size = 'NO TRADE', 'red', 'NONE'
        entry_level = target_50 = target_75 = target_100 = stop_level = current_price
    elif position == 'dead_zone':
        direction, color, position_size = 'WAIT', 'yellow', 'NONE'
        entry_level = target_50 = target_75 = target_100 = stop_level = current_price
        warnings.append(f"CALLS activate at {nearest_cone.descending_rail:.2f}")
        warnings.append(f"PUTS activate at {nearest_cone.ascending_rail:.2f}")
    elif position == 'lower_edge':
        direction = 'CALLS'
        # Boost confidence if structure was validated
        if structure_validated:
            color = 'green' if confluence_score >= 65 else 'yellow'  # Lower threshold for validated
            position_size = 'FULL' if confluence_score >= 65 else 'REDUCED'
        else:
            color = 'green' if confluence_score >= 75 else 'yellow'
            position_size = 'FULL' if confluence_score >= 75 else 'REDUCED'
        entry_level = nearest_cone.descending_rail
        target_100 = nearest_cone.ascending_rail
        cone_height = target_100 - entry_level
        target_50 = entry_level + (cone_height * 0.50)
        target_75 = entry_level + (cone_height * 0.75)
        stop_level = entry_level - 2
        contract_exp = calculate_contract_expectation('CALLS', entry_level, target_100, nearest_cone.name, 'descending')
    else:
        direction = 'PUTS'
        if structure_validated:
            color = 'green' if confluence_score >= 65 else 'yellow'
            position_size = 'FULL' if confluence_score >= 65 else 'REDUCED'
        else:
            color = 'green' if confluence_score >= 75 else 'yellow'
            position_size = 'FULL' if confluence_score >= 75 else 'REDUCED'
        entry_level = nearest_cone.ascending_rail
        target_100 = nearest_cone.descending_rail
        cone_height = entry_level - target_100
        target_50 = entry_level - (cone_height * 0.50)
        target_75 = entry_level - (cone_height * 0.75)
        stop_level = entry_level + 2
        contract_exp = calculate_contract_expectation('PUTS', entry_level, target_100, nearest_cone.name, 'ascending')
    
    if contract_exp and contract_exp.contract_profit_50 / 100 < MIN_CONTRACT_MOVE:
        warnings.append(f"Contract move below ${MIN_CONTRACT_MOVE:.0f} min")
        if color == 'green':
            color, position_size = 'yellow', 'REDUCED'
    
    return ActionCard(
        direction=direction, active_cone=nearest_cone.name, active_rail=nearest_rail_type,
        entry_level=entry_level, target_50=target_50, target_75=target_75, target_100=target_100,
        stop_level=stop_level, contract_expectation=contract_exp, position_size=position_size,
        confluence_score=confluence_score, warnings=warnings, color=color
    )

# ============================================================================
# PREMIUM UI
# ============================================================================

def inject_premium_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    
    .stApp {
        background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%);
    }
    
    /* HEADER */
    .prophet-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%);
        padding: 2.5rem 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        border: 1px solid rgba(255,255,255,0.1);
        position: relative;
        overflow: hidden;
    }
    .prophet-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #f59e0b, #eab308, #f59e0b);
    }
    .prophet-title {
        font-size: 2.75rem;
        font-weight: 800;
        background: linear-gradient(135deg, #ffffff 0%, #fbbf24 50%, #f59e0b 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        letter-spacing: -0.03em;
    }
    .prophet-tagline {
        font-size: 1.1rem;
        color: #94a3b8;
        margin-top: 0.5rem;
        font-weight: 400;
        letter-spacing: 0.05em;
    }
    
    /* CARDS */
    .premium-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
        border: 1px solid #e2e8f0;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    .premium-card:hover {
        box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 10px 10px -5px rgba(0,0,0,0.04);
        transform: translateY(-2px);
    }
    .card-header {
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #64748b;
        margin-bottom: 0.75rem;
    }
    .card-value {
        font-size: 2rem;
        font-weight: 700;
        color: #0f172a;
    }
    .card-value-sm {
        font-size: 1.25rem;
        font-weight: 600;
        color: #0f172a;
    }
    
    /* ACTION CARDS */
    .action-card {
        border-radius: 20px;
        padding: 2rem;
        text-align: center;
        box-shadow: 0 25px 50px -12px rgba(0,0,0,0.15);
        margin: 1rem 0;
        position: relative;
        overflow: hidden;
    }
    .action-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 4px;
    }
    .action-green {
        background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
        border: 2px solid #22c55e;
    }
    .action-green::before { background: #22c55e; }
    .action-yellow {
        background: linear-gradient(135deg, #fef9c3 0%, #fef08a 100%);
        border: 2px solid #eab308;
    }
    .action-yellow::before { background: #eab308; }
    .action-red {
        background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
        border: 2px solid #ef4444;
    }
    .action-red::before { background: #ef4444; }
    
    .direction-label {
        font-size: 2.5rem;
        font-weight: 800;
        letter-spacing: -0.02em;
    }
    .direction-green { color: #15803d; }
    .direction-yellow { color: #a16207; }
    .direction-red { color: #dc2626; }
    
    /* DECISION TIME CARDS */
    .decision-card {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 16px;
        padding: 1.5rem;
        color: white;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.2);
        border: 1px solid #475569;
    }
    .decision-time {
        font-size: 1.5rem;
        font-weight: 700;
        color: #fbbf24;
        margin-bottom: 1rem;
    }
    .decision-label {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #94a3b8;
        margin-bottom: 0.25rem;
    }
    .decision-value {
        font-size: 1.1rem;
        font-weight: 600;
        color: #f8fafc;
    }
    .decision-puts { color: #f87171; }
    .decision-calls { color: #4ade80; }
    
    /* CONTRACT BOX */
    .contract-card {
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        border: 2px solid #3b82f6;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 10px 15px -3px rgba(59,130,246,0.2);
    }
    .contract-header {
        font-size: 1rem;
        font-weight: 700;
        color: #1e40af;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* SCORE RING */
    .score-container {
        text-align: center;
        padding: 1rem;
    }
    .score-ring {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto;
        position: relative;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.2);
    }
    .score-high { background: linear-gradient(135deg, #22c55e, #16a34a); }
    .score-medium { background: linear-gradient(135deg, #eab308, #ca8a04); }
    .score-low { background: linear-gradient(135deg, #ef4444, #dc2626); }
    .score-value {
        font-size: 2.5rem;
        font-weight: 800;
        color: white;
    }
    .score-label {
        font-size: 0.75rem;
        color: #64748b;
        margin-top: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    
    /* TABLE STYLING */
    .highlight-row {
        background: linear-gradient(90deg, #fef3c7 0%, #fde68a 100%) !important;
        font-weight: 600 !important;
    }
    
    /* CHECKLIST */
    .check-item {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.5rem 0;
        border-bottom: 1px solid #e2e8f0;
    }
    .check-pass { color: #22c55e; }
    .check-fail { color: #ef4444; }
    .check-warn { color: #eab308; }
    
    /* WARNING BADGES */
    .warning-badge {
        background: #fef3c7;
        border: 1px solid #f59e0b;
        color: #92400e;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-size: 0.85rem;
        margin: 0.25rem 0;
    }
    .info-badge {
        background: #dbeafe;
        border: 1px solid #3b82f6;
        color: #1e40af;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-size: 0.85rem;
        margin: 0.25rem 0;
    }
    
    /* PROXIMITY METER */
    .proximity-bar {
        height: 8px;
        border-radius: 4px;
        background: #e2e8f0;
        overflow: hidden;
        margin-top: 0.5rem;
    }
    .proximity-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s ease;
    }
    .proximity-close { background: linear-gradient(90deg, #22c55e, #4ade80); }
    .proximity-medium { background: linear-gradient(90deg, #eab308, #facc15); }
    .proximity-far { background: linear-gradient(90deg, #ef4444, #f87171); }
    
    /* LIVE CLOCK */
    .live-clock {
        background: linear-gradient(135deg, #0f172a, #1e293b);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        color: white;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.2);
    }
    .clock-time {
        font-size: 2rem;
        font-weight: 700;
        font-family: 'SF Mono', monospace;
        color: #fbbf24;
    }
    .clock-label {
        font-size: 0.7rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    
    /* SIDEBAR */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] .stMarkdown h4,
    section[data-testid="stSidebar"] .stCaption,
    section[data-testid="stSidebar"] .stMetric label,
    section[data-testid="stSidebar"] [data-testid="stMetricValue"],
    section[data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        color: #f8fafc !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stNumberInput label,
    section[data-testid="stSidebar"] .stTextInput label,
    section[data-testid="stSidebar"] .stDateInput label,
    section[data-testid="stSidebar"] .stCheckbox label {
        color: #94a3b8 !important;
    }
    /* Fix input fields to have dark text on light background */
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] .stDateInput input,
    section[data-testid="stSidebar"] .stNumberInput input,
    section[data-testid="stSidebar"] .stTextInput input {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
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

def render_checklist(regime: RegimeAnalysis, action: ActionCard):
    checks = [
        ("Overnight Range", regime.overnight_range_pct <= 0.40, f"{regime.overnight_range_pct:.0%} of cone"),
        ("Cone Width", regime.cone_width_adequate, "Adequate" if regime.cone_width_adequate else "Too narrow"),
        ("Prior Day Range", regime.prior_day_range_adequate, "Adequate" if regime.prior_day_range_adequate else "Weak"),
        ("First Bar Energy", regime.first_bar_energy != 'weak', regime.first_bar_energy.title()),
        ("Price Position", regime.opening_position != 'dead_zone', regime.opening_position.replace('_', ' ').title()),
    ]
    
    st.markdown("#### ✅ Trade Checklist")
    
    for label, passed, detail in checks:
        icon = "✓" if passed else "✗"
        color_class = "check-pass" if passed else "check-fail"
        st.markdown(f"""
        <div class="check-item">
            <span class="{color_class}" style="font-size: 1.25rem; font-weight: bold;">{icon}</span>
            <span style="flex: 1; font-weight: 500;">{label}</span>
            <span style="color: #64748b; font-size: 0.85rem;">{detail}</span>
        </div>
        """, unsafe_allow_html=True)

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
            
            # Apply price offset to auto-detected values
            auto_high = prior_session['high'] - price_offset
            auto_low = prior_session['low'] - price_offset
            auto_close = prior_session['close'] - price_offset
            
            use_manual = st.checkbox("✏️ Manual Price Override", value=False, help="Enable to enter your TradingView prices directly")
            
            if use_manual:
                st.info("Enter your TradingView prices below")
                high_price = st.number_input("High", value=float(auto_high), format="%.2f")
                high_time_str = st.text_input("High Time (CT)", value=prior_session['high_time'].strftime('%H:%M'))
                low_price = st.number_input("Low", value=float(auto_low), format="%.2f")
                low_time_str = st.text_input("Low Time (CT)", value=prior_session['low_time'].strftime('%H:%M'))
                close_price = st.number_input("Close", value=float(auto_close), format="%.2f")
            else:
                # Show corrected values (with offset applied)
                high_price = auto_high
                low_price = auto_low
                close_price = auto_close
                high_time_str = prior_session['high_time'].strftime('%H:%M')
                low_time_str = prior_session['low_time'].strftime('%H:%M')
                
                st.metric("High", f"{high_price:.2f}", f"@ {high_time_str} CT")
                st.metric("Low", f"{low_price:.2f}", f"@ {low_time_str} CT")
                st.metric("Close", f"{close_price:.2f}")
                
                if price_offset != 0:
                    st.caption(f"📉 Offset applied: -{price_offset:.2f} pts")
            
            # Secondary Pivots Display
            if prior_session.get('secondary_high') is not None or prior_session.get('secondary_low') is not None:
                st.markdown("---")
                st.markdown("### 📍 Secondary Pivots")
            
            if prior_session.get('secondary_high') is not None:
                st.success("🔄 Secondary High Detected!")
                secondary_high_price = prior_session['secondary_high'] - price_offset
                secondary_high_time = prior_session['secondary_high_time']
                st.metric("2nd High (High²)", f"{secondary_high_price:.2f}", f"@ {secondary_high_time.strftime('%H:%M')} CT")
            
            if prior_session.get('secondary_low') is not None:
                st.success("🔄 Secondary Low Detected!")
                secondary_low_price = prior_session['secondary_low'] - price_offset
                secondary_low_time = prior_session['secondary_low_time']
                st.metric("2nd Low (Low²)", f"{secondary_low_price:.2f}", f"@ {secondary_low_time.strftime('%H:%M')} CT")
            
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
                st.write(f"**Primary High:** {high_price:.2f} @ {high_time_str} CT")
                st.write(f"**Primary Low:** {low_price:.2f} @ {low_time_str} CT")
                if secondary_high_price is not None:
                    st.write(f"**Secondary High²:** {secondary_high_price:.2f} @ {secondary_high_time.strftime('%H:%M')} CT")
                else:
                    st.write("**Secondary High²:** Not detected")
                if secondary_low_price is not None:
                    st.write(f"**Secondary Low²:** {secondary_low_price:.2f} @ {secondary_low_time.strftime('%H:%M')} CT")
                else:
                    st.write("**Secondary Low²:** Not detected")
                if use_premarket_high and premarket_high_price:
                    st.write(f"**Pre-Market High:** {premarket_high_price:.2f} @ {premarket_high_time.strftime('%H:%M')} CT")
                if use_premarket_low and premarket_low_price:
                    st.write(f"**Pre-Market Low:** {premarket_low_price:.2f} @ {premarket_low_time.strftime('%H:%M')} CT")
            
            try:
                h, m = map(int, high_time_str.split(':'))
                high_time = CT_TZ.localize(datetime.combine(prior_session['date'], time(h, m)))
            except:
                high_time = prior_session['high_time']
            
            try:
                h, m = map(int, low_time_str.split(':'))
                low_time = CT_TZ.localize(datetime.combine(prior_session['date'], time(h, m)))
            except:
                low_time = prior_session['low_time']
            
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
    
    # ===== MAIN LAYOUT =====
    
    # Row 1: Live Price + Score + Action
    col1, col2, col3 = st.columns([1.5, 1, 1.5])
    
    with col1:
        st.markdown(f"""
        <div class="premium-card">
            <div class="card-header">SPX Live Price</div>
            <div class="card-value">{current_price:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Live clock
        ct_time = get_ct_now()
        st.markdown(f"""
        <div class="live-clock">
            <div class="clock-label">Central Time</div>
            <div class="clock-time">{ct_time.strftime('%H:%M:%S')}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        render_score_ring(action.confluence_score)
    
    with col3:
        render_action_card(action)
        if action.direction in ['CALLS', 'PUTS']:
            st.markdown(f"""
            <div style="text-align: center; margin-top: -0.5rem;">
                <span style="font-size: 0.9rem; color: #64748b;">Structure: </span>
                <span style="font-weight: 600;">{action.active_cone} Cone</span>
                <span style="font-size: 0.9rem; color: #64748b;"> | Size: </span>
                <span style="font-weight: 600;">{action.position_size}</span>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Row 2: Decision Windows
    st.markdown("### 🎯 Decision Window Entry Levels")
    col_830, col_1000 = st.columns(2)
    
    with col_830:
        render_decision_card("⏰ 8:30 AM CT — Market Open", cones_830)
    
    with col_1000:
        render_decision_card("⏰ 10:00 AM CT — Key Decision", cones_1000)
    
    # Confluence Zones - Show BOTH Calls and Puts levels
    st.markdown("#### 🔥 High Probability Entry Levels")
    
    col_calls, col_puts = st.columns(2)
    
    with col_calls:
        st.markdown("##### 🟢 CALLS (Support Levels)")
        
        # Show confluence zones first (highest probability)
        if confluence_zones.get('calls_confluence'):
            for zone in confluence_zones['calls_confluence']:
                strength_stars = "⭐" * zone['strength']
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%); 
                            border: 2px solid #22c55e; border-radius: 10px; padding: 0.75rem; margin: 0.5rem 0;">
                    <div style="font-weight: 700; color: #15803d; font-size: 1.1rem;">
                        {zone['price']:.2f} {strength_stars}
                    </div>
                    <div style="font-size: 0.8rem; color: #166534;">
                        Confluence: {' + '.join(zone['rails'])}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # Show all individual levels
        if confluence_zones.get('all_calls_levels'):
            with st.expander("📋 All Support Rails"):
                for level in confluence_zones['all_calls_levels']:
                    st.write(f"**{level['price']:.2f}** — {level['name']}")
    
    with col_puts:
        st.markdown("##### 🔴 PUTS (Resistance Levels)")
        
        # Show confluence zones first (highest probability)
        if confluence_zones.get('puts_confluence'):
            for zone in confluence_zones['puts_confluence']:
                strength_stars = "⭐" * zone['strength']
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); 
                            border: 2px solid #ef4444; border-radius: 10px; padding: 0.75rem; margin: 0.5rem 0;">
                    <div style="font-weight: 700; color: #dc2626; font-size: 1.1rem;">
                        {zone['price']:.2f} {strength_stars}
                    </div>
                    <div style="font-size: 0.8rem; color: #991b1b;">
                        Confluence: {' + '.join(zone['rails'])}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # Show all individual levels
        if confluence_zones.get('all_puts_levels'):
            with st.expander("📋 All Resistance Rails"):
                for level in confluence_zones['all_puts_levels']:
                    st.write(f"**{level['price']:.2f}** — {level['name']}")
    
    # Show message if no confluence found
    if not confluence_zones.get('calls_confluence') and not confluence_zones.get('puts_confluence'):
        st.info("No rail confluences detected at current time. Check individual rails in the expanders above.")
    
    # ========== OVERNIGHT VALIDATION DISPLAY ==========
    if overnight_validation and overnight_validation.get('validation_notes'):
        st.markdown("#### 🌙 Overnight Structure Validation")
        
        col_val1, col_val2 = st.columns(2)
        
        with col_val1:
            # High structure status
            active_high = overnight_validation.get('active_high_structure', 'primary')
            if active_high == 'secondary':
                st.success("🎯 **HIGH: Secondary (High²) is ACTIVE**")
                st.caption("Overnight touched and respected the secondary high descending rail")
            elif active_high == 'primary':
                if overnight_validation.get('high_secondary_broken'):
                    st.warning("⚠️ **HIGH: Primary only** (Secondary was broken)")
                else:
                    st.info("📍 **HIGH: Primary is active**")
            elif active_high == 'both':
                st.info("📍 **HIGH: Both structures are candidates**")
                st.caption("Neither was tested overnight - watch both levels")
        
        with col_val2:
            # Low structure status
            active_low = overnight_validation.get('active_low_structure', 'primary')
            if active_low == 'secondary':
                st.success("🎯 **LOW: Secondary (Low²) is ACTIVE**")
                st.caption("Overnight touched and respected the secondary low ascending rail")
            elif active_low == 'primary':
                if overnight_validation.get('low_secondary_broken'):
                    st.warning("⚠️ **LOW: Primary only** (Secondary was broken)")
                else:
                    st.info("📍 **LOW: Primary is active**")
            elif active_low == 'both':
                st.info("📍 **LOW: Both structures are candidates**")
                st.caption("Neither was tested overnight - watch both levels")
        
        # Show detailed validation notes in expander
        with st.expander("📋 Detailed Overnight Analysis"):
            for note in overnight_validation['validation_notes']:
                if note.startswith("✓"):
                    st.success(note)
                elif note.startswith("✗"):
                    st.error(note)
                elif note.startswith("→"):
                    st.info(note)
                else:
                    st.write(note)
    
    st.markdown("---")
    
    # Row 3: Trade Setup + Contract Expectations
    if action.direction in ['CALLS', 'PUTS']:
        col_setup, col_contract = st.columns(2)
        
        with col_setup:
            st.markdown("""
            <div class="premium-card">
                <div class="card-header">📋 Trade Setup</div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"""
            | Level | Price |
            |-------|-------|
            | **Entry** | {action.entry_level:.2f} |
            | **Target 50%** (60% out) | {action.target_50:.2f} |
            | **Target 75%** (20% out) | {action.target_75:.2f} |
            | **Target 100%** (20% out) | {action.target_100:.2f} |
            | **Stop Loss** | {action.stop_level:.2f} |
            """)
        
        with col_contract:
            if action.contract_expectation:
                ce = action.contract_expectation
                st.markdown(f"""
                <div class="contract-card">
                    <div class="contract-header">💰 Contract Expectations (ATM 0DTE)</div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                        <div>
                            <div style="font-size: 0.75rem; color: #64748b;">Underlying Move (50%)</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #1e40af;">{ce.expected_underlying_move_50:.2f} pts</div>
                        </div>
                        <div>
                            <div style="font-size: 0.75rem; color: #64748b;">Underlying Move (100%)</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #1e40af;">{ce.expected_underlying_move_100:.2f} pts</div>
                        </div>
                    </div>
                    <hr style="margin: 1rem 0; border-color: #93c5fd;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; text-align: center;">
                        <div>
                            <div style="font-size: 0.7rem; color: #64748b;">Profit @ 50%</div>
                            <div style="font-size: 1.5rem; font-weight: 800; color: #15803d;">${ce.contract_profit_50:.0f}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.7rem; color: #64748b;">Profit @ 75%</div>
                            <div style="font-size: 1.5rem; font-weight: 800; color: #15803d;">${ce.contract_profit_75:.0f}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.7rem; color: #64748b;">Profit @ 100%</div>
                            <div style="font-size: 1.5rem; font-weight: 800; color: #15803d;">${ce.contract_profit_100:.0f}</div>
                        </div>
                    </div>
                    <hr style="margin: 1rem 0; border-color: #93c5fd;">
                    <div style="text-align: center;">
                        <span style="font-size: 0.85rem; color: #64748b;">Risk/Reward (to 50%): </span>
                        <span style="font-size: 1.1rem; font-weight: 700; color: #1e40af;">{ce.risk_reward_50:.1f}:1</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Contract calculator
                st.markdown("#### 🧮 P&L Calculator")
                num_contracts = st.number_input("Number of Contracts", min_value=1, max_value=100, value=10)
                st.markdown(f"""
                | Target | Profit ({num_contracts} contracts) |
                |--------|-------------------------------------|
                | **50%** | **${ce.contract_profit_50 * num_contracts:,.0f}** |
                | **75%** | **${ce.contract_profit_75 * num_contracts:,.0f}** |
                | **100%** | **${ce.contract_profit_100 * num_contracts:,.0f}** |
                """)
    
    st.markdown("---")
    
    # Row 4: Proximity + Checklist
    col_prox, col_check = st.columns(2)
    
    with col_prox:
        render_proximity_meters(cones_1000, current_price)
    
    with col_check:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        render_checklist(regime, action)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Warnings
        if action.warnings:
            st.markdown("#### ⚠️ Alerts")
            for w in action.warnings:
                if "activate" in w.lower():
                    st.markdown(f'<div class="info-badge">{w}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="warning-badge">{w}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Row 5: Full Projection Table
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
