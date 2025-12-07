"""
SPX Prophet - Where Structure Becomes Foresight
A professional SPX trading assistant using structural cones, timing rules, and flow-regime detection.
Version 2.0 - Premium UI + Calibrated Slopes
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

# Asymmetric slopes (calibrated)
SLOPE_ASCENDING = 0.50   # More aggressive for upside
SLOPE_DESCENDING = 0.44  # Slightly conservative for downside

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

def project_rail(pivot_price: float, blocks: int, direction: str, asc_slope: float, desc_slope: float) -> float:
    if direction == 'ascending':
        return pivot_price + (blocks * asc_slope)
    else:
        return pivot_price - (blocks * desc_slope)

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
        st.error(f"Error fetching ES overnight data: {e}")
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

def build_cones(pivots: List[Pivot], eval_time: datetime, asc_slope: float, desc_slope: float) -> List[Cone]:
    cones = []
    
    for pivot in pivots:
        blocks = count_30min_blocks(pivot.time, eval_time)
        
        ascending_rail = project_rail(pivot.price, blocks, 'ascending', asc_slope, desc_slope)
        descending_rail = project_rail(pivot.price, blocks, 'descending', asc_slope, desc_slope)
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
        warnings.append(f"Overnight range too wide ({regime.overnight_range_pct:.0%} of cone)")
        no_trade = True
    
    if position == 'dead_zone' and nearest_distance > 20:
        warnings.append("Price in dead zone - no clear edge")
        no_trade = True
    
    if not regime.cone_width_adequate:
        warnings.append("Cone width too narrow - insufficient profit potential")
        no_trade = True
    
    if not regime.prior_day_range_adequate:
        warnings.append("Prior day range weak - unreliable pivots")
        no_trade = True
    
    if len(regime.overnight_touched_rails) > 0:
        warnings.append(f"Overnight touched: {', '.join(regime.overnight_touched_rails)}")
    
    if regime.first_bar_energy == 'weak':
        warnings.append("First bar shows weak energy")
    
    if no_trade:
        direction = 'NO TRADE'
        color = 'red'
        position_size = 'NONE'
    elif position == 'dead_zone':
        direction = 'WAIT'
        color = 'yellow'
        position_size = 'NONE'
        warnings.append(f"Call setup activates at {nearest_cone.descending_rail:.2f} or below")
        warnings.append(f"Put setup activates at {nearest_cone.ascending_rail:.2f} or above")
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
        warnings.append(f"Expected contract move (${expected_contract_move:.2f}) below minimum")
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

def create_cone_chart(cones: List[Cone], current_price: float, session_date: datetime, asc_slope: float, desc_slope: float, pivots: List[Pivot]) -> go.Figure:
    
    fig = go.Figure()
    
    colors = {
        'High': {'asc': '#ff6b6b', 'desc': '#ee5a5a', 'fill': 'rgba(255, 107, 107, 0.08)'},
        'Close': {'asc': '#4dabf7', 'desc': '#339af0', 'fill': 'rgba(77, 171, 247, 0.08)'},
        'Low': {'asc': '#51cf66', 'desc': '#40c057', 'fill': 'rgba(81, 207, 102, 0.08)'}
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
    
    for cone, pivot in zip(cones, pivots):
        ascending_values = []
        descending_values = []
        
        for t in time_points:
            blocks = count_30min_blocks(pivot.time, t)
            asc = project_rail(pivot.price, blocks, 'ascending', asc_slope, desc_slope)
            desc = project_rail(pivot.price, blocks, 'descending', asc_slope, desc_slope)
            ascending_values.append(asc)
            descending_values.append(desc)
        
        time_labels = [t.strftime('%H:%M') for t in time_points]
        
        # Fill between rails
        fig.add_trace(go.Scatter(
            x=time_labels + time_labels[::-1],
            y=ascending_values + descending_values[::-1],
            fill='toself',
            fillcolor=colors[cone.name]['fill'],
            line=dict(color='rgba(0,0,0,0)'),
            name=f'{cone.name} Zone',
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Ascending rail
        fig.add_trace(go.Scatter(
            x=time_labels,
            y=ascending_values,
            mode='lines',
            name=f'{cone.name} ▲',
            line=dict(color=colors[cone.name]['asc'], width=2.5),
            hovertemplate='<b>%{y:.2f}</b><extra>' + cone.name + ' Ascending</extra>'
        ))
        
        # Descending rail
        fig.add_trace(go.Scatter(
            x=time_labels,
            y=descending_values,
            mode='lines',
            name=f'{cone.name} ▼',
            line=dict(color=colors[cone.name]['desc'], width=2.5, dash='dot'),
            hovertemplate='<b>%{y:.2f}</b><extra>' + cone.name + ' Descending</extra>'
        ))
    
    # Current price line
    fig.add_hline(
        y=current_price,
        line=dict(color='#ffd43b', width=3),
        annotation_text=f'  SPX: {current_price:,.2f}',
        annotation_position='right',
        annotation_font=dict(color='#ffd43b', size=14, family='Inter')
    )
    
    # Decision window markers - using shapes and annotations separately for categorical axis
    # Find indices for the time labels
    time_labels = [t.strftime('%H:%M') for t in time_points]
    
    # Find index positions for vertical lines
    idx_830 = time_labels.index('08:30') if '08:30' in time_labels else 0
    idx_1000 = time_labels.index('10:00') if '10:00' in time_labels else 3
    
    # Add vertical lines as shapes using index positions
    fig.add_shape(
        type="line",
        x0=idx_830, x1=idx_830,
        y0=0, y1=1,
        xref='x', yref='paper',
        line=dict(color='rgba(255,212,59,0.4)', width=2, dash='dash')
    )
    fig.add_shape(
        type="line",
        x0=idx_1000, x1=idx_1000,
        y0=0, y1=1,
        xref='x', yref='paper',
        line=dict(color='#ffd43b', width=3)
    )
    
    # Add annotations separately
    fig.add_annotation(
        x=idx_830, y=1.05, xref='x', yref='paper',
        text='Open',
        showarrow=False,
        font=dict(color='#ffd43b', size=11)
    )
    fig.add_annotation(
        x=idx_1000, y=1.05, xref='x', yref='paper',
        text='10:00 Decision',
        showarrow=False,
        font=dict(color='#ffd43b', size=12, family='Inter')
    )
    
    fig.update_layout(
        title=dict(
            text='<b>Cone Structure Projections</b>',
            font=dict(size=20, color='#f8f9fa', family='Inter'),
            x=0.5
        ),
        xaxis=dict(
            title='Time (CT)',
            titlefont=dict(color='#adb5bd', size=13),
            tickfont=dict(color='#adb5bd', size=11),
            gridcolor='rgba(173, 181, 189, 0.1)',
            showgrid=True
        ),
        yaxis=dict(
            title='SPX Price',
            titlefont=dict(color='#adb5bd', size=13),
            tickfont=dict(color='#adb5bd', size=11),
            gridcolor='rgba(173, 181, 189, 0.1)',
            showgrid=True,
            tickformat=',.0f'
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        height=520,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
            font=dict(color='#f8f9fa', size=11),
            bgcolor='rgba(0,0,0,0)'
        ),
        hovermode='x',
        margin=dict(l=60, r=30, t=80, b=60)
    )
    
    return fig

# ============================================================================
# STREAMLIT UI - PREMIUM DESIGN
# ============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet",
        page_icon="🔮",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Premium CSS
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
    
    :root {
        --bg-primary: #0a0e17;
        --bg-secondary: #111827;
        --bg-card: linear-gradient(145deg, #1a1f2e 0%, #151922 100%);
        --accent-blue: #3b82f6;
        --accent-cyan: #06b6d4;
        --accent-green: #10b981;
        --accent-yellow: #f59e0b;
        --accent-red: #ef4444;
        --accent-purple: #8b5cf6;
        --text-primary: #f8fafc;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
        --border-color: rgba(148, 163, 184, 0.1);
        --glow-blue: 0 0 20px rgba(59, 130, 246, 0.3);
        --glow-green: 0 0 20px rgba(16, 185, 129, 0.3);
        --glow-yellow: 0 0 20px rgba(245, 158, 11, 0.3);
        --glow-red: 0 0 20px rgba(239, 68, 68, 0.3);
    }
    
    .stApp {
        background: linear-gradient(180deg, #0a0e17 0%, #111827 50%, #0a0e17 100%);
    }
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    code, .stCode {
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Main Header */
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 50%, #1e1b4b 100%);
        padding: 2.5rem 3rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        border: 1px solid rgba(59, 130, 246, 0.2);
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255,255,255,0.05);
        position: relative;
        overflow: hidden;
    }
    
    .main-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.5), transparent);
    }
    
    .main-header::after {
        content: '';
        position: absolute;
        top: -50%;
        right: -10%;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle, rgba(59, 130, 246, 0.1) 0%, transparent 70%);
        pointer-events: none;
    }
    
    .logo-container {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .logo-icon {
        font-size: 3rem;
        filter: drop-shadow(0 0 10px rgba(59, 130, 246, 0.5));
    }
    
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #f8fafc 0%, #3b82f6 50%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
        letter-spacing: -0.03em;
        text-shadow: 0 0 30px rgba(59, 130, 246, 0.3);
    }
    
    .tagline {
        font-size: 1.15rem;
        color: #94a3b8;
        margin-top: 0.5rem;
        font-weight: 400;
        letter-spacing: 0.02em;
    }
    
    .tagline span {
        color: #3b82f6;
        font-weight: 500;
    }
    
    /* Metric Cards */
    .metric-card {
        background: linear-gradient(145deg, #1a1f2e 0%, #151922 100%);
        padding: 1.5rem;
        border-radius: 16px;
        border: 1px solid rgba(148, 163, 184, 0.1);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .metric-card:hover {
        border-color: rgba(59, 130, 246, 0.3);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3), 0 0 20px rgba(59, 130, 246, 0.1);
        transform: translateY(-2px);
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #f8fafc;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .metric-value.price {
        background: linear-gradient(135deg, #ffd43b 0%, #fab005 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    /* Price Display */
    .price-display {
        background: linear-gradient(145deg, #1a1f2e 0%, #151922 100%);
        padding: 2rem;
        border-radius: 20px;
        border: 1px solid rgba(255, 212, 59, 0.2);
        box-shadow: 0 0 30px rgba(255, 212, 59, 0.1);
        text-align: center;
        margin-bottom: 1.5rem;
    }
    
    .price-label {
        font-size: 0.85rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        font-weight: 600;
        margin-bottom: 0.75rem;
    }
    
    .price-value {
        font-size: 3.5rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        background: linear-gradient(135deg, #ffd43b 0%, #fab005 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-shadow: 0 0 40px rgba(255, 212, 59, 0.3);
    }
    
    /* Action Cards */
    .action-card {
        padding: 2rem;
        border-radius: 20px;
        margin: 1.5rem 0;
        position: relative;
        overflow: hidden;
    }
    
    .action-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        opacity: 0.1;
        pointer-events: none;
    }
    
    .action-card-green {
        background: linear-gradient(145deg, #064e3b 0%, #022c22 100%);
        border: 2px solid #10b981;
        box-shadow: 0 0 40px rgba(16, 185, 129, 0.2), inset 0 1px 0 rgba(255,255,255,0.05);
    }
    
    .action-card-yellow {
        background: linear-gradient(145deg, #713f12 0%, #451a03 100%);
        border: 2px solid #f59e0b;
        box-shadow: 0 0 40px rgba(245, 158, 11, 0.2), inset 0 1px 0 rgba(255,255,255,0.05);
    }
    
    .action-card-red {
        background: linear-gradient(145deg, #7f1d1d 0%, #450a0a 100%);
        border: 2px solid #ef4444;
        box-shadow: 0 0 40px rgba(239, 68, 68, 0.2), inset 0 1px 0 rgba(255,255,255,0.05);
    }
    
    .direction-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.75rem;
        padding: 1rem 2rem;
        border-radius: 12px;
        font-size: 1.75rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
    }
    
    .direction-badge.calls {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
    }
    
    .direction-badge.puts {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white;
        box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
    }
    
    .direction-badge.wait {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white;
        box-shadow: 0 4px 15px rgba(245, 158, 11, 0.4);
    }
    
    .direction-badge.notrade {
        background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
        color: white;
        box-shadow: 0 4px 15px rgba(107, 114, 128, 0.4);
    }
    
    /* Confluence Score */
    .confluence-container {
        background: linear-gradient(145deg, #1a1f2e 0%, #151922 100%);
        padding: 2rem;
        border-radius: 20px;
        border: 1px solid rgba(148, 163, 184, 0.1);
        text-align: center;
        margin-bottom: 1.5rem;
    }
    
    .confluence-score {
        font-size: 4.5rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        line-height: 1;
    }
    
    .confluence-score.high {
        background: linear-gradient(135deg, #10b981 0%, #06b6d4 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-shadow: 0 0 40px rgba(16, 185, 129, 0.4);
    }
    
    .confluence-score.medium {
        background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-shadow: 0 0 40px rgba(245, 158, 11, 0.4);
    }
    
    .confluence-score.low {
        background: linear-gradient(135deg, #ef4444 0%, #f87171 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        text-shadow: 0 0 40px rgba(239, 68, 68, 0.4);
    }
    
    .confluence-label {
        font-size: 0.8rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        font-weight: 600;
        margin-top: 0.5rem;
    }
    
    /* Data Table */
    .data-table {
        background: linear-gradient(145deg, #1a1f2e 0%, #151922 100%);
        border-radius: 16px;
        border: 1px solid rgba(148, 163, 184, 0.1);
        overflow: hidden;
    }
    
    /* Warning Badges */
    .warning-badge {
        background: linear-gradient(145deg, rgba(245, 158, 11, 0.15) 0%, rgba(245, 158, 11, 0.05) 100%);
        border: 1px solid rgba(245, 158, 11, 0.3);
        color: #fbbf24;
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        font-size: 0.9rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .info-badge {
        background: linear-gradient(145deg, rgba(59, 130, 246, 0.15) 0%, rgba(59, 130, 246, 0.05) 100%);
        border: 1px solid rgba(59, 130, 246, 0.3);
        color: #60a5fa;
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        font-size: 0.9rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .success-badge {
        background: linear-gradient(145deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #34d399;
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        font-size: 0.9rem;
        font-weight: 500;
    }
    
    /* Section Headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 1.5rem 0 1rem 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .section-header::after {
        content: '';
        flex: 1;
        height: 1px;
        background: linear-gradient(90deg, rgba(148, 163, 184, 0.2), transparent);
        margin-left: 1rem;
    }
    
    /* Trade Details */
    .trade-detail {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.75rem 0;
        border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    }
    
    .trade-detail:last-child {
        border-bottom: none;
    }
    
    .trade-detail-label {
        color: #94a3b8;
        font-size: 0.9rem;
        font-weight: 500;
    }
    
    .trade-detail-value {
        color: #f8fafc;
        font-size: 1rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* Regime Indicators */
    .regime-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        margin: 1rem 0;
    }
    
    .regime-item {
        background: linear-gradient(145deg, #1a1f2e 0%, #151922 100%);
        padding: 1.25rem;
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.1);
        text-align: center;
    }
    
    .regime-item-label {
        font-size: 0.7rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }
    
    .regime-item-value {
        font-size: 1rem;
        font-weight: 600;
        color: #f8fafc;
    }
    
    .regime-item-status {
        font-size: 1.25rem;
        margin-top: 0.25rem;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111827 0%, #0a0e17 100%);
        border-right: 1px solid rgba(148, 163, 184, 0.1);
    }
    
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #f8fafc;
        font-weight: 600;
        font-size: 0.95rem;
        letter-spacing: 0.02em;
    }
    
    /* Input Styling */
    .stNumberInput > div > div > input,
    .stTextInput > div > div > input {
        background: #1a1f2e !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        border-radius: 8px !important;
        color: #f8fafc !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    .stNumberInput > div > div > input:focus,
    .stTextInput > div > div > input:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
    }
    
    .stSelectbox > div > div {
        background: #1a1f2e !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        border-radius: 8px !important;
    }
    
    .stDateInput > div > div > input {
        background: #1a1f2e !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        border-radius: 8px !important;
        color: #f8fafc !important;
    }
    
    /* Checkbox */
    .stCheckbox label {
        color: #f8fafc !important;
    }
    
    /* Dataframe */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
    }
    
    .stDataFrame [data-testid="stDataFrameResizable"] {
        background: #1a1f2e;
    }
    
    /* Plotly Chart Container */
    .stPlotlyChart {
        background: linear-gradient(145deg, #1a1f2e 0%, #151922 100%);
        border-radius: 16px;
        border: 1px solid rgba(148, 163, 184, 0.1);
        padding: 1rem;
    }
    
    /* Insight Box */
    .insight-box {
        background: linear-gradient(145deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.05) 100%);
        border: 1px solid rgba(59, 130, 246, 0.2);
        border-radius: 12px;
        padding: 1.25rem;
        margin-top: 1rem;
    }
    
    .insight-box .icon {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
    }
    
    .insight-box .text {
        color: #94a3b8;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    
    .insight-box .highlight {
        color: #60a5fa;
        font-weight: 600;
    }
    
    /* Animations */
    @keyframes pulse-glow {
        0%, 100% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.3); }
        50% { box-shadow: 0 0 40px rgba(59, 130, 246, 0.5); }
    }
    
    @keyframes float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-5px); }
    }
    
    .pulse-animation {
        animation: pulse-glow 2s ease-in-out infinite;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
    <div class="main-header">
        <div class="logo-container">
            <span class="logo-icon">🔮</span>
            <div>
                <h1 class="main-title">SPX Prophet</h1>
                <p class="tagline">Where <span>Structure</span> Becomes <span>Foresight</span></p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 📅 Session")
        
        session_date = st.date_input(
            "Trading Date",
            value=datetime.now().date(),
            help="Select the trading session to analyze"
        )
        session_date = datetime.combine(session_date, time(0, 0))
        
        st.markdown("---")
        
        # Slope configuration
        st.markdown("### ⚙️ Slope Parameters")
        
        asc_slope = st.number_input(
            "Ascending Slope",
            value=SLOPE_ASCENDING,
            min_value=0.30,
            max_value=0.70,
            step=0.01,
            format="%.2f",
            help="Points per 30-min block (upside)"
        )
        
        desc_slope = st.number_input(
            "Descending Slope", 
            value=SLOPE_DESCENDING,
            min_value=0.30,
            max_value=0.70,
            step=0.01,
            format="%.2f",
            help="Points per 30-min block (downside)"
        )
        
        st.markdown("---")
        
        # Fetch data
        prior_session = fetch_prior_session_data(session_date)
        es_data = fetch_es_overnight_data(session_date)
        current_price = fetch_current_spx() or (prior_session['close'] if prior_session else 6000)
        first_bar = fetch_first_30min_bar(session_date)
        
        st.markdown("### 📍 Pivots")
        
        if prior_session:
            st.caption(f"Source: {prior_session['date'].strftime('%Y-%m-%d')}")
            
            use_manual = st.checkbox("Override pivots", value=False)
            
            if use_manual:
                st.warning("⚠️ Manual mode")
            
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
            st.error("Could not fetch data")
            use_manual = True
            
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
        
        st.markdown("---")
        
        if es_data and es_data.get('offset'):
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
        is_10am_window = ct_now.time() >= time(10, 0)
    else:
        eval_time = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        is_10am_window = True
    
    cones = build_cones(pivots, eval_time, asc_slope, desc_slope)
    regime = analyze_regime(cones, es_data, prior_session, first_bar, current_price)
    action_card = generate_action_card(cones, regime, current_price, is_10am_window)
    
    # Main Layout
    col_main, col_action = st.columns([2, 1])
    
    with col_main:
        # Price Display
        st.markdown(f"""
        <div class="price-display">
            <div class="price-label">SPX Current Price</div>
            <div class="price-value">{current_price:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Cone Chart
        st.plotly_chart(
            create_cone_chart(cones, current_price, session_date, asc_slope, desc_slope, pivots),
            use_container_width=True
        )
        
        # Cone Projections Table
        st.markdown('<div class="section-header">📊 Cone Projections at Key Times</div>', unsafe_allow_html=True)
        
        time_830 = CT_TZ.localize(datetime.combine(session_date, time(8, 30)))
        time_1000 = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        
        cones_830 = build_cones(pivots, time_830, asc_slope, desc_slope)
        cones_1000 = build_cones(pivots, time_1000, asc_slope, desc_slope)
        
        table_data = []
        for i, cone_name in enumerate(['High', 'Close', 'Low']):
            table_data.append({
                'Cone': f"🔺 {cone_name}" if cone_name == 'High' else (f"🔷 {cone_name}" if cone_name == 'Close' else f"🔻 {cone_name}"),
                '08:30 ▲': f"{cones_830[i].ascending_rail:.2f}",
                '08:30 ▼': f"{cones_830[i].descending_rail:.2f}",
                '10:00 ▲': f"{cones_1000[i].ascending_rail:.2f}",
                '10:00 ▼': f"{cones_1000[i].descending_rail:.2f}",
                'Width': f"{cones_1000[i].width:.2f}",
                'Width %': f"{(cones_1000[i].width / current_price * 100):.3f}%"
            })
        
        df_cones = pd.DataFrame(table_data)
        st.dataframe(df_cones, use_container_width=True, hide_index=True)
        
        # Regime Analysis
        st.markdown('<div class="section-header">🔍 Regime Analysis</div>', unsafe_allow_html=True)
        
        col_r1, col_r2, col_r3 = st.columns(3)
        
        with col_r1:
            overnight_status = "✅" if regime.overnight_range_pct < 0.30 else ("⚠️" if regime.overnight_range_pct < 0.40 else "❌")
            st.markdown(f"""
            <div class="regime-item">
                <div class="regime-item-label">Overnight Range</div>
                <div class="regime-item-value">{regime.overnight_range:.1f} pts</div>
                <div class="regime-item-status">{regime.overnight_range_pct:.0%} of cone {overnight_status}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_r2:
            position_emoji = "✅" if regime.opening_position in ['lower_edge', 'upper_edge'] else "⚠️"
            st.markdown(f"""
            <div class="regime-item">
                <div class="regime-item-label">Price Position</div>
                <div class="regime-item-value">{regime.opening_position.replace('_', ' ').title()}</div>
                <div class="regime-item-status">{position_emoji}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_r3:
            energy_emoji = "✅" if regime.first_bar_energy == 'strong' else ("⚠️" if regime.first_bar_energy == 'neutral' else "❌")
            st.markdown(f"""
            <div class="regime-item">
                <div class="regime-item-label">First Bar Energy</div>
                <div class="regime-item-value">{regime.first_bar_energy.title()}</div>
                <div class="regime-item-status">{energy_emoji}</div>
            </div>
            """, unsafe_allow_html=True)
        
        col_r4, col_r5, col_r6 = st.columns(3)
        
        with col_r4:
            st.markdown(f"""
            <div class="regime-item">
                <div class="regime-item-label">Cone Width</div>
                <div class="regime-item-value">{'Adequate' if regime.cone_width_adequate else 'Narrow'}</div>
                <div class="regime-item-status">{'✅' if regime.cone_width_adequate else '❌'}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_r5:
            st.markdown(f"""
            <div class="regime-item">
                <div class="regime-item-label">Prior Day Range</div>
                <div class="regime-item-value">{'Adequate' if regime.prior_day_range_adequate else 'Weak'}</div>
                <div class="regime-item-status">{'✅' if regime.prior_day_range_adequate else '❌'}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_r6:
            touch_text = ", ".join(regime.overnight_touched_rails) if regime.overnight_touched_rails else "None"
            st.markdown(f"""
            <div class="regime-item">
                <div class="regime-item-label">Overnight Touches</div>
                <div class="regime-item-value" style="font-size: 0.85rem;">{touch_text}</div>
                <div class="regime-item-status">{'⚠️' if regime.overnight_touched_rails else '✅'}</div>
            </div>
            """, unsafe_allow_html=True)
    
    with col_action:
        # Confluence Score
        score_class = "high" if action_card.confluence_score >= 75 else ("medium" if action_card.confluence_score >= 50 else "low")
        st.markdown(f"""
        <div class="confluence-container">
            <div class="confluence-score {score_class}">{action_card.confluence_score}</div>
            <div class="confluence-label">Confluence Score</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Action Card
        card_class = f"action-card action-card-{action_card.color}"
        direction_class = action_card.direction.lower().replace(' ', '')
        direction_icon = '📈' if action_card.direction == 'CALLS' else ('📉' if action_card.direction == 'PUTS' else ('⏳' if action_card.direction == 'WAIT' else '⛔'))
        
        st.markdown(f"""
        <div class="{card_class}">
            <div style="text-align: center;">
                <span class="direction-badge {direction_class}">{direction_icon} {action_card.direction}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Trade Details
        if action_card.direction in ['CALLS', 'PUTS']:
            st.markdown('<div class="section-header">📋 Setup Details</div>', unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="trade-detail">
                    <span class="trade-detail-label">Structure</span>
                    <span class="trade-detail-value">{action_card.active_cone} - {action_card.active_rail.title()}</span>
                </div>
                <div class="trade-detail">
                    <span class="trade-detail-label">Entry Level</span>
                    <span class="trade-detail-value">{action_card.entry_level:.2f}</span>
                </div>
                <div class="trade-detail">
                    <span class="trade-detail-label">Position Size</span>
                    <span class="trade-detail-value" style="color: {'#10b981' if action_card.position_size == 'FULL' else '#f59e0b'};">{action_card.position_size}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="section-header">🎯 Exit Targets</div>', unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="trade-detail">
                    <span class="trade-detail-label">60% @ 50%</span>
                    <span class="trade-detail-value" style="color: #10b981;">{action_card.target_50:.2f}</span>
                </div>
                <div class="trade-detail">
                    <span class="trade-detail-label">20% @ 75%</span>
                    <span class="trade-detail-value" style="color: #10b981;">{action_card.target_75:.2f}</span>
                </div>
                <div class="trade-detail">
                    <span class="trade-detail-label">20% @ 100%</span>
                    <span class="trade-detail-value" style="color: #10b981;">{action_card.target_100:.2f}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown('<div class="section-header">🛑 Risk Management</div>', unsafe_allow_html=True)
            
            st.markdown(f"""
            <div class="metric-card">
                <div class="trade-detail">
                    <span class="trade-detail-label">Stop Loss</span>
                    <span class="trade-detail-value" style="color: #ef4444;">{action_card.stop_level:.2f}</span>
                </div>
                <div class="trade-detail">
                    <span class="trade-detail-label">ATM 0DTE Move</span>
                    <span class="trade-detail-value">${action_card.expected_contract_move:.2f}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        elif action_card.direction == 'WAIT':
            st.markdown("""
            <div class="metric-card">
                <div style="text-align: center; padding: 1rem;">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">⏳</div>
                    <div style="color: #f8fafc; font-weight: 600;">Waiting for Setup</div>
                    <div style="color: #94a3b8; font-size: 0.9rem; margin-top: 0.5rem;">Price in dead zone. Monitor for migration to edge.</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Warnings
        if action_card.warnings:
            st.markdown('<div class="section-header">⚠️ Alerts</div>', unsafe_allow_html=True)
            
            for warning in action_card.warnings:
                if "activates at" in warning:
                    st.markdown(f'<div class="info-badge">📍 {warning}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="warning-badge">⚠️ {warning}</div>', unsafe_allow_html=True)
        
        # Insight Box
        st.markdown("""
        <div class="insight-box">
            <div class="icon">💡</div>
            <div class="text">
                Your edge is highest when the <span class="highlight">10:00 CT reaction</span> aligns with your primary cone structure.
            </div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
