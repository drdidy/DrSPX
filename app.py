from __future__ import annotations
import io, zipfile
from datetime import datetime, date, time, timedelta
from typing import Dict, List, Tuple, Optional, Any
import logging

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# ===== APPLICATION METADATA =====
APP_NAME = "MarketLens Pro"
VERSION = "4.0.0"
COMPANY = "Quantum Trading Systems"
TAGLINE = "Advanced SPX Forecasting & Analytics Platform"

# ===== STRATEGY CONSTANTS =====
SPX_SLOPES_DOWN = {"HIGH": -0.2792, "CLOSE": -0.2792, "LOW": -0.2792}
SPX_SLOPES_UP   = {"HIGH": +0.3171, "CLOSE": +0.3171, "LOW": +0.3171}
TICK = 0.25
BASELINE_DATE_STR = "2000-01-01"

# ===== DESIGN SYSTEM CONSTANTS =====
COLORS = {
    "primary": "#007AFF", "primary_dark": "#0056CC", "secondary": "#5AC8FA", "accent": "#FF3B30",
    "tesla_red": "#E31937", "tesla_black": "#171A20", "tesla_white": "#FFFFFF", "tesla_gray": "#393C41",
    "success": "#34C759", "warning": "#FF9500", "error": "#FF3B30", "info": "#007AFF",
    "gray_50": "#F9FAFB","gray_100": "#F3F4F6","gray_200": "#E5E7EB","gray_300": "#D1D5DB",
    "gray_400": "#9CA3AF","gray_500": "#6B7280","gray_600": "#4B5563","gray_700": "#374151",
    "gray_800": "#1F2937","gray_900": "#111827",
    "bull": "#00D4AA","bear": "#FF6B6B","neutral": "#8B5CF6",
}

ICONS = {"high":"📈","close":"⚡","low":"📉","trending_up":"↗️","trending_down":"↘️","analytics":"🔍",
         "settings":"⚙️","export":"📊","fibonacci":"🌀","contract":"📋","live":"🔴"}

FONT_SIZES = {"xs":"0.75rem","sm":"0.875rem","base":"1rem","lg":"1.125rem","xl":"1.25rem",
              "2xl":"1.5rem","3xl":"1.875rem","4xl":"2.25rem"}

# ===== TRADING RULES & STRATEGIES (unchanged content) =====
SPX_GOLDEN_RULES = [
    "🎯 Exit levels are exits - never entries",
    "🧲 Anchors are magnets, not timing signals - let price come to you", 
    "⏰ The market will give you your entry - don't force it",
    "📊 Consistency in process trumps perfection in prediction",
    "🤔 When in doubt, stay out - there's always another trade",
    "🚫 SPX ignores the full 16:00-17:00 maintenance block",
]

SPX_ANCHOR_RULES = {
    "rth_breaks": [
        "📉 30-min close below RTH entry anchor: price may retrace above anchor line but will fall below again shortly after",
        "🚀 Don't chase the bounce: prepare for the inevitable breakdown", 
        "✅ Wait for confirmation: let the market give you the entry",
    ],
    "extended_hours": [
        "🌙 Extended session weakness + recovery: use recovered anchor as buy signal in RTH",
        "⚡ Extended session anchors carry forward momentum into regular trading hours",
        "📈 Extended bounce of anchors carry forward momentum into regular trading hours", 
        "🌅 Overnight anchor recovery: strong setup for next day strength",
    ],
    "mon_wed_fri": [
        "📅 No touch of high, close, or low anchors on Mon/Wed/Fri = potential sell day later",
        "🎯 Don't trade TO the anchor: let the market give you the entry",
        "⏳ Wait for price action confirmation rather than anticipating touches",
    ],
    "fibonacci_bounce": [
        "🎯 SPX Line Touch + Bounce: when SPX price touches line and bounces, contract follows the same pattern",
        "📐 0.786 Fibonacci Entry: contract retraces to 0.786 fib level (low to high of bounce) = major algo entry point",
        "⏰ Next Hour Candle: the 0.786 retracement typically occurs in the NEXT hour candle, not the same one", 
        "🎪 High Probability: algos consistently enter at 0.786 level for profitable runs",
        "✨ Setup Requirements: clear bounce off SPX line + identifiable low-to-high swing for fib calculation",
    ],
}

CONTRACT_STRATEGIES = {
    "tuesday_play": [
        "🔍 Identify two overnight option low points that rise $400-$500",
        "📈 Use them to set Tuesday contract slope",
        "⚡ Tuesday contract setups often provide best mid-week momentum",
    ],
    "thursday_play": [
        "💰 If Wednesday's low premium was cheap: Thursday low ≈ Wed low (buy-day)",
        "📉 If Wednesday stayed pricey: Thursday likely a put-day (avoid longs)",
        "📊 Wednesday pricing telegraphs Thursday direction",
    ],
}

TIME_RULES = {
    "market_sessions": [
        "🌅 9:30-10:00 AM: initial range, avoid FOMO entries",
        "💼 10:30-11:30 AM: institutional flow window, best entries",
        "🚀 2:00-3:00 PM: final push time, momentum plays", 
        "⚠️ 3:30+ PM: scalps only, avoid new positions",
    ],
    "volume_patterns": [
        "📊 Entry volume > 20-day average: strong conviction signal",
        "📉 Declining volume on bounces: fade the move",
        "💥 Volume spike + anchor break: high probability setup",
    ],
    "multi_timeframe": [
        "🎯 5-min + 15-min + 1-hour all pointing same direction = high conviction",
        "⚖️ Conflicting timeframes = wait for resolution",
        "🏆 Daily anchor + intraday setup = strongest edge",
    ],
}

RISK_RULES = {
    "position_sizing": [
        "🛡️ Never risk more than 2% per trade: consistency beats home runs",
        "📊 Scale into positions: 1/3 initial, 1/3 confirmation, 1/3 momentum",
        "📅 Reduce size on Fridays: weekend risk isn't worth it",
    ],
    "stop_strategy": [
        "🚨 Hard stops at -15% for options: no exceptions",
        "📈 Trailing stops after +25%: protect profits aggressively", 
        "⏰ Time stops at 3:45 PM: avoid close volatility",
    ],
    "market_context": [
        "📊 VIX above 25: reduce position sizes by 50%",
        "📈 Major earnings week: avoid unrelated tickers",
        "📰 FOMC/CPI days: trade post-announcement only (10:30+ AM)",
    ],
    "psychological": [
        "😤 3 losses in a row: step away for 1 hour minimum",
        "🎉 Big win euphoria: reduce next position size by 50%",
        "😡 Revenge trading: automatic day-end (no exceptions)",
    ],
    "performance_targets": [
        "🎯 Win rate target: 55%+",
        "💰 Risk/reward minimum: 1:1.5", 
        "📊 Weekly P&L cap: stop after +20% or -10% weekly moves",
    ],
}

# ===== CSS / JS (unchanged content) =====
CSS_DESIGN_SYSTEM = """<style> ... (omitted for brevity – keep your original CSS_DESIGN_SYSTEM contents) ...</style>"""
CSS_COMPONENTS = """<style> ... (omitted for brevity – keep your original CSS_COMPONENTS contents) ...</style>"""
DARK_MODE_SCRIPT = """<script> ... (omitted for brevity – keep your original DARK_MODE_SCRIPT contents) ...</script>"""

# ===== TIME & UTILS =====
RTH_START, RTH_END = time(8, 30), time(15, 30)

def spx_blocks_between(t1: datetime, t2: datetime) -> int:
    if not isinstance(t1, datetime) or not isinstance(t2, datetime):
        raise ValueError("Both arguments must be datetime objects")
    if t2 < t1:
        t1, t2 = t2, t1
    blocks = 0
    current = t1
    while current < t2:
        if current.hour != 16:  # exclude 16:00 maintenance
            blocks += 1
        current += timedelta(minutes=30)
    return blocks

def make_time_slots(start: time, end: time, step_minutes: int = 30) -> List[str]:
    if not isinstance(start, time) or not isinstance(end, time):
        raise ValueError("Start and end must be time objects")
    if step_minutes <= 0:
        raise ValueError("Step minutes must be positive")
    slots = []
    current = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    if end_dt < current:
        end_dt += timedelta(days=1)
    while current <= end_dt:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=step_minutes)
    return slots

def round_to_tick(value: float, tick: float = TICK) -> float:
    if tick <= 0:
        return float(value)
    rounded = round(value / tick) * tick
    return round(rounded, 4)

def project_price(anchor_price: float, slope_per_block: float, blocks: int) -> float:
    if not isinstance(anchor_price, (int, float)) or anchor_price <= 0:
        raise ValueError("Anchor price must be a positive number")
    if not isinstance(blocks, int) or blocks < 0:
        raise ValueError("Blocks must be a non-negative integer")
    projected = anchor_price + (slope_per_block * blocks)
    return round_to_tick(projected)

SPX_SLOTS = make_time_slots(RTH_START, RTH_END)
EXTENDED_SLOTS = make_time_slots(time(7, 30), RTH_END)

def is_trading_hours(dt: datetime) -> bool:
    return RTH_START <= dt.time() <= RTH_END

def is_maintenance_hour(dt: datetime) -> bool:
    return dt.hour == 16

def get_next_trading_slot(current_time: time) -> Optional[str]:
    current_str = current_time.strftime("%H:%M")
    for slot in SPX_SLOTS:
        if slot > current_str:
            return slot
    return None

def calculate_trading_minutes_remaining(current_time: time) -> int:
    if current_time >= RTH_END:
        return 0
    current_dt = datetime.combine(date.today(), current_time)
    end_dt = datetime.combine(date.today(), RTH_END)
    return int((end_dt - current_dt).total_seconds() / 60)

# ===== STREAMLIT PAGE CONFIG =====
st.set_page_config(
    page_title=f"{APP_NAME} — Enterprise SPX Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/your-repo/marketlens-pro',
        'Report a bug': 'https://github.com/your-repo/marketlens-pro/issues',
        'About': f"{APP_NAME} v{VERSION} - Professional SPX Forecasting Platform"
    }
)

# ===== STATE / VALIDATION / ERRORS / PERF =====
class MarketLensState:
    def __init__(self): self.initialize_state()
    def initialize_state(self):
        defaults = {
            'initialized': True, 'theme': 'light', 'print_mode': False,
            'anchors_locked': False, 'forecasts_generated': False,
            'contract': {'anchor_time': None, 'anchor_price': None, 'slope': None, 'label': 'Manual'},
            'sidebar_expanded': True, 'auto_refresh': False, 'refresh_interval': 60,
            'risk_alerts_enabled': True, 'sound_notifications': False, 'advanced_charts': True,
            'default_tolerance': 0.50, 'preferred_timeframe': '30min', 'chart_theme': 'professional',
            'session_start_time': datetime.now(), 'page_loads': 0, 'last_data_refresh': None,
        }
        for k,v in defaults.items():
            if k not in st.session_state: st.session_state[k] = v
        st.session_state.page_loads += 1
    def reset_forecasts(self):
        st.session_state.forecasts_generated = False
        st.session_state.anchors_locked = False
    def save_user_preferences(self):
        st.session_state.user_preferences = {
            'theme': st.session_state.theme,
            'default_tolerance': st.session_state.default_tolerance,
            'auto_refresh': st.session_state.auto_refresh,
            'advanced_charts': st.session_state.advanced_charts,
        }

class DataValidator:
    @staticmethod
    def validate_price(price: float, min_price: float = 0.01, max_price: float = 10000.0) -> bool:
        try:
            price = float(price); return min_price <= price <= max_price
        except (ValueError, TypeError): return False
    @staticmethod
    def validate_time_input(time_input: time) -> bool:
        if not isinstance(time_input, time): return False
        return time(6,0) <= time_input <= time(20,0)
    @staticmethod
    def validate_date_input(date_input: date) -> Tuple[bool, str]:
        if not isinstance(date_input, date): return False, "Invalid date format"
        today = date.today()
        if date_input < today - timedelta(days=7): return False, "Date cannot be more than 7 days in the past"
        if date_input > today + timedelta(days=30): return False, "Date cannot be more than 30 days in the future"
        if date_input.weekday() >= 5: return False, "Selected date falls on a weekend"
        return True, "Valid date"
    @staticmethod
    def validate_slope(slope: float) -> Tuple[bool, str]:
        try:
            slope = float(slope)
            if abs(slope) > 10.0: return False, "Slope too extreme (max ±10.0)"
            if slope == 0: return False, "Slope cannot be zero"
            return True, "Valid slope"
        except (ValueError, TypeError): return False, "Invalid slope format"

class MarketLensError(Exception): pass
class DataFetchError(MarketLensError): pass
class ValidationError(MarketLensError): pass
class CalculationError(MarketLensError): pass

def safe_execute(func, *args, default=None, error_msg="Operation failed", **kwargs):
    try: return func(*args, **kwargs)
    except Exception as e:
        logging.error(f"{error_msg}: {str(e)}")
        if default is not None: return default
        raise MarketLensError(f"{error_msg}: {str(e)}")

class PerformanceMonitor:
    def __init__(self): self.start_time = datetime.now(); self.operation_times = {}
    def start_operation(self, name: str): self.operation_times[name] = datetime.now()
    def end_operation(self, name: str) -> float:
        if name in self.operation_times:
            d = (datetime.now()-self.operation_times[name]).total_seconds()
            del self.operation_times[name]; return d
        return 0.0
    def get_session_duration(self) -> float: return (datetime.now()-self.start_time).total_seconds()

# Initialize systems
state_manager = MarketLensState()
if 'performance_monitor' not in st.session_state: st.session_state.performance_monitor = PerformanceMonitor()
validator = DataValidator()

# ===== APPLY DESIGN SYSTEM =====
st.markdown(CSS_DESIGN_SYSTEM, unsafe_allow_html=True)
st.markdown(CSS_COMPONENTS, unsafe_allow_html=True)
st.markdown(DARK_MODE_SCRIPT, unsafe_allow_html=True)

# ===== DATA FETCHING =====
@st.cache_data(ttl=60, show_spinner=False)
def fetch_spx_live_data():
    try:
        st.session_state.performance_monitor.start_operation('fetch_spx_data')
        ticker = yf.Ticker("^GSPC")
        intraday = ticker.history(period="1d", interval="1m")
        daily = ticker.history(period="6d", interval="1d")
        if intraday is None or intraday.empty or daily is None or daily.empty or len(daily) < 1:
            return {"status":"error","message":"No data available"}
        last_bar = intraday.iloc[-1]
        current_price = float(last_bar["Close"])
        today_high = float(daily.iloc[-1]["High"])
        today_low = float(daily.iloc[-1]["Low"])
        prev_close = float(daily.iloc[-2]["Close"]) if len(daily) >= 2 else current_price
        price_change = current_price - prev_close
        percent_change = (price_change / prev_close * 100) if prev_close else 0.0
        volume = float(last_bar["Volume"]) if "Volume" in last_bar else 0
        volatility = float(intraday["Close"].tail(20).std()) if len(intraday) >= 20 else 0.0
        is_market_open = RTH_START <= datetime.now().time() <= RTH_END
        fetch_time = st.session_state.performance_monitor.end_operation('fetch_spx_data')
        return {
            "status":"success","price":round(current_price,2),"change":round(price_change,2),
            "change_percent":round(percent_change,2),"today_high":round(today_high,2),
            "today_low":round(today_low,2),"volume":int(volume),"volatility":round(volatility,2),
            "is_market_open":is_market_open,"last_update":datetime.now(),"fetch_time":round(fetch_time,3)
        }
    except Exception as e:
        return {"status":"error","message":f"Data fetch failed: {str(e)}","last_update":datetime.now()}

@st.cache_data(ttl=300, show_spinner=False)
def get_previous_day_anchors(forecast_date: date):
    try:
        df = yf.Ticker("^GSPC").history(period="1mo", interval="1d")
        if df is None or df.empty: return None
        daily = df.reset_index()
        if "Date" not in daily.columns:
            daily.rename(columns={daily.columns[0]:"Date"}, inplace=True)
        daily["DateOnly"] = daily["Date"].dt.tz_localize(None).dt.date
        previous_days = daily.loc[daily["DateOnly"] < forecast_date]
        if previous_days.empty: return None
        prev_row = previous_days.iloc[-1]
        return {
            "date": prev_row["DateOnly"],
            "high": round(float(prev_row["High"]), 2),
            "close": round(float(prev_row["Close"]), 2),
            "low": round(float(prev_row["Low"]), 2),
            "volume": int(prev_row["Volume"]) if "Volume" in prev_row else 0
        }
    except Exception as e:
        st.error(f"⚠️ Could not fetch previous day data: {str(e)}")
        return None

@st.cache_data(ttl=120, show_spinner=False)
def fetch_intraday_data(target_date: date) -> pd.DataFrame:
    try:
        ticker = yf.Ticker("^GSPC")
        start_date = target_date - timedelta(days=1)
        end_date = target_date + timedelta(days=1)
        df = ticker.history(start=start_date, end=end_date, interval="1m")
        if df is None or df.empty: return pd.DataFrame()
        df = df.reset_index()
        datetime_col = "Datetime" if "Datetime" in df.columns else df.columns[0]
        df.rename(columns={datetime_col: "dt"}, inplace=True)
        df["Time"] = df["dt"].dt.tz_localize(None).dt.strftime("%H:%M")
        df["Date"] = df["dt"].dt.tz_localize(None).dt.date
        df = df[df["Date"] == target_date].copy()
        return df
    except Exception as e:
        st.error(f"⚠️ Could not fetch intraday data: {str(e)}")
        return pd.DataFrame()

def convert_to_30min_bars(df_1min: pd.DataFrame) -> pd.DataFrame:
    if df_1min.empty: return pd.DataFrame()
    try:
        df = df_1min.copy()
        df = df.set_index(pd.to_datetime(df["dt"]).dt.tz_localize(None)).sort_index()
        ohlc = df[["Open","High","Low","Close","Volume"]].resample(
            "30min", label="right", closed="right"
        ).agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
        ohlc = ohlc.reset_index().rename(columns={"index":"dt","Datetime":"dt"})
        ohlc["Time"] = ohlc["dt"].dt.strftime("%H:%M")
        ohlc = ohlc[(ohlc["Time"] >= "08:30") & (ohlc["Time"] <= "15:30")].copy()
        ohlc["TS"] = pd.to_datetime(BASELINE_DATE_STR + " " + ohlc["Time"])
        return ohlc[["Time","Open","High","Low","Close","Volume","TS"]]
    except Exception as e:
        st.error(f"⚠️ Could not convert to 30-min bars: {str(e)}")
        return pd.DataFrame()

# Thin wrappers used later (missing in your file)
def fetch_spx_intraday_1m(target_date: date) -> pd.DataFrame:
    return fetch_intraday_data(target_date)

def to_30m(df_1m: pd.DataFrame) -> pd.DataFrame:
    return convert_to_30min_bars(df_1m)

# ===== HERO / LIVE STRIP =====
def render_hero_section():
    st.markdown(
        f"""
        <div class="hero-container animate-fade-in">
            <div class="hero-content">
                <div class="brand-logo">{APP_NAME}</div>
                <div class="brand-tagline">{TAGLINE}</div>
                <div class="brand-meta">v{VERSION} • {COMPANY}</div>
            </div>
        </div>
        """, unsafe_allow_html=True
    )

def render_live_price_strip():
    market_data = fetch_spx_live_data()
    if market_data["status"] == "success":
        change_color = COLORS["success"] if market_data["change"] >= 0 else COLORS["error"]
        change_symbol = "+" if market_data["change"] >= 0 else ""
        market_status = "🟢 OPEN" if market_data["is_market_open"] else "🔴 CLOSED"
        live_price_html = f"""
        <div class="live-price-container animate-slide-up">
            <div class="live-indicator"><div class="live-dot"></div><span>SPX LIVE</span></div>
            <div class="price-main">${market_data['price']:,.2f}</div>
            <div class="price-change" style="color:{change_color};">
                {change_symbol}{market_data['change']:,.2f} ({change_symbol}{market_data['change_percent']:.2f}%)
            </div>
            <div class="price-meta">H: ${market_data['today_high']:,.2f} • L: ${market_data['today_low']:,.2f}</div>
            <div class="price-meta">{market_status} • Vol: {market_data['volume']:,}</div>
            <div class="price-meta">Updated: {market_data['last_update'].strftime('%H:%M:%S')} • Fetch: {market_data['fetch_time']}s</div>
        </div>
        """
        st.markdown(live_price_html, unsafe_allow_html=True)
    else:
        st.markdown(
            f"""
            <div class="live-price-container">
                <div class="live-indicator"><div style="width:8px;height:8px;background:#666;border-radius:50%;"></div><span>SPX DATA</span></div>
                <div style="color:#999;font-size:var(--text-lg);">⚠️ {market_data.get('message','Data unavailable')}</div>
            </div>
            """, unsafe_allow_html=True
        )

def render_metrics_dashboard(forecast_date: date):
    anchors = get_previous_day_anchors(forecast_date)
    if anchors:
        st.markdown('<div class="metrics-grid animate-slide-up">', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="metric-tile">
                <div class="metric-icon">{ICONS["high"]}</div>
                <div class="metric-value" style="color:{COLORS['success']};">${anchors['high']:,.2f}</div>
                <div class="metric-label">Previous Day High</div>
                <div class="metric-change positive">Session: {anchors['date']}</div>
            </div>
            """, unsafe_allow_html=True
        )
        st.markdown(
            f"""
            <div class="metric-tile">
                <div class="metric-icon">{ICONS["close"]}</div>
                <div class="metric-value" style="color:{COLORS['primary']};">${anchors['close']:,.2f}</div>
                <div class="metric-label">Previous Day Close</div>
                <div class="metric-change">Session: {anchors['date']}</div>
            </div>
            """, unsafe_allow_html=True
        )
        st.markdown(
            f"""
            <div class="metric-tile">
                <div class="metric-icon">{ICONS["low"]}</div>
                <div class="metric-value" style="color:{COLORS['error']};">${anchors['low']:,.2f}</div>
                <div class="metric-label">Previous Day Low</div>
                <div class="metric-change negative">Session: {anchors['date']}</div>
            </div>
            """, unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
        return anchors
    else:
        st.markdown(
            """
            <div class="premium-card">
                <div style="text-align:center;color:var(--warning);padding:var(--space-4);">
                    ⚠️ Could not determine previous trading day anchors for the selected forecast date.
                </div>
            </div>
            """, unsafe_allow_html=True
        )
        return None

# ===== SIDEBAR =====
def render_enhanced_sidebar():
    with st.sidebar:
        st.markdown('<div class="section-header">🎨 Appearance</div>', unsafe_allow_html=True)
        current_theme = st.session_state.get('theme','light')
        theme_options = ['light','dark']
        new_theme = st.radio("Theme Mode", options=theme_options,
                             index=theme_options.index(current_theme),
                             format_func=lambda x: "☀️ Light Mode" if x=='light' else "🌙 Dark Mode",
                             horizontal=True)
        if new_theme != current_theme:
            st.session_state.theme = new_theme
            st.markdown(f"<script>window.setMarketLensTheme('{new_theme}')</script>", unsafe_allow_html=True)
            st.rerun()

        st.session_state.print_mode = st.toggle("📄 Print-friendly mode",
                                                value=st.session_state.get('print_mode', False),
                                                help="Optimize layout for printing")
        st.divider()

        st.markdown('<div class="section-header">📅 Forecast Setup</div>', unsafe_allow_html=True)
        forecast_date = st.date_input("Target Trading Session", value=date.today() + timedelta(days=1),
                                      help="Select the date you want to forecast")
        is_valid, validation_msg = validator.validate_date_input(forecast_date)
        if not is_valid: st.warning(f"⚠️ {validation_msg}")
        day_names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        st.info(f"📆 **{day_names[forecast_date.weekday()]}** session • Anchors reference the previous trading day")
        st.divider()

        st.markdown('<div class="section-header">🎯 Entry Detection</div>', unsafe_allow_html=True)
        tolerance = st.slider("Touch Tolerance ($)", 0.00, 5.00,
                              value=st.session_state.get('default_tolerance', 0.50),
                              step=0.05, help="Price tolerance for line touches")
        rule_type = st.radio("Detection Rule",
                             options=["Close above Exit / below Entry", "Near line (±tol) only"],
                             index=0, help="Choose how strict the entry detection should be")
        st.divider()

        if 'performance_monitor' in st.session_state:
            monitor = st.session_state.performance_monitor
            session_time = monitor.get_session_duration()
            st.markdown('<div class="section-header">📊 Session Stats</div>', unsafe_allow_html=True)
            c1,c2 = st.columns(2)
            with c1: st.metric("Page Loads", st.session_state.get('page_loads', 0))
            with c2: st.metric("Session Time", f"{session_time/60:.1f}m")

        return forecast_date, tolerance, rule_type

# ===== MAIN INTERFACE RENDERING =====
render_hero_section()
render_live_price_strip()
forecast_date, tolerance, rule_requirement = render_enhanced_sidebar()
previous_anchors = render_metrics_dashboard(forecast_date)

# ===== ANCHOR INPUTS / LOCKING =====
def create_single_anchor_input(anchor_type: str, default_price: float, default_time: time, 
                              icon: str, color: str, description: str):
    st.markdown(
        f"""
        <div class="premium-card animate-slide-up">
            <div class="subsection-header">
                <span style="font-size:1.5rem;">{icon}</span>
                <span style="color:{color};font-weight:700;font-size:var(--text-2xl);">{anchor_type} Anchor</span>
            </div>
            <div style="color:var(--text-tertiary);margin-bottom:var(--space-4);font-size:var(--text-sm);">
                {description}
            </div>
        """, unsafe_allow_html=True
    )
    col1, col2 = st.columns([3,2])
    with col1:
        price = st.number_input("Price ($)", value=float(default_price), min_value=0.0, max_value=10000.0,
                                step=0.1, format="%.2f", key=f"anchor_{anchor_type.lower()}_price_input",
                                help=f"Enter the {anchor_type.lower()} price from the previous trading day")
        is_valid_price = True
        if price <= 0:
            st.error("⚠️ Price must be greater than 0"); is_valid_price = False
        elif price > 10000:
            st.error("⚠️ Price seems unreasonably high"); is_valid_price = False
        elif price < 1000:
            st.warning("⚠️ Price seems low for SPX - please verify")
    with col2:
        anchor_time = st.time_input("Time", value=default_time, step=300,
                                    key=f"anchor_{anchor_type.lower()}_time_input",
                                    help=f"Time when the {anchor_type.lower()} occurred")
        is_valid_time = True
        if not (time(6,0) <= anchor_time <= time(20,0)):
            st.warning("⚠️ Time outside extended hours (06:00-20:00)"); is_valid_time = False
    if is_valid_price and is_valid_time:
        st.markdown(
            f"""
            <div style="background:rgba(52,199,89,0.1);color:#34C759;padding:var(--space-2) var(--space-3);
                 border-radius:var(--radius-md);font-size:var(--text-sm);font-weight:500;margin-top:var(--space-2);">
                ✅ {anchor_type} anchor: ${price:.2f} at {anchor_time.strftime('%H:%M')}
            </div>
            """, unsafe_allow_html=True
        )
    st.markdown('</div>', unsafe_allow_html=True)
    return price, anchor_time, (is_valid_price and is_valid_time)

def render_anchor_header(forecast_date: date, previous_anchors: dict = None):
    st.markdown("""<div class="section-header animate-fade-in">🔧 SPX Anchor Configuration</div>""",
                unsafe_allow_html=True)
    st.markdown(
        f"""
        <div style="color:var(--text-secondary);margin-bottom:var(--space-6);font-size:var(--text-lg);">
            Configure your SPX anchors from the previous trading day. These will be used to generate
            precise entry and exit projections for <strong>{forecast_date.strftime('%A, %B %d, %Y')}</strong>.
        </div>
        """, unsafe_allow_html=True
    )
    if previous_anchors:
        prev_date = previous_anchors.get('date','Unknown')
        st.markdown(
            f"""
            <div class="glass-card">
                <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-3);">
                    <span style="font-size:1.2rem;">📅</span>
                    <span style="font-weight:600;">Auto-populated from {prev_date}</span>
                </div>
                <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                    Values below are automatically loaded from the previous trading day.
                    You can modify them if needed before generating forecasts.
                </div>
            </div>
            """, unsafe_allow_html=True
        )
        return {'high_default': previous_anchors.get('high', 6185.80),
                'close_default': previous_anchors.get('close', 6170.20),
                'low_default': previous_anchors.get('low', 6130.40)}
    else:
        st.markdown(
            """
            <div class="premium-card" style="background:rgba(255,149,0,0.1);border-color:#FF9500;">
                <div style="display:flex;align-items:center;gap:var(--space-3);">
                    <span style="font-size:1.2rem;">⚠️</span>
                    <span style="color:#FF9500;font-weight:600;">Manual Input Required</span>
                </div>
                <div style="color:var(--text-secondary);margin-top:var(--space-2);">
                    Previous day data not available. Please enter anchors manually.
                </div>
            </div>
            """, unsafe_allow_html=True
        )
        return {'high_default': 6185.80,'close_default': 6170.20,'low_default': 6130.40}

def render_basic_anchor_inputs(defaults: dict):
    col1,col2,col3 = st.columns(3)
    with col1:
        high_price, high_time, high_valid = create_single_anchor_input(
            "HIGH", defaults['high_default'], time(11,30), "📈", "#34C759",
            "Previous day's highest price point - typically your strongest resistance level.")
    with col2:
        close_price, close_time, close_valid = create_single_anchor_input(
            "CLOSE", defaults['close_default'], time(15,0), "⚡", "#007AFF",
            "Previous day's closing price - the market's final consensus value.")
    with col3:
        low_price, low_time, low_valid = create_single_anchor_input(
            "LOW", defaults['low_default'], time(13,30), "📉", "#FF3B30",
            "Previous day's lowest price point - typically your strongest support level.")
    return {
        'high_price': high_price,'high_time': high_time,'high_valid': high_valid,
        'close_price': close_price,'close_time': close_time,'close_valid': close_valid,
        'low_price': low_price,'low_time': low_time,'low_valid': low_valid,
        'all_valid': high_valid and close_valid and low_valid
    }

def render_validation_status(anchor_data: dict):
    all_valid = anchor_data['all_valid']
    if all_valid:
        status_html = """
        <div class="glass-card" style="background:rgba(52,199,89,0.1);border-color:#34C759;">
            <div style="display:flex;align-items:center;gap:var(--space-3);">
                <span style="font-size:1.5rem;">✅</span>
                <div>
                    <div style="font-weight:700;color:#34C759;">Anchors Valid</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                        All three anchors are properly configured and ready to lock
                    </div>
                </div>
            </div>
        </div>"""
    else:
        invalid_count = sum([not anchor_data['high_valid'], not anchor_data['close_valid'], not anchor_data['low_valid']])
        status_html = f"""
        <div class="glass-card" style="background:rgba(255,149,0,0.1);border-color:#FF9500;">
            <div style="display:flex;align-items:center;gap:var(--space-3);">
                <span style="font-size:1.5rem;">⚠️</span>
                <div>
                    <div style="font-weight:700;color:#FF9500;">Validation Issues</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                        {invalid_count} anchor(s) need attention before locking
                    </div>
                </div>
            </div>
        </div>"""
    st.markdown(status_html, unsafe_allow_html=True)
    return all_valid

def render_lock_unlock_controls(anchor_data: dict):
    is_locked = st.session_state.get('anchors_locked', False)
    all_valid = anchor_data['all_valid']
    col_action, col_generate = st.columns([1,1])
    with col_action:
        if not is_locked and all_valid:
            if st.button("🔒 Lock Anchors", use_container_width=True, type="primary"):
                st.session_state.anchors_locked = True
                st.session_state.locked_anchor_data = {
                    'high': {'price': anchor_data['high_price'], 'time': anchor_data['high_time']},
                    'close': {'price': anchor_data['close_price'], 'time': anchor_data['close_time']},
                    'low': {'price': anchor_data['low_price'], 'time': anchor_data['low_time']},
                    'locked_at': datetime.now()
                }
                st.success("🎯 Anchors locked successfully!"); st.rerun()
        elif is_locked:
            if st.button("🔓 Unlock Anchors", use_container_width=True):
                st.session_state.anchors_locked = False
                st.session_state.locked_anchor_data = None
                st.info("🔄 Anchors unlocked for editing"); st.rerun()
        else:
            st.button("🔒 Fix Validation Issues", use_container_width=True, disabled=True)
    with col_generate:
        can_generate = is_locked and all_valid
        if can_generate:
            if st.button("🚀 Generate Forecast", use_container_width=True, type="primary"):
                st.session_state.forecasts_generated = True
                st.success("📊 Forecast generation initiated!"); st.rerun()
        else:
            reason = "Lock Anchors First" if not is_locked else "Fix Validation Issues"
            st.button(f"🚀 {reason}", use_container_width=True, disabled=True)
    return is_locked, (is_locked and all_valid)

def render_locked_anchor_summary():
    if not st.session_state.get('anchors_locked', False): return None
    if 'locked_anchor_data' not in st.session_state: return None
    locked_data = st.session_state.locked_anchor_data
    locked_time = locked_data['locked_at'].strftime('%H:%M:%S')
    st.markdown(
        f"""
        <div class="premium-card" style="background:rgba(0,122,255,0.05);border-color:#007AFF;">
            <div style="display:flex;align-items:center;gap:var(--space-3);margin-bottom:var(--space-4);">
                <span style="font-size:1.5rem;">🔒</span>
                <div>
                    <div style="font-weight:700;color:#007AFF;">Anchors Locked & Ready</div>
                    <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                        Locked at {locked_time} • Configuration protected from changes
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True
    )
    col1,col2,col3 = st.columns(3)
    with col1:
        st.markdown(f"""
            <div style="text-align:center;padding:var(--space-3);background:rgba(52,199,89,0.05);border-radius:var(--radius-md);">
                <div style="color:#34C759;font-weight:700;font-size:var(--text-xl);">${locked_data['high']['price']:.2f}</div>
                <div style="color:var(--text-tertiary);font-size:var(--text-sm);margin-top:var(--space-1);">
                    HIGH @ {locked_data['high']['time'].strftime('%H:%M')}
                </div>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div style="text-align:center;padding:var(--space-3);background:rgba(0,122,255,0.05);border-radius:var(--radius-md);">
                <div style="color:#007AFF;font-weight:700;font-size:var(--text-xl);">${locked_data['close']['price']:.2f}</div>
                <div style="color:var(--text-tertiary);font-size:var(--text-sm);margin-top:var(--space-1);">
                    CLOSE @ {locked_data['close']['time'].strftime('%H:%M')}
                </div>
            </div>
        """, unsafe_allow_html=True)
    with col3:
        low_info = (locked_data or {}).get("low", {})
        price = low_info.get("price"); tval = low_info.get("time")
        price_str = f"{price:.2f}" if isinstance(price,(int,float)) else "--"
        time_str = tval.strftime("%H:%M") if hasattr(tval,"strftime") else (str(tval) if tval else "--")
        st.markdown(f"""
            <div style="text-align:center;padding:var(--space-3);background:rgba(255,59,48,0.05);border-radius:var(--radius-md);">
                <div style="color:#FF3B30;font-weight:700;font-size:var(--text-xl);">&#36;{price_str}</div>
                <div style="color:var(--text-tertiary);font-size:var(--text-sm);margin-top:var(--space-1);">
                    LOW @ {time_str}
                </div>
            </div>
        """, unsafe_allow_html=True)

def handle_anchor_management(anchor_data: dict):
    st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
    col_status, col_controls = st.columns([2,2])
    with col_status: all_valid = render_validation_status(anchor_data)
    with col_controls: is_locked, can_generate = render_lock_unlock_controls(anchor_data)
    if is_locked:
        st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
        render_locked_anchor_summary()
    return {'is_locked': is_locked, 'can_generate': can_generate, 'all_valid': all_valid}

def get_anchor_configuration():
    if st.session_state.get('anchors_locked', False) and 'locked_anchor_data' in st.session_state:
        locked_data = st.session_state.locked_anchor_data
        return {
            'high_price': locked_data['high']['price'],'high_time': locked_data['high']['time'],
            'close_price': locked_data['close']['price'],'close_time': locked_data['close']['time'],
            'low_price': locked_data['low']['price'],'low_time': locked_data['low']['time'],
            'is_locked': True, 'locked_at': locked_data['locked_at']
        }
    else:
        return {'is_locked': False, 'error': 'Anchors must be locked before generating forecasts'}

# ===== FAN GENERATION =====
def build_enhanced_fan_dataframe(anchor_type: str, anchor_price: float, anchor_time: time, forecast_date: date) -> pd.DataFrame:
    try:
        anchor_datetime = datetime.combine(forecast_date - timedelta(days=1), anchor_time)
        rows = []
        for time_slot in SPX_SLOTS:
            try:
                hour, minute = map(int, time_slot.split(":"))
                target_datetime = datetime.combine(forecast_date, time(hour, minute))
                blocks = spx_blocks_between(anchor_datetime, target_datetime)
                entry_price = project_price(anchor_price, SPX_SLOPES_DOWN[anchor_type], blocks)
                exit_price  = project_price(anchor_price, SPX_SLOPES_UP[anchor_type],   blocks)
                rows.append({
                    'Time': time_slot,'Entry': round(entry_price,2),'Exit': round(exit_price,2),
                    'Blocks': blocks,'Anchor_Price': anchor_price,'Anchor_Type': anchor_type,
                    'Spread': round(exit_price - entry_price, 2)
                })
            except Exception:
                continue
        fan_df = pd.DataFrame(rows)
        if not fan_df.empty:
            fan_df['TS'] = pd.to_datetime(BASELINE_DATE_STR + " " + fan_df['Time'])
            fan_df.attrs.update({
                'anchor_type': anchor_type,'anchor_price': anchor_price,'anchor_time': anchor_time,
                'forecast_date': forecast_date,'generated_at': datetime.now()
            })
        return fan_df
    except Exception as e:
        st.error(f"⚠️ Error generating {anchor_type} fan data: {str(e)}"); return pd.DataFrame()

def generate_all_fan_data(anchor_config: dict, forecast_date: date) -> dict:
    if not anchor_config.get('is_locked', False):
        st.error("🔒 Anchors must be locked before generating fan data"); return {}
    progress_bar = st.progress(0); status_text = st.empty()
    fan = {}
    status_text.text("🔄 Generating HIGH anchor fan..."); progress_bar.progress(10)
    fan['high'] = build_enhanced_fan_dataframe('HIGH', anchor_config['high_price'], anchor_config['high_time'], forecast_date)
    progress_bar.progress(35)
    status_text.text("🔄 Generating CLOSE anchor fan..."); progress_bar.progress(40)
    fan['close'] = build_enhanced_fan_dataframe('CLOSE', anchor_config['close_price'], anchor_config['close_time'], forecast_date)
    progress_bar.progress(70)
    status_text.text("🔄 Generating LOW anchor fan..."); progress_bar.progress(75)
    fan['low'] = build_enhanced_fan_dataframe('LOW', anchor_config['low_price'], anchor_config['low_time'], forecast_date)
    progress_bar.progress(100)
    total_rows = sum(len(df) for df in fan.values() if isinstance(df,pd.DataFrame) and not df.empty)
    if total_rows > 0:
        status_text.markdown(f"""<div style="color:#34C759;font-weight:600;">✅ Generated {total_rows} forecast data points across all anchors</div>""",
                             unsafe_allow_html=True)
        st.session_state.fan_data = fan
        st.session_state.fan_data_generated_at = datetime.now()
        st.session_state.fan_forecast_date = forecast_date
    else:
        status_text.markdown("""<div style="color:#FF3B30;font-weight:600;">❌ Failed to generate fan data - please check anchor configuration</div>""",
                             unsafe_allow_html=True)
    return fan

def display_fan_data_tables(fan_datasets: dict):
    if not fan_datasets: return
    st.markdown("""<div class="section-header">📋 Fan Forecast Tables</div>""", unsafe_allow_html=True)
    tab_high, tab_close, tab_low = st.tabs(["📈 HIGH Fan", "⚡ CLOSE Fan", "📉 LOW Fan"])
    def show_tab(df, color_name, label):
        if df is None or df.empty: st.error(f"❌ {label} fan data not available"); return
        st.markdown(
            f"""
            <div class="premium-card" style="margin-bottom:var(--space-4);">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <span style="font-weight:700;color:{COLORS[color_name]};">{label} Anchor Fan</span>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                            Anchor: ${df.attrs.get('anchor_price', 0):.2f} @ {df.attrs.get('anchor_time', time()).strftime('%H:%M')}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:600;">{len(df)} time slots</div>
                        <div style="color:var(--text-tertiary);font-size:var(--text-sm);">
                            Generated: {df.attrs.get('generated_at', datetime.now()).strftime('%H:%M:%S')}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True
        )
        display_cols = ['Time','Entry','Exit','Blocks','Spread']
        st.dataframe(df[display_cols], use_container_width=True, hide_index=True,
                     column_config={'Entry': st.column_config.NumberColumn('Entry ($)', format="%.2f"),
                                    'Exit': st.column_config.NumberColumn('Exit ($)', format="%.2f"),
                                    'Spread': st.column_config.NumberColumn('Spread ($)', format="%.2f")})
    with tab_high:  show_tab(fan_datasets.get('high'), 'success', 'HIGH')
    with tab_close: show_tab(fan_datasets.get('close'), 'primary', 'CLOSE')
    with tab_low:   show_tab(fan_datasets.get('low'), 'error', 'LOW')

# ===== CHARTS =====
def create_premium_plotly_theme():
    current = st.session_state.get('theme','light')
    if current == 'dark':
        return {'bg_color':'#0F141B','paper_color':'#1C1C1E','text_color':'#FFFFFF',
                'grid_color':'rgba(255,255,255,0.1)','zero_line_color':'rgba(255,255,255,0.2)',
                'font_family':'SF Pro Display, Inter, -apple-system, sans-serif'}
    else:
        return {'bg_color':'#F2F2F7','paper_color':'#FFFFFF','text_color':'#000000',
                'grid_color':'rgba(0,0,0,0.1)','zero_line_color':'rgba(0,0,0,0.2)',
                'font_family':'SF Pro Display, Inter, -apple-system, sans-serif'}

def create_enhanced_fan_chart(fan_df: pd.DataFrame, chart_title: str, intraday_data: pd.DataFrame = None):
    if fan_df.empty: return None
    theme = create_premium_plotly_theme()
    fig = go.Figure()
    anchor_type = fan_df.attrs.get('anchor_type','UNKNOWN')
    if anchor_type == 'HIGH':
        entry_color, exit_color, fill_color = '#FF6B6B', '#34C759', 'rgba(52,199,89,0.08)'
    elif anchor_type == 'CLOSE':
        entry_color, exit_color, fill_color = '#FF9500', '#007AFF', 'rgba(0,122,255,0.08)'
    else: # LOW
        entry_color, exit_color, fill_color = '#FF3B30', '#00D4AA', 'rgba(0,212,170,0.08)'

    fig.add_trace(go.Scatter(x=fan_df['TS'], y=fan_df['Exit'], name='Exit Line (↗️)',
                             line=dict(width=3, color=exit_color, shape='spline', smoothing=0.3),
                             hovertemplate='<b>Exit Signal</b><br>Time: %{x|%H:%M}<br>Price: $%{y:,.2f}<br><extra></extra>'))
    fig.add_trace(go.Scatter(x=fan_df['TS'], y=fan_df['Entry'], name='Entry Line (↘️)',
                             line=dict(width=3, color=entry_color, shape='spline', smoothing=0.3),
                             fill='tonexty', fillcolor=fill_color,
                             hovertemplate='<b>Entry Signal</b><br>Time: %{x|%H:%M}<br>Price: $%{y:,.2f}<br><extra></extra>'))
    if intraday_data is not None and not intraday_data.empty:
        fig.add_trace(go.Scatter(x=intraday_data['TS'], y=intraday_data['Close'], name='SPX (30m close)',
                                 line=dict(width=2, color='#8B5CF6'),
                                 hovertemplate='<b>SPX Price</b><br>Time: %{x|%H:%M}<br>Price: $%{y:,.2f}<br><extra></extra>'))
    fig.update_layout(
        title=dict(text=f'<b>{chart_title}</b>', font=dict(family=theme['font_family'], size=24, color=theme['text_color']), x=0.02),
        height=450, margin=dict(l=20, r=20, t=60, b=20),
        plot_bgcolor=theme['bg_color'], paper_bgcolor=theme['paper_color'],
        font=dict(family=theme['font_family'], color=theme['text_color'], size=12),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0, bgcolor='rgba(0,0,0,0)'),
        dragmode='pan', autosize=True
    )
    fig.update_xaxes(title='<b>Trading Hours (RTH)</b>', showgrid=True, gridwidth=1, gridcolor=theme['grid_color'],
                     zeroline=True, zerolinewidth=1, zerolinecolor=theme['zero_line_color'],
                     tickformat='%H:%M', rangeslider=dict(visible=True, bgcolor=theme['paper_color']))
    fig.update_yaxes(title='<b>SPX Price ($)</b>', showgrid=True, gridwidth=1, gridcolor=theme['grid_color'],
                     zeroline=False, tickformat='$,.0f', side='left')
    return fig

def create_combined_fan_overview(fan_datasets: dict, intraday_data: pd.DataFrame = None):
    if not fan_datasets: return None
    theme = create_premium_plotly_theme()
    fig = go.Figure()
    colors = {'high': {'entry':'#FF6B6B','exit':'#34C759'},
              'close': {'entry':'#FF9500','exit':'#007AFF'},
              'low': {'entry':'#FF3B30','exit':'#00D4AA'}}
    for anchor_name, fan_df in fan_datasets.items():
        if fan_df is None or fan_df.empty: continue
        c = colors.get(anchor_name, colors['close'])
        anchor_type = fan_df.attrs.get('anchor_type', anchor_name.upper())
        fig.add_trace(go.Scatter(x=fan_df['TS'], y=fan_df['Exit'], name=f'{anchor_type} Exit',
                                 line=dict(width=2, color=c['exit'])))
        fig.add_trace(go.Scatter(x=fan_df['TS'], y=fan_df['Entry'], name=f'{anchor_type} Entry',
                                 line=dict(width=2, color=c['entry'], dash='dot')))
    if intraday_data is not None and not intraday_data.empty:
        fig.add_trace(go.Scatter(x=intraday_data['TS'], y=intraday_data['Close'], name='SPX (30m)',
                                 line=dict(width=3, color='#8B5CF6')))
    fig.update_layout(
        title=dict(text='<b>📊 All Anchor Fans Overview</b>', font=dict(family=theme['font_family'], size=24, color=theme['text_color']), x=0.02),
        height=500, margin=dict(l=20, r=20, t=60, b=20),
        plot_bgcolor=theme['bg_color'], paper_bgcolor=theme['paper_color'],
        font=dict(family=theme['font_family'], color=theme['text_color']),
        legend=dict(orientation='v', yanchor='top', y=0.98, xanchor='left', x=1.02, bgcolor='rgba(0,0,0,0)'),
        dragmode='pan'
    )
    fig.update_xaxes(title='<b>Trading Hours</b>', showgrid=True, gridcolor=theme['grid_color'],
                     rangeslider=dict(visible=True))
    fig.update_yaxes(title='<b>SPX Price ($)</b>', showgrid=True, gridcolor=theme['grid_color'], tickformat='$,.0f')
    return fig

def display_premium_charts(fan_datasets: dict, intraday_data: pd.DataFrame = None):
    if not fan_datasets:
        st.error("❌ No fan data available for charting"); return
    st.markdown("""<div class="section-header">📈 Premium Fan Charts</div>""", unsafe_allow_html=True)
    st.markdown("### 📊 Combined Overview")
    overview_chart = create_combined_fan_overview(fan_datasets, intraday_data)
    if overview_chart:
        st.plotly_chart(overview_chart, use_container_width=True,
                        config={'displayModeBar': True, 'displaylogo': False, 'modeBarButtonsToRemove': ['select2d','lasso2d']})
    st.markdown("### 📋 Individual Anchor Charts")
    tab_high, tab_close, tab_low = st.tabs(["📈 HIGH Anchor","⚡ CLOSE Anchor","📉 LOW Anchor"])
    with tab_high:
        df = fan_datasets.get('high')
        if df is not None and not df.empty:
            fig = create_enhanced_fan_chart(df, "HIGH Anchor Fan — Resistance Levels", intraday_data)
            if fig: st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})
        else: st.error("❌ HIGH anchor data not available")
    with tab_close:
        df = fan_datasets.get('close')
        if df is not None and not df.empty:
            fig = create_enhanced_fan_chart(df, "CLOSE Anchor Fan — Consensus Levels", intraday_data)
            if fig: st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})
        else: st.error("❌ CLOSE anchor data not available")
    with tab_low:
        df = fan_datasets.get('low')
        if df is not None and not df.empty:
            fig = create_enhanced_fan_chart(df, "LOW Anchor Fan — Support Levels", intraday_data)
            if fig: st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True, 'displaylogo': False})
        else: st.error("❌ LOW anchor data not available")

def handle_premium_charting(fan_datasets: dict, forecast_date: date):
    intraday_1m = fetch_spx_intraday_1m(forecast_date)
    intraday_30m = to_30m(intraday_1m)
    display_premium_charts(fan_datasets, intraday_30m)
    return {'charts_displayed': True, 'intraday_available': (not intraday_30m.empty),
            'chart_count': len([df for df in fan_datasets.values() if not df.empty])}

# ===== ENTRY DETECTION / EXPORT =====
def detect_enhanced_entry_signals(fan_df: pd.DataFrame, intraday_data: pd.DataFrame, tolerance: float, rule_type: str) -> dict:
    if fan_df.empty or intraday_data.empty:
        return {'fan_type': fan_df.attrs.get('anchor_type','UNKNOWN'),'signal_time':'—','signal_type':'—',
                'spx_price':'—','line_price':'—','delta':'—','status':'No Data','note':'No intraday data available for detection'}
    try:
        merged = pd.merge(fan_df[['Time','Entry','Exit']], intraday_data[['Time','Close']], on='Time', how='inner')
        if merged.empty:
            return {'fan_type': fan_df.attrs.get('anchor_type','UNKNOWN'),'signal_time':'—','signal_type':'—',
                    'spx_price':'—','line_price':'—','delta':'—','status':'No Match','note':'No time alignment between projections and market data'}
        for _, row in merged.iterrows():
            spx_close = float(row['Close']); exit_level = float(row['Exit']); entry_level = float(row['Entry'])
            candidates = []
            if rule_type.startswith("Close"):
                exit_valid = (spx_close >= exit_level and (spx_close - exit_level) <= tolerance)
            else:
                exit_valid = abs(spx_close - exit_level) <= tolerance
            if exit_valid:
                candidates.append({'type':'Exit↑','line_price':exit_level,'delta':abs(spx_close - exit_level)})
            if rule_type.startswith("Close"):
                entry_valid = (spx_close <= entry_level and (entry_level - spx_close) <= tolerance)
            else:
                entry_valid = abs(spx_close - entry_level) <= tolerance
            if entry_valid:
                candidates.append({'type':'Entry↓','line_price':entry_level,'delta':abs(spx_close - entry_level)})
            if candidates:
                best = min(candidates, key=lambda x: x['delta'])
                return {'fan_type': fan_df.attrs.get('anchor_type','UNKNOWN'),'signal_time': row['Time'],
                        'signal_type': best['type'],'spx_price': round(spx_close,2),
                        'line_price': round(best['line_price'],2),'delta': round(best['delta'],2),
                        'status':'Signal Detected','note': f"Rule: {rule_type[:15]}..."}
        return {'fan_type': fan_df.attrs.get('anchor_type','UNKNOWN'),'signal_time':'—','signal_type':'—',
                'spx_price':'—','line_price':'—','delta':'—','status':'No Signal',
                'note': f'No touches within ${tolerance:.2f} tolerance'}
    except Exception as e:
        return {'fan_type': fan_df.attrs.get('anchor_type','UNKNOWN'),'signal_time':'—','signal_type':'—',
                'spx_price':'—','line_price':'—','delta':'—','status':'Error','note': f'Detection error: {str(e)[:50]}...'}

def run_comprehensive_entry_detection(fan_datasets: dict, intraday_data: pd.DataFrame, tolerance: float, rule_type: str) -> pd.DataFrame:
    results = []
    for _, fan_df in fan_datasets.items():
        if fan_df is None or fan_df.empty: continue
        results.append(detect_enhanced_entry_signals(fan_df, intraday_data, tolerance, rule_type))
    if results:
        df = pd.DataFrame(results)
        df.attrs['detection_timestamp'] = datetime.now()
        df.attrs['tolerance_used'] = tolerance
        df.attrs['rule_type_used'] = rule_type
        return df
    return pd.DataFrame()

def display_entry_detection_results(results_df: pd.DataFrame, tolerance: float, rule_type: str):
    st.markdown("""<div class="section-header">🎯 Entry Detection Results</div>""", unsafe_allow_html=True)
    if results_df.empty:
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-8);">
                <div style="font-size:2rem;margin-bottom:var(--space-4);">📊</div>
                <div style="font-weight:600;margin-bottom:var(--space-2);">No Detection Results</div>
                <div style="color:var(--text-tertiary);">Generate fan data first to run entry detection</div>
            </div>
            """, unsafe_allow_html=True
        ); return
    st.markdown(
        f"""
        <div class="glass-card">
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:var(--space-4);">
                <div><div style="font-weight:600;color:var(--text-secondary);">Detection Rule</div>
                    <div style="font-family:'JetBrains Mono', monospace;">{rule_type}</div></div>
                <div><div style="font-weight:600;color:var(--text-secondary);">Tolerance</div>
                    <div style="font-family:'JetBrains Mono', monospace;">${tolerance:.2f}</div></div>
                <div><div style="font-weight:600;color:var(--text-secondary);">Timestamp</div>
                    <div style="font-family:'JetBrains Mono', monospace;">{results_df.attrs.get('detection_timestamp', datetime.now()).strftime('%H:%M:%S')}</div></div>
            </div>
        </div>
        """, unsafe_allow_html=True
    )
    def style_status(s):
        return '🎯 Signal Detected' if s=='Signal Detected' else ('⭕ No Signal' if s=='No Signal' else ('📊 No Data' if s=='No Data' else f'⚠️ {s}'))
    display_df = results_df.copy()
    display_df['Status'] = display_df['status'].apply(style_status)
    st.dataframe(
        display_df[['fan_type','signal_time','signal_type','spx_price','line_price','delta','Status','note']],
        use_container_width=True, hide_index=True,
        column_config={
            'fan_type': st.column_config.TextColumn('Anchor'),
            'signal_time': st.column_config.TextColumn('Time'),
            'signal_type': st.column_config.TextColumn('Signal'),
            'spx_price': st.column_config.NumberColumn('SPX Price', format='$%.2f'),
            'line_price': st.column_config.NumberColumn('Line Price', format='$%.2f'),
            'delta': st.column_config.NumberColumn('Delta', format='$%.2f'),
            'Status': st.column_config.TextColumn('Status'),
            'note': st.column_config.TextColumn('Note'),
        }
    )
    c1,c2,c3 = st.columns(3)
    with c1:
        signals = len(display_df[display_df['status']=='Signal Detected'])
        st.metric("🎯 Signals Detected", signals, delta=f"{signals}/{len(display_df)} fans")
    with c2:
        if signals > 0:
            avg_delta = display_df[display_df['status']=='Signal Detected']['delta'].mean()
            st.metric("📏 Avg Distance", f"${avg_delta:.2f}", delta=f"±${tolerance:.2f} tolerance")
        else:
            st.metric("📏 Avg Distance", "—")
    with c3:
        first_signal_time = '—'
        if signals > 0:
            fs = display_df[display_df['status']=='Signal Detected']
            if not fs.empty: first_signal_time = fs.iloc[0]['signal_time']
        st.metric("⏰ First Signal", first_signal_time)

def create_exportable_datasets(fan_datasets: dict, detection_results: pd.DataFrame, forecast_date: date, anchor_config: dict) -> dict:
    export_data = {}
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    for fan_name, fan_df in fan_datasets.items():
        if fan_df is not None and not fan_df.empty:
            export_df = fan_df.copy()
            export_df['Forecast_Date'] = forecast_date
            export_df['Generated_At'] = datetime.now()
            export_df['Anchor_Price'] = fan_df.attrs.get('anchor_price', 0)
            export_df['Anchor_Time'] = fan_df.attrs.get('anchor_time', time()).strftime('%H:%M')
            export_data[f'{fan_name.upper()}_Fan_{timestamp}.csv'] = export_df.to_csv(index=False).encode()
    if detection_results is not None and not detection_results.empty:
        detection_export = detection_results.copy()
        detection_export['Forecast_Date'] = forecast_date
        detection_export['Exported_At'] = datetime.now()
        export_data[f'Entry_Detection_{timestamp}.csv'] = detection_export.to_csv(index=False).encode()
    summary_df = pd.DataFrame({
        'Export_Timestamp':[datetime.now()],
        'Forecast_Date':[forecast_date],
        'High_Anchor':[f"${anchor_config.get('high_price',0):.2f} @ {anchor_config.get('high_time', time()).strftime('%H:%M')}"],
        'Close_Anchor':[f"${anchor_config.get('close_price',0):.2f} @ {anchor_config.get('close_time', time()).strftime('%H:%M')}"],
        'Low_Anchor':[f"${anchor_config.get('low_price',0):.2f} @ {anchor_config.get('low_time', time()).strftime('%H:%M')}"],
        'Total_Fans_Generated':[len([df for df in fan_datasets.values() if df is not None and not df.empty])],
        'Signals_Detected':[len(detection_results[detection_results['status']=='Signal Detected']) if detection_results is not None and not detection_results.empty else 0]
    })
    export_data[f'MarketLens_Summary_{timestamp}.csv'] = summary_df.to_csv(index=False).encode()
    return export_data

def display_enhanced_export_section(fan_datasets: dict, detection_results: pd.DataFrame, forecast_date: date, anchor_config: dict):
    st.markdown("""<div class="section-header">📤 Export & Download Center</div>""", unsafe_allow_html=True)
    if (not fan_datasets) and (detection_results is None or detection_results.empty):
        st.markdown(
            """
            <div class="premium-card" style="text-align:center;padding:var(--space-6);">
                <div style="color:var(--text-tertiary);">📊 Generate forecast data to enable exports</div>
            </div>
            """, unsafe_allow_html=True
        ); return
    col1, col2 = st.columns([3,1])
    with col1:
        st.markdown(
            """
            <div class="glass-card">
                <div style="font-weight:600;margin-bottom:var(--space-3);">📋 Available Exports</div>
                <div style="color:var(--text-secondary);font-size:var(--text-sm);line-height:1.6;">
                    • Individual fan forecast data (HIGH, CLOSE, LOW)<br>
                    • Entry detection results with metadata<br>
                    • Session summary with anchor configuration<br>
                    • All files packaged in timestamped ZIP archive
                </div>
            </div>
            """, unsafe_allow_html=True
        )
    with col2:
        if st.button("📦 Create Export Package", use_container_width=True, type="primary"):
            with st.spinner("🔄 Preparing export package..."):
                export_datasets = create_exportable_datasets(fan_datasets, detection_results, forecast_date, anchor_config)
                if export_datasets:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for filename, data in export_datasets.items():
                            zip_file.writestr(filename, data)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    zip_filename = f"MarketLens_Pro_Export_{timestamp}.zip"
                    st.download_button("⬇️ Download Export Package", data=zip_buffer.getvalue(),
                                       file_name=zip_filename, mime="application/zip", use_container_width=True)
                    st.success(f"✅ Export package ready: {len(export_datasets)} files")
                else:
                    st.error("❌ No data available for export")

def handle_entry_detection_and_export(fan_datasets: dict, forecast_date: date, tolerance: float, rule_type: str, anchor_config: dict):
    intraday_1m = fetch_spx_intraday_1m(forecast_date)
    intraday_30m = to_30m(intraday_1m)
    results = run_comprehensive_entry_detection(fan_datasets, intraday_30m, tolerance, rule_type)
    display_entry_detection_results(results, tolerance, rule_type)
    st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
    display_enhanced_export_section(fan_datasets, results, forecast_date, anchor_config)
    return {'detection_completed': True,
            'signals_found': len(results[results['status']=='Signal Detected']) if results is not None and not results.empty else 0,
            'intraday_available': (not intraday_30m.empty),
            'export_ready': bool(fan_datasets or (results is not None and not results.empty))}

# ===== INTEGRATION FLOW =====
defaults = render_anchor_header(forecast_date, previous_anchors)
anchor_inputs_data = render_basic_anchor_inputs(defaults)
control_status = handle_anchor_management(anchor_inputs_data)
anchor_config = get_anchor_configuration() if control_status['can_generate'] else None

if st.session_state.get("forecasts_generated", False) and anchor_config:
    st.markdown('<div style="margin:var(--space-8) 0;"></div>', unsafe_allow_html=True)
    fan_data = generate_all_fan_data(anchor_config, forecast_date)
    if fan_data:
        st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
        _chart_status = handle_premium_charting(fan_data, forecast_date)
    if fan_data:
        st.markdown('<div style="margin:var(--space-6) 0;"></div>', unsafe_allow_html=True)
        _det_status = handle_entry_detection_and_export(fan_data, forecast_date, tolerance, rule_requirement, anchor_config)

# ===== BACKWARD COMPAT =====
if anchor_config:
    high_price = anchor_config['high_price']; high_time = anchor_config['high_time']
    close_price = anchor_config['close_price']; close_time = anchor_config['close_time']
    low_price = anchor_config['low_price']; low_time = anchor_config['low_time']
else:
    high_price = 6185.80; high_time = time(11,30)
    close_price = 6170.20; close_time = time(15,0)
    low_price = 6130.40; low_time = time(13,30)