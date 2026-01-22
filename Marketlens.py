# ═══════════════════════════════════════════════════════════════════════════════
# SPX PROPHET V7.0 - STRUCTURAL 0DTE TRADING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
# 
# COMPLETE SYSTEM WITH ALL INDICATORS:
# 1. Overnight Channel (Sydney → Tokyo → London)
# 2. 200 EMA Bias (Call/Put directional bias)
# 3. 8/21 EMA Cross (Trend confirmation)
# 4. VIX Overnight Range (2-6 AM zone from Polygon)
# 5. VIX Position (Current vs overnight range)
# 6. MM Bias (VIX term structure)
# 7. Decision Engine (Primary/Alternate scenarios)
#
# ═══════════════════════════════════════════════════════════════════════════════

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import pytz
import json
import os
import math
from datetime import datetime, date, time, timedelta
from enum import Enum
from typing import Optional, Dict

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="SPX Prophet V7", page_icon="🔮", layout="wide")

CT = pytz.timezone("America/Chicago")
ET = pytz.timezone("America/New_York")
UTC = pytz.UTC

SLOPE = 0.48  # Points per 30-minute block
SAVE_FILE = "spx_prophet_v7_inputs.json"

# Polygon API
POLYGON_API_KEY = "jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm"
POLYGON_BASE_URL = "https://api.polygon.io"

# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════
class ChannelType(Enum):
    ASCENDING = "ASCENDING"       # Higher high → bullish bias
    DESCENDING = "DESCENDING"     # Lower low → bearish bias
    EXPANDING = "EXPANDING"       # Both → volatile, fade extremes
    CONTRACTING = "CONTRACTING"   # Neither → no trade
    UNDETERMINED = "UNDETERMINED"

class Position(Enum):
    ABOVE = "ABOVE"
    INSIDE = "INSIDE"
    BELOW = "BELOW"

class Bias(Enum):
    CALLS = "CALLS"
    PUTS = "PUTS"
    NEUTRAL = "NEUTRAL"

class VIXPosition(Enum):
    ABOVE_RANGE = "ABOVE RANGE"   # Fear spiking → puts pressure
    IN_RANGE = "IN RANGE"         # Normal
    BELOW_RANGE = "BELOW RANGE"   # Complacency → calls pressure
    UNKNOWN = "UNKNOWN"

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
# BLACK-SCHOLES PRICING
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

def calc_0dte_iv(vix, hours_to_expiry):
    """0DTE IV calibrated to market (~1.6-1.8x VIX)."""
    if hours_to_expiry > 5:
        mult = 1.6
    elif hours_to_expiry > 3:
        mult = 1.7
    else:
        mult = 1.8
    return max((vix / 100) * mult, 0.15)

def estimate_0dte_premium(spot, strike, hours_to_expiry, vix, opt_type):
    iv = calc_0dte_iv(vix, hours_to_expiry)
    T = max(0.0001, hours_to_expiry / (365 * 24))
    premium = black_scholes(spot, strike, T, 0.05, iv, opt_type)
    return max(round(premium, 2), 0.05)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING - Yahoo Finance
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def fetch_es_current():
    """Current ES price."""
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
    """ES 30-minute candles for session extraction."""
    try:
        es = yf.Ticker("ES=F")
        data = es.history(period=f"{days}d", interval="30m")
        if data is not None and not data.empty and len(data) > 10:
            return data
    except:
        pass
    return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_spx_with_ema():
    """
    Fetch SPX data and calculate:
    - Current price
    - 200 EMA (daily)
    - 8 EMA and 21 EMA (for cross)
    """
    result = {
        "price": None,
        "ema_200": None,
        "ema_8": None,
        "ema_21": None,
        "above_200": None,
        "ema_cross": None,  # "BULLISH" (8 > 21), "BEARISH" (8 < 21)
        "ema_bias": Bias.NEUTRAL
    }
    
    try:
        # Get daily data for 200 EMA
        spx = yf.Ticker("^GSPC")
        daily = spx.history(period="1y", interval="1d")
        
        if daily is not None and not daily.empty and len(daily) > 200:
            # Current price
            result["price"] = round(float(daily['Close'].iloc[-1]), 2)
            
            # 200 EMA
            daily['EMA_200'] = daily['Close'].ewm(span=200, adjust=False).mean()
            result["ema_200"] = round(float(daily['EMA_200'].iloc[-1]), 2)
            
            # 8 and 21 EMA
            daily['EMA_8'] = daily['Close'].ewm(span=8, adjust=False).mean()
            daily['EMA_21'] = daily['Close'].ewm(span=21, adjust=False).mean()
            result["ema_8"] = round(float(daily['EMA_8'].iloc[-1]), 2)
            result["ema_21"] = round(float(daily['EMA_21'].iloc[-1]), 2)
            
            # Bias calculations
            result["above_200"] = result["price"] > result["ema_200"]
            
            if result["ema_8"] > result["ema_21"]:
                result["ema_cross"] = "BULLISH"
            else:
                result["ema_cross"] = "BEARISH"
            
            # Combined EMA bias
            if result["above_200"] and result["ema_cross"] == "BULLISH":
                result["ema_bias"] = Bias.CALLS
            elif not result["above_200"] and result["ema_cross"] == "BEARISH":
                result["ema_bias"] = Bias.PUTS
            else:
                result["ema_bias"] = Bias.NEUTRAL
                
    except Exception as e:
        pass
    
    return result

@st.cache_data(ttl=60, show_spinner=False)
def fetch_vix_yahoo():
    """Fallback VIX from Yahoo."""
    try:
        vix = yf.Ticker("^VIX")
        data = vix.history(period="2d")
        if data is not None and not data.empty:
            return round(float(data['Close'].iloc[-1]), 2)
    except:
        pass
    return 16.0

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING - Polygon API
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def fetch_vix_polygon():
    """Fetch current VIX from Polygon."""
    try:
        url = f"{POLYGON_BASE_URL}/v3/snapshot?ticker.any_of=I:VIX"
        params = {"apiKey": POLYGON_API_KEY}
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                return round(float(data["results"][0].get("value", 0)), 2)
    except:
        pass
    return None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_vix_overnight_range(trading_date):
    """
    Get VIX overnight range from 2:00 AM - 6:00 AM CT using Polygon.
    This is the key zone for VIX position analysis.
    """
    result = {
        "bottom": None,
        "top": None,
        "range_size": None,
        "available": False
    }
    
    try:
        date_str = trading_date.strftime("%Y-%m-%d")
        url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/I:VIX/range/1/minute/{date_str}/{date_str}"
        params = {
            "adjusted": "true",
            "sort": "asc",
            "limit": 50000,
            "apiKey": POLYGON_API_KEY
        }
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                df = pd.DataFrame(data["results"])
                
                # Convert timestamp to CT
                df['datetime'] = pd.to_datetime(df['t'], unit='ms', utc=True).dt.tz_convert(CT)
                
                # Filter to 2:00 AM - 6:00 AM CT window
                zone_start = CT.localize(datetime.combine(trading_date, time(2, 0)))
                zone_end = CT.localize(datetime.combine(trading_date, time(6, 0)))
                
                zone_df = df[(df['datetime'] >= zone_start) & (df['datetime'] <= zone_end)]
                
                if not zone_df.empty and len(zone_df) > 5:
                    result["bottom"] = round(float(zone_df['l'].min()), 2)
                    result["top"] = round(float(zone_df['h'].max()), 2)
                    result["range_size"] = round(result["top"] - result["bottom"], 2)
                    result["available"] = True
    except:
        pass
    
    return result

def get_vix_position(current_vix, vix_range):
    """Determine where VIX is relative to overnight range."""
    if not vix_range["available"] or current_vix is None:
        return VIXPosition.UNKNOWN, "No range data"
    
    bottom = vix_range["bottom"]
    top = vix_range["top"]
    
    if current_vix > top:
        diff = round(current_vix - top, 2)
        return VIXPosition.ABOVE_RANGE, f"VIX {diff} pts ABOVE range → Fear rising → Supports PUTS"
    elif current_vix < bottom:
        diff = round(bottom - current_vix, 2)
        return VIXPosition.BELOW_RANGE, f"VIX {diff} pts BELOW range → Complacency → Supports CALLS"
    else:
        return VIXPosition.IN_RANGE, f"VIX within overnight range ({bottom}-{top}) → Neutral"

# ═══════════════════════════════════════════════════════════════════════════════
# MM BIAS - VIX Term Structure (Simplified & Clear)
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def fetch_mm_bias():
    """
    Market Maker Bias from VIX Term Structure.
    
    Simple interpretation:
    - VIX < VIX3M (Contango): Retail is CALLS HEAVY → MMs push DOWN
    - VIX > VIX3M (Backwardation): Retail is PUTS HEAVY → MMs push UP
    """
    result = {
        "vix": None,
        "vix3m": None,
        "spread": None,
        "bias": Bias.NEUTRAL,
        "retail_position": None,
        "mm_action": None,
        "interpretation": None
    }
    
    try:
        vix_data = yf.Ticker("^VIX").history(period="2d")
        vix3m_data = yf.Ticker("^VIX3M").history(period="2d")
        
        if not vix_data.empty and not vix3m_data.empty:
            vix = round(float(vix_data['Close'].iloc[-1]), 2)
            vix3m = round(float(vix3m_data['Close'].iloc[-1]), 2)
            spread = round(vix - vix3m, 2)
            
            result["vix"] = vix
            result["vix3m"] = vix3m
            result["spread"] = spread
            
            if spread <= -1.5:
                # Contango - calls heavy
                result["bias"] = Bias.CALLS
                result["retail_position"] = "CALLS HEAVY"
                result["mm_action"] = "MMs likely push DOWN"
                result["interpretation"] = f"Spread {spread:+.1f} → Retail loaded with calls → MMs profit by pushing price DOWN to make calls expire worthless"
            elif spread >= 1.5:
                # Backwardation - puts heavy
                result["bias"] = Bias.PUTS
                result["retail_position"] = "PUTS HEAVY"
                result["mm_action"] = "MMs likely push UP"
                result["interpretation"] = f"Spread {spread:+.1f} → Retail loaded with puts → MMs profit by pushing price UP to make puts expire worthless"
            else:
                result["bias"] = Bias.NEUTRAL
                result["retail_position"] = "BALANCED"
                result["mm_action"] = "No strong MM pressure"
                result["interpretation"] = f"Spread {spread:+.1f} → Balanced positioning → Follow structure"
    except:
        result["interpretation"] = "Unable to fetch VIX term structure"
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════
def extract_sessions(es_candles, trading_date):
    """
    Extract session highs/lows with exact times.
    
    Sessions (CT):
    - Sydney: 5:00 PM - 8:30 PM (previous day)
    - Tokyo:  9:00 PM - 1:30 AM
    - London: 2:00 AM - 5:00 AM
    """
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
def determine_channel(sydney, tokyo, london=None):
    """
    Determine channel from overnight session progression.
    """
    if not sydney or not tokyo:
        return ChannelType.UNDETERMINED, "Missing data", None, None, None, None
    
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
    
    highest = max(all_highs, key=lambda x: x[0])
    lowest = min(all_lows, key=lambda x: x[0])
    
    true_high, high_time, high_session = highest
    true_low, low_time, low_session = lowest
    
    tokyo_expanded_high = tokyo["high"] > sydney["high"]
    tokyo_expanded_low = tokyo["low"] < sydney["low"]
    
    london_expanded_high = london["high"] > max(sydney["high"], tokyo["high"]) if london else False
    london_expanded_low = london["low"] < min(sydney["low"], tokyo["low"]) if london else False
    
    expanded_high = tokyo_expanded_high or london_expanded_high
    expanded_low = tokyo_expanded_low or london_expanded_low
    
    if expanded_high and expanded_low:
        reason = f"Range expanded both ways → Volatile"
        return ChannelType.EXPANDING, reason, true_high, true_low, high_time, low_time
    elif not expanded_high and not expanded_low:
        reason = f"Range contracted → No direction"
        return ChannelType.CONTRACTING, reason, true_high, true_low, high_time, low_time
    elif expanded_high:
        reason = f"{high_session} made higher high ({true_high})"
        return ChannelType.ASCENDING, reason, true_high, true_low, high_time, low_time
    else:
        reason = f"{low_session} made lower low ({true_low})"
        return ChannelType.DESCENDING, reason, true_high, true_low, high_time, low_time

def calc_channel_levels(upper_pivot, lower_pivot, upper_time, lower_time, ref_time, channel_type):
    """
    Project channel levels to reference time using slope.
    
    ASCENDING:   +0.48 / +0.48 (both rise)
    DESCENDING:  -0.48 / -0.48 (both fall)
    EXPANDING:   +0.48 / -0.48 (diverge)
    CONTRACTING: -0.48 / +0.48 (converge)
    """
    if upper_pivot is None or lower_pivot is None:
        return None, None
    
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
    """Calculate profit targets from prior RTH."""
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
    if price > ceiling:
        return Position.ABOVE
    elif price < floor:
        return Position.BELOW
    return Position.INSIDE

# ═══════════════════════════════════════════════════════════════════════════════
# DECISION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
def analyze_market_state(current_spx, ceiling_spx, floor_spx, channel_type, 
                         mm_bias, ema_bias, vix_position,
                         upper_cone_spx, lower_cone_spx, vix):
    """
    Generate trading scenarios based on all indicators.
    
    Inputs:
    - Channel type & levels
    - MM Bias (from VIX term structure)
    - EMA Bias (200 EMA + 8/21 cross)
    - VIX Position (vs overnight range)
    """
    
    result = {
        "no_trade": False,
        "no_trade_reason": None,
        "confluence": [],  # List of supporting factors
        "primary": None,
        "alternate": None
    }
    
    # Position
    if current_spx > ceiling_spx:
        position = Position.ABOVE
        pos_desc = f"ABOVE ceiling by {round(current_spx - ceiling_spx, 1)} pts"
    elif current_spx < floor_spx:
        position = Position.BELOW
        pos_desc = f"BELOW floor by {round(floor_spx - current_spx, 1)} pts"
    else:
        position = Position.INSIDE
        pos_desc = f"INSIDE channel"
    
    # Default targets
    calls_target = upper_cone_spx if upper_cone_spx else ceiling_spx + 25
    puts_target = lower_cone_spx if lower_cone_spx else floor_spx - 25
    
    def make_scenario(name, direction, entry, stop, target, trigger, rationale, confidence):
        if direction == "CALLS":
            potential = round(target - entry, 1)
            strike = int(math.ceil((entry + 20) / 5) * 5)
            opt_type = "CALL"
        else:
            potential = round(entry - target, 1)
            strike = int(math.floor((entry - 20) / 5) * 5)
            opt_type = "PUT"
        
        entry_premium = estimate_0dte_premium(entry, strike, 6.0, vix, opt_type)
        target_premium = estimate_0dte_premium(target, strike, 4.0, vix, opt_type)
        dollar_profit = round((target_premium - entry_premium) * 100, 0)
        
        return {
            "name": name, "direction": direction,
            "entry": entry, "stop": stop, "target": target,
            "trigger": trigger, "rationale": rationale, "confidence": confidence,
            "potential_pts": potential,
            "rr_ratio": round(potential / 5.0, 1) if potential > 0 else 0,
            "strike": strike,
            "contract": f"SPX {strike}{'C' if direction == 'CALLS' else 'P'} 0DTE",
            "entry_premium": entry_premium,
            "target_premium": target_premium,
            "dollar_profit": dollar_profit
        }
    
    # Check confluence
    calls_support = []
    puts_support = []
    
    if channel_type == ChannelType.ASCENDING:
        calls_support.append("ASCENDING channel")
    elif channel_type == ChannelType.DESCENDING:
        puts_support.append("DESCENDING channel")
    
    if ema_bias == Bias.CALLS:
        calls_support.append("Above 200 EMA + 8/21 bullish")
    elif ema_bias == Bias.PUTS:
        puts_support.append("Below 200 EMA + 8/21 bearish")
    
    if mm_bias == Bias.PUTS:  # Puts heavy = MMs push UP
        calls_support.append("MMs pushing UP (puts heavy)")
    elif mm_bias == Bias.CALLS:  # Calls heavy = MMs push DOWN
        puts_support.append("MMs pushing DOWN (calls heavy)")
    
    if vix_position == VIXPosition.BELOW_RANGE:
        calls_support.append("VIX below range (complacent)")
    elif vix_position == VIXPosition.ABOVE_RANGE:
        puts_support.append("VIX above range (fearful)")
    
    result["calls_confluence"] = calls_support
    result["puts_confluence"] = puts_support
    
    # NO TRADE
    if channel_type == ChannelType.CONTRACTING:
        result["no_trade"] = True
        result["no_trade_reason"] = "CONTRACTING channel - No directional bias"
        return result
    
    if channel_type == ChannelType.UNDETERMINED:
        result["no_trade"] = True
        result["no_trade_reason"] = "Cannot determine channel"
        return result
    
    # SCENARIO GENERATION based on channel + confluence
    if channel_type == ChannelType.ASCENDING:
        if position == Position.INSIDE or position == Position.BELOW:
            conf = "HIGH" if len(calls_support) >= 3 else "MEDIUM" if len(calls_support) >= 2 else "LOW"
            result["primary"] = make_scenario(
                "Floor Bounce", "CALLS", floor_spx, floor_spx - 5, calls_target,
                "Price touches floor → CALLS on support",
                f"Confluence: {', '.join(calls_support)}" if calls_support else "ASCENDING structure",
                conf
            )
            result["alternate"] = make_scenario(
                "Floor Break", "PUTS", floor_spx, floor_spx + 5, puts_target,
                "If floor breaks → PUTS",
                "Failed support becomes resistance", "LOW"
            )
        else:  # ABOVE
            if mm_bias == Bias.CALLS:  # MMs push down
                result["primary"] = make_scenario(
                    "MM Reversal", "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                    "Price at ceiling → PUTS (MM pushing down)",
                    f"Confluence: {', '.join(puts_support)}" if puts_support else "MM pressure",
                    "HIGH"
                )
            else:
                result["primary"] = make_scenario(
                    "Ceiling Support", "CALLS", ceiling_spx, ceiling_spx - 5, calls_target,
                    "Price pulls back to ceiling → CALLS on support",
                    f"Confluence: {', '.join(calls_support)}" if calls_support else "Breakout continuation",
                    "MEDIUM"
                )
            result["alternate"] = make_scenario(
                "Ceiling Fails", "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
                "If ceiling breaks down → PUTS", "Failed support", "LOW"
            )
    
    elif channel_type == ChannelType.DESCENDING:
        if position == Position.INSIDE or position == Position.ABOVE:
            conf = "HIGH" if len(puts_support) >= 3 else "MEDIUM" if len(puts_support) >= 2 else "LOW"
            result["primary"] = make_scenario(
                "Ceiling Rejection", "PUTS", ceiling_spx, ceiling_spx + 5, puts_target,
                "Price touches ceiling → PUTS on resistance",
                f"Confluence: {', '.join(puts_support)}" if puts_support else "DESCENDING structure",
                conf
            )
            result["alternate"] = make_scenario(
                "Ceiling Break", "CALLS", ceiling_spx, ceiling_spx - 5, calls_target,
                "If ceiling breaks up → CALLS",
                "Failed resistance becomes support", "LOW"
            )
        else:  # BELOW
            if mm_bias == Bias.PUTS:  # MMs push up
                result["primary"] = make_scenario(
                    "MM Reversal", "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                    "Price at floor → CALLS (MM pushing up)",
                    f"Confluence: {', '.join(calls_support)}" if calls_support else "MM pressure",
                    "HIGH"
                )
            else:
                result["primary"] = make_scenario(
                    "Floor Resistance", "PUTS", floor_spx, floor_spx + 5, puts_target,
                    "Price rallies to floor → PUTS on resistance",
                    f"Confluence: {', '.join(puts_support)}" if puts_support else "Breakdown continuation",
                    "MEDIUM"
                )
            result["alternate"] = make_scenario(
                "Floor Reclaim", "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
                "If reclaims floor → CALLS", "Back inside channel", "LOW"
            )
    
    elif channel_type == ChannelType.EXPANDING:
        # Fade extremes
        result["primary"] = make_scenario(
            "Fade Ceiling", "PUTS", ceiling_spx, ceiling_spx + 5, floor_spx,
            "Price at ceiling → PUTS to fade",
            "EXPANDING: Fade extremes", "MEDIUM"
        )
        result["alternate"] = make_scenario(
            "Fade Floor", "CALLS", floor_spx, floor_spx - 5, ceiling_spx,
            "Price at floor → CALLS to fade",
            "EXPANDING: Fade extremes", "MEDIUM"
        )
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
def sidebar():
    saved = load_inputs()
    with st.sidebar:
        st.title("🔮 SPX Prophet V7")
        st.caption("Complete 0DTE System")
        st.divider()
        
        trading_date = st.date_input("📅 Trading Date", value=date.today())
        offset = st.number_input("⚙️ ES→SPX Offset", value=float(saved.get("offset", 35.5)), step=0.5)
        
        st.divider()
        override = st.checkbox("📝 Manual Override")
        manual = {}
        if override:
            st.caption("ES Values:")
            c1, c2 = st.columns(2)
            manual["sydney_high"] = c1.number_input("Sydney H", value=6075.0, step=0.5)
            manual["sydney_low"] = c2.number_input("Sydney L", value=6050.0, step=0.5)
            manual["tokyo_high"] = c1.number_input("Tokyo H", value=6080.0, step=0.5)
            manual["tokyo_low"] = c2.number_input("Tokyo Low", value=6045.0, step=0.5)
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
        # Session data
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
            overnight = {"high": max(m["sydney_high"], m["tokyo_high"], m["london_high"]),
                         "low": min(m["sydney_low"], m["tokyo_low"], m["london_low"])}
            sessions = {}
        else:
            es_candles = fetch_es_candles()
            current_es = fetch_es_current() or 6050
            sessions = extract_sessions(es_candles, inputs["trading_date"]) or {}
            sydney = sessions.get("sydney")
            tokyo = sessions.get("tokyo")
            london = sessions.get("london")
            overnight = sessions.get("overnight")
        
        # Indicators
        vix_polygon = fetch_vix_polygon()
        vix = vix_polygon if vix_polygon else fetch_vix_yahoo()
        
        vix_range = fetch_vix_overnight_range(inputs["trading_date"])
        vix_pos, vix_pos_desc = get_vix_position(vix, vix_range)
        
        mm_data = fetch_mm_bias()
        ema_data = fetch_spx_with_ema()
    
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
    
    # Prior RTH targets
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
        current_spx, ceiling_spx, floor_spx, channel_type,
        mm_data["bias"], ema_data["ema_bias"], vix_pos,
        upper_cone_spx, lower_cone_spx, vix
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - HEADER
    # ═══════════════════════════════════════════════════════════════════════════
    st.title("🔮 SPX Prophet V7")
    st.caption("Structure • EMAs • VIX • MM Bias → Trade Decision")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - TRADE DECISION
    # ═══════════════════════════════════════════════════════════════════════════
    if decision["no_trade"]:
        st.error(f"### 🚫 NO TRADE: {decision['no_trade_reason']}")
    else:
        # Show confluence
        cols = st.columns(2)
        with cols[0]:
            if decision.get("calls_confluence"):
                st.success(f"**CALLS Support:** {' • '.join(decision['calls_confluence'])}")
            else:
                st.info("CALLS Support: None")
        with cols[1]:
            if decision.get("puts_confluence"):
                st.error(f"**PUTS Support:** {' • '.join(decision['puts_confluence'])}")
            else:
                st.info("PUTS Support: None")
        
        # PRIMARY
        p = decision["primary"]
        if p:
            icon = "🟢" if p["direction"] == "CALLS" else "🔴"
            st.markdown(f"### {icon} PRIMARY: {p['name']} ({p['confidence']})")
            
            with st.container(border=True):
                st.markdown(f"#### 📋 `{p['contract']}`")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Entry", f"${p['entry_premium']:.2f}")
                c2.metric("Target", f"${p['target_premium']:.2f}")
                c3.metric("Profit", f"${p['dollar_profit']:.0f}")
                c4.metric("R:R", f"{p['rr_ratio']}:1")
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("SPX Entry", f"{p['entry']}")
                c2.metric("Stop", f"{p['stop']}")
                c3.metric("Target", f"{p['target']}")
                c4.metric("Move", f"+{p['potential_pts']} pts")
                
                st.markdown(f"**🎯 {p['trigger']}**")
                st.caption(p['rationale'])
        
        # ALTERNATE
        a = decision["alternate"]
        if a:
            with st.expander(f"↩️ ALTERNATE: {a['name']} — `{a['contract']}`"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Entry", f"${a['entry_premium']:.2f}")
                c2.metric("Target", f"${a['target_premium']:.2f}")
                c3.metric("Profit", f"${a['dollar_profit']:.0f}")
                st.markdown(f"**🎯 {a['trigger']}**")
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - INDICATORS DASHBOARD
    # ═══════════════════════════════════════════════════════════════════════════
    st.subheader("📊 Market Indicators")
    
    # Row 1: Channel + Current Price
    c1, c2, c3 = st.columns(3)
    
    chan_icons = {ChannelType.ASCENDING: "🟢", ChannelType.DESCENDING: "🔴",
                  ChannelType.EXPANDING: "🟣", ChannelType.CONTRACTING: "🟡"}
    c1.metric(f"{chan_icons.get(channel_type, '⚪')} Channel", channel_type.value, channel_reason)
    c2.metric("SPX", f"{current_spx:,.2f}", f"ES {current_es:,.2f}")
    c3.metric("Position", position.value)
    
    st.divider()
    
    # Row 2: All Indicators
    c1, c2, c3, c4 = st.columns(4)
    
    # 200 EMA Bias
    with c1:
        st.markdown("**📈 200 EMA Bias**")
        if ema_data["ema_200"]:
            above = "✅ ABOVE" if ema_data["above_200"] else "❌ BELOW"
            st.write(f"Price vs 200 EMA: **{above}**")
            st.write(f"200 EMA: {ema_data['ema_200']}")
            if ema_data["ema_bias"] == Bias.CALLS:
                st.success("→ Supports CALLS")
            elif ema_data["ema_bias"] == Bias.PUTS:
                st.error("→ Supports PUTS")
            else:
                st.info("→ Neutral")
        else:
            st.write("No data")
    
    # 8/21 EMA Cross
    with c2:
        st.markdown("**🔀 8/21 EMA Cross**")
        if ema_data["ema_8"]:
            st.write(f"8 EMA: {ema_data['ema_8']}")
            st.write(f"21 EMA: {ema_data['ema_21']}")
            if ema_data["ema_cross"] == "BULLISH":
                st.success("**BULLISH** (8 > 21)")
            else:
                st.error("**BEARISH** (8 < 21)")
        else:
            st.write("No data")
    
    # VIX Overnight Range
    with c3:
        st.markdown("**📊 VIX Overnight (2-6 AM)**")
        if vix_range["available"]:
            st.write(f"Range: **{vix_range['bottom']} - {vix_range['top']}**")
            st.write(f"Size: {vix_range['range_size']} pts")
            st.write(f"Current VIX: **{vix}**")
            if vix_pos == VIXPosition.ABOVE_RANGE:
                st.error("⬆️ ABOVE range")
            elif vix_pos == VIXPosition.BELOW_RANGE:
                st.success("⬇️ BELOW range")
            else:
                st.info("↔️ IN range")
        else:
            st.write(f"Current VIX: {vix}")
            st.caption("Range not available (before 6 AM?)")
    
    # MM Bias
    with c4:
        st.markdown("**🏦 Market Maker Bias**")
        st.write(f"VIX: {mm_data.get('vix', 'N/A')} | VIX3M: {mm_data.get('vix3m', 'N/A')}")
        if mm_data.get("retail_position"):
            if mm_data["bias"] == Bias.CALLS:
                st.error(f"**{mm_data['retail_position']}**")
                st.write(mm_data["mm_action"])
            elif mm_data["bias"] == Bias.PUTS:
                st.success(f"**{mm_data['retail_position']}**")
                st.write(mm_data["mm_action"])
            else:
                st.info(f"**{mm_data['retail_position']}**")
                st.write(mm_data["mm_action"])
        else:
            st.write("No data")
    
    st.divider()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # UI - SESSIONS
    # ═══════════════════════════════════════════════════════════════════════════
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
    st.subheader(f"📐 Channel @ {inputs['ref_time'][0]}:{inputs['ref_time'][1]:02d} AM")
    c1, c2 = st.columns(2)
    c1.metric("🟢 Ceiling", f"{ceiling_spx}", f"ES {ceiling_es}")
    c2.metric("🔴 Floor", f"{floor_spx}", f"ES {floor_es}")

if __name__ == "__main__":
    main()
