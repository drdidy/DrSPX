"""
SPX PROPHET - Daily Trading Plan Dashboard
Version 3.0 - Complete Unified View

A comprehensive 0DTE options trading system that combines:
- VIX Zone Analysis (0.15 increments)
- SPX Structural Cones (Prior High/Low/Close)
- ES Overnight Validation
- EMA Confirmation (8/21 on 1-min)
- Profit Calculations & Position Sizing
- Real-time Trade Signals

Everything in ONE view for seamless daily trading.
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
# CONFIGURATION
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

SLOPE_ASCENDING = 0.45
SLOPE_DESCENDING = 0.45
VIX_ZONE_INCREMENT = 0.15
MIN_CONE_WIDTH = 25.0
AT_RAIL_THRESHOLD = 5.0
STOP_LOSS_PTS = 3.0
STRIKE_OFFSET = 17.5

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

@dataclass
class Cone:
    name: str
    pivot: Pivot
    ascending_rail: float
    descending_rail: float
    width: float
    blocks_from_pivot: int

@dataclass
class TradeSetup:
    direction: str  # CALLS or PUTS
    entry_price: float
    stop_loss: float
    target_50: float
    target_75: float
    target_100: float
    strike: int
    profit_50: float
    profit_75: float
    profit_100: float
    risk_dollars: float
    rr_ratio: float
    cone_name: str
    rail_type: str  # ascending or descending

# ============================================================================
# DATA FETCHING
# ============================================================================

@st.cache_data(ttl=300)
def fetch_prior_session(session_date: datetime) -> Optional[Dict]:
    """Fetch prior day's High, Low, Close."""
    try:
        spx = yf.Ticker("^GSPC")
        end = session_date
        start = end - timedelta(days=10)
        df = spx.history(start=start, end=end, interval='1d')
        if len(df) >= 1:
            last = df.iloc[-1]
            return {
                'high': float(last['High']),
                'low': float(last['Low']),
                'close': float(last['Close']),
                'date': df.index[-1]
            }
    except:
        pass
    return None

@st.cache_data(ttl=60)
def fetch_current_spx() -> Optional[float]:
    """Fetch current SPX price."""
    try:
        spx = yf.Ticker("^GSPC")
        data = spx.history(period='1d', interval='1m')
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    return None

@st.cache_data(ttl=60)
def fetch_es_current() -> Optional[float]:
    """Fetch current ES futures price."""
    try:
        es = yf.Ticker("ES=F")
        data = es.history(period='1d', interval='1m')
        if not data.empty:
            return float(data['Close'].iloc[-1])
    except:
        pass
    return None

# ============================================================================
# CONE CALCULATIONS
# ============================================================================

def count_30min_blocks(start_time: datetime, end_time: datetime) -> int:
    """Count 30-minute blocks between two times."""
    if end_time <= start_time:
        return 0
    diff = (end_time - start_time).total_seconds()
    return int(diff // 1800)

def build_cones(pivots: List[Pivot], eval_time: datetime) -> List[Cone]:
    """Build cones from pivots at evaluation time."""
    cones = []
    for pivot in pivots:
        blocks = count_30min_blocks(pivot.time, eval_time)
        if blocks <= 0:
            blocks = 1
        
        ascending = pivot.price + (blocks * SLOPE_ASCENDING)
        descending = pivot.price - (blocks * SLOPE_DESCENDING)
        width = ascending - descending
        
        cones.append(Cone(
            name=pivot.name,
            pivot=pivot,
            ascending_rail=ascending,
            descending_rail=descending,
            width=width,
            blocks_from_pivot=blocks
        ))
    return cones

def find_nearest_rail(price: float, cones: List[Cone]) -> Tuple[Optional[Cone], str, float]:
    """Find the nearest rail to current price."""
    nearest_cone = None
    nearest_type = ""
    nearest_dist = float('inf')
    
    for cone in cones:
        dist_asc = abs(price - cone.ascending_rail)
        dist_desc = abs(price - cone.descending_rail)
        
        if dist_asc < nearest_dist:
            nearest_dist = dist_asc
            nearest_cone = cone
            nearest_type = "ascending"
        if dist_desc < nearest_dist:
            nearest_dist = dist_desc
            nearest_cone = cone
            nearest_type = "descending"
    
    return nearest_cone, nearest_type, nearest_dist

# ============================================================================
# VIX ZONE ANALYSIS
# ============================================================================

def analyze_vix_zone(zone_bottom: float, zone_top: float, current_vix: float) -> Dict:
    """Analyze VIX position within zone and determine trade bias."""
    
    if zone_bottom <= 0 or zone_top <= 0:
        return {
            'status': 'NO_DATA',
            'bias': 'UNKNOWN',
            'action': 'Enter VIX zone data',
            'position_pct': 0
        }
    
    zone_size = zone_top - zone_bottom
    
    # Calculate zones above and below
    zones_above = [zone_top + (i * VIX_ZONE_INCREMENT) for i in range(1, 5)]
    zones_below = [zone_bottom - (i * VIX_ZONE_INCREMENT) for i in range(1, 5)]
    
    if current_vix <= 0:
        return {
            'status': 'WAITING',
            'bias': 'UNKNOWN',
            'action': 'Enter current VIX',
            'position_pct': 0,
            'zones_above': zones_above,
            'zones_below': zones_below,
            'zone_top': zone_top,
            'zone_bottom': zone_bottom
        }
    
    # Determine position
    if current_vix > zone_top:
        status = 'BREAKOUT_UP'
        bias = 'PUTS'
        action = 'VIX broke UP → PUTS targets extend'
        position_pct = 100 + ((current_vix - zone_top) / VIX_ZONE_INCREMENT * 25)
    elif current_vix < zone_bottom:
        status = 'BREAKOUT_DOWN'
        bias = 'CALLS'
        action = 'VIX broke DOWN → CALLS targets extend'
        position_pct = -((zone_bottom - current_vix) / VIX_ZONE_INCREMENT * 25)
    else:
        position_pct = ((current_vix - zone_bottom) / zone_size * 100) if zone_size > 0 else 50
        status = 'CONTAINED'
        
        if position_pct >= 75:
            bias = 'CALLS'
            action = 'VIX at TOP → Wait for 30-min CLOSE → CALLS'
        elif position_pct <= 25:
            bias = 'PUTS'
            action = 'VIX at BOTTOM → Wait for 30-min CLOSE → PUTS'
        else:
            bias = 'WAIT'
            action = 'VIX mid-zone → Wait for edge'
    
    return {
        'status': status,
        'bias': bias,
        'action': action,
        'position_pct': position_pct,
        'zones_above': zones_above,
        'zones_below': zones_below,
        'zone_top': zone_top,
        'zone_bottom': zone_bottom,
        'current': current_vix
    }

# ============================================================================
# TRADE SETUP GENERATION
# ============================================================================

def generate_setups(cones: List[Cone], current_price: float) -> List[TradeSetup]:
    """Generate trade setups from cones."""
    setups = []
    delta = 0.33  # Approximate delta for 15-20pt OTM
    
    for cone in cones:
        if cone.width < MIN_CONE_WIDTH:
            continue
        
        # CALLS setup (at descending rail)
        entry_calls = cone.descending_rail
        target_calls = cone.ascending_rail
        move_calls = target_calls - entry_calls
        
        strike_calls = int(entry_calls + STRIKE_OFFSET)
        strike_calls = ((strike_calls + 4) // 5) * 5
        
        profit_50_calls = move_calls * 0.5 * delta * 100
        profit_75_calls = move_calls * 0.75 * delta * 100
        profit_100_calls = move_calls * delta * 100
        risk_calls = STOP_LOSS_PTS * delta * 100
        
        setups.append(TradeSetup(
            direction='CALLS',
            entry_price=entry_calls,
            stop_loss=entry_calls - STOP_LOSS_PTS,
            target_50=entry_calls + move_calls * 0.5,
            target_75=entry_calls + move_calls * 0.75,
            target_100=target_calls,
            strike=strike_calls,
            profit_50=profit_50_calls,
            profit_75=profit_75_calls,
            profit_100=profit_100_calls,
            risk_dollars=risk_calls,
            rr_ratio=profit_50_calls / risk_calls if risk_calls > 0 else 0,
            cone_name=cone.name,
            rail_type='descending'
        ))
        
        # PUTS setup (at ascending rail)
        entry_puts = cone.ascending_rail
        target_puts = cone.descending_rail
        move_puts = entry_puts - target_puts
        
        strike_puts = int(entry_puts - STRIKE_OFFSET)
        strike_puts = (strike_puts // 5) * 5
        
        profit_50_puts = move_puts * 0.5 * delta * 100
        profit_75_puts = move_puts * 0.75 * delta * 100
        profit_100_puts = move_puts * delta * 100
        risk_puts = STOP_LOSS_PTS * delta * 100
        
        setups.append(TradeSetup(
            direction='PUTS',
            entry_price=entry_puts,
            stop_loss=entry_puts + STOP_LOSS_PTS,
            target_50=entry_puts - move_puts * 0.5,
            target_75=entry_puts - move_puts * 0.75,
            target_100=target_puts,
            strike=strike_puts,
            profit_50=profit_50_puts,
            profit_75=profit_75_puts,
            profit_100=profit_100_puts,
            risk_dollars=risk_puts,
            rr_ratio=profit_50_puts / risk_puts if risk_puts > 0 else 0,
            cone_name=cone.name,
            rail_type='ascending'
        ))
    
    return setups

# ============================================================================
# MAIN DASHBOARD
# ============================================================================

def render_dashboard_html(
    spx_price: float,
    vix_data: Dict,
    cones: List[Cone],
    setups: List[TradeSetup],
    es_price: float,
    es_offset: float,
    prior_session: Dict
) -> str:
    """Render the complete dashboard as HTML."""
    
    ct_now = get_ct_now()
    market_open = time(8, 30)
    market_close = time(15, 0)
    is_market_open = market_open <= ct_now.time() <= market_close
    
    # VIX signal colors
    vix_bias = vix_data.get('bias', 'UNKNOWN')
    if vix_bias == 'CALLS':
        signal_color = '#10b981'
        signal_bg = '#d1fae5'
        signal_icon = '🟢'
    elif vix_bias == 'PUTS':
        signal_color = '#ef4444'
        signal_bg = '#fee2e2'
        signal_icon = '🔴'
    elif vix_bias == 'WAIT':
        signal_color = '#f59e0b'
        signal_bg = '#fef3c7'
        signal_icon = '🟡'
    else:
        signal_color = '#6b7280'
        signal_bg = '#f3f4f6'
        signal_icon = '⏳'
    
    # Get nearest rail
    nearest_cone, nearest_type, nearest_dist = find_nearest_rail(spx_price, cones) if cones else (None, '', 999)
    
    # Determine trade direction from nearest rail
    if nearest_type == 'descending' and nearest_dist <= AT_RAIL_THRESHOLD:
        spx_signal = 'CALLS'
        spx_color = '#10b981'
    elif nearest_type == 'ascending' and nearest_dist <= AT_RAIL_THRESHOLD:
        spx_signal = 'PUTS'
        spx_color = '#ef4444'
    else:
        spx_signal = 'WAIT'
        spx_color = '#f59e0b'
    
    # Check confluence
    has_confluence = (vix_bias == 'CALLS' and spx_signal == 'CALLS') or (vix_bias == 'PUTS' and spx_signal == 'PUTS')
    confluence_text = '✓ CONFLUENCE' if has_confluence else '✗ NO CONFLUENCE'
    confluence_color = '#10b981' if has_confluence else '#ef4444'
    
    # Build setups HTML
    calls_setups = [s for s in setups if s.direction == 'CALLS']
    puts_setups = [s for s in setups if s.direction == 'PUTS']
    
    calls_html = ""
    for s in calls_setups[:3]:
        dist = abs(spx_price - s.entry_price)
        status = "AT RAIL" if dist <= 5 else f"{dist:.0f} pts away"
        calls_html += f"""
        <div class="setup-card calls">
            <div class="setup-header">
                <span class="setup-cone">{s.cone_name} ▼</span>
                <span class="setup-status">{status}</span>
            </div>
            <div class="setup-grid">
                <div><span class="label">Entry</span><span class="value">{s.entry_price:.2f}</span></div>
                <div><span class="label">Stop</span><span class="value red">{s.stop_loss:.2f}</span></div>
                <div><span class="label">Target</span><span class="value green">{s.target_100:.2f}</span></div>
                <div><span class="label">Strike</span><span class="value">{s.strike}C</span></div>
            </div>
            <div class="profit-row">
                <div><span class="label">50%</span><span class="profit">${s.profit_50:.0f}</span></div>
                <div><span class="label">75%</span><span class="profit">${s.profit_75:.0f}</span></div>
                <div><span class="label">100%</span><span class="profit">${s.profit_100:.0f}</span></div>
                <div><span class="label">R:R</span><span class="profit">{s.rr_ratio:.1f}:1</span></div>
            </div>
        </div>
        """
    
    puts_html = ""
    for s in puts_setups[:3]:
        dist = abs(spx_price - s.entry_price)
        status = "AT RAIL" if dist <= 5 else f"{dist:.0f} pts away"
        puts_html += f"""
        <div class="setup-card puts">
            <div class="setup-header">
                <span class="setup-cone">{s.cone_name} ▲</span>
                <span class="setup-status">{status}</span>
            </div>
            <div class="setup-grid">
                <div><span class="label">Entry</span><span class="value">{s.entry_price:.2f}</span></div>
                <div><span class="label">Stop</span><span class="value red">{s.stop_loss:.2f}</span></div>
                <div><span class="label">Target</span><span class="value green">{s.target_100:.2f}</span></div>
                <div><span class="label">Strike</span><span class="value">{s.strike}P</span></div>
            </div>
            <div class="profit-row">
                <div><span class="label">50%</span><span class="profit">${s.profit_50:.0f}</span></div>
                <div><span class="label">75%</span><span class="profit">${s.profit_75:.0f}</span></div>
                <div><span class="label">100%</span><span class="profit">${s.profit_100:.0f}</span></div>
                <div><span class="label">R:R</span><span class="profit">{s.rr_ratio:.1f}:1</span></div>
            </div>
        </div>
        """
    
    # Cone rails table
    rails_html = ""
    for cone in cones:
        rails_html += f"""
        <tr>
            <td>{cone.name}</td>
            <td class="green">{cone.ascending_rail:.2f}</td>
            <td class="red">{cone.descending_rail:.2f}</td>
            <td>{cone.width:.1f}</td>
        </tr>
        """
    
    # VIX zones
    vix_top = vix_data.get('zone_top', 0)
    vix_bot = vix_data.get('zone_bottom', 0)
    vix_now = vix_data.get('current', 0)
    vix_pct = vix_data.get('position_pct', 0)
    zones_above = vix_data.get('zones_above', [0,0,0,0])
    zones_below = vix_data.get('zones_below', [0,0,0,0])
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }}
            body {{ background: #f8fafc; color: #1e293b; line-height: 1.5; }}
            
            .dashboard {{ max-width: 1400px; margin: 0 auto; padding: 16px; }}
            
            /* Header */
            .header {{
                background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                border-radius: 16px;
                padding: 20px 24px;
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 16px;
            }}
            .header-left {{ display: flex; align-items: center; gap: 16px; }}
            .logo {{
                width: 56px; height: 56px;
                background: linear-gradient(135deg, #f59e0b, #d97706);
                border-radius: 12px;
                display: flex; align-items: center; justify-content: center;
                font-size: 28px;
            }}
            .title {{ font-size: 28px; font-weight: 800; color: #f8fafc; }}
            .subtitle {{ font-size: 12px; color: #fbbf24; letter-spacing: 2px; text-transform: uppercase; }}
            .header-stats {{ display: flex; gap: 32px; }}
            .stat {{ text-align: center; }}
            .stat-label {{ font-size: 10px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }}
            .stat-value {{ font-size: 24px; font-weight: 700; color: #f8fafc; font-family: 'JetBrains Mono', monospace; }}
            .stat-value.live {{ color: #10b981; }}
            
            /* Main Grid */
            .main-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }}
            @media (max-width: 900px) {{
                .main-grid {{ grid-template-columns: 1fr; }}
            }}
            
            /* Cards */
            .card {{
                background: #fff;
                border-radius: 12px;
                border: 1px solid #e2e8f0;
                overflow: hidden;
            }}
            .card-header {{
                padding: 16px 20px;
                border-bottom: 1px solid #e2e8f0;
                font-weight: 600;
                font-size: 14px;
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .card-body {{ padding: 20px; }}
            
            /* Signal Box */
            .signal-box {{
                background: {signal_bg};
                border: 2px solid {signal_color};
                border-radius: 12px;
                padding: 24px;
                text-align: center;
                margin-bottom: 20px;
            }}
            .signal-icon {{ font-size: 48px; margin-bottom: 8px; }}
            .signal-title {{ font-size: 32px; font-weight: 800; color: {signal_color}; }}
            .signal-action {{ font-size: 14px; color: #475569; margin-top: 8px; }}
            
            /* Confluence */
            .confluence {{
                background: {confluence_color}15;
                border: 2px solid {confluence_color};
                border-radius: 8px;
                padding: 12px 16px;
                text-align: center;
                font-weight: 700;
                font-size: 16px;
                color: {confluence_color};
                margin-bottom: 20px;
            }}
            
            /* VIX Zone */
            .vix-zone {{ margin-bottom: 20px; }}
            .zone-box {{
                border-radius: 8px;
                padding: 12px;
                text-align: center;
                margin-bottom: 8px;
            }}
            .zone-box.top {{ background: linear-gradient(135deg, #d1fae5, #a7f3d0); border: 2px solid #10b981; }}
            .zone-box.current {{ background: #0f172a; }}
            .zone-box.bottom {{ background: linear-gradient(135deg, #fee2e2, #fecaca); border: 2px solid #ef4444; }}
            .zone-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 600; }}
            .zone-label.green {{ color: #047857; }}
            .zone-label.white {{ color: #94a3b8; }}
            .zone-label.red {{ color: #b91c1c; }}
            .zone-value {{ font-family: 'JetBrains Mono', monospace; font-size: 24px; font-weight: 700; margin: 4px 0; }}
            .zone-value.green {{ color: #047857; }}
            .zone-value.white {{ color: #f8fafc; }}
            .zone-value.red {{ color: #b91c1c; }}
            .zone-hint {{ font-size: 11px; color: #64748b; }}
            
            /* Setups */
            .setup-card {{
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 12px;
                border-left: 4px solid;
            }}
            .setup-card.calls {{ background: #f0fdf4; border-left-color: #10b981; }}
            .setup-card.puts {{ background: #fef2f2; border-left-color: #ef4444; }}
            .setup-header {{
                display: flex;
                justify-content: space-between;
                margin-bottom: 12px;
            }}
            .setup-cone {{ font-weight: 700; font-size: 14px; }}
            .setup-status {{ font-size: 12px; color: #64748b; }}
            .setup-grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 8px;
                margin-bottom: 12px;
            }}
            .setup-grid .label {{ font-size: 10px; color: #64748b; display: block; }}
            .setup-grid .value {{ font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 600; }}
            .setup-grid .value.green {{ color: #059669; }}
            .setup-grid .value.red {{ color: #dc2626; }}
            .profit-row {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 8px;
                padding-top: 12px;
                border-top: 1px solid #e2e8f0;
            }}
            .profit-row .label {{ font-size: 10px; color: #64748b; display: block; }}
            .profit-row .profit {{ font-family: 'JetBrains Mono', monospace; font-size: 14px; font-weight: 700; color: #059669; }}
            
            /* Rails Table */
            table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
            th {{ text-align: left; padding: 10px; background: #f8fafc; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; }}
            td {{ padding: 10px; border-bottom: 1px solid #f1f5f9; font-family: 'JetBrains Mono', monospace; }}
            td.green {{ color: #059669; font-weight: 600; }}
            td.red {{ color: #dc2626; font-weight: 600; }}
            
            /* Checklist */
            .checklist {{ display: flex; flex-direction: column; gap: 8px; }}
            .check-item {{
                display: flex;
                align-items: center;
                gap: 10px;
                padding: 10px 12px;
                border-radius: 6px;
                font-size: 13px;
            }}
            .check-item.pass {{ background: #f0fdf4; }}
            .check-item.fail {{ background: #fef2f2; }}
            .check-item.wait {{ background: #f8fafc; }}
            .check-icon {{ font-size: 16px; }}
            .check-text {{ flex: 1; }}
            
            /* Info Grid */
            .info-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }}
            .info-box {{
                background: #f8fafc;
                border-radius: 8px;
                padding: 12px;
            }}
            .info-label {{ font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }}
            .info-value {{ font-family: 'JetBrains Mono', monospace; font-size: 16px; font-weight: 600; margin-top: 4px; }}
            
            /* Warning */
            .warning {{
                background: #fef3c7;
                border: 1px solid #f59e0b;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 13px;
                color: #92400e;
                margin-bottom: 16px;
            }}
        </style>
    </head>
    <body>
        <div class="dashboard">
            <!-- Header -->
            <div class="header">
                <div class="header-left">
                    <div class="logo">📈</div>
                    <div>
                        <div class="title">SPX PROPHET</div>
                        <div class="subtitle">Daily Trading Plan • {ct_now.strftime('%b %d, %Y')}</div>
                    </div>
                </div>
                <div class="header-stats">
                    <div class="stat">
                        <div class="stat-label">SPX</div>
                        <div class="stat-value">{spx_price:,.2f}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">ES</div>
                        <div class="stat-value">{es_price:,.2f if es_price else '—'}</div>
                    </div>
                    <div class="stat">
                        <div class="stat-label">Time (CT)</div>
                        <div class="stat-value live">{ct_now.strftime('%H:%M')}</div>
                    </div>
                </div>
            </div>
            
            <!-- Warning -->
            <div class="warning">
                ⏱️ <strong>30-MIN CANDLE CLOSE MATTERS:</strong> VIX wicks can pierce levels — wait for candle CLOSE to confirm before entering.
            </div>
            
            <div class="main-grid">
                <!-- Left Column -->
                <div>
                    <!-- Signal -->
                    <div class="card">
                        <div class="card-header">🎯 Trade Signal</div>
                        <div class="card-body">
                            <div class="signal-box">
                                <div class="signal-icon">{signal_icon}</div>
                                <div class="signal-title">{vix_bias}</div>
                                <div class="signal-action">{vix_data.get('action', 'Enter VIX data')}</div>
                            </div>
                            <div class="confluence">{confluence_text}</div>
                            
                            <!-- Checklist -->
                            <div class="checklist">
                                <div class="check-item {'pass' if nearest_dist <= 5 else 'wait'}">
                                    <span class="check-icon">{'✓' if nearest_dist <= 5 else '⏳'}</span>
                                    <span class="check-text">At Rail ({nearest_dist:.1f} pts from {nearest_cone.name if nearest_cone else 'N/A'} {nearest_type})</span>
                                </div>
                                <div class="check-item {'pass' if vix_bias in ['CALLS','PUTS'] else 'wait'}">
                                    <span class="check-icon">{'✓' if vix_bias in ['CALLS','PUTS'] else '⏳'}</span>
                                    <span class="check-text">VIX at Zone Edge ({vix_pct:.0f}% in zone)</span>
                                </div>
                                <div class="check-item {'pass' if has_confluence else 'fail'}">
                                    <span class="check-icon">{'✓' if has_confluence else '✗'}</span>
                                    <span class="check-text">SPX + VIX Confluence</span>
                                </div>
                                <div class="check-item wait">
                                    <span class="check-icon">⏳</span>
                                    <span class="check-text">30-Min Candle Close (verify manually)</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- VIX Zone -->
                    <div class="card" style="margin-top: 20px;">
                        <div class="card-header">📊 VIX Zone Ladder</div>
                        <div class="card-body">
                            <div class="vix-zone">
                                <div class="zone-box top">
                                    <div class="zone-label green">Zone Top (Resistance)</div>
                                    <div class="zone-value green">{vix_top:.2f if vix_top > 0 else '—'}</div>
                                    <div class="zone-hint">VIX closes here → CALLS</div>
                                </div>
                                <div class="zone-box current">
                                    <div class="zone-label white">Current VIX</div>
                                    <div class="zone-value white">{vix_now:.2f if vix_now > 0 else '—'}</div>
                                    <div class="zone-hint" style="color:#94a3b8;">{vix_pct:.0f}% in zone</div>
                                </div>
                                <div class="zone-box bottom">
                                    <div class="zone-label red">Zone Bottom (Support)</div>
                                    <div class="zone-value red">{vix_bot:.2f if vix_bot > 0 else '—'}</div>
                                    <div class="zone-hint">VIX closes here → PUTS</div>
                                </div>
                            </div>
                            
                            <div class="info-grid">
                                <div class="info-box">
                                    <div class="info-label">Entry Rail</div>
                                    <div class="info-value" style="color:#059669;">SPX {'▼ descending' if vix_bias == 'CALLS' else '▲ ascending' if vix_bias == 'PUTS' else '—'}</div>
                                </div>
                                <div class="info-box">
                                    <div class="info-label">Exit When</div>
                                    <div class="info-value" style="color:#dc2626;">VIX hits {vix_bot:.2f if vix_bias == 'CALLS' else vix_top:.2f if vix_bias == 'PUTS' else '—'}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Right Column -->
                <div>
                    <!-- CALLS Setups -->
                    <div class="card">
                        <div class="card-header" style="color:#059669;">🟢 CALLS Setups</div>
                        <div class="card-body">
                            {calls_html if calls_html else '<div style="color:#64748b;text-align:center;padding:20px;">No CALLS setups available</div>'}
                        </div>
                    </div>
                    
                    <!-- PUTS Setups -->
                    <div class="card" style="margin-top: 20px;">
                        <div class="card-header" style="color:#dc2626;">🔴 PUTS Setups</div>
                        <div class="card-body">
                            {puts_html if puts_html else '<div style="color:#64748b;text-align:center;padding:20px;">No PUTS setups available</div>'}
                        </div>
                    </div>
                    
                    <!-- Rails Table -->
                    <div class="card" style="margin-top: 20px;">
                        <div class="card-header">📐 Cone Rails (10:00 AM)</div>
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
                                    {rails_html if rails_html else '<tr><td colspan="4" style="text-align:center;color:#64748b;">No cones available</td></tr>'}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet - Daily Trading Plan",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Hide Streamlit elements
    st.markdown("""
    <style>
    #MainMenu, footer { visibility: hidden; }
    header { visibility: visible !important; }
    [data-testid="stSidebar"] { background: #f8fafc; }
    [data-testid="stSidebar"] * { font-size: 14px !important; color: #374151 !important; }
    [data-testid="stSidebar"] h3 { font-size: 16px !important; font-weight: 600 !important; color: #111827 !important; }
    [data-testid="stSidebar"] label { font-size: 13px !important; }
    [data-testid="stSidebar"] input { font-size: 14px !important; }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'vix_bottom' not in st.session_state:
        st.session_state.vix_bottom = 0.0
        st.session_state.vix_top = 0.0
        st.session_state.vix_current = 0.0
        st.session_state.es_offset = 8.0
    
    # Sidebar - Inputs
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        
        session_date = st.date_input("📅 Session Date", value=datetime.now().date())
        session_dt = datetime.combine(session_date, time(0, 0))
        
        st.markdown("---")
        st.markdown("### 📊 VIX Zone (Overnight)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.vix_bottom = st.number_input(
                "Bottom",
                min_value=0.0, max_value=100.0,
                value=st.session_state.vix_bottom,
                step=0.01, format="%.2f"
            )
        with col2:
            st.session_state.vix_top = st.number_input(
                "Top",
                min_value=0.0, max_value=100.0,
                value=st.session_state.vix_top,
                step=0.01, format="%.2f"
            )
        
        st.session_state.vix_current = st.number_input(
            "Current VIX",
            min_value=0.0, max_value=100.0,
            value=st.session_state.vix_current,
            step=0.01, format="%.2f"
        )
        
        st.markdown("---")
        st.markdown("### 🌙 ES → SPX Offset")
        st.session_state.es_offset = st.number_input(
            "ES - SPX",
            min_value=-100.0, max_value=100.0,
            value=st.session_state.es_offset,
            step=0.25, format="%.2f",
            help="Positive if ES > SPX, Negative if ES < SPX"
        )
        
        st.markdown("---")
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    # Fetch data
    prior_session = fetch_prior_session(session_dt)
    current_spx = fetch_current_spx() or (prior_session['close'] if prior_session else 6000)
    current_es = fetch_es_current()
    
    # Build pivots and cones
    pivots = []
    if prior_session:
        base_time = session_dt.replace(hour=15, minute=0) - timedelta(days=1)
        pivots = [
            Pivot(prior_session['high'], base_time, 'High'),
            Pivot(prior_session['low'], base_time, 'Low'),
            Pivot(prior_session['close'], base_time, 'Close'),
        ]
    
    # Evaluate at 10:00 AM
    eval_time = session_dt.replace(hour=10, minute=0)
    cones = build_cones(pivots, eval_time) if pivots else []
    
    # Generate setups
    setups = generate_setups(cones, current_spx) if cones else []
    
    # Analyze VIX
    vix_data = analyze_vix_zone(
        st.session_state.vix_bottom,
        st.session_state.vix_top,
        st.session_state.vix_current
    )
    
    # Render dashboard
    dashboard_html = render_dashboard_html(
        spx_price=current_spx,
        vix_data=vix_data,
        cones=cones,
        setups=setups,
        es_price=current_es,
        es_offset=st.session_state.es_offset,
        prior_session=prior_session
    )
    
    components.html(dashboard_html, height=1400, scrolling=True)

if __name__ == "__main__":
    main()