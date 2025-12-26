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

def estimate_0dte_price(vix, otm_distance, hours_left, is_put=False):
    """
    Estimate SPX 0DTE option price.
    Calibrated to real trade data. MAE: ~$0.62
    
    Args:
        vix: Current VIX level (use 16 as default if not set)
        otm_distance: Points OTM
        hours_left: Hours until 3pm CT (6.5 at 8:30 AM, 6 at 9:00 AM)
        is_put: True for puts
    
    Returns: Estimated premium per contract
    """
    if vix <= 0:
        vix = 16  # Default assumption
    
    base = 7.50
    
    # VIX adjustment (steeper above 18)
    if vix <= 15:
        vix_adj = 0
    elif vix <= 18:
        vix_adj = (vix - 15) * 0.35
    else:
        vix_adj = 1.05 + (vix - 18) * 0.60
    
    # OTM adjustment (reduced penalty at high VIX)
    otm_penalty = 0.10 * max(0.4, 1 - (vix - 15) * 0.04)
    otm_adj = -otm_penalty * max(0, otm_distance - 15)
    
    # Put skew (only at high VIX - fear premium)
    if is_put and vix >= 19:
        skew = 1.20 + (vix - 19) * 0.10
    else:
        skew = 1.0
    
    # Time decay (severe for 0DTE)
    if hours_left >= 6:
        time_factor = 1.0
    elif hours_left >= 5:
        time_factor = 0.30 + 0.70 * (hours_left - 5)
    elif hours_left >= 4:
        time_factor = 0.15 + 0.15 * (hours_left - 4)
    else:
        time_factor = max(0.05, 0.15 * hours_left / 4)
    
    price = (base + vix_adj + otm_adj) * time_factor * skew
    return max(0.50, round(price, 2))

def get_option_data_for_entry(entry_rail, opt_type, vix_current=16, eval_time=None):
    """Get option data for SPX contracts ~15 pts OTM from entry rail"""
    is_put = opt_type.upper() in ["P", "PUT", "PUTS"]
    
    if is_put:
        spx_strike = int(round((entry_rail - OTM_DISTANCE_PTS) / 5) * 5)
    else:
        spx_strike = int(round((entry_rail + OTM_DISTANCE_PTS) / 5) * 5)
    
    otm_distance = abs(spx_strike - entry_rail)
    
    # Calculate hours left (default to 6 hours = 9:00 AM entry)
    if eval_time:
        hours_left = 15 - (eval_time.hour + eval_time.minute / 60)
    else:
        hours_left = 6.0  # Default to 9:00 AM
    
    hours_left = max(0.5, hours_left)
    
    # Use calibrated pricing model
    spx_price = estimate_0dte_price(vix_current, otm_distance, hours_left, is_put)
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
    cones = []
    for pivot in pivots:
        if pivot.price <= 0 or pivot.pivot_time is None:
            continue
        blocks = count_blocks(pivot.pivot_time + timedelta(minutes=30), eval_time)
        expansion = blocks * SLOPE_PER_30MIN
        if pivot.pivot_type == "HIGH":
            base = pivot.candle_high if pivot.candle_high > 0 else pivot.price
            ascending, descending = base + expansion, pivot.price - expansion
        elif pivot.pivot_type == "LOW":
            base = pivot.candle_open if pivot.candle_open > 0 else pivot.price
            ascending, descending = pivot.price + expansion, base - expansion
        else:
            ascending, descending = pivot.price + expansion, pivot.price - expansion
        width = ascending - descending
        cones.append(Cone(name=pivot.name, pivot=pivot, ascending_rail=round(ascending, 2), descending_rail=round(descending, 2), width=round(width, 2), blocks=blocks, is_tradeable=(width >= MIN_CONE_WIDTH)))
    return cones

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
                    base = piv.candle_high if piv.candle_high > 0 else piv.price
                    setattr(row, attr_asc, round(base + exp, 2))
                    setattr(row, attr_desc, round(piv.price - exp, 2))
                elif piv.pivot_type == "LOW":
                    base = piv.candle_open if piv.candle_open > 0 else piv.price
                    setattr(row, attr_asc, round(piv.price + exp, 2))
                    setattr(row, attr_desc, round(base - exp, 2))
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
        zone.zones_away = -int(np.ceil((vix_bottom - vix_current) / zone.zone_size)) if zone.zone_size > 0 else 0
        zone.position_pct = 0
        zone.bias = "CALLS"
        zone.bias_reason = f"VIX {abs(zone.zones_away)} zone(s) below → SPX UP"
    elif vix_current > vix_top:
        zone.zones_away = int(np.ceil((vix_current - vix_top) / zone.zone_size)) if zone.zone_size > 0 else 0
        zone.position_pct = 100
        zone.bias = "PUTS"
        zone.bias_reason = f"VIX {zone.zones_away} zone(s) above → SPX DOWN"
    else:
        zone.zones_away = 0
        zone.position_pct = ((vix_current - vix_bottom) / zone.zone_size * 100) if zone.zone_size > 0 else 50
        if zone.position_pct >= 75:
            zone.bias, zone.bias_reason = "CALLS", f"VIX at {zone.position_pct:.0f}% (top) → SPX UP"
        elif zone.position_pct <= 25:
            zone.bias, zone.bias_reason = "PUTS", f"VIX at {zone.position_pct:.0f}% (bottom) → SPX DOWN"
        else:
            zone.bias, zone.bias_reason = "WAIT", f"VIX at {zone.position_pct:.0f}% (mid-zone)"
    if cones and zone.bias in ["CALLS", "PUTS"]:
        rails = [(c.descending_rail if zone.bias == "CALLS" else c.ascending_rail, c.name) for c in cones if c.is_tradeable]
        if rails:
            rails.sort(key=lambda x: x[0])
            zone.matched_rail, zone.matched_cone = rails[len(rails)//2]
    return zone

def generate_setups(cones, current_price, vix_current=16, eval_time=None, is_after_cutoff=False):
    """Generate trade setups with calibrated option pricing"""
    setups = []
    for cone in cones:
        if not cone.is_tradeable:
            continue
        # CALLS - enter at descending rail
        entry_c = cone.descending_rail
        dist_c = abs(current_price - entry_c)
        opt_c = get_option_data_for_entry(entry_c, "C", vix_current, eval_time)
        delta_c = abs(opt_c.spy_delta) if opt_c else DELTA_IDEAL
        setups.append(TradeSetup(
            direction="CALLS", cone_name=cone.name, cone_width=cone.width, entry=entry_c,
            stop=round(entry_c - STOP_LOSS_PTS, 2),
            target_25=round(entry_c + cone.width * 0.25, 2), target_50=round(entry_c + cone.width * 0.50, 2),
            target_75=round(entry_c + cone.width * 0.75, 2), target_100=round(entry_c + cone.width, 2),
            distance=round(dist_c, 1), option=opt_c,
            profit_25=round(cone.width * 0.25 * delta_c * 100, 0), profit_50=round(cone.width * 0.50 * delta_c * 100, 0),
            profit_75=round(cone.width * 0.75 * delta_c * 100, 0), profit_100=round(cone.width * delta_c * 100, 0),
            risk_dollars=round(STOP_LOSS_PTS * delta_c * 100, 0),
            status="GREY" if is_after_cutoff else ("ACTIVE" if dist_c <= RAIL_PROXIMITY else "WAIT")
        ))
        # PUTS - enter at ascending rail
        entry_p = cone.ascending_rail
        dist_p = abs(current_price - entry_p)
        opt_p = get_option_data_for_entry(entry_p, "P", vix_current, eval_time)
        delta_p = abs(opt_p.spy_delta) if opt_p else DELTA_IDEAL
        setups.append(TradeSetup(
            direction="PUTS", cone_name=cone.name, cone_width=cone.width, entry=entry_p,
            stop=round(entry_p + STOP_LOSS_PTS, 2),
            target_25=round(entry_p - cone.width * 0.25, 2), target_50=round(entry_p - cone.width * 0.50, 2),
            target_75=round(entry_p - cone.width * 0.75, 2), target_100=round(entry_p - cone.width, 2),
            distance=round(dist_p, 1), option=opt_p,
            profit_25=round(cone.width * 0.25 * delta_p * 100, 0), profit_50=round(cone.width * 0.50 * delta_p * 100, 0),
            profit_75=round(cone.width * 0.75 * delta_p * 100, 0), profit_100=round(cone.width * delta_p * 100, 0),
            risk_dollars=round(STOP_LOSS_PTS * delta_p * 100, 0),
            status="GREY" if is_after_cutoff else ("ACTIVE" if dist_p <= RAIL_PROXIMITY else "WAIT")
        ))
    return setups

def calculate_day_score(vix_zone, cones, setups):
    score = DayScore()
    total = 0
    if vix_zone.bias in ["CALLS", "PUTS"] and any(s.direction == vix_zone.bias and s.distance <= 10 for s in setups):
        total += 25
    if vix_zone.bias != "WAIT" and (vix_zone.position_pct >= 75 or vix_zone.position_pct <= 25 or vix_zone.zones_away != 0):
        total += 25
    tradeable = [c for c in cones if c.is_tradeable]
    if tradeable:
        total += 20 if max(c.width for c in tradeable) >= 30 else 10
    sweet = sum(1 for s in setups if s.option and s.option.in_sweet_spot)
    total += 15 if sweet >= 3 else 10 if sweet >= 1 else 5
    score.total = total
    score.grade = "A" if total >= 80 else "B" if total >= 60 else "C" if total >= 40 else "D"
    score.color = "#10b981" if total >= 80 else "#3b82f6" if total >= 60 else "#f59e0b" if total >= 40 else "#ef4444"
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

def render_dashboard(vix_zone, cones, setups, pivot_table, prior_session, day_score, alerts, spx_price, trading_date, pivot_date, pivot_session_info, is_historical, theme):
    # Color system
    if theme == "light":
        bg_main = "#f1f5f9"
        bg_card = "#ffffff"
        bg_elevated = "#f8fafc"
        text_primary = "#0f172a"
        text_secondary = "#475569"
        text_muted = "#94a3b8"
        border_light = "#e2e8f0"
        border_medium = "#cbd5e1"
        shadow_sm = "0 1px 2px rgba(0,0,0,0.05)"
        shadow_md = "0 4px 12px rgba(0,0,0,0.08)"
        shadow_lg = "0 10px 40px rgba(0,0,0,0.12)"
    else:
        bg_main = "#0c0f1a"
        bg_card = "#151a2d"
        bg_elevated = "#1a2038"
        text_primary = "#f1f5f9"
        text_secondary = "#94a3b8"
        text_muted = "#64748b"
        border_light = "#1e293b"
        border_medium = "#334155"
        shadow_sm = "0 1px 2px rgba(0,0,0,0.3)"
        shadow_md = "0 4px 12px rgba(0,0,0,0.4)"
        shadow_lg = "0 10px 40px rgba(0,0,0,0.5)"
    
    # Accent colors
    green = "#10b981"
    green_light = "#d1fae5" if theme == "light" else "#064e3b"
    red = "#ef4444"
    red_light = "#fee2e2" if theme == "light" else "#7f1d1d"
    amber = "#f59e0b"
    amber_light = "#fef3c7" if theme == "light" else "#78350f"
    blue = "#3b82f6"
    blue_light = "#dbeafe" if theme == "light" else "#1e3a8a"
    purple = "#8b5cf6"
    cyan = "#06b6d4"
    
    bias_color = green if vix_zone.bias == "CALLS" else red if vix_zone.bias == "PUTS" else amber
    bias_bg = green_light if vix_zone.bias == "CALLS" else red_light if vix_zone.bias == "PUTS" else amber_light
    bias_icon = "↑" if vix_zone.bias == "CALLS" else "↓" if vix_zone.bias == "PUTS" else "•"
    
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
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {{
    --bg-main: {bg_main};
    --bg-card: {bg_card};
    --bg-elevated: {bg_elevated};
    --text-primary: {text_primary};
    --text-secondary: {text_secondary};
    --text-muted: {text_muted};
    --border-light: {border_light};
    --border-medium: {border_medium};
    --green: {green};
    --green-light: {green_light};
    --red: {red};
    --red-light: {red_light};
    --amber: {amber};
    --amber-light: {amber_light};
    --blue: {blue};
    --purple: {purple};
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}

body {{
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg-main);
    color: var(--text-primary);
    line-height: 1.6;
    padding: 24px;
    min-height: 100vh;
}}

.container {{ max-width: 1400px; margin: 0 auto; }}

/* Header */
.header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 28px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--border-light);
}}
.brand {{ display: flex; align-items: center; gap: 14px; }}
.brand-icon {{
    width: 52px; height: 52px;
    background: linear-gradient(135deg, {blue}, {purple});
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    font-family: 'JetBrains Mono'; font-weight: 700; font-size: 16px; color: white;
    box-shadow: {shadow_md};
}}
.brand-text h1 {{ font-size: 22px; font-weight: 800; letter-spacing: -0.5px; }}
.brand-text span {{ font-size: 12px; color: var(--text-muted); font-weight: 500; }}
.header-right {{ display: flex; align-items: center; gap: 24px; }}
.clock {{
    font-family: 'JetBrains Mono';
    font-size: 28px;
    font-weight: 600;
    color: var(--text-primary);
}}
.countdown-group {{ display: flex; gap: 16px; }}
.countdown-item {{ text-align: center; }}
.countdown-label {{ font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }}
.countdown-value {{ font-family: 'JetBrains Mono'; font-size: 16px; font-weight: 600; color: {amber}; }}

/* Alert Banner */
.alert-banner {{
    padding: 14px 20px;
    border-radius: 12px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 14px;
    font-weight: 600;
}}
.alert-banner.info {{ background: {blue_light}; color: {blue}; border: 1px solid {blue}30; }}
.alert-banner.warning {{ background: {amber_light}; color: {"#92400e" if theme == "light" else amber}; border: 1px solid {amber}30; }}
.alert-banner.historical {{ background: {"#f3e8ff" if theme == "light" else "#3b0764"}; color: {purple}; border: 1px solid {purple}30; }}

/* Card */
.card {{
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: 16px;
    margin-bottom: 20px;
    box-shadow: {shadow_sm};
    overflow: hidden;
}}
.card-header {{
    padding: 18px 22px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    transition: background 0.15s;
    border-bottom: 1px solid transparent;
}}
.card-header:hover {{ background: var(--bg-elevated); }}
.card-title {{
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 10px;
}}
.card-title-icon {{ font-size: 18px; }}
.card-chevron {{
    width: 20px; height: 20px;
    color: var(--text-muted);
    transition: transform 0.2s;
}}
.card.collapsed .card-content {{ display: none; }}
.card.collapsed .card-chevron {{ transform: rotate(-90deg); }}
.card-content {{ padding: 22px; }}

/* Main Grid */
.main-grid {{
    display: grid;
    grid-template-columns: 1fr 340px;
    gap: 20px;
    margin-bottom: 20px;
}}
@media (max-width: 1100px) {{ .main-grid {{ grid-template-columns: 1fr; }} }}

/* VIX Zone */
.vix-section {{ display: flex; flex-direction: column; gap: 20px; }}
.vix-meter {{
    background: var(--bg-elevated);
    border-radius: 12px;
    padding: 20px;
    border: 1px solid var(--border-light);
}}
.vix-bar {{
    position: relative;
    height: 12px;
    background: linear-gradient(90deg, {green}40, var(--bg-main) 35%, var(--bg-main) 65%, {red}40);
    border-radius: 6px;
    margin: 12px 0;
}}
.vix-marker {{
    position: absolute;
    width: 18px; height: 18px;
    background: {bias_color};
    border: 3px solid var(--bg-card);
    border-radius: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    box-shadow: 0 0 0 4px {bias_color}30, {shadow_sm};
}}
.vix-labels {{
    display: flex;
    justify-content: space-between;
    font-family: 'JetBrains Mono';
    font-size: 12px;
    color: var(--text-muted);
}}
.vix-stats {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-top: 16px;
}}
.vix-stat {{
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: 10px;
    padding: 14px;
    text-align: center;
}}
.vix-stat-value {{
    font-family: 'JetBrains Mono';
    font-size: 20px;
    font-weight: 700;
}}
.vix-stat-label {{
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
}}

/* Bias Display */
.bias-card {{
    background: {bias_bg};
    border: 2px solid {bias_color}50;
    border-radius: 16px;
    padding: 28px;
    text-align: center;
}}
.bias-icon {{
    font-size: 48px;
    font-weight: 800;
    color: {bias_color};
    line-height: 1;
}}
.bias-label {{
    font-size: 28px;
    font-weight: 800;
    color: {bias_color};
    margin-top: 8px;
    letter-spacing: 2px;
}}
.bias-reason {{
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 10px;
}}

/* Trading Checklist */
.checklist-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: 16px;
    overflow: hidden;
}}
.checklist-header {{
    padding: 16px 20px;
    background: {"#f0fdf4" if trade_ready else "#fef2f2"} ;
    border-bottom: 1px solid var(--border-light);
    display: flex;
    justify-content: space-between;
    align-items: center;
}}
.checklist-title {{
    font-size: 14px;
    font-weight: 700;
    color: {green if trade_ready else red};
}}
.checklist-score {{
    font-family: 'JetBrains Mono';
    font-size: 14px;
    font-weight: 700;
    color: {green if trade_ready else red};
}}
.checklist-items {{ padding: 8px 0; }}
.checklist-item {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 20px;
    border-bottom: 1px solid var(--border-light);
}}
.checklist-item:last-child {{ border-bottom: none; }}
.check-icon {{
    width: 22px; height: 22px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 700;
    flex-shrink: 0;
}}
.check-icon.pass {{ background: {green_light}; color: {green}; }}
.check-icon.fail {{ background: {red_light}; color: {red}; }}
.check-text {{ flex: 1; }}
.check-label {{ font-size: 13px; font-weight: 600; color: var(--text-primary); }}
.check-detail {{ font-size: 11px; color: var(--text-muted); }}

/* Collapsible Setup Sections */
.setup-section {{
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: 16px;
    margin-bottom: 16px;
    overflow: hidden;
}}
.setup-section-header {{
    padding: 18px 22px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: pointer;
    transition: background 0.15s;
}}
.setup-section-header:hover {{ background: var(--bg-elevated); }}
.setup-section-title {{
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 15px;
    font-weight: 700;
}}
.setup-section-title.calls {{ color: {green}; }}
.setup-section-title.puts {{ color: {red}; }}
.setup-count {{
    font-size: 12px;
    padding: 4px 12px;
    border-radius: 20px;
    font-weight: 600;
}}
.setup-count.calls {{ background: {green_light}; color: {green}; }}
.setup-count.puts {{ background: {red_light}; color: {red}; }}
.setup-section-chevron {{
    font-size: 12px;
    color: var(--text-muted);
    transition: transform 0.2s;
}}
.setup-section.collapsed .setup-section-content {{ display: none; }}
.setup-section.collapsed .setup-section-chevron {{ transform: rotate(-90deg); }}
.setup-section-content {{
    padding: 20px;
    border-top: 1px solid var(--border-light);
    background: var(--bg-elevated);
}}
.setup-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
}}

/* Setup Card */
.setup-card {{
    background: var(--bg-card);
    border: 1px solid var(--border-light);
    border-radius: 14px;
    padding: 20px;
    position: relative;
    transition: all 0.2s;
}}
.setup-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    border-radius: 14px 14px 0 0;
}}
.setup-card.calls::before {{ background: {green}; }}
.setup-card.puts::before {{ background: {red}; }}
.setup-card.active {{
    border-color: {green};
    box-shadow: 0 0 0 3px {green}20;
}}
.setup-card.active.puts {{
    border-color: {red};
    box-shadow: 0 0 0 3px {red}20;
}}
.setup-card.grey {{ opacity: 0.5; }}

.setup-card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}}
.setup-cone-name {{ font-size: 16px; font-weight: 700; }}
.setup-status {{
    font-size: 10px;
    padding: 5px 12px;
    border-radius: 20px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.setup-status.active {{ background: {green_light}; color: {green}; }}
.setup-status.wait {{ background: {amber_light}; color: {"#92400e" if theme == "light" else amber}; }}
.setup-status.grey {{ background: var(--bg-elevated); color: var(--text-muted); }}

.entry-display {{
    background: var(--bg-elevated);
    border-radius: 12px;
    padding: 18px;
    text-align: center;
    margin-bottom: 16px;
}}
.entry-label {{
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
}}
.entry-price {{
    font-family: 'JetBrains Mono';
    font-size: 32px;
    font-weight: 700;
}}
.entry-price.calls {{ color: {green}; }}
.entry-price.puts {{ color: {red}; }}
.entry-distance {{
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 6px;
}}

.contract-info {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 16px;
}}
.contract-box {{
    background: var(--bg-elevated);
    border-radius: 10px;
    padding: 14px;
    text-align: center;
}}
.contract-label {{ font-size: 9px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }}
.contract-value {{ font-family: 'JetBrains Mono'; font-size: 18px; font-weight: 700; margin-top: 4px; }}
.contract-value.calls {{ color: {green}; }}
.contract-value.puts {{ color: {red}; }}
.contract-sub {{ font-size: 11px; color: var(--text-secondary); margin-top: 2px; }}
.sweet-badge {{
    display: inline-block;
    background: {amber_light};
    color: {"#92400e" if theme == "light" else amber};
    font-size: 9px;
    padding: 3px 8px;
    border-radius: 10px;
    font-weight: 700;
    margin-top: 6px;
}}

.targets-section {{ margin-bottom: 14px; }}
.targets-label {{ font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }}
.targets-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
}}
.target-box {{
    background: var(--bg-elevated);
    border-radius: 8px;
    padding: 10px 6px;
    text-align: center;
}}
.target-pct {{ font-size: 10px; color: var(--text-muted); font-weight: 600; }}
.target-price {{ font-family: 'JetBrains Mono'; font-size: 11px; color: var(--text-secondary); margin-top: 2px; }}
.target-profit {{ font-family: 'JetBrains Mono'; font-size: 13px; font-weight: 700; color: {green}; margin-top: 2px; }}

.risk-display {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: {red_light};
    border-radius: 10px;
    padding: 12px 16px;
}}
.risk-label {{ font-size: 12px; color: {red}; font-weight: 600; }}
.risk-values {{ text-align: right; }}
.risk-stop {{ font-family: 'JetBrains Mono'; font-size: 12px; color: {red}; }}
.risk-amount {{ font-family: 'JetBrains Mono'; font-size: 16px; font-weight: 700; color: {red}; }}

/* Stats Grid */
.stats-row {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
}}
@media (max-width: 700px) {{ .stats-row {{ grid-template-columns: repeat(2, 1fr); }} }}
.stat-card {{
    background: var(--bg-elevated);
    border: 1px solid var(--border-light);
    border-radius: 12px;
    padding: 18px;
    text-align: center;
}}
.stat-value {{ font-family: 'JetBrains Mono'; font-size: 22px; font-weight: 700; }}
.stat-label {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 6px; }}

/* Table */
.data-table {{ width: 100%; border-collapse: collapse; }}
.data-table th {{
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    padding: 14px 12px;
    text-align: left;
    border-bottom: 1px solid var(--border-medium);
    background: var(--bg-elevated);
}}
.data-table td {{
    padding: 14px 12px;
    font-size: 13px;
    border-bottom: 1px solid var(--border-light);
}}
.data-table tr:hover {{ background: var(--bg-elevated); }}
.mono {{ font-family: 'JetBrains Mono'; }}
.text-green {{ color: {green}; }}
.text-red {{ color: {red}; }}
.text-amber {{ color: {amber}; }}
.text-blue {{ color: {blue}; }}
.badge {{
    display: inline-block;
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 10px;
    font-weight: 700;
}}
.badge-green {{ background: {green_light}; color: {green}; }}
.badge-red {{ background: {red_light}; color: {red}; }}

/* Footer */
.footer {{
    text-align: center;
    padding: 28px;
    color: var(--text-muted);
    font-size: 12px;
    border-top: 1px solid var(--border-light);
    margin-top: 28px;
}}
.footer-brand {{ font-weight: 700; color: var(--text-secondary); margin-bottom: 6px; }}
</style>
</head>
<body>
<div class="container">

<!-- HEADER -->
<header class="header">
    <div class="brand">
        <div class="brand-icon">SPX</div>
        <div class="brand-text">
            <h1>SPX Prophet</h1>
            <span>Institutional Edition v7.1</span>
        </div>
    </div>
    <div class="header-right">
        <div class="countdown-group">
            <div class="countdown-item">
                <div class="countdown-label">Entry Window</div>
                <div class="countdown-value">{format_countdown(get_time_until(ENTRY_TARGET))}</div>
            </div>
            <div class="countdown-item">
                <div class="countdown-label">Cutoff</div>
                <div class="countdown-value">{format_countdown(get_time_until(CUTOFF_TIME))}</div>
            </div>
        </div>
        <div class="clock">{now.strftime("%H:%M")} CT</div>
    </div>
</header>

<!-- BANNERS -->
'''
    
    if session_note:
        html += f'<div class="alert-banner info">⏰ Prior Session ({pivot_date.strftime("%b %d")}): {session_note}</div>'
    if is_historical:
        html += f'<div class="alert-banner historical">📅 Historical Analysis Mode: {trading_date.strftime("%A, %B %d, %Y")}</div>'
    if INST_WINDOW_START <= now.time() <= INST_WINDOW_END and not is_historical:
        html += f'<div class="alert-banner warning">🏛️ INSTITUTIONAL WINDOW ACTIVE — Prime Entry Zone</div>'
    
    # Main grid with VIX and Checklist
    zones_color = "text-green" if vix_zone.zones_away < 0 else "text-red" if vix_zone.zones_away > 0 else ""
    html += f'''
<!-- MAIN GRID -->
<div class="main-grid">
    <div class="vix-section">
        <div class="vix-meter">
            <div style="font-size:13px;font-weight:700;color:var(--text-secondary);margin-bottom:8px;">VIX Zone Analysis</div>
            <div class="vix-bar">
                <div class="vix-marker" style="left:{marker_pos}%"></div>
            </div>
            <div class="vix-labels">
                <span>{vix_zone.bottom:.2f}</span>
                <span>Zone: {vix_zone.zone_size:.2f}</span>
                <span>{vix_zone.top:.2f}</span>
            </div>
            <div class="vix-stats">
                <div class="vix-stat">
                    <div class="vix-stat-value">{vix_zone.current:.2f}</div>
                    <div class="vix-stat-label">Current</div>
                </div>
                <div class="vix-stat">
                    <div class="vix-stat-value">{vix_zone.position_pct:.0f}%</div>
                    <div class="vix-stat-label">Position</div>
                </div>
                <div class="vix-stat">
                    <div class="vix-stat-value text-blue">±{vix_zone.expected_spx_move:.0f}</div>
                    <div class="vix-stat-label">Exp. Move</div>
                </div>
                <div class="vix-stat">
                    <div class="vix-stat-value {zones_color}">{vix_zone.zones_away:+d}</div>
                    <div class="vix-stat-label">Zones Away</div>
                </div>
            </div>
        </div>
        <div class="bias-card">
            <div class="bias-icon">{bias_icon}</div>
            <div class="bias-label">{vix_zone.bias}</div>
            <div class="bias-reason">{vix_zone.bias_reason}</div>
        </div>
    </div>
    
    <div class="checklist-card">
        <div class="checklist-header" style="background:{'#f0fdf4' if trade_ready else '#fef2f2' if theme == 'light' else '#064e3b' if trade_ready else '#7f1d1d'}">
            <div class="checklist-title" style="color:{green if trade_ready else red}">{"✅ READY TO TRADE" if trade_ready else "⏸️ NOT OPTIMAL"}</div>
            <div class="checklist-score" style="color:{grade_color}">{total_score}/100 ({grade})</div>
        </div>
        <div class="checklist-items">
'''
    for item in checklist:
        pts = item["pts"]
        max_pts = item["max"]
        pct = (pts / max_pts * 100) if max_pts > 0 else 0
        pts_color = green if pct >= 75 else amber if pct >= 50 else red
        html += f'''
            <div class="checklist-item">
                <div class="check-pts" style="background:{pts_color}20;color:{pts_color};min-width:60px;text-align:center;padding:6px 10px;border-radius:8px;font-family:'JetBrains Mono';font-size:13px;font-weight:700;">{pts}/{max_pts}</div>
                <div class="check-text" style="flex:1;margin-left:12px;">
                    <div class="check-label">{item["label"]}</div>
                    <div class="check-detail">{item["detail"]}</div>
                </div>
            </div>
'''
    html += '''
        </div>
    </div>
</div>
'''
    
    # Collapsible CALLS Section
    html += f'''
<!-- CALLS SETUPS (Collapsible) -->
<div class="setup-section" id="calls-section">
    <div class="setup-section-header" onclick="document.getElementById('calls-section').classList.toggle('collapsed')">
        <div class="setup-section-title calls">
            <span>▲</span>
            <span>CALLS SETUPS</span>
            <span class="setup-count calls">{len(calls_setups)} Available</span>
        </div>
        <span class="setup-section-chevron">▼</span>
    </div>
    <div class="setup-section-content">
        <div class="setup-grid">
'''
    for s in calls_setups:
        opt = s.option
        status_class = "active" if s.status == "ACTIVE" else "grey" if s.status == "GREY" else ""
        status_text = "ACTIVE" if s.status == "ACTIVE" else "CLOSED" if s.status == "GREY" else "WAIT"
        status_style = "active" if s.status == "ACTIVE" else "grey" if s.status == "GREY" else "wait"
        html += f'''
            <div class="setup-card calls {status_class}">
                <div class="setup-card-header">
                    <div class="setup-cone-name">{s.cone_name}</div>
                    <div class="setup-status {status_style}">{status_text}</div>
                </div>
                <div class="entry-display">
                    <div class="entry-label">Entry Rail</div>
                    <div class="entry-price calls">{s.entry:,.2f}</div>
                    <div class="entry-distance">{s.distance:.0f} pts from current</div>
                </div>
                <div class="contract-info">
                    <div class="contract-box">
                        <div class="contract-label">SPX Strike</div>
                        <div class="contract-value calls">{opt.spx_strike}C</div>
                        <div class="contract-sub">{opt.otm_distance:.0f} pts OTM</div>
                    </div>
                    <div class="contract-box">
                        <div class="contract-label">Est. Premium</div>
                        <div class="contract-value">${opt.spx_price_est:.2f}</div>
                        <div class="contract-sub">${opt.spx_price_est * 100:,.0f}/contract</div>
                        {"<div class='sweet-badge'>★ SWEET SPOT</div>" if opt.in_sweet_spot else ""}
                    </div>
                </div>
                <div class="targets-section">
                    <div class="targets-label">Profit Targets</div>
                    <div class="targets-grid">
                        <div class="target-box"><div class="target-pct">25%</div><div class="target-price">{s.target_25:,.0f}</div><div class="target-profit">+${s.profit_25:,.0f}</div></div>
                        <div class="target-box"><div class="target-pct">50%</div><div class="target-price">{s.target_50:,.0f}</div><div class="target-profit">+${s.profit_50:,.0f}</div></div>
                        <div class="target-box"><div class="target-pct">75%</div><div class="target-price">{s.target_75:,.0f}</div><div class="target-profit">+${s.profit_75:,.0f}</div></div>
                        <div class="target-box"><div class="target-pct">100%</div><div class="target-price">{s.target_100:,.0f}</div><div class="target-profit">+${s.profit_100:,.0f}</div></div>
                    </div>
                </div>
                <div class="risk-display">
                    <div class="risk-label">Stop Loss</div>
                    <div class="risk-values">
                        <div class="risk-stop">{s.stop:,.2f}</div>
                        <div class="risk-amount">-${s.risk_dollars:,.0f}</div>
                    </div>
                </div>
            </div>
'''
    html += '</div></div></div>'
    
    # Collapsible PUTS Section
    html += f'''
<!-- PUTS SETUPS (Collapsible) -->
<div class="setup-section collapsed" id="puts-section">
    <div class="setup-section-header" onclick="document.getElementById('puts-section').classList.toggle('collapsed')">
        <div class="setup-section-title puts">
            <span>▼</span>
            <span>PUTS SETUPS</span>
            <span class="setup-count puts">{len(puts_setups)} Available</span>
        </div>
        <span class="setup-section-chevron">▼</span>
    </div>
    <div class="setup-section-content">
        <div class="setup-grid">
'''
    for s in puts_setups:
        opt = s.option
        status_class = "active" if s.status == "ACTIVE" else "grey" if s.status == "GREY" else ""
        status_text = "ACTIVE" if s.status == "ACTIVE" else "CLOSED" if s.status == "GREY" else "WAIT"
        status_style = "active" if s.status == "ACTIVE" else "grey" if s.status == "GREY" else "wait"
        html += f'''
            <div class="setup-card puts {status_class}">
                <div class="setup-card-header">
                    <div class="setup-cone-name">{s.cone_name}</div>
                    <div class="setup-status {status_style}">{status_text}</div>
                </div>
                <div class="entry-display">
                    <div class="entry-label">Entry Rail</div>
                    <div class="entry-price puts">{s.entry:,.2f}</div>
                    <div class="entry-distance">{s.distance:.0f} pts from current</div>
                </div>
                <div class="contract-info">
                    <div class="contract-box">
                        <div class="contract-label">SPX Strike</div>
                        <div class="contract-value puts">{opt.spx_strike}P</div>
                        <div class="contract-sub">{opt.otm_distance:.0f} pts OTM</div>
                    </div>
                    <div class="contract-box">
                        <div class="contract-label">Est. Premium</div>
                        <div class="contract-value">${opt.spx_price_est:.2f}</div>
                        <div class="contract-sub">${opt.spx_price_est * 100:,.0f}/contract</div>
                        {"<div class='sweet-badge'>★ SWEET SPOT</div>" if opt.in_sweet_spot else ""}
                    </div>
                </div>
                <div class="targets-section">
                    <div class="targets-label">Profit Targets</div>
                    <div class="targets-grid">
                        <div class="target-box"><div class="target-pct">25%</div><div class="target-price">{s.target_25:,.0f}</div><div class="target-profit">+${s.profit_25:,.0f}</div></div>
                        <div class="target-box"><div class="target-pct">50%</div><div class="target-price">{s.target_50:,.0f}</div><div class="target-profit">+${s.profit_50:,.0f}</div></div>
                        <div class="target-box"><div class="target-pct">75%</div><div class="target-price">{s.target_75:,.0f}</div><div class="target-profit">+${s.profit_75:,.0f}</div></div>
                        <div class="target-box"><div class="target-pct">100%</div><div class="target-price">{s.target_100:,.0f}</div><div class="target-profit">+${s.profit_100:,.0f}</div></div>
                    </div>
                </div>
                <div class="risk-display">
                    <div class="risk-label">Stop Loss</div>
                    <div class="risk-values">
                        <div class="risk-stop">{s.stop:,.2f}</div>
                        <div class="risk-amount">-${s.risk_dollars:,.0f}</div>
                    </div>
                </div>
            </div>
'''
    html += '</div></div></div>'
    
    # Prior Session Stats
    html += f'''
<!-- PRIOR SESSION -->
<div class="card">
    <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="card-title">
            <span class="card-title-icon">📈</span>
            Prior Session ({pivot_date.strftime("%b %d")})
        </div>
        <span class="card-chevron">▼</span>
    </div>
    <div class="card-content">
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-value text-green">{prior_session.get("high",0):,.2f}</div>
                <div class="stat-label">High</div>
            </div>
            <div class="stat-card">
                <div class="stat-value text-red">{prior_session.get("low",0):,.2f}</div>
                <div class="stat-label">Low</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{prior_session.get("close",0):,.2f}</div>
                <div class="stat-label">Close</div>
            </div>
            <div class="stat-card">
                <div class="stat-value text-blue">{prior_session.get("high",0) - prior_session.get("low",0):,.0f}</div>
                <div class="stat-label">Range</div>
            </div>
        </div>
    </div>
</div>
'''
    
    # Structural Cones
    html += f'''
<!-- STRUCTURAL CONES -->
<div class="card">
    <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="card-title">
            <span class="card-title-icon">📐</span>
            Structural Cones
        </div>
        <span class="card-chevron">▼</span>
    </div>
    <div class="card-content">
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
        width_color = "text-green" if c.width >= 25 else "text-amber" if c.width >= MIN_CONE_WIDTH else "text-red"
        badge = '<span class="badge badge-green">YES</span>' if c.is_tradeable else '<span class="badge badge-red">NO</span>'
        html += f'''
                <tr>
                    <td><strong>{c.name}</strong></td>
                    <td class="mono text-red">{c.ascending_rail:,.2f}</td>
                    <td class="mono text-green">{c.descending_rail:,.2f}</td>
                    <td class="mono {width_color}">{c.width:.0f} pts</td>
                    <td>{badge}</td>
                </tr>
'''
    html += '''
            </tbody>
        </table>
    </div>
</div>
'''
    
    # Pivot Table (collapsed by default)
    html += f'''
<!-- PIVOT TABLE -->
<div class="card collapsed">
    <div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <div class="card-title">
            <span class="card-title-icon">📋</span>
            Pivot Time Table
        </div>
        <span class="card-chevron">▼</span>
    </div>
    <div class="card-content">
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
        row_style = f'style="background:{amber_light}"' if is_inst else ""
        html += f'''
                <tr {row_style}>
                    <td><strong>{row.time_block}{inst_marker}</strong></td>
                    <td class="mono text-red">{row.prior_high_asc:,.2f}</td>
                    <td class="mono text-green">{row.prior_high_desc:,.2f}</td>
                    <td class="mono text-red">{row.prior_low_asc:,.2f}</td>
                    <td class="mono text-green">{row.prior_low_desc:,.2f}</td>
                    <td class="mono text-red">{row.prior_close_asc:,.2f}</td>
                    <td class="mono text-green">{row.prior_close_desc:,.2f}</td>
                </tr>
'''
    html += '''
            </tbody>
        </table>
    </div>
</div>
'''
    
    # Footer
    html += f'''
<!-- FOOTER -->
<footer class="footer">
    <div class="footer-brand">SPX Prophet v7.1 — Institutional Edition</div>
    <div>Trading: {trading_date.strftime("%B %d, %Y")} • Pivot Anchor: {pivot_date.strftime("%B %d, %Y")}</div>
    <div style="margin-top:4px;">Contracts ~15pts OTM • Sweet Spot: $4-$8 ($400-$800/contract)</div>
</footer>

</div>
</body>
</html>
'''
    return html

def main():
    st.set_page_config(page_title="SPX Prophet v7.0", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
    defaults = {'theme': 'light', 'vix_bottom': 0.0, 'vix_top': 0.0, 'vix_current': 0.0, 'use_manual_pivots': False, 'high_price': 0.0, 'high_time': "10:30", 'low_price': 0.0, 'low_time': "14:00", 'close_price': 0.0, 'trading_date': None, 'last_refresh': None}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    
    with st.sidebar:
        st.markdown("## 📈 SPX Prophet v7.0")
        st.caption("Institutional Edition")
        st.divider()
        theme = st.radio("🎨 Theme", ["Light", "Dark"], horizontal=True, index=0 if st.session_state.theme == "light" else 1)
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
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.vix_bottom = st.number_input("Bottom", value=st.session_state.vix_bottom, step=0.01, format="%.2f")
        with col2:
            st.session_state.vix_top = st.number_input("Top", value=st.session_state.vix_top, step=0.01, format="%.2f")
        st.session_state.vix_current = st.number_input("Current VIX", value=st.session_state.vix_current, step=0.01, format="%.2f")
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
    prior_bars = polygon_get_daily_bars("I:SPX", pivot_date, pivot_date)
    prior_session = {"high": prior_bars[0].get("h", 0), "low": prior_bars[0].get("l", 0), "close": prior_bars[0].get("c", 0), "open": prior_bars[0].get("o", 0)} if prior_bars else {}
    
    if st.session_state.use_manual_pivots and st.session_state.high_price > 0:
        pivots = create_manual_pivots(st.session_state.high_price, st.session_state.high_time, st.session_state.low_price, st.session_state.low_time, st.session_state.close_price, pivot_date, pivot_close_time)
    else:
        bars_30m = polygon_get_intraday_bars("I:SPX", pivot_date, pivot_date, 30)
        pivots = detect_pivots_auto(bars_30m, pivot_date, pivot_close_time) if bars_30m else []
        if not pivots and prior_session:
            pivots = [Pivot(name="Prior High", price=prior_session.get("high", 0), pivot_time=CT_TZ.localize(datetime.combine(pivot_date, time(10, 30))), pivot_type="HIGH", candle_high=prior_session.get("high", 0)),
                      Pivot(name="Prior Low", price=prior_session.get("low", 0), pivot_time=CT_TZ.localize(datetime.combine(pivot_date, time(14, 0))), pivot_type="LOW", candle_open=prior_session.get("low", 0)),
                      Pivot(name="Prior Close", price=prior_session.get("close", 0), pivot_time=CT_TZ.localize(datetime.combine(pivot_date, pivot_close_time)), pivot_type="CLOSE")]
    
    eval_time = CT_TZ.localize(datetime.combine(trading_date, time(9, 0)))
    cones = build_cones(pivots, eval_time)
    vix_zone = analyze_vix_zone(st.session_state.vix_bottom, st.session_state.vix_top, st.session_state.vix_current, cones)
    spx_price = polygon_get_index_price("I:SPX") or prior_session.get("close", 0)
    is_after_cutoff = (trading_date == now.date() and now.time() > CUTOFF_TIME) or is_historical
    
    # Pass VIX for accurate option pricing
    vix_for_pricing = st.session_state.vix_current if st.session_state.vix_current > 0 else 16
    setups = generate_setups(cones, spx_price, vix_for_pricing, eval_time, is_after_cutoff)
    
    day_score = calculate_day_score(vix_zone, cones, setups)
    pivot_table = build_pivot_table(pivots, trading_date)
    alerts = check_alerts(setups, vix_zone, now.time()) if not is_historical else []
    html = render_dashboard(vix_zone, cones, setups, pivot_table, prior_session, day_score, alerts, spx_price, trading_date, pivot_date, pivot_session_info, is_historical, st.session_state.theme)
    components.html(html, height=4000, scrolling=True)

if __name__ == "__main__":
    main()