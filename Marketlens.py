"""
SPX Prophet - Where Structure Becomes Foresight
A professional SPX trading assistant using structural cones, timing rules, and flow-regime detection.
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta, time
import pytz
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

SLOPE_PER_30MIN = 0.45  # Points per 30-minute block
CONTRACT_FACTOR = 0.33  # ATM contract move factor

# Trading hours (CT)
RTH_OPEN_CT = time(8, 30)
RTH_CLOSE_CT = time(15, 0)
MAINTENANCE_START_CT = time(16, 0)
MAINTENANCE_END_CT = time(17, 0)
OVERNIGHT_START_CT = time(17, 0)
OVERNIGHT_END_CT = time(8, 30)

# Decision windows
DECISION_WINDOW_1 = time(8, 30)
DECISION_WINDOW_2 = time(10, 0)

# No-trade filter thresholds
OVERNIGHT_RANGE_MAX_PCT = 0.40  # 40% of cone width
DEAD_ZONE_PCT = 0.40  # Middle 40% is dead zone
MIN_CONE_WIDTH_PCT = 0.0045  # 0.45% of SPX
MIN_PRIOR_DAY_RANGE_PCT = 0.009  # 0.90% of SPX
MIN_CONTRACT_MOVE = 8.0  # Minimum $8 expected move
RAIL_TOUCH_THRESHOLD = 1.0  # Within 1 point = touch
EDGE_ZONE_PCT = 0.30  # 30% from each rail is edge zone

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
    ascending_rail: float  # At current evaluation time
    descending_rail: float  # At current evaluation time
    width: float
    blocks_from_pivot: int

@dataclass
class RegimeAnalysis:
    overnight_range: float
    overnight_range_pct: float
    overnight_touched_rails: List[str]
    opening_print: float
    opening_position: str  # 'upper_edge', 'lower_edge', 'dead_zone'
    first_bar_energy: str  # 'strong', 'weak', 'neutral'
    cone_width_adequate: bool
    prior_day_range_adequate: bool
    es_spx_offset: float

@dataclass
class ActionCard:
    direction: str  # 'CALLS', 'PUTS', 'NO TRADE', 'WAIT'
    active_cone: str
    active_rail: str
    entry_level: float
    target_50: float
    target_75: float
    target_100: float
    stop_level: float
    expected_contract_move: float
    position_size: str  # 'FULL', 'REDUCED', 'NONE'
    confluence_score: int
    warnings: List[str]
    color: str  # 'green', 'yellow', 'red'

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_ct_now() -> datetime:
    """Get current time in Central Time."""
    return datetime.now(CT_TZ)

def to_ct(dt: datetime) -> datetime:
    """Convert datetime to Central Time."""
    if dt.tzinfo is None:
        dt = ET_TZ.localize(dt)
    return dt.astimezone(CT_TZ)

def count_30min_blocks(start_time: datetime, end_time: datetime) -> int:
    """
    Count 30-minute blocks between two times, skipping the 16:00-17:00 CT maintenance hour.
    """
    if start_time >= end_time:
        return 0
    
    blocks = 0
    current = start_time
    
    while current < end_time:
        current_ct_time = current.astimezone(CT_TZ).time()
        
        # Skip maintenance hour (16:00-17:00 CT)
        if MAINTENANCE_START_CT <= current_ct_time < MAINTENANCE_END_CT:
            current = current + timedelta(minutes=30)
            continue
        
        blocks += 1
        current = current + timedelta(minutes=30)
    
    return blocks

def project_rail(pivot_price: float, blocks: int, direction: str) -> float:
    """Project a rail price from pivot."""
    if direction == 'ascending':
        return pivot_price + (blocks * SLOPE_PER_30MIN)
    else:
        return pivot_price - (blocks * SLOPE_PER_30MIN)

def get_position_in_cone(price: float, ascending_rail: float, descending_rail: float) -> Tuple[str, float]:
    """
    Determine position within a cone.
    Returns: (zone, distance_to_nearest_rail)
    """
    cone_width = ascending_rail - descending_rail
    if cone_width <= 0:
        return 'invalid', 0
    
    # Calculate position as percentage from descending rail
    position_pct = (price - descending_rail) / cone_width
    
    if position_pct <= EDGE_ZONE_PCT:
        return 'lower_edge', abs(price - descending_rail)
    elif position_pct >= (1 - EDGE_ZONE_PCT):
        return 'upper_edge', abs(price - ascending_rail)
    else:
        return 'dead_zone', min(abs(price - ascending_rail), abs(price - descending_rail))

# ============================================================================
# DATA FETCHING
# ============================================================================

@st.cache_data(ttl=300)
def fetch_prior_session_data(session_date: datetime) -> Optional[Dict]:
    """Fetch prior RTH session OHLC data for SPX."""
    try:
        # Get the prior trading day
        prior_date = session_date - timedelta(days=1)
        
        # Skip weekends
        while prior_date.weekday() >= 5:
            prior_date = prior_date - timedelta(days=1)
        
        # Fetch SPX data
        spx = yf.Ticker("^GSPC")
        
        # Get intraday data to find high/low times
        start_date = prior_date.strftime('%Y-%m-%d')
        end_date = (prior_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Try to get 30-minute data for time detection
        df_intraday = spx.history(start=start_date, end=end_date, interval='30m')
        
        if df_intraday.empty:
            # Fallback to daily data
            df_daily = spx.history(start=start_date, end=end_date, interval='1d')
            if df_daily.empty:
                return None
            
            row = df_daily.iloc[0]
            close_time = datetime.combine(prior_date, time(15, 0))
            close_time = CT_TZ.localize(close_time)
            
            return {
                'date': prior_date,
                'high': row['High'],
                'high_time': close_time,  # Approximate
                'low': row['Low'],
                'low_time': close_time,  # Approximate
                'close': row['Close'],
                'close_time': close_time,
                'open': row['Open'],
                'range': row['High'] - row['Low'],
                'range_pct': (row['High'] - row['Low']) / row['Close']
            }
        
        # Find high and low times from intraday data
        high_idx = df_intraday['High'].idxmax()
        low_idx = df_intraday['Low'].idxmin()
        
        high_time = to_ct(high_idx.to_pydatetime())
        low_time = to_ct(low_idx.to_pydatetime())
        close_time = datetime.combine(prior_date, time(15, 0))
        close_time = CT_TZ.localize(close_time)
        
        return {
            'date': prior_date,
            'high': df_intraday['High'].max(),
            'high_time': high_time,
            'low': df_intraday['Low'].min(),
            'low_time': low_time,
            'close': df_intraday['Close'].iloc[-1],
            'close_time': close_time,
            'open': df_intraday['Open'].iloc[0],
            'range': df_intraday['High'].max() - df_intraday['Low'].min(),
            'range_pct': (df_intraday['High'].max() - df_intraday['Low'].min()) / df_intraday['Close'].iloc[-1]
        }
        
    except Exception as e:
        st.error(f"Error fetching SPX data: {e}")
        return None

@st.cache_data(ttl=300)
def fetch_es_overnight_data(session_date: datetime) -> Optional[Dict]:
    """Fetch ES overnight data and calculate SPX offset."""
    try:
        prior_date = session_date - timedelta(days=1)
        while prior_date.weekday() >= 5:
            prior_date = prior_date - timedelta(days=1)
        
        # Fetch ES futures data
        es = yf.Ticker("ES=F")
        spx = yf.Ticker("^GSPC")
        
        # Get data for offset calculation (14:30 CT of prior day)
        start_date = prior_date.strftime('%Y-%m-%d')
        end_date = (session_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        df_es = es.history(start=start_date, end=end_date, interval='5m')
        df_spx = spx.history(start=start_date, end=end_date, interval='30m')
        
        if df_es.empty:
            return {'offset': 0, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0}
        
        # Calculate ES-SPX offset at 14:30 CT
        offset = 0
        if not df_spx.empty:
            # Find closest data point to 14:30 CT
            target_time = datetime.combine(prior_date, time(14, 30))
            target_time = CT_TZ.localize(target_time)
            
            try:
                # Get SPX close for the day
                spx_close = df_spx['Close'].iloc[-1]
                
                # Get ES at similar time
                es_at_time = df_es[df_es.index.tz_convert(CT_TZ).time <= time(14, 30)]
                if not es_at_time.empty:
                    es_price = es_at_time['Close'].iloc[-1]
                    offset = es_price - spx_close
            except:
                offset = 0
        
        # Get overnight session data (17:00 CT prior day to 08:30 CT session day)
        overnight_start = datetime.combine(prior_date, time(17, 0))
        overnight_start = CT_TZ.localize(overnight_start)
        overnight_end = datetime.combine(session_date, time(8, 30))
        overnight_end = CT_TZ.localize(overnight_end)
        
        # Filter for overnight hours
        df_es_tz = df_es.copy()
        df_es_tz.index = df_es_tz.index.tz_convert(CT_TZ)
        
        overnight_mask = (df_es_tz.index >= overnight_start) & (df_es_tz.index <= overnight_end)
        df_overnight = df_es_tz[overnight_mask]
        
        if df_overnight.empty:
            return {'offset': offset, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0}
        
        overnight_high = df_overnight['High'].max()
        overnight_low = df_overnight['Low'].min()
        overnight_range = overnight_high - overnight_low
        
        # Convert to SPX equivalent
        overnight_high_spx = overnight_high - offset
        overnight_low_spx = overnight_low - offset
        
        return {
            'offset': offset,
            'overnight_high': overnight_high,
            'overnight_low': overnight_low,
            'overnight_high_spx': overnight_high_spx,
            'overnight_low_spx': overnight_low_spx,
            'overnight_range': overnight_range,
            'df_overnight': df_overnight
        }
        
    except Exception as e:
        st.error(f"Error fetching ES overnight data: {e}")
        return {'offset': 0, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0}

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

@st.cache_data(ttl=300)
def fetch_first_30min_bar(session_date: datetime) -> Optional[Dict]:
    """Fetch the first 30-minute bar of the session."""
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
        
        # Determine bar energy
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
        
    except Exception as e:
        return None

# ============================================================================
# STRUCTURAL ENGINE
# ============================================================================

def build_cones(pivots: List[Pivot], eval_time: datetime) -> List[Cone]:
    """Build all three cones for the given evaluation time."""
    cones = []
    
    for pivot in pivots:
        blocks = count_30min_blocks(pivot.time, eval_time)
        
        ascending_rail = project_rail(pivot.price, blocks, 'ascending')
        descending_rail = project_rail(pivot.price, blocks, 'descending')
        width = ascending_rail - descending_rail
        
        cone = Cone(
            name=pivot.name,
            pivot=pivot,
            ascending_rail=ascending_rail,
            descending_rail=descending_rail,
            width=width,
            blocks_from_pivot=blocks
        )
        cones.append(cone)
    
    return cones

def find_nearest_rail(price: float, cones: List[Cone]) -> Tuple[Cone, str, float]:
    """Find the nearest rail across all cones."""
    nearest_cone = None
    nearest_rail_type = None
    nearest_distance = float('inf')
    
    for cone in cones:
        # Check ascending rail
        dist_asc = abs(price - cone.ascending_rail)
        if dist_asc < nearest_distance:
            nearest_distance = dist_asc
            nearest_cone = cone
            nearest_rail_type = 'ascending'
        
        # Check descending rail
        dist_desc = abs(price - cone.descending_rail)
        if dist_desc < nearest_distance:
            nearest_distance = dist_desc
            nearest_cone = cone
            nearest_rail_type = 'descending'
    
    return nearest_cone, nearest_rail_type, nearest_distance

def check_overnight_rail_touches(cones: List[Cone], es_data: Dict, eval_time: datetime) -> List[str]:
    """Check if any rails were touched overnight (SPX equivalent)."""
    touched = []
    
    if not es_data or es_data.get('overnight_high_spx') is None:
        return touched
    
    overnight_high_spx = es_data['overnight_high_spx']
    overnight_low_spx = es_data['overnight_low_spx']
    
    for cone in cones:
        # Check ascending rail
        if abs(overnight_high_spx - cone.ascending_rail) <= RAIL_TOUCH_THRESHOLD:
            touched.append(f"{cone.name} Ascending")
        
        # Check descending rail
        if abs(overnight_low_spx - cone.descending_rail) <= RAIL_TOUCH_THRESHOLD:
            touched.append(f"{cone.name} Descending")
    
    return touched

# ============================================================================
# REGIME DETECTION
# ============================================================================

def analyze_regime(
    cones: List[Cone],
    es_data: Dict,
    prior_session: Dict,
    first_bar: Optional[Dict],
    current_price: float
) -> RegimeAnalysis:
    """Analyze the current market regime."""
    
    # Find the most relevant cone (nearest to current price)
    nearest_cone, _, _ = find_nearest_rail(current_price, cones)
    
    # Overnight range analysis
    overnight_range = es_data.get('overnight_range', 0) if es_data else 0
    overnight_range_pct = overnight_range / nearest_cone.width if nearest_cone.width > 0 else 0
    
    # Overnight rail touches
    overnight_touched = check_overnight_rail_touches(cones, es_data, get_ct_now())
    
    # Opening position analysis
    opening_print = prior_session.get('open', current_price) if prior_session else current_price
    position, _ = get_position_in_cone(
        current_price,
        nearest_cone.ascending_rail,
        nearest_cone.descending_rail
    )
    
    # First bar energy
    first_bar_energy = first_bar.get('energy', 'neutral') if first_bar else 'neutral'
    
    # Cone width adequacy
    spx_price = current_price
    cone_width_pct = nearest_cone.width / spx_price if spx_price > 0 else 0
    cone_width_adequate = cone_width_pct >= MIN_CONE_WIDTH_PCT
    
    # Prior day range adequacy
    prior_range_pct = prior_session.get('range_pct', 0) if prior_session else 0
    prior_day_range_adequate = prior_range_pct >= MIN_PRIOR_DAY_RANGE_PCT
    
    return RegimeAnalysis(
        overnight_range=overnight_range,
        overnight_range_pct=overnight_range_pct,
        overnight_touched_rails=overnight_touched,
        opening_print=opening_print,
        opening_position=position,
        first_bar_energy=first_bar_energy,
        cone_width_adequate=cone_width_adequate,
        prior_day_range_adequate=prior_day_range_adequate,
        es_spx_offset=es_data.get('offset', 0) if es_data else 0
    )

# ============================================================================
# CONFLUENCE SCORING
# ============================================================================

def calculate_confluence_score(
    nearest_distance: float,
    regime: RegimeAnalysis,
    cones: List[Cone],
    current_price: float,
    is_10am_window: bool
) -> int:
    """Calculate confluence score (0-100)."""
    score = 0
    
    # Price within 5 points of a rail (+25)
    if nearest_distance <= 5:
        score += 25
    elif nearest_distance <= 10:
        score += 15
    elif nearest_distance <= 15:
        score += 8
    
    # Two cones have rails within 5 points of each other at current price (+20)
    rail_prices = []
    for cone in cones:
        rail_prices.append(cone.ascending_rail)
        rail_prices.append(cone.descending_rail)
    
    rail_prices.sort()
    for i in range(len(rail_prices) - 1):
        if abs(rail_prices[i] - rail_prices[i+1]) <= 5:
            if abs(current_price - rail_prices[i]) <= 15:
                score += 20
                break
    
    # Overnight touched this rail (+15)
    if len(regime.overnight_touched_rails) > 0:
        score += 15
    
    # 10:00 CT timing (+15)
    if is_10am_window:
        score += 15
    
    # Cone width > 0.60% (+10)
    nearest_cone, _, _ = find_nearest_rail(current_price, cones)
    if nearest_cone and (nearest_cone.width / current_price) > 0.006:
        score += 10
    
    # Overnight range < 30% of cone (+10)
    if regime.overnight_range_pct < 0.30:
        score += 10
    
    # Strong first bar (+5)
    if regime.first_bar_energy == 'strong':
        score += 5
    
    return min(score, 100)

# ============================================================================
# ACTION CARD GENERATION
# ============================================================================

def generate_action_card(
    cones: List[Cone],
    regime: RegimeAnalysis,
    current_price: float,
    is_10am_window: bool
) -> ActionCard:
    """Generate the daily action card."""
    
    warnings = []
    
    # Find nearest rail
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    
    # Calculate confluence score
    confluence_score = calculate_confluence_score(
        nearest_distance, regime, cones, current_price, is_10am_window
    )
    
    # Determine position in cone
    position, _ = get_position_in_cone(
        current_price,
        nearest_cone.ascending_rail,
        nearest_cone.descending_rail
    )
    
    # Check no-trade filters
    no_trade = False
    
    if regime.overnight_range_pct > OVERNIGHT_RANGE_MAX_PCT:
        warnings.append(f"⚠️ Overnight range too wide ({regime.overnight_range_pct:.0%} of cone)")
        no_trade = True
    
    if position == 'dead_zone' and nearest_distance > 20:
        warnings.append("⚠️ Price in dead zone - no clear edge")
        no_trade = True
    
    if not regime.cone_width_adequate:
        warnings.append("⚠️ Cone width too narrow - insufficient profit potential")
        no_trade = True
    
    if not regime.prior_day_range_adequate:
        warnings.append("⚠️ Prior day range weak - unreliable pivots")
        no_trade = True
    
    if len(regime.overnight_touched_rails) > 0:
        warnings.append(f"⚠️ Overnight touched: {', '.join(regime.overnight_touched_rails)}")
    
    if regime.first_bar_energy == 'weak':
        warnings.append("⚠️ First bar shows weak energy")
    
    # Determine direction
    if no_trade:
        direction = 'NO TRADE'
        color = 'red'
        position_size = 'NONE'
    elif position == 'dead_zone':
        direction = 'WAIT'
        color = 'yellow'
        position_size = 'NONE'
        warnings.append(f"📍 Call setup activates at {nearest_cone.descending_rail:.2f} or below")
        warnings.append(f"📍 Put setup activates at {nearest_cone.ascending_rail:.2f} or above")
    elif position == 'lower_edge':
        direction = 'CALLS'
        color = 'green' if confluence_score >= 75 else 'yellow'
        position_size = 'FULL' if confluence_score >= 75 else 'REDUCED'
    else:  # upper_edge
        direction = 'PUTS'
        color = 'green' if confluence_score >= 75 else 'yellow'
        position_size = 'FULL' if confluence_score >= 75 else 'REDUCED'
    
    # Calculate entry, targets, and stop
    if direction == 'CALLS':
        entry_level = nearest_cone.descending_rail
        target_100 = nearest_cone.ascending_rail
        cone_height = target_100 - entry_level
        target_50 = entry_level + (cone_height * 0.50)
        target_75 = entry_level + (cone_height * 0.75)
        stop_level = entry_level - 2  # 2 points below entry rail
    elif direction == 'PUTS':
        entry_level = nearest_cone.ascending_rail
        target_100 = nearest_cone.descending_rail
        cone_height = entry_level - target_100
        target_50 = entry_level - (cone_height * 0.50)
        target_75 = entry_level - (cone_height * 0.75)
        stop_level = entry_level + 2  # 2 points above entry rail
    else:
        entry_level = current_price
        target_50 = current_price
        target_75 = current_price
        target_100 = current_price
        stop_level = current_price
    
    # Calculate expected contract move
    expected_move = abs(target_50 - entry_level)
    expected_contract_move = expected_move * CONTRACT_FACTOR
    
    if expected_contract_move < MIN_CONTRACT_MOVE and direction in ['CALLS', 'PUTS']:
        warnings.append(f"⚠️ Expected contract move (${expected_contract_move:.2f}) below minimum")
        if not no_trade:
            color = 'yellow'
            position_size = 'REDUCED'
    
    return ActionCard(
        direction=direction,
        active_cone=nearest_cone.name,
        active_rail=nearest_rail_type,
        entry_level=entry_level,
        target_50=target_50,
        target_75=target_75,
        target_100=target_100,
        stop_level=stop_level,
        expected_contract_move=expected_contract_move,
        position_size=position_size,
        confluence_score=confluence_score,
        warnings=warnings,
        color=color
    )

# ============================================================================
# VISUALIZATION
# ============================================================================

def create_cone_chart(cones: List[Cone], current_price: float, session_date: datetime) -> go.Figure:
    """Create an interactive cone visualization."""
    
    fig = go.Figure()
    
    colors = {
        'High': {'line': '#ef4444', 'fill': 'rgba(239, 68, 68, 0.1)'},
        'Close': {'line': '#3b82f6', 'fill': 'rgba(59, 130, 246, 0.1)'},
        'Low': {'line': '#22c55e', 'fill': 'rgba(34, 197, 94, 0.1)'}
    }
    
    # Generate time points from 08:30 to 15:00 CT
    start_time = datetime.combine(session_date, time(8, 30))
    start_time = CT_TZ.localize(start_time)
    
    time_points = []
    current = start_time
    end_time = datetime.combine(session_date, time(15, 0))
    end_time = CT_TZ.localize(end_time)
    
    while current <= end_time:
        time_points.append(current)
        current = current + timedelta(minutes=30)
    
    for cone in cones:
        ascending_values = []
        descending_values = []
        
        for t in time_points:
            blocks = count_30min_blocks(cone.pivot.time, t)
            asc = project_rail(cone.pivot.price, blocks, 'ascending')
            desc = project_rail(cone.pivot.price, blocks, 'descending')
            ascending_values.append(asc)
            descending_values.append(desc)
        
        time_labels = [t.strftime('%H:%M') for t in time_points]
        
        # Ascending rail
        fig.add_trace(go.Scatter(
            x=time_labels,
            y=ascending_values,
            mode='lines',
            name=f'{cone.name} Ascending',
            line=dict(color=colors[cone.name]['line'], width=2),
            hovertemplate='%{y:.2f}<extra></extra>'
        ))
        
        # Descending rail
        fig.add_trace(go.Scatter(
            x=time_labels,
            y=descending_values,
            mode='lines',
            name=f'{cone.name} Descending',
            line=dict(color=colors[cone.name]['line'], width=2, dash='dash'),
            hovertemplate='%{y:.2f}<extra></extra>'
        ))
    
    # Add current price line
    fig.add_hline(
        y=current_price,
        line=dict(color='white', width=2, dash='dot'),
        annotation_text=f'Current: {current_price:.2f}',
        annotation_position='right'
    )
    
    # Add decision window markers
    fig.add_vline(x='08:30', line=dict(color='#fbbf24', width=1, dash='dash'))
    fig.add_vline(x='10:00', line=dict(color='#fbbf24', width=2))
    
    fig.update_layout(
        title='Cone Projections',
        xaxis_title='Time (CT)',
        yaxis_title='SPX Price',
        template='plotly_dark',
        height=500,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        hovermode='x unified'
    )
    
    return fig

# ============================================================================
# STREAMLIT UI
# ============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
        padding: 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        border: 1px solid #334155;
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
        letter-spacing: -0.02em;
    }
    
    .tagline {
        font-size: 1.1rem;
        color: #94a3b8;
        margin-top: 0.5rem;
        font-style: italic;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #334155;
        margin-bottom: 1rem;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 1.75rem;
        font-weight: 600;
        color: #f8fafc;
    }
    
    .action-card-green {
        background: linear-gradient(135deg, #065f46 0%, #064e3b 100%);
        border: 2px solid #10b981;
        padding: 2rem;
        border-radius: 16px;
        margin: 1rem 0;
    }
    
    .action-card-yellow {
        background: linear-gradient(135deg, #713f12 0%, #451a03 100%);
        border: 2px solid #f59e0b;
        padding: 2rem;
        border-radius: 16px;
        margin: 1rem 0;
    }
    
    .action-card-red {
        background: linear-gradient(135deg, #7f1d1d 0%, #450a0a 100%);
        border: 2px solid #ef4444;
        padding: 2rem;
        border-radius: 16px;
        margin: 1rem 0;
    }
    
    .direction-text {
        font-size: 2rem;
        font-weight: 700;
        color: #ffffff;
        text-align: center;
        margin-bottom: 1rem;
    }
    
    .cone-table {
        background: #1e293b;
        border-radius: 8px;
        overflow: hidden;
    }
    
    .warning-badge {
        background: rgba(251, 191, 36, 0.2);
        border: 1px solid #fbbf24;
        color: #fbbf24;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        margin: 0.25rem 0;
        font-size: 0.9rem;
    }
    
    .info-badge {
        background: rgba(59, 130, 246, 0.2);
        border: 1px solid #3b82f6;
        color: #3b82f6;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        margin: 0.25rem 0;
        font-size: 0.9rem;
    }
    
    .stSelectbox > div > div {
        background-color: #1e293b;
    }
    
    .stNumberInput > div > div > input {
        background-color: #1e293b;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 1.5rem;
    }
    
    .confluence-score {
        font-size: 3rem;
        font-weight: 700;
        text-align: center;
    }
    
    .score-high { color: #10b981; }
    .score-medium { color: #f59e0b; }
    .score-low { color: #ef4444; }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1 class="main-title">📈 SPX Prophet</h1>
        <p class="tagline">Where Structure Becomes Foresight</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar - Session & Pivots
    with st.sidebar:
        st.markdown("### 📅 Session Configuration")
        
        session_date = st.date_input(
            "Trading Session Date",
            value=datetime.now().date(),
            help="Select the trading session you want to analyze"
        )
        session_date = datetime.combine(session_date, time(0, 0))
        
        st.markdown("---")
        
        # Fetch data
        prior_session = fetch_prior_session_data(session_date)
        es_data = fetch_es_overnight_data(session_date)
        current_price = fetch_current_spx() or (prior_session['close'] if prior_session else 6000)
        first_bar = fetch_first_30min_bar(session_date)
        
        st.markdown("### 📍 Pivots (Prior Session)")
        
        if prior_session:
            st.info(f"Data from: {prior_session['date'].strftime('%Y-%m-%d')}")
            
            # Manual override toggle
            use_manual = st.checkbox("Use manual pivot overrides", value=False)
            
            if use_manual:
                st.warning("⚠️ Manual pivots in use")
            
            col1, col2 = st.columns(2)
            
            with col1:
                high_price = st.number_input(
                    "High Price",
                    value=float(prior_session['high']),
                    step=0.01,
                    format="%.2f",
                    disabled=not use_manual
                )
                
                low_price = st.number_input(
                    "Low Price",
                    value=float(prior_session['low']),
                    step=0.01,
                    format="%.2f",
                    disabled=not use_manual
                )
                
                close_price = st.number_input(
                    "Close Price",
                    value=float(prior_session['close']),
                    step=0.01,
                    format="%.2f",
                    disabled=not use_manual
                )
            
            with col2:
                high_time_str = st.text_input(
                    "High Time (HH:MM CT)",
                    value=prior_session['high_time'].strftime('%H:%M'),
                    disabled=not use_manual
                )
                
                low_time_str = st.text_input(
                    "Low Time (HH:MM CT)",
                    value=prior_session['low_time'].strftime('%H:%M'),
                    disabled=not use_manual
                )
                
                close_time_str = "15:00"  # Always market close
                st.text_input(
                    "Close Time (CT)",
                    value=close_time_str,
                    disabled=True
                )
            
            # Parse times
            try:
                high_hour, high_min = map(int, high_time_str.split(':'))
                high_time = datetime.combine(prior_session['date'], time(high_hour, high_min))
                high_time = CT_TZ.localize(high_time)
            except:
                high_time = prior_session['high_time']
            
            try:
                low_hour, low_min = map(int, low_time_str.split(':'))
                low_time = datetime.combine(prior_session['date'], time(low_hour, low_min))
                low_time = CT_TZ.localize(low_time)
            except:
                low_time = prior_session['low_time']
            
            close_time = datetime.combine(prior_session['date'], time(15, 0))
            close_time = CT_TZ.localize(close_time)
            
        else:
            st.error("Could not fetch prior session data. Please enter manually.")
            use_manual = True
            
            high_price = st.number_input("High Price", value=6050.0, step=0.01, format="%.2f")
            low_price = st.number_input("Low Price", value=6000.0, step=0.01, format="%.2f")
            close_price = st.number_input("Close Price", value=6025.0, step=0.01, format="%.2f")
            
            high_time_str = st.text_input("High Time (HH:MM CT)", value="10:30")
            low_time_str = st.text_input("Low Time (HH:MM CT)", value="13:45")
            
            prior_date = session_date - timedelta(days=1)
            while prior_date.weekday() >= 5:
                prior_date = prior_date - timedelta(days=1)
            
            try:
                high_hour, high_min = map(int, high_time_str.split(':'))
                high_time = datetime.combine(prior_date, time(high_hour, high_min))
                high_time = CT_TZ.localize(high_time)
            except:
                high_time = CT_TZ.localize(datetime.combine(prior_date, time(10, 30)))
            
            try:
                low_hour, low_min = map(int, low_time_str.split(':'))
                low_time = datetime.combine(prior_date, time(low_hour, low_min))
                low_time = CT_TZ.localize(low_time)
            except:
                low_time = CT_TZ.localize(datetime.combine(prior_date, time(13, 45)))
            
            close_time = CT_TZ.localize(datetime.combine(prior_date, time(15, 0)))
        
        st.markdown("---")
        st.markdown("### ⚙️ Parameters")
        st.text(f"Slope: ±{SLOPE_PER_30MIN} pts/30min")
        st.text(f"Contract Factor: {CONTRACT_FACTOR}")
        
        # ES-SPX Offset display
        if es_data and es_data.get('offset'):
            st.markdown("---")
            st.markdown("### 🔄 ES-SPX Offset")
            st.metric("Offset", f"{es_data['offset']:.2f} pts")
    
    # Build pivots and cones
    pivots = [
        Pivot(price=high_price, time=high_time, name='High'),
        Pivot(price=close_price, time=close_time, name='Close'),
        Pivot(price=low_price, time=low_time, name='Low')
    ]
    
    # Determine evaluation time
    ct_now = get_ct_now()
    if session_date.date() == ct_now.date():
        # Today - use current time
        eval_time = ct_now
        if ct_now.time() >= time(10, 0):
            is_10am_window = True
        else:
            is_10am_window = False
    else:
        # Historical - default to 10:00 CT
        eval_time = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        is_10am_window = True
    
    # Build cones
    cones = build_cones(pivots, eval_time)
    
    # Analyze regime
    regime = analyze_regime(cones, es_data, prior_session, first_bar, current_price)
    
    # Generate action card
    action_card = generate_action_card(cones, regime, current_price, is_10am_window)
    
    # Main content area
    col_main, col_action = st.columns([2, 1])
    
    with col_main:
        # Current price display
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">SPX Current Price</div>
            <div class="metric-value">{current_price:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Cone chart
        st.plotly_chart(
            create_cone_chart(cones, current_price, session_date),
            use_container_width=True
        )
        
        # Cone projections table
        st.markdown("### 📊 Cone Projections at Key Times")
        
        # Calculate values at 08:30 and 10:00 CT
        time_830 = CT_TZ.localize(datetime.combine(session_date, time(8, 30)))
        time_1000 = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        
        cones_830 = build_cones(pivots, time_830)
        cones_1000 = build_cones(pivots, time_1000)
        
        table_data = []
        for i, cone_name in enumerate(['High', 'Close', 'Low']):
            table_data.append({
                'Cone': cone_name,
                '08:30 Ascending': f"{cones_830[i].ascending_rail:.2f}",
                '08:30 Descending': f"{cones_830[i].descending_rail:.2f}",
                '10:00 Ascending': f"{cones_1000[i].ascending_rail:.2f}",
                '10:00 Descending': f"{cones_1000[i].descending_rail:.2f}",
                'Width': f"{cones_1000[i].width:.2f}",
                'Width %': f"{(cones_1000[i].width / current_price * 100):.2f}%"
            })
        
        df_cones = pd.DataFrame(table_data)
        st.dataframe(df_cones, use_container_width=True, hide_index=True)
        
        # Regime analysis
        st.markdown("### 🔍 Regime Analysis")
        
        col_r1, col_r2, col_r3 = st.columns(3)
        
        with col_r1:
            overnight_status = "✅" if regime.overnight_range_pct < 0.30 else ("⚠️" if regime.overnight_range_pct < 0.40 else "❌")
            st.metric(
                "Overnight Range",
                f"{regime.overnight_range:.1f} pts",
                f"{regime.overnight_range_pct:.0%} of cone {overnight_status}"
            )
        
        with col_r2:
            position_emoji = "🟢" if regime.opening_position in ['lower_edge', 'upper_edge'] else "🟡"
            st.metric(
                "Opening Position",
                regime.opening_position.replace('_', ' ').title(),
                position_emoji
            )
        
        with col_r3:
            energy_emoji = "✅" if regime.first_bar_energy == 'strong' else ("⚠️" if regime.first_bar_energy == 'neutral' else "❌")
            st.metric(
                "First Bar Energy",
                regime.first_bar_energy.title(),
                energy_emoji
            )
        
        col_r4, col_r5, col_r6 = st.columns(3)
        
        with col_r4:
            st.metric(
                "Cone Width Adequate",
                "Yes ✅" if regime.cone_width_adequate else "No ❌"
            )
        
        with col_r5:
            st.metric(
                "Prior Day Range",
                "Adequate ✅" if regime.prior_day_range_adequate else "Weak ❌"
            )
        
        with col_r6:
            if regime.overnight_touched_rails:
                st.metric("Overnight Rail Touches", ", ".join(regime.overnight_touched_rails))
            else:
                st.metric("Overnight Rail Touches", "None ✅")
    
    with col_action:
        # Confluence score
        score_class = "score-high" if action_card.confluence_score >= 75 else ("score-medium" if action_card.confluence_score >= 50 else "score-low")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Confluence Score</div>
            <div class="confluence-score {score_class}">{action_card.confluence_score}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Action card
        card_class = f"action-card-{action_card.color}"
        st.markdown(f"""
        <div class="{card_class}">
            <div class="direction-text">
                {'🟢' if action_card.direction == 'CALLS' else ('🔴' if action_card.direction == 'PUTS' else ('🟡' if action_card.direction == 'WAIT' else '⛔'))} {action_card.direction}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Trade details
        if action_card.direction in ['CALLS', 'PUTS']:
            st.markdown("#### 📋 Trade Setup")
            st.markdown(f"**Structure:** {action_card.active_cone} Cone - {action_card.active_rail.title()} Rail")
            st.markdown(f"**Entry Level:** {action_card.entry_level:.2f}")
            
            st.markdown("#### 🎯 Exit Targets")
            st.markdown(f"- **60% @ 50%:** {action_card.target_50:.2f}")
            st.markdown(f"- **20% @ 75%:** {action_card.target_75:.2f}")
            st.markdown(f"- **20% @ 100%:** {action_card.target_100:.2f}")
            
            st.markdown(f"#### 🛑 Stop Loss")
            st.markdown(f"**Close below:** {action_card.stop_level:.2f}")
            
            st.markdown("#### 💰 Expected Contract Move")
            st.metric("ATM 0DTE Move", f"${action_card.expected_contract_move:.2f}")
            
            st.markdown(f"#### 📊 Position Size")
            size_color = "#10b981" if action_card.position_size == "FULL" else "#f59e0b"
            st.markdown(f"<span style='color: {size_color}; font-weight: bold; font-size: 1.25rem;'>{action_card.position_size}</span>", unsafe_allow_html=True)
        
        elif action_card.direction == 'WAIT':
            st.markdown("#### ⏳ Waiting for Setup")
            st.markdown("Price is in the dead zone. Monitor for migration to edge zones.")
        
        # Warnings
        if action_card.warnings:
            st.markdown("#### ⚠️ Alerts")
            for warning in action_card.warnings:
                if warning.startswith("📍"):
                    st.markdown(f'<div class="info-badge">{warning}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="warning-badge">{warning}</div>', unsafe_allow_html=True)
        
        # Key insight
        st.markdown("---")
        st.markdown("#### 💡 Key Insight")
        st.info("Your edge is highest when the 10:00 CT reaction aligns with your primary cone structure.")

if __name__ == "__main__":
    main()