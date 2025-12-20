"""
SPX PROPHET v4.1 - Institutional Grade 0DTE SPX Options Decision Support System
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time, date
import yfinance as yf
import pytz
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="SPX Prophet",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# CONSTANTS
# =============================================================================

class Config:
    SLOPE_PER_30MIN = 0.45
    MIN_CONE_WIDTH = 18.0
    STOP_LOSS_PTS = 6.0
    STRIKE_OTM_DISTANCE = 17.5
    DELTA = 0.33
    CONTRACT_MULTIPLIER = 100
    TARGET_1_PCT = 0.125
    TARGET_2_PCT = 0.25
    TARGET_3_PCT = 0.50
    VIX_ZONE_LOW = 0.20
    VIX_ZONE_HIGH = 0.45
    ZONE_TOP_PCT = 75
    ZONE_BOTTOM_PCT = 25


class Phase(Enum):
    OVERNIGHT = ("Overnight Prep", "#3b82f6", "🌙", "Zone Building")
    ZONE_LOCK = ("Zone Lock", "#06b6d4", "🔒", "Analysis Mode")
    DANGER_ZONE = ("Danger Zone", "#f59e0b", "⚠️", "Caution Required")
    RTH = ("RTH Active", "#10b981", "🟢", "Execution Mode")
    POST_SESSION = ("Post-Session", "#8b5cf6", "📊", "Review Mode")
    MARKET_CLOSED = ("Market Closed", "#6b7280", "⭘", "Offline")
    
    def __init__(self, label, color, icon, mode):
        self.label = label
        self.color = color
        self.icon = icon
        self.mode = mode


class Bias(Enum):
    CALLS = ("CALLS", "#10b981", "📈")
    PUTS = ("PUTS", "#ef4444", "📉")
    WAIT = ("WAIT", "#f59e0b", "⏸️")
    
    def __init__(self, label, color, icon):
        self.label = label
        self.color = color
        self.icon = icon


class Confidence(Enum):
    STRONG = ("STRONG", "●●●●", "#10b981")
    MODERATE = ("MODERATE", "●●●○", "#f59e0b")
    WEAK = ("WEAK", "●●○○", "#ef4444")
    NO_TRADE = ("NO TRADE", "○○○○", "#6b7280")
    
    def __init__(self, label, dots, color):
        self.label = label
        self.dots = dots
        self.color = color


class LevelStatus(Enum):
    NOT_HIT = ("Not Hit", "○", "#6b7280")
    HIT = ("HIT", "✓", "#10b981")
    STOPPED = ("STOPPED", "✗", "#ef4444")
    
    def __init__(self, label, icon, color):
        self.label = label
        self.icon = icon
        self.color = color


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VIXZone:
    bottom: float
    top: float
    current: float
    
    @property
    def size(self):
        return round(self.top - self.bottom, 4)
    
    @property
    def position_pct(self):
        if self.size == 0:
            return 50.0
        return round(((self.current - self.bottom) / self.size) * 100, 1)
    
    @property
    def potential(self):
        if self.size < Config.VIX_ZONE_LOW:
            return "LOW"
        elif self.size < Config.VIX_ZONE_HIGH:
            return "NORMAL"
        return "HIGH"
    
    def get_extension(self, level):
        if level > 0:
            return round(self.top + (level * self.size), 2)
        return round(self.bottom + (level * self.size), 2)


@dataclass
class Pivot:
    name: str
    price: float
    timestamp: datetime
    pivot_type: str = "primary"
    enabled: bool = True


@dataclass
class ConeRails:
    pivot: Pivot
    ascending: float
    descending: float
    width: float
    blocks: int
    
    @property
    def is_tradeable(self):
        return self.width >= Config.MIN_CONE_WIDTH


@dataclass 
class TradeSetup:
    direction: Bias
    cone: ConeRails
    entry: float
    stop: float
    target_1: float
    target_2: float
    target_3: float
    strike: int
    
    @property
    def reward_1_pts(self):
        return abs(self.target_1 - self.entry)
    
    @property
    def reward_2_pts(self):
        return abs(self.target_2 - self.entry)
    
    @property
    def reward_3_pts(self):
        return abs(self.target_3 - self.entry)


@dataclass
class LevelHit:
    level_name: str
    level_price: float
    status: LevelStatus


# =============================================================================
# ENGINE
# =============================================================================

class SPXProphetEngine:
    def __init__(self):
        self.ct_tz = pytz.timezone('America/Chicago')
    
    def get_current_time_ct(self):
        return datetime.now(self.ct_tz)
    
    def get_phase(self, dt=None):
        if dt is None:
            dt = self.get_current_time_ct()
        elif dt.tzinfo is None:
            dt = self.ct_tz.localize(dt)
        else:
            dt = dt.astimezone(self.ct_tz)
        
        t = dt.time()
        weekday = dt.weekday()
        
        if weekday >= 5:
            return Phase.MARKET_CLOSED
        
        if time(17, 0) <= t or t < time(2, 0):
            return Phase.OVERNIGHT
        elif time(2, 0) <= t < time(6, 30):
            return Phase.ZONE_LOCK
        elif time(6, 30) <= t < time(9, 30):
            return Phase.DANGER_ZONE
        elif time(9, 30) <= t < time(16, 0):
            return Phase.RTH
        elif time(16, 0) <= t < time(17, 0):
            return Phase.POST_SESSION
        
        return Phase.MARKET_CLOSED
    
    def get_time_to_next_phase(self, dt=None):
        if dt is None:
            dt = self.get_current_time_ct()
        
        t = dt.time()
        today = dt.date()
        
        transitions = [
            (time(2, 0), Phase.ZONE_LOCK),
            (time(6, 30), Phase.DANGER_ZONE),
            (time(9, 30), Phase.RTH),
            (time(16, 0), Phase.POST_SESSION),
            (time(17, 0), Phase.OVERNIGHT),
        ]
        
        for trans_time, next_phase in transitions:
            if t < trans_time:
                next_dt = self.ct_tz.localize(datetime.combine(today, trans_time))
                return next_phase, next_dt - dt
        
        tomorrow = today + timedelta(days=1)
        next_dt = self.ct_tz.localize(datetime.combine(tomorrow, time(17, 0)))
        return Phase.OVERNIGHT, next_dt - dt
    
    def determine_bias(self, zone, phase):
        pos = zone.position_pct
        phase_penalty = 1 if phase == Phase.DANGER_ZONE else 0
        
        if pos >= Config.ZONE_TOP_PCT:
            bias = Bias.CALLS
            if pos >= 90:
                conf_level = max(0, 3 - phase_penalty)
            elif pos >= 80:
                conf_level = max(0, 2 - phase_penalty)
            else:
                conf_level = max(0, 1 - phase_penalty)
            confidence = [Confidence.NO_TRADE, Confidence.WEAK, Confidence.MODERATE, Confidence.STRONG][conf_level]
            explanation = f"VIX at TOP ({pos:.0f}%) - Expect VIX down, SPX UP"
            
        elif pos <= Config.ZONE_BOTTOM_PCT:
            bias = Bias.PUTS
            if pos <= 10:
                conf_level = max(0, 3 - phase_penalty)
            elif pos <= 20:
                conf_level = max(0, 2 - phase_penalty)
            else:
                conf_level = max(0, 1 - phase_penalty)
            confidence = [Confidence.NO_TRADE, Confidence.WEAK, Confidence.MODERATE, Confidence.STRONG][conf_level]
            explanation = f"VIX at BOTTOM ({pos:.0f}%) - Expect VIX up, SPX DOWN"
            
        else:
            bias = Bias.WAIT
            confidence = Confidence.NO_TRADE
            explanation = f"VIX mid-zone ({pos:.0f}%) - No edge, WAIT"
        
        if phase == Phase.DANGER_ZONE and bias != Bias.WAIT:
            explanation += " ⚠️ DANGER ZONE"
        
        return bias, confidence, explanation
    
    def calculate_blocks(self, pivot_time, eval_time):
        if pivot_time.tzinfo is None:
            pivot_time = self.ct_tz.localize(pivot_time)
        if eval_time.tzinfo is None:
            eval_time = self.ct_tz.localize(eval_time)
        
        diff = eval_time - pivot_time
        total_minutes = diff.total_seconds() / 60
        return max(int(total_minutes / 30), 1)
    
    def calculate_cone(self, pivot, eval_time):
        blocks = self.calculate_blocks(pivot.timestamp, eval_time)
        expansion = blocks * Config.SLOPE_PER_30MIN
        
        ascending = round(pivot.price + expansion, 2)
        descending = round(pivot.price - expansion, 2)
        width = round(ascending - descending, 2)
        
        return ConeRails(pivot=pivot, ascending=ascending, descending=descending, width=width, blocks=blocks)
    
    def generate_setup(self, cone, direction):
        if not cone.is_tradeable or direction == Bias.WAIT:
            return None
        
        if direction == Bias.CALLS:
            entry = cone.descending
            opposite = cone.ascending
            stop = entry - Config.STOP_LOSS_PTS
            strike = int(round((entry - Config.STRIKE_OTM_DISTANCE) / 5) * 5)
            move = opposite - entry
            t1 = entry + (move * Config.TARGET_1_PCT)
            t2 = entry + (move * Config.TARGET_2_PCT)
            t3 = entry + (move * Config.TARGET_3_PCT)
        else:
            entry = cone.ascending
            opposite = cone.descending
            stop = entry + Config.STOP_LOSS_PTS
            strike = int(round((entry + Config.STRIKE_OTM_DISTANCE) / 5) * 5)
            move = entry - opposite
            t1 = entry - (move * Config.TARGET_1_PCT)
            t2 = entry - (move * Config.TARGET_2_PCT)
            t3 = entry - (move * Config.TARGET_3_PCT)
        
        return TradeSetup(
            direction=direction, cone=cone, entry=round(entry, 2), stop=round(stop, 2),
            target_1=round(t1, 2), target_2=round(t2, 2), target_3=round(t3, 2), strike=strike
        )
    
    def calculate_profit(self, points, contracts=1):
        return round(points * Config.DELTA * Config.CONTRACT_MULTIPLIER * contracts, 2)
    
    def calculate_max_contracts(self, risk_budget):
        risk_per = self.calculate_profit(Config.STOP_LOSS_PTS, 1)
        return int(risk_budget / risk_per) if risk_per > 0 else 0
    
    def analyze_level_hits(self, setup, session_high, session_low):
        hits = []
        is_calls = setup.direction == Bias.CALLS
        
        entry_hit = (session_low <= setup.entry) if is_calls else (session_high >= setup.entry)
        hits.append(LevelHit("Entry", setup.entry, LevelStatus.HIT if entry_hit else LevelStatus.NOT_HIT))
        
        if entry_hit:
            if is_calls:
                stop_hit = session_low <= setup.stop
            else:
                stop_hit = session_high >= setup.stop
            hits.append(LevelHit("Stop", setup.stop, LevelStatus.STOPPED if stop_hit else LevelStatus.NOT_HIT))
            
            for name, price in [("12.5%", setup.target_1), ("25%", setup.target_2), ("50%", setup.target_3)]:
                if is_calls:
                    target_hit = session_high >= price
                else:
                    target_hit = session_low <= price
                hits.append(LevelHit(name, price, LevelStatus.HIT if target_hit else LevelStatus.NOT_HIT))
        else:
            hits.append(LevelHit("Stop", setup.stop, LevelStatus.NOT_HIT))
            hits.append(LevelHit("12.5%", setup.target_1, LevelStatus.NOT_HIT))
            hits.append(LevelHit("25%", setup.target_2, LevelStatus.NOT_HIT))
            hits.append(LevelHit("50%", setup.target_3, LevelStatus.NOT_HIT))
        
        return hits
    
    def calculate_theoretical_pnl(self, setup, hits, contracts=1):
        entry_hit = any(h.level_name == "Entry" and h.status == LevelStatus.HIT for h in hits)
        if not entry_hit:
            return 0.0, "Entry not reached"
        
        stop_hit = any(h.level_name == "Stop" and h.status == LevelStatus.STOPPED for h in hits)
        if stop_hit:
            return -self.calculate_profit(Config.STOP_LOSS_PTS, contracts), "Stopped out"
        
        target_hits = [(h.level_name, h.level_price) for h in hits 
                       if h.level_name in ["12.5%", "25%", "50%"] and h.status == LevelStatus.HIT]
        
        if not target_hits:
            return 0.0, "Entry hit, targets pending"
        
        target_map = {"12.5%": Config.TARGET_1_PCT, "25%": Config.TARGET_2_PCT, "50%": Config.TARGET_3_PCT}
        highest = max(target_hits, key=lambda x: target_map.get(x[0], 0))
        points = abs(highest[1] - setup.entry)
        
        return self.calculate_profit(points, contracts), f"{highest[0]} target hit"


# =============================================================================
# DATA FETCHING
# =============================================================================

@st.cache_data(ttl=60)
def fetch_live_data():
    try:
        spx = yf.Ticker("^GSPC")
        vix = yf.Ticker("^VIX")
        
        spx_hist = spx.history(period="5d")
        vix_hist = vix.history(period="1d")
        
        spx_price = float(spx_hist['Close'].iloc[-1]) if not spx_hist.empty else None
        vix_price = float(vix_hist['Close'].iloc[-1]) if not vix_hist.empty else None
        
        prior_data = None
        if len(spx_hist) >= 2:
            prior = spx_hist.iloc[-2]
            prior_data = {
                'date': spx_hist.index[-2],
                'high': float(prior['High']),
                'low': float(prior['Low']),
                'close': float(prior['Close']),
                'open': float(prior['Open'])
            }
        
        return spx_price, vix_price, prior_data
    except Exception:
        return None, None, None


@st.cache_data(ttl=300)
def fetch_historical_data(target_date):
    try:
        spx = yf.Ticker("^GSPC")
        start = target_date - timedelta(days=5)
        end = target_date + timedelta(days=1)
        hist = spx.history(start=start, end=end)
        
        if hist.empty:
            return None
        
        target_str = target_date.strftime('%Y-%m-%d')
        for idx in hist.index:
            if idx.strftime('%Y-%m-%d') == target_str:
                row = hist.loc[idx]
                return {
                    'date': idx,
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'range': float(row['High'] - row['Low'])
                }
        return None
    except Exception:
        return None


# =============================================================================
# STYLES
# =============================================================================

def inject_styles():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap');
    
    .stApp { background-color: #0f172a; }
    
    [data-testid="stSidebar"] {
        background-color: #1e293b;
        border-right: 1px solid #334155;
    }
    
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    footer { visibility: hidden; }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_header(spx, vix, phase, engine):
    now = engine.get_current_time_ct()
    next_phase, time_remaining = engine.get_time_to_next_phase(now)
    
    hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    countdown = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1.5, 1.5])
    
    with col1:
        st.markdown("## SPX PROPHET")
        st.caption("Institutional 0DTE System")
    
    with col2:
        st.metric("SPX", f"{spx:,.2f}")
    
    with col3:
        st.metric("VIX", f"{vix:.2f}")
    
    with col4:
        st.metric("Time (CT)", now.strftime('%I:%M %p'))
        st.caption(f"{phase.icon} {phase.label}")
    
    with col5:
        st.metric(f"Next: {next_phase.label}", countdown)


def render_bias_card(bias, confidence, explanation, phase):
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if phase == Phase.DANGER_ZONE and bias != Bias.WAIT:
            st.warning(f"⚠️ DANGER ZONE - {bias.icon} {bias.label} bias with caution")
        
        st.markdown(f"### {bias.icon} Today's Bias: **{bias.label}**")
        st.markdown(f"Confidence: `{confidence.dots}` **{confidence.label}**")
        st.info(explanation)


def render_vix_zone(zone):
    st.markdown("#### 📊 VIX Zone Ladder")
    
    potential_emoji = {"LOW": "⚠️", "NORMAL": "✓", "HIGH": "🔥"}.get(zone.potential, "")
    
    data = []
    data.append({"Level": "+2", "Price": f"{zone.get_extension(2):.2f}", "Type": "Extension"})
    data.append({"Level": "+1", "Price": f"{zone.get_extension(1):.2f}", "Type": "Extension"})
    data.append({"Level": "TOP", "Price": f"{zone.top:.2f}", "Type": "Zone Edge"})
    data.append({"Level": "VIX NOW", "Price": f"{zone.current:.2f}", "Type": "Current"})
    data.append({"Level": "BOTTOM", "Price": f"{zone.bottom:.2f}", "Type": "Zone Edge"})
    data.append({"Level": "-1", "Price": f"{zone.get_extension(-1):.2f}", "Type": "Extension"})
    data.append({"Level": "-2", "Price": f"{zone.get_extension(-2):.2f}", "Type": "Extension"})
    
    st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Zone Size", f"{zone.size:.2f}")
    col2.metric("Position", f"{zone.position_pct:.0f}%")
    col3.metric("Potential", f"{potential_emoji} {zone.potential}")


def render_checklist(zone, phase, setup, price):
    st.markdown("#### ✅ Entry Checklist")
    
    checks = [
        ("VIX at zone edge", zone.position_pct >= 75 or zone.position_pct <= 25),
        ("Reliable timing window", phase in [Phase.ZONE_LOCK, Phase.RTH]),
        ("30-min candle closed", True),
        ("Price at entry (within 5 pts)", setup and abs(price - setup.entry) <= 5.0),
        ("Cone width ≥ 18 pts", setup and setup.cone.is_tradeable if setup else False)
    ]
    
    for label, passed in checks:
        icon = "✅" if passed else "⬜"
        st.markdown(f"{icon} {label}")
    
    if all(p for _, p in checks):
        st.success("**READY TO ENTER**")
    else:
        st.warning("**WAITING FOR CONDITIONS**")


def render_cone_table(cones, best_name):
    st.markdown("#### 📐 Cone Rails")
    
    data = []
    for c in cones:
        status = "⭐ BEST" if c.pivot.name == best_name else ("✓" if c.is_tradeable else "✗")
        data.append({
            "Pivot": c.pivot.name,
            "Ascending": f"{c.ascending:,.2f}",
            "Descending": f"{c.descending:,.2f}",
            "Width": f"{c.width:.1f}",
            "Blocks": c.blocks,
            "Status": status
        })
    
    if data:
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)


def render_setup_card(setup, price, engine, is_best=False):
    badge = "⭐ BEST SETUP" if is_best else ""
    st.markdown(f"##### {setup.direction.icon} {setup.direction.label} Setup - {setup.cone.pivot.name} {badge}")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Entry", f"{setup.entry:,.2f}")
    col2.metric("Stop", f"{setup.stop:,.2f}")
    col3.metric("12.5%", f"{setup.target_1:,.2f}")
    col4.metric("25%", f"{setup.target_2:,.2f}")
    col5.metric("50%", f"{setup.target_3:,.2f}")
    
    distance = price - setup.entry
    p2 = engine.calculate_profit(setup.reward_2_pts, 1)
    risk = engine.calculate_profit(Config.STOP_LOSS_PTS, 1)
    rr = p2 / risk if risk > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.caption(f"Distance: **{distance:+.2f}** pts")
    col2.caption(f"Strike: **{setup.strike}**")
    col3.caption(f"R:R @25%: **{rr:.1f}:1**")
    col4.caption(f"Profit @25%: **${p2:,.0f}**")
    
    st.markdown("---")


def render_position_calculator(engine, setup):
    st.markdown("#### 💰 Position Calculator")
    
    risk_budget = st.number_input("Risk Budget ($)", 100, 100000, 1000, 100)
    
    if setup:
        contracts = engine.calculate_max_contracts(risk_budget)
        risk_total = engine.calculate_profit(Config.STOP_LOSS_PTS, contracts)
        p1 = engine.calculate_profit(setup.reward_1_pts, contracts)
        p2 = engine.calculate_profit(setup.reward_2_pts, contracts)
        p3 = engine.calculate_profit(setup.reward_3_pts, contracts)
        
        st.metric("Max Contracts", contracts)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Risk", f"${risk_total:,.0f}")
        col2.metric("@ 12.5%", f"${p1:,.0f}")
        col3.metric("@ 25%", f"${p2:,.0f}")
        col4.metric("@ 50%", f"${p3:,.0f}")


def render_historical_analysis(session_data, setup, hits, pnl, pnl_note, engine):
    st.markdown("#### 📊 Session Stats")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Open", f"{session_data['open']:,.2f}")
    col2.metric("High", f"{session_data['high']:,.2f}")
    col3.metric("Low", f"{session_data['low']:,.2f}")
    col4.metric("Close", f"{session_data['close']:,.2f}")
    col5.metric("Range", f"{session_data['range']:.2f}")
    
    st.markdown("##### Level Hits")
    for hit in hits:
        st.markdown(f"{hit.status.icon} **{hit.level_name}**: {hit.level_price:,.2f} - {hit.status.label}")
    
    pnl_display = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
    st.metric("Theoretical P&L (1 contract)", pnl_display, delta=pnl_note)


def render_trade_rules():
    st.markdown("#### 📖 Trade Rules")
    st.markdown("""
    **Entry:** CALLS at descending rail • PUTS at ascending rail
    
    **Stop:** 6 points from entry
    
    **Targets:** 12.5% → 25% → 50% of cone width
    
    **Confirmation:** Wait for 30-min candle CLOSE
    
    **⚠️ Danger Zone:** 6:30-9:30 AM CT - Reversals common
    """)


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar(engine, prior_data):
    st.sidebar.markdown("## ⚙️ Configuration")
    
    st.sidebar.markdown("#### 📌 Mode")
    mode = st.sidebar.radio("Mode", ["Live Trading", "Historical Analysis"], horizontal=True, label_visibility="collapsed")
    
    st.sidebar.markdown("---")
    
    st.sidebar.markdown("#### 📅 Session Date")
    ct_tz = pytz.timezone('America/Chicago')
    today = datetime.now(ct_tz).date()
    
    if mode == "Live Trading":
        session_date = today
        st.sidebar.info(f"Today: {session_date}")
    else:
        session_date = st.sidebar.date_input("Date", today - timedelta(days=1), max_value=today)
    
    st.sidebar.markdown("---")
    
    st.sidebar.markdown("#### 📊 VIX Zone")
    c1, c2 = st.sidebar.columns(2)
    vix_bottom = c1.number_input("Bottom", 5.0, 100.0, 16.50, 0.01, format="%.2f")
    vix_top = c2.number_input("Top", 5.0, 100.0, 16.65, 0.01, format="%.2f")
    vix_current = st.sidebar.number_input("Current VIX", 5.0, 100.0, 16.55, 0.01, format="%.2f")
    
    zone = VIXZone(vix_bottom, vix_top, vix_current)
    
    st.sidebar.markdown("---")
    
    st.sidebar.markdown("#### 📍 Prior Day Pivots")
    manual = st.sidebar.checkbox("Manual Input", False)
    
    prior_date = session_date - timedelta(days=1)
    if prior_date.weekday() >= 5:
        prior_date -= timedelta(days=prior_date.weekday() - 4)
    
    if manual or prior_data is None:
        c1, c2 = st.sidebar.columns(2)
        p_high = c1.number_input("High", 1000.0, 10000.0, 6050.0, 1.0)
        p_high_t = c2.time_input("High Time", time(11, 30))
        c1, c2 = st.sidebar.columns(2)
        p_low = c1.number_input("Low", 1000.0, 10000.0, 6020.0, 1.0)
        p_low_t = c2.time_input("Low Time", time(14, 0))
        p_close = st.sidebar.number_input("Close", 1000.0, 10000.0, 6035.0, 1.0)
    else:
        p_high = prior_data['high']
        p_low = prior_data['low']
        p_close = prior_data['close']
        prior_date = prior_data['date'].date() if hasattr(prior_data['date'], 'date') else prior_data['date']
        p_high_t = time(11, 30)
        p_low_t = time(14, 0)
        st.sidebar.success(f"Loaded: {prior_date}")
    
    pivots = [
        Pivot("Prior High", p_high, ct_tz.localize(datetime.combine(prior_date, p_high_t))),
        Pivot("Prior Low", p_low, ct_tz.localize(datetime.combine(prior_date, p_low_t))),
        Pivot("Prior Close", p_close, ct_tz.localize(datetime.combine(prior_date, time(16, 0))))
    ]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 📍 Secondary Pivots")
    
    if st.sidebar.checkbox("Enable High²"):
        c1, c2 = st.sidebar.columns(2)
        h2_p = c1.number_input("High² Price", 1000.0, 10000.0, p_high - 10, 1.0)
        h2_t = c2.time_input("High² Time", time(10, 0))
        pivots.append(Pivot("High²", h2_p, ct_tz.localize(datetime.combine(prior_date, h2_t)), "secondary"))
    
    if st.sidebar.checkbox("Enable Low²"):
        c1, c2 = st.sidebar.columns(2)
        l2_p = c1.number_input("Low² Price", 1000.0, 10000.0, p_low + 10, 1.0)
        l2_t = c2.time_input("Low² Time", time(13, 0))
        pivots.append(Pivot("Low²", l2_p, ct_tz.localize(datetime.combine(prior_date, l2_t)), "secondary"))
    
    st.sidebar.markdown("---")
    st.sidebar.caption("SPX Prophet v4.1")
    
    return mode, session_date, zone, pivots


# =============================================================================
# MAIN
# =============================================================================

def main():
    inject_styles()
    engine = SPXProphetEngine()
    ct_tz = pytz.timezone('America/Chicago')
    
    spx_live, vix_live, prior_data = fetch_live_data()
    spx_price = spx_live or 6000.0
    vix_price = vix_live or 16.50
    
    mode, session_date, zone, pivots = render_sidebar(engine, prior_data)
    
    if mode == "Live Trading" and vix_live:
        zone = VIXZone(zone.bottom, zone.top, vix_live)
    
    now = engine.get_current_time_ct()
    phase = engine.get_phase(now)
    bias, confidence, explanation = engine.determine_bias(zone, phase)
    
    if mode == "Live Trading":
        eval_time = ct_tz.localize(datetime.combine(now.date(), time(10, 0)))
        if now.time() > time(10, 0):
            eval_time = now
    else:
        eval_time = ct_tz.localize(datetime.combine(session_date, time(10, 0)))
    
    cones = [engine.calculate_cone(p, eval_time) for p in pivots]
    valid_cones = [c for c in cones if c.is_tradeable]
    best_cone = max(valid_cones, key=lambda x: x.width) if valid_cones else None
    best_name = best_cone.pivot.name if best_cone else ""
    
    setups = []
    for cone in cones:
        if cone.is_tradeable:
            setup = engine.generate_setup(cone, bias)
            if setup:
                setups.append(setup)
    
    best_setup = next((s for s in setups if s.cone.pivot.name == best_name), None)
    
    # RENDER
    render_header(spx_price, vix_price, phase, engine)
    
    if mode == "Live Trading":
        render_bias_card(bias, confidence, explanation, phase)
        
        col1, col2 = st.columns(2)
        with col1:
            render_vix_zone(zone)
        with col2:
            render_checklist(zone, phase, best_setup, spx_price)
        
        render_cone_table(cones, best_name)
        
        if bias != Bias.WAIT and setups:
            st.markdown(f"### {bias.icon} {bias.label} Setups")
            for setup in setups:
                render_setup_card(setup, spx_price, engine, setup.cone.pivot.name == best_name)
        else:
            st.info("VIX mid-zone. Waiting for edge...")
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            render_position_calculator(engine, best_setup)
        with col2:
            render_trade_rules()
    
    else:
        st.markdown(f"### 📊 Historical: {session_date}")
        session_data = fetch_historical_data(session_date)
        
        if session_data:
            render_bias_card(bias, confidence, explanation, Phase.POST_SESSION)
            
            col1, col2 = st.columns(2)
            with col1:
                render_vix_zone(zone)
            with col2:
                if best_setup:
                    hits = engine.analyze_level_hits(best_setup, session_data['high'], session_data['low'])
                    pnl, note = engine.calculate_theoretical_pnl(best_setup, hits)
                    render_historical_analysis(session_data, best_setup, hits, pnl, note, engine)
            
            render_cone_table(cones, best_name)
            
            if setups:
                st.markdown("### Setup Analysis")
                for setup in setups:
                    render_setup_card(setup, session_data['close'], engine, setup.cone.pivot.name == best_name)
                    hits = engine.analyze_level_hits(setup, session_data['high'], session_data['low'])
                    pnl, note = engine.calculate_theoretical_pnl(setup, hits)
                    st.caption(f"Result: {note} | P&L: ${pnl:,.2f}")
        else:
            st.error(f"No data for {session_date}")
    
    st.markdown("---")
    st.caption("SPX Prophet v4.1 | Data: Yahoo Finance | Not Financial Advice")


if __name__ == "__main__":
    main()