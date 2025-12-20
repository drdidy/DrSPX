"""
SPX PROPHET v4.0 - Institutional Grade 0DTE SPX Options Decision Support System

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time, date
import yfinance as yf
import pytz
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum
import json

# =============================================================================
# PAGE CONFIG - Must be first
# =============================================================================

st.set_page_config(
    page_title="SPX Prophet | Institutional 0DTE System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# CONSTANTS & CONFIGURATION
# =============================================================================

class Config:
    """System configuration constants"""
    # Trading parameters
    SLOPE_PER_30MIN = 0.45
    MIN_CONE_WIDTH = 18.0
    STOP_LOSS_PTS = 6.0
    STRIKE_OTM_DISTANCE = 17.5
    DELTA = 0.33
    CONTRACT_MULTIPLIER = 100
    
    # Realistic 0DTE targets
    TARGET_1_PCT = 0.125  # 12.5%
    TARGET_2_PCT = 0.25   # 25%
    TARGET_3_PCT = 0.50   # 50%
    
    # VIX zone thresholds
    VIX_ZONE_LOW = 0.20
    VIX_ZONE_NORMAL = 0.30
    VIX_ZONE_HIGH = 0.45
    
    # Bias thresholds
    ZONE_TOP_PCT = 75
    ZONE_BOTTOM_PCT = 25
    
    # Validation limits
    MAX_CONE_WIDTH = 200
    MIN_VIX = 5.0
    MAX_VIX = 100.0
    MIN_SPX = 1000.0
    MAX_SPX = 10000.0


class Phase(Enum):
    """Trading day phases with metadata"""
    OVERNIGHT = ("Overnight Prep", "#3b82f6", "🌙", "Zone Building")
    ZONE_LOCK = ("Zone Lock", "#06b6d4", "🔒", "Analysis Mode")
    DANGER_ZONE = ("Danger Zone", "#f59e0b", "⚠️", "Caution Required")
    RTH = ("RTH Active", "#10b981", "🟢", "Execution Mode")
    POST_SESSION = ("Post-Session", "#8b5cf6", "📊", "Review Mode")
    MARKET_CLOSED = ("Market Closed", "#6b7280", "⭘", "Offline")
    
    def __init__(self, label: str, color: str, icon: str, mode: str):
        self.label = label
        self.color = color
        self.icon = icon
        self.mode = mode


class Bias(Enum):
    CALLS = ("CALLS", "#10b981", "📈")
    PUTS = ("PUTS", "#ef4444", "📉")
    WAIT = ("WAIT", "#f59e0b", "⏸️")
    
    def __init__(self, label: str, color: str, icon: str):
        self.label = label
        self.color = color
        self.icon = icon


class Confidence(Enum):
    STRONG = ("STRONG", "●●●●", "#10b981")
    MODERATE = ("MODERATE", "●●●○", "#f59e0b")
    WEAK = ("WEAK", "●●○○", "#ef4444")
    NO_TRADE = ("NO TRADE", "○○○○", "#6b7280")
    
    def __init__(self, label: str, dots: str, color: str):
        self.label = label
        self.dots = dots
        self.color = color


class LevelStatus(Enum):
    """Status for level hit tracking"""
    NOT_HIT = ("Not Hit", "○", "#6b7280")
    HIT = ("HIT", "✓", "#10b981")
    STOPPED = ("STOPPED", "✗", "#ef4444")
    PENDING = ("Pending", "◔", "#f59e0b")
    
    def __init__(self, label: str, icon: str, color: str):
        self.label = label
        self.icon = icon
        self.color = color


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class VIXZone:
    """VIX Zone with validation"""
    bottom: float
    top: float
    current: float
    locked: bool = False
    lock_time: Optional[datetime] = None
    
    def __post_init__(self):
        # Validation
        if self.bottom >= self.top:
            self.top = self.bottom + 0.01
    
    @property
    def size(self) -> float:
        return round(self.top - self.bottom, 4)
    
    @property
    def position_pct(self) -> float:
        if self.size == 0:
            return 50.0
        return round(((self.current - self.bottom) / self.size) * 100, 1)
    
    @property
    def potential(self) -> str:
        if self.size < Config.VIX_ZONE_LOW:
            return "LOW"
        elif self.size < Config.VIX_ZONE_HIGH:
            return "NORMAL"
        return "HIGH"
    
    @property
    def potential_emoji(self) -> str:
        return {"LOW": "⚠️", "NORMAL": "✓", "HIGH": "🔥"}.get(self.potential, "")
    
    def get_extension(self, level: int) -> float:
        if level > 0:
            return round(self.top + (level * self.size), 2)
        return round(self.bottom + (level * self.size), 2)
    
    def is_valid(self) -> Tuple[bool, str]:
        if self.size < 0.01:
            return False, "Zone size too small"
        if self.size > 2.0:
            return False, "Zone size unusually large"
        if not (Config.MIN_VIX <= self.current <= Config.MAX_VIX):
            return False, f"VIX out of range ({Config.MIN_VIX}-{Config.MAX_VIX})"
        return True, "Valid"


@dataclass
class Pivot:
    """Price pivot with metadata"""
    name: str
    price: float
    timestamp: datetime
    pivot_type: str = "primary"  # primary, secondary
    enabled: bool = True
    
    def is_valid(self) -> Tuple[bool, str]:
        if not (Config.MIN_SPX <= self.price <= Config.MAX_SPX):
            return False, f"Price out of range"
        return True, "Valid"


@dataclass
class ConeRails:
    """Cone projection with calculations"""
    pivot: Pivot
    ascending: float
    descending: float
    width: float
    blocks: int
    eval_time: datetime
    
    @property
    def is_tradeable(self) -> bool:
        return self.width >= Config.MIN_CONE_WIDTH
    
    @property
    def status(self) -> str:
        if not self.is_tradeable:
            return "Too Narrow"
        return "Valid"


@dataclass
class TradeSetup:
    """Complete trade setup with all levels"""
    direction: Bias
    cone: ConeRails
    entry: float
    stop: float
    target_1: float  # 12.5%
    target_2: float  # 25%
    target_3: float  # 50%
    strike: int
    
    # Calculated fields
    risk_pts: float = Config.STOP_LOSS_PTS
    cone_width: float = 0.0
    
    def __post_init__(self):
        self.cone_width = self.cone.width
    
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
    """Tracks whether a price level was hit"""
    level_name: str
    level_price: float
    status: LevelStatus
    hit_time: Optional[datetime] = None
    hit_price: Optional[float] = None


@dataclass
class SessionAnalysis:
    """Complete session analysis for historical review"""
    session_date: date
    spx_open: float
    spx_high: float
    spx_low: float
    spx_close: float
    spx_range: float
    vix_zone: Optional[VIXZone]
    bias: Bias
    setups: List[TradeSetup]
    level_hits: List[LevelHit]
    theoretical_pnl: float = 0.0


@dataclass
class AuditEntry:
    """Audit trail entry"""
    timestamp: datetime
    event: str
    details: str
    values: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# CALCULATION ENGINE
# =============================================================================

class SPXProphetEngine:
    """Core calculation engine with full functionality"""
    
    def __init__(self):
        self.ct_tz = pytz.timezone('America/Chicago')
        self.audit_log: List[AuditEntry] = []
    
    def log_audit(self, event: str, details: str, values: Dict = None):
        """Add entry to audit log"""
        self.audit_log.append(AuditEntry(
            timestamp=datetime.now(self.ct_tz),
            event=event,
            details=details,
            values=values or {}
        ))
    
    def get_current_time_ct(self) -> datetime:
        """Get current time in Central Time"""
        return datetime.now(self.ct_tz)
    
    def get_phase(self, dt: datetime = None) -> Phase:
        """Determine trading phase for given datetime"""
        if dt is None:
            dt = self.get_current_time_ct()
        else:
            dt = dt.astimezone(self.ct_tz) if dt.tzinfo else self.ct_tz.localize(dt)
        
        t = dt.time()
        weekday = dt.weekday()
        
        # Weekend
        if weekday >= 5:
            return Phase.MARKET_CLOSED
        
        # Phase windows (CT)
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
    
    def get_time_to_next_phase(self, dt: datetime = None) -> Tuple[Phase, timedelta]:
        """Calculate time remaining until next phase"""
        if dt is None:
            dt = self.get_current_time_ct()
        
        current_phase = self.get_phase(dt)
        t = dt.time()
        today = dt.date()
        
        phase_transitions = [
            (time(2, 0), Phase.ZONE_LOCK),
            (time(6, 30), Phase.DANGER_ZONE),
            (time(9, 30), Phase.RTH),
            (time(16, 0), Phase.POST_SESSION),
            (time(17, 0), Phase.OVERNIGHT),
        ]
        
        for transition_time, next_phase in phase_transitions:
            if t < transition_time:
                next_dt = self.ct_tz.localize(datetime.combine(today, transition_time))
                return next_phase, next_dt - dt
        
        # Next day overnight
        tomorrow = today + timedelta(days=1)
        next_dt = self.ct_tz.localize(datetime.combine(tomorrow, time(17, 0)))
        return Phase.OVERNIGHT, next_dt - dt
    
    def determine_bias(self, zone: VIXZone, phase: Phase) -> Tuple[Bias, Confidence, str]:
        """Determine trading bias with confidence scoring"""
        pos = zone.position_pct
        
        # Phase-aware confidence adjustment
        phase_penalty = 0
        if phase == Phase.DANGER_ZONE:
            phase_penalty = 1  # Reduce confidence by one level
        
        if pos >= Config.ZONE_TOP_PCT:
            bias = Bias.CALLS
            base_explanation = f"VIX at zone TOP ({pos:.0f}%)"
            
            if pos >= 90:
                conf_level = max(0, 3 - phase_penalty)
            elif pos >= 80:
                conf_level = max(0, 2 - phase_penalty)
            else:
                conf_level = max(0, 1 - phase_penalty)
            
            confidence = [Confidence.NO_TRADE, Confidence.WEAK, Confidence.MODERATE, Confidence.STRONG][conf_level]
            explanation = f"{base_explanation} → Expect VIX to fall → SPX UP"
            
        elif pos <= Config.ZONE_BOTTOM_PCT:
            bias = Bias.PUTS
            base_explanation = f"VIX at zone BOTTOM ({pos:.0f}%)"
            
            if pos <= 10:
                conf_level = max(0, 3 - phase_penalty)
            elif pos <= 20:
                conf_level = max(0, 2 - phase_penalty)
            else:
                conf_level = max(0, 1 - phase_penalty)
            
            confidence = [Confidence.NO_TRADE, Confidence.WEAK, Confidence.MODERATE, Confidence.STRONG][conf_level]
            explanation = f"{base_explanation} → Expect VIX to rise → SPX DOWN"
            
        else:
            bias = Bias.WAIT
            confidence = Confidence.NO_TRADE
            explanation = f"VIX mid-zone ({pos:.0f}%) → No directional edge → WAIT"
        
        if phase == Phase.DANGER_ZONE and bias != Bias.WAIT:
            explanation += " ⚠️ DANGER ZONE - Reversals possible"
        
        self.log_audit("BIAS_DETERMINED", explanation, {
            "bias": bias.label,
            "confidence": confidence.label,
            "vix_position": pos,
            "phase": phase.label
        })
        
        return bias, confidence, explanation
    
    def calculate_blocks(self, pivot_time: datetime, eval_time: datetime) -> int:
        """Calculate 30-min blocks between times"""
        if pivot_time.tzinfo is None:
            pivot_time = self.ct_tz.localize(pivot_time)
        if eval_time.tzinfo is None:
            eval_time = self.ct_tz.localize(eval_time)
        
        diff = eval_time - pivot_time
        total_minutes = diff.total_seconds() / 60
        return max(int(total_minutes / 30), 1)
    
    def calculate_cone(self, pivot: Pivot, eval_time: datetime) -> ConeRails:
        """Calculate cone rails from pivot"""
        blocks = self.calculate_blocks(pivot.timestamp, eval_time)
        expansion = blocks * Config.SLOPE_PER_30MIN
        
        ascending = round(pivot.price + expansion, 2)
        descending = round(pivot.price - expansion, 2)
        width = round(ascending - descending, 2)
        
        return ConeRails(
            pivot=pivot,
            ascending=ascending,
            descending=descending,
            width=width,
            blocks=blocks,
            eval_time=eval_time
        )
    
    def generate_setup(self, cone: ConeRails, direction: Bias) -> Optional[TradeSetup]:
        """Generate complete trade setup"""
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
            direction=direction,
            cone=cone,
            entry=round(entry, 2),
            stop=round(stop, 2),
            target_1=round(t1, 2),
            target_2=round(t2, 2),
            target_3=round(t3, 2),
            strike=strike
        )
    
    def calculate_profit(self, points: float, contracts: int = 1) -> float:
        """Calculate dollar profit from point movement"""
        return round(points * Config.DELTA * Config.CONTRACT_MULTIPLIER * contracts, 2)
    
    def calculate_max_contracts(self, risk_budget: float) -> int:
        """Calculate max contracts for given risk budget"""
        risk_per = self.calculate_profit(Config.STOP_LOSS_PTS, 1)
        return int(risk_budget / risk_per) if risk_per > 0 else 0
    
    def analyze_level_hits(self, setup: TradeSetup, session_high: float, 
                          session_low: float) -> List[LevelHit]:
        """Analyze which levels were hit during session"""
        hits = []
        
        is_calls = setup.direction == Bias.CALLS
        
        # Entry level
        entry_hit = (session_low <= setup.entry) if is_calls else (session_high >= setup.entry)
        hits.append(LevelHit(
            level_name="Entry",
            level_price=setup.entry,
            status=LevelStatus.HIT if entry_hit else LevelStatus.NOT_HIT
        ))
        
        # Only check targets/stop if entry was hit
        if entry_hit:
            # Stop
            if is_calls:
                stop_hit = session_low <= setup.stop
            else:
                stop_hit = session_high >= setup.stop
            
            hits.append(LevelHit(
                level_name="Stop",
                level_price=setup.stop,
                status=LevelStatus.STOPPED if stop_hit else LevelStatus.NOT_HIT
            ))
            
            # Targets
            for name, price in [("12.5%", setup.target_1), ("25%", setup.target_2), ("50%", setup.target_3)]:
                if is_calls:
                    target_hit = session_high >= price
                else:
                    target_hit = session_low <= price
                
                hits.append(LevelHit(
                    level_name=name,
                    level_price=price,
                    status=LevelStatus.HIT if target_hit else LevelStatus.NOT_HIT
                ))
        else:
            # Entry not hit - all others pending/not applicable
            hits.append(LevelHit("Stop", setup.stop, LevelStatus.NOT_HIT))
            hits.append(LevelHit("12.5%", setup.target_1, LevelStatus.NOT_HIT))
            hits.append(LevelHit("25%", setup.target_2, LevelStatus.NOT_HIT))
            hits.append(LevelHit("50%", setup.target_3, LevelStatus.NOT_HIT))
        
        return hits
    
    def calculate_theoretical_pnl(self, setup: TradeSetup, hits: List[LevelHit], 
                                  contracts: int = 1) -> Tuple[float, str]:
        """Calculate theoretical P&L based on level hits"""
        entry_hit = any(h.level_name == "Entry" and h.status == LevelStatus.HIT for h in hits)
        
        if not entry_hit:
            return 0.0, "Entry not reached"
        
        stop_hit = any(h.level_name == "Stop" and h.status == LevelStatus.STOPPED for h in hits)
        
        if stop_hit:
            pnl = -self.calculate_profit(Config.STOP_LOSS_PTS, contracts)
            return pnl, "Stopped out"
        
        # Find highest target hit
        target_hits = [(h.level_name, h.level_price) for h in hits 
                       if h.level_name in ["12.5%", "25%", "50%"] and h.status == LevelStatus.HIT]
        
        if not target_hits:
            return 0.0, "Entry hit, no targets reached"
        
        # Calculate based on highest target
        target_map = {"12.5%": Config.TARGET_1_PCT, "25%": Config.TARGET_2_PCT, "50%": Config.TARGET_3_PCT}
        highest = max(target_hits, key=lambda x: target_map.get(x[0], 0))
        
        points = abs(highest[1] - setup.entry)
        pnl = self.calculate_profit(points, contracts)
        
        return pnl, f"{highest[0]} target hit"


# =============================================================================
# DATA FETCHING
# =============================================================================

@st.cache_data(ttl=60)
def fetch_live_data() -> Tuple[Optional[float], Optional[float], Optional[Dict]]:
    """Fetch current SPX and VIX data"""
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
    except Exception as e:
        st.error(f"Data fetch error: {e}")
        return None, None, None


@st.cache_data(ttl=300)
def fetch_historical_data(target_date: date) -> Optional[Dict]:
    """Fetch historical data for a specific date"""
    try:
        spx = yf.Ticker("^GSPC")
        
        # Fetch range around target date
        start = target_date - timedelta(days=5)
        end = target_date + timedelta(days=1)
        
        hist = spx.history(start=start, end=end)
        
        if hist.empty:
            return None
        
        # Find the exact date or closest
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
    except Exception as e:
        return None


# =============================================================================
# GLOBAL STYLES
# =============================================================================

def inject_styles():
    """Inject global CSS styles"""
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

/* Dark theme base */
.stApp {
    background: linear-gradient(180deg, #0a0f1a 0%, #0f172a 100%);
}

/* Typography */
h1, h2, h3, h4, h5, h6 {
    font-family: 'Inter', sans-serif !important;
    color: #f8fafc !important;
}

p, span, label, div {
    font-family: 'Inter', sans-serif;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
    border-right: 1px solid #334155;
}

[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, 
[data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {
    color: #f8fafc !important;
}

/* Metrics */
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.1rem !important;
    color: #f8fafc !important;
}

[data-testid="stMetricLabel"] {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.7rem !important;
    color: #94a3b8 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

[data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace !important;
}

/* Dataframes */
.stDataFrame {
    border-radius: 8px;
    border: 1px solid #334155;
}

/* Inputs */
.stNumberInput input, .stTextInput input, .stDateInput input {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    color: #f8fafc !important;
    border-radius: 6px !important;
    font-family: 'JetBrains Mono', monospace !important;
}

.stSelectbox > div > div {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
}

/* Checkbox */
.stCheckbox label {
    color: #cbd5e1 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: #1e293b;
    padding: 8px;
    border-radius: 8px;
}

.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #94a3b8;
    border-radius: 6px;
    padding: 8px 16px;
}

.stTabs [aria-selected="true"] {
    background: #3b82f6 !important;
    color: white !important;
}

/* Info/Warning/Error boxes */
.stAlert {
    border-radius: 8px;
}

/* Hide footer */
footer {visibility: hidden;}

/* Custom scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: #1e293b;
}
::-webkit-scrollbar-thumb {
    background: #475569;
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: #64748b;
}
</style>
""", unsafe_allow_html=True)


# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_header(spx: float, vix: float, phase: Phase, engine: SPXProphetEngine):
    """Render main header with phase indicator"""
    now = engine.get_current_time_ct()
    next_phase, time_remaining = engine.get_time_to_next_phase(now)
    
    # Format countdown
    hours, remainder = divmod(int(time_remaining.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    countdown = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    st.markdown(f"""
<div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
        <div>
            <h1 style="font-family: 'JetBrains Mono', monospace; font-size: 1.75rem; font-weight: 700; color: #f8fafc; margin: 0; letter-spacing: -0.5px;">SPX PROPHET</h1>
            <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; margin: 4px 0 0 0; text-transform: uppercase; letter-spacing: 1.5px;">Institutional 0DTE Decision System</p>
        </div>
        <div style="display: flex; gap: 24px; align-items: center;">
            <div style="text-align: right;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; margin: 0; text-transform: uppercase; letter-spacing: 1px;">SPX</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.4rem; font-weight: 700; color: #f8fafc; margin: 0;">{spx:,.2f}</p>
            </div>
            <div style="text-align: right;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; margin: 0; text-transform: uppercase; letter-spacing: 1px;">VIX</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.4rem; font-weight: 700; color: #f8fafc; margin: 0;">{vix:.2f}</p>
            </div>
            <div style="text-align: right; border-left: 1px solid #334155; padding-left: 24px;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; margin: 0; text-transform: uppercase; letter-spacing: 1px;">{now.strftime('%I:%M:%S %p')} CT</p>
                <p style="font-family: 'Inter', sans-serif; font-size: 0.9rem; font-weight: 600; color: {phase.color}; margin: 4px 0 0 0;">{phase.icon} {phase.label}</p>
            </div>
            <div style="text-align: right; background: rgba(0,0,0,0.3); padding: 8px 12px; border-radius: 8px;">
                <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; color: #64748b; margin: 0; text-transform: uppercase;">Next: {next_phase.label}</p>
                <p style="font-family: 'JetBrains Mono', monospace; font-size: 1rem; font-weight: 600; color: {next_phase.color}; margin: 2px 0 0 0;">{countdown}</p>
            </div>
        </div>
    </div>
    <div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #334155;">
        <p style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: #94a3b8; margin: 0;">
            <span style="color: {phase.color}; font-weight: 600;">{phase.mode}</span> — {get_phase_guidance(phase)}
        </p>
    </div>
</div>
""", unsafe_allow_html=True)


def get_phase_guidance(phase: Phase) -> str:
    """Get contextual guidance for current phase"""
    guidance = {
        Phase.OVERNIGHT: "Monitor VIX to establish zone boundaries. Record high and low values.",
        Phase.ZONE_LOCK: "Zone locked. Analyze bias and identify cone entry levels. Reliable breakout window.",
        Phase.DANGER_ZONE: "⚠️ Caution: VIX reversals common. Wait for confirmation before entering.",
        Phase.RTH: "Primary trading window. Execute setups when entry checklist is complete.",
        Phase.POST_SESSION: "Review session performance. Analyze which levels were hit.",
        Phase.MARKET_CLOSED: "Market closed. Use historical mode to analyze past sessions."
    }
    return guidance.get(phase, "")


def render_bias_card(bias: Bias, confidence: Confidence, explanation: str, phase: Phase):
    """Render bias determination card with phase-aware styling"""
    
    # Danger zone gets muted styling
    if phase == Phase.DANGER_ZONE and bias != Bias.WAIT:
        border_style = f"border: 2px dashed {bias.color};"
        opacity = "opacity: 0.8;"
        warning = '<p style="font-size: 0.7rem; color: #f59e0b; margin-top: 8px;">⚠️ DANGER ZONE - Await confirmation</p>'
    else:
        border_style = f"border: 2px solid {bias.color};"
        opacity = ""
        warning = ""
    
    bg_colors = {
        Bias.CALLS: "#064e3b",
        Bias.PUTS: "#7f1d1d",
        Bias.WAIT: "#78350f"
    }
    
    st.markdown(f"""
<div style="background: linear-gradient(135deg, {bg_colors.get(bias, '#1f2937')} 0%, #1e293b 100%); {border_style} border-radius: 12px; padding: 24px; text-align: center; margin-bottom: 20px; {opacity}">
    <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 2px; margin: 0 0 8px 0;">Today's Bias</p>
    <h2 style="font-family: 'JetBrains Mono', monospace; font-size: 2.5rem; font-weight: 700; color: {bias.color}; margin: 0; letter-spacing: 3px;">{bias.icon} {bias.label}</h2>
    <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; color: {confidence.color}; margin: 12px 0 4px 0; letter-spacing: 3px;">{confidence.dots}</p>
    <p style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: {confidence.color}; margin: 0;">{confidence.label}</p>
    <div style="margin-top: 16px; padding: 12px; background: rgba(0,0,0,0.3); border-radius: 8px;">
        <p style="font-family: 'Inter', sans-serif; font-size: 0.8rem; color: #cbd5e1; margin: 0;">{explanation}</p>
    </div>
    {warning}
</div>
""", unsafe_allow_html=True)


def render_vix_zone(zone: VIXZone):
    """Render VIX zone ladder"""
    
    valid, valid_msg = zone.is_valid()
    
    def level_row(label: str, value: float, style_type: str) -> str:
        styles = {
            "extension": "background: #1e293b; color: #64748b;",
            "top": "background: #064e3b; color: #10b981; border: 1px solid #10b981;",
            "bottom": "background: #7f1d1d; color: #ef4444; border: 1px solid #ef4444;",
            "current": "background: #1e3a8a; color: #60a5fa; border: 2px solid #3b82f6; font-weight: 600;"
        }
        return f'''<div style="display: flex; justify-content: space-between; padding: 8px 14px; margin: 3px 0; border-radius: 6px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; {styles.get(style_type, '')}">
            <span>{label}</span><span>{value:.2f}</span>
        </div>'''
    
    rows = ""
    rows += level_row("+2", zone.get_extension(2), "extension")
    rows += level_row("+1", zone.get_extension(1), "extension")
    rows += level_row("TOP", zone.top, "top")
    rows += level_row(f"VIX {zone.current:.2f}", zone.current, "current")
    rows += level_row("BOTTOM", zone.bottom, "bottom")
    rows += level_row("-1", zone.get_extension(-1), "extension")
    rows += level_row("-2", zone.get_extension(-2), "extension")
    
    potential_colors = {"LOW": "#f59e0b", "NORMAL": "#3b82f6", "HIGH": "#10b981"}
    
    validation_html = ""
    if not valid:
        validation_html = f'<p style="font-size: 0.7rem; color: #ef4444; margin-top: 8px;">⚠️ {valid_msg}</p>'
    
    st.markdown(f"""
<div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 12px; padding: 16px;">
    <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 12px 0;">📊 VIX Zone Ladder</p>
    {rows}
    <div style="display: flex; justify-content: space-between; margin-top: 14px; padding-top: 14px; border-top: 1px solid #334155;">
        <div style="text-align: center; flex: 1;">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; text-transform: uppercase; margin: 0;">Size</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; color: #f8fafc; margin: 4px 0 0 0;">{zone.size:.2f}</p>
        </div>
        <div style="text-align: center; flex: 1;">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; text-transform: uppercase; margin: 0;">Position</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; color: #f8fafc; margin: 4px 0 0 0;">{zone.position_pct:.0f}%</p>
        </div>
        <div style="text-align: center; flex: 1;">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.65rem; color: #64748b; text-transform: uppercase; margin: 0;">Potential</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; font-weight: 600; color: {potential_colors.get(zone.potential, '#64748b')}; margin: 4px 0 0 0;">{zone.potential_emoji} {zone.potential}</p>
        </div>
    </div>
    {validation_html}
</div>
""", unsafe_allow_html=True)


def render_entry_checklist(zone: VIXZone, phase: Phase, setup: Optional[TradeSetup], 
                          current_price: float, engine: SPXProphetEngine):
    """Render entry checklist with live updates"""
    
    checks = []
    
    # 1. VIX at zone edge
    vix_at_edge = zone.position_pct >= Config.ZONE_TOP_PCT or zone.position_pct <= Config.ZONE_BOTTOM_PCT
    checks.append(("VIX at zone edge (≤25% or ≥75%)", vix_at_edge, f"Currently at {zone.position_pct:.0f}%"))
    
    # 2. Reliable timing window
    reliable_window = phase in [Phase.ZONE_LOCK, Phase.RTH]
    window_note = "✓ Reliable" if reliable_window else f"Current: {phase.label}"
    checks.append(("Reliable timing window", reliable_window, window_note))
    
    # 3. 30-min candle (placeholder - would need real candle data)
    candle_closed = True  # Assume true for now
    checks.append(("30-min candle closed", candle_closed, "Awaiting candle data"))
    
    # 4. Price at rail entry
    price_at_entry = False
    distance_note = "No setup"
    if setup:
        distance = abs(current_price - setup.entry)
        price_at_entry = distance <= 5.0
        distance_note = f"{distance:.1f} pts away"
    checks.append(("Price at rail entry (within 5 pts)", price_at_entry, distance_note))
    
    # 5. Cone width
    cone_valid = setup and setup.cone.is_tradeable if setup else False
    width_note = f"{setup.cone.width:.1f} pts" if setup else "No setup"
    checks.append(("Cone width ≥ 18 pts", cone_valid, width_note))
    
    # Build HTML
    items_html = ""
    for label, passed, note in checks:
        icon = "✓" if passed else "○"
        icon_color = "#10b981" if passed else "#475569"
        text_color = "#e2e8f0" if passed else "#64748b"
        items_html += f'''
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #1e293b;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.1rem; color: {icon_color}; width: 20px;">{icon}</span>
                <span style="font-family: 'Inter', sans-serif; font-size: 0.8rem; color: {text_color};">{label}</span>
            </div>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; color: #64748b;">{note}</span>
        </div>'''
    
    all_pass = all(p for _, p, _ in checks)
    status_bg = "#064e3b" if all_pass else "#1e293b"
    status_color = "#10b981" if all_pass else "#64748b"
    status_border = "#10b981" if all_pass else "#334155"
    status_text = "✓ READY TO ENTER" if all_pass else "WAITING FOR CONDITIONS"
    
    st.markdown(f"""
<div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 12px; padding: 16px;">
    <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 12px 0;">✅ Entry Checklist</p>
    {items_html}
    <div style="margin-top: 14px; padding: 12px; background: {status_bg}; border-radius: 8px; text-align: center; border: 1px solid {status_border};">
        <p style="font-family: 'Inter', sans-serif; font-size: 0.8rem; font-weight: 600; color: {status_color}; margin: 0; text-transform: uppercase; letter-spacing: 1px;">{status_text}</p>
    </div>
</div>
""", unsafe_allow_html=True)


def render_cone_table(cones: List[ConeRails], best_name: str):
    """Render cone rails table"""
    
    st.markdown("""
<p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin: 20px 0 10px 0;">📐 Cone Rails</p>
""", unsafe_allow_html=True)
    
    data = []
    for c in cones:
        is_best = c.pivot.name == best_name
        status = "⭐ BEST" if is_best else ("✓ Valid" if c.is_tradeable else "✗ Narrow")
        data.append({
            "Pivot": c.pivot.name,
            "Type": c.pivot.pivot_type.title(),
            "Ascending": f"{c.ascending:,.2f}",
            "Descending": f"{c.descending:,.2f}",
            "Width": f"{c.width:.1f}",
            "Blocks": c.blocks,
            "Status": status
        })
    
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No cones configured. Add pivot data in the sidebar.")


def render_setup_card(setup: TradeSetup, current_price: float, engine: SPXProphetEngine, 
                     is_best: bool = False):
    """Render trade setup card"""
    
    color = setup.direction.color
    bg = "#064e3b" if setup.direction == Bias.CALLS else "#7f1d1d"
    
    distance = current_price - setup.entry
    dist_str = f"{'+' if distance > 0 else ''}{distance:.2f}"
    dist_color = "#10b981" if abs(distance) <= 10 else "#64748b"
    
    # Profits
    p1 = engine.calculate_profit(setup.reward_1_pts, 1)
    p2 = engine.calculate_profit(setup.reward_2_pts, 1)
    p3 = engine.calculate_profit(setup.reward_3_pts, 1)
    risk = engine.calculate_profit(Config.STOP_LOSS_PTS, 1)
    rr = p2 / risk if risk > 0 else 0
    
    best_badge = '<span style="background: #fbbf24; color: #000; padding: 2px 8px; border-radius: 4px; font-size: 0.6rem; font-weight: 600; margin-left: 8px;">⭐ BEST</span>' if is_best else ''
    
    def price_box(label: str, value: float, highlight: bool = False, is_stop: bool = False) -> str:
        border = f"border: 1px solid {color};" if highlight else ("border: 1px solid #ef4444;" if is_stop else "")
        return f'''<div style="background: rgba(0,0,0,0.3); border-radius: 6px; padding: 10px 6px; text-align: center; {border}">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 4px 0;">{label}</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; font-weight: 600; color: #f8fafc; margin: 0;">{value:,.2f}</p>
        </div>'''
    
    def stat_item(label: str, value: str, color: str = "#f8fafc") -> str:
        return f'''<div style="text-align: center;">
            <p style="font-family: 'Inter', sans-serif; font-size: 0.6rem; color: #64748b; text-transform: uppercase; margin: 0;">{label}</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; color: {color}; margin: 2px 0 0 0;">{value}</p>
        </div>'''
    
    st.markdown(f"""
<div style="background: linear-gradient(135deg, {bg} 0%, #1e293b 100%); border: 2px solid {color}; border-radius: 12px; padding: 16px; margin-bottom: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
        <span style="font-family: 'JetBrains Mono', monospace; font-size: 1rem; font-weight: 700; color: {color};">{setup.direction.icon} {setup.direction.label} SETUP{best_badge}</span>
        <span style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #94a3b8;">{setup.cone.pivot.name} Cone</span>
    </div>
    <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 14px;">
        {price_box("Entry", setup.entry, True)}
        {price_box("Stop", setup.stop, False, True)}
        {price_box("12.5%", setup.target_1)}
        {price_box("25%", setup.target_2)}
        {price_box("50%", setup.target_3)}
    </div>
    <div style="display: flex; justify-content: space-between; padding-top: 12px; border-top: 1px solid #334155;">
        {stat_item("Distance", f"{dist_str} pts", dist_color)}
        {stat_item("Strike", str(setup.strike))}
        {stat_item("Width", f"{setup.cone.width:.1f}")}
        {stat_item("R:R @25%", f"{rr:.1f}:1")}
        {stat_item("Profit @25%", f"${p2:,.0f}", "#10b981")}
    </div>
</div>
""", unsafe_allow_html=True)


def render_position_calculator(engine: SPXProphetEngine, setup: Optional[TradeSetup]):
    """Render position sizing calculator"""
    
    st.markdown("""
<p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 12px 0;">💰 Position Calculator</p>
""", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        risk_budget = st.number_input("Risk Budget ($)", min_value=100, max_value=100000, 
                                      value=1000, step=100, key="risk_budget")
    with col2:
        if setup:
            st.metric("Max Contracts", engine.calculate_max_contracts(risk_budget))
    
    if setup:
        contracts = engine.calculate_max_contracts(risk_budget)
        risk_total = engine.calculate_profit(Config.STOP_LOSS_PTS, contracts)
        p1 = engine.calculate_profit(setup.reward_1_pts, contracts)
        p2 = engine.calculate_profit(setup.reward_2_pts, contracts)
        p3 = engine.calculate_profit(setup.reward_3_pts, contracts)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Risk", f"${risk_total:,.0f}", delta=None)
        with col2:
            st.metric("@ 12.5%", f"${p1:,.0f}", delta=f"{p1/risk_total:.1f}x" if risk_total > 0 else None)
        with col3:
            st.metric("@ 25%", f"${p2:,.0f}", delta=f"{p2/risk_total:.1f}x" if risk_total > 0 else None)
        with col4:
            st.metric("@ 50%", f"${p3:,.0f}", delta=f"{p3/risk_total:.1f}x" if risk_total > 0 else None)
    else:
        st.info("Configure a valid setup to calculate position sizing.")


def render_historical_analysis(session_data: Dict, setup: TradeSetup, hits: List[LevelHit],
                              pnl: float, pnl_note: str, engine: SPXProphetEngine):
    """Render historical session analysis"""
    
    st.markdown(f"""
<div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
    <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 16px 0;">📊 Session Analysis</p>
    <div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px;">
        <div style="text-align: center;">
            <p style="font-size: 0.65rem; color: #64748b; margin: 0;">OPEN</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #f8fafc; margin: 4px 0 0 0;">{session_data['open']:,.2f}</p>
        </div>
        <div style="text-align: center;">
            <p style="font-size: 0.65rem; color: #64748b; margin: 0;">HIGH</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #10b981; margin: 4px 0 0 0;">{session_data['high']:,.2f}</p>
        </div>
        <div style="text-align: center;">
            <p style="font-size: 0.65rem; color: #64748b; margin: 0;">LOW</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #ef4444; margin: 4px 0 0 0;">{session_data['low']:,.2f}</p>
        </div>
        <div style="text-align: center;">
            <p style="font-size: 0.65rem; color: #64748b; margin: 0;">CLOSE</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #f8fafc; margin: 4px 0 0 0;">{session_data['close']:,.2f}</p>
        </div>
        <div style="text-align: center;">
            <p style="font-size: 0.65rem; color: #64748b; margin: 0;">RANGE</p>
            <p style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #3b82f6; margin: 4px 0 0 0;">{session_data['range']:.2f}</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
    
    # Level hits
    st.markdown("##### Level Hits")
    
    hits_html = ""
    for hit in hits:
        hits_html += f'''
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; margin: 4px 0; background: #1e293b; border-radius: 6px; border-left: 3px solid {hit.status.color};">
            <span style="font-family: 'Inter', sans-serif; font-size: 0.8rem; color: #e2e8f0;">{hit.level_name}</span>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #94a3b8;">{hit.level_price:,.2f}</span>
            <span style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: {hit.status.color}; font-weight: 600;">{hit.status.icon} {hit.status.label}</span>
        </div>'''
    
    pnl_color = "#10b981" if pnl >= 0 else "#ef4444"
    pnl_prefix = "+" if pnl >= 0 else ""
    
    st.markdown(f"""
<div style="margin-top: 12px;">
    {hits_html}
</div>
<div style="margin-top: 16px; padding: 16px; background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-radius: 8px; border: 1px solid #334155;">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <p style="font-size: 0.7rem; color: #64748b; margin: 0; text-transform: uppercase;">Theoretical P&L (1 contract)</p>
            <p style="font-size: 0.75rem; color: #94a3b8; margin: 4px 0 0 0;">{pnl_note}</p>
        </div>
        <p style="font-family: 'JetBrains Mono', monospace; font-size: 1.5rem; font-weight: 700; color: {pnl_color}; margin: 0;">{pnl_prefix}${abs(pnl):,.2f}</p>
    </div>
</div>
""", unsafe_allow_html=True)


def render_audit_log(audit_log: List[AuditEntry]):
    """Render audit trail"""
    
    if not audit_log:
        st.info("No audit entries yet.")
        return
    
    st.markdown("##### 📋 Audit Trail")
    
    for entry in reversed(audit_log[-10:]):  # Show last 10
        st.markdown(f"""
<div style="padding: 8px 12px; margin: 4px 0; background: #1e293b; border-radius: 6px; border-left: 3px solid #3b82f6;">
    <div style="display: flex; justify-content: space-between;">
        <span style="font-family: 'Inter', sans-serif; font-size: 0.75rem; color: #f8fafc; font-weight: 600;">{entry.event}</span>
        <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; color: #64748b;">{entry.timestamp.strftime('%H:%M:%S')}</span>
    </div>
    <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #94a3b8; margin: 4px 0 0 0;">{entry.details}</p>
</div>
""", unsafe_allow_html=True)


def render_trade_rules():
    """Render trade rules reminder"""
    
    st.markdown("""
<div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 1px solid #334155; border-radius: 12px; padding: 16px;">
    <p style="font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 12px 0;">📖 Trade Rules</p>
    <div style="font-family: 'Inter', sans-serif; font-size: 0.8rem; color: #cbd5e1; line-height: 1.8;">
        <p style="margin: 0 0 8px 0;"><strong style="color: #f8fafc;">Entry:</strong> CALLS at descending rail (support) • PUTS at ascending rail (resistance)</p>
        <p style="margin: 0 0 8px 0;"><strong style="color: #f8fafc;">Stop:</strong> Fixed 6 points from entry</p>
        <p style="margin: 0 0 8px 0;"><strong style="color: #f8fafc;">Targets:</strong> 12.5% → 25% → 50% of cone width</p>
        <p style="margin: 0 0 8px 0;"><strong style="color: #f8fafc;">Confirmation:</strong> Wait for 30-min candle CLOSE at level</p>
        <p style="margin: 0;"><strong style="color: #f59e0b;">⚠️ Danger Zone:</strong> 6:30-9:30 AM CT — VIX reversals common</p>
    </div>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar(engine: SPXProphetEngine, prior_data: Optional[Dict]) -> Tuple[str, date, VIXZone, List[Pivot]]:
    """Render sidebar configuration"""
    
    st.sidebar.markdown("## ⚙️ Configuration")
    
    # Mode Selection
    st.sidebar.markdown("#### 📌 Mode")
    mode = st.sidebar.radio(
        "Select Mode",
        ["Live Trading", "Historical Analysis"],
        horizontal=True,
        label_visibility="collapsed"
    )
    
    st.sidebar.markdown("---")
    
    # Date Selection
    st.sidebar.markdown("#### 📅 Session Date")
    ct_tz = pytz.timezone('America/Chicago')
    today = datetime.now(ct_tz).date()
    
    if mode == "Live Trading":
        session_date = today
        st.sidebar.info(f"📍 Today: {session_date.strftime('%B %d, %Y')}")
    else:
        session_date = st.sidebar.date_input(
            "Select Date",
            value=today - timedelta(days=1),
            max_value=today,
            key="session_date"
        )
    
    st.sidebar.markdown("---")
    
    # VIX Zone
    st.sidebar.markdown("#### 📊 VIX Zone")
    st.sidebar.caption("Overnight range (5pm-2am CT)")
    
    c1, c2 = st.sidebar.columns(2)
    vix_bottom = c1.number_input("Bottom", 5.0, 100.0, 16.50, 0.01, format="%.2f", key="vix_bottom")
    vix_top = c2.number_input("Top", 5.0, 100.0, 16.65, 0.01, format="%.2f", key="vix_top")
    vix_current = st.sidebar.number_input("Current VIX", 5.0, 100.0, 16.55, 0.01, format="%.2f", key="vix_current")
    
    zone = VIXZone(vix_bottom, vix_top, vix_current)
    
    st.sidebar.markdown("---")
    
    # Prior Day Pivots
    st.sidebar.markdown("#### 📍 Prior Day Pivots")
    manual_pivots = st.sidebar.checkbox("✏️ Manual Input", value=False, key="manual_pivots")
    
    # Calculate prior date
    prior_date = session_date - timedelta(days=1)
    if prior_date.weekday() == 6:
        prior_date -= timedelta(days=2)
    elif prior_date.weekday() == 5:
        prior_date -= timedelta(days=1)
    
    if manual_pivots or prior_data is None:
        st.sidebar.caption(f"Pivots from: {prior_date}")
        c1, c2 = st.sidebar.columns(2)
        p_high = c1.number_input("High", 1000.0, 10000.0, 6050.0, 1.0, key="p_high")
        p_high_t = c2.time_input("Time", time(11, 30), key="p_high_t")
        
        c1, c2 = st.sidebar.columns(2)
        p_low = c1.number_input("Low", 1000.0, 10000.0, 6020.0, 1.0, key="p_low")
        p_low_t = c2.time_input("Time", time(14, 0), key="p_low_t")
        
        p_close = st.sidebar.number_input("Close", 1000.0, 10000.0, 6035.0, 1.0, key="p_close")
    else:
        p_high = prior_data['high']
        p_low = prior_data['low']
        p_close = prior_data['close']
        prior_date = prior_data['date'].date() if hasattr(prior_data['date'], 'date') else prior_data['date']
        p_high_t = time(11, 30)
        p_low_t = time(14, 0)
        
        st.sidebar.success(f"✓ Loaded: {prior_date}")
        st.sidebar.caption(f"H: {p_high:,.2f} | L: {p_low:,.2f} | C: {p_close:,.2f}")
    
    pivots = [
        Pivot("Prior High", p_high, ct_tz.localize(datetime.combine(prior_date, p_high_t)), "primary"),
        Pivot("Prior Low", p_low, ct_tz.localize(datetime.combine(prior_date, p_low_t)), "primary"),
        Pivot("Prior Close", p_close, ct_tz.localize(datetime.combine(prior_date, time(16, 0))), "primary")
    ]
    
    st.sidebar.markdown("---")
    
    # Secondary Pivots
    st.sidebar.markdown("#### 📍 Secondary Pivots")
    st.sidebar.caption("Optional additional levels")
    
    if st.sidebar.checkbox("Enable High²", key="en_h2"):
        c1, c2 = st.sidebar.columns(2)
        h2_price = c1.number_input("Price", 1000.0, 10000.0, p_high - 10, 1.0, key="h2_price")
        h2_time = c2.time_input("Time", time(10, 0), key="h2_time")
        pivots.append(Pivot("High²", h2_price, ct_tz.localize(datetime.combine(prior_date, h2_time)), "secondary"))
    
    if st.sidebar.checkbox("Enable Low²", key="en_l2"):
        c1, c2 = st.sidebar.columns(2)
        l2_price = c1.number_input("Price", 1000.0, 10000.0, p_low + 10, 1.0, key="l2_price")
        l2_time = c2.time_input("Time", time(13, 0), key="l2_time")
        pivots.append(Pivot("Low²", l2_price, ct_tz.localize(datetime.combine(prior_date, l2_time)), "secondary"))
    
    st.sidebar.markdown("---")
    st.sidebar.caption("SPX Prophet v4.0 | Institutional Grade")
    
    return mode, session_date, zone, pivots


# =============================================================================
# MAIN APPLICATION
# =============================================================================

def main():
    # Initialize
    inject_styles()
    engine = SPXProphetEngine()
    ct_tz = pytz.timezone('America/Chicago')
    
    # Fetch live data
    spx_live, vix_live, prior_data = fetch_live_data()
    spx_price = spx_live or 6000.0
    vix_price = vix_live or 16.50
    
    # Render sidebar
    mode, session_date, zone, pivots = render_sidebar(engine, prior_data)
    
    # Update zone with live VIX if in live mode
    if mode == "Live Trading" and vix_live:
        zone = VIXZone(zone.bottom, zone.top, vix_live)
    
    # Get current phase
    now = engine.get_current_time_ct()
    phase = engine.get_phase(now)
    
    # Determine bias
    bias, confidence, explanation = engine.determine_bias(zone, phase)
    
    # Calculate cones
    if mode == "Live Trading":
        eval_time = ct_tz.localize(datetime.combine(now.date(), time(10, 0)))
        if now.time() > time(10, 0):
            eval_time = now
    else:
        eval_time = ct_tz.localize(datetime.combine(session_date, time(10, 0)))
    
    cones = [engine.calculate_cone(p, eval_time) for p in pivots if p.enabled]
    
    # Find best cone
    valid_cones = [c for c in cones if c.is_tradeable]
    best_cone = max(valid_cones, key=lambda x: x.width) if valid_cones else None
    best_name = best_cone.pivot.name if best_cone else ""
    
    # Generate setups
    setups = []
    for cone in cones:
        if cone.is_tradeable:
            setup = engine.generate_setup(cone, bias)
            if setup:
                setups.append(setup)
    
    best_setup = next((s for s in setups if s.cone.pivot.name == best_name), None)
    
    # ==========================================================================
    # RENDER UI
    # ==========================================================================
    
    # Header
    render_header(spx_price, vix_price, phase, engine)
    
    # Main content based on mode
    if mode == "Live Trading":
        # Bias Card
        render_bias_card(bias, confidence, explanation, phase)
        
        # Two column layout
        col1, col2 = st.columns(2)
        
        with col1:
            render_vix_zone(zone)
        
        with col2:
            render_entry_checklist(zone, phase, best_setup, spx_price, engine)
        
        # Cone table
        render_cone_table(cones, best_name)
        
        # Trade setups
        if bias != Bias.WAIT and setups:
            st.markdown(f"### {bias.icon} {bias.label} Setups")
            for setup in setups:
                is_best = setup.cone.pivot.name == best_name
                render_setup_card(setup, spx_price, engine, is_best)
        elif bias == Bias.WAIT:
            st.info("📊 VIX is mid-zone. No directional edge. Waiting for VIX to reach zone edge...")
        else:
            st.warning("No valid setups available. Check cone widths and pivot configuration.")
        
        # Bottom section
        st.markdown("---")
        col1, col2 = st.columns([1, 1])
        
        with col1:
            render_position_calculator(engine, best_setup)
        
        with col2:
            render_trade_rules()
        
        # Audit log (collapsible)
        with st.expander("📋 Audit Trail"):
            render_audit_log(engine.audit_log)
    
    else:
        # Historical Analysis Mode
        st.markdown(f"### 📊 Historical Analysis: {session_date.strftime('%B %d, %Y')}")
        
        # Fetch historical session data
        session_data = fetch_historical_data(session_date)
        
        if session_data:
            # Show bias card
            render_bias_card(bias, confidence, explanation, Phase.POST_SESSION)
            
            # Two columns
            col1, col2 = st.columns(2)
            
            with col1:
                render_vix_zone(zone)
            
            with col2:
                # Session stats and level hits
                if best_setup:
                    hits = engine.analyze_level_hits(best_setup, session_data['high'], session_data['low'])
                    pnl, pnl_note = engine.calculate_theoretical_pnl(best_setup, hits, 1)
                    render_historical_analysis(session_data, best_setup, hits, pnl, pnl_note, engine)
                else:
                    st.info("Configure pivots to analyze levels")
            
            # All setups with their level analysis
            render_cone_table(cones, best_name)
            
            if setups:
                st.markdown("### Setup Analysis")
                for setup in setups:
                    is_best = setup.cone.pivot.name == best_name
                    
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        render_setup_card(setup, session_data['close'], engine, is_best)
                    
                    with col2:
                        hits = engine.analyze_level_hits(setup, session_data['high'], session_data['low'])
                        pnl, note = engine.calculate_theoretical_pnl(setup, hits, 1)
                        
                        # Compact level hits
                        for hit in hits:
                            icon_html = f'<span style="color: {hit.status.color};">{hit.status.icon}</span>'
                            st.markdown(f"{icon_html} **{hit.level_name}**: {hit.level_price:,.2f} - {hit.status.label}", 
                                       unsafe_allow_html=True)
                        
                        pnl_color = "#10b981" if pnl >= 0 else "#ef4444"
                        st.markdown(f"**P&L:** <span style='color: {pnl_color};'>${pnl:,.2f}</span> ({note})", 
                                   unsafe_allow_html=True)
        else:
            st.error(f"No data available for {session_date}. This may be a weekend or holiday.")
            st.info("Try selecting a different date.")
    
    # Footer
    st.markdown("---")
    st.caption("SPX Prophet v4.0 | Institutional Grade 0DTE Decision System | Data: Yahoo Finance | Not Financial Advice")


if __name__ == "__main__":
    main()
