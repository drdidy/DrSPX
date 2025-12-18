"""
SPX Prophet v2.0 - Professional Edition
Clean, functional, profitable.
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
VIX_ZONE_SIZE = 0.15

# Slopes for cone rails
SLOPE_ASCENDING = 0.45
SLOPE_DESCENDING = 0.45

# Trading thresholds
MIN_CONE_WIDTH = 18.0
AT_RAIL_THRESHOLD = 8.0
STOP_LOSS_PTS = 3.0

# Time constants
POWER_HOUR_START = time(14, 0)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_ct_now() -> datetime:
    return datetime.now(CT_TZ)

def get_time_block_index(dt: datetime, base_time: time = time(8, 30)) -> int:
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
    name: str

@dataclass
class Cone:
    pivot: Pivot
    name: str
    ascending_rail: float
    descending_rail: float

@dataclass
class VIXZone:
    support: float
    resistance: float
    zone_size: float
    current: float
    position_pct: float
    trade_bias: str
    levels_above: List[float]
    levels_below: List[float]

@dataclass
class TradeSetup:
    direction: str
    entry_price: float
    target_price: float
    stop_price: float
    cone_name: str
    rail_type: str
    risk_pts: float
    reward_pts: float
    rr_ratio: float

# ============================================================================
# VIX ZONE CALCULATIONS
# ============================================================================

def calculate_vix_zones(support: float, resistance: float, current: float) -> VIXZone:
    zone_size = resistance - support
    
    if zone_size > 0 and current > 0:
        position_pct = ((current - support) / zone_size) * 100
        position_pct = max(-50, min(150, position_pct))
    else:
        position_pct = 50
    
    if current <= 0:
        trade_bias = "ENTER VIX"
    elif position_pct >= 70:
        trade_bias = "CALLS"
    elif position_pct <= 30:
        trade_bias = "PUTS"
    else:
        trade_bias = "NEUTRAL"
    
    levels_above = [round(resistance + (VIX_ZONE_SIZE * i), 2) for i in range(1, 5)]
    levels_below = [round(support - (VIX_ZONE_SIZE * i), 2) for i in range(1, 5)]
    
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

# ============================================================================
# CONE CALCULATIONS
# ============================================================================

def calculate_rail_price(pivot_price: float, pivot_time: datetime, 
                         target_time: datetime, is_ascending: bool) -> float:
    blocks = get_time_block_index(target_time) - get_time_block_index(pivot_time)
    slope = SLOPE_ASCENDING if is_ascending else -SLOPE_DESCENDING
    return pivot_price + (slope * blocks)

def create_cone(pivot: Pivot, target_time: datetime) -> Cone:
    ascending = calculate_rail_price(pivot.price, pivot.time, target_time, True)
    descending = calculate_rail_price(pivot.price, pivot.time, target_time, False)
    return Cone(pivot=pivot, name=pivot.name, ascending_rail=ascending, descending_rail=descending)

def find_nearest_rail(price: float, cones: List[Cone]) -> Tuple[Optional[Cone], str, float]:
    nearest_cone = None
    nearest_type = ''
    nearest_distance = float('inf')
    
    for cone in cones:
        dist_desc = abs(price - cone.descending_rail)
        if dist_desc < nearest_distance:
            nearest_distance = dist_desc
            nearest_cone = cone
            nearest_type = 'descending'
        
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
        
        df_before_power = df[df.index.time < POWER_HOUR_START]
        if not df_before_power.empty:
            high_idx = df_before_power['High'].idxmax()
        else:
            high_idx = df['High'].idxmax()
        
        low_close_idx = df['Close'].idxmin()
        
        return {
            'date': prior_date,
            'high': df.loc[high_idx, 'High'],
            'high_time': high_idx,
            'low': df.loc[low_close_idx, 'Close'],
            'low_time': low_close_idx,
            'close': df['Close'].iloc[-1],
        }
    except Exception as e:
        return None

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

# ============================================================================
# TRADE SETUP GENERATION
# ============================================================================

def generate_trade_setups(cones: List[Cone], current_price: float) -> List[TradeSetup]:
    setups = []
    
    for cone in cones:
        cone_width = cone.ascending_rail - cone.descending_rail
        if cone_width < MIN_CONE_WIDTH:
            continue
        
        # CALLS setup
        calls_entry = cone.descending_rail
        calls_target = cone.ascending_rail
        calls_stop = calls_entry - STOP_LOSS_PTS
        calls_reward = calls_target - calls_entry
        
        setups.append(TradeSetup(
            direction='CALLS',
            entry_price=calls_entry,
            target_price=calls_target,
            stop_price=calls_stop,
            cone_name=cone.name,
            rail_type='descending',
            risk_pts=STOP_LOSS_PTS,
            reward_pts=calls_reward,
            rr_ratio=calls_reward / STOP_LOSS_PTS
        ))
        
        # PUTS setup
        puts_entry = cone.ascending_rail
        puts_target = cone.descending_rail
        puts_stop = puts_entry + STOP_LOSS_PTS
        puts_reward = puts_entry - puts_target
        
        setups.append(TradeSetup(
            direction='PUTS',
            entry_price=puts_entry,
            target_price=puts_target,
            stop_price=puts_stop,
            cone_name=cone.name,
            rail_type='ascending',
            risk_pts=STOP_LOSS_PTS,
            reward_pts=puts_reward,
            rr_ratio=puts_reward / STOP_LOSS_PTS
        ))
    
    return setups

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    st.set_page_config(
        page_title="SPX Prophet",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Header
    st.title("📈 SPX Prophet")
    st.caption("Where Structure Becomes Foresight")
    
    # ==================== SIDEBAR ====================
    with st.sidebar:
        st.header("Settings")
        
        # Date Selection
        st.subheader("📅 Session Date")
        session_date = st.date_input(
            "Select Date",
            value=get_ct_now().date()
        )
        session_date = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        
        ct_now = get_ct_now()
        st.caption(f"Current: {ct_now.strftime('%I:%M %p CT')}")
        
        st.divider()
        
        # VIX Zone Input
        st.subheader("🧭 VIX Zone (5pm-2am)")
        
        if 'vix_support' not in st.session_state:
            st.session_state.vix_support = 0.0
        if 'vix_resistance' not in st.session_state:
            st.session_state.vix_resistance = 0.0
        if 'vix_current' not in st.session_state:
            st.session_state.vix_current = 0.0
        
        vix_support = st.number_input(
            "Support (Zone Bottom)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_support,
            step=0.01,
            format="%.2f"
        )
        st.session_state.vix_support = vix_support
        
        vix_resistance = st.number_input(
            "Resistance (Zone Top)",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_resistance,
            step=0.01,
            format="%.2f"
        )
        st.session_state.vix_resistance = vix_resistance
        
        vix_current = st.number_input(
            "Current VIX",
            min_value=0.0,
            max_value=100.0,
            value=st.session_state.vix_current,
            step=0.01,
            format="%.2f"
        )
        st.session_state.vix_current = vix_current
        
        # Calculate VIX Zone
        vix_zone = None
        if vix_support > 0 and vix_resistance > 0:
            vix_zone = calculate_vix_zones(vix_support, vix_resistance, vix_current)
            zone_size = vix_resistance - vix_support
            if 0.13 <= zone_size <= 0.17:
                st.success(f"✓ Valid zone ({zone_size:.2f})")
            else:
                zones = round(zone_size / 0.15, 1)
                st.info(f"~{zones} zones ({zone_size:.2f})")
        
        st.divider()
        
        # ES-SPX Offset
        st.subheader("📊 ES-SPX Offset")
        
        if 'es_offset' not in st.session_state:
            st.session_state.es_offset = 0.0
        
        es_offset = st.number_input(
            "ES minus SPX",
            min_value=-100.0,
            max_value=100.0,
            value=st.session_state.es_offset,
            step=0.25,
            format="%.2f",
            help="Positive if ES > SPX, Negative if ES < SPX"
        )
        st.session_state.es_offset = es_offset
        
        if es_offset >= 0:
            st.caption(f"ES is {es_offset:.2f} above SPX")
        else:
            st.caption(f"ES is {abs(es_offset):.2f} below SPX")
        
        st.divider()
        
        # Manual Pivots
        st.subheader("📍 Manual Pivots")
        use_manual = st.checkbox("Override Auto Pivots")
        
        if 'manual_high' not in st.session_state:
            st.session_state.manual_high = 0.0
        if 'manual_low' not in st.session_state:
            st.session_state.manual_low = 0.0
        if 'manual_close' not in st.session_state:
            st.session_state.manual_close = 0.0
        
        if use_manual:
            st.session_state.manual_high = st.number_input("High (Wick)", value=st.session_state.manual_high, format="%.2f")
            st.session_state.manual_low = st.number_input("Low (Close)", value=st.session_state.manual_low, format="%.2f")
            st.session_state.manual_close = st.number_input("Close", value=st.session_state.manual_close, format="%.2f")
    
    # ==================== MAIN CONTENT ====================
    
    # Fetch data
    prior_session = fetch_prior_session_data(session_date)
    current_price = fetch_current_spx() or 6000.0
    
    # Determine pivots
    if use_manual and st.session_state.manual_high > 0:
        high_price = st.session_state.manual_high
        low_price = st.session_state.manual_low
        close_price = st.session_state.manual_close
        prior_date = session_date.date() - timedelta(days=1)
        high_time = CT_TZ.localize(datetime.combine(prior_date, time(12, 0)))
        low_time = high_time
    elif prior_session:
        high_price = prior_session['high']
        low_price = prior_session['low']
        close_price = prior_session['close']
        high_time = prior_session['high_time']
        low_time = prior_session['low_time']
        prior_date = prior_session['date']
    else:
        st.error("❌ Could not fetch prior session data. Please use manual pivots.")
        return
    
    # Create pivots and cones
    target_time = session_date.replace(hour=10, minute=0)
    
    pivots = [
        Pivot(price=high_price, time=high_time, name='High'),
        Pivot(price=low_price, time=low_time, name='Low'),
        Pivot(price=close_price, time=CT_TZ.localize(datetime.combine(prior_date, time(15, 0))), name='Close'),
    ]
    
    cones = [create_cone(p, target_time) for p in pivots]
    trade_setups = generate_trade_setups(cones, current_price)
    
    # Find nearest rail
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    
    # ==================== TOP METRICS ====================
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("SPX Price", f"{current_price:,.2f}")
    
    with col2:
        if vix_zone and vix_zone.current > 0:
            st.metric("VIX", f"{vix_zone.current:.2f}", f"{vix_zone.position_pct:.0f}% in zone")
        else:
            st.metric("VIX", "—")
    
    with col3:
        st.metric("Distance to Rail", f"{nearest_distance:.1f} pts")
    
    with col4:
        if nearest_cone:
            cone_width = nearest_cone.ascending_rail - nearest_cone.descending_rail
            st.metric("Cone Width", f"{cone_width:.0f} pts")
    
    st.divider()
    
    # ==================== VIX ZONE PANEL ====================
    if vix_zone and vix_zone.support > 0:
        st.subheader("🧭 VIX Zone Analysis")
        
        # Trade bias banner
        if vix_zone.trade_bias == "CALLS":
            st.success(f"🟢 **CALLS ZONE** — VIX at {vix_zone.position_pct:.0f}% (near resistance)")
        elif vix_zone.trade_bias == "PUTS":
            st.error(f"🔴 **PUTS ZONE** — VIX at {vix_zone.position_pct:.0f}% (near support)")
        else:
            st.warning(f"🟡 **NEUTRAL** — VIX at {vix_zone.position_pct:.0f}% (mid-zone, wait for extremes)")
        
        # Zone ladder
        zone_col1, zone_col2 = st.columns(2)
        
        with zone_col1:
            st.markdown("**Zone Levels**")
            
            # Levels above
            for i, level in enumerate(reversed(vix_zone.levels_above), 1):
                st.caption(f"↑ +{5-i}: {level:.2f} — PUTS extend")
            
            # Current zone
            st.markdown(f"🔴 **RES: {vix_zone.resistance:.2f}** — CALLS entry")
            if vix_zone.current > 0:
                st.markdown(f"📍 **NOW: {vix_zone.current:.2f}** ({vix_zone.position_pct:.0f}%)")
            st.markdown(f"🟢 **SUP: {vix_zone.support:.2f}** — PUTS entry")
            
            # Levels below
            for i, level in enumerate(vix_zone.levels_below, 1):
                st.caption(f"↓ -{i}: {level:.2f} — CALLS extend")
        
        with zone_col2:
            st.markdown("**VIX-SPX Mapping**")
            st.info("""
            **VIX at Resistance** → SPX at Descending Rail → **CALLS**
            
            **VIX at Support** → SPX at Ascending Rail → **PUTS**
            
            **VIX breaks up** → SPX breaks down → PUTS target extends
            
            **VIX breaks down** → SPX breaks up → CALLS target extends
            """)
        
        st.divider()
    
    # ==================== TRADE CHECKLIST ====================
    st.subheader("📋 Trade Checklist")
    
    check_col1, check_col2 = st.columns([2, 1])
    
    with check_col1:
        checks_passed = 0
        total_checks = 4
        
        # 1. At Rail
        at_rail = nearest_distance <= AT_RAIL_THRESHOLD
        if at_rail:
            st.success(f"✓ **At Rail** — {nearest_distance:.1f} pts from {nearest_cone.name if nearest_cone else 'N/A'} {nearest_rail_type}")
            checks_passed += 1
        else:
            st.error(f"✗ **At Rail** — {nearest_distance:.1f} pts away (need ≤{AT_RAIL_THRESHOLD})")
        
        # 2. Structure
        if nearest_cone:
            cone_width = nearest_cone.ascending_rail - nearest_cone.descending_rail
            structure_ok = cone_width >= MIN_CONE_WIDTH
            if structure_ok:
                st.success(f"✓ **Structure** — {cone_width:.0f} pts room")
                checks_passed += 1
            else:
                st.error(f"✗ **Structure** — Only {cone_width:.0f} pts (need ≥{MIN_CONE_WIDTH})")
        
        # 3. Active Cone
        if nearest_cone:
            st.success(f"✓ **Active Cone** — {nearest_cone.name} cone, {nearest_rail_type} rail")
            checks_passed += 1
        else:
            st.error("✗ **Active Cone** — No cone detected")
        
        # 4. VIX Aligned
        if vix_zone and vix_zone.current > 0:
            expected = "CALLS" if nearest_rail_type == 'descending' else "PUTS"
            if vix_zone.trade_bias == expected:
                st.success(f"✓ **VIX Aligned** — VIX says {vix_zone.trade_bias}")
                checks_passed += 1
            elif vix_zone.trade_bias == "NEUTRAL":
                st.warning(f"⚠ **VIX Aligned** — VIX neutral, wait for extremes")
            else:
                st.error(f"✗ **VIX Aligned** — VIX says {vix_zone.trade_bias}, not {expected}")
        else:
            st.info("ℹ **VIX Aligned** — Enter VIX data in sidebar")
            checks_passed += 1  # Don't penalize
    
    with check_col2:
        # Overall verdict
        st.markdown("**Verdict**")
        
        if checks_passed == 4:
            st.success("🟢 **GO** - Perfect setup")
        elif checks_passed >= 3:
            st.success("🟢 **GO** - Good setup")
        elif not at_rail:
            st.warning("🟡 **WAIT** - Not at rail yet")
        else:
            st.error("🔴 **SKIP** - Setup incomplete")
        
        # Trade direction
        st.markdown("**Direction**")
        if nearest_rail_type == 'descending':
            st.info("📈 **CALLS**")
        else:
            st.info("📉 **PUTS**")
    
    st.divider()
    
    # ==================== TRADE SETUPS ====================
    st.subheader("🎯 Trade Setups @ 10:00 AM")
    
    calls_tab, puts_tab = st.tabs(["📈 CALLS (Buy Points)", "📉 PUTS (Sell Points)"])
    
    calls_setups = sorted([s for s in trade_setups if s.direction == 'CALLS'], 
                          key=lambda x: abs(current_price - x.entry_price))
    puts_setups = sorted([s for s in trade_setups if s.direction == 'PUTS'],
                         key=lambda x: abs(current_price - x.entry_price))
    
    with calls_tab:
        if calls_setups:
            for setup in calls_setups:
                distance = abs(current_price - setup.entry_price)
                is_near = distance <= AT_RAIL_THRESHOLD
                
                # VIX alignment
                vix_status = ""
                if vix_zone and vix_zone.current > 0:
                    if vix_zone.trade_bias == "CALLS":
                        vix_status = "✓ VIX aligned"
                    elif vix_zone.trade_bias == "NEUTRAL":
                        vix_status = "⚠ VIX neutral"
                    else:
                        vix_status = "✗ VIX misaligned"
                
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.markdown(f"**{setup.cone_name}**")
                        st.caption("Descending Rail")
                    with col2:
                        st.metric("Entry", f"{setup.entry_price:.2f}")
                    with col3:
                        st.metric("Target", f"{setup.target_price:.2f}")
                    with col4:
                        st.metric("Stop", f"{setup.stop_price:.2f}")
                    with col5:
                        if is_near:
                            st.success(f"🎯 {distance:.1f} pts")
                        else:
                            st.caption(f"{distance:.1f} pts away")
                        st.caption(f"R:R {setup.rr_ratio:.1f}:1")
                        if vix_status:
                            st.caption(vix_status)
                    st.divider()
        else:
            st.info("No CALLS setups available")
    
    with puts_tab:
        if puts_setups:
            for setup in puts_setups:
                distance = abs(current_price - setup.entry_price)
                is_near = distance <= AT_RAIL_THRESHOLD
                
                # VIX alignment
                vix_status = ""
                if vix_zone and vix_zone.current > 0:
                    if vix_zone.trade_bias == "PUTS":
                        vix_status = "✓ VIX aligned"
                    elif vix_zone.trade_bias == "NEUTRAL":
                        vix_status = "⚠ VIX neutral"
                    else:
                        vix_status = "✗ VIX misaligned"
                
                with st.container():
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.markdown(f"**{setup.cone_name}**")
                        st.caption("Ascending Rail")
                    with col2:
                        st.metric("Entry", f"{setup.entry_price:.2f}")
                    with col3:
                        st.metric("Target", f"{setup.target_price:.2f}")
                    with col4:
                        st.metric("Stop", f"{setup.stop_price:.2f}")
                    with col5:
                        if is_near:
                            st.success(f"🎯 {distance:.1f} pts")
                        else:
                            st.caption(f"{distance:.1f} pts away")
                        st.caption(f"R:R {setup.rr_ratio:.1f}:1")
                        if vix_status:
                            st.caption(vix_status)
                    st.divider()
        else:
            st.info("No PUTS setups available")
    
    # ==================== REFERENCE DATA ====================
    st.subheader("📍 Reference Data")
    
    ref_col1, ref_col2 = st.columns(2)
    
    with ref_col1:
        st.markdown("**Prior Session Pivots**")
        st.markdown(f"- High (Wick): **{high_price:.2f}**")
        st.markdown(f"- Low (Close): **{low_price:.2f}**")
        st.markdown(f"- Close: **{close_price:.2f}**")
    
    with ref_col2:
        st.markdown("**10:00 AM Rail Values**")
        for cone in cones:
            st.markdown(f"- {cone.name}: ▲ **{cone.ascending_rail:.2f}** | ▼ **{cone.descending_rail:.2f}**")

if __name__ == "__main__":
    main()