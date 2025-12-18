"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           SPX PROPHET v2.0                                    ║
║                    Where Structure Becomes Foresight                          ║
║                         LEGENDARY EDITION                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

THE SYSTEM:
-----------
VIX moves in 0.15 zones set overnight (5pm-2am). These zones map directly to 
SPX cone rails. When VIX touches a zone boundary, SPX touches a rail.

VIX Zone TOP (resistance) → SPX Descending Rail → CALLS entry, PUTS exit
VIX Zone BOTTOM (support) → SPX Ascending Rail → PUTS entry, CALLS exit

When VIX breaks a zone, target extends by 0.15 (or multiples: 0.30, 0.45, 0.60)

THE INVERSE RELATIONSHIP:
-------------------------
VIX UP   → SPX DOWN
VIX DOWN → SPX UP

================================================================================
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
# CONFIGURATION
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')
VIX_ZONE_SIZE = 0.15  # The magic number

# Slopes for cone rails
SLOPE_ASCENDING = 0.45
SLOPE_DESCENDING = 0.45

# Trading thresholds
MIN_CONE_WIDTH = 18.0
AT_RAIL_THRESHOLD = 8.0
STOP_LOSS_PTS = 3.0
STRIKE_OFFSET = 17.5

# Time constants
POWER_HOUR_START = time(14, 0)
SECONDARY_PIVOT_MIN_DISTANCE = 5.0

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_ct_now() -> datetime:
    """Get current time in Central timezone."""
    return datetime.now(CT_TZ)

def get_time_block_index(dt: datetime, base_time: time = time(8, 30)) -> int:
    """Calculate 30-minute block index from base time."""
    base = dt.replace(hour=base_time.hour, minute=base_time.minute, second=0, microsecond=0)
    if dt < base:
        return 0
    diff = (dt - base).total_seconds()
    return int(diff // 1800)

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Pivot:
    price: float
    time: datetime
    name: str  # 'High', 'Low', 'Close', 'High²', 'Low²'

@dataclass
class Cone:
    pivot: Pivot
    name: str
    ascending_rail: float
    descending_rail: float
    
@dataclass 
class VIXZone:
    support: float          # Zone bottom
    resistance: float       # Zone top
    zone_size: float        # Should be ~0.15
    current: float          # Current VIX
    position_pct: float     # 0-100%
    trade_bias: str         # 'CALLS', 'PUTS', 'NEUTRAL'
    levels_above: List[float]
    levels_below: List[float]

@dataclass
class TradeSetup:
    direction: str          # 'CALLS' or 'PUTS'
    entry_price: float      # SPX rail price
    target_price: float     # Opposite rail
    stop_price: float       # 3 pts beyond entry
    cone_name: str
    rail_type: str          # 'ascending' or 'descending'
    vix_entry_zone: str     # 'resistance' or 'support'
    vix_exit_zone: str      # Opposite zone
    risk_pts: float
    reward_pts: float
    rr_ratio: float

# ============================================================================
# VIX ZONE CALCULATIONS
# ============================================================================

def calculate_vix_zones(support: float, resistance: float, current: float) -> VIXZone:
    """Calculate VIX zone structure with all levels."""
    zone_size = resistance - support
    
    # Calculate position percentage (0% = at support, 100% = at resistance)
    if zone_size > 0 and current > 0:
        position_pct = ((current - support) / zone_size) * 100
        position_pct = max(-50, min(150, position_pct))  # Allow some overflow
    else:
        position_pct = 50
    
    # Determine trade bias
    if current <= 0:
        trade_bias = "ENTER VIX"
    elif position_pct >= 70:
        trade_bias = "CALLS"
    elif position_pct <= 30:
        trade_bias = "PUTS"
    else:
        trade_bias = "NEUTRAL"
    
    # Calculate levels above (resistance breaks)
    levels_above = []
    for i in range(1, 5):
        levels_above.append(round(resistance + (VIX_ZONE_SIZE * i), 2))
    
    # Calculate levels below (support breaks)
    levels_below = []
    for i in range(1, 5):
        levels_below.append(round(support - (VIX_ZONE_SIZE * i), 2))
    
    return VIXZone(
        support=support,
        resistance=resistance,
        zone_size=zone_size,
        current=current,
        position_pct=position_pct,
        trade_bias=trade_bias,
        levels_above=levels_above,
        levels_below=levels_below
    )

def get_vix_zone_status(vix_zone: VIXZone) -> Tuple[str, str, str]:
    """Get zone status, entry rail, and exit rail."""
    if vix_zone.current <= 0:
        return "Enter VIX data", "N/A", "N/A"
    
    current = vix_zone.current
    
    # Check if broken above
    if current > vix_zone.resistance:
        zones_above = (current - vix_zone.resistance) / VIX_ZONE_SIZE
        target_zone = int(zones_above) + 1
        status = f"BREAKOUT ↑ Targeting +{target_zone} zone ({vix_zone.levels_above[min(target_zone-1, 3)]:.2f})"
        return status, "PUTS extending", "Wait for reversal"
    
    # Check if broken below
    if current < vix_zone.support:
        zones_below = (vix_zone.support - current) / VIX_ZONE_SIZE
        target_zone = int(zones_below) + 1
        status = f"BREAKOUT ↓ Targeting -{target_zone} zone ({vix_zone.levels_below[min(target_zone-1, 3)]:.2f})"
        return status, "CALLS extending", "Wait for reversal"
    
    # Within zone
    if vix_zone.position_pct >= 70:
        return "At RESISTANCE → CALLS entry zone", "Descending (▼)", "Ascending (▲)"
    elif vix_zone.position_pct <= 30:
        return "At SUPPORT → PUTS entry zone", "Ascending (▲)", "Descending (▼)"
    else:
        return "MID-ZONE → Wait for extremes", "Wait", "Wait"

# ============================================================================
# CONE CALCULATIONS
# ============================================================================

def calculate_rail_price(pivot_price: float, pivot_time: datetime, 
                         target_time: datetime, is_ascending: bool) -> float:
    """Calculate rail price at target time."""
    blocks = get_time_block_index(target_time) - get_time_block_index(pivot_time)
    slope = SLOPE_ASCENDING if is_ascending else -SLOPE_DESCENDING
    return pivot_price + (slope * blocks)

def create_cone(pivot: Pivot, target_time: datetime) -> Cone:
    """Create a cone from a pivot at target time."""
    ascending = calculate_rail_price(pivot.price, pivot.time, target_time, True)
    descending = calculate_rail_price(pivot.price, pivot.time, target_time, False)
    
    return Cone(
        pivot=pivot,
        name=pivot.name,
        ascending_rail=ascending,
        descending_rail=descending
    )

def find_nearest_rail(price: float, cones: List[Cone]) -> Tuple[Optional[Cone], str, float]:
    """Find the nearest rail to current price."""
    nearest_cone = None
    nearest_type = ''
    nearest_distance = float('inf')
    
    for cone in cones:
        # Check descending rail (support - CALLS entry)
        dist_desc = abs(price - cone.descending_rail)
        if dist_desc < nearest_distance:
            nearest_distance = dist_desc
            nearest_cone = cone
            nearest_type = 'descending'
        
        # Check ascending rail (resistance - PUTS entry)
        dist_asc = abs(price - cone.ascending_rail)
        if dist_asc < nearest_distance:
            nearest_distance = dist_asc
            nearest_cone = cone
            nearest_type = 'ascending'
    
    return nearest_cone, nearest_type, nearest_distance

# ============================================================================
# DATA FETCHING
# ============================================================================

@st.cache_data(ttl=300)
def fetch_prior_session_data(session_date: datetime) -> Optional[Dict]:
    """Fetch prior session pivot data."""
    try:
        prior_date = session_date - timedelta(days=1)
        while prior_date.weekday() >= 5:
            prior_date = prior_date - timedelta(days=1)
        
        spx = yf.Ticker("^GSPC")
        start_date = prior_date.strftime('%Y-%m-%d')
        end_date = (prior_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        df = spx.history(start=start_date, end=end_date, interval='30m')
        
        if df.empty:
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
            }
        
        df.index = df.index.tz_convert(CT_TZ)
        
        # Filter power hour for high
        df_before_power = df[df.index.time < POWER_HOUR_START]
        if not df_before_power.empty:
            high_idx = df_before_power['High'].idxmax()
        else:
            high_idx = df['High'].idxmax()
        
        low_idx = df['Low'].idxmin()
        
        # Get close-based low (commitment level)
        low_close_idx = df['Close'].idxmin()
        
        return {
            'date': prior_date,
            'high': df.loc[high_idx, 'High'],
            'high_time': high_idx,
            'low': df.loc[low_close_idx, 'Close'],  # Use close for low
            'low_time': low_close_idx,
            'close': df['Close'].iloc[-1],
        }
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return None

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

# ============================================================================
# TRADE SETUP GENERATION
# ============================================================================

def generate_trade_setups(cones: List[Cone], current_price: float, 
                          vix_zone: Optional[VIXZone]) -> List[TradeSetup]:
    """Generate trade setups from cones with VIX zone mapping."""
    setups = []
    
    for cone in cones:
        cone_width = cone.ascending_rail - cone.descending_rail
        if cone_width < MIN_CONE_WIDTH:
            continue
        
        # CALLS setup (descending rail entry)
        calls_entry = cone.descending_rail
        calls_target = cone.ascending_rail
        calls_stop = calls_entry - STOP_LOSS_PTS
        calls_reward = calls_target - calls_entry
        calls_risk = STOP_LOSS_PTS
        
        setups.append(TradeSetup(
            direction='CALLS',
            entry_price=calls_entry,
            target_price=calls_target,
            stop_price=calls_stop,
            cone_name=cone.name,
            rail_type='descending',
            vix_entry_zone='resistance',
            vix_exit_zone='support',
            risk_pts=calls_risk,
            reward_pts=calls_reward,
            rr_ratio=calls_reward / calls_risk if calls_risk > 0 else 0
        ))
        
        # PUTS setup (ascending rail entry)
        puts_entry = cone.ascending_rail
        puts_target = cone.descending_rail
        puts_stop = puts_entry + STOP_LOSS_PTS
        puts_reward = puts_entry - puts_target
        puts_risk = STOP_LOSS_PTS
        
        setups.append(TradeSetup(
            direction='PUTS',
            entry_price=puts_entry,
            target_price=puts_target,
            stop_price=puts_stop,
            cone_name=cone.name,
            rail_type='ascending',
            vix_entry_zone='support',
            vix_exit_zone='resistance',
            risk_pts=puts_risk,
            reward_pts=puts_reward,
            rr_ratio=puts_reward / puts_risk if puts_risk > 0 else 0
        ))
    
    return setups

# ============================================================================
# PREMIUM UI STYLES
# ============================================================================

def inject_premium_css():
    """Inject premium dark theme CSS."""
    st.markdown("""
    <style>
    /* Global Dark Theme */
    .stApp {
        background: linear-gradient(180deg, #0a0a0f 0%, #12121a 100%);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Premium Header */
    .prophet-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        border: 1px solid rgba(79, 172, 254, 0.3);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 24px;
        text-align: center;
        box-shadow: 0 8px 32px rgba(79, 172, 254, 0.15);
    }
    
    .prophet-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        letter-spacing: 4px;
    }
    
    .prophet-subtitle {
        color: #64748b;
        font-size: 0.85rem;
        letter-spacing: 3px;
        margin-top: 8px;
    }
    
    /* VIX Zone Panel */
    .vix-zone-panel {
        background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
        border: 2px solid rgba(139, 92, 246, 0.4);
        border-radius: 16px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px rgba(139, 92, 246, 0.2);
    }
    
    /* Trade Cards */
    .trade-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #252540 100%);
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        border-left: 4px solid;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    }
    
    .trade-card-calls {
        border-left-color: #10b981;
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, #1a1a2e 100%);
    }
    
    .trade-card-puts {
        border-left-color: #ef4444;
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, #1a1a2e 100%);
    }
    
    /* Checklist */
    .checklist-item {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        margin: 8px 0;
        border-radius: 8px;
        transition: all 0.2s ease;
    }
    
    .checklist-pass {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(16, 185, 129, 0.05) 100%);
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    
    .checklist-fail {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(239, 68, 68, 0.05) 100%);
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    
    /* Zone Ladder */
    .zone-ladder {
        background: #1a1a2e;
        border-radius: 12px;
        padding: 16px;
        font-family: 'SF Mono', 'Monaco', monospace;
    }
    
    .zone-level {
        display: flex;
        justify-content: space-between;
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 6px;
    }
    
    .zone-resistance {
        background: rgba(239, 68, 68, 0.2);
        border-left: 3px solid #ef4444;
    }
    
    .zone-support {
        background: rgba(16, 185, 129, 0.2);
        border-left: 3px solid #10b981;
    }
    
    .zone-current {
        background: rgba(59, 130, 246, 0.3);
        border: 2px solid #3b82f6;
        font-weight: bold;
    }
    
    /* Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #1e1e2e 0%, #2a2a3e 100%);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        font-family: 'SF Mono', monospace;
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 4px;
    }
    
    /* Signal Badge */
    .signal-badge {
        display: inline-block;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 1px;
    }
    
    .signal-calls {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
    }
    
    .signal-puts {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white;
        box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4);
    }
    
    .signal-neutral {
        background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
        color: white;
    }
    
    /* Progress Bar Override */
    .stProgress > div > div {
        background: linear-gradient(90deg, #10b981 0%, #fbbf24 50%, #ef4444 100%);
        border-radius: 10px;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0f1a 0%, #1a1a2e 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    [data-testid="stSidebar"] .stMarkdown h3 {
        color: #4facfe;
        border-bottom: 1px solid rgba(79, 172, 254, 0.3);
        padding-bottom: 8px;
    }
    
    /* Input Styling */
    .stNumberInput input, .stTextInput input {
        background: #1a1a2e !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: white !important;
        border-radius: 8px !important;
    }
    
    .stNumberInput input:focus, .stTextInput input:focus {
        border-color: #4facfe !important;
        box-shadow: 0 0 0 2px rgba(79, 172, 254, 0.2) !important;
    }
    
    /* Section Headers */
    .section-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 24px 0 16px 0;
        padding-bottom: 12px;
        border-bottom: 2px solid rgba(79, 172, 254, 0.2);
    }
    
    .section-icon {
        font-size: 1.5rem;
    }
    
    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #e2e8f0;
        letter-spacing: 0.5px;
    }
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_header():
    """Render premium header."""
    st.markdown("""
    <div class="prophet-header">
        <h1 class="prophet-title">SPX PROPHET</h1>
        <p class="prophet-subtitle">WHERE STRUCTURE BECOMES FORESIGHT</p>
    </div>
    """, unsafe_allow_html=True)

def render_vix_zone_panel(vix_zone: VIXZone):
    """Render the VIX Zone visual panel."""
    status, entry_rail, exit_rail = get_vix_zone_status(vix_zone)
    
    # Determine colors
    if vix_zone.trade_bias == "CALLS":
        bias_color = "#10b981"
        bias_bg = "rgba(16, 185, 129, 0.2)"
    elif vix_zone.trade_bias == "PUTS":
        bias_color = "#ef4444"
        bias_bg = "rgba(239, 68, 68, 0.2)"
    else:
        bias_color = "#fbbf24"
        bias_bg = "rgba(251, 191, 36, 0.2)"
    
    # Build zone ladder HTML
    ladder_html = '<div class="zone-ladder">'
    
    # Levels above (reversed for display)
    for i, level in enumerate(reversed(vix_zone.levels_above)):
        zone_num = 4 - i
        ladder_html += f'''
        <div class="zone-level zone-resistance">
            <span style="color: #ef4444;">+{zone_num}</span>
            <span style="color: #f8fafc; font-weight: 600;">{level:.2f}</span>
            <span style="color: #94a3b8; font-size: 0.75rem;">PUTS extend</span>
        </div>'''
    
    # Resistance (Zone Top)
    ladder_html += f'''
    <div class="zone-level" style="background: rgba(239, 68, 68, 0.4); border: 2px solid #ef4444;">
        <span style="color: #fecaca;">RES</span>
        <span style="color: #ffffff; font-weight: 700;">{vix_zone.resistance:.2f}</span>
        <span style="color: #fecaca; font-size: 0.75rem;">CALLS Entry</span>
    </div>'''
    
    # Current VIX (if within zone)
    if vix_zone.support <= vix_zone.current <= vix_zone.resistance:
        ladder_html += f'''
        <div class="zone-level zone-current">
            <span style="color: #93c5fd;">NOW</span>
            <span style="color: #ffffff; font-weight: 700;">{vix_zone.current:.2f}</span>
            <span style="color: #93c5fd; font-size: 0.75rem;">{vix_zone.position_pct:.0f}%</span>
        </div>'''
    
    # Support (Zone Bottom)
    ladder_html += f'''
    <div class="zone-level" style="background: rgba(16, 185, 129, 0.4); border: 2px solid #10b981;">
        <span style="color: #bbf7d0;">SUP</span>
        <span style="color: #ffffff; font-weight: 700;">{vix_zone.support:.2f}</span>
        <span style="color: #bbf7d0; font-size: 0.75rem;">PUTS Entry</span>
    </div>'''
    
    # Levels below
    for i, level in enumerate(vix_zone.levels_below):
        zone_num = i + 1
        ladder_html += f'''
        <div class="zone-level zone-support">
            <span style="color: #10b981;">-{zone_num}</span>
            <span style="color: #f8fafc; font-weight: 600;">{level:.2f}</span>
            <span style="color: #94a3b8; font-size: 0.75rem;">CALLS extend</span>
        </div>'''
    
    ladder_html += '</div>'
    
    # Main panel
    st.markdown(f"""
    <div class="vix-zone-panel">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <div>
                <div style="font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;">VIX Trade Compass</div>
                <div style="font-size: 1.5rem; font-weight: 700; color: {bias_color};">{vix_zone.trade_bias}</div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 0.75rem; color: #94a3b8;">Zone Size</div>
                <div style="font-size: 1.2rem; font-weight: 600; color: #f8fafc;">{vix_zone.zone_size:.2f}</div>
            </div>
        </div>
        
        <div style="background: {bias_bg}; border-radius: 8px; padding: 12px; margin-bottom: 16px; border-left: 4px solid {bias_color};">
            <div style="color: #f8fafc; font-weight: 500;">{status}</div>
            <div style="color: #94a3b8; font-size: 0.8rem; margin-top: 4px;">
                Entry: SPX {entry_rail} | Target: SPX {exit_rail}
            </div>
        </div>
        
        {ladder_html}
    </div>
    """, unsafe_allow_html=True)

def render_trade_card(setup: TradeSetup, current_price: float, vix_zone: Optional[VIXZone]):
    """Render a trade setup card."""
    distance = abs(current_price - setup.entry_price)
    is_near = distance <= AT_RAIL_THRESHOLD
    
    card_class = "trade-card-calls" if setup.direction == "CALLS" else "trade-card-puts"
    direction_color = "#10b981" if setup.direction == "CALLS" else "#ef4444"
    
    # VIX alignment check
    vix_aligned = False
    vix_status = "Enter VIX data"
    if vix_zone and vix_zone.current > 0:
        if setup.direction == "CALLS" and vix_zone.trade_bias == "CALLS":
            vix_aligned = True
            vix_status = f"✓ VIX at {vix_zone.position_pct:.0f}% (resistance zone)"
        elif setup.direction == "PUTS" and vix_zone.trade_bias == "PUTS":
            vix_aligned = True
            vix_status = f"✓ VIX at {vix_zone.position_pct:.0f}% (support zone)"
        elif vix_zone.trade_bias == "NEUTRAL":
            vix_status = f"⚠ VIX mid-range ({vix_zone.position_pct:.0f}%)"
        else:
            vix_status = f"✗ VIX favors {vix_zone.trade_bias}"
    
    st.markdown(f"""
    <div class="trade-card {card_class}">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
            <div>
                <span class="signal-badge signal-{setup.direction.lower()}">{setup.direction}</span>
                <span style="color: #94a3b8; font-size: 0.8rem; margin-left: 8px;">{setup.cone_name} Cone</span>
            </div>
            <div style="text-align: right;">
                <div style="color: {'#10b981' if is_near else '#94a3b8'}; font-size: 0.8rem;">
                    {'🎯 AT RAIL' if is_near else f'{distance:.1f} pts away'}
                </div>
            </div>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 12px;">
            <div class="metric-card">
                <div class="metric-value" style="color: {direction_color};">{setup.entry_price:.2f}</div>
                <div class="metric-label">Entry</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" style="color: #fbbf24;">{setup.target_price:.2f}</div>
                <div class="metric-label">Target</div>
            </div>
            <div class="metric-card">
                <div class="metric-value" style="color: #94a3b8;">{setup.stop_price:.2f}</div>
                <div class="metric-label">Stop</div>
            </div>
        </div>
        
        <div style="display: flex; justify-content: space-between; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.1);">
            <div>
                <span style="color: #94a3b8; font-size: 0.75rem;">R:R</span>
                <span style="color: {'#10b981' if setup.rr_ratio >= 3 else '#fbbf24'}; font-weight: 600; margin-left: 4px;">
                    {setup.rr_ratio:.1f}:1
                </span>
            </div>
            <div>
                <span style="color: #94a3b8; font-size: 0.75rem;">VIX:</span>
                <span style="color: {'#10b981' if vix_aligned else '#94a3b8'}; font-size: 0.75rem; margin-left: 4px;">
                    {vix_status}
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_checklist(cones: List[Cone], current_price: float, vix_zone: Optional[VIXZone]):
    """Render the 4-point trade checklist."""
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    
    if nearest_cone:
        cone_width = nearest_cone.ascending_rail - nearest_cone.descending_rail
    else:
        cone_width = 0
    
    # Build checks
    checks = []
    
    # 1. At Rail
    at_rail_ok = nearest_distance <= AT_RAIL_THRESHOLD
    at_rail_detail = f"{nearest_distance:.1f} pts away" if nearest_distance > AT_RAIL_THRESHOLD else "At entry zone"
    checks.append(("At Rail", at_rail_ok, at_rail_detail))
    
    # 2. Structure
    structure_ok = cone_width >= MIN_CONE_WIDTH
    structure_detail = f"{cone_width:.0f} pts room" if structure_ok else f"Too narrow ({cone_width:.0f} pts)"
    checks.append(("Structure", structure_ok, structure_detail))
    
    # 3. Active Cone
    active_ok = nearest_cone is not None
    active_detail = f"{nearest_cone.name} {nearest_rail_type}" if nearest_cone else "No cone"
    checks.append(("Active Cone", active_ok, active_detail))
    
    # 4. VIX Aligned
    if vix_zone and vix_zone.current > 0:
        expected_bias = "CALLS" if nearest_rail_type == 'descending' else "PUTS"
        vix_ok = vix_zone.trade_bias == expected_bias
        vix_detail = f"VIX says {vix_zone.trade_bias}" if vix_zone.trade_bias != "NEUTRAL" else "VIX neutral"
    else:
        vix_ok = True  # Don't penalize
        vix_detail = "Enter VIX data"
    checks.append(("VIX Aligned", vix_ok, vix_detail))
    
    # Calculate overall
    passed = sum(1 for _, ok, _ in checks if ok)
    
    if passed == 4:
        overall = "🟢 GO - Perfect Setup"
        overall_color = "#10b981"
    elif passed >= 3:
        overall = "🟢 GO - Good Setup"
        overall_color = "#10b981"
    elif not at_rail_ok:
        overall = "🟡 WAIT - Not at rail"
        overall_color = "#fbbf24"
    elif not structure_ok:
        overall = "🔴 SKIP - Structure issue"
        overall_color = "#ef4444"
    else:
        overall = "🟡 CAUTION"
        overall_color = "#fbbf24"
    
    # Render
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(0,0,0,0.4) 0%, rgba(0,0,0,0.2) 100%); 
                border: 2px solid {overall_color}; border-radius: 12px; padding: 16px; margin-bottom: 16px;">
        <div style="font-size: 1.2rem; font-weight: 700; color: {overall_color}; margin-bottom: 12px;">
            {overall}
        </div>
    """, unsafe_allow_html=True)
    
    for label, ok, detail in checks:
        icon = "✓" if ok else "✗"
        color = "#10b981" if ok else "#ef4444"
        st.markdown(f"""
        <div class="checklist-item {'checklist-pass' if ok else 'checklist-fail'}">
            <span style="color: {color}; font-size: 1.2rem; font-weight: bold; width: 24px;">{icon}</span>
            <span style="flex: 1; color: #f8fafc; font-weight: 500; margin-left: 12px;">{label}</span>
            <span style="color: #94a3b8; font-size: 0.85rem;">{detail}</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Trade direction
    if nearest_rail_type == 'descending':
        direction = "CALLS"
        direction_color = "#10b981"
    else:
        direction = "PUTS"
        direction_color = "#ef4444"
    
    st.markdown(f"""
        <div style="text-align: center; margin-top: 16px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.1);">
            <div style="color: #94a3b8; font-size: 0.75rem; margin-bottom: 4px;">TRADE DIRECTION</div>
            <span class="signal-badge signal-{direction.lower()}">{direction}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet v2.0",
        page_icon="🎯",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    inject_premium_css()
    render_header()
    
    # ========== SIDEBAR ==========
    with st.sidebar:
        st.markdown("### 📅 Session")
        
        # Date selection
        session_date = st.date_input(
            "Trading Date",
            value=get_ct_now().date(),
            help="Select the trading session date"
        )
        session_date = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        
        # Current time display
        ct_now = get_ct_now()
        st.caption(f"🕐 {ct_now.strftime('%I:%M %p CT')} | {ct_now.strftime('%A, %b %d')}")
        
        st.markdown("---")
        
        # ========== VIX ZONE INPUT ==========
        st.markdown("### 🧭 VIX Zone (5pm-2am)")
        st.caption("Enter overnight support/resistance")
        
        # Initialize session state
        if 'vix_support' not in st.session_state:
            st.session_state.vix_support = 0.0
        if 'vix_resistance' not in st.session_state:
            st.session_state.vix_resistance = 0.0
        if 'vix_current' not in st.session_state:
            st.session_state.vix_current = 0.0
        
        col1, col2 = st.columns(2)
        with col1:
            vix_support = st.number_input(
                "Support",
                min_value=0.0,
                max_value=100.0,
                value=st.session_state.vix_support,
                step=0.01,
                format="%.2f",
                help="Zone bottom (PUTS entry when VIX here)"
            )
            st.session_state.vix_support = vix_support
        
        with col2:
            vix_resistance = st.number_input(
                "Resistance",
                min_value=0.0,
                max_value=100.0,
                value=st.session_state.vix_resistance,
                step=0.01,
                format="%.2f",
                help="Zone top (CALLS entry when VIX here)"
            )
            st.session_state.vix_resistance = vix_resistance
        
        vix_current = st.number_input(
            "Current VIX",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_current,
            step=0.01,
            format="%.2f",
            help="Live VIX value from TradingView"
        )
        st.session_state.vix_current = vix_current
        
        # Calculate VIX zone
        vix_zone = None
        if vix_support > 0 and vix_resistance > 0:
            vix_zone = calculate_vix_zones(vix_support, vix_resistance, vix_current)
            
            # Zone validation
            zone_size = vix_resistance - vix_support
            if abs(zone_size - 0.15) < 0.02:
                st.success(f"✓ Valid zone: {zone_size:.2f}")
            elif zone_size > 0:
                zones = round(zone_size / 0.15)
                st.info(f"Zone spans ~{zones} levels ({zone_size:.2f})")
        
        st.markdown("---")
        
        # ========== ES-SPX OFFSET ==========
        st.markdown("### 📊 ES-SPX Offset")
        
        if 'es_offset' not in st.session_state:
            st.session_state.es_offset = 0.0
        
        es_offset = st.number_input(
            "ES - SPX",
            min_value=-100.0,
            max_value=100.0,
            value=st.session_state.es_offset,
            step=0.25,
            format="%.2f",
            help="Enter (ES price - SPX price). Negative if ES < SPX"
        )
        st.session_state.es_offset = es_offset
        
        if es_offset >= 0:
            st.caption(f"ES is {es_offset:.2f} pts ABOVE SPX")
        else:
            st.caption(f"ES is {abs(es_offset):.2f} pts BELOW SPX")
        
        st.markdown("---")
        
        # ========== MANUAL PIVOTS ==========
        st.markdown("### 📍 Manual Pivots")
        st.caption("Override auto-detected values")
        
        use_manual = st.checkbox("Enable Manual Override", value=False)
        
        if 'manual_high' not in st.session_state:
            st.session_state.manual_high = 0.0
        if 'manual_low' not in st.session_state:
            st.session_state.manual_low = 0.0
        if 'manual_close' not in st.session_state:
            st.session_state.manual_close = 0.0
        
        if use_manual:
            manual_high = st.number_input("High (Wick)", value=st.session_state.manual_high, format="%.2f")
            manual_low = st.number_input("Low (Close)", value=st.session_state.manual_low, format="%.2f")
            manual_close = st.number_input("Close", value=st.session_state.manual_close, format="%.2f")
            st.session_state.manual_high = manual_high
            st.session_state.manual_low = manual_low
            st.session_state.manual_close = manual_close
    
    # ========== MAIN CONTENT ==========
    
    # Fetch data
    prior_session = fetch_prior_session_data(session_date)
    current_price = fetch_current_spx() or 6000.0
    
    # Use manual pivots if enabled
    if use_manual and st.session_state.manual_high > 0:
        high_price = st.session_state.manual_high
        low_price = st.session_state.manual_low
        close_price = st.session_state.manual_close
        high_time = CT_TZ.localize(datetime.combine(session_date.date() - timedelta(days=1), time(12, 0)))
        low_time = high_time
    elif prior_session:
        high_price = prior_session['high']
        low_price = prior_session['low']
        close_price = prior_session['close']
        high_time = prior_session['high_time']
        low_time = prior_session['low_time']
    else:
        st.error("Could not fetch prior session data")
        return
    
    # Create pivots
    target_time = session_date.replace(hour=10, minute=0)
    
    pivots = [
        Pivot(price=high_price, time=high_time, name='High'),
        Pivot(price=low_price, time=low_time, name='Low'),
        Pivot(price=close_price, time=CT_TZ.localize(datetime.combine(session_date.date() - timedelta(days=1), time(15, 0))), name='Close'),
    ]
    
    # Create cones
    cones = [create_cone(p, target_time) for p in pivots]
    
    # Generate trade setups
    trade_setups = generate_trade_setups(cones, current_price, vix_zone)
    
    # ========== TOP METRICS BAR ==========
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #4facfe;">{current_price:,.2f}</div>
            <div class="metric-label">SPX Price</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if vix_zone and vix_zone.current > 0:
            vix_color = "#10b981" if vix_zone.trade_bias == "CALLS" else "#ef4444" if vix_zone.trade_bias == "PUTS" else "#fbbf24"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="color: {vix_color};">{vix_zone.current:.2f}</div>
                <div class="metric-label">VIX ({vix_zone.position_pct:.0f}%)</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="metric-card">
                <div class="metric-value" style="color: #64748b;">—</div>
                <div class="metric-label">VIX</div>
            </div>
            """, unsafe_allow_html=True)
    
    with col3:
        nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
        dist_color = "#10b981" if nearest_distance <= 5 else "#fbbf24" if nearest_distance <= 10 else "#64748b"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: {dist_color};">{nearest_distance:.1f}</div>
            <div class="metric-label">Pts to Rail</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        if nearest_cone:
            cone_width = nearest_cone.ascending_rail - nearest_cone.descending_rail
            width_color = "#10b981" if cone_width >= 25 else "#fbbf24" if cone_width >= 18 else "#ef4444"
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value" style="color: {width_color};">{cone_width:.0f}</div>
                <div class="metric-label">Cone Width</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ========== MAIN LAYOUT ==========
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        # VIX Zone Panel
        if vix_zone and vix_zone.support > 0:
            st.markdown("""
            <div class="section-header">
                <div class="section-icon">🧭</div>
                <div class="section-title">VIX Zone Analysis</div>
            </div>
            """, unsafe_allow_html=True)
            render_vix_zone_panel(vix_zone)
        
        # Trade Setups
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">🎯</div>
            <div class="section-title">Trade Setups</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Filter and sort setups
        calls_setups = sorted([s for s in trade_setups if s.direction == 'CALLS'], 
                              key=lambda x: abs(current_price - x.entry_price))
        puts_setups = sorted([s for s in trade_setups if s.direction == 'PUTS'],
                             key=lambda x: abs(current_price - x.entry_price))
        
        tab1, tab2 = st.tabs(["📈 CALLS (Buy Points)", "📉 PUTS (Sell Points)"])
        
        with tab1:
            if calls_setups:
                for setup in calls_setups[:3]:
                    render_trade_card(setup, current_price, vix_zone)
            else:
                st.info("No CALLS setups available")
        
        with tab2:
            if puts_setups:
                for setup in puts_setups[:3]:
                    render_trade_card(setup, current_price, vix_zone)
            else:
                st.info("No PUTS setups available")
    
    with right_col:
        # Checklist
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">📋</div>
            <div class="section-title">Trade Checklist</div>
        </div>
        """, unsafe_allow_html=True)
        render_checklist(cones, current_price, vix_zone)
        
        # Pivot Reference
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">📍</div>
            <div class="section-title">Prior Session</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="background: #1a1a2e; border-radius: 12px; padding: 16px;">
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                <span style="color: #94a3b8;">High (Wick)</span>
                <span style="color: #ef4444; font-weight: 600; font-family: monospace;">{high_price:.2f}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                <span style="color: #94a3b8;">Low (Close)</span>
                <span style="color: #10b981; font-weight: 600; font-family: monospace;">{low_price:.2f}</span>
            </div>
            <div style="display: flex; justify-content: space-between; padding: 8px 0;">
                <span style="color: #94a3b8;">Close</span>
                <span style="color: #fbbf24; font-weight: 600; font-family: monospace;">{close_price:.2f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Cone Rails at 10am
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">📐</div>
            <div class="section-title">10am Rails</div>
        </div>
        """, unsafe_allow_html=True)
        
        rails_html = '<div style="background: #1a1a2e; border-radius: 12px; padding: 16px;">'
        for cone in cones:
            rails_html += f"""
            <div style="margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid rgba(255,255,255,0.1);">
                <div style="color: #94a3b8; font-size: 0.8rem; margin-bottom: 4px;">{cone.name} Cone</div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #ef4444;">▲ {cone.ascending_rail:.2f}</span>
                    <span style="color: #10b981;">▼ {cone.descending_rail:.2f}</span>
                </div>
            </div>
            """
        rails_html += '</div>'
        st.markdown(rails_html, unsafe_allow_html=True)

# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    main()