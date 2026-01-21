# ═══════════════════════════════════════════════════════════════════════════════
# SPX PROPHET V8 - COMPLETE TRADING SYSTEM
# Overnight Analysis | Channel Detection | SPY P/C Ratio | All Entry Scenarios
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
import time as time_module
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="SPX Prophet V8", page_icon="🔮", layout="wide", initial_sidebar_state="expanded")
CT = pytz.timezone("America/Chicago")
ET = pytz.timezone("America/New_York")
SLOPE = 0.48  # pts per 30-min block
BREAK_THRESHOLD = 6.0  # pts for momentum probe
POLYGON_KEY = "6ZAi7hZZOUrviEq27ESoH8QP25DMyejQ"
POLYGON_BASE = "https://api.polygon.io"

# ═══════════════════════════════════════════════════════════════════════════════
# STYLES
# ═══════════════════════════════════════════════════════════════════════════════
STYLES = """<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=DM+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root{--bg:#0a0a0f;--bg2:#12121a;--card:rgba(255,255,255,0.03);--border:rgba(255,255,255,0.08);--text:#fff;--text2:rgba(255,255,255,0.6);--green:#00d4aa;--red:#ff4757;--amber:#ffa502;--purple:#a855f7;--cyan:#22d3ee;--blue:#3b82f6}
.stApp{background:linear-gradient(135deg,var(--bg),var(--bg2));font-family:'DM Sans',sans-serif}
.stApp>header{background:transparent!important}
[data-testid="stSidebar"]{background:rgba(10,10,15,0.95)!important;border-right:1px solid var(--border)}
[data-testid="stSidebar"] *{color:var(--text)!important}
h1,h2,h3{font-family:'Space Grotesk',sans-serif!important;color:var(--text)!important}
.hero{background:linear-gradient(135deg,rgba(168,85,247,0.15),rgba(34,211,238,0.15));border:1px solid var(--border);border-radius:20px;padding:24px;margin-bottom:20px;text-align:center}
.hero-title{font-family:'Space Grotesk',sans-serif;font-size:28px;font-weight:700;background:linear-gradient(135deg,#a855f7,#22d3ee);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero-sub{font-size:13px;color:var(--text2);margin-top:4px}
.hero-price{font-family:'IBM Plex Mono',monospace;font-size:42px;font-weight:700;color:var(--cyan);margin-top:8px}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px;margin-bottom:16px}
.channel-badge{padding:6px 16px;border-radius:20px;font-size:12px;font-weight:600;letter-spacing:0.5px;display:inline-block}
.ascending{background:linear-gradient(135deg,#00d4aa,#00a885);color:white}
.descending{background:linear-gradient(135deg,#ff4757,#ff2f42);color:white}
.expanding{background:linear-gradient(135deg,#a855f7,#8b5cf6);color:white}
.contracting{background:linear-gradient(135deg,#6b7280,#4b5563);color:white}
.level-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}
.level-box{background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:12px;padding:16px}
.level-label{font-size:11px;color:var(--text2);text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.level-value{font-family:'IBM Plex Mono',monospace;font-size:20px;font-weight:600}
.scenario-card{background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:14px;padding:18px;margin-bottom:12px;transition:all 0.2s}
.scenario-card:hover{border-color:rgba(255,255,255,0.15);background:rgba(255,255,255,0.04)}
.scenario-card.calls{border-left:4px solid var(--green)}
.scenario-card.puts{border-left:4px solid var(--red)}
.scenario-card.highlighted{background:rgba(0,212,170,0.08);border-color:var(--green)}
.scenario-card.highlighted.puts{background:rgba(255,71,87,0.08);border-color:var(--red)}
.scenario-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.scenario-title{font-weight:600;font-size:14px}
.scenario-badge{padding:4px 12px;border-radius:12px;font-size:11px;font-weight:600}
.calls-badge{background:rgba(0,212,170,0.15);color:var(--green)}
.puts-badge{background:rgba(255,71,87,0.15);color:var(--red)}
.mm-badge{background:rgba(168,85,247,0.2);color:var(--purple);padding:3px 8px;border-radius:8px;font-size:10px;margin-left:8px}
.scenario-details{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;font-size:12px}
.scenario-detail{text-align:center;padding:10px;background:rgba(255,255,255,0.03);border-radius:8px}
.scenario-detail-label{color:var(--text2);font-size:10px;margin-bottom:4px}
.scenario-detail-value{font-family:'IBM Plex Mono',monospace;font-weight:600}
.pc-ratio{display:flex;align-items:center;gap:16px;padding:16px;background:rgba(255,255,255,0.02);border-radius:12px;margin-top:12px}
.pc-bar{flex:1;height:28px;background:rgba(255,255,255,0.1);border-radius:14px;overflow:hidden;display:flex}
.pc-calls{background:linear-gradient(90deg,#00d4aa,#00b894);height:100%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600}
.pc-puts{background:linear-gradient(90deg,#ff4757,#ee3b4d);height:100%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600}
.session-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}
.session-box{background:rgba(255,255,255,0.02);border:1px solid var(--border);border-radius:12px;padding:14px}
.session-name{font-size:12px;font-weight:600;margin-bottom:8px;display:flex;align-items:center;gap:6px}
.session-values{font-size:11px;color:var(--text2)}
.session-value{display:flex;justify-content:space-between;padding:4px 0}
.high-val{color:var(--green)}
.low-val{color:var(--red)}
.no-trade{background:rgba(107,114,128,0.1);border:1px solid rgba(107,114,128,0.3);border-radius:14px;padding:24px;text-align:center}
.no-trade-icon{font-size:36px;margin-bottom:10px}
.no-trade-text{font-size:15px;color:var(--text2)}
.current-pos{background:linear-gradient(135deg,rgba(34,211,238,0.1),rgba(168,85,247,0.1));border:1px solid rgba(34,211,238,0.3);border-radius:14px;padding:18px;margin-bottom:16px}
.current-pos-title{font-size:12px;color:var(--text2);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.current-pos-value{font-size:18px;font-weight:600}
.flow-indicator{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:10px;font-size:12px;font-weight:600}
.flow-bullish{background:rgba(0,212,170,0.15);color:var(--green)}
.flow-bearish{background:rgba(255,71,87,0.15);color:var(--red)}
.flow-neutral{background:rgba(255,165,2,0.15);color:var(--amber)}
.footer{text-align:center;padding:16px;color:var(--text2);font-size:11px;border-top:1px solid var(--border);margin-top:20px}
.live-dot{width:8px;height:8px;background:#00d4aa;border-radius:50%;display:inline-block;margin-right:6px;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}
</style>"""

# ═══════════════════════════════════════════════════════════════════════════════
# MATH FUNCTIONS
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

def get_strike(price, opt_type, offset=20):
    """Get ATM or slightly OTM strike price"""
    if opt_type == "CALL":
        return int(round((price + offset) / 5) * 5)
    return int(round((price - offset) / 5) * 5)

def estimate_premium(price, strike, opt_type, vix, hours_to_expiry):
    """Estimate option premium using Black-Scholes"""
    T = max(hours_to_expiry / (252 * 6.5), 0.001)
    iv = vix / 100 * 1.2
    return round(black_scholes(price, strike, T, 0.05, iv, opt_type), 2)

# ═══════════════════════════════════════════════════════════════════════════════
# TIME HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def now_ct():
    return datetime.now(CT)

def blocks_between(start, end):
    """Count 30-min blocks between two timestamps"""
    if start is None or end is None or end <= start:
        return 0
    return int((end - start).total_seconds() / 60 // 30)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING - ES FUTURES
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def fetch_es_candles(days=7):
    """Fetch ES futures 30-min candles"""
    try:
        es = yf.Ticker("ES=F")
        df = es.history(period=f"{days}d", interval="30m")
        if df is not None and not df.empty:
            return df
    except:
        pass
    return None

@st.cache_data(ttl=15, show_spinner=False)
def fetch_es_current():
    """Fetch current ES price with multiple fallbacks"""
    # Try 1-min data
    try:
        es = yf.Ticker("ES=F")
        d = es.history(period="2d", interval="1m")
        if d is not None and not d.empty:
            return round(float(d['Close'].iloc[-1]), 2)
    except:
        pass
    
    # Try 5-min data
    try:
        es = yf.Ticker("ES=F")
        d = es.history(period="5d", interval="5m")
        if d is not None and not d.empty:
            return round(float(d['Close'].iloc[-1]), 2)
    except:
        pass
    
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING - POLYGON (SPX, VIX)
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=60, show_spinner=False)
def fetch_spx_polygon():
    """Fetch SPX from Polygon"""
    try:
        url = f"{POLYGON_BASE}/v3/snapshot?ticker.any_of=I:SPX&apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            d = r.json()
            if "results" in d and len(d["results"]) > 0:
                res = d["results"][0]
                p = res.get("value") or res.get("session", {}).get("close")
                if p:
                    return round(float(p), 2)
    except:
        pass
    return None

@st.cache_data(ttl=60, show_spinner=False)
def fetch_vix_polygon():
    """Fetch VIX from Polygon"""
    try:
        url = f"{POLYGON_BASE}/v3/snapshot?ticker.any_of=I:VIX&apiKey={POLYGON_KEY}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            d = r.json()
            if "results" in d and len(d["results"]) > 0:
                res = d["results"][0]
                p = res.get("value") or res.get("session", {}).get("close")
                if p:
                    return round(float(p), 2)
    except:
        pass
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING - SPY OPTIONS (P/C RATIO)
# Uses SPY as proxy since it has reliable OI data
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300, show_spinner=False)
def fetch_spy_options_pc_ratio(expiry_date):
    """
    Fetch SPY options open interest from Polygon to calculate P/C ratio.
    SPY is used as a proxy for SPX market sentiment since SPXW doesn't have OI data.
    """
    try:
        exp_str = expiry_date.strftime("%Y-%m-%d")
        
        # Use snapshot endpoint (faster, returns OI directly)
        url = f"{POLYGON_BASE}/v3/snapshot/options/SPY"
        params = {
            "expiration_date": exp_str,
            "limit": 250,
            "apiKey": POLYGON_KEY
        }
        
        total_calls_oi = 0
        total_puts_oi = 0
        total_calls_vol = 0
        total_puts_vol = 0
        
        while True:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code != 200:
                break
            data = r.json()
            results = data.get("results", [])
            if not results:
                break
            
            for opt in results:
                details = opt.get("details", {})
                day = opt.get("day", {})
                
                contract_type = details.get("contract_type", "").upper()
                oi = day.get("open_interest", 0) or 0
                vol = day.get("volume", 0) or 0
                
                if contract_type == "CALL":
                    total_calls_oi += oi
                    total_calls_vol += vol
                elif contract_type == "PUT":
                    total_puts_oi += oi
                    total_puts_vol += vol
            
            # Check for pagination
            if "next_url" in data:
                url = data["next_url"]
                params = {"apiKey": POLYGON_KEY}
            else:
                break
        
        total_oi = total_calls_oi + total_puts_oi
        if total_oi > 0:
            pc_ratio = total_puts_oi / total_calls_oi if total_calls_oi > 0 else 1.0
            calls_pct = total_calls_oi / total_oi * 100
            puts_pct = total_puts_oi / total_oi * 100
            
            return {
                "calls_oi": total_calls_oi,
                "puts_oi": total_puts_oi,
                "calls_vol": total_calls_vol,
                "puts_vol": total_puts_vol,
                "pc_ratio": round(pc_ratio, 3),
                "calls_pct": round(calls_pct, 1),
                "puts_pct": round(puts_pct, 1),
                "calls_dominant": total_calls_oi > total_puts_oi,
                "puts_dominant": total_puts_oi > total_calls_oi,
                "source": "SPY"
            }
    except Exception as e:
        pass
    
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# OVERNIGHT SESSION EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════
def extract_session_data(es_candles, trading_date, offset=18.0):
    """Extract Sydney, Tokyo, London session highs/lows and overnight range"""
    if es_candles is None or es_candles.empty:
        return None
    
    result = {}
    
    # Convert to CT timezone
    df = es_candles.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize(ET).tz_convert(CT)
    else:
        df.index = df.index.tz_convert(CT)
    
    # Overnight starts evening before trading_date
    overnight_day = trading_date - timedelta(days=1)
    
    # Session times (CT) - adjusted for global markets
    sydney_start = CT.localize(datetime.combine(overnight_day, time(17, 0)))   # 5 PM CT
    sydney_end = CT.localize(datetime.combine(overnight_day, time(20, 30)))    # 8:30 PM CT
    tokyo_start = CT.localize(datetime.combine(overnight_day, time(21, 0)))    # 9 PM CT
    tokyo_end = CT.localize(datetime.combine(trading_date, time(1, 30)))       # 1:30 AM CT
    london_start = CT.localize(datetime.combine(trading_date, time(2, 0)))     # 2 AM CT
    london_end = CT.localize(datetime.combine(trading_date, time(4, 0)))       # 4 AM CT
    overnight_end = CT.localize(datetime.combine(trading_date, time(8, 30)))   # 8:30 AM CT (pre-RTH)
    
    # Extract session candles
    sydney = df[(df.index >= sydney_start) & (df.index <= sydney_end)]
    tokyo = df[(df.index >= tokyo_start) & (df.index <= tokyo_end)]
    london = df[(df.index >= london_start) & (df.index <= london_end)]
    overnight = df[(df.index >= sydney_start) & (df.index <= overnight_end)]
    
    # Sydney
    if not sydney.empty:
        result["sydney_high"] = round(float(sydney["High"].max()), 2)
        result["sydney_low"] = round(float(sydney["Low"].min()), 2)
    else:
        result["sydney_high"] = result["sydney_low"] = None
    
    # Tokyo
    if not tokyo.empty:
        result["tokyo_high"] = round(float(tokyo["High"].max()), 2)
        result["tokyo_low"] = round(float(tokyo["Low"].min()), 2)
    else:
        result["tokyo_high"] = result["tokyo_low"] = None
    
    # London
    if not london.empty:
        result["london_high"] = round(float(london["High"].max()), 2)
        result["london_low"] = round(float(london["Low"].min()), 2)
    else:
        result["london_high"] = result["london_low"] = None
    
    # Full overnight range
    if not overnight.empty:
        result["on_high"] = round(float(overnight["High"].max()), 2)
        result["on_low"] = round(float(overnight["Low"].min()), 2)
        
        # Find WHEN the high/low occurred (for slope calculation)
        high_idx = overnight["High"].idxmax()
        low_idx = overnight["Low"].idxmin()
        result["on_high_time"] = high_idx
        result["on_low_time"] = low_idx
    else:
        result["on_high"] = result["on_low"] = None
        result["on_high_time"] = result["on_low_time"] = None
    
    return result

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL DETERMINATION
# ═══════════════════════════════════════════════════════════════════════════════
def determine_channel(sydney_high, sydney_low, tokyo_high, tokyo_low):
    """
    Determine channel type based on Sydney vs Tokyo comparison:
    
    Tokyo High > Sydney High → ASCENDING
    Tokyo Low < Sydney Low → DESCENDING
    Both conditions → EXPANDING (trade cone boundaries)
    Neither condition → CONTRACTING (no trade)
    """
    if sydney_high is None or tokyo_high is None or sydney_low is None or tokyo_low is None:
        return "UNKNOWN", "Missing session data"
    
    ascending = tokyo_high > sydney_high
    descending = tokyo_low < sydney_low
    
    if ascending and descending:
        return "EXPANDING", f"Tokyo expanded BOTH directions: H {tokyo_high:.0f} > Syd H {sydney_high:.0f}, L {tokyo_low:.0f} < Syd L {sydney_low:.0f}"
    elif ascending:
        return "ASCENDING", f"Tokyo High ({tokyo_high:.0f}) > Sydney High ({sydney_high:.0f})"
    elif descending:
        return "DESCENDING", f"Tokyo Low ({tokyo_low:.0f}) < Sydney Low ({sydney_low:.0f})"
    else:
        return "CONTRACTING", f"Tokyo inside Sydney range - NO TRADE"

# ═══════════════════════════════════════════════════════════════════════════════
# CHANNEL LEVEL CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_channel_levels(on_high, on_high_time, on_low, on_low_time, ref_time, channel_type):
    """
    Calculate dynamic ceiling and floor levels based on channel type and time.
    Levels expand/contract at 0.48 pts per 30-min block.
    """
    blocks_from_high = blocks_between(on_high_time, ref_time) if on_high_time else 0
    blocks_from_low = blocks_between(on_low_time, ref_time) if on_low_time else 0
    
    expansion_high = blocks_from_high * SLOPE
    expansion_low = blocks_from_low * SLOPE
    
    if channel_type == "ASCENDING":
        # Rising channel: both levels rise
        ceiling = round(on_high + expansion_high, 2)
        floor = round(on_low + expansion_low, 2)
    elif channel_type == "DESCENDING":
        # Falling channel: both levels fall
        ceiling = round(on_high - expansion_high, 2)
        floor = round(on_low - expansion_low, 2)
    elif channel_type == "EXPANDING":
        # Expanding: ceiling rises, floor falls
        ceiling = round(on_high + expansion_high, 2)
        floor = round(on_low - expansion_low, 2)
    else:
        # Contracting or unknown: use static levels
        ceiling = on_high
        floor = on_low
    
    return {
        "ceiling": ceiling,
        "floor": floor,
        "blocks_high": blocks_from_high,
        "blocks_low": blocks_from_low,
        "expansion_high": expansion_high,
        "expansion_low": expansion_low
    }

# ═══════════════════════════════════════════════════════════════════════════════
# DETERMINE CURRENT POSITION
# ═══════════════════════════════════════════════════════════════════════════════
def determine_position(current_price, ceiling, floor):
    """Determine if current price is ABOVE, INSIDE, or BELOW the channel"""
    if current_price is None or ceiling is None or floor is None:
        return "UNKNOWN", 0
    
    if current_price > ceiling:
        return "ABOVE", round(current_price - ceiling, 2)
    elif current_price < floor:
        return "BELOW", round(floor - current_price, 2)
    else:
        # Inside - return distance to nearest edge
        dist_to_ceiling = ceiling - current_price
        dist_to_floor = current_price - floor
        return "INSIDE", round(min(dist_to_ceiling, dist_to_floor), 2)

# ═══════════════════════════════════════════════════════════════════════════════
# CALCULATE FLOW BIAS
# ═══════════════════════════════════════════════════════════════════════════════
def calculate_flow_bias(current_price, on_high, on_low, vix):
    """Calculate flow bias based on where price is within overnight range"""
    if on_high is None or on_low is None or current_price is None:
        return {"bias": "NEUTRAL", "strength": 0, "description": "Insufficient data"}
    
    on_range = on_high - on_low
    if on_range <= 0:
        return {"bias": "NEUTRAL", "strength": 0, "description": "No range"}
    
    # Where are we in the O/N range? 0 = at low, 1 = at high
    position_pct = (current_price - on_low) / on_range
    
    if position_pct >= 0.7:
        bias = "BULLISH"
        strength = min(100, int((position_pct - 0.5) * 200))
        desc = f"Near O/N high ({position_pct:.0%})"
    elif position_pct <= 0.3:
        bias = "BEARISH"
        strength = min(100, int((0.5 - position_pct) * 200))
        desc = f"Near O/N low ({position_pct:.0%})"
    else:
        bias = "NEUTRAL"
        strength = int(abs(position_pct - 0.5) * 100)
        desc = f"Mid-range ({position_pct:.0%})"
    
    return {"bias": bias, "strength": strength, "description": desc}

# ═══════════════════════════════════════════════════════════════════════════════
# SCENARIO GENERATION
# ═══════════════════════════════════════════════════════════════════════════════
def generate_scenarios(channel_type, ceiling_spx, floor_spx, current_spx, vix, hours_to_expiry, pc_data=None):
    """
    Generate all possible entry scenarios based on:
    - Channel type (Ascending/Descending/Expanding)
    - Current position (Above/Inside/Below)
    - P/C ratio (MM positioning)
    """
    scenarios = []
    
    # Get P/C data
    calls_dominant = pc_data.get("calls_dominant", False) if pc_data else False
    puts_dominant = pc_data.get("puts_dominant", False) if pc_data else False
    
    # Determine current position
    position, dist = determine_position(current_spx, ceiling_spx, floor_spx)
    
    channel_width = ceiling_spx - floor_spx if ceiling_spx and floor_spx else 0
    
    if channel_type == "ASCENDING":
        # ═══════════════════════════════════════════════════════════════════
        # ASCENDING CHANNEL SCENARIOS
        # ═══════════════════════════════════════════════════════════════════
        
        # Scenario 1: ABOVE channel - normal drop to ceiling for CALLS
        scenarios.append({
            "id": "asc_above_calls",
            "open_position": "ABOVE Channel",
            "condition": "Price drops to ceiling",
            "entry_level": ceiling_spx,
            "direction": "CALLS",
            "target": None,
            "description": "Enter CALLS when price drops to touch ceiling",
            "highlighted": position == "ABOVE",
            "mm_scenario": False
        })
        
        # Scenario 2: ABOVE channel - if CALLS > PUTS (MM avoidance)
        if calls_dominant:
            scenarios.append({
                "id": "asc_above_mm",
                "open_position": "ABOVE Channel",
                "condition": "CALLS > PUTS - MM Manipulation",
                "entry_level": ceiling_spx,
                "direction": "PUTS",
                "target": floor_spx,
                "description": "MMs break ceiling down, use as resistance → PUTS to floor",
                "highlighted": position == "ABOVE" and calls_dominant,
                "mm_scenario": True
            })
        
        # Scenario 3: ABOVE channel - continues to floor
        scenarios.append({
            "id": "asc_above_floor",
            "open_position": "ABOVE Channel",
            "condition": "Price drops through to floor",
            "entry_level": floor_spx,
            "direction": "CALLS",
            "target": ceiling_spx,
            "description": "If price drops all the way to floor → CALLS targeting ceiling",
            "highlighted": False,
            "mm_scenario": False
        })
        
        # Scenario 4: INSIDE - breaks UP
        scenarios.append({
            "id": "asc_inside_up",
            "open_position": "INSIDE Channel",
            "condition": "Breaks UP through ceiling",
            "entry_level": ceiling_spx,
            "direction": "CALLS",
            "target": None,
            "description": "After breakout up, enter CALLS on retrace to ceiling",
            "highlighted": position == "INSIDE",
            "mm_scenario": False
        })
        
        # Scenario 5: INSIDE - breaks DOWN
        scenarios.append({
            "id": "asc_inside_down",
            "open_position": "INSIDE Channel",
            "condition": "Breaks DOWN through floor",
            "entry_level": floor_spx,
            "direction": "PUTS",
            "target": None,
            "description": "After breakdown, enter PUTS on rally back to floor",
            "highlighted": position == "INSIDE",
            "mm_scenario": False
        })
        
        # Scenario 6: INSIDE - touches floor, closes inside
        scenarios.append({
            "id": "asc_inside_floor_touch",
            "open_position": "INSIDE Channel",
            "condition": "Touches floor, closes inside",
            "entry_level": floor_spx,
            "direction": "CALLS",
            "target": ceiling_spx,
            "description": "CALLS at floor targeting ceiling (mean reversion)",
            "highlighted": position == "INSIDE",
            "mm_scenario": False
        })
        
        # Scenario 7: BELOW channel
        scenarios.append({
            "id": "asc_below",
            "open_position": "BELOW Channel",
            "condition": "Rally to floor, close below",
            "entry_level": floor_spx,
            "direction": "PUTS",
            "target": None,
            "description": "Enter PUTS when price rallies to floor and gets rejected",
            "highlighted": position == "BELOW",
            "mm_scenario": False
        })
    
    elif channel_type == "DESCENDING":
        # ═══════════════════════════════════════════════════════════════════
        # DESCENDING CHANNEL SCENARIOS (Vice Versa)
        # ═══════════════════════════════════════════════════════════════════
        
        # Scenario 1: BELOW channel - normal rally to floor for PUTS
        scenarios.append({
            "id": "desc_below_puts",
            "open_position": "BELOW Channel",
            "condition": "Price rallies to floor",
            "entry_level": floor_spx,
            "direction": "PUTS",
            "target": None,
            "description": "Enter PUTS when price rallies to touch floor",
            "highlighted": position == "BELOW",
            "mm_scenario": False
        })
        
        # Scenario 2: BELOW channel - if PUTS > CALLS (MM avoidance)
        if puts_dominant:
            scenarios.append({
                "id": "desc_below_mm",
                "open_position": "BELOW Channel",
                "condition": "PUTS > CALLS - MM Manipulation",
                "entry_level": floor_spx,
                "direction": "CALLS",
                "target": ceiling_spx,
                "description": "MMs break floor up, use as support → CALLS to ceiling",
                "highlighted": position == "BELOW" and puts_dominant,
                "mm_scenario": True
            })
        
        # Scenario 3: BELOW channel - continues to ceiling
        scenarios.append({
            "id": "desc_below_ceiling",
            "open_position": "BELOW Channel",
            "condition": "Price rallies through to ceiling",
            "entry_level": ceiling_spx,
            "direction": "PUTS",
            "target": floor_spx,
            "description": "If price rallies all the way to ceiling → PUTS targeting floor",
            "highlighted": False,
            "mm_scenario": False
        })
        
        # Scenario 4: INSIDE - breaks DOWN
        scenarios.append({
            "id": "desc_inside_down",
            "open_position": "INSIDE Channel",
            "condition": "Breaks DOWN through floor",
            "entry_level": floor_spx,
            "direction": "PUTS",
            "target": None,
            "description": "After breakdown, enter PUTS on retrace to floor",
            "highlighted": position == "INSIDE",
            "mm_scenario": False
        })
        
        # Scenario 5: INSIDE - breaks UP
        scenarios.append({
            "id": "desc_inside_up",
            "open_position": "INSIDE Channel",
            "condition": "Breaks UP through ceiling",
            "entry_level": ceiling_spx,
            "direction": "CALLS",
            "target": None,
            "description": "After breakout, enter CALLS on drop back to ceiling",
            "highlighted": position == "INSIDE",
            "mm_scenario": False
        })
        
        # Scenario 6: INSIDE - touches ceiling, closes inside
        scenarios.append({
            "id": "desc_inside_ceiling_touch",
            "open_position": "INSIDE Channel",
            "condition": "Touches ceiling, closes inside",
            "entry_level": ceiling_spx,
            "direction": "PUTS",
            "target": floor_spx,
            "description": "PUTS at ceiling targeting floor (mean reversion)",
            "highlighted": position == "INSIDE",
            "mm_scenario": False
        })
        
        # Scenario 7: ABOVE channel
        scenarios.append({
            "id": "desc_above",
            "open_position": "ABOVE Channel",
            "condition": "Drop to ceiling, close above",
            "entry_level": ceiling_spx,
            "direction": "CALLS",
            "target": None,
            "description": "Enter CALLS when price drops to ceiling and holds",
            "highlighted": position == "ABOVE",
            "mm_scenario": False
        })
    
    elif channel_type == "EXPANDING":
        # ═══════════════════════════════════════════════════════════════════
        # EXPANDING CHANNEL - Trade Cone Boundaries
        # ═══════════════════════════════════════════════════════════════════
        scenarios.append({
            "id": "exp_ceiling",
            "open_position": "Any",
            "condition": "Price reaches ceiling",
            "entry_level": ceiling_spx,
            "direction": "PUTS",
            "target": floor_spx,
            "description": "Fade at ceiling → PUTS targeting floor",
            "highlighted": position in ["ABOVE", "INSIDE"],
            "mm_scenario": False
        })
        
        scenarios.append({
            "id": "exp_floor",
            "open_position": "Any",
            "condition": "Price reaches floor",
            "entry_level": floor_spx,
            "direction": "CALLS",
            "target": ceiling_spx,
            "description": "Fade at floor → CALLS targeting ceiling",
            "highlighted": position in ["BELOW", "INSIDE"],
            "mm_scenario": False
        })
    
    # Add strike and premium info to each scenario
    for s in scenarios:
        opt_type = "CALL" if s["direction"] == "CALLS" else "PUT"
        s["strike"] = get_strike(s["entry_level"], opt_type)
        s["premium"] = estimate_premium(s["entry_level"], s["strike"], opt_type, vix, hours_to_expiry)
        
        if s["target"]:
            s["target_premium"] = estimate_premium(s["target"], s["strike"], opt_type, vix, max(hours_to_expiry - 2, 0.5))
            s["profit_pct"] = round((s["target_premium"] - s["premium"]) / s["premium"] * 100, 0) if s["premium"] > 0 else 0
        else:
            s["target_premium"] = None
            s["profit_pct"] = None
        
        # Distance from current price to entry
        s["distance"] = round(abs(current_spx - s["entry_level"]), 2) if current_spx else None
    
    return scenarios, position, dist

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    st.markdown(STYLES, unsafe_allow_html=True)
    
    now = now_ct()
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ═══════════════════════════════════════════════════════════════════════════
    with st.sidebar:
        st.markdown("## 🔮 SPX Prophet V8")
        st.markdown("*Complete Trading System*")
        
        st.markdown("---")
        
        trading_date = st.date_input("📅 Trading Date", value=date.today())
        
        # Offset with persistence
        if "offset" not in st.session_state:
            st.session_state.offset = 18.0
        
        offset = st.number_input("⚙️ ES→SPX Offset", value=st.session_state.offset, step=0.5, 
                                 help="SPX = ES - Offset (typically 15-22)")
        if offset != st.session_state.offset:
            st.session_state.offset = offset
        
        st.markdown("---")
        st.markdown("### 📝 Manual Overrides")
        
        override_es = st.checkbox("Override ES Price")
        manual_es = st.number_input("ES Price", value=6100.0, step=0.25) if override_es else None
        
        override_sessions = st.checkbox("Override Session Data")
        if override_sessions:
            col1, col2 = st.columns(2)
            sydney_high = col1.number_input("Sydney High", value=6100.0, step=0.5)
            sydney_low = col2.number_input("Sydney Low", value=6070.0, step=0.5)
            tokyo_high = col1.number_input("Tokyo High", value=6110.0, step=0.5)
            tokyo_low = col2.number_input("Tokyo Low", value=6065.0, step=0.5)
        else:
            sydney_high = sydney_low = tokyo_high = tokyo_low = None
        
        st.markdown("---")
        auto_refresh = st.checkbox("🔄 Auto Refresh (30s)", value=False)
        show_debug = st.checkbox("🐛 Show Debug Info", value=False)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DATA FETCHING
    # ═══════════════════════════════════════════════════════════════════════════
    with st.spinner("Loading market data..."):
        # ES Candles and current price
        es_candles = fetch_es_candles(7)
        es_price = manual_es if override_es and manual_es else fetch_es_current()
        
        # SPX and VIX from Polygon
        spx_price = fetch_spx_polygon()
        vix = fetch_vix_polygon() or 16.0
        
        # SPY Options P/C Ratio
        pc_data = fetch_spy_options_pc_ratio(trading_date)
        
        # Extract session data
        if override_sessions:
            session_data = {
                "sydney_high": sydney_high,
                "sydney_low": sydney_low,
                "tokyo_high": tokyo_high,
                "tokyo_low": tokyo_low,
                "on_high": max(sydney_high, tokyo_high),
                "on_low": min(sydney_low, tokyo_low),
                "on_high_time": CT.localize(datetime.combine(trading_date - timedelta(days=1), time(22, 0))),
                "on_low_time": CT.localize(datetime.combine(trading_date, time(2, 0)))
            }
        else:
            session_data = extract_session_data(es_candles, trading_date, offset)
    
    # Fallbacks for ES/SPX
    if es_price is None:
        if spx_price:
            es_price = round(spx_price + offset, 2)
        else:
            st.warning("⚠️ Could not fetch ES price. Please enable manual override.")
            es_price = 6100
    
    if spx_price is None:
        spx_price = round(es_price - offset, 2)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CALCULATIONS
    # ═══════════════════════════════════════════════════════════════════════════
    channel_type = "UNKNOWN"
    channel_reason = "Missing data"
    ceiling_es = floor_es = ceiling_spx = floor_spx = None
    
    if session_data:
        sydney_h = session_data.get("sydney_high")
        sydney_l = session_data.get("sydney_low")
        tokyo_h = session_data.get("tokyo_high")
        tokyo_l = session_data.get("tokyo_low")
        on_high = session_data.get("on_high")
        on_low = session_data.get("on_low")
        on_high_time = session_data.get("on_high_time")
        on_low_time = session_data.get("on_low_time")
        
        # Determine channel type
        channel_type, channel_reason = determine_channel(sydney_h, sydney_l, tokyo_h, tokyo_l)
        
        # Calculate dynamic levels at current time
        ref_time = now if now.date() == trading_date else CT.localize(datetime.combine(trading_date, time(9, 0)))
        levels = calculate_channel_levels(on_high, on_high_time, on_low, on_low_time, ref_time, channel_type)
        
        ceiling_es = levels["ceiling"]
        floor_es = levels["floor"]
        ceiling_spx = round(ceiling_es - offset, 2) if ceiling_es else None
        floor_spx = round(floor_es - offset, 2) if floor_es else None
    
    # Hours to expiry
    expiry_time = CT.localize(datetime.combine(trading_date, time(15, 0)))
    hours_to_expiry = max(0.5, (expiry_time - now).total_seconds() / 3600)
    
    # Flow bias
    flow = calculate_flow_bias(es_price, session_data.get("on_high") if session_data else None,
                               session_data.get("on_low") if session_data else None, vix)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # HERO BANNER
    # ═══════════════════════════════════════════════════════════════════════════
    channel_class = channel_type.lower() if channel_type in ["ASCENDING", "DESCENDING", "EXPANDING", "CONTRACTING"] else ""
    is_live = trading_date == date.today()
    live_indicator = '<span class="live-dot"></span>LIVE' if is_live else '📅 ' + trading_date.strftime("%b %d")
    
    st.markdown(f'''<div class="hero">
<div class="hero-title">🔮 SPX Prophet V8</div>
<div class="hero-sub">ES: {es_price:,.2f} | Offset: {offset:+.1f} | VIX: {vix:.1f} | {live_indicator}</div>
<div class="hero-price">{spx_price:,.2f}</div>
<div style="margin-top:12px"><span class="channel-badge {channel_class}">{channel_type}</span></div>
<div style="font-size:11px;color:rgba(255,255,255,0.5);margin-top:8px">{trading_date.strftime("%A, %B %d, %Y")} | {hours_to_expiry:.1f}h to expiry</div>
</div>''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SESSION DATA
    # ═══════════════════════════════════════════════════════════════════════════
    if session_data and sydney_h:
        st.markdown("### 📊 Overnight Sessions")
        
        st.markdown(f'''<div class="session-grid">
<div class="session-box">
<div class="session-name">🌏 Sydney</div>
<div class="session-values">
<div class="session-value"><span>High</span><span class="high-val">{sydney_h:,.2f}</span></div>
<div class="session-value"><span>Low</span><span class="low-val">{sydney_l:,.2f}</span></div>
</div>
</div>
<div class="session-box">
<div class="session-name">🗼 Tokyo</div>
<div class="session-values">
<div class="session-value"><span>High</span><span class="high-val">{tokyo_h:,.2f}</span></div>
<div class="session-value"><span>Low</span><span class="low-val">{tokyo_l:,.2f}</span></div>
</div>
</div>
<div class="session-box">
<div class="session-name">📈 O/N High</div>
<div class="session-values">
<div class="session-value"><span>ES</span><span class="high-val">{on_high:,.2f}</span></div>
<div class="session-value"><span>SPX</span><span class="high-val">{round(on_high - offset, 2):,.2f}</span></div>
</div>
</div>
<div class="session-box">
<div class="session-name">📉 O/N Low</div>
<div class="session-values">
<div class="session-value"><span>ES</span><span class="low-val">{on_low:,.2f}</span></div>
<div class="session-value"><span>SPX</span><span class="low-val">{round(on_low - offset, 2):,.2f}</span></div>
</div>
</div>
</div>''', unsafe_allow_html=True)
        
        st.markdown(f'<div style="font-size:12px;color:rgba(255,255,255,0.5);margin-top:8px;text-align:center">{channel_reason}</div>', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CHANNEL LEVELS & CURRENT POSITION
    # ═══════════════════════════════════════════════════════════════════════════
    if ceiling_es and floor_es:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 📐 Channel Levels")
            st.markdown(f'''<div class="level-grid">
<div class="level-box">
<div class="level-label">Ceiling</div>
<div class="level-value" style="color:var(--green)">{ceiling_spx:,.2f}</div>
<div style="font-size:11px;color:var(--text2);margin-top:4px">ES: {ceiling_es:,.2f}</div>
</div>
<div class="level-box">
<div class="level-label">Floor</div>
<div class="level-value" style="color:var(--red)">{floor_spx:,.2f}</div>
<div style="font-size:11px;color:var(--text2);margin-top:4px">ES: {floor_es:,.2f}</div>
</div>
</div>''', unsafe_allow_html=True)
        
        with col2:
            # Current position
            position, dist = determine_position(spx_price, ceiling_spx, floor_spx)
            pos_color = "var(--green)" if position == "ABOVE" else "var(--red)" if position == "BELOW" else "var(--amber)"
            
            st.markdown("### 📍 Position")
            st.markdown(f'''<div class="current-pos">
<div class="current-pos-title">Current Position</div>
<div class="current-pos-value" style="color:{pos_color}">{position}</div>
<div style="font-size:12px;color:var(--text2);margin-top:6px">{dist:.2f} pts from edge</div>
</div>''', unsafe_allow_html=True)
            
            # Flow indicator
            flow_class = "flow-bullish" if flow["bias"] == "BULLISH" else "flow-bearish" if flow["bias"] == "BEARISH" else "flow-neutral"
            st.markdown(f'''<div class="flow-indicator {flow_class}">
{"📈" if flow["bias"] == "BULLISH" else "📉" if flow["bias"] == "BEARISH" else "➡️"} {flow["bias"]} Flow
</div>
<div style="font-size:11px;color:var(--text2);margin-top:4px">{flow["description"]}</div>''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # PUT/CALL RATIO (SPY-based)
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### 📊 Put/Call Open Interest (SPY)")
    
    if pc_data:
        calls_pct = pc_data["calls_pct"]
        puts_pct = pc_data["puts_pct"]
        dominant = "CALLS" if pc_data["calls_dominant"] else "PUTS" if pc_data["puts_dominant"] else "NEUTRAL"
        dominant_color = "var(--green)" if dominant == "CALLS" else "var(--red)" if dominant == "PUTS" else "var(--amber)"
        
        # MM implication
        if pc_data["calls_dominant"]:
            mm_msg = "⚠️ MMs short CALLS → May push price DOWN to avoid paying"
        elif pc_data["puts_dominant"]:
            mm_msg = "⚠️ MMs short PUTS → May push price UP to avoid paying"
        else:
            mm_msg = "Balanced positioning"
        
        st.markdown(f'''<div class="pc-ratio">
<div style="font-size:13px;font-weight:600;min-width:100px">P/C: {pc_data["pc_ratio"]:.2f}</div>
<div class="pc-bar">
<div class="pc-calls" style="width:{calls_pct}%">CALLS {calls_pct:.0f}%</div>
<div class="pc-puts" style="width:{puts_pct}%">PUTS {puts_pct:.0f}%</div>
</div>
<div style="font-size:12px;font-weight:600;color:{dominant_color}">{dominant}</div>
</div>
<div style="font-size:11px;color:var(--text2);margin-top:8px">
{mm_msg}<br>
Calls OI: {pc_data["calls_oi"]:,} | Puts OI: {pc_data["puts_oi"]:,}
</div>''', unsafe_allow_html=True)
    else:
        st.info("📊 SPY options data not available. Using neutral assumptions.")
        pc_data = {"calls_dominant": False, "puts_dominant": False}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ENTRY SCENARIOS
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### 🎯 Entry Scenarios")
    
    if channel_type == "CONTRACTING":
        st.markdown('''<div class="no-trade">
<div class="no-trade-icon">⚠️</div>
<div class="no-trade-text"><strong>NO TRADE</strong> - Contracting Channel</div>
<div style="font-size:12px;color:var(--text2);margin-top:8px">Tokyo range is inside Sydney range. Price is consolidating - wait for clearer direction.</div>
</div>''', unsafe_allow_html=True)
    
    elif channel_type == "UNKNOWN" or ceiling_spx is None:
        st.warning("Cannot generate scenarios without session data. Please use manual overrides in sidebar.")
    
    else:
        scenarios, position, dist = generate_scenarios(
            channel_type, ceiling_spx, floor_spx, spx_price, vix, hours_to_expiry, pc_data
        )
        
        # Show position-relevant scenarios first
        highlighted = [s for s in scenarios if s.get("highlighted")]
        others = [s for s in scenarios if not s.get("highlighted")]
        
        if highlighted:
            st.markdown(f"**📍 Based on current position ({position}):**")
        
        for s in (highlighted + others):
            direction_class = "calls" if s["direction"] == "CALLS" else "puts"
            badge_class = "calls-badge" if s["direction"] == "CALLS" else "puts-badge"
            highlight_class = "highlighted" if s.get("highlighted") else ""
            mm_badge = '<span class="mm-badge">MM SCENARIO</span>' if s.get("mm_scenario") else ""
            
            target_html = ""
            if s.get("target"):
                target_html = f'''<div class="scenario-detail">
<div class="scenario-detail-label">Target</div>
<div class="scenario-detail-value">{s["target"]:,.2f}</div>
</div>'''
            
            profit_html = ""
            if s.get("profit_pct"):
                profit_color = "var(--green)" if s["profit_pct"] > 0 else "var(--red)"
                profit_html = f'''<div class="scenario-detail">
<div class="scenario-detail-label">Est. P/L</div>
<div class="scenario-detail-value" style="color:{profit_color}">{s["profit_pct"]:+.0f}%</div>
</div>'''
            
            distance_html = ""
            if s.get("distance") is not None:
                distance_html = f'''<div class="scenario-detail">
<div class="scenario-detail-label">Distance</div>
<div class="scenario-detail-value">{s["distance"]:.1f} pts</div>
</div>'''
            
            st.markdown(f'''<div class="scenario-card {direction_class} {highlight_class}">
<div class="scenario-header">
<div>
<div class="scenario-title">{s["open_position"]} → {s["condition"]}{mm_badge}</div>
<div style="font-size:11px;color:var(--text2);margin-top:2px">{s["description"]}</div>
</div>
<span class="scenario-badge {badge_class}">{s["direction"]}</span>
</div>
<div class="scenario-details">
<div class="scenario-detail">
<div class="scenario-detail-label">Entry</div>
<div class="scenario-detail-value">{s["entry_level"]:,.2f}</div>
</div>
<div class="scenario-detail">
<div class="scenario-detail-label">Strike</div>
<div class="scenario-detail-value">{s["strike"]}</div>
</div>
<div class="scenario-detail">
<div class="scenario-detail-label">Premium</div>
<div class="scenario-detail-value">${s["premium"]:.2f}</div>
</div>
{distance_html or target_html}
{profit_html}
</div>
</div>''', unsafe_allow_html=True)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DEBUG INFO
    # ═══════════════════════════════════════════════════════════════════════════
    if show_debug:
        with st.expander("🐛 Debug Information"):
            st.write("**Session Data:**")
            st.json(session_data if session_data else {})
            
            st.write("**P/C Data:**")
            st.json(pc_data if pc_data else {})
            
            st.write("**Levels:**")
            st.write(f"- Ceiling ES: {ceiling_es}, SPX: {ceiling_spx}")
            st.write(f"- Floor ES: {floor_es}, SPX: {floor_spx}")
            st.write(f"- Channel Type: {channel_type}")
            
            st.write("**Timing:**")
            st.write(f"- Current CT: {now}")
            st.write(f"- Hours to Expiry: {hours_to_expiry:.2f}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown(f'''<div class="footer">
🔮 SPX Prophet V8 | Complete Trading System<br>
<span style="font-size:10px">Sydney/Tokyo Channel • SPY P/C Ratio • MM Positioning • All Entry Scenarios</span>
</div>''', unsafe_allow_html=True)
    
    # Auto refresh
    if auto_refresh and is_live:
        time_module.sleep(30)
        st.rerun()

if __name__ == "__main__":
    main()
