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

HOLIDAYS_2024 = {date(2024, 12, 25): "Christmas 2024"}
HOLIDAYS_2025 = {
    date(2025, 1, 1): "New Year's Day", date(2025, 1, 20): "MLK Day",
    date(2025, 2, 17): "Presidents Day", date(2025, 4, 18): "Good Friday",
    date(2025, 5, 26): "Memorial Day", date(2025, 6, 19): "Juneteenth",
    date(2025, 7, 4): "Independence Day", date(2025, 9, 1): "Labor Day",
    date(2025, 11, 27): "Thanksgiving", date(2025, 12, 25): "Christmas",
}
HALF_DAYS_2024 = {date(2024, 12, 24): "Christmas Eve 2024"}
HALF_DAYS_2025 = {
    date(2025, 7, 3): "Day before July 4th",
    date(2025, 11, 26): "Day before Thanksgiving",
    date(2025, 11, 28): "Day after Thanksgiving",
    date(2025, 12, 24): "Christmas Eve",
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
    return d in HOLIDAYS_2025 or d in HOLIDAYS_2024

def is_half_day(d):
    return d in HALF_DAYS_2025 or d in HALF_DAYS_2024

def get_market_close_time(d):
    return HALF_DAY_CLOSE if is_half_day(d) else REGULAR_CLOSE

def get_session_info(d):
    if is_holiday(d):
        return {"is_trading": False, "reason": HOLIDAYS_2025.get(d) or HOLIDAYS_2024.get(d, "Holiday")}
    return {"is_trading": True, "is_half_day": is_half_day(d), "close_ct": get_market_close_time(d),
            "reason": HALF_DAYS_2025.get(d) or HALF_DAYS_2024.get(d, "") if is_half_day(d) else ""}

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

def get_time_until(target, from_dt=None):
    if from_dt is None:
        from_dt = get_ct_now()
    target_dt = CT_TZ.localize(datetime.combine(from_dt.date(), target))
    return max(target_dt - from_dt, timedelta(0))

def format_countdown(td):
    if td.total_seconds() <= 0:
        return "NOW"
    total_secs = int(td.total_seconds())
    hours, remainder = divmod(total_secs, 3600)
    minutes, seconds = divmod(remainder, 60)
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

def get_option_data_for_entry(entry_rail, opt_type, expiry):
    if opt_type.upper() in ["C", "CALL", "CALLS"]:
        spx_strike = int(round((entry_rail + OTM_DISTANCE_PTS) / 5) * 5)
    else:
        spx_strike = int(round((entry_rail - OTM_DISTANCE_PTS) / 5) * 5)
    otm_distance = abs(spx_strike - entry_rail)
    spy_level = entry_rail / 10
    spy_otm = otm_distance / 10
    spy_strike = int(round(spy_level + spy_otm)) if opt_type.upper() in ["C", "CALL", "CALLS"] else int(round(spy_level - spy_otm))
    spy_price = 5.50  # Default estimate
    return OptionData(spy_strike=spy_strike, spy_price=spy_price, spy_delta=DELTA_IDEAL if opt_type.upper() in ["C", "CALL", "CALLS"] else -DELTA_IDEAL,
                      spx_strike=spx_strike, spx_price_est=spy_price * 10, otm_distance=otm_distance,
                      in_sweet_spot=(PREMIUM_SWEET_LOW <= spy_price <= PREMIUM_SWEET_HIGH))

def detect_pivots_auto(bars, pivot_date, close_time_ct):
    if not bars:
        return []
    filtered_bars = filter_bars_to_session(bars, pivot_date, close_time_ct)
    if not filtered_bars or len(filtered_bars) < 3:
        return []
    pivots = []
    candles = []
    for bar in filtered_bars:
        ts = bar.get("t", 0)
        dt = datetime.fromtimestamp(ts / 1000, tz=ET_TZ).astimezone(CT_TZ)
        candles.append({"time": dt, "open": bar.get("o", 0), "high": bar.get("h", 0), "low": bar.get("l", 0), "close": bar.get("c", 0), "is_green": bar.get("c", 0) >= bar.get("o", 0)})
    
    high_candidates = []
    for i in range(len(candles) - 1):
        curr, nxt = candles[i], candles[i + 1]
        if curr["is_green"] and not nxt["is_green"] and nxt["close"] < curr["open"]:
            high_candidates.append({"price": curr["high"], "time": curr["time"], "open": curr["open"]})
    
    low_candidates = []
    for i in range(len(candles) - 1):
        curr, nxt = candles[i], candles[i + 1]
        if not curr["is_green"] and nxt["is_green"] and nxt["close"] > curr["open"]:
            low_candidates.append({"price": curr["low"], "time": curr["time"], "open": nxt["open"]})
    
    if high_candidates:
        high_candidates.sort(key=lambda x: x["price"], reverse=True)
        pivots.append(Pivot(name="Prior High", price=high_candidates[0]["price"], pivot_time=high_candidates[0]["time"], pivot_type="HIGH", candle_high=high_candidates[0]["price"], candle_open=high_candidates[0]["open"]))
    
    if low_candidates:
        low_candidates.sort(key=lambda x: x["price"])
        pivots.append(Pivot(name="Prior Low", price=low_candidates[0]["price"], pivot_time=low_candidates[0]["time"], pivot_type="LOW", candle_open=low_candidates[0]["open"]))
    
    if candles:
        pivots.append(Pivot(name="Prior Close", price=candles[-1]["close"], pivot_time=CT_TZ.localize(datetime.combine(pivot_date, close_time_ct)), pivot_type="CLOSE"))
    
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
    if eval_time <= start_time:
        return 0
    MAINT_START, MAINT_END = time(16, 0), time(17, 0)
    if start_time.tzinfo is None:
        start_time = CT_TZ.localize(start_time)
    if eval_time.tzinfo is None:
        eval_time = CT_TZ.localize(eval_time)
    blocks = 0
    current = start_time
    for _ in range(2000):
        if current >= eval_time:
            break
        wd, ct = current.weekday(), current.time()
        if wd >= 5:
            current = CT_TZ.localize(datetime.combine(current.date() + timedelta(days=(7 - wd) if wd == 5 else 1), MAINT_END))
            continue
        if MAINT_START <= ct < MAINT_END:
            current = CT_TZ.localize(datetime.combine(current.date(), MAINT_END))
            continue
        if wd == 4 and ct >= MAINT_START:
            current = CT_TZ.localize(datetime.combine(current.date() + timedelta(days=2), MAINT_END))
            continue
        next_block = current + timedelta(minutes=30)
        if next_block > eval_time:
            break
        if ct < MAINT_START and next_block.time() >= MAINT_START:
            blocks += 1
            current = CT_TZ.localize(datetime.combine(current.date(), MAINT_END))
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

def generate_setups(cones, current_price, expiry, is_after_cutoff=False):
    setups = []
    for cone in cones:
        if not cone.is_tradeable:
            continue
        # CALLS
        entry_c = cone.descending_rail
        dist_c = abs(current_price - entry_c)
        opt_c = get_option_data_for_entry(entry_c, "C", expiry)
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
        # PUTS
        entry_p = cone.ascending_rail
        dist_p = abs(current_price - entry_p)
        opt_p = get_option_data_for_entry(entry_p, "P", expiry)
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
    if theme == "dark":
        bg, card_bg, text1, text2, border = "#0a0a0f", "rgba(20,20,30,0.85)", "#ffffff", "#a1a1aa", "rgba(255,255,255,0.08)"
    else:
        bg, card_bg, text1, text2, border = "#f8fafc", "rgba(255,255,255,0.9)", "#0f172a", "#475569", "rgba(0,0,0,0.08)"
    green, red, amber, blue, purple, cyan = "#10b981", "#ef4444", "#f59e0b", "#3b82f6", "#8b5cf6", "#06b6d4"
    bias_color = green if vix_zone.bias == "CALLS" else red if vix_zone.bias == "PUTS" else amber
    bias_icon = "▲" if vix_zone.bias == "CALLS" else "▼" if vix_zone.bias == "PUTS" else "●"
    now = get_ct_now()
    marker_pos = min(max(vix_zone.position_pct, 5), 95) if vix_zone.zone_size > 0 else 50
    session_note = f"Half Day - Closed {pivot_session_info['close_ct'].strftime('%I:%M %p')} CT" if pivot_session_info.get("is_half_day") else ""
    
    html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Outfit',sans-serif;background:{bg};color:{text1};padding:24px;line-height:1.6}}
.container{{max-width:1800px;margin:0 auto}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:32px;flex-wrap:wrap;gap:24px}}
.logo{{display:flex;align-items:center;gap:16px}}
.logo-mark{{width:56px;height:56px;background:linear-gradient(135deg,{blue},{purple});border-radius:14px;display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono';font-size:18px;font-weight:800;color:white;box-shadow:0 8px 24px {blue}40}}
.logo h1{{font-size:26px;font-weight:800}}.tagline{{font-size:11px;color:{text2}}}
.time-display{{font-family:'JetBrains Mono';font-size:32px;font-weight:700}}
.countdown{{text-align:right}}.countdown-label{{font-size:9px;text-transform:uppercase;letter-spacing:2px;color:{text2}}}.countdown-value{{font-family:'JetBrains Mono';font-size:16px;color:{amber};font-weight:600}}
.banner{{padding:14px 20px;border-radius:14px;display:flex;align-items:center;gap:14px;margin-bottom:20px}}
.banner-session{{background:{cyan}15;border:1px solid {cyan}40}}.banner-hist{{background:{purple}15;border:1px solid {purple}40}}.banner-inst{{background:{amber}15;border:1px solid {amber}40}}
.card{{background:{card_bg};backdrop-filter:blur(20px);border:1px solid {border};border-radius:20px;padding:24px;margin-bottom:20px}}
.card-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;cursor:pointer}}
.card-title{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:{text2};display:flex;align-items:center;gap:10px}}
.collapsed .card-content{{display:none}}
.alert{{padding:14px 18px;border-radius:12px;font-size:13px;font-weight:500;margin-bottom:10px}}
.alert-HIGH{{background:{red}12;border-left:4px solid {red};color:{red}}}.alert-MEDIUM{{background:{amber}12;border-left:4px solid {amber};color:{amber}}}.alert-INFO{{background:{blue}12;border-left:4px solid {blue};color:{blue}}}
.grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}@media(max-width:1100px){{.grid-2{{grid-template-columns:1fr}}}}
.vix-ladder{{position:relative;height:70px;margin:16px 0;background:rgba(255,255,255,0.02);border-radius:12px}}
.vix-track{{position:absolute;left:20px;right:20px;height:36px;top:50%;transform:translateY(-50%);background:linear-gradient(90deg,{green}50,{bg},{bg},{red}50);border-radius:18px}}
.vix-marker{{position:absolute;width:20px;height:20px;background:{bias_color};border-radius:50%;top:50%;transform:translate(-50%,-50%);box-shadow:0 0 20px {bias_color}60;border:3px solid {card_bg};z-index:10}}
.vix-labels{{position:absolute;bottom:4px;left:20px;right:20px;display:flex;justify-content:space-between;font-family:'JetBrains Mono';font-size:11px;color:{text2}}}
.stat-box{{background:rgba(255,255,255,0.02);border:1px solid {border};border-radius:14px;padding:14px;text-align:center}}
.stat-value{{font-family:'JetBrains Mono';font-size:20px;font-weight:700}}.stat-value.green{{color:{green}}}.stat-value.red{{color:{red}}}.stat-value.blue{{color:{blue}}}
.stat-label{{font-size:8px;text-transform:uppercase;letter-spacing:1.5px;color:{text2};margin-top:4px}}
.bias-display{{background:linear-gradient(135deg,{bias_color}18,{bias_color}05);border:2px solid {bias_color}40;border-radius:20px;padding:36px;text-align:center}}
.bias-icon{{font-size:56px;color:{bias_color};text-shadow:0 0 30px {bias_color}50}}.bias-label{{font-size:32px;font-weight:800;color:{bias_color};letter-spacing:3px;margin-top:8px}}.bias-reason{{font-size:13px;color:{text2};margin-top:12px}}.bias-match{{font-size:12px;color:{blue};margin-top:8px;font-weight:600}}
.setup-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:20px}}
.setup-card{{background:{card_bg};border:1px solid {border};border-radius:20px;padding:24px;transition:all 0.3s;position:relative;overflow:hidden}}
.setup-card::before{{content:'';position:absolute;top:0;left:0;right:0;height:4px}}.setup-card.calls::before{{background:{green}}}.setup-card.puts::before{{background:{red}}}
.setup-card.active{{border-color:{green}60;box-shadow:0 0 30px {green}25}}.setup-card.active.puts{{border-color:{red}60;box-shadow:0 0 30px {red}25}}.setup-card.grey{{opacity:0.4}}
.setup-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}}.setup-cone{{font-size:18px;font-weight:700}}
.setup-badge{{font-size:10px;font-weight:700;padding:6px 14px;border-radius:100px;text-transform:uppercase}}.setup-badge.calls{{background:{green}20;color:{green}}}.setup-badge.puts{{background:{red}20;color:{red}}}
.entry-block{{background:rgba(255,255,255,0.02);border:1px solid {border};border-radius:16px;padding:24px;text-align:center;margin-bottom:20px}}
.entry-label{{font-size:9px;text-transform:uppercase;letter-spacing:2px;color:{text2};margin-bottom:6px}}.entry-price{{font-family:'JetBrains Mono';font-size:36px;font-weight:800}}.entry-price.calls{{color:{green}}}.entry-price.puts{{color:{red}}}
.entry-status{{font-size:12px;color:{text2};margin-top:10px}}.entry-status.active{{color:{green};font-weight:700}}
.contract-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px}}.contract-box{{background:rgba(255,255,255,0.02);border:1px solid {border};border-radius:14px;padding:16px;text-align:center}}
.contract-label{{font-size:8px;text-transform:uppercase;letter-spacing:1.5px;color:{text2};margin-bottom:6px}}.contract-strike{{font-family:'JetBrains Mono';font-size:22px;font-weight:700}}.contract-strike.calls{{color:{green}}}.contract-strike.puts{{color:{red}}}
.contract-premium{{font-size:12px;color:{text2};margin-top:4px}}.contract-otm{{font-size:9px;color:{text2}}}
.sweet-spot{{display:inline-block;background:{amber}20;color:{amber};font-size:8px;padding:3px 8px;border-radius:100px;margin-top:6px;font-weight:600}}
.targets-title{{font-size:9px;text-transform:uppercase;letter-spacing:2px;color:{text2};margin-bottom:12px}}
.target-row{{display:flex;justify-content:space-between;align-items:center;padding:12px 14px;background:rgba(255,255,255,0.02);border:1px solid {border};border-radius:12px;margin-bottom:8px}}
.target-label{{font-size:12px;color:{text2}}}.target-price{{font-family:'JetBrains Mono';font-size:13px}}.target-profit{{font-family:'JetBrains Mono';font-size:15px;font-weight:700;color:{green}}}
.risk-section{{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;background:{red}08;border:1px solid {red}25;border-radius:14px;margin-top:16px}}
.risk-label{{font-size:11px;color:{red};font-weight:600}}.risk-stop{{font-family:'JetBrains Mono';font-size:13px;color:{red}}}.risk-amount{{font-family:'JetBrains Mono';font-size:16px;font-weight:700;color:{red}}}
.score-circle{{width:100px;height:100px;border-radius:50%;margin:0 auto 16px;display:flex;flex-direction:column;align-items:center;justify-content:center;border:5px solid}}
.score-value{{font-family:'JetBrains Mono';font-size:32px;font-weight:800}}.score-grade{{font-size:14px;font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:12px}}th{{font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:{text2};padding:12px 8px;text-align:left;border-bottom:1px solid {border}}}td{{padding:14px 8px;border-bottom:1px solid {border}}}.mono{{font-family:'JetBrains Mono'}}.green{{color:{green}}}.red{{color:{red}}}.amber{{color:{amber}}}
.pill{{display:inline-block;padding:4px 10px;border-radius:100px;font-size:9px;font-weight:700}}.pill-yes{{background:{green}20;color:{green}}}.pill-no{{background:{red}20;color:{red}}}
.footer{{text-align:center;padding:32px;color:{text2};font-size:10px;border-top:1px solid {border};margin-top:32px}}
</style></head><body><div class="container">
<header class="header">
<div class="logo"><div class="logo-mark">SP</div><div><h1>SPX Prophet</h1><div class="tagline">Institutional Edition v7.0</div></div></div>
<div style="display:flex;align-items:center;gap:28px">
<div class="countdown"><div class="countdown-label">Entry Window</div><div class="countdown-value">{format_countdown(get_time_until(ENTRY_TARGET))}</div></div>
<div class="countdown"><div class="countdown-label">Cutoff</div><div class="countdown-value">{format_countdown(get_time_until(CUTOFF_TIME))}</div></div>
<div class="time-display">{now.strftime("%H:%M")} CT</div>
</div></header>'''
    
    if session_note:
        html += f'<div class="banner banner-session"><span style="font-size:24px">⏰</span><span style="color:{cyan};font-weight:600">Prior Session ({pivot_date.strftime("%b %d")}): {session_note}</span></div>'
    if is_historical:
        html += f'<div class="banner banner-hist"><span style="font-size:24px">📅</span><span style="color:{purple};font-weight:600">Historical Analysis: {trading_date.strftime("%B %d, %Y")}</span></div>'
    if INST_WINDOW_START <= now.time() <= INST_WINDOW_END and not is_historical:
        html += f'<div class="banner banner-inst"><span style="font-size:24px">🏛️</span><span style="color:{amber};font-weight:600">INSTITUTIONAL WINDOW ACTIVE</span></div>'
    
    if alerts:
        html += '<div style="margin-bottom:20px">'
        for a in alerts[:5]:
            html += f'<div class="alert alert-{a["priority"]}">{a["message"]}</div>'
        html += '</div>'
    
    zones_cls = "green" if vix_zone.zones_away < 0 else "red" if vix_zone.zones_away > 0 else ""
    html += f'''<div class="card"><div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')"><div class="card-title"><span>📊</span>VIX Zone Analysis</div><span style="color:{text2}">▼</span></div><div class="card-content"><div class="grid-2">
<div><div class="vix-ladder"><div class="vix-track"></div><div class="vix-marker" style="left:{marker_pos}%"></div><div class="vix-labels"><span>{vix_zone.bottom:.2f}</span><span>Zone: {vix_zone.zone_size:.2f}</span><span>{vix_zone.top:.2f}</span></div></div>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:20px">
<div class="stat-box"><div class="stat-value">{vix_zone.current:.2f}</div><div class="stat-label">Current VIX</div></div>
<div class="stat-box"><div class="stat-value">{vix_zone.position_pct:.0f}%</div><div class="stat-label">Position</div></div>
<div class="stat-box"><div class="stat-value blue">±{vix_zone.expected_spx_move:.0f}</div><div class="stat-label">Expected Move</div></div>
<div class="stat-box"><div class="stat-value {zones_cls}">{vix_zone.zones_away:+d}</div><div class="stat-label">Zones Away</div></div>
</div></div>
<div class="bias-display"><div class="bias-icon">{bias_icon}</div><div class="bias-label">{vix_zone.bias}</div><div class="bias-reason">{vix_zone.bias_reason}</div>{"<div class='bias-match'>🎯 Target: " + vix_zone.matched_cone + " @ " + f"{vix_zone.matched_rail:,.2f}" + "</div>" if vix_zone.matched_rail > 0 else ""}</div>
</div></div></div>'''
    
    def render_setups(direction):
        filtered = [s for s in setups if s.direction == direction]
        icon = "▲" if direction == "CALLS" else "▼"
        h = f'<div style="margin-bottom:24px"><div style="display:flex;align-items:center;gap:12px;margin-bottom:16px"><span style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:{green if direction=="CALLS" else red}">{icon} {direction} SETUPS</span><span style="font-size:10px;padding:4px 12px;border-radius:100px;font-weight:600;background:{green if direction=="CALLS" else red}20;color:{green if direction=="CALLS" else red}">{len(filtered)} Available</span></div><div class="setup-grid">'
        for s in filtered:
            opt = s.option
            status_class = "active" if s.status == "ACTIVE" else "grey" if s.status == "GREY" else ""
            status_text = "🎯 ACTIVE — READY" if s.status == "ACTIVE" else "CLOSED" if s.status == "GREY" else f"{s.distance:.0f} pts away"
            status_cls = "active" if s.status == "ACTIVE" else ""
            spx_strike = f"{opt.spx_strike}{'C' if direction == 'CALLS' else 'P'}" if opt else "—"
            spx_price = f"${opt.spx_price_est:.0f}" if opt else "—"
            spy_strike = f"SPY {int(opt.spy_strike)}{'C' if direction == 'CALLS' else 'P'}" if opt else "—"
            spy_price = f"${opt.spy_price:.2f}" if opt else "—"
            otm = f"{opt.otm_distance:.0f} pts OTM" if opt else "—"
            sweet = opt.in_sweet_spot if opt else False
            h += f'''<div class="setup-card {direction.lower()} {status_class}">
<div class="setup-header"><div class="setup-cone">{s.cone_name}</div><div class="setup-badge {direction.lower()}">{direction[:-1]}</div></div>
<div class="entry-block"><div class="entry-label">Entry Level</div><div class="entry-price {direction.lower()}">{s.entry:,.2f}</div><div class="entry-status {status_cls}">{status_text}</div></div>
<div class="contract-grid"><div class="contract-box"><div class="contract-label">SPX Contract</div><div class="contract-strike {direction.lower()}">{spx_strike}</div><div class="contract-premium">Est. {spx_price}</div><div class="contract-otm">{otm}</div></div>
<div class="contract-box"><div class="contract-label">SPY Ref</div><div class="contract-strike">{spy_strike}</div><div class="contract-premium">{spy_price}</div>{"<div class='sweet-spot'>★ SWEET SPOT</div>" if sweet else ""}</div></div>
<div class="targets-title">Profit Targets</div>
<div class="target-row"><div class="target-label">25%</div><div class="target-price">{s.target_25:,.2f}</div><div class="target-profit">+${s.profit_25:,.0f}</div></div>
<div class="target-row"><div class="target-label">50%</div><div class="target-price">{s.target_50:,.2f}</div><div class="target-profit">+${s.profit_50:,.0f}</div></div>
<div class="target-row"><div class="target-label">75%</div><div class="target-price">{s.target_75:,.2f}</div><div class="target-profit">+${s.profit_75:,.0f}</div></div>
<div class="target-row"><div class="target-label">100%</div><div class="target-price">{s.target_100:,.2f}</div><div class="target-profit">+${s.profit_100:,.0f}</div></div>
<div class="risk-section"><div class="risk-label">Stop</div><div class="risk-stop">{s.stop:,.2f}</div><div class="risk-amount">-${s.risk_dollars:,.0f}</div></div>
</div>'''
        h += '</div></div>'
        return h
    
    html += render_setups("CALLS") + render_setups("PUTS")
    
    score_desc = "🟢 Excellent" if day_score.total >= 80 else "🔵 Good" if day_score.total >= 60 else "🟠 Marginal" if day_score.total >= 40 else "🔴 Skip"
    html += f'''<div class="grid-2">
<div class="card"><div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')"><div class="card-title"><span>📈</span>Prior Session ({pivot_date.strftime("%b %d")})</div><span style="color:{text2}">▼</span></div><div class="card-content">
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px">
<div class="stat-box"><div class="stat-value green">{prior_session.get("high",0):,.2f}</div><div class="stat-label">High</div></div>
<div class="stat-box"><div class="stat-value red">{prior_session.get("low",0):,.2f}</div><div class="stat-label">Low</div></div>
<div class="stat-box"><div class="stat-value">{prior_session.get("close",0):,.2f}</div><div class="stat-label">Close</div></div>
<div class="stat-box"><div class="stat-value blue">{prior_session.get("high",0)-prior_session.get("low",0):,.0f}</div><div class="stat-label">Range</div></div>
</div></div></div>
<div class="card"><div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')"><div class="card-title"><span>🎯</span>Day Score</div><span style="color:{text2}">▼</span></div><div class="card-content" style="text-align:center">
<div class="score-circle" style="border-color:{day_score.color};color:{day_score.color}"><div class="score-value">{day_score.total}</div><div class="score-grade">{day_score.grade}</div></div>
<div style="font-size:13px;color:{text2}">{score_desc}</div>
</div></div></div>'''
    
    html += f'''<div class="card"><div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')"><div class="card-title"><span>📐</span>Structural Cones</div><span style="color:{text2}">▼</span></div><div class="card-content">
<table><thead><tr><th>Pivot</th><th>Ascending (Puts)</th><th>Descending (Calls)</th><th>Width</th><th>Tradeable</th></tr></thead><tbody>'''
    for c in cones:
        w_cls = "green" if c.width >= 25 else "amber" if c.width >= MIN_CONE_WIDTH else "red"
        pill = '<span class="pill pill-yes">YES</span>' if c.is_tradeable else '<span class="pill pill-no">NO</span>'
        html += f'<tr><td><strong>{c.name}</strong></td><td class="mono red">{c.ascending_rail:,.2f}</td><td class="mono green">{c.descending_rail:,.2f}</td><td class="mono {w_cls}">{c.width:.0f}</td><td>{pill}</td></tr>'
    html += '</tbody></table></div></div>'
    
    html += f'''<div class="card collapsed"><div class="card-header" onclick="this.parentElement.classList.toggle('collapsed')"><div class="card-title"><span>📋</span>Pivot Table</div><span style="color:{text2}">▼</span></div><div class="card-content">
<table><thead><tr><th>Time CT</th><th>High ▲</th><th>High ▼</th><th>Low ▲</th><th>Low ▼</th><th>Close ▲</th><th>Close ▼</th></tr></thead><tbody>'''
    for row in pivot_table:
        inst = "🏛️" if INST_WINDOW_START <= row.time_ct <= INST_WINDOW_END else ""
        bg_style = f"background:{amber}08" if inst else ""
        html += f'<tr style="{bg_style}"><td><strong>{row.time_block}{inst}</strong></td><td class="mono red">{row.prior_high_asc:,.2f}</td><td class="mono green">{row.prior_high_desc:,.2f}</td><td class="mono red">{row.prior_low_asc:,.2f}</td><td class="mono green">{row.prior_low_desc:,.2f}</td><td class="mono red">{row.prior_close_asc:,.2f}</td><td class="mono green">{row.prior_close_desc:,.2f}</td></tr>'
    html += '</tbody></table></div></div>'
    
    html += f'''<footer class="footer"><div style="font-weight:700;margin-bottom:8px">SPX Prophet v7.0 — Institutional Edition</div>
<div>Trading: {trading_date.strftime("%B %d, %Y")} • Pivot Anchor: {pivot_date.strftime("%B %d, %Y")} {f"({session_note})" if session_note else ""}</div></footer>
</div></body></html>'''
    return html

def main():
    st.set_page_config(page_title="SPX Prophet v7.0", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
    defaults = {'theme': 'dark', 'vix_bottom': 0.0, 'vix_top': 0.0, 'vix_current': 0.0, 'use_manual_pivots': False, 'high_price': 0.0, 'high_time': "10:30", 'low_price': 0.0, 'low_time': "14:00", 'close_price': 0.0, 'trading_date': None, 'last_refresh': None}
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    
    with st.sidebar:
        st.markdown("## 📈 SPX Prophet v7.0")
        st.caption("Institutional Edition")
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
        selected_date = st.date_input("Select", value=st.session_state.trading_date or next_trade, min_value=today - timedelta(days=730), max_value=today + timedelta(days=7))
        st.session_state.trading_date = selected_date
        if is_holiday(selected_date):
            st.error(f"🚫 {HOLIDAYS_2025.get(selected_date) or HOLIDAYS_2024.get(selected_date, 'Holiday')} - Closed")
        elif is_half_day(selected_date):
            st.warning(f"⏰ {HALF_DAYS_2025.get(selected_date) or HALF_DAYS_2024.get(selected_date, 'Half Day')} - 12pm CT")
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
    setups = generate_setups(cones, spx_price, trading_date, is_after_cutoff)
    day_score = calculate_day_score(vix_zone, cones, setups)
    pivot_table = build_pivot_table(pivots, trading_date)
    alerts = check_alerts(setups, vix_zone, now.time()) if not is_historical else []
    html = render_dashboard(vix_zone, cones, setups, pivot_table, prior_session, day_score, alerts, spx_price, trading_date, pivot_date, pivot_session_info, is_historical, st.session_state.theme)
    components.html(html, height=4000, scrolling=True)

if __name__ == "__main__":
    main()
