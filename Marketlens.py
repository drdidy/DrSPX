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

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

SLOPE_ASCENDING = 0.53  # Points per 30-minute block (ascending)
SLOPE_DESCENDING = 0.43  # Points per 30-minute block (descending)
CONTRACT_FACTOR = 0.33  # ATM contract move factor

# Trading hours (CT)
MAINTENANCE_START_CT = time(16, 0)
MAINTENANCE_END_CT = time(17, 0)

# No-trade filter thresholds
OVERNIGHT_RANGE_MAX_PCT = 0.40
DEAD_ZONE_PCT = 0.40
MIN_CONE_WIDTH_PCT = 0.0045
MIN_PRIOR_DAY_RANGE_PCT = 0.009
MIN_CONTRACT_MOVE = 8.0
RAIL_TOUCH_THRESHOLD = 1.0
EDGE_ZONE_PCT = 0.30

# Time blocks for projection table (CT)
TIME_BLOCKS = [
    time(8, 30), time(9, 0), time(9, 30), time(10, 0), time(10, 30),
    time(11, 0), time(11, 30), time(12, 0), time(12, 30), time(13, 0),
    time(13, 30), time(14, 0), time(14, 30)
]

HIGHLIGHT_TIMES = [time(8, 30), time(10, 0)]  # Decision windows

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
    direction: str  # 'CALLS' or 'PUTS'
    entry_price: float
    entry_rail: str
    target_50_underlying: float
    target_75_underlying: float
    target_100_underlying: float
    stop_underlying: float
    expected_underlying_move_50: float
    expected_underlying_move_100: float
    contract_entry_estimate: float
    contract_target_50: float
    contract_target_75: float
    contract_target_100: float
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
    if start_time >= end_time:
        return 0
    
    blocks = 0
    current = start_time
    
    while current < end_time:
        current_ct_time = current.astimezone(CT_TZ).time()
        
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
        
        df_intraday = spx.history(start=start_date, end=end_date, interval='30m')
        
        if df_intraday.empty:
            df_daily = spx.history(start=start_date, end=end_date, interval='1d')
            if df_daily.empty:
                return None
            
            row = df_daily.iloc[0]
            close_time = datetime.combine(prior_date, time(15, 0))
            close_time = CT_TZ.localize(close_time)
            
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
                'range_pct': (row['High'] - row['Low']) / row['Close']
            }
        
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
            return {'offset': 0, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0}
        
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
        
        overnight_start = datetime.combine(prior_date, time(17, 0))
        overnight_start = CT_TZ.localize(overnight_start)
        overnight_end = datetime.combine(session_date, time(8, 30))
        overnight_end = CT_TZ.localize(overnight_end)
        
        df_es_tz = df_es.copy()
        df_es_tz.index = df_es_tz.index.tz_convert(CT_TZ)
        
        overnight_mask = (df_es_tz.index >= overnight_start) & (df_es_tz.index <= overnight_end)
        df_overnight = df_es_tz[overnight_mask]
        
        if df_overnight.empty:
            return {'offset': offset, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0}
        
        overnight_high = df_overnight['High'].max()
        overnight_low = df_overnight['Low'].min()
        overnight_range = overnight_high - overnight_low
        
        overnight_high_spx = overnight_high - offset
        overnight_low_spx = overnight_low - offset
        
        return {
            'offset': offset,
            'overnight_high': overnight_high,
            'overnight_low': overnight_low,
            'overnight_high_spx': overnight_high_spx,
            'overnight_low_spx': overnight_low_spx,
            'overnight_range': overnight_range
        }
        
    except Exception as e:
        return {'offset': 0, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0}

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
        
    except Exception as e:
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

def build_projection_table(pivots: List[Pivot], session_date: datetime) -> pd.DataFrame:
    """Build full projection table from 8:30 to 14:30 CT"""
    
    data = []
    
    for t in TIME_BLOCKS:
        eval_time = CT_TZ.localize(datetime.combine(session_date, t))
        cones = build_cones_at_time(pivots, eval_time)
        
        row = {'Time (CT)': t.strftime('%H:%M')}
        
        for cone in cones:
            row[f'{cone.name} Asc'] = cone.ascending_rail
            row[f'{cone.name} Desc'] = cone.descending_rail
        
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
    
    overnight_high_spx = es_data['overnight_high_spx']
    overnight_low_spx = es_data['overnight_low_spx']
    
    for cone in cones:
        if abs(overnight_high_spx - cone.ascending_rail) <= RAIL_TOUCH_THRESHOLD:
            touched.append(f"{cone.name} Asc")
        
        if abs(overnight_low_spx - cone.descending_rail) <= RAIL_TOUCH_THRESHOLD:
            touched.append(f"{cone.name} Desc")
    
    return touched

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
    """Calculate expected contract moves and profits"""
    
    cone_height = abs(opposite_rail - entry_rail)
    
    if direction == 'CALLS':
        target_50 = entry_rail + (cone_height * 0.50)
        target_75 = entry_rail + (cone_height * 0.75)
        target_100 = opposite_rail
        stop = entry_rail - 2  # 2 points below entry
    else:  # PUTS
        target_50 = entry_rail - (cone_height * 0.50)
        target_75 = entry_rail - (cone_height * 0.75)
        target_100 = opposite_rail
        stop = entry_rail + 2  # 2 points above entry
    
    # Underlying moves
    move_50 = abs(target_50 - entry_rail)
    move_75 = abs(target_75 - entry_rail)
    move_100 = abs(target_100 - entry_rail)
    
    # Contract estimates (ATM 0DTE approximation)
    # Entry contract price estimate based on typical ATM 0DTE pricing
    # This is a rough estimate - actual prices depend on IV and time
    contract_entry = move_50 * 0.8  # Rough ATM estimate
    
    # Contract moves using the 0.33 factor
    contract_move_50 = move_50 * CONTRACT_FACTOR
    contract_move_75 = move_75 * CONTRACT_FACTOR
    contract_move_100 = move_100 * CONTRACT_FACTOR
    
    # Contract targets
    contract_target_50 = contract_entry + contract_move_50
    contract_target_75 = contract_entry + contract_move_75
    contract_target_100 = contract_entry + contract_move_100
    
    # Profits per contract
    profit_50 = contract_move_50 * 100  # Per contract (100 multiplier)
    profit_75 = contract_move_75 * 100
    profit_100 = contract_move_100 * 100
    
    # Risk/reward at 50% target
    risk = 2 * CONTRACT_FACTOR * 100  # 2 point stop * factor * 100
    rr_50 = profit_50 / risk if risk > 0 else 0
    
    return ContractExpectation(
        direction=direction,
        entry_price=entry_rail,
        entry_rail=f"{cone_name} {rail_type.title()}",
        target_50_underlying=target_50,
        target_75_underlying=target_75,
        target_100_underlying=target_100,
        stop_underlying=stop,
        expected_underlying_move_50=move_50,
        expected_underlying_move_100=move_100,
        contract_entry_estimate=contract_entry,
        contract_target_50=contract_target_50,
        contract_target_75=contract_target_75,
        contract_target_100=contract_target_100,
        contract_profit_50=profit_50,
        contract_profit_75=profit_75,
        contract_profit_100=profit_100,
        risk_reward_50=rr_50
    )

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
    
    nearest_cone, _, _ = find_nearest_rail(current_price, cones)
    
    overnight_range = es_data.get('overnight_range', 0) if es_data else 0
    overnight_range_pct = overnight_range / nearest_cone.width if nearest_cone.width > 0 else 0
    
    overnight_touched = check_overnight_rail_touches(cones, es_data)
    
    position, _ = get_position_in_cone(
        current_price,
        nearest_cone.ascending_rail,
        nearest_cone.descending_rail
    )
    
    first_bar_energy = first_bar.get('energy', 'neutral') if first_bar else 'neutral'
    
    spx_price = current_price
    cone_width_pct = nearest_cone.width / spx_price if spx_price > 0 else 0
    cone_width_adequate = cone_width_pct >= MIN_CONE_WIDTH_PCT
    
    prior_range_pct = prior_session.get('range_pct', 0) if prior_session else 0
    prior_day_range_adequate = prior_range_pct >= MIN_PRIOR_DAY_RANGE_PCT
    
    return RegimeAnalysis(
        overnight_range=overnight_range,
        overnight_range_pct=overnight_range_pct,
        overnight_touched_rails=overnight_touched,
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
    score = 0
    
    if nearest_distance <= 5:
        score += 25
    elif nearest_distance <= 10:
        score += 15
    elif nearest_distance <= 15:
        score += 8
    
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
    
    if len(regime.overnight_touched_rails) > 0:
        score += 15
    
    if is_10am_window:
        score += 15
    
    nearest_cone, _, _ = find_nearest_rail(current_price, cones)
    if nearest_cone and (nearest_cone.width / current_price) > 0.006:
        score += 10
    
    if regime.overnight_range_pct < 0.30:
        score += 10
    
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
    
    warnings = []
    
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    
    confluence_score = calculate_confluence_score(
        nearest_distance, regime, cones, current_price, is_10am_window
    )
    
    position, _ = get_position_in_cone(
        current_price,
        nearest_cone.ascending_rail,
        nearest_cone.descending_rail
    )
    
    no_trade = False
    
    if regime.overnight_range_pct > OVERNIGHT_RANGE_MAX_PCT:
        warnings.append(f"⚠️ Overnight range too wide ({regime.overnight_range_pct:.0%} of cone)")
        no_trade = True
    
    if position == 'dead_zone' and nearest_distance > 20:
        warnings.append("⚠️ Price in dead zone - no clear edge")
        no_trade = True
    
    if not regime.cone_width_adequate:
        warnings.append("⚠️ Cone width too narrow")
        no_trade = True
    
    if not regime.prior_day_range_adequate:
        warnings.append("⚠️ Prior day range weak")
        no_trade = True
    
    if len(regime.overnight_touched_rails) > 0:
        warnings.append(f"⚠️ Overnight touched: {', '.join(regime.overnight_touched_rails)}")
    
    if regime.first_bar_energy == 'weak':
        warnings.append("⚠️ First bar shows weak energy")
    
    # Determine direction and setup
    contract_exp = None
    
    if no_trade:
        direction = 'NO TRADE'
        color = 'red'
        position_size = 'NONE'
        entry_level = current_price
        target_50 = current_price
        target_75 = current_price
        target_100 = current_price
        stop_level = current_price
    elif position == 'dead_zone':
        direction = 'WAIT'
        color = 'yellow'
        position_size = 'NONE'
        entry_level = current_price
        target_50 = current_price
        target_75 = current_price
        target_100 = current_price
        stop_level = current_price
        warnings.append(f"📍 Call setup activates at {nearest_cone.descending_rail:.2f} or below")
        warnings.append(f"📍 Put setup activates at {nearest_cone.ascending_rail:.2f} or above")
    elif position == 'lower_edge':
        direction = 'CALLS'
        color = 'green' if confluence_score >= 75 else 'yellow'
        position_size = 'FULL' if confluence_score >= 75 else 'REDUCED'
        entry_level = nearest_cone.descending_rail
        target_100 = nearest_cone.ascending_rail
        cone_height = target_100 - entry_level
        target_50 = entry_level + (cone_height * 0.50)
        target_75 = entry_level + (cone_height * 0.75)
        stop_level = entry_level - 2
        
        contract_exp = calculate_contract_expectation(
            'CALLS', entry_level, target_100, nearest_cone.name, 'descending'
        )
    else:  # upper_edge
        direction = 'PUTS'
        color = 'green' if confluence_score >= 75 else 'yellow'
        position_size = 'FULL' if confluence_score >= 75 else 'REDUCED'
        entry_level = nearest_cone.ascending_rail
        target_100 = nearest_cone.descending_rail
        cone_height = entry_level - target_100
        target_50 = entry_level - (cone_height * 0.50)
        target_75 = entry_level - (cone_height * 0.75)
        stop_level = entry_level + 2
        
        contract_exp = calculate_contract_expectation(
            'PUTS', entry_level, target_100, nearest_cone.name, 'ascending'
        )
    
    # Check minimum contract move
    if contract_exp and contract_exp.contract_profit_50 / 100 < MIN_CONTRACT_MOVE:
        warnings.append(f"⚠️ Expected contract move below ${MIN_CONTRACT_MOVE:.0f} minimum")
        if color == 'green':
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
        contract_expectation=contract_exp,
        position_size=position_size,
        confluence_score=confluence_score,
        warnings=warnings,
        color=color
    )

# ============================================================================
# STYLING FUNCTIONS
# ============================================================================

def highlight_decision_times(row):
    """Highlight 8:30 and 10:00 rows"""
    if row['Time (CT)'] in ['08:30', '10:00']:
        return ['background-color: #fff3cd; font-weight: bold'] * len(row)
    return [''] * len(row)

def format_price(val):
    """Format price values"""
    if isinstance(val, (int, float)):
        return f"{val:.2f}"
    return val

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
    
    # Light theme CSS
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #1a5f7a 0%, #086972 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
    }
    .tagline {
        font-size: 1rem;
        margin-top: 0.25rem;
        opacity: 0.9;
    }
    .decision-box {
        background: #f8f9fa;
        border: 2px solid #dee2e6;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .decision-box-highlight {
        background: #fff3cd;
        border: 2px solid #ffc107;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .action-card-green {
        background: #d4edda;
        border: 3px solid #28a745;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .action-card-yellow {
        background: #fff3cd;
        border: 3px solid #ffc107;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .action-card-red {
        background: #f8d7da;
        border: 3px solid #dc3545;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .contract-box {
        background: #e7f3ff;
        border: 2px solid #0066cc;
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .entry-level {
        font-size: 1.5rem;
        font-weight: bold;
        color: #0066cc;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1 class="main-title">📈 SPX Prophet</h1>
        <p class="tagline">Where Structure Becomes Foresight</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("📅 Session Configuration")
        
        session_date = st.date_input(
            "Trading Session Date",
            value=datetime.now().date(),
            help="Select the trading session to analyze"
        )
        session_date = datetime.combine(session_date, time(0, 0))
        
        st.divider()
        
        # Fetch data
        prior_session = fetch_prior_session_data(session_date)
        es_data = fetch_es_overnight_data(session_date)
        current_price = fetch_current_spx() or (prior_session['close'] if prior_session else 6000)
        first_bar = fetch_first_30min_bar(session_date)
        
        st.header("📍 Pivots (Prior Session)")
        
        if prior_session:
            st.info(f"Source: {prior_session['date'].strftime('%Y-%m-%d')}")
            
            use_manual = st.checkbox("Override pivots manually", value=False)
            
            if use_manual:
                st.warning("Manual pivots active")
            
            high_price = st.number_input(
                "High",
                value=float(prior_session['high']),
                step=0.01,
                format="%.2f",
                disabled=not use_manual
            )
            
            high_time_str = st.text_input(
                "High Time (CT)",
                value=prior_session['high_time'].strftime('%H:%M'),
                disabled=not use_manual
            )
            
            low_price = st.number_input(
                "Low",
                value=float(prior_session['low']),
                step=0.01,
                format="%.2f",
                disabled=not use_manual
            )
            
            low_time_str = st.text_input(
                "Low Time (CT)",
                value=prior_session['low_time'].strftime('%H:%M'),
                disabled=not use_manual
            )
            
            close_price = st.number_input(
                "Close",
                value=float(prior_session['close']),
                step=0.01,
                format="%.2f",
                disabled=not use_manual
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
            st.error("Could not fetch data. Enter manually.")
            
            high_price = st.number_input("High", value=6050.0, step=0.01, format="%.2f")
            low_price = st.number_input("Low", value=6000.0, step=0.01, format="%.2f")
            close_price = st.number_input("Close", value=6025.0, step=0.01, format="%.2f")
            
            high_time_str = st.text_input("High Time (CT)", value="10:30")
            low_time_str = st.text_input("Low Time (CT)", value="13:45")
            
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
        
        st.divider()
        
        st.header("⚙️ Slope Parameters")
        st.metric("Ascending", f"+{SLOPE_ASCENDING} pts/30min")
        st.metric("Descending", f"-{SLOPE_DESCENDING} pts/30min")
        
        if es_data and es_data.get('offset'):
            st.divider()
            st.header("🔄 ES-SPX Offset")
            st.metric("Offset", f"{es_data['offset']:.2f} pts")
    
    # Build pivots
    pivots = [
        Pivot(price=high_price, time=high_time, name='High'),
        Pivot(price=close_price, time=close_time, name='Close'),
        Pivot(price=low_price, time=low_time, name='Low')
    ]
    
    # Determine evaluation time
    ct_now = get_ct_now()
    if session_date.date() == ct_now.date():
        eval_time = ct_now
        is_10am_window = ct_now.time() >= time(10, 0)
    else:
        eval_time = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        is_10am_window = True
    
    # Build cones for current time
    cones = build_cones_at_time(pivots, eval_time)
    
    # Build cones for decision windows
    time_830 = CT_TZ.localize(datetime.combine(session_date, time(8, 30)))
    time_1000 = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
    cones_830 = build_cones_at_time(pivots, time_830)
    cones_1000 = build_cones_at_time(pivots, time_1000)
    
    # Analyze regime
    regime = analyze_regime(cones, es_data, prior_session, first_bar, current_price)
    
    # Generate action card
    action_card = generate_action_card(cones, regime, current_price, is_10am_window)
    
    # ========== MAIN CONTENT ==========
    
    # Current Price
    col_price, col_score = st.columns([2, 1])
    with col_price:
        st.metric("📊 SPX Current Price", f"{current_price:,.2f}")
    with col_score:
        score_color = "🟢" if action_card.confluence_score >= 75 else ("🟡" if action_card.confluence_score >= 50 else "🔴")
        st.metric(f"{score_color} Confluence Score", f"{action_card.confluence_score}/100")
    
    st.divider()
    
    # ========== DECISION WINDOWS ==========
    st.header("🎯 Decision Window Levels")
    
    col_830, col_1000 = st.columns(2)
    
    with col_830:
        st.markdown("### ⏰ 8:30 AM CT (Open)")
        
        for cone in cones_830:
            st.markdown(f"""
            **{cone.name} Cone:**
            - Ascending (Puts): **{cone.ascending_rail:.2f}**
            - Descending (Calls): **{cone.descending_rail:.2f}**
            - Width: {cone.width:.2f} pts
            """)
    
    with col_1000:
        st.markdown("### ⏰ 10:00 AM CT (Key Decision)")
        
        for cone in cones_1000:
            st.markdown(f"""
            **{cone.name} Cone:**
            - Ascending (Puts): **{cone.ascending_rail:.2f}**
            - Descending (Calls): **{cone.descending_rail:.2f}**
            - Width: {cone.width:.2f} pts
            """)
    
    st.divider()
    
    # ========== ACTION CARD ==========
    st.header("🚀 Action Card")
    
    col_action, col_contract = st.columns([1, 1])
    
    with col_action:
        card_class = f"action-card-{action_card.color}"
        emoji = '🟢' if action_card.direction == 'CALLS' else ('🔴' if action_card.direction == 'PUTS' else ('🟡' if action_card.direction == 'WAIT' else '⛔'))
        
        st.markdown(f"""
        <div class="{card_class}">
            <h2 style="text-align: center; margin: 0;">{emoji} {action_card.direction}</h2>
        </div>
        """, unsafe_allow_html=True)
        
        if action_card.direction in ['CALLS', 'PUTS']:
            st.markdown(f"**Active Structure:** {action_card.active_cone} Cone - {action_card.active_rail.title()} Rail")
            st.markdown(f"**Position Size:** {action_card.position_size}")
            
            st.markdown("---")
            
            st.markdown("#### 📍 Underlying Levels")
            st.markdown(f"**Entry:** {action_card.entry_level:.2f}")
            st.markdown(f"**Target 50% (60% out):** {action_card.target_50:.2f}")
            st.markdown(f"**Target 75% (20% out):** {action_card.target_75:.2f}")
            st.markdown(f"**Target 100% (20% out):** {action_card.target_100:.2f}")
            st.markdown(f"**Stop:** {action_card.stop_level:.2f}")
        
        # Warnings
        if action_card.warnings:
            st.markdown("---")
            st.markdown("#### ⚠️ Alerts")
            for warning in action_card.warnings:
                if warning.startswith("📍"):
                    st.info(warning)
                else:
                    st.warning(warning)
    
    with col_contract:
        if action_card.contract_expectation:
            ce = action_card.contract_expectation
            
            st.markdown("""
            <div class="contract-box">
                <h3 style="margin-top: 0;">💰 Contract Expectations (ATM 0DTE)</h3>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown(f"**Direction:** {ce.direction}")
            st.markdown(f"**Entry Rail:** {ce.entry_rail}")
            
            st.markdown("---")
            
            st.markdown("#### 📈 Expected Underlying Moves")
            st.markdown(f"- To 50% target: **{ce.expected_underlying_move_50:.2f} pts**")
            st.markdown(f"- To 100% target: **{ce.expected_underlying_move_100:.2f} pts**")
            
            st.markdown("---")
            
            st.markdown("#### 💵 Expected Contract Profits (per contract)")
            
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.metric("@ 50% Target", f"${ce.contract_profit_50:.0f}")
            with col_t2:
                st.metric("@ 100% Target", f"${ce.contract_profit_100:.0f}")
            
            st.markdown("---")
            
            st.markdown(f"**Risk/Reward (to 50%):** {ce.risk_reward_50:.1f}:1")
            
            # Flag if below minimum
            if ce.contract_profit_50 / 100 < MIN_CONTRACT_MOVE:
                st.error(f"⚠️ Expected move ${ce.contract_profit_50/100:.2f} is below ${MIN_CONTRACT_MOVE:.0f} minimum")
            else:
                st.success(f"✅ Expected move ${ce.contract_profit_50/100:.2f} meets minimum threshold")
        else:
            st.info("Contract expectations will appear when a trade setup is active.")
    
    st.divider()
    
    # ========== FULL PROJECTION TABLE ==========
    st.header("📋 Full Cone Projection Table (8:30 AM - 2:30 PM CT)")
    
    # Build the table
    df_projections = build_projection_table(pivots, session_date)
    
    # Format the dataframe
    df_display = df_projections.copy()
    for col in df_display.columns:
        if col != 'Time (CT)':
            df_display[col] = df_display[col].apply(lambda x: f"{x:.2f}")
    
    # Apply highlighting
    styled_df = df_display.style.apply(highlight_decision_times, axis=1)
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.caption("💡 **Yellow highlighted rows** are key decision windows (8:30 AM and 10:00 AM CT)")
    
    st.divider()
    
    # ========== REGIME ANALYSIS ==========
    st.header("🔍 Regime Analysis")
    
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    
    with col_r1:
        status = "✅" if regime.overnight_range_pct < 0.30 else ("⚠️" if regime.overnight_range_pct < 0.40 else "❌")
        st.metric("Overnight Range", f"{regime.overnight_range:.1f} pts", f"{regime.overnight_range_pct:.0%} of cone {status}")
    
    with col_r2:
        pos_emoji = "🟢" if regime.opening_position in ['lower_edge', 'upper_edge'] else "🟡"
        st.metric("Price Position", f"{pos_emoji} {regime.opening_position.replace('_', ' ').title()}")
    
    with col_r3:
        energy_emoji = "✅" if regime.first_bar_energy == 'strong' else ("⚠️" if regime.first_bar_energy == 'neutral' else "❌")
        st.metric("First Bar Energy", f"{energy_emoji} {regime.first_bar_energy.title()}")
    
    with col_r4:
        width_emoji = "✅" if regime.cone_width_adequate else "❌"
        range_emoji = "✅" if regime.prior_day_range_adequate else "❌"
        st.metric("Quality Checks", f"Width {width_emoji} | Range {range_emoji}")
    
    # Key insight
    st.info("💡 **Key Insight:** Your edge is highest when the 10:00 CT reaction aligns with your primary cone structure.")

if __name__ == "__main__":
    main()
