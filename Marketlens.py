"""
SPX PROPHET v9.0 - BEAUTY & BRAINS
Premium design + Full functionality
"""

import streamlit as st
import pandas as pd
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

# =============================================================================
# STYLES
# =============================================================================

def get_styles():
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    .stApp {
        background: linear-gradient(180deg, #f0f4f8 0%, #e2e8f0 100%);
    }
    
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
    }
    
    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stNumberInput label,
    section[data-testid="stSidebar"] .stDateInput label,
    section[data-testid="stSidebar"] .stTimeInput label,
    section[data-testid="stSidebar"] .stCheckbox label {
        color: #94a3b8 !important;
    }
    
    #MainMenu, footer, .stDeployButton { display: none; }
    
    .prophet-header {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 20px;
        padding: 28px 36px;
        margin-bottom: 24px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.15);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 20px;
    }
    
    .prophet-title {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 2.2rem;
        font-weight: 800;
        color: #ffffff;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    
    .prophet-subtitle {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.85rem;
        color: #94a3b8;
        margin: 4px 0 0 0;
    }
    
    .prophet-spx {
        text-align: right;
    }
    
    .prophet-spx-label {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.7rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin: 0;
    }
    
    .prophet-spx-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 2.5rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0;
        letter-spacing: -1px;
    }
    
    .prophet-phase {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.85rem;
        color: #22d3ee;
        margin: 4px 0 0 0;
    }
    
    .card {
        background: #ffffff;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        margin-bottom: 20px;
        border: 1px solid rgba(0,0,0,0.04);
    }
    
    .card-calls {
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        border: 2px solid #10b981;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(16, 185, 129, 0.15);
        margin-bottom: 20px;
    }
    
    .card-puts {
        background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
        border: 2px solid #ef4444;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(239, 68, 68, 0.15);
        margin-bottom: 20px;
    }
    
    .card-wait {
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
        border: 2px solid #f59e0b;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(245, 158, 11, 0.15);
        margin-bottom: 20px;
    }
    
    .card-blue {
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        border: 2px solid #3b82f6;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(59, 130, 246, 0.15);
        margin-bottom: 20px;
    }
    
    .card-dark {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        margin-bottom: 20px;
    }
    
    .label {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.7rem;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin: 0 0 8px 0;
    }
    
    .label-light {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.7rem;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        margin: 0 0 8px 0;
    }
    
    .big-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 2.8rem;
        font-weight: 800;
        margin: 0;
        line-height: 1;
        letter-spacing: -2px;
    }
    
    .medium-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
        line-height: 1;
        letter-spacing: -1px;
    }
    
    .small-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.1rem;
        font-weight: 600;
        margin: 0;
    }
    
    .green { color: #059669; }
    .red { color: #dc2626; }
    .blue { color: #2563eb; }
    .orange { color: #ea580c; }
    .white { color: #ffffff; }
    .gray { color: #64748b; }
    
    .section-title {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.3rem;
        font-weight: 700;
        color: #1e293b;
        margin: 32px 0 16px 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, #cbd5e1, transparent);
        margin: 24px 0;
    }
    
    .grid-3 {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
    }
    
    .grid-5 {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 16px;
    }
    
    .cone-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
    }
    
    .cone-table th {
        background: #1e293b;
        color: #ffffff;
        padding: 12px 16px;
        text-align: center;
        font-weight: 600;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .cone-table th:first-child {
        border-radius: 12px 0 0 0;
    }
    
    .cone-table th:last-child {
        border-radius: 0 12px 0 0;
    }
    
    .cone-table td {
        padding: 10px 14px;
        text-align: center;
        border-bottom: 1px solid #e2e8f0;
        background: #ffffff;
    }
    
    .cone-table tr:last-child td:first-child {
        border-radius: 0 0 0 12px;
    }
    
    .cone-table tr:last-child td:last-child {
        border-radius: 0 0 12px 0;
    }
    
    .cone-table .time-col {
        font-weight: 700;
        color: #1e293b;
        background: #f8fafc;
    }
    
    .cone-table .highlight-row td {
        background: linear-gradient(90deg, #fef3c7, #fde68a, #fef3c7) !important;
        font-weight: 700;
    }
    
    .cone-table .asc {
        color: #dc2626;
    }
    
    .cone-table .desc {
        color: #059669;
    }
    
    .pnl-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .pnl-table th {
        background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
        color: #ffffff;
        padding: 14px 16px;
        text-align: center;
        font-weight: 600;
        font-size: 0.8rem;
    }
    
    .pnl-table th:first-child {
        border-radius: 12px 0 0 0;
    }
    
    .pnl-table th:last-child {
        border-radius: 0 12px 0 0;
    }
    
    .pnl-table td {
        padding: 14px 16px;
        text-align: center;
        border-bottom: 1px solid #e2e8f0;
        font-size: 1rem;
        font-weight: 600;
    }
    
    .pnl-table tr:last-child td:first-child {
        border-radius: 0 0 0 12px;
    }
    
    .pnl-table tr:last-child td:last-child {
        border-radius: 0 0 12px 0;
    }
    
    .pnl-table .contracts {
        background: #f8fafc;
        font-weight: 700;
        color: #1e293b;
    }
    
    .pnl-table .loss {
        background: #fef2f2;
        color: #dc2626;
    }
    
    .pnl-table .profit {
        background: #f0fdf4;
        color: #059669;
    }
    
    .trigger-box {
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    
    .trigger-buy {
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        border-left: 5px solid #10b981;
    }
    
    .trigger-sell {
        background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%);
        border-left: 5px solid #ef4444;
    }
    
    .confluence-badge {
        display: inline-block;
        background: linear-gradient(135deg, #a78bfa 0%, #8b5cf6 100%);
        color: white;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-left: 12px;
    }
    
    .best-badge {
        display: inline-block;
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
        color: #000;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 700;
        margin-right: 12px;
    }
    
    .ladder-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 16px;
        margin: 4px 0;
        border-radius: 8px;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .ladder-current {
        background: linear-gradient(90deg, #dbeafe 0%, #bfdbfe 100%);
        border: 2px solid #3b82f6;
        font-weight: 700;
    }
    
    .ladder-top {
        background: #dcfce7;
        border: 1px solid #86efac;
    }
    
    .ladder-bottom {
        background: #fee2e2;
        border: 1px solid #fecaca;
    }
    
    .ladder-ext {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
    }
    </style>
    """

st.markdown(get_styles(), unsafe_allow_html=True)


# =============================================================================
# CONSTANTS & CLASSES
# =============================================================================

class Config:
    SLOPE_PER_30MIN = 0.45
    MIN_CONE_WIDTH = 18.0
    STOP_LOSS_PTS = 6.0
    DELTA = 0.33
    CONTRACT_MULTIPLIER = 100
    EM_BASE = 35
    EM_ZONE_BASELINE = 0.10
    EM_MULTIPLIER = 100
    EM_CAP_LOW = 65
    EM_CAP_HIGH = 70
    CONFLUENCE_THRESHOLD = 6.0


class Bias(Enum):
    CALLS = ("CALLS", "green", "↑", "card-calls")
    PUTS = ("PUTS", "red", "↓", "card-puts")
    WAIT = ("WAIT", "orange", "◆", "card-wait")
    
    def __init__(self, label, color, arrow, card):
        self.label = label
        self.color = color
        self.arrow = arrow
        self.card = card


class Confidence(Enum):
    HIGH = ("HIGH", "●●●")
    MEDIUM = ("MEDIUM", "●●○")
    LOW = ("LOW", "●○○")
    NONE = ("NONE", "○○○")


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
            return "+1"
        elif self.current < self.bottom:
            ext = (self.bottom - self.current) / self.size if self.size > 0 else 0
            if ext >= 2: return "-3"
            elif ext >= 1: return "-2"
            return "-1"
        return "BASE"
    
    @property
    def buy_trigger(self) -> float:
        if self.current <= self.top:
            return self.top
        ext = int((self.current - self.top) / self.size) + 1 if self.size > 0 else 1
        return self.top + (ext * self.size)
    
    @property
    def sell_trigger(self) -> float:
        if self.current >= self.bottom:
            return self.bottom
        ext = int((self.bottom - self.current) / self.size) + 1 if self.size > 0 else 1
        return self.bottom - (ext * self.size)
    
    @property
    def dist_to_buy(self) -> float:
        return round(self.buy_trigger - self.current, 2)
    
    @property
    def dist_to_sell(self) -> float:
        return round(self.current - self.sell_trigger, 2)
    
    def extension(self, level: int) -> float:
        if level > 0:
            return round(self.top + (level * self.size), 2)
        return round(self.bottom + (level * self.size), 2)
    
    def expected_move(self) -> Tuple[float, float]:
        if self.size <= 0:
            return (0, 0)
        em = Config.EM_BASE + ((self.size - Config.EM_ZONE_BASELINE) * Config.EM_MULTIPLIER)
        em = min(em, Config.EM_CAP_LOW)
        return (round(max(em, 0), 0), round(min(em + 5, Config.EM_CAP_HIGH), 0))


@dataclass
class Pivot:
    name: str
    price: float
    timestamp: datetime


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
class TradeSetup:
    direction: Bias
    cone: ConeRails
    entry: float
    stop: float
    t1: float
    t2: float
    t3: float
    strike: int
    is_confluent: bool = False


# =============================================================================
# ENGINE
# =============================================================================

class Engine:
    def __init__(self):
        self.tz = pytz.timezone('America/Chicago')
    
    def now(self) -> datetime:
        return datetime.now(self.tz)
    
    def phase(self) -> str:
        t = self.now().time()
        if self.now().weekday() >= 5:
            return "CLOSED"
        if time(17, 0) <= t or t < time(6, 0):
            return "ZONE BUILDING"
        if time(6, 0) <= t < time(9, 30):
            return "PRE-RTH"
        if time(9, 30) <= t < time(16, 0):
            return "RTH"
        return "POST"
    
    def bias(self, zone: VIXZone) -> Tuple[Bias, Confidence, str]:
        if abs(zone.dist_to_buy) <= 0.05:
            return Bias.CALLS, Confidence.HIGH, "VIX at buy trigger → SPX UP"
        if abs(zone.dist_to_sell) <= 0.05:
            return Bias.PUTS, Confidence.HIGH, "VIX at sell trigger → SPX DOWN"
        if "+" in zone.current_zone:
            c = Confidence.MEDIUM if zone.dist_to_buy > 0.10 else Confidence.LOW
            return Bias.PUTS, c, f"VIX in {zone.current_zone} → Put bias"
        if "-" in zone.current_zone:
            c = Confidence.MEDIUM if zone.dist_to_sell > 0.10 else Confidence.LOW
            return Bias.CALLS, c, f"VIX in {zone.current_zone} → Call bias"
        return Bias.WAIT, Confidence.NONE, "VIX in BASE → Trend day possible"
    
    def blocks(self, pivot_time: datetime, eval_time: datetime) -> int:
        if pivot_time.tzinfo is None:
            pivot_time = self.tz.localize(pivot_time)
        if eval_time.tzinfo is None:
            eval_time = self.tz.localize(eval_time)
        mins = (eval_time - pivot_time).total_seconds() / 60
        return max(int(mins / 30), 1)
    
    def cone(self, pivot: Pivot, eval_time: datetime) -> ConeRails:
        b = self.blocks(pivot.timestamp, eval_time)
        exp = b * Config.SLOPE_PER_30MIN
        asc = round(pivot.price + exp, 2)
        desc = round(pivot.price - exp, 2)
        return ConeRails(pivot, asc, desc, round(asc - desc, 2), b)
    
    def cone_at_time(self, pivot: Pivot, target_time: time, base_date: date) -> ConeRails:
        eval_dt = self.tz.localize(datetime.combine(base_date, target_time))
        return self.cone(pivot, eval_dt)
    
    def setup(self, cone: ConeRails, direction: Bias) -> Optional[TradeSetup]:
        if not cone.is_tradeable or direction == Bias.WAIT:
            return None
        if direction == Bias.CALLS:
            entry = cone.descending
            stop = entry - Config.STOP_LOSS_PTS
            move = cone.ascending - entry
            strike = int(round((entry - 17.5) / 5) * 5)
        else:
            entry = cone.ascending
            stop = entry + Config.STOP_LOSS_PTS
            move = entry - cone.descending
            strike = int(round((entry + 17.5) / 5) * 5)
        
        t1 = entry + move * 0.125 if direction == Bias.CALLS else entry - move * 0.125
        t2 = entry + move * 0.25 if direction == Bias.CALLS else entry - move * 0.25
        t3 = entry + move * 0.50 if direction == Bias.CALLS else entry - move * 0.50
        
        return TradeSetup(direction, cone, round(entry, 2), round(stop, 2),
                         round(t1, 2), round(t2, 2), round(t3, 2), strike)
    
    def profit(self, pts: float, contracts: int) -> float:
        return round(pts * Config.DELTA * Config.CONTRACT_MULTIPLIER * contracts, 2)


# =============================================================================
# DATA
# =============================================================================

@st.cache_data(ttl=60)
def get_spx():
    try:
        h = yf.Ticker("^GSPC").history(period="5d", interval="1d")
        return float(h['Close'].iloc[-1]) if not h.empty else 6000.0
    except:
        return 6000.0


@st.cache_data(ttl=300)
def get_prior(session_date: date):
    try:
        h = yf.Ticker("^GSPC").history(start=session_date - timedelta(days=10), end=session_date + timedelta(days=1))
        if h.empty or len(h) < 2:
            return None
        s = session_date.strftime('%Y-%m-%d')
        for i, idx in enumerate(h.index):
            if idx.strftime('%Y-%m-%d') == s and i > 0:
                p = h.iloc[i-1]
                return {'high': float(p['High']), 'low': float(p['Low']), 'close': float(p['Close'])}
        p = h.iloc[-2]
        return {'high': float(p['High']), 'low': float(p['Low']), 'close': float(p['Close'])}
    except:
        return None


# =============================================================================
# SIDEBAR
# =============================================================================

def sidebar(engine: Engine):
    st.sidebar.markdown("## ⚡ SPX Prophet")
    st.sidebar.caption("v9.0 Beauty & Brains")
    st.sidebar.divider()
    
    mode = st.sidebar.radio("Mode", ["Live", "Historical"], horizontal=True)
    
    today = engine.now().date()
    session = today if mode == "Live" else st.sidebar.date_input("Date", today - timedelta(days=1), max_value=today)
    
    st.sidebar.divider()
    st.sidebar.markdown("### VIX Zone")
    
    c1, c2 = st.sidebar.columns(2)
    vb = c1.number_input("Bottom", 5.0, 50.0, 15.87, 0.01, format="%.2f")
    vt = c2.number_input("Top", 5.0, 50.0, 16.17, 0.01, format="%.2f")
    vc = st.sidebar.number_input("Current", 5.0, 50.0, 16.00, 0.01, format="%.2f")
    
    zone = VIXZone(vb, vt, vc)
    
    st.sidebar.divider()
    st.sidebar.markdown("### Pivots")
    
    prior = get_prior(session)
    pdate = session - timedelta(days=1)
    while pdate.weekday() >= 5:
        pdate -= timedelta(days=1)
    
    if prior:
        ph, pl, pc = prior['high'], prior['low'], prior['close']
        st.sidebar.success(f"✓ Loaded")
    else:
        ph = st.sidebar.number_input("High", value=6050.0)
        pl = st.sidebar.number_input("Low", value=6020.0)
        pc = st.sidebar.number_input("Close", value=6035.0)
    
    c1, c2 = st.sidebar.columns(2)
    pht = c1.time_input("H Time", time(11, 30))
    plt = c2.time_input("L Time", time(14, 0))
    
    pivots = [
        Pivot("Prior High", ph, engine.tz.localize(datetime.combine(pdate, pht))),
        Pivot("Prior Low", pl, engine.tz.localize(datetime.combine(pdate, plt))),
        Pivot("Prior Close", pc, engine.tz.localize(datetime.combine(pdate, time(16, 0))))
    ]
    
    return session, zone, pivots


# =============================================================================
# CONE TIME TABLE
# =============================================================================

def cone_time_table(engine: Engine, pivots: List[Pivot], session: date, direction: Bias):
    """Generate cone rails for each 30-min slot from 8:30am to 3pm CT"""
    
    times = []
    t = time(8, 30)
    while t <= time(15, 0):
        times.append(t)
        dt = datetime.combine(date.today(), t) + timedelta(minutes=30)
        t = dt.time()
        if t > time(15, 0):
            break
    
    # Build table header
    header = "<tr><th>Time (CT)</th>"
    for p in pivots:
        if direction == Bias.CALLS:
            header += f"<th>{p.name} ↓</th>"
        else:
            header += f"<th>{p.name} ↑</th>"
    header += "</tr>"
    
    # Build rows
    rows = ""
    for t in times:
        is_10am = t.hour == 10 and t.minute == 0
        row_class = "highlight-row" if is_10am else ""
        time_label = "🏛️ 10:00 AM" if is_10am else t.strftime('%I:%M %p').lstrip('0')
        
        rows += f'<tr class="{row_class}">'
        rows += f'<td class="time-col">{time_label}</td>'
        
        for p in pivots:
            cone = engine.cone_at_time(p, t, session)
            if direction == Bias.CALLS:
                val = cone.descending
                css = "desc"
            else:
                val = cone.ascending
                css = "asc"
            rows += f'<td class="{css}">{val:,.2f}</td>'
        
        rows += "</tr>"
    
    return f"""
    <div style="overflow-x: auto;">
        <table class="cone-table">
            {header}
            {rows}
        </table>
    </div>
    <p style="margin-top: 12px; font-size: 0.85rem; color: #64748b;">
        🏛️ <strong>10:00 AM</strong> = Institutional entry time
    </p>
    """


# =============================================================================
# MAIN
# =============================================================================

def main():
    engine = Engine()
    spx = get_spx()
    session, zone, pivots = sidebar(engine)
    
    now = engine.now()
    phase = engine.phase()
    bias, conf, expl = engine.bias(zone)
    
    eval_time = engine.tz.localize(datetime.combine(session, time(10, 0)))
    cones = [engine.cone(p, eval_time) for p in pivots]
    
    valid = [c for c in cones if c.is_tradeable]
    best = max(valid, key=lambda x: x.width) if valid else None
    
    setups = [engine.setup(c, bias) for c in cones if c.is_tradeable]
    setups = [s for s in setups if s]
    setups.sort(key=lambda s: -s.cone.width)
    best_setup = setups[0] if setups else None
    
    em_low, em_high = zone.expected_move()
    
    # =========================================================================
    # HEADER
    # =========================================================================
    
    st.markdown(f"""
    <div class="prophet-header">
        <div>
            <h1 class="prophet-title">⚡ SPX Prophet</h1>
            <p class="prophet-subtitle">Institutional SPX Prediction System</p>
        </div>
        <div class="prophet-spx">
            <p class="prophet-spx-label">S&P 500 Index</p>
            <p class="prophet-spx-value">{spx:,.2f}</p>
            <p class="prophet-phase">{phase} • {now.strftime('%I:%M %p')} CT</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # =========================================================================
    # ROW 1: DIRECTION + EXPECTED MOVE + VIX
    # =========================================================================
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="{bias.card}">
            <p class="label">DIRECTION</p>
            <p class="big-value {bias.color}">{bias.arrow} {bias.label}</p>
            <p style="margin-top: 12px; font-size: 1.1rem;">{conf.value[1]} {conf.value[0]}</p>
            <p style="margin-top: 8px; color: #64748b;">{expl}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="card-blue">
            <p class="label">EXPECTED MOVE</p>
            <p class="big-value blue">{em_low:.0f} - {em_high:.0f}</p>
            <p style="margin-top: 12px; font-size: 1rem;">points from entry</p>
            <p style="margin-top: 8px; color: #64748b;">Zone Size: {zone.size:.2f}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="card">
            <p class="label">CURRENT VIX</p>
            <p class="big-value">{zone.current:.2f}</p>
            <p style="margin-top: 12px; font-size: 1rem; color: #3b82f6; font-weight: 600;">Zone: {zone.current_zone}</p>
        </div>
        """, unsafe_allow_html=True)
    
    # =========================================================================
    # ROW 2: ALGO TRIGGERS
    # =========================================================================
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"""
        <div class="trigger-box trigger-buy">
            <p class="label green">↑ BUY ALGO TRIGGER</p>
            <p class="medium-value green">{zone.buy_trigger:.2f}</p>
            <p style="margin-top: 8px; color: #065f46;">VIX tops here → SPX rallies</p>
            <p style="margin-top: 8px; font-size: 1.2rem; font-weight: 700; color: #059669;">{zone.dist_to_buy:+.2f} away</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="trigger-box trigger-sell">
            <p class="label red">↓ SELL ALGO TRIGGER</p>
            <p class="medium-value red">{zone.sell_trigger:.2f}</p>
            <p style="margin-top: 8px; color: #991b1b;">VIX bottoms here → SPX sells</p>
            <p style="margin-top: 8px; font-size: 1.2rem; font-weight: 700; color: #dc2626;">{zone.dist_to_sell:.2f} away</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # =========================================================================
    # BEST SETUP
    # =========================================================================
    
    if best_setup:
        conf_badge = '<span class="confluence-badge">🎯 CONFLUENCE</span>' if best_setup.is_confluent else ''
        
        st.markdown(f"""
        <p class="section-title">
            <span class="best-badge">⭐ BEST SETUP</span>
            {best_setup.direction.arrow} {best_setup.direction.label} — {best_setup.cone.pivot.name}
            {conf_badge}
        </p>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="grid-5">
            <div class="{best_setup.direction.card}" style="text-align: center;">
                <p class="label">ENTRY</p>
                <p class="medium-value">{best_setup.entry:,.2f}</p>
            </div>
            <div class="card-puts" style="text-align: center;">
                <p class="label">STOP (-6)</p>
                <p class="medium-value red">{best_setup.stop:,.2f}</p>
            </div>
            <div class="card" style="text-align: center;">
                <p class="label">T1 (12.5%)</p>
                <p class="medium-value green">{best_setup.t1:,.2f}</p>
            </div>
            <div class="card" style="text-align: center;">
                <p class="label">T2 (25%)</p>
                <p class="medium-value green">{best_setup.t2:,.2f}</p>
            </div>
            <div class="card" style="text-align: center;">
                <p class="label">T3 (50%)</p>
                <p class="medium-value green">{best_setup.t3:,.2f}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Setup metrics
        dist = spx - best_setup.entry
        rr = engine.profit(abs(best_setup.t2 - best_setup.entry), 1) / engine.profit(6, 1)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Strike", best_setup.strike)
        col2.metric("Distance", f"{dist:+.1f} pts")
        col3.metric("Width", f"{best_setup.cone.width:.1f} pts")
        col4.metric("R:R @ T2", f"{rr:.1f}:1")
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # =================================================================
        # POSITION SIZING & P/L
        # =================================================================
        
        st.markdown('<p class="section-title">💰 Position Sizing & Profit/Loss</p>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            contracts = st.selectbox("Contracts", [1, 2, 3, 5, 10, 15, 20, 25, 50], index=4)
        
        risk = engine.profit(6, contracts)
        p1 = engine.profit(abs(best_setup.t1 - best_setup.entry), contracts)
        p2 = engine.profit(abs(best_setup.t2 - best_setup.entry), contracts)
        p3 = engine.profit(abs(best_setup.t3 - best_setup.entry), contracts)
        
        with col2:
            st.markdown(f"""
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
                <div class="card-puts" style="text-align: center;">
                    <p class="label">MAX LOSS</p>
                    <p class="big-value red">-${risk:,.0f}</p>
                </div>
                <div class="card-calls" style="text-align: center;">
                    <p class="label">@ T1</p>
                    <p class="big-value green">+${p1:,.0f}</p>
                </div>
                <div class="card-calls" style="text-align: center;">
                    <p class="label">@ T2</p>
                    <p class="big-value green">+${p2:,.0f}</p>
                </div>
                <div class="card-calls" style="text-align: center;">
                    <p class="label">@ T3</p>
                    <p class="big-value green">+${p3:,.0f}</p>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # P&L Table
        st.markdown('<p class="section-title">📊 Quick P&L Reference</p>', unsafe_allow_html=True)
        
        pnl_rows = ""
        for c in [1, 5, 10, 20, 50]:
            r = engine.profit(6, c)
            t1 = engine.profit(abs(best_setup.t1 - best_setup.entry), c)
            t2 = engine.profit(abs(best_setup.t2 - best_setup.entry), c)
            t3 = engine.profit(abs(best_setup.t3 - best_setup.entry), c)
            pnl_rows += f"""
            <tr>
                <td class="contracts">{c}</td>
                <td class="loss">-${r:,.0f}</td>
                <td class="profit">+${t1:,.0f}</td>
                <td class="profit">+${t2:,.0f}</td>
                <td class="profit">+${t3:,.0f}</td>
            </tr>
            """
        
        st.markdown(f"""
        <table class="pnl-table">
            <tr>
                <th>Contracts</th>
                <th>Max Loss</th>
                <th>@ T1 (12.5%)</th>
                <th>@ T2 (25%)</th>
                <th>@ T3 (50%)</th>
            </tr>
            {pnl_rows}
        </table>
        """, unsafe_allow_html=True)
    
    else:
        st.warning("⏳ No valid setup. VIX in BASE zone or cones too narrow.")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # =========================================================================
    # CONE RAILS TIME TABLE
    # =========================================================================
    
    st.markdown(f'<p class="section-title">📐 Cone Rails by Time ({bias.label} Entries)</p>', unsafe_allow_html=True)
    
    table_html = cone_time_table(engine, pivots, session, bias)
    st.markdown(table_html, unsafe_allow_html=True)
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # =========================================================================
    # VIX LADDER + PIVOTS
    # =========================================================================
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<p class="section-title">📶 VIX Ladder</p>', unsafe_allow_html=True)
        
        ladder = ""
        for lbl, val, cls in [
            ("+2", zone.extension(2), "ladder-ext"),
            ("+1", zone.extension(1), "ladder-ext"),
            ("TOP", zone.top, "ladder-top"),
            ("VIX →", zone.current, "ladder-current"),
            ("BTM", zone.bottom, "ladder-bottom"),
            ("-1", zone.extension(-1), "ladder-ext"),
            ("-2", zone.extension(-2), "ladder-ext"),
        ]:
            ladder += f'<div class="ladder-row {cls}"><span>{lbl}</span><span>{val:.2f}</span></div>'
        
        st.markdown(f'<div class="card">{ladder}</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<p class="section-title">📍 Pivots & Cones</p>', unsafe_allow_html=True)
        
        rows = ""
        for c in cones:
            is_best = best and c.pivot.name == best.pivot.name
            badge = "⭐" if is_best else ("✓" if c.is_tradeable else "✗")
            rows += f"""
            <tr>
                <td><strong>{c.pivot.name}</strong></td>
                <td>{c.pivot.price:,.2f}</td>
                <td class="asc">{c.ascending:,.2f}</td>
                <td class="desc">{c.descending:,.2f}</td>
                <td>{c.width:.1f}</td>
                <td>{badge}</td>
            </tr>
            """
        
        st.markdown(f"""
        <table class="cone-table">
            <tr>
                <th>Pivot</th>
                <th>Price</th>
                <th>↑ Asc</th>
                <th>↓ Desc</th>
                <th>Width</th>
                <th></th>
            </tr>
            {rows}
        </table>
        """, unsafe_allow_html=True)
    
    # Footer
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.caption("SPX Prophet v9.0 | Not Financial Advice")


if __name__ == "__main__":
    main()
