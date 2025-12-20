"""
SPX PROPHET v7.0
Institutional SPX Prediction System

Uses native Streamlit components for reliability.
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
import plotly.graph_objects as go

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="SPX Prophet",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# MINIMAL STYLING - Only what Streamlit handles reliably
# =============================================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    .stApp {
        background-color: #f8fafc;
    }
    
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    [data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.8rem;
    }
    
    [data-testid="stMetricLabel"] {
        font-family: 'Inter', sans-serif;
        font-size: 0.8rem;
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
    CALLS = ("CALLS", "green", "↑")
    PUTS = ("PUTS", "red", "↓")
    WAIT = ("WAIT", "orange", "◆")
    
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
    
    def get_phase(self, dt: datetime = None) -> Tuple[str, str]:
        if dt is None:
            dt = self.get_current_time_ct()
        elif dt.tzinfo is None:
            dt = self.ct_tz.localize(dt)
        
        t = dt.time()
        weekday = dt.weekday()
        
        if weekday >= 5:
            return "Closed", "⭘"
        if time(17, 0) <= t or t < time(6, 0):
            return "Zone Building", "🌙"
        elif time(6, 0) <= t < time(9, 30):
            return "Pre-RTH", "⏳"
        elif time(9, 30) <= t < time(16, 0):
            return "RTH Active", "🟢"
        else:
            return "Post Session", "📊"
    
    def determine_bias(self, zone: VIXZone) -> Tuple[Bias, Confidence, str]:
        dist_buy = zone.distance_to_buy
        dist_sell = zone.distance_to_sell
        current = zone.current_zone
        
        if abs(dist_buy) <= 0.05:
            return Bias.CALLS, Confidence.HIGH, f"VIX at buy trigger ({zone.nearest_buy_trigger:.2f}). SPX UP"
        if abs(dist_sell) <= 0.05:
            return Bias.PUTS, Confidence.HIGH, f"VIX at sell trigger ({zone.nearest_sell_trigger:.2f}). SPX DOWN"
        if "+" in current:
            conf = Confidence.MEDIUM if dist_buy > 0.10 else Confidence.LOW
            return Bias.PUTS, conf, f"VIX in {current} zone. Put bias."
        if "-" in current:
            conf = Confidence.MEDIUM if dist_sell > 0.10 else Confidence.LOW
            return Bias.CALLS, conf, f"VIX in {current} zone. Call bias."
        return Bias.WAIT, Confidence.NONE, "VIX in Base Zone. Trend day possible."
    
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
    
    def max_contracts(self, risk_budget: float) -> int:
        risk_per = self.calculate_profit(Config.STOP_LOSS_PTS, 1)
        return int(risk_budget / risk_per) if risk_per > 0 else 0


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


@st.cache_data(ttl=60)
def fetch_intraday():
    try:
        spx = yf.Ticker("^GSPC")
        hist = spx.history(period="2d", interval="30m")
        return hist if not hist.empty else None
    except:
        return None


# =============================================================================
# CHART
# =============================================================================

def create_chart(intraday: pd.DataFrame, cones: List[ConeRails], 
                setup: Optional[TradeSetup], spx: float):
    fig = go.Figure()
    
    # Get data
    if intraday is not None and not intraday.empty:
        today = datetime.now().date()
        data = intraday[intraday.index.date == today]
        if data.empty:
            data = intraday.tail(13)
        
        # Candlesticks
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name='SPX',
            increasing_line_color='#22c55e',
            decreasing_line_color='#ef4444',
            increasing_fillcolor='#bbf7d0',
            decreasing_fillcolor='#fecaca'
        ))
        
        y_min = data['Low'].min()
        y_max = data['High'].max()
    else:
        y_min = spx - 30
        y_max = spx + 30
    
    # Cone colors
    colors = {'Prior High': '#f59e0b', 'Prior Low': '#3b82f6', 
              'Prior Close': '#8b5cf6', 'High²': '#f97316', 'Low²': '#06b6d4'}
    
    # Add cone rails
    for cone in cones:
        if not cone.is_tradeable:
            continue
        color = colors.get(cone.pivot.name, '#64748b')
        
        fig.add_hline(y=cone.ascending, line_dash="dot", line_color=color, line_width=2,
                     annotation_text=f"↑ {cone.pivot.name} {cone.ascending:.0f}",
                     annotation_position="right")
        fig.add_hline(y=cone.descending, line_dash="dot", line_color=color, line_width=2,
                     annotation_text=f"↓ {cone.pivot.name} {cone.descending:.0f}",
                     annotation_position="right")
        
        y_min = min(y_min, cone.descending - 5)
        y_max = max(y_max, cone.ascending + 5)
    
    # Setup levels
    if setup:
        entry_color = '#22c55e' if setup.direction == Bias.CALLS else '#ef4444'
        
        fig.add_hline(y=setup.entry, line_color=entry_color, line_width=3,
                     annotation_text=f"ENTRY {setup.entry:.0f}", annotation_position="left")
        fig.add_hline(y=setup.stop, line_dash="dash", line_color='#dc2626', line_width=2,
                     annotation_text=f"STOP {setup.stop:.0f}", annotation_position="left")
        
        for name, price in [("T1", setup.target_1), ("T2", setup.target_2), ("T3", setup.target_3)]:
            fig.add_hline(y=price, line_dash="dash", line_color='#16a34a', line_width=1,
                         annotation_text=f"{name} {price:.0f}", annotation_position="left")
            y_max = max(y_max, price + 3)
            y_min = min(y_min, price - 3)
    
    # Current price
    fig.add_hline(y=spx, line_color='#1e293b', line_width=1,
                 annotation_text=f"NOW {spx:.2f}", annotation_position="right")
    
    # Layout
    padding = (y_max - y_min) * 0.08
    
    fig.update_layout(
        height=400,
        margin=dict(l=10, r=120, t=10, b=10),
        xaxis=dict(rangeslider=dict(visible=False), showgrid=True, gridcolor='#f1f5f9'),
        yaxis=dict(side='left', showgrid=True, gridcolor='#f1f5f9', 
                  tickformat=',.0f', range=[y_min - padding, y_max + padding]),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        showlegend=False,
        hovermode='x unified'
    )
    
    return fig


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar(engine: SPXProphetEngine):
    st.sidebar.title("⚡ SPX Prophet")
    st.sidebar.caption("Configuration")
    
    mode = st.sidebar.radio("Mode", ["Live", "Historical"], horizontal=True)
    
    st.sidebar.divider()
    
    ct_tz = pytz.timezone('America/Chicago')
    today = datetime.now(ct_tz).date()
    
    if mode == "Live":
        session_date = today
        st.sidebar.success(f"📅 {session_date.strftime('%B %d, %Y')}")
    else:
        session_date = st.sidebar.date_input("Session Date", today - timedelta(days=1), max_value=today)
    
    st.sidebar.divider()
    st.sidebar.subheader("VIX Zone")
    st.sidebar.caption("5pm-6am CT overnight range")
    
    c1, c2 = st.sidebar.columns(2)
    vix_bottom = c1.number_input("Bottom", 5.0, 50.0, 15.87, 0.01, format="%.2f")
    vix_top = c2.number_input("Top", 5.0, 50.0, 16.17, 0.01, format="%.2f")
    vix_current = st.sidebar.number_input("Current VIX", 5.0, 50.0, 16.00, 0.01, format="%.2f")
    
    zone = VIXZone(vix_bottom, vix_top, vix_current)
    
    st.sidebar.divider()
    st.sidebar.subheader("Prior Day Pivots")
    
    prior_data = fetch_prior_day(session_date)
    manual = st.sidebar.checkbox("Manual Input", value=(prior_data is None))
    
    prior_date = session_date - timedelta(days=1)
    while prior_date.weekday() >= 5:
        prior_date -= timedelta(days=1)
    
    if manual or prior_data is None:
        c1, c2 = st.sidebar.columns(2)
        p_high = c1.number_input("High", 1000.0, 10000.0, 6050.0, 1.0)
        p_high_t = c2.time_input("Time", time(11, 30), key="ht")
        c1, c2 = st.sidebar.columns(2)
        p_low = c1.number_input("Low", 1000.0, 10000.0, 6020.0, 1.0)
        p_low_t = c2.time_input("Time", time(14, 0), key="lt")
        p_close = st.sidebar.number_input("Close", 1000.0, 10000.0, 6035.0, 1.0)
    else:
        p_high = prior_data['high']
        p_low = prior_data['low']
        p_close = prior_data['close']
        prior_date = prior_data['date'].date() if hasattr(prior_data['date'], 'date') else prior_data['date']
        p_high_t = time(11, 30)
        p_low_t = time(14, 0)
        st.sidebar.success(f"✓ Loaded: {prior_date}")
    
    pivots = [
        Pivot("Prior High", p_high, ct_tz.localize(datetime.combine(prior_date, p_high_t))),
        Pivot("Prior Low", p_low, ct_tz.localize(datetime.combine(prior_date, p_low_t))),
        Pivot("Prior Close", p_close, ct_tz.localize(datetime.combine(prior_date, time(16, 0))))
    ]
    
    st.sidebar.divider()
    
    if st.sidebar.checkbox("Add High²"):
        c1, c2 = st.sidebar.columns(2)
        h2p = c1.number_input("H² Price", 1000.0, 10000.0, p_high - 10, 1.0, key="h2p")
        h2t = c2.time_input("H² Time", time(10, 0), key="h2t")
        pivots.append(Pivot("High²", h2p, ct_tz.localize(datetime.combine(prior_date, h2t)), "secondary"))
    
    if st.sidebar.checkbox("Add Low²"):
        c1, c2 = st.sidebar.columns(2)
        l2p = c1.number_input("L² Price", 1000.0, 10000.0, p_low + 10, 1.0, key="l2p")
        l2t = c2.time_input("L² Time", time(13, 0), key="l2t")
        pivots.append(Pivot("Low²", l2p, ct_tz.localize(datetime.combine(prior_date, l2t)), "secondary"))
    
    st.sidebar.divider()
    st.sidebar.caption("SPX Prophet v7.0")
    
    return mode, session_date, zone, pivots


# =============================================================================
# MAIN
# =============================================================================

def main():
    engine = SPXProphetEngine()
    ct_tz = pytz.timezone('America/Chicago')
    
    # Get data
    spx_live, _ = fetch_spx_data()
    spx = spx_live or 6000.0
    
    # Sidebar
    mode, session_date, zone, pivots = render_sidebar(engine)
    
    # Calculate
    now = engine.get_current_time_ct()
    phase_name, phase_icon = engine.get_phase(now)
    bias, confidence, explanation = engine.determine_bias(zone)
    
    eval_time = ct_tz.localize(datetime.combine(
        now.date() if mode == "Live" else session_date, 
        time(10, 0) if now.time() < time(10, 0) else now.time()
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
    
    setups.sort(key=lambda s: (s.cone.pivot.name != (best_cone.pivot.name if best_cone else ""), 
                               not s.is_confluent, -s.cone.width))
    best_setup = setups[0] if setups else None
    
    em_low, em_high = zone.get_expected_move()
    
    # =========================================================================
    # RENDER
    # =========================================================================
    
    # Header Row
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("⚡ SPX Prophet")
        st.caption("Institutional SPX Prediction System")
    with col2:
        st.metric("S&P 500", f"{spx:,.2f}")
    
    # Status Bar
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Phase", f"{phase_icon} {phase_name}")
    c2.metric("Time (CT)", now.strftime('%I:%M %p'))
    c3.metric("Expected Move", f"{em_low:.0f} - {em_high:.0f} pts")
    c4.metric("VIX Zone Size", f"{zone.size:.2f}")
    
    st.divider()
    
    # =========================================================================
    # MAIN LAYOUT: Chart + Key Info
    # =========================================================================
    
    tab1, tab2, tab3 = st.tabs(["📈 Trading View", "📊 Analysis", "⚙️ Details"])
    
    with tab1:
        # Chart
        intraday = fetch_intraday()
        fig = create_chart(intraday, cones, best_setup, spx)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Bias + Algo Triggers + Expected Move
        c1, c2, c3 = st.columns(3)
        
        with c1:
            if bias == Bias.CALLS:
                st.success(f"### {bias.arrow} {bias.label}")
            elif bias == Bias.PUTS:
                st.error(f"### {bias.arrow} {bias.label}")
            else:
                st.warning(f"### {bias.arrow} {bias.label}")
            st.caption(f"Confidence: {confidence.dots} {confidence.label}")
            st.write(explanation)
        
        with c2:
            st.markdown("### Algo Triggers")
            st.metric("Current VIX", f"{zone.current:.2f}", f"Zone: {zone.current_zone}")
            tc1, tc2 = st.columns(2)
            with tc1:
                st.success(f"**↑ BUY**\n\n{zone.nearest_buy_trigger:.2f}\n\n{zone.distance_to_buy:+.2f} away")
            with tc2:
                st.error(f"**↓ SELL**\n\n{zone.nearest_sell_trigger:.2f}\n\n{zone.distance_to_sell:.2f} away")
        
        with c3:
            st.markdown("### Expected Move")
            st.metric("Points from Entry", f"{em_low:.0f} - {em_high:.0f}")
            st.caption(f"Based on VIX zone size: {zone.size:.2f}")
            st.info(f"Zone: {zone.bottom:.2f} - {zone.top:.2f}")
        
        st.divider()
        
        # =====================================================================
        # BEST SETUP + POSITION SIZING
        # =====================================================================
        
        if best_setup:
            c1, c2 = st.columns([2, 1])
            
            with c1:
                if best_setup.direction == Bias.CALLS:
                    st.success(f"### ⭐ {best_setup.direction.arrow} {best_setup.direction.label} — {best_setup.cone.pivot.name} Cone")
                else:
                    st.error(f"### ⭐ {best_setup.direction.arrow} {best_setup.direction.label} — {best_setup.cone.pivot.name} Cone")
                
                if best_setup.is_confluent:
                    st.info("🎯 **CONFLUENCE DETECTED** — Multiple cones converge at this level")
                
                # Entry, Stop, Targets
                ec1, ec2, ec3, ec4, ec5 = st.columns(5)
                ec1.metric("Entry", f"{best_setup.entry:,.2f}")
                ec2.metric("Stop (-6 pts)", f"{best_setup.stop:,.2f}")
                ec3.metric("T1 (12.5%)", f"{best_setup.target_1:,.2f}")
                ec4.metric("T2 (25%)", f"{best_setup.target_2:,.2f}")
                ec5.metric("T3 (50%)", f"{best_setup.target_3:,.2f}")
                
                # Additional metrics
                distance = spx - best_setup.entry
                rr = engine.calculate_profit(best_setup.reward_2, 1) / engine.calculate_profit(Config.STOP_LOSS_PTS, 1)
                
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("Distance", f"{distance:+.1f} pts")
                mc2.metric("Strike", f"{best_setup.strike}")
                mc3.metric("Width", f"{best_setup.cone.width:.1f} pts")
                mc4.metric("R:R @ T2", f"{rr:.1f}:1")
            
            with c2:
                st.markdown("### Position Calculator")
                
                # Contract selector
                contracts = st.selectbox("Contracts", [1, 2, 3, 5, 10, 15, 20], index=0)
                
                # Calculate P&L
                risk = engine.calculate_profit(Config.STOP_LOSS_PTS, contracts)
                p1 = engine.calculate_profit(best_setup.reward_1, contracts)
                p2 = engine.calculate_profit(best_setup.reward_2, contracts)
                p3 = engine.calculate_profit(best_setup.reward_3, contracts)
                
                st.divider()
                
                st.error(f"**Max Loss:** -${risk:,.0f}")
                st.success(f"**@ T1 (12.5%):** +${p1:,.0f}")
                st.success(f"**@ T2 (25%):** +${p2:,.0f}")
                st.success(f"**@ T3 (50%):** +${p3:,.0f}")
                
                st.divider()
                
                # Quick P&L Table for 1, 5, 10 contracts
                st.caption("Quick P&L Reference")
                pnl_data = []
                for c in [1, 5, 10]:
                    pnl_data.append({
                        "Contracts": c,
                        "Risk": f"-${engine.calculate_profit(Config.STOP_LOSS_PTS, c):,.0f}",
                        "T1": f"+${engine.calculate_profit(best_setup.reward_1, c):,.0f}",
                        "T2": f"+${engine.calculate_profit(best_setup.reward_2, c):,.0f}",
                        "T3": f"+${engine.calculate_profit(best_setup.reward_3, c):,.0f}"
                    })
                st.dataframe(pd.DataFrame(pnl_data), hide_index=True, use_container_width=True)
        
        else:
            if bias == Bias.WAIT:
                st.info("📊 VIX in Base Zone. Potential trend day. Waiting for boundary touch...")
            else:
                st.warning("No valid setups. Cones may not meet minimum width requirement (18 pts).")
    
    with tab2:
        # =====================================================================
        # PIVOT TABLE
        # =====================================================================
        
        st.markdown("### 📍 Pivot Table")
        
        pivot_data = []
        for p in pivots:
            pivot_data.append({
                "Pivot": p.name,
                "Price": f"{p.price:,.2f}",
                "Time": p.timestamp.strftime('%I:%M %p'),
                "Type": p.pivot_type.title()
            })
        
        st.dataframe(pd.DataFrame(pivot_data), hide_index=True, use_container_width=True)
        
        st.divider()
        
        # =====================================================================
        # VIX LADDER
        # =====================================================================
        
        st.markdown("### 📶 VIX Zone Ladder")
        
        c1, c2 = st.columns(2)
        
        with c1:
            ladder_data = []
            for label, value in [("+3", zone.get_extension(3)), 
                                  ("+2", zone.get_extension(2)),
                                  ("+1", zone.get_extension(1)),
                                  ("TOP", zone.top),
                                  ("CURRENT", zone.current),
                                  ("BOTTOM", zone.bottom),
                                  ("-1", zone.get_extension(-1)),
                                  ("-2", zone.get_extension(-2)),
                                  ("-3", zone.get_extension(-3))]:
                marker = "👉" if label == "CURRENT" else ""
                ladder_data.append({"Level": f"{marker} {label}", "VIX": f"{value:.2f}"})
            
            st.dataframe(pd.DataFrame(ladder_data), hide_index=True, use_container_width=True)
        
        with c2:
            st.markdown("**Zone Info**")
            st.write(f"• **Top Boundary:** {zone.top:.2f}")
            st.write(f"• **Bottom Boundary:** {zone.bottom:.2f}")
            st.write(f"• **Zone Size:** {zone.size:.2f}")
            st.write(f"• **Current VIX:** {zone.current:.2f}")
            st.write(f"• **Current Zone:** {zone.current_zone}")
            
            st.divider()
            
            st.write(f"• **Buy Trigger:** {zone.nearest_buy_trigger:.2f} ({zone.distance_to_buy:+.2f})")
            st.write(f"• **Sell Trigger:** {zone.nearest_sell_trigger:.2f} ({zone.distance_to_sell:.2f})")
        
        st.divider()
        
        # =====================================================================
        # CONFLUENCE ZONES
        # =====================================================================
        
        st.markdown("### 🎯 Confluence Zones")
        
        if support or resistance:
            c1, c2 = st.columns(2)
            
            with c1:
                st.markdown("**Support (Descending Rails)**")
                if support:
                    for level in support:
                        stars = "⭐⭐⭐" if level.strength == "strong" else "⭐⭐"
                        st.success(f"{stars} **{level.price:,.2f}**\n\n{', '.join(level.cones)}")
                else:
                    st.caption("No support confluence detected")
            
            with c2:
                st.markdown("**Resistance (Ascending Rails)**")
                if resistance:
                    for level in resistance:
                        stars = "⭐⭐⭐" if level.strength == "strong" else "⭐⭐"
                        st.error(f"{stars} **{level.price:,.2f}**\n\n{', '.join(level.cones)}")
                else:
                    st.caption("No resistance confluence detected")
        else:
            st.info("No confluence zones detected. Rails are more than 6 points apart.")
    
    with tab3:
        # =====================================================================
        # CONE RAILS TABLE
        # =====================================================================
        
        st.markdown("### 📐 Cone Rails")
        
        cone_data = []
        for c in cones:
            is_best = best_cone and c.pivot.name == best_cone.pivot.name
            status = "⭐ BEST" if is_best else ("✓ Valid" if c.is_tradeable else "✗ Too Narrow")
            cone_data.append({
                "Pivot": c.pivot.name,
                "Ascending ↑": f"{c.ascending:,.2f}",
                "Descending ↓": f"{c.descending:,.2f}",
                "Width": f"{c.width:.1f}",
                "Blocks": c.blocks,
                "Status": status
            })
        
        st.dataframe(pd.DataFrame(cone_data), hide_index=True, use_container_width=True)
        
        st.divider()
        
        # =====================================================================
        # ALL SETUPS TABLE
        # =====================================================================
        
        st.markdown("### 📋 All Trade Setups")
        
        if setups:
            setup_data = []
            for i, s in enumerate(setups):
                is_best = "⭐" if i == 0 else ""
                conf = "🎯" if s.is_confluent else ""
                setup_data.append({
                    "": f"{is_best}{conf}",
                    "Direction": f"{s.direction.arrow} {s.direction.label}",
                    "Cone": s.cone.pivot.name,
                    "Entry": f"{s.entry:,.2f}",
                    "Stop": f"{s.stop:,.2f}",
                    "T1": f"{s.target_1:,.2f}",
                    "T2": f"{s.target_2:,.2f}",
                    "T3": f"{s.target_3:,.2f}",
                    "Strike": s.strike,
                    "Width": f"{s.cone.width:.1f}"
                })
            
            st.dataframe(pd.DataFrame(setup_data), hide_index=True, use_container_width=True)
        else:
            st.info("No valid setups available.")
        
        st.divider()
        
        # =====================================================================
        # TRADING RULES REMINDER
        # =====================================================================
        
        st.markdown("### 📖 Trading Rules")
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("""
            **Entry Rules:**
            - Enter at descending rail for CALLS
            - Enter at ascending rail for PUTS
            - Wait for price to touch the rail
            - Confirm VIX at boundary trigger
            """)
        
        with c2:
            st.markdown(f"""
            **Risk Management:**
            - Stop Loss: {Config.STOP_LOSS_PTS} points
            - T1: 12.5% of cone width
            - T2: 25% of cone width
            - T3: 50% of cone width
            - Min cone width: {Config.MIN_CONE_WIDTH} points
            """)
    
    # Footer
    st.divider()
    st.caption("SPX Prophet v7.1 | Institutional SPX Prediction System | Not Financial Advice")


if __name__ == "__main__":
    main()
