# ═══════════════════════════════════════════════════════════════════════════════
# SPX PROPHET V7.0 - STRUCTURAL 0DTE TRADING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
# 
# A complete system for 0DTE SPX options trading based on overnight structure.
#
# CORE CONCEPT:
# - Overnight sessions (Sydney → Tokyo → London) create a structural channel
# - Channel type determines market bias and trade direction
# - MM positioning (via VIX term structure) can override normal setups
# - Entry at channel boundaries, targets at cone projections
#
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
import json
import os
import math
from datetime import datetime, date, time, timedelta
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="SPX Prophet V7", page_icon="🔮", layout="wide")

CT = pytz.timezone("America/Chicago")
ET = pytz.timezone("America/New_York")
SLOPE = 0.48  # Points per 30-minute block
SAVE_FILE = "spx_prophet_v7_inputs.json"

# Session times (CT)
SESSION_TIMES = {
    "sydney": {"start": (17, 0), "end": (20, 30)},   # 5:00 PM - 8:30 PM
    "tokyo":  {"start": (21, 0), "end": (1, 30)},    # 9:00 PM - 1:30 AM
    "london": {"start": (2, 0),  "end": (5, 0)},     # 2:00 AM - 5:00 AM
}

# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════
class ChannelType(Enum):
    ASCENDING = "ASCENDING"       # Tokyo/London made higher high → bullish
    DESCENDING = "DESCENDING"     # Tokyo/London made lower low → bearish  
    EXPANDING = "EXPANDING"       # Both higher high AND lower low → volatile
    CONTRACTING = "CONTRACTING"   # Neither → no directional bias
    UNDETERMINED = "UNDETERMINED"

class Position(Enum):
    ABOVE = "ABOVE"    # Price above ceiling
    INSIDE = "INSIDE"  # Price between ceiling and floor
    BELOW = "BELOW"    # Price below floor

class MMBias(Enum):
    CALLS_HEAVY = "CALLS_HEAVY"  # Retail long calls → MMs push DOWN
    PUTS_HEAVY = "PUTS_HEAVY"    # Retail long puts → MMs push UP
    NEUTRAL = "NEUTRAL"

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
def now_ct():
    return datetime.now(CT)

def blocks_between(start, end):
    """Calculate number of 30-minute blocks between two times."""
    if start is None or end is None or end <= start:
        return 0
    return max(0, int((end - start).total_seconds() / 1800))

def save_inputs(data):
    try:
        with open(SAVE_FILE, 'w') as f:
            json.dump(data, f)
    except:
        pass

def load_inputs():
    try:
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {}

# ═══════════════════════════════════════════════════════════════════════════════
# BLACK-SCHOLES PRICING (Calibrated to real 0DTE market)
# ═══════════════════════════════════════════════════════════════════════════════
def norm_cdf(x):
    """Standard normal cumulative distribution function."""
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p, sign = 0.3275911, 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)

def black_scholes(S, K, T, r, sigma, opt_type):
    """Calculate option price using Black-Scholes model."""
    if T <= 0:
        return max(0, S - K) if opt_type == "CALL" else max(0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if opt_type == "CALL":
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

def calc_0dte_iv(vix, spot, strike, hours_to_expiry):
    """
    Calculate realistic 0DTE implied volatility.
    
    Calibrated to real market: Barchart SPX IV ~32.73% when VIX ~20 (ratio ~1.6x)
    """
    # Base multiplier varies by time to expiry
    if hours_to_expiry > 5:
        base_mult = 1.6
    elif hours_to_expiry > 3:
        base_mult = 1.7
    else:
        base_mult = 1.8
    
    base_iv = (vix / 100) * base_mult
    
    # IV Smile: OTM strikes have higher IV (+0.5% per 10 pts OTM)
    distance_otm = abs(spot - strike)
    smile_add = (distance_otm / 10) * 0.005
    
    return max(base_iv + smile_add, 0.15)

def estimate_0dte_premium(spot, strike, hours_to_expiry, vix, opt_type):
    """Estimate 0DTE option premium using calibrated Black-Scholes."""
    iv = calc_0dte_iv(vix, spot, strike, hours_to_expiry)
    T = max(0.0001, hours_to_expiry / (365 * 24))
    premium = black_scholes(spot, strike, T, 0.05, iv, opt_type)
    return max(round(premium, 2), 0.05)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def fetch_es_current():
    """Fetch current ES futures price."""
    try:
        es = yf.Ticker("ES=F")
        d = es.history(period="2d", interval="5m")
        if d is not None and not d.empty:
            return round(float(d['Close'].iloc[-1]), 2)
    except:
        pass
    return None

@st.cache_data(ttl=120, show_spinner=False)
def fetch_es_candles(days=7):
    """Fetch ES futures 30-minute candles."""
    try:
        es = yf.Ticker("ES=F")
        data = es.history(period=f"{days}d", interval="30m")
        if data is not None and not data.empty and len(data) > 10:
            return data
    except:
        pass
    return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_vix():
    """Fetch current VIX value."""
    try:
        vix = yf.Ticker("^VIX")
        data = vix.history(period="2d")
        if data is not None and not data.empty:
            return round(float(data['Close'].iloc[-1]), 2)
    except:
        pass
    return 16.0  # Default

@st.cache_data(ttl=300, show_spinner=False)
def fetch_mm_bias():
    """
    Analyze Market Maker positioning via VIX Term Structure.
    
    VIX vs VIX3M spread indicates retail positioning:
    - Contango (VIX < VIX3M): Complacency → Calls heavy → MMs push DOWN
    - Backwardation (VIX > VIX3M): Fear → Puts heavy → MMs push UP
    """
    results = {
        "vix": None, "vix3m": None, "spread": None,
        "vix_structure": None, "score": 0,
        "bias": MMBias.NEUTRAL, "interpretation": ""
    }
    
    try:
        vix_data = yf.Ticker("^VIX").history(period="2d")
        vix3m_data = yf.Ticker("^VIX3M").history(period="2d")
        
        if not vix_data.empty and not vix3m_data.empty:
            vix = round(float(vix_data['Close'].iloc[-1]), 2)
            vix3m = round(float(vix3m_data['Close'].iloc[-1]), 2)
            spread = round(vix - vix3m, 2)
            
            results["vix"] = vix
            results["vix3m"] = vix3m
            results["spread"] = spread
            
            # Score based on spread magnitude
            if spread <= -3:
                results["vix_structure"] = "DEEP CONTANGO"
                results["score"] = -100
                results["bias"] = MMBias.CALLS_HEAVY
                results["interpretation"] = f"Deep Contango ({spread:+.1f}): Extreme complacency. MMs push DOWN."
            elif spread <= -1.5:
                results["vix_structure"] = "CONTANGO"
                results["score"] = -50
                results["bias"] = MMBias.CALLS_HEAVY
                results["interpretation"] = f"Contango ({spread:+.1f}): Calls heavy. MMs likely push DOWN."
            elif spread < 0:
                results["vix_structure"] = "MILD CONTANGO"
                results["score"] = -25
                results["bias"] = MMBias.NEUTRAL
                results["interpretation"] = f"Mild Contango ({spread:+.1f}): Slight call bias."
            elif spread <= 1.5:
                results["vix_structure"] = "FLAT"
                results["score"] = 0
                results["bias"] = MMBias.NEUTRAL
                results["interpretation"] = f"Flat ({spread:+.1f}): Balanced positioning."
            elif spread <= 3:
                results["vix_structure"] = "MILD BACKWARDATION"
                results["score"] = 25
                results["bias"] = MMBias.NEUTRAL
                results["interpretation"] = f"Mild Backwardation ({spread:+.1f}): Slight put bias."
            elif spread <= 5:
                results["vix_structure"] = "BACKWARDATION"
                results["score"] = 50
                results["bias"] = MMBias.PUTS_HEAVY
                results["interpretation"] = f"Backwardation ({spread:+.1f}): Puts heavy. MMs push UP."
            else:
                results["vix_structure"] = "DEEP BACKWARDATION"
                results["score"] = 100
                results["bias"] = MMBias.PUTS_HEAVY
                results["interpretation"] = f"Deep Backwardation ({spread:+.1f}): Extreme fear. MMs push UP."
    except:
        results["interpretation"] = "Unable to fetch VIX data"
    
    return results

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════
def extract_sessions(es_candles, trading_date):
    """
    Extract session highs/lows from overnight candles.
    
    Sessions (CT):
    - Sydney: 5:00 PM - 8:30 PM (previous day)
    - Tokyo:  9:00 PM - 1:30 AM
    - London: 2:00 AM - 5:00 AM
    - Prior RTH: 8:30 AM - 3:00 PM (previous day)
    """
    if es_candles is None or es_candles.empty:
        return None
    
    result = {}
    overnight_day = trading_date - timedelta(days=1)
    if overnight_day.weekday() >= 5:  # Weekend adjustment
        overnight_day -= timedelta(days=(overnight_day.weekday() - 4))
    
    df = es_candles.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize(ET).tz_convert(CT)
    else:
        df.index = df.index.tz_convert(CT)
    
    # Define session windows
    sessions = {
        "sydney": (CT.localize(datetime.combine(overnight_day, time(17, 0))),
                   CT.localize(datetime.combine(overnight_day, time(20, 30)))),
        "tokyo": (CT.localize(datetime.combine(overnight_day, time(21, 0))),
                  CT.localize(datetime.combine(trading_date, time(1, 30)))),
        "london": (CT.localize(datetime.combine(trading_date, time(2, 0))),
                   CT.localize(datetime.combine(trading_date, time(5, 0)))),
        "overnight": (CT.localize(datetime.combine(overnight_day, time(17, 0))),
                      CT.localize(datetime.combine(trading_date, time(8, 30))))
    }
    
    # Extract high/low for each session
    for name, (start, end) in sessions.items():
        mask = (df.index >= start) & (df.index <= end)
        data = df[mask]
        if not data.empty:
            result[name] = {
                "high": round(data['High'].max(), 2),
                "low": round(data['Low'].min(), 2),
                "high_time": data['High'].idxmax(),
                "low_time": data['Low'].idxmin()
            }
    
    # Prior RTH session
    prior_day = trading_date - timedelta(days=1)
    if prior_day.weekday() >= 5:
        prior_day -= timedelta(days=(prior_day.weekday() - 4))
    prior_start = CT.localize(datetime.combine(prior_day, time(8, 30)))
    prior_end = CT.localize(datetime.combine(prior_day, time(15, 0)))
    prior_mask = (df.index >= prior_start) & (df.index <= prior_end)
    prior_data = df[prior_mask]
    if not prior_data.empty:
        result["prior_close"] = round(prior_data['Close'].iloc[-1], 2)
        result["prior_high"] = round(prior_data['High'].max(), 2)
        result["prior_low"] = round(prior_data['Low'].min(), 2)
        result["prior_high_time"] = prior_data['High'].idxmax()
        result["prior_low_time"] = prior_data['Low'].idxmin()
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL DETERMINATION
# ═══════════════════════════════════════════════════════════════════════════════
def determine_channel(sydney, tokyo, london=None):
    """
    Determine channel type from overnight session progression.
    
    Logic:
    1. Compare Sydney → Tokyo → London highs and lows
    2. Find TRUE high and TRUE low (which session made them)
    3. Determine channel by whether range expanded/contracted and direction
    
    Channel Types:
    - ASCENDING:   Later session made higher high (market trending up)
    - DESCENDING:  Later session made lower low (market trending down)
    - EXPANDING:   Both higher high AND lower low (volatile)
    - CONTRACTING: Neither (no directional bias)
    
    Returns: (channel_type, reason, upper_pivot, lower_pivot, upper_time, lower_time)
    """
    if not sydney or not tokyo:
        return ChannelType.UNDETERMINED, "Missing data", None, None, None, None
    
    # Gather all session highs/lows
    all_highs = [
        (sydney["high"], sydney.get("high_time"), "Sydney"),
        (tokyo["high"], tokyo.get("high_time"), "Tokyo")
    ]
    all_lows = [
        (sydney["low"], sydney.get("low_time"), "Sydney"),
        (tokyo["low"], tokyo.get("low_time"), "Tokyo")
    ]
    
    if london:
        all_highs.append((london["high"], london.get("high_time"), "London"))
        all_lows.append((london["low"], london.get("low_time"), "London"))
    
    # Find TRUE high and low
    highest = max(all_highs, key=lambda x: x[0])
    lowest = min(all_lows, key=lambda x: x[0])
    
    true_high, high_time, high_session = highest
    true_low, low_time, low_session = lowest
    
    # Check expansion/contraction vs Sydney baseline
    tokyo_expanded_high = tokyo["high"] > sydney["high"]
    tokyo_expanded_low = tokyo["low"] < sydney["low"]
    
    london_expanded_high = london["high"] > max(sydney["high"], tokyo["high"]) if london else False
    london_expanded_low = london["low"] < min(sydney["low"], tokyo["low"]) if london else False
    
    # Determine channel type
    if london:
        expanded_high = tokyo_expanded_high or london_expanded_high
        expanded_low = tokyo_expanded_low or london_expanded_low
    else:
        expanded_high = tokyo_expanded_high
        expanded_low = tokyo_expanded_low
    
    if expanded_high and expanded_low:
        reason = f"EXPANDING: Range expanded both ways (H:{true_high} from {high_session}, L:{true_low} from {low_session})"
        return ChannelType.EXPANDING, reason, true_high, true_low, high_time, low_time
    elif not expanded_high and not expanded_low:
        reason = f"CONTRACTING: Range stayed within Sydney"
        return ChannelType.CONTRACTING, reason, true_high, true_low, high_time, low_time
    elif expanded_high:
        reason = f"ASCENDING: {high_session} made higher high ({true_high})"
        return ChannelType.ASCENDING, reason, true_high, true_low, high_time, low_time
    else:
        reason = f"DESCENDING: {low_session} made lower low ({true_low})"
        return ChannelType.DESCENDING, reason, true_high, true_low, high_time, low_time

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL LEVEL CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════
def calc_channel_levels(upper_pivot, lower_pivot, upper_time, lower_time, ref_time, channel_type):
    """
    Calculate ceiling/floor at reference time (9 AM) by projecting slope from pivots.
    
    SLOPE RULES (0.48 points per 30-min block):
    - ASCENDING:   Ceiling +0.48, Floor +0.48 (both rise)
    - DESCENDING:  Ceiling -0.48, Floor -0.48 (both fall)
    - EXPANDING:   Ceiling +0.48, Floor -0.48 (diverge)
    - CONTRACTING: Ceiling -0.48, Floor +0.48 (converge)
    """
    if upper_pivot is None or lower_pivot is None:
        return None, None
    
    # Calculate blocks from pivot times to reference time
    blocks_high = blocks_between(upper_time, ref_time) if upper_time and ref_time else 0
    blocks_low = blocks_between(lower_time, ref_time) if lower_time and ref_time else 0
    
    if channel_type == ChannelType.ASCENDING:
        ceiling = round(upper_pivot + SLOPE * blocks_high, 2)
        floor = round(lower_pivot + SLOPE * blocks_low, 2)
    elif channel_type == ChannelType.DESCENDING:
        ceiling = round(upper_pivot - SLOPE * blocks_high, 2)
        floor = round(lower_pivot - SLOPE * blocks_low, 2)
    elif channel_type == ChannelType.EXPANDING:
        ceiling = round(upper_pivot + SLOPE * blocks_high, 2)
        floor = round(lower_pivot - SLOPE * blocks_low, 2)
    elif channel_type == ChannelType.CONTRACTING:
        ceiling = round(upper_pivot - SLOPE * blocks_high, 2)
        floor = round(lower_pivot + SLOPE * blocks_low, 2)
    else:
        ceiling, floor = upper_pivot, lower_pivot
    
    return ceiling, floor

def calc_prior_rth_cone(prior_high, prior_low, prior_high_time, prior_low_time, ref_time, channel_type):
    """
    Calculate profit target cones from prior RTH session.
    
    These serve as dynamic profit targets for breakout trades.
    """
    if prior_high is None or prior_low is None:
        return None, None, 0, 0
    
    blocks_high = blocks_between(prior_high_time, ref_time) if prior_high_time and ref_time else 0
    blocks_low = blocks_between(prior_low_time, ref_time) if prior_low_time and ref_time else 0
    
    if channel_type == ChannelType.ASCENDING:
        upper_cone = round(prior_high + SLOPE * blocks_high, 2)
        lower_cone = round(prior_low + SLOPE * blocks_low, 2)
    elif channel_type == ChannelType.DESCENDING:
        upper_cone = round(prior_high - SLOPE * blocks_high, 2)
        lower_cone = round(prior_low - SLOPE * blocks_low, 2)
    elif channel_type == ChannelType.EXPANDING:
        upper_cone = round(prior_high + SLOPE * blocks_high, 2)
        lower_cone = round(prior_low - SLOPE * blocks_low, 2)
    else:
        upper_cone, lower_cone = prior_high, prior_low
    
    return upper_cone, lower_cone, blocks_high, blocks_low

def get_position(price, ceiling, floor):
    """Determine current price position relative to channel."""
    if price > ceiling:
        return Position.ABOVE
    elif price < floor:
        return Position.BELOW
    return Position.INSIDE

# ═══════════════════════════════════════════════════════════════════════════════
# DECISION ENGINE - The Brain
# ═══════════════════════════════════════════════════════════════════════════════
def analyze_market_state(current_spx, ceiling_spx, floor_spx, channel_type, mm_bias, 
                         upper_cone_spx, lower_cone_spx, vix):
    """
    Analyze market state and generate PRIMARY and ALTERNATE trade scenarios.
    
    Returns:
    - primary: Most likely trade setup with contract details
    - alternate: Backup if primary fails
    - no_trade: True if should not trade
    - context: Market structure summary
    """
    
    result = {
        "no_trade": False,
        "no_trade_reason": None,
        "context": None,
        "primary": None,
        "alternate": None
    }
    
    # Determine position
    if current_spx > ceiling_spx:
        position = Position.ABOVE
        pos_desc = f"ABOVE ceiling by {round(current_spx - ceiling_spx, 1)} pts"
    elif current_spx < floor_spx:
        position = Position.BELOW
        pos_desc = f"BELOW floor by {round(floor_spx - current_spx, 1)} pts"
    else:
        position = Position.INSIDE
        dist_ceil = round(ceiling_spx - current_spx, 1)
        dist_floor = round(current_spx - floor_spx, 1)
        pos_desc = f"INSIDE (↑{dist_ceil} to ceiling, ↓{dist_floor} to floor)"
    
    # Default targets
    calls_target = upper_cone_spx if upper_cone_spx else ceiling_spx + 25
    puts_target = lower_cone_spx if lower_cone_spx else floor_spx - 25
    
    result["context"] = f"{channel_type.value} | {pos_desc} | MM: {mm_bias.value}"
    
    def make_scenario(name, direction, entry, stop, target, trigger, rationale, confidence):
        """Build a complete trade scenario with contract details."""
        if direction == "CALLS":
            potential = round(target - entry, 1)
            strike = int(math.ceil((entry + 20) / 5) * 5)  # 20 pts OTM, round up
            opt_type = "CALL"
        else:
            potential = round(entry - target, 1)
            strike = int(math.floor((entry - 20) / 5) * 5)  # 20 pts OTM, round down
            opt_type = "PUT"
        
        # Calculate premiums at entry (9 AM, 6 hrs to expiry) and target (11 AM, 4 hrs)
        entry_premium = estimate_0dte_premium(entry, strike, 6.0, vix, opt_type)
        target_premium = estimate_0dte_premium(target, strike, 4.0, vix, opt_type)
        dollar_profit = round((target_premium - entry_premium) * 100, 0)
        
        return {
            "name": name,
            "direction": direction,
            "entry": entry,
            "stop": stop,
            "target": target,
            "trigger": trigger,
            "rationale": rationale,
            "confidence": confidence,
            "potential_pts": potential,
            "rr_ratio": round(potential / 5.0, 1) if potential > 0 else 0,
            "strike": strike,
            "contract": f"SPX {strike}{'C' if direction == 'CALLS' else 'P'} 0DTE",
            "entry_premium": entry_premium,
            "target_premium": target_premium,
            "dollar_profit": dollar_profit
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # NO TRADE CONDITIONS
    # ═══════════════════════════════════════════════════════════════════════════
    if channel_type == ChannelType.CONTRACTING:
        result["no_trade"] = True
        result["no_trade_reason"] = "CONTRACTING channel - No directional bias. Wait for expansion."
        return result
    
    if channel_type == ChannelType.UNDETERMINED:
        result["no_trade"] = True
        result["no_trade_reason"] = "Cannot determine channel. Check data inputs."
        return result
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ASCENDING CHANNEL SCENARIOS
    # ═══════════════════════════════════════════════════════════════════════════
    if channel_type == ChannelType.ASCENDING:
        
        if position == Position.ABOVE:
            if mm_bias == MMBias.CALLS_HEAVY:
                result["primary"] = make_scenario(
                    "MM Reversal", "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                    "Price rallies to ceiling → PUTS on rejection",
                    "CALLS HEAVY: MMs push DOWN to avoid paying calls", "HIGH"
                )
                result["alternate"] = make_scenario(
                    "Floor Bounce", "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                    "If price reaches floor → CALLS on support",
                    "Floor bounce back to ceiling", "MEDIUM"
                )
            else:
                result["primary"] = make_scenario(
                    "Ceiling Support", "CALLS", ceiling_spx, ceiling_spx - 5, calls_target,
                    "Price dips to ceiling → CALLS on support",
                    "ASCENDING + ABOVE: Ceiling is support", "HIGH"
                )
                result["alternate"] = make_scenario(
                    "Ceiling Fails", "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                    "If ceiling breaks → PUTS on rejection",
                    "Failed support becomes resistance", "MEDIUM"
                )
        
        elif position == Position.INSIDE:
            result["primary"] = make_scenario(
                "Floor Rejection", "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                "Price touches floor → CALLS if closes above",
                "ASCENDING: Floor rejection is bullish", "HIGH"
            )
            result["alternate"] = make_scenario(
                "Ceiling Breakout", "CALLS", ceiling_spx, ceiling_spx - 5, calls_target,
                "If breaks ceiling → CALLS on retrace to ceiling",
                "Ceiling becomes support → Target: Upper Cone", "MEDIUM"
            )
        
        elif position == Position.BELOW:
            result["primary"] = make_scenario(
                "Floor Resistance", "PUTS", floor_spx, floor_spx + 5, puts_target,
                "Price rallies to floor → PUTS on rejection",
                "ASCENDING + BELOW: Floor is resistance (bearish)", "HIGH"
            )
            result["alternate"] = make_scenario(
                "Reclaim Floor", "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                "If reclaims floor → CALLS",
                "Back inside channel = bullish", "MEDIUM"
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DESCENDING CHANNEL SCENARIOS  
    # ═══════════════════════════════════════════════════════════════════════════
    elif channel_type == ChannelType.DESCENDING:
        
        if position == Position.BELOW:
            if mm_bias == MMBias.PUTS_HEAVY:
                result["primary"] = make_scenario(
                    "MM Reversal", "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                    "Price drops to floor → CALLS on support",
                    "PUTS HEAVY: MMs push UP to avoid paying puts", "HIGH"
                )
                result["alternate"] = make_scenario(
                    "Ceiling Fade", "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                    "If rallies to ceiling → PUTS on resistance",
                    "Fade the rally", "MEDIUM"
                )
            else:
                result["primary"] = make_scenario(
                    "Floor Resistance", "PUTS", floor_spx, floor_spx + 5, puts_target,
                    "Price rallies to floor → PUTS on rejection",
                    "DESCENDING + BELOW: Floor is resistance", "HIGH"
                )
                result["alternate"] = make_scenario(
                    "Floor Reclaimed", "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                    "If reclaims floor → CALLS",
                    "Failed resistance becomes support", "MEDIUM"
                )
        
        elif position == Position.INSIDE:
            result["primary"] = make_scenario(
                "Ceiling Rejection", "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                "Price touches ceiling → PUTS if closes below",
                "DESCENDING: Ceiling rejection is bearish", "HIGH"
            )
            result["alternate"] = make_scenario(
                "Floor Breakdown", "PUTS", floor_spx, floor_spx + 5, puts_target,
                "If breaks floor → PUTS on retrace to floor",
                "Floor becomes resistance → Target: Lower Cone", "MEDIUM"
            )
        
        elif position == Position.ABOVE:
            result["primary"] = make_scenario(
                "Ceiling Support", "CALLS", ceiling_spx, ceiling_spx - 5, calls_target,
                "Price drops to ceiling → CALLS on support",
                "DESCENDING + ABOVE: Ceiling is support (bullish)", "HIGH"
            )
            result["alternate"] = make_scenario(
                "Lose Ceiling", "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                "If ceiling breaks → PUTS",
                "Back inside channel = bearish", "MEDIUM"
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EXPANDING CHANNEL - Fade Extremes
    # ═══════════════════════════════════════════════════════════════════════════
    elif channel_type == ChannelType.EXPANDING:
        result["primary"] = make_scenario(
            "Fade Ceiling", "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
            "Price reaches ceiling → PUTS to fade extreme",
            "EXPANDING: Volatile, fade extremes", "MEDIUM"
        )
        result["alternate"] = make_scenario(
            "Fade Floor", "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
            "Price reaches floor → CALLS to fade extreme",
            "EXPANDING: Volatile, fade extremes", "MEDIUM"
        )
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
def sidebar():
    saved = load_inputs()
    with st.sidebar:
        st.title("🔮 SPX Prophet V7")
        st.caption("Structural 0DTE System")
        st.divider()
        
        trading_date = st.date_input("📅 Trading Date", value=date.today())
        offset = st.number_input("⚙️ ES→SPX Offset", value=float(saved.get("offset", 35.5)), step=0.5)
        
        st.divider()
        override = st.checkbox("📝 Manual Override")
        manual = {}
        if override:
            st.caption("Enter ES values:")
            c1, c2 = st.columns(2)
            manual["sydney_high"] = c1.number_input("Sydney H", value=6075.0, step=0.5)
            manual["sydney_low"] = c2.number_input("Sydney L", value=6050.0, step=0.5)
            manual["tokyo_high"] = c1.number_input("Tokyo H", value=6080.0, step=0.5)
            manual["tokyo_low"] = c2.number_input("Tokyo L", value=6045.0, step=0.5)
            manual["london_high"] = c1.number_input("London H", value=6078.0, step=0.5)
            manual["london_low"] = c2.number_input("London L", value=6040.0, step=0.5)
            manual["current_es"] = st.number_input("Current ES", value=6065.0, step=0.5)
        
        st.divider()
        ref_time = st.selectbox("⏰ Reference Time", ["9:00 AM", "9:30 AM", "10:00 AM"])
        
        c1, c2 = st.columns(2)
        if c1.button("💾 Save", use_container_width=True):
            save_inputs({"offset": offset})
            st.success("Saved!")
        if c2.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    
    ref_map = {"9:00 AM": (9, 0), "9:30 AM": (9, 30), "10:00 AM": (10, 0)}
    return {
        "trading_date": trading_date, "offset": offset, "override": override,
        "manual": manual, "ref_time": ref_map[ref_time]
    }

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    inputs = sidebar()
    now = now_ct()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DATA LOADING
    # ═══════════════════════════════════════════════════════════════════════════
    with st.spinner("Loading market data..."):
        if inputs["override"]:
            m = inputs["manual"]
            current_es = m["current_es"]
            sydney = {"high": m["sydney_high"], "low": m["sydney_low"],
                      "high_time": CT.localize(datetime.combine(inputs["trading_date"] - timedelta(days=1), time(18, 0))),
                      "low_time": CT.localize(datetime.combine(inputs["trading_date"] - timedelta(days=1), time(19, 0)))}
            tokyo = {"high": m["tokyo_high"], "low": m["tokyo_low"],
                     "high_time": CT.localize(datetime.combine(inputs["trading_date"] - timedelta(days=1), time(23, 0))),
                     "low_time": CT.localize(datetime.combine(inputs["trading_date"], time(0, 30)))}
            london = {"high": m["london_high"], "low": m["london_low"],
                      "high_time": CT.localize(datetime.combine(inputs["trading_date"], time(3, 0))),
                      "low_time": CT.localize(datetime.combine(inputs["trading_date"], time(4, 0)))}
            overnight = {
                "high": max(m["sydney_high"], m["tokyo_high"], m["london_high"]),
                "low": min(m["sydney_low"], m["tokyo_low"], m["london_low"])
            }
            sessions = {}
            es_candles = None
        else:
            es_candles = fetch_es_candles()
            current_es = fetch_es_current() or 6050
            sessions = extract_sessions(es_candles, inputs["trading_date"]) or {}
            sydney = sessions.get("sydney")
            tokyo = sessions.get("tokyo")
            london = sessions.get("london")
            overnight = sessions.get("overnight")
        
        vix = fetch_vix()
        mm_data = fetch_mm_bias()
    
    offset = inputs["offset"]
    current_spx = round(current_es - offset, 2)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CHANNEL CALCULATION
    # ═══════════════════════════════════════════════════════════════════════════
    channel_type, channel_reason, upper_pivot, lower_pivot, upper_time, lower_time = \
        determine_channel(sydney, tokyo, london)
    
    ref_time = CT.localize(datetime.combine(inputs["trading_date"], time(*inputs["ref_time"])))
    ceiling_es, floor_es = calc_channel_levels(upper_pivot, lower_pivot, upper_time, lower_time, ref_time, channel_type)
    
    if ceiling_es is None:
        ceiling_es, floor_es = 6080, 6040
    
    ceiling_spx = round(ceiling_es - offset, 2)
    floor_spx = round(floor_es - offset, 2)
    position = get_position(current_es, ceiling_es, floor_es)
    mm_bias = mm_data["bias"]
    
    # Prior RTH Cone Targets
    prior_high = sessions.get("prior_high") if sessions else None
    prior_low = sessions.get("prior_low") if sessions else None
    prior_high_time = sessions.get("prior_high_time") if sessions else None
    prior_low_time = sessions.get("prior_low_time") if sessions else None
    
    if prior_high:
        upper_cone_es, lower_cone_es, _, _ = calc_prior_rth_cone(
            prior_high, prior_low, prior_high_time, prior_low_time, ref_time, channel_type
        )
        upper_cone_spx = round(upper_cone_es - offset, 2) if upper_cone_es else None
        lower_cone_spx = round(lower_cone_es - offset, 2) if lower_cone_es else None
    else:
        upper_cone_spx = lower_cone_spx = None
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DECISION ENGINE
    # ═══════════════════════════════════════════════════════════════════════════
    decision = analyze_market_state(
        current_spx, ceiling_spx, floor_spx, channel_type, mm_bias,
        upper_cone_spx, lower_cone_spx, vix
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - HEADER
    # ═══════════════════════════════════════════════════════════════════════════
    st.title("🔮 SPX Prophet V7")
    st.caption("Overnight Structure → Channel → Trade Decision")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - TRADE DECISION (Most Important - Top of Page)
    # ═══════════════════════════════════════════════════════════════════════════
    if decision["no_trade"]:
        st.error(f"### 🚫 NO TRADE")
        st.warning(decision["no_trade_reason"])
    else:
        st.info(f"📊 **{decision['context']}**")
        
        # PRIMARY
        p = decision["primary"]
        if p:
            icon = "🟢" if p["direction"] == "CALLS" else "🔴"
            st.markdown(f"### {icon} PRIMARY: {p['name']}")
            
            with st.container(border=True):
                st.markdown(f"#### 📋 `{p['contract']}`")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Entry Premium", f"${p['entry_premium']:.2f}", "@ 9:00 AM")
                c2.metric("Target Premium", f"${p['target_premium']:.2f}")
                c3.metric("Profit/Contract", f"${p['dollar_profit']:.0f}")
                c4.metric("R:R", f"{p['rr_ratio']}:1")
                
                st.divider()
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("SPX Entry", f"{p['entry']}")
                c2.metric("SPX Stop", f"{p['stop']}")
                c3.metric("SPX Target", f"{p['target']}")
                c4.metric("Potential", f"+{p['potential_pts']} pts")
                
                st.markdown(f"**🎯 Trigger:** {p['trigger']}")
                st.caption(f"💡 {p['rationale']} | Confidence: **{p['confidence']}**")
        
        # ALTERNATE (collapsed)
        a = decision["alternate"]
        if a:
            icon = "🟢" if a["direction"] == "CALLS" else "🔴"
            with st.expander(f"↩️ ALTERNATE: {a['name']} — `{a['contract']}` @ ${a['entry_premium']:.2f}"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Entry", f"${a['entry_premium']:.2f}")
                c2.metric("Target", f"${a['target_premium']:.2f}")
                c3.metric("Profit", f"${a['dollar_profit']:.0f}")
                c4.metric("R:R", f"{a['rr_ratio']}:1")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("SPX Entry", f"{a['entry']}")
                c2.metric("Stop", f"{a['stop']}")
                c3.metric("Target", f"{a['target']}")
                c4.metric("Move", f"+{a['potential_pts']} pts")
                
                st.markdown(f"**🎯 Trigger:** {a['trigger']}")
                st.caption(f"💡 {a['rationale']}")
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - CHANNEL & MARKET DATA
    # ═══════════════════════════════════════════════════════════════════════════
    colors = {
        ChannelType.ASCENDING: "🟢",
        ChannelType.DESCENDING: "🔴", 
        ChannelType.EXPANDING: "🟣",
        ChannelType.CONTRACTING: "🟡"
    }
    icon = colors.get(channel_type, "⚪")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    col1.metric(f"{icon} Channel", channel_type.value, channel_reason)
    col2.metric("SPX", f"{current_spx:,.2f}", f"ES {current_es:,.2f}")
    col3.metric("Position", position.value)
    
    st.divider()
    
    # Sessions
    st.subheader("🌏 Sessions (Sydney → Tokyo → London)")
    c1, c2, c3, c4 = st.columns(4)
    
    def show_session(col, name, emoji, data, is_upper=False, is_lower=False):
        with col:
            st.markdown(f"**{emoji} {name}**")
            if data:
                h_mark = " ⬆️" if is_upper else ""
                l_mark = " ⬇️" if is_lower else ""
                st.write(f"High: **{data['high']}**{h_mark}")
                st.write(f"Low: **{data['low']}**{l_mark}")
            else:
                st.write("No data")
    
    # Determine which session has pivots
    syd_upper = sydney and upper_pivot == sydney.get("high") if upper_pivot and sydney else False
    syd_lower = sydney and lower_pivot == sydney.get("low") if lower_pivot and sydney else False
    tok_upper = tokyo and upper_pivot == tokyo.get("high") if upper_pivot and tokyo else False
    tok_lower = tokyo and lower_pivot == tokyo.get("low") if lower_pivot and tokyo else False
    lon_upper = london and upper_pivot == london.get("high") if upper_pivot and london else False
    lon_lower = london and lower_pivot == london.get("low") if lower_pivot and london else False
    
    show_session(c1, "Sydney", "🦘", sydney, syd_upper, syd_lower)
    show_session(c2, "Tokyo", "🗼", tokyo, tok_upper, tok_lower)
    show_session(c3, "London", "🏛️", london, lon_upper, lon_lower)
    show_session(c4, "Overnight", "🌙", overnight)
    
    st.divider()
    
    # Channel Levels
    st.subheader(f"📊 Channel Levels @ {inputs['ref_time'][0]}:{inputs['ref_time'][1]:02d} AM")
    c1, c2 = st.columns(2)
    c1.metric("🟢 Ceiling", f"{ceiling_spx}", f"ES {ceiling_es}")
    c2.metric("🔴 Floor", f"{floor_spx}", f"ES {floor_es}")
    
    st.divider()
    
    # MM Bias
    st.subheader("🏦 Market Maker Bias")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VIX", f"{mm_data.get('vix', 'N/A')}")
    c2.metric("VIX3M", f"{mm_data.get('vix3m', 'N/A')}")
    c3.metric("Spread", f"{mm_data.get('spread', 'N/A'):+.2f}" if mm_data.get('spread') else "N/A")
    c4.metric("Structure", mm_data.get("vix_structure", "N/A"))
    
    interp = mm_data.get("interpretation", "")
    if interp:
        if mm_bias == MMBias.CALLS_HEAVY:
            st.error(f"📉 {interp}")
        elif mm_bias == MMBias.PUTS_HEAVY:
            st.success(f"📈 {interp}")
        else:
            st.info(f"⚖️ {interp}")

if __name__ == "__main__":
    main()
