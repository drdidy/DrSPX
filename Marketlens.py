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

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

SLOPE_ASCENDING = 0.50  # Points per 30-minute block (ascending)
SLOPE_DESCENDING = 0.44  # Points per 30-minute block (descending)
CONTRACT_FACTOR = 0.33  # ATM contract move factor

# Trading hours (CT)
RTH_OPEN_CT = time(8, 30)
RTH_CLOSE_CT = time(15, 0)
MAINTENANCE_START_CT = time(16, 0)
MAINTENANCE_END_CT = time(17, 0)

# Decision windows
DECISION_WINDOW_1 = time(8, 30)
DECISION_WINDOW_2 = time(10, 0)

# No-trade filter thresholds
OVERNIGHT_RANGE_MAX_PCT = 0.40
DEAD_ZONE_PCT = 0.40
MIN_CONE_WIDTH_PCT = 0.0045
MIN_PRIOR_DAY_RANGE_PCT = 0.009
MIN_CONTRACT_MOVE = 8.0
RAIL_TOUCH_THRESHOLD = 1.0
EDGE_ZONE_PCT = 0.30

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
class RegimeAnalysis:
    overnight_range: float
    overnight_range_pct: float
    overnight_touched_rails: List[str]
    opening_print: float
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
    expected_contract_move: float
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
            'overnight_range': overnight_range,
            'df_overnight': df_overnight
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

def build_cones(pivots: List[Pivot], eval_time: datetime) -> List[Cone]:
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

def check_overnight_rail_touches(cones: List[Cone], es_data: Dict, eval_time: datetime) -> List[str]:
    touched = []
    
    if not es_data or es_data.get('overnight_high_spx') is None:
        return touched
    
    overnight_high_spx = es_data['overnight_high_spx']
    overnight_low_spx = es_data['overnight_low_spx']
    
    for cone in cones:
        if abs(overnight_high_spx - cone.ascending_rail) <= RAIL_TOUCH_THRESHOLD:
            touched.append(f"{cone.name} Ascending")
        
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
    
    nearest_cone, _, _ = find_nearest_rail(current_price, cones)
    
    overnight_range = es_data.get('overnight_range', 0) if es_data else 0
    overnight_range_pct = overnight_range / nearest_cone.width if nearest_cone.width > 0 else 0
    
    overnight_touched = check_overnight_rail_touches(cones, es_data, get_ct_now())
    
    opening_print = prior_session.get('open', current_price) if prior_session else current_price
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
    else:
        direction = 'PUTS'
        color = 'green' if confluence_score >= 75 else 'yellow'
        position_size = 'FULL' if confluence_score >= 75 else 'REDUCED'
    
    if direction == 'CALLS':
        entry_level = nearest_cone.descending_rail
        target_100 = nearest_cone.ascending_rail
        cone_height = target_100 - entry_level
        target_50 = entry_level + (cone_height * 0.50)
        target_75 = entry_level + (cone_height * 0.75)
        stop_level = entry_level - 2
    elif direction == 'PUTS':
        entry_level = nearest_cone.ascending_rail
        target_100 = nearest_cone.descending_rail
        cone_height = entry_level - target_100
        target_50 = entry_level - (cone_height * 0.50)
        target_75 = entry_level - (cone_height * 0.75)
        stop_level = entry_level + 2
    else:
        entry_level = current_price
        target_50 = current_price
        target_75 = current_price
        target_100 = current_price
        stop_level = current_price
    
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

def create_cone_chart(cones: List[Cone], current_price: float, session_date: datetime, pivots: List[Pivot]) -> go.Figure:
    
    fig = go.Figure()
    
    colors = {
        'High': {'line': '#e53935', 'fill': 'rgba(229, 57, 53, 0.1)'},
        'Close': {'line': '#1e88e5', 'fill': 'rgba(30, 136, 229, 0.1)'},
        'Low': {'line': '#43a047', 'fill': 'rgba(67, 160, 71, 0.1)'}
    }
    
    start_time = datetime.combine(session_date, time(8, 30))
    start_time = CT_TZ.localize(start_time)
    
    time_points = []
    current = start_time
    end_time = datetime.combine(session_date, time(15, 0))
    end_time = CT_TZ.localize(end_time)
    
    while current <= end_time:
        time_points.append(current)
        current = current + timedelta(minutes=30)
    
    time_labels = [t.strftime('%H:%M') for t in time_points]
    
    for cone, pivot in zip(cones, pivots):
        ascending_values = []
        descending_values = []
        
        for t in time_points:
            blocks = count_30min_blocks(pivot.time, t)
            asc = project_rail(pivot.price, blocks, 'ascending')
            desc = project_rail(pivot.price, blocks, 'descending')
            ascending_values.append(asc)
            descending_values.append(desc)
        
        # Ascending rail
        fig.add_trace(go.Scatter(
            x=time_labels,
            y=ascending_values,
            mode='lines',
            name=f'{cone.name} Asc',
            line=dict(color=colors[cone.name]['line'], width=2),
            hovertemplate='%{y:.2f}<extra></extra>'
        ))
        
        # Descending rail
        fig.add_trace(go.Scatter(
            x=time_labels,
            y=descending_values,
            mode='lines',
            name=f'{cone.name} Desc',
            line=dict(color=colors[cone.name]['line'], width=2, dash='dash'),
            hovertemplate='%{y:.2f}<extra></extra>'
        ))
    
    # Current price line
    fig.add_hline(
        y=current_price,
        line=dict(color='#ff9800', width=2, dash='dot'),
        annotation_text=f'Current: {current_price:.2f}',
        annotation_position='right'
    )
    
    fig.update_layout(
        title='Cone Projections',
        xaxis_title='Time (CT)',
        yaxis_title='SPX Price',
        template='plotly_white',
        height=500,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        ),
        hovermode='x'
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
    
    # Light theme CSS
    st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        margin-bottom: 1rem;
    }
    .action-card-green {
        background: #d4edda;
        border: 2px solid #28a745;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .action-card-yellow {
        background: #fff3cd;
        border: 2px solid #ffc107;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .action-card-red {
        background: #f8d7da;
        border: 2px solid #dc3545;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .direction-text {
        font-size: 1.75rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 1rem;
    }
    .direction-green { color: #28a745; }
    .direction-yellow { color: #856404; }
    .direction-red { color: #dc3545; }
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
            st.info(f"Data from: {prior_session['date'].strftime('%Y-%m-%d')}")
            
            use_manual = st.checkbox("Override pivots manually", value=False)
            
            if use_manual:
                st.warning("Manual pivots active")
            
            high_price = st.number_input(
                "High Price",
                value=float(prior_session['high']),
                step=0.01,
                format="%.2f",
                disabled=not use_manual
            )
            
            high_time_str = st.text_input(
                "High Time (HH:MM CT)",
                value=prior_session['high_time'].strftime('%H:%M'),
                disabled=not use_manual
            )
            
            low_price = st.number_input(
                "Low Price",
                value=float(prior_session['low']),
                step=0.01,
                format="%.2f",
                disabled=not use_manual
            )
            
            low_time_str = st.text_input(
                "Low Time (HH:MM CT)",
                value=prior_session['low_time'].strftime('%H:%M'),
                disabled=not use_manual
            )
            
            close_price = st.number_input(
                "Close Price",
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
        
        st.divider()
        
        st.header("⚙️ Slope Parameters")
        st.text(f"Ascending: +{SLOPE_ASCENDING} pts/30min")
        st.text(f"Descending: -{SLOPE_DESCENDING} pts/30min")
        
        if es_data and es_data.get('offset'):
            st.divider()
            st.header("🔄 ES-SPX Offset")
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
        eval_time = ct_now
        is_10am_window = ct_now.time() >= time(10, 0)
    else:
        eval_time = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        is_10am_window = True
    
    # Build cones
    cones = build_cones(pivots, eval_time)
    
    # Analyze regime
    regime = analyze_regime(cones, es_data, prior_session, first_bar, current_price)
    
    # Generate action card
    action_card = generate_action_card(cones, regime, current_price, is_10am_window)
    
    # Main content
    col_main, col_action = st.columns([2, 1])
    
    with col_main:
        # Current price
        st.metric("SPX Current Price", f"{current_price:,.2f}")
        
        # Chart
        st.plotly_chart(
            create_cone_chart(cones, current_price, session_date, pivots),
            use_container_width=True
        )
        
        # Cone table
        st.subheader("📊 Cone Projections at Key Times")
        
        time_830 = CT_TZ.localize(datetime.combine(session_date, time(8, 30)))
        time_1000 = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        
        cones_830 = build_cones(pivots, time_830)
        cones_1000 = build_cones(pivots, time_1000)
        
        table_data = []
        for i, cone_name in enumerate(['High', 'Close', 'Low']):
            table_data.append({
                'Cone': cone_name,
                '08:30 Asc': f"{cones_830[i].ascending_rail:.2f}",
                '08:30 Desc': f"{cones_830[i].descending_rail:.2f}",
                '10:00 Asc': f"{cones_1000[i].ascending_rail:.2f}",
                '10:00 Desc': f"{cones_1000[i].descending_rail:.2f}",
                'Width': f"{cones_1000[i].width:.2f}"
            })
        
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)
        
        # Regime analysis
        st.subheader("🔍 Regime Analysis")
        
        col_r1, col_r2, col_r3 = st.columns(3)
        
        with col_r1:
            status = "✅" if regime.overnight_range_pct < 0.30 else ("⚠️" if regime.overnight_range_pct < 0.40 else "❌")
            st.metric("Overnight Range", f"{regime.overnight_range:.1f} pts", f"{regime.overnight_range_pct:.0%} of cone {status}")
        
        with col_r2:
            st.metric("Opening Position", regime.opening_position.replace('_', ' ').title())
        
        with col_r3:
            st.metric("First Bar Energy", regime.first_bar_energy.title())
        
        col_r4, col_r5 = st.columns(2)
        
        with col_r4:
            st.metric("Cone Width Adequate", "Yes ✅" if regime.cone_width_adequate else "No ❌")
        
        with col_r5:
            st.metric("Prior Day Range", "Adequate ✅" if regime.prior_day_range_adequate else "Weak ❌")
    
    with col_action:
        # Confluence score
        score_color = "#28a745" if action_card.confluence_score >= 75 else ("#ffc107" if action_card.confluence_score >= 50 else "#dc3545")
        st.markdown(f"### Confluence Score")
        st.markdown(f"<h1 style='text-align: center; color: {score_color};'>{action_card.confluence_score}</h1>", unsafe_allow_html=True)
        
        # Action card
        card_class = f"action-card-{action_card.color}"
        direction_class = f"direction-{action_card.color}"
        
        emoji = '🟢' if action_card.direction == 'CALLS' else ('🔴' if action_card.direction == 'PUTS' else ('🟡' if action_card.direction == 'WAIT' else '⛔'))
        
        st.markdown(f"""
        <div class="{card_class}">
            <div class="direction-text {direction_class}">
                {emoji} {action_card.direction}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Trade details
        if action_card.direction in ['CALLS', 'PUTS']:
            st.markdown("#### 📋 Trade Setup")
            st.write(f"**Structure:** {action_card.active_cone} - {action_card.active_rail.title()}")
            st.write(f"**Entry:** {action_card.entry_level:.2f}")
            
            st.markdown("#### 🎯 Targets")
            st.write(f"• 60% @ 50%: {action_card.target_50:.2f}")
            st.write(f"• 20% @ 75%: {action_card.target_75:.2f}")
            st.write(f"• 20% @ 100%: {action_card.target_100:.2f}")
            
            st.markdown("#### 🛑 Stop")
            st.write(f"**Below:** {action_card.stop_level:.2f}")
            
            st.markdown("#### 💰 Expected Move")
            st.metric("ATM 0DTE", f"${action_card.expected_contract_move:.2f}")
            
            st.markdown("#### 📊 Position Size")
            st.write(f"**{action_card.position_size}**")
        
        # Warnings
        if action_card.warnings:
            st.markdown("#### ⚠️ Alerts")
            for warning in action_card.warnings:
                st.warning(warning)
        
        st.divider()
        st.info("💡 Your edge is highest when the 10:00 CT reaction aligns with your primary cone.")

if __name__ == "__main__":
    main()
