"""
SPX PROPHET v4.2 - Institutional Grade 0DTE SPX Options Decision Support System
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time, date
import yfinance as yf
import pytz
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
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
# STYLES - Using regular string (not f-string) to avoid CSS parsing issues
# =============================================================================

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

.stApp {
    background: #0a0f1a;
}

[data-testid="stSidebar"] {
    background: #1e293b;
    border-right: 1px solid #334155;
}

[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3,
[data-testid="stSidebar"] .stMarkdown h4 {
    color: #f8fafc;
}

[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace;
    color: #f8fafc;
}

[data-testid="stMetricLabel"] {
    color: #94a3b8;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.5px;
}

.stDataFrame {
    border-radius: 8px;
}

footer {visibility: hidden;}

.prophet-card {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
}

.prophet-header {
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
}

.prophet-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.75rem;
    font-weight: 700;
    color: #f8fafc;
    margin: 0;
    letter-spacing: -0.5px;
}

.prophet-subtitle {
    font-family: 'Inter', sans-serif;
    font-size: 0.7rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 4px 0 0 0;
}

.prophet-value-large {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.4rem;
    font-weight: 700;
    color: #f8fafc;
    margin: 0;
}

.prophet-value-medium {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1rem;
    font-weight: 600;
    color: #f8fafc;
    margin: 0;
}

.prophet-value-small {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    font-weight: 600;
    color: #f8fafc;
    margin: 0;
}

.prophet-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.65rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 0;
}

.prophet-text {
    font-family: 'Inter', sans-serif;
    font-size: 0.8rem;
    color: #cbd5e1;
    margin: 0;
}

.prophet-text-muted {
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    color: #94a3b8;
    margin: 0;
}

.bias-calls {
    background: linear-gradient(135deg, #064e3b 0%, #1e293b 100%);
    border: 2px solid #10b981;
}

.bias-puts {
    background: linear-gradient(135deg, #7f1d1d 0%, #1e293b 100%);
    border: 2px solid #ef4444;
}

.bias-wait {
    background: linear-gradient(135deg, #78350f 0%, #1e293b 100%);
    border: 2px solid #f59e0b;
}

.level-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 14px;
    margin: 3px 0;
    border-radius: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
}

.level-extension {
    background: #1e293b;
    color: #64748b;
}

.level-top {
    background: #064e3b;
    color: #10b981;
    border: 1px solid #10b981;
}

.level-bottom {
    background: #7f1d1d;
    color: #ef4444;
    border: 1px solid #ef4444;
}

.level-current {
    background: #1e3a8a;
    color: #60a5fa;
    border: 2px solid #3b82f6;
    font-weight: 600;
}

.check-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid #1e293b;
}

.setup-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 8px;
    margin-bottom: 14px;
}

.setup-box {
    background: rgba(0,0,0,0.3);
    border-radius: 6px;
    padding: 10px 6px;
    text-align: center;
}

.stats-row {
    display: flex;
    justify-content: space-between;
    padding-top: 12px;
    border-top: 1px solid #334155;
}

.stat-item {
    text-align: center;
}
</style>
"""

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

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
    CALLS = ("CALLS", "#10b981", "📈", "bias-calls")
    PUTS = ("PUTS", "#ef4444", "📉", "bias-puts")
    WAIT = ("WAIT", "#f59e0b", "⏸️", "bias-wait")
    
    def __init__(self, label, color, icon, css_class):
        self.label = label
        self.color = color
        self.icon = icon
        self.css_class = css_class


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
    
    @property
    def potential_config(self):
        configs = {
            "LOW": ("⚠️", "#f59e0b"),
            "NORMAL": ("✓", "#3b82f6"),
            "HIGH": ("🔥", "#10b981")
        }
        return configs.get(self.potential, ("", "#64748b"))
    
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
    
    def get_phase_guidance(self, phase):
        guidance = {
            Phase.OVERNIGHT: "Monitor VIX to establish zone boundaries",
            Phase.ZONE_LOCK: "Zone locked. Identify cone entries. Reliable window.",
            Phase.DANGER_ZONE: "⚠️ VIX reversals common. Await confirmation.",
            Phase.RTH: "Execute setups when checklist complete.",
            Phase.POST_SESSION: "Review session performance.",
            Phase.MARKET_CLOSED: "Use historical mode for past sessions."
        }
        return guidance.get(phase, "")
    
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
            explanation = "VIX at TOP - Expect VIX down, SPX UP"
            
        elif pos <= Config.ZONE_BOTTOM_PCT:
            bias = Bias.PUTS
            if pos <= 10:
                conf_level = max(0, 3 - phase_penalty)
            elif pos <= 20:
                conf_level = max(0, 2 - phase_penalty)
            else:
                conf_level = max(0, 1 - phase_penalty)
            confidence = [Confidence.NO_TRADE, Confidence.WEAK, Confidence.MODERATE, Confidence.STRONG][conf_level]
            explanation = "VIX at BOTTOM - Expect VIX up, SPX DOWN"
            
        else:
            bias = Bias.WAIT
            confidence = Confidence.NO_TRADE
            explanation = "VIX mid-zone - No edge, WAIT"
        
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
            stop_hit = (session_low <= setup.stop) if is_calls else (session_high >= setup.stop)
            hits.append(LevelHit("Stop", setup.stop, LevelStatus.STOPPED if stop_hit else LevelStatus.NOT_HIT))
            
            for name, price in [("12.5%", setup.target_1), ("25%", setup.target_2), ("50%", setup.target_3)]:
                target_hit = (session_high >= price) if is_calls else (session_low <= price)
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
        
        return self.calculate_profit(points, contracts), highest[0] + " target hit"


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
        start = target_date - timedelta(days=10)
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


@st.cache_data(ttl=300)
def fetch_prior_day_data(session_date):
    """Fetch the trading day BEFORE the given session date (for pivots)"""
    try:
        spx = yf.Ticker("^GSPC")
        # Fetch 10 days of history to account for weekends/holidays
        start = session_date - timedelta(days=10)
        end = session_date + timedelta(days=1)
        hist = spx.history(start=start, end=end)
        
        if hist.empty or len(hist) < 2:
            return None
        
        # Find the session date in the index
        session_str = session_date.strftime('%Y-%m-%d')
        session_idx = None
        
        for i, idx in enumerate(hist.index):
            if idx.strftime('%Y-%m-%d') == session_str:
                session_idx = i
                break
        
        # If session found and there's a prior day
        if session_idx is not None and session_idx > 0:
            prior_idx = hist.index[session_idx - 1]
            prior = hist.iloc[session_idx - 1]
            return {
                'date': prior_idx,
                'high': float(prior['High']),
                'low': float(prior['Low']),
                'close': float(prior['Close']),
                'open': float(prior['Open'])
            }
        
        # If session not found (might be today or future), get the last available prior day
        # This handles the "live" case where session_date = today
        if len(hist) >= 2:
            prior = hist.iloc[-2]
            return {
                'date': hist.index[-2],
                'high': float(prior['High']),
                'low': float(prior['Low']),
                'close': float(prior['Close']),
                'open': float(prior['Open'])
            }
        
        return None
    except Exception:
        return None


# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_header(spx, vix, phase, engine):
    now = engine.get_current_time_ct()
    next_phase, time_remaining = engine.get_time_to_next_phase(now)
    
    hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    countdown = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    guidance = engine.get_phase_guidance(phase)
    
    html = f"""
    <div class="prophet-header">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
            <div>
                <h1 class="prophet-title">SPX PROPHET</h1>
                <p class="prophet-subtitle">Institutional 0DTE Decision System</p>
            </div>
            <div style="display: flex; gap: 24px; align-items: center;">
                <div style="text-align: right;">
                    <p class="prophet-label">SPX</p>
                    <p class="prophet-value-large">{spx:,.2f}</p>
                </div>
                <div style="text-align: right;">
                    <p class="prophet-label">VIX</p>
                    <p class="prophet-value-large">{vix:.2f}</p>
                </div>
                <div style="text-align: right; border-left: 1px solid #334155; padding-left: 24px;">
                    <p class="prophet-label">{now.strftime('%I:%M:%S %p')} CT</p>
                    <p class="prophet-value-medium" style="color: {phase.color};">{phase.icon} {phase.label}</p>
                </div>
                <div style="text-align: right; background: rgba(0,0,0,0.3); padding: 8px 12px; border-radius: 8px;">
                    <p class="prophet-label">Next: {next_phase.label}</p>
                    <p class="prophet-value-medium" style="color: {next_phase.color};">{countdown}</p>
                </div>
            </div>
        </div>
        <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #334155;">
            <p class="prophet-text-muted"><span style="color: {phase.color}; font-weight: 600;">{phase.mode}</span> — {guidance}</p>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_bias_card(bias, confidence, explanation, zone, phase):
    danger_warning = ""
    if phase == Phase.DANGER_ZONE and bias != Bias.WAIT:
        danger_warning = '<p style="font-size: 0.7rem; color: #f59e0b; margin-top: 12px;">⚠️ DANGER ZONE - Await confirmation before entry</p>'
    
    html = f"""
    <div class="prophet-card {bias.css_class}" style="text-align: center; border-width: 2px;">
        <p class="prophet-label" style="letter-spacing: 2px; margin-bottom: 8px;">Today's Bias</p>
        <h2 style="font-family: 'JetBrains Mono', monospace; font-size: 2.5rem; font-weight: 700; color: {bias.color}; margin: 0; letter-spacing: 3px;">{bias.icon} {bias.label}</h2>
        <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; color: {confidence.color}; margin: 12px 0 4px 0; letter-spacing: 3px;">{confidence.dots}</p>
        <p style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: {confidence.color}; margin: 0;">{confidence.label}</p>
        <div style="margin-top: 16px; padding: 12px; background: rgba(0,0,0,0.3); border-radius: 8px;">
            <p class="prophet-text">{explanation} ({zone.position_pct:.0f}% in zone)</p>
        </div>
        {danger_warning}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_vix_zone(zone):
    pot_emoji, pot_color = zone.potential_config
    
    levels = [
        ("+2", zone.get_extension(2), "level-extension"),
        ("+1", zone.get_extension(1), "level-extension"),
        ("TOP", zone.top, "level-top"),
        (f"VIX {zone.current:.2f}", zone.current, "level-current"),
        ("BOTTOM", zone.bottom, "level-bottom"),
        ("-1", zone.get_extension(-1), "level-extension"),
        ("-2", zone.get_extension(-2), "level-extension"),
    ]
    
    rows_html = ""
    for label, value, css_class in levels:
        rows_html += f'<div class="level-row {css_class}"><span>{label}</span><span>{value:.2f}</span></div>'
    
    html = f"""
    <div class="prophet-card">
        <p class="prophet-label" style="margin-bottom: 12px;">📊 VIX Zone Ladder</p>
        {rows_html}
        <div style="display: flex; justify-content: space-between; margin-top: 14px; padding-top: 14px; border-top: 1px solid #334155;">
            <div style="text-align: center; flex: 1;">
                <p class="prophet-label">Size</p>
                <p class="prophet-value-small">{zone.size:.2f}</p>
            </div>
            <div style="text-align: center; flex: 1;">
                <p class="prophet-label">Position</p>
                <p class="prophet-value-small">{zone.position_pct:.0f}%</p>
            </div>
            <div style="text-align: center; flex: 1;">
                <p class="prophet-label">Potential</p>
                <p class="prophet-value-small" style="color: {pot_color};">{pot_emoji} {zone.potential}</p>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_checklist(zone, phase, setup, price):
    checks = [
        ("VIX at zone edge (≤25% or ≥75%)", zone.position_pct >= 75 or zone.position_pct <= 25, f"{zone.position_pct:.0f}%"),
        ("Reliable timing window", phase in [Phase.ZONE_LOCK, Phase.RTH], phase.label),
        ("30-min candle closed", True, "Manual check"),
        ("Price at entry (within 5 pts)", setup and abs(price - setup.entry) <= 5.0, f"{abs(price - setup.entry):.1f} pts" if setup else "No setup"),
        ("Cone width ≥ 18 pts", setup and setup.cone.is_tradeable if setup else False, f"{setup.cone.width:.1f}" if setup else "No setup")
    ]
    
    items_html = ""
    for label, passed, note in checks:
        icon = "✓" if passed else "○"
        icon_color = "#10b981" if passed else "#475569"
        text_color = "#e2e8f0" if passed else "#64748b"
        items_html += f"""
        <div class="check-item">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.1rem; color: {icon_color};">{icon}</span>
                <span style="font-family: 'Inter', sans-serif; font-size: 0.8rem; color: {text_color};">{label}</span>
            </div>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #64748b;">{note}</span>
        </div>
        """
    
    all_pass = all(p for _, p, _ in checks)
    status_bg = "#064e3b" if all_pass else "#1e293b"
    status_color = "#10b981" if all_pass else "#64748b"
    status_border = "#10b981" if all_pass else "#334155"
    status_text = "✓ READY TO ENTER" if all_pass else "WAITING FOR CONDITIONS"
    
    html = f"""
    <div class="prophet-card">
        <p class="prophet-label" style="margin-bottom: 12px;">✅ Entry Checklist</p>
        {items_html}
        <div style="margin-top: 14px; padding: 12px; background: {status_bg}; border-radius: 8px; text-align: center; border: 1px solid {status_border};">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.8rem; font-weight: 600; color: {status_color}; margin: 0; text-transform: uppercase; letter-spacing: 1px;">{status_text}</p>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_cone_table(cones, best_name):
    st.markdown('<p class="prophet-label" style="margin: 20px 0 10px 0;">📐 Cone Rails</p>', unsafe_allow_html=True)
    
    data = []
    for c in cones:
        status = "⭐ BEST" if c.pivot.name == best_name else ("✓ Valid" if c.is_tradeable else "✗ Narrow")
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
    best_badge = '<span style="background: #fbbf24; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 0.6rem; font-weight: 600; margin-left: 8px;">⭐ BEST</span>' if is_best else ''
    
    distance = price - setup.entry
    dist_color = "#10b981" if abs(distance) <= 10 else "#64748b"
    
    p1 = engine.calculate_profit(setup.reward_1_pts, 1)
    p2 = engine.calculate_profit(setup.reward_2_pts, 1)
    p3 = engine.calculate_profit(setup.reward_3_pts, 1)
    risk = engine.calculate_profit(Config.STOP_LOSS_PTS, 1)
    rr = p2 / risk if risk > 0 else 0
    
    def box(label, value, highlight=False, is_stop=False):
        border = f"border: 1px solid {setup.direction.color};" if highlight else ("border: 1px solid #ef4444;" if is_stop else "")
        return f"""<div class="setup-box" style="{border}">
            <p class="prophet-label" style="margin-bottom: 4px;">{label}</p>
            <p class="prophet-value-small">{value:,.2f}</p>
        </div>"""
    
    def stat(label, value, color="#f8fafc"):
        return f"""<div class="stat-item">
            <p class="prophet-label">{label}</p>
            <p class="prophet-value-small" style="color: {color}; margin-top: 2px;">{value}</p>
        </div>"""
    
    html = f"""
    <div class="prophet-card {setup.direction.css_class}" style="border-width: 2px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 1rem; font-weight: 700; color: {setup.direction.color};">{setup.direction.icon} {setup.direction.label} SETUP{best_badge}</span>
            <span class="prophet-text-muted">{setup.cone.pivot.name} Cone</span>
        </div>
        <div class="setup-grid">
            {box("Entry", setup.entry, True)}
            {box("Stop", setup.stop, False, True)}
            {box("12.5%", setup.target_1)}
            {box("25%", setup.target_2)}
            {box("50%", setup.target_3)}
        </div>
        <div class="stats-row">
            {stat("Distance", f"{distance:+.2f} pts", dist_color)}
            {stat("Strike", str(setup.strike))}
            {stat("Width", f"{setup.cone.width:.1f}")}
            {stat("R:R @25%", f"{rr:.1f}:1")}
            {stat("Profit @25%", f"${p2:,.0f}", "#10b981")}
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_position_calculator(engine, setup):
    st.markdown('<p class="prophet-label" style="margin-bottom: 12px;">💰 Position Calculator</p>', unsafe_allow_html=True)
    
    risk_budget = st.number_input("Risk Budget ($)", 100, 100000, 1000, 100, label_visibility="collapsed")
    st.caption("Risk Budget ($)")
    
    if setup:
        contracts = engine.calculate_max_contracts(risk_budget)
        risk_total = engine.calculate_profit(Config.STOP_LOSS_PTS, contracts)
        p1 = engine.calculate_profit(setup.reward_1_pts, contracts)
        p2 = engine.calculate_profit(setup.reward_2_pts, contracts)
        p3 = engine.calculate_profit(setup.reward_3_pts, contracts)
        
        html = f"""
        <div style="background: #1e293b; border-radius: 8px; padding: 14px; text-align: center; margin: 12px 0; border: 1px solid #334155;">
            <p class="prophet-label">Max Contracts</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 700; color: #10b981; margin: 4px 0 0 0;">{contracts}</p>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            <div style="background: #1e293b; border-radius: 6px; padding: 10px; border: 1px solid #334155;">
                <p class="prophet-label">Risk</p>
                <p class="prophet-value-small" style="color: #ef4444; margin-top: 4px;">${risk_total:,.0f}</p>
            </div>
            <div style="background: #1e293b; border-radius: 6px; padding: 10px; border: 1px solid #334155;">
                <p class="prophet-label">@ 12.5%</p>
                <p class="prophet-value-small" style="color: #10b981; margin-top: 4px;">${p1:,.0f}</p>
            </div>
            <div style="background: #1e293b; border-radius: 6px; padding: 10px; border: 1px solid #334155;">
                <p class="prophet-label">@ 25%</p>
                <p class="prophet-value-small" style="color: #10b981; margin-top: 4px;">${p2:,.0f}</p>
            </div>
            <div style="background: #1e293b; border-radius: 6px; padding: 10px; border: 1px solid #334155;">
                <p class="prophet-label">@ 50%</p>
                <p class="prophet-value-small" style="color: #10b981; margin-top: 4px;">${p3:,.0f}</p>
            </div>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    else:
        st.info("Configure a valid setup first")


def render_historical_analysis(session_data, setup, hits, pnl, pnl_note, engine):
    html = f"""
    <div class="prophet-card">
        <p class="prophet-label" style="margin-bottom: 16px;">📊 Session Stats</p>
        <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px;">
            <div style="text-align: center;">
                <p class="prophet-label">Open</p>
                <p class="prophet-value-small">{session_data['open']:,.2f}</p>
            </div>
            <div style="text-align: center;">
                <p class="prophet-label">High</p>
                <p class="prophet-value-small" style="color: #10b981;">{session_data['high']:,.2f}</p>
            </div>
            <div style="text-align: center;">
                <p class="prophet-label">Low</p>
                <p class="prophet-value-small" style="color: #ef4444;">{session_data['low']:,.2f}</p>
            </div>
            <div style="text-align: center;">
                <p class="prophet-label">Close</p>
                <p class="prophet-value-small">{session_data['close']:,.2f}</p>
            </div>
            <div style="text-align: center;">
                <p class="prophet-label">Range</p>
                <p class="prophet-value-small" style="color: #3b82f6;">{session_data['range']:.2f}</p>
            </div>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    
    st.markdown('<p class="prophet-label" style="margin: 16px 0 8px 0;">Level Hits</p>', unsafe_allow_html=True)
    
    hits_html = ""
    for hit in hits:
        hits_html += f"""
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; margin: 4px 0; background: #1e293b; border-radius: 6px; border-left: 3px solid {hit.status.color};">
            <span class="prophet-text">{hit.level_name}</span>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #94a3b8;">{hit.level_price:,.2f}</span>
            <span style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: {hit.status.color}; font-weight: 600;">{hit.status.icon} {hit.status.label}</span>
        </div>
        """
    
    pnl_color = "#10b981" if pnl >= 0 else "#ef4444"
    pnl_prefix = "+" if pnl >= 0 else ""
    
    html2 = f"""
    <div style="margin-top: 8px;">{hits_html}</div>
    <div style="margin-top: 16px; padding: 16px; background: #1e293b; border-radius: 8px; border: 1px solid #334155;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <p class="prophet-label">Theoretical P&L (1 contract)</p>
                <p class="prophet-text-muted" style="margin-top: 4px;">{pnl_note}</p>
            </div>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 700; color: {pnl_color}; margin: 0;">{pnl_prefix}${abs(pnl):,.2f}</p>
        </div>
    </div>
    """
    st.markdown(html2, unsafe_allow_html=True)


def render_trade_rules():
    html = """
    <div class="prophet-card">
        <p class="prophet-label" style="margin-bottom: 12px;">📖 Trade Rules</p>
        <div class="prophet-text" style="line-height: 1.8;">
            <p style="margin: 0 0 8px 0;"><strong style="color: #f8fafc;">Entry:</strong> CALLS at descending rail • PUTS at ascending rail</p>
            <p style="margin: 0 0 8px 0;"><strong style="color: #f8fafc;">Stop:</strong> 6 points from entry</p>
            <p style="margin: 0 0 8px 0;"><strong style="color: #f8fafc;">Targets:</strong> 12.5% → 25% → 50% of cone width</p>
            <p style="margin: 0 0 8px 0;"><strong style="color: #f8fafc;">Confirmation:</strong> Wait for 30-min candle CLOSE</p>
            <p style="margin: 0;"><strong style="color: #f59e0b;">⚠️ Danger Zone:</strong> 6:30-9:30 AM CT</p>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar(engine):
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
    
    # Fetch prior day data based on selected session date
    prior_data = fetch_prior_day_data(session_date)
    
    st.sidebar.markdown("---")
    
    st.sidebar.markdown("#### 📊 VIX Zone")
    st.sidebar.caption("Overnight range (5pm-2am CT)")
    c1, c2 = st.sidebar.columns(2)
    vix_bottom = c1.number_input("Bottom", 5.0, 100.0, 16.50, 0.01, format="%.2f")
    vix_top = c2.number_input("Top", 5.0, 100.0, 16.65, 0.01, format="%.2f")
    vix_current = st.sidebar.number_input("Current VIX", 5.0, 100.0, 16.55, 0.01, format="%.2f")
    
    zone = VIXZone(vix_bottom, vix_top, vix_current)
    
    st.sidebar.markdown("---")
    
    st.sidebar.markdown("#### 📍 Prior Day Pivots")
    manual = st.sidebar.checkbox("Manual Input", False)
    
    # Calculate expected prior date (skip weekends)
    prior_date = session_date - timedelta(days=1)
    while prior_date.weekday() >= 5:  # Skip Saturday (5) and Sunday (6)
        prior_date -= timedelta(days=1)
    
    if manual or prior_data is None:
        st.sidebar.caption(f"Pivot date: {prior_date}")
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
        # Use the actual date from fetched data
        prior_date = prior_data['date'].date() if hasattr(prior_data['date'], 'date') else prior_data['date']
        p_high_t = time(11, 30)
        p_low_t = time(14, 0)
        st.sidebar.success(f"✓ Loaded: {prior_date}")
        st.sidebar.caption(f"H: {p_high:,.2f} | L: {p_low:,.2f} | C: {p_close:,.2f}")
    
    pivots = [
        Pivot("Prior High", p_high, ct_tz.localize(datetime.combine(prior_date, p_high_t))),
        Pivot("Prior Low", p_low, ct_tz.localize(datetime.combine(prior_date, p_low_t))),
        Pivot("Prior Close", p_close, ct_tz.localize(datetime.combine(prior_date, time(16, 0))))
    ]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 📍 Secondary Pivots")
    st.sidebar.caption("Optional additional levels")
    
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
    st.sidebar.caption("SPX Prophet v4.2")
    
    return mode, session_date, zone, pivots


# =============================================================================
# MAIN
# =============================================================================

def main():
    engine = SPXProphetEngine()
    ct_tz = pytz.timezone('America/Chicago')
    
    spx_live, vix_live, _ = fetch_live_data()
    spx_price = spx_live or 6000.0
    vix_price = vix_live or 16.50
    
    mode, session_date, zone, pivots = render_sidebar(engine)
    
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
        render_bias_card(bias, confidence, explanation, zone, phase)
        
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
        elif bias == Bias.WAIT:
            st.info("📊 VIX mid-zone. No directional edge. Waiting...")
        else:
            st.warning("No valid setups. Check cone widths.")
        
        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        with col1:
            render_position_calculator(engine, best_setup)
        with col2:
            render_trade_rules()
    
    else:
        st.markdown(f"### 📊 Historical Analysis: {session_date}")
        session_data = fetch_historical_data(session_date)
        
        if session_data:
            render_bias_card(bias, confidence, explanation, zone, Phase.POST_SESSION)
            
            col1, col2 = st.columns(2)
            with col1:
                render_vix_zone(zone)
            with col2:
                if best_setup:
                    hits = engine.analyze_level_hits(best_setup, session_data['high'], session_data['low'])
                    pnl, note = engine.calculate_theoretical_pnl(best_setup, hits)
                    render_historical_analysis(session_data, best_setup, hits, pnl, note, engine)
                else:
                    st.info("Configure pivots to see analysis")
            
            render_cone_table(cones, best_name)
            
            if setups:
                st.markdown("### Setup Analysis")
                for setup in setups:
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        render_setup_card(setup, session_data['close'], engine, setup.cone.pivot.name == best_name)
                    with col2:
                        hits = engine.analyze_level_hits(setup, session_data['high'], session_data['low'])
                        pnl, note = engine.calculate_theoretical_pnl(setup, hits)
                        
                        for hit in hits:
                            st.markdown(f"<span style='color: {hit.status.color};'>{hit.status.icon}</span> **{hit.level_name}**: {hit.level_price:,.2f}", unsafe_allow_html=True)
                        
                        pnl_color = "#10b981" if pnl >= 0 else "#ef4444"
                        st.markdown(f"**P&L:** <span style='color: {pnl_color};'>${pnl:,.2f}</span> ({note})", unsafe_allow_html=True)
        else:
            st.error(f"No data for {session_date}. May be weekend/holiday.")
    
    st.markdown("---")
    st.caption("SPX Prophet v4.2 | Data: Yahoo Finance | Not Financial Advice")


if __name__ == "__main__":
    main()