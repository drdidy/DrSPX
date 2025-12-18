"""
SPX PROPHET PRO - Million Dollar Edition
=========================================
The Ultimate SPX-VIX Confluence Trading System

Core Strategy:
- VIX moves in 0.15 zones set overnight (5pm-2am)
- VIX at zone TOP + SPX at descending rail = CALLS
- VIX at zone BOTTOM + SPX at ascending rail = PUTS
- 30-minute candle CLOSE confirms VIX levels
"""

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta, time
import pytz
from dataclasses import dataclass
from typing import Optional, List, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')
SLOPE = 0.45  # Points per 30-min block

# ============================================================================
# STYLING - Clean, Professional, Light Theme
# ============================================================================

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    /* Global */
    .stApp { background: #ffffff; }
    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    
    /* Hide Streamlit branding */
    #MainMenu, footer, header { visibility: hidden; }
    
    /* Sidebar - Compact & Clean */
    [data-testid="stSidebar"] { background: #fafafa; border-right: 1px solid #e5e5e5; }
    [data-testid="stSidebar"] * { font-size: 12px !important; }
    [data-testid="stSidebar"] h1 { font-size: 16px !important; font-weight: 700 !important; color: #111 !important; }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { font-size: 13px !important; font-weight: 600 !important; color: #333 !important; }
    [data-testid="stSidebar"] label { font-size: 11px !important; color: #555 !important; font-weight: 500 !important; }
    [data-testid="stSidebar"] .stNumberInput input { font-size: 13px !important; font-family: 'JetBrains Mono', monospace !important; }
    [data-testid="stSidebar"] .stMetric label { font-size: 10px !important; }
    [data-testid="stSidebar"] .stMetric [data-testid="stMetricValue"] { font-size: 14px !important; }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span { color: #444 !important; }
    
    /* Main content */
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        padding: 20px 24px;
        border-radius: 12px;
        margin-bottom: 20px;
    }
    .main-title {
        font-size: 24px;
        font-weight: 700;
        color: #fff;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-subtitle {
        font-size: 12px;
        color: #fbbf24;
        margin-top: 4px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Signal Box */
    .signal-box {
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        margin-bottom: 16px;
    }
    .signal-calls {
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        border: 2px solid #10b981;
    }
    .signal-puts {
        background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
        border: 2px solid #ef4444;
    }
    .signal-wait {
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
        border: 2px solid #f59e0b;
    }
    .signal-icon { font-size: 48px; margin-bottom: 8px; }
    .signal-text { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
    .signal-sub { font-size: 13px; color: #666; }
    
    /* Info Cards */
    .info-card {
        background: #fff;
        border: 1px solid #e5e5e5;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .info-card-title {
        font-size: 11px;
        font-weight: 600;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    
    /* Zone Ladder */
    .zone-ladder {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        line-height: 1.6;
    }
    .zone-row { padding: 2px 0; color: #666; }
    .zone-row-highlight {
        background: #f0f9ff;
        padding: 4px 8px;
        border-radius: 4px;
        margin: 2px 0;
        font-weight: 600;
    }
    .zone-top { background: #d1fae5; color: #047857; }
    .zone-now { background: #dbeafe; color: #1d4ed8; }
    .zone-bot { background: #fee2e2; color: #b91c1c; }
    
    /* Trade Setup Cards */
    .setup-card {
        background: #fff;
        border: 1px solid #e5e5e5;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 4px solid;
    }
    .setup-calls { border-left-color: #10b981; }
    .setup-puts { border-left-color: #ef4444; }
    .setup-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }
    .setup-title { font-size: 14px; font-weight: 600; color: #111; }
    .setup-badge {
        font-size: 10px;
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 4px;
    }
    .badge-calls { background: #d1fae5; color: #047857; }
    .badge-puts { background: #fee2e2; color: #b91c1c; }
    .setup-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 12px;
    }
    .setup-item label {
        font-size: 10px;
        color: #888;
        text-transform: uppercase;
    }
    .setup-item value {
        font-size: 14px;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
        color: #111;
        display: block;
        margin-top: 2px;
    }
    
    /* Checklist */
    .checklist-item {
        display: flex;
        align-items: center;
        padding: 8px 12px;
        border-radius: 6px;
        margin-bottom: 6px;
        font-size: 13px;
    }
    .checklist-pass { background: #f0fdf4; }
    .checklist-fail { background: #fef2f2; }
    .checklist-icon { margin-right: 10px; font-size: 14px; }
    .checklist-text { flex: 1; color: #333; }
    .checklist-detail { font-size: 11px; color: #888; }
    
    /* Warning Box */
    .warning-box {
        background: #fffbeb;
        border: 1px solid #fcd34d;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 16px;
        font-size: 12px;
        color: #92400e;
    }
    
    /* Metrics Row */
    .metrics-row {
        display: flex;
        gap: 12px;
        margin-bottom: 16px;
    }
    .metric-box {
        flex: 1;
        background: #fafafa;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    .metric-label { font-size: 10px; color: #888; text-transform: uppercase; }
    .metric-value { font-size: 18px; font-weight: 700; color: #111; font-family: 'JetBrains Mono', monospace; }
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_ct_now():
    return datetime.now(CT_TZ)

@st.cache_data(ttl=60)
def fetch_spx_price():
    try:
        ticker = yf.Ticker("^GSPC")
        data = ticker.history(period='1d', interval='1m')
        if not data.empty:
            return data['Close'].iloc[-1]
    except:
        pass
    return None

@st.cache_data(ttl=300)
def fetch_prior_session(session_date):
    try:
        ticker = yf.Ticker("^GSPC")
        prior = session_date - timedelta(days=1)
        while prior.weekday() > 4:
            prior -= timedelta(days=1)
        
        start = (prior - timedelta(days=3)).strftime('%Y-%m-%d')
        end = (prior + timedelta(days=1)).strftime('%Y-%m-%d')
        
        data = ticker.history(start=start, end=end, interval='1d')
        if not data.empty:
            row = data.iloc[-1]
            return {
                'high': row['High'],
                'low': row['Low'],
                'close': row['Close'],
                'date': data.index[-1].strftime('%Y-%m-%d')
            }
    except:
        pass
    return None

# ============================================================================
# CONE CALCULATIONS
# ============================================================================

@dataclass
class Cone:
    name: str
    anchor: float
    anchor_time: datetime
    ascending_rail: float
    descending_rail: float

def calculate_cones(prior_session: dict, session_date: datetime, target_time: time) -> List[Cone]:
    if not prior_session:
        return []
    
    anchor_dt = CT_TZ.localize(datetime.combine(session_date.date(), time(8, 30)))
    target_dt = CT_TZ.localize(datetime.combine(session_date.date(), target_time))
    
    minutes_elapsed = (target_dt - anchor_dt).total_seconds() / 60
    blocks = minutes_elapsed / 30
    
    cones = []
    for name, price in [('High', prior_session['high']), ('Low', prior_session['low']), ('Close', prior_session['close'])]:
        asc = price + (SLOPE * blocks)
        desc = price - (SLOPE * blocks)
        cones.append(Cone(name=name, anchor=price, anchor_time=anchor_dt, ascending_rail=asc, descending_rail=desc))
    
    return cones

def find_nearest_rail(price: float, cones: List[Cone]) -> Tuple[Optional[Cone], str, float]:
    nearest_cone = None
    nearest_type = ''
    nearest_dist = float('inf')
    
    for cone in cones:
        for rail_type, rail_val in [('descending', cone.descending_rail), ('ascending', cone.ascending_rail)]:
            dist = abs(price - rail_val)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest_cone = cone
                nearest_type = rail_type
    
    return nearest_cone, nearest_type, nearest_dist

# ============================================================================
# VIX ZONE ANALYSIS
# ============================================================================

def analyze_vix_zone(zone_bottom: float, zone_top: float, current_vix: float) -> dict:
    """Analyze VIX position within 0.15 zones"""
    
    zone_size = zone_top - zone_bottom
    zones_above = [round(zone_top + (0.15 * i), 2) for i in range(1, 5)]
    zones_below = [round(zone_bottom - (0.15 * i), 2) for i in range(1, 5)]
    
    if current_vix <= 0:
        return {
            'status': 'NO_DATA',
            'bias': 'UNKNOWN',
            'action': 'Enter current VIX',
            'entry_rail': 'N/A',
            'exit_target': '',
            'position_pct': 50,
            'zones_above': zones_above,
            'zones_below': zones_below,
            'zone_top': zone_top,
            'zone_bottom': zone_bottom
        }
    
    if current_vix > zone_top:
        zones_up = int((current_vix - zone_top) / 0.15) + 1
        return {
            'status': 'BREAKOUT_UP',
            'bias': 'PUTS',
            'action': f'VIX broke UP +{zones_up} zone(s) → PUTS extend',
            'entry_rail': 'ascending (▲)',
            'exit_target': f'Target: {zone_top + (0.15 * zones_up):.2f}',
            'position_pct': 100,
            'zones_above': zones_above,
            'zones_below': zones_below,
            'zone_top': zone_top,
            'zone_bottom': zone_bottom
        }
    
    if current_vix < zone_bottom:
        zones_down = int((zone_bottom - current_vix) / 0.15) + 1
        return {
            'status': 'BREAKOUT_DOWN',
            'bias': 'CALLS',
            'action': f'VIX broke DOWN -{zones_down} zone(s) → CALLS extend',
            'entry_rail': 'descending (▼)',
            'exit_target': f'Target: {zone_bottom - (0.15 * zones_down):.2f}',
            'position_pct': 0,
            'zones_above': zones_above,
            'zones_below': zones_below,
            'zone_top': zone_top,
            'zone_bottom': zone_bottom
        }
    
    # Within zone
    position_pct = ((current_vix - zone_bottom) / zone_size * 100) if zone_size > 0 else 50
    
    if position_pct >= 75:
        return {
            'status': 'AT_TOP',
            'bias': 'CALLS',
            'action': 'VIX at TOP → rejects → SPX UP',
            'entry_rail': 'descending (▼)',
            'exit_target': f'Exit at VIX {zone_bottom:.2f}',
            'position_pct': position_pct,
            'zones_above': zones_above,
            'zones_below': zones_below,
            'zone_top': zone_top,
            'zone_bottom': zone_bottom
        }
    elif position_pct <= 25:
        return {
            'status': 'AT_BOTTOM',
            'bias': 'PUTS',
            'action': 'VIX at BOTTOM → bounces → SPX DOWN',
            'entry_rail': 'ascending (▲)',
            'exit_target': f'Exit at VIX {zone_top:.2f}',
            'position_pct': position_pct,
            'zones_above': zones_above,
            'zones_below': zones_below,
            'zone_top': zone_top,
            'zone_bottom': zone_bottom
        }
    else:
        return {
            'status': 'MID_ZONE',
            'bias': 'WAIT',
            'action': 'VIX mid-zone → wait for edge',
            'entry_rail': 'wait',
            'exit_target': 'Wait for VIX extremes',
            'position_pct': position_pct,
            'zones_above': zones_above,
            'zones_below': zones_below,
            'zone_top': zone_top,
            'zone_bottom': zone_bottom
        }

# ============================================================================
# CONFLUENCE CHECK
# ============================================================================

def check_confluence(vix_analysis: dict, rail_type: str, distance: float) -> dict:
    """Check SPX-VIX confluence for trade validity"""
    
    checks = []
    
    # 1. At Rail
    if distance <= 3:
        checks.append(('At Rail', True, f'{distance:.1f} pts - Excellent'))
    elif distance <= 5:
        checks.append(('At Rail', True, f'{distance:.1f} pts - Good'))
    elif distance <= 8:
        checks.append(('At Rail', True, f'{distance:.1f} pts - OK'))
    else:
        checks.append(('At Rail', False, f'{distance:.1f} pts - Too far'))
    
    # 2. VIX Confluence
    vix_bias = vix_analysis.get('bias', 'UNKNOWN')
    vix_status = vix_analysis.get('status', 'NO_DATA')
    
    if rail_type == 'descending':  # CALLS
        if vix_bias == 'CALLS':
            checks.append(('VIX Confluence', True, 'VIX at TOP/broke down'))
        elif vix_bias == 'WAIT':
            checks.append(('VIX Confluence', False, 'VIX mid-zone'))
        else:
            checks.append(('VIX Confluence', False, 'VIX favors PUTS'))
    else:  # PUTS
        if vix_bias == 'PUTS':
            checks.append(('VIX Confluence', True, 'VIX at BOTTOM/broke up'))
        elif vix_bias == 'WAIT':
            checks.append(('VIX Confluence', False, 'VIX mid-zone'))
        else:
            checks.append(('VIX Confluence', False, 'VIX favors CALLS'))
    
    # 3. 30-min Close (user must verify)
    checks.append(('30-Min Close', None, 'Verify candle closed'))
    
    passed = sum(1 for _, p, _ in checks if p == True)
    total = sum(1 for _, p, _ in checks if p is not None)
    
    return {
        'checks': checks,
        'passed': passed,
        'total': total,
        'go': passed >= total
    }

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet Pro",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    inject_css()
    
    # Session state initialization
    if 'vix_zone_bottom' not in st.session_state:
        st.session_state.vix_zone_bottom = 0.0
        st.session_state.vix_zone_top = 0.0
        st.session_state.vix_current = 0.0
        st.session_state.es_offset = 8.0
    
    ct_now = get_ct_now()
    
    # ========================================================================
    # SIDEBAR
    # ========================================================================
    with st.sidebar:
        st.markdown("# ⚡ SPX Prophet")
        st.markdown("---")
        
        # Date Selection
        st.markdown("### 📅 Session")
        session_date = st.date_input("Date", value=ct_now.date(), label_visibility="collapsed")
        session_date = datetime.combine(session_date, time(0, 0))
        
        # Fetch data
        prior = fetch_prior_session(session_date)
        spx_price = fetch_spx_price() or (prior['close'] if prior else 6000)
        
        st.markdown("---")
        
        # VIX Zone Inputs
        st.markdown("### 🎯 VIX Zone (5pm-2am)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.vix_zone_bottom = st.number_input(
                "Bottom", 
                value=st.session_state.vix_zone_bottom,
                step=0.01, format="%.2f",
                help="Overnight LOW"
            )
        with col2:
            st.session_state.vix_zone_top = st.number_input(
                "Top",
                value=st.session_state.vix_zone_top,
                step=0.01, format="%.2f",
                help="Overnight HIGH"
            )
        
        st.session_state.vix_current = st.number_input(
            "Current VIX",
            value=st.session_state.vix_current,
            step=0.01, format="%.2f",
            help="Live from TradingView"
        )
        
        # Zone validation
        if st.session_state.vix_zone_top > 0 and st.session_state.vix_zone_bottom > 0:
            zone_size = st.session_state.vix_zone_top - st.session_state.vix_zone_bottom
            if 0.13 <= zone_size <= 0.17:
                st.success(f"✓ Perfect zone: {zone_size:.2f}")
            else:
                zones = round(zone_size / 0.15)
                st.info(f"Zone = {zones} level(s)")
        
        # VIX Analysis
        vix_analysis = None
        if st.session_state.vix_zone_bottom > 0 and st.session_state.vix_zone_top > 0:
            vix_analysis = analyze_vix_zone(
                st.session_state.vix_zone_bottom,
                st.session_state.vix_zone_top,
                st.session_state.vix_current
            )
            
            # Signal Display
            st.markdown("---")
            bias = vix_analysis['bias']
            if bias == 'CALLS':
                st.markdown(f"""
                <div style="background:#d1fae5;border:2px solid #10b981;border-radius:8px;padding:10px;text-align:center;">
                    <div style="font-size:24px;">🟢</div>
                    <div style="font-weight:700;color:#047857;font-size:16px;">CALLS</div>
                    <div style="font-size:10px;color:#065f46;">{vix_analysis['action']}</div>
                </div>
                """, unsafe_allow_html=True)
            elif bias == 'PUTS':
                st.markdown(f"""
                <div style="background:#fee2e2;border:2px solid #ef4444;border-radius:8px;padding:10px;text-align:center;">
                    <div style="font-size:24px;">🔴</div>
                    <div style="font-weight:700;color:#b91c1c;font-size:16px;">PUTS</div>
                    <div style="font-size:10px;color:#7f1d1d;">{vix_analysis['action']}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background:#fef3c7;border:2px solid #f59e0b;border-radius:8px;padding:10px;text-align:center;">
                    <div style="font-size:24px;">🟡</div>
                    <div style="font-weight:700;color:#92400e;font-size:16px;">WAIT</div>
                    <div style="font-size:10px;color:#78350f;">{vix_analysis['action']}</div>
                </div>
                """, unsafe_allow_html=True)
            
            if vix_analysis['exit_target']:
                st.caption(f"🎯 {vix_analysis['exit_target']}")
            
            # Zone Ladder
            st.markdown("---")
            st.markdown("**Zone Ladder**")
            
            ladder_html = '<div class="zone-ladder">'
            for i in range(3, -1, -1):
                ladder_html += f'<div class="zone-row">+{i+1}: {vix_analysis["zones_above"][i]:.2f}</div>'
            ladder_html += f'<div class="zone-row-highlight zone-top">TOP: {vix_analysis["zone_top"]:.2f} ←CALLS</div>'
            if vix_analysis['status'] not in ['BREAKOUT_UP', 'BREAKOUT_DOWN'] and st.session_state.vix_current > 0:
                ladder_html += f'<div class="zone-row-highlight zone-now">NOW: {st.session_state.vix_current:.2f} ({vix_analysis["position_pct"]:.0f}%)</div>'
            ladder_html += f'<div class="zone-row-highlight zone-bot">BOT: {vix_analysis["zone_bottom"]:.2f} ←PUTS</div>'
            for i in range(4):
                ladder_html += f'<div class="zone-row">-{i+1}: {vix_analysis["zones_below"][i]:.2f}</div>'
            ladder_html += '</div>'
            st.markdown(ladder_html, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # ES Offset
        st.markdown("### 🔧 ES → SPX")
        st.session_state.es_offset = st.number_input(
            "Offset",
            value=st.session_state.es_offset,
            step=0.25, format="%.2f",
            help="ES - SPX difference"
        )
    
    # ========================================================================
    # MAIN CONTENT
    # ========================================================================
    
    # Header
    st.markdown(f"""
    <div class="main-header">
        <div class="main-title">SPX Prophet Pro</div>
        <div class="main-subtitle">SPX-VIX Confluence Trading System</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Warning about 30-min close
    st.markdown("""
    <div class="warning-box">
        ⚠️ <strong>30-MINUTE CANDLE CLOSE MATTERS</strong> — VIX wicks can pierce levels. 
        Wait for the candle to CLOSE to confirm rejection/bounce before entering.
    </div>
    """, unsafe_allow_html=True)
    
    # Metrics Row
    market_status = "LIVE" if time(8, 30) <= ct_now.time() <= time(15, 0) else "CLOSED"
    st.markdown(f"""
    <div class="metrics-row">
        <div class="metric-box">
            <div class="metric-label">SPX</div>
            <div class="metric-value">{spx_price:,.2f}</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Time (CT)</div>
            <div class="metric-value">{ct_now.strftime('%H:%M')}</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Market</div>
            <div class="metric-value">{market_status}</div>
        </div>
        <div class="metric-box">
            <div class="metric-label">Session</div>
            <div class="metric-value">{session_date.strftime('%m/%d')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Calculate cones
    target_time = ct_now.time() if session_date.date() == ct_now.date() else time(10, 0)
    if target_time < time(8, 30):
        target_time = time(10, 0)
    
    cones = calculate_cones(prior, session_date, target_time)
    
    if not cones or not prior:
        st.error("Unable to fetch market data. Please check your connection.")
        return
    
    # Main Signal Display
    if vix_analysis and vix_analysis['bias'] != 'UNKNOWN':
        nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(spx_price, cones)
        
        # Determine trade direction based on nearest rail
        if nearest_rail_type == 'descending':
            trade_dir = 'CALLS'
            trade_color = '#10b981'
        else:
            trade_dir = 'PUTS'
            trade_color = '#ef4444'
        
        # Check confluence
        confluence = check_confluence(vix_analysis, nearest_rail_type, nearest_distance)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Signal Box
            bias = vix_analysis['bias']
            if bias == 'CALLS' and confluence['go']:
                st.markdown(f"""
                <div class="signal-box signal-calls">
                    <div class="signal-icon">🟢</div>
                    <div class="signal-text" style="color:#047857;">CALLS SIGNAL</div>
                    <div class="signal-sub">VIX at TOP + SPX at descending rail</div>
                </div>
                """, unsafe_allow_html=True)
            elif bias == 'PUTS' and confluence['go']:
                st.markdown(f"""
                <div class="signal-box signal-puts">
                    <div class="signal-icon">🔴</div>
                    <div class="signal-text" style="color:#b91c1c;">PUTS SIGNAL</div>
                    <div class="signal-sub">VIX at BOTTOM + SPX at ascending rail</div>
                </div>
                """, unsafe_allow_html=True)
            elif bias == 'WAIT':
                st.markdown(f"""
                <div class="signal-box signal-wait">
                    <div class="signal-icon">🟡</div>
                    <div class="signal-text" style="color:#92400e;">WAIT</div>
                    <div class="signal-sub">VIX in mid-zone — no clear direction</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="signal-box signal-wait">
                    <div class="signal-icon">⚠️</div>
                    <div class="signal-text" style="color:#92400e;">NO CONFLUENCE</div>
                    <div class="signal-sub">VIX ({bias}) doesn't match SPX position ({trade_dir})</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            # Checklist
            st.markdown('<div class="info-card-title">Confluence Check</div>', unsafe_allow_html=True)
            for name, passed, detail in confluence['checks']:
                if passed is True:
                    st.markdown(f"""
                    <div class="checklist-item checklist-pass">
                        <span class="checklist-icon">✓</span>
                        <span class="checklist-text">{name}</span>
                        <span class="checklist-detail">{detail}</span>
                    </div>
                    """, unsafe_allow_html=True)
                elif passed is False:
                    st.markdown(f"""
                    <div class="checklist-item checklist-fail">
                        <span class="checklist-icon">✗</span>
                        <span class="checklist-text">{name}</span>
                        <span class="checklist-detail">{detail}</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="checklist-item" style="background:#f5f5f5;">
                        <span class="checklist-icon">⏳</span>
                        <span class="checklist-text">{name}</span>
                        <span class="checklist-detail">{detail}</span>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="signal-box" style="background:#f5f5f5;border:2px dashed #ccc;">
            <div class="signal-icon">📊</div>
            <div class="signal-text" style="color:#666;">Enter VIX Zone</div>
            <div class="signal-sub">Add VIX overnight zone in sidebar to see signals</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Trade Setups
    st.markdown("### 📍 Trade Setups at 10:00 AM")
    
    cones_10am = calculate_cones(prior, session_date, time(10, 0))
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### CALLS — Descending Rails (▼)")
        for cone in cones_10am:
            entry = cone.descending_rail
            target = cone.ascending_rail
            room = target - entry
            
            # Check if this is the active setup
            dist_from_price = abs(spx_price - entry)
            is_near = dist_from_price <= 15
            
            st.markdown(f"""
            <div class="setup-card setup-calls" {'style="border-width:3px;box-shadow:0 2px 8px rgba(16,185,129,0.2);"' if is_near else ''}>
                <div class="setup-header">
                    <span class="setup-title">{cone.name} Cone</span>
                    <span class="setup-badge badge-calls">CALLS</span>
                </div>
                <div class="setup-grid">
                    <div class="setup-item">
                        <label>Entry</label>
                        <value>{entry:,.2f}</value>
                    </div>
                    <div class="setup-item">
                        <label>Target</label>
                        <value>{target:,.2f}</value>
                    </div>
                    <div class="setup-item">
                        <label>Room</label>
                        <value>{room:,.0f} pts</value>
                    </div>
                </div>
                {f'<div style="margin-top:8px;font-size:11px;color:#059669;">📍 {dist_from_price:.0f} pts away</div>' if is_near else ''}
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### PUTS — Ascending Rails (▲)")
        for cone in cones_10am:
            entry = cone.ascending_rail
            target = cone.descending_rail
            room = entry - target
            
            dist_from_price = abs(spx_price - entry)
            is_near = dist_from_price <= 15
            
            st.markdown(f"""
            <div class="setup-card setup-puts" {'style="border-width:3px;box-shadow:0 2px 8px rgba(239,68,68,0.2);"' if is_near else ''}>
                <div class="setup-header">
                    <span class="setup-title">{cone.name} Cone</span>
                    <span class="setup-badge badge-puts">PUTS</span>
                </div>
                <div class="setup-grid">
                    <div class="setup-item">
                        <label>Entry</label>
                        <value>{entry:,.2f}</value>
                    </div>
                    <div class="setup-item">
                        <label>Target</label>
                        <value>{target:,.2f}</value>
                    </div>
                    <div class="setup-item">
                        <label>Room</label>
                        <value>{room:,.0f} pts</value>
                    </div>
                </div>
                {f'<div style="margin-top:8px;font-size:11px;color:#dc2626;">📍 {dist_from_price:.0f} pts away</div>' if is_near else ''}
            </div>
            """, unsafe_allow_html=True)
    
    # Prior Session Info
    st.markdown("---")
    st.markdown("### 📊 Prior Session Pivots")
    
    if prior:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("High", f"{prior['high']:,.2f}")
        with c2:
            st.metric("Low", f"{prior['low']:,.2f}")
        with c3:
            st.metric("Close", f"{prior['close']:,.2f}")
    
    # Footer
    st.markdown("---")
    st.caption(f"SPX Prophet Pro • {ct_now.strftime('%Y-%m-%d %H:%M:%S CT')} • Data from Yahoo Finance")

if __name__ == "__main__":
    main()
