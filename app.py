"""
🔮 SPX PROPHET — NEXT GEN
"Where Structure Becomes Foresight."
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time as dtime
import pytz

from data_fetcher import (
    fetch_es_price, fetch_spx_price, fetch_es_1min,
    fetch_afternoon_1min, fetch_afternoon_30min
)
from channel_builder import (
    build_channels, auto_detect_anchors, AnchorPoint,
    get_channel_values_at_time, count_blocks, CT, SLOPE
)
from cross_detector import get_monitor_state, check_line_proximity
from trade_logic import (
    assess_ascending_day, assess_descending_day, assess_asian_session,
    convert_es_to_spx, get_session_mode, PropFirmRisk, round_strike
)

st.set_page_config(page_title="SPX Prophet", page_icon="🔮", layout="wide", initial_sidebar_state="collapsed")


# ═══════════════════════════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════════════════════════

def inject_css():
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700;800;900&family=Sora:wght@300;400;500;600;700;800&display=swap');
    :root{--bg:#050a14;--bg2:rgba(12,24,48,0.65);--border:rgba(0,200,255,0.08);--border2:rgba(0,200,255,0.2);--t1:#e8f0ff;--t2:#7a8baa;--t3:#4a5570;--cyan:#00c8ff;--gold:#ffd700;--green:#00e88f;--red:#ff4466;--purple:#a78bfa;--orange:#ff8c42}
    html,body,[data-testid="stAppViewContainer"],[data-testid="stApp"]{background:var(--bg)!important;color:var(--t1)!important;font-family:'Outfit',sans-serif!important}
    [data-testid="stAppViewContainer"]::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(ellipse 900px 600px at 10% 0%,rgba(0,200,255,0.04),transparent),radial-gradient(ellipse 800px 500px at 90% 100%,rgba(255,215,0,0.03),transparent);pointer-events:none;z-index:0}
    [data-testid="stHeader"]{background:transparent!important}
    [data-testid="stMainBlockContainer"]{max-width:1400px;padding-top:0.5rem!important}
    #MainMenu,footer,[data-testid="stToolbar"]{display:none!important}
    ::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:var(--bg)}::-webkit-scrollbar-thumb{background:rgba(0,200,255,0.2);border-radius:3px}

    /* Sidebar */
    [data-testid="stSidebar"]{background:linear-gradient(180deg,#060e1e,#0a1628,#060e1e)!important;border-right:1px solid var(--border)!important}
    [data-testid="collapsedControl"]{background:rgba(0,200,255,0.15)!important;border:1px solid rgba(0,200,255,0.3)!important;border-radius:8px!important}
    [data-testid="collapsedControl"] svg{fill:var(--cyan)!important;stroke:var(--cyan)!important}

    /* Inputs */
    .stNumberInput label,.stDateInput label,.stRadio label,.stCheckbox label,.stSelectbox label{color:var(--cyan)!important;font-family:'Outfit'!important;font-weight:600!important;text-transform:uppercase!important;letter-spacing:0.06em!important;font-size:0.72rem!important}
    input,[data-testid="stNumberInput"] input{background:rgba(0,200,255,0.04)!important;border:1px solid var(--border)!important;color:var(--t1)!important;border-radius:8px!important;font-family:'JetBrains Mono'!important}
    input:focus{border-color:var(--cyan)!important;box-shadow:0 0 12px rgba(0,200,255,0.15)!important}

    /* Buttons */
    .stButton>button{background:linear-gradient(135deg,rgba(0,200,255,0.12),rgba(0,200,255,0.04))!important;border:1px solid rgba(0,200,255,0.25)!important;color:var(--cyan)!important;font-family:'Outfit'!important;font-weight:600!important;border-radius:8px!important;transition:all 0.3s!important}
    .stButton>button:hover{background:linear-gradient(135deg,rgba(0,200,255,0.22),rgba(0,200,255,0.08))!important;border-color:var(--cyan)!important;box-shadow:0 0 20px rgba(0,200,255,0.15)!important;transform:translateY(-1px)!important}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"]{gap:4px;background:rgba(0,200,255,0.03);border-radius:10px;padding:4px;border:1px solid var(--border)}
    .stTabs [data-baseweb="tab"]{border-radius:8px;color:var(--t2);font-family:'Outfit';font-weight:500}
    .stTabs [aria-selected="true"]{background:rgba(0,200,255,0.1)!important;color:var(--cyan)!important}

    /* Expander */
    .streamlit-expanderHeader{background:var(--bg2)!important;border:1px solid var(--border)!important;border-radius:10px!important;color:var(--t1)!important;font-family:'Outfit'!important}

    /* Metrics */
    [data-testid="stMetric"]{background:var(--bg2)!important;border:1px solid var(--border)!important;border-radius:12px!important;padding:1rem!important}
    [data-testid="stMetricValue"]{font-family:'JetBrains Mono'!important}
    [data-testid="stMetricLabel"]{color:var(--t2)!important;font-family:'Outfit'!important;text-transform:uppercase!important;letter-spacing:0.08em!important;font-size:0.72rem!important}

    /* Custom classes */
    .prophet-card{background:var(--bg2);border:1px solid var(--border);border-radius:16px;padding:1.5rem;margin-bottom:1rem;backdrop-filter:blur(20px)}
    .prophet-card:hover{border-color:var(--border2);box-shadow:0 8px 32px rgba(0,0,0,0.3)}
    .card-label{font-family:'Outfit';font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.12em;color:var(--t3);margin-bottom:0.4rem}
    .card-value{font-family:'JetBrains Mono';font-size:1.8rem;font-weight:700;line-height:1.1}
    .card-sub{font-family:'Outfit';font-size:0.78rem;color:var(--t2);margin-top:0.3rem}

    .hero-container{text-align:center;padding:1.2rem 0 0.8rem}
    .hero-orb{width:52px;height:52px;margin:0 auto 0.8rem;border-radius:50%;background:radial-gradient(circle at 35% 35%,rgba(0,200,255,0.6),rgba(0,200,255,0.2) 40%,rgba(167,139,250,0.15) 70%,transparent);box-shadow:0 0 40px rgba(0,200,255,0.2);animation:orbPulse 4s ease-in-out infinite}
    @keyframes orbPulse{0%,100%{transform:scale(1);box-shadow:0 0 40px rgba(0,200,255,0.2)}50%{transform:scale(1.05);box-shadow:0 0 50px rgba(0,200,255,0.3)}}
    .hero-title{font-family:'Sora';font-size:1.8rem;font-weight:800;background:linear-gradient(135deg,#e8f0ff,#00c8ff,#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-0.03em}
    .hero-tagline{font-family:'Outfit';font-size:0.75rem;color:var(--t3);letter-spacing:0.15em;text-transform:uppercase}

    .status-badge{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:20px;font-family:'JetBrains Mono';font-size:0.7rem;font-weight:600}
    .status-live{background:rgba(0,232,143,0.1);border:1px solid rgba(0,232,143,0.25);color:var(--green)}
    .dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:dotP 2s ease-in-out infinite}
    @keyframes dotP{0%,100%{opacity:1}50%{opacity:0.3}}

    .signal-card{background:var(--bg2);border-radius:16px;padding:1.2rem 1.5rem;margin:0.8rem 0;position:relative;overflow:hidden}
    .signal-calls,.signal-long{border:1px solid rgba(0,232,143,0.2);box-shadow:0 0 20px rgba(0,232,143,0.04)}
    .signal-calls::before,.signal-long::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--green),transparent)}
    .signal-puts,.signal-short{border:1px solid rgba(255,68,102,0.2);box-shadow:0 0 20px rgba(255,68,102,0.04)}
    .signal-puts::before,.signal-short::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--red),transparent)}

    .strength-strong{background:rgba(0,232,143,0.1);color:var(--green);border:1px solid rgba(0,232,143,0.2);padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:700;font-family:'JetBrains Mono'}
    .strength-standard{background:rgba(0,200,255,0.1);color:var(--cyan);border:1px solid rgba(0,200,255,0.2);padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:700;font-family:'JetBrains Mono'}
    .strength-caution{background:rgba(255,140,66,0.1);color:var(--orange);border:1px solid rgba(255,140,66,0.2);padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:700;font-family:'JetBrains Mono'}

    .strike-call{background:rgba(0,232,143,0.1);color:var(--green);border:1px solid rgba(0,232,143,0.2);padding:3px 10px;border-radius:6px;font-family:'JetBrains Mono';font-size:0.85rem;font-weight:600}
    .strike-put{background:rgba(255,68,102,0.1);color:var(--red);border:1px solid rgba(255,68,102,0.2);padding:3px 10px;border-radius:6px;font-family:'JetBrains Mono';font-size:0.85rem;font-weight:600}

    .risk-bar{width:100%;height:8px;background:rgba(255,255,255,0.05);border-radius:4px;overflow:hidden;margin-top:0.5rem}
    .risk-fill{height:100%;border-radius:4px;transition:width 0.5s}
    .risk-clear{background:var(--green)}.risk-active{background:var(--cyan)}.risk-caution{background:var(--orange)}.risk-danger{background:var(--red)}

    .day-asc{background:linear-gradient(135deg,rgba(0,232,143,0.08),rgba(0,232,143,0.02));border:1px solid rgba(0,232,143,0.2);padding:0.6rem 1.2rem;border-radius:10px;text-align:center}
    .day-desc{background:linear-gradient(135deg,rgba(255,68,102,0.08),rgba(255,68,102,0.02));border:1px solid rgba(255,68,102,0.2);padding:0.6rem 1.2rem;border-radius:10px;text-align:center}

    .gold-card{border-color:var(--gold)!important;box-shadow:0 0 20px rgba(255,215,0,0.08)!important}
    .gold-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--gold),transparent)}
    </style>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

def render_hero():
    st.markdown('<div class="hero-container"><div class="hero-orb"></div><div class="hero-title">SPX PROPHET</div><div class="hero-tagline">Where Structure Becomes Foresight</div></div>', unsafe_allow_html=True)


def render_live_bar(es_price, es_src, spx_price, spx_src, offset, session_mode):
    labels = {"asian": "ASIAN SESSION", "pre_rth": "PRE-MARKET", "rth": "RTH ACTIVE", "afternoon": "AFTERNOON", "off": "MARKET CLOSED"}
    now_ct = datetime.now(CT)
    src_badge = f"<span style='font-size:0.6rem;color:var(--t3);'>({es_src})</span>"
    st.markdown(f"""<div class="prophet-card" style="padding:1rem 1.5rem;">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.8rem;">
    <span class="status-badge status-live"><span class="dot"></span>{labels.get(session_mode, '—')}</span>
    <div style="display:flex;gap:2rem;align-items:center;flex-wrap:wrap;">
    <div><div class="card-label">ES {src_badge}</div><div style="font-family:'JetBrains Mono';font-size:1.3rem;font-weight:700;color:var(--cyan);">{es_price:,.2f}</div></div>
    <div><div class="card-label">SPX</div><div style="font-family:'JetBrains Mono';font-size:1.3rem;font-weight:700;color:var(--t1);">{spx_price:,.2f}</div></div>
    <div><div class="card-label">OFFSET</div><div style="font-family:'JetBrains Mono';font-size:1.3rem;font-weight:700;color:var(--purple);">{offset:+.1f}</div></div>
    <div><div class="card-label">CT</div><div style="font-family:'JetBrains Mono';font-size:1.3rem;font-weight:700;color:var(--t2);">{now_ct.strftime("%I:%M %p")}</div></div>
    </div></div></div>""", unsafe_allow_html=True)


def render_scenario_card(s, trading_date=None):
    is_bull = s.direction in ("CALLS", "LONG ES")
    sig_cls = ("signal-calls" if s.direction == "CALLS" else "signal-long") if is_bull else ("signal-puts" if s.direction == "PUTS" else "signal-short")
    c = "var(--green)" if is_bull else "var(--red)"
    str_cls = f"strength-{s.strength.lower()}"
    pri = "PRIMARY" if s.is_primary else "ALTERNATE"

    parts = [
        f'<div class="signal-card {sig_cls}">',
        f'<div><span class="{str_cls}">{s.strength}</span><span style="margin-left:8px;font-size:0.7rem;color:var(--t3);">{pri}</span></div>',
        f'<div style="margin-top:0.6rem;"><span style="font-family:Sora;font-size:1.3rem;font-weight:800;color:{c};">{s.direction}</span><span style="color:var(--t3);font-size:0.85rem;margin-left:0.5rem;">at</span></div>',
        f'<div style="font-family:JetBrains Mono;font-size:1.8rem;font-weight:700;color:{c};margin-top:0.2rem;">{s.entry_level:,.2f}</div>',
        f'<div class="card-sub">{s.entry_label}</div>',
        f'<div style="font-size:0.82rem;color:var(--t2);margin-top:0.4rem;">{s.rationale}</div>',
    ]

    if s.target_level:
        parts.append(f'<div style="margin-top:0.4rem;"><span class="card-sub">Target: </span><span style="font-family:JetBrains Mono;color:{c};">{s.target_level:,.2f}</span><span class="card-sub"> ({s.target_label})</span></div>')

    sl = getattr(s, 'stop_loss', None)
    if sl:
        parts.append(f'<div style="margin-top:0.3rem;"><span class="card-sub">Stop: </span><span style="font-family:JetBrains Mono;color:var(--red);font-weight:600;">{sl:,.2f}</span></div>')

    tp1 = getattr(s, 'take_profit_1', None)
    if tp1:
        tp2 = getattr(s, 'take_profit_2', 0)
        tp3 = getattr(s, 'take_profit_3', 0)
        parts.append(f'<div style="display:flex;gap:1rem;margin-top:0.3rem;flex-wrap:wrap;">')
        parts.append(f'<div><span class="card-sub">TP1: </span><span style="font-family:JetBrains Mono;color:var(--gold);font-size:0.85rem;">{tp1:,.2f}</span></div>')
        parts.append(f'<div><span class="card-sub">TP2: </span><span style="font-family:JetBrains Mono;color:var(--gold);font-size:0.85rem;">{tp2:,.2f}</span></div>')
        parts.append(f'<div><span class="card-sub">TP3: </span><span style="font-family:JetBrains Mono;color:var(--gold);font-size:0.85rem;">{tp3:,.2f}</span></div>')
        parts.append('</div>')

    if s.strike and s.direction in ("CALLS", "PUTS"):
        cp = "C" if s.direction == "CALLS" else "P"
        scls = "strike-call" if s.direction == "CALLS" else "strike-put"
        parts.append(f'<div style="margin-top:0.8rem;padding-top:0.6rem;border-top:1px solid var(--border);"><span class="{scls}">{s.strike}{cp}</span></div>')

    parts.append('</div>')
    st.markdown(''.join(parts), unsafe_allow_html=True)


def render_cross_monitor(state):
    if "VALID" in state.status: scls = "color:var(--green);animation:crossFlash 1s ease-in-out 3"
    elif state.status == "READY": scls = "color:var(--gold)"
    elif "INVALID" in state.status: scls = "color:var(--red)"
    else: scls = "color:var(--t2)"

    sc = "var(--green)" if state.current_spread > 0 else "var(--red)"
    dp = min(100, (state.max_divergence / 10.0) * 100)
    dc = "var(--gold)" if state.is_diverged_enough else "var(--t3)"
    dt = "✓ THRESHOLD MET" if state.is_diverged_enough else "Need 10+ pts"

    st.markdown(f"""<div class="prophet-card">
    <div class="card-label">8 / 50 EMA CROSS MONITOR — ES 1-MIN</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;margin-top:1rem;">
    <div><div class="card-sub">Spread</div><div style="font-family:JetBrains Mono;font-size:1.4rem;font-weight:700;color:{sc};">{state.current_spread:+.1f}</div></div>
    <div><div class="card-sub">Max Divergence</div><div style="font-family:JetBrains Mono;font-size:1.4rem;font-weight:700;color:{dc};">{state.max_divergence:.1f}</div>
    <div class="risk-bar" style="margin-top:0.3rem;"><div class="risk-fill {'risk-clear' if state.is_diverged_enough else 'risk-active'}" style="width:{dp}%;"></div></div>
    <div class="card-sub" style="font-size:0.65rem;">{dt}</div></div>
    <div><div class="card-sub">Status</div><div style="{scls};font-family:Sora;font-size:1rem;font-weight:700;">{state.status}</div></div>
    </div>
    <div style="margin-top:1rem;padding-top:0.8rem;border-top:1px solid var(--border);"><div class="card-sub">{state.status_detail}</div></div>
    </div>""", unsafe_allow_html=True)


def render_prop_firm(risk):
    rc = {"CLEAR":"risk-clear","ACTIVE":"risk-active","CAUTION":"risk-caution","DANGER":"risk-danger","LIMIT HIT":"risk-danger"}
    st.markdown(f"""<div class="prophet-card">
    <div class="card-label">THE FUTURES DESK — RISK</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;margin-top:0.8rem;">
    <div><div class="card-sub">Max</div><div style="font-family:JetBrains Mono;font-size:1rem;">{risk.max_es} ES / {risk.max_mes} MES</div></div>
    <div><div class="card-sub">Daily Limit</div><div style="font-family:JetBrains Mono;font-size:1rem;color:var(--red);">${risk.daily_loss_limit:,.0f}</div></div>
    <div><div class="card-sub">Risk Used</div><div style="font-family:JetBrains Mono;font-size:1rem;color:{'var(--green)' if risk.risk_pct < 50 else 'var(--red)'};">{risk.risk_pct:.0f}%</div>
    <div class="risk-bar"><div class="risk-fill {rc.get(risk.risk_status,'risk-active')}" style="width:{risk.risk_pct}%;"></div></div></div>
    </div></div>""", unsafe_allow_html=True)


def render_channel_card(vals, label="ES"):
    ae = f"{vals['asc_extreme']:,.2f}" if vals.get('asc_extreme') else "—"
    de = f"{vals['desc_extreme']:,.2f}" if vals.get('desc_extreme') else "—"
    st.markdown(f"""<div class="prophet-card">
    <div class="card-label">CHANNEL LEVELS — {label}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:0.8rem;">
    <div style="border-left:3px solid var(--green);padding-left:1rem;">
    <div class="card-label" style="color:var(--green);">ASCENDING</div>
    <div style="display:flex;justify-content:space-between;margin-top:0.3rem;"><span class="card-sub">Extreme</span><span style="font-family:JetBrains Mono;color:rgba(0,232,143,0.5);font-size:0.9rem;">{ae}</span></div>
    <div style="display:flex;justify-content:space-between;"><span class="card-sub">Ceiling</span><span style="font-family:JetBrains Mono;color:var(--green);font-size:0.9rem;font-weight:600;">{vals['asc_ceiling']:,.2f}</span></div>
    <div style="display:flex;justify-content:space-between;"><span class="card-sub">Floor</span><span style="font-family:JetBrains Mono;color:var(--green);font-size:0.9rem;font-weight:600;">{vals['asc_floor']:,.2f}</span></div></div>
    <div style="border-left:3px solid var(--red);padding-left:1rem;">
    <div class="card-label" style="color:var(--red);">DESCENDING</div>
    <div style="display:flex;justify-content:space-between;margin-top:0.3rem;"><span class="card-sub">Ceiling</span><span style="font-family:JetBrains Mono;color:var(--red);font-size:0.9rem;font-weight:600;">{vals['desc_ceiling']:,.2f}</span></div>
    <div style="display:flex;justify-content:space-between;"><span class="card-sub">Floor</span><span style="font-family:JetBrains Mono;color:var(--red);font-size:0.9rem;font-weight:600;">{vals['desc_floor']:,.2f}</span></div>
    <div style="display:flex;justify-content:space-between;"><span class="card-sub">Extreme</span><span style="font-family:JetBrains Mono;color:rgba(255,68,102,0.5);font-size:0.9rem;">{de}</span></div></div>
    </div></div>""", unsafe_allow_html=True)


def make_projection_table(channels, trading_date, times_list, offset=0):
    """Build projection table. Each row = base + incremental 0.52 blocks."""
    if not times_list:
        return pd.DataFrame()
    base_t = CT.localize(datetime.combine(trading_date, times_list[0][1]))
    bv = get_channel_values_at_time(channels, base_t)
    rows = []
    for i, (label, t) in enumerate(times_list):
        rows.append({
            "Time (CT)": label,
            "Asc Ceil": round(bv["asc_ceiling"] + (SLOPE * i) - offset, 2),
            "Asc Floor": round(bv["asc_floor"] + (SLOPE * i) - offset, 2),
            "Desc Ceil": round(bv["desc_ceiling"] - (SLOPE * i) - offset, 2),
            "Desc Floor": round(bv["desc_floor"] - (SLOPE * i) - offset, 2),
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    inject_css()
    render_hero()

    # Session state defaults
    defs = {"lb":0.0,"lb_h":13,"lb_m":30,"hr":0.0,"hr_h":14,"hr_m":0,"hw":0.0,"hw_h":13,"hw_m":0,"lw":0.0,"lw_h":14,"lw_m":30,"offset_input":45.0,"auto_detected":False}
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ─── COMMAND CENTER ───
    with st.expander("⚙️ COMMAND CENTER", expanded=True):
        trading_date = st.date_input("TRADING DATE", value=date.today())
        day_type = st.radio("DAY TYPE", ["ASCENDING", "DESCENDING"], horizontal=True)
        day_type_lower = day_type.lower()
        manual_offset = st.number_input("ES - SPX OFFSET", format="%.2f", key="offset_input")

        st.markdown("---")

        # Auto-detect button
        auto_col1, auto_col2 = st.columns([1, 1])
        with auto_col1:
            if st.button("🔍 AUTO-DETECT ANCHORS", use_container_width=True):
                with st.spinner("Fetching afternoon data..."):
                    df_1m, used_date = fetch_afternoon_1min(trading_date)
                    df_30m, _ = fetch_afternoon_30min(trading_date)
                    if not df_1m.empty:
                        detected = auto_detect_anchors(df_1m, df_30m)
                        if detected:
                            st.session_state["lb"] = detected['lb'].price
                            st.session_state["lb_h"] = detected['lb'].timestamp.hour
                            st.session_state["lb_m"] = detected['lb'].timestamp.minute
                            st.session_state["hr"] = detected['hr'].price
                            st.session_state["hr_h"] = detected['hr'].timestamp.hour
                            st.session_state["hr_m"] = detected['hr'].timestamp.minute
                            st.session_state["hw"] = detected['hw'].price
                            st.session_state["hw_h"] = detected['hw'].timestamp.hour
                            st.session_state["hw_m"] = detected['hw'].timestamp.minute
                            st.session_state["lw"] = detected['lw'].price
                            st.session_state["lw_h"] = detected['lw'].timestamp.hour
                            st.session_state["lw_m"] = detected['lw'].timestamp.minute
                            st.session_state["auto_detected"] = True
                            st.success(f"Detected from {used_date.strftime('%b %d')} — verify below")
                            st.rerun()
                        else:
                            st.warning("Could not detect anchors. Enter manually.")
                    else:
                        st.warning("No afternoon data available. Enter manually.")

        with auto_col2:
            if st.button("🔄 REFRESH PRICES", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        if st.session_state.get("auto_detected"):
            st.info("Auto-detected values loaded. Verify and adjust if needed.")

        st.markdown("""<div class="card-label" style="margin:0.5rem 0;">12-3 PM ANCHORS (ES from TradingView)</div>""", unsafe_allow_html=True)

        # Anchor inputs — stacked for mobile
        lb1, lb2, lb3 = st.columns([3, 1, 1])
        with lb1: man_lb = st.number_input("Lowest Bounce", format="%.2f", key="lb")
        with lb2: man_lb_h = st.number_input("LB Hr", min_value=12, max_value=15, key="lb_h")
        with lb3: man_lb_m = st.number_input("LB Min", min_value=0, max_value=59, key="lb_m")

        hr1, hr2, hr3 = st.columns([3, 1, 1])
        with hr1: man_hr = st.number_input("Highest Rejection", format="%.2f", key="hr")
        with hr2: man_hr_h = st.number_input("HR Hr", min_value=12, max_value=15, key="hr_h")
        with hr3: man_hr_m = st.number_input("HR Min", min_value=0, max_value=59, key="hr_m")

        hw1, hw2, hw3 = st.columns([3, 1, 1])
        with hw1: man_hw = st.number_input("Highest Wick", format="%.2f", key="hw")
        with hw2: man_hw_h = st.number_input("HW Hr", min_value=12, max_value=15, key="hw_h")
        with hw3: man_hw_m = st.number_input("HW Min", min_value=0, max_value=59, key="hw_m")

        lw1, lw2, lw3 = st.columns([3, 1, 1])
        with lw1: man_lw = st.number_input("Lowest Wick", format="%.2f", key="lw")
        with lw2: man_lw_h = st.number_input("LW Hr", min_value=12, max_value=15, key="lw_h")
        with lw3: man_lw_m = st.number_input("LW Min", min_value=0, max_value=59, key="lw_m")

        auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)

    # ─── FETCH PRICES ───
    es_price, es_src = fetch_es_price()
    spx_price, spx_src = fetch_spx_price()
    offset = manual_offset
    session_mode = get_session_mode()
    es_1min = fetch_es_1min()

    render_live_bar(es_price, es_src, spx_price, spx_src, offset, session_mode)

    # ─── BUILD CHANNELS ───
    channels = None
    prior_date = trading_date - timedelta(days=1)
    while prior_date.weekday() >= 5:
        prior_date -= timedelta(days=1)

    if man_lb > 0 and man_hr > 0:
        try:
            channels = build_channels(
                AnchorPoint(man_lb, CT.localize(datetime.combine(prior_date, dtime(man_lb_h, man_lb_m))), "Lowest Bounce"),
                AnchorPoint(man_hr, CT.localize(datetime.combine(prior_date, dtime(man_hr_h, man_hr_m))), "Highest Rejection"),
                AnchorPoint(man_hw if man_hw > 0 else man_hr, CT.localize(datetime.combine(prior_date, dtime(man_hw_h, man_hw_m))), "Highest Wick"),
                AnchorPoint(man_lw if man_lw > 0 else man_lb, CT.localize(datetime.combine(prior_date, dtime(man_lw_h, man_lw_m))), "Lowest Wick"),
            )
        except Exception as e:
            st.error(f"Channel error: {e}")

    if channels is None:
        st.markdown('<div class="prophet-card" style="text-align:center;padding:2rem;"><div style="font-size:2rem;">📝</div><div style="font-family:Outfit;color:var(--gold);font-size:1rem;font-weight:600;">ENTER CHANNEL ANCHORS</div><div class="card-sub">Enter Lowest Bounce and Highest Rejection above to generate projections.</div></div>', unsafe_allow_html=True)
        return

    # ─── DAY TYPE ───
    if day_type_lower == "ascending":
        st.markdown('<div class="day-asc"><div class="card-label" style="color:rgba(0,232,143,0.6);">TODAY\'S CHANNEL</div><div style="font-family:Sora;font-size:1.3rem;font-weight:800;color:var(--green);">▲ ASCENDING DAY</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="day-desc"><div class="card-label" style="color:rgba(255,68,102,0.6);">TODAY\'S CHANNEL</div><div style="font-family:Sora;font-size:1.3rem;font-weight:800;color:var(--red);">▼ DESCENDING DAY</div></div>', unsafe_allow_html=True)

    # ─── CURRENT VALUES ───
    now_ct = datetime.now(CT)
    es_vals = get_channel_values_at_time(channels, now_ct)

    # Asian session date = prior_date (same day as anchors, evening session)
    asian_date = prior_date

    # ─── TABS ───
    tab_asian, tab_rth, tab_proj = st.tabs(["🌏 ASIAN", "📈 RTH", "📊 PROJECTIONS"])

    # ═══ ASIAN TAB ═══
    with tab_asian:
        asian_times = [(f"{h}:{m:02d} PM" if h < 21 else f"{h-12}:{m:02d} PM", dtime(h, m))
                       for h in range(17, 22) for m in (0, 30) if not (h == 21 and m == 30)]
        asian_df = make_projection_table(channels, asian_date, asian_times)
        st.dataframe(asian_df, use_container_width=True, hide_index=True)

        render_channel_card(es_vals, "ES NOW")

        if es_price > 0:
            assessment = assess_asian_session(es_price, es_vals)
            st.markdown(f'<div class="prophet-card"><div class="card-label">POSITION — ES @ {es_price:,.2f}</div><div style="font-family:Sora;font-size:1.1rem;font-weight:700;color:var(--cyan);margin-top:0.5rem;">{assessment.zone_label}</div><div class="card-sub">Nearest: {assessment.nearest_line} ({assessment.nearest_distance:.2f} pts)</div></div>', unsafe_allow_html=True)
            for s in assessment.scenarios:
                render_scenario_card(s)
            render_prop_firm(PropFirmRisk())

    # ═══ RTH TAB ═══
    with tab_rth:
        # 9 AM entry card
        nine_am = CT.localize(datetime.combine(trading_date, dtime(9, 0)))
        v9 = get_channel_values_at_time(channels, nine_am)
        s9 = convert_es_to_spx(v9, offset)

        st.markdown(
            f'<div class="prophet-card gold-card" style="position:relative;overflow:hidden;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div class="card-label" style="color:var(--gold);font-size:0.8rem;">9:00 AM CT — ENTRY LEVELS (SPX)</div>'
            f'<span class="status-badge" style="background:rgba(255,215,0,0.1);border:1px solid rgba(255,215,0,0.3);color:var(--gold);">INSTITUTIONAL OPEN</span></div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-top:1rem;">'
            f'<div style="border-left:3px solid var(--green);padding-left:1rem;"><div class="card-label" style="color:var(--green);">ASCENDING</div>'
            f'<div style="display:flex;justify-content:space-between;margin-top:0.3rem;"><span class="card-sub">Ceiling</span><span style="font-family:JetBrains Mono;color:var(--green);font-size:1.1rem;font-weight:700;">{s9["asc_ceiling"]:,.2f}</span></div>'
            f'<div style="display:flex;justify-content:space-between;"><span class="card-sub">Floor</span><span style="font-family:JetBrains Mono;color:var(--green);font-size:1.1rem;font-weight:700;">{s9["asc_floor"]:,.2f}</span></div></div>'
            f'<div style="border-left:3px solid var(--red);padding-left:1rem;"><div class="card-label" style="color:var(--red);">DESCENDING</div>'
            f'<div style="display:flex;justify-content:space-between;margin-top:0.3rem;"><span class="card-sub">Ceiling</span><span style="font-family:JetBrains Mono;color:var(--red);font-size:1.1rem;font-weight:700;">{s9["desc_ceiling"]:,.2f}</span></div>'
            f'<div style="display:flex;justify-content:space-between;"><span class="card-sub">Floor</span><span style="font-family:JetBrains Mono;color:var(--red);font-size:1.1rem;font-weight:700;">{s9["desc_floor"]:,.2f}</span></div></div>'
            f'</div></div>',
            unsafe_allow_html=True
        )

        # Scenarios from 9 AM values
        price_rth = spx_price if spx_price > 0 else (es_price - offset if es_price > 0 else 0)
        if price_rth > 0:
            rth_assess = assess_ascending_day(price_rth, s9) if day_type_lower == "ascending" else assess_descending_day(price_rth, s9)
            st.markdown(f'<div class="prophet-card"><div class="card-label">POSITION — SPX @ {price_rth:,.2f}</div><div style="font-family:Sora;font-size:1.1rem;font-weight:700;color:var(--cyan);margin-top:0.5rem;">{rth_assess.zone_label}</div><div class="card-sub">Nearest: {rth_assess.nearest_line} ({rth_assess.nearest_distance:.2f} pts)</div></div>', unsafe_allow_html=True)
            for s in rth_assess.scenarios:
                render_scenario_card(s, trading_date)

        # RTH projection table
        rth_times = [
            ("8:30", dtime(8,30)), ("★ 9:00", dtime(9,0)), ("9:30", dtime(9,30)),
            ("10:00", dtime(10,0)), ("10:30", dtime(10,30)), ("11:00", dtime(11,0)),
            ("11:30", dtime(11,30)), ("12:00", dtime(12,0)), ("12:30", dtime(12,30)), ("1:00", dtime(13,0)),
        ]
        st.markdown('<div class="card-label" style="margin-top:1rem;">RTH PROJECTIONS — SPX</div>', unsafe_allow_html=True)
        rth_df = make_projection_table(channels, trading_date, rth_times, offset)
        st.dataframe(rth_df, use_container_width=True, hide_index=True)

    # ═══ PROJECTIONS TAB ═══
    with tab_proj:
        st.markdown('<div class="card-label">FULL ES PROJECTION TABLE</div>', unsafe_allow_html=True)
        # Evening session: prior_date 5 PM - 11:30 PM
        eve_times = [(f"{h}:{m:02d} PM", dtime(h, m)) for h in range(17, 24) for m in (0, 30)]
        eve_df = make_projection_table(channels, asian_date, eve_times)
        # Overnight + morning: trading_date 12 AM - 1 PM
        morn_times = [(f"{h}:{m:02d} AM" if h < 12 else f"{h-12 if h > 12 else 12}:{m:02d} PM", dtime(h, m)) for h in range(0, 14) for m in (0, 30)]
        # For morning, base calculation needs to continue from where evening left off
        if not eve_df.empty:
            last_eve_row = len(eve_times)
            base_t = CT.localize(datetime.combine(asian_date, dtime(17, 0)))
            bv = get_channel_values_at_time(channels, base_t)
            morn_rows = []
            for i, (label, t) in enumerate(morn_times):
                block_i = last_eve_row + i
                morn_rows.append({
                    "Time (CT)": label,
                    "Asc Ceil": round(bv["asc_ceiling"] + (SLOPE * block_i), 2),
                    "Asc Floor": round(bv["asc_floor"] + (SLOPE * block_i), 2),
                    "Desc Ceil": round(bv["desc_ceiling"] - (SLOPE * block_i), 2),
                    "Desc Floor": round(bv["desc_floor"] - (SLOPE * block_i), 2),
                })
            morn_df = pd.DataFrame(morn_rows)
            full_df = pd.concat([eve_df, morn_df], ignore_index=True)
        else:
            full_df = pd.DataFrame()
        st.dataframe(full_df, use_container_width=True, hide_index=True, height=600)

    # ─── CROSS MONITOR ───
    st.markdown('<div class="card-label" style="margin:1.5rem 0 0.5rem;font-size:0.75rem;">ENTRY CONFIRMATION</div>', unsafe_allow_html=True)
    if not es_1min.empty:
        cs = get_monitor_state(es_1min)
        if es_price > 0:
            nearby = check_line_proximity(es_price, es_vals, 5.0)
            if nearby and "CROSS" in cs.status:
                cs.status_detail += f" | Near {nearby} — LINE TOUCH ✓"
        render_cross_monitor(cs)
        if cs.recent_crosses:
            with st.expander("📋 Cross History"):
                for cx in reversed(cs.recent_crosses):
                    v = "✅" if cx.is_valid else "❌"
                    d = "▲" if cx.cross_type == "bullish" else "▼"
                    c = "var(--green)" if cx.cross_type == "bullish" else "var(--red)"
                    st.markdown(f'<div style="padding:0.4rem 0;border-bottom:1px solid var(--border);font-family:JetBrains Mono;font-size:0.78rem;"><span style="color:{c};">{d}</span> {cx.timestamp.strftime("%I:%M %p")} | Div: {cx.divergence:.1f} | {cx.nearest_hour} | {v}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="prophet-card"><div class="card-label">8/50 CROSS MONITOR</div><div class="card-sub">Waiting for ES 1-min data...</div></div>', unsafe_allow_html=True)

    # ─── DEBUG ───
    with st.expander("🔧 Anchor Debug"):
        for ap in channels.anchor_points:
            st.markdown(f'<div style="padding:0.3rem 0;font-family:JetBrains Mono;font-size:0.8rem;"><span style="color:var(--cyan);">{ap.label}</span> | {ap.price:,.2f} | {ap.timestamp.strftime("%b %d %Y, %I:%M %p CT")}</div>', unsafe_allow_html=True)
        test_t = CT.localize(datetime.combine(trading_date, dtime(9, 0)))
        tb = count_blocks(channels.anchor_points[0].timestamp, test_t)
        st.markdown(f'<div style="color:var(--gold);font-family:JetBrains Mono;font-size:0.75rem;">Blocks from {channels.anchor_points[0].label} to 9 AM = {tb:.0f} | Change = {SLOPE*tb:.2f} pts</div>', unsafe_allow_html=True)

    # ─── FOOTER ───
    st.markdown('<div style="text-align:center;padding:1.5rem 0 1rem;margin-top:1.5rem;border-top:1px solid var(--border);"><div style="font-family:Sora;font-size:0.7rem;color:var(--t3);letter-spacing:0.1em;">SPX PROPHET — NEXT GEN | BUILT FOR PRECISION</div></div>', unsafe_allow_html=True)

    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()


if __name__ == "__main__":
    main()
