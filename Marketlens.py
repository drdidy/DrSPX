
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time as dtime
from typing import Tuple, Optional

# =========================================
# CORE CONSTANTS (UNCHANGED)
# =========================================

APP_NAME = "SPX Prophet"
TAGLINE = "Where Structure Becomes Foresight."

# Underlying rail slope (points per 30-minute block)
SLOPE_MAG = 0.475

# Default contract factor (option move as fraction of SPX move)
DEFAULT_CONTRACT_FACTOR = 0.30

# Base date used to build a consistent time grid
BASE_DATE = datetime(2000, 1, 1, 15, 0)  # 15:00 = previous session reference


# =========================================
# ELEGANT UI - STABLE & BEAUTIFUL
# =========================================

def inject_css():
    css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    /* Base Styles */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    .main {
        background: linear-gradient(to bottom, #f7fafc, #edf2f7);
    }
    
    /* Hero Section */
    .hero-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        padding: 2.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        text-align: center;
        color: white;
    }
    
    .hero-title {
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    
    .hero-subtitle {
        font-size: 1.2rem;
        opacity: 0.95;
        margin-bottom: 1rem;
    }
    
    .hero-meta {
        background: rgba(255, 255, 255, 0.2);
        border-radius: 10px;
        padding: 0.8rem;
        display: inline-block;
        backdrop-filter: blur(10px);
    }
    
    /* Cards */
    .card-container {
        background: white;
        border-radius: 15px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        border: 1px solid #e2e8f0;
    }
    
    .card-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: #2d3748;
        margin-bottom: 0.5rem;
    }
    
    .card-subtitle {
        color: #718096;
        line-height: 1.6;
    }
    
    /* Section Headers */
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #4a5568;
        margin: 1.5rem 0 1rem 0;
        padding-left: 1rem;
        border-left: 4px solid #667eea;
    }
    
    /* Metrics */
    .metric-box {
        background: linear-gradient(135deg, #f7fafc, #edf2f7);
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid #cbd5e0;
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: #718096;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.25rem;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #2d3748;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
        transition: transform 0.2s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
    }
    
    /* Info boxes */
    .info-box {
        background: #edf2f7;
        border-left: 4px solid #667eea;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(237, 242, 247, 0.5);
        border-radius: 10px;
        padding: 4px;
    }
    
    .stTabs [aria-selected="true"] {
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    /* Make sure content is visible */
    .element-container {
        opacity: 1 !important;
        visibility: visible !important;
    }
    
    .stMarkdown {
        opacity: 1 !important;
        visibility: visible !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def show_hero():
    """Display hero section with app branding"""
    cf = st.session_state.get("contract_factor", DEFAULT_CONTRACT_FACTOR)
    st.markdown(
        f"""
        <div class="hero-container">
            <div class="hero-title">{APP_NAME}</div>
            <div class="hero-subtitle">{TAGLINE}</div>
            <div class="hero-meta">
                Slope: {SLOPE_MAG:.3f} pts/30m · Contract Factor: {cf:.2f}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def start_card(title: str, subtitle: str = ""):
    """Start a card section"""
    st.markdown(
        f"""
        <div class="card-container">
            <div class="card-title">{title}</div>
            <div class="card-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(text: str):
    """Display a section header"""
    st.markdown(
        f'<div class="section-header">{text}</div>',
        unsafe_allow_html=True
    )


def show_metric(label: str, value: str):
    """Display a metric box"""
    st.markdown(
        f"""
        <div class="metric-box">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================
# TIME / GRID HELPERS (UNCHANGED)
# =========================================

def align_30min(dt: datetime) -> datetime:
    minute = 0 if dt.minute < 15 else (30 if dt.minute < 45 else 0)
    if dt.minute >= 45:
        dt = dt + timedelta(hours=1)
    return dt.replace(minute=minute, second=0, microsecond=0)


def blocks_from_base(dt: datetime) -> int:
    diff = dt - BASE_DATE
    return int(round(diff.total_seconds() / 1800.0))


def rth_slots() -> pd.DatetimeIndex:
    """RTH grid for the *new* session day: 08:30–14:30."""
    next_day = BASE_DATE.date() + timedelta(days=1)
    start = datetime(next_day.year, next_day.month, next_day.day, 8, 30)
    end = datetime(next_day.year, next_day.month, next_day.day, 14, 30)
    return pd.date_range(start=start, end=end, freq="30min")


def make_dt_prev_session(t: dtime) -> datetime:
    """Map a pivot time into the *previous* session day."""
    return BASE_DATE.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


# =========================================
# CHANNEL ENGINE (UNCHANGED)
# =========================================

def build_channel(
    high_price: float,
    high_time: dtime,
    low_price: float,
    low_time: dtime,
    slope_sign: int,
) -> Tuple[pd.DataFrame, float]:
    """Build a structural channel from previous-session pivots."""
    s = slope_sign * SLOPE_MAG

    dt_hi = align_30min(make_dt_prev_session(high_time))
    dt_lo = align_30min(make_dt_prev_session(low_time))

    k_hi = blocks_from_base(dt_hi)
    k_lo = blocks_from_base(dt_lo)

    b_top = high_price - s * k_hi
    b_bottom = low_price - s * k_lo

    channel_height = b_top - b_bottom

    rows = []
    for dt in rth_slots():
        k = blocks_from_base(dt)
        top = s * k + b_top
        bottom = s * k + b_bottom
        rows.append(
            {
                "Time": dt.strftime("%H:%M"),
                "Top Rail": round(top, 4),
                "Bottom Rail": round(bottom, 4),
            }
        )

    df = pd.DataFrame(rows)
    return df, float(abs(round(channel_height, 4)))


def compute_contract_factor(
    spx_start: float,
    spx_end: float,
    opt_start: float,
    opt_end: float,
) -> Optional[float]:
    spx_move = spx_end - spx_start
    opt_move = opt_end - opt_start
    if spx_move == 0:
        return None
    return abs(opt_move) / abs(spx_move)


# =========================================
# MAIN APP
# =========================================

def main():
    st.set_page_config(
        page_title=APP_NAME,
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize contract factor
    if "contract_factor" not in st.session_state:
        st.session_state["contract_factor"] = DEFAULT_CONTRACT_FACTOR

    # Apply CSS
    inject_css()

    # Sidebar
    with st.sidebar:
        st.title(APP_NAME)
        st.caption(TAGLINE)
        st.divider()
        
        st.subheader("Core Parameters")
        st.write(f"Rails slope: **{SLOPE_MAG:.3f} pts / 30m**")
        st.write(f"Contract factor: **{st.session_state['contract_factor']:.2f} × SPX**")
        
        st.divider()
        st.caption(
            "Underlying: 16:00–17:00 CT maintenance\n\n"
            "Contracts: 16:00–19:00 CT maintenance\n\n"
            "RTH projection: 08:30–14:30 CT"
        )

    # Hero Section
    show_hero()

    # Main Tabs
    tabs = st.tabs(["🧱 Rails Setup", "📐 Contract Factor", "🔮 Daily Foresight", "ℹ️ About"])

    # TAB 1: Rails Setup
    with tabs[0]:
        st.subheader("Structure Engine")
        st.write("Define structural channels using previous RTH pivots, projected into the new session.")
        
        section_header("Underlying Pivots (Previous RTH Day)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**High Pivot**")
            high_price = st.number_input(
                "High pivot price",
                value=5200.0,
                step=0.25,
                key="rails_high_price",
            )
            high_time = st.time_input(
                "High pivot time (previous RTH, CT)",
                value=dtime(13, 0),
                step=1800,
                key="rails_high_time",
            )
        
        with col2:
            st.write("**Low Pivot**")
            low_price = st.number_input(
                "Low pivot price",
                value=5100.0,
                step=0.25,
                key="rails_low_price",
            )
            low_time = st.time_input(
                "Low pivot time (previous RTH, CT)",
                value=dtime(10, 0),
                step=1800,
                key="rails_low_time",
            )
        
        section_header("Channel Regime")
        mode = st.radio(
            "Select channel mode",
            ["Ascending", "Descending", "Both"],
            index=2,
            horizontal=True,
        )
        
        if st.button("Build Structural Rails", type="primary"):
            # Build channels based on mode
            if mode in ("Ascending", "Both"):
                df_asc, h_asc = build_channel(
                    high_price, high_time, low_price, low_time, +1
                )
                st.session_state["rails_asc_df"] = df_asc
                st.session_state["rails_asc_height"] = h_asc
            else:
                st.session_state["rails_asc_df"] = None
                st.session_state["rails_asc_height"] = None
            
            if mode in ("Descending", "Both"):
                df_desc, h_desc = build_channel(
                    high_price, high_time, low_price, low_time, -1
                )
                st.session_state["rails_desc_df"] = df_desc
                st.session_state["rails_desc_height"] = h_desc
            else:
                st.session_state["rails_desc_df"] = None
                st.session_state["rails_desc_height"] = None
            
            st.success("✨ Structural rails generated successfully!")
        
        # Display results
        df_asc = st.session_state.get("rails_asc_df")
        df_desc = st.session_state.get("rails_desc_df")
        h_asc = st.session_state.get("rails_asc_height")
        h_desc = st.session_state.get("rails_desc_height")
        
        if df_asc is not None or df_desc is not None:
            section_header("Underlying Rails • RTH 08:30–14:30 CT")
            
            if df_asc is not None:
                st.write("**Ascending Channel**")
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.dataframe(df_asc, use_container_width=True, hide_index=True)
                with col2:
                    show_metric("Channel Height", f"{h_asc:.2f} pts")
                    st.download_button(
                        "📥 Download CSV",
                        df_asc.to_csv(index=False).encode(),
                        "ascending_rails.csv",
                        "text/csv",
                    )
            
            if df_desc is not None:
                st.write("**Descending Channel**")
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.dataframe(df_desc, use_container_width=True, hide_index=True)
                with col2:
                    show_metric("Channel Height", f"{h_desc:.2f} pts")
                    st.download_button(
                        "📥 Download CSV",
                        df_desc.to_csv(index=False).encode(),
                        "descending_rails.csv",
                        "text/csv",
                    )

    # TAB 2: Contract Factor
    with tabs[1]:
        st.subheader("Contract Factor Helper")
        st.write("Calibrate how option prices move relative to SPX moves.")
        
        section_header("Current Factor")
        cf = st.session_state["contract_factor"]
        
        col1, col2 = st.columns(2)
        with col1:
            show_metric("Active Contract Factor", f"{cf:.3f} × SPX")
        with col2:
            new_cf = st.number_input(
                "Manual override",
                value=float(cf),
                step=0.05,
            )
            if st.button("Update Factor"):
                st.session_state["contract_factor"] = new_cf
                st.success(f"✅ Factor updated to {new_cf:.3f}")
        
        section_header("Calibrate From Real Trade")
        st.write("Enter a past trade to calculate the factor.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**SPX Movement**")
            spx_start = st.number_input("SPX start", value=6800.0, step=1.0)
            spx_end = st.number_input("SPX end", value=6820.0, step=1.0)
        
        with col2:
            st.write("**Option Movement**")
            opt_start = st.number_input("Option start", value=10.0, step=0.1)
            opt_end = st.number_input("Option end", value=15.0, step=0.1)
        
        if st.button("Compute Factor"):
            factor = compute_contract_factor(spx_start, spx_end, opt_start, opt_end)
            if factor:
                spx_move = spx_end - spx_start
                opt_move = opt_end - opt_start
                show_metric(
                    "Suggested Factor",
                    f"{factor:.3f} × SPX"
                )
                st.info(f"Based on: SPX {spx_move:+.1f} pts → Option {opt_move:+.2f}")
                if st.button("Apply This Factor"):
                    st.session_state["contract_factor"] = factor
                    st.success(f"✅ Factor updated to {factor:.3f}")
            else:
                st.warning("SPX move cannot be zero.")

    # TAB 3: Daily Foresight
    with tabs[2]:
        st.subheader("Daily Foresight")
        st.write("Your structural playbook for today's session.")
        
        df_asc = st.session_state.get("rails_asc_df")
        df_desc = st.session_state.get("rails_desc_df")
        h_asc = st.session_state.get("rails_asc_height")
        h_desc = st.session_state.get("rails_desc_height")
        cf = st.session_state["contract_factor"]
        
        if df_asc is None and df_desc is None:
            st.warning("⚠️ Build rails first in the Rails Setup tab.")
        else:
            section_header("Structure Summary")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                scenario = "Ascending" if df_asc is not None else "Descending"
                show_metric("Default Scenario", scenario)
            
            with col2:
                if h_asc and h_desc:
                    ch_text = f"A: {h_asc:.1f} · D: {h_desc:.1f}"
                elif h_asc:
                    ch_text = f"{h_asc:.1f} pts"
                elif h_desc:
                    ch_text = f"{h_desc:.1f} pts"
                else:
                    ch_text = "—"
                show_metric("Channel Heights", ch_text)
            
            with col3:
                if h_asc:
                    target = cf * h_asc
                elif h_desc:
                    target = cf * h_desc
                else:
                    target = 0
                show_metric("Option Target", f"{target:.2f} units")
            
            # Active scenario selection
            section_header("Active Trading Scenario")
            options = []
            if df_asc is not None:
                options.append("Ascending")
            if df_desc is not None:
                options.append("Descending")
            
            if options:
                active = st.radio("Select channel", options, horizontal=True)
                
                df_ch = df_asc if active == "Ascending" else df_desc
                h_ch = h_asc if active == "Ascending" else h_desc
                
                if df_ch is not None and h_ch is not None:
                    contract_move = cf * h_ch
                    
                    st.info(
                        f"**Channel Play Strategy:**\n\n"
                        f"• **Long calls:** Buy near lower rail → Target upper rail "
                        f"(~{h_ch:.1f} pts = ~{contract_move:.1f} option units)\n\n"
                        f"• **Long puts:** Sell near upper rail → Target lower rail "
                        f"(same magnitude, opposite direction)"
                    )
                    
                    section_header("Time-Aligned Map")
                    merged = df_ch.copy()
                    merged["SPX Move"] = round(float(h_ch), 2)
                    merged["Option Target"] = round(float(contract_move), 2)
                    
                    st.dataframe(merged, use_container_width=True, hide_index=True)

    # TAB 4: About
    with tabs[4]:
        st.subheader("About SPX Prophet")
        st.write(TAGLINE)
        
        st.info(
            "**Core Concept:**\n\n"
            "Previous RTH pivots define today's rails.\n\n"
            "• Previous high/low pivots form your structural channel\n"
            "• Fixed slope of 0.475 points per 30 minutes\n"
            "• Choose ascending or descending regime\n"
            "• Contract factor maps SPX moves to option targets\n\n"
            "The result: A clean structural map for your trading session."
        )
    
    # Footer
    st.divider()
    st.caption(f"© 2025 {APP_NAME} · {TAGLINE}")


if __name__ == "__main__":
    main()