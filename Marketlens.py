# ═══════════════════════════════════════════════════════════════════════════════
# SPX PROPHET V7.0 - STRUCTURAL 0DTE TRADING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import pytz
import json
import os
import math
import time as time_module
from datetime import datetime, date, time, timedelta
from enum import Enum

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="SPX Prophet V7", page_icon="🔮", layout="wide")

CT = pytz.timezone("America/Chicago")
ET = pytz.timezone("America/New_York")
SLOPE = 0.48
SAVE_FILE = "spx_prophet_v7_inputs.json"

# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════
class ChannelType(Enum):
    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"
    EXPANDING = "EXPANDING"
    CONTRACTING = "CONTRACTING"
    UNDETERMINED = "UNDETERMINED"

class Position(Enum):
    ABOVE = "ABOVE"
    INSIDE = "INSIDE"
    BELOW = "BELOW"

class MMBias(Enum):
    CALLS_HEAVY = "CALLS_HEAVY"
    PUTS_HEAVY = "PUTS_HEAVY"
    NEUTRAL = "NEUTRAL"

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════
def now_ct():
    return datetime.now(CT)

def blocks_between(start, end):
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
# BLACK-SCHOLES WITH 0DTE IV ADJUSTMENT
# ═══════════════════════════════════════════════════════════════════════════════
def norm_cdf(x):
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p, sign = 0.3275911, 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)

def black_scholes(S, K, T, r, sigma, opt_type):
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
    
    Based on real market observation:
    - Barchart SPX IV: 32.73% when VIX: ~20 = ratio of ~1.6x
    - 0DTE tends to run slightly higher due to gamma risk
    - Morning (more time) = slightly lower IV than afternoon
    - OTM strikes have higher IV (smile effect)
    
    Calibrated to real market data (Jan 2026):
    - Base multiplier: 1.6-1.8x VIX
    - Smile adjustment: +0.5% per 10 pts OTM
    """
    # Base IV from VIX - calibrated to real market
    # Morning (6hrs): 1.6x, Midday (4hrs): 1.7x, Afternoon (2hrs): 1.8x
    if hours_to_expiry > 5:
        base_mult = 1.6
    elif hours_to_expiry > 3:
        base_mult = 1.7
    else:
        base_mult = 1.8
    
    base_iv = (vix / 100) * base_mult
    
    # IV Smile adjustment - OTM strikes have higher IV
    # Approximately +0.5% (0.005) per 10 points OTM
    distance_otm = abs(spot - strike)
    smile_add = (distance_otm / 10) * 0.005
    
    # Total IV (floor at 15% minimum for 0DTE)
    total_iv = max(base_iv + smile_add, 0.15)
    
    return total_iv

def get_strike(entry_level, direction):
    if direction == "CALLS":
        return int(round((entry_level + 15) / 5) * 5)
    return int(round((entry_level - 15) / 5) * 5)

def estimate_premium(entry_spx, direction, vix, hours_to_expiry):
    strike = get_strike(entry_spx, direction)
    opt_type = "CALL" if direction == "CALLS" else "PUT"
    iv = calc_0dte_iv(vix, entry_spx, strike, hours_to_expiry)
    T = max(0.0001, hours_to_expiry / (365 * 24))
    premium = black_scholes(entry_spx, strike, T, 0.05, iv, opt_type)
    return max(round(premium, 2), 0.10), strike

def estimate_0dte_premium(spot, strike, hours_to_expiry, vix, opt_type):
    """
    Standalone function for 0DTE premium estimation.
    Used by Decision Engine for contract pricing.
    """
    iv = calc_0dte_iv(vix, spot, strike, hours_to_expiry)
    T = max(0.0001, hours_to_expiry / (365 * 24))
    premium = black_scholes(spot, strike, T, 0.05, iv, opt_type)
    return max(round(premium, 2), 0.05)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def fetch_es_current():
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
    try:
        vix = yf.Ticker("^VIX")
        data = vix.history(period="2d")
        if data is not None and not data.empty:
            return round(float(data['Close'].iloc[-1]), 2)
    except:
        pass
    return 16.0

@st.cache_data(ttl=300, show_spinner=False)
def fetch_mm_bias():
    """
    MM Bias Analysis using VIX Term Structure
    
    VIX vs VIX3M spread indicates market positioning:
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
            spread_pct = (spread / vix3m) * 100 if vix3m > 0 else 0
            
            results["vix"] = vix
            results["vix3m"] = vix3m
            results["spread"] = spread
            
            # Scoring based on spread magnitude
            # Deep contango = strong calls heavy
            # Deep backwardation = strong puts heavy
            if spread <= -3:
                results["vix_structure"] = "DEEP CONTANGO"
                results["score"] = -100
                results["bias"] = MMBias.CALLS_HEAVY
                results["interpretation"] = f"Deep Contango ({spread:+.1f}): Extreme complacency. Retail heavily long calls. MMs will push price DOWN to floor."
            elif spread <= -1.5:
                results["vix_structure"] = "CONTANGO"
                results["score"] = -50
                results["bias"] = MMBias.CALLS_HEAVY
                results["interpretation"] = f"Contango ({spread:+.1f}): Complacency. Calls heavy positioning. MMs likely push price DOWN."
            elif spread < 0:
                results["vix_structure"] = "MILD CONTANGO"
                results["score"] = -25
                results["bias"] = MMBias.NEUTRAL
                results["interpretation"] = f"Mild Contango ({spread:+.1f}): Slight call bias but not extreme. Watch for direction."
            elif spread <= 1.5:
                results["vix_structure"] = "FLAT"
                results["score"] = 0
                results["bias"] = MMBias.NEUTRAL
                results["interpretation"] = f"Flat ({spread:+.1f}): Balanced positioning. No strong MM directional bias."
            elif spread <= 3:
                results["vix_structure"] = "MILD BACKWARDATION"
                results["score"] = 25
                results["bias"] = MMBias.NEUTRAL
                results["interpretation"] = f"Mild Backwardation ({spread:+.1f}): Slight put bias. Watch for upside."
            elif spread <= 5:
                results["vix_structure"] = "BACKWARDATION"
                results["score"] = 50
                results["bias"] = MMBias.PUTS_HEAVY
                results["interpretation"] = f"Backwardation ({spread:+.1f}): Fear rising. Puts heavy. MMs likely push price UP."
            else:
                results["vix_structure"] = "DEEP BACKWARDATION"
                results["score"] = 100
                results["bias"] = MMBias.PUTS_HEAVY
                results["interpretation"] = f"Deep Backwardation ({spread:+.1f}): Extreme fear. Retail heavily long puts. MMs will push price UP to ceiling."
    except Exception as e:
        results["interpretation"] = f"VIX data unavailable: {str(e)}"
    
    return results

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════
def extract_sessions(es_candles, trading_date):
    if es_candles is None or es_candles.empty:
        return None
    
    result = {}
    overnight_day = trading_date - timedelta(days=1)
    if overnight_day.weekday() >= 5:
        overnight_day -= timedelta(days=(overnight_day.weekday() - 4))
    
    df = es_candles.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize(ET).tz_convert(CT)
    else:
        df.index = df.index.tz_convert(CT)
    
    # Session times (CT)
    sessions = {
        "sydney": (CT.localize(datetime.combine(overnight_day, time(17, 0))),
                   CT.localize(datetime.combine(overnight_day, time(20, 30)))),
        "tokyo": (CT.localize(datetime.combine(overnight_day, time(21, 0))),
                  CT.localize(datetime.combine(trading_date, time(1, 30)))),
        "london": (CT.localize(datetime.combine(trading_date, time(2, 0))),
                   CT.localize(datetime.combine(trading_date, time(4, 0)))),
        "overnight": (CT.localize(datetime.combine(overnight_day, time(17, 0))),
                      CT.localize(datetime.combine(trading_date, time(8, 30))))
    }
    
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
    
    # Prior RTH
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
# CHANNEL LOGIC
# ═══════════════════════════════════════════════════════════════════════════════
def determine_channel(sydney, tokyo):
    """
    ASCENDING:   Tokyo High > Sydney High
    DESCENDING:  Tokyo Low < Sydney Low
    EXPANDING:   Both
    CONTRACTING: Neither
    """
    if not sydney or not tokyo:
        return ChannelType.UNDETERMINED, "Missing data"
    
    higher_high = tokyo["high"] > sydney["high"]
    lower_low = tokyo["low"] < sydney["low"]
    
    if higher_high and lower_low:
        return ChannelType.EXPANDING, f"Tokyo expanded both (H:{tokyo['high']}>{sydney['high']}, L:{tokyo['low']}<{sydney['low']})"
    elif not higher_high and not lower_low:
        return ChannelType.CONTRACTING, f"Tokyo contracted (H:{tokyo['high']}≤{sydney['high']}, L:{tokyo['low']}≥{sydney['low']})"
    elif higher_high:
        return ChannelType.ASCENDING, f"Tokyo High ({tokyo['high']}) > Sydney High ({sydney['high']})"
    else:
        return ChannelType.DESCENDING, f"Tokyo Low ({tokyo['low']}) < Sydney Low ({sydney['low']})"

def calc_channel_levels(overnight, ref_time, channel_type):
    """Calculate ceiling/floor with 0.48 slope"""
    if not overnight:
        return None, None
    
    on_high, on_low = overnight["high"], overnight["low"]
    blocks_high = blocks_between(overnight.get("high_time"), ref_time)
    blocks_low = blocks_between(overnight.get("low_time"), ref_time)
    
    if channel_type == ChannelType.ASCENDING:
        ceiling = round(on_high + SLOPE * blocks_high, 2)
        floor = round(on_low + SLOPE * blocks_low, 2)
    elif channel_type == ChannelType.DESCENDING:
        ceiling = round(on_high - SLOPE * blocks_high, 2)
        floor = round(on_low - SLOPE * blocks_low, 2)
    else:
        ceiling, floor = on_high, on_low
    
    return ceiling, floor


def calc_prior_rth_cone(prior_high, prior_low, prior_high_time, prior_low_time, ref_time, channel_type):
    """
    Calculate cone projections from prior RTH session.
    
    The cone projects where price "should" be based on:
    - Prior RTH High/Low as anchor points
    - 0.48 slope per 30-min block
    - Channel direction (ascending/descending)
    
    Returns: (upper_cone, lower_cone, blocks_from_high, blocks_from_low)
    """
    if prior_high is None or prior_low is None:
        return None, None, 0, 0
    
    blocks_from_high = blocks_between(prior_high_time, ref_time)
    blocks_from_low = blocks_between(prior_low_time, ref_time)
    
    if channel_type == ChannelType.ASCENDING:
        # Both lines rise
        upper_cone = round(prior_high + SLOPE * blocks_from_high, 2)
        lower_cone = round(prior_low + SLOPE * blocks_from_low, 2)
    elif channel_type == ChannelType.DESCENDING:
        # Both lines fall
        upper_cone = round(prior_high - SLOPE * blocks_from_high, 2)
        lower_cone = round(prior_low - SLOPE * blocks_from_low, 2)
    else:
        # Expanding/Contracting - use static levels
        upper_cone = prior_high
        lower_cone = prior_low
    
    return upper_cone, lower_cone, blocks_from_high, blocks_from_low


def get_position(price, ceiling, floor):
    if price > ceiling:
        return Position.ABOVE
    elif price < floor:
        return Position.BELOW
    return Position.INSIDE

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO GENERATION
# ═══════════════════════════════════════════════════════════════════════════════
def generate_scenarios(channel_type, position, ceiling_es, floor_es, mm_bias, offset, vix, hours_to_expiry, upper_cone_spx=None, lower_cone_spx=None):
    scenarios = []
    ceiling_spx = round(ceiling_es - offset, 2)
    floor_spx = round(floor_es - offset, 2)
    
    # Use cone targets if available, otherwise use fixed offset
    calls_target = upper_cone_spx if upper_cone_spx else ceiling_spx + 25
    puts_target = lower_cone_spx if lower_cone_spx else floor_spx - 25
    
    def add(condition, action, entry_spx, direction, target_spx, trigger, notes, confidence="HIGH"):
        premium, strike = estimate_premium(entry_spx, direction, vix, hours_to_expiry) if direction != "NO_TRADE" else (0, 0)
        scenarios.append({
            "condition": condition, "action": action,
            "entry_spx": entry_spx, "direction": direction,
            "target_spx": target_spx, "trigger": trigger,
            "notes": notes, "confidence": confidence,
            "premium": premium, "strike": strike
        })
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ASCENDING CHANNEL
    # ═══════════════════════════════════════════════════════════════════════════
    if channel_type == ChannelType.ASCENDING:
        if position == Position.ABOVE:
            # Normal: Drop to ceiling for support
            add("ABOVE (Normal)", "Drop to ceiling for support", ceiling_spx, "CALLS", calls_target,
                "Price drops to ceiling and holds (closes above)", f"Ceiling is support in ascending → Target: Upper Cone ({calls_target})")
            
            # If CALLS > PUTS: MMs don't want to pay calls, push price DOWN
            if mm_bias == MMBias.CALLS_HEAVY:
                add("ABOVE + CALLS HEAVY", "Ceiling becomes resistance, rally back to ceiling", ceiling_spx, "PUTS", floor_spx,
                    "Price breaks through ceiling, rallies back to ceiling, rejection", "MMs avoid paying calls → Push to floor", "HIGH")
                add("ABOVE + CALLS HEAVY (Alt)", "Drop all the way to floor", floor_spx, "CALLS", ceiling_spx,
                    "If price reaches floor, enter CALLS", "Bounce from floor back to ceiling", "MEDIUM")
        
        elif position == Position.INSIDE:
            add("INSIDE → Breaks UP", "Retrace to ceiling", ceiling_spx, "CALLS", calls_target,
                "30-min close above ceiling, then retrace to ceiling", f"Ceiling becomes support → Target: Upper Cone ({calls_target})")
            add("INSIDE → Breaks DOWN", "Rally back to floor", floor_spx, "PUTS", puts_target,
                "30-min close below floor, then rally back to floor", f"Floor becomes resistance → Target: Lower Cone ({puts_target})")
            add("INSIDE → Touches floor, closes inside", "Floor rejection", floor_spx, "CALLS", ceiling_spx,
                "Candle touches floor but closes above it", "Floor holding = bullish in ascending")
        
        elif position == Position.BELOW:
            add("BELOW (Normal)", "Rally to floor, close below", floor_spx, "PUTS", puts_target,
                "Price rallies to floor, touches it, closes below", f"Floor is resistance when below → Target: Lower Cone ({puts_target})")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DESCENDING CHANNEL
    # ═══════════════════════════════════════════════════════════════════════════
    elif channel_type == ChannelType.DESCENDING:
        if position == Position.BELOW:
            # Normal: Rally to floor for resistance
            add("BELOW (Normal)", "Rally to floor for resistance", floor_spx, "PUTS", puts_target,
                "Price rallies to floor and fails (closes below)", f"Floor is resistance in descending → Target: Lower Cone ({puts_target})")
            
            # If PUTS > CALLS: MMs don't want to pay puts, push price UP
            if mm_bias == MMBias.PUTS_HEAVY:
                add("BELOW + PUTS HEAVY", "Floor becomes support, drop back to floor", floor_spx, "CALLS", ceiling_spx,
                    "Price breaks through floor, drops back to floor, holds", "MMs avoid paying puts → Push to ceiling", "HIGH")
                add("BELOW + PUTS HEAVY (Alt)", "Rally all the way to ceiling", ceiling_spx, "PUTS", floor_spx,
                    "If price reaches ceiling, enter PUTS", "Fade rally from ceiling", "MEDIUM")
        
        elif position == Position.INSIDE:
            add("INSIDE → Breaks DOWN", "Retrace to floor", floor_spx, "PUTS", puts_target,
                "30-min close below floor, then retrace to floor", f"Floor becomes resistance → Target: Lower Cone ({puts_target})")
            add("INSIDE → Breaks UP", "Drop back to ceiling", ceiling_spx, "CALLS", calls_target,
                "30-min close above ceiling, then drop back to ceiling", f"Ceiling becomes support → Target: Upper Cone ({calls_target})")
            add("INSIDE → Touches ceiling, closes inside", "Ceiling rejection", ceiling_spx, "PUTS", floor_spx,
                "Candle touches ceiling but closes below it", "Ceiling holding = bearish in descending")
        
        elif position == Position.ABOVE:
            add("ABOVE (Normal)", "Drop to ceiling, close above", ceiling_spx, "CALLS", calls_target,
                "Price drops to ceiling, touches it, closes above", f"Ceiling is support when above → Target: Upper Cone ({calls_target})")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EXPANDING - Trade Boundaries (fade extremes)
    # ═══════════════════════════════════════════════════════════════════════════
    elif channel_type == ChannelType.EXPANDING:
        add("EXPANDING → At Ceiling", "Fade the extreme", ceiling_spx, "PUTS", floor_spx,
            "Price reaches ceiling → PUTS to floor", "Expanding channel = fade extremes", "MEDIUM")
        add("EXPANDING → At Floor", "Fade the extreme", floor_spx, "CALLS", ceiling_spx,
            "Price reaches floor → CALLS to ceiling", "Expanding channel = fade extremes", "MEDIUM")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONTRACTING - NO TRADE
    # ═══════════════════════════════════════════════════════════════════════════
    elif channel_type == ChannelType.CONTRACTING:
        add("CONTRACTING", "NO TRADE - Wait for expansion", 0, "NO_TRADE", 0,
            "Do not trade contracting channels", "Tokyo inside Sydney = no directional bias", "N/A")
    
    return scenarios


# ═══════════════════════════════════════════════════════════════════════════════
# DECISION ENGINE - The Brain
# ═══════════════════════════════════════════════════════════════════════════════
def analyze_market_state(current_spx, ceiling_spx, floor_spx, channel_type, mm_bias, 
                         upper_cone_spx, lower_cone_spx, vix, hours_to_expiry):
    """
    Analyzes current market state and returns PRIMARY and ALTERNATE scenarios.
    
    Returns dict with:
    - primary: Most likely trade setup
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
        dist_to_ceil = round(ceiling_spx - current_spx, 1)
        dist_to_floor = round(current_spx - floor_spx, 1)
        pos_desc = f"INSIDE channel (↑{dist_to_ceil} to ceiling, ↓{dist_to_floor} to floor)"
    
    # Use cone targets or defaults
    calls_target = upper_cone_spx if upper_cone_spx else ceiling_spx + 25
    puts_target = lower_cone_spx if lower_cone_spx else floor_spx - 25
    
    # Build context
    result["context"] = f"{channel_type.value} | {pos_desc} | MM Bias: {mm_bias.value}"
    
    def make_scenario(name, direction, entry, stop, target, trigger, rationale, confidence):
        if direction == "CALLS":
            potential = round(target - entry, 1)
            # OTM strike ~20 points above entry for calls
            strike = int(math.ceil((entry + 20) / 5) * 5)
            opt_type = "CALL"
        else:
            potential = round(entry - target, 1)
            # OTM strike ~20 points below entry for puts
            strike = int(math.floor((entry - 20) / 5) * 5)
            opt_type = "PUT"
        
        # Calculate premium at entry (9:00-9:10 AM = ~6 hours to expiry)
        entry_premium = estimate_0dte_premium(entry, strike, 6.0, vix, opt_type)
        
        # Calculate premium at target (~2 hours later, 4 hours left)
        target_premium = estimate_0dte_premium(target, strike, 4.0, vix, opt_type)
        
        # Dollar profit per contract (x100 multiplier)
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
            # Contract details
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
        result["no_trade_reason"] = "CONTRACTING channel - Tokyo inside Sydney. No directional bias. Wait for expansion."
        return result
    
    if channel_type == ChannelType.UNDETERMINED:
        result["no_trade"] = True
        result["no_trade_reason"] = "Cannot determine channel type. Check data inputs."
        return result
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ASCENDING CHANNEL SCENARIOS
    # ═══════════════════════════════════════════════════════════════════════════
    if channel_type == ChannelType.ASCENDING:
        
        if position == Position.ABOVE:
            if mm_bias == MMBias.CALLS_HEAVY:
                # MMs will push DOWN
                result["primary"] = make_scenario(
                    "MM Reversal Play",
                    "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                    "Wait for price to rally back to ceiling → Enter PUTS on rejection (30-min close below ceiling)",
                    "CALLS HEAVY: MMs avoid paying calls → Will push price DOWN to floor",
                    "HIGH"
                )
                result["alternate"] = make_scenario(
                    "Continuation if Floor Reached",
                    "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                    "If price drops all the way to floor → Enter CALLS on support (30-min close above floor)",
                    "Floor bounce back to ceiling",
                    "MEDIUM"
                )
            else:
                # Normal - ceiling is support
                result["primary"] = make_scenario(
                    "Ceiling Support",
                    "CALLS", ceiling_spx, ceiling_spx - 5, calls_target,
                    "Wait for price to drop to ceiling → Enter CALLS on support (30-min close above ceiling)",
                    "ASCENDING + ABOVE: Ceiling acts as support in uptrend",
                    "HIGH"
                )
                result["alternate"] = make_scenario(
                    "Breakdown if Ceiling Fails",
                    "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                    "If ceiling breaks → Wait for rally back to ceiling → Enter PUTS on rejection",
                    "Failed support becomes resistance",
                    "MEDIUM"
                )
        
        elif position == Position.INSIDE:
            # Inside channel - primary is floor bounce, alternate is breakout
            result["primary"] = make_scenario(
                "Floor Rejection",
                "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                "Wait for price to touch floor → Enter CALLS if candle closes ABOVE floor",
                "ASCENDING + INSIDE: Floor rejection is bullish",
                "HIGH"
            )
            result["alternate"] = make_scenario(
                "Ceiling Breakout",
                "CALLS", ceiling_spx, ceiling_spx - 5, calls_target,
                "If price breaks above ceiling → Wait for retrace to ceiling → Enter CALLS",
                "Ceiling becomes support after breakout → Target: Upper Cone",
                "MEDIUM"
            )
        
        elif position == Position.BELOW:
            # Below ascending channel - bearish
            result["primary"] = make_scenario(
                "Floor Resistance",
                "PUTS", floor_spx, floor_spx + 5, puts_target,
                "Wait for price to rally to floor → Enter PUTS on rejection (30-min close below floor)",
                "ASCENDING + BELOW: Floor is resistance, market showing weakness",
                "HIGH"
            )
            result["alternate"] = make_scenario(
                "Reclaim Floor",
                "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                "If price reclaims floor (30-min close above) → Enter CALLS",
                "Back inside channel = bullish",
                "MEDIUM"
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DESCENDING CHANNEL SCENARIOS
    # ═══════════════════════════════════════════════════════════════════════════
    elif channel_type == ChannelType.DESCENDING:
        
        if position == Position.BELOW:
            if mm_bias == MMBias.PUTS_HEAVY:
                # MMs will push UP
                result["primary"] = make_scenario(
                    "MM Reversal Play",
                    "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                    "Wait for price to drop back to floor → Enter CALLS on support (30-min close above floor)",
                    "PUTS HEAVY: MMs avoid paying puts → Will push price UP to ceiling",
                    "HIGH"
                )
                result["alternate"] = make_scenario(
                    "Continuation if Ceiling Reached",
                    "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                    "If price rallies all the way to ceiling → Enter PUTS on resistance",
                    "Fade the rally from ceiling",
                    "MEDIUM"
                )
            else:
                # Normal - floor is resistance
                result["primary"] = make_scenario(
                    "Floor Resistance",
                    "PUTS", floor_spx, floor_spx + 5, puts_target,
                    "Wait for price to rally to floor → Enter PUTS on rejection (30-min close below floor)",
                    "DESCENDING + BELOW: Floor acts as resistance in downtrend",
                    "HIGH"
                )
                result["alternate"] = make_scenario(
                    "Breakup if Floor Reclaimed",
                    "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                    "If floor reclaimed → Enter CALLS on support",
                    "Failed resistance becomes support",
                    "MEDIUM"
                )
        
        elif position == Position.INSIDE:
            # Inside channel - primary is ceiling rejection, alternate is breakdown
            result["primary"] = make_scenario(
                "Ceiling Rejection",
                "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                "Wait for price to touch ceiling → Enter PUTS if candle closes BELOW ceiling",
                "DESCENDING + INSIDE: Ceiling rejection is bearish",
                "HIGH"
            )
            result["alternate"] = make_scenario(
                "Floor Breakdown",
                "PUTS", floor_spx, floor_spx + 5, puts_target,
                "If price breaks below floor → Wait for retrace to floor → Enter PUTS",
                "Floor becomes resistance after breakdown → Target: Lower Cone",
                "MEDIUM"
            )
        
        elif position == Position.ABOVE:
            # Above descending channel - bullish
            result["primary"] = make_scenario(
                "Ceiling Support",
                "CALLS", ceiling_spx, ceiling_spx - 5, calls_target,
                "Wait for price to drop to ceiling → Enter CALLS on support (30-min close above ceiling)",
                "DESCENDING + ABOVE: Ceiling is support, market showing strength",
                "HIGH"
            )
            result["alternate"] = make_scenario(
                "Lose Ceiling",
                "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                "If ceiling breaks (30-min close below) → Enter PUTS",
                "Back inside channel = bearish",
                "MEDIUM"
            )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EXPANDING CHANNEL - Fade Extremes
    # ═══════════════════════════════════════════════════════════════════════════
    elif channel_type == ChannelType.EXPANDING:
        result["primary"] = make_scenario(
            "Fade Ceiling",
            "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
            "If price reaches ceiling → Enter PUTS to fade the extreme",
            "EXPANDING: Volatile, fade extremes",
            "MEDIUM"
        )
        result["alternate"] = make_scenario(
            "Fade Floor",
            "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
            "If price reaches floor → Enter CALLS to fade the extreme",
            "EXPANDING: Volatile, fade extremes",
            "MEDIUM"
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
        offset = st.number_input("⚙️ ES→SPX Offset", value=float(saved.get("offset", 18.0)), step=0.5)
        
        st.divider()
        override = st.checkbox("📝 Manual Session Override")
        manual = {}
        if override:
            c1, c2 = st.columns(2)
            manual["sydney_high"] = c1.number_input("Sydney High", value=6075.0, step=0.5)
            manual["sydney_low"] = c2.number_input("Sydney Low", value=6050.0, step=0.5)
            manual["tokyo_high"] = c1.number_input("Tokyo High", value=6080.0, step=0.5)
            manual["tokyo_low"] = c2.number_input("Tokyo Low", value=6045.0, step=0.5)
            manual["current_es"] = st.number_input("Current ES", value=6065.0, step=0.5)
        
        st.divider()
        ref_time = st.selectbox("⏰ Reference Time", ["9:00 AM", "9:30 AM", "10:00 AM"])
        debug = st.checkbox("🔧 Debug Mode")
        
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
        "manual": manual, "ref_time": ref_map[ref_time], "debug": debug
    }

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    inputs = sidebar()
    now = now_ct()
    
    # Fetch data
    with st.spinner("Loading..."):
        es_candles = fetch_es_candles(7)
        if inputs["override"] and inputs["manual"].get("current_es"):
            current_es = inputs["manual"]["current_es"]
        else:
            current_es = fetch_es_current() or 6050
        vix = fetch_vix()
        
        # MM Bias - combined VIX Term Structure + P/C Ratio
        mm_data = fetch_mm_bias()
    
    offset = inputs["offset"]
    current_spx = round(current_es - offset, 2)
    
    # Sessions
    if inputs["override"]:
        m = inputs["manual"]
        sydney = {"high": m["sydney_high"], "low": m["sydney_low"]}
        tokyo = {"high": m["tokyo_high"], "low": m["tokyo_low"]}
        overnight = {
            "high": max(m["sydney_high"], m["tokyo_high"]),
            "low": min(m["sydney_low"], m["tokyo_low"]),
            "high_time": CT.localize(datetime.combine(inputs["trading_date"] - timedelta(days=1), time(22, 0))),
            "low_time": CT.localize(datetime.combine(inputs["trading_date"], time(2, 0)))
        }
    else:
        sessions = extract_sessions(es_candles, inputs["trading_date"]) or {}
        sydney = sessions.get("sydney")
        tokyo = sessions.get("tokyo")
        overnight = sessions.get("overnight")
    
    # Channel
    channel_type, channel_reason = determine_channel(sydney, tokyo)
    ref_time = CT.localize(datetime.combine(inputs["trading_date"], time(*inputs["ref_time"])))
    ceiling_es, floor_es = calc_channel_levels(overnight, ref_time, channel_type)
    
    if ceiling_es is None:
        ceiling_es, floor_es = 6080, 6040
    
    ceiling_spx = round(ceiling_es - offset, 2)
    floor_spx = round(floor_es - offset, 2)
    position = get_position(current_es, ceiling_es, floor_es)
    mm_bias = mm_data["bias"]
    
    # Prior RTH Cone Projections
    if not inputs["override"]:
        sessions = sessions if 'sessions' in dir() else extract_sessions(es_candles, inputs["trading_date"]) or {}
        prior_high = sessions.get("prior_high")
        prior_low = sessions.get("prior_low")
        prior_high_time = sessions.get("prior_high_time")
        prior_low_time = sessions.get("prior_low_time")
        prior_close = sessions.get("prior_close")
        
        upper_cone_es, lower_cone_es, blocks_from_high, blocks_from_low = calc_prior_rth_cone(
            prior_high, prior_low, prior_high_time, prior_low_time, ref_time, channel_type
        )
        if upper_cone_es:
            upper_cone_spx = round(upper_cone_es - offset, 2)
            lower_cone_spx = round(lower_cone_es - offset, 2)
        else:
            upper_cone_spx = lower_cone_spx = None
            prior_high = prior_low = prior_close = None
            blocks_from_high = blocks_from_low = 0
    else:
        # Manual override - no prior RTH data
        prior_high = prior_low = prior_close = None
        upper_cone_spx = lower_cone_spx = None
        upper_cone_es = lower_cone_es = None
        blocks_from_high = blocks_from_low = 0
    
    hours_to_expiry = max(0.5, (CT.localize(datetime.combine(inputs["trading_date"], time(15, 0))) - now).total_seconds() / 3600)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DECISION ENGINE - Get trading decision
    # ═══════════════════════════════════════════════════════════════════════════
    decision = analyze_market_state(
        current_spx, ceiling_spx, floor_spx, channel_type, mm_bias,
        upper_cone_spx, lower_cone_spx, vix, hours_to_expiry
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI
    # ═══════════════════════════════════════════════════════════════════════════
    st.title("🔮 SPX Prophet V7")
    st.caption("Three Pillars. One Vision. Total Clarity.")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # TRADE DECISION - Top Priority Display
    # ═══════════════════════════════════════════════════════════════════════════
    
    if decision["no_trade"]:
        st.error(f"### 🚫 NO TRADE")
        st.warning(f"{decision['no_trade_reason']}")
    else:
        # Context bar
        st.info(f"📊 **{decision['context']}**")
        
        # PRIMARY SCENARIO
        primary = decision["primary"]
        if primary:
            dir_icon = "🟢" if primary["direction"] == "CALLS" else "🔴"
            
            st.markdown(f"### {dir_icon} PRIMARY: {primary['name']}")
            
            with st.container(border=True):
                # Contract info - most important
                st.markdown(f"#### 📋 Contract: `{primary['contract']}`")
                
                # Premium and profit row
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Entry Premium", f"${primary['entry_premium']:.2f}", "@ 9:00-9:10 AM")
                c2.metric("Target Premium", f"${primary['target_premium']:.2f}")
                c3.metric("Profit/Contract", f"${primary['dollar_profit']:.0f}")
                c4.metric("R:R", f"{primary['rr_ratio']}:1")
                
                st.divider()
                
                # SPX Levels
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("SPX Entry", f"{primary['entry']}")
                c2.metric("SPX Stop", f"{primary['stop']}")
                c3.metric("SPX Target", f"{primary['target']}")
                c4.metric("Move", f"+{primary['potential_pts']} pts")
                
                st.markdown(f"**🎯 Trigger:** {primary['trigger']}")
                st.caption(f"💡 {primary['rationale']} | Confidence: **{primary['confidence']}**")
        
        # ALTERNATE SCENARIO
        alternate = decision["alternate"]
        if alternate:
            dir_icon = "🟢" if alternate["direction"] == "CALLS" else "🔴"
            
            with st.expander(f"↩️ ALTERNATE: {alternate['name']} — `{alternate['contract']}` @ ${alternate['entry_premium']:.2f}"):
                # Contract info
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Entry Premium", f"${alternate['entry_premium']:.2f}")
                c2.metric("Target Premium", f"${alternate['target_premium']:.2f}")
                c3.metric("Profit/Contract", f"${alternate['dollar_profit']:.0f}")
                c4.metric("R:R", f"{alternate['rr_ratio']}:1")
                
                # SPX Levels
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("SPX Entry", f"{alternate['entry']}")
                c2.metric("SPX Stop", f"{alternate['stop']}")
                c3.metric("SPX Target", f"{alternate['target']}")
                c4.metric("Move", f"+{alternate['potential_pts']} pts")
                
                st.markdown(f"**🎯 Trigger:** {alternate['trigger']}")
                st.caption(f"💡 {alternate['rationale']} | Confidence: **{alternate['confidence']}**")
    
    st.divider()
    
    # Channel Banner
    colors = {
        ChannelType.ASCENDING: ("🟢", "green"),
        ChannelType.DESCENDING: ("🔴", "red"),
        ChannelType.EXPANDING: ("🟣", "violet"),
        ChannelType.CONTRACTING: ("🟡", "orange")
    }
    icon, color = colors.get(channel_type, ("⚪", "gray"))
    
    col1, col2, col3 = st.columns([2, 1, 1])
    col1.metric(f"{icon} Channel", channel_type.value, channel_reason)
    col2.metric("SPX", f"{current_spx:,.2f}", f"ES {current_es:,.2f}")
    col3.metric("Position", position.value)
    
    # NO TRADE Warning
    if channel_type == ChannelType.CONTRACTING:
        st.warning("⚠️ **NO TRADE — CONTRACTING CHANNEL**\n\nTokyo contracted inside Sydney. Wait for expansion.")
    
    st.divider()
    
    # Sessions
    st.subheader("🌏 Session Data")
    c1, c2, c3, c4 = st.columns(4)
    
    def show_session(col, name, emoji, data):
        with col:
            st.markdown(f"**{emoji} {name}**")
            if data:
                st.write(f"High: **{data['high']}**")
                st.write(f"Low: **{data['low']}**")
            else:
                st.write("No data")
    
    show_session(c1, "Sydney", "🦘", sydney)
    show_session(c2, "Tokyo", "🗼", tokyo)
    show_session(c3, "London", "🏛️", sessions.get("london") if not inputs["override"] else None)
    show_session(c4, "Overnight", "🌙", overnight)
    
    st.divider()
    
    # MM Bias - VIX Term Structure Analysis
    st.subheader("🏦 Market Maker Bias")
    
    # Extract data
    vix_val = mm_data.get("vix")
    vix3m_val = mm_data.get("vix3m")
    spread = mm_data.get("spread")
    vix_structure = mm_data.get("vix_structure", "N/A")
    score = mm_data.get("score", 0)
    interpretation = mm_data.get("interpretation", "")
    
    # Display metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VIX", f"{vix_val:.2f}" if vix_val else "N/A")
    c2.metric("VIX3M", f"{vix3m_val:.2f}" if vix3m_val else "N/A")
    c3.metric("Spread", f"{spread:+.2f}" if spread is not None else "N/A")
    c4.metric("Structure", vix_structure)
    
    # Visual score bar
    normalized = (score + 100) / 200
    if score < -25:
        st.progress(normalized, text=f"← CALLS HEAVY ({score:+d}) | MMs push DOWN to FLOOR")
    elif score > 25:
        st.progress(normalized, text=f"PUTS HEAVY ({score:+d}) → | MMs push UP to CEILING")
    else:
        st.progress(normalized, text=f"NEUTRAL ({score:+d})")
    
    # Interpretation
    if interpretation:
        if mm_bias == MMBias.CALLS_HEAVY:
            st.error(f"📉 {interpretation}")
        elif mm_bias == MMBias.PUTS_HEAVY:
            st.success(f"📈 {interpretation}")
        else:
            st.info(f"⚖️ {interpretation}")
    
    st.divider()
    
    # Channel Levels
    st.subheader("📊 Channel Levels @ 9:00 AM")
    c1, c2 = st.columns(2)
    c1.metric("🟢 Ceiling", f"{ceiling_spx}", f"ES {ceiling_es}")
    c2.metric("🔴 Floor", f"{floor_spx}", f"ES {floor_es}")
    
    st.divider()
    
    # Prior RTH Cone Projections
    st.subheader("📐 Prior RTH Cone Projections")
    
    if upper_cone_spx is not None and prior_high is not None:
        # Show prior RTH data
        c1, c2, c3 = st.columns(3)
        c1.metric("Prior RTH High", f"{round(prior_high - offset, 2)}", f"ES {prior_high}")
        c2.metric("Prior RTH Low", f"{round(prior_low - offset, 2)}", f"ES {prior_low}")
        if prior_close:
            c3.metric("Prior Close", f"{round(prior_close - offset, 2)}", f"ES {prior_close}")
        
        # Show projected cone levels as PROFIT TARGETS
        st.markdown("**🎯 Projected Profit Targets @ Reference Time:**")
        c1, c2 = st.columns(2)
        c1.metric("🟢 CALLS Target (Upper Cone)", f"{upper_cone_spx}", f"ES {upper_cone_es} | +{blocks_from_high} blocks")
        c2.metric("🔴 PUTS Target (Lower Cone)", f"{lower_cone_spx}", f"ES {lower_cone_es} | +{blocks_from_low} blocks")
        
        # Explain the targets
        st.markdown("""
        **How to Use:**
        - **CALLS**: When price breaks ABOVE ceiling → Target = **Upper Cone** (Prior RTH High projected)
        - **PUTS**: When price breaks BELOW floor → Target = **Lower Cone** (Prior RTH Low projected)
        """)
        
        # Show potential profit in points
        calls_potential = round(upper_cone_spx - ceiling_spx, 2)
        puts_potential = round(floor_spx - lower_cone_spx, 2)
        
        c1, c2 = st.columns(2)
        if calls_potential > 0:
            c1.success(f"📈 CALLS Potential: +{calls_potential} pts (Ceiling → Upper Cone)")
        else:
            c1.warning(f"⚠️ Upper Cone below Ceiling ({calls_potential} pts) - Limited upside")
        
        if puts_potential > 0:
            c2.success(f"📉 PUTS Potential: +{puts_potential} pts (Floor → Lower Cone)")
        else:
            c2.warning(f"⚠️ Lower Cone above Floor ({puts_potential} pts) - Limited downside")
        
        # Current price context
        st.markdown("**Current Position vs Targets:**")
        if current_spx > ceiling_spx:
            pts_to_target = round(upper_cone_spx - current_spx, 2)
            if pts_to_target > 0:
                st.info(f"Price ABOVE ceiling → {pts_to_target} pts to CALLS target ({upper_cone_spx})")
            else:
                st.warning(f"Price has EXCEEDED upper cone target by {abs(pts_to_target)} pts - Consider taking profits")
        elif current_spx < floor_spx:
            pts_to_target = round(current_spx - lower_cone_spx, 2)
            if pts_to_target > 0:
                st.info(f"Price BELOW floor → {pts_to_target} pts to PUTS target ({lower_cone_spx})")
            else:
                st.warning(f"Price has EXCEEDED lower cone target by {abs(pts_to_target)} pts - Consider taking profits")
        else:
            st.info(f"Price INSIDE channel → Wait for breakout to use cone targets")
    else:
        st.warning("Prior RTH data not available. Enable historical data or use manual override.")
    
    st.divider()
    
    # Scenarios
    if channel_type != ChannelType.CONTRACTING:
        st.subheader("🎯 Trade Scenarios")
        scenarios = generate_scenarios(channel_type, position, ceiling_es, floor_es, mm_bias, offset, vix, hours_to_expiry, upper_cone_spx, lower_cone_spx)
        
        for s in scenarios:
            direction = s["direction"]
            if direction == "CALLS":
                box = st.container(border=True)
                box.markdown(f"### 🟢 {s['condition']}")
            elif direction == "PUTS":
                box = st.container(border=True)
                box.markdown(f"### 🔴 {s['condition']}")
            else:
                box = st.container(border=True)
                box.markdown(f"### ⚠️ {s['condition']}")
            
            with box:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Entry", f"{s['entry_spx']}")
                c2.metric("Strike", f"{s['strike']}")
                c3.metric("Premium", f"${s['premium']:.2f}")
                c4.metric("Target", f"{s['target_spx']}")
                
                st.markdown(f"**Action:** {s['action']}")
                st.markdown(f"**Trigger:** {s['trigger']}")
                st.caption(f"💡 {s['notes']} | Confidence: {s['confidence']}")
    
    # Debug
    if inputs["debug"]:
        with st.expander("🔧 Debug"):
            st.json({
                "sydney": sydney, "tokyo": tokyo, "overnight": overnight,
                "channel": channel_type.value, "ceiling_es": ceiling_es, "floor_es": floor_es,
                "position": position.value, "mm_bias": mm_bias.value,
                "mm_data": {
                    "vix": mm_data.get("vix"),
                    "vix3m": mm_data.get("vix3m"),
                    "spread": mm_data.get("spread"),
                    "vix_structure": mm_data.get("vix_structure"),
                    "score": mm_data.get("score")
                }
            })

if __name__ == "__main__":
    main()
