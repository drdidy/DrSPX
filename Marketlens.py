"""
SPX PROPHET v6.0 - LEGENDARY EDITION
The Institutional SPX Prediction System

Predicts SPX moves using VIX algo trigger zones, structural cones, and time-based analysis.
Features proprietary Expected Move formula and Cone Confluence detection.

Chart-centric design with premium aesthetics.
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
# PREMIUM LIGHT THEME - LEGENDARY EDITION
# =============================================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
    --bg-primary: #ffffff;
    --bg-secondary: #f8fafc;
    --bg-tertiary: #f1f5f9;
    --border-light: #e2e8f0;
    --border-medium: #cbd5e1;
    --text-primary: #0f172a;
    --text-secondary: #334155;
    --text-muted: #64748b;
    --text-faint: #94a3b8;
    --accent-blue: #3b82f6;
    --accent-green: #059669;
    --accent-red: #dc2626;
    --accent-amber: #d97706;
    --accent-purple: #7c3aed;
    --gradient-green: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
    --gradient-red: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
    --gradient-blue: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    --gradient-amber: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.04);
    --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.03);
    --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -4px rgba(0,0,0,0.03);
    --shadow-glow-green: 0 0 20px rgba(5, 150, 105, 0.15);
    --shadow-glow-red: 0 0 20px rgba(220, 38, 38, 0.15);
    --shadow-glow-blue: 0 0 20px rgba(59, 130, 246, 0.15);
}

/* Base */
.stApp {
    background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    border-right: 1px solid var(--border-light);
}

section[data-testid="stSidebar"] .stMarkdown {
    color: var(--text-secondary);
}

/* Hide Streamlit */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display: none;}

/* Metrics */
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    color: var(--text-primary);
}

[data-testid="stMetricLabel"] {
    font-family: 'Inter', sans-serif;
    color: var(--text-muted);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.5px;
}

/* Inputs */
div[data-baseweb="input"] > div {
    background: var(--bg-primary);
    border: 1px solid var(--border-light);
    border-radius: 10px;
    transition: all 0.2s ease;
}

div[data-baseweb="input"] > div:focus-within {
    border-color: var(--accent-blue);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
    color: white;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
    padding: 10px 24px;
    transition: all 0.2s ease;
    box-shadow: var(--shadow-md);
}

.stButton > button:hover {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    box-shadow: var(--shadow-lg), var(--shadow-glow-blue);
    transform: translateY(-1px);
}

/* Dataframe */
.stDataFrame {
    border: 1px solid var(--border-light);
    border-radius: 12px;
    overflow: hidden;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: var(--bg-tertiary);
    padding: 4px;
    border-radius: 12px;
}

.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: var(--text-muted);
    border-radius: 8px;
    padding: 10px 24px;
    font-weight: 600;
    font-family: 'Inter', sans-serif;
}

.stTabs [aria-selected="true"] {
    background: var(--bg-primary);
    color: var(--text-primary);
    box-shadow: var(--shadow-sm);
}

/* Plotly Chart Container */
.js-plotly-plot {
    border-radius: 16px;
    overflow: hidden;
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


class Phase(Enum):
    ZONE_BUILDING = ("Zone Building", "#6366f1", "🌙", "5pm-6am CT")
    ZONE_LOCKED = ("Zone Locked", "#0ea5e9", "🔒", "6am+ CT")
    PRE_RTH = ("Pre-RTH", "#8b5cf6", "⏳", "6am-9:30am CT")
    RTH = ("RTH Active", "#059669", "🟢", "9:30am-4pm CT")
    POST = ("Post Session", "#64748b", "📊", "After 4pm CT")
    CLOSED = ("Closed", "#94a3b8", "⭘", "Weekend")
    
    def __init__(self, label, color, icon, time_range):
        self.label = label
        self.color = color
        self.icon = icon
        self.time_range = time_range


class Bias(Enum):
    CALLS = ("CALLS", "#059669", "↑")
    PUTS = ("PUTS", "#dc2626", "↓")
    WAIT = ("WAIT", "#d97706", "◆")
    
    def __init__(self, label, color, arrow):
        self.label = label
        self.color = color
        self.arrow = arrow


class Confidence(Enum):
    HIGH = ("HIGH", "●●●", "#059669")
    MEDIUM = ("MEDIUM", "●●○", "#d97706")
    LOW = ("LOW", "●○○", "#dc2626")
    NONE = ("NONE", "○○○", "#94a3b8")
    
    def __init__(self, label, dots, color):
        self.label = label
        self.dots = dots
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
    def distance_to_buy_trigger(self) -> float:
        return round(self.nearest_buy_trigger - self.current, 2)
    
    @property
    def distance_to_sell_trigger(self) -> float:
        return round(self.current - self.nearest_sell_trigger, 2)
    
    def get_extension(self, level: int) -> float:
        if level > 0:
            return round(self.top + (level * self.size), 2)
        elif level < 0:
            return round(self.bottom + (level * self.size), 2)
        return self.top if level == 0 else self.bottom
    
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
    confluence_cones: List[str] = None
    
    @property
    def reward_1_pts(self) -> float:
        return abs(self.target_1 - self.entry)
    
    @property
    def reward_2_pts(self) -> float:
        return abs(self.target_2 - self.entry)
    
    @property
    def reward_3_pts(self) -> float:
        return abs(self.target_3 - self.entry)


@dataclass
class LevelHit:
    level_name: str
    level_price: float
    was_hit: bool
    hit_time: Optional[str] = None


# =============================================================================
# ENGINE
# =============================================================================

class SPXProphetEngine:
    def __init__(self):
        self.ct_tz = pytz.timezone('America/Chicago')
    
    def get_current_time_ct(self) -> datetime:
        return datetime.now(self.ct_tz)
    
    def get_phase(self, dt: datetime = None) -> Phase:
        if dt is None:
            dt = self.get_current_time_ct()
        elif dt.tzinfo is None:
            dt = self.ct_tz.localize(dt)
        else:
            dt = dt.astimezone(self.ct_tz)
        
        t = dt.time()
        weekday = dt.weekday()
        
        if weekday >= 5:
            return Phase.CLOSED
        
        if time(17, 0) <= t or t < time(6, 0):
            return Phase.ZONE_BUILDING
        elif time(6, 0) <= t < time(9, 30):
            return Phase.PRE_RTH
        elif time(9, 30) <= t < time(16, 0):
            return Phase.RTH
        elif time(16, 0) <= t < time(17, 0):
            return Phase.POST
        
        return Phase.CLOSED
    
    def determine_bias(self, zone: VIXZone) -> Tuple[Bias, Confidence, str]:
        dist_to_buy = zone.distance_to_buy_trigger
        dist_to_sell = zone.distance_to_sell_trigger
        current_zone = zone.current_zone
        
        if dist_to_buy <= 0.05 and dist_to_buy >= -0.05:
            return Bias.CALLS, Confidence.HIGH, f"VIX at buy trigger ({zone.nearest_buy_trigger:.2f}). Buy algos active → SPX UP"
        
        if dist_to_sell <= 0.05 and dist_to_sell >= -0.05:
            return Bias.PUTS, Confidence.HIGH, f"VIX at sell trigger ({zone.nearest_sell_trigger:.2f}). Sell algos active → SPX DOWN"
        
        if "+" in current_zone:
            conf = Confidence.MEDIUM if dist_to_buy > 0.10 else Confidence.LOW
            return Bias.PUTS, conf, f"VIX in {current_zone} zone. Put bias until buy trigger at {zone.nearest_buy_trigger:.2f}"
        
        if "-" in current_zone:
            conf = Confidence.MEDIUM if dist_to_sell > 0.10 else Confidence.LOW
            return Bias.CALLS, conf, f"VIX in {current_zone} zone. Call bias until sell trigger at {zone.nearest_sell_trigger:.2f}"
        
        return Bias.WAIT, Confidence.NONE, "VIX in Base Zone. Potential trend day. Wait for boundary touch."
    
    def calculate_blocks(self, pivot_time: datetime, eval_time: datetime) -> int:
        if pivot_time.tzinfo is None:
            pivot_time = self.ct_tz.localize(pivot_time)
        if eval_time.tzinfo is None:
            eval_time = self.ct_tz.localize(eval_time)
        diff = eval_time - pivot_time
        total_minutes = diff.total_seconds() / 60
        return max(int(total_minutes / 30), 1)
    
    def calculate_cone(self, pivot: Pivot, eval_time: datetime) -> ConeRails:
        blocks = self.calculate_blocks(pivot.timestamp, eval_time)
        expansion = blocks * Config.SLOPE_PER_30MIN
        ascending = round(pivot.price + expansion, 2)
        descending = round(pivot.price - expansion, 2)
        width = round(ascending - descending, 2)
        return ConeRails(pivot=pivot, ascending=ascending, descending=descending, width=width, blocks=blocks)
    
    def find_confluence(self, cones: List[ConeRails]) -> Tuple[List[ConfluentLevel], List[ConfluentLevel]]:
        support_levels = []
        resistance_levels = []
        
        ascending_rails = [(c.ascending, c.pivot.name) for c in cones if c.is_tradeable]
        descending_rails = [(c.descending, c.pivot.name) for c in cones if c.is_tradeable]
        
        for i, (price1, name1) in enumerate(ascending_rails):
            confluent_cones = [name1]
            for j, (price2, name2) in enumerate(ascending_rails):
                if i != j and abs(price1 - price2) <= Config.CONFLUENCE_THRESHOLD:
                    confluent_cones.append(name2)
            if len(confluent_cones) >= 2:
                avg_price = sum(p for p, n in ascending_rails if n in confluent_cones) / len(confluent_cones)
                strength = "strong" if len(confluent_cones) >= 3 else "moderate"
                if not any(abs(r.price - avg_price) < 1 for r in resistance_levels):
                    resistance_levels.append(ConfluentLevel(round(avg_price, 2), "resistance", confluent_cones, strength))
        
        for i, (price1, name1) in enumerate(descending_rails):
            confluent_cones = [name1]
            for j, (price2, name2) in enumerate(descending_rails):
                if i != j and abs(price1 - price2) <= Config.CONFLUENCE_THRESHOLD:
                    confluent_cones.append(name2)
            if len(confluent_cones) >= 2:
                avg_price = sum(p for p, n in descending_rails if n in confluent_cones) / len(confluent_cones)
                strength = "strong" if len(confluent_cones) >= 3 else "moderate"
                if not any(abs(s.price - avg_price) < 1 for s in support_levels):
                    support_levels.append(ConfluentLevel(round(avg_price, 2), "support", confluent_cones, strength))
        
        return support_levels, resistance_levels
    
    def generate_setup(self, cone: ConeRails, direction: Bias, 
                      support_confluence: List[ConfluentLevel] = None,
                      resistance_confluence: List[ConfluentLevel] = None) -> Optional[TradeSetup]:
        if not cone.is_tradeable or direction == Bias.WAIT:
            return None
        
        support_confluence = support_confluence or []
        resistance_confluence = resistance_confluence or []
        
        if direction == Bias.CALLS:
            entry = cone.descending
            opposite = cone.ascending
            stop = entry - Config.STOP_LOSS_PTS
            strike = int(round((entry - Config.STRIKE_OTM_DISTANCE) / 5) * 5)
            move = opposite - entry
            t1 = entry + (move * Config.TARGET_1_PCT)
            t2 = entry + (move * Config.TARGET_2_PCT)
            t3 = entry + (move * Config.TARGET_3_PCT)
            is_confluent = any(abs(c.price - entry) <= Config.CONFLUENCE_THRESHOLD for c in support_confluence)
            conf_cones = [c.cones for c in support_confluence if abs(c.price - entry) <= Config.CONFLUENCE_THRESHOLD]
        else:
            entry = cone.ascending
            opposite = cone.descending
            stop = entry + Config.STOP_LOSS_PTS
            strike = int(round((entry + Config.STRIKE_OTM_DISTANCE) / 5) * 5)
            move = entry - opposite
            t1 = entry - (move * Config.TARGET_1_PCT)
            t2 = entry - (move * Config.TARGET_2_PCT)
            t3 = entry - (move * Config.TARGET_3_PCT)
            is_confluent = any(abs(c.price - entry) <= Config.CONFLUENCE_THRESHOLD for c in resistance_confluence)
            conf_cones = [c.cones for c in resistance_confluence if abs(c.price - entry) <= Config.CONFLUENCE_THRESHOLD]
        
        return TradeSetup(
            direction=direction, cone=cone, entry=round(entry, 2), stop=round(stop, 2),
            target_1=round(t1, 2), target_2=round(t2, 2), target_3=round(t3, 2),
            strike=strike, is_confluent=is_confluent,
            confluence_cones=conf_cones[0] if conf_cones else None
        )
    
    def calculate_profit(self, points: float, contracts: int = 1) -> float:
        return round(points * Config.DELTA * Config.CONTRACT_MULTIPLIER * contracts, 2)
    
    def calculate_max_contracts(self, risk_budget: float) -> int:
        risk_per = self.calculate_profit(Config.STOP_LOSS_PTS, 1)
        return int(risk_budget / risk_per) if risk_per > 0 else 0
    
    def analyze_level_hits(self, setup: TradeSetup, session_high: float, session_low: float) -> List[LevelHit]:
        hits = []
        is_calls = setup.direction == Bias.CALLS
        
        entry_hit = (session_low <= setup.entry) if is_calls else (session_high >= setup.entry)
        hits.append(LevelHit("Entry", setup.entry, entry_hit))
        
        if entry_hit:
            stop_hit = (session_low <= setup.stop) if is_calls else (session_high >= setup.stop)
            hits.append(LevelHit("Stop", setup.stop, stop_hit))
            for name, price in [("T1 (12.5%)", setup.target_1), ("T2 (25%)", setup.target_2), ("T3 (50%)", setup.target_3)]:
                target_hit = (session_high >= price) if is_calls else (session_low <= price)
                hits.append(LevelHit(name, price, target_hit))
        else:
            hits.append(LevelHit("Stop", setup.stop, False))
            hits.append(LevelHit("T1 (12.5%)", setup.target_1, False))
            hits.append(LevelHit("T2 (25%)", setup.target_2, False))
            hits.append(LevelHit("T3 (50%)", setup.target_3, False))
        
        return hits
    
    def calculate_theoretical_pnl(self, setup: TradeSetup, hits: List[LevelHit], contracts: int = 1) -> Tuple[float, str]:
        entry_hit = next((h for h in hits if h.level_name == "Entry"), None)
        if not entry_hit or not entry_hit.was_hit:
            return 0.0, "Entry not reached"
        
        stop_hit = next((h for h in hits if h.level_name == "Stop"), None)
        if stop_hit and stop_hit.was_hit:
            return -self.calculate_profit(Config.STOP_LOSS_PTS, contracts), "Stopped out"
        
        target_hits = [h for h in hits if "T1" in h.level_name or "T2" in h.level_name or "T3" in h.level_name]
        target_hits = [h for h in target_hits if h.was_hit]
        
        if not target_hits:
            return 0.0, "Entry hit, targets pending"
        
        target_order = {"T1 (12.5%)": 1, "T2 (25%)": 2, "T3 (50%)": 3}
        highest = max(target_hits, key=lambda h: target_order.get(h.level_name, 0))
        points = abs(highest.level_price - setup.entry)
        return self.calculate_profit(points, contracts), f"{highest.level_name} hit"


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
            prior = {'date': hist.index[-2], 'open': float(p['Open']), 'high': float(p['High']), 
                    'low': float(p['Low']), 'close': float(p['Close'])}
        return current, prior
    except:
        return None, None


@st.cache_data(ttl=300)
def fetch_historical_spx(target_date: date) -> Optional[Dict]:
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
                return {'date': idx, 'open': float(row['Open']), 'high': float(row['High']),
                       'low': float(row['Low']), 'close': float(row['Close']), 
                       'range': float(row['High'] - row['Low'])}
        return None
    except:
        return None


@st.cache_data(ttl=300)
def fetch_prior_day_data(session_date: date) -> Optional[Dict]:
    try:
        spx = yf.Ticker("^GSPC")
        start = session_date - timedelta(days=10)
        end = session_date + timedelta(days=1)
        hist = spx.history(start=start, end=end)
        if hist.empty or len(hist) < 2:
            return None
        session_str = session_date.strftime('%Y-%m-%d')
        session_idx = None
        for i, idx in enumerate(hist.index):
            if idx.strftime('%Y-%m-%d') == session_str:
                session_idx = i
                break
        if session_idx is not None and session_idx > 0:
            prior = hist.iloc[session_idx - 1]
            return {'date': hist.index[session_idx - 1], 'high': float(prior['High']),
                   'low': float(prior['Low']), 'close': float(prior['Close']), 'open': float(prior['Open'])}
        if len(hist) >= 2:
            prior = hist.iloc[-2]
            return {'date': hist.index[-2], 'high': float(prior['High']), 'low': float(prior['Low']),
                   'close': float(prior['Close']), 'open': float(prior['Open'])}
        return None
    except:
        return None


@st.cache_data(ttl=60)
def fetch_intraday_spx() -> Optional[pd.DataFrame]:
    try:
        spx = yf.Ticker("^GSPC")
        hist = spx.history(period="2d", interval="30m")
        return hist if not hist.empty else None
    except:
        return None


# =============================================================================
# LEGENDARY CHART
# =============================================================================

def create_legendary_chart(intraday_data: pd.DataFrame, cones: List[ConeRails], 
                          best_setup: Optional[TradeSetup], spx_price: float) -> go.Figure:
    """Create a stunning, professional candlestick chart with cone projections"""
    
    fig = go.Figure()
    
    if intraday_data is not None and not intraday_data.empty:
        today = datetime.now().date()
        today_data = intraday_data[intraday_data.index.date == today]
        if today_data.empty:
            today_data = intraday_data.tail(13)
        
        # Candlesticks
        fig.add_trace(go.Candlestick(
            x=today_data.index,
            open=today_data['Open'],
            high=today_data['High'],
            low=today_data['Low'],
            close=today_data['Close'],
            name='SPX',
            increasing=dict(line=dict(color='#10b981', width=1.5), fillcolor='#d1fae5'),
            decreasing=dict(line=dict(color='#ef4444', width=1.5), fillcolor='#fee2e2'),
            whiskerwidth=0.8
        ))
        
        price_min = today_data['Low'].min()
        price_max = today_data['High'].max()
    else:
        price_min = spx_price - 30
        price_max = spx_price + 30
    
    # Cone colors - premium palette
    cone_colors = {
        'Prior High': '#f59e0b',
        'Prior Low': '#3b82f6', 
        'Prior Close': '#8b5cf6',
        'High²': '#f97316',
        'Low²': '#06b6d4'
    }
    
    # Add cone rails as horizontal lines
    for cone in cones:
        if not cone.is_tradeable:
            continue
        
        color = cone_colors.get(cone.pivot.name, '#64748b')
        
        # Ascending (resistance)
        fig.add_hline(
            y=cone.ascending,
            line=dict(color=color, width=2, dash='dot'),
            annotation=dict(
                text=f"▲ {cone.pivot.name} {cone.ascending:.0f}",
                font=dict(size=11, color=color, family='JetBrains Mono'),
                bgcolor='rgba(255,255,255,0.9)',
                bordercolor=color,
                borderwidth=1,
                borderpad=4
            ),
            annotation_position="right"
        )
        
        # Descending (support)
        fig.add_hline(
            y=cone.descending,
            line=dict(color=color, width=2, dash='dot'),
            annotation=dict(
                text=f"▼ {cone.pivot.name} {cone.descending:.0f}",
                font=dict(size=11, color=color, family='JetBrains Mono'),
                bgcolor='rgba(255,255,255,0.9)',
                bordercolor=color,
                borderwidth=1,
                borderpad=4
            ),
            annotation_position="right"
        )
        
        price_min = min(price_min, cone.descending - 5)
        price_max = max(price_max, cone.ascending + 5)
    
    # Best setup entry/stop/targets
    if best_setup:
        # Entry line - thick and prominent
        entry_color = '#10b981' if best_setup.direction == Bias.CALLS else '#ef4444'
        
        fig.add_hline(
            y=best_setup.entry,
            line=dict(color=entry_color, width=3),
            annotation=dict(
                text=f"◉ ENTRY {best_setup.entry:.0f}",
                font=dict(size=12, color='white', family='JetBrains Mono', weight='bold'),
                bgcolor=entry_color,
                borderpad=6
            ),
            annotation_position="left"
        )
        
        # Stop loss
        fig.add_hline(
            y=best_setup.stop,
            line=dict(color='#dc2626', width=2, dash='dash'),
            annotation=dict(
                text=f"✕ STOP {best_setup.stop:.0f}",
                font=dict(size=10, color='#dc2626', family='JetBrains Mono'),
                bgcolor='rgba(254,226,226,0.95)',
                bordercolor='#dc2626',
                borderwidth=1,
                borderpad=4
            ),
            annotation_position="left"
        )
        
        # Targets
        target_colors = ['#059669', '#047857', '#065f46']
        for i, (name, price) in enumerate([("T1", best_setup.target_1), ("T2", best_setup.target_2), ("T3", best_setup.target_3)]):
            fig.add_hline(
                y=price,
                line=dict(color=target_colors[i], width=1.5, dash='dash'),
                annotation=dict(
                    text=f"🎯 {name} {price:.0f}",
                    font=dict(size=10, color=target_colors[i], family='JetBrains Mono'),
                    bgcolor='rgba(220,252,231,0.95)',
                    bordercolor=target_colors[i],
                    borderwidth=1,
                    borderpad=3
                ),
                annotation_position="left"
            )
            price_max = max(price_max, price + 3)
            price_min = min(price_min, price - 3)
    
    # Current price line
    fig.add_hline(
        y=spx_price,
        line=dict(color='#1e293b', width=1, dash='solid'),
        annotation=dict(
            text=f"● NOW {spx_price:.2f}",
            font=dict(size=11, color='#1e293b', family='JetBrains Mono'),
            bgcolor='rgba(241,245,249,0.95)',
            borderpad=4
        ),
        annotation_position="right"
    )
    
    # Layout - premium styling
    padding = (price_max - price_min) * 0.08
    
    fig.update_layout(
        title=None,
        height=420,
        margin=dict(l=10, r=140, t=20, b=10),
        xaxis=dict(
            rangeslider=dict(visible=False),
            showgrid=True,
            gridcolor='rgba(226,232,240,0.6)',
            gridwidth=1,
            tickfont=dict(size=10, color='#64748b', family='Inter'),
            showline=True,
            linewidth=1,
            linecolor='#e2e8f0'
        ),
        yaxis=dict(
            side='left',
            showgrid=True,
            gridcolor='rgba(226,232,240,0.6)',
            gridwidth=1,
            tickfont=dict(size=11, color='#1e293b', family='JetBrains Mono'),
            tickformat=',.0f',
            range=[price_min - padding, price_max + padding],
            showline=True,
            linewidth=1,
            linecolor='#e2e8f0'
        ),
        plot_bgcolor='#ffffff',
        paper_bgcolor='#ffffff',
        showlegend=False,
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='white',
            font_size=12,
            font_family='JetBrains Mono'
        )
    )
    
    return fig


# =============================================================================
# LEGENDARY UI COMPONENTS
# =============================================================================

def render_legendary_header(spx: float, phase: Phase, engine: SPXProphetEngine):
    now = engine.get_current_time_ct()
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 50%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        padding: 24px 32px;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.03);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 20px;">
            <div style="display: flex; align-items: center; gap: 16px;">
                <div style="
                    width: 56px; height: 56px;
                    background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                    border-radius: 14px;
                    display: flex; align-items: center; justify-content: center;
                    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
                ">
                    <span style="font-size: 28px;">⚡</span>
                </div>
                <div>
                    <h1 style="
                        font-family: 'Inter', sans-serif;
                        font-size: 1.75rem;
                        font-weight: 800;
                        color: #0f172a;
                        margin: 0;
                        letter-spacing: -0.5px;
                    ">SPX Prophet</h1>
                    <p style="
                        font-family: 'Inter', sans-serif;
                        font-size: 0.8rem;
                        color: #64748b;
                        font-weight: 500;
                        margin: 2px 0 0 0;
                        letter-spacing: 0.3px;
                    ">Institutional SPX Prediction System</p>
                </div>
            </div>
            
            <div style="display: flex; align-items: center; gap: 32px;">
                <div style="text-align: right;">
                    <p style="
                        font-family: 'Inter', sans-serif;
                        font-size: 0.65rem;
                        font-weight: 700;
                        color: #94a3b8;
                        text-transform: uppercase;
                        letter-spacing: 1px;
                        margin: 0 0 4px 0;
                    ">S&P 500</p>
                    <p style="
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 2.25rem;
                        font-weight: 700;
                        color: #0f172a;
                        margin: 0;
                        letter-spacing: -1px;
                    ">{spx:,.2f}</p>
                </div>
                
                <div style="width: 1px; height: 50px; background: #e2e8f0;"></div>
                
                <div style="text-align: right;">
                    <p style="
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 0.9rem;
                        font-weight: 600;
                        color: #64748b;
                        margin: 0 0 4px 0;
                    ">{now.strftime('%I:%M %p')} CT</p>
                    <div style="
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        background: {phase.color}15;
                        padding: 6px 12px;
                        border-radius: 8px;
                        border: 1px solid {phase.color}30;
                    ">
                        <span style="font-size: 14px;">{phase.icon}</span>
                        <span style="
                            font-family: 'Inter', sans-serif;
                            font-size: 0.8rem;
                            font-weight: 600;
                            color: {phase.color};
                        ">{phase.label}</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_bias_card_compact(bias: Bias, confidence: Confidence, explanation: str):
    if bias == Bias.CALLS:
        gradient = "linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)"
        border_color = "#10b981"
        glow = "0 0 20px rgba(16, 185, 129, 0.15)"
    elif bias == Bias.PUTS:
        gradient = "linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)"
        border_color = "#ef4444"
        glow = "0 0 20px rgba(239, 68, 68, 0.15)"
    else:
        gradient = "linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%)"
        border_color = "#f59e0b"
        glow = "0 0 20px rgba(245, 158, 11, 0.15)"
    
    st.markdown(f"""
    <div style="
        background: {gradient};
        border: 2px solid {border_color};
        border-radius: 16px;
        padding: 20px;
        box-shadow: {glow};
        height: 100%;
    ">
        <p style="
            font-family: 'Inter', sans-serif;
            font-size: 0.65rem;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin: 0 0 12px 0;
        ">Directional Bias</p>
        
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
            <span style="
                font-family: 'JetBrains Mono', monospace;
                font-size: 2rem;
                font-weight: 800;
                color: {bias.color};
                letter-spacing: -1px;
            ">{bias.arrow} {bias.label}</span>
        </div>
        
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
            <span style="
                font-family: 'JetBrains Mono', monospace;
                font-size: 1.1rem;
                color: {confidence.color};
                letter-spacing: 2px;
            ">{confidence.dots}</span>
            <span style="
                font-family: 'Inter', sans-serif;
                font-size: 0.7rem;
                font-weight: 600;
                color: {confidence.color};
                text-transform: uppercase;
            ">{confidence.label}</span>
        </div>
        
        <p style="
            font-family: 'Inter', sans-serif;
            font-size: 0.8rem;
            color: #475569;
            margin: 0;
            line-height: 1.4;
        ">{explanation}</p>
    </div>
    """, unsafe_allow_html=True)


def render_algo_triggers_compact(zone: VIXZone):
    st.markdown(f"""
    <div style="
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        height: 100%;
    ">
        <p style="
            font-family: 'Inter', sans-serif;
            font-size: 0.65rem;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin: 0 0 12px 0;
        ">Algo Triggers</p>
        
        <div style="display: flex; align-items: baseline; gap: 8px; margin-bottom: 16px;">
            <span style="
                font-family: 'JetBrains Mono', monospace;
                font-size: 1.5rem;
                font-weight: 700;
                color: #0f172a;
            ">{zone.current:.2f}</span>
            <span style="
                font-family: 'Inter', sans-serif;
                font-size: 0.75rem;
                font-weight: 600;
                color: #3b82f6;
                background: #eff6ff;
                padding: 3px 8px;
                border-radius: 6px;
            ">{zone.current_zone}</span>
        </div>
        
        <div style="
            background: linear-gradient(90deg, #dcfce7 0%, #bbf7d0 100%);
            border-left: 3px solid #10b981;
            padding: 10px 12px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 8px;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 600; color: #065f46;">↑ BUY TRIGGER</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; color: #059669;">{zone.nearest_buy_trigger:.2f}</span>
            </div>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #065f46;">{zone.distance_to_buy_trigger:+.2f} away</span>
        </div>
        
        <div style="
            background: linear-gradient(90deg, #fee2e2 0%, #fecaca 100%);
            border-left: 3px solid #ef4444;
            padding: 10px 12px;
            border-radius: 0 8px 8px 0;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 600; color: #991b1b;">↓ SELL TRIGGER</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; color: #dc2626;">{zone.nearest_sell_trigger:.2f}</span>
            </div>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #991b1b;">{zone.distance_to_sell_trigger:.2f} away</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_expected_move_compact(zone: VIXZone):
    em_low, em_high = zone.get_expected_move()
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        border: 1px solid #bfdbfe;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 0 20px rgba(59, 130, 246, 0.1);
        height: 100%;
    ">
        <p style="
            font-family: 'Inter', sans-serif;
            font-size: 0.65rem;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin: 0 0 12px 0;
        ">Expected Move</p>
        
        <p style="
            font-family: 'JetBrains Mono', monospace;
            font-size: 2.25rem;
            font-weight: 800;
            color: #1e40af;
            margin: 0;
            letter-spacing: -1px;
        ">{em_low:.0f} - {em_high:.0f}</p>
        
        <p style="
            font-family: 'Inter', sans-serif;
            font-size: 0.7rem;
            font-weight: 600;
            color: #3b82f6;
            margin: 8px 0 0 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        ">Points from Entry</p>
        
        <div style="
            margin-top: 12px;
            padding: 8px 12px;
            background: rgba(255,255,255,0.7);
            border-radius: 8px;
        ">
            <span style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: #475569;">
                VIX Zone: <strong>{zone.size:.2f}</strong>
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_best_setup_hero(setup: TradeSetup, spx: float, engine: SPXProphetEngine):
    if not setup:
        st.markdown("""
        <div style="
            background: #f8fafc;
            border: 2px dashed #e2e8f0;
            border-radius: 16px;
            padding: 40px;
            text-align: center;
        ">
            <p style="font-family: 'Inter', sans-serif; font-size: 1rem; color: #94a3b8; margin: 0;">
                Waiting for setup...
            </p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    distance = spx - setup.entry
    risk = engine.calculate_profit(Config.STOP_LOSS_PTS, 1)
    p1 = engine.calculate_profit(setup.reward_1_pts, 1)
    p2 = engine.calculate_profit(setup.reward_2_pts, 1)
    p3 = engine.calculate_profit(setup.reward_3_pts, 1)
    rr = p2 / risk if risk > 0 else 0
    
    if setup.direction == Bias.CALLS:
        gradient = "linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)"
        border = "#10b981"
        glow = "0 8px 32px rgba(16, 185, 129, 0.2)"
    else:
        gradient = "linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%)"
        border = "#ef4444"
        glow = "0 8px 32px rgba(239, 68, 68, 0.2)"
    
    confluence_badge = ""
    if setup.is_confluent:
        confluence_badge = '<span style="background: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 100%); color: white; padding: 4px 10px; border-radius: 20px; font-size: 0.7rem; font-weight: 600; margin-left: 10px;">🎯 CONFLUENCE</span>'
    
    st.markdown(f"""
    <div style="
        background: {gradient};
        border: 2px solid {border};
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: {glow};
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="
                    background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
                    padding: 6px 12px;
                    border-radius: 8px;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.7rem;
                    font-weight: 700;
                    color: #000;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">⭐ Best Setup</span>
                <span style="
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 1.5rem;
                    font-weight: 800;
                    color: {setup.direction.color};
                ">{setup.direction.arrow} {setup.direction.label}</span>
                {confluence_badge}
            </div>
            <span style="
                font-family: 'Inter', sans-serif;
                font-size: 0.8rem;
                font-weight: 600;
                color: #64748b;
            ">{setup.cone.pivot.name} Cone</span>
        </div>
        
        <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px;">
            <div style="
                background: rgba(255,255,255,0.9);
                padding: 16px;
                border-radius: 12px;
                text-align: center;
                border: 2px solid {setup.direction.color};
                box-shadow: 0 2px 8px rgba(0,0,0,0.04);
            ">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 6px 0;">Entry</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.25rem; font-weight: 700; color: #0f172a; margin: 0;">{setup.entry:,.2f}</p>
            </div>
            <div style="
                background: rgba(254,226,226,0.5);
                padding: 16px;
                border-radius: 12px;
                text-align: center;
                border: 1px solid #fca5a5;
            ">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 6px 0;">Stop</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.25rem; font-weight: 700; color: #dc2626; margin: 0;">{setup.stop:,.2f}</p>
            </div>
            <div style="background: rgba(255,255,255,0.7); padding: 16px; border-radius: 12px; text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 6px 0;">T1 (12.5%)</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.25rem; font-weight: 700; color: #059669; margin: 0;">{setup.target_1:,.2f}</p>
            </div>
            <div style="background: rgba(255,255,255,0.7); padding: 16px; border-radius: 12px; text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 6px 0;">T2 (25%)</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.25rem; font-weight: 700; color: #059669; margin: 0;">{setup.target_2:,.2f}</p>
            </div>
            <div style="background: rgba(255,255,255,0.7); padding: 16px; border-radius: 12px; text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 6px 0;">T3 (50%)</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.25rem; font-weight: 700; color: #059669; margin: 0;">{setup.target_3:,.2f}</p>
            </div>
        </div>
        
        <div style="
            display: flex;
            justify-content: space-between;
            padding-top: 16px;
            border-top: 1px solid rgba(0,0,0,0.08);
        ">
            <div style="text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin: 0 0 4px 0;">Distance</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.95rem; font-weight: 600; color: #334155; margin: 0;">{distance:+.1f} pts</p>
            </div>
            <div style="text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin: 0 0 4px 0;">Strike</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.95rem; font-weight: 600; color: #334155; margin: 0;">{setup.strike}</p>
            </div>
            <div style="text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin: 0 0 4px 0;">Width</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.95rem; font-weight: 600; color: #334155; margin: 0;">{setup.cone.width:.1f} pts</p>
            </div>
            <div style="text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin: 0 0 4px 0;">R:R @T2</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.95rem; font-weight: 600; color: #334155; margin: 0;">{rr:.1f}:1</p>
            </div>
            <div style="text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin: 0 0 4px 0;">Risk</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.95rem; font-weight: 600; color: #dc2626; margin: 0;">${risk:,.0f}</p>
            </div>
            <div style="text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin: 0 0 4px 0;">Profit @T2</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.95rem; font-weight: 600; color: #059669; margin: 0;">${p2:,.0f}</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_vix_ladder_compact(zone: VIXZone):
    levels = [
        ("+2", zone.get_extension(2), "#94a3b8", "#f8fafc"),
        ("+1", zone.get_extension(1), "#94a3b8", "#f8fafc"),
        ("TOP", zone.top, "#10b981", "#dcfce7"),
        ("VIX", zone.current, "#1e40af", "#dbeafe"),
        ("BTM", zone.bottom, "#ef4444", "#fee2e2"),
        ("-1", zone.get_extension(-1), "#94a3b8", "#f8fafc"),
        ("-2", zone.get_extension(-2), "#94a3b8", "#f8fafc"),
    ]
    
    rows_html = ""
    for label, value, color, bg in levels:
        weight = "700" if label in ["VIX", "TOP", "BTM"] else "500"
        border = f"2px solid {color}" if label == "VIX" else f"1px solid #e2e8f0"
        rows_html += f"""
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            margin: 3px 0;
            background: {bg};
            border: {border};
            border-radius: 8px;
        ">
            <span style="font-family: 'Inter', sans-serif; font-weight: {weight}; color: {color}; font-size: 0.75rem;">{label}</span>
            <span style="font-family: 'JetBrains Mono', monospace; font-weight: {weight}; color: {color}; font-size: 0.85rem;">{value:.2f}</span>
        </div>
        """
    
    st.markdown(f"""
    <div style="
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    ">
        <p style="
            font-family: 'Inter', sans-serif;
            font-size: 0.65rem;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin: 0 0 12px 0;
        ">VIX Ladder</p>
        {rows_html}
    </div>
    """, unsafe_allow_html=True)


def render_confluence_compact(support: List[ConfluentLevel], resistance: List[ConfluentLevel]):
    if not support and not resistance:
        st.markdown("""
        <div style="
            background: #f8fafc;
            border: 1px dashed #e2e8f0;
            border-radius: 16px;
            padding: 20px;
            text-align: center;
        ">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.85rem; color: #94a3b8; margin: 0;">
                No confluence detected
            </p>
        </div>
        """, unsafe_allow_html=True)
        return
    
    items_html = ""
    for level in resistance:
        stars = "⭐⭐⭐" if level.strength == "strong" else "⭐⭐"
        items_html += f"""
        <div style="
            background: linear-gradient(90deg, #fef2f2 0%, #fee2e2 100%);
            border-left: 3px solid #ef4444;
            padding: 10px 12px;
            border-radius: 0 8px 8px 0;
            margin: 6px 0;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 600; color: #dc2626;">RESISTANCE {stars}</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; color: #dc2626;">{level.price:,.0f}</span>
            </div>
            <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #991b1b; margin: 4px 0 0 0;">{', '.join(level.cones)}</p>
        </div>
        """
    
    for level in support:
        stars = "⭐⭐⭐" if level.strength == "strong" else "⭐⭐"
        items_html += f"""
        <div style="
            background: linear-gradient(90deg, #f0fdf4 0%, #dcfce7 100%);
            border-left: 3px solid #10b981;
            padding: 10px 12px;
            border-radius: 0 8px 8px 0;
            margin: 6px 0;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 600; color: #059669;">SUPPORT {stars}</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 700; color: #059669;">{level.price:,.0f}</span>
            </div>
            <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #065f46; margin: 4px 0 0 0;">{', '.join(level.cones)}</p>
        </div>
        """
    
    st.markdown(f"""
    <div style="
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    ">
        <p style="
            font-family: 'Inter', sans-serif;
            font-size: 0.65rem;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin: 0 0 12px 0;
        ">🎯 Confluence Zones</p>
        {items_html}
    </div>
    """, unsafe_allow_html=True)


def render_position_calc_compact(engine: SPXProphetEngine, setup: Optional[TradeSetup]):
    st.markdown("""
    <div style="
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    ">
        <p style="
            font-family: 'Inter', sans-serif;
            font-size: 0.65rem;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin: 0 0 12px 0;
        ">Position Calculator</p>
    """, unsafe_allow_html=True)
    
    risk_budget = st.number_input("Risk Budget", min_value=100, max_value=100000, value=1000, step=100, 
                                  label_visibility="collapsed", key="pos_calc_main")
    
    if setup:
        contracts = engine.calculate_max_contracts(risk_budget)
        risk_total = engine.calculate_profit(Config.STOP_LOSS_PTS, contracts)
        p1 = engine.calculate_profit(setup.reward_1_pts, contracts)
        p2 = engine.calculate_profit(setup.reward_2_pts, contracts)
        p3 = engine.calculate_profit(setup.reward_3_pts, contracts)
        
        st.markdown(f"""
        <div style="text-align: center; padding: 16px; background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 10px; margin: 12px 0;">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; font-weight: 700; color: #64748b; text-transform: uppercase; margin: 0 0 4px 0;">Contracts</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 2rem; font-weight: 800; color: #1e40af; margin: 0;">{contracts}</p>
        </div>
        
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            <div style="background: #fef2f2; padding: 10px; border-radius: 8px; text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; font-weight: 600; color: #94a3b8; margin: 0 0 2px 0;">RISK</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 700; color: #dc2626; margin: 0;">${risk_total:,.0f}</p>
            </div>
            <div style="background: #f0fdf4; padding: 10px; border-radius: 8px; text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; font-weight: 600; color: #94a3b8; margin: 0 0 2px 0;">@T1</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 700; color: #059669; margin: 0;">${p1:,.0f}</p>
            </div>
            <div style="background: #f0fdf4; padding: 10px; border-radius: 8px; text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; font-weight: 600; color: #94a3b8; margin: 0 0 2px 0;">@T2</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 700; color: #059669; margin: 0;">${p2:,.0f}</p>
            </div>
            <div style="background: #f0fdf4; padding: 10px; border-radius: 8px; text-align: center;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; font-weight: 600; color: #94a3b8; margin: 0 0 2px 0;">@T3</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 700; color: #059669; margin: 0;">${p3:,.0f}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar(engine: SPXProphetEngine):
    st.sidebar.markdown("""
    <div style="text-align: center; padding: 10px 0 20px 0;">
        <span style="font-size: 24px;">⚡</span>
        <p style="font-family: 'Inter', sans-serif; font-size: 0.8rem; font-weight: 600; color: #64748b; margin: 4px 0 0 0;">Configuration</p>
    </div>
    """, unsafe_allow_html=True)
    
    mode = st.sidebar.radio("Mode", ["Live", "Historical"], horizontal=True, label_visibility="collapsed")
    
    st.sidebar.markdown("---")
    
    ct_tz = pytz.timezone('America/Chicago')
    today = datetime.now(ct_tz).date()
    
    if mode == "Live":
        session_date = today
        st.sidebar.success(f"📅 {session_date.strftime('%B %d, %Y')}")
    else:
        session_date = st.sidebar.date_input("Session Date", today - timedelta(days=1), max_value=today)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### VIX Zone")
    st.sidebar.caption("Overnight boundaries (5pm-6am CT)")
    
    col1, col2 = st.sidebar.columns(2)
    vix_bottom = col1.number_input("Bottom", 5.0, 50.0, 15.87, 0.01, format="%.2f")
    vix_top = col2.number_input("Top", 5.0, 50.0, 16.17, 0.01, format="%.2f")
    vix_current = st.sidebar.number_input("Current VIX", 5.0, 50.0, 16.00, 0.01, format="%.2f")
    
    zone = VIXZone(vix_bottom, vix_top, vix_current)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### Prior Day Pivots")
    
    prior_data = fetch_prior_day_data(session_date)
    manual = st.sidebar.checkbox("Manual Input", value=(prior_data is None))
    
    prior_date = session_date - timedelta(days=1)
    while prior_date.weekday() >= 5:
        prior_date -= timedelta(days=1)
    
    if manual or prior_data is None:
        st.sidebar.caption(f"Pivot date: {prior_date}")
        col1, col2 = st.sidebar.columns(2)
        p_high = col1.number_input("High", 1000.0, 10000.0, 6050.0, 1.0)
        p_high_t = col2.time_input("Time", time(11, 30), key="p_high_t")
        col1, col2 = st.sidebar.columns(2)
        p_low = col1.number_input("Low", 1000.0, 10000.0, 6020.0, 1.0)
        p_low_t = col2.time_input("Time", time(14, 0), key="p_low_t")
        p_close = st.sidebar.number_input("Close", 1000.0, 10000.0, 6035.0, 1.0)
    else:
        p_high = prior_data['high']
        p_low = prior_data['low']
        p_close = prior_data['close']
        prior_date = prior_data['date'].date() if hasattr(prior_data['date'], 'date') else prior_data['date']
        p_high_t = time(11, 30)
        p_low_t = time(14, 0)
        st.sidebar.success(f"✓ {prior_date}")
        st.sidebar.caption(f"H: {p_high:,.2f} | L: {p_low:,.2f} | C: {p_close:,.2f}")
    
    pivots = [
        Pivot("Prior High", p_high, ct_tz.localize(datetime.combine(prior_date, p_high_t))),
        Pivot("Prior Low", p_low, ct_tz.localize(datetime.combine(prior_date, p_low_t))),
        Pivot("Prior Close", p_close, ct_tz.localize(datetime.combine(prior_date, time(16, 0))))
    ]
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("##### Secondary Pivots")
    
    if st.sidebar.checkbox("High²"):
        col1, col2 = st.sidebar.columns(2)
        h2_p = col1.number_input("Price", 1000.0, 10000.0, p_high - 10, 1.0, key="h2_price")
        h2_t = col2.time_input("Time", time(10, 0), key="h2_time")
        pivots.append(Pivot("High²", h2_p, ct_tz.localize(datetime.combine(prior_date, h2_t)), "secondary"))
    
    if st.sidebar.checkbox("Low²"):
        col1, col2 = st.sidebar.columns(2)
        l2_p = col1.number_input("Price", 1000.0, 10000.0, p_low + 10, 1.0, key="l2_price")
        l2_t = col2.time_input("Time", time(13, 0), key="l2_time")
        pivots.append(Pivot("Low²", l2_p, ct_tz.localize(datetime.combine(prior_date, l2_t)), "secondary"))
    
    st.sidebar.markdown("---")
    st.sidebar.caption("SPX Prophet v6.0 Legendary Edition")
    
    return mode, session_date, zone, pivots


# =============================================================================
# MAIN
# =============================================================================

def main():
    engine = SPXProphetEngine()
    ct_tz = pytz.timezone('America/Chicago')
    
    spx_live, _ = fetch_spx_data()
    spx_price = spx_live or 6000.0
    
    mode, session_date, zone, pivots = render_sidebar(engine)
    
    now = engine.get_current_time_ct()
    phase = engine.get_phase(now)
    
    bias, confidence, explanation = engine.determine_bias(zone)
    
    if mode == "Live":
        eval_time = ct_tz.localize(datetime.combine(now.date(), time(10, 0)))
        if now.time() > time(10, 0):
            eval_time = now
    else:
        eval_time = ct_tz.localize(datetime.combine(session_date, time(10, 0)))
    
    cones = [engine.calculate_cone(p, eval_time) for p in pivots]
    support_confluence, resistance_confluence = engine.find_confluence(cones)
    
    valid_cones = [c for c in cones if c.is_tradeable]
    best_cone = max(valid_cones, key=lambda x: x.width) if valid_cones else None
    best_name = best_cone.pivot.name if best_cone else ""
    
    setups = []
    for cone in cones:
        if cone.is_tradeable:
            setup = engine.generate_setup(cone, bias, support_confluence, resistance_confluence)
            if setup:
                setups.append(setup)
    
    setups.sort(key=lambda s: (s.cone.pivot.name != best_name, not s.is_confluent, -s.cone.width))
    best_setup = setups[0] if setups else None
    
    # =========================================================================
    # RENDER - LEGENDARY LAYOUT
    # =========================================================================
    
    # Header
    render_legendary_header(spx_price, phase, engine)
    
    # Chart - Hero Element
    st.markdown("""
    <div style="
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        padding: 20px;
        margin-bottom: 24px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    ">
    """, unsafe_allow_html=True)
    
    intraday = fetch_intraday_spx()
    fig = create_legendary_chart(intraday, cones, best_setup, spx_price)
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Key Metrics Row
    col1, col2, col3 = st.columns(3)
    
    with col1:
        render_bias_card_compact(bias, confidence, explanation)
    
    with col2:
        render_algo_triggers_compact(zone)
    
    with col3:
        render_expected_move_compact(zone)
    
    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
    
    # Best Setup - Prominent
    render_best_setup_hero(best_setup, spx_price, engine)
    
    # Bottom Row
    col1, col2, col3 = st.columns(3)
    
    with col1:
        render_vix_ladder_compact(zone)
    
    with col2:
        render_confluence_compact(support_confluence, resistance_confluence)
    
    with col3:
        render_position_calc_compact(engine, best_setup)
    
    # Cone Table
    if cones:
        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
        
        with st.expander("📊 All Cone Rails", expanded=False):
            data = []
            for c in cones:
                status = "⭐ BEST" if c.pivot.name == best_name else ("✓" if c.is_tradeable else "✗")
                data.append({
                    "Pivot": c.pivot.name,
                    "Ascending ↑": f"{c.ascending:,.2f}",
                    "Descending ↓": f"{c.descending:,.2f}",
                    "Width": f"{c.width:.1f}",
                    "Blocks": c.blocks,
                    "Status": status
                })
            st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
    
    # Footer
    st.markdown("""
    <div style="
        text-align: center;
        padding: 24px 0;
        margin-top: 24px;
        border-top: 1px solid #e2e8f0;
    ">
        <p style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: #94a3b8; margin: 0;">
            SPX Prophet v6.0 Legendary Edition • Institutional SPX Prediction System • Not Financial Advice
        </p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
