"""
SPX Prophet - Where Structure Becomes Foresight
LEGENDARY EDITION
A professional institutional-grade SPX 0DTE trading assistant

================================================================================
SPX-VIX CONFLUENCE TRADING SYSTEM
================================================================================

THE CORE CONCEPT:
-----------------
This is a SPX-VIX CONFLUENCE system - BOTH must align for a valid trade signal.
VIX zones tell you DIRECTION, SPX rails tell you ENTRY POINT.

CONFLUENCE REQUIREMENT:
----------------------
✓ CALLS valid when: VIX at zone TOP + SPX at DESCENDING rail (▼)
✓ PUTS valid when:  VIX at zone BOTTOM + SPX at ASCENDING rail (▲)
✗ NO TRADE when:    VIX and SPX positions don't match

================================================================================
THE VIX ZONE SYSTEM
================================================================================

VIX moves in precise 0.15 increments. The overnight session (5pm-2am) establishes
the trading zone for the next day.

⚠️  CRITICAL: It's the 30-MINUTE CANDLE CLOSE that matters, NOT the wick!
    VIX can spike past a level but if it CLOSES at/below resistance or 
    at/above support, the zone is still valid. Wait for the candle to close!

ZONE STRUCTURE:
--------------
+4: +0.60 from zone top (PUTS target extends here)
+3: +0.45 from zone top
+2: +0.30 from zone top  
+1: +0.15 from zone top
═══════════════════════════════════════════════════
ZONE TOP (Resistance) ← VIX CLOSES here → CALLS (if SPX at ▼ rail)
═══════════════════════════════════════════════════
ZONE BOTTOM (Support) ← VIX CLOSES here → PUTS (if SPX at ▲ rail)
═══════════════════════════════════════════════════
-1: -0.15 from zone bottom
-2: -0.30 from zone bottom
-3: -0.45 from zone bottom
-4: -0.60 from zone bottom (CALLS target extends here)

================================================================================
GAP SCENARIOS (When SPX is far from cones)
================================================================================

When SPX gaps significantly and stays above/below all cones overnight, the 
normal cone rails may not be reachable. In these cases:

GAP UP (SPX far above High cone all night):
- No descending rails (▼) are accessible
- Use OVERNIGHT LOW as buy point
- Valid for CALLS if VIX at zone TOP (resistance)

GAP DOWN (SPX far below Low cone all night):
- No ascending rails (▲) are accessible  
- Use OVERNIGHT HIGH as sell point
- Valid for PUTS if VIX at zone BOTTOM (support)

================================================================================
TRADE LOGIC SUMMARY
================================================================================

STANDARD SETUP:
1. VIX at zone TOP (75%+) + SPX at descending rail (▼):
   - WAIT for 30-min VIX candle CLOSE at/below zone top
   - Enter CALLS at SPX descending rail
   - Exit when VIX CLOSES at zone BOTTOM

2. VIX at zone BOTTOM (25% or less) + SPX at ascending rail (▲):
   - WAIT for 30-min VIX candle CLOSE at/above zone bottom
   - Enter PUTS at SPX ascending rail
   - Exit when VIX CLOSES at zone TOP

GAP SETUP:
3. VIX at zone TOP + SPX gapped above all cones:
   - Use overnight LOW as CALLS entry point
   
4. VIX at zone BOTTOM + SPX gapped below all cones:
   - Use overnight HIGH as PUTS entry point

BREAKOUTS (30-min candle must CLOSE beyond level):
- VIX CLOSES ABOVE zone top: PUTS targets EXTEND
- VIX CLOSES BELOW zone bottom: CALLS targets EXTEND

THE 4-POINT CHECKLIST:
---------------------
1. AT RAIL - Is SPX at cone rail (or gap level if gapped)?
2. STRUCTURE - Is cone width adequate (18+ pts) and not broken overnight?
3. ACTIVE CONE - Are we at the correct cone (High/Low/Close)?
4. VIX ALIGNED - Is VIX at the correct zone edge for this trade?

KEY RULES:
----------
- CONFLUENCE REQUIRED: VIX zone + SPX rail must BOTH align
- VIX zone TOP + SPX descending rail = CALLS
- VIX zone BOTTOM + SPX ascending rail = PUTS
- Gap scenarios: Use overnight high/low as entry points
- 30-min candle CLOSE confirms VIX levels
- 3:1 minimum risk/reward ratio required
- Skip broken overnight levels

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
# CONFIGURATION & CONSTANTS
# ============================================================================

CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

# SLOPES - Symmetric ±0.45 pts per 30-min block (calibrated to TradingView)
SLOPE_ASCENDING = 0.45
SLOPE_DESCENDING = 0.45

# CONTRACT FACTOR: A 15-20pt OTM option moves ~0.30-0.35x the underlying
# Using 0.33 as middle estimate. Actual delta varies with time and distance OTM.
CONTRACT_FACTOR = 0.33

# Market hours
MAINTENANCE_START_CT = time(16, 0)
MAINTENANCE_END_CT = time(17, 0)
POWER_HOUR_START = time(14, 0)  # Highs after 2pm are less reliable pivots

# Pre-market window (for detecting pre-market pivots from ES)
PREMARKET_START_CT = time(6, 0)
PREMARKET_END_CT = time(8, 30)

# Secondary Pivot Detection
SECONDARY_PIVOT_MIN_PULLBACK_PCT = 0.003  # 0.3% = ~18 pts on SPX 6000
SECONDARY_PIVOT_MIN_DISTANCE = 5.0  # At least 5 points from primary
SECONDARY_PIVOT_START_TIME = time(13, 0)  # After structure develops

# ============================================================================
# CORE TRADING THRESHOLDS - These directly affect trade decisions
# ============================================================================

# Cone width: Need at least 25 pts to have meaningful 0DTE trade
# Math: 25 pts × 50% target = 12.5 pt move × 0.33 delta × $100 = $412 profit
# This justifies the risk of a $100 stop
MIN_CONE_WIDTH = 25.0

# Entry threshold: Within 5 pts of rail = actionable entry
# Beyond 5 pts = wait for price to come to you
AT_RAIL_THRESHOLD = 5.0

# Stop loss: 3 pts from entry
# Math: 3 pts × 0.33 delta × $100 = ~$100 risk per contract
STOP_LOSS_PTS = 3.0

# Strike offset: 15-20 pts OTM for ~0.30-0.35 delta
STRIKE_OFFSET = 17.5

# Minimum R:R to take a trade: At least 3:1 at 50% target
# Below this, risk doesn't justify reward
MIN_RR_RATIO = 3.0

# Rail touch threshold: Within 2 pts = ES "touched" the rail
RAIL_TOUCH_THRESHOLD = 2.0

# Confluence: Rails within 5 pts of each other = converging
CONFLUENCE_THRESHOLD = 5.0

# ============================================================================
# TIME DECAY (THETA) - Critical for 0DTE
# ============================================================================
# 0DTE options lose value rapidly. These multipliers adjust expected profit
# based on time remaining. Derived from typical theta decay curves.
#
# Morning (8:30-10:00): Full value, theta hasn't kicked in hard yet
# Mid-day (10:00-12:00): ~85% of theoretical value (theta accelerating)
# Afternoon (12:00-14:00): ~65% of theoretical value (theta crushing)
# Late (14:00+): ~40% of theoretical value (avoid new entries)

THETA_MULTIPLIER = {
    'morning': 1.0,      # 8:30-10:00 CT
    'mid_day': 0.85,     # 10:00-12:00 CT  
    'afternoon': 0.65,   # 12:00-14:00 CT
    'late': 0.40,        # 14:00+ CT - generally avoid
}

# Last reasonable entry time for 0DTE
LAST_ENTRY_TIME = time(13, 30)  # After 1:30pm, theta too aggressive

# ============================================================================
# EMA CONFIRMATION SETTINGS
# ============================================================================
# Entry is confirmed when 8 EMA crosses 21 EMA in trade direction on 1-min chart
EMA_FAST = 8
EMA_SLOW = 21
ENTRY_TOUCH_THRESHOLD = 3.0  # Must close within 3 pts of entry level
ENTRY_TIME_LIMIT_MINUTES = 90  # 1.5 hours to get EMA confirmation after touch
ALERT_APPROACH_DISTANCE = 10.0  # Alert when within 10 pts of entry

# ============================================================================
# DELTA APPROXIMATION BY DISTANCE OTM
# ============================================================================
# More accurate than fixed 0.33 - delta decreases as you go further OTM
# These are approximate for SPX 0DTE options mid-morning

DELTA_BY_OTM = {
    10: 0.42,   # 10 pts OTM
    15: 0.35,   # 15 pts OTM  
    20: 0.30,   # 20 pts OTM (our target zone)
    25: 0.25,   # 25 pts OTM
    30: 0.20,   # 30 pts OTM
}

def get_delta_estimate(otm_distance: float) -> float:
    """Estimate delta based on distance OTM."""
    if otm_distance <= 10:
        return 0.42
    elif otm_distance <= 15:
        return 0.35
    elif otm_distance <= 20:
        return 0.30
    elif otm_distance <= 25:
        return 0.25
    else:
        return 0.20

def get_theta_multiplier() -> Tuple[float, str]:
    """Get current theta multiplier based on time of day."""
    ct_now = get_ct_now().time()
    
    if ct_now < time(10, 0):
        return THETA_MULTIPLIER['morning'], 'morning'
    elif ct_now < time(12, 0):
        return THETA_MULTIPLIER['mid_day'], 'mid_day'
    elif ct_now < time(14, 0):
        return THETA_MULTIPLIER['afternoon'], 'afternoon'
    else:
        return THETA_MULTIPLIER['late'], 'late'

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
    """Simplified regime - only keep what matters for trading decisions."""
    overnight_range: float  # How much ES moved overnight
    overnight_range_pct: float  # As percentage of cone
    overnight_touched_rails: List[str]  # Which rails ES touched
    opening_position: str  # Where price opened relative to cone
    es_spx_offset: float  # Current ES-SPX spread

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

# ============================================================================
# EMA & ENTRY CONFIRMATION FUNCTIONS
# ============================================================================

@st.cache_data(ttl=30)  # Cache for 30 seconds
def fetch_1min_data_for_ema() -> Optional[pd.DataFrame]:
    """Fetch 1-minute SPX data for EMA calculation."""
    try:
        spx = yf.Ticker("^GSPC")
        df = spx.history(period='1d', interval='1m')
        if df.empty:
            return None
        df.index = df.index.tz_convert(CT_TZ)
        return df
    except Exception:
        return None

def calculate_emas(df: pd.DataFrame) -> Tuple[float, float, bool, bool]:
    """
    Calculate 8 EMA and 21 EMA from 1-min data.
    Returns: (ema_8, ema_21, bullish_cross, bearish_cross)
    - bullish_cross: True if 8 EMA just crossed ABOVE 21 EMA
    - bearish_cross: True if 8 EMA just crossed BELOW 21 EMA
    """
    if df is None or len(df) < EMA_SLOW + 2:
        return 0, 0, False, False
    
    # Calculate EMAs
    ema_8 = df['Close'].ewm(span=EMA_FAST, adjust=False).mean()
    ema_21 = df['Close'].ewm(span=EMA_SLOW, adjust=False).mean()
    
    current_8 = ema_8.iloc[-1]
    current_21 = ema_21.iloc[-1]
    prev_8 = ema_8.iloc[-2]
    prev_21 = ema_21.iloc[-2]
    
    # Detect crosses
    bullish_cross = (prev_8 <= prev_21) and (current_8 > current_21)
    bearish_cross = (prev_8 >= prev_21) and (current_8 < current_21)
    
    return float(current_8), float(current_21), bullish_cross, bearish_cross

def get_entry_status(setup, current_price: float, ema_data: dict, session_state: dict) -> dict:
    """
    Determine entry status for a setup.
    
    Status flow:
    1. WAITING - Price not yet at entry zone
    2. APPROACHING - Price within ALERT_APPROACH_DISTANCE of entry
    3. TOUCHED - Price touched entry level (within ENTRY_TOUCH_THRESHOLD)
    4. CONFIRMING - Touched, waiting for EMA cross (within time limit)
    5. CONFIRMED - EMA cross happened after touch = ENTER NOW
    6. EXPIRED - Time limit passed without EMA confirmation
    7. INVALIDATED - Price moved too far from entry without confirmation
    
    Returns dict with:
    - status: one of the above
    - message: human readable status
    - alert_level: 'none', 'approaching', 'touched', 'confirmed'
    - time_remaining: minutes left for confirmation (if applicable)
    """
    entry_price = setup.entry_price
    direction = setup.direction  # 'CALLS' or 'PUTS'
    setup_id = f"{setup.direction}_{entry_price:.0f}"
    
    # Get or initialize touch tracking for this setup
    touch_key = f"touch_time_{setup_id}"
    touched_key = f"touched_{setup_id}"
    
    result = {
        'status': 'WAITING',
        'message': 'Waiting for price to approach entry',
        'alert_level': 'none',
        'time_remaining': None,
        'ema_8': ema_data.get('ema_8', 0),
        'ema_21': ema_data.get('ema_21', 0),
        'distance_to_entry': 0
    }
    
    # Calculate distance to entry
    if direction == 'CALLS':
        # For CALLS (buy at support), price needs to come DOWN to entry
        distance = current_price - entry_price
        at_entry = distance <= ENTRY_TOUCH_THRESHOLD and distance >= -ENTRY_TOUCH_THRESHOLD
        approaching = distance <= ALERT_APPROACH_DISTANCE and distance > ENTRY_TOUCH_THRESHOLD
        past_entry = distance < -ENTRY_TOUCH_THRESHOLD  # Broke through support
    else:
        # For PUTS (sell at resistance), price needs to come UP to entry
        distance = entry_price - current_price
        at_entry = distance <= ENTRY_TOUCH_THRESHOLD and distance >= -ENTRY_TOUCH_THRESHOLD
        approaching = distance <= ALERT_APPROACH_DISTANCE and distance > ENTRY_TOUCH_THRESHOLD
        past_entry = distance < -ENTRY_TOUCH_THRESHOLD  # Broke through resistance
    
    result['distance_to_entry'] = abs(current_price - entry_price)
    
    # Check if already touched
    was_touched = session_state.get(touched_key, False)
    touch_time = session_state.get(touch_key)
    
    # State machine
    if past_entry and not was_touched:
        result['status'] = 'INVALIDATED'
        result['message'] = 'Price broke through entry without touch'
        result['alert_level'] = 'none'
        return result
    
    if at_entry and not was_touched:
        # First touch! Record it
        session_state[touched_key] = True
        session_state[touch_key] = get_ct_now()
        was_touched = True
        touch_time = session_state[touch_key]
        result['status'] = 'TOUCHED'
        result['message'] = '🎯 ENTRY TOUCHED! Waiting for EMA confirmation...'
        result['alert_level'] = 'touched'
    
    if was_touched and touch_time:
        # Calculate time remaining
        elapsed = (get_ct_now() - touch_time).total_seconds() / 60
        time_remaining = ENTRY_TIME_LIMIT_MINUTES - elapsed
        result['time_remaining'] = max(0, time_remaining)
        
        if time_remaining <= 0:
            result['status'] = 'EXPIRED'
            result['message'] = '⏰ Time limit expired without EMA confirmation'
            result['alert_level'] = 'none'
            return result
        
        # Check for EMA confirmation
        if direction == 'CALLS':
            # Need bullish cross (8 EMA crosses ABOVE 21 EMA)
            if ema_data.get('bullish_cross', False):
                result['status'] = 'CONFIRMED'
                result['message'] = '✅ ENTRY CONFIRMED! 8 EMA crossed above 21 EMA - BUY NOW!'
                result['alert_level'] = 'confirmed'
                return result
            elif ema_data.get('ema_8', 0) > ema_data.get('ema_21', 0):
                result['status'] = 'CONFIRMING'
                result['message'] = f'⏳ EMA aligned bullish, watching for fresh cross ({time_remaining:.0f}m left)'
                result['alert_level'] = 'touched'
        else:
            # Need bearish cross (8 EMA crosses BELOW 21 EMA)
            if ema_data.get('bearish_cross', False):
                result['status'] = 'CONFIRMED'
                result['message'] = '✅ ENTRY CONFIRMED! 8 EMA crossed below 21 EMA - SELL NOW!'
                result['alert_level'] = 'confirmed'
                return result
            elif ema_data.get('ema_8', 0) < ema_data.get('ema_21', 0):
                result['status'] = 'CONFIRMING'
                result['message'] = f'⏳ EMA aligned bearish, watching for fresh cross ({time_remaining:.0f}m left)'
                result['alert_level'] = 'touched'
        
        if result['status'] == 'TOUCHED':
            result['status'] = 'CONFIRMING'
            result['message'] = f'⏳ Waiting for EMA cross confirmation ({time_remaining:.0f}m left)'
            result['alert_level'] = 'touched'
        
        return result
    
    if approaching:
        result['status'] = 'APPROACHING'
        result['message'] = f'📍 Price approaching entry ({result["distance_to_entry"]:.1f} pts away)'
        result['alert_level'] = 'approaching'
        return result
    
    return result

def render_alert_javascript():
    """Render JavaScript for audio alerts and browser notifications."""
    return """
    <script>
    // Audio context for alerts
    let audioContext = null;
    
    function initAudio() {
        if (!audioContext) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        return audioContext;
    }
    
    function playTone(frequency, duration, type='sine') {
        try {
            const ctx = initAudio();
            const oscillator = ctx.createOscillator();
            const gainNode = ctx.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(ctx.destination);
            
            oscillator.frequency.value = frequency;
            oscillator.type = type;
            
            gainNode.gain.setValueAtTime(0.3, ctx.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + duration);
            
            oscillator.start(ctx.currentTime);
            oscillator.stop(ctx.currentTime + duration);
        } catch(e) {
            console.log('Audio not available:', e);
        }
    }
    
    function playApproachingAlert() {
        // Two short beeps
        playTone(800, 0.15);
        setTimeout(() => playTone(800, 0.15), 200);
    }
    
    function playTouchedAlert() {
        // Three ascending tones
        playTone(600, 0.2);
        setTimeout(() => playTone(800, 0.2), 250);
        setTimeout(() => playTone(1000, 0.2), 500);
    }
    
    function playConfirmedAlert() {
        // Triumphant fanfare
        playTone(523, 0.15);  // C
        setTimeout(() => playTone(659, 0.15), 150);  // E
        setTimeout(() => playTone(784, 0.15), 300);  // G
        setTimeout(() => playTone(1047, 0.4), 450);  // High C
    }
    
    // Browser notification
    function requestNotificationPermission() {
        if ('Notification' in window && Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }
    
    function showNotification(title, body, tag) {
        if ('Notification' in window && Notification.permission === 'granted') {
            new Notification(title, { body: body, tag: tag, requireInteraction: true });
        }
    }
    
    // Request permission on load
    requestNotificationPermission();
    
    // Expose functions to Streamlit
    window.spxAlerts = {
        approaching: playApproachingAlert,
        touched: playTouchedAlert,
        confirmed: playConfirmedAlert,
        notify: showNotification
    };
    </script>
    """

def render_alert_trigger(alert_level: str, setup_id: str, message: str):
    """Render JavaScript to trigger an alert based on level."""
    if alert_level == 'none':
        return ""
    
    # Use session state to track which alerts have been played
    alert_key = f"alert_played_{setup_id}_{alert_level}"
    if st.session_state.get(alert_key, False):
        return ""  # Already played this alert
    
    st.session_state[alert_key] = True
    
    if alert_level == 'approaching':
        return f"""
        <script>
        if (window.spxAlerts) {{
            window.spxAlerts.approaching();
            window.spxAlerts.notify('SPX Prophet', '{message}', 'approaching_{setup_id}');
        }}
        </script>
        """
    elif alert_level == 'touched':
        return f"""
        <script>
        if (window.spxAlerts) {{
            window.spxAlerts.touched();
            window.spxAlerts.notify('🎯 ENTRY TOUCHED!', '{message}', 'touched_{setup_id}');
        }}
        </script>
        """
    elif alert_level == 'confirmed':
        return f"""
        <script>
        if (window.spxAlerts) {{
            window.spxAlerts.confirmed();
            window.spxAlerts.notify('✅ ENTRY CONFIRMED!', '{message}', 'confirmed_{setup_id}');
        }}
        </script>
        """
    return ""

def count_30min_blocks(start_time: datetime, end_time: datetime) -> int:
    """
    Count 30-minute blocks between two times, skipping:
    - Daily maintenance window: 4pm-5pm CT (16:00-17:00)
    - Weekend: Friday 4pm CT to Sunday 5pm CT
    
    TradingView behavior: Friday's last candle is 3:30pm, next candle is Sunday 5pm.
    So we skip Friday after 4pm, all of Saturday, and Sunday until 5pm.
    """
    if start_time >= end_time:
        return 0
    
    blocks = 0
    current = start_time
    
    FRIDAY_CUTOFF = time(16, 0)  # Friday stops at 4pm CT
    SUNDAY_RESUME = time(17, 0)  # Sunday resumes at 5pm CT
    
    while current < end_time:
        current_ct = current.astimezone(CT_TZ)
        current_ct_time = current_ct.time()
        current_weekday = current_ct.weekday()  # 0=Mon, 4=Fri, 5=Sat, 6=Sun
        
        # Friday after 4pm - SKIP (weekend started)
        if current_weekday == 4 and current_ct_time >= FRIDAY_CUTOFF:
            current = current + timedelta(minutes=30)
            continue
        
        # Saturday - SKIP entirely
        if current_weekday == 5:
            current = current + timedelta(minutes=30)
            continue
        
        # Sunday before 5pm - SKIP
        if current_weekday == 6 and current_ct_time < SUNDAY_RESUME:
            current = current + timedelta(minutes=30)
            continue
        
        # Daily maintenance window (4pm-5pm CT) on weekdays
        # (Friday after 4pm is already handled above)
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
    """Determine if price is at a rail or in dead zone."""
    cone_width = ascending_rail - descending_rail
    if cone_width <= 0:
        return 'invalid', 0
    
    distance_to_lower = abs(price - descending_rail)
    distance_to_upper = abs(price - ascending_rail)
    
    # At rail = within AT_RAIL_THRESHOLD (5 pts)
    if distance_to_lower <= AT_RAIL_THRESHOLD:
        return 'lower_edge', distance_to_lower
    elif distance_to_upper <= AT_RAIL_THRESHOLD:
        return 'upper_edge', distance_to_upper
    else:
        return 'dead_zone', min(distance_to_upper, distance_to_lower)

# ============================================================================
# DATA FETCHING WITH POWER HOUR FILTER
# ============================================================================

@st.cache_data(ttl=300)
def fetch_prior_session_data(session_date: datetime) -> Optional[Dict]:
    """
    Fetch prior session data with both candlestick (wick) and line chart (close) pivot detection.
    Line chart values are RECOMMENDED as they represent true structure turning points.
    """
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
                'secondary_low_time': None,
                # Line chart values
                'high_line': row['Close'],
                'high_line_time': close_time,
                'low_line': row['Close'],
                'low_line_time': close_time,
                'secondary_high_line': None,
                'secondary_high_line_time': None,
                'secondary_low_line': None,
                'secondary_low_line_time': None
            }
        
        # Convert index to CT
        df = df_intraday.copy()
        df.index = df.index.tz_convert(CT_TZ)
        
        # ============================================================
        # CANDLESTICK (WICK) BASED DETECTION
        # ============================================================
        df_before_power = df[df.index.time < POWER_HOUR_START]
        
        power_hour_filtered = False
        if not df_before_power.empty:
            overall_high_idx = df['High'].idxmax()
            if overall_high_idx.time() >= POWER_HOUR_START:
                high_idx = df_before_power['High'].idxmax()
                power_hour_filtered = True
            else:
                high_idx = overall_high_idx
        else:
            high_idx = df['High'].idxmax()
        
        low_idx = df['Low'].idxmin()
        
        high_price = df.loc[high_idx, 'High']
        high_time = high_idx
        low_price = df.loc[low_idx, 'Low']
        low_time = low_idx
        close_price = df['Close'].iloc[-1]
        close_time = CT_TZ.localize(datetime.combine(prior_date, time(15, 0)))
        
        # ============================================================
        # LINE CHART BASED DETECTION (Using Close prices)
        # This is more accurate for structure detection
        # ============================================================
        if not df_before_power.empty:
            overall_high_close_idx = df['Close'].idxmax()
            if overall_high_close_idx.time() >= POWER_HOUR_START:
                high_line_idx = df_before_power['Close'].idxmax()
            else:
                high_line_idx = overall_high_close_idx
        else:
            high_line_idx = df['Close'].idxmax()
        
        low_line_idx = df['Close'].idxmin()
        
        high_line_price = df.loc[high_line_idx, 'Close']
        high_line_time = high_line_idx
        low_line_price = df.loc[low_line_idx, 'Close']
        low_line_time = low_line_idx
        
        # ============================================================
        # SECONDARY HIGH DETECTION - Using LINE CHART (Close prices)
        # Pattern: Primary High -> Drop -> LOCAL PEAK (Secondary High) -> Drop
        # 
        # Key insight: We need to find the FIRST local peak after the high,
        # not the bounce after the absolute low. The secondary high is a
        # failed attempt to make a new high.
        # ============================================================
        secondary_high_line = None
        secondary_high_line_time = None
        
        df_after_high = df[df.index > high_line_idx]
        
        if len(df_after_high) >= 3:
            closes = df_after_high['Close'].values
            indices = df_after_high.index.tolist()
            
            # Look for local peaks: price higher than both neighbors
            for i in range(1, len(closes) - 1):
                prev_close = closes[i - 1]
                curr_close = closes[i]
                next_close = closes[i + 1]
                
                # Is this a local peak? (higher than both neighbors)
                if curr_close > prev_close and curr_close > next_close:
                    # Is it lower than primary high? (required for secondary)
                    if curr_close < high_line_price:
                        # Is it at least 5 points below primary?
                        if (high_line_price - curr_close) >= SECONDARY_PIVOT_MIN_DISTANCE:
                            # Found the first valid secondary high
                            secondary_high_line = curr_close
                            secondary_high_line_time = indices[i]
                            break
        
        # ============================================================
        # SECONDARY LOW DETECTION - Using LINE CHART (Close prices)
        # Pattern: Primary Low -> Rise -> LOCAL TROUGH (Secondary Low) -> Rise
        # 
        # Similar to secondary high, we find the FIRST local trough after
        # the primary low, not the dip after the absolute high.
        # ============================================================
        secondary_low_line = None
        secondary_low_line_time = None
        
        df_after_low = df[df.index > low_line_idx]
        
        # Exclude secondary high candle if it exists
        if secondary_high_line_time is not None:
            df_after_low = df_after_low[df_after_low.index != secondary_high_line_time]
        
        if len(df_after_low) >= 3:
            closes = df_after_low['Close'].values
            indices = df_after_low.index.tolist()
            
            # Look for local troughs: price lower than both neighbors
            for i in range(1, len(closes) - 1):
                prev_close = closes[i - 1]
                curr_close = closes[i]
                next_close = closes[i + 1]
                
                # Is this a local trough? (lower than both neighbors)
                if curr_close < prev_close and curr_close < next_close:
                    # Is it higher than primary low? (required for secondary)
                    if curr_close > low_line_price:
                        # Is it at least 5 points above primary?
                        if (curr_close - low_line_price) >= SECONDARY_PIVOT_MIN_DISTANCE:
                            # Found the first valid secondary low
                            secondary_low_line = curr_close
                            secondary_low_line_time = indices[i]
                            break
        
        # Candlestick secondary detection (for reference) - using same local peak logic
        secondary_high = None
        secondary_high_time = None
        secondary_low = None
        secondary_low_time = None
        
        df_after_high_candle = df[df.index > high_idx]
        if len(df_after_high_candle) >= 3:
            highs = df_after_high_candle['High'].values
            indices_candle = df_after_high_candle.index.tolist()
            
            for i in range(1, len(highs) - 1):
                if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
                    if highs[i] < high_price and (high_price - highs[i]) >= SECONDARY_PIVOT_MIN_DISTANCE:
                        secondary_high = highs[i]
                        secondary_high_time = indices_candle[i]
                        break
        
        df_after_low_candle = df[df.index > low_idx]
        if secondary_high_time is not None:
            df_after_low_candle = df_after_low_candle[df_after_low_candle.index != secondary_high_time]
        if len(df_after_low_candle) >= 3:
            lows = df_after_low_candle['Low'].values
            indices_candle = df_after_low_candle.index.tolist()
            
            for i in range(1, len(lows) - 1):
                if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
                    if lows[i] > low_price and (lows[i] - low_price) >= SECONDARY_PIVOT_MIN_DISTANCE:
                        secondary_low = lows[i]
                        secondary_low_time = indices_candle[i]
                        break
        
        return {
            'date': prior_date,
            # Candlestick (wick) values
            'high': high_price,
            'high_time': high_time,
            'low': low_price,
            'low_time': low_time,
            'close': close_price,
            'close_time': close_time,
            'open': df['Open'].iloc[0],
            'range': df['High'].max() - df['Low'].min(),
            'range_pct': (df['High'].max() - df['Low'].min()) / close_price,
            'power_hour_filtered': power_hour_filtered,
            'secondary_high': secondary_high,
            'secondary_high_time': secondary_high_time,
            'secondary_low': secondary_low,
            'secondary_low_time': secondary_low_time,
            # LINE CHART values (RECOMMENDED)
            'high_line': high_line_price,
            'high_line_time': high_line_time,
            'low_line': low_line_price,
            'low_line_time': low_line_time,
            'secondary_high_line': secondary_high_line,
            'secondary_high_line_time': secondary_high_line_time,
            'secondary_low_line': secondary_low_line,
            'secondary_low_line_time': secondary_low_line_time
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

@st.cache_data(ttl=60)  # Cache for 60 seconds for more real-time updates
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
            return {'offset': 0, 'current': None, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0, 'df_overnight': None}
        
        offset = 8  # Default: ES typically ~8 pts higher than SPX
        if not df_spx.empty and not df_es.empty:
            try:
                # Compare ES and SPX at the same time (2:30 PM CT)
                # Both actively trading at this time = reliable comparison
                
                df_es_ct = df_es.copy()
                df_es_ct.index = df_es_ct.index.tz_convert(CT_TZ)
                
                df_spx_ct = df_spx.copy()
                df_spx_ct.index = df_spx_ct.index.tz_convert(CT_TZ)
                
                # Get ES at 2:30 PM CT
                es_at_230 = df_es_ct[df_es_ct.index.time <= time(14, 30)]
                # Get SPX at 2:30 PM CT  
                spx_at_230 = df_spx_ct[df_spx_ct.index.time <= time(14, 30)]
                
                if not es_at_230.empty and not spx_at_230.empty:
                    es_price = float(es_at_230['Close'].iloc[-1])
                    spx_price = float(spx_at_230['Close'].iloc[-1])
                    calculated_offset = es_price - spx_price
                    
                    # ES should always be higher than SPX (positive offset)
                    # If calculation gives negative or zero, use default
                    if calculated_offset > 0:
                        offset = calculated_offset
                    else:
                        offset = 8  # Default if calculation seems wrong
            except Exception:
                offset = 8  # Default spread
        
        overnight_start = CT_TZ.localize(datetime.combine(prior_date, time(17, 0)))
        
        # For ACTIVE CONE detection: extend to 10:00 AM CT to capture early RTH breaks
        ct_now = get_ct_now()
        if ct_now.time() < time(10, 0):
            overnight_end = ct_now
        else:
            overnight_end = CT_TZ.localize(datetime.combine(session_date, time(10, 0)))
        
        df_es_tz = df_es.copy()
        df_es_tz.index = df_es_tz.index.tz_convert(CT_TZ)
        
        overnight_mask = (df_es_tz.index >= overnight_start) & (df_es_tz.index <= overnight_end)
        df_overnight = df_es_tz[overnight_mask]
        
        if df_overnight.empty:
            return {'offset': offset, 'current': None, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0, 'df_overnight': None}
        
        overnight_high = df_overnight['High'].max()
        overnight_low = df_overnight['Low'].min()
        
        # For ENTRY INVALIDATION: only use true overnight (before 8:30am RTH open)
        # Breaks during RTH are part of normal trading, not invalidation
        pre_rth_end = CT_TZ.localize(datetime.combine(session_date, time(8, 30)))
        pre_rth_mask = (df_es_tz.index >= overnight_start) & (df_es_tz.index < pre_rth_end)
        df_pre_rth = df_es_tz[pre_rth_mask]
        
        if not df_pre_rth.empty:
            pre_rth_high = df_pre_rth['High'].max()
            pre_rth_low = df_pre_rth['Low'].min()
        else:
            pre_rth_high = overnight_high
            pre_rth_low = overnight_low
        
        # Get current ES price (most recent)
        current_es = float(df_es['Close'].iloc[-1]) if not df_es.empty else None
        
        return {
            'offset': offset,
            'current': current_es,
            'overnight_high': overnight_high,
            'overnight_low': overnight_low,
            'overnight_high_spx': overnight_high - offset,
            'overnight_low_spx': overnight_low - offset,
            'overnight_range': overnight_high - overnight_low,
            'df_overnight': df_overnight,
            # Pre-RTH values for entry invalidation (only before 8:30am)
            'pre_rth_high': pre_rth_high,
            'pre_rth_low': pre_rth_low,
            'pre_rth_high_spx': pre_rth_high - offset,
            'pre_rth_low_spx': pre_rth_low - offset
        }
        
    except Exception as e:
        return {'offset': 0, 'current': None, 'overnight_high': None, 'overnight_low': None, 'overnight_range': 0, 'df_overnight': None, 'pre_rth_high': None, 'pre_rth_low': None, 'pre_rth_high_spx': None, 'pre_rth_low_spx': None}

# ============================================================================
# VIX OVERNIGHT SIGNAL SYSTEM
# ============================================================================
# 
# This system uses VIX futures (VX=F) overnight behavior to confirm/invalidate
# SPX trade setups at cone rails.
#
# LOGIC:
# 1. Find "Anchor" low/high close between 5pm-12am CT
# 2. Check if 2-3am tests and respects OR breaks the anchor
# 3. After 6:30am, check if anchor still holds
# 4. Generate signal: CONFIRMED, INVALIDATED, or RETEST
#
# SIGNALS:
# - Anchor Low holds + no new low after 6:30am = SELL at Close Cone ▲ CONFIRMED
# - Anchor Low breaks after 6:30am = SELL INVALIDATED (breakout day)
# - Anchor Low breaks drastically at 2-3am = RETEST setup at 10am
# - Vice versa for BUY signals using Anchor High

@st.cache_data(ttl=60)
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
    except Exception:
        return None

def fetch_todays_session_range() -> Dict:
    """Fetch today's actual session high and low from Yahoo Finance."""
    try:
        spx = yf.Ticker("^GSPC")
        data = spx.history(period='1d', interval='1m')
        if not data.empty:
            return {
                'high': float(data['High'].max()),
                'low': float(data['Low'].min()),
                'current': float(data['Close'].iloc[-1])
            }
        return {'high': None, 'low': None, 'current': None}
    except Exception:
        return {'high': None, 'low': None, 'current': None}

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
    except Exception:
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

def determine_active_cone(cones: List[Cone], es_data: Dict, session_high: float = None, session_low: float = None) -> Dict:
    """
    Determine which cone is ACTIVE based on overnight ES behavior and RTH price action.
    
    RULES:
    - If ES stayed within Close cone overnight → Close cone is active
    - If ES broke ABOVE Close cone ▲ → High cone is active  
    - If ES broke BELOW Close cone ▼ → Low cone is active
    
    RAIL REVERSAL RULES (for 10am entries):
    - Low cone active + RTH rises through Low ▲ → Low ▲ becomes BUY point (not sell)
    - High cone active + RTH drops through High ▼ → High ▼ becomes SELL point (not buy)
    
    Returns dict with:
        - 'active_cone': 'Close', 'High', or 'Low'
        - 'rail_reversal': None, 'low_top_is_buy', or 'high_bottom_is_sell'
        - 'reason': Explanation string
    """
    result = {
        'active_cone': 'Close',
        'rail_reversal': None,
        'reason': 'Default to Close cone'
    }
    
    if not es_data or es_data.get('overnight_high_spx') is None:
        result['reason'] = 'No overnight data - using Close cone'
        return result
    
    overnight_high_spx = es_data.get('overnight_high_spx')
    overnight_low_spx = es_data.get('overnight_low_spx')
    
    # Find cones
    close_cone = next((c for c in cones if c.name == 'Close'), None)
    high_cone = next((c for c in cones if c.name == 'High'), None)
    low_cone = next((c for c in cones if c.name == 'Low'), None)
    
    if not close_cone:
        return result
    
    # Check if ES broke above Close cone (use 2pt buffer)
    broke_above = overnight_high_spx > close_cone.ascending_rail + 2
    
    # Check if ES broke below Close cone (use 2pt buffer)
    broke_below = overnight_low_spx < close_cone.descending_rail - 2
    
    if broke_above and not broke_below:
        result['active_cone'] = 'High'
        result['reason'] = 'ES broke ABOVE Close cone overnight → High cone entries'
        
        # Check for RTH rail reversal: High ▼ becomes SELL point ONLY IF:
        # 1. Session HIGH first touched High ▲ (top) - we went up first
        # 2. THEN session LOW broke below High ▼ (bottom) - we reversed down through
        if high_cone and session_low is not None and session_high is not None:
            touched_top_first = session_high >= high_cone.ascending_rail - 2
            broke_through_bottom = session_low < high_cone.descending_rail - 2
            if touched_top_first and broke_through_bottom:
                result['rail_reversal'] = 'high_bottom_is_sell'
                result['reason'] = 'ES broke above Close overnight, RTH touched High ▲ then broke through High ▼ → High ▼ is SELL point'
                
    elif broke_below and not broke_above:
        result['active_cone'] = 'Low'
        result['reason'] = 'ES broke BELOW Close cone overnight → Low cone entries'
        
        # Check for RTH rail reversal: Low ▲ becomes BUY point ONLY IF:
        # 1. Session LOW first touched Low ▼ (bottom) - we went down first
        # 2. THEN session HIGH broke above Low ▲ (top) - we reversed up through
        if low_cone and session_high is not None and session_low is not None:
            touched_bottom_first = session_low <= low_cone.descending_rail + 2
            broke_through_top = session_high > low_cone.ascending_rail + 2
            if touched_bottom_first and broke_through_top:
                result['rail_reversal'] = 'low_top_is_buy'
                result['reason'] = 'ES broke below Close overnight, RTH touched Low ▼ then broke through Low ▲ → Low ▲ is BUY point'
                
    elif broke_above and broke_below:
        # Both broken - use which one broke more significantly
        above_break = overnight_high_spx - close_cone.ascending_rail
        below_break = close_cone.descending_rail - overnight_low_spx
        if above_break > below_break:
            result['active_cone'] = 'High'
            result['reason'] = 'ES broke both directions, more above → High cone entries'
        else:
            result['active_cone'] = 'Low'
            result['reason'] = 'ES broke both directions, more below → Low cone entries'
    else:
        result['active_cone'] = 'Close'
        result['reason'] = 'ES stayed within Close cone overnight → Close cone entries'
    
    return result

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
# TRADE SETUP GENERATOR - Creates complete trade plans from confluence zones
# ============================================================================

@dataclass
class TradeSetup:
    """Complete trade setup for a confluence zone."""
    direction: str  # CALLS or PUTS
    trade_type: str  # BUY POINT or SELL POINT
    entry_price: float  # The confluence zone price
    confluence_rails: List[str]  # Which rails form this confluence
    confluence_strength: int  # Number of rails converging
    strike: int  # Recommended option strike
    strike_label: str  # e.g., "SPX 6810C"
    stop_loss: float  # Stop level in underlying
    target_50: float  # 50% target
    target_75: float  # 75% target  
    target_100: float  # 100% target (opposite side of cone)
    profit_50: float  # Expected $ profit at 50% (theoretical)
    profit_75: float  # Expected $ profit at 75% (theoretical)
    profit_100: float  # Expected $ profit at 100% (theoretical)
    profit_50_theta_adjusted: float  # Theta-adjusted profit at 50%
    risk_dollars: float  # Risk in dollars
    rr_ratio: float  # Risk/reward at 50% (theoretical)
    rr_ratio_theta_adjusted: float  # R:R accounting for theta
    cone_width: float  # Width of the trading range
    delta_estimate: float  # Estimated delta for this strike
    theta_period: str  # Time period for theta (morning, mid_day, etc.)
    rail_type: str = ""  # ASCENDING or DESCENDING
    overnight_broken: bool = False  # True if ES broke this level overnight
    follow_through_pct: float = 1.0  # Expected follow-through (0.70-0.75 if 8:30 already touched)
    distance: float = 0.0  # Distance from current price (set dynamically)
    triggered: bool = False  # True if entry was triggered today (set dynamically)

def generate_trade_setups(cones: List[Cone], current_price: float = None, 
                          es_data: Dict = None, session_830_touched: Dict = None,
                          active_cone_info: Dict = None) -> Dict:
    """
    Generate complete trade setups for all confluence zones.
    
    This is the MAIN function that connects everything:
    - Finds confluence zones
    - Calculates exact entry, stop, targets
    - Recommends specific contract strike
    - Calculates expected profit/risk
    - Marks entries broken overnight
    - Applies 70-75% follow-through if 8:30 already touched
    - Filters to show only ACTIVE CONE entries based on overnight behavior
    - Applies RAIL REVERSAL when RTH breaks through active cone edge
    
    Args:
        cones: List of Cone objects at the evaluation time
        current_price: Current SPX price
        es_data: Overnight ES data with overnight_high_spx and overnight_low_spx
        session_830_touched: Dict with 'high_touched' and 'low_touched' booleans for 8:30am touch
        active_cone_info: Dict from determine_active_cone with 'active_cone', 'rail_reversal', 'reason'
    
    Returns dict with 'calls_setups' and 'puts_setups' lists.
    """
    
    confluence_data = find_confluence_zones(cones)
    calls_setups = []
    puts_setups = []
    
    # Extract active cone info
    active_cone = None
    rail_reversal = None
    active_cone_reason = "Close cone (default)"
    
    if active_cone_info:
        active_cone = active_cone_info.get('active_cone', 'Close')
        rail_reversal = active_cone_info.get('rail_reversal')
        active_cone_reason = active_cone_info.get('reason', '')
    
    # Get overnight levels for validation (includes up to 10am for active cone detection)
    overnight_high_spx = None
    overnight_low_spx = None
    # Get PRE-RTH levels for entry invalidation (only before 8:30am)
    # Breaks during RTH are part of normal trading, not invalidation
    pre_rth_high_spx = None
    pre_rth_low_spx = None
    if es_data:
        overnight_high_spx = es_data.get('overnight_high_spx')
        overnight_low_spx = es_data.get('overnight_low_spx')
        pre_rth_high_spx = es_data.get('pre_rth_high_spx')
        pre_rth_low_spx = es_data.get('pre_rth_low_spx')
    
    # Check if 8:30 already touched an edge (for 70-75% follow-through rule)
    touched_830_high = session_830_touched.get('high_touched', False) if session_830_touched else False
    touched_830_low = session_830_touched.get('low_touched', False) if session_830_touched else False
    
    # Get average cone width for target calculation
    avg_cone_width = sum(c.ascending_rail - c.descending_rail for c in cones) / len(cones) if cones else 30
    
    # =========================================================================
    # CALLS SETUPS - From descending rail confluences (support zones)
    # =========================================================================
    for zone in confluence_data.get('calls_confluence', []):
        entry_price = zone['price']
        rails = zone['rails']
        strength = zone.get('strength', len(rails))
        
        # Check if this entry was BROKEN overnight (pre-RTH, before 8:30am)
        # RTH breaks are part of trading, not invalidation
        overnight_broken = False
        if pre_rth_low_spx is not None and pre_rth_low_spx < entry_price - 2:
            overnight_broken = True
        
        # Check for reduced follow-through (8:30 already touched this zone)
        # If 8:30 bounced from descending rail, 10am touch has 70-75% follow-through
        follow_through_pct = 1.0
        if touched_830_low:
            follow_through_pct = 0.725  # Average of 70-75%
        
        # Find the corresponding ascending rail for target (opposite side)
        # Use the average of ascending rails from the cones that form this confluence
        target_prices = []
        for cone in cones:
            for rail in rails:
                if cone.name in rail:
                    target_prices.append(cone.ascending_rail)
                    break
        
        if target_prices:
            target_100 = sum(target_prices) / len(target_prices)
        else:
            target_100 = entry_price + avg_cone_width
        
        cone_width = target_100 - entry_price
        
        # Skip if cone width is too small
        if cone_width < MIN_CONE_WIDTH:
            continue
        
        # Calculate targets (apply follow-through adjustment)
        effective_width = cone_width * follow_through_pct
        target_50 = entry_price + (effective_width * 0.50)
        target_75 = entry_price + (effective_width * 0.75)
        target_100 = entry_price + effective_width
        stop_loss = entry_price - STOP_LOSS_PTS
        
        # Calculate strike (OTM CALLS = strike ABOVE entry price)
        strike = int(entry_price + STRIKE_OFFSET)
        strike = ((strike + 4) // 5) * 5  # Round UP to nearest 5
        strike_label = f"SPX {strike}C"
        
        # Get accurate delta estimate based on OTM distance
        otm_distance = strike - entry_price
        delta_estimate = get_delta_estimate(otm_distance)
        
        # Calculate profits using accurate delta (with follow-through adjustment)
        move_50 = effective_width * 0.50
        move_75 = effective_width * 0.75
        move_100 = effective_width
        
        profit_50 = move_50 * delta_estimate * 100
        profit_75 = move_75 * delta_estimate * 100
        profit_100 = move_100 * delta_estimate * 100
        risk_dollars = STOP_LOSS_PTS * delta_estimate * 100
        
        # Apply theta adjustment for realistic profit expectation
        theta_mult, theta_period = get_theta_multiplier()
        profit_50_theta = profit_50 * theta_mult
        
        rr_ratio = profit_50 / risk_dollars if risk_dollars > 0 else 0
        rr_ratio_theta = profit_50_theta / risk_dollars if risk_dollars > 0 else 0
        
        setup = TradeSetup(
            direction='CALLS',
            trade_type='BUY POINT',  # Descending rails are buy points
            entry_price=entry_price,
            confluence_rails=rails,
            confluence_strength=strength,
            strike=strike,
            strike_label=strike_label,
            stop_loss=stop_loss,
            target_50=target_50,
            target_75=target_75,
            target_100=target_100,
            profit_50=profit_50,
            profit_75=profit_75,
            profit_100=profit_100,
            profit_50_theta_adjusted=profit_50_theta,
            risk_dollars=risk_dollars,
            rr_ratio=rr_ratio,
            rr_ratio_theta_adjusted=rr_ratio_theta,
            cone_width=cone_width,
            delta_estimate=delta_estimate,
            theta_period=theta_period,
            rail_type='DESCENDING',
            overnight_broken=overnight_broken,
            follow_through_pct=follow_through_pct
        )
        calls_setups.append(setup)
    
    # =========================================================================
    # PUTS SETUPS - From ascending rail confluences (resistance zones)
    # =========================================================================
    for zone in confluence_data.get('puts_confluence', []):
        entry_price = zone['price']
        rails = zone['rails']
        strength = zone.get('strength', len(rails))
        
        # Check if this entry was BROKEN overnight (pre-RTH, before 8:30am)
        # RTH breaks are part of trading, not invalidation
        overnight_broken = False
        if pre_rth_high_spx is not None and pre_rth_high_spx > entry_price + 2:
            overnight_broken = True
        
        # Check for reduced follow-through (8:30 already touched this zone)
        # If 8:30 rejected from ascending rail, 10am touch has 70-75% follow-through
        follow_through_pct = 1.0
        if touched_830_high:
            follow_through_pct = 0.725  # Average of 70-75%
        
        # Find the corresponding descending rail for target (opposite side)
        target_prices = []
        for cone in cones:
            for rail in rails:
                if cone.name in rail:
                    target_prices.append(cone.descending_rail)
                    break
        
        if target_prices:
            target_100 = sum(target_prices) / len(target_prices)
        else:
            target_100 = entry_price - avg_cone_width
        
        cone_width = entry_price - target_100
        
        # Skip if cone width is too small
        if cone_width < MIN_CONE_WIDTH:
            continue
        
        # Calculate targets
        # Calculate targets (apply follow-through adjustment)
        effective_width = cone_width * follow_through_pct
        target_50 = entry_price - (effective_width * 0.50)
        target_75 = entry_price - (effective_width * 0.75)
        target_100 = entry_price - effective_width
        stop_loss = entry_price + STOP_LOSS_PTS
        
        # Calculate strike (OTM PUTS = strike BELOW entry price)
        strike = int(entry_price - STRIKE_OFFSET)
        strike = (strike // 5) * 5  # Round DOWN to nearest 5
        strike_label = f"SPX {strike}P"
        
        # Get accurate delta estimate based on OTM distance
        otm_distance = entry_price - strike
        delta_estimate = get_delta_estimate(otm_distance)
        
        # Calculate profits using accurate delta (with follow-through adjustment)
        move_50 = effective_width * 0.50
        move_75 = effective_width * 0.75
        move_100 = effective_width
        
        profit_50 = move_50 * delta_estimate * 100
        profit_75 = move_75 * delta_estimate * 100
        profit_100 = move_100 * delta_estimate * 100
        risk_dollars = STOP_LOSS_PTS * delta_estimate * 100
        
        # Apply theta adjustment
        theta_mult, theta_period = get_theta_multiplier()
        profit_50_theta = profit_50 * theta_mult
        
        rr_ratio = profit_50 / risk_dollars if risk_dollars > 0 else 0
        rr_ratio_theta = profit_50_theta / risk_dollars if risk_dollars > 0 else 0
        
        setup = TradeSetup(
            direction='PUTS',
            trade_type='SELL POINT',  # Ascending rails are sell points
            entry_price=entry_price,
            confluence_rails=rails,
            confluence_strength=strength,
            strike=strike,
            strike_label=strike_label,
            stop_loss=stop_loss,
            target_50=target_50,
            target_75=target_75,
            target_100=target_100,
            profit_50=profit_50,
            profit_75=profit_75,
            profit_100=profit_100,
            profit_50_theta_adjusted=profit_50_theta,
            risk_dollars=risk_dollars,
            rr_ratio=rr_ratio,
            rr_ratio_theta_adjusted=rr_ratio_theta,
            cone_width=cone_width,
            delta_estimate=delta_estimate,
            theta_period=theta_period,
            rail_type='ASCENDING',
            overnight_broken=overnight_broken,
            follow_through_pct=follow_through_pct
        )
        puts_setups.append(setup)
    
    # Sort by R:R (theta-adjusted) - best first
    calls_setups.sort(key=lambda x: x.rr_ratio_theta_adjusted, reverse=True)
    puts_setups.sort(key=lambda x: x.rr_ratio_theta_adjusted, reverse=True)
    
    # Also include single-rail setups for reference (lower priority)
    # These are individual rails without confluence
    single_calls = []
    single_puts = []
    
    for level in confluence_data.get('all_calls_levels', []):
        # Check if this level is already in a confluence
        is_in_confluence = any(
            abs(level['price'] - setup.entry_price) < 5 
            for setup in calls_setups
        )
        if not is_in_confluence:
            single_calls.append({
                'price': level['price'],
                'rail': level['name'],
                'type': 'single'
            })
    
    for level in confluence_data.get('all_puts_levels', []):
        is_in_confluence = any(
            abs(level['price'] - setup.entry_price) < 5 
            for setup in puts_setups
        )
        if not is_in_confluence:
            single_puts.append({
                'price': level['price'],
                'rail': level['name'],
                'type': 'single'
            })
    
    # =========================================================================
    # FILTER BY ACTIVE CONE
    # =========================================================================
    # Only show entries from the active cone based on overnight behavior
    # Close = stayed in range, High = broke above, Low = broke below
    
    if active_cone:
        # Filter CALLS setups - keep only those from active cone
        calls_setups = [
            s for s in calls_setups 
            if any(active_cone in rail for rail in s.confluence_rails)
        ]
        
        # Filter PUTS setups - keep only those from active cone
        puts_setups = [
            s for s in puts_setups 
            if any(active_cone in rail for rail in s.confluence_rails)
        ]
        
        # Filter single rails too
        single_calls = [s for s in single_calls if active_cone in s['rail']]
        single_puts = [s for s in single_puts if active_cone in s['rail']]
        
        # =====================================================================
        # CREATE SETUPS FOR ACTIVE CONE (High or Low)
        # =====================================================================
        # When High or Low cone is active, we need BOTH rails of that cone:
        # 
        # LOW CONE ACTIVE (broke below Close overnight):
        #   - Low ▼ (descending/bottom) = BUY point (support)
        #   - Low ▲ (ascending/top) = SELL point (resistance)
        #
        # HIGH CONE ACTIVE (broke above Close overnight):
        #   - High ▼ (descending/bottom) = BUY point (support)  
        #   - High ▲ (ascending/top) = SELL point (resistance)
        #
        # ALSO include secondary cones (Low2, High2) if they exist!
        #
        # This replaces any filtering - we directly create setups from the active cone(s)
        
        if active_cone in ['High', 'Low']:
            # Clear any filtered setups - we'll create fresh ones
            calls_setups = []
            puts_setups = []
            
            delta_estimate = get_delta_estimate(STRIKE_OFFSET)
            theta_mult, theta_period = get_theta_multiplier()
            risk_dollars = STOP_LOSS_PTS * delta_estimate * 100
            
            # Determine which cones to use based on active direction
            # Low active -> use Low and Low² (if exists)
            # High active -> use High and High² (if exists)
            if active_cone == 'Low':
                active_cones_to_use = [c for c in cones if c.name in ['Low', 'Low²']]
            else:  # High
                active_cones_to_use = [c for c in cones if c.name in ['High', 'High²']]
            
            for cone_obj in active_cones_to_use:
                cone_width = cone_obj.width
                cone_name = cone_obj.name
                
                # -----------------------------------------------------------------
                # BUY POINT: Bottom of cone (descending rail)
                # -----------------------------------------------------------------
                buy_entry = cone_obj.descending_rail
                buy_stop = buy_entry - STOP_LOSS_PTS
                buy_target_50 = buy_entry + (cone_width * 0.5)
                buy_target_75 = buy_entry + (cone_width * 0.75)
                buy_target_100 = cone_obj.ascending_rail  # Top of cone
                
                # Strike for CALLS (above entry)
                buy_strike = int(buy_entry + STRIKE_OFFSET)
                buy_strike = ((buy_strike + 4) // 5) * 5
                
                # Profit calculations
                buy_profit_50 = (buy_target_50 - buy_entry) * delta_estimate * 100
                buy_profit_75 = (buy_target_75 - buy_entry) * delta_estimate * 100
                buy_profit_100 = (buy_target_100 - buy_entry) * delta_estimate * 100
                buy_profit_50_theta = buy_profit_50 * theta_mult
                buy_rr = buy_profit_50 / risk_dollars if risk_dollars > 0 else 0
                buy_rr_theta = buy_profit_50_theta / risk_dollars if risk_dollars > 0 else 0
                
                # Check if broken overnight (pre-RTH only, before 8:30am)
                buy_overnight_broken = False
                if pre_rth_low_spx is not None and pre_rth_low_spx < buy_entry - 2:
                    buy_overnight_broken = True
                
                calls_setup = TradeSetup(
                    direction='CALLS',
                    trade_type='BUY POINT',
                    entry_price=buy_entry,
                    confluence_rails=[f"{cone_name} ▼"],
                    confluence_strength=1,
                    strike=buy_strike,
                    strike_label=f"SPX {buy_strike}C",
                    stop_loss=buy_stop,
                    target_50=buy_target_50,
                    target_75=buy_target_75,
                    target_100=buy_target_100,
                    profit_50=buy_profit_50,
                    profit_75=buy_profit_75,
                    profit_100=buy_profit_100,
                    profit_50_theta_adjusted=buy_profit_50_theta,
                    risk_dollars=risk_dollars,
                    rr_ratio=buy_rr,
                    rr_ratio_theta_adjusted=buy_rr_theta,
                    cone_width=cone_width,
                    delta_estimate=delta_estimate,
                    theta_period=theta_period,
                    rail_type='DESCENDING',
                    overnight_broken=buy_overnight_broken,
                    follow_through_pct=1.0
                )
                calls_setups.append(calls_setup)
                
                # -----------------------------------------------------------------
                # SELL POINT: Top of cone (ascending rail)
                # -----------------------------------------------------------------
                sell_entry = cone_obj.ascending_rail
                sell_stop = sell_entry + STOP_LOSS_PTS
                sell_target_50 = sell_entry - (cone_width * 0.5)
                sell_target_75 = sell_entry - (cone_width * 0.75)
                sell_target_100 = cone_obj.descending_rail  # Bottom of cone
                
                # Strike for PUTS (below entry)
                sell_strike = int(sell_entry - STRIKE_OFFSET)
                sell_strike = (sell_strike // 5) * 5
                
                # Profit calculations
                sell_profit_50 = (sell_entry - sell_target_50) * delta_estimate * 100
                sell_profit_75 = (sell_entry - sell_target_75) * delta_estimate * 100
                sell_profit_100 = (sell_entry - sell_target_100) * delta_estimate * 100
                sell_profit_50_theta = sell_profit_50 * theta_mult
                sell_rr = sell_profit_50 / risk_dollars if risk_dollars > 0 else 0
                sell_rr_theta = sell_profit_50_theta / risk_dollars if risk_dollars > 0 else 0
                
                # Check if broken overnight (pre-RTH only, before 8:30am)
                sell_overnight_broken = False
                if pre_rth_high_spx is not None and pre_rth_high_spx > sell_entry + 2:
                    sell_overnight_broken = True
                
                puts_setup = TradeSetup(
                    direction='PUTS',
                    trade_type='SELL POINT',
                    entry_price=sell_entry,
                    confluence_rails=[f"{cone_name} ▲"],
                    confluence_strength=1,
                    strike=sell_strike,
                    strike_label=f"SPX {sell_strike}P",
                    stop_loss=sell_stop,
                    target_50=sell_target_50,
                    target_75=sell_target_75,
                    target_100=sell_target_100,
                    profit_50=sell_profit_50,
                    profit_75=sell_profit_75,
                    profit_100=sell_profit_100,
                    profit_50_theta_adjusted=sell_profit_50_theta,
                    risk_dollars=risk_dollars,
                    rr_ratio=sell_rr,
                    rr_ratio_theta_adjusted=sell_rr_theta,
                    cone_width=cone_width,
                    delta_estimate=delta_estimate,
                    theta_period=theta_period,
                    rail_type='ASCENDING',
                    overnight_broken=sell_overnight_broken,
                    follow_through_pct=1.0
                )
                puts_setups.append(puts_setup)
    
    # =========================================================================
    # RAIL REVERSAL LOGIC
    # =========================================================================
    # When certain conditions are met, ascending rails become BUY points
    # and descending rails become SELL points (opposite of normal)
    
    if rail_reversal == 'low_top_is_buy':
        # Low cone ▲ (normally SELL) becomes BUY point
        # Move any Low ▲ setups from puts to calls and flip direction
        reversed_setups = []
        remaining_puts = []
        for s in puts_setups:
            if 'Low' in ''.join(s.confluence_rails) and s.rail_type == 'ASCENDING':
                # This ascending rail is now a BUY point
                s.direction = 'CALLS'
                s.trade_type = 'BUY POINT (REVERSAL)'
                # Recalculate strike for CALLS (above entry)
                s.strike = int(s.entry_price + STRIKE_OFFSET)
                s.strike = ((s.strike + 4) // 5) * 5
                s.strike_label = f"SPX {s.strike}C"
                reversed_setups.append(s)
            else:
                remaining_puts.append(s)
        calls_setups.extend(reversed_setups)
        puts_setups = remaining_puts
        
    elif rail_reversal == 'high_bottom_is_sell':
        # High cone ▼ (normally BUY) becomes SELL point
        # Move any High ▼ setups from calls to puts and flip direction
        reversed_setups = []
        remaining_calls = []
        for s in calls_setups:
            if 'High' in ''.join(s.confluence_rails) and s.rail_type == 'DESCENDING':
                # This descending rail is now a SELL point
                s.direction = 'PUTS'
                s.trade_type = 'SELL POINT (REVERSAL)'
                # Recalculate strike for PUTS (below entry)
                s.strike = int(s.entry_price - STRIKE_OFFSET)
                s.strike = (s.strike // 5) * 5
                s.strike_label = f"SPX {s.strike}P"
                reversed_setups.append(s)
            else:
                remaining_calls.append(s)
        puts_setups.extend(reversed_setups)
        calls_setups = remaining_calls
    
    return {
        'calls_setups': calls_setups,
        'puts_setups': puts_setups,
        'single_calls': single_calls,
        'single_puts': single_puts,
        'active_cone': active_cone,
        'rail_reversal': rail_reversal,
        'active_cone_reason': active_cone_reason
    }

def render_institutional_trade_card(setup: TradeSetup, current_price: float, entry_status: dict = None, vix_signal: dict = None):
    """Render a professional institutional-style trade card with entry confirmation status and VIX confirmation."""
    
    # Calculate distance
    distance = abs(current_price - setup.entry_price)
    
    # Determine VIX confirmation status for this setup
    vix_confirmed = None
    vix_status_html = ""
    if vix_signal and vix_signal.get('direction_confirmed'):
        trade_direction = vix_signal.get('trade_direction')
        
        # Check if VIX direction matches this setup
        if setup.direction == "PUTS" and trade_direction == "PUTS":
            vix_confirmed = True
            vix_status_html = '<div style="background: #d1fae5; border: 1px solid #10b981; border-radius: 4px; padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.75rem; color: #065f46;">✅ VIX CONFIRMED PUTS — VIX rejected UP → SPX will DROP</div>'
        elif setup.direction == "CALLS" and trade_direction == "CALLS":
            vix_confirmed = True
            vix_status_html = '<div style="background: #d1fae5; border: 1px solid #10b981; border-radius: 4px; padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.75rem; color: #065f46;">✅ VIX CONFIRMED CALLS — VIX rejected DOWN → SPX will RISE</div>'
        elif setup.direction == "PUTS" and trade_direction == "CALLS":
            vix_confirmed = False
            vix_status_html = '<div style="background: #fee2e2; border: 1px solid #ef4444; border-radius: 4px; padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.75rem; color: #991b1b;">⛔ VIX SAYS CALLS — This PUTS setup goes against VIX signal</div>'
        elif setup.direction == "CALLS" and trade_direction == "PUTS":
            vix_confirmed = False
            vix_status_html = '<div style="background: #fee2e2; border: 1px solid #ef4444; border-radius: 4px; padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.75rem; color: #991b1b;">⛔ VIX SAYS PUTS — This CALLS setup goes against VIX signal</div>'
    elif vix_signal and vix_signal.get('anchor_low', 0) > 0:
        # VIX data entered but no signal yet
        vix_status_html = '<div style="background: #fef3c7; border: 1px solid #f59e0b; border-radius: 4px; padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.75rem; color: #92400e;">⏳ WAITING FOR VIX SIGNAL — Watch 9-9:30am rejection</div>'
    
    # Determine status based on entry confirmation system
    if entry_status:
        es = entry_status.get('status', 'WAITING')
        if es == 'CONFIRMED':
            status = "ENTER NOW"
            status_class = "badge-go"
        elif es == 'TOUCHED' or es == 'CONFIRMING':
            status = "CONFIRMING"
            status_class = "badge-wait"
        elif es == 'APPROACHING':
            status = "APPROACHING"
            status_class = "badge-wait"
        elif es == 'EXPIRED':
            status = "EXPIRED"
            status_class = "badge-nogo"
        elif es == 'INVALIDATED':
            status = "INVALID"
            status_class = "badge-nogo"
        elif setup.overnight_broken:
            status = "BROKEN"
            status_class = "badge-nogo"
        else:
            status = "WAITING"
            status_class = "badge-nogo"
    else:
        # Fallback to distance-based status
        if setup.overnight_broken:
            status = "INVALID"
            status_class = "badge-nogo"
        elif distance <= AT_RAIL_THRESHOLD:
            status = "ACTIVE"
            status_class = "badge-go"
        elif distance <= 15:
            status = "WATCH"
            status_class = "badge-wait"
        else:
            status = "STANDBY"
            status_class = "badge-nogo"
    
    # Direction styling
    direction_class = "badge-calls" if setup.direction == "CALLS" else "badge-puts"
    
    # Trade type styling (BUY = green, SELL = red)
    trade_type_class = "badge-go" if "BUY" in setup.trade_type else "badge-nogo"
    
    # GO/NO-GO (broken overnight = automatic NO-GO, VIX invalidated = NO-GO)
    ct_now = get_ct_now().time()
    time_ok = ct_now < LAST_ENTRY_TIME
    rr_ok = setup.rr_ratio_theta_adjusted >= MIN_RR_RATIO
    width_ok = setup.cone_width >= MIN_CONE_WIDTH
    confluence_ok = setup.confluence_strength >= 1  # Allow single-rail setups for active cones
    not_broken = not setup.overnight_broken
    vix_ok = vix_confirmed is not False  # True or None = OK, False = NOT OK
    
    if rr_ok and width_ok and confluence_ok and time_ok and not_broken and vix_ok:
        decision = "GO"
        decision_class = "badge-go"
    else:
        decision = "NO-GO"
        decision_class = "badge-nogo"
    
    # Theta multiplier for display
    theta_mult = THETA_MULTIPLIER.get(setup.theta_period, 1.0)
    
    # Build warnings HTML
    warnings_html = ""
    if setup.overnight_broken:
        warnings_html += '<div style="background: rgba(239, 68, 68, 0.2); border: 1px solid var(--accent-red); border-radius: 4px; padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.75rem; color: var(--accent-red);">❌ BROKEN OVERNIGHT — Entry invalidated</div>'
    if setup.follow_through_pct < 1.0:
        pct = int(setup.follow_through_pct * 100)
        warnings_html += f'<div style="background: rgba(245, 158, 11, 0.2); border: 1px solid var(--accent-gold); border-radius: 4px; padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.75rem; color: var(--accent-gold);">⚠️ 8:30 already touched — Expect {pct}% follow-through</div>'
    
    # Add VIX status to warnings
    warnings_html += vix_status_html
    
    # Entry confirmation status HTML
    entry_status_html = ""
    if entry_status:
        es = entry_status.get('status', 'WAITING')
        msg = entry_status.get('message', '')
        time_rem = entry_status.get('time_remaining')
        
        if es == 'CONFIRMED':
            entry_status_html = f'<div style="background: rgba(16, 185, 129, 0.3); border: 2px solid #10b981; border-radius: 4px; padding: 0.75rem; margin-bottom: 0.5rem; font-size: 0.85rem; color: #10b981; font-weight: 600; text-align: center; animation: pulse 1s infinite;">✅ {msg}</div>'
        elif es == 'TOUCHED' or es == 'CONFIRMING':
            entry_status_html = f'<div style="background: rgba(245, 158, 11, 0.2); border: 1px solid #f59e0b; border-radius: 4px; padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.75rem; color: #f59e0b;">🎯 {msg}</div>'
        elif es == 'APPROACHING':
            entry_status_html = f'<div style="background: rgba(59, 130, 246, 0.2); border: 1px solid #3b82f6; border-radius: 4px; padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.75rem; color: #3b82f6;">📍 {msg}</div>'
        elif es == 'EXPIRED':
            entry_status_html = f'<div style="background: rgba(107, 114, 128, 0.2); border: 1px solid #6b7280; border-radius: 4px; padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.75rem; color: #6b7280;">⏰ {msg}</div>'
    
    # Validation rule text
    if "BUY" in setup.trade_type:
        valid_rule = "<strong>✅ Valid BUY:</strong> Bearish candle touches entry, closes &lt;3pts above, 8 EMA crosses above 21 EMA + VIX anchor high holds"
    else:
        valid_rule = "<strong>✅ Valid SELL:</strong> Bullish candle touches entry, closes &lt;3pts below, 8 EMA crosses below 21 EMA + VIX anchor low holds"
    
    # Sources
    sources = ' + '.join(setup.confluence_rails)
    
    # Profit calculations
    profit_75_adj = int(setup.profit_75 * theta_mult)
    profit_100_adj = int(setup.profit_100 * theta_mult)
    
    html = f'''<div class="trade-panel">
<div class="trade-panel-header">
<div style="display: flex; align-items: center; gap: 0.5rem;">
<span class="trade-panel-badge {trade_type_class}">{setup.trade_type}</span>
<span class="trade-panel-badge {direction_class}">{setup.direction}</span>
<span style="font-family: JetBrains Mono, monospace; font-size: 1.1rem; color: var(--accent-gold); font-weight: 600;">{setup.strike_label}</span>
</div>
<div style="display: flex; gap: 0.5rem;">
<span class="trade-panel-badge {status_class}">{status}</span>
<span class="trade-panel-badge {decision_class}">{decision}</span>
</div>
</div>
<div class="trade-panel-body">
{entry_status_html}
{warnings_html}
<div class="entry-row">
<div class="entry-item"><div class="entry-label">Entry ({setup.rail_type})</div><div class="entry-value gold">{setup.entry_price:,.2f}</div></div>
<div class="entry-item"><div class="entry-label">Stop Loss</div><div class="entry-value red">{setup.stop_loss:,.2f}</div></div>
<div class="entry-item"><div class="entry-label">Target 50%</div><div class="entry-value green">{setup.target_50:,.2f}</div></div>
<div class="entry-item"><div class="entry-label">Target 100%</div><div class="entry-value green">{setup.target_100:,.2f}</div></div>
</div>
<div class="entry-row">
<div class="entry-item"><div class="entry-label">Distance</div><div class="entry-value">{distance:.1f} pts</div></div>
<div class="entry-item"><div class="entry-label">Confluence</div><div class="entry-value">{setup.confluence_strength} Rails</div></div>
<div class="entry-item"><div class="entry-label">R:R (θ-adj)</div><div class="entry-value">{setup.rr_ratio_theta_adjusted:.1f}:1</div></div>
<div class="entry-item"><div class="entry-label">Delta</div><div class="entry-value">{setup.delta_estimate:.2f}</div></div>
</div>
<div class="entry-row" style="border-bottom: none;">
<div class="entry-item"><div class="entry-label">Profit @ 50%</div><div class="entry-value green">+${setup.profit_50_theta_adjusted:,.0f}</div></div>
<div class="entry-item"><div class="entry-label">Profit @ 75%</div><div class="entry-value green">+${profit_75_adj}</div></div>
<div class="entry-item"><div class="entry-label">Profit @ 100%</div><div class="entry-value green">+${profit_100_adj}</div></div>
<div class="entry-item"><div class="entry-label">Risk</div><div class="entry-value red">-${setup.risk_dollars:,.0f}</div></div>
</div>
<div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border-color); font-size: 0.75rem; color: var(--text-muted);"><strong>Sources:</strong> {sources}</div>
<div style="margin-top: 0.5rem; padding: 0.5rem 0.75rem; background: var(--bg-tertiary); border-radius: 4px; font-size: 0.7rem; color: var(--text-secondary);">{valid_rule}</div>
</div>
</div>'''
    
    st.markdown(html, unsafe_allow_html=True)


# ============================================================================
# CONTRACT EXPECTATION ENGINE
# ============================================================================

# ============================================================================
# REGIME & SCORING
# ============================================================================

def analyze_regime(cones, es_data, prior_session, first_bar, current_price) -> RegimeAnalysis:
    """Analyze market regime - only factors that matter for trading."""
    nearest_cone, _, _ = find_nearest_rail(current_price, cones)
    
    overnight_range = es_data.get('overnight_range', 0) if es_data else 0
    overnight_range_pct = overnight_range / nearest_cone.width if nearest_cone.width > 0 else 0
    overnight_touched = check_overnight_rail_touches(cones, es_data)
    
    position, _ = get_position_in_cone(current_price, nearest_cone.ascending_rail, nearest_cone.descending_rail)
    
    return RegimeAnalysis(
        overnight_range=overnight_range,
        overnight_range_pct=overnight_range_pct,
        overnight_touched_rails=overnight_touched,
        opening_position=position,
        es_spx_offset=es_data.get('offset', 0) if es_data else 0
    )

def calculate_confluence_score(nearest_distance, regime, cones, current_price, is_10am, 
                                nearest_rail_type=None, overnight_validation=None) -> dict:
    """
    Calculate a principled confluence score based on structural edge factors.
    
    The score represents EDGE QUALITY, not probability. Higher score = more factors align.
    
    SCORING PHILOSOPHY:
    - Base: Start at 50 (neutral - no edge either way)
    - Each factor adds or subtracts based on its importance
    - Maximum theoretical score: 100
    - Minimum practical score: ~20 (many negatives)
    - Trade threshold: 65+ for full size, 50-65 reduced, <50 no trade
    
    FACTOR WEIGHTS (based on structural trading principles):
    1. CONFLUENCE (35 pts max) - Multiple rails agreeing is the core edge
    2. STRUCTURE VALIDATION (20 pts max) - Overnight behavior confirms/denies
    3. DISTANCE TO RAIL (15 pts max) - Tighter entry = better R:R
    4. TIME WINDOW (10 pts max) - Decision windows matter
    5. REGIME QUALITY (10 pts max) - Market conditions
    6. SECONDARY PIVOT ALIGNMENT (10 pts max) - Extra confirmation
    
    Returns dict with score and breakdown for transparency.
    """
    breakdown = {}
    score = 50  # Neutral starting point
    
    # =========================================================================
    # 1. CONFLUENCE - The Core Edge (up to +35 or -10)
    # Multiple rails pointing to same level = structural agreement
    # =========================================================================
    zones_data = find_confluence_zones(cones)
    calls_zones = zones_data.get('calls_confluence', [])
    puts_zones = zones_data.get('puts_confluence', [])
    
    # Check if current price is near a confluence zone
    best_confluence = None
    best_confluence_distance = float('inf')
    
    # For CALLS, check descending rail confluences
    if nearest_rail_type == 'descending':
        for zone in calls_zones:
            dist = abs(current_price - zone['price'])
            if dist < best_confluence_distance:
                best_confluence_distance = dist
                best_confluence = zone
    # For PUTS, check ascending rail confluences
    elif nearest_rail_type == 'ascending':
        for zone in puts_zones:
            dist = abs(current_price - zone['price'])
            if dist < best_confluence_distance:
                best_confluence_distance = dist
                best_confluence = zone
    
    if best_confluence and best_confluence_distance <= 10:
        num_rails = best_confluence.get('strength', len(best_confluence.get('rails', [])))
        if num_rails >= 4:
            confluence_pts = 35  # Exceptional - 4+ rails converge
            breakdown['confluence'] = f"+{confluence_pts} (4+ rails converge!)"
        elif num_rails == 3:
            confluence_pts = 28  # Excellent - 3 rails converge
            breakdown['confluence'] = f"+{confluence_pts} (3 rails converge)"
        elif num_rails == 2:
            confluence_pts = 20  # Good - 2 rails converge
            breakdown['confluence'] = f"+{confluence_pts} (2 rails converge)"
        else:
            confluence_pts = 10
            breakdown['confluence'] = f"+{confluence_pts} (weak confluence)"
        score += confluence_pts
    elif nearest_distance <= 5:
        # At a single rail but no confluence
        confluence_pts = 5
        score += confluence_pts
        breakdown['confluence'] = f"+{confluence_pts} (single rail, no confluence)"
    else:
        confluence_pts = -10
        score += confluence_pts
        breakdown['confluence'] = f"{confluence_pts} (no confluence nearby)"
    
    # =========================================================================
    # 2. STRUCTURE VALIDATION - Overnight Behavior (up to +20 or -15)
    # Did ES respect or violate the structure overnight?
    # =========================================================================
    if overnight_validation:
        validated_rails = overnight_validation.get('validated', [])
        broken_rails = overnight_validation.get('broken', [])
        
        # Check if the rail we're trading was validated
        rail_validated = False
        rail_broken = False
        
        for v in validated_rails:
            if nearest_rail_type == 'descending' and '▼' in v:
                rail_validated = True
            elif nearest_rail_type == 'ascending' and '▲' in v:
                rail_validated = True
        
        for b in broken_rails:
            if nearest_rail_type == 'descending' and '▼' in b:
                rail_broken = True
            elif nearest_rail_type == 'ascending' and '▲' in b:
                rail_broken = True
        
        if rail_validated and not rail_broken:
            validation_pts = 20
            breakdown['validation'] = f"+{validation_pts} (rail validated overnight)"
        elif rail_broken:
            validation_pts = -15
            breakdown['validation'] = f"{validation_pts} (rail BROKEN overnight!)"
        elif len(validated_rails) > 0:
            validation_pts = 10
            breakdown['validation'] = f"+{validation_pts} (other rails validated)"
        else:
            validation_pts = 0
            breakdown['validation'] = f"+{validation_pts} (no overnight validation)"
        
        score += validation_pts
    else:
        breakdown['validation'] = "+0 (no overnight data)"
    
    # =========================================================================
    # 3. DISTANCE TO RAIL (up to +15 or -5)
    # Tighter entry = better risk/reward
    # =========================================================================
    if nearest_distance <= 2:
        distance_pts = 15
        breakdown['distance'] = f"+{distance_pts} (excellent entry <2 pts)"
    elif nearest_distance <= 5:
        distance_pts = 12
        breakdown['distance'] = f"+{distance_pts} (good entry <5 pts)"
    elif nearest_distance <= 10:
        distance_pts = 8
        breakdown['distance'] = f"+{distance_pts} (acceptable <10 pts)"
    elif nearest_distance <= 15:
        distance_pts = 3
        breakdown['distance'] = f"+{distance_pts} (wide entry <15 pts)"
    else:
        distance_pts = -5
        breakdown['distance'] = f"{distance_pts} (too far from rail)"
    score += distance_pts
    
    # =========================================================================
    # 4. TIME WINDOW (up to +10)
    # Decision windows provide cleaner entries
    # =========================================================================
    ct_now = get_ct_now()
    ct_time = ct_now.time()
    
    # Check if within 30 mins of key decision times
    is_830_window = time(8, 15) <= ct_time <= time(9, 0)
    is_1000_window = time(9, 45) <= ct_time <= time(10, 15)
    
    if is_1000_window:
        time_pts = 10
        breakdown['time'] = f"+{time_pts} (10:00 AM decision window)"
    elif is_830_window:
        time_pts = 8
        breakdown['time'] = f"+{time_pts} (8:30 AM open window)"
    elif time(10, 15) < ct_time < time(14, 0):
        time_pts = 3
        breakdown['time'] = f"+{time_pts} (mid-day)"
    else:
        time_pts = 0
        breakdown['time'] = f"+{time_pts} (outside optimal windows)"
    score += time_pts
    
    # =========================================================================
    # 5. OVERNIGHT BEHAVIOR (simple: tight = good, wide = neutral)
    # Only matters if extreme - minor variations don't predict outcome
    # =========================================================================
    if regime.overnight_range_pct < 0.25:
        regime_pts = 5
        breakdown['overnight'] = f"+{regime_pts} (tight overnight - structure respected)"
    elif regime.overnight_range_pct > 0.60:
        regime_pts = -5
        breakdown['overnight'] = f"{regime_pts} (wide overnight - volatile)"
    else:
        regime_pts = 0
        breakdown['overnight'] = f"+{regime_pts} (normal overnight range)"
    score += regime_pts
    
    # =========================================================================
    # 6. SECONDARY PIVOT ALIGNMENT (up to +10)
    # If secondary pivots also project to this level = extra confluence
    # =========================================================================
    secondary_alignment = False
    for cone in cones:
        if 'High²' in cone.name or 'Low²' in cone.name:
            if nearest_rail_type == 'descending':
                if abs(cone.descending_rail - current_price) <= CONFLUENCE_THRESHOLD:
                    secondary_alignment = True
            elif nearest_rail_type == 'ascending':
                if abs(cone.ascending_rail - current_price) <= CONFLUENCE_THRESHOLD:
                    secondary_alignment = True
    
    if secondary_alignment:
        secondary_pts = 10
        breakdown['secondary'] = f"+{secondary_pts} (secondary pivot confirms)"
    else:
        secondary_pts = 0
        breakdown['secondary'] = f"+{secondary_pts} (no secondary confirmation)"
    score += secondary_pts
    
    # =========================================================================
    # FINAL SCORE
    # =========================================================================
    final_score = max(0, min(100, score))
    
    return {
        'score': final_score,
        'breakdown': breakdown,
        'recommendation': get_score_recommendation(final_score)
    }

def get_score_recommendation(score: int) -> str:
    """Convert score to actionable recommendation."""
    if score >= 80:
        return "STRONG SETUP - Full position, high confidence"
    elif score >= 70:
        return "GOOD SETUP - Full position"
    elif score >= 60:
        return "ACCEPTABLE - Reduced position"
    elif score >= 50:
        return "MARGINAL - Small position or wait"
    else:
        return "NO TRADE - Insufficient edge"

def generate_action_card(cones, regime, current_price, is_10am, overnight_validation=None) -> ActionCard:
    """
    Generate trading action based on David's structural methodology:
    
    RULES:
    1. Descending rails = BUY points (CALLS) - price finds support
    2. Ascending rails = SELL points (PUTS) - price finds resistance
    3. EXCEPTION: If price is FAR BELOW all descending rails → could be PUTS (breakdown)
    4. EXCEPTION: If price is FAR ABOVE all ascending rails → could be CALLS (breakout)
    5. Contract 15-20 pts OTM moves ~0.33x the underlying move
    """
    warnings = []
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    
    # Get the new structured confluence score
    score_result = calculate_confluence_score(
        nearest_distance, regime, cones, current_price, is_10am,
        nearest_rail_type=nearest_rail_type, 
        overnight_validation=overnight_validation
    )
    confluence_score = score_result['score']
    score_breakdown = score_result['breakdown']
    score_recommendation = score_result['recommendation']
    
    # ==========================================================================
    # DETERMINE DIRECTION based on David's rules
    # ==========================================================================
    
    # Get ALL rail levels to check for extreme positions
    all_descending = sorted([c.descending_rail for c in cones])
    all_ascending = sorted([c.ascending_rail for c in cones], reverse=True)
    
    lowest_descending = min(all_descending) if all_descending else current_price
    highest_ascending = max(all_ascending) if all_ascending else current_price
    
    # Check for extreme positions (FAR outside all rails)
    far_below_support = current_price < lowest_descending - 15  # More than 15 pts below ALL support
    far_above_resistance = current_price > highest_ascending + 15  # More than 15 pts above ALL resistance
    
    # Cone width for position calculation
    cone_width = nearest_cone.ascending_rail - nearest_cone.descending_rail
    
    # Distance thresholds
    at_rail_threshold = 10  # Within 10 pts = "at the rail"
    
    # Determine position and direction
    if far_below_support:
        # Price broke down below all support - could be PUTS (continuation) or wait
        position = 'breakdown'
        direction = 'PUTS'
        entry_level = current_price
        target_100 = lowest_descending - cone_width  # Project further down
        warnings.append("⚠️ Price below ALL support - breakdown mode")
    elif far_above_resistance:
        # Price broke above all resistance - could be CALLS (continuation) or wait
        position = 'breakout'
        direction = 'CALLS'
        entry_level = current_price
        target_100 = highest_ascending + cone_width  # Project further up
        warnings.append("⚠️ Price above ALL resistance - breakout mode")
    elif nearest_rail_type == 'descending' and nearest_distance <= at_rail_threshold:
        # At a descending rail = support = BUY CALLS
        position = 'at_support'
        direction = 'CALLS'
        entry_level = nearest_cone.descending_rail
        target_100 = nearest_cone.ascending_rail
    elif nearest_rail_type == 'ascending' and nearest_distance <= at_rail_threshold:
        # At an ascending rail = resistance = BUY PUTS
        position = 'at_resistance'
        direction = 'PUTS'
        entry_level = nearest_cone.ascending_rail
        target_100 = nearest_cone.descending_rail
    else:
        # In the middle - determine which rail to target
        dist_to_desc = abs(current_price - nearest_cone.descending_rail)
        dist_to_asc = abs(current_price - nearest_cone.ascending_rail)
        
        if dist_to_desc < dist_to_asc:
            # Closer to support - wait for it or anticipate CALLS
            position = 'approaching_support'
            direction = 'WAIT'
            entry_level = nearest_cone.descending_rail
            target_100 = nearest_cone.ascending_rail
            warnings.append(f"Wait for support at {nearest_cone.descending_rail:.2f} for CALLS")
        else:
            # Closer to resistance - wait for it or anticipate PUTS  
            position = 'approaching_resistance'
            direction = 'WAIT'
            entry_level = nearest_cone.ascending_rail
            target_100 = nearest_cone.descending_rail
            warnings.append(f"Wait for resistance at {nearest_cone.ascending_rail:.2f} for PUTS")
    
    # ==========================================================================
    # CALCULATE CONTRACT EXPECTATION (Always calculate, even for WAIT)
    # ==========================================================================
    
    cone_height = abs(target_100 - entry_level)
    
    if direction == 'CALLS' or (direction == 'WAIT' and position == 'approaching_support'):
        calc_direction = 'CALLS'
        target_50 = entry_level + (cone_height * 0.50)
        target_75 = entry_level + (cone_height * 0.75)
        stop_level = entry_level - 3  # 3 pt stop
        
        # OTM CALLS = strike ABOVE entry (15-20 pts OTM for ~0.33 delta)
        recommended_strike = int(entry_level + 17.5)
        recommended_strike = ((recommended_strike + 4) // 5) * 5  # Round UP to nearest 5
    else:
        calc_direction = 'PUTS'
        target_50 = entry_level - (cone_height * 0.50)
        target_75 = entry_level - (cone_height * 0.75)
        stop_level = entry_level + 3  # 3 pt stop
        
        # OTM PUTS = strike BELOW entry (15-20 pts OTM for ~0.33 delta)
        recommended_strike = int(entry_level - 17.5)
        recommended_strike = (recommended_strike // 5) * 5  # Round DOWN to nearest 5
    
    # Calculate expected contract moves
    move_50 = cone_height * 0.50
    move_75 = cone_height * 0.75
    move_100 = cone_height
    
    contract_move_50 = move_50 * CONTRACT_FACTOR
    contract_move_75 = move_75 * CONTRACT_FACTOR
    contract_move_100 = move_100 * CONTRACT_FACTOR
    
    # Dollar values (assuming $100 per point for SPX options)
    profit_50 = contract_move_50 * 100
    profit_75 = contract_move_75 * 100
    profit_100 = contract_move_100 * 100
    
    # Risk calculation (3 pt stop × 0.33 factor × $100)
    risk_dollars = 3 * CONTRACT_FACTOR * 100  # ~$99 risk
    rr_50 = profit_50 / risk_dollars if risk_dollars > 0 else 0
    
    contract_exp = ContractExpectation(
        direction=calc_direction,
        entry_price=entry_level,
        entry_rail=f"{nearest_cone.name} {'▼' if nearest_rail_type == 'descending' else '▲'}",
        target_50_underlying=target_50,
        target_75_underlying=target_75,
        target_100_underlying=target_100,
        stop_underlying=stop_level,
        expected_underlying_move_50=move_50,
        expected_underlying_move_100=move_100,
        contract_profit_50=profit_50,
        contract_profit_75=profit_75,
        contract_profit_100=profit_100,
        risk_reward_50=rr_50
    )
    
    # Store strike recommendation in warnings for display
    if direction in ['CALLS', 'PUTS']:
        warnings.insert(0, f"📋 Recommended: {calc_direction} @ {recommended_strike} strike")
        warnings.insert(1, f"💰 Expected move: ${contract_move_50:.0f}-${contract_move_100:.0f} per contract")
    
    # ==========================================================================
    # POSITION SIZING based on confluence score
    # ==========================================================================
    
    if direction == 'WAIT':
        color = 'yellow'
        position_size = 'WAIT'
    elif confluence_score >= 70:
        color, position_size = 'green', 'FULL'
    elif confluence_score >= 60:
        color, position_size = 'yellow', 'FULL'
    elif confluence_score >= 50:
        color, position_size = 'yellow', 'REDUCED'
    else:
        color, position_size = 'red', 'SKIP'
        warnings.append("Low confluence - consider skipping")
    
    # ==========================================================================
    # STRUCTURE VALIDATION NOTES
    # ==========================================================================
    
    if overnight_validation:
        validated = overnight_validation.get('validated', [])
        broken = overnight_validation.get('broken', [])
        
        if broken:
            for b in broken:
                if (direction == 'CALLS' and '▼' in b) or (direction == 'PUTS' and '▲' in b):
                    warnings.insert(0, f"⛔ WARNING: {b} was BROKEN overnight")
                    color = 'red'
                    position_size = 'SKIP'
        
        if validated:
            for v in validated:
                if (direction == 'CALLS' and '▼' in v) or (direction == 'PUTS' and '▲' in v):
                    warnings.insert(0, f"✅ {v} VALIDATED overnight")
    
    # Add score info
    warnings.append(f"Score: {confluence_score} - {score_recommendation}")
    
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
# PREMIUM UI
# ============================================================================

def inject_premium_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    :root {
        --bg-primary: #f8fafc;
        --bg-secondary: #f1f5f9;
        --bg-tertiary: #e2e8f0;
        --bg-card: #ffffff;
        --text-primary: #0f172a;
        --text-secondary: #475569;
        --text-muted: #64748b;
        --accent-gold: #d97706;
        --accent-green: #059669;
        --accent-red: #dc2626;
        --accent-blue: #2563eb;
        --border-color: #cbd5e1;
    }
    
    .stApp {
        background: linear-gradient(180deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
    }
    
    /* Override Streamlit defaults for light theme */
    .stApp > header { background: transparent; }
    .stMarkdown, .stText, p, span, label { color: var(--text-primary) !important; }
    h1, h2, h3, h4, h5, h6 { color: var(--text-primary) !important; }
    .stMetric label { color: var(--text-secondary) !important; }
    .stMetric [data-testid="stMetricValue"] { color: var(--text-primary) !important; font-family: 'JetBrains Mono', monospace !important; }
    
    /* INSTITUTIONAL HEADER - dark header on light background */
    .terminal-header {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border: 1px solid #475569;
        border-radius: 8px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .terminal-logo {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .terminal-logo-icon {
        width: 48px;
        height: 48px;
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
        font-weight: 800;
        color: #1e293b;
    }
    .terminal-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: #f8fafc;
        letter-spacing: -0.02em;
        font-family: 'Inter', sans-serif;
    }
    .terminal-subtitle {
        font-size: 0.8rem;
        color: #fbbf24;
        text-transform: uppercase;
        letter-spacing: 0.15em;
        font-weight: 500;
    }
    .terminal-status {
        display: flex;
        gap: 2rem;
        align-items: center;
    }
    .status-item {
        text-align: right;
    }
    .status-label {
        font-size: 0.65rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    .status-value {
        font-size: 1.1rem;
        font-weight: 600;
        color: #f8fafc;
        font-family: 'JetBrains Mono', monospace;
    }
    .status-live {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
    }
    .live-dot {
        width: 8px;
        height: 8px;
        background: #10b981;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    /* DATA GRID */
    .data-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    /* METRIC CARDS */
    .metric-card {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        padding: 1.25rem;
        transition: all 0.2s ease;
    }
    .metric-card:hover {
        border-color: var(--accent-gold);
        box-shadow: 0 0 20px rgba(245, 158, 11, 0.1);
    }
    .metric-label {
        font-size: 0.7rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.5rem;
    }
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        color: var(--text-primary);
    }
    .metric-value.positive { color: var(--accent-green); }
    .metric-value.negative { color: var(--accent-red); }
    .metric-value.gold { color: var(--accent-gold); }
    .metric-delta {
        font-size: 0.8rem;
        color: var(--text-secondary);
        margin-top: 0.25rem;
    }
    
    /* TRADE PANEL */
    .trade-panel {
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        overflow: hidden;
        margin-bottom: 1rem;
    }
    .trade-panel-header {
        background: linear-gradient(90deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
        padding: 1rem 1.25rem;
        border-bottom: 1px solid var(--border-color);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .trade-panel-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: var(--text-primary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .trade-panel-badge {
        padding: 0.25rem 0.75rem;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-calls {
        background: rgba(16, 185, 129, 0.2);
        color: var(--accent-green);
        border: 1px solid var(--accent-green);
    }
    .badge-puts {
        background: rgba(239, 68, 68, 0.2);
        color: var(--accent-red);
        border: 1px solid var(--accent-red);
    }
    .badge-go {
        background: rgba(16, 185, 129, 0.2);
        color: var(--accent-green);
        border: 1px solid var(--accent-green);
    }
    .badge-nogo {
        background: rgba(239, 68, 68, 0.2);
        color: var(--accent-red);
        border: 1px solid var(--accent-red);
    }
    .badge-wait {
        background: rgba(245, 158, 11, 0.2);
        color: var(--accent-gold);
        border: 1px solid var(--accent-gold);
    }
    .trade-panel-body {
        padding: 1.25rem;
    }
    
    /* ENTRY ROW */
    .entry-row {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr 1fr;
        gap: 1rem;
        padding: 1rem 0;
        border-bottom: 1px solid var(--border-color);
    }
    .entry-row:last-child { border-bottom: none; }
    .entry-item {
        text-align: center;
    }
    .entry-label {
        font-size: 0.65rem;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 0.25rem;
    }
    .entry-value {
        font-size: 1.1rem;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
        color: var(--text-primary);
    }
    .entry-value.green { color: var(--accent-green); }
    .entry-value.red { color: var(--accent-red); }
    .entry-value.gold { color: var(--accent-gold); }
    
    /* CONTRACT DISPLAY */
    .contract-display {
        background: linear-gradient(135deg, var(--bg-tertiary) 0%, var(--bg-secondary) 100%);
        border: 2px solid var(--accent-gold);
        border-radius: 8px;
        padding: 1.5rem;
        text-align: center;
        margin: 1rem 0;
    }
    .contract-strike {
        font-size: 2rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        color: var(--accent-gold);
        letter-spacing: -0.02em;
    }
    .contract-type {
        font-size: 0.8rem;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 0.25rem;
    }
    
    /* TABLE STYLES */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
    }
    .data-table th {
        background: var(--bg-tertiary);
        color: var(--text-muted);
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 0.75rem 1rem;
        text-align: left;
        border-bottom: 1px solid var(--border-color);
    }
    .data-table td {
        padding: 0.75rem 1rem;
        border-bottom: 1px solid var(--border-color);
        color: var(--text-primary);
    }
    .data-table tr:hover { background: rgba(255,255,255,0.02); }
    
    /* SECTION HEADERS */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--border-color);
    }
    .section-icon {
        width: 32px;
        height: 32px;
        background: var(--bg-tertiary);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
    }
    .section-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* QUICK STATS BAR */
    .stats-bar {
        display: flex;
        gap: 2rem;
        padding: 1rem 1.5rem;
        background: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 8px;
        margin-bottom: 1.5rem;
    }
    .stat-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .stat-indicator {
        width: 10px;
        height: 10px;
        border-radius: 2px;
    }
    .stat-indicator.green { background: var(--accent-green); }
    .stat-indicator.red { background: var(--accent-red); }
    .stat-indicator.gold { background: var(--accent-gold); }
    .stat-text {
        font-size: 0.8rem;
        color: var(--text-secondary);
    }
    .stat-text strong {
        color: var(--text-primary);
        font-family: 'JetBrains Mono', monospace;
    }
    
    /* DISTANCE INDICATOR */
    .distance-bar {
        height: 4px;
        background: var(--bg-tertiary);
        border-radius: 2px;
        overflow: hidden;
        margin-top: 0.5rem;
    }
    .distance-fill {
        height: 100%;
        border-radius: 2px;
        transition: width 0.3s ease;
    }
    .distance-fill.close { background: var(--accent-green); }
    .distance-fill.medium { background: var(--accent-gold); }
    .distance-fill.far { background: var(--accent-red); }
    
    /* Hide Streamlit elements */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }
    
    /* Override Streamlit dataframe */
    .stDataFrame { background: var(--bg-card) !important; border-radius: 8px !important; }
    
    /* SIDEBAR STYLING - Dark sidebar with light text */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
    }
    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3,
    section[data-testid="stSidebar"] .stMarkdown h4,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stCaption,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] div {
        color: #f8fafc !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stNumberInput label,
    section[data-testid="stSidebar"] .stTextInput label,
    section[data-testid="stSidebar"] .stDateInput label,
    section[data-testid="stSidebar"] .stCheckbox label {
        color: #cbd5e1 !important;
    }
    /* Input fields - dark text on light background */
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] .stTextInput input,
    section[data-testid="stSidebar"] .stNumberInput input {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #475569 !important;
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
    /* Expander styling in sidebar */
    section[data-testid="stSidebar"] .streamlit-expanderHeader {
        color: #f8fafc !important;
    }
    section[data-testid="stSidebar"] .streamlit-expanderContent {
        color: #e2e8f0 !important;
    }
    /* Metric values in sidebar */
    section[data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #f8fafc !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMetricDelta"] {
        color: #10b981 !important;
    }
    
    /* MAIN AREA - ensure text is visible */
    .main .block-container {
        color: var(--text-primary);
    }
    .stExpander {
        border-color: var(--border-color) !important;
    }
    .streamlit-expanderHeader {
        color: var(--text-primary) !important;
    }
    
    /* PULSE ANIMATION for confirmed entries */
    @keyframes pulse {
        0% { opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { opacity: 1; box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
        100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
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

def render_checklist(regime: RegimeAnalysis, action: ActionCard, cones: List[Cone], current_price: float, overnight_validation: dict = None, vix_signal: dict = None, active_cone_info: dict = None, ema_data: dict = None):
    """
    PRACTICAL TRADE CHECKLIST - What Actually Matters for Profitability
    
    4 ESSENTIAL CHECKS:
    1. AT RAIL - Is price at the entry point?
    2. STRUCTURE - Is cone wide enough & not broken?
    3. ACTIVE CONE - Are we trading the right cone?
    4. VIX ALIGNED - Does VIX zone support this trade direction?
    """
    
    st.markdown("#### 📋 Trade Checklist")
    
    # Find nearest rail info
    nearest_cone, nearest_rail_type, nearest_distance = find_nearest_rail(current_price, cones)
    cone_width = nearest_cone.ascending_rail - nearest_cone.descending_rail if nearest_cone else 0
    
    # Check if rail was broken overnight
    rail_broken = False
    if overnight_validation:
        broken = overnight_validation.get('broken', [])
        for b in broken:
            if nearest_rail_type == 'descending' and '▼' in b:
                rail_broken = True
            elif nearest_rail_type == 'ascending' and '▲' in b:
                rail_broken = True
    
    # Get active cone info
    active_cone = active_cone_info.get('active_cone', 'Close') if active_cone_info else 'Close'
    
    # Get VIX zone info (updated for new structure)
    vix_trade_bias = vix_signal.get('trade_bias', 'UNKNOWN') if vix_signal else 'UNKNOWN'
    vix_zone_status = vix_signal.get('zone_status', 'NO_DATA') if vix_signal else 'NO_DATA'
    vix_position = vix_signal.get('position_in_zone', 50) if vix_signal else 50
    
    # =========================================================================
    # THE 4 ESSENTIAL CHECKS
    # =========================================================================
    
    checks = []
    
    # 1. AT RAIL - The most important check
    if nearest_distance <= 3:
        at_rail_ok = True
        at_rail_detail = f"✓ Excellent - {nearest_distance:.1f} pts away"
    elif nearest_distance <= 5:
        at_rail_ok = True
        at_rail_detail = f"✓ Good - {nearest_distance:.1f} pts away"
    elif nearest_distance <= 8:
        at_rail_ok = True
        at_rail_detail = f"OK - {nearest_distance:.1f} pts away"
    else:
        at_rail_ok = False
        at_rail_detail = f"✗ Too far - {nearest_distance:.1f} pts (WAIT)"
    
    checks.append(("1. At Rail", at_rail_ok, at_rail_detail))
    
    # 2. STRUCTURE - Cone width and not broken
    if rail_broken:
        structure_ok = False
        structure_detail = "✗ Rail BROKEN overnight - SKIP"
    elif cone_width >= 35:
        structure_ok = True
        structure_detail = f"✓ Excellent ({cone_width:.0f} pts room)"
    elif cone_width >= 25:
        structure_ok = True
        structure_detail = f"✓ Good ({cone_width:.0f} pts room)"
    elif cone_width >= 18:
        structure_ok = True
        structure_detail = f"OK - tight ({cone_width:.0f} pts)"
    else:
        structure_ok = False
        structure_detail = f"✗ Too narrow ({cone_width:.0f} pts)"
    
    checks.append(("2. Structure OK", structure_ok, structure_detail))
    
    # 3. ACTIVE CONE - Are we at the right cone?
    if nearest_cone:
        if active_cone in nearest_cone.name or active_cone == 'Close':
            active_ok = True
            active_detail = f"✓ {nearest_cone.name} ({active_cone} active)"
        else:
            active_ok = False
            active_detail = f"✗ At {nearest_cone.name}, but {active_cone} active"
    else:
        active_ok = False
        active_detail = "✗ No cone found"
    
    checks.append(("3. Active Cone", active_ok, active_detail))
    
    # 4. SPX-VIX CONFLUENCE - Both must align!
    # Descending rail (▼) = CALLS → VIX must be at zone TOP (or broke down)
    # Ascending rail (▲) = PUTS → VIX must be at zone BOTTOM (or broke up)
    if vix_signal and vix_signal.get('current', 0) > 0:
        if nearest_rail_type == 'descending':  # CALLS trade - need VIX at TOP
            if vix_trade_bias == "CALLS":
                vix_ok = True
                if vix_zone_status == "BREAKOUT_DOWN":
                    vix_detail = "✓ CONFLUENCE: SPX ▼ + VIX broke down"
                else:
                    vix_detail = f"✓ CONFLUENCE: SPX ▼ + VIX at TOP ({vix_position:.0f}%)"
            elif vix_trade_bias == "WAIT":
                vix_ok = False
                vix_detail = f"⚠ VIX mid-zone ({vix_position:.0f}%) - no confluence"
            else:
                vix_ok = False
                vix_detail = "✗ NO CONFLUENCE: VIX favors PUTS"
        else:  # PUTS trade (ascending rail) - need VIX at BOTTOM
            if vix_trade_bias == "PUTS":
                vix_ok = True
                if vix_zone_status == "BREAKOUT_UP":
                    vix_detail = "✓ CONFLUENCE: SPX ▲ + VIX broke up"
                else:
                    vix_detail = f"✓ CONFLUENCE: SPX ▲ + VIX at BOTTOM ({vix_position:.0f}%)"
            elif vix_trade_bias == "WAIT":
                vix_ok = False
                vix_detail = f"⚠ VIX mid-zone ({vix_position:.0f}%) - no confluence"
            else:
                vix_ok = False
                vix_detail = "✗ NO CONFLUENCE: VIX favors CALLS"
    else:
        vix_ok = True  # Don't penalize if VIX not entered
        vix_detail = "Enter VIX in sidebar"
    
    checks.append(("4. Confluence", vix_ok, vix_detail))
    
    # =========================================================================
    # RENDER CHECKLIST
    # =========================================================================
    
    passed_count = sum(1 for _, passed, _ in checks if passed)
    total_checks = len(checks)
    
    # Critical checks
    at_rail_passed = checks[0][1]
    structure_passed = checks[1][1]
    
    # Overall assessment
    if not structure_passed:
        overall = "🔴 NO TRADE - Structure broken/narrow"
        overall_color = "#ef4444"
    elif not at_rail_passed:
        overall = "🟡 WAIT - Not at rail yet"
        overall_color = "#eab308"
    elif passed_count == 4:
        overall = "🟢 GO - Perfect setup"
        overall_color = "#22c55e"
    elif passed_count >= 3:
        overall = "🟢 GO - Good setup"
        overall_color = "#22c55e"
    elif passed_count >= 2:
        overall = "🟡 CAUTION - Reduce size"
        overall_color = "#eab308"
    else:
        overall = "🔴 SKIP"
        overall_color = "#ef4444"
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {overall_color}22, {overall_color}11); 
                border-left: 4px solid {overall_color}; padding: 0.75rem; border-radius: 8px; margin-bottom: 1rem;">
        <span style="font-weight: 700; font-size: 1.1rem;">{overall}</span>
        <span style="color: #64748b; margin-left: 0.5rem;">({passed_count}/{total_checks})</span>
    </div>
    """, unsafe_allow_html=True)
    
    for label, passed, detail in checks:
        icon = "✓" if passed else "✗"
        color = "#22c55e" if passed else "#ef4444"
        bg = "#22c55e11" if passed else "#ef444411"
        st.markdown(f"""
        <div style="display: flex; align-items: center; padding: 0.5rem; margin: 0.25rem 0; 
                    background: {bg}; border-radius: 6px;">
            <span style="color: {color}; font-size: 1.1rem; font-weight: bold; width: 1.5rem;">{icon}</span>
            <span style="flex: 1; font-weight: 500;">{label}</span>
            <span style="color: #64748b; font-size: 0.85rem;">{detail}</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Trade direction and target
    st.markdown("---")
    if nearest_rail_type == 'descending':
        direction = "CALLS"
        direction_color = "#22c55e"
        target = "ascending rail (▲)"
    else:
        direction = "PUTS"
        direction_color = "#ef4444"
        target = "descending rail (▼)"
    
    st.markdown(f"""
    <div style="text-align: center; padding: 0.75rem; background: {direction_color}22; border-radius: 8px; border: 2px solid {direction_color};">
        <div style="font-size: 0.75rem; color: #64748b;">Trade Direction</div>
        <div style="font-size: 1.3rem; font-weight: 700; color: {direction_color};">{direction}</div>
        <div style="font-size: 0.75rem; color: #64748b; margin-top: 4px;">Entry: {nearest_cone.name if nearest_cone else 'N/A'} {nearest_rail_type} (▼ or ▲)</div>
        <div style="font-size: 0.75rem; color: #64748b;">Target: {target}</div>
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
    
    # Inject alert JavaScript
    st.markdown(render_alert_javascript(), unsafe_allow_html=True)
    
    # ===== INTRADAY SESSION TRACKING =====
    # Track session high/low to detect triggered entries
    ct_now = get_ct_now()
    today_str = ct_now.strftime('%Y-%m-%d')
    
    # Initialize session state if needed
    if 'session_date' not in st.session_state:
        st.session_state.session_date = today_str
        st.session_state.session_high = None
        st.session_state.session_low = None
        st.session_state.manual_override = False
    
    # Initialize VIX manual input session state
    if 'vix_manual_mode' not in st.session_state:
        st.session_state.vix_manual_mode = True  # Default to manual since Yahoo is unreliable
        st.session_state.vix_anchor_low = 0.0
        st.session_state.vix_anchor_high = 0.0
        st.session_state.vix_2_3am_status = "Anchors Held"
        st.session_state.vix_930_signal = "⏳ Waiting for signal"
        st.session_state.vix_current = 0.0
    
    # Reset if new trading day
    if st.session_state.session_date != today_str:
        st.session_state.session_date = today_str
        st.session_state.session_high = None
        st.session_state.session_low = None
        st.session_state.manual_override = False
        # Reset VIX inputs for new day
        st.session_state.vix_anchor_low = 0.0
        st.session_state.vix_anchor_high = 0.0
        st.session_state.vix_2_3am_status = "Anchors Held"
        st.session_state.vix_930_signal = "⏳ Waiting for signal"
        st.session_state.vix_current = 0.0
    
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
        
        # IMPORTANT: Recalculate overnight SPX values using MANUAL offset
        # The auto-calculated offset from Yahoo is often wrong
        manual_offset = st.session_state.get('manual_es_offset', 8.0)
        if es_data and es_data.get('overnight_high') is not None:
            es_data['overnight_high_spx'] = es_data['overnight_high'] - manual_offset
            es_data['overnight_low_spx'] = es_data['overnight_low'] - manual_offset
            if es_data.get('pre_rth_high') is not None:
                es_data['pre_rth_high_spx'] = es_data['pre_rth_high'] - manual_offset
                es_data['pre_rth_low_spx'] = es_data['pre_rth_low'] - manual_offset
            es_data['offset'] = manual_offset  # Update offset to manual value
        
        # VIX Signal - Manual input since Yahoo is unreliable
        vix_signal = None  # Will be built from manual inputs
        
        # Fetch TODAY'S ACTUAL session high/low from Yahoo (not just current price)
        market_open = time(8, 30)
        market_close = time(15, 0)
        is_market_hours = market_open <= ct_now.time() <= market_close
        is_today = session_date.date() == ct_now.date()
        
        # Only auto-update if no manual override
        if is_today and not st.session_state.get('manual_override', False):
            todays_range = fetch_todays_session_range()
            if todays_range['high'] is not None:
                st.session_state.session_high = todays_range['high']
            if todays_range['low'] is not None:
                st.session_state.session_low = todays_range['low']
        
        # Show session tracking info with MANUAL OVERRIDE
        # Only relevant during RTH (Regular Trading Hours) for rail reversal logic
        st.markdown("---")
        st.markdown("### 📊 RTH Session Tracker")
        
        if is_today and is_market_hours:
            # Active session - show real values
            sess_col1, sess_col2 = st.columns(2)
            with sess_col1:
                display_high = st.session_state.session_high
                st.metric("Session High", f"{display_high:,.2f}" if display_high else "—")
            with sess_col2:
                display_low = st.session_state.session_low
                st.metric("Session Low", f"{display_low:,.2f}" if display_low else "—")
            
            if st.session_state.get('manual_override'):
                st.caption("⚠️ Manual override active")
            else:
                st.caption("📡 Auto-updating from Yahoo Finance")
            
            # Manual override inputs
            with st.expander("✏️ Manual Override"):
                st.caption("Use if Yahoo data differs from TradingView")
                manual_high = st.number_input(
                    "Session High", 
                    value=float(st.session_state.session_high) if st.session_state.session_high else float(current_price),
                    step=0.5,
                    format="%.2f",
                    key="manual_high_input"
                )
                manual_low = st.number_input(
                    "Session Low", 
                    value=float(st.session_state.session_low) if st.session_state.session_low else float(current_price),
                    step=0.5,
                    format="%.2f",
                    key="manual_low_input"
                )
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✅ Set Manual"):
                        st.session_state.session_high = manual_high
                        st.session_state.session_low = manual_low
                        st.session_state.manual_override = True
                        st.rerun()
                with col_btn2:
                    if st.button("🔄 Reset Auto"):
                        st.session_state.manual_override = False
                        st.rerun()
        else:
            # Market closed - show message
            st.caption("🌙 Market closed - RTH session tracking inactive")
            st.caption("Session High/Low will update when market opens (8:30am CT)")
        
        # Show ES → SPX implied price (useful for overnight planning)
        st.markdown("---")
        st.markdown("### 🌙 ES → SPX Conversion")
        
        # Initialize manual offset in session state
        if 'manual_es_offset' not in st.session_state:
            st.session_state.manual_es_offset = 8.0  # Default offset
        
        # Manual offset input - expanded range for unusual market conditions
        st.session_state.manual_es_offset = st.number_input(
            "ES - SPX Offset",
            min_value=-100.0,
            max_value=100.0,
            value=st.session_state.manual_es_offset,
            step=0.25,
            format="%.2f",
            help="Enter (ES price - SPX price). Positive if ES > SPX, Negative if ES < SPX. Example: If ES=6000 and SPX=6058, enter -58"
        )
        
        # Clarify the math
        es_offset = st.session_state.manual_es_offset
        if es_offset >= 0:
            st.caption(f"📐 SPX = ES - {es_offset:.2f} (ES is {es_offset:.2f} pts ABOVE SPX)")
        else:
            st.caption(f"📐 SPX = ES + {abs(es_offset):.2f} (ES is {abs(es_offset):.2f} pts BELOW SPX)")
        
        # Get current ES if available
        try:
            es_ticker = yf.Ticker("ES=F")
            es_current_data = es_ticker.history(period='1d', interval='1m')
            if not es_current_data.empty:
                es_current = es_current_data['Close'].iloc[-1]
                spx_implied = es_current - es_offset  # This works for both positive and negative offsets
                
                es_col1, es_col2 = st.columns(2)
                with es_col1:
                    st.metric("ES Futures", f"{es_current:,.2f}")
                with es_col2:
                    st.metric("SPX Implied", f"{spx_implied:,.2f}")
                
                if not is_market_hours:
                    st.info("💡 Use SPX Implied to check overnight levels")
        except Exception:
            st.warning("Unable to fetch ES futures data")
        
        # ========== VIX ZONE SYSTEM ==========
        # VIX moves in discrete 0.15 zones. Overnight (5pm-2am) sets the zone.
        st.markdown("---")
        st.markdown("### 🎯 SPX-VIX Confluence")
        st.caption("BOTH must align: VIX zone + SPX rail")
        st.markdown("""
        <div style="background: #fef3c7; border-left: 3px solid #d97706; padding: 8px 12px; margin-bottom: 12px; border-radius: 0 6px 6px 0; font-size: 0.75rem; color: #78350f;">
            ⚠️ <strong style="color: #92400e;">30-MIN CLOSE matters!</strong> Wicks can pierce levels — wait for candle CLOSE to confirm.
        </div>
        """, unsafe_allow_html=True)
        
        # Zone boundaries from overnight
        st.markdown("**Overnight Zone (5pm-2am)**")
        vix_col1, vix_col2 = st.columns(2)
        with vix_col1:
            st.session_state.vix_anchor_low = st.number_input(
                "Zone Bottom", 
                min_value=0.0, 
                max_value=100.0, 
                value=st.session_state.vix_anchor_low,
                step=0.01,
                format="%.2f",
                help="Overnight LOW - VIX bounces here → SPX DOWN → PUTS entry"
            )
        with vix_col2:
            st.session_state.vix_anchor_high = st.number_input(
                "Zone Top", 
                min_value=0.0, 
                max_value=100.0, 
                value=st.session_state.vix_anchor_high,
                step=0.01,
                format="%.2f",
                help="Overnight HIGH - VIX rejects here → SPX UP → CALLS entry"
            )
        
        # Current VIX
        st.session_state.vix_current = st.number_input(
            "Current VIX", 
            min_value=0.0, 
            max_value=100.0, 
            value=st.session_state.vix_current,
            step=0.01,
            format="%.2f",
            help="Live VIX from TradingView"
        )
        
        # Build comprehensive VIX zone analysis
        vix_signal = None
        if st.session_state.vix_anchor_low > 0 and st.session_state.vix_anchor_high > 0:
            zone_bottom = st.session_state.vix_anchor_low
            zone_top = st.session_state.vix_anchor_high
            vix_current = st.session_state.vix_current
            zone_size = zone_top - zone_bottom
            
            # Generate all zone levels (±4 zones = ±0.60)
            VIX_ZONE_INCREMENT = 0.15
            zones_above = [round(zone_top + (VIX_ZONE_INCREMENT * i), 2) for i in range(1, 5)]
            zones_below = [round(zone_bottom - (VIX_ZONE_INCREMENT * i), 2) for i in range(1, 5)]
            
            # Determine current zone status
            if vix_current > 0:
                if vix_current > zone_top:
                    # BREAKOUT UP - VIX above resistance
                    zones_broken_up = int((vix_current - zone_top) / VIX_ZONE_INCREMENT) + 1
                    next_target_up = zone_top + (VIX_ZONE_INCREMENT * zones_broken_up)
                    zone_status = "BREAKOUT_UP"
                    zone_status_text = f"VIX BROKE UP +{zones_broken_up} zone(s)"
                    trade_bias = "PUTS"
                    trade_action = "PUTS targets EXTEND"
                    spx_direction = "SPX heading DOWN"
                    # When VIX breaks up, we're looking for SPX to hit ascending rails
                    entry_rail = "ascending (▲)"
                    exit_target = f"VIX target: {next_target_up:.2f}"
                elif vix_current < zone_bottom:
                    # BREAKOUT DOWN - VIX below support
                    zones_broken_down = int((zone_bottom - vix_current) / VIX_ZONE_INCREMENT) + 1
                    next_target_down = zone_bottom - (VIX_ZONE_INCREMENT * zones_broken_down)
                    zone_status = "BREAKOUT_DOWN"
                    zone_status_text = f"VIX BROKE DOWN -{zones_broken_down} zone(s)"
                    trade_bias = "CALLS"
                    trade_action = "CALLS targets EXTEND"
                    spx_direction = "SPX heading UP"
                    entry_rail = "descending (▼)"
                    exit_target = f"VIX target: {next_target_down:.2f}"
                else:
                    # CONTAINED - VIX within overnight zone
                    zone_status = "CONTAINED"
                    zone_status_text = "VIX in overnight zone"
                    
                    # Calculate position within zone (0% = bottom, 100% = top)
                    if zone_size > 0:
                        position_in_zone = ((vix_current - zone_bottom) / zone_size) * 100
                    else:
                        position_in_zone = 50
                    
                    # Near top (>75%) = CALLS entry zone
                    # Near bottom (<25%) = PUTS entry zone
                    # Middle (25-75%) = WAIT
                    if position_in_zone >= 75:
                        trade_bias = "CALLS"
                        trade_action = "VIX at TOP → rejects DOWN → SPX UP"
                        spx_direction = "SPX heading UP"
                        entry_rail = "descending (▼)"
                        exit_target = f"Exit when VIX hits {zone_bottom:.2f}"
                    elif position_in_zone <= 25:
                        trade_bias = "PUTS"
                        trade_action = "VIX at BOTTOM → bounces UP → SPX DOWN"
                        spx_direction = "SPX heading DOWN"
                        entry_rail = "ascending (▲)"
                        exit_target = f"Exit when VIX hits {zone_top:.2f}"
                    else:
                        trade_bias = "WAIT"
                        trade_action = "VIX mid-zone → wait for edge"
                        spx_direction = "Direction unclear"
                        entry_rail = "wait"
                        exit_target = "Wait for VIX to reach zone edge"
            else:
                zone_status = "NO_DATA"
                zone_status_text = "Enter current VIX"
                trade_bias = "UNKNOWN"
                trade_action = "Enter current VIX"
                spx_direction = ""
                entry_rail = "N/A"
                exit_target = ""
                position_in_zone = 50
            
            # Build vix_signal dict
            vix_signal = {
                'zone_bottom': zone_bottom,
                'zone_top': zone_top,
                'zone_size': zone_size,
                'current': vix_current,
                'zone_status': zone_status,
                'zone_status_text': zone_status_text,
                'trade_bias': trade_bias,
                'trade_action': trade_action,
                'spx_direction': spx_direction,
                'entry_rail': entry_rail,
                'exit_target': exit_target,
                'zones_above': zones_above,
                'zones_below': zones_below,
                'position_in_zone': position_in_zone if zone_status == "CONTAINED" else None,
                'data_source': 'MANUAL'
            }
            
            # ===== SIDEBAR VIX ZONE DISPLAY =====
            st.markdown("---")
            
            # Zone validation
            num_zones = round(zone_size / VIX_ZONE_INCREMENT) if zone_size > 0 else 0
            if 0.13 <= zone_size <= 0.17:
                st.success(f"✓ Perfect zone: {zone_size:.2f}")
            elif zone_size > 0:
                st.info(f"Zone = {num_zones} level(s) ({zone_size:.2f})")
            
            # Trade bias indicator
            if trade_bias == "CALLS":
                st.markdown(f"""
                <div style="background: #d1fae5; border: 2px solid #10b981; border-radius: 8px; padding: 12px; text-align: center;">
                    <div style="font-size: 1.5rem;">🟢</div>
                    <div style="font-weight: 700; color: #059669; font-size: 1.1rem;">CALLS</div>
                    <div style="font-size: 0.75rem; color: #065f46;">{trade_action}</div>
                    <div style="font-size: 0.7rem; color: #064e3b; margin-top: 4px;">Entry: SPX {entry_rail}</div>
                </div>
                """, unsafe_allow_html=True)
            elif trade_bias == "PUTS":
                st.markdown(f"""
                <div style="background: #fee2e2; border: 2px solid #ef4444; border-radius: 8px; padding: 12px; text-align: center;">
                    <div style="font-size: 1.5rem;">🔴</div>
                    <div style="font-weight: 700; color: #dc2626; font-size: 1.1rem;">PUTS</div>
                    <div style="font-size: 0.75rem; color: #991b1b;">{trade_action}</div>
                    <div style="font-size: 0.7rem; color: #7f1d1d; margin-top: 4px;">Entry: SPX {entry_rail}</div>
                </div>
                """, unsafe_allow_html=True)
            elif trade_bias == "WAIT":
                st.markdown(f"""
                <div style="background: #fef3c7; border: 2px solid #f59e0b; border-radius: 8px; padding: 12px; text-align: center;">
                    <div style="font-size: 1.5rem;">🟡</div>
                    <div style="font-weight: 700; color: #d97706; font-size: 1.1rem;">WAIT</div>
                    <div style="font-size: 0.75rem; color: #92400e;">{trade_action}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Exit target
            if exit_target:
                st.caption(f"🎯 {exit_target}")
            
            # ===== VIX ZONE LADDER =====
            st.markdown("---")
            st.markdown("**📊 Zone Ladder**")
            
            # Build ladder HTML
            ladder_html = '<div style="font-family: monospace; font-size: 0.75rem; line-height: 1.6;">'
            
            # Zones above (reversed to show highest first)
            for i in range(3, -1, -1):
                level = zones_above[i]
                is_target = zone_status == "BREAKOUT_UP" and vix_current > 0 and level > vix_current and (i == 0 or zones_above[i-1] < vix_current if i > 0 else True)
                style = 'color: #ef4444; font-weight: 600;' if is_target else 'color: #9ca3af;'
                marker = ' ◀ TARGET' if is_target else ''
                ladder_html += f'<div style="{style}">+{i+1}: {level:.2f} <span style="color: #ef4444; font-size: 0.65rem;">(PUTS extend){marker}</span></div>'
            
            # Zone top (resistance)
            top_style = 'background: #d1fae5; padding: 4px 8px; border-radius: 4px; margin: 4px 0;'
            ladder_html += f'<div style="{top_style}"><strong style="color: #059669;">TOP: {zone_top:.2f}</strong> <span style="color: #065f46; font-size: 0.7rem;">← CALLS entry / PUTS exit</span></div>'
            
            # Current VIX position (if in zone)
            if zone_status == "CONTAINED" and vix_current > 0:
                pos_pct = vix_signal.get('position_in_zone', 50)
                ladder_html += f'<div style="background: #dbeafe; padding: 4px 8px; border-radius: 4px; margin: 4px 0;"><strong style="color: #1d4ed8;">NOW: {vix_current:.2f}</strong> <span style="color: #1e40af; font-size: 0.7rem;">({pos_pct:.0f}% in zone)</span></div>'
            
            # Zone bottom (support)
            bot_style = 'background: #fee2e2; padding: 4px 8px; border-radius: 4px; margin: 4px 0;'
            ladder_html += f'<div style="{bot_style}"><strong style="color: #dc2626;">BOT: {zone_bottom:.2f}</strong> <span style="color: #991b1b; font-size: 0.7rem;">← PUTS entry / CALLS exit</span></div>'
            
            # Zones below
            for i in range(4):
                level = zones_below[i]
                is_target = zone_status == "BREAKOUT_DOWN" and vix_current > 0 and level < vix_current and (i == 0 or zones_below[i-1] > vix_current if i > 0 else True)
                style = 'color: #10b981; font-weight: 600;' if is_target else 'color: #9ca3af;'
                marker = ' ◀ TARGET' if is_target else ''
                ladder_html += f'<div style="{style}">-{i+1}: {level:.2f} <span style="color: #10b981; font-size: 0.65rem;">(CALLS extend){marker}</span></div>'
            
            ladder_html += '</div>'
            st.markdown(ladder_html, unsafe_allow_html=True)
            
            # Breakout indicator
            if zone_status == "BREAKOUT_UP":
                st.error(f"⚠️ VIX BROKE ABOVE {zone_top:.2f}")
            elif zone_status == "BREAKOUT_DOWN":
                st.success(f"⚡ VIX BROKE BELOW {zone_bottom:.2f}")
        
        st.markdown("---")
        st.markdown("### ⚙️ Parameters")
        col_slope1, col_slope2 = st.columns(2)
        with col_slope1:
            st.metric("Ascending", f"+{SLOPE_ASCENDING}")
        with col_slope2:
            st.metric("Descending", f"-{SLOPE_DESCENDING}")
        
        # ========== ALERT SETTINGS ==========
        st.markdown("---")
        st.markdown("### 🔔 Alert Settings")
        
        # Initialize alert settings in session state
        if 'alerts_enabled' not in st.session_state:
            st.session_state.alerts_enabled = True
        if 'sound_enabled' not in st.session_state:
            st.session_state.sound_enabled = True
        
        st.session_state.alerts_enabled = st.checkbox("Enable Alerts", value=st.session_state.alerts_enabled)
        st.session_state.sound_enabled = st.checkbox("Sound Alerts", value=st.session_state.sound_enabled, disabled=not st.session_state.alerts_enabled)
        
        st.caption(f"Approach alert: {ALERT_APPROACH_DISTANCE:.0f} pts from entry")
        st.caption(f"Touch threshold: {ENTRY_TOUCH_THRESHOLD:.0f} pts")
        st.caption(f"Confirmation window: {ENTRY_TIME_LIMIT_MINUTES:.0f} min")
        
        # Reset touched entries button
        if st.button("🔄 Reset Entry Tracking"):
            # Clear all touch tracking from session state
            keys_to_clear = [k for k in st.session_state.keys() if k.startswith('touch_') or k.startswith('touched_') or k.startswith('alert_played_')]
            for key in keys_to_clear:
                del st.session_state[key]
            st.success("Entry tracking reset!")
            st.rerun()
        
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
            
            # ============================================================
            # PIVOT DETECTION METHODOLOGY
            # HIGH pivots (Primary & Secondary) = Use WICKS - rejection points
            #   → Both ascending AND descending rails from High use wick value
            # LOW pivots (Primary & Secondary) = Use CLOSE - commitment points
            #   → Both ascending AND descending rails from Low use close value
            # ============================================================
            st.info("📊 **HIGH pivots** → Wick (rejection) | **LOW pivots** → Close (commitment)")
            
            # HIGH pivot → Use candle HIGH (wick) - both rails project from this
            base_high = prior_session['high']  # Wick high
            base_high_time = prior_session['high_time']
            base_sec_high = prior_session.get('secondary_high')  # Wick-based secondary high
            base_sec_high_time = prior_session.get('secondary_high_time')
            
            # LOW pivot → Use CLOSE - both rails project from this
            base_low = prior_session.get('low_line', prior_session['low'])  # Close-based low
            base_low_time = prior_session.get('low_line_time', prior_session['low_time'])
            base_sec_low = prior_session.get('secondary_low_line')  # Close-based secondary low
            base_sec_low_time = prior_session.get('secondary_low_line_time')
            
            # Apply price offset
            auto_high = base_high - price_offset
            auto_low = base_low - price_offset
            auto_close = prior_session['close'] - price_offset
            
            use_manual = st.checkbox("✏️ Manual Price Override", value=False, help="Enable to enter your TradingView prices directly")
            
            if use_manual:
                st.info("Enter your TradingView prices below")
                high_price = st.number_input("High (Wick)", value=float(auto_high), format="%.2f", help="For ascending rails (resistance)")
                high_time_str = st.text_input("High Time (CT)", value=base_high_time.strftime('%H:%M'))
                low_price = st.number_input("Low (Close)", value=float(auto_low), format="%.2f", help="For descending rails (support)")
                low_time_str = st.text_input("Low Time (CT)", value=base_low_time.strftime('%H:%M'))
                close_price = st.number_input("Close", value=float(auto_close), format="%.2f")
            else:
                # Show corrected values (with offset applied)
                high_price = auto_high
                low_price = auto_low
                close_price = auto_close
                high_time_str = base_high_time.strftime('%H:%M')
                low_time_str = base_low_time.strftime('%H:%M')
                
                st.metric("High (Wick)", f"{high_price:.2f}", f"@ {high_time_str} CT")
                st.metric("Low (Close)", f"{low_price:.2f}", f"@ {low_time_str} CT")
                st.metric("Close", f"{close_price:.2f}")
                
                if price_offset != 0:
                    st.caption(f"📉 Offset applied: -{price_offset:.2f} pts")
            
            # Secondary Pivots Section with Manual Override
            st.markdown("---")
            st.markdown("### 📍 Secondary Pivots")
            st.caption("High² = Wick | Low² = Close")
            
            # Initialize session state for manual secondary pivots
            if 'use_manual_secondary' not in st.session_state:
                st.session_state.use_manual_secondary = False
            
            use_manual_secondary = st.checkbox("✏️ Manual Secondary Override", value=st.session_state.use_manual_secondary, help="Enable to manually enter secondary pivots")
            st.session_state.use_manual_secondary = use_manual_secondary
            
            if use_manual_secondary:
                st.info("Enter secondary pivot values from TradingView")
                
                # Secondary High² (Wick)
                use_sec_high = st.checkbox("Enable High²", value=base_sec_high is not None)
                if use_sec_high:
                    default_sec_high = float(base_sec_high - price_offset) if base_sec_high else float(high_price - 5)
                    secondary_high_price = st.number_input(
                        "High² (Wick)", 
                        value=default_sec_high, 
                        format="%.2f", 
                        help="Secondary high pivot - use wick value"
                    )
                    sec_high_time_str = st.text_input(
                        "High² Time (CT)", 
                        value=base_sec_high_time.strftime('%H:%M') if base_sec_high_time else "14:00"
                    )
                    try:
                        h, m = map(int, sec_high_time_str.split(':'))
                        prior_date = prior_session['date'].date() if prior_session else session_date.date() - timedelta(days=1)
                        secondary_high_time = CT_TZ.localize(datetime.combine(prior_date, time(h, m)))
                    except:
                        secondary_high_time = CT_TZ.localize(datetime.combine(prior_date, time(14, 0)))
                else:
                    secondary_high_price = None
                    secondary_high_time = None
                
                # Secondary Low² (Close)
                use_sec_low = st.checkbox("Enable Low²", value=base_sec_low is not None)
                if use_sec_low:
                    default_sec_low = float(base_sec_low - price_offset) if base_sec_low else float(low_price + 5)
                    secondary_low_price = st.number_input(
                        "Low² (Close)", 
                        value=default_sec_low, 
                        format="%.2f", 
                        help="Secondary low pivot - use close value"
                    )
                    sec_low_time_str = st.text_input(
                        "Low² Time (CT)", 
                        value=base_sec_low_time.strftime('%H:%M') if base_sec_low_time else "10:00"
                    )
                    try:
                        h, m = map(int, sec_low_time_str.split(':'))
                        prior_date = prior_session['date'].date() if prior_session else session_date.date() - timedelta(days=1)
                        secondary_low_time = CT_TZ.localize(datetime.combine(prior_date, time(h, m)))
                    except:
                        secondary_low_time = CT_TZ.localize(datetime.combine(prior_date, time(10, 0)))
                else:
                    secondary_low_price = None
                    secondary_low_time = None
                    
            else:
                # Auto-detected secondary pivots (display only)
                if base_sec_high is not None:
                    st.success("🔄 Secondary High Detected!")
                    secondary_high_price = base_sec_high - price_offset
                    secondary_high_time = base_sec_high_time
                    st.metric("2nd High² (Wick)", f"{secondary_high_price:.2f}", f"@ {secondary_high_time.strftime('%H:%M')} CT")
                else:
                    st.caption("High²: Not detected")
                
                if base_sec_low is not None:
                    st.success("🔄 Secondary Low Detected!")
                    secondary_low_price = base_sec_low - price_offset
                    secondary_low_time = base_sec_low_time
                    st.metric("2nd Low² (Close)", f"{secondary_low_price:.2f}", f"@ {secondary_low_time.strftime('%H:%M')} CT")
                else:
                    st.caption("Low²: Not detected")
            
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
                    except Exception:
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
                    except Exception:
                        premarket_low_time = None
            
            # Debug: Show timing info
            with st.expander("🔍 Pivot Timing Details"):
                st.markdown("**Methodology:**")
                st.markdown("- **HIGH pivots** → Use Wick (rejection point)")
                st.markdown("- **LOW pivots** → Use Close (commitment point)")
                st.markdown("- Each pivot projects BOTH ascending & descending rails")
                st.markdown("---")
                st.write(f"**Primary High (Wick):** {high_price:.2f} @ {high_time_str} CT")
                st.write(f"**Primary Low (Close):** {low_price:.2f} @ {low_time_str} CT")
                if secondary_high_price is not None:
                    st.write(f"**Secondary High² (Wick):** {secondary_high_price:.2f} @ {secondary_high_time.strftime('%H:%M')} CT")
                else:
                    st.write("**Secondary High²:** Not detected")
                if secondary_low_price is not None:
                    st.write(f"**Secondary Low² (Close):** {secondary_low_price:.2f} @ {secondary_low_time.strftime('%H:%M')} CT")
                else:
                    st.write("**Secondary Low²:** Not detected")
                if use_premarket_high and premarket_high_price:
                    st.write(f"**Pre-Market High:** {premarket_high_price:.2f} @ {premarket_high_time.strftime('%H:%M')} CT")
                if use_premarket_low and premarket_low_price:
                    st.write(f"**Pre-Market Low:** {premarket_low_price:.2f} @ {premarket_low_time.strftime('%H:%M')} CT")
                
                # Show all raw values for reference
                st.markdown("---")
                st.markdown("**📊 Raw Detected Values (for comparison):**")
                candle_high = prior_session['high']
                candle_high_time = prior_session['high_time']
                line_low = prior_session.get('low_line', prior_session['low'])
                line_low_time = prior_session.get('low_line_time', prior_session['low_time'])
                candle_low = prior_session['low']
                candle_low_time = prior_session['low_time']
                st.write(f"High (Wick): {candle_high - price_offset:.2f} @ {candle_high_time.strftime('%H:%M')} ✓ Used")
                st.write(f"Low (Wick): {candle_low - price_offset:.2f} @ {candle_low_time.strftime('%H:%M')}")
                st.write(f"Low (Close): {line_low - price_offset:.2f} @ {line_low_time.strftime('%H:%M')} ✓ Used")
            
            try:
                h, m = map(int, high_time_str.split(':'))
                high_time = CT_TZ.localize(datetime.combine(prior_session['date'], time(h, m)))
            except Exception:
                high_time = base_high_time
            
            try:
                h, m = map(int, low_time_str.split(':'))
                low_time = CT_TZ.localize(datetime.combine(prior_session['date'], time(h, m)))
            except Exception:
                low_time = base_low_time
            
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
            except Exception:
                high_time = CT_TZ.localize(datetime.combine(prior_date, time(10, 30)))
            try:
                h, m = map(int, low_time_str.split(':'))
                low_time = CT_TZ.localize(datetime.combine(prior_date, time(h, m)))
            except Exception:
                low_time = CT_TZ.localize(datetime.combine(prior_date, time(13, 45)))
            close_time = CT_TZ.localize(datetime.combine(prior_date, time(15, 0)))
        
        if es_data:
            st.markdown("---")
            st.markdown("### 🔄 ES-SPX Offset")
            manual_offset_val = st.session_state.get('manual_es_offset', 8.0)
            st.metric("Offset (Manual)", f"{manual_offset_val:.2f} pts")
            
            # DEBUG: Show overnight values for cone detection
            with st.expander("🔍 Overnight ES Data"):
                if es_data.get('overnight_high_spx'):
                    # Recalculate overnight SPX using manual offset
                    es_overnight_high = es_data.get('overnight_high')
                    es_overnight_low = es_data.get('overnight_low')
                    if es_overnight_high and es_overnight_low:
                        overnight_high_spx = es_overnight_high - manual_offset_val
                        overnight_low_spx = es_overnight_low - manual_offset_val
                        st.caption(f"**Overnight High (SPX):** {overnight_high_spx:.2f}")
                        st.caption(f"**Overnight Low (SPX):** {overnight_low_spx:.2f}")
                        st.caption(f"**Overnight Range:** {es_overnight_high - es_overnight_low:.2f} pts")
                    else:
                        st.caption(f"**Overnight High (SPX):** {es_data['overnight_high_spx']:.2f}")
                        st.caption(f"**Overnight Low (SPX):** {es_data['overnight_low_spx']:.2f}")
                        st.caption(f"**Overnight Range:** {es_data.get('overnight_range', 0):.2f} pts")
                    st.caption(f"**ES Current:** {es_data.get('current', 'N/A')}")
                else:
                    st.caption("No overnight data available")
    
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
    
    # Check if viewing a future date (no session data available yet)
    # EXCEPTION: On Monday evening after market close (5pm+), Tuesday is the "next trading day"
    # and we CAN project cones using Monday's completed session data
    ct_now = get_ct_now()
    is_after_market_close = ct_now.time() >= time(17, 0)  # After 5pm CT
    is_tomorrow = session_date.date() == (ct_now + timedelta(days=1)).date()
    
    # Handle weekend: Sunday evening looking at Monday
    if ct_now.weekday() == 6:  # Sunday
        next_trading_day = ct_now + timedelta(days=1)  # Monday
        is_next_trading_day = session_date.date() == next_trading_day.date()
    # Handle Friday evening looking at Monday
    elif ct_now.weekday() == 4 and is_after_market_close:  # Friday evening
        next_trading_day = ct_now + timedelta(days=3)  # Monday
        is_next_trading_day = session_date.date() == next_trading_day.date()
    else:
        is_next_trading_day = is_tomorrow
    
    # Future date logic:
    # - If after 5pm and looking at NEXT trading day -> NOT a future date (we have today's data)
    # - Otherwise, if date > today -> IS a future date
    if is_after_market_close and is_next_trading_day:
        is_future_date = False  # We can use today's completed session for tomorrow's projections
    else:
        is_future_date = session_date.date() > ct_now.date()
    
    # Detect if 8:30 already touched cone edges (for 70-75% follow-through rule)
    # If 8:30 bounced from support, 10am support touch has reduced expectation
    # Only applicable for today or past dates, not future dates
    session_830_touched = {'high_touched': False, 'low_touched': False}
    if not is_future_date and cones_830:
        # Get 8:30 cone edges (using Close cone as the primary reference)
        close_cone_830 = next((c for c in cones_830 if c.name == 'Close'), None)
        if close_cone_830 and st.session_state.get('session_low') and st.session_state.get('session_high'):
            sess_low = st.session_state.session_low
            sess_high = st.session_state.session_high
            # Check if session came within 5 pts of descending rail (support)
            if sess_low <= close_cone_830.descending_rail + 5:
                session_830_touched['low_touched'] = True
            # Check if session came within 5 pts of ascending rail (resistance)
            if sess_high >= close_cone_830.ascending_rail - 5:
                session_830_touched['high_touched'] = True
    
    # Determine ACTIVE CONE based on overnight + RTH behavior
    # For future dates, there's no overnight data, so default to Close cone
    session_high_val = st.session_state.get('session_high') if not is_future_date else None
    session_low_val = st.session_state.get('session_low') if not is_future_date else None
    
    if is_future_date:
        # For future dates, default to Close cone since we have no overnight data
        active_cone_info = {'active_cone': 'Close', 'reason': 'Future date - no overnight data available', 'rail_reversal': None}
    else:
        active_cone_info = determine_active_cone(cones_1000, es_data, session_high_val, session_low_val)
    
    # DEBUG: Show cone detection comparison (only for today/past, not future dates)
    close_cone_1000 = next((c for c in cones_1000 if c.name == 'Close'), None)
    if close_cone_1000 and es_data and es_data.get('overnight_high_spx') and not is_future_date:
        with st.sidebar:
            with st.expander("🎯 Cone Detection Debug", expanded=True):
                st.caption(f"**Close Cone ▲:** {close_cone_1000.ascending_rail:.2f}")
                st.caption(f"**Close Cone ▼:** {close_cone_1000.descending_rail:.2f}")
                st.caption(f"**Overnight High (SPX):** {es_data['overnight_high_spx']:.2f}")
                st.caption(f"**Overnight Low (SPX):** {es_data['overnight_low_spx']:.2f}")
                
                # Show PRE-RTH values (for entry invalidation)
                pre_rth_high = es_data.get('pre_rth_high_spx')
                pre_rth_low = es_data.get('pre_rth_low_spx')
                if pre_rth_high and pre_rth_low:
                    st.caption(f"**Pre-RTH High (for invalidation):** {pre_rth_high:.2f}")
                    st.caption(f"**Pre-RTH Low (for invalidation):** {pre_rth_low:.2f}")
                
                broke_above = es_data['overnight_high_spx'] > close_cone_1000.ascending_rail + 2
                broke_below = es_data['overnight_low_spx'] < close_cone_1000.descending_rail - 2
                
                st.caption(f"**Broke Above?** {broke_above} (>{close_cone_1000.ascending_rail + 2:.2f})")
                st.caption(f"**Broke Below?** {broke_below} (<{close_cone_1000.descending_rail - 2:.2f})")
                st.caption(f"**Active Cone:** {active_cone_info.get('active_cone')}")
                st.caption(f"**Rail Reversal:** {active_cone_info.get('rail_reversal', 'None')}")
                st.caption(f"**Reason:** {active_cone_info.get('reason')}")
                
                # Show active cone rails if not Close
                active_cone_name = active_cone_info.get('active_cone')
                if active_cone_name in ['High', 'Low']:
                    active_cone_obj = next((c for c in cones_1000 if c.name == active_cone_name), None)
                    if active_cone_obj:
                        st.markdown("---")
                        st.caption(f"**{active_cone_name} Cone ▲ (SELL):** {active_cone_obj.ascending_rail:.2f}")
                        st.caption(f"**{active_cone_name} Cone ▼ (BUY):** {active_cone_obj.descending_rail:.2f}")
                        
                        # Show reversal conditions
                        session_high_val = st.session_state.get('session_high')
                        session_low_val = st.session_state.get('session_low')
                        if session_high_val and session_low_val:
                            st.caption(f"**Session High:** {session_high_val:.2f}")
                            st.caption(f"**Session Low:** {session_low_val:.2f}")
                            if active_cone_name == 'Low':
                                touched_bottom = session_low_val <= active_cone_obj.descending_rail + 2
                                broke_top = session_high_val > active_cone_obj.ascending_rail + 2
                                st.caption(f"**Touched Low ▼?** {touched_bottom}")
                                st.caption(f"**Broke through Low ▲?** {broke_top}")
                            else:
                                touched_top = session_high_val >= active_cone_obj.ascending_rail - 2
                                broke_bottom = session_low_val < active_cone_obj.descending_rail - 2
                                st.caption(f"**Touched High ▲?** {touched_top}")
                                st.caption(f"**Broke through High ▼?** {broke_bottom}")
                        
                        # Show Low²/High² if exists
                        secondary_name = f"{active_cone_name}²"
                        secondary_cone = next((c for c in cones_1000 if c.name == secondary_name), None)
                        if secondary_cone:
                            st.markdown("---")
                            st.caption(f"**{secondary_name} Cone ▲:** {secondary_cone.ascending_rail:.2f}")
                            st.caption(f"**{secondary_name} Cone ▼:** {secondary_cone.descending_rail:.2f}")
                        else:
                            st.caption(f"**{secondary_name}:** Not detected")
    
    # VIX Debug Panel - Simplified for manual mode
    with st.sidebar:
        with st.expander("📊 VIX Signal Status", expanded=False):
            if vix_signal is None:
                st.warning("⚠️ Enter VIX data above to enable signals")
            else:
                st.success("✅ VIX Data Entered")
                
                st.caption(f"**Anchor Low:** {vix_signal.get('anchor_low', 0):.2f}")
                st.caption(f"**Anchor High:** {vix_signal.get('anchor_high', 0):.2f}")
                st.caption(f"**2-3am Status:** {vix_signal.get('vix_2_3am_status', 'N/A')}")
                st.markdown("---")
                st.caption(f"**9-9:30am Signal:** {vix_signal.get('vix_930_signal', 'N/A')}")
                st.caption(f"**Trade Direction:** {vix_signal.get('trade_direction', 'Waiting')}")
                st.caption(f"**Direction Confirmed:** {vix_signal.get('direction_confirmed', False)}")
    
    # Generate complete trade setups for all confluence zones
    trade_setups_830 = generate_trade_setups(cones_830, current_price, es_data=es_data, session_830_touched=None, active_cone_info=None)
    trade_setups_1000 = generate_trade_setups(cones_1000, current_price, es_data=es_data, session_830_touched=session_830_touched, active_cone_info=active_cone_info)
    
    # ===== INSTITUTIONAL TERMINAL LAYOUT =====
    
    # Count setups
    num_calls = len(trade_setups_1000.get('calls_setups', []))
    num_puts = len(trade_setups_1000.get('puts_setups', []))
    ct_time = get_ct_now()
    
    # Determine market status
    market_open_time = time(8, 30)
    market_close_time = time(15, 0)
    is_weekend = ct_time.weekday() >= 5
    is_market_open = not is_weekend and market_open_time <= ct_time.time() <= market_close_time
    
    # Determine display price (use ES-derived when market closed)
    # Get manual offset for ES-SPX conversion
    manual_offset = st.session_state.get('manual_es_offset', 8.0)
    
    if is_market_open:
        display_price = current_price
        price_label = "SPX Index"
        market_status = "LIVE"
    else:
        # Use ES-derived SPX with manual offset
        if es_data and es_data.get('current'):
            display_price = es_data['current'] - manual_offset
            price_label = "SPX (from ES)"
            market_status = "FUTURES"
        else:
            display_price = current_price
            price_label = "SPX (Last)"
            market_status = "CLOSED"
    
    # TERMINAL HEADER
    st.markdown(f"""
    <div class="terminal-header">
        <div class="terminal-logo">
            <div class="terminal-logo-icon">SP</div>
            <div>
                <div class="terminal-title">SPX PROPHET</div>
                <div class="terminal-subtitle">Institutional Options Intelligence</div>
            </div>
        </div>
        <div class="terminal-status">
            <div class="status-item">
                <div class="status-label">{price_label}</div>
                <div class="status-value">{display_price:,.2f}</div>
                <div style="font-size: 0.55rem; color: {'#10b981' if market_status == 'LIVE' else '#f59e0b'}; text-transform: uppercase;">{market_status}</div>
            </div>
            <div class="status-item">
                <div class="status-label">Session</div>
                <div class="status-value status-live">
                    <span class="live-dot"></span>
                    {ct_time.strftime('%H:%M:%S')} CT
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # QUICK STATS BAR
    trading_window = "OPEN" if ct_time.time() < LAST_ENTRY_TIME and is_market_open else "CLOSED"
    window_color = "green" if trading_window == "OPEN" else "red"
    
    st.markdown(f"""
    <div class="stats-bar">
        <div class="stat-item">
            <div class="stat-indicator green"></div>
            <div class="stat-text"><strong>{num_calls}</strong> CALLS Setups</div>
        </div>
        <div class="stat-item">
            <div class="stat-indicator red"></div>
            <div class="stat-text"><strong>{num_puts}</strong> PUTS Setups</div>
        </div>
        <div class="stat-item">
            <div class="stat-indicator {window_color}"></div>
            <div class="stat-text">Trading Window: <strong>{trading_window}</strong></div>
        </div>
        <div class="stat-item">
            <div class="stat-indicator gold"></div>
            <div class="stat-text">Decision: <strong>10:00 AM CT</strong></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ==========================================================================
    # OVERNIGHT ES DATA (shows SPX implied from ES futures)
    # ==========================================================================
    # Use manual offset from session state
    manual_offset = st.session_state.get('manual_es_offset', 8.0)
    
    if es_data and es_data.get('current'):
        es_current = es_data['current']
        spx_implied = es_current - manual_offset
        
        st.markdown("#### 📊 ES Futures → SPX Implied")
        es_c1, es_c2, es_c3 = st.columns(3)
        with es_c1:
            st.metric("ES Futures", f"{es_current:,.2f}")
        with es_c2:
            st.metric("Offset (Manual)", f"{manual_offset:+.2f}")
        with es_c3:
            st.metric("SPX Implied", f"{spx_implied:,.2f}")
    
    # ==========================================================================
    # ACTIVE TRADE SETUPS (10:00 AM - PRIMARY)
    # ==========================================================================
    
    # Check if viewing today's date (for EMA display)
    is_viewing_today = session_date.date() == get_ct_now().date()
    
    # Fetch 1-min data for EMA confirmation (only for today)
    ema_8, ema_21, bullish_cross, bearish_cross = 0, 0, False, False
    if is_viewing_today:
        df_1min = fetch_1min_data_for_ema()
        ema_8, ema_21, bullish_cross, bearish_cross = calculate_emas(df_1min)
    
    ema_data = {
        'ema_8': ema_8,
        'ema_21': ema_21,
        'bullish_cross': bullish_cross,
        'bearish_cross': bearish_cross
    }
    
    # Get active cone info from trade setups
    active_cone_name = trade_setups_1000.get('active_cone', 'Close')
    rail_reversal = trade_setups_1000.get('rail_reversal')
    cone_reason = trade_setups_1000.get('active_cone_reason', 'Close cone (default)')
    
    # Add reversal indicator if applicable
    reversal_badge = ""
    if rail_reversal == 'low_top_is_buy':
        reversal_badge = " ⚡ REVERSAL: Low ▲ is BUY"
    elif rail_reversal == 'high_bottom_is_sell':
        reversal_badge = " ⚡ REVERSAL: High ▼ is SELL"
    
    # ==========================================================================
    # VIX ZONE SYSTEM PANEL (Main Display)
    # ==========================================================================
    # Show VIX panel for:
    # - Today and past dates
    # - Next trading day IF we're in the overnight session (after 5pm CT)
    ct_now = get_ct_now()
    is_overnight_session = ct_now.time() >= time(17, 0)  # After 5pm CT
    is_next_trading_day = session_date.date() == (ct_now + timedelta(days=1)).date()
    
    # Also handle Sunday evening -> Monday case
    if ct_now.weekday() == 6:  # Sunday
        # Monday is the next trading day
        next_trading = ct_now + timedelta(days=1)
        is_next_trading_day = session_date.date() == next_trading.date()
    
    show_vix_panel = not is_future_date or (is_future_date and is_overnight_session and is_next_trading_day)
    
    if show_vix_panel:
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">🎯</div>
            <div class="section-title">SPX-VIX Confluence System</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Confluence requirement reminder
        st.markdown("""
        <div style="background: #f0f9ff; border: 1px solid #0ea5e9; border-radius: 8px; padding: 10px 14px; margin-bottom: 12px;">
            <div style="font-weight: 600; color: #0369a1; font-size: 0.8rem; margin-bottom: 4px;">Confluence Required:</div>
            <div style="display: flex; gap: 16px; font-size: 0.75rem; color: #0c4a6e;">
                <span>🟢 <strong>CALLS:</strong> VIX at TOP + SPX at ▼ rail</span>
                <span>🔴 <strong>PUTS:</strong> VIX at BOTTOM + SPX at ▲ rail</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 30-min close reminder
        st.markdown("""
        <div style="background: #fef3c7; border: 1px solid #d97706; border-radius: 8px; padding: 10px 14px; margin-bottom: 16px; display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 1.2rem;">⏱️</span>
            <div>
                <div style="font-weight: 600; color: #78350f; font-size: 0.85rem;">30-Minute Candle CLOSE Matters</div>
                <div style="color: #92400e; font-size: 0.75rem;">VIX wicks can pierce levels — wait for candle CLOSE to confirm rejection/bounce</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        if vix_signal is None:
            # VIX data not entered - prompt user
            st.markdown("""
            <div style="background: #dbeafe; border: 2px solid #3b82f6; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
                <div style="font-weight: 600; color: #1e40af; font-size: 0.9rem;">📝 Enter VIX Zone in Sidebar</div>
                <div style="color: #1e3a8a; font-size: 0.8rem; margin-top: 8px;">Enter VIX overnight zone (5pm-2am) to see trade direction and targets.</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Get the key values from vix_signal
            zone_bottom = vix_signal.get('zone_bottom', 0)
            zone_top = vix_signal.get('zone_top', 0)
            vix_current = vix_signal.get('current', 0)
            zone_status = vix_signal.get('zone_status', 'NO_DATA')
            zone_status_text = vix_signal.get('zone_status_text', '')
            trade_bias = vix_signal.get('trade_bias', 'UNKNOWN')
            trade_action = vix_signal.get('trade_action', '')
            spx_direction = vix_signal.get('spx_direction', '')
            entry_rail = vix_signal.get('entry_rail', 'N/A')
            exit_target = vix_signal.get('exit_target', '')
            zones_above = vix_signal.get('zones_above', [])
            zones_below = vix_signal.get('zones_below', [])
            position_in_zone = vix_signal.get('position_in_zone', 50)
            
            # Determine colors based on trade bias
            if trade_bias == "CALLS":
                main_color = "#10b981"
                main_bg = "#d1fae5"
                main_icon = "🟢"
                direction_text = "BULLISH"
            elif trade_bias == "PUTS":
                main_color = "#ef4444"
                main_bg = "#fee2e2"
                main_icon = "🔴"
                direction_text = "BEARISH"
            elif trade_bias == "WAIT":
                main_color = "#f59e0b"
                main_bg = "#fef3c7"
                main_icon = "🟡"
                direction_text = "NEUTRAL"
            else:
                main_color = "#6b7280"
                main_bg = "#f3f4f6"
                main_icon = "⏳"
                direction_text = "WAITING"
            
            # Breakout badge
            breakout_badge = ""
            if zone_status == "BREAKOUT_UP":
                breakout_badge = '<div style="background: #fee2e2; color: #dc2626; padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; margin-top: 8px;">⚠️ VIX BROKE UP — PUTS targets extend</div>'
            elif zone_status == "BREAKOUT_DOWN":
                breakout_badge = '<div style="background: #d1fae5; color: #059669; padding: 6px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; margin-top: 8px;">⚡ VIX BROKE DOWN — CALLS targets extend</div>'
            
            # Build main VIX Zone HTML
            vix_html = f"""
            <div style="background: #ffffff; border: 2px solid {main_color}; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                
                <!-- Main Trade Signal -->
                <div style="background: {main_bg}; border-radius: 8px; padding: 16px; margin-bottom: 16px; text-align: center;">
                    <div style="font-size: 2.5rem; margin-bottom: 4px;">{main_icon}</div>
                    <div style="font-weight: 700; color: {main_color}; font-size: 1.4rem;">{trade_bias}</div>
                    <div style="color: #64748b; font-size: 0.9rem; margin-top: 4px;">{trade_action}</div>
                    <div style="color: #475569; font-size: 0.8rem; margin-top: 2px; font-weight: 500;">{spx_direction}</div>
                    {breakout_badge}
                </div>
                
                <!-- VIX Zone Ladder (Visual) -->
                <div style="display: grid; grid-template-columns: 1fr 2fr 1fr; gap: 12px; margin-bottom: 16px;">
                    
                    <!-- Zones Above (PUTS extend) -->
                    <div style="text-align: center;">
                        <div style="font-size: 0.65rem; color: #ef4444; text-transform: uppercase; font-weight: 600; margin-bottom: 8px;">PUTS Extend ↑</div>
                        <div style="font-family: monospace; font-size: 0.75rem; color: #9ca3af; line-height: 1.8;">
                            {f'+4: {zones_above[3]:.2f}' if len(zones_above) > 3 else ''}<br>
                            {f'+3: {zones_above[2]:.2f}' if len(zones_above) > 2 else ''}<br>
                            {f'+2: {zones_above[1]:.2f}' if len(zones_above) > 1 else ''}<br>
                            {f'+1: {zones_above[0]:.2f}' if len(zones_above) > 0 else ''}
                        </div>
                    </div>
                    
                    <!-- Current Zone -->
                    <div>
                        <!-- Zone Top -->
                        <div style="background: linear-gradient(135deg, #d1fae5, #a7f3d0); border-radius: 8px; padding: 12px; text-align: center; margin-bottom: 8px; border: 2px solid #10b981;">
                            <div style="font-size: 0.7rem; color: #059669; text-transform: uppercase; font-weight: 600;">Zone Top (Resistance)</div>
                            <div style="font-family: monospace; font-size: 1.3rem; font-weight: 700; color: #047857;">{zone_top:.2f}</div>
                            <div style="font-size: 0.65rem; color: #065f46;">VIX <strong>CLOSES</strong> here → SPX UP → <strong>CALLS</strong></div>
                        </div>
                        
                        <!-- Current VIX -->
                        <div style="background: #0f172a; border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 8px;">
                            <div style="font-size: 0.65rem; color: #94a3b8; text-transform: uppercase;">Current VIX</div>
                            <div style="font-family: monospace; font-size: 1.5rem; font-weight: 700; color: #f8fafc;">{vix_current:.2f if vix_current > 0 else '—'}</div>
                            <div style="font-size: 0.65rem; color: #64748b;">{f'{position_in_zone:.0f}% in zone' if zone_status == 'CONTAINED' and position_in_zone else zone_status_text}</div>
                        </div>
                        
                        <!-- Zone Bottom -->
                        <div style="background: linear-gradient(135deg, #fee2e2, #fecaca); border-radius: 8px; padding: 12px; text-align: center; border: 2px solid #ef4444;">
                            <div style="font-size: 0.7rem; color: #dc2626; text-transform: uppercase; font-weight: 600;">Zone Bottom (Support)</div>
                            <div style="font-family: monospace; font-size: 1.3rem; font-weight: 700; color: #b91c1c;">{zone_bottom:.2f}</div>
                            <div style="font-size: 0.65rem; color: #991b1b;">VIX <strong>CLOSES</strong> here → SPX DOWN → <strong>PUTS</strong></div>
                        </div>
                    </div>
                    
                    <!-- Zones Below (CALLS extend) -->
                    <div style="text-align: center;">
                        <div style="font-size: 0.65rem; color: #10b981; text-transform: uppercase; font-weight: 600; margin-bottom: 8px;">CALLS Extend ↓</div>
                        <div style="font-family: monospace; font-size: 0.75rem; color: #9ca3af; line-height: 1.8;">
                            {f'-1: {zones_below[0]:.2f}' if len(zones_below) > 0 else ''}<br>
                            {f'-2: {zones_below[1]:.2f}' if len(zones_below) > 1 else ''}<br>
                            {f'-3: {zones_below[2]:.2f}' if len(zones_below) > 2 else ''}<br>
                            {f'-4: {zones_below[3]:.2f}' if len(zones_below) > 3 else ''}
                        </div>
                    </div>
                </div>
                
                <!-- Entry and Exit Info -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                    <div style="background: #f0fdf4; border-left: 4px solid #10b981; padding: 12px; border-radius: 0 8px 8px 0;">
                        <div style="font-size: 0.7rem; color: #065f46; text-transform: uppercase; font-weight: 600;">Entry Rail</div>
                        <div style="font-size: 0.95rem; color: #047857; font-weight: 600;">SPX {entry_rail}</div>
                    </div>
                    <div style="background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px; border-radius: 0 8px 8px 0;">
                        <div style="font-size: 0.7rem; color: #991b1b; text-transform: uppercase; font-weight: 600;">Exit Target</div>
                        <div style="font-size: 0.95rem; color: #b91c1c; font-weight: 600;">{exit_target if exit_target else 'Enter VIX data'}</div>
                    </div>
                </div>
            </div>
            """
            st.markdown(vix_html, unsafe_allow_html=True)
    
    st.markdown(f"### 🎯 10:00 AM Setups — {active_cone_name} Cone Active{reversal_badge}")
    st.caption(cone_reason)
    
    # EMA Status Display - Only show for today's live trading session
    # BULLISH = 8 EMA above 21 EMA (good for CALLS entries)
    # BEARISH = 8 EMA below 21 EMA (good for PUTS entries)
    
    if is_viewing_today and ema_8 > 0 and ema_21 > 0:
        ema_status_color = "#10b981" if ema_8 > ema_21 else "#ef4444"
        ema_direction = "BULLISH (8 > 21)" if ema_8 > ema_21 else "BEARISH (8 < 21)"
        ema_hint = "Favors CALLS entries" if ema_8 > ema_21 else "Favors PUTS entries"
        cross_alert = ""
        if bullish_cross:
            cross_alert = "🔔 BULLISH CROSS! 8 EMA crossed ABOVE 21 EMA - BUY signal!"
        elif bearish_cross:
            cross_alert = "🔔 BEARISH CROSS! 8 EMA crossed BELOW 21 EMA - SELL signal!"
        
        st.markdown(f"""
        <div style="background: #ffffff; border: 2px solid {ema_status_color}; border-radius: 8px; padding: 12px; margin-bottom: 16px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div>
                    <span style="color: #64748b; font-size: 0.7rem; font-weight: 600;">ENTRY CONFIRMATION (1-MIN EMAs)</span>
                    <div style="color: {ema_status_color}; font-weight: 700; font-size: 1.1rem;">{ema_direction}</div>
                    <div style="color: #64748b; font-size: 0.7rem;">{ema_hint}</div>
                </div>
                <div style="text-align: right; background: #f1f5f9; padding: 8px 12px; border-radius: 6px;">
                    <div style="color: #334155; font-size: 0.75rem; font-weight: 500;">8 EMA: <span style="font-family: monospace; color: #0f172a;">{ema_8:.2f}</span></div>
                    <div style="color: #334155; font-size: 0.75rem; font-weight: 500;">21 EMA: <span style="font-family: monospace; color: #0f172a;">{ema_21:.2f}</span></div>
                </div>
            </div>
            {f'<div style="background: #fef3c7; color: #92400e; font-weight: 600; margin-top: 10px; padding: 8px; border-radius: 4px; text-align: center;">{cross_alert}</div>' if cross_alert else ''}
        </div>
        """, unsafe_allow_html=True)
    elif is_viewing_today:
        # Today but EMA data unavailable (market closed or data fetch failed)
        st.markdown("""
        <div style="background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; margin-bottom: 16px;">
            <span style="color: #64748b; font-size: 0.8rem;">📊 EMA data unavailable (market may be closed)</span>
        </div>
        """, unsafe_allow_html=True)
    # For historical dates, don't show EMA panel at all
    
    # CALLS SECTION
    st.markdown("""
    <div class="section-header">
        <div class="section-icon">📈</div>
        <div class="section-title">BUY Points — Descending Rails (CALLS)</div>
    </div>
    """, unsafe_allow_html=True)
    
    if num_calls > 0:
        for setup in trade_setups_1000['calls_setups']:
            # Get entry status for this setup (only for today's live trading)
            if is_viewing_today:
                entry_status = get_entry_status(setup, current_price, ema_data, st.session_state)
            else:
                entry_status = None  # No entry tracking for historical dates
            render_institutional_trade_card(setup, current_price, entry_status, vix_signal if not is_future_date else None)
            
            # Trigger alerts if needed (only for today)
            if is_viewing_today and entry_status:
                setup_id = f"{setup.direction}_{setup.entry_price:.0f}"
                alert_html = render_alert_trigger(entry_status['alert_level'], setup_id, entry_status['message'])
                if alert_html:
                    st.markdown(alert_html, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="trade-panel">
            <div class="trade-panel-body" style="text-align: center; color: var(--text-muted);">
                No high-probability BUY entries detected for this session
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # PUTS SECTION
    st.markdown("""
    <div class="section-header">
        <div class="section-icon">📉</div>
        <div class="section-title">SELL Points — Ascending Rails (PUTS)</div>
    </div>
    """, unsafe_allow_html=True)
    
    if num_puts > 0:
        for setup in trade_setups_1000['puts_setups']:
            # Get entry status for this setup (only for today's live trading)
            if is_viewing_today:
                entry_status = get_entry_status(setup, current_price, ema_data, st.session_state)
            else:
                entry_status = None  # No entry tracking for historical dates
            render_institutional_trade_card(setup, current_price, entry_status, vix_signal if not is_future_date else None)
            
            # Trigger alerts if needed (only for today)
            if is_viewing_today and entry_status:
                setup_id = f"{setup.direction}_{setup.entry_price:.0f}"
                alert_html = render_alert_trigger(entry_status['alert_level'], setup_id, entry_status['message'])
                if alert_html:
                    st.markdown(alert_html, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="trade-panel">
            <div class="trade-panel-body" style="text-align: center; color: var(--text-muted);">
                No high-probability SELL entries detected for this session
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # ==========================================================================
    # POSITION MONITOR
    # ==========================================================================
    
    all_setups = trade_setups_1000.get('calls_setups', []) + trade_setups_1000.get('puts_setups', [])
    
    if all_setups:
        st.markdown("""
        <div class="section-header">
            <div class="section-icon">🎯</div>
            <div class="section-title">Position Monitor — Next Entry</div>
        </div>
        """, unsafe_allow_html=True)
        
        # For future dates, don't use session high/low (they don't exist yet)
        if is_future_date:
            session_high = None
            session_low = None
        else:
            session_high = st.session_state.get('session_high')
            session_low = st.session_state.get('session_low')
        
        # Buffer for "close enough" triggers (accounts for spreads/slippage/data source differences)
        TRIGGER_BUFFER = 2.0  # 2 point buffer
        
        active_setups = []
        triggered_setups = []
        
        for setup in all_setups:
            setup.distance = abs(current_price - setup.entry_price)
            setup.triggered = False
            
            if setup.direction == "CALLS":
                # CALLS entry triggers when price dips TO or NEAR entry level
                # Check if session low reached within buffer of entry
                if session_low is not None and session_low <= setup.entry_price + TRIGGER_BUFFER:
                    setup.triggered = True
                    triggered_setups.append(setup)
                else:
                    active_setups.append(setup)
            else:  # PUTS
                # PUTS entry triggers when price rises TO or NEAR entry level
                # Check if session high reached within buffer of entry
                if session_high is not None and session_high >= setup.entry_price - TRIGGER_BUFFER:
                    setup.triggered = True
                    triggered_setups.append(setup)
                else:
                    active_setups.append(setup)
        
        # Show next active entry (not yet triggered)
        if active_setups:
            nearest = min(active_setups, key=lambda x: x.distance)
            
            # Determine status
            if nearest.distance <= AT_RAIL_THRESHOLD:
                status = "AT ENTRY"
                status_class = "badge-go"
            elif nearest.distance <= 15:
                status = "APPROACHING"
                status_class = "badge-wait"
            else:
                status = "WAITING"
                status_class = "badge-nogo"
            
            direction_class = "badge-calls" if nearest.direction == "CALLS" else "badge-puts"
            
            st.markdown(f"""
            <div class="trade-panel">
                <div class="trade-panel-header">
                    <div class="trade-panel-title">Priority Target</div>
                    <div>
                        <span class="trade-panel-badge {direction_class}">{nearest.direction}</span>
                        <span class="trade-panel-badge {status_class}">{status}</span>
                    </div>
                </div>
                <div class="trade-panel-body">
                    <div class="contract-display">
                        <div class="contract-strike">{nearest.strike_label}</div>
                        <div class="contract-type">0DTE SPX Option</div>
                    </div>
                    <div class="entry-row">
                        <div class="entry-item">
                            <div class="entry-label">Current Price</div>
                            <div class="entry-value">{current_price:,.2f}</div>
                        </div>
                        <div class="entry-item">
                            <div class="entry-label">Entry Level</div>
                            <div class="entry-value gold">{nearest.entry_price:,.2f}</div>
                        </div>
                        <div class="entry-item">
                            <div class="entry-label">Distance</div>
                            <div class="entry-value">{nearest.distance:.1f} pts</div>
                        </div>
                        <div class="entry-item">
                            <div class="entry-label">Target (50%)</div>
                            <div class="entry-value green">+${nearest.profit_50_theta_adjusted:,.0f}</div>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Show triggered entries (completed trades)
        if triggered_setups:
            st.markdown(f"""
            <div style="margin-top: 0.5rem; padding: 0.75rem 1rem; background: var(--bg-tertiary); border-radius: 6px; border-left: 3px solid var(--accent-green);">
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">✅ TRIGGERED TODAY</div>
                <div style="font-size: 0.85rem; color: var(--text-primary);">
                    {', '.join([f"{s.direction} @ {s.entry_price:.2f}" for s in triggered_setups])}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        if not active_setups:
            st.markdown("""
            <div class="trade-panel">
                <div class="trade-panel-body" style="text-align: center; color: var(--text-muted);">
                    All entries triggered for today — no active setups remaining
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ==========================================================================
    # CANDLE VALIDATION CHECKLIST
    # ==========================================================================
    
    with st.expander("📋 Entry Validation Checklist"):
        st.markdown("""
        ### ✅ Valid BUY Entry (CALLS at Descending Rail)
        
        The candle that touches the BUY POINT must be:
        1. **Bearish candle** (red/down candle)
        2. **Closes less than 5 points ABOVE** the entry level
        3. **Does NOT drop more than 5 points BELOW** the entry level
        
        ---
        
        ### ✅ Valid SELL Entry (PUTS at Ascending Rail)
        
        The candle that touches the SELL POINT must be:
        1. **Bullish candle** (green/up candle)
        2. **Closes less than 5 points BELOW** the entry level
        3. **Does NOT rise more than 5 points ABOVE** the entry level
        
        ---
        
        ### ⚠️ Important Notes
        
        - **Descending Rails** = BUY points (except on strong DOWN days)
        - **Ascending Rails** = SELL points (except on strong UP days)
        - On **strong UP days**: Ascending rail can become temporary BUY point
        - On **strong DOWN days**: Descending rail can become temporary SELL point
        - **Close Cone** is best for range/chop days (most common)
        - **High Cone** is best for strong UP trend days
        - **Low Cone** is best for strong DOWN trend days
        """)
    
    # ==========================================================================
    # SECONDARY: Decision Windows Comparison
    # ==========================================================================
    
    with st.expander("🕐 Compare 8:30 AM vs 10:00 AM Setups"):
        col_830_exp, col_1000_exp = st.columns(2)
        
        with col_830_exp:
            st.markdown("**8:30 AM Setups:**")
            if trade_setups_830.get('calls_setups'):
                for s in trade_setups_830['calls_setups']:
                    st.write(f"🟢 {s.strike_label} @ {s.entry_price:.2f}")
            if trade_setups_830.get('puts_setups'):
                for s in trade_setups_830['puts_setups']:
                    st.write(f"🔴 {s.strike_label} @ {s.entry_price:.2f}")
        
        with col_1000_exp:
            st.markdown("**10:00 AM Setups:**")
            if trade_setups_1000.get('calls_setups'):
                for s in trade_setups_1000['calls_setups']:
                    st.write(f"🟢 {s.strike_label} @ {s.entry_price:.2f}")
            if trade_setups_1000.get('puts_setups'):
                for s in trade_setups_1000['puts_setups']:
                    st.write(f"🔴 {s.strike_label} @ {s.entry_price:.2f}")
    
    # ==========================================================================
    # CHECKLIST & VALIDATION INFO
    # ==========================================================================
    
    col_check, col_val = st.columns(2)
    
    with col_check:
        render_checklist(regime, action, cones, current_price, overnight_validation, vix_signal, active_cone_info, ema_data)
    
    with col_val:
        # Overnight Validation Display
        if overnight_validation and overnight_validation.get('validation_notes'):
            st.markdown("#### 🌙 Overnight Validation")
            
            # High structure status
            active_high = overnight_validation.get('active_high_structure', 'primary')
            if active_high == 'secondary':
                st.success("✓ HIGH: Secondary (High²) validated")
            elif overnight_validation.get('high_secondary_broken'):
                st.warning("⚠ HIGH: Secondary broken overnight")
            
            # Low structure status
            active_low = overnight_validation.get('active_low_structure', 'primary')
            if active_low == 'secondary':
                st.success("✓ LOW: Secondary (Low²) validated")
            elif overnight_validation.get('low_secondary_broken'):
                st.warning("⚠ LOW: Secondary broken overnight")
            
            # Validation notes in expander
            with st.expander("📋 Detailed Notes"):
                for note in overnight_validation['validation_notes']:
                    st.write(note)
        else:
            st.info("No overnight validation data available")
    
    st.markdown("---")
    
    # Row: Full Projection Table
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
