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

SLOPE_ASCENDING = 0.54
SLOPE_DESCENDING = 0.44
CONTRACT_FACTOR = 0.33

MAINTENANCE_START_CT = time(16, 0)
MAINTENANCE_END_CT = time(17, 0)
POWER_HOUR_START = time(14, 0)  # Avoid highs during power hour

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
                'power_hour_filtered': False
            }
        
        # Convert index to CT for filtering
        df_intraday_ct = df_intraday.copy()
        df_intraday_ct['ct_time'] = df_intraday_ct.index.tz_convert(CT_TZ).time
        
        # POWER HOUR FILTER: Find high before 14:00 CT
        df_before_power_hour = df_intraday_ct[df_intraday_ct['ct_time'] < POWER_HOUR_START]
        
        power_hour_filtered = False
        if not df_before_power_hour.empty:
            # Check if the overall high is during power hour
            overall_high_idx = df_intraday['High'].idxmax()
            overall_high_time = to_ct(overall_high_idx.to_pydatetime()).time()
            
            if overall_high_time >= POWER_HOUR_START:
                # Use the high before power hour instead
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
        
        return {
            'date': prior_date,
            'high': high_price,
            'high_time': high_time,
            'low': df_intraday['Low'].min(),
            'low_time': low_time,
            'close': df_intraday['Close'].iloc[-1],
            'close_time': close_time,
            'open': df_intraday['Open'].iloc[0],
            'range': df_intraday['High'].max() - df_intraday['Low'].min(),
            'range_pct': (df_intraday['High'].max() - df_intraday['Low'].min()) / df_intraday['Close'].iloc[-1],
            'power_hour_filtered': power_hour_filtered
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
        
        overnight_start = CT_TZ.localize(datetime.combine(prior_date, time(17, 0)))
        overnight_end = CT_TZ.localize(datetime.combine(session_date, time(8, 30)))
        
        df_es_tz = df_es.copy()
        df_es_tz.index = df_es_tz.index.tz_convert(CT_TZ)
        
        overnight_mask = (df_es_tz.index >= overnight_start) & (df_es_tz.index <= overnight_end)
        df_overnight = df_es_tz[overnight_mask]
        
        if df_overnight.empty:
            return {'offset': offset, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0}
        
        overnight_high = df_overnight['High'].max()
        overnight_low = df_overnight['Low'].min()
        
        return {
            'offset': offset,
            'overnight_high': overnight_high,
            'overnight_low': overnight_low,
            'overnight_high_spx': overnight_high - offset,
            'overnight_low_spx': overnight_low - offset,
            'overnight_range': overnight_high - overnight_low
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

def find_confluence_zones(cones: List[Cone], threshold: float = 5.0) -> List[Dict]:
    """Find where multiple cone rails converge"""
    zones = []
    rails = []
    
    for cone in cones:
        rails.append({'price': cone.ascending_rail, 'name': f"{cone.name} ▲", 'type': 'puts'})
        rails.append({'price': cone.descending_rail, 'name': f"{cone.name} ▼", 'type': 'calls'})
    
    # Check for convergence
    for i, r1 in enumerate(rails):
        for r2 in rails[i+1:]:
            if abs(r1['price'] - r2['price']) <= threshold:
                avg_price = (r1['price'] + r2['price']) / 2
                zones.append({
                    'price': avg_price,
                    'rails': [r1['name'], r2['name']],
                    'type': r1['type']
                })
    
    return zones

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
    
    # Confluence bonus
    zones = find_confluence_zones(cones)
    for zone in zones:
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

def generate_action_card(cones, regime, current_price, is_10am) -> ActionCard:
    warnings = []
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    confluence_score = calculate_confluence_score(nearest_distance, regime, cones, current_price, is_10am)
    position, _ = get_position_in_cone(current_price, nearest_cone.ascending_rail, nearest_cone.descending_rail)
    
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
    section[data-testid="stSidebar"] * {
        color: #f8fafc !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stNumberInput label,
    section[data-testid="stSidebar"] .stTextInput label {
        color: #94a3b8 !important;
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
    cone_html = ""
    for cone in cones:
        cone_html += f"""
        <div style="margin-bottom: 1rem;">
            <div style="font-weight: 600; color: #fbbf24; margin-bottom: 0.5rem;">{cone.name} Cone</div>
            <div style="display: flex; justify-content: space-between;">
                <div>
                    <div class="decision-label">Puts Entry ▲</div>
                    <div class="decision-value decision-puts">{cone.ascending_rail:.2f}</div>
                </div>
                <div>
                    <div class="decision-label">Calls Entry ▼</div>
                    <div class="decision-value decision-calls">{cone.descending_rail:.2f}</div>
                </div>
            </div>
        </div>
        """
    
    st.markdown(f"""
    <div class="decision-card">
        <div class="decision-time">{title}</div>
        {cone_html}
    </div>
    """, unsafe_allow_html=True)

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
        current_price = fetch_current_spx() or (prior_session['close'] if prior_session else 6000)
        first_bar = fetch_first_30min_bar(session_date)
        
        st.markdown("---")
        st.markdown("### ⚙️ Slope Parameters")
        st.metric("Ascending", f"+{SLOPE_ASCENDING}")
        st.metric("Descending", f"-{SLOPE_DESCENDING}")
        
        st.markdown("---")
        st.markdown("### 📍 Pivots")
        
        if prior_session:
            st.caption(f"Source: {prior_session['date'].strftime('%Y-%m-%d')}")
            if prior_session.get('power_hour_filtered'):
                st.warning("⚡ High filtered (power hour)")
            
            use_manual = st.checkbox("Override", value=False)
            
            high_price = st.number_input("High", value=float(prior_session['high']), disabled=not use_manual, format="%.2f")
            high_time_str = st.text_input("High Time (CT)", value=prior_session['high_time'].strftime('%H:%M'), disabled=not use_manual)
            low_price = st.number_input("Low", value=float(prior_session['low']), disabled=not use_manual, format="%.2f")
            low_time_str = st.text_input("Low Time (CT)", value=prior_session['low_time'].strftime('%H:%M'), disabled=not use_manual)
            close_price = st.number_input("Close", value=float(prior_session['close']), disabled=not use_manual, format="%.2f")
            
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
    
    # Build pivots and cones
    pivots = [
        Pivot(price=high_price, time=high_time, name='High'),
        Pivot(price=close_price, time=close_time, name='Close'),
        Pivot(price=low_price, time=low_time, name='Low')
    ]
    
    ct_now = get_ct_now()
    if session_date.date() == ct_now.date():
        eval_time = ct_now
        is_10am = ct_now.time() >= time(10, 0)
    else:
        eval_time = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        is_10am = True
    
    cones = build_cones_at_time(pivots, eval_time)
    cones_830 = build_cones_at_time(pivots, CT_TZ.localize(datetime.combine(session_date, time(8, 30))))
    cones_1000 = build_cones_at_time(pivots, CT_TZ.localize(datetime.combine(session_date, time(10, 0))))
    
    regime = analyze_regime(cones, es_data, prior_session, first_bar, current_price)
    action = generate_action_card(cones, regime, current_price, is_10am)
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
    
    # Confluence Zones
    if confluence_zones:
        st.markdown("#### 🔥 Confluence Zones (High Probability)")
        for zone in confluence_zones:
            st.markdown(f"""
            <div class="info-badge">
                <strong>{zone['type'].upper()}</strong> @ <strong>{zone['price']:.2f}</strong> — 
                Convergence of {' + '.join(zone['rails'])}
            </div>
            """, unsafe_allow_html=True)
    
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
    st.caption("💡 Yellow rows = Key decision windows (8:30 AM and 10:00 AM CT)")
    
    df = build_projection_table(pivots, session_date)
    
    # Format numbers
    for col in df.columns:
        if col != 'Time':
            df[col] = df[col].apply(lambda x: f"{x:.2f}")
    
    styled = df.style.apply(highlight_times, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)
    
    # Footer insight
    st.markdown("---")
    st.info("💡 **Pro Tip:** Your highest-probability trades occur when price touches a rail at the 10:00 AM CT decision window AND that rail shows confluence with another cone.")

if __name__ == "__main__":
    main()
