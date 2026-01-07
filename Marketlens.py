"""
SPX PROPHET v9.0 - OBSIDIAN PREMIUM
"Where Structure Becomes Foresight"

DESIGN: Deep obsidian dark theme with glassmorphism, glowing accents, and premium typography.

THREE PILLARS:
1. VIX Zone → Direction (CALLS at bottom/below, PUTS at top/above)
2. MA Bias → Confirmation (LONG/SHORT/NEUTRAL)
3. Day Structure → Entry + Contract + Stop

KEY FEATURES:
✓ VIX Zone scaling (1% of VIX, rounded to 0.05 ticks)
✓ Dynamic stops based on VIX level (4-10 pts)
✓ Strike = Entry ± 10 (OTM at entry, ITM at target)
✓ Day Structure = Buy Zone / Exit Zone with contract pricing
✓ Flip signals when structure breaks
✓ Trading Rules Reference (collapsible)
✓ Contextual Rule Warnings
"""

import streamlit as st
import streamlit.components.v1 as components
import requests
import numpy as np
from datetime import datetime, date, time, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
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

# ═══════════════════════════════════════════════════════════════════════════════
# ECONOMIC CALENDAR - High Impact Events for 0DTE Trading
# ═══════════════════════════════════════════════════════════════════════════════

# 2025-2026 FOMC Meeting Dates (announcement at 2:00 PM ET / 1:00 PM CT)
FOMC_DATES_2025_2026 = [
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-11-05", "2025-12-17",
    # 2026
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-10",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16"
]

# Known high-impact recurring events
# Format: (name, typical_time_ct, recurring_rule)
HIGH_IMPACT_RECURRING = {
    "NFP": ("Nonfarm Payrolls", "07:30", "first_friday"),  # First Friday of month
    "CPI": ("Consumer Price Index", "07:30", "mid_month"),  # ~13th of month
    "PPI": ("Producer Price Index", "07:30", "mid_month"),  # ~14th of month
    "RETAIL": ("Retail Sales", "07:30", "mid_month"),  # ~15th of month
    "JOBLESS": ("Initial Jobless Claims", "07:30", "thursday"),  # Every Thursday
}

def get_economic_events(target_date):
    """
    Get economic events for a given date.
    Returns list of (event_name, time_ct, impact_level) tuples.
    
    Impact levels: "HIGH", "MEDIUM", "LOW"
    """
    events = []
    date_str = target_date.strftime("%Y-%m-%d")
    day_of_week = target_date.weekday()  # 0=Monday, 4=Friday
    day_of_month = target_date.day
    
    # Check FOMC
    if date_str in FOMC_DATES_2025_2026:
        events.append(("🏛️ FOMC Rate Decision", "13:00", "HIGH"))
    
    # Check day before FOMC (often volatile)
    tomorrow = target_date + timedelta(days=1)
    if tomorrow.strftime("%Y-%m-%d") in FOMC_DATES_2025_2026:
        events.append(("🏛️ FOMC Eve (Pre-Announcement)", "—", "MEDIUM"))
    
    # NFP - First Friday of month
    if day_of_week == 4 and day_of_month <= 7:  # Friday in first week
        events.append(("📊 Nonfarm Payrolls (NFP)", "07:30", "HIGH"))
    
    # Initial Jobless Claims - Every Thursday
    if day_of_week == 3:  # Thursday
        events.append(("📋 Initial Jobless Claims", "07:30", "MEDIUM"))
    
    # CPI - Usually around 13th of month (approximate)
    if 10 <= day_of_month <= 15:
        # CPI is typically released mid-month
        if day_of_week not in [5, 6]:  # Not weekend
            # Check if this might be CPI day (rough heuristic)
            if day_of_month in [12, 13, 14]:
                events.append(("📈 CPI (Potential)", "07:30", "HIGH"))
    
    # Quad Witching - Third Friday of March, June, September, December
    if day_of_week == 4 and 15 <= day_of_month <= 21:  # Third Friday
        if target_date.month in [3, 6, 9, 12]:
            events.append(("🔮 Quad Witching Expiry", "08:30-15:00", "MEDIUM"))
    
    # Monthly Options Expiry - Third Friday
    if day_of_week == 4 and 15 <= day_of_month <= 21:
        events.append(("📅 Monthly Options Expiry", "15:00", "LOW"))
    
    return events

def get_event_warning(events):
    """
    Generate warning message based on events.
    Returns (warning_text, should_warn_entry, warning_level)
    """
    if not events:
        return None, False, None
    
    high_impact = [e for e in events if e[2] == "HIGH"]
    medium_impact = [e for e in events if e[2] == "MEDIUM"]
    
    if high_impact:
        event_names = ", ".join([e[0] for e in high_impact])
        return f"⚠️ HIGH IMPACT: {event_names}", True, "HIGH"
    elif medium_impact:
        event_names = ", ".join([e[0] for e in medium_impact])
        return f"📌 Notable: {event_names}", True, "MEDIUM"
    
    return None, False, None
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
class Confluence:
    """VIX + MA Bias confluence scoring"""
    vix_bias: str = "WAIT"
    ma_bias: str = "NEUTRAL"
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
    """Simplified - just stores current overnight SPX price for calculations"""
    current_price: float = 0.0
    
    # Legacy fields kept for compatibility but not actively used
    position: str = "UNKNOWN"
    position_detail: str = ""
    nearest_rail: float = 0.0
    nearest_rail_name: str = ""
    nearest_rail_type: str = ""
    nearest_rail_distance: float = 0.0
    nearest_cone_name: str = ""
    inside_cone: bool = False
    inside_cone_name: str = ""
    action: str = ""
    action_detail: str = ""
    rail_distances: Dict = None

@dataclass
class DayStructure:
    """Trendlines from Asian session to London session projected into RTH
    
    Includes contract price projections for integrated entry planning.
    """
    
    # High trendline - for PUTS (resistance)
    high_line_valid: bool = False
    high_line_slope: float = 0.0  # SPX $/minute (active line slope)
    high_line_at_entry: float = 0.0  # Projected SPX price at entry time
    high_line_direction: str = ""  # "ASCENDING", "DESCENDING", "FLAT"
    
    # Low trendline - for CALLS (support)
    low_line_valid: bool = False
    low_line_slope: float = 0.0  # SPX $/minute (active line slope)
    low_line_at_entry: float = 0.0  # Projected SPX price at entry time
    low_line_direction: str = ""  # "ASCENDING", "DESCENDING", "FLAT"
    
    # Original anchor points - ALL 3 SESSIONS
    sydney_high: float = 0.0
    sydney_low: float = 0.0
    tokyo_high: float = 0.0
    tokyo_low: float = 0.0
    london_high: float = 0.0
    london_low: float = 0.0
    
    # Legacy aliases (for backward compatibility)
    asia_high: float = 0.0  # Now maps to tokyo_high
    asia_low: float = 0.0   # Now maps to tokyo_low
    
    # 3-POINT TRENDLINE ANALYSIS
    # High Line: Sydney High → Tokyo High → London High
    high_syd_tok_slope: float = 0.0  # Sydney → Tokyo slope
    high_tok_lon_slope: float = 0.0  # Tokyo → London slope
    high_line_pivot: bool = False     # True if slopes conflict (V or Λ shape)
    high_line_pivot_type: str = ""    # "V_BOTTOM", "INVERTED_V", "ALIGNED"
    high_line_active_segment: str = "" # "SYD_TOK_LON" (3-point) or "TOK_LON" (pivot)
    high_line_quality: str = ""       # "STRONG", "MODERATE", "WEAK"
    
    # Low Line: Sydney Low → Tokyo Low → London Low
    low_syd_tok_slope: float = 0.0   # Sydney → Tokyo slope
    low_tok_lon_slope: float = 0.0   # Tokyo → London slope
    low_line_pivot: bool = False      # True if slopes conflict (V or Λ shape)
    low_line_pivot_type: str = ""     # "V_BOTTOM", "INVERTED_V", "ALIGNED"
    low_line_active_segment: str = "" # "SYD_TOK_LON" (3-point) or "TOK_LON" (pivot)
    low_line_quality: str = ""        # "STRONG", "MODERATE", "WEAK"
    
    # Overall structure quality
    structure_quality: str = ""  # "STRONG", "MODERATE", "WEAK"
    
    # Overall structure shape
    structure_shape: str = ""  # "EXPANDING", "CONTRACTING", "PARALLEL_UP", "PARALLEL_DOWN", "MIXED"
    
    # Confluence with cones
    high_confluence_cone: str = ""  # Cone name where high line aligns
    high_confluence_rail: str = ""  # "ascending" or "descending"
    high_confluence_dist: float = 0.0  # Distance in points
    
    low_confluence_cone: str = ""
    low_confluence_rail: str = ""
    low_confluence_dist: float = 0.0
    
    # Best confluence
    has_confluence: bool = False
    best_confluence_detail: str = ""
    
    # CONTRACT PRICING - PUT (tracks high line for resistance)
    put_price_sydney: float = 0.0  # PUT contract price at Sydney High
    put_price_tokyo: float = 0.0   # PUT contract price at Tokyo High
    put_price_london: float = 0.0  # PUT contract price at London High
    put_price_asia: float = 0.0    # Legacy alias for tokyo
    put_price_at_entry: float = 0.0  # Projected PUT price at entry time
    put_slope_per_hour: float = 0.0  # PUT decay rate $/hour
    put_strike: int = 0  # Strike = Entry (High Line) - 10 (slightly OTM at entry)
    
    # CONTRACT PRICING - CALL (tracks low line for support)
    call_price_sydney: float = 0.0  # CALL contract price at Sydney Low
    call_price_tokyo: float = 0.0   # CALL contract price at Tokyo Low
    call_price_london: float = 0.0  # CALL contract price at London Low
    call_price_asia: float = 0.0    # Legacy alias for tokyo
    call_price_at_entry: float = 0.0  # Projected CALL price at entry time
    call_slope_per_hour: float = 0.0  # CALL decay rate $/hour
    call_strike: int = 0  # Strike = Entry (Low Line) + 10 (slightly OTM at entry)
    
    # BREAK & RETEST signals
    high_line_broken: bool = False  # SPX broke above high line → FLIP to CALLS
    low_line_broken: bool = False  # SPX broke below low line → FLIP to PUTS
    
    # FLIP TRADE LOGIC:
    # When low line breaks DOWN: Direction = PUTS, Strike = Broken Low Line
    # When high line breaks UP: Direction = CALLS, Strike = Broken High Line

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

# ═══════════════════════════════════════════════════════════════════════════
# POLYGON API
# ═══════════════════════════════════════════════════════════════════════════

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

def calculate_confluence(vix_zone, ma_bias):
    """
    Calculate confluence between VIX Zone and MA Bias.
    
    Scoring (40 pts max):
    - VIX + MA aligned: 40/40 (STRONG)
    - VIX clear, MA neutral: 25/40 (MODERATE)
    - MA clear, VIX neutral: 15/40 (WEAK)
    - Both neutral: 15/40 (WEAK)
    - VIX + MA CONFLICT: 0/40 + NO TRADE
    """
    conf = Confluence()
    conf.vix_bias = vix_zone.bias
    conf.ma_bias = ma_bias.bias if ma_bias else "NEUTRAL"
    
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
        # VIX + MA ALIGNED
        conf.is_aligned = True
        conf.no_trade = False
        conf.alignment_score = 40
        conf.signal_strength = "STRONG"
        breakout_note = " (BREAKOUT)" if vix_zone.is_breakout else ""
        conf.recommendation = f"✅ {vix_direction}{breakout_note} — Full confluence"
    elif vix_direction != "NEUTRAL":
        # VIX has signal, MA is neutral
        conf.is_aligned = False
        conf.no_trade = False
        conf.alignment_score = 25
        conf.signal_strength = "MODERATE"
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

def calculate_day_structure(sydney_high, sydney_high_time, sydney_low, sydney_low_time,
                            tokyo_high, tokyo_high_time, tokyo_low, tokyo_low_time,
                            london_high, london_high_time, london_low, london_low_time,
                            entry_time_mins, cones, trading_date,
                            put_price_sydney=0, put_price_tokyo=0, put_price_london=0,
                            call_price_sydney=0, call_price_tokyo=0, call_price_london=0,
                            high_line_broken=False, low_line_broken=False):
    """
    Calculate day structure trendlines from 3 sessions: Sydney → Tokyo → London.
    Detects pivot points (V-shape or inverted-V) when slopes conflict.
    Uses the ACTIVE line (most recent segment if pivoted) for RTH projection.
    
    Times are in CT (Central Time).
    Session times: Sydney 4pm-6pm, Tokyo 6pm-2am, London 2am-6:30am
    """
    ds = DayStructure()
    ds.high_line_broken = high_line_broken
    ds.low_line_broken = low_line_broken
    
    # Store original anchor points
    ds.sydney_high = sydney_high
    ds.sydney_low = sydney_low
    ds.tokyo_high = tokyo_high
    ds.tokyo_low = tokyo_low
    ds.london_high = london_high
    ds.london_low = london_low
    
    # Legacy aliases (for backward compatibility)
    ds.asia_high = tokyo_high
    ds.asia_low = tokyo_low
    
    def parse_time_to_mins_from_midnight(t_str):
        """Parse time string to minutes from midnight"""
        try:
            t_str = t_str.strip().replace(" ", "")
            parts = t_str.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            return h * 60 + m
        except:
            return 0
    
    def calc_slope(price1, time1_mins, price2, time2_mins):
        """Calculate slope between two points, handling overnight"""
        t2 = time2_mins
        if t2 < time1_mins:
            t2 += 24 * 60  # Overnight adjustment
        time_diff = t2 - time1_mins
        if time_diff > 0:
            return (price2 - price1) / time_diff, time_diff
        return 0, 0
    
    def slopes_aligned(slope1, slope2, threshold=0.0005):
        """Check if two slopes are in same direction (both up or both down)"""
        if abs(slope1) < threshold and abs(slope2) < threshold:
            return True  # Both flat = aligned
        return (slope1 > threshold and slope2 > threshold) or (slope1 < -threshold and slope2 < -threshold)
    
    # Entry time in minutes from midnight (8:30 AM + entry_time_mins)
    entry_mins = 8 * 60 + 30 + entry_time_mins
    
    # ═══════════════════════════════════════════════════════════════════════
    # HIGH LINE ANALYSIS (Sydney High → Tokyo High → London High) - for PUTS
    # ═══════════════════════════════════════════════════════════════════════
    
    syd_h_mins = parse_time_to_mins_from_midnight(sydney_high_time) if sydney_high > 0 else 0
    tok_h_mins = parse_time_to_mins_from_midnight(tokyo_high_time) if tokyo_high > 0 else 0
    lon_h_mins = parse_time_to_mins_from_midnight(london_high_time) if london_high > 0 else 0
    
    # Calculate segment slopes
    if sydney_high > 0 and tokyo_high > 0:
        ds.high_syd_tok_slope, _ = calc_slope(sydney_high, syd_h_mins, tokyo_high, tok_h_mins)
    if tokyo_high > 0 and london_high > 0:
        ds.high_tok_lon_slope, _ = calc_slope(tokyo_high, tok_h_mins, london_high, lon_h_mins)
    
    # Determine if we have valid 3-point or 2-point line
    has_3pt_high = sydney_high > 0 and tokyo_high > 0 and london_high > 0
    has_2pt_high = tokyo_high > 0 and london_high > 0
    
    if has_3pt_high:
        # Check for pivot (slopes conflict)
        if slopes_aligned(ds.high_syd_tok_slope, ds.high_tok_lon_slope):
            # All 3 points aligned - use full line
            ds.high_line_pivot = False
            ds.high_line_pivot_type = "ALIGNED"
            ds.high_line_active_segment = "SYD_TOK_LON"
            ds.high_line_quality = "STRONG"
            # Use Sydney → London for projection (but slope from Tok→Lon for accuracy)
            ds.high_line_slope = ds.high_tok_lon_slope  # Most recent slope
        else:
            # Pivot detected at Tokyo
            ds.high_line_pivot = True
            ds.high_line_active_segment = "TOK_LON"
            ds.high_line_quality = "MODERATE"
            ds.high_line_slope = ds.high_tok_lon_slope  # Use Tokyo → London
            
            # Determine pivot type
            if ds.high_syd_tok_slope < 0 and ds.high_tok_lon_slope > 0:
                ds.high_line_pivot_type = "V_BOTTOM"  # Descended then ascended
            elif ds.high_syd_tok_slope > 0 and ds.high_tok_lon_slope < 0:
                ds.high_line_pivot_type = "INVERTED_V"  # Ascended then descended
            else:
                ds.high_line_pivot_type = "MIXED"
        
        ds.high_line_valid = True
        
    elif has_2pt_high:
        # Only Tokyo → London available
        ds.high_line_pivot = False
        ds.high_line_pivot_type = "2PT_ONLY"
        ds.high_line_active_segment = "TOK_LON"
        ds.high_line_quality = "MODERATE"
        ds.high_line_slope = ds.high_tok_lon_slope
        ds.high_line_valid = True
    
    # Project high line to entry time (always use Tokyo as base for projection)
    if ds.high_line_valid and tokyo_high > 0:
        tok_h_adj = tok_h_mins
        entry_mins_adj = entry_mins
        if entry_mins < tok_h_mins:
            entry_mins_adj += 24 * 60
        
        mins_from_tokyo = entry_mins_adj - tok_h_adj
        ds.high_line_at_entry = tokyo_high + (ds.high_line_slope * mins_from_tokyo)
        
        # Direction from active slope
        if ds.high_line_slope > 0.001:
            ds.high_line_direction = "ASCENDING"
        elif ds.high_line_slope < -0.001:
            ds.high_line_direction = "DESCENDING"
        else:
            ds.high_line_direction = "FLAT"
    
    # PUT CONTRACT PRICING (use Tokyo and London prices)
    ds.put_price_sydney = put_price_sydney
    ds.put_price_tokyo = put_price_tokyo
    ds.put_price_london = put_price_london
    ds.put_price_asia = put_price_tokyo  # Legacy alias
    
    # ═══════════════════════════════════════════════════════════════════════
    # LOW LINE ANALYSIS (Sydney Low → Tokyo Low → London Low) - for CALLS
    # ═══════════════════════════════════════════════════════════════════════
    
    syd_l_mins = parse_time_to_mins_from_midnight(sydney_low_time) if sydney_low > 0 else 0
    tok_l_mins = parse_time_to_mins_from_midnight(tokyo_low_time) if tokyo_low > 0 else 0
    lon_l_mins = parse_time_to_mins_from_midnight(london_low_time) if london_low > 0 else 0
    
    # Calculate segment slopes
    if sydney_low > 0 and tokyo_low > 0:
        ds.low_syd_tok_slope, _ = calc_slope(sydney_low, syd_l_mins, tokyo_low, tok_l_mins)
    if tokyo_low > 0 and london_low > 0:
        ds.low_tok_lon_slope, _ = calc_slope(tokyo_low, tok_l_mins, london_low, lon_l_mins)
    
    # Determine if we have valid 3-point or 2-point line
    has_3pt_low = sydney_low > 0 and tokyo_low > 0 and london_low > 0
    has_2pt_low = tokyo_low > 0 and london_low > 0
    
    if has_3pt_low:
        # Check for pivot (slopes conflict)
        if slopes_aligned(ds.low_syd_tok_slope, ds.low_tok_lon_slope):
            # All 3 points aligned - strong structure
            ds.low_line_pivot = False
            ds.low_line_pivot_type = "ALIGNED"
            ds.low_line_active_segment = "SYD_TOK_LON"
            ds.low_line_quality = "STRONG"
            ds.low_line_slope = ds.low_tok_lon_slope  # Most recent slope
        else:
            # Pivot detected at Tokyo
            ds.low_line_pivot = True
            ds.low_line_active_segment = "TOK_LON"
            ds.low_line_quality = "MODERATE"
            ds.low_line_slope = ds.low_tok_lon_slope  # Use Tokyo → London
            
            # Determine pivot type
            if ds.low_syd_tok_slope < 0 and ds.low_tok_lon_slope > 0:
                ds.low_line_pivot_type = "V_BOTTOM"  # Descended then ascended (bullish)
            elif ds.low_syd_tok_slope > 0 and ds.low_tok_lon_slope < 0:
                ds.low_line_pivot_type = "INVERTED_V"  # Ascended then descended (bearish)
            else:
                ds.low_line_pivot_type = "MIXED"
        
        ds.low_line_valid = True
        
    elif has_2pt_low:
        # Only Tokyo → London available
        ds.low_line_pivot = False
        ds.low_line_pivot_type = "2PT_ONLY"
        ds.low_line_active_segment = "TOK_LON"
        ds.low_line_quality = "MODERATE"
        ds.low_line_slope = ds.low_tok_lon_slope
        ds.low_line_valid = True
    
    # Project low line to entry time
    if ds.low_line_valid and tokyo_low > 0:
        tok_l_adj = tok_l_mins
        entry_mins_adj = entry_mins
        if entry_mins < tok_l_mins:
            entry_mins_adj += 24 * 60
        
        mins_from_tokyo = entry_mins_adj - tok_l_adj
        ds.low_line_at_entry = tokyo_low + (ds.low_line_slope * mins_from_tokyo)
        
        # Direction from active slope
        if ds.low_line_slope > 0.001:
            ds.low_line_direction = "ASCENDING"
        elif ds.low_line_slope < -0.001:
            ds.low_line_direction = "DESCENDING"
        else:
            ds.low_line_direction = "FLAT"
    
    # CALL CONTRACT PRICING
    ds.call_price_sydney = call_price_sydney
    ds.call_price_tokyo = call_price_tokyo
    ds.call_price_london = call_price_london
    ds.call_price_asia = call_price_tokyo  # Legacy alias
    
    # ═══════════════════════════════════════════════════════════════════════
    # OVERALL STRUCTURE QUALITY
    # ═══════════════════════════════════════════════════════════════════════
    
    if ds.high_line_quality == "STRONG" and ds.low_line_quality == "STRONG":
        ds.structure_quality = "STRONG"
    elif ds.high_line_quality == "STRONG" or ds.low_line_quality == "STRONG":
        ds.structure_quality = "MODERATE"
    elif ds.high_line_valid or ds.low_line_valid:
        ds.structure_quality = "WEAK"
    else:
        ds.structure_quality = ""
    
    # STRUCTURE SHAPE
    if ds.high_line_valid and ds.low_line_valid:
        if ds.high_line_slope > 0 and ds.low_line_slope > 0:
            ds.structure_shape = "PARALLEL_UP"
        elif ds.high_line_slope < 0 and ds.low_line_slope < 0:
            ds.structure_shape = "PARALLEL_DOWN"
        elif ds.high_line_slope > ds.low_line_slope:
            ds.structure_shape = "EXPANDING"
        elif ds.high_line_slope < ds.low_line_slope:
            ds.structure_shape = "CONTRACTING"
        else:
            ds.structure_shape = "PARALLEL"
    elif ds.high_line_valid:
        ds.structure_shape = "HIGH_ONLY"
    elif ds.low_line_valid:
        ds.structure_shape = "LOW_ONLY"
    
    # ═══════════════════════════════════════════════════════════════════════
    # CALCULATE STRIKES
    # ═══════════════════════════════════════════════════════════════════════
    if ds.high_line_valid and ds.low_line_valid:
        if ds.low_line_broken:
            # FLIP to PUTS: Strike = London Low (where support broke)
            break_level = ds.london_low if ds.london_low > 0 else ds.low_line_at_entry
            ds.put_strike = int(round(break_level / 5) * 5)
            ds.call_strike = int(round(ds.low_line_at_entry / 5) * 5) + 10
        elif ds.high_line_broken:
            # FLIP to CALLS: Strike = London High (where resistance broke)
            break_level = ds.london_high if ds.london_high > 0 else ds.high_line_at_entry
            ds.call_strike = int(round(break_level / 5) * 5)
            ds.put_strike = int(round(ds.high_line_at_entry / 5) * 5) - 10
        else:
            # Normal: Strike slightly OTM at entry
            ds.put_strike = int(round(ds.high_line_at_entry / 5) * 5) - 10
            ds.call_strike = int(round(ds.low_line_at_entry / 5) * 5) + 10
    
    # FIND CONFLUENCE WITH CONE RAILS
    if cones:
        tradeable = [c for c in cones if c.is_tradeable]
        
        # Check high line confluence (looking for resistance alignment)
        if ds.high_line_valid and ds.high_line_at_entry > 0:
            best_dist = float('inf')
            for cone in tradeable:
                # Check against ascending rails (resistance/PUTS entry)
                dist = abs(ds.high_line_at_entry - cone.ascending_rail)
                if dist < best_dist and dist <= 10:  # Within 10 pts = confluence
                    best_dist = dist
                    ds.high_confluence_cone = cone.name
                    ds.high_confluence_rail = "ascending"
                    ds.high_confluence_dist = dist
        
        # Check low line confluence (looking for support alignment)
        if ds.low_line_valid and ds.low_line_at_entry > 0:
            best_dist = float('inf')
            for cone in tradeable:
                # Check against descending rails (support/CALLS entry)
                dist = abs(ds.low_line_at_entry - cone.descending_rail)
                if dist < best_dist and dist <= 10:  # Within 10 pts = confluence
                    best_dist = dist
                    ds.low_confluence_cone = cone.name
                    ds.low_confluence_rail = "descending"
                    ds.low_confluence_dist = dist
    
    # DETERMINE BEST CONFLUENCE
    if ds.high_confluence_cone or ds.low_confluence_cone:
        ds.has_confluence = True
        details = []
        if ds.low_confluence_cone:
            details.append(f"Low → {ds.low_confluence_cone} ({ds.low_confluence_dist:.0f} pts) = CALLS")
        if ds.high_confluence_cone:
            details.append(f"High → {ds.high_confluence_cone} ({ds.high_confluence_dist:.0f} pts) = PUTS")
        ds.best_confluence_detail = " | ".join(details)
    
    return ds

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

def generate_setups(cones, current_price, vix_current=16, mins_after_open=30, is_after_cutoff=False, broken_structures=None, tested_structures=None):
    """Generate trade setups with calibrated option pricing
    
    broken_structures: dict mapping cone names to {"CALLS": bool, "PUTS": bool}
        - BROKEN = 30-min candle closed through rail, structure invalidated
        - Direction-specific: CALLS broken if descending rail violated, PUTS if ascending
    tested_structures: dict mapping cone names to {"CALLS": "TESTED", "PUTS": "TESTED"}
        - TESTED = overnight price went through rail but came back, weakened structure
    """
    if broken_structures is None:
        broken_structures = {}
    if tested_structures is None:
        tested_structures = {}
    
    setups = []
    for cone in cones:
        if not cone.is_tradeable:
            continue
        
        # Get direction-specific broken/tested status for this cone
        cone_broken = broken_structures.get(cone.name, {})
        cone_tested = tested_structures.get(cone.name, {})
        
        # CALLS - enter at descending rail
        entry_c = cone.descending_rail
        dist_c = abs(current_price - entry_c)
        opt_c = get_option_data_for_entry(entry_c, "C", vix_current, mins_after_open)
        delta_c = abs(opt_c.spy_delta) if opt_c else DELTA_IDEAL
        
        # Check CALLS-specific broken/tested
        calls_broken = cone_broken.get("CALLS", False) if isinstance(cone_broken, dict) else cone_broken
        calls_tested = cone_tested.get("CALLS") == "TESTED" if isinstance(cone_tested, dict) else cone_tested == "TESTED"
        
        # Determine CALLS status
        if is_after_cutoff:
            calls_status = "GREY"
        elif calls_broken:
            calls_status = "BROKEN"
        elif calls_tested:
            calls_status = "TESTED"
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
        
        # Check PUTS-specific broken/tested
        puts_broken = cone_broken.get("PUTS", False) if isinstance(cone_broken, dict) else cone_broken
        puts_tested = cone_tested.get("PUTS") == "TESTED" if isinstance(cone_tested, dict) else cone_tested == "TESTED"
        
        # Determine PUTS status
        if is_after_cutoff:
            puts_status = "GREY"
        elif puts_broken:
            puts_status = "BROKEN"
        elif puts_tested:
            puts_status = "TESTED"
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

def generate_day_structure_setups(day_structure, current_price, vix_current=16, mins_after_open=30, is_after_cutoff=False, dynamic_stop=6.0):
    """Generate CALL and PUT setups from Day Structure lines
    
    DAY STRUCTURE SETUP LOGIC:
    ═══════════════════════════════════════════════════════════════════════════
    
    NORMAL (no breaks):
    - CALL: Entry at Low Line (support), Target at High Line
           Strike = Entry - 15 to 20 (slightly ITM at entry, deeper ITM at target)
    - PUT:  Entry at High Line (resistance), Target at Low Line
           Strike = Entry + 15 to 20 (slightly ITM at entry, deeper ITM at target)
    
    WHEN LOW LINE BREAKS (FLIP TO PUTS):
    - CALL setup is INVALIDATED (removed entirely)
    - PUT becomes the FLIP trade:
           Entry: Wait for retest of broken low OR enter at high line
           Strike = Broken Low Line (will be ATM/ITM as price drops through)
           Example: Low broke at 6875 → Buy 6880P or 6875P
    
    WHEN HIGH LINE BREAKS (FLIP TO CALLS):
    - PUT setup is INVALIDATED (removed entirely)  
    - CALL becomes the FLIP trade:
           Entry: Wait for retest of broken high OR enter at low line
           Strike = Broken High Line (will be ATM/ITM as price rises through)
           Example: High broke at 6920 → Buy 6920C or 6915C
    
    STRIKE SELECTION PRINCIPLE:
    - Strike should be near ENTRY point, so contract is slightly ITM or ATM
    - As price moves to target, contract goes deeper ITM = bigger gains
    - Round to nearest 5 for SPX options
    ═══════════════════════════════════════════════════════════════════════════
    """
    setups = []
    
    if not day_structure:
        return setups
    
    # Both lines required for proper setup
    if not (day_structure.high_line_valid and day_structure.low_line_valid):
        return setups
    
    low_line = day_structure.low_line_at_entry
    high_line = day_structure.high_line_at_entry
    
    if low_line <= 0 or high_line <= 0:
        return setups
    
    # Structure width = potential profit
    structure_width = abs(high_line - low_line)
    
    if structure_width < 5:  # Too narrow
        return setups
    
    low_line_broken = day_structure.low_line_broken
    high_line_broken = day_structure.high_line_broken
    
    # ═══════════════════════════════════════════════════════════════════════
    # DAY STRUCTURE CALL SETUP
    # Normal: Entry at Low Line (support) | Target at High Line
    # If High Line broken: This becomes the FLIP trade
    # If Low Line broken: This setup is INVALIDATED - don't show it
    # ═══════════════════════════════════════════════════════════════════════
    
    if not low_line_broken:  # Only show CALL if Low Line is intact
        entry_c = low_line
        dist_c = abs(current_price - entry_c)
        
        # Use Day Structure contract pricing if available, else estimate
        if day_structure.call_price_at_entry > 0:
            call_premium = day_structure.call_price_at_entry
            delta_c = min(0.50, max(0.15, call_premium / 12))
        else:
            opt_c = get_option_data_for_entry(entry_c, "C", vix_current, mins_after_open)
            call_premium = opt_c.spx_price_est if opt_c else 0
            delta_c = abs(opt_c.spy_delta) if opt_c else DELTA_IDEAL
        
        # STRIKE LOGIC FOR CALLS:
        # Strike should be ABOVE entry (slightly OTM at entry)
        # As price rises to High Line target, contract goes ITM
        # Use Entry + 10 points, rounded to nearest 5
        if day_structure.call_strike > 0:
            call_strike = day_structure.call_strike
        else:
            # Strike = Entry rounded up to nearest 5, plus 10
            # CALL strike ABOVE entry = OTM, becomes ITM as price rises
            call_strike = int((entry_c // 5) * 5) + 10
        
        # Determine status
        if is_after_cutoff:
            calls_status = "GREY"
        elif high_line_broken:
            # High line broke UP = bullish, CALL is the FLIP trade (but we show it as active opportunity)
            calls_status = "ACTIVE" if dist_c <= RAIL_PROXIMITY * 2 else "WAIT"
        elif dist_c <= RAIL_PROXIMITY:
            calls_status = "ACTIVE"
        else:
            calls_status = "WAIT"
        
        call_option = OptionData(
            spx_strike=call_strike,
            spx_price_est=call_premium,
            spy_delta=delta_c,
            otm_distance=abs(entry_c - call_strike),
            in_sweet_spot=(PREMIUM_SWEET_LOW <= call_premium <= PREMIUM_SWEET_HIGH) if call_premium > 0 else False
        )
        
        setups.append(TradeSetup(
            direction="CALLS",
            cone_name="Day Structure",
            cone_width=structure_width,
            entry=round(entry_c, 2),
            stop=round(entry_c - dynamic_stop, 2),
            target_25=round(entry_c + structure_width * 0.25, 2),
            target_50=round(entry_c + structure_width * 0.50, 2),
            target_75=round(entry_c + structure_width * 0.75, 2),
            target_100=round(high_line, 2),
            distance=round(dist_c, 1),
            option=call_option,
            profit_25=round(structure_width * 0.25 * delta_c * 100, 0),
            profit_50=round(structure_width * 0.50 * delta_c * 100, 0),
            profit_75=round(structure_width * 0.75 * delta_c * 100, 0),
            profit_100=round(structure_width * delta_c * 100, 0),
            risk_dollars=round(dynamic_stop * delta_c * 100, 0),
            status=calls_status
        ))
    
    # ═══════════════════════════════════════════════════════════════════════
    # DAY STRUCTURE PUT SETUP  
    # Normal: Entry at High Line (resistance) | Target at Low Line
    # If Low Line broken: FLIP trade - Entry at Low Line (broken support = resistance)
    # If High Line broken: This setup is INVALIDATED - don't show it
    # ═══════════════════════════════════════════════════════════════════════
    
    if not high_line_broken:  # Only show PUT if High Line is intact
        
        # ENTRY POINT LOGIC:
        if low_line_broken:
            # FLIP: Entry at LOW LINE (broken support becomes resistance on retest)
            entry_p = low_line
        else:
            # Normal: Entry at HIGH LINE (resistance)
            entry_p = high_line
        
        dist_p = abs(current_price - entry_p)
        
        # Use Day Structure contract pricing if available, else estimate
        if day_structure.put_price_at_entry > 0:
            put_premium = day_structure.put_price_at_entry
            delta_p = min(0.50, max(0.15, put_premium / 12))
        else:
            opt_p = get_option_data_for_entry(entry_p, "P", vix_current, mins_after_open)
            put_premium = opt_p.spx_price_est if opt_p else 0
            delta_p = abs(opt_p.spy_delta) if opt_p else DELTA_IDEAL
        
        # STRIKE LOGIC FOR PUTS:
        # ═══════════════════════════════════════════════════════════════════
        # When Low Line is BROKEN: Strike = LONDON LOW (the break level)
        # Normal: Strike = Entry - 10 (slightly OTM at entry, ITM at target)
        # ═══════════════════════════════════════════════════════════════════
        
        if low_line_broken:
            # FLIP TRADE: Strike = London Low (where support broke)
            break_level = day_structure.london_low if day_structure.london_low > 0 else low_line
            put_strike = int(round(break_level / 5) * 5)
        elif day_structure.put_strike > 0:
            put_strike = day_structure.put_strike
        else:
            # Normal: Strike = Entry - 10 (slightly OTM at entry)
            # PUT strike BELOW entry = OTM, becomes ITM as price drops
            put_strike = int((entry_p // 5) * 5) - 10
        
        # Determine status
        if is_after_cutoff:
            puts_status = "GREY"
        elif low_line_broken:
            # LOW LINE BROKE DOWN = bearish FLIP signal
            # PUT is now the active trade - price should retest and reject
            puts_status = "ACTIVE"  # Always active when it's a FLIP trade
        elif dist_p <= RAIL_PROXIMITY:
            puts_status = "ACTIVE"
        else:
            puts_status = "WAIT"
        
        put_option = OptionData(
            spx_strike=put_strike,
            spx_price_est=put_premium,
            spy_delta=delta_p,
            otm_distance=abs(entry_p - put_strike),
            in_sweet_spot=(PREMIUM_SWEET_LOW <= put_premium <= PREMIUM_SWEET_HIGH) if put_premium > 0 else False
        )
        
        # Calculate target based on whether it's a FLIP or normal trade
        if low_line_broken:
            # FLIP: Target is extension below (Asia Low or structure width down)
            asia_low = day_structure.asia_low if day_structure.asia_low > 0 else low_line - structure_width
            target_100 = min(asia_low, low_line - structure_width)  # Whichever is lower
        else:
            # Normal: Target is Low Line
            target_100 = low_line
        
        setups.append(TradeSetup(
            direction="PUTS",
            cone_name="Day Structure" + (" ⚡FLIP" if low_line_broken else ""),
            cone_width=structure_width,
            entry=round(entry_p, 2),
            stop=round(entry_p + dynamic_stop, 2),
            target_25=round(entry_p - structure_width * 0.25, 2),
            target_50=round(entry_p - structure_width * 0.50, 2),
            target_75=round(entry_p - structure_width * 0.75, 2),
            target_100=round(target_100, 2),
            distance=round(dist_p, 1),
            option=put_option,
            profit_25=round(structure_width * 0.25 * delta_p * 100, 0),
            profit_50=round(structure_width * 0.50 * delta_p * 100, 0),
            profit_75=round(structure_width * 0.75 * delta_p * 100, 0),
            profit_100=round(structure_width * delta_p * 100, 0),
            risk_dollars=round(dynamic_stop * delta_p * 100, 0),
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

def render_dashboard(vix_zone, cones, setups, pivot_table, prior_session, day_score, alerts, spx_price, trading_date, pivot_date, pivot_session_info, is_historical, theme, ma_bias=None, confluence=None, market_ctx=None, price_proximity=None, day_structure=None):
    # ═══════════════════════════════════════════════════════════════════════
    # OBSIDIAN PREMIUM DESIGN SYSTEM
    # ═══════════════════════════════════════════════════════════════════════
    
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
        # OBSIDIAN DARK - Deep, rich, premium
        bg_main = "#050506"  # Nearly black with subtle warmth
        bg_card = "#0a0a0c"  # Slightly elevated
        bg_elevated = "#111114"  # Card surfaces
        bg_subtle = "#0d0d10"  # Subtle backgrounds
        text_primary = "#f4f4f5"  # Bright but not harsh
        text_secondary = "#a1a1aa"  # Muted text
        text_muted = "#52525b"  # Very subtle
        border_light = "rgba(255,255,255,0.06)"  # Subtle glass borders
        border_medium = "rgba(255,255,255,0.1)"  # More visible
        shadow_sm = "0 1px 2px rgba(0,0,0,0.5)"
        shadow_md = "0 4px 12px rgba(0,0,0,0.4)"
        shadow_lg = "0 8px 32px rgba(0,0,0,0.5)"
        shadow_card = "0 4px 24px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.03)"
    
    # Premium accent colors - vibrant but sophisticated
    green = "#10b981"  # Emerald
    green_light = "#f0fdf4" if theme == "light" else "rgba(16,185,129,0.15)"
    green_muted = "#86efac" if theme == "light" else "rgba(16,185,129,0.25)"
    red = "#ef4444"  # Red
    red_light = "#fef2f2" if theme == "light" else "rgba(239,68,68,0.15)"
    red_muted = "#fca5a5" if theme == "light" else "rgba(239,68,68,0.25)"
    amber = "#f59e0b"  # Amber
    amber_light = "#fefce8" if theme == "light" else "rgba(245,158,11,0.15)"
    blue = "#3b82f6"  # Blue
    blue_light = "#eff6ff" if theme == "light" else "rgba(59,130,246,0.15)"
    purple = "#8b5cf6"  # Purple
    neutral = "#71717a"
    
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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
/* ═══════════════════════════════════════════════════════════════════════════
   SPX PROPHET v9.0 - OBSIDIAN PREMIUM DESIGN SYSTEM
   Bloomberg Terminal × Apple × Stripe × Linear × Vercel
   ═══════════════════════════════════════════════════════════════════════════ */

:root {{
    /* ─── Core Colors ─── */
    --bg-base: {bg_main};
    --bg-surface: {bg_card};
    --bg-surface-2: {bg_elevated};
    --bg-surface-3: {bg_subtle};
    --text-primary: {text_primary};
    --text-secondary: {text_secondary};
    --text-tertiary: {text_muted};
    --border: {border_light};
    --border-strong: {border_medium};
    
    /* ─── Semantic Colors with Glow ─── */
    --success: {green};
    --success-soft: {green_light};
    --success-muted: {green_muted};
    --success-glow: {"rgba(16,185,129,0.5)" if theme == "dark" else "rgba(16,185,129,0.2)"};
    --danger: {red};
    --danger-soft: {red_light};
    --danger-muted: {red_muted};
    --danger-glow: {"rgba(239,68,68,0.5)" if theme == "dark" else "rgba(239,68,68,0.2)"};
    --warning: {amber};
    --warning-soft: {amber_light};
    --info: {blue};
    --info-soft: {blue_light};
    --accent: {purple};
    
    /* ─── Premium Gradients ─── */
    --gradient-calls: linear-gradient(135deg, rgba(16,185,129,0.2) 0%, rgba(16,185,129,0.05) 50%, rgba(16,185,129,0.1) 100%);
    --gradient-puts: linear-gradient(135deg, rgba(239,68,68,0.2) 0%, rgba(239,68,68,0.05) 50%, rgba(239,68,68,0.1) 100%);
    --gradient-premium: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
    
    /* ─── Glassmorphism ─── */
    --glass-bg: {"rgba(10,10,12,0.8)" if theme == "dark" else "rgba(255,255,255,0.85)"};
    --glass-border: {"rgba(255,255,255,0.08)" if theme == "dark" else "rgba(0,0,0,0.08)"};
    --glass-blur: blur(20px);
    
    /* ─── Shadows ─── */
    --shadow-sm: {shadow_sm};
    --shadow-md: {shadow_md};
    --shadow-lg: {shadow_lg};
    --shadow-card: {shadow_card};
    --shadow-glow-green: 0 0 30px rgba(16,185,129,0.4), 0 0 60px rgba(16,185,129,0.2);
    --shadow-glow-red: 0 0 30px rgba(239,68,68,0.4), 0 0 60px rgba(239,68,68,0.2);
    
    /* ─── Spacing Scale ─── */
    --space-1: 4px;
    --space-2: 8px;
    --space-3: 12px;
    --space-4: 16px;
    --space-5: 20px;
    --space-6: 24px;
    --space-8: 32px;
    --space-10: 40px;
    
    /* ─── Typography ─── */
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
    
    /* ─── Radius ─── */
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 14px;
    --radius-xl: 20px;
    --radius-2xl: 28px;
}}

/* ─────────────────────────────────────────────────────────────────
   ANIMATIONS
   ───────────────────────────────────────────────────────────────── */

@keyframes pulse-glow {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.8; }}
}}

@keyframes pulse-border-green {{
    0%, 100% {{ box-shadow: var(--shadow-glow-green); }}
    50% {{ box-shadow: 0 0 50px rgba(16,185,129,0.5), 0 0 100px rgba(16,185,129,0.3); }}
}}

@keyframes pulse-border-red {{
    0%, 100% {{ box-shadow: var(--shadow-glow-red); }}
    50% {{ box-shadow: 0 0 50px rgba(239,68,68,0.5), 0 0 100px rgba(239,68,68,0.3); }}
}}

@keyframes slide-up {{
    from {{ opacity: 0; transform: translateY(15px); }}
    to {{ opacity: 1; transform: translateY(0); }}
}}

@keyframes fade-in {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
}}

@keyframes float {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-4px); }}
}}

.animate-slide-up {{ animation: slide-up 0.4s ease-out; }}
.animate-pulse {{ animation: pulse-glow 2.5s ease-in-out infinite; }}
.animate-float {{ animation: float 3s ease-in-out infinite; }}

/* ─────────────────────────────────────────────────────────────────
   BASE STYLES
   ───────────────────────────────────────────────────────────────── */

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
    /* Subtle gradient background */
    background-image: 
        radial-gradient(ellipse 80% 50% at 50% -20%, {"rgba(139,92,246,0.06)" if theme == "dark" else "rgba(139,92,246,0.02)"}, transparent),
        radial-gradient(ellipse 60% 40% at 100% 100%, {"rgba(16,185,129,0.04)" if theme == "dark" else "rgba(16,185,129,0.01)"}, transparent);
    background-attachment: fixed;
}}

/* ─────────────────────────────────────────────────────────────────
   LAYOUT
   ───────────────────────────────────────────────────────────────── */

.dashboard {{
    max-width: 1440px;
    margin: 0 auto;
    padding: var(--space-6);
}}

/* ─────────────────────────────────────────────────────────────────
   BRAND HERO - Dramatic Entry
   ───────────────────────────────────────────────────────────────── */

.brand-hero {{
    text-align: center;
    padding: var(--space-10) var(--space-6) var(--space-8);
    margin-bottom: var(--space-6);
    position: relative;
    overflow: hidden;
}}

/* Ambient glow behind the brand */
.brand-hero::before {{
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 600px;
    height: 400px;
    background: radial-gradient(ellipse, {"rgba(139,92,246,0.15)" if theme == "dark" else "rgba(139,92,246,0.08)"} 0%, transparent 70%);
    pointer-events: none;
    z-index: 0;
}}

.brand-icon {{
    width: 120px;
    height: 120px;
    margin: 0 auto var(--space-5);
    position: relative;
    z-index: 1;
    animation: float 4s ease-in-out infinite;
    filter: drop-shadow(0 10px 40px {"rgba(139,92,246,0.4)" if theme == "dark" else "rgba(139,92,246,0.2)"});
}}

.brand-icon svg {{
    width: 100%;
    height: 100%;
}}

.brand-name {{
    font-size: 56px;
    font-weight: 800;
    letter-spacing: -2px;
    line-height: 1;
    margin-bottom: var(--space-3);
    position: relative;
    z-index: 1;
    background: var(--gradient-premium);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: none;
}}

/* Glow effect behind text */
.brand-name::after {{
    content: 'SPX PROPHET';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    font-size: 56px;
    font-weight: 800;
    letter-spacing: -2px;
    background: var(--gradient-premium);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    filter: blur(30px);
    opacity: 0.5;
    z-index: -1;
}}

.brand-tagline {{
    font-size: 16px;
    font-weight: 500;
    color: var(--text-secondary);
    letter-spacing: 4px;
    text-transform: uppercase;
    position: relative;
    z-index: 1;
}}

.brand-divider {{
    width: 80px;
    height: 2px;
    background: var(--gradient-premium);
    margin: var(--space-5) auto 0;
    border-radius: 1px;
    position: relative;
    z-index: 1;
}}

/* ─────────────────────────────────────────────────────────────────
   HEADER - Slim Info Bar (simplified after brand hero)
   ───────────────────────────────────────────────────────────────── */

.header {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: var(--space-6);
    padding: var(--space-4) var(--space-6);
    margin-bottom: var(--space-6);
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-xl);
    box-shadow: var(--shadow-card);
    position: relative;
}}

/* Shine effect */
.header::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
}}

/* Hide old logo section - no longer needed */
.logo {{
    display: none;
}}

.logo-mark {{
    display: none;
}}
    background: var(--gradient-premium);
    border-radius: var(--radius-lg);
    display: grid;
    place-items: center;
    font-family: var(--font-mono);
    font-size: 15px;
    font-weight: 700;
    color: white;
    letter-spacing: -0.5px;
    box-shadow: 0 4px 20px rgba(139, 92, 246, 0.4);
    animation: float 4s ease-in-out infinite;
}}

.logo-text {{
    display: flex;
    flex-direction: column;
    gap: 3px;
}}

.logo-title {{
    font-size: 28px;
    font-weight: 800;
    letter-spacing: -1px;
    line-height: 1.1;
    background: var(--gradient-premium);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}

.logo-subtitle {{
    font-size: 12px;
    color: var(--text-tertiary);
    font-weight: 500;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}}

.header-meta {{
    display: flex;
    align-items: center;
    gap: var(--space-8);
}}

.meta-group {{
    display: flex;
    gap: var(--space-6);
}}

.meta-item {{
    text-align: center;
    padding: var(--space-2) var(--space-4);
    background: var(--bg-surface-2);
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
}}

.meta-label {{
    font-size: 9px;
    font-weight: 600;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 2px;
}}

.meta-value {{
    font-family: var(--font-mono);
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
}}

.clock {{
    font-family: var(--font-mono);
    font-size: 24px;
    font-weight: 500;
    color: var(--text-primary);
    letter-spacing: -1px;
}}

/* ─────────────────────────────────────────────────────────────────
   SIGNAL HERO - The main decision display (PREMIUM)
   ───────────────────────────────────────────────────────────────── */

.signal-hero {{
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-2xl);
    padding: var(--space-8);
    margin-bottom: var(--space-6);
    display: grid;
    grid-template-columns: 1fr 280px;
    gap: var(--space-6);
    box-shadow: var(--shadow-card);
    position: relative;
    overflow: hidden;
    animation: slide-up 0.4s ease-out;
}}

/* Shine effect on top edge */
.signal-hero::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.1), transparent);
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
    padding: var(--space-3) var(--space-5);
    border-radius: var(--radius-lg);
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.5px;
    transition: all 0.3s ease;
}}

.direction-badge.calls {{
    background: var(--gradient-calls);
    color: var(--success);
    border: 1px solid var(--success-muted);
    box-shadow: 0 0 20px var(--success-glow);
}}

.direction-badge.puts {{
    background: var(--gradient-puts);
    color: var(--danger);
    border: 1px solid var(--danger-muted);
    box-shadow: 0 0 20px var(--danger-glow);
}}

.direction-badge.wait {{
    background: var(--bg-surface-2);
    color: var(--text-tertiary);
    border: 1px solid var(--border);
}}

.signal-title {{
    font-size: 36px;
    font-weight: 800;
    letter-spacing: -1.5px;
    line-height: 1.1;
}}

.signal-title.calls {{ 
    color: var(--success); 
    text-shadow: 0 0 40px var(--success-glow);
}}
.signal-title.puts {{ 
    color: var(--danger); 
    text-shadow: 0 0 40px var(--danger-glow);
}}
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
    border: 1px solid var(--border);
    width: fit-content;
}}

.confluence-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    animation: pulse-glow 2s ease-in-out infinite;
}}

.confluence-dot.strong {{ 
    background: var(--success); 
    box-shadow: 0 0 10px var(--success-glow);
}}
.confluence-dot.moderate {{ 
    background: var(--info); 
}}
.confluence-dot.weak {{ background: var(--text-tertiary); }}
.confluence-dot.conflict {{ 
    background: var(--danger); 
    box-shadow: 0 0 10px var(--danger-glow);
}}

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
    margin-bottom: var(--space-6);
}}

.indicator-card {{
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    -webkit-backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-xl);
    padding: var(--space-5);
    position: relative;
    overflow: hidden;
    transition: all 0.3s ease;
    box-shadow: var(--shadow-card);
}}

.indicator-card:hover {{
    transform: translateY(-4px);
    border-color: var(--border-strong);
    box-shadow: var(--shadow-lg);
}}

/* Top accent bar */
.indicator-card::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
}}

.indicator-card.long::before {{ 
    background: linear-gradient(90deg, var(--success), rgba(16,185,129,0.5)); 
}}
.indicator-card.short::before {{ 
    background: linear-gradient(90deg, var(--danger), rgba(239,68,68,0.5)); 
}}
.indicator-card.neutral::before {{ 
    background: var(--text-tertiary); 
}}

.indicator-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-3);
}}

.indicator-title {{
    font-size: 10px;
    font-weight: 700;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 1px;
}}

.indicator-status {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
}}

.indicator-status.long {{ 
    background: var(--success); 
    box-shadow: 0 0 8px var(--success-glow);
}}
.indicator-status.short {{ 
    background: var(--danger); 
    box-shadow: 0 0 8px var(--danger-glow);
}}
.indicator-status.neutral {{ background: var(--text-tertiary); }}

.indicator-value {{
    font-size: 24px;
    font-weight: 800;
    font-family: var(--font-mono);
    letter-spacing: -1px;
    margin-bottom: var(--space-1);
}}

.indicator-value.long {{ color: var(--success); }}
.indicator-value.short {{ color: var(--danger); }}
.indicator-value.neutral {{ color: var(--text-tertiary); }}

.indicator-detail {{
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.4;
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
    padding: var(--space-4) var(--space-5);
    background: var(--glass-bg);
    backdrop-filter: var(--glass-blur);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-xl) var(--radius-xl) 0 0;
    cursor: pointer;
    transition: all 0.2s;
}}

.setups-header:hover {{
    background: var(--bg-surface-2);
}}

.setups-title {{
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.setups-title.calls {{ color: var(--success); }}
.setups-title.puts {{ color: var(--danger); }}

.setups-count {{
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: var(--radius-md);
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
    border: 1px solid var(--glass-border);
    border-top: none;
    border-radius: 0 0 var(--radius-xl) var(--radius-xl);
    padding: var(--space-5);
}}

.setups-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-4);
}}

.setup-card {{
    background: var(--glass-bg);
    backdrop-filter: blur(10px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    position: relative;
    overflow: hidden;
    transition: all 0.3s ease;
}}

.setup-card:hover {{
    transform: translateY(-2px);
    border-color: var(--border-strong);
}}

.setup-card::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
}}

.setup-card.calls::before {{ background: linear-gradient(90deg, var(--success), transparent); }}
.setup-card.puts::before {{ background: linear-gradient(90deg, var(--danger), transparent); }}
.setup-card.active {{ 
    border-color: var(--success-muted); 
    box-shadow: 0 0 20px var(--success-glow);
}}
.setup-card.active.puts {{ 
    border-color: var(--danger-muted); 
    box-shadow: 0 0 20px var(--danger-glow);
}}
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

.collapse-icon {{
    transition: transform 0.2s ease;
    color: var(--text-muted);
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
.table-section.collapsed .table-content {{ display: none; }}
.table-section.collapsed .table-header {{ border-bottom: none; }}
.table-section.collapsed .collapse-icon {{ transform: rotate(-90deg); }}

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

<!-- BRAND HERO -->
<div class="brand-hero">
    <div class="brand-icon">
        <svg viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
            <!-- Three ascending triangles forming a pyramid -->
            <!-- Back triangle (largest, most transparent) -->
            <path d="M60 10 L105 95 L15 95 Z" fill="url(#grad1)" opacity="0.3"/>
            <!-- Middle triangle -->
            <path d="M60 25 L95 90 L25 90 Z" fill="url(#grad2)" opacity="0.6"/>
            <!-- Front triangle (smallest, most solid) -->
            <path d="M60 40 L85 85 L35 85 Z" fill="url(#grad3)" opacity="0.9"/>
            <!-- Glow center line -->
            <path d="M60 40 L60 85" stroke="url(#grad3)" stroke-width="2" opacity="0.8"/>
            <!-- Three pillar dots -->
            <circle cx="40" cy="85" r="4" fill="#8b5cf6"/>
            <circle cx="60" cy="40" r="4" fill="#a855f7"/>
            <circle cx="80" cy="85" r="4" fill="#8b5cf6"/>
            <!-- Gradients -->
            <defs>
                <linearGradient id="grad1" x1="60" y1="10" x2="60" y2="95" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stop-color="#6366f1"/>
                    <stop offset="100%" stop-color="#8b5cf6"/>
                </linearGradient>
                <linearGradient id="grad2" x1="60" y1="25" x2="60" y2="90" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stop-color="#7c3aed"/>
                    <stop offset="100%" stop-color="#a855f7"/>
                </linearGradient>
                <linearGradient id="grad3" x1="60" y1="40" x2="60" y2="85" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stop-color="#8b5cf6"/>
                    <stop offset="100%" stop-color="#c084fc"/>
                </linearGradient>
            </defs>
        </svg>
    </div>
    <div class="brand-name">SPX PROPHET</div>
    <div class="brand-tagline">Where Structure Becomes Foresight</div>
    <div class="brand-divider"></div>
</div>

<!-- HEADER (Info Bar) -->
<header class="header">
    <div class="meta-group">
        <div class="meta-item">
            <div class="meta-label">Entry Window</div>
            <div class="meta-value">{format_countdown(get_time_until(ENTRY_TARGET))}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Cutoff</div>
            <div class="meta-value">{format_countdown(get_time_until(CUTOFF_TIME))}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Time CT</div>
            <div class="meta-value">{now.strftime("%H:%M")}</div>
        </div>
        <div class="meta-item">
            <div class="meta-label">Date</div>
            <div class="meta-value">{trading_date.strftime("%b %d")}</div>
        </div>
    </div>
</header>
'''
    
    # Alert banners
    if is_historical:
        html += f'<div style="background:var(--bg-surface-2);border:1px solid var(--border);border-radius:var(--radius-md);padding:var(--space-3) var(--space-4);margin-bottom:var(--space-4);font-size:12px;color:var(--text-secondary);">📅 Historical Mode: {trading_date.strftime("%A, %B %d, %Y")}</div>'
    
    # Economic Event Warning Banner
    econ_events = get_economic_events(trading_date)
    event_warning, should_warn, warning_level = get_event_warning(econ_events)
    
    # Also check for manual event
    manual_event = st.session_state.get("manual_event", "")
    manual_event_time = st.session_state.get("manual_event_time", "")
    
    if econ_events or manual_event:
        # Build event list HTML
        event_items = []
        for event_name, event_time, impact in econ_events:
            icon = "🔴" if impact == "HIGH" else "🟡" if impact == "MEDIUM" else "🔵"
            event_items.append(f"{icon} {event_name} @ {event_time}")
        
        if manual_event:
            event_items.append(f"📌 {manual_event} @ {manual_event_time or 'TBD'}")
        
        # Determine banner style based on highest impact
        if warning_level == "HIGH":
            banner_bg = "linear-gradient(135deg, rgba(239,68,68,0.2) 0%, rgba(239,68,68,0.05) 100%)"
            banner_border = "var(--danger)"
            banner_icon = "⚠️"
            banner_title = "HIGH IMPACT EVENT"
        elif warning_level == "MEDIUM" or manual_event:
            banner_bg = "linear-gradient(135deg, rgba(234,179,8,0.2) 0%, rgba(234,179,8,0.05) 100%)"
            banner_border = "var(--warning)"
            banner_icon = "📌"
            banner_title = "NOTABLE EVENT"
        else:
            banner_bg = "var(--bg-surface)"
            banner_border = "var(--border)"
            banner_icon = "📅"
            banner_title = "TODAY'S EVENTS"
        
        events_html = " | ".join(event_items)
        
        html += f'''
<div style="background:{banner_bg};border:1px solid {banner_border};border-radius:var(--radius-md);padding:var(--space-3) var(--space-4);margin-bottom:var(--space-4);">
    <div style="display:flex;align-items:center;gap:var(--space-2);">
        <span style="font-size:16px;">{banner_icon}</span>
        <span style="font-size:12px;font-weight:600;color:var(--text-primary);">{banner_title}</span>
    </div>
    <div style="font-size:12px;color:var(--text-secondary);margin-top:var(--space-2);">{events_html}</div>
    {"<div style='font-size:11px;color:var(--danger);margin-top:var(--space-2);font-weight:600;'>⚡ Avoid entries 30 min before/after HIGH impact events</div>" if warning_level == "HIGH" else ""}
</div>
'''
    
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
    
    # Find BEST setup - NEW PRIORITY ORDER:
    # 1. Day structure confluence (closest to DS line)
    # 2. If inside a cone, that cone's setup  
    # 3. Score by proximity to current price
    best_setup = None
    setups_with_confluence = []  # Track which setups have DS confluence
    
    search_direction = show_direction if show_direction in ["CALLS", "PUTS"] else None
    if search_direction and not has_conflict:
        # Exclude GREY, BROKEN, and TESTED setups from consideration
        matching = [s for s in setups if s.direction == search_direction and s.status not in ["GREY", "BROKEN", "TESTED"]]
        if matching:
            # PRIORITY 1: Day Structure Confluence
            # For CALLS, check low line confluence (support)
            # For PUTS, check high line confluence (resistance)
            if day_structure:
                if search_direction == "CALLS" and day_structure.low_line_valid and day_structure.low_line_at_entry > 0:
                    # Find setup closest to day structure low line
                    for s in matching:
                        dist_to_ds = abs(s.entry - day_structure.low_line_at_entry)
                        if dist_to_ds <= 10:  # Within 10 pts = confluence
                            setups_with_confluence.append((s, dist_to_ds))
                    if setups_with_confluence:
                        # Best = closest to day structure line
                        setups_with_confluence.sort(key=lambda x: x[1])
                        best_setup = setups_with_confluence[0][0]
                
                elif search_direction == "PUTS" and day_structure.high_line_valid and day_structure.high_line_at_entry > 0:
                    # Find setup closest to day structure high line
                    for s in matching:
                        dist_to_ds = abs(s.entry - day_structure.high_line_at_entry)
                        if dist_to_ds <= 10:  # Within 10 pts = confluence
                            setups_with_confluence.append((s, dist_to_ds))
                    if setups_with_confluence:
                        setups_with_confluence.sort(key=lambda x: x[1])
                        best_setup = setups_with_confluence[0][0]
            
            # PRIORITY 2: If inside a cone and that cone has a matching setup, use it
            if not best_setup:
                if price_proximity and price_proximity.inside_cone and price_proximity.inside_cone_name:
                    inside_match = [s for s in matching if s.cone_name == price_proximity.inside_cone_name]
                    if inside_match:
                        best_setup = inside_match[0]
            
            # PRIORITY 3: Score by proximity to current price
            if not best_setup:
                def setup_score(s):
                    if price_proximity and price_proximity.current_price > 0:
                        price_to_entry = abs(s.entry - price_proximity.current_price)
                        distance_score = max(0, 50 - price_to_entry)
                    else:
                        distance_score = max(0, 30 - s.distance)
                    width_score = s.cone_width
                    return distance_score + width_score
                best_setup = max(matching, key=setup_score)
    
    # Create set of cone names with confluence for de-emphasizing others
    confluence_cone_names = set(s.cone_name for s, _ in setups_with_confluence) if setups_with_confluence else set()
    
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

    # ════════════════════════════════════════════════════════════════════════
    # CONTEXTUAL RULE WARNINGS
    # Show warnings when rules are being violated or need attention
    # ════════════════════════════════════════════════════════════════════════
    
    rule_warnings = []
    
    # Rule 1.2: Never trade against trend
    if ma_bias and vix_zone:
        if ma_bias.bias == "LONG" and vix_zone.bias == "PUTS":
            rule_warnings.append(("Rule 1.2", "Do not look for PUTS in bullish environment (50 EMA > 200 SMA, Price > 50 EMA)", "danger"))
        elif ma_bias.bias == "SHORT" and vix_zone.bias == "CALLS":
            rule_warnings.append(("Rule 1.2", "Do not look for CALLS in bearish environment (50 EMA < 200 SMA, Price < 50 EMA)", "danger"))
    
    # Rule 2.4: VIX + MA must align
    if has_conflict:
        rule_warnings.append(("Rule 2.4", f"VIX and MA bias CONFLICT — No trade allowed", "danger"))
    
    # Rule 3.2: Both lines required
    if day_structure:
        if day_structure.high_line_valid and not day_structure.low_line_valid:
            rule_warnings.append(("Rule 3.2", "Only High Line defined — Need BOTH lines for strike calculation", "warning"))
        elif day_structure.low_line_valid and not day_structure.high_line_valid:
            rule_warnings.append(("Rule 3.2", "Only Low Line defined — Need BOTH lines for strike calculation", "warning"))
    
    # Rule 4.2: Need 2 price points for projection
    if day_structure and day_structure.high_line_valid and day_structure.low_line_valid:
        if vix_zone.bias == "CALLS" or (vix_zone.bias == "WAIT" and ma_bias and ma_bias.bias == "LONG"):
            if day_structure.call_price_asia > 0 and day_structure.call_price_london == 0:
                rule_warnings.append(("Rule 4.2", "Only 1 CALL price point — Need Asia + London for projection", "warning"))
            elif day_structure.call_price_asia == 0 and day_structure.call_price_london > 0:
                rule_warnings.append(("Rule 4.2", "Only 1 CALL price point — Need Asia + London for projection", "warning"))
        if vix_zone.bias == "PUTS" or (vix_zone.bias == "WAIT" and ma_bias and ma_bias.bias == "SHORT"):
            if day_structure.put_price_asia > 0 and day_structure.put_price_london == 0:
                rule_warnings.append(("Rule 4.2", "Only 1 PUT price point — Need Asia + London for projection", "warning"))
            elif day_structure.put_price_asia == 0 and day_structure.put_price_london > 0:
                rule_warnings.append(("Rule 4.2", "Only 1 PUT price point — Need Asia + London for projection", "warning"))
    
    # Rule 5.2: Entry window check
    if market_ctx and market_ctx.time_warning:
        if market_ctx.time_warning == "Very late":
            rule_warnings.append(("Rule 5.2", "After 11:30am CT — Contracts too cheap, theta dominant", "danger"))
        elif market_ctx.time_warning == "Late entry":
            rule_warnings.append(("Rule 5.2", "10:30-11:30am CT — Late entry, reduced opportunity", "warning"))
    
    # Display warnings if any
    if rule_warnings:
        html += '''
<!-- RULE WARNINGS -->
<div style="margin-bottom:var(--space-4);">
'''
        for rule_id, rule_msg, severity in rule_warnings:
            if severity == "danger":
                bg_color = "var(--danger-soft)"
                border_color = "var(--danger)"
                icon = "⛔"
            else:
                bg_color = "var(--warning-soft)"
                border_color = "var(--warning)"
                icon = "⚠️"
            
            html += f'''
    <div style="background:{bg_color};border:1px solid {border_color};border-radius:var(--radius-sm);padding:var(--space-3);margin-bottom:var(--space-2);display:flex;align-items:center;gap:var(--space-2);">
        <span style="font-size:16px;">{icon}</span>
        <div>
            <span style="font-weight:700;color:var(--text-primary);">{rule_id}:</span>
            <span style="color:var(--text-secondary);">{rule_msg}</span>
        </div>
    </div>
'''
        html += '</div>'

    # ════════════════════════════════════════════════════════════════════════
    # YOUR TRADE - The Main Focus (replaces old Price Proximity)
    # Shows: Direction + Entry + Contract + Risk/Reward + Flip Signal
    # ════════════════════════════════════════════════════════════════════════
    
    # Get dynamic stop from market context (based on VIX level)
    dynamic_stop = market_ctx.recommended_stop if market_ctx else STOP_LOSS_PTS
    
    # Determine the best trade based on VIX + MA + Day Structure
    trade_direction = None
    trade_entry_spx = 0
    trade_target_spx = 0  # Exit zone
    trade_contract = ""
    trade_contract_price = 0
    trade_strike = 0
    trade_stop = 0
    trade_cone = ""
    trade_ds_line = ""
    flip_watch_contract = ""
    flip_watch_price = 0
    flip_enter_direction = ""
    has_flip_signal = False
    current_price = price_proximity.current_price if price_proximity else 0
    
    # Get direction from VIX/MA confluence
    if not has_conflict:
        if vix_zone.bias == "CALLS" or (vix_zone.bias == "WAIT" and ma_bias and ma_bias.bias == "LONG"):
            trade_direction = "CALLS"
        elif vix_zone.bias == "PUTS" or (vix_zone.bias == "WAIT" and ma_bias and ma_bias.bias == "SHORT"):
            trade_direction = "PUTS"
    
    # ════════════════════════════════════════════════════════════════════════
    # FLIP SIGNAL LOGIC - When a line breaks, REVERSE the trade
    # ════════════════════════════════════════════════════════════════════════
    # When Low Line breaks DOWN → FLIP to PUTS (bearish)
    # When High Line breaks UP → FLIP to CALLS (bullish)
    # The FLIP trade is often the biggest move of the day
    # ════════════════════════════════════════════════════════════════════════
    
    if day_structure and day_structure.high_line_valid and day_structure.low_line_valid:
        # Check for FLIP conditions FIRST - these override normal direction
        if day_structure.low_line_broken:
            # LOW LINE BROKEN = FLIP TO PUTS
            # This is bearish - support broke, expect continuation down
            has_flip_signal = True
            trade_direction = "PUTS"  # Override to PUTS regardless of VIX/MA
            # FLIP ENTRY LOGIC:
            # When Low Line BREAKS, price is BELOW the structure
            # Entry = Low Line (broken support, now resistance on retest)
            # Target = Further down (could be Asia Low or extension)
            # This catches the continuation move after the break
            trade_entry_spx = day_structure.low_line_at_entry  # Enter at broken low line (retest)
            trade_target_spx = day_structure.low_line_at_entry - (day_structure.high_line_at_entry - day_structure.low_line_at_entry)  # Target = extension down
            trade_ds_line = "Low Line (Broken)"
            trade_cone = "Day Structure ⚡FLIP"
            
            # STRIKE = The LONDON LOW (where support broke)
            # Example: London Low 6874.9 → Strike = 6875P
            break_level = day_structure.london_low if day_structure.london_low > 0 else day_structure.low_line_at_entry
            trade_strike = int(round(break_level / 5) * 5)
            trade_contract = f"{trade_strike}P"
            
            # Use PUT contract price
            if day_structure.put_price_at_entry > 0:
                trade_contract_price = day_structure.put_price_at_entry
            
            trade_stop = trade_entry_spx + dynamic_stop
            
            # Show what to watch for (CALL price returning = confirmation to enter PUTS)
            if day_structure.call_price_at_entry > 0:
                flip_watch_contract = f"{trade_strike}C"
                flip_watch_price = day_structure.call_price_at_entry
                flip_enter_direction = "PUTS"  # When CALL returns to this price, enter PUTS
        
        elif day_structure.high_line_broken:
            # HIGH LINE BROKEN = FLIP TO CALLS
            # When High Line BREAKS, price is ABOVE the structure
            # Entry = High Line (broken resistance, now support on retest)
            # Target = Further up (extension)
            has_flip_signal = True
            trade_direction = "CALLS"  # Override to CALLS regardless of VIX/MA
            trade_entry_spx = day_structure.high_line_at_entry  # Enter at broken high line (retest)
            trade_target_spx = day_structure.high_line_at_entry + (day_structure.high_line_at_entry - day_structure.low_line_at_entry)  # Target = extension up
            trade_ds_line = "High Line (Broken)"
            trade_cone = "Day Structure ⚡FLIP"
            
            # STRIKE = The LONDON HIGH (where resistance broke)
            break_level = day_structure.london_high if day_structure.london_high > 0 else day_structure.high_line_at_entry
            trade_strike = int(round(break_level / 5) * 5)
            trade_contract = f"{trade_strike}C"
            
            # Use CALL contract price
            if day_structure.call_price_at_entry > 0:
                trade_contract_price = day_structure.call_price_at_entry
            
            trade_stop = trade_entry_spx - dynamic_stop
            
            # Show what to watch for
            if day_structure.put_price_at_entry > 0:
                flip_watch_contract = f"{trade_strike + 5}P"
                flip_watch_price = day_structure.put_price_at_entry
                flip_enter_direction = "CALLS"  # When PUT returns to this price, enter CALLS
    
    # NORMAL trade (no flip) - use Day Structure if available
    if trade_direction and not has_flip_signal and day_structure and day_structure.high_line_valid and day_structure.low_line_valid:
        if trade_direction == "CALLS":
            trade_entry_spx = day_structure.low_line_at_entry
            trade_target_spx = day_structure.high_line_at_entry
            trade_ds_line = "Low Line"
            trade_cone = day_structure.low_confluence_cone if day_structure.low_confluence_cone else "Day Structure"
            
            # Get contract price if available
            if day_structure.call_price_at_entry > 0:
                trade_contract_price = day_structure.call_price_at_entry
            
            # Strike = Entry + 10 (slightly OTM at entry, ITM at target)
            # CALL strike ABOVE entry = OTM
            trade_strike = int(round(trade_entry_spx / 5) * 5) + 10
            trade_contract = f"{trade_strike}C"
            
            trade_stop = trade_entry_spx - dynamic_stop
                
        elif trade_direction == "PUTS":
            trade_entry_spx = day_structure.high_line_at_entry
            trade_target_spx = day_structure.low_line_at_entry
            trade_ds_line = "High Line"
            trade_cone = day_structure.high_confluence_cone if day_structure.high_confluence_cone else "Day Structure"
            
            # Get contract price if available
            if day_structure.put_price_at_entry > 0:
                trade_contract_price = day_structure.put_price_at_entry
            
            # Strike = Entry - 10 (slightly OTM at entry, ITM at target)
            # PUT strike BELOW entry = OTM
            trade_strike = int(round(trade_entry_spx / 5) * 5) - 10
            trade_contract = f"{trade_strike}P"
            
            trade_stop = trade_entry_spx + dynamic_stop
    
    # Fallback to best setup from cones if no Day Structure
    elif trade_direction and best_setup and not has_flip_signal:
        trade_entry_spx = best_setup.entry
        trade_cone = best_setup.cone_name
        trade_ds_line = ""
        trade_stop = best_setup.stop
        if best_setup.option:
            trade_strike = best_setup.option.spx_strike
            trade_contract = f"{trade_strike}{'C' if trade_direction == 'CALLS' else 'P'}"
            trade_contract_price = best_setup.option.spx_price_est
    
    # Calculate distance from current price
    distance_to_entry = 0
    if current_price > 0 and trade_entry_spx > 0:
        distance_to_entry = trade_entry_spx - current_price
    
    # Calculate risk/reward if we have contract price
    risk_dollars = 0
    target_50_dollars = 0
    target_100_dollars = 0
    if trade_contract_price > 0:
        # Assuming 1 contract = 100 multiplier for SPX options
        risk_dollars = STOP_LOSS_PTS * 10  # Rough estimate: $10 per point for ATM-ish options
        target_50_dollars = trade_contract_price * 0.5 * 100  # 50% gain on contract
        target_100_dollars = trade_contract_price * 1.0 * 100  # 100% gain on contract
    
    # Build YOUR TRADE section
    if trade_direction and trade_entry_spx > 0:
        trade_color = "var(--success)" if trade_direction == "CALLS" else "var(--danger)"
        trade_bg = "linear-gradient(135deg, rgba(34,197,94,0.15) 0%, rgba(34,197,94,0.05) 100%)" if trade_direction == "CALLS" else "linear-gradient(135deg, rgba(239,68,68,0.15) 0%, rgba(239,68,68,0.05) 100%)"
        trade_icon = "↑" if trade_direction == "CALLS" else "↓"
        
        # Confluence info
        confluence_text = f"{trade_ds_line}"
        if trade_cone and trade_ds_line:
            confluence_text += f" + {trade_cone}"
        elif trade_cone:
            confluence_text = trade_cone
        
        # Calculate channel width (profit runway)
        channel_width = abs(trade_target_spx - trade_entry_spx) if trade_target_spx > 0 else 0
        
        # Contract display with target
        contract_html = ""
        if trade_contract:
            target_html = ""
            if trade_target_spx > 0:
                target_html = f'''
                    <div style="text-align:center;">
                        <div style="font-size:11px;color:var(--text-muted);">TARGET</div>
                        <div style="font-size:16px;font-weight:600;color:var(--success);font-family:var(--font-mono);">{trade_target_spx:,.0f}</div>
                        <div style="font-size:10px;color:var(--text-muted);">{channel_width:.0f} pts</div>
                    </div>'''
            
            # Show price if available, otherwise show "needs 2 prices" message
            if trade_contract_price > 0:
                price_html = f'''
                    <div style="text-align:center;">
                        <div style="font-size:11px;color:var(--text-muted);">PROJECTED COST</div>
                        <div style="font-size:24px;font-weight:700;color:var(--text-primary);font-family:var(--font-mono);">${trade_contract_price:.2f}</div>
                    </div>'''
            else:
                price_html = f'''
                    <div style="text-align:center;">
                        <div style="font-size:11px;color:var(--text-muted);">PROJECTED COST</div>
                        <div style="font-size:14px;font-weight:600;color:var(--warning);">Need 2 prices</div>
                        <div style="font-size:10px;color:var(--text-muted);">Asia + London</div>
                    </div>'''
            
            contract_html = f'''
            <div style="background:var(--bg-surface);padding:var(--space-3);border-radius:var(--radius-sm);border-left:3px solid {trade_color};margin-top:var(--space-3);">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <div style="font-size:11px;color:var(--text-muted);">CONTRACT</div>
                        <div style="font-size:20px;font-weight:700;color:{trade_color};font-family:var(--font-mono);">{trade_contract}</div>
                        <div style="font-size:10px;color:var(--text-muted);">OTM at entry → ITM at target</div>
                    </div>
                    {price_html}
                    {target_html}
                    <div style="text-align:right;">
                        <div style="font-size:11px;color:var(--text-muted);">STOP</div>
                        <div style="font-size:16px;font-weight:600;color:var(--danger);font-family:var(--font-mono);">{trade_stop:,.0f}</div>
                        <div style="font-size:10px;color:var(--text-muted);">{dynamic_stop:.0f} pts</div>
                    </div>
                </div>
            </div>'''
        
        # Distance from current price
        distance_html = ""
        if current_price > 0:
            dist_color = "var(--success)" if abs(distance_to_entry) <= 10 else "var(--warning)" if abs(distance_to_entry) <= 20 else "var(--text-secondary)"
            distance_html = f'''
            <div style="margin-top:var(--space-3);padding:var(--space-2);background:var(--bg-elevated);border-radius:var(--radius-sm);">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <span style="color:var(--text-muted);font-size:11px;">CURRENT PRICE</span>
                        <span style="font-family:var(--font-mono);font-weight:600;color:var(--text-primary);margin-left:8px;">{current_price:,.0f}</span>
                    </div>
                    <div style="text-align:right;">
                        <span style="color:var(--text-muted);font-size:11px;">DISTANCE TO ENTRY</span>
                        <span style="font-family:var(--font-mono);font-weight:700;color:{dist_color};margin-left:8px;">{distance_to_entry:+.0f} pts</span>
                    </div>
                </div>
            </div>'''
        
        # Flip signal
        flip_html = ""
        if has_flip_signal:
            flip_html = f'''
            <div style="margin-top:var(--space-3);padding:var(--space-3);background:var(--warning-soft);border-radius:var(--radius-sm);border:1px solid var(--warning);">
                <div style="display:flex;align-items:center;gap:var(--space-2);margin-bottom:var(--space-2);">
                    <span style="font-size:16px;">⚡</span>
                    <span style="font-size:12px;font-weight:700;color:var(--warning);">STRUCTURE BROKEN - FLIP SIGNAL ACTIVE</span>
                </div>
                <div style="color:var(--text-primary);font-size:13px;">
                    Watch <strong style="font-family:var(--font-mono);">{flip_watch_contract}</strong> return to 
                    <strong style="font-family:var(--font-mono);">${flip_watch_price:.2f}</strong> 
                    → Then enter <strong style="color:{'var(--danger)' if flip_enter_direction == 'PUTS' else 'var(--success)'};">{flip_enter_direction}</strong>
                </div>
            </div>'''
        
        html += f'''
<!-- YOUR TRADE - PRIMARY ACTION -->
<div style="background:{trade_bg};border:2px solid {trade_color};border-radius:var(--radius-xl);padding:var(--space-5);margin-bottom:var(--space-4);box-shadow:0 4px 20px rgba(0,0,0,0.2);">
    <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-3);">
        <div style="width:48px;height:48px;background:{trade_color};border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:24px;color:white;font-weight:700;">{trade_icon}</div>
        <div>
            <div style="font-size:12px;color:var(--text-muted);letter-spacing:1px;">YOUR TRADE</div>
            <div style="font-size:28px;font-weight:700;color:{trade_color};">{trade_direction}</div>
        </div>
        <div style="margin-left:auto;text-align:right;">
            <div style="font-size:11px;color:var(--text-muted);">ENTRY LEVEL</div>
            <div style="font-size:32px;font-weight:700;color:var(--text-primary);font-family:var(--font-mono);">{trade_entry_spx:,.0f}</div>
            <div style="font-size:12px;color:var(--text-secondary);">{confluence_text}</div>
        </div>
    </div>
    {contract_html}
    {distance_html}
    {flip_html}
</div>
'''
    elif has_conflict:
        # NO TRADE state
        html += f'''
<!-- NO TRADE -->
<div style="background:var(--danger-soft);border:2px solid var(--danger);border-radius:var(--radius-xl);padding:var(--space-5);margin-bottom:var(--space-4);">
    <div style="display:flex;align-items:center;gap:var(--space-3);">
        <div style="width:48px;height:48px;background:var(--danger);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:24px;color:white;">⛔</div>
        <div>
            <div style="font-size:12px;color:var(--text-muted);letter-spacing:1px;">SIGNAL CONFLICT</div>
            <div style="font-size:28px;font-weight:700;color:var(--danger);">NO TRADE</div>
            <div style="font-size:14px;color:var(--text-secondary);margin-top:4px;">{confluence.no_trade_reason if confluence else "VIX and MA signals conflict"}</div>
        </div>
    </div>
</div>
'''
    else:
        # WAIT state - need more data
        html += f'''
<!-- WAITING FOR SETUP -->
<div style="background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-xl);padding:var(--space-5);margin-bottom:var(--space-4);">
    <div style="display:flex;align-items:center;gap:var(--space-3);">
        <div style="width:48px;height:48px;background:var(--bg-elevated);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:24px;color:var(--text-muted);">⏳</div>
        <div>
            <div style="font-size:12px;color:var(--text-muted);letter-spacing:1px;">WAITING</div>
            <div style="font-size:28px;font-weight:700;color:var(--text-secondary);">Enter Day Structure</div>
            <div style="font-size:14px;color:var(--text-muted);margin-top:4px;">Need BOTH High Line + Low Line for strike calculation</div>
        </div>
    </div>
</div>
'''

    # ════════════════════════════════════════════════════════════════════════
    # DAY STRUCTURE ZONES - Buy & Exit Points
    # Low Line = CALL BUY ZONE (cheapest) / PUT EXIT ZONE (exhausted)
    # High Line = PUT BUY ZONE (cheapest) / CALL EXIT ZONE (exhausted)
    # ════════════════════════════════════════════════════════════════════════
    
    if current_price > 0 and day_structure and (day_structure.low_line_valid or day_structure.high_line_valid):
        calls_entry = day_structure.low_line_at_entry if day_structure.low_line_valid else 0
        puts_entry = day_structure.high_line_at_entry if day_structure.high_line_valid else 0
        
        calls_dist = calls_entry - current_price if calls_entry > 0 else 0
        puts_dist = puts_entry - current_price if puts_entry > 0 else 0
        
        # Channel width = profit runway
        channel_width = puts_entry - calls_entry if (puts_entry > 0 and calls_entry > 0) else 0
        
        # Position in channel
        position_text = ""
        position_color = "var(--text-secondary)"
        if calls_entry > 0 and puts_entry > 0:
            if current_price < calls_entry:
                position_text = "BELOW CHANNEL"
                position_color = "var(--danger)"
            elif current_price > puts_entry:
                position_text = "ABOVE CHANNEL"
                position_color = "var(--danger)"
            else:
                # Calculate position as percentage through channel
                pct_through = ((current_price - calls_entry) / channel_width * 100) if channel_width > 0 else 50
                position_text = f"IN CHANNEL ({pct_through:.0f}% from bottom)"
                position_color = "var(--success)"
        
        # Contract info - USE LONDON PRICES (most recent known), not projections
        # The projected prices are unreliable due to 0DTE theta/gamma dynamics
        call_at_low = f"${day_structure.call_price_london:.2f}" if day_structure.call_price_london > 0 else (f"${day_structure.call_price_asia:.2f}" if day_structure.call_price_asia > 0 else "—")
        put_at_high = f"${day_structure.put_price_london:.2f}" if day_structure.put_price_london > 0 else (f"${day_structure.put_price_asia:.2f}" if day_structure.put_price_asia > 0 else "—")
        
        # Show broken status
        low_broken_badge = "<div style='font-size:10px;color:var(--warning);font-weight:600;margin-top:4px;'>⚡ BROKEN</div>" if day_structure.low_line_broken else ""
        high_broken_badge = "<div style='font-size:10px;color:var(--warning);font-weight:600;margin-top:4px;'>⚡ BROKEN</div>" if day_structure.high_line_broken else ""
        
        # Structure quality and pivot info
        quality_color = "var(--success)" if day_structure.structure_quality == "STRONG" else "var(--warning)" if day_structure.structure_quality == "MODERATE" else "var(--text-muted)"
        quality_icon = "✅" if day_structure.structure_quality == "STRONG" else "⚠️" if day_structure.structure_quality == "MODERATE" else "○"
        
        # Build pivot info text
        pivot_info = ""
        if day_structure.low_line_pivot or day_structure.high_line_pivot:
            pivot_parts = []
            if day_structure.low_line_pivot:
                pivot_parts.append(f"Low: {day_structure.low_line_pivot_type.replace('_', ' ')}")
            if day_structure.high_line_pivot:
                pivot_parts.append(f"High: {day_structure.high_line_pivot_type.replace('_', ' ')}")
            pivot_info = f"<div style='font-size:10px;color:var(--warning);'>Pivot: {' | '.join(pivot_parts)}</div>"
        
        # Build line segment info
        low_segment = f"({day_structure.low_line_active_segment.replace('_', '→')})" if day_structure.low_line_active_segment else ""
        high_segment = f"({day_structure.high_line_active_segment.replace('_', '→')})" if day_structure.high_line_active_segment else ""
        
        html += f'''
<!-- DAY STRUCTURE ZONES -->
<div style="background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-lg);padding:var(--space-4);margin-bottom:var(--space-4);">
    <div style="display:flex;align-items:center;gap:var(--space-2);margin-bottom:var(--space-3);">
        <span style="font-size:16px;">📐</span>
        <span style="font-size:13px;font-weight:600;color:var(--text-primary);">Day Structure</span>
        <span style="font-size:11px;color:{quality_color};margin-left:8px;">{quality_icon} {day_structure.structure_quality}</span>
        {"" if channel_width == 0 else f'<span style="font-size:11px;color:var(--text-muted);margin-left:auto;">Channel: {channel_width:.0f} pts</span>'}
    </div>
    {pivot_info}
    
    <div style="display:flex;justify-content:space-between;align-items:stretch;gap:var(--space-3);margin-top:var(--space-2);">
        <!-- LOW LINE = CALL BUY ZONE -->
        {"" if calls_entry == 0 else f'''
        <div style="flex:1;padding:var(--space-3);background:var(--success-soft);border-radius:var(--radius-sm);border-left:3px solid var(--success);{"opacity:0.5;" if day_structure.low_line_broken else ""}">
            <div style="font-size:10px;color:var(--success);font-weight:600;margin-bottom:4px;">📥 CALL ZONE {low_segment}</div>
            <div style="font-size:20px;font-weight:700;color:var(--text-primary);font-family:var(--font-mono);">{calls_entry:,.0f}</div>
            <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">{day_structure.low_line_direction} {day_structure.low_line_quality}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">CALL @ London: {call_at_low}</div>
            {low_broken_badge}
            <div style="font-size:12px;font-weight:600;color:{"var(--success)" if abs(calls_dist) <= 15 else "var(--text-secondary)"};margin-top:8px;">{calls_dist:+.0f} pts away</div>
        </div>
        '''}
        
        <!-- CURRENT PRICE -->
        <div style="flex:1;padding:var(--space-3);background:var(--bg-elevated);border-radius:var(--radius-sm);text-align:center;">
            <div style="font-size:10px;color:var(--text-muted);margin-bottom:4px;">CURRENT PRICE</div>
            <div style="font-size:24px;font-weight:700;color:var(--text-primary);font-family:var(--font-mono);">{current_price:,.0f}</div>
            <div style="font-size:12px;color:{position_color};font-weight:600;margin-top:8px;">{position_text}</div>
        </div>
        
        <!-- HIGH LINE = PUT BUY ZONE -->
        {"" if puts_entry == 0 else f'''
        <div style="flex:1;padding:var(--space-3);background:var(--danger-soft);border-radius:var(--radius-sm);border-right:3px solid var(--danger);{"opacity:0.5;" if day_structure.high_line_broken else ""}">
            <div style="font-size:10px;color:var(--danger);font-weight:600;margin-bottom:4px;">📥 PUT ZONE {high_segment}</div>
            <div style="font-size:20px;font-weight:700;color:var(--text-primary);font-family:var(--font-mono);">{puts_entry:,.0f}</div>
            <div style="font-size:10px;color:var(--text-muted);margin-top:2px;">{day_structure.high_line_direction} {day_structure.high_line_quality}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:4px;">PUT @ London: {put_at_high}</div>
            {high_broken_badge}
            <div style="font-size:12px;font-weight:600;color:{"var(--success)" if abs(puts_dist) <= 15 else "var(--text-secondary)"};margin-top:8px;">{puts_dist:+.0f} pts away</div>
        </div>
        '''}
    </div>
</div>
'''

    # DAY STRUCTURE SECTION - Simplified to just show the trade setup
    # REMOVED: Complex "Day Structure Details" that showed confusing projections
    # The Day Structure Zones above already shows the key info
    
    # Show FLIP signal prominently if applicable
    if day_structure and day_structure.low_line_broken and day_structure.high_line_valid and day_structure.low_line_valid:
        # Low line broken = FLIP to PUTS
        flip_strike = int(round(day_structure.london_low / 5) * 5) if day_structure.london_low > 0 else int(round(day_structure.low_line_at_entry / 5) * 5)
        # Use London PUT price as reference (most recent known price)
        put_ref_price = day_structure.put_price_london if day_structure.put_price_london > 0 else day_structure.put_price_asia
        
        html += f'''
<!-- FLIP SIGNAL - Low Line Broken -->
<div style="background:linear-gradient(135deg, rgba(234,179,8,0.2) 0%, rgba(234,179,8,0.05) 100%);border:2px solid var(--warning);border-radius:var(--radius-lg);padding:var(--space-4);margin-bottom:var(--space-4);">
    <div style="display:flex;align-items:center;gap:var(--space-2);margin-bottom:var(--space-3);">
        <span style="font-size:20px;">⚡</span>
        <span style="font-size:16px;font-weight:700;color:var(--warning);">FLIP SIGNAL - LOW LINE BROKEN</span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-4);">
        <div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">DIRECTION</div>
            <div style="font-size:24px;font-weight:700;color:var(--danger);">PUTS</div>
        </div>
        <div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">STRIKE</div>
            <div style="font-size:24px;font-weight:700;color:var(--text-primary);font-family:var(--font-mono);">{flip_strike}P</div>
        </div>
        <div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">ENTRY LEVEL</div>
            <div style="font-size:18px;font-weight:600;color:var(--text-primary);font-family:var(--font-mono);">{day_structure.low_line_at_entry:,.0f}</div>
            <div style="font-size:10px;color:var(--text-muted);">Low Line (broken support)</div>
        </div>
        <div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">REFERENCE PRICE</div>
            <div style="font-size:18px;font-weight:600;color:var(--text-primary);font-family:var(--font-mono);">{f"${put_ref_price:.2f}" if put_ref_price > 0 else "—"}</div>
            <div style="font-size:10px;color:var(--text-muted);">@ London High (last known)</div>
        </div>
    </div>
    <div style="margin-top:var(--space-3);padding-top:var(--space-3);border-top:1px solid var(--warning);font-size:12px;color:var(--text-secondary);">
        💡 When CALL returns to entry price → confirms PUT entry
    </div>
</div>
'''
    
    elif day_structure and day_structure.high_line_broken and day_structure.high_line_valid and day_structure.low_line_valid:
        # High line broken = FLIP to CALLS
        flip_strike = int(round(day_structure.london_high / 5) * 5) if day_structure.london_high > 0 else int(round(day_structure.high_line_at_entry / 5) * 5)
        call_ref_price = day_structure.call_price_london if day_structure.call_price_london > 0 else day_structure.call_price_asia
        
        html += f'''
<!-- FLIP SIGNAL - High Line Broken -->
<div style="background:linear-gradient(135deg, rgba(234,179,8,0.2) 0%, rgba(234,179,8,0.05) 100%);border:2px solid var(--warning);border-radius:var(--radius-lg);padding:var(--space-4);margin-bottom:var(--space-4);">
    <div style="display:flex;align-items:center;gap:var(--space-2);margin-bottom:var(--space-3);">
        <span style="font-size:20px;">⚡</span>
        <span style="font-size:16px;font-weight:700;color:var(--warning);">FLIP SIGNAL - HIGH LINE BROKEN</span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-4);">
        <div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">DIRECTION</div>
            <div style="font-size:24px;font-weight:700;color:var(--success);">CALLS</div>
        </div>
        <div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">STRIKE</div>
            <div style="font-size:24px;font-weight:700;color:var(--text-primary);font-family:var(--font-mono);">{flip_strike}C</div>
        </div>
        <div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">ENTRY LEVEL</div>
            <div style="font-size:18px;font-weight:600;color:var(--text-primary);font-family:var(--font-mono);">{day_structure.high_line_at_entry:,.0f}</div>
            <div style="font-size:10px;color:var(--text-muted);">High Line (broken resistance)</div>
        </div>
        <div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;">REFERENCE PRICE</div>
            <div style="font-size:18px;font-weight:600;color:var(--text-primary);font-family:var(--font-mono);">{f"${call_ref_price:.2f}" if call_ref_price > 0 else "—"}</div>
            <div style="font-size:10px;color:var(--text-muted);">@ London Low (last known)</div>
        </div>
    </div>
    <div style="margin-top:var(--space-3);padding-top:var(--space-3);border-top:1px solid var(--warning);font-size:12px;color:var(--text-secondary);">
        💡 When PUT returns to entry price → confirms CALL entry
    </div>
</div>
'''

    # VIX Section
    # Calculate stacked zone boundaries
    zone_width = vix_zone.zone_size
    zone_minus1 = round(vix_zone.bottom - zone_width, 2) if zone_width > 0 else 0
    zone_plus1 = round(vix_zone.top + zone_width, 2) if zone_width > 0 else 0
    
    html += f'''
<!-- VIX METER -->
<div class="vix-section">
    <div class="section-header">
        <div class="section-title">VIX Zone Analysis</div>
        <div style="font-size:12px;color:var(--text-secondary);">Zone Width: {zone_width:.2f} (5pm-3am range)</div>
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
        is_tested = s.status == "TESTED"
        has_ds_confluence = s.cone_name in confluence_cone_names
        
        # De-emphasize setups without confluence when confluence exists
        should_deemphasize = bool(confluence_cone_names) and not has_ds_confluence and not is_broken and not is_tested
        
        # Status class and text
        if is_broken:
            status_class = "broken"
            status_text = "🚫 BROKEN"
            status_style = "broken"
        elif is_tested:
            status_class = "tested"
            status_text = "⚠️ TESTED"
            status_style = "tested"
        elif s.status == "ACTIVE":
            status_class = "active"
            status_text = "📐 BEST" if is_best and has_ds_confluence else "★ BEST" if is_best else "ACTIVE"
            status_style = "best" if is_best else "active"
        elif s.status == "GREY":
            status_class = "grey"
            status_text = "CLOSED"
            status_style = "grey"
        else:
            status_class = ""
            status_text = "📐 BEST" if is_best and has_ds_confluence else "★ BEST" if is_best else "WAIT"
            status_style = "best" if is_best else "wait"
        
        # Styling
        best_style = "border:2px solid var(--warning);box-shadow:0 0 20px rgba(234,179,8,0.3);" if is_best and not is_broken and not is_tested else ""
        confluence_style = "border:2px solid var(--accent);box-shadow:0 0 15px rgba(139,92,246,0.3);" if has_ds_confluence and is_best else ""
        broken_style = "opacity:0.5;border:1px solid var(--danger);" if is_broken else ""
        tested_style = "opacity:0.7;border:1px dashed var(--warning);" if is_tested else ""
        deemph_style = "opacity:0.5;" if should_deemphasize else ""
        
        # Calculate distance from overnight price if available
        if price_proximity and price_proximity.current_price > 0:
            price_to_entry = s.entry - price_proximity.current_price
            distance_display = f"{price_to_entry:+.0f} pts from price"
            distance_color = "var(--success)" if abs(price_to_entry) <= 8 else "var(--text-secondary)"
        else:
            distance_display = f"{s.distance:.0f} pts away"
            distance_color = "var(--text-secondary)"
        
        # Confluence badge
        confluence_badge = ""
        if has_ds_confluence and day_structure and day_structure.low_line_at_entry > 0:
            ds_dist = abs(s.entry - day_structure.low_line_at_entry)
            confluence_badge = f'<div style="background:var(--accent-soft);color:var(--accent);padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600;margin-top:4px;">📐 DS Low @ {day_structure.low_line_at_entry:,.0f} ({ds_dist:.0f} pts)</div>'
        
        html += f'''
            <div class="setup-card calls {status_class}" style="{best_style}{confluence_style}{broken_style}{tested_style}{deemph_style}">
                <div class="setup-header">
                    <div class="setup-name">{"⭐ " if is_best and not is_broken and not is_tested else ""}{s.cone_name}</div>
                    <div class="setup-status {status_style}" style="{'background:var(--danger-soft);color:var(--danger);' if is_broken else 'background:var(--accent-soft);color:var(--accent);' if has_ds_confluence and is_best else 'background:var(--warning-soft);color:var(--warning);' if is_tested or is_best else ''}">{status_text}</div>
                </div>
                <div class="setup-entry">
                    <div class="setup-entry-label">Entry Rail</div>
                    <div class="setup-entry-price calls">{s.entry:,.2f}</div>
                    <div class="setup-entry-distance" style="color:{distance_color};">{distance_display}</div>
                    {confluence_badge}
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
        is_tested = s.status == "TESTED"
        has_ds_confluence = s.cone_name in confluence_cone_names
        
        # De-emphasize setups without confluence when confluence exists
        should_deemphasize = bool(confluence_cone_names) and not has_ds_confluence and not is_broken and not is_tested
        
        # Status class and text
        if is_broken:
            status_class = "broken"
            status_text = "🚫 BROKEN"
            status_style = "broken"
        elif is_tested:
            status_class = "tested"
            status_text = "⚠️ TESTED"
            status_style = "tested"
        elif s.status == "ACTIVE":
            status_class = "active puts"
            status_text = "📐 BEST" if is_best and has_ds_confluence else "★ BEST" if is_best else "ACTIVE"
            status_style = "best" if is_best else "active"
        elif s.status == "GREY":
            status_class = "grey"
            status_text = "CLOSED"
            status_style = "grey"
        else:
            status_class = ""
            status_text = "📐 BEST" if is_best and has_ds_confluence else "★ BEST" if is_best else "WAIT"
            status_style = "best" if is_best else "wait"
        
        # Styling
        best_style = "border:2px solid var(--warning);box-shadow:0 0 20px rgba(234,179,8,0.3);" if is_best and not is_broken and not is_tested else ""
        confluence_style = "border:2px solid var(--accent);box-shadow:0 0 15px rgba(139,92,246,0.3);" if has_ds_confluence and is_best else ""
        broken_style = "opacity:0.5;border:1px solid var(--danger);" if is_broken else ""
        tested_style = "opacity:0.7;border:1px dashed var(--warning);" if is_tested else ""
        deemph_style = "opacity:0.5;" if should_deemphasize else ""
        
        # Calculate distance from overnight price if available
        if price_proximity and price_proximity.current_price > 0:
            price_to_entry = s.entry - price_proximity.current_price
            distance_display = f"{price_to_entry:+.0f} pts from price"
            distance_color = "var(--success)" if abs(price_to_entry) <= 8 else "var(--text-secondary)"
        else:
            distance_display = f"{s.distance:.0f} pts away"
            distance_color = "var(--text-secondary)"
        
        # Confluence badge
        confluence_badge = ""
        if has_ds_confluence and day_structure and day_structure.high_line_at_entry > 0:
            ds_dist = abs(s.entry - day_structure.high_line_at_entry)
            confluence_badge = f'<div style="background:var(--accent-soft);color:var(--accent);padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600;margin-top:4px;">📐 DS High @ {day_structure.high_line_at_entry:,.0f} ({ds_dist:.0f} pts)</div>'
        
        html += f'''
            <div class="setup-card puts {status_class}" style="{best_style}{confluence_style}{broken_style}{tested_style}{deemph_style}">
                <div class="setup-header">
                    <div class="setup-name">{"⭐ " if is_best and not is_broken and not is_tested else ""}{s.cone_name}</div>
                    <div class="setup-status {status_style}" style="{'background:var(--danger-soft);color:var(--danger);' if is_broken else 'background:var(--accent-soft);color:var(--accent);' if has_ds_confluence and is_best else 'background:var(--warning-soft);color:var(--warning);' if is_tested or is_best else ''}">{status_text}</div>
                </div>
                <div class="setup-entry">
                    <div class="setup-entry-label">Entry Rail</div>
                    <div class="setup-entry-price puts">{s.entry:,.2f}</div>
                    <div class="setup-entry-distance" style="color:{distance_color};">{distance_display}</div>
                    {confluence_badge}
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
        <span class="collapse-icon">▼</span>
    </div>
    <div class="table-content" style="padding:var(--space-4);display:grid;grid-template-columns:repeat(4,1fr);gap:var(--space-3);">
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
        <span class="collapse-icon">▼</span>
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
        <span class="collapse-icon">▼</span>
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

    # ════════════════════════════════════════════════════════════════════════
    # TRADING RULES REFERENCE - Collapsible Section
    # ════════════════════════════════════════════════════════════════════════
    html += '''
<!-- TRADING RULES -->
<div class="table-section collapsed" style="margin-top:var(--space-4);">
    <div class="table-header" style="cursor:pointer;">
        <span>📖 Trading Rules Reference</span>
        <span class="collapse-icon">▼</span>
    </div>
    <div class="table-content" style="padding:var(--space-4);font-size:13px;line-height:1.6;">
        
        <div style="margin-bottom:var(--space-4);">
            <h3 style="color:var(--accent);margin-bottom:var(--space-2);font-size:15px;">PART 1: MARKET ENVIRONMENT</h3>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 1.1:</strong> Determine market bias using 50 EMA vs 200 SMA on SPX 24-hour chart.</p>
            <ul style="color:var(--text-secondary);margin-left:var(--space-4);margin-bottom:var(--space-2);">
                <li><span style="color:var(--success);">BULLISH:</span> 50 EMA > 200 SMA, Price > 50 EMA → CALLS only</li>
                <li><span style="color:var(--danger);">BEARISH:</span> 50 EMA < 200 SMA, Price < 50 EMA → PUTS only</li>
                <li><span style="color:var(--warning);">TRANSITIONAL:</span> Mixed signals → Trade with caution</li>
            </ul>
            <p style="color:var(--text-secondary);"><strong style="color:var(--text-primary);">Rule 1.2:</strong> <span style="color:var(--danger);">NEVER</span> trade against the trend. No PUTS in bullish, no CALLS in bearish.</p>
        </div>
        
        <div style="margin-bottom:var(--space-4);">
            <h3 style="color:var(--accent);margin-bottom:var(--space-2);font-size:15px;">PART 2: VIX ZONE</h3>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 2.1:</strong> Track VIX from 5pm-8:30am CT to establish overnight zone.</p>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 2.2:</strong> Expected zone = 1% of VIX, rounded to 0.05.</p>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 2.3:</strong> VIX position determines direction:</p>
            <ul style="color:var(--text-secondary);margin-left:var(--space-4);margin-bottom:var(--space-2);">
                <li>At/Below Bottom → <span style="color:var(--success);">CALLS</span></li>
                <li>At/Above Top → <span style="color:var(--danger);">PUTS</span></li>
                <li>Mid-Zone → WAIT (defer to MA bias)</li>
            </ul>
            <p style="color:var(--text-secondary);"><strong style="color:var(--text-primary);">Rule 2.4:</strong> VIX + MA must align. Conflict = <span style="color:var(--danger);">NO TRADE</span>.</p>
        </div>
        
        <div style="margin-bottom:var(--space-4);">
            <h3 style="color:var(--accent);margin-bottom:var(--space-2);font-size:15px;">PART 3: DAY STRUCTURE</h3>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 3.1:</strong> Build Day Structure from 5pm-6:30am CT (Asia High/Low → London High/Low). Cutoff before US economic releases.</p>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 3.2:</strong> <span style="color:var(--warning);">BOTH</span> lines required for proper strike calculation.</p>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 3.3:</strong> Low Line = CALL buy zone (cheapest). High Line = PUT buy zone (cheapest).</p>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 3.4:</strong> Break & Retest:</p>
            <ul style="color:var(--text-secondary);margin-left:var(--space-4);">
                <li>Below structure at open → Wait for GREEN candle to touch Low Line (not break above) → Enter PUTS</li>
                <li>Above structure at open → Wait for RED candle to touch High Line (not break below) → Enter CALLS</li>
            </ul>
        </div>
        
        <div style="margin-bottom:var(--space-4);">
            <h3 style="color:var(--accent);margin-bottom:var(--space-2);font-size:15px;">PART 4: CONTRACT SELECTION</h3>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 4.1:</strong> Strike = Target - 20 (20 pts ITM at exit zone).</p>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 4.2:</strong> Contract projection requires 2 price points (Asia + London).</p>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 4.3:</strong> Round Number Magnet Rule:</p>
            <ul style="color:var(--text-secondary);margin-left:var(--space-4);">
                <li><span style="color:var(--danger);">PUTS:</span> 8:30 drop below round # (6850, 6800) → Watch that PUT contract rally → Enter at 0.786 Fib retracement of contract price rally</li>
                <li><span style="color:var(--success);">CALLS:</span> 8:30 rally above round # (6900, 7000) → Watch that CALL contract rally → Enter at 0.786 Fib retracement of contract price rally</li>
            </ul>
        </div>
        
        <div style="margin-bottom:var(--space-4);">
            <h3 style="color:var(--accent);margin-bottom:var(--space-2);font-size:15px;">PART 5: RISK MANAGEMENT</h3>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 5.1:</strong> Dynamic stop based on VIX: <14 = 4pts | 14-20 = 6pts | 20-25 = 8pts | >25 = 10pts</p>
            <p style="color:var(--text-secondary);margin-bottom:var(--space-2);"><strong style="color:var(--text-primary);">Rule 5.2:</strong> Entry window: <span style="color:var(--success);">9-10am optimal</span> | 10-10:30am good | 10:30-11:30am late | After 11:30am avoid</p>
            <p style="color:var(--text-secondary);"><strong style="color:var(--text-primary);">Rule 5.3:</strong> Structure break = Flip signal. Watch contract return to entry price → Enter opposite direction.</p>
        </div>
        
        <div>
            <h3 style="color:var(--accent);margin-bottom:var(--space-2);font-size:15px;">PART 6: NO TRADE CONDITIONS</h3>
            <ul style="color:var(--danger);margin-left:var(--space-4);">
                <li>VIX and MA bias in CONFLICT</li>
                <li>PUTS in bullish environment / CALLS in bearish environment</li>
                <li>Only one Day Structure line defined</li>
                <li>After 11:30am CT cutoff</li>
                <li>Holiday or half-day</li>
            </ul>
        </div>
        
    </div>
</div>
'''
    
    # Footer
    html += f'''
<!-- FOOTER -->
<footer class="footer">
    <div class="footer-brand">SPX Prophet v9.0</div>
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
    defaults = {
        'theme': 'dark', 
        'vix_bottom': 0.0, 'vix_top': 0.0, 'vix_current': 0.0, 
        'entry_time_mins': 30, 
        'use_manual_pivots': False, 
        'high_price': 0.0, 'high_time': "10:30", 
        'low_price': 0.0, 'low_time': "14:00", 
        'close_price': 0.0, 
        'trading_date': None, 
        'last_refresh': None,
        'overnight_spx': 0.0,  # Current SPX/ES price for proximity analysis
        # Day Structure - 3 Session pivots for trendlines (Sydney → Tokyo → London)
        # Session times (CT): Sydney 4pm-6pm, Tokyo 6pm-2am, London 2am-6:30am
        'sydney_high': 0.0, 'sydney_high_time': "17:00",
        'sydney_low': 0.0, 'sydney_low_time': "17:30",
        'tokyo_high': 0.0, 'tokyo_high_time': "21:00", 
        'tokyo_low': 0.0, 'tokyo_low_time': "23:00",
        'london_high': 0.0, 'london_high_time': "05:00", 
        'london_low': 0.0, 'london_low_time': "06:00",
        # Contract Prices - PUT (tracks high line)
        'put_price_sydney': 0.0,
        'put_price_tokyo': 0.0,
        'put_price_london': 0.0,
        # Contract Prices - CALL (tracks low line)
        'call_price_sydney': 0.0,
        'call_price_tokyo': 0.0,
        'call_price_london': 0.0,
        # Structure broken flags
        'high_line_broken': False,
        'low_line_broken': False
    }
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
                st.rerun()
        with col2:
            if st.button("📆 Prior", use_container_width=True):
                st.session_state.trading_date = get_prior_trading_day(today)
                st.rerun()
        
        # Use a unique key and only set default value if not already set
        default_date = st.session_state.trading_date if st.session_state.trading_date else next_trade
        selected_date = st.date_input(
            "Select", 
            value=default_date, 
            min_value=today - timedelta(days=730), 
            max_value=today + timedelta(days=400),
            key="date_picker"
        )
        # Only update session state if user actually selected a different date
        if selected_date != st.session_state.trading_date:
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
        st.caption("5pm-3am overnight range = Zone 0")
        
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
                    vix_val, src = fetch_vix_current()
                    if vix_val > 0:
                        st.session_state.vix_current = vix_val
                        st.info(f"Current VIX: {vix_val:.2f} ({src})")
                    else:
                        st.error("Could not fetch VIX data")
        
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.vix_bottom = st.number_input("Bottom (5pm-3am Low)", value=st.session_state.vix_bottom, step=0.05, format="%.2f")
        with col2:
            st.session_state.vix_top = st.number_input("Top (5pm-3am High)", value=st.session_state.vix_top, step=0.05, format="%.2f")
        st.session_state.vix_current = st.number_input("Current VIX", value=st.session_state.vix_current, step=0.05, format="%.2f")
        
        # VIX Zone Info with stacking explanation
        if st.session_state.vix_bottom > 0 and st.session_state.vix_top > 0:
            actual_zone = st.session_state.vix_top - st.session_state.vix_bottom
            zone_width = actual_zone
            zone_ticks = int(round(actual_zone / 0.05))
            
            # Show zone width and stacked zones
            st.caption(f"**Zone Width: {actual_zone:.2f}** ({zone_ticks} ticks)")
            
            # Show stacked zones
            z_bottom = st.session_state.vix_bottom
            z_top = st.session_state.vix_top
            zone_minus1_bottom = round(z_bottom - zone_width, 2)
            zone_plus1_top = round(z_top + zone_width, 2)
            
            with st.expander("📊 Zone Stack", expanded=False):
                st.markdown(f"""
**Zone +1**: {z_top:.2f} - {zone_plus1_top:.2f} *(PUTS territory)*  
**Zone 0**: {z_bottom:.2f} - {z_top:.2f} *(Overnight range)*  
**Zone -1**: {zone_minus1_bottom:.2f} - {z_bottom:.2f} *(CALLS territory)*

*Width: ±{zone_width:.2f} per zone*
                """)
            
            # Current position info
            if st.session_state.vix_current > 0:
                vix_curr = st.session_state.vix_current
                if vix_curr < z_bottom:
                    zones_away = -int(np.ceil((z_bottom - vix_curr) / zone_width)) if zone_width > 0 else -1
                    st.info(f"VIX {vix_curr:.2f} → **{zones_away} zones** (CALLS)")
                elif vix_curr > z_top:
                    zones_away = int(np.ceil((vix_curr - z_top) / zone_width)) if zone_width > 0 else 1
                    st.warning(f"VIX {vix_curr:.2f} → **+{zones_away} zones** (PUTS)")
                else:
                    pct = ((vix_curr - z_bottom) / zone_width * 100) if zone_width > 0 else 50
                    st.success(f"VIX {vix_curr:.2f} → **{pct:.0f}%** in Zone 0")
        
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
        
        # STRUCTURE BROKEN CHECKBOXES - Direction-specific (Prior session only)
        broken_keys = [
            "broken_prior_high_calls", "broken_prior_high_puts",
            "broken_prior_low_calls", "broken_prior_low_puts", 
            "broken_prior_close_calls", "broken_prior_close_puts"
        ]
        for key in broken_keys:
            if key not in st.session_state:
                st.session_state[key] = False
        
        st.caption("🚫 Mark broken (30-min close through rail):")
        st.caption("↓ = Descending (CALLS) | ↑ = Ascending (PUTS)")
        
        # Prior High
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown("<small style='color:#888;'>Prior High</small>", unsafe_allow_html=True)
        with col2:
            st.session_state.broken_prior_high_calls = st.checkbox("↓", value=st.session_state.broken_prior_high_calls, key="chk_ph_c", help="CALLS entry broken")
        with col3:
            st.session_state.broken_prior_high_puts = st.checkbox("↑", value=st.session_state.broken_prior_high_puts, key="chk_ph_p", help="PUTS entry broken")
        
        # Prior Low
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown("<small style='color:#888;'>Prior Low</small>", unsafe_allow_html=True)
        with col2:
            st.session_state.broken_prior_low_calls = st.checkbox("↓", value=st.session_state.broken_prior_low_calls, key="chk_pl_c", help="CALLS entry broken")
        with col3:
            st.session_state.broken_prior_low_puts = st.checkbox("↑", value=st.session_state.broken_prior_low_puts, key="chk_pl_p", help="PUTS entry broken")
        
        # Prior Close
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown("<small style='color:#888;'>Prior Close</small>", unsafe_allow_html=True)
        with col2:
            st.session_state.broken_prior_close_calls = st.checkbox("↓", value=st.session_state.broken_prior_close_calls, key="chk_pc_c", help="CALLS entry broken")
        with col3:
            st.session_state.broken_prior_close_puts = st.checkbox("↑", value=st.session_state.broken_prior_close_puts, key="chk_pc_p", help="PUTS entry broken")
        
        st.divider()
        
        # ECONOMIC CALENDAR
        st.markdown("### 📅 Economic Calendar")
        
        # Get today's events
        trading_date = st.session_state.get("trading_date", date.today())
        if isinstance(trading_date, str):
            trading_date = datetime.strptime(trading_date, "%Y-%m-%d").date()
        
        econ_events = get_economic_events(trading_date)
        event_warning, should_warn, warning_level = get_event_warning(econ_events)
        
        if econ_events:
            for event_name, event_time, impact in econ_events:
                if impact == "HIGH":
                    st.error(f"**{event_name}**  \n⏰ {event_time} CT")
                elif impact == "MEDIUM":
                    st.warning(f"**{event_name}**  \n⏰ {event_time} CT")
                else:
                    st.info(f"**{event_name}**  \n⏰ {event_time} CT")
        else:
            st.success("✅ No major events today")
        
        # Manual event override
        if "manual_event" not in st.session_state:
            st.session_state.manual_event = ""
        if "manual_event_time" not in st.session_state:
            st.session_state.manual_event_time = ""
        
        with st.expander("➕ Add Custom Event", expanded=False):
            st.session_state.manual_event = st.text_input("Event Name", value=st.session_state.manual_event, placeholder="e.g., Fed Chair Speech")
            st.session_state.manual_event_time = st.text_input("Time (CT)", value=st.session_state.manual_event_time, placeholder="e.g., 10:00")
            if st.session_state.manual_event:
                st.warning(f"📌 {st.session_state.manual_event} @ {st.session_state.manual_event_time or 'TBD'}")
        
        st.divider()
        st.markdown("### ⏰ Entry Time")
        st.caption("Target entry time for projections")
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
        
        # DAY STRUCTURE - 3 Session Trendlines
        st.markdown("### 📐 Day Structure")
        st.caption("3-Session trendlines (Sydney → Tokyo → London)")
        
        with st.expander("HIGH LINE (PUTS)", expanded=False):
            st.markdown("**Sydney High** (4pm-6pm CT)")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.sydney_high = st.number_input("SPX", value=st.session_state.sydney_high, step=0.01, format="%.2f", key="syd_h")
            with c2:
                st.session_state.sydney_high_time = st.text_input("Time", value=st.session_state.sydney_high_time, key="syd_ht", help="CT, e.g. 17:00")
            
            st.markdown("**Tokyo High** (6pm-2am CT)")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.tokyo_high = st.number_input("SPX", value=st.session_state.tokyo_high, step=0.01, format="%.2f", key="tok_h")
            with c2:
                st.session_state.tokyo_high_time = st.text_input("Time", value=st.session_state.tokyo_high_time, key="tok_ht", help="CT, e.g. 21:00")
            
            st.markdown("**London High** (2am-6:30am CT)")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.london_high = st.number_input("SPX", value=st.session_state.london_high, step=0.01, format="%.2f", key="lon_h")
            with c2:
                st.session_state.london_high_time = st.text_input("Time", value=st.session_state.london_high_time, key="lon_ht")
            
            st.markdown("**PUT Contract Prices** (10 OTM)")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.session_state.put_price_sydney = st.number_input("@ Syd", value=st.session_state.put_price_sydney, step=0.10, format="%.2f", key="put_syd")
            with c2:
                st.session_state.put_price_tokyo = st.number_input("@ Tok", value=st.session_state.put_price_tokyo, step=0.10, format="%.2f", key="put_tok")
            with c3:
                st.session_state.put_price_london = st.number_input("@ Lon", value=st.session_state.put_price_london, step=0.10, format="%.2f", key="put_lon")
            
            # High line broken checkbox
            st.session_state.high_line_broken = st.checkbox("⚡ High line BROKEN (SPX broke above)", value=st.session_state.get("high_line_broken", False), key="high_broken")
        
        with st.expander("LOW LINE (CALLS)", expanded=False):
            st.markdown("**Sydney Low** (4pm-6pm CT)")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.sydney_low = st.number_input("SPX", value=st.session_state.sydney_low, step=0.01, format="%.2f", key="syd_l")
            with c2:
                st.session_state.sydney_low_time = st.text_input("Time", value=st.session_state.sydney_low_time, key="syd_lt", help="CT, e.g. 17:30")
            
            st.markdown("**Tokyo Low** (6pm-2am CT)")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.tokyo_low = st.number_input("SPX", value=st.session_state.tokyo_low, step=0.01, format="%.2f", key="tok_l")
            with c2:
                st.session_state.tokyo_low_time = st.text_input("Time", value=st.session_state.tokyo_low_time, key="tok_lt", help="CT, e.g. 23:00")
            
            st.markdown("**London Low** (2am-6:30am CT)")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.session_state.london_low = st.number_input("SPX", value=st.session_state.london_low, step=0.01, format="%.2f", key="lon_l")
            with c2:
                st.session_state.london_low_time = st.text_input("Time", value=st.session_state.london_low_time, key="lon_lt")
            
            st.markdown("**CALL Contract Prices** (10 OTM)")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.session_state.call_price_sydney = st.number_input("@ Syd", value=st.session_state.call_price_sydney, step=0.10, format="%.2f", key="call_syd")
            with c2:
                st.session_state.call_price_tokyo = st.number_input("@ Tok", value=st.session_state.call_price_tokyo, step=0.10, format="%.2f", key="call_tok")
            with c3:
                st.session_state.call_price_london = st.number_input("@ Lon", value=st.session_state.call_price_london, step=0.10, format="%.2f", key="call_lon")
            
            # Low line broken checkbox
            st.session_state.low_line_broken = st.checkbox("⚡ Low line BROKEN (SPX broke below)", value=st.session_state.get("low_line_broken", False), key="low_broken")
        
        # Show day structure status
        has_high_line = st.session_state.tokyo_high > 0 and st.session_state.london_high > 0
        has_low_line = st.session_state.tokyo_low > 0 and st.session_state.london_low > 0
        has_sydney_high = st.session_state.sydney_high > 0
        has_sydney_low = st.session_state.sydney_low > 0
        
        if has_high_line or has_low_line:
            status_parts = []
            if has_sydney_high and has_high_line:
                status_parts.append("High 3pt ✓")
            elif has_high_line:
                status_parts.append("High 2pt")
            if has_sydney_low and has_low_line:
                status_parts.append("Low 3pt ✓")
            elif has_low_line:
                status_parts.append("Low 2pt")
            st.success(f"📐 {' | '.join(status_parts)}")
            
            if st.session_state.high_line_broken:
                st.warning("⚡ HIGH LINE BROKEN → FLIP to CALLS")
            if st.session_state.low_line_broken:
                st.warning("⚡ LOW LINE BROKEN → FLIP to PUTS")
        
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
    
    # BUILD CONES from prior session pivots
    eval_time = CT_TZ.localize(datetime.combine(trading_date, time(9, 0)))
    prior_cones = build_cones(pivots, eval_time)
    
    # DETERMINE STRUCTURE BOUNDARIES from prior session cones
    tradeable_prior = [c for c in prior_cones if c.is_tradeable]
    if tradeable_prior:
        highest_ascending = max(c.ascending_rail for c in tradeable_prior)
        lowest_descending = min(c.descending_rail for c in tradeable_prior)
    else:
        highest_ascending = 0
        lowest_descending = float('inf')
    
    # Use prior_cones as final cones (no overnight pivots added)
    cones = prior_cones
    
    # DETECT TESTED RAILS using Day Structure
    # If day structure low went below descending rails = CALLS tested
    # If day structure high went above ascending rails = PUTS tested
    tested_structures = {}
    
    # Get day structure session lows/highs for tested detection
    # Use the LOWER of Asia Low and London Low as the session low test level
    asia_low = st.session_state.get("asia_low", 0.0)
    london_low = st.session_state.get("london_low", 0.0)
    asia_high = st.session_state.get("asia_high", 0.0)
    london_high = st.session_state.get("london_high", 0.0)
    
    # Session low = lowest point in Asia or London (tests descending rails)
    # Session high = highest point in Asia or London (tests ascending rails)
    session_low = min(asia_low, london_low) if asia_low > 0 and london_low > 0 else max(asia_low, london_low)
    session_high = max(asia_high, london_high) if asia_high > 0 and london_high > 0 else max(asia_high, london_high)
    
    if session_low > 0 and tradeable_prior:
        # Check which descending rails the session low breached (affects CALLS)
        for cone in tradeable_prior:
            if session_low < cone.descending_rail:
                if cone.name not in tested_structures:
                    tested_structures[cone.name] = {}
                tested_structures[cone.name]["CALLS"] = "TESTED"
    
    if session_high > 0 and tradeable_prior:
        # Check which ascending rails the session high breached (affects PUTS)
        for cone in tradeable_prior:
            if session_high > cone.ascending_rail:
                if cone.name not in tested_structures:
                    tested_structures[cone.name] = {}
                tested_structures[cone.name]["PUTS"] = "TESTED"
    
    # Debug: Show tested structures
    if tested_structures:
        with st.sidebar:
            tested_msgs = []
            for cone_name, directions in tested_structures.items():
                dirs = [d for d in directions.keys()]
                tested_msgs.append(f"{cone_name} ({'/'.join(dirs)})")
            st.warning(f"⚠️ Tested: {', '.join(tested_msgs)}")
    
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
    
    # Calculate Market Context
    market_ctx = analyze_market_context(prior_session, st.session_state.vix_current, now.time())
    
    # Calculate Confluence (VIX + MA)
    confluence = calculate_confluence(vix_zone, ma_bias)
    
    # Debug: Show confluence in sidebar
    with st.sidebar:
        if ma_bias.sma200 > 0:
            st.caption(f"📊 MA: {ma_bias.bias} | SMA: {ma_bias.sma200:.0f}")
        if confluence:
            conf_emoji = "✅" if confluence.is_aligned else "⚠️" if confluence.signal_strength == "CONFLICT" else "◐"
            st.caption(f"{conf_emoji} Confluence: {confluence.signal_strength}")
        if price_proximity and price_proximity.position != "UNKNOWN":
            st.caption(f"📍 {price_proximity.position_detail}")
    
    # Pass VIX and entry time for accurate option pricing
    vix_for_pricing = st.session_state.vix_current if st.session_state.vix_current > 0 else 16
    mins_after_open = st.session_state.entry_time_mins
    
    # Use overnight price for setup status if provided, otherwise use SPX from Polygon
    price_for_setups = overnight_price if overnight_price > 0 else spx_price
    
    # Get broken structure states (manually marked) - direction-specific
    broken_structures = {
        "Prior High": {
            "CALLS": st.session_state.get("broken_prior_high_calls", False),
            "PUTS": st.session_state.get("broken_prior_high_puts", False)
        },
        "Prior Low": {
            "CALLS": st.session_state.get("broken_prior_low_calls", False),
            "PUTS": st.session_state.get("broken_prior_low_puts", False)
        },
        "Prior Close": {
            "CALLS": st.session_state.get("broken_prior_close_calls", False),
            "PUTS": st.session_state.get("broken_prior_close_puts", False)
        }
    }
    
    setups = generate_setups(cones, price_for_setups, vix_for_pricing, mins_after_open, is_after_cutoff, broken_structures, tested_structures)
    
    # Calculate Day Structure (3-session trendlines + contract pricing)
    day_structure = calculate_day_structure(
        st.session_state.get("sydney_high", 0.0),
        st.session_state.get("sydney_high_time", "17:00"),
        st.session_state.get("sydney_low", 0.0),
        st.session_state.get("sydney_low_time", "17:30"),
        st.session_state.get("tokyo_high", 0.0),
        st.session_state.get("tokyo_high_time", "21:00"),
        st.session_state.get("tokyo_low", 0.0),
        st.session_state.get("tokyo_low_time", "23:00"),
        st.session_state.get("london_high", 0.0),
        st.session_state.get("london_high_time", "05:00"),
        st.session_state.get("london_low", 0.0),
        st.session_state.get("london_low_time", "06:00"),
        mins_after_open,
        cones,
        trading_date,
        put_price_sydney=st.session_state.get("put_price_sydney", 0.0),
        put_price_tokyo=st.session_state.get("put_price_tokyo", 0.0),
        put_price_london=st.session_state.get("put_price_london", 0.0),
        call_price_sydney=st.session_state.get("call_price_sydney", 0.0),
        call_price_tokyo=st.session_state.get("call_price_tokyo", 0.0),
        call_price_london=st.session_state.get("call_price_london", 0.0),
        high_line_broken=st.session_state.get("high_line_broken", False),
        low_line_broken=st.session_state.get("low_line_broken", False)
    )
    
    # ═══════════════════════════════════════════════════════════════════════
    # ADD DAY STRUCTURE SETUPS (4th setup in each direction)
    # ═══════════════════════════════════════════════════════════════════════
    dynamic_stop = market_ctx.recommended_stop if market_ctx else STOP_LOSS_PTS
    ds_setups = generate_day_structure_setups(
        day_structure, 
        price_for_setups, 
        vix_for_pricing, 
        mins_after_open, 
        is_after_cutoff,
        dynamic_stop
    )
    setups.extend(ds_setups)  # Add DS setups to the main setups list
    
    # Debug: Show day structure info in sidebar
    if day_structure.has_confluence:
        with st.sidebar:
            st.success(f"📐 {day_structure.best_confluence_detail}")
    if day_structure.put_price_at_entry > 0:
        with st.sidebar:
            st.caption(f"PUT: ${day_structure.put_price_at_entry:.2f} @ {day_structure.put_strike}P")
    if day_structure.call_price_at_entry > 0:
        with st.sidebar:
            st.caption(f"CALL: ${day_structure.call_price_at_entry:.2f} @ {day_structure.call_strike}C")
    
    # Updated scoring with confluence
    day_score = calculate_day_score(vix_zone, cones, setups, confluence, market_ctx)
    pivot_table = build_pivot_table(pivots, trading_date)
    alerts = check_alerts(setups, vix_zone, now.time()) if not is_historical else []
    html = render_dashboard(vix_zone, cones, setups, pivot_table, prior_session, day_score, alerts, spx_price, trading_date, pivot_date, pivot_session_info, is_historical, st.session_state.theme, ma_bias, confluence, market_ctx, price_proximity, day_structure)
    components.html(html, height=4500, scrolling=True)

if __name__ == "__main__":
    main()
