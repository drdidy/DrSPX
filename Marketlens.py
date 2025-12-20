"""
SPX PROPHET v8.0 - WINNING EDITION
Focused on what helps you WIN. No fluff.
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time, date
import yfinance as yf
import pytz
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from enum import Enum

# =============================================================================
# CONFIG
# =============================================================================

st.set_page_config(
    page_title="SPX Prophet",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Clean styling
st.markdown("""
<style>
    .stApp { background-color: #fafafa; }
    section[data-testid="stSidebar"] { background-color: #ffffff; }
    #MainMenu, footer, .stDeployButton { display: none; }
    
    div[data-testid="stMetricValue"] {
        font-size: 1.6rem;
        font-weight: 700;
    }
    
    .big-number {
        font-size: 3rem;
        font-weight: 800;
        font-family: 'Courier New', monospace;
        margin: 0;
        line-height: 1;
    }
    
    .medium-number {
        font-size: 1.8rem;
        font-weight: 700;
        font-family: 'Courier New', monospace;
        margin: 0;
    }
    
    .label {
        font-size: 0.75rem;
        font-weight: 600;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 4px;
    }
    
    .green { color: #16a34a; }
    .red { color: #dc2626; }
    .blue { color: #2563eb; }
    .orange { color: #ea580c; }
    
    .card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 16px;
    }
    
    .card-green {
        background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
        border: 2px solid #16a34a;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }
    
    .card-red {
        background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
        border: 2px solid #dc2626;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }
    
    .card-blue {
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        border: 2px solid #2563eb;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }
    
    .card-orange {
        background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
        border: 2px solid #ea580c;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)


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
    CONFLUENCE_THRESHOLD = 6.0
    EM_BASE = 35
    EM_ZONE_BASELINE = 0.10
    EM_MULTIPLIER = 100
    EM_CAP_LOW = 65
    EM_CAP_HIGH = 70


class Bias(Enum):
    CALLS = ("CALLS", "#16a34a", "↑")
    PUTS = ("PUTS", "#dc2626", "↓")
    WAIT = ("WAIT", "#ea580c", "◆")
    
    def __init__(self, label, color, arrow):
        self.label = label
        self.color = color
        self.arrow = arrow


class Confidence(Enum):
    HIGH = ("HIGH", "●●●")
    MEDIUM = ("MEDIUM", "●●○")
    LOW = ("LOW", "●○○")
    NONE = ("NONE", "○○○")
    
    def __init__(self, label, dots):
        self.label = label
        self.dots = dots


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VIXZone:
    bottom: float
    top: float
    current: float
    
    @property
    def size(self) -> float:
        return round(self.top - self.bottom, 4)
    
    @property
    def current_zone(self) -> str:
        if self.current > self.top:
            ext = (self.current - self.top) / self.size if self.size > 0 else 0
            if ext >= 2: return "+3"
            elif ext >= 1: return "+2"
            else: return "+1"
        elif self.current < self.bottom:
            ext = (self.bottom - self.current) / self.size if self.size > 0 else 0
            if ext >= 2: return "-3"
            elif ext >= 1: return "-2"
            else: return "-1"
        return "BASE"
    
    @property
    def nearest_buy_trigger(self) -> float:
        if self.current <= self.bottom:
            return self.bottom
        elif self.current <= self.top:
            return self.top
        else:
            ext = int((self.current - self.top) / self.size) + 1 if self.size > 0 else 1
            return self.top + (ext * self.size)
    
    @property
    def nearest_sell_trigger(self) -> float:
        if self.current >= self.top:
            return self.top
        elif self.current >= self.bottom:
            return self.bottom
        else:
            ext = int((self.bottom - self.current) / self.size) + 1 if self.size > 0 else 1
            return self.bottom - (ext * self.size)
    
    @property
    def distance_to_buy(self) -> float:
        return round(self.nearest_buy_trigger - self.current, 2)
    
    @property
    def distance_to_sell(self) -> float:
        return round(self.current - self.nearest_sell_trigger, 2)
    
    def get_extension(self, level: int) -> float:
        if level > 0:
            return round(self.top + (level * self.size), 2)
        elif level < 0:
            return round(self.bottom + (level * self.size), 2)
        return self.top
    
    def get_expected_move(self) -> Tuple[float, float]:
        if self.size <= 0:
            return (0, 0)
        em_low = Config.EM_BASE + ((self.size - Config.EM_ZONE_BASELINE) * Config.EM_MULTIPLIER)
        em_high = em_low + 5
        em_low = min(em_low, Config.EM_CAP_LOW)
        em_high = min(em_high, Config.EM_CAP_HIGH)
        return (round(max(em_low, 0), 1), round(em_high, 1))


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
    def is_tradeable(self) -> bool:
        return self.width >= Config.MIN_CONE_WIDTH


@dataclass
class ConfluentLevel:
    price: float
    rail_type: str
    cones: List[str]
    strength: str


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
    is_confluent: bool = False
    
    @property
    def reward_1(self) -> float:
        return abs(self.target_1 - self.entry)
    
    @property
    def reward_2(self) -> float:
        return abs(self.target_2 - self.entry)
    
    @property
    def reward_3(self) -> float:
        return abs(self.target_3 - self.entry)


# =============================================================================
# ENGINE
# =============================================================================

class SPXProphetEngine:
    def __init__(self):
        self.ct_tz = pytz.timezone('America/Chicago')
    
    def get_current_time_ct(self) -> datetime:
        return datetime.now(self.ct_tz)
    
    def get_phase(self) -> Tuple[str, str]:
        dt = self.get_current_time_ct()
        t = dt.time()
        weekday = dt.weekday()
        
        if weekday >= 5:
            return "CLOSED", "Weekend"
        if time(17, 0) <= t or t < time(6, 0):
            return "ZONE BUILDING", "5pm-6am CT"
        elif time(6, 0) <= t < time(9, 30):
            return "PRE-RTH", "6am-9:30am CT"
        elif time(9, 30) <= t < time(16, 0):
            return "RTH", "9:30am-4pm CT"
        else:
            return "POST", "After 4pm CT"
    
    def determine_bias(self, zone: VIXZone) -> Tuple[Bias, Confidence, str]:
        dist_buy = zone.distance_to_buy
        dist_sell = zone.distance_to_sell
        current = zone.current_zone
        
        if abs(dist_buy) <= 0.05:
            return Bias.CALLS, Confidence.HIGH, f"VIX at buy trigger. SPX rallies."
        if abs(dist_sell) <= 0.05:
            return Bias.PUTS, Confidence.HIGH, f"VIX at sell trigger. SPX sells."
        if "+" in current:
            conf = Confidence.MEDIUM if dist_buy > 0.10 else Confidence.LOW
            return Bias.PUTS, conf, f"VIX in {current}. Put bias."
        if "-" in current:
            conf = Confidence.MEDIUM if dist_sell > 0.10 else Confidence.LOW
            return Bias.CALLS, conf, f"VIX in {current}. Call bias."
        return Bias.WAIT, Confidence.NONE, "VIX in BASE. Trend day possible."
    
    def calculate_blocks(self, pivot_time: datetime, eval_time: datetime) -> int:
        if pivot_time.tzinfo is None:
            pivot_time = self.ct_tz.localize(pivot_time)
        if eval_time.tzinfo is None:
            eval_time = self.ct_tz.localize(eval_time)
        diff = eval_time - pivot_time
        return max(int(diff.total_seconds() / 60 / 30), 1)
    
    def calculate_cone(self, pivot: Pivot, eval_time: datetime) -> ConeRails:
        blocks = self.calculate_blocks(pivot.timestamp, eval_time)
        expansion = blocks * Config.SLOPE_PER_30MIN
        asc = round(pivot.price + expansion, 2)
        desc = round(pivot.price - expansion, 2)
        return ConeRails(pivot=pivot, ascending=asc, descending=desc, 
                        width=round(asc - desc, 2), blocks=blocks)
    
    def find_confluence(self, cones: List[ConeRails]) -> Tuple[List[ConfluentLevel], List[ConfluentLevel]]:
        support, resistance = [], []
        asc_rails = [(c.ascending, c.pivot.name) for c in cones if c.is_tradeable]
        desc_rails = [(c.descending, c.pivot.name) for c in cones if c.is_tradeable]
        
        for i, (p1, n1) in enumerate(asc_rails):
            matches = [n1] + [n2 for j, (p2, n2) in enumerate(asc_rails) if i != j and abs(p1-p2) <= Config.CONFLUENCE_THRESHOLD]
            if len(matches) >= 2:
                avg = sum(p for p, n in asc_rails if n in matches) / len(matches)
                if not any(abs(r.price - avg) < 1 for r in resistance):
                    resistance.append(ConfluentLevel(round(avg, 2), "resistance", matches, "strong" if len(matches) >= 3 else "moderate"))
        
        for i, (p1, n1) in enumerate(desc_rails):
            matches = [n1] + [n2 for j, (p2, n2) in enumerate(desc_rails) if i != j and abs(p1-p2) <= Config.CONFLUENCE_THRESHOLD]
            if len(matches) >= 2:
                avg = sum(p for p, n in desc_rails if n in matches) / len(matches)
                if not any(abs(s.price - avg) < 1 for s in support):
                    support.append(ConfluentLevel(round(avg, 2), "support", matches, "strong" if len(matches) >= 3 else "moderate"))
        
        return support, resistance
    
    def generate_setup(self, cone: ConeRails, direction: Bias, 
                      support: List[ConfluentLevel], resistance: List[ConfluentLevel]) -> Optional[TradeSetup]:
        if not cone.is_tradeable or direction == Bias.WAIT:
            return None
        
        if direction == Bias.CALLS:
            entry, opposite = cone.descending, cone.ascending
            stop = entry - Config.STOP_LOSS_PTS
            strike = int(round((entry - Config.STRIKE_OTM_DISTANCE) / 5) * 5)
            move = opposite - entry
            t1, t2, t3 = entry + move * 0.125, entry + move * 0.25, entry + move * 0.50
            is_conf = any(abs(c.price - entry) <= Config.CONFLUENCE_THRESHOLD for c in support)
        else:
            entry, opposite = cone.ascending, cone.descending
            stop = entry + Config.STOP_LOSS_PTS
            strike = int(round((entry + Config.STRIKE_OTM_DISTANCE) / 5) * 5)
            move = entry - opposite
            t1, t2, t3 = entry - move * 0.125, entry - move * 0.25, entry - move * 0.50
            is_conf = any(abs(c.price - entry) <= Config.CONFLUENCE_THRESHOLD for c in resistance)
        
        return TradeSetup(direction=direction, cone=cone, entry=round(entry, 2), stop=round(stop, 2),
                         target_1=round(t1, 2), target_2=round(t2, 2), target_3=round(t3, 2),
                         strike=strike, is_confluent=is_conf)
    
    def calculate_profit(self, points: float, contracts: int = 1) -> float:
        return round(points * Config.DELTA * Config.CONTRACT_MULTIPLIER * contracts, 2)


# =============================================================================
# DATA FETCHING
# =============================================================================

@st.cache_data(ttl=60)
def fetch_spx_data():
    try:
        spx = yf.Ticker("^GSPC")
        hist = spx.history(period="5d", interval="1d")
        if hist.empty:
            return None, None
        current = float(hist['Close'].iloc[-1])
        prior = None
        if len(hist) >= 2:
            p = hist.iloc[-2]
            prior = {'date': hist.index[-2], 'high': float(p['High']), 
                    'low': float(p['Low']), 'close': float(p['Close'])}
        return current, prior
    except:
        return None, None


@st.cache_data(ttl=300)
def fetch_prior_day(session_date: date) -> Optional[Dict]:
    try:
        spx = yf.Ticker("^GSPC")
        hist = spx.history(start=session_date - timedelta(days=10), end=session_date + timedelta(days=1))
        if hist.empty or len(hist) < 2:
            return None
        session_str = session_date.strftime('%Y-%m-%d')
        for i, idx in enumerate(hist.index):
            if idx.strftime('%Y-%m-%d') == session_str and i > 0:
                prior = hist.iloc[i - 1]
                return {'date': hist.index[i-1], 'high': float(prior['High']),
                       'low': float(prior['Low']), 'close': float(prior['Close'])}
        prior = hist.iloc[-2]
        return {'date': hist.index[-2], 'high': float(prior['High']),
               'low': float(prior['Low']), 'close': float(prior['Close'])}
    except:
        return None


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar(engine: SPXProphetEngine):
    st.sidebar.markdown("## ⚡ SPX Prophet")
    st.sidebar.caption("v8.0 Winning Edition")
    
    st.sidebar.divider()
    
    mode = st.sidebar.radio("Mode", ["Live", "Historical"], horizontal=True)
    
    ct_tz = pytz.timezone('America/Chicago')
    today = datetime.now(ct_tz).date()
    
    if mode == "Live":
        session_date = today
    else:
        session_date = st.sidebar.date_input("Session Date", today - timedelta(days=1), max_value=today)
    
    st.sidebar.divider()
    st.sidebar.markdown("### VIX Zone")
    st.sidebar.caption("5pm-6am CT")
    
    c1, c2 = st.sidebar.columns(2)
    vix_bottom = c1.number_input("Bottom", 5.0, 50.0, 15.87, 0.01, format="%.2f")
    vix_top = c2.number_input("Top", 5.0, 50.0, 16.17, 0.01, format="%.2f")
    vix_current = st.sidebar.number_input("Current VIX", 5.0, 50.0, 16.00, 0.01, format="%.2f")
    
    zone = VIXZone(vix_bottom, vix_top, vix_current)
    
    st.sidebar.divider()
    st.sidebar.markdown("### Prior Day Pivots")
    
    prior_data = fetch_prior_day(session_date)
    
    prior_date = session_date - timedelta(days=1)
    while prior_date.weekday() >= 5:
        prior_date -= timedelta(days=1)
    
    if prior_data:
        p_high = prior_data['high']
        p_low = prior_data['low']
        p_close = prior_data['close']
        st.sidebar.success(f"✓ Loaded {prior_date}")
    else:
        p_high = st.sidebar.number_input("High", 1000.0, 10000.0, 6050.0, 1.0)
        p_low = st.sidebar.number_input("Low", 1000.0, 10000.0, 6020.0, 1.0)
        p_close = st.sidebar.number_input("Close", 1000.0, 10000.0, 6035.0, 1.0)
    
    c1, c2 = st.sidebar.columns(2)
    p_high_t = c1.time_input("High Time", time(11, 30))
    p_low_t = c2.time_input("Low Time", time(14, 0))
    
    pivots = [
        Pivot("Prior High", p_high, ct_tz.localize(datetime.combine(prior_date, p_high_t))),
        Pivot("Prior Low", p_low, ct_tz.localize(datetime.combine(prior_date, p_low_t))),
        Pivot("Prior Close", p_close, ct_tz.localize(datetime.combine(prior_date, time(16, 0))))
    ]
    
    st.sidebar.divider()
    
    if st.sidebar.checkbox("Add High²"):
        c1, c2 = st.sidebar.columns(2)
        h2p = c1.number_input("H² Price", value=p_high - 10)
        h2t = c2.time_input("H² Time", time(10, 0))
        pivots.append(Pivot("High²", h2p, ct_tz.localize(datetime.combine(prior_date, h2t)), "secondary"))
    
    if st.sidebar.checkbox("Add Low²"):
        c1, c2 = st.sidebar.columns(2)
        l2p = c1.number_input("L² Price", value=p_low + 10)
        l2t = c2.time_input("L² Time", time(13, 0))
        pivots.append(Pivot("Low²", l2p, ct_tz.localize(datetime.combine(prior_date, l2t)), "secondary"))
    
    return mode, session_date, zone, pivots


# =============================================================================
# MAIN
# =============================================================================

def main():
    engine = SPXProphetEngine()
    ct_tz = pytz.timezone('America/Chicago')
    
    spx_live, _ = fetch_spx_data()
    spx = spx_live or 6000.0
    
    mode, session_date, zone, pivots = render_sidebar(engine)
    
    now = engine.get_current_time_ct()
    phase, phase_time = engine.get_phase()
    bias, confidence, explanation = engine.determine_bias(zone)
    
    eval_time = ct_tz.localize(datetime.combine(
        now.date() if mode == "Live" else session_date,
        max(now.time(), time(10, 0)) if mode == "Live" else time(10, 0)
    ))
    
    cones = [engine.calculate_cone(p, eval_time) for p in pivots]
    support, resistance = engine.find_confluence(cones)
    
    valid = [c for c in cones if c.is_tradeable]
    best_cone = max(valid, key=lambda x: x.width) if valid else None
    
    setups = []
    for cone in cones:
        if cone.is_tradeable:
            s = engine.generate_setup(cone, bias, support, resistance)
            if s:
                setups.append(s)
    
    setups.sort(key=lambda s: (s.cone.pivot.name != (best_cone.pivot.name if best_cone else ""), -s.cone.width))
    best_setup = setups[0] if setups else None
    
    em_low, em_high = zone.get_expected_move()
    
    # =========================================================================
    # HEADER
    # =========================================================================
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown("# ⚡ SPX Prophet")
    
    with col2:
        st.metric("SPX", f"{spx:,.2f}")
    
    with col3:
        st.metric(phase, now.strftime('%I:%M %p CT'))
    
    st.divider()
    
    # =========================================================================
    # ROW 1: BIAS + EXPECTED MOVE + ALGO TRIGGERS
    # =========================================================================
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        card_class = "card-green" if bias == Bias.CALLS else ("card-red" if bias == Bias.PUTS else "card-orange")
        st.markdown(f"""
        <div class="{card_class}">
            <p class="label">DIRECTION</p>
            <p class="big-number" style="color: {bias.color}">{bias.arrow} {bias.label}</p>
            <p style="margin-top: 8px; font-size: 1.2rem;">{confidence.dots} {confidence.label}</p>
            <p style="margin-top: 8px; color: #666;">{explanation}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="card-blue">
            <p class="label">EXPECTED MOVE</p>
            <p class="big-number blue">{em_low:.0f} - {em_high:.0f}</p>
            <p style="margin-top: 8px; font-size: 1rem;">points from entry</p>
            <p style="margin-top: 8px; color: #666;">VIX Zone: {zone.size:.2f}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="card">
            <p class="label">VIX NOW</p>
            <p class="big-number">{zone.current:.2f}</p>
            <p style="margin-top: 8px; font-size: 1rem; color: #2563eb;">Zone: {zone.current_zone}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # =========================================================================
    # ROW 2: ALGO TRIGGERS
    # =========================================================================
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div class="card-green">
            <p class="label">↑ BUY ALGO TRIGGER</p>
            <p class="medium-number green">{zone.nearest_buy_trigger:.2f}</p>
            <p style="margin-top: 8px;">VIX tops here → SPX rallies</p>
            <p style="font-size: 1.2rem; font-weight: 700; margin-top: 8px;">{zone.distance_to_buy:+.2f} away</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="card-red">
            <p class="label">↓ SELL ALGO TRIGGER</p>
            <p class="medium-number red">{zone.nearest_sell_trigger:.2f}</p>
            <p style="margin-top: 8px;">VIX bottoms here → SPX sells</p>
            <p style="font-size: 1.2rem; font-weight: 700; margin-top: 8px;">{zone.distance_to_sell:.2f} away</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # =========================================================================
    # ROW 3: BEST SETUP
    # =========================================================================
    
    if best_setup:
        setup_class = "card-green" if best_setup.direction == Bias.CALLS else "card-red"
        conf_badge = "🎯 CONFLUENCE" if best_setup.is_confluent else ""
        
        st.markdown(f"## ⭐ Best Setup: {best_setup.cone.pivot.name} Cone {conf_badge}")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.markdown(f"""
            <div class="{setup_class}" style="text-align: center;">
                <p class="label">ENTRY</p>
                <p class="medium-number">{best_setup.entry:,.2f}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="card-red" style="text-align: center;">
                <p class="label">STOP (-6 pts)</p>
                <p class="medium-number red">{best_setup.stop:,.2f}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="card" style="text-align: center;">
                <p class="label">T1 (12.5%)</p>
                <p class="medium-number green">{best_setup.target_1:,.2f}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="card" style="text-align: center;">
                <p class="label">T2 (25%)</p>
                <p class="medium-number green">{best_setup.target_2:,.2f}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col5:
            st.markdown(f"""
            <div class="card" style="text-align: center;">
                <p class="label">T3 (50%)</p>
                <p class="medium-number green">{best_setup.target_3:,.2f}</p>
            </div>
            """, unsafe_allow_html=True)
        
        # Setup details
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Strike", best_setup.strike)
        col2.metric("Distance to Entry", f"{spx - best_setup.entry:+.1f} pts")
        col3.metric("Cone Width", f"{best_setup.cone.width:.1f} pts")
        rr = engine.calculate_profit(best_setup.reward_2, 1) / engine.calculate_profit(Config.STOP_LOSS_PTS, 1)
        col4.metric("R:R @ T2", f"{rr:.1f}:1")
        
        st.divider()
        
        # =====================================================================
        # ROW 4: POSITION SIZING & P/L
        # =====================================================================
        
        st.markdown("## 💰 Position Sizing & Profit/Loss")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            contracts = st.selectbox("Select Contracts", [1, 2, 3, 5, 10, 15, 20, 25, 50], index=0)
            
            risk = engine.calculate_profit(Config.STOP_LOSS_PTS, contracts)
            p1 = engine.calculate_profit(best_setup.reward_1, contracts)
            p2 = engine.calculate_profit(best_setup.reward_2, contracts)
            p3 = engine.calculate_profit(best_setup.reward_3, contracts)
            
            st.markdown(f"""
            <div class="card-red" style="text-align: center; margin-top: 16px;">
                <p class="label">MAX LOSS</p>
                <p class="big-number red">-${risk:,.0f}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            pc1, pc2, pc3 = st.columns(3)
            
            with pc1:
                st.markdown(f"""
                <div class="card-green" style="text-align: center;">
                    <p class="label">@ T1 (12.5%)</p>
                    <p class="big-number green">+${p1:,.0f}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with pc2:
                st.markdown(f"""
                <div class="card-green" style="text-align: center;">
                    <p class="label">@ T2 (25%)</p>
                    <p class="big-number green">+${p2:,.0f}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with pc3:
                st.markdown(f"""
                <div class="card-green" style="text-align: center;">
                    <p class="label">@ T3 (50%)</p>
                    <p class="big-number green">+${p3:,.0f}</p>
                </div>
                """, unsafe_allow_html=True)
        
        # Quick P&L Table
        st.markdown("### Quick P&L Reference")
        
        pnl_data = []
        for c in [1, 5, 10, 20]:
            pnl_data.append({
                "Contracts": c,
                "Max Loss": f"-${engine.calculate_profit(Config.STOP_LOSS_PTS, c):,.0f}",
                "@ T1 (12.5%)": f"+${engine.calculate_profit(best_setup.reward_1, c):,.0f}",
                "@ T2 (25%)": f"+${engine.calculate_profit(best_setup.reward_2, c):,.0f}",
                "@ T3 (50%)": f"+${engine.calculate_profit(best_setup.reward_3, c):,.0f}"
            })
        
        st.dataframe(pd.DataFrame(pnl_data), hide_index=True, use_container_width=True)
    
    else:
        st.warning("⏳ No valid setup. VIX may be in BASE zone (trend day) or cones too narrow.")
    
    st.divider()
    
    # =========================================================================
    # ROW 5: PIVOTS + CONES + VIX LADDER
    # =========================================================================
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📍 Pivots")
        pivot_data = []
        for p in pivots:
            pivot_data.append({
                "Pivot": p.name,
                "Price": f"{p.price:,.2f}",
                "Time": p.timestamp.strftime('%I:%M %p')
            })
        st.dataframe(pd.DataFrame(pivot_data), hide_index=True, use_container_width=True)
    
    with col2:
        st.markdown("### 📐 Cones")
        cone_data = []
        for c in cones:
            status = "⭐" if best_cone and c.pivot.name == best_cone.pivot.name else ("✓" if c.is_tradeable else "✗")
            cone_data.append({
                "Cone": c.pivot.name,
                "↑": f"{c.ascending:,.2f}",
                "↓": f"{c.descending:,.2f}",
                "Width": f"{c.width:.1f}",
                "": status
            })
        st.dataframe(pd.DataFrame(cone_data), hide_index=True, use_container_width=True)
    
    with col3:
        st.markdown("### 📶 VIX Ladder")
        ladder_data = []
        for label, value in [("+2", zone.get_extension(2)), ("+1", zone.get_extension(1)),
                             ("TOP", zone.top), ("VIX →", zone.current), ("BTM", zone.bottom),
                             ("-1", zone.get_extension(-1)), ("-2", zone.get_extension(-2))]:
            ladder_data.append({"Level": label, "Value": f"{value:.2f}"})
        st.dataframe(pd.DataFrame(ladder_data), hide_index=True, use_container_width=True)
    
    # =========================================================================
    # ROW 6: CONFLUENCE
    # =========================================================================
    
    if support or resistance:
        st.divider()
        st.markdown("### 🎯 Confluence Zones")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if support:
                for level in support:
                    stars = "⭐⭐⭐" if level.strength == "strong" else "⭐⭐"
                    st.success(f"**SUPPORT {stars}**  \n{level.price:,.2f}  \n{', '.join(level.cones)}")
        
        with col2:
            if resistance:
                for level in resistance:
                    stars = "⭐⭐⭐" if level.strength == "strong" else "⭐⭐"
                    st.error(f"**RESISTANCE {stars}**  \n{level.price:,.2f}  \n{', '.join(level.cones)}")
    
    # =========================================================================
    # ALL SETUPS
    # =========================================================================
    
    if len(setups) > 1:
        with st.expander("📋 All Setups"):
            for i, s in enumerate(setups):
                prefix = "⭐ BEST: " if i == 0 else ""
                conf = " 🎯" if s.is_confluent else ""
                st.write(f"**{prefix}{s.direction.arrow} {s.direction.label} — {s.cone.pivot.name}{conf}**")
                st.write(f"Entry: {s.entry:,.2f} | Stop: {s.stop:,.2f} | T1: {s.target_1:,.2f} | T2: {s.target_2:,.2f} | T3: {s.target_3:,.2f} | Strike: {s.strike}")
                st.divider()
    
    # Footer
    st.caption("SPX Prophet v8.0 | Not Financial Advice")


if __name__ == "__main__":
    main()
