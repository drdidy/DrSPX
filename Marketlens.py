"""
SPX PROPHET v7.0 - INSTITUTIONAL EDITION
"Where Structure Becomes Foresight"

FIXES:
✓ Holiday/Half-Day handling - Correctly anchors to truncated session (Dec 24 = 12pm CT close)
✓ Clear trade setups - Shows ALL CALLS & PUTS with entries, strikes, profit projections
✓ Legendary UI - Glassmorphism, institutional-grade design
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import numpy as np
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional
import pytz

# Configuration
POLYGON_API_KEY = "jrbBZ2y12cJAOp2Buqtlay0TdprcTDIm"
POLYGON_BASE = "https://api.polygon.io"
CT_TZ = pytz.timezone('America/Chicago')
ET_TZ = pytz.timezone('America/New_York')

SLOPE_PER_30MIN = 0.45
MIN_CONE_WIDTH = 18.0
STOP_LOSS_PTS = 6.0
RAIL_PROXIMITY = 5.0
OTM_DISTANCE_PTS = 15
PREMIUM_SWEET_LOW = 4.00
PREMIUM_SWEET_HIGH = 8.00
DELTA_IDEAL = 0.30
VIX_TO_SPX_MULTIPLIER = 175

INST_WINDOW_START = time(9, 0)
INST_WINDOW_END = time(9, 30)
ENTRY_TARGET = time(9, 10)
CUTOFF_TIME = time(11, 30)
REGULAR_CLOSE = time(16, 0)
HALF_DAY_CLOSE = time(12, 0)

HOLIDAYS_2025 = {
    date(2025, 1, 1): "New Year's Day",
    date(2025, 1, 20): "MLK Day",
    date(2025, 2, 17): "Presidents Day",
    date(2025, 4, 18): "Good Friday",
    date(2025, 5, 26): "Memorial Day",
    date(2025, 6, 19): "Juneteenth",
    date(2025, 7, 4): "Independence Day",
    date(2025, 9, 1): "Labor Day",
    date(2025, 11, 27): "Thanksgiving",
    date(2025, 12, 25): "Christmas",  # Thursday Dec 25, 2025
}
HALF_DAYS_2025 = {
    date(2025, 7, 3): "Day before July 4th",
    date(2025, 11, 26): "Day before Thanksgiving",
    date(2025, 11, 28): "Day after Thanksgiving",
    date(2025, 12, 24): "Christmas Eve",  # Wednesday Dec 24, 2025 - closes 12pm CT
}

# 2026 Holidays and Half-Days
HOLIDAYS_2026 = {
    date(2026, 1, 1): "New Year's Day",  # Thursday Jan 1, 2026
    date(2026, 1, 19): "MLK Day",
    date(2026, 2, 16): "Presidents Day",
    date(2026, 4, 3): "Good Friday",
    date(2026, 5, 25): "Memorial Day",
    date(2026, 6, 19): "Juneteenth",
    date(2026, 7, 3): "Independence Day (observed)",  # July 4 is Saturday, observed Friday
    date(2026, 9, 7): "Labor Day",
    date(2026, 11, 26): "Thanksgiving",
    date(2026, 12, 25): "Christmas",  # Friday Dec 25, 2026
}
HALF_DAYS_2026 = {
    date(2025, 12, 31): "New Year's Eve",  # Wednesday Dec 31, 2025 - closes 12pm CT (for Jan 1, 2026)
    date(2026, 7, 2): "Day before July 4th (observed)",
    date(2026, 11, 25): "Day before Thanksgiving",
    date(2026, 11, 27): "Day after Thanksgiving",
    date(2026, 12, 24): "Christmas Eve",  # Thursday Dec 24, 2026 - closes 12pm CT
}

@dataclass
class VIXZone:
    bottom: float = 0.0
    top: float = 0.0
    current: float = 0.0
    zone_size: float = 0.0
    position_pct: float = 50.0
    zones_away: int = 0
    expected_spx_move: float = 0.0
    bias: str = "WAIT"
    bias_reason: str = ""
    matched_rail: float = 0.0
    matched_cone: str = ""
    # Breakout detection
    is_breakout: bool = False
    breakout_direction: str = ""  # "ABOVE", "BELOW"
    breakout_level: float = 0.0   # The level it broke out from (spring/resistance)
    distance_to_boundary: float = 0.0  # How close to breaking out

@dataclass
class GapAnalysis:
    """Overnight gap analysis for 0DTE edge"""
    prior_close: float = 0.0
    open_price: float = 0.0
    gap_points: float = 0.0
    gap_pct: float = 0.0
    gap_direction: str = "FLAT"  # "UP", "DOWN", "FLAT"
    gap_size: str = "NONE"  # "SMALL" (<0.3%), "MEDIUM" (0.3-0.7%), "LARGE" (>0.7%)
    trade_bias: str = "NEUTRAL"  # What the gap suggests
    trade_reason: str = ""

@dataclass
class Confluence:
    """VIX + MA Bias confluence scoring"""
    vix_bias: str = "WAIT"
    ma_bias: str = "NEUTRAL"
    gap_bias: str = "NEUTRAL"
    is_aligned: bool = False
    alignment_score: int = 0  # 0 to 40
    signal_strength: str = "WEAK"  # "WEAK", "MODERATE", "STRONG", "CONFLICT"
    recommendation: str = ""
    no_trade: bool = False
    no_trade_reason: str = ""
    
@dataclass
class MarketContext:
    """Overall market context for the day"""
    prior_day_range: float = 0.0
    avg_daily_range: float = 0.0  # 10-day ATR
    prior_day_type: str = "NORMAL"  # "TREND", "RANGE", "NORMAL"
    vix_level: str = "NORMAL"  # "LOW" (<14), "NORMAL" (14-20), "ELEVATED" (20-25), "HIGH" (>25)
    recommended_stop: float = 6.0  # Dynamic based on VIX
    is_prime_time: bool = False  # 9:00-10:30 AM
    time_warning: str = ""

@dataclass
class Pivot:
    name: str = ""
    price: float = 0.0
    pivot_time: datetime = None
    pivot_type: str = ""
    is_secondary: bool = False
    candle_high: float = 0.0
    candle_open: float = 0.0

@dataclass
class Cone:
    name: str = ""
    pivot: Pivot = None
    ascending_rail: float = 0.0
    descending_rail: float = 0.0
    width: float = 0.0
    blocks: int = 0
    is_tradeable: bool = True

@dataclass
class OptionData:
    spy_strike: float = 0.0
    spy_price: float = 0.0
    spy_delta: float = 0.0
    spx_strike: int = 0
    spx_price_est: float = 0.0
    otm_distance: float = 0.0
    in_sweet_spot: bool = False

@dataclass
class TradeSetup:
    direction: str = ""
    cone_name: str = ""
    cone_width: float = 0.0
    entry: float = 0.0
    stop: float = 0.0
    target_25: float = 0.0
    target_50: float = 0.0
    target_75: float = 0.0
    target_100: float = 0.0
    distance: float = 0.0
    option: OptionData = None
    profit_25: float = 0.0
    profit_50: float = 0.0
    profit_75: float = 0.0
    profit_100: float = 0.0
    risk_dollars: float = 0.0
    status: str = "WAIT"

@dataclass
class MABias:
    """Moving Average Bias Filter - 30min timeframe"""
    sma200: float = 0.0           # 200-period SMA
    ema50: float = 0.0            # 50-period EMA
    current_close: float = 0.0    # Latest 30-min close
    
    # Directional permission
    price_vs_sma200: str = "NEUTRAL"  # "ABOVE" = long-only, "BELOW" = short-only, "NEUTRAL" = ranging
    
    # Trend health
    ema_vs_sma: str = "NEUTRAL"   # "BULLISH" (EMA50 > SMA200), "BEARISH" (EMA50 < SMA200)
    
    # Final bias
    bias: str = "NEUTRAL"         # "LONG", "SHORT", "NEUTRAL"
    bias_reason: str = ""
    
    # Regime warning
    regime_warning: str = ""      # Warning about recent MA crosses

@dataclass
class DayScore:
    total: int = 0
    grade: str = ""
    color: str = ""

@dataclass
class PivotTableRow:
    time_block: str = ""
    time_ct: time = None
    prior_high_asc: float = 0.0
    prior_high_desc: float = 0.0
    prior_low_asc: float = 0.0
    prior_low_desc: float = 0.0
    prior_close_asc: float = 0.0
    prior_close_desc: float = 0.0

@dataclass
class PriceProximity:
    """Analyzes current price position relative to structural cones"""
    current_price: float = 0.0
    
    # Position relative to all cones
    position: str = "UNKNOWN"  # "ABOVE_ALL", "BELOW_ALL", "INSIDE_CONE", "NEAR_RAIL", "BETWEEN_CONES"
    position_detail: str = ""  # Human-readable description
    
    # Nearest rail info
    nearest_rail: float = 0.0
    nearest_rail_name: str = ""  # e.g., "Prior High ascending"
    nearest_rail_type: str = ""  # "ascending" or "descending"
    nearest_rail_distance: float = 0.0  # Positive = above, Negative = below
    nearest_cone_name: str = ""
    
    # If inside a cone
    inside_cone: bool = False
    inside_cone_name: str = ""
    
    # Action guidance
    action: str = ""  # What to do: "WAIT_FOR_PULLBACK", "WAIT_FOR_RALLY", "WATCH_FOR_ENTRY", "INSIDE_WAIT"
    action_detail: str = ""  # Specific instruction
    
    # All rail distances for table display
    rail_distances: Dict = None  # {cone_name: {"asc": dist, "desc": dist}}

def get_ct_now():
    return datetime.now(CT_TZ)

def is_holiday(d):
    return d in HOLIDAYS_2025 or d in HOLIDAYS_2026

def is_half_day(d):
    return d in HALF_DAYS_2025 or d in HALF_DAYS_2026

def get_market_close_time(d):
    return HALF_DAY_CLOSE if is_half_day(d) else REGULAR_CLOSE

def get_session_info(d):
    if is_holiday(d):
        return {"is_trading": False, "reason": HOLIDAYS_2025.get(d) or HOLIDAYS_2026.get(d, "Holiday")}
    return {"is_trading": True, "is_half_day": is_half_day(d), "close_ct": get_market_close_time(d),
            "reason": HALF_DAYS_2025.get(d) or HALF_DAYS_2026.get(d, "") if is_half_day(d) else ""}

def get_next_trading_day(from_date=None):
    if from_date is None:
        now = get_ct_now()
        from_date = now.date()
        if now.time() > get_market_close_time(from_date):
            from_date += timedelta(days=1)
    next_day = from_date
    while next_day.weekday() >= 5 or is_holiday(next_day):
        next_day += timedelta(days=1)
    return next_day

def get_prior_trading_day(from_date):
    prior = from_date - timedelta(days=1)
    while prior.weekday() >= 5 or is_holiday(prior):
        prior -= timedelta(days=1)
    return prior

def get_time_until(target, from_dt=None, trading_date=None):
    """
    Get time until target time on trading_date.
    If target time has passed today, count down to next trading day.
    """
    if from_dt is None:
        from_dt = get_ct_now()
    
    if trading_date is None:
        trading_date = from_dt.date()
    
    target_dt = CT_TZ.localize(datetime.combine(trading_date, target))
    
    # If target time has passed, use next trading day
    if target_dt <= from_dt:
        next_trade_day = get_next_trading_day(from_dt.date() + timedelta(days=1))
        target_dt = CT_TZ.localize(datetime.combine(next_trade_day, target))
    
    return target_dt - from_dt

def format_countdown(td):
    if td.total_seconds() <= 0:
        return "NOW"
    total_secs = int(td.total_seconds())
    hours, remainder = divmod(total_secs, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours >= 24:
        days = hours // 24
        hours = hours % 24
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"

def polygon_get(endpoint, params=None):
    try:
        if params is None:
            params = {}
        params["apiKey"] = POLYGON_API_KEY
        resp = requests.get(f"{POLYGON_BASE}{endpoint}", params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def polygon_get_daily_bars(ticker, from_date, to_date):
    data = polygon_get(f"/v2/aggs/ticker/{ticker}/range/1/day/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}", {"adjusted": "true", "sort": "asc"})
    return data.get("results", []) if data else []

def polygon_get_intraday_bars(ticker, from_date, to_date, multiplier=30):
    data = polygon_get(f"/v2/aggs/ticker/{ticker}/range/{multiplier}/minute/{from_date.strftime('%Y-%m-%d')}/{to_date.strftime('%Y-%m-%d')}", {"adjusted": "true", "sort": "asc", "limit": 5000})
    return data.get("results", []) if data else []

def fetch_es_ma_bias():
    """
    Fetch ES futures 30-min data from Yahoo Finance and calculate MA bias.
    ES runs ~23 hours/day so we get plenty of bars for 200 SMA.
    
    Uses 15 days of data to ensure 200+ valid bars even with gaps.
    """
    ma_bias = MABias()
    
    try:
        # Get 15 days of 30-min data (should give ~500+ bars)
        end_ts = int(datetime.now().timestamp())
        start_ts = end_ts - (15 * 24 * 60 * 60)  # 15 days back
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/ES=F?period1={start_ts}&period2={end_ts}&interval=30m"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            # Fallback: Try with SPY ETF as proxy
            ma_bias.bias = "NEUTRAL"
            ma_bias.bias_reason = "Data unavailable"
            return ma_bias
        
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            ma_bias.bias = "NEUTRAL"
            ma_bias.bias_reason = "No market data"
            return ma_bias
        
        quotes = result[0].get("indicators", {}).get("quote", [{}])[0]
        closes = quotes.get("close", [])
        
        # Filter out None values (market closed periods)
        closes = [c for c in closes if c is not None]
        
        if len(closes) < 200:
            ma_bias.bias = "NEUTRAL"
            ma_bias.bias_reason = f"Building data ({len(closes)}/200)"
            return ma_bias
        
        # Use only the most recent 200 bars for SMA calculation
        recent_closes = closes[-250:]  # Keep extra for cross detection
        current_close = recent_closes[-1]
        ma_bias.current_close = current_close
        
        # Calculate SMA200 using last 200 bars
        sma200_bars = recent_closes[-200:]
        ma_bias.sma200 = sum(sma200_bars) / 200
        
        # Calculate EMA50 properly (need to start from beginning for accuracy)
        ema50_seed = recent_closes[-100:]  # Use 100 bars to seed EMA
        multiplier = 2 / (50 + 1)
        ema = sum(ema50_seed[:50]) / 50  # Start with SMA of first 50
        for price in ema50_seed[50:]:
            ema = (price - ema) * multiplier + ema
        ma_bias.ema50 = ema
        
        # Calculate distances
        price_to_sma = ((current_close - ma_bias.sma200) / ma_bias.sma200) * 100
        ema_to_sma = ((ma_bias.ema50 - ma_bias.sma200) / ma_bias.sma200) * 100
        
        # Determine directional permission (price vs SMA200)
        if price_to_sma > 0.15:  # More than 0.15% above
            ma_bias.price_vs_sma200 = "ABOVE"
        elif price_to_sma < -0.15:  # More than 0.15% below
            ma_bias.price_vs_sma200 = "BELOW"
        else:
            ma_bias.price_vs_sma200 = "NEUTRAL"
        
        # Determine trend health (EMA50 vs SMA200)
        if ema_to_sma > 0.1:
            ma_bias.ema_vs_sma = "BULLISH"
        elif ema_to_sma < -0.1:
            ma_bias.ema_vs_sma = "BEARISH"
        else:
            ma_bias.ema_vs_sma = "NEUTRAL"
        
        # Check for recent SMA200 crosses (choppiness indicator)
        cross_count = 0
        check_bars = recent_closes[-20:]  # Last 20 bars
        for i in range(1, len(check_bars)):
            prev_above = check_bars[i-1] > ma_bias.sma200
            curr_above = check_bars[i] > ma_bias.sma200
            if prev_above != curr_above:
                cross_count += 1
        
        # Determine final bias with clear reasoning
        if cross_count >= 4:
            ma_bias.bias = "NEUTRAL"
            ma_bias.bias_reason = f"Choppy: {cross_count} MA crosses"
            ma_bias.regime_warning = "⚠️ Price whipsawing around SMA200"
        elif ma_bias.price_vs_sma200 == "ABOVE" and ma_bias.ema_vs_sma == "BULLISH":
            ma_bias.bias = "LONG"
            ma_bias.bias_reason = f"Uptrend: +{price_to_sma:.1f}% from SMA"
        elif ma_bias.price_vs_sma200 == "BELOW" and ma_bias.ema_vs_sma == "BEARISH":
            ma_bias.bias = "SHORT"
            ma_bias.bias_reason = f"Downtrend: {price_to_sma:.1f}% from SMA"
        elif ma_bias.price_vs_sma200 == "ABOVE" and ma_bias.ema_vs_sma != "BULLISH":
            ma_bias.bias = "NEUTRAL"
            ma_bias.bias_reason = "Trend weakening"
            ma_bias.regime_warning = "⚠️ EMA curling down"
        elif ma_bias.price_vs_sma200 == "BELOW" and ma_bias.ema_vs_sma != "BEARISH":
            ma_bias.bias = "NEUTRAL"
            ma_bias.bias_reason = "Potential reversal"
            ma_bias.regime_warning = "⚠️ EMA curling up"
        else:
            ma_bias.bias = "NEUTRAL"
            ma_bias.bias_reason = "Ranging market"
        
        return ma_bias
        
    except Exception as e:
        ma_bias.bias = "NEUTRAL"
        ma_bias.bias_reason = "Connection error"
        return ma_bias

def fetch_vix_current():
    """
    Fetch current VIX from Polygon (preferred) or Yahoo Finance (fallback).
    Returns tuple: (vix_value, source)
    """
    # Try Polygon first (more reliable for indices)
    try:
        data = polygon_get(f"/v2/aggs/ticker/I:VIX/prev")
        if data and data.get("results"):
            vix = data["results"][0].get("c", 0)
            if vix > 0:
                return (round(vix, 2), "polygon")
    except:
        pass
    
    # Fallback to Yahoo Finance
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=1d"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            if result:
                meta = result[0].get("meta", {})
                vix = meta.get("regularMarketPrice", 0)
                if vix > 0:
                    return (round(vix, 2), "yahoo")
    except:
        pass
    
    return (0.0, "none")

def fetch_vix_zone_auto():
    """
    Fetch VIX zone boundaries (overnight high/low) from Polygon.
    Returns tuple: (bottom, top, current)
    """
    try:
        # Get last 2 days of VIX data to find overnight range
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        data = polygon_get(f"/v2/aggs/ticker/I:VIX/range/1/day/{week_ago}/{today}", {"limit": 5, "sort": "desc"})
        
        if data and data.get("results") and len(data["results"]) >= 1:
            latest = data["results"][0]
            vix_high = latest.get("h", 0)
            vix_low = latest.get("l", 0)
            vix_close = latest.get("c", 0)
            
            if vix_high > 0 and vix_low > 0:
                return (round(vix_low, 2), round(vix_high, 2), round(vix_close, 2))
    except:
        pass
    
    return (0.0, 0.0, 0.0)

def analyze_gap(prior_close, current_price):
    """
    Analyze overnight gap for 0DTE trading edge.
    
    Gap Rules:
    - Gap UP into VIX at top → Fade (PUTS)
    - Gap DOWN into VIX at bottom → Fade (CALLS)  
    - Gap in direction of trend → Continuation
    """
    gap = GapAnalysis()
    gap.prior_close = prior_close
    gap.open_price = current_price
    
    if prior_close <= 0 or current_price <= 0:
        gap.trade_bias = "NEUTRAL"
        gap.trade_reason = "No gap data"
        return gap
    
    gap.gap_points = round(current_price - prior_close, 2)
    gap.gap_pct = round((gap.gap_points / prior_close) * 100, 3)
    
    # Determine gap direction
    if gap.gap_pct > 0.05:
        gap.gap_direction = "UP"
    elif gap.gap_pct < -0.05:
        gap.gap_direction = "DOWN"
    else:
        gap.gap_direction = "FLAT"
    
    # Determine gap size
    abs_pct = abs(gap.gap_pct)
    if abs_pct < 0.3:
        gap.gap_size = "SMALL"
    elif abs_pct < 0.7:
        gap.gap_size = "MEDIUM"
    else:
        gap.gap_size = "LARGE"
    
    # Trading bias based on gap
    # Large gaps tend to fill (fade them)
    # Small gaps in trend direction tend to continue
    if gap.gap_size == "LARGE":
        if gap.gap_direction == "UP":
            gap.trade_bias = "PUTS"
            gap.trade_reason = f"Large gap up (+{gap.gap_pct:.2f}%) → Fade"
        elif gap.gap_direction == "DOWN":
            gap.trade_bias = "CALLS"
            gap.trade_reason = f"Large gap down ({gap.gap_pct:.2f}%) → Fade"
    elif gap.gap_size == "MEDIUM":
        if gap.gap_direction == "UP":
            gap.trade_bias = "NEUTRAL"
            gap.trade_reason = f"Medium gap up (+{gap.gap_pct:.2f}%) → Wait for direction"
        elif gap.gap_direction == "DOWN":
            gap.trade_bias = "NEUTRAL"
            gap.trade_reason = f"Medium gap down ({gap.gap_pct:.2f}%) → Wait for direction"
    else:
        gap.trade_bias = "NEUTRAL"
        gap.trade_reason = f"Small/no gap ({gap.gap_pct:+.2f}%) → No edge"
    
    return gap

def calculate_confluence(vix_zone, ma_bias, gap_analysis=None):
    """
    Calculate confluence between VIX Zone and MA Bias.
    Gap is informational only, not part of scoring.
    
    New Scoring (40 pts max):
    - VIX + MA perfectly aligned: 40/40
    - VIX clear, MA neutral: 25/40
    - Both neutral: 15/40
    - VIX + MA CONFLICT: 0/40 + NO TRADE warning
    """
    conf = Confluence()
    conf.vix_bias = vix_zone.bias
    conf.ma_bias = ma_bias.bias if ma_bias else "NEUTRAL"
    conf.gap_bias = gap_analysis.trade_bias if gap_analysis else "NEUTRAL"
    
    # Convert to directional terms
    vix_direction = "LONG" if conf.vix_bias == "CALLS" else "SHORT" if conf.vix_bias == "PUTS" else "NEUTRAL"
    
    # Check for conflict first (most important)
    if vix_direction != "NEUTRAL" and conf.ma_bias != "NEUTRAL" and vix_direction != conf.ma_bias:
        # CONFLICT - VIX says one thing, MA says opposite
        conf.is_aligned = False
        conf.alignment_score = 0
        conf.signal_strength = "CONFLICT"
        conf.no_trade = True
        conf.no_trade_reason = f"VIX says {vix_direction}, MA says {conf.ma_bias}"
        conf.recommendation = "⛔ NO TRADE — Signals conflict"
    elif vix_direction != "NEUTRAL" and conf.ma_bias != "NEUTRAL" and vix_direction == conf.ma_bias:
        # PERFECT ALIGNMENT
        conf.is_aligned = True
        conf.alignment_score = 40
        conf.signal_strength = "STRONG"
        conf.no_trade = False
        breakout_note = " (BREAKOUT)" if vix_zone.is_breakout else ""
        conf.recommendation = f"✅ {vix_direction}{breakout_note} — Full confluence"
    elif vix_direction != "NEUTRAL":
        # VIX has signal, MA is neutral
        conf.is_aligned = False
        conf.alignment_score = 25
        conf.signal_strength = "MODERATE"
        conf.no_trade = False
        conf.recommendation = f"◐ {vix_direction} — VIX only, MA neutral"
    elif conf.ma_bias != "NEUTRAL":
        # MA has signal, VIX is neutral (mid-zone)
        conf.is_aligned = False
        conf.alignment_score = 15
        conf.signal_strength = "WEAK"
        conf.no_trade = False
        conf.recommendation = f"○ {conf.ma_bias} — MA only, VIX mid-zone"
    else:
        # Both neutral
        conf.is_aligned = False
        conf.alignment_score = 15
        conf.signal_strength = "WEAK"
        conf.no_trade = False
        conf.recommendation = "– No clear direction"
    
    return conf

def analyze_market_context(prior_session, vix_current, current_time_ct):
    """
    Analyze overall market context for the trading day.
    
    For 0DTE strategy:
    - Optimal: 9:00-10:00 AM (best risk/reward)
    - Good: 10:00-10:30 AM (still tradeable)
    - Late: 10:30-11:30 AM (reduced opportunity)
    - Very Late: After 11:30 (contracts too cheap, less edge)
    """
    ctx = MarketContext()
    
    # Prior day range
    if prior_session:
        ctx.prior_day_range = prior_session.get("high", 0) - prior_session.get("low", 0)
    
    # VIX level classification and dynamic stops
    if vix_current > 0:
        if vix_current < 14:
            ctx.vix_level = "LOW"
            ctx.recommended_stop = 4.0
        elif vix_current < 20:
            ctx.vix_level = "NORMAL"
            ctx.recommended_stop = 6.0
        elif vix_current < 25:
            ctx.vix_level = "ELEVATED"
            ctx.recommended_stop = 8.0
        else:
            ctx.vix_level = "HIGH"
            ctx.recommended_stop = 10.0
    
    # Prior day type
    if ctx.prior_day_range > 0:
        if ctx.prior_day_range > 50:
            ctx.prior_day_type = "TREND"
        elif ctx.prior_day_range < 25:
            ctx.prior_day_type = "RANGE"
        else:
            ctx.prior_day_type = "NORMAL"
    
    # Trading window assessment for 0DTE
    optimal_start = time(9, 0)
    optimal_end = time(10, 0)
    good_end = time(10, 30)
    late_end = time(11, 30)
    
    if current_time_ct < optimal_start:
        ctx.is_prime_time = False
        ctx.time_warning = "Pre-market"
    elif optimal_start <= current_time_ct <= optimal_end:
        ctx.is_prime_time = True
        ctx.time_warning = ""  # Optimal - no warning needed
    elif optimal_end < current_time_ct <= good_end:
        ctx.is_prime_time = False
        ctx.time_warning = "Good"
    elif good_end < current_time_ct <= late_end:
        ctx.is_prime_time = False
        ctx.time_warning = "Late entry"
    else:
        ctx.is_prime_time = False
        ctx.time_warning = "Very late"
    
    return ctx

def filter_bars_to_session(bars, session_date, close_time_ct):
    """CRITICAL FIX: Filter bars to session close time (handles half days)"""
    if not bars:
        return []
    close_hour_et = min(close_time_ct.hour + 1, 23)
    close_time_et = time(close_hour_et, close_time_ct.minute)
    session_start_et = time(9, 30)
    filtered = []
    for bar in bars:
        ts = bar.get("t", 0)
        if ts == 0:
            continue
        bar_dt_et = datetime.fromtimestamp(ts / 1000, tz=ET_TZ)
        bar_time_et = bar_dt_et.time()
        bar_date = bar_dt_et.date()
        if bar_date == session_date and session_start_et <= bar_time_et <= close_time_et:
            filtered.append(bar)
    return filtered

def polygon_get_index_price(ticker):
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    data = polygon_get(f"/v2/aggs/ticker/{ticker}/range/1/day/{week_ago}/{today}", {"limit": 5})
    if data and data.get("results"):
        return data["results"][-1].get("c", 0)
    return 0.0

def estimate_0dte_price(vix, otm_distance, hours_left, is_put=False, mins_after_open=30):
    """
    Estimate SPX 0DTE option price based on real trade data.
    
    CALIBRATION DATA (David's actual trades):
    - VIX 15.11, 15 OTM, 8:30 AM: $7.40 → 9:10 AM: $3.90 (47% drop)
    - VIX 17.53, 15 OTM, 8:30 AM: $5.80 → 9:10 AM: $3.60 (38% drop)
    - VIX 16.52, 15 OTM, 10:00 AM: $2.25
    
    Sweet spot entry: 9:00-10:00 AM at $3-$5 range
    """
    if vix <= 0:
        vix = 16
    
    # STEP 1: Calculate base price at 8:30 AM
    # Base: $6.50 at VIX 15, 15 OTM
    base = 6.50
    
    # VIX adjustment: Higher VIX = higher premium
    # +$0.30 per VIX point from 12-16
    # +$0.50 per VIX point from 16-20
    # +$0.70 per VIX point above 20
    if vix <= 12:
        vix_adj = -1.20  # Low VIX = cheaper
    elif vix <= 16:
        vix_adj = (vix - 14) * 0.30
    elif vix <= 20:
        vix_adj = 0.60 + (vix - 16) * 0.50
    else:
        vix_adj = 2.60 + (vix - 20) * 0.70
    
    # OTM adjustment: Further OTM = cheaper
    # -$0.12 per point beyond 15 OTM
    if otm_distance <= 15:
        otm_adj = 0
    else:
        otm_adj = -(otm_distance - 15) * 0.12
    
    # Put premium: Puts slightly more expensive at high VIX
    if is_put and vix >= 18:
        put_adj = (vix - 18) * 0.15
    else:
        put_adj = 0
    
    # 8:30 AM price
    price_830 = max(1.0, base + vix_adj + otm_adj + put_adj)
    
    # STEP 2: Apply time decay based on entry time
    # Your data shows ~45% drop from 8:30 to 9:10 AM
    # And ~70% drop from 8:30 to 10:00 AM
    
    if mins_after_open <= 0:
        time_factor = 1.0
    elif mins_after_open <= 20:
        # 8:30-8:50: Initial spike period, prices volatile
        time_factor = 1.0 - (mins_after_open / 20) * 0.20
    elif mins_after_open <= 40:
        # 8:50-9:10: Retrace period - YOUR ENTRY ZONE
        time_factor = 0.80 - ((mins_after_open - 20) / 20) * 0.25
    elif mins_after_open <= 60:
        # 9:10-9:30: Post-retrace stabilization
        time_factor = 0.55 - ((mins_after_open - 40) / 20) * 0.10
    elif mins_after_open <= 90:
        # 9:30-10:00: Accelerating theta
        time_factor = 0.45 - ((mins_after_open - 60) / 30) * 0.12
    else:
        # 10:00+ AM: Heavy decay
        time_factor = max(0.20, 0.33 - ((mins_after_open - 90) / 60) * 0.10)
    
    # Higher VIX = premium holds better
    if vix > 16:
        vix_retention = 1 + (vix - 16) * 0.02
        time_factor = min(1.0, time_factor * vix_retention)
    
    price = price_830 * time_factor
    return max(0.50, round(price, 2))

def get_option_data_for_entry(entry_rail, opt_type, vix_current=16, mins_after_open=30):
    """Get option data for SPX contracts ~15 pts OTM from entry rail"""
    is_put = opt_type.upper() in ["P", "PUT", "PUTS"]
    
    if is_put:
        spx_strike = int(round((entry_rail - OTM_DISTANCE_PTS) / 5) * 5)
    else:
        spx_strike = int(round((entry_rail + OTM_DISTANCE_PTS) / 5) * 5)
    
    otm_distance = abs(spx_strike - entry_rail)
    
    # Calculate hours left based on entry time
    # 8:30 AM = 6.5 hrs, 9:00 AM = 6 hrs, 9:30 AM = 5.5 hrs, 10:00 AM = 5 hrs
    hours_left = 6.5 - (mins_after_open / 60)
    hours_left = max(0.5, hours_left)
    
    # Use calibrated pricing model with entry time
    spx_price = estimate_0dte_price(vix_current, otm_distance, hours_left, is_put, mins_after_open)
    spx_cost = spx_price * 100  # Total cost per contract
    
    # Sweet spot: $4-$7 is perfect, $3.50-$8 is acceptable
    in_sweet_spot = 4.0 <= spx_price <= 7.0
    
    # Estimate delta based on OTM distance
    if otm_distance <= 10:
        delta = 0.40
    elif otm_distance <= 15:
        delta = 0.30
    elif otm_distance <= 20:
        delta = 0.25
    else:
        delta = 0.20
    
    return OptionData(
        spy_strike=0, spy_price=0, spy_delta=delta,
        spx_strike=spx_strike, spx_price_est=spx_price,
        otm_distance=round(otm_distance, 1),
        in_sweet_spot=in_sweet_spot
    )

def detect_pivots_auto(bars, pivot_date, close_time_ct):
    """Auto-detect pivots with FALLBACK to session high/low if patterns not found"""
    if not bars:
        return []
    filtered_bars = filter_bars_to_session(bars, pivot_date, close_time_ct)
    if not filtered_bars or len(filtered_bars) < 2:
        return []
    
    pivots = []
    candles = []
    for bar in filtered_bars:
        ts = bar.get("t", 0)
        dt = datetime.fromtimestamp(ts / 1000, tz=ET_TZ).astimezone(CT_TZ)
        candles.append({"time": dt, "open": bar.get("o", 0), "high": bar.get("h", 0), 
                        "low": bar.get("l", 0), "close": bar.get("c", 0), 
                        "is_green": bar.get("c", 0) >= bar.get("o", 0)})
    
    # Session high/low for fallback
    session_high = max(c["high"] for c in candles)
    session_low = min(c["low"] for c in candles)
    session_high_candle = next(c for c in candles if c["high"] == session_high)
    session_low_candle = next(c for c in candles if c["low"] == session_low)
    
    # Find HIGH pivot pattern
    high_candidates = []
    for i in range(len(candles) - 1):
        curr, nxt = candles[i], candles[i + 1]
        if curr["is_green"] and not nxt["is_green"] and nxt["close"] < curr["open"]:
            high_candidates.append({"price": curr["high"], "time": curr["time"], "open": curr["open"]})
    
    # Find LOW pivot pattern
    low_candidates = []
    for i in range(len(candles) - 1):
        curr, nxt = candles[i], candles[i + 1]
        if not curr["is_green"] and nxt["is_green"] and nxt["close"] > curr["open"]:
            low_candidates.append({"price": curr["low"], "time": curr["time"], "open": nxt["open"]})
    
    # Add HIGH pivot (pattern or fallback)
    if high_candidates:
        high_candidates.sort(key=lambda x: x["price"], reverse=True)
        pivots.append(Pivot(name="Prior High", price=high_candidates[0]["price"], 
                           pivot_time=high_candidates[0]["time"], pivot_type="HIGH", 
                           candle_high=high_candidates[0]["price"], candle_open=high_candidates[0]["open"]))
    else:
        pivots.append(Pivot(name="Prior High", price=session_high, 
                           pivot_time=session_high_candle["time"], pivot_type="HIGH", 
                           candle_high=session_high, candle_open=session_high_candle["open"]))
    
    # Add LOW pivot (pattern or fallback to session low)
    if low_candidates:
        low_candidates.sort(key=lambda x: x["price"])
        pivots.append(Pivot(name="Prior Low", price=low_candidates[0]["price"], 
                           pivot_time=low_candidates[0]["time"], pivot_type="LOW", 
                           candle_open=low_candidates[0]["open"]))
    else:
        # FALLBACK: Use session low
        pivots.append(Pivot(name="Prior Low", price=session_low, 
                           pivot_time=session_low_candle["time"], pivot_type="LOW", 
                           candle_open=session_low_candle["open"]))
    
    # Add CLOSE pivot
    if candles:
        pivots.append(Pivot(name="Prior Close", price=candles[-1]["close"], 
                           pivot_time=CT_TZ.localize(datetime.combine(pivot_date, close_time_ct)), 
                           pivot_type="CLOSE"))
    
    return pivots

def create_manual_pivots(high_price, high_time_str, low_price, low_time_str, close_price, pivot_date, close_time):
    def parse_t(s):
        try:
            parts = s.replace(" ", "").split(":")
            return time(int(parts[0]), int(parts[1]))
        except:
            return time(10, 30)
    pivots = []
    if high_price > 0:
        pivots.append(Pivot(name="Prior High", price=high_price, pivot_time=CT_TZ.localize(datetime.combine(pivot_date, parse_t(high_time_str))), pivot_type="HIGH", candle_high=high_price))
    if low_price > 0:
        pivots.append(Pivot(name="Prior Low", price=low_price, pivot_time=CT_TZ.localize(datetime.combine(pivot_date, parse_t(low_time_str))), pivot_type="LOW", candle_open=low_price))
    if close_price > 0:
        pivots.append(Pivot(name="Prior Close", price=close_price, pivot_time=CT_TZ.localize(datetime.combine(pivot_date, close_time)), pivot_type="CLOSE"))
    return pivots

def count_blocks(start_time, eval_time):
    """
    Count 30-min blocks between start_time and eval_time.
    
    CRITICAL RULES:
    - Regular day: Market closes 3pm CT, but 2 more candles (3-3:30, 3:30-4) before maintenance
    - Maintenance: 4pm-5pm CT daily (skip)
    - Overnight: 5pm CT to next morning
    - Weekends: Skip Sat, futures reopen Sun 5pm CT
    - Holidays: Skip, futures reopen 5pm CT on the holiday
    - Half-days: Market closes 12pm CT, 1 more candle (12-12:30) before holiday closure
    - Evening before holiday: Skip (futures closed)
    
    BLOCK COUNTS:
    - Regular weekday: 2 candles (3-4pm) + 32 overnight (5pm-9am) = 34 blocks
    - Friday → Monday: 2 candles (3-4pm) + 32 overnight (Sun 5pm-Mon 9am) = 34 blocks  
    - Half-day → Post-holiday: 1 candle (12-12:30) + 32 overnight (Holiday 5pm-next 9am) = 33 blocks
    """
    if eval_time <= start_time:
        return 0
    
    MAINT_START = time(16, 0)   # 4pm CT
    MAINT_END = time(17, 0)     # 5pm CT
    MARKET_CLOSE = time(15, 0)  # 3pm CT regular close
    HALF_DAY_CLOSE = time(12, 0)  # 12pm CT half-day close
    
    if start_time.tzinfo is None:
        start_time = CT_TZ.localize(start_time)
    if eval_time.tzinfo is None:
        eval_time = CT_TZ.localize(eval_time)
    
    blocks = 0
    current = start_time
    
    for _ in range(5000):
        if current >= eval_time:
            break
        
        current_date = current.date()
        next_date = current_date + timedelta(days=1)
        wd = current.weekday()
        ct = current.time()
        
        # WEEKENDS
        if wd == 5:  # Saturday - skip entirely to Sunday 5pm
            current = CT_TZ.localize(datetime.combine(current_date + timedelta(days=1), MAINT_END))
            continue
        if wd == 6:  # Sunday
            if ct < MAINT_END:  # Before 5pm - skip to 5pm
                current = CT_TZ.localize(datetime.combine(current_date, MAINT_END))
                continue
        
        # EVENING BEFORE HOLIDAY - futures closed
        if is_holiday(next_date) and ct >= MAINT_END:
            current = CT_TZ.localize(datetime.combine(next_date, MAINT_END))
            continue
        
        # HOLIDAY - skip to 5pm when futures reopen
        if is_holiday(current_date):
            if ct < MAINT_END:
                current = CT_TZ.localize(datetime.combine(current_date, MAINT_END))
                continue
        
        # HALF DAY
        if is_half_day(current_date):
            # After 12:30pm on half day - check if tomorrow is holiday
            if ct >= time(12, 30):
                if is_holiday(next_date):
                    # Skip to holiday 5pm
                    current = CT_TZ.localize(datetime.combine(next_date, MAINT_END))
                    continue
                else:
                    # Not before a holiday - skip to regular maintenance end
                    if ct < MAINT_END:
                        current = CT_TZ.localize(datetime.combine(current_date, MAINT_END))
                        continue
        
        # MAINTENANCE WINDOW (4pm-5pm CT)
        if MAINT_START <= ct < MAINT_END:
            current = CT_TZ.localize(datetime.combine(current_date, MAINT_END))
            continue
        
        # FRIDAY after 4pm - skip to Sunday 5pm
        if wd == 4 and ct >= MAINT_START:
            current = CT_TZ.localize(datetime.combine(current_date + timedelta(days=2), MAINT_END))
            continue
        
        # COUNT THE BLOCK
        next_block = current + timedelta(minutes=30)
        
        if next_block > eval_time:
            break
        
        # Check if next block crosses into maintenance
        if ct < MAINT_START and next_block.time() >= MAINT_START:
            blocks += 1
            current = CT_TZ.localize(datetime.combine(current_date, MAINT_END))
            continue
        
        # Check if on half-day and next block crosses 12:30 (last candle before holiday closure)
        if is_half_day(current_date) and is_holiday(next_date):
            if ct < time(12, 30) and next_block.time() >= time(12, 30):
                blocks += 1
                current = CT_TZ.localize(datetime.combine(next_date, MAINT_END))
                continue
        
        blocks += 1
        current = next_block
    
    return max(blocks, 1)

def build_cones(pivots, eval_time):
    """
    Build structural cones from pivots.
    
    PIVOT RULES:
    - HIGH pivot:
      - Ascending: Use highest WICK (candle_high) + expansion
      - Descending: Use highest CLOSE (pivot.price) - expansion
    - LOW pivot:
      - Both rails use lowest CLOSE (pivot.price)
      - Ascending: pivot.price + expansion
      - Descending: pivot.price - expansion
    - CLOSE pivot:
      - Both rails use the close price
    """
    cones = []
    for pivot in pivots:
        if pivot.price <= 0 or pivot.pivot_time is None:
            continue
        blocks = count_blocks(pivot.pivot_time + timedelta(minutes=30), eval_time)
        expansion = blocks * SLOPE_PER_30MIN
        if pivot.pivot_type == "HIGH":
            # HIGH: Ascending from wick, Descending from close
            wick = pivot.candle_high if pivot.candle_high > 0 else pivot.price
            ascending = wick + expansion
            descending = pivot.price - expansion  # pivot.price is the close
        elif pivot.pivot_type == "LOW":
            # LOW: BOTH from close (pivot.price is the lowest close)
            ascending = pivot.price + expansion
            descending = pivot.price - expansion
        else:
            # CLOSE: Both from close price
            ascending = pivot.price + expansion
            descending = pivot.price - expansion
        width = ascending - descending
        cones.append(Cone(name=pivot.name, pivot=pivot, ascending_rail=round(ascending, 2), descending_rail=round(descending, 2), width=round(width, 2), blocks=blocks, is_tradeable=(width >= MIN_CONE_WIDTH)))
    return cones

def analyze_price_proximity(current_price: float, cones: List[Cone], vix_zone=None) -> PriceProximity:
    """
    Analyze current SPX price position relative to structural cones.
    
    Returns actionable guidance based on where price sits:
    - Above all cones: Wait for pullback
    - Below all cones: Wait for rally  
    - Inside a cone: Wait for rail touch
    - Near a rail: Setup active
    """
    proximity = PriceProximity(current_price=current_price, rail_distances={})
    
    if not cones or current_price <= 0:
        proximity.position = "UNKNOWN"
        proximity.position_detail = "No price data"
        return proximity
    
    tradeable_cones = [c for c in cones if c.is_tradeable]
    if not tradeable_cones:
        proximity.position = "UNKNOWN"
        proximity.position_detail = "No tradeable cones"
        return proximity
    
    # Get all rails and their distances
    all_rails = []
    for cone in tradeable_cones:
        asc_dist = current_price - cone.ascending_rail
        desc_dist = current_price - cone.descending_rail
        proximity.rail_distances[cone.name] = {
            "ascending": round(asc_dist, 1),
            "descending": round(desc_dist, 1),
            "asc_rail": cone.ascending_rail,
            "desc_rail": cone.descending_rail
        }
        all_rails.append({
            "rail": cone.ascending_rail,
            "type": "ascending",
            "cone": cone.name,
            "distance": asc_dist
        })
        all_rails.append({
            "rail": cone.descending_rail,
            "type": "descending",
            "cone": cone.name,
            "distance": desc_dist
        })
    
    # Find highest ascending and lowest descending across all cones
    highest_asc = max(c.ascending_rail for c in tradeable_cones)
    lowest_desc = min(c.descending_rail for c in tradeable_cones)
    
    # Find nearest rail
    nearest = min(all_rails, key=lambda x: abs(x["distance"]))
    proximity.nearest_rail = nearest["rail"]
    proximity.nearest_rail_name = f"{nearest['cone']} {nearest['type']}"
    proximity.nearest_rail_type = nearest["type"]
    proximity.nearest_rail_distance = round(nearest["distance"], 1)
    proximity.nearest_cone_name = nearest["cone"]
    
    # Determine position
    NEAR_THRESHOLD = 8  # Within 8 points = "near"
    
    if current_price > highest_asc:
        # Price is ABOVE all cones
        proximity.position = "ABOVE_ALL"
        dist_to_highest = round(current_price - highest_asc, 1)
        proximity.position_detail = f"Extended {dist_to_highest} pts above structure"
        proximity.action = "WAIT_FOR_PULLBACK"
        proximity.action_detail = f"Wait for pullback to {nearest['cone']} ascending @ {nearest['rail']:,.0f}"
        
    elif current_price < lowest_desc:
        # Price is BELOW all cones
        proximity.position = "BELOW_ALL"
        dist_to_lowest = round(lowest_desc - current_price, 1)
        proximity.position_detail = f"Extended {dist_to_lowest} pts below structure"
        proximity.action = "WAIT_FOR_RALLY"
        proximity.action_detail = f"Wait for rally to {nearest['cone']} descending @ {nearest['rail']:,.0f}"
        
    else:
        # Price is within the cone zone - check if inside a specific cone
        inside_cones = [c for c in tradeable_cones 
                       if c.descending_rail <= current_price <= c.ascending_rail]
        
        if inside_cones:
            # Inside one or more cones
            proximity.inside_cone = True
            proximity.inside_cone_name = inside_cones[0].name
            proximity.position = "INSIDE_CONE"
            proximity.position_detail = f"Inside {inside_cones[0].name} cone"
            proximity.action = "INSIDE_WAIT"
            
            # Find nearest rail of the cone we're inside
            cone = inside_cones[0]
            dist_to_asc = cone.ascending_rail - current_price
            dist_to_desc = current_price - cone.descending_rail
            
            if dist_to_asc < dist_to_desc:
                proximity.action_detail = f"Approaching ascending rail @ {cone.ascending_rail:,.0f} ({dist_to_asc:.0f} pts) — watch for PUTS entry"
            else:
                proximity.action_detail = f"Approaching descending rail @ {cone.descending_rail:,.0f} ({dist_to_desc:.0f} pts) — watch for CALLS entry"
        
        elif abs(nearest["distance"]) <= NEAR_THRESHOLD:
            # Near a rail
            proximity.position = "NEAR_RAIL"
            proximity.position_detail = f"{abs(nearest['distance']):.0f} pts from {nearest['cone']} {nearest['type']}"
            proximity.action = "WATCH_FOR_ENTRY"
            
            if nearest["type"] == "ascending":
                proximity.action_detail = f"Approaching {nearest['cone']} ascending @ {nearest['rail']:,.0f} — PUTS entry zone"
            else:
                proximity.action_detail = f"Approaching {nearest['cone']} descending @ {nearest['rail']:,.0f} — CALLS entry zone"
        
        else:
            # Between cones but not inside any
            proximity.position = "BETWEEN_CONES"
            proximity.position_detail = f"Between structures, {abs(nearest['distance']):.0f} pts to nearest rail"
            proximity.action = "WAIT_FOR_APPROACH"
            proximity.action_detail = f"Wait for price to approach {nearest['cone']} {nearest['type']} @ {nearest['rail']:,.0f}"
    
    return proximity

def build_pivot_table(pivots, trading_date):
    rows = []
    time_blocks = [("8:30", time(8, 30)), ("9:00", time(9, 0)), ("9:30", time(9, 30)), ("10:00", time(10, 0)), ("10:30", time(10, 30)), ("11:00", time(11, 0)), ("11:30", time(11, 30)), ("12:00", time(12, 0))]
    high_p = next((p for p in pivots if p.name == "Prior High"), None)
    low_p = next((p for p in pivots if p.name == "Prior Low"), None)
    close_p = next((p for p in pivots if p.name == "Prior Close"), None)
    for label, t in time_blocks:
        eval_dt = CT_TZ.localize(datetime.combine(trading_date, t))
        row = PivotTableRow(time_block=label, time_ct=t)
        for piv, attr_asc, attr_desc in [(high_p, "prior_high_asc", "prior_high_desc"), (low_p, "prior_low_asc", "prior_low_desc"), (close_p, "prior_close_asc", "prior_close_desc")]:
            if piv and piv.pivot_time:
                blocks = count_blocks(piv.pivot_time + timedelta(minutes=30), eval_dt)
                exp = blocks * SLOPE_PER_30MIN
                if piv.pivot_type == "HIGH":
                    # HIGH: Ascending from wick, Descending from close
                    base = piv.candle_high if piv.candle_high > 0 else piv.price
                    setattr(row, attr_asc, round(base + exp, 2))
                    setattr(row, attr_desc, round(piv.price - exp, 2))
                elif piv.pivot_type == "LOW":
                    # LOW: BOTH from close (pivot.price)
                    setattr(row, attr_asc, round(piv.price + exp, 2))
                    setattr(row, attr_desc, round(piv.price - exp, 2))
                else:
                    setattr(row, attr_asc, round(piv.price + exp, 2))
                    setattr(row, attr_desc, round(piv.price - exp, 2))
        rows.append(row)
    return rows

def analyze_vix_zone(vix_bottom, vix_top, vix_current, cones=None):
    zone = VIXZone(bottom=vix_bottom, top=vix_top, current=vix_current)
    if vix_bottom <= 0 or vix_top <= 0:
        zone.bias = "WAIT"
        zone.bias_reason = "VIX zone not set"
        return zone
    zone.zone_size = round(vix_top - vix_bottom, 2)
    zone.expected_spx_move = zone.zone_size * VIX_TO_SPX_MULTIPLIER
    
    if vix_current < vix_bottom:
        # BREAKOUT BELOW - VIX broke below overnight zone
        zone.zones_away = -int(np.ceil((vix_bottom - vix_current) / zone.zone_size)) if zone.zone_size > 0 else -1
        zone.position_pct = 0
        zone.bias = "CALLS"
        zone.is_breakout = True
        zone.breakout_direction = "BELOW"
        zone.breakout_level = vix_bottom  # This is the spring level for calls
        zone.bias_reason = f"⚡ BROKE BELOW {vix_bottom:.2f} → Strong CALLS"
        zone.distance_to_boundary = 0
    elif vix_current > vix_top:
        # BREAKOUT ABOVE - VIX broke above overnight zone
        zone.zones_away = int(np.ceil((vix_current - vix_top) / zone.zone_size)) if zone.zone_size > 0 else 1
        zone.position_pct = 100
        zone.bias = "PUTS"
        zone.is_breakout = True
        zone.breakout_direction = "ABOVE"
        zone.breakout_level = vix_top  # This is the resistance/spring level
        zone.bias_reason = f"⚡ BROKE ABOVE {vix_top:.2f} → Strong PUTS"
        zone.distance_to_boundary = 0
    else:
        zone.zones_away = 0
        zone.position_pct = ((vix_current - vix_bottom) / zone.zone_size * 100) if zone.zone_size > 0 else 50
        zone.is_breakout = False
        
        # Calculate distance to nearest boundary
        dist_to_top = vix_top - vix_current
        dist_to_bottom = vix_current - vix_bottom
        zone.distance_to_boundary = min(dist_to_top, dist_to_bottom)
        
        if zone.position_pct >= 80:
            zone.bias = "CALLS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (top) → {dist_to_top:.2f} from breakout"
        elif zone.position_pct >= 70:
            zone.bias = "CALLS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (upper) → SPX UP"
        elif zone.position_pct <= 20:
            zone.bias = "PUTS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (bottom) → {dist_to_bottom:.2f} from breakout"
        elif zone.position_pct <= 30:
            zone.bias = "PUTS"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (lower) → SPX DOWN"
        else:
            zone.bias = "WAIT"
            zone.bias_reason = f"VIX at {zone.position_pct:.0f}% (mid-zone) → No edge"
    
    if cones and zone.bias in ["CALLS", "PUTS"]:
        rails = [(c.descending_rail if zone.bias == "CALLS" else c.ascending_rail, c.name) for c in cones if c.is_tradeable]
        if rails:
            rails.sort(key=lambda x: x[0])
            zone.matched_rail, zone.matched_cone = rails[len(rails)//2]
    return zone

def calculate_ma_bias(bars_30m):
    """
    Calculate 30-minute MA Bias Filter.
    
    Uses:
    - SMA200: 200-period Simple Moving Average for directional permission
    - EMA50: 50-period Exponential Moving Average for trend health
    
    Logic:
    - Price > SMA200 → Long-only permission
    - Price < SMA200 → Short-only permission
    - EMA50 > SMA200 → Bullish trend (validates longs)
    - EMA50 < SMA200 → Bearish trend (validates shorts)
    """
    ma_bias = MABias()
    
    if not bars_30m or len(bars_30m) < 200:
        ma_bias.bias = "NEUTRAL"
        ma_bias.bias_reason = f"Insufficient data ({len(bars_30m) if bars_30m else 0}/200 bars)"
        return ma_bias
    
    # Extract closing prices
    closes = [bar.get("c", 0) for bar in bars_30m]
    if not all(closes):
        ma_bias.bias = "NEUTRAL"
        ma_bias.bias_reason = "Invalid price data"
        return ma_bias
    
    current_close = closes[-1]
    ma_bias.current_close = current_close
    
    # Calculate SMA200
    sma200_closes = closes[-200:]
    ma_bias.sma200 = sum(sma200_closes) / 200
    
    # Calculate EMA50
    ema50_closes = closes[-50:]
    multiplier = 2 / (50 + 1)
    ema = ema50_closes[0]
    for price in ema50_closes[1:]:
        ema = (price - ema) * multiplier + ema
    ma_bias.ema50 = ema
    
    # Determine price vs SMA200 (directional permission)
    sma_buffer = ma_bias.sma200 * 0.001  # 0.1% buffer to avoid whipsaws
    if current_close > ma_bias.sma200 + sma_buffer:
        ma_bias.price_vs_sma200 = "ABOVE"
    elif current_close < ma_bias.sma200 - sma_buffer:
        ma_bias.price_vs_sma200 = "BELOW"
    else:
        ma_bias.price_vs_sma200 = "NEUTRAL"
    
    # Determine EMA50 vs SMA200 (trend health)
    if ma_bias.ema50 > ma_bias.sma200:
        ma_bias.ema_vs_sma = "BULLISH"
    elif ma_bias.ema50 < ma_bias.sma200:
        ma_bias.ema_vs_sma = "BEARISH"
    else:
        ma_bias.ema_vs_sma = "NEUTRAL"
    
    # Determine final bias
    if ma_bias.price_vs_sma200 == "ABOVE" and ma_bias.ema_vs_sma == "BULLISH":
        ma_bias.bias = "LONG"
        ma_bias.bias_reason = "Price > SMA200 & EMA50 > SMA200 → LONG ONLY"
    elif ma_bias.price_vs_sma200 == "BELOW" and ma_bias.ema_vs_sma == "BEARISH":
        ma_bias.bias = "SHORT"
        ma_bias.bias_reason = "Price < SMA200 & EMA50 < SMA200 → SHORT ONLY"
    elif ma_bias.price_vs_sma200 == "ABOVE" and ma_bias.ema_vs_sma == "BEARISH":
        ma_bias.bias = "NEUTRAL"
        ma_bias.bias_reason = "Price > SMA200 but EMA50 < SMA200 → Mixed signals"
        ma_bias.regime_warning = "⚠️ Potential trend reversal brewing"
    elif ma_bias.price_vs_sma200 == "BELOW" and ma_bias.ema_vs_sma == "BULLISH":
        ma_bias.bias = "NEUTRAL"
        ma_bias.bias_reason = "Price < SMA200 but EMA50 > SMA200 → Mixed signals"
        ma_bias.regime_warning = "⚠️ Potential trend reversal brewing"
    else:
        ma_bias.bias = "NEUTRAL"
        ma_bias.bias_reason = "Price near SMA200 → Ranging/Choppy"
    
    # Check for recent crosses (regime shift warning)
    if len(closes) >= 10:
        recent_closes = closes[-10:]
        crosses = 0
        for i in range(1, len(recent_closes)):
            prev_above = recent_closes[i-1] > ma_bias.sma200
            curr_above = recent_closes[i] > ma_bias.sma200
            if prev_above != curr_above:
                crosses += 1
        if crosses >= 3:
            ma_bias.regime_warning = f"⚠️ {crosses} SMA200 crosses in last 10 bars → CHOPPY"
            ma_bias.bias = "NEUTRAL"
            ma_bias.bias_reason = "Multiple MA crosses → Avoid trading"
    
    return ma_bias

def generate_setups(cones, current_price, vix_current=16, mins_after_open=30, is_after_cutoff=False, broken_structures=None):
    """Generate trade setups with calibrated option pricing
    
    broken_structures: dict mapping cone names to broken status
        - If a cone is marked broken, its setups get status "BROKEN"
        - CALLS broken = 30-min close below descending rail
        - PUTS broken = 30-min close above ascending rail
    """
    if broken_structures is None:
        broken_structures = {}
    
    setups = []
    for cone in cones:
        if not cone.is_tradeable:
            continue
        
        # Check if this cone's structure is broken
        is_broken = broken_structures.get(cone.name, False)
        
        # CALLS - enter at descending rail
        entry_c = cone.descending_rail
        dist_c = abs(current_price - entry_c)
        opt_c = get_option_data_for_entry(entry_c, "C", vix_current, mins_after_open)
        delta_c = abs(opt_c.spy_delta) if opt_c else DELTA_IDEAL
        
        # Determine CALLS status: BROKEN if structure broken, else normal logic
        if is_after_cutoff:
            calls_status = "GREY"
        elif is_broken:
            calls_status = "BROKEN"
        elif dist_c <= RAIL_PROXIMITY:
            calls_status = "ACTIVE"
        else:
            calls_status = "WAIT"
        
        setups.append(TradeSetup(
            direction="CALLS", cone_name=cone.name, cone_width=cone.width, entry=entry_c,
            stop=round(entry_c - STOP_LOSS_PTS, 2),
            target_25=round(entry_c + cone.width * 0.25, 2), target_50=round(entry_c + cone.width * 0.50, 2),
            target_75=round(entry_c + cone.width * 0.75, 2), target_100=round(entry_c + cone.width, 2),
            distance=round(dist_c, 1), option=opt_c,
            profit_25=round(cone.width * 0.25 * delta_c * 100, 0), profit_50=round(cone.width * 0.50 * delta_c * 100, 0),
            profit_75=round(cone.width * 0.75 * delta_c * 100, 0), profit_100=round(cone.width * delta_c * 100, 0),
            risk_dollars=round(STOP_LOSS_PTS * delta_c * 100, 0),
            status=calls_status
        ))
        
        # PUTS - enter at ascending rail
        entry_p = cone.ascending_rail
        dist_p = abs(current_price - entry_p)
        opt_p = get_option_data_for_entry(entry_p, "P", vix_current, mins_after_open)
        delta_p = abs(opt_p.spy_delta) if opt_p else DELTA_IDEAL
        
        # Determine PUTS status: BROKEN if structure broken, else normal logic
        if is_after_cutoff:
            puts_status = "GREY"
        elif is_broken:
            puts_status = "BROKEN"
        elif dist_p <= RAIL_PROXIMITY:
            puts_status = "ACTIVE"
        else:
            puts_status = "WAIT"
        
        setups.append(TradeSetup(
            direction="PUTS", cone_name=cone.name, cone_width=cone.width, entry=entry_p,
            stop=round(entry_p + STOP_LOSS_PTS, 2),
            target_25=round(entry_p - cone.width * 0.25, 2), target_50=round(entry_p - cone.width * 0.50, 2),
            target_75=round(entry_p - cone.width * 0.75, 2), target_100=round(entry_p - cone.width, 2),
            distance=round(dist_p, 1), option=opt_p,
            profit_25=round(cone.width * 0.25 * delta_p * 100, 0), profit_50=round(cone.width * 0.50 * delta_p * 100, 0),
            profit_75=round(cone.width * 0.75 * delta_p * 100, 0), profit_100=round(cone.width * delta_p * 100, 0),
            risk_dollars=round(STOP_LOSS_PTS * delta_p * 100, 0),
            status=puts_status
        ))
    return setups

def calculate_day_score(vix_zone, cones, setups, confluence=None, market_ctx=None):
    """
    Calculate trading day score.
    
    New Scoring (100 points):
    - VIX-MA Confluence: 40 pts (the core decision)
    - VIX Zone Position: 30 pts (how extreme in zone)
    - VIX-Cone Alignment: 20 pts (is there a rail to trade?)
    - Cone Width: 10 pts (profit potential)
    
    NO TRADE if:
    - Confluence conflicts (VIX vs MA)
    - Score < 65
    """
    score = DayScore()
    total = 0
    
    # Check for NO TRADE condition first
    if confluence and confluence.no_trade:
        score.total = 0
        score.grade = "NO TRADE"
        score.color = "#ef4444"
        return score
    
    # 1. VIX-MA Confluence (40 pts)
    if confluence:
        total += confluence.alignment_score  # Already 0-40 from confluence calc
    else:
        total += 15  # Default if no confluence data
    
    # 2. VIX Zone Position (30 pts) - How extreme is VIX in the zone?
    if vix_zone.is_breakout:
        total += 30  # Breakout = maximum points
    elif vix_zone.bias != "WAIT":
        if vix_zone.position_pct >= 80 or vix_zone.position_pct <= 20:
            total += 30  # At extremes
        elif vix_zone.position_pct >= 70 or vix_zone.position_pct <= 30:
            total += 20  # Good position
        elif vix_zone.position_pct >= 60 or vix_zone.position_pct <= 40:
            total += 10  # Weak position
        else:
            total += 0   # Mid-zone = no points
    
    # 3. VIX-Cone Alignment (20 pts) - Is there a rail within range?
    if vix_zone.bias in ["CALLS", "PUTS"]:
        matching_setups = [s for s in setups if s.direction == vix_zone.bias]
        if matching_setups:
            closest = min(s.distance for s in matching_setups)
            if closest <= 5:
                total += 20  # Very close
            elif closest <= 10:
                total += 15  # Close
            elif closest <= 15:
                total += 10  # Reachable
            elif closest <= 25:
                total += 5   # Far but possible
    
    # 4. Cone Width (10 pts) - Profit potential
    tradeable = [c for c in cones if c.is_tradeable]
    if tradeable:
        best_width = max(c.width for c in tradeable)
        if best_width >= 35:
            total += 10
        elif best_width >= 28:
            total += 7
        elif best_width >= 20:
            total += 4
    
    score.total = min(100, total)
    
    # Grade and color
    if total >= 80:
        score.grade = "A"
        score.color = "#22c55e"  # Green
    elif total >= 65:
        score.grade = "B"
        score.color = "#3b82f6"  # Blue
    elif total >= 50:
        score.grade = "C"
        score.color = "#eab308"  # Amber
    else:
        score.grade = "D"
        score.color = "#ef4444"  # Red
    
    return score

def check_alerts(setups, vix_zone, current_time):
    alerts = []
    for s in setups:
        if s.status == "ACTIVE":
            alerts.append({"priority": "HIGH", "message": f"🎯 {s.direction} {s.cone_name} ACTIVE @ {s.entry:,.2f}"})
        elif 5 < s.distance <= 15 and s.status != "GREY":
            alerts.append({"priority": "MEDIUM", "message": f"⚠️ {s.direction} {s.cone_name} ({s.distance:.0f} pts away)"})
    if vix_zone.zones_away != 0:
        alerts.append({"priority": "HIGH", "message": f"📊 VIX {abs(vix_zone.zones_away)} zone(s) {'above' if vix_zone.zones_away > 0 else 'below'} → {vix_zone.bias}"})
    if INST_WINDOW_START <= current_time <= INST_WINDOW_END:
        alerts.append({"priority": "INFO", "message": "🏛️ Institutional Window (9:00-9:30 CT)"})
    return alerts

def render_dashboard(vix_zone, cones, setups, pivot_table, prior_session, day_score, alerts, spx_price, trading_date, pivot_date, pivot_session_info, is_historical, theme, ma_bias=None, confluence=None, gap_analysis=None, market_ctx=None, price_proximity=None):
    # PREMIUM DESIGN SYSTEM - Institutional Grade
    if theme == "light":
        # Clean, minimal light theme inspired by Linear/Stripe
        bg_main = "#fafafa"
        bg_card = "#ffffff"
        bg_elevated = "#f5f5f5"
        bg_subtle = "#fafafa"
        text_primary = "#171717"
        text_secondary = "#525252"
        text_muted = "#a3a3a3"
        border_light = "#e5e5e5"
        border_medium = "#d4d4d4"
        shadow_sm = "0 1px 2px rgba(0,0,0,0.04)"
        shadow_md = "0 2px 8px rgba(0,0,0,0.06)"
        shadow_lg = "0 8px 24px rgba(0,0,0,0.08)"
        shadow_card = "0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03)"
    else:
        # Rich dark theme
        bg_main = "#09090b"
        bg_card = "#18181b"
        bg_elevated = "#27272a"
        bg_subtle = "#18181b"
        text_primary = "#fafafa"
        text_secondary = "#a1a1aa"
        text_muted = "#71717a"
        border_light = "#27272a"
        border_medium = "#3f3f46"
        shadow_sm = "0 1px 2px rgba(0,0,0,0.4)"
        shadow_md = "0 2px 8px rgba(0,0,0,0.5)"
        shadow_lg = "0 8px 24px rgba(0,0,0,0.6)"
        shadow_card = "0 1px 3px rgba(0,0,0,0.3)"
    
    # Refined accent colors - more muted, professional
    green = "#22c55e"
    green_light = "#f0fdf4" if theme == "light" else "#14532d"
    green_muted = "#86efac" if theme == "light" else "#166534"
    red = "#ef4444"
    red_light = "#fef2f2" if theme == "light" else "#450a0a"
    red_muted = "#fca5a5" if theme == "light" else "#7f1d1d"
    amber = "#eab308"
    amber_light = "#fefce8" if theme == "light" else "#422006"
    blue = "#3b82f6"
    blue_light = "#eff6ff" if theme == "light" else "#1e3a8a"
    purple = "#a855f7"
    neutral = "#737373"
    
    bias_color = green if vix_zone.bias == "CALLS" else red if vix_zone.bias == "PUTS" else neutral
    bias_bg = green_light if vix_zone.bias == "CALLS" else red_light if vix_zone.bias == "PUTS" else bg_elevated
    bias_icon = "↑" if vix_zone.bias == "CALLS" else "↓" if vix_zone.bias == "PUTS" else "–"
    
    # MA Bias colors
    if ma_bias:
        ma_color = green if ma_bias.bias == "LONG" else red if ma_bias.bias == "SHORT" else neutral
        ma_bg = green_light if ma_bias.bias == "LONG" else red_light if ma_bias.bias == "SHORT" else bg_elevated
        ma_icon = "▲" if ma_bias.bias == "LONG" else "▼" if ma_bias.bias == "SHORT" else "–"
    else:
        ma_color, ma_bg, ma_icon = neutral, bg_elevated, "–"
    
    now = get_ct_now()
    marker_pos = min(max(vix_zone.position_pct, 3), 97) if vix_zone.zone_size > 0 else 50
    session_note = f"Half Day – {pivot_session_info['close_ct'].strftime('%I:%M %p')} CT Close" if pivot_session_info.get("is_half_day") else ""
    
    calls_setups = [s for s in setups if s.direction == "CALLS"]
    puts_setups = [s for s in setups if s.direction == "PUTS"]
    
    # Build trading checklist with CORRECT scoring
    checklist = []
    total_score = 0
    
    # 1. VIX-CONE ALIGNMENT (25 pts)
    # VIX bias direction has a cone rail within 10 pts = 25
    alignment_pts = 0
    alignment_detail = ""
    if vix_zone.bias in ["CALLS", "PUTS"]:
        # Get rails matching the bias direction
        if vix_zone.bias == "CALLS":
            aligned_rails = [(s.entry, s.cone_name) for s in calls_setups if s.distance <= 10]
        else:
            aligned_rails = [(s.entry, s.cone_name) for s in puts_setups if s.distance <= 10]
        
        if aligned_rails:
            closest = min(s.distance for s in (calls_setups if vix_zone.bias == "CALLS" else puts_setups) if s.distance <= 10)
            alignment_pts = 25
            alignment_detail = f"{vix_zone.bias} rail {closest:.0f} pts away"
        else:
            alignment_detail = f"No {vix_zone.bias} rail within 10 pts"
    else:
        alignment_detail = "No VIX bias to align"
    
    checklist.append({
        "pts": alignment_pts, 
        "max": 25, 
        "label": "VIX-Cone Alignment", 
        "detail": alignment_detail
    })
    total_score += alignment_pts
    
    # 2. VIX ZONE CLARITY (25 pts)
    # Clear bias (top/bottom 25%) = 25, 25-40% = 15, Middle = 0
    clarity_pts = 0
    clarity_detail = ""
    if vix_zone.zones_away != 0:
        # Outside zone entirely = strongest signal
        clarity_pts = 25
        clarity_detail = f"{abs(vix_zone.zones_away)} zone(s) {'below' if vix_zone.zones_away < 0 else 'above'} – Maximum clarity"
    elif vix_zone.position_pct <= 25 or vix_zone.position_pct >= 75:
        # Top/bottom 25%
        clarity_pts = 25
        clarity_detail = f"At {vix_zone.position_pct:.0f}% – Clear bias zone"
    elif vix_zone.position_pct <= 40 or vix_zone.position_pct >= 60:
        # 25-40% or 60-75%
        clarity_pts = 15
        clarity_detail = f"At {vix_zone.position_pct:.0f}% – Moderate clarity"
    else:
        # Middle 40-60%
        clarity_pts = 0
        clarity_detail = f"At {vix_zone.position_pct:.0f}% – Mid-zone, no clarity"
    
    checklist.append({
        "pts": clarity_pts, 
        "max": 25, 
        "label": "VIX Zone Clarity", 
        "detail": clarity_detail
    })
    total_score += clarity_pts
    
    # 3. CONE WIDTH QUALITY (20 pts)
    # Best cone >30 = 20, >25 = 15, >20 = 10, <18 = 0
    width_pts = 0
    width_detail = ""
    tradeable_cones = [c for c in cones if c.is_tradeable]
    if tradeable_cones:
        best_width = max(c.width for c in tradeable_cones)
        if best_width >= 30:
            width_pts = 20
            width_detail = f"Best: {best_width:.0f} pts – Excellent range"
        elif best_width >= 25:
            width_pts = 15
            width_detail = f"Best: {best_width:.0f} pts – Good range"
        elif best_width >= 20:
            width_pts = 10
            width_detail = f"Best: {best_width:.0f} pts – Acceptable"
        elif best_width >= 18:
            width_pts = 5
            width_detail = f"Best: {best_width:.0f} pts – Minimum"
        else:
            width_pts = 0
            width_detail = f"Best: {best_width:.0f} pts – Too narrow"
    else:
        width_detail = "No tradeable cones"
    
    checklist.append({
        "pts": width_pts, 
        "max": 20, 
        "label": "Cone Width Quality", 
        "detail": width_detail
    })
    total_score += width_pts
    
    # 4. PREMIUM SWEET SPOT (15 pts)
    # Options $4-7 = 15, $3.50-8 = 10, outside = 5
    premium_pts = 0
    premium_detail = ""
    # Check if any setup has premium in sweet spot
    perfect_sweet = [s for s in setups if s.option and 4.0 <= s.option.spx_price_est <= 7.0]
    good_sweet = [s for s in setups if s.option and 3.5 <= s.option.spx_price_est <= 8.0]
    
    if perfect_sweet:
        premium_pts = 15
        premium_detail = f"{len(perfect_sweet)} setups in $4-$7 perfect zone"
    elif good_sweet:
        premium_pts = 10
        premium_detail = f"{len(good_sweet)} setups in $3.50-$8 range"
    else:
        premium_pts = 5
        premium_detail = "Premiums outside sweet spot"
    
    checklist.append({
        "pts": premium_pts, 
        "max": 15, 
        "label": "Premium Sweet Spot", 
        "detail": premium_detail
    })
    total_score += premium_pts
    
    # 5. MULTIPLE CONE CONFLUENCE (15 pts)
    # 2+ rails within 5 pts of each other = 15 (institutional level)
    confluence_pts = 0
    confluence_detail = ""
    
    # Get all entry rails
    all_call_entries = sorted([s.entry for s in calls_setups])
    all_put_entries = sorted([s.entry for s in puts_setups])
    
    # Check for confluence (rails within 5 pts of each other)
    def check_confluence(entries):
        if len(entries) < 2:
            return 0
        confluent_count = 0
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                if abs(entries[i] - entries[j]) <= 5:
                    confluent_count += 1
        return confluent_count
    
    call_confluence = check_confluence(all_call_entries)
    put_confluence = check_confluence(all_put_entries)
    
    if call_confluence >= 1 or put_confluence >= 1:
        confluence_pts = 15
        if call_confluence and put_confluence:
            confluence_detail = "Confluence on both CALLS & PUTS rails"
        elif call_confluence:
            confluence_detail = f"{call_confluence + 1} CALLS rails within 5 pts"
        else:
            confluence_detail = f"{put_confluence + 1} PUTS rails within 5 pts"
    else:
        confluence_pts = 0
        confluence_detail = "No rail confluence detected"
    
    checklist.append({
        "pts": confluence_pts, 
        "max": 15, 
        "label": "Multiple Cone Confluence", 
        "detail": confluence_detail
    })
    total_score += confluence_pts
    
    # Determine grade based on total (out of 100)
    if total_score >= 80:
        grade = "A"
        grade_color = green
        trade_ready = True
    elif total_score >= 60:
        grade = "B"
        grade_color = blue
        trade_ready = True
    elif total_score >= 40:
        grade = "C"
        grade_color = amber
        trade_ready = False
    else:
        grade = "D"
        grade_color = red
        trade_ready = False
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
/* ═══════════════════════════════════════════════════════════════
   SPX PROPHET v7 - PREMIUM INSTITUTIONAL DESIGN SYSTEM
   Inspired by: Bloomberg Terminal, Stripe Dashboard, Linear App
   ═══════════════════════════════════════════════════════════════ */

:root {{
    --bg-base: {bg_main};
    --bg-surface: {bg_card};
    --bg-surface-2: {bg_elevated};
    --bg-surface-3: {bg_subtle};
    --text-primary: {text_primary};
    --text-secondary: {text_secondary};
    --text-tertiary: {text_muted};
    --border: {border_light};
    --border-strong: {border_medium};
    
    /* Semantic Colors */
    --success: {green};
    --success-soft: {green_light};
    --danger: {red};
    --danger-soft: {red_light};
    --warning: {amber};
    --warning-soft: {amber_light};
    --info: {blue};
    --info-soft: {blue_light};
    
    /* Spacing Scale */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 20px;
    --space-6: 24px;
    --space-8: 32px;
    --space-10: 40px;
    
    /* Typography */
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    --font-mono: 'SF Mono', 'Roboto Mono', 'Fira Code', monospace;
    
    /* Radius */
    --radius-sm: 6px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-xl: 16px;
}}

*, *::before, *::after {{ 
    margin: 0; 
    padding: 0; 
    box-sizing: border-box; 
}}

html {{
    font-size: 14px;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}

body {{
    font-family: var(--font-sans);
    background: var(--bg-base);
    color: var(--text-primary);
    line-height: 1.5;
    min-height: 100vh;
}}

/* ─────────────────────────────────────────────────────────────────
   LAYOUT
   ───────────────────────────────────────────────────────────────── */

.dashboard {{
    max-width: 1440px;
    margin: 0 auto;
    padding: var(--space-6);
}}

.header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: var(--space-5);
    margin-bottom: var(--space-6);
    border-bottom: 1px solid var(--border);
}}

.logo {{
    display: flex;
    align-items: center;
    gap: var(--space-4);
}}

.logo-mark {{
    width: 56px;
    height: 56px;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
    border-radius: var(--radius-lg);
    display: grid;
    place-items: center;
    font-family: var(--font-mono);
    font-size: 15px;
    font-weight: 700;
    color: white;
    letter-spacing: -0.5px;
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35);
}}

.logo-text {{
    display: flex;
    flex-direction: column;
    gap: 3px;
}}

.logo-title {{
    font-size: 28px;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.5px;
    line-height: 1.1;
    background: linear-gradient(135deg, var(--text-primary) 0%, #a78bfa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}

.logo-subtitle {{
    font-size: 14px;
    color: var(--text-secondary);
    font-weight: 500;
    letter-spacing: 0.5px;
    font-style: italic;
}}

.header-meta {{
    display: flex;
    align-items: center;
    gap: var(--space-8);
}}

.meta-group {{
    display: flex;
    gap: var(--space-5);
}}

.meta-item {{
    text-align: right;
}}

.meta-label {{
    font-size: 10px;
    font-weight: 500;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.meta-value {{
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    margin-top: 2px;
}}

.clock {{
    font-family: var(--font-mono);
    font-size: 24px;
    font-weight: 500;
    color: var(--text-primary);
    letter-spacing: -1px;
}}

/* ─────────────────────────────────────────────────────────────────
   SIGNAL HERO - The main decision display
   ───────────────────────────────────────────────────────────────── */

.signal-hero {{
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: var(--space-6);
    margin-bottom: var(--space-5);
    display: grid;
    grid-template-columns: 1fr 280px;
    gap: var(--space-6);
}}

.signal-main {{
    display: flex;
    flex-direction: column;
    gap: var(--space-5);
}}

.signal-direction {{
    display: flex;
    align-items: center;
    gap: var(--space-4);
}}

.direction-badge {{
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-md);
    font-size: 13px;
    font-weight: 600;
}}

.direction-badge.calls {{
    background: var(--success-soft);
    color: var(--success);
}}

.direction-badge.puts {{
    background: var(--danger-soft);
    color: var(--danger);
}}

.direction-badge.wait {{
    background: var(--bg-surface-2);
    color: var(--text-tertiary);
}}

.signal-title {{
    font-size: 32px;
    font-weight: 700;
    letter-spacing: -1px;
    line-height: 1.1;
}}

.signal-title.calls {{ color: var(--success); }}
.signal-title.puts {{ color: var(--danger); }}
.signal-title.wait {{ color: var(--text-tertiary); }}

.signal-subtitle {{
    font-size: 14px;
    color: var(--text-secondary);
    margin-top: var(--space-1);
}}

.signal-confluence {{
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-surface-2);
    border-radius: var(--radius-md);
    width: fit-content;
}}

.confluence-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
}}

.confluence-dot.strong {{ background: var(--success); }}
.confluence-dot.moderate {{ background: var(--info); }}
.confluence-dot.weak {{ background: var(--text-tertiary); }}
.confluence-dot.conflict {{ background: var(--danger); }}

.confluence-text {{
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
}}

.signal-metrics {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-3);
}}

.metric {{
    background: var(--bg-surface-2);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    text-align: center;
}}

.metric-value {{
    font-family: var(--font-mono);
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
}}

.metric-value.success {{ color: var(--success); }}
.metric-value.danger {{ color: var(--danger); }}

.metric-label {{
    font-size: 10px;
    font-weight: 500;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin-top: var(--space-1);
}}

/* Score Ring */
.signal-score {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-3);
}}

.score-ring {{
    position: relative;
    width: 140px;
    height: 140px;
}}

.score-ring svg {{
    transform: rotate(-90deg);
}}

.score-ring-bg {{
    fill: none;
    stroke: var(--bg-surface-2);
    stroke-width: 8;
}}

.score-ring-fill {{
    fill: none;
    stroke-width: 8;
    stroke-linecap: round;
    transition: stroke-dashoffset 0.5s ease;
}}

.score-ring-fill.a {{ stroke: var(--success); }}
.score-ring-fill.b {{ stroke: var(--info); }}
.score-ring-fill.c {{ stroke: var(--warning); }}
.score-ring-fill.d {{ stroke: var(--danger); }}

.score-center {{
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}}

.score-value {{
    font-family: var(--font-mono);
    font-size: 36px;
    font-weight: 700;
    letter-spacing: -2px;
}}

.score-grade {{
    font-size: 11px;
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 1px;
}}

.score-label {{
    font-size: 12px;
    color: var(--text-tertiary);
    font-weight: 500;
}}

/* ─────────────────────────────────────────────────────────────────
   VIX METER
   ───────────────────────────────────────────────────────────────── */

.vix-section {{
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: var(--space-5);
    margin-bottom: var(--space-5);
}}

.section-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-4);
}}

.section-title {{
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.vix-display {{
    display: grid;
    grid-template-columns: 1fr auto;
    gap: var(--space-5);
    align-items: center;
}}

.vix-meter-track {{
    height: 6px;
    background: linear-gradient(90deg, var(--success) 0%, var(--warning) 50%, var(--danger) 100%);
    border-radius: 3px;
    position: relative;
}}

.vix-meter-thumb {{
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 14px;
    height: 14px;
    background: var(--bg-surface);
    border: 2px solid var(--text-primary);
    border-radius: 50%;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}}

.vix-meter-labels {{
    display: flex;
    justify-content: space-between;
    margin-top: var(--space-2);
}}

.vix-meter-label {{
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-tertiary);
}}

.vix-current {{
    text-align: right;
}}

.vix-current-value {{
    font-family: var(--font-mono);
    font-size: 28px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -1px;
}}

.vix-current-label {{
    font-size: 10px;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* ─────────────────────────────────────────────────────────────────
   INDICATOR CARDS - MA Bias, Gap, etc.
   ───────────────────────────────────────────────────────────────── */

.indicators-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--space-4);
    margin-bottom: var(--space-5);
}}

.indicator-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
}}

.indicator-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-3);
}}

.indicator-title {{
    font-size: 10px;
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.indicator-status {{
    width: 6px;
    height: 6px;
    border-radius: 50%;
}}

.indicator-status.long {{ background: var(--success); }}
.indicator-status.short {{ background: var(--danger); }}
.indicator-status.neutral {{ background: var(--text-tertiary); }}

.indicator-value {{
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.5px;
    margin-bottom: var(--space-1);
}}

.indicator-value.long {{ color: var(--success); }}
.indicator-value.short {{ color: var(--danger); }}
.indicator-value.neutral {{ color: var(--text-tertiary); }}

.indicator-detail {{
    font-size: 11px;
    color: var(--text-secondary);
}}

/* ─────────────────────────────────────────────────────────────────
   SETUP CARDS
   ───────────────────────────────────────────────────────────────── */

.setups-section {{
    margin-bottom: var(--space-5);
}}

.setups-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-3) var(--space-4);
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    cursor: pointer;
    transition: background 0.15s;
}}

.setups-header:hover {{
    background: var(--bg-surface-2);
}}

.setups-title {{
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: 13px;
    font-weight: 600;
}}

.setups-title.calls {{ color: var(--success); }}
.setups-title.puts {{ color: var(--danger); }}

.setups-count {{
    font-size: 11px;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 10px;
}}

.setups-count.calls {{ background: var(--success-soft); color: var(--success); }}
.setups-count.puts {{ background: var(--danger-soft); color: var(--danger); }}

.setups-chevron {{
    font-size: 10px;
    color: var(--text-tertiary);
    transition: transform 0.2s;
}}

.setups-body {{
    background: var(--bg-surface-2);
    border: 1px solid var(--border);
    border-top: none;
    border-radius: 0 0 var(--radius-lg) var(--radius-lg);
    padding: var(--space-4);
}}

.setups-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-3);
}}

.setup-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    position: relative;
    overflow: hidden;
}}

.setup-card::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
}}

.setup-card.calls::before {{ background: var(--success); }}
.setup-card.puts::before {{ background: var(--danger); }}
.setup-card.active {{ border-color: var(--success); }}
.setup-card.active.puts {{ border-color: var(--danger); }}
.setup-card.grey {{ opacity: 0.5; }}

.setup-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-3);
}}

.setup-name {{
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
}}

.setup-status {{
    font-size: 9px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 3px 8px;
    border-radius: 4px;
}}

.setup-status.active {{ background: var(--success-soft); color: var(--success); }}
.setup-status.wait {{ background: var(--warning-soft); color: var(--warning); }}
.setup-status.grey {{ background: var(--bg-surface-2); color: var(--text-tertiary); }}

.setup-entry {{
    background: var(--bg-surface-2);
    border-radius: var(--radius-sm);
    padding: var(--space-3);
    text-align: center;
    margin-bottom: var(--space-3);
}}

.setup-entry-label {{
    font-size: 9px;
    font-weight: 500;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.setup-entry-price {{
    font-family: var(--font-mono);
    font-size: 22px;
    font-weight: 600;
    margin-top: 2px;
}}

.setup-entry-price.calls {{ color: var(--success); }}
.setup-entry-price.puts {{ color: var(--danger); }}

.setup-entry-distance {{
    font-size: 10px;
    color: var(--text-tertiary);
    margin-top: 2px;
}}

.setup-contract {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
}}

.contract-item {{
    background: var(--bg-surface-2);
    border-radius: var(--radius-sm);
    padding: var(--space-2);
    text-align: center;
}}

.contract-label {{
    font-size: 9px;
    color: var(--text-tertiary);
    text-transform: uppercase;
}}

.contract-value {{
    font-family: var(--font-mono);
    font-size: 13px;
    font-weight: 600;
    margin-top: 1px;
}}

.contract-value.calls {{ color: var(--success); }}
.contract-value.puts {{ color: var(--danger); }}

.setup-targets {{
    margin-bottom: var(--space-3);
}}

.targets-row {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
}}

.target-item {{
    background: var(--bg-surface-2);
    border-radius: 4px;
    padding: 6px 4px;
    text-align: center;
}}

.target-pct {{
    font-size: 9px;
    color: var(--text-tertiary);
    font-weight: 500;
}}

.target-profit {{
    font-family: var(--font-mono);
    font-size: 10px;
    font-weight: 600;
    color: var(--success);
    margin-top: 1px;
}}

.setup-risk {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--danger-soft);
    border-radius: var(--radius-sm);
    padding: var(--space-2) var(--space-3);
}}

.risk-label {{
    font-size: 10px;
    font-weight: 500;
    color: var(--danger);
}}

.risk-value {{
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    color: var(--danger);
}}

/* Collapsed state */
.setups-section.collapsed .setups-body {{ display: none; }}
.setups-section.collapsed .setups-chevron {{ transform: rotate(-90deg); }}

/* ─────────────────────────────────────────────────────────────────
   DATA TABLE
   ───────────────────────────────────────────────────────────────── */

.table-section {{
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    margin-bottom: var(--space-5);
}}

.table-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--border);
    cursor: pointer;
}}

.table-header:hover {{
    background: var(--bg-surface-2);
}}

.table-title {{
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
}}

.data-table {{
    width: 100%;
    border-collapse: collapse;
}}

.data-table th {{
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    color: var(--text-tertiary);
    padding: var(--space-3);
    text-align: left;
    background: var(--bg-surface-2);
    border-bottom: 1px solid var(--border);
}}

.data-table td {{
    font-size: 12px;
    padding: var(--space-3);
    border-bottom: 1px solid var(--border);
}}

.data-table tr:last-child td {{
    border-bottom: none;
}}

.data-table tr:hover {{
    background: var(--bg-surface-2);
}}

.table-section.collapsed .data-table {{ display: none; }}
.table-section.collapsed .table-header {{ border-bottom: none; }}

/* ─────────────────────────────────────────────────────────────────
   FOOTER
   ───────────────────────────────────────────────────────────────── */

.footer {{
    text-align: center;
    padding: var(--space-5);
    border-top: 1px solid var(--border);
    margin-top: var(--space-6);
}}

.footer-brand {{
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: var(--space-1);
}}

.footer-meta {{
    font-size: 11px;
    color: var(--text-tertiary);
}}

/* ─────────────────────────────────────────────────────────────────
   UTILITIES
   ───────────────────────────────────────────────────────────────── */

.mono {{ font-family: var(--font-mono); }}
.text-success {{ color: var(--success); }}
.text-danger {{ color: var(--danger); }}
.text-warning {{ color: var(--warning); }}
.text-muted {{ color: var(--text-tertiary); }}

</style>
</head>
<body>
<div class="dashboard">

<!-- HEADER -->
<header class="header">
    <div class="logo">
        <div class="logo-mark">SPX</div>
        <div class="logo-text">
            <div class="logo-title">SPX Prophet</div>
            <div class="logo-subtitle">Where Structure Becomes Foresight</div>
        </div>
    </div>
    <div class="header-meta">
        <div class="meta-group">
            <div class="meta-item">
                <div class="meta-label">Entry Window</div>
                <div class="meta-value">{format_countdown(get_time_until(ENTRY_TARGET))}</div>
            </div>
            <div class="meta-item">
                <div class="meta-label">Cutoff</div>
                <div class="meta-value">{format_countdown(get_time_until(CUTOFF_TIME))}</div>
            </div>
        </div>
        <div class="clock">{now.strftime("%H:%M")}</div>
    </div>
</header>
'''
    
    # Alert banners
    if is_historical:
        html += f'<div style="background:var(--bg-surface-2);border:1px solid var(--border);border-radius:var(--radius-md);padding:var(--space-3) var(--space-4);margin-bottom:var(--space-4);font-size:12px;color:var(--text-secondary);">📅 Historical Mode: {trading_date.strftime("%A, %B %d, %Y")}</div>'
    
    # Check for NO TRADE conditions
    # TRUE NO TRADE = signal conflict only. Low score = warning, not no-trade
    has_conflict = confluence and confluence.no_trade
    is_weak_setup = total_score < 65 and not has_conflict
    
    # Determine date context for messaging
    today = get_ct_now().date()
    if trading_date == today:
        date_context = "Today"
    elif trading_date > today:
        date_context = trading_date.strftime("%A")  # "Wednesday"
    else:
        date_context = trading_date.strftime("%b %d")  # "Dec 30"
    
    # Determine confluence status
    conf_class = "strong" if confluence and confluence.is_aligned else "conflict" if confluence and confluence.signal_strength == "CONFLICT" else "moderate" if confluence and confluence.signal_strength == "MODERATE" else "weak"
    conf_text = confluence.recommendation if confluence else "No data"
    
    # Signal Hero Section - only grey out for TRUE conflict
    if has_conflict:
        direction_class = "notrade"
    else:
        direction_class = "calls" if vix_zone.bias == "CALLS" else "puts" if vix_zone.bias == "PUTS" else "wait"
    
    # Determine the actual direction to show (use MA if VIX is mid-zone)
    if vix_zone.bias in ["CALLS", "PUTS"]:
        show_direction = vix_zone.bias
        direction_text = "Go Long" if vix_zone.bias == "CALLS" else "Go Short"
    elif ma_bias and ma_bias.bias in ["LONG", "SHORT"]:
        show_direction = "CALLS" if ma_bias.bias == "LONG" else "PUTS"
        direction_text = "Lean Long" if ma_bias.bias == "LONG" else "Lean Short"
        direction_class = "calls" if ma_bias.bias == "LONG" else "puts"
    else:
        show_direction = "WAIT"
        direction_text = "Wait for Setup"
    
    # Score ring calculation
    score_pct = total_score / 100 if total_score > 0 else 0
    circumference = 2 * 3.14159 * 58
    stroke_offset = circumference * (1 - score_pct)
    score_class = "a" if total_score >= 80 else "b" if total_score >= 65 else "c" if total_score >= 50 else "d"
    
    # Find BEST setup (matches direction + closest to price + widest cone)
    # PRIORITY: If inside a cone, that cone's setup is best (when direction matches)
    best_setup = None
    search_direction = show_direction if show_direction in ["CALLS", "PUTS"] else None
    if search_direction and not has_conflict:
        # Exclude GREY and BROKEN setups from consideration
        matching = [s for s in setups if s.direction == search_direction and s.status not in ["GREY", "BROKEN"]]
        if matching:
            # PRIORITY 1: If inside a cone and that cone has a matching setup, use it
            if price_proximity and price_proximity.inside_cone and price_proximity.inside_cone_name:
                inside_match = [s for s in matching if s.cone_name == price_proximity.inside_cone_name]
                if inside_match:
                    best_setup = inside_match[0]  # The setup from the cone we're inside
            
            # PRIORITY 2: Otherwise, score by proximity to current price
            if not best_setup:
                def setup_score(s):
                    # If overnight price provided, use distance from price to entry
                    if price_proximity and price_proximity.current_price > 0:
                        price_to_entry = abs(s.entry - price_proximity.current_price)
                        distance_score = max(0, 50 - price_to_entry)  # Closer to current price = higher score
                    else:
                        distance_score = max(0, 30 - s.distance)  # Closer = higher score
                    width_score = s.cone_width  # Wider = higher score
                    return distance_score + width_score
                best_setup = max(matching, key=setup_score)
    
    # Breakout indicator
    breakout_html = ""
    if vix_zone.is_breakout:
        breakout_html = f'''
        <div style="background:var(--warning-soft);color:var(--warning);padding:var(--space-2) var(--space-3);border-radius:var(--radius-sm);font-size:11px;font-weight:600;margin-top:var(--space-2);">
            ⚡ BREAKOUT {vix_zone.breakout_direction} — Spring/Resistance: {vix_zone.breakout_level:.2f}
        </div>
'''
    
    # Weak setup warning (shows direction but with warning)
    weak_warning_html = ""
    if is_weak_setup:
        weak_warning_html = f'''
        <div style="background:var(--warning-soft);color:var(--warning);padding:var(--space-2) var(--space-3);border-radius:var(--radius-sm);font-size:11px;font-weight:500;margin-top:var(--space-2);">
            ⚠️ Weak Setup — Score {total_score}/100 (65+ recommended)
        </div>
'''
    
    html += f'''
<!-- SIGNAL HERO -->
<div class="signal-hero" style="{'opacity:0.4;' if has_conflict else ''}">
    <div class="signal-main">
        <div class="signal-direction">
            <div class="direction-badge {direction_class}" style="{'background:var(--danger-soft);color:var(--danger);' if has_conflict else ''}">
                {"⛔" if has_conflict else "↑" if show_direction == "CALLS" else "↓" if show_direction == "PUTS" else "–"} {"NO TRADE" if has_conflict else show_direction}
            </div>
        </div>
        <div>
            <div class="signal-title {direction_class}" style="{'color:var(--danger);' if has_conflict else ''}">
                {"No Trade — " + date_context if has_conflict else direction_text}
            </div>
            <div class="signal-subtitle">{confluence.no_trade_reason if has_conflict else vix_zone.bias_reason}</div>
            {breakout_html}
            {weak_warning_html}
        </div>
        <div class="signal-confluence">
            <div class="confluence-dot {conf_class}"></div>
            <div class="confluence-text">{conf_text}</div>
        </div>
        <div class="signal-metrics">
            <div class="metric">
                <div class="metric-value">{vix_zone.current:.2f}</div>
                <div class="metric-label">VIX</div>
            </div>
            <div class="metric">
                <div class="metric-value">{vix_zone.position_pct:.0f}%</div>
                <div class="metric-label">Zone Position</div>
            </div>
            <div class="metric">
                <div class="metric-value {'' if ma_bias.bias == 'NEUTRAL' else 'success' if ma_bias.bias == 'LONG' else 'danger'}">{ma_bias.bias}</div>
                <div class="metric-label">MA Bias</div>
            </div>
            <div class="metric">
                <div class="metric-value">{spx_price:,.0f}</div>
                <div class="metric-label">SPX</div>
            </div>
        </div>
    </div>
    <div class="signal-score">
        <div class="score-ring">
            <svg width="140" height="140" viewBox="0 0 140 140">
                <circle class="score-ring-bg" cx="70" cy="70" r="58"></circle>
                <circle class="score-ring-fill {score_class}" cx="70" cy="70" r="58" 
                    stroke-dasharray="{circumference}" 
                    stroke-dashoffset="{stroke_offset}"></circle>
            </svg>
            <div class="score-center">
                <div class="score-value" style="color:var(--{"success" if total_score >= 80 else "info" if total_score >= 65 else "warning" if total_score >= 50 else "danger"});">{total_score}</div>
                <div class="score-grade">Grade {grade}</div>
            </div>
        </div>
        <div class="score-label">Trade Readiness</div>
    </div>
</div>
'''

    # Price Proximity Alert Box (only show if overnight price provided)
    if price_proximity and price_proximity.current_price > 0:
        # Determine alert styling based on position
        if price_proximity.position == "NEAR_RAIL":
            prox_bg = "linear-gradient(135deg, rgba(34,197,94,0.15) 0%, rgba(34,197,94,0.05) 100%)"
            prox_border = "var(--success)"
            prox_icon = "🎯"
            prox_title = "SETUP ACTIVE"
        elif price_proximity.position == "ABOVE_ALL":
            prox_bg = "linear-gradient(135deg, rgba(239,68,68,0.15) 0%, rgba(239,68,68,0.05) 100%)"
            prox_border = "var(--danger)"
            prox_icon = "⚡"
            prox_title = "EXTENDED ABOVE"
        elif price_proximity.position == "BELOW_ALL":
            prox_bg = "linear-gradient(135deg, rgba(239,68,68,0.15) 0%, rgba(239,68,68,0.05) 100%)"
            prox_border = "var(--danger)"
            prox_icon = "⚡"
            prox_title = "EXTENDED BELOW"
        elif price_proximity.position == "INSIDE_CONE":
            prox_bg = "linear-gradient(135deg, rgba(234,179,8,0.15) 0%, rgba(234,179,8,0.05) 100%)"
            prox_border = "var(--warning)"
            prox_icon = "📍"
            prox_title = "INSIDE STRUCTURE"
        else:
            prox_bg = "var(--bg-surface)"
            prox_border = "var(--border)"
            prox_icon = "📍"
            prox_title = "PRICE POSITION"
        
        # Build rail distances display for each cone - show actual prices and distances
        rail_dist_html = ""
        if price_proximity.rail_distances:
            rail_dist_html = '<div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(180px, 1fr));gap:var(--space-3);margin-top:var(--space-3);">'
            for cone_name, dists in price_proximity.rail_distances.items():
                asc_dist = dists["ascending"]
                desc_dist = dists["descending"]
                asc_rail = dists["asc_rail"]
                desc_rail = dists["desc_rail"]
                asc_color = "var(--success)" if abs(asc_dist) <= 8 else "var(--text-secondary)"
                desc_color = "var(--success)" if abs(desc_dist) <= 8 else "var(--text-secondary)"
                # Highlight the cone we're inside
                is_inside = price_proximity.inside_cone and price_proximity.inside_cone_name == cone_name
                box_border = "border:1px solid var(--warning);" if is_inside else ""
                rail_dist_html += f'''
                <div style="background:var(--bg-elevated);padding:var(--space-2) var(--space-3);border-radius:var(--radius-sm);font-size:11px;{box_border}">
                    <div style="font-weight:600;color:var(--text-primary);margin-bottom:6px;">{cone_name}{"  ◀ YOU ARE HERE" if is_inside else ""}</div>
                    <div style="display:flex;justify-content:space-between;gap:var(--space-3);">
                        <div>
                            <div style="color:var(--text-muted);font-size:9px;margin-bottom:2px;">PUTS Entry ↑</div>
                            <div style="color:{asc_color};font-weight:600;">{asc_rail:,.0f} <span style="font-weight:400;">({asc_dist:+.0f})</span></div>
                        </div>
                        <div style="text-align:right;">
                            <div style="color:var(--text-muted);font-size:9px;margin-bottom:2px;">CALLS Entry ↓</div>
                            <div style="color:{desc_color};font-weight:600;">{desc_rail:,.0f} <span style="font-weight:400;">({desc_dist:+.0f})</span></div>
                        </div>
                    </div>
                </div>'''
            rail_dist_html += '</div>'
        
        html += f'''
<!-- PRICE PROXIMITY ALERT -->
<div style="background:{prox_bg};border:1px solid {prox_border};border-radius:var(--radius-lg);padding:var(--space-4);margin-bottom:var(--space-4);">
    <div style="display:flex;align-items:flex-start;gap:var(--space-3);">
        <div style="font-size:28px;">{prox_icon}</div>
        <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:var(--space-2);margin-bottom:var(--space-1);">
                <span style="font-size:12px;font-weight:700;color:var(--text-primary);letter-spacing:0.5px;">{prox_title}</span>
                <span style="font-size:18px;font-weight:700;color:var(--text-primary);font-family:var(--font-mono);">SPX @ {price_proximity.current_price:,.2f}</span>
            </div>
            <div style="font-size:13px;color:var(--text-secondary);margin-bottom:var(--space-2);">{price_proximity.position_detail}</div>
            <div style="font-size:14px;font-weight:600;color:var(--text-primary);">{price_proximity.action_detail}</div>
            {rail_dist_html}
        </div>
        <div style="text-align:right;">
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:2px;">Nearest Rail</div>
            <div style="font-size:16px;font-weight:700;font-family:var(--font-mono);color:var(--text-primary);">{price_proximity.nearest_rail:,.0f}</div>
            <div style="font-size:12px;color:var(--text-secondary);">{price_proximity.nearest_rail_distance:+.0f} pts</div>
        </div>
    </div>
</div>
'''

    # VIX Section
    html += f'''
<!-- VIX METER -->
<div class="vix-section">
    <div class="section-header">
        <div class="section-title">VIX Zone Analysis</div>
    </div>
    <div class="vix-display">
        <div style="flex:1;">
            <div class="vix-meter-track">
                <div class="vix-meter-thumb" style="left:{marker_pos}%"></div>
            </div>
            <div class="vix-meter-labels">
                <span>{vix_zone.bottom:.2f}</span>
                <span>Zone: {vix_zone.zone_size:.2f} ({vix_zone.zones_away:+d} away)</span>
                <span>{vix_zone.top:.2f}</span>
            </div>
        </div>
        <div class="vix-current">
            <div class="vix-current-value">{vix_zone.current:.2f}</div>
            <div class="vix-current-label">Current VIX</div>
        </div>
    </div>
</div>
'''

    # Indicator Cards
    ma_status_class = "long" if ma_bias.bias == "LONG" else "short" if ma_bias.bias == "SHORT" else "neutral"
    
    html += f'''
<!-- INDICATOR CARDS -->
<div class="indicators-grid">
    <div class="indicator-card">
        <div class="indicator-header">
            <div class="indicator-title">30-Min MA Bias</div>
            <div class="indicator-status {ma_status_class}"></div>
        </div>
        <div class="indicator-value {ma_status_class}">{ma_bias.bias}</div>
        <div class="indicator-detail">{ma_bias.bias_reason}</div>
    </div>
'''
    
    # Entry Window Card
    if market_ctx:
        window_class = "long" if market_ctx.is_prime_time else "neutral"
        window_text = "OPTIMAL" if market_ctx.is_prime_time else market_ctx.time_warning.upper() if market_ctx.time_warning else "PRE-MARKET"
        html += f'''
    <div class="indicator-card">
        <div class="indicator-header">
            <div class="indicator-title">Entry Window</div>
            <div class="indicator-status {window_class}"></div>
        </div>
        <div class="indicator-value {window_class}">{window_text}</div>
        <div class="indicator-detail">Stop: {market_ctx.recommended_stop:.0f} pts | VIX Level: {market_ctx.vix_level}</div>
    </div>
'''
    
    # Gap Card
    if gap_analysis and gap_analysis.gap_direction != "FLAT":
        gap_class = "long" if gap_analysis.trade_bias == "CALLS" else "short" if gap_analysis.trade_bias == "PUTS" else "neutral"
        html += f'''
    <div class="indicator-card">
        <div class="indicator-header">
            <div class="indicator-title">Overnight Gap</div>
            <div class="indicator-status {gap_class}"></div>
        </div>
        <div class="indicator-value {gap_class}">{gap_analysis.gap_pct:+.2f}%</div>
        <div class="indicator-detail">{gap_analysis.trade_reason}</div>
    </div>
'''
    
    # Price Proximity Card (only show if overnight price provided)
    if price_proximity and price_proximity.current_price > 0:
        prox_class = "long" if price_proximity.position == "NEAR_RAIL" else "short" if price_proximity.position in ["ABOVE_ALL", "BELOW_ALL"] else "neutral"
        prox_icon = "🎯" if price_proximity.position == "NEAR_RAIL" else "⚡" if price_proximity.position in ["ABOVE_ALL", "BELOW_ALL"] else "📍"
        html += f'''
    <div class="indicator-card">
        <div class="indicator-header">
            <div class="indicator-title">Price Proximity</div>
            <div class="indicator-status {prox_class}"></div>
        </div>
        <div class="indicator-value {prox_class}">{prox_icon} {price_proximity.position.replace("_", " ")}</div>
        <div class="indicator-detail">{price_proximity.position_detail}</div>
    </div>
'''
    
    html += '</div>'
    
    # CALLS Setups Section
    html += f'''
<!-- CALLS SETUPS -->
<div class="setups-section" id="calls-section">
    <div class="setups-header">
        <div class="setups-title calls">
            <span>↑</span>
            <span>Calls Setups</span>
            <span class="setups-count calls">{len(calls_setups)}</span>
        </div>
        <span class="setups-chevron">▾</span>
    </div>
    <div class="setups-body">
        <div class="setups-grid">
'''
    for s in calls_setups:
        opt = s.option
        is_best = best_setup and s.cone_name == best_setup.cone_name and s.direction == best_setup.direction
        is_broken = s.status == "BROKEN"
        
        # Status class and text
        if is_broken:
            status_class = "broken"
            status_text = "🚫 BROKEN"
            status_style = "broken"
        elif s.status == "ACTIVE":
            status_class = "active"
            status_text = "★ BEST" if is_best else "ACTIVE"
            status_style = "best" if is_best else "active"
        elif s.status == "GREY":
            status_class = "grey"
            status_text = "CLOSED"
            status_style = "grey"
        else:
            status_class = ""
            status_text = "★ BEST" if is_best else "WAIT"
            status_style = "best" if is_best else "wait"
        
        best_style = "border:2px solid var(--warning);box-shadow:0 0 20px rgba(234,179,8,0.3);" if is_best and not is_broken else ""
        broken_style = "opacity:0.5;border:1px solid var(--danger);" if is_broken else ""
        
        # Calculate distance from overnight price if available
        if price_proximity and price_proximity.current_price > 0:
            price_to_entry = s.entry - price_proximity.current_price
            distance_display = f"{price_to_entry:+.0f} pts from price"
            distance_color = "var(--success)" if abs(price_to_entry) <= 8 else "var(--text-secondary)"
        else:
            distance_display = f"{s.distance:.0f} pts away"
            distance_color = "var(--text-secondary)"
        
        html += f'''
            <div class="setup-card calls {status_class}" style="{best_style}{broken_style}">
                <div class="setup-header">
                    <div class="setup-name">{"⭐ " if is_best and not is_broken else ""}{s.cone_name}</div>
                    <div class="setup-status {status_style}" style="{'background:var(--danger-soft);color:var(--danger);' if is_broken else 'background:var(--warning-soft);color:var(--warning);' if is_best else ''}">{status_text}</div>
                </div>
                <div class="setup-entry">
                    <div class="setup-entry-label">Entry Rail</div>
                    <div class="setup-entry-price calls">{s.entry:,.2f}</div>
                    <div class="setup-entry-distance" style="color:{distance_color};">{distance_display}</div>
                </div>
                <div class="setup-contract">
                    <div class="contract-item">
                        <div class="contract-label">Strike</div>
                        <div class="contract-value calls">{opt.spx_strike}C</div>
                    </div>
                    <div class="contract-item">
                        <div class="contract-label">Premium</div>
                        <div class="contract-value">${opt.spx_price_est:.2f}</div>
                    </div>
                </div>
                <div class="setup-targets">
                    <div class="targets-row">
                        <div class="target-item"><div class="target-pct">25%</div><div class="target-profit">+${s.profit_25:,.0f}</div></div>
                        <div class="target-item"><div class="target-pct">50%</div><div class="target-profit">+${s.profit_50:,.0f}</div></div>
                        <div class="target-item"><div class="target-pct">75%</div><div class="target-profit">+${s.profit_75:,.0f}</div></div>
                        <div class="target-item"><div class="target-pct">100%</div><div class="target-profit">+${s.profit_100:,.0f}</div></div>
                    </div>
                </div>
                <div class="setup-risk">
                    <div class="risk-label">Stop: {s.stop:,.0f}</div>
                    <div class="risk-value">-${s.risk_dollars:,.0f}</div>
                </div>
            </div>
'''
    html += '</div></div></div>'
    
    # PUTS Setups Section
    html += f'''
<!-- PUTS SETUPS -->
<div class="setups-section collapsed" id="puts-section">
    <div class="setups-header">
        <div class="setups-title puts">
            <span>↓</span>
            <span>Puts Setups</span>
            <span class="setups-count puts">{len(puts_setups)}</span>
        </div>
        <span class="setups-chevron">▾</span>
    </div>
    <div class="setups-body">
        <div class="setups-grid">
'''
    for s in puts_setups:
        opt = s.option
        is_best = best_setup and s.cone_name == best_setup.cone_name and s.direction == best_setup.direction
        is_broken = s.status == "BROKEN"
        
        # Status class and text
        if is_broken:
            status_class = "broken"
            status_text = "🚫 BROKEN"
            status_style = "broken"
        elif s.status == "ACTIVE":
            status_class = "active puts"
            status_text = "★ BEST" if is_best else "ACTIVE"
            status_style = "best" if is_best else "active"
        elif s.status == "GREY":
            status_class = "grey"
            status_text = "CLOSED"
            status_style = "grey"
        else:
            status_class = ""
            status_text = "★ BEST" if is_best else "WAIT"
            status_style = "best" if is_best else "wait"
        
        best_style = "border:2px solid var(--warning);box-shadow:0 0 20px rgba(234,179,8,0.3);" if is_best and not is_broken else ""
        broken_style = "opacity:0.5;border:1px solid var(--danger);" if is_broken else ""
        
        # Calculate distance from overnight price if available
        if price_proximity and price_proximity.current_price > 0:
            price_to_entry = s.entry - price_proximity.current_price
            distance_display = f"{price_to_entry:+.0f} pts from price"
            distance_color = "var(--success)" if abs(price_to_entry) <= 8 else "var(--text-secondary)"
        else:
            distance_display = f"{s.distance:.0f} pts away"
            distance_color = "var(--text-secondary)"
        
        html += f'''
            <div class="setup-card puts {status_class}" style="{best_style}{broken_style}">
                <div class="setup-header">
                    <div class="setup-name">{"⭐ " if is_best and not is_broken else ""}{s.cone_name}</div>
                    <div class="setup-status {status_style}" style="{'background:var(--danger-soft);color:var(--danger);' if is_broken else 'background:var(--warning-soft);color:var(--warning);' if is_best else ''}">{status_text}</div>
                </div>
                <div class="setup-entry">
                    <div class="setup-entry-label">Entry Rail</div>
                    <div class="setup-entry-price puts">{s.entry:,.2f}</div>
                    <div class="setup-entry-distance" style="color:{distance_color};">{distance_display}</div>
                </div>
                <div class="setup-contract">
                    <div class="contract-item">
                        <div class="contract-label">Strike</div>
                        <div class="contract-value puts">{opt.spx_strike}P</div>
                    </div>
                    <div class="contract-item">
                        <div class="contract-label">Premium</div>
                        <div class="contract-value">${opt.spx_price_est:.2f}</div>
                    </div>
                </div>
                <div class="setup-targets">
                    <div class="targets-row">
                        <div class="target-item"><div class="target-pct">25%</div><div class="target-profit">+${s.profit_25:,.0f}</div></div>
                        <div class="target-item"><div class="target-pct">50%</div><div class="target-profit">+${s.profit_50:,.0f}</div></div>
                        <div class="target-item"><div class="target-pct">75%</div><div class="target-profit">+${s.profit_75:,.0f}</div></div>
                        <div class="target-item"><div class="target-pct">100%</div><div class="target-profit">+${s.profit_100:,.0f}</div></div>
                    </div>
                </div>
                <div class="setup-risk">
                    <div class="risk-label">Stop: {s.stop:,.0f}</div>
                    <div class="risk-value">-${s.risk_dollars:,.0f}</div>
                </div>
            </div>
'''
    html += '</div></div></div>'
    
    # Prior Session Stats
    html += f'''
<!-- PRIOR SESSION -->
<div class="table-section">
    <div class="table-header">
        <div class="table-title">📈 Prior Session ({pivot_date.strftime("%b %d")})</div>
        <span class="setups-chevron">▾</span>
    </div>
    <div style="padding:var(--space-4);display:grid;grid-template-columns:repeat(4,1fr);gap:var(--space-3);">
        <div style="background:var(--bg-surface-2);border-radius:var(--radius-md);padding:var(--space-3);text-align:center;">
            <div class="mono text-success" style="font-size:16px;font-weight:600;">{prior_session.get("high",0):,.2f}</div>
            <div style="font-size:10px;color:var(--text-tertiary);text-transform:uppercase;margin-top:4px;">High</div>
        </div>
        <div style="background:var(--bg-surface-2);border-radius:var(--radius-md);padding:var(--space-3);text-align:center;">
            <div class="mono text-danger" style="font-size:16px;font-weight:600;">{prior_session.get("low",0):,.2f}</div>
            <div style="font-size:10px;color:var(--text-tertiary);text-transform:uppercase;margin-top:4px;">Low</div>
        </div>
        <div style="background:var(--bg-surface-2);border-radius:var(--radius-md);padding:var(--space-3);text-align:center;">
            <div class="mono" style="font-size:16px;font-weight:600;">{prior_session.get("close",0):,.2f}</div>
            <div style="font-size:10px;color:var(--text-tertiary);text-transform:uppercase;margin-top:4px;">Close</div>
        </div>
        <div style="background:var(--bg-surface-2);border-radius:var(--radius-md);padding:var(--space-3);text-align:center;">
            <div class="mono" style="font-size:16px;font-weight:600;color:var(--info);">{prior_session.get("high",0) - prior_session.get("low",0):,.0f}</div>
            <div style="font-size:10px;color:var(--text-tertiary);text-transform:uppercase;margin-top:4px;">Range</div>
        </div>
    </div>
</div>
'''
    
    # Structural Cones
    html += f'''
<!-- STRUCTURAL CONES -->
<div class="table-section">
    <div class="table-header">
        <div class="table-title">📐 Structural Cones</div>
        <span class="setups-chevron">▾</span>
    </div>
    <table class="data-table">
        <thead>
            <tr>
                <th>Pivot</th>
                <th>Ascending (Puts)</th>
                <th>Descending (Calls)</th>
                <th>Width</th>
                <th>Tradeable</th>
            </tr>
        </thead>
        <tbody>
'''
    for c in cones:
        width_color = "text-success" if c.width >= 25 else "text-warning" if c.width >= MIN_CONE_WIDTH else "text-danger"
        badge = '<span style="background:var(--success-soft);color:var(--success);padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;">YES</span>' if c.is_tradeable else '<span style="background:var(--danger-soft);color:var(--danger);padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;">NO</span>'
        html += f'''
            <tr>
                <td><strong>{c.name}</strong></td>
                <td class="mono text-danger">{c.ascending_rail:,.2f}</td>
                <td class="mono text-success">{c.descending_rail:,.2f}</td>
                <td class="mono {width_color}">{c.width:.0f} pts</td>
                <td>{badge}</td>
            </tr>
'''
    html += '''
        </tbody>
    </table>
</div>
'''
    
    # Pivot Table (collapsed by default)
    html += f'''
<!-- PIVOT TABLE -->
<div class="table-section collapsed">
    <div class="table-header">
        <div class="table-title">📋 Pivot Time Table</div>
        <span class="setups-chevron">▾</span>
    </div>
    <table class="data-table">
        <thead>
            <tr>
                <th>Time CT</th>
                <th>High ▲</th>
                <th>High ▼</th>
                <th>Low ▲</th>
                <th>Low ▼</th>
                <th>Close ▲</th>
                <th>Close ▼</th>
            </tr>
        </thead>
        <tbody>
'''
    for row in pivot_table:
        is_inst = INST_WINDOW_START <= row.time_ct <= INST_WINDOW_END
        inst_marker = " 🏛️" if is_inst else ""
        row_style = f'style="background:var(--warning-soft);"' if is_inst else ""
        html += f'''
            <tr {row_style}>
                <td><strong>{row.time_block}{inst_marker}</strong></td>
                <td class="mono text-danger">{row.prior_high_asc:,.2f}</td>
                <td class="mono text-success">{row.prior_high_desc:,.2f}</td>
                <td class="mono text-danger">{row.prior_low_asc:,.2f}</td>
                <td class="mono text-success">{row.prior_low_desc:,.2f}</td>
                <td class="mono text-danger">{row.prior_close_asc:,.2f}</td>
                <td class="mono text-success">{row.prior_close_desc:,.2f}</td>
            </tr>
'''
    html += '''
        </tbody>
    </table>
</div>
'''
    
    # Footer
    html += f'''
<!-- FOOTER -->
<footer class="footer">
    <div class="footer-brand">SPX Prophet v7.2</div>
    <div class="footer-meta">Where Structure Becomes Foresight | {trading_date.strftime("%B %d, %Y")}</div>
</footer>

<script>
// Handle all collapsible sections
document.addEventListener('DOMContentLoaded', function() {{
    // Setup sections (Calls/Puts)
    document.querySelectorAll('.setups-header').forEach(function(header) {{
        header.addEventListener('click', function(e) {{
            e.preventDefault();
            e.stopPropagation();
            var section = this.parentElement;
            if (section) {{
                section.classList.toggle('collapsed');
            }}
        }});
    }});
    
    // Table sections
    document.querySelectorAll('.table-header').forEach(function(header) {{
        header.addEventListener('click', function(e) {{
            e.preventDefault();
            e.stopPropagation();
            var section = this.parentElement;
            if (section) {{
                section.classList.toggle('collapsed');
            }}
        }});
    }});
    
    // Card headers (other collapsible cards)
    document.querySelectorAll('.card-header').forEach(function(header) {{
        header.addEventListener('click', function(e) {{
            e.preventDefault();
            e.stopPropagation();
            var card = this.parentElement;
            if (card) {{
                card.classList.toggle('collapsed');
            }}
        }});
    }});
}});
</script>

</div>
</body>
</html>
'''
    return html

def main():
    st.set_page_config(page_title="SPX Prophet", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
    defaults = {'theme': 'dark', 'vix_bottom': 0.0, 'vix_top': 0.0, 'vix_current': 0.0, 'entry_time_mins': 30, 'use_manual_pivots': False, 'high_price': 0.0, 'high_time': "10:30", 'low_price': 0.0, 'low_time': "14:00", 'close_price': 0.0, 'trading_date': None, 'last_refresh': None}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    
    with st.sidebar:
        st.markdown("## 📈 SPX Prophet")
        st.caption("Where Structure Becomes Foresight")
        st.divider()
        theme = st.radio("🎨 Theme", ["Dark", "Light"], horizontal=True, index=0 if st.session_state.theme == "dark" else 1)
        st.session_state.theme = theme.lower()
        st.divider()
        st.markdown("### 📅 Trading Date")
        today = get_ct_now().date()
        next_trade = get_next_trading_day(today)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📍 Next", use_container_width=True):
                st.session_state.trading_date = next_trade
        with col2:
            if st.button("📆 Prior", use_container_width=True):
                st.session_state.trading_date = get_prior_trading_day(today)
        selected_date = st.date_input("Select", value=st.session_state.trading_date or next_trade, min_value=today - timedelta(days=730), max_value=today + timedelta(days=400))
        st.session_state.trading_date = selected_date
        if is_holiday(selected_date):
            holiday_name = HOLIDAYS_2025.get(selected_date) or HOLIDAYS_2026.get(selected_date, "Holiday")
            st.error(f"🚫 {holiday_name} - Closed")
        elif is_half_day(selected_date):
            half_day_name = HALF_DAYS_2025.get(selected_date) or HALF_DAYS_2026.get(selected_date, "Half Day")
            st.warning(f"⏰ {half_day_name} - 12pm CT")
        prior = get_prior_trading_day(selected_date)
        prior_info = get_session_info(prior)
        if prior_info.get("is_half_day"):
            st.info(f"📌 Pivot: {prior.strftime('%b %d')} (Half Day)")
        st.divider()
        st.markdown("### 📊 VIX Zone")
        
        # Auto-fetch VIX button
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("🔄 Auto-Fetch VIX", use_container_width=True):
                vix_low, vix_high, vix_curr = fetch_vix_zone_auto()
                if vix_low > 0:
                    st.session_state.vix_bottom = vix_low
                    st.session_state.vix_top = vix_high
                    st.session_state.vix_current = vix_curr
                    st.success(f"VIX: {vix_low:.2f} - {vix_high:.2f} (Current: {vix_curr:.2f})")
                else:
                    # Try just current VIX
                    vix_val, src = fetch_vix_current()
                    if vix_val > 0:
                        st.session_state.vix_current = vix_val
                        st.info(f"Current VIX: {vix_val:.2f} ({src})")
                    else:
                        st.error("Could not fetch VIX data")
        
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.vix_bottom = st.number_input("Bottom", value=st.session_state.vix_bottom, step=0.01, format="%.2f")
        with col2:
            st.session_state.vix_top = st.number_input("Top", value=st.session_state.vix_top, step=0.01, format="%.2f")
        st.session_state.vix_current = st.number_input("Current VIX", value=st.session_state.vix_current, step=0.01, format="%.2f")
        st.divider()
        
        # OVERNIGHT SPX PRICE INPUT
        st.markdown("### 📍 Overnight SPX Price")
        st.caption("Enter current SPX/ES price for proximity analysis")
        
        # Initialize session state for overnight price
        if "overnight_spx" not in st.session_state:
            st.session_state.overnight_spx = 0.0
        
        st.session_state.overnight_spx = st.number_input(
            "Current SPX Price", 
            value=st.session_state.overnight_spx, 
            step=1.0, 
            format="%.2f",
            help="Enter the current overnight SPX futures price to see distance to entries"
        )
        
        if st.session_state.overnight_spx > 0:
            st.success(f"📊 Price tracking: {st.session_state.overnight_spx:,.2f}")
        else:
            st.caption("💡 Optional: Shows distance to entry rails")
        
        # STRUCTURE BROKEN CHECKBOXES
        # Initialize session state
        if "broken_prior_high" not in st.session_state:
            st.session_state.broken_prior_high = False
        if "broken_prior_low" not in st.session_state:
            st.session_state.broken_prior_low = False
        if "broken_prior_close" not in st.session_state:
            st.session_state.broken_prior_close = False
        
        st.caption("🚫 Mark broken if 30-min candle closed through rail:")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.session_state.broken_prior_high = st.checkbox("High", value=st.session_state.broken_prior_high, key="chk_high")
        with col2:
            st.session_state.broken_prior_low = st.checkbox("Low", value=st.session_state.broken_prior_low, key="chk_low")
        with col3:
            st.session_state.broken_prior_close = st.checkbox("Close", value=st.session_state.broken_prior_close, key="chk_close")
        
        st.divider()
        st.markdown("### ⏰ Entry Time")
        st.caption("Slide to estimate contract prices at your entry time")
        st.session_state.entry_time_mins = st.slider(
            "Entry Time (CT)", 
            min_value=0, 
            max_value=120, 
            value=st.session_state.entry_time_mins,
            step=10,
            format="%d mins after 8:30"
        )
        entry_hour = 8 + (30 + st.session_state.entry_time_mins) // 60
        entry_min = (30 + st.session_state.entry_time_mins) % 60
        st.caption(f"📍 Pricing at **{entry_hour}:{entry_min:02d} AM CT**")
        st.divider()
        
        # CONTRACT SLOPE CALCULATOR
        st.markdown("### 📈 Contract Slope")
        st.caption("Input 2 price points to project future prices")
        with st.expander("Open Calculator", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                slope_time1 = st.text_input("Time 1", value="7:30 PM", key="slope_t1", help="e.g., 7:30 PM, 8:30 AM")
                slope_price1 = st.number_input("Price 1", value=0.0, step=0.10, format="%.2f", key="slope_p1")
            with col2:
                slope_time2 = st.text_input("Time 2", value="7:30 AM", key="slope_t2")
                slope_price2 = st.number_input("Price 2", value=0.0, step=0.10, format="%.2f", key="slope_p2")
            
            if slope_price1 > 0 and slope_price2 > 0 and slope_price1 != slope_price2:
                # Parse times and calculate slope
                def parse_time_to_mins(t_str):
                    """Convert time string to minutes from midnight, handling PM/AM"""
                    t_str = t_str.strip().upper()
                    is_pm = "PM" in t_str or "P" in t_str
                    is_am = "AM" in t_str or "A" in t_str
                    t_str = t_str.replace("PM", "").replace("AM", "").replace("P", "").replace("A", "").strip()
                    parts = t_str.replace(":", " ").split()
                    hour = int(parts[0])
                    mins = int(parts[1]) if len(parts) > 1 else 0
                    if is_pm and hour != 12:
                        hour += 12
                    elif is_am and hour == 12:
                        hour = 0
                    return hour * 60 + mins
                
                try:
                    mins1 = parse_time_to_mins(slope_time1)
                    mins2 = parse_time_to_mins(slope_time2)
                    
                    # Handle overnight (if time2 < time1, add 24 hours)
                    if mins2 < mins1:
                        mins2 += 24 * 60
                    
                    time_diff = mins2 - mins1
                    price_diff = slope_price2 - slope_price1
                    slope_per_min = price_diff / time_diff if time_diff > 0 else 0
                    slope_per_30min = slope_per_min * 30
                    
                    st.success(f"**Slope:** ${slope_per_30min:+.3f}/30 mins")
                    
                    # Project prices at key times
                    st.markdown("**Projected Prices:**")
                    target_times = [
                        ("8:30 AM", 8 * 60 + 30),
                        ("9:00 AM", 9 * 60),
                        ("9:30 AM", 9 * 60 + 30),
                        ("10:00 AM", 10 * 60),
                    ]
                    
                    for label, target_mins in target_times:
                        # Handle overnight projection
                        if target_mins < mins1:
                            target_mins += 24 * 60
                        mins_from_p1 = target_mins - mins1
                        projected = slope_price1 + (slope_per_min * mins_from_p1)
                        st.write(f"  {label}: **${projected:.2f}**")
                        
                except Exception as e:
                    st.error(f"Invalid time format. Use: 7:30 PM or 8:30 AM")
        
        st.divider()
        
        # FIBONACCI RETRACE CALCULATOR
        st.markdown("### 📉 Retrace Calculator")
        st.caption("Calculate fib levels after morning spike")
        with st.expander("Open Calculator", expanded=False):
            fib_low = st.number_input("Spike Low $", value=0.0, step=0.10, format="%.2f", key="fib_low", help="Starting price before spike")
            fib_high = st.number_input("Spike High $", value=0.0, step=0.10, format="%.2f", key="fib_high", help="Top of spike (usually before 9 AM)")
            
            if fib_low > 0 and fib_high > fib_low:
                range_size = fib_high - fib_low
                
                fib_786 = fib_high - (range_size * 0.786)
                fib_618 = fib_high - (range_size * 0.618)
                fib_500 = fib_high - (range_size * 0.500)
                fib_382 = fib_high - (range_size * 0.382)
                
                st.markdown("**Retrace Levels:**")
                st.write(f"  0.786 (Deep): **${fib_786:.2f}** ← Optimal Entry")
                st.write(f"  0.618 (Golden): **${fib_618:.2f}**")
                st.write(f"  0.500 (Half): **${fib_500:.2f}**")
                st.write(f"  0.382 (Shallow): **${fib_382:.2f}**")
                
                st.info(f"Range: ${range_size:.2f} | Entry Zone: ${fib_786:.2f} - ${fib_618:.2f}")
        
        st.divider()
        st.markdown("### 📍 Manual Pivots")
        st.session_state.use_manual_pivots = st.checkbox("Override Auto", st.session_state.use_manual_pivots)
        if st.session_state.use_manual_pivots:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.high_price = st.number_input("High $", value=st.session_state.high_price, step=0.01, format="%.2f")
            with c2:
                st.session_state.high_time = st.text_input("Time", value=st.session_state.high_time, key="ht")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.low_price = st.number_input("Low $", value=st.session_state.low_price, step=0.01, format="%.2f")
            with c2:
                st.session_state.low_time = st.text_input("Time", value=st.session_state.low_time, key="lt")
            st.session_state.close_price = st.number_input("Close $", value=st.session_state.close_price, step=0.01, format="%.2f")
        st.divider()
        if st.button("🔄 REFRESH", use_container_width=True, type="primary"):
            st.session_state.last_refresh = get_ct_now()
            st.rerun()
        if st.session_state.last_refresh:
            st.caption(f"Updated: {st.session_state.last_refresh.strftime('%H:%M:%S CT')}")
    
    now = get_ct_now()
    trading_date = st.session_state.trading_date or get_next_trading_day()
    if is_holiday(trading_date):
        trading_date = get_next_trading_day(trading_date)
    pivot_date = get_prior_trading_day(trading_date)
    pivot_session_info = get_session_info(pivot_date)
    pivot_close_time = pivot_session_info.get("close_ct", REGULAR_CLOSE)
    is_historical = trading_date < now.date() or (trading_date == now.date() and now.time() > CUTOFF_TIME)
    
    # Debug: Show what dates we're using in sidebar
    with st.sidebar:
        st.caption(f"📊 Trading: {trading_date} | Pivot: {pivot_date}")
    
    prior_bars = polygon_get_daily_bars("I:SPX", pivot_date, pivot_date)
    prior_session = {"high": prior_bars[0].get("h", 0), "low": prior_bars[0].get("l", 0), "close": prior_bars[0].get("c", 0), "open": prior_bars[0].get("o", 0)} if prior_bars else {}
    
    # Override prior_session with manual values if manual pivots are enabled
    if st.session_state.use_manual_pivots and st.session_state.high_price > 0:
        prior_session = {
            "high": st.session_state.high_price,
            "low": st.session_state.low_price,
            "close": st.session_state.close_price,
            "open": prior_session.get("open", 0)  # Keep open from Polygon if available
        }
    
    # Debug: Show data status
    with st.sidebar:
        if st.session_state.use_manual_pivots and st.session_state.high_price > 0:
            st.caption(f"✏️ Manual: H={prior_session.get('high',0):.0f} L={prior_session.get('low',0):.0f}")
        elif prior_session:
            st.caption(f"✅ Daily data: H={prior_session.get('high',0):.0f} L={prior_session.get('low',0):.0f}")
        else:
            st.warning(f"⚠️ No daily data for {pivot_date}")
    
    if st.session_state.use_manual_pivots and st.session_state.high_price > 0:
        pivots = create_manual_pivots(st.session_state.high_price, st.session_state.high_time, st.session_state.low_price, st.session_state.low_time, st.session_state.close_price, pivot_date, pivot_close_time)
    else:
        bars_30m = polygon_get_intraday_bars("I:SPX", pivot_date, pivot_date, 30)
        pivots = detect_pivots_auto(bars_30m, pivot_date, pivot_close_time) if bars_30m else []
        
        # Debug: Show intraday data status
        with st.sidebar:
            if bars_30m:
                st.caption(f"✅ Intraday bars: {len(bars_30m)}")
            else:
                st.caption(f"⚠️ No intraday data - using daily")
        
        # Fallback to daily data if no intraday pivots detected
        if not pivots and prior_session and prior_session.get("high", 0) > 0:
            pivots = [Pivot(name="Prior High", price=prior_session.get("high", 0), pivot_time=CT_TZ.localize(datetime.combine(pivot_date, time(10, 30))), pivot_type="HIGH", candle_high=prior_session.get("high", 0)),
                      Pivot(name="Prior Low", price=prior_session.get("low", 0), pivot_time=CT_TZ.localize(datetime.combine(pivot_date, time(14, 0))), pivot_type="LOW", candle_open=prior_session.get("low", 0)),
                      Pivot(name="Prior Close", price=prior_session.get("close", 0), pivot_time=CT_TZ.localize(datetime.combine(pivot_date, pivot_close_time)), pivot_type="CLOSE")]
    
    # Final debug: Show pivot count
    with st.sidebar:
        st.caption(f"📍 Pivots found: {len(pivots)}")
    
    eval_time = CT_TZ.localize(datetime.combine(trading_date, time(9, 0)))
    cones = build_cones(pivots, eval_time)
    vix_zone = analyze_vix_zone(st.session_state.vix_bottom, st.session_state.vix_top, st.session_state.vix_current, cones)
    spx_price = polygon_get_index_price("I:SPX") or prior_session.get("close", 0)
    is_after_cutoff = (trading_date == now.date() and now.time() > CUTOFF_TIME) or is_historical
    
    # Analyze price proximity if overnight SPX price provided
    overnight_price = st.session_state.get("overnight_spx", 0.0)
    price_proximity = None
    if overnight_price > 0 and cones:
        price_proximity = analyze_price_proximity(overnight_price, cones, vix_zone)
    
    # Calculate MA Bias using ES futures from Yahoo Finance (23 hrs/day = more bars)
    ma_bias = fetch_es_ma_bias()
    
    # Calculate Gap Analysis
    prior_close = prior_session.get("close", 0)
    gap_analysis = analyze_gap(prior_close, spx_price) if prior_close > 0 and spx_price > 0 else None
    
    # Calculate Market Context
    market_ctx = analyze_market_context(prior_session, st.session_state.vix_current, now.time())
    
    # Calculate Confluence (the key new feature!)
    confluence = calculate_confluence(vix_zone, ma_bias, gap_analysis)
    
    # Debug: Show confluence in sidebar
    with st.sidebar:
        if ma_bias.sma200 > 0:
            st.caption(f"📊 MA: {ma_bias.bias} | SMA: {ma_bias.sma200:.0f}")
        if confluence:
            conf_emoji = "✅" if confluence.is_aligned else "⚠️" if confluence.signal_strength == "CONFLICTING" else "◐"
            st.caption(f"{conf_emoji} Confluence: {confluence.signal_strength}")
        if gap_analysis and gap_analysis.gap_direction != "FLAT":
            st.caption(f"📊 Gap: {gap_analysis.gap_pct:+.2f}%")
        if price_proximity and price_proximity.position != "UNKNOWN":
            st.caption(f"📍 {price_proximity.position_detail}")
    
    # Pass VIX and entry time for accurate option pricing
    vix_for_pricing = st.session_state.vix_current if st.session_state.vix_current > 0 else 16
    mins_after_open = st.session_state.entry_time_mins
    
    # Use overnight price for setup status if provided, otherwise use SPX from Polygon
    price_for_setups = overnight_price if overnight_price > 0 else spx_price
    
    # Get broken structure states
    broken_structures = {
        "Prior High": st.session_state.get("broken_prior_high", False),
        "Prior Low": st.session_state.get("broken_prior_low", False),
        "Prior Close": st.session_state.get("broken_prior_close", False)
    }
    
    setups = generate_setups(cones, price_for_setups, vix_for_pricing, mins_after_open, is_after_cutoff, broken_structures)
    
    # Updated scoring with confluence
    day_score = calculate_day_score(vix_zone, cones, setups, confluence, market_ctx)
    pivot_table = build_pivot_table(pivots, trading_date)
    alerts = check_alerts(setups, vix_zone, now.time()) if not is_historical else []
    html = render_dashboard(vix_zone, cones, setups, pivot_table, prior_session, day_score, alerts, spx_price, trading_date, pivot_date, pivot_session_info, is_historical, st.session_state.theme, ma_bias, confluence, gap_analysis, market_ctx, price_proximity)
    components.html(html, height=4500, scrolling=True)

if __name__ == "__main__":
    main()