"""
🔮 SPX PROPHET — NEXT GEN
"Where Structure Becomes Foresight."
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time as dtime
import pytz

from data_fetcher import fetch_es_price, fetch_spx_price, fetch_es_1min, fetch_afternoon_1min, fetch_afternoon_30min
from channel_builder import build_channels, auto_detect_anchors, AnchorPoint, get_channel_values_at_time, count_blocks, CT, SLOPE
from cross_detector import get_monitor_state, check_line_proximity
from trade_logic import assess_ascending_day, assess_descending_day, assess_asian_session, convert_es_to_spx, get_session_mode, PropFirmRisk, round_strike

st.set_page_config(page_title="SPX Prophet", page_icon="🔮", layout="wide", initial_sidebar_state="collapsed")

def inject_css():
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700;800;900&family=Sora:wght@300;400;500;600;700;800&display=swap');
    :root{--bg:#050a14;--bg2:rgba(12,24,48,0.6);--bg3:rgba(8,16,36,0.8);--border:rgba(0,200,255,0.08);--border2:rgba(0,200,255,0.2);--t1:#e8f0ff;--t2:#7a8baa;--t3:#4a5570;--cyan:#00c8ff;--gold:#ffd700;--green:#00e88f;--red:#ff4466;--purple:#a78bfa;--orange:#ff8c42;--teal:#00f5d4}
    html,body,[data-testid="stAppViewContainer"],[data-testid="stApp"]{background:var(--bg)!important;color:var(--t1)!important;font-family:'Outfit',sans-serif!important}

    /* Cosmic background with floating orbs */
    [data-testid="stAppViewContainer"]::before{content:'';position:fixed;top:0;left:0;right:0;bottom:0;background:radial-gradient(ellipse 600px 400px at 15% 10%,rgba(0,245,212,0.05),transparent),radial-gradient(ellipse 500px 350px at 85% 90%,rgba(155,93,229,0.04),transparent),radial-gradient(ellipse 400px 300px at 50% 50%,rgba(0,187,249,0.03),transparent);pointer-events:none;z-index:0;animation:cosmicDrift 20s ease-in-out infinite}
    @keyframes cosmicDrift{0%,100%{opacity:0.7}50%{opacity:1}}

    [data-testid="stHeader"]{background:transparent!important}
    [data-testid="stMainBlockContainer"]{max-width:1400px;padding-top:0.5rem!important}
    #MainMenu,footer,[data-testid="stToolbar"]{display:none!important}
    ::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:rgba(0,200,255,0.15);border-radius:3px}

    [data-testid="collapsedControl"]{background:rgba(0,200,255,0.15)!important;border:1px solid rgba(0,200,255,0.3)!important;border-radius:8px!important}
    [data-testid="collapsedControl"] svg{fill:var(--cyan)!important}

    .stNumberInput label,.stDateInput label,.stRadio label,.stCheckbox label,.stSelectbox label{color:var(--cyan)!important;font-family:'Outfit'!important;font-weight:600!important;text-transform:uppercase!important;letter-spacing:0.06em!important;font-size:0.72rem!important}
    input,[data-testid="stNumberInput"] input{background:rgba(0,200,255,0.03)!important;border:1px solid var(--border)!important;color:var(--t1)!important;border-radius:8px!important;font-family:'JetBrains Mono'!important}
    input:focus{border-color:var(--cyan)!important;box-shadow:0 0 15px rgba(0,200,255,0.12)!important}

    .stButton>button{background:linear-gradient(135deg,rgba(0,245,212,0.1),rgba(0,200,255,0.04))!important;border:1px solid rgba(0,245,212,0.25)!important;color:var(--teal)!important;font-family:'Outfit'!important;font-weight:600!important;border-radius:10px!important;transition:all 0.3s cubic-bezier(0.4,0,0.2,1)!important}
    .stButton>button:hover{background:linear-gradient(135deg,rgba(0,245,212,0.2),rgba(0,200,255,0.08))!important;box-shadow:0 0 25px rgba(0,245,212,0.12),0 4px 15px rgba(0,0,0,0.3)!important;transform:translateY(-2px)!important}

    .stTabs [data-baseweb="tab-list"]{gap:4px;background:var(--bg3);border-radius:12px;padding:4px;border:1px solid var(--border)}
    .stTabs [data-baseweb="tab"]{border-radius:8px;color:var(--t2);font-family:'Outfit';font-weight:500;transition:all 0.2s}
    .stTabs [aria-selected="true"]{background:rgba(0,245,212,0.08)!important;color:var(--teal)!important}

    .streamlit-expanderHeader{background:var(--bg3)!important;border:1px solid var(--border)!important;border-radius:12px!important;color:var(--t1)!important;font-family:'Outfit'!important}

    /* ═══ GLASSMORPHIC CARD SYSTEM ═══ */
    .prophet-card{background:var(--bg2);border:1px solid var(--border);border-radius:16px;padding:1.5rem;margin-bottom:1rem;backdrop-filter:blur(24px) saturate(150%);transition:all 0.3s cubic-bezier(0.4,0,0.2,1)}
    .prophet-card:hover{border-color:var(--border2);box-shadow:0 8px 40px rgba(0,0,0,0.35),inset 0 1px 0 rgba(255,255,255,0.03)}
    .card-label{font-family:'Outfit';font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:0.12em;color:var(--t3);margin-bottom:0.4rem}
    .card-sub{font-family:'Outfit';font-size:0.78rem;color:var(--t2);margin-top:0.3rem}

    /* ═══ EPIC ANIMATED HERO WITH PYRAMID ═══ */
    .hero-banner{position:relative;text-align:center;padding:1.5rem 1rem;margin-bottom:0.5rem;background:linear-gradient(135deg,rgba(5,10,20,0.9),rgba(10,22,40,0.9));border:1px solid rgba(0,245,212,0.1);border-radius:20px;overflow:hidden}
    .hero-banner::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 80% 120% at 20% 50%,rgba(0,245,212,0.08),transparent 50%),radial-gradient(ellipse 80% 120% at 80% 50%,rgba(155,93,229,0.06),transparent 50%);animation:heroAurora 8s ease-in-out infinite;pointer-events:none}
    @keyframes heroAurora{0%,100%{opacity:0.6;transform:translateX(0)}50%{opacity:1;transform:translateX(2%)}}
    .hero-banner::after{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;background:linear-gradient(90deg,var(--teal),var(--purple),var(--cyan));box-shadow:0 0 20px rgba(0,245,212,0.4)}

    /* Animated Pyramid Logo */
    .pyramid-wrap{position:relative;width:80px;height:80px;margin:0 auto 0.8rem;animation:pyramidFloat 4s ease-in-out infinite}
    @keyframes pyramidFloat{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-5px) scale(1.03)}}
    .pyramid-ring{position:absolute;inset:-8px;border:1.5px solid rgba(0,245,212,0.25);border-radius:50%;animation:ringRotate 15s linear infinite}
    .pyramid-ring::before{content:'';position:absolute;top:-3px;left:50%;width:6px;height:6px;background:var(--teal);border-radius:50%;box-shadow:0 0 12px var(--teal)}
    @keyframes ringRotate{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
    .pyramid-ring-inner{position:absolute;inset:2px;border:1px solid rgba(155,93,229,0.3);border-radius:50%;animation:ringRotate 10s linear infinite reverse}
    .pyramid-ring-inner::before{content:'';position:absolute;bottom:-2px;left:50%;width:4px;height:4px;background:var(--purple);border-radius:50%;box-shadow:0 0 8px var(--purple)}
    .pyramid-body{position:absolute;top:10px;left:50%;transform:translateX(-50%);width:0;height:0;border-left:32px solid transparent;border-right:32px solid transparent;border-bottom:55px solid rgba(0,245,212,0.12);filter:drop-shadow(0 0 20px rgba(0,245,212,0.3));animation:pyramidGlow 3s ease-in-out infinite}
    @keyframes pyramidGlow{0%,100%{filter:drop-shadow(0 0 15px rgba(0,245,212,0.2));border-bottom-color:rgba(0,245,212,0.1)}50%{filter:drop-shadow(0 0 30px rgba(0,245,212,0.5));border-bottom-color:rgba(0,245,212,0.2)}}
    .pyramid-inner{position:absolute;top:24px;left:50%;transform:translateX(-50%);width:0;height:0;border-left:18px solid transparent;border-right:18px solid transparent;border-bottom:32px solid rgba(155,93,229,0.15);animation:pyramidGlow 3s ease-in-out infinite 0.5s}
    .pyramid-eye{position:absolute;top:32px;left:50%;transform:translateX(-50%);width:14px;height:14px;border-radius:50%;background:radial-gradient(circle,rgba(0,245,212,0.8),rgba(0,245,212,0.2) 60%,transparent);box-shadow:0 0 15px rgba(0,245,212,0.6);animation:eyePulse 2s ease-in-out infinite}
    @keyframes eyePulse{0%,100%{box-shadow:0 0 10px rgba(0,245,212,0.4);transform:translateX(-50%) scale(1)}50%{box-shadow:0 0 25px rgba(0,245,212,0.8);transform:translateX(-50%) scale(1.15)}}
    .pyramid-energy{position:absolute;inset:-15px;border-radius:50%;background:radial-gradient(circle,rgba(0,245,212,0.06),transparent 70%);animation:energyPulse 4s ease-in-out infinite}
    @keyframes energyPulse{0%,100%{transform:scale(1);opacity:0.4}50%{transform:scale(1.2);opacity:0.7}}

    .hero-title{font-family:'Sora';font-size:2rem;font-weight:800;background:linear-gradient(135deg,#e8f0ff 0%,var(--teal) 40%,var(--purple) 70%,var(--cyan) 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-0.03em;animation:titleShimmer 6s ease-in-out infinite;background-size:200% 200%}
    @keyframes titleShimmer{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
    .hero-tagline{font-family:'Outfit';font-size:0.72rem;color:var(--t3);letter-spacing:0.2em;text-transform:uppercase;margin-top:0.2rem}

    .status-badge{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;border-radius:20px;font-family:'JetBrains Mono';font-size:0.7rem;font-weight:600}
    .status-live{background:rgba(0,232,143,0.08);border:1px solid rgba(0,232,143,0.2);color:var(--green)}
    .dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:dotP 2s ease-in-out infinite}
    @keyframes dotP{0%,100%{opacity:1}50%{opacity:0.3}}

    .signal-card{background:var(--bg2);border-radius:16px;padding:1.2rem 1.5rem;margin:0.8rem 0;position:relative;overflow:hidden;backdrop-filter:blur(20px)}
    .signal-calls,.signal-long{border:1px solid rgba(0,232,143,0.15);box-shadow:0 0 25px rgba(0,232,143,0.03)}
    .signal-calls::before,.signal-long::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--green),transparent)}
    .signal-puts,.signal-short{border:1px solid rgba(255,68,102,0.15);box-shadow:0 0 25px rgba(255,68,102,0.03)}
    .signal-puts::before,.signal-short::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--red),transparent)}

    .strength-strong{background:rgba(0,232,143,0.08);color:var(--green);border:1px solid rgba(0,232,143,0.2);padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:700;font-family:'JetBrains Mono'}
    .strength-standard{background:rgba(0,200,255,0.08);color:var(--cyan);border:1px solid rgba(0,200,255,0.2);padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:700;font-family:'JetBrains Mono'}
    .strength-caution{background:rgba(255,140,66,0.08);color:var(--orange);border:1px solid rgba(255,140,66,0.2);padding:2px 8px;border-radius:4px;font-size:0.65rem;font-weight:700;font-family:'JetBrains Mono'}

    .strike-call{background:rgba(0,232,143,0.08);color:var(--green);border:1px solid rgba(0,232,143,0.2);padding:3px 10px;border-radius:6px;font-family:'JetBrains Mono';font-size:0.85rem;font-weight:600}
    .strike-put{background:rgba(255,68,102,0.08);color:var(--red);border:1px solid rgba(255,68,102,0.2);padding:3px 10px;border-radius:6px;font-family:'JetBrains Mono';font-size:0.85rem;font-weight:600}

    .risk-bar{width:100%;height:6px;background:rgba(255,255,255,0.04);border-radius:3px;overflow:hidden;margin-top:0.5rem}
    .risk-fill{height:100%;border-radius:3px;transition:width 0.5s}
    .risk-clear{background:var(--green)}.risk-active{background:var(--cyan)}.risk-caution{background:var(--orange)}.risk-danger{background:var(--red)}

    .day-asc{background:linear-gradient(135deg,rgba(0,232,143,0.06),rgba(0,232,143,0.01));border:1px solid rgba(0,232,143,0.15);padding:0.8rem 1.2rem;border-radius:12px;text-align:center}
    .day-desc{background:linear-gradient(135deg,rgba(255,68,102,0.06),rgba(255,68,102,0.01));border:1px solid rgba(255,68,102,0.15);padding:0.8rem 1.2rem;border-radius:12px;text-align:center}

    .gold-card{border-color:rgba(255,215,0,0.2)!important;box-shadow:0 0 30px rgba(255,215,0,0.06)!important;position:relative;overflow:hidden}
    .gold-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,var(--gold),transparent)}

    /* Distance badge */
    .dist-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-family:'JetBrains Mono';font-size:0.7rem;font-weight:600;margin-left:6px}
    .dist-near{background:rgba(255,215,0,0.1);color:var(--gold);border:1px solid rgba(255,215,0,0.2)}
    .dist-far{background:rgba(0,200,255,0.06);color:var(--t2);border:1px solid var(--border)}

    /* Dataframe styling */
    [data-testid="stDataFrame"]{border:1px solid var(--border)!important;border-radius:12px!important;overflow:hidden!important}
    </style>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

def render_hero():
    st.markdown("""<div class="hero-banner">
    <div class="pyramid-wrap"><div class="pyramid-energy"></div><div class="pyramid-ring"></div><div class="pyramid-ring-inner"></div>
    <div class="pyramid-body"></div><div class="pyramid-inner"></div><div class="pyramid-eye"></div></div>
    <div class="hero-title">SPX PROPHET</div>
    <div class="hero-tagline">Where Structure Becomes Foresight</div>
    </div>""", unsafe_allow_html=True)


def render_live_bar(es_price, es_src, spx_price, spx_src, offset, session_mode):
    labels = {"asian":"ASIAN SESSION","pre_rth":"PRE-MARKET","rth":"RTH ACTIVE","afternoon":"AFTERNOON","off":"MARKET CLOSED"}
    now_ct = datetime.now(CT)
    st.markdown(f"""<div class="prophet-card" style="padding:1rem 1.5rem;">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.8rem;">
    <span class="status-badge status-live"><span class="dot"></span>{labels.get(session_mode,'—')}</span>
    <div style="display:flex;gap:2rem;align-items:center;flex-wrap:wrap;">
    <div><div class="card-label">ES <span style="font-size:0.55rem;color:var(--t3);">({es_src})</span></div><div style="font-family:'JetBrains Mono';font-size:1.3rem;font-weight:700;color:var(--teal);">{es_price:,.2f}</div></div>
    <div><div class="card-label">SPX</div><div style="font-family:'JetBrains Mono';font-size:1.3rem;font-weight:700;color:var(--t1);">{spx_price:,.2f}</div></div>
    <div><div class="card-label">OFFSET</div><div style="font-family:'JetBrains Mono';font-size:1.3rem;font-weight:700;color:var(--purple);">{offset:+.1f}</div></div>
    <div><div class="card-label">CT</div><div style="font-family:'JetBrains Mono';font-size:1.3rem;font-weight:700;color:var(--t2);">{now_ct.strftime("%I:%M %p")}</div></div>
    </div></div></div>""", unsafe_allow_html=True)


def render_scenario_card(s, trading_date=None, current_price=0):
    is_bull = s.direction in ("CALLS", "LONG ES")
    sig_cls = ("signal-calls" if s.direction == "CALLS" else "signal-long") if is_bull else ("signal-puts" if s.direction == "PUTS" else "signal-short")
    c = "var(--green)" if is_bull else "var(--red)"
    str_cls = f"strength-{s.strength.lower()}"
    pri = "PRIMARY" if s.is_primary else "ALTERNATE"

    # Distance to entry
    dist_html = ""
    if current_price > 0:
        dist = abs(current_price - s.entry_level)
        dist_cls = "dist-near" if dist < 10 else "dist-far"
        dist_html = f'<span class="dist-badge {dist_cls}">{dist:.1f} pts away</span>'

    parts = [
        f'<div class="signal-card {sig_cls}">',
        f'<div><span class="{str_cls}">{s.strength}</span><span style="margin-left:8px;font-size:0.7rem;color:var(--t3);">{pri}</span>{dist_html}</div>',
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
        tp2, tp3 = getattr(s, 'take_profit_2', 0), getattr(s, 'take_profit_3', 0)
        parts.append(f'<div style="display:flex;gap:1rem;margin-top:0.3rem;flex-wrap:wrap;"><div><span class="card-sub">TP1: </span><span style="font-family:JetBrains Mono;color:var(--gold);font-size:0.85rem;">{tp1:,.2f}</span></div><div><span class="card-sub">TP2: </span><span style="font-family:JetBrains Mono;color:var(--gold);font-size:0.85rem;">{tp2:,.2f}</span></div><div><span class="card-sub">TP3: </span><span style="font-family:JetBrains Mono;color:var(--gold);font-size:0.85rem;">{tp3:,.2f}</span></div></div>')
    if s.strike and s.direction in ("CALLS", "PUTS"):
        cp = "C" if s.direction == "CALLS" else "P"
        scls = "strike-call" if s.direction == "CALLS" else "strike-put"
        parts.append(f'<div style="margin-top:0.8rem;padding-top:0.6rem;border-top:1px solid var(--border);"><span class="{scls}">{s.strike}{cp}</span></div>')
    parts.append('</div>')
    st.markdown(''.join(parts), unsafe_allow_html=True)


def render_cross_monitor(state):
    sc = "var(--green)" if state.current_spread > 0 else "var(--red)"
    dp = min(100, (state.max_divergence / 10.0) * 100)
    dc = "var(--gold)" if state.is_diverged_enough else "var(--t3)"
    if "VALID" in state.status: scls = "color:var(--green)"
    elif state.status == "READY": scls = "color:var(--gold)"
    elif "INVALID" in state.status: scls = "color:var(--red)"
    else: scls = "color:var(--t2)"
    st.markdown(f"""<div class="prophet-card">
    <div class="card-label">8 / 50 EMA CROSS MONITOR — ES 1-MIN</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;margin-top:1rem;">
    <div><div class="card-sub">Spread</div><div style="font-family:JetBrains Mono;font-size:1.4rem;font-weight:700;color:{sc};">{state.current_spread:+.1f}</div></div>
    <div><div class="card-sub">Max Div</div><div style="font-family:JetBrains Mono;font-size:1.4rem;font-weight:700;color:{dc};">{state.max_divergence:.1f}</div>
    <div class="risk-bar"><div class="risk-fill {'risk-clear' if state.is_diverged_enough else 'risk-active'}" style="width:{dp}%;"></div></div></div>
    <div><div class="card-sub">Status</div><div style="{scls};font-family:Sora;font-size:1rem;font-weight:700;">{state.status}</div></div>
    </div><div style="margin-top:0.8rem;padding-top:0.6rem;border-top:1px solid var(--border);"><div class="card-sub">{state.status_detail}</div></div></div>""", unsafe_allow_html=True)


def render_prop_firm(risk):
    rc = {"CLEAR":"risk-clear","ACTIVE":"risk-active","CAUTION":"risk-caution","DANGER":"risk-danger","LIMIT HIT":"risk-danger"}
    st.markdown(f"""<div class="prophet-card">
    <div class="card-label">THE FUTURES DESK — RISK</div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;margin-top:0.8rem;">
    <div><div class="card-sub">Max</div><div style="font-family:JetBrains Mono;font-size:1rem;">{risk.max_es} ES / {risk.max_mes} MES</div></div>
    <div><div class="card-sub">Daily Limit</div><div style="font-family:JetBrains Mono;font-size:1rem;color:var(--red);">${risk.daily_loss_limit:,.0f}</div></div>
    <div><div class="card-sub">Risk</div><div style="font-family:JetBrains Mono;font-size:1rem;color:{'var(--green)' if risk.risk_pct < 50 else 'var(--red)'};">{risk.risk_pct:.0f}%</div>
    <div class="risk-bar"><div class="risk-fill {rc.get(risk.risk_status,'risk-active')}" style="width:{risk.risk_pct}%;"></div></div></div></div></div>""", unsafe_allow_html=True)


def render_channel_card(vals, label="ES"):
    ae = f"{vals['asc_extreme']:,.2f}" if vals.get('asc_extreme') else "—"
    de = f"{vals['desc_extreme']:,.2f}" if vals.get('desc_extreme') else "—"
    st.markdown(f"""<div class="prophet-card">
    <div class="card-label">CHANNEL LEVELS — {label}</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:0.8rem;">
    <div style="border-left:3px solid var(--green);padding-left:1rem;"><div class="card-label" style="color:var(--green);">ASCENDING</div>
    <div style="display:flex;justify-content:space-between;margin-top:0.3rem;"><span class="card-sub">Extreme</span><span style="font-family:JetBrains Mono;color:rgba(0,232,143,0.4);font-size:0.85rem;">{ae}</span></div>
    <div style="display:flex;justify-content:space-between;"><span class="card-sub">Ceiling</span><span style="font-family:JetBrains Mono;color:var(--green);font-size:0.95rem;font-weight:600;">{vals['asc_ceiling']:,.2f}</span></div>
    <div style="display:flex;justify-content:space-between;"><span class="card-sub">Floor</span><span style="font-family:JetBrains Mono;color:var(--green);font-size:0.95rem;font-weight:600;">{vals['asc_floor']:,.2f}</span></div></div>
    <div style="border-left:3px solid var(--red);padding-left:1rem;"><div class="card-label" style="color:var(--red);">DESCENDING</div>
    <div style="display:flex;justify-content:space-between;margin-top:0.3rem;"><span class="card-sub">Ceiling</span><span style="font-family:JetBrains Mono;color:var(--red);font-size:0.95rem;font-weight:600;">{vals['desc_ceiling']:,.2f}</span></div>
    <div style="display:flex;justify-content:space-between;"><span class="card-sub">Floor</span><span style="font-family:JetBrains Mono;color:var(--red);font-size:0.95rem;font-weight:600;">{vals['desc_floor']:,.2f}</span></div>
    <div style="display:flex;justify-content:space-between;"><span class="card-sub">Extreme</span><span style="font-family:JetBrains Mono;color:rgba(255,68,102,0.4);font-size:0.85rem;">{de}</span></div></div>
    </div></div>""", unsafe_allow_html=True)


def fmt_hour(h, m):
    if h == 0: return f"12:{m:02d} AM"
    if h < 12: return f"{h}:{m:02d} AM"
    if h == 12: return f"12:{m:02d} PM"
    return f"{h-12}:{m:02d} PM"


def make_projection_table(channels, target_date, times_list, offset=0):
    if not times_list:
        return pd.DataFrame()
    rows = []
    for label, t in times_list:
        target_t = CT.localize(datetime.combine(target_date, t))
        vals = get_channel_values_at_time(channels, target_t)
        rows.append({"Time (CT)": label, "Asc Ceil": round(vals["asc_ceiling"] - offset, 2), "Asc Floor": round(vals["asc_floor"] - offset, 2), "Desc Ceil": round(vals["desc_ceiling"] - offset, 2), "Desc Floor": round(vals["desc_floor"] - offset, 2)})
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    inject_css()
    render_hero()

    # Session state defaults
    defs = {"lb":0.0,"lb_h":13,"lb_m":30,"hr":0.0,"hr_h":14,"hr_m":0,"hw":0.0,"hw_h":13,"hw_m":0,"lw":0.0,"lw_h":14,"lw_m":30,"offset_input":45.0,"auto_detected":False,"sim_price":0.0,"sim_es":0.0}
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

        auto_col1, auto_col2 = st.columns([1, 1])
        with auto_col1:
            if st.button("🔍 AUTO-DETECT", use_container_width=True):
                with st.spinner("Fetching..."):
                    df_1m, used_date = fetch_afternoon_1min(trading_date)
                    df_30m, used_date_30 = fetch_afternoon_30min(trading_date)
                    actual_date = used_date or used_date_30
                    if not df_1m.empty or not df_30m.empty:
                        detected = auto_detect_anchors(df_1m, df_30m)
                        if detected:
                            for key, ap in [("lb", detected['lb']), ("hr", detected['hr']), ("hw", detected['hw']), ("lw", detected['lw'])]:
                                st.session_state[key] = ap.price
                                st.session_state[f"{key}_h"] = ap.timestamp.hour
                                st.session_state[f"{key}_m"] = ap.timestamp.minute
                            if actual_date:
                                st.session_state["anchor_date"] = actual_date.isoformat()
                            st.session_state["auto_detected"] = True
                            st.success(f"Detected from {actual_date.strftime('%b %d') if actual_date else 'data'}")
                            st.rerun()
                        else:
                            st.warning("Could not detect. Enter manually.")
                    else:
                        st.warning("No data available.")
        with auto_col2:
            if st.button("🔄 REFRESH", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        if st.session_state.get("auto_detected"):
            st.info("Auto-detected. Verify and adjust if needed.")

        st.markdown('<div class="card-label" style="margin:0.5rem 0;">12-3 PM ANCHORS (ES)</div>', unsafe_allow_html=True)

        for label, key in [("Lowest Bounce", "lb"), ("Highest Rejection", "hr"), ("Highest Wick", "hw"), ("Lowest Wick", "lw")]:
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1: st.number_input(label, format="%.2f", key=key)
            with c2: st.number_input(f"{key.upper()} Hr", min_value=12, max_value=15, key=f"{key}_h")
            with c3: st.number_input(f"{key.upper()} Min", min_value=0, max_value=59, key=f"{key}_m")

        auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)

    # ─── FETCH DATA ───
    man_lb, man_hr = st.session_state["lb"], st.session_state["hr"]
    man_hw, man_lw = st.session_state["hw"], st.session_state["lw"]
    man_lb_h, man_lb_m = st.session_state["lb_h"], st.session_state["lb_m"]
    man_hr_h, man_hr_m = st.session_state["hr_h"], st.session_state["hr_m"]
    man_hw_h, man_hw_m = st.session_state["hw_h"], st.session_state["hw_m"]
    man_lw_h, man_lw_m = st.session_state["lw_h"], st.session_state["lw_m"]
    offset = st.session_state["offset_input"]

    es_price, es_src = fetch_es_price()
    spx_price, spx_src = fetch_spx_price()
    session_mode = get_session_mode()
    es_1min = fetch_es_1min()

    render_live_bar(es_price, es_src, spx_price, spx_src, offset, session_mode)

    # ─── BUILD CHANNELS ───
    channels = None
    prior_date = trading_date - timedelta(days=1)
    while prior_date.weekday() >= 5:
        prior_date -= timedelta(days=1)

    # Use actual detected date if available (more accurate than calculated prior_date)
    anchor_date = prior_date
    if "anchor_date" in st.session_state and st.session_state["anchor_date"]:
        try:
            anchor_date = date.fromisoformat(st.session_state["anchor_date"])
        except Exception:
            anchor_date = prior_date

    if man_lb > 0 and man_hr > 0:
        try:
            channels = build_channels(
                AnchorPoint(man_lb, CT.localize(datetime.combine(anchor_date, dtime(man_lb_h, man_lb_m))), "Lowest Bounce"),
                AnchorPoint(man_hr, CT.localize(datetime.combine(anchor_date, dtime(man_hr_h, man_hr_m))), "Highest Rejection"),
                AnchorPoint(man_hw if man_hw > 0 else man_hr, CT.localize(datetime.combine(anchor_date, dtime(man_hw_h, man_hw_m))), "Highest Wick"),
                AnchorPoint(man_lw if man_lw > 0 else man_lb, CT.localize(datetime.combine(anchor_date, dtime(man_lw_h, man_lw_m))), "Lowest Wick"),
            )
        except Exception as e:
            st.error(f"Channel error: {e}")

    if channels is None:
        st.markdown('<div class="prophet-card" style="text-align:center;padding:2.5rem;"><div style="font-size:2.5rem;margin-bottom:0.5rem;">📝</div><div style="font-family:Sora;color:var(--gold);font-size:1.1rem;font-weight:700;">ENTER CHANNEL ANCHORS</div><div class="card-sub" style="margin-top:0.5rem;">Enter Lowest Bounce and Highest Rejection above to generate projections.</div></div>', unsafe_allow_html=True)
        return

    # ─── DAY TYPE INDICATOR ───
    if day_type_lower == "ascending":
        st.markdown('<div class="day-asc"><div class="card-label" style="color:rgba(0,232,143,0.5);">TODAY\'S CHANNEL</div><div style="font-family:Sora;font-size:1.4rem;font-weight:800;color:var(--green);">▲ ASCENDING DAY</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="day-desc"><div class="card-label" style="color:rgba(255,68,102,0.5);">TODAY\'S CHANNEL</div><div style="font-family:Sora;font-size:1.4rem;font-weight:800;color:var(--red);">▼ DESCENDING DAY</div></div>', unsafe_allow_html=True)

    now_ct = datetime.now(CT)
    es_vals = get_channel_values_at_time(channels, now_ct)
    asian_date = anchor_date

    # ─── TABS ───
    tab_asian, tab_rth, tab_proj = st.tabs(["🌏 ASIAN", "📈 RTH", "📊 PROJECTIONS"])

    # ═══ ASIAN ═══
    with tab_asian:
        asian_times = [(fmt_hour(h, m), dtime(h, m)) for h in range(17, 22) for m in (0, 30) if not (h == 21 and m == 30)]
        st.dataframe(make_projection_table(channels, asian_date, asian_times), use_container_width=True, hide_index=True)
        render_channel_card(es_vals, "ES NOW")

        is_hist = trading_date != date.today()
        if is_hist:
            st.markdown('<div class="card-label">SIMULATE ES PRICE</div>', unsafe_allow_html=True)
            asian_price = st.number_input("ES Price", format="%.2f", key="sim_es", label_visibility="collapsed")
        else:
            asian_price = es_price

        if asian_price > 0:
            assessment = assess_asian_session(asian_price, es_vals)
            st.markdown(f'<div class="prophet-card"><div class="card-label">POSITION — ES @ {asian_price:,.2f}</div><div style="font-family:Sora;font-size:1.1rem;font-weight:700;color:var(--teal);margin-top:0.5rem;">{assessment.zone_label}</div><div class="card-sub">Nearest: {assessment.nearest_line} ({assessment.nearest_distance:.2f} pts)</div></div>', unsafe_allow_html=True)
            for s in assessment.scenarios:
                render_scenario_card(s, current_price=asian_price)
            render_prop_firm(PropFirmRisk())

    # ═══ RTH ═══
    with tab_rth:
        nine_am = CT.localize(datetime.combine(trading_date, dtime(9, 0)))
        v9 = get_channel_values_at_time(channels, nine_am)
        s9 = convert_es_to_spx(v9, offset)
        ae_9 = f"{s9['asc_extreme']:,.2f}" if s9.get('asc_extreme') else "—"
        de_9 = f"{s9['desc_extreme']:,.2f}" if s9.get('desc_extreme') else "—"

        st.markdown(
            f'<div class="prophet-card gold-card">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<div class="card-label" style="color:var(--gold);font-size:0.8rem;">9:00 AM CT — ENTRY LEVELS (SPX)</div>'
            f'<span class="status-badge" style="background:rgba(255,215,0,0.08);border:1px solid rgba(255,215,0,0.2);color:var(--gold);">INSTITUTIONAL OPEN</span></div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-top:1rem;">'
            f'<div style="border-left:3px solid var(--green);padding-left:1rem;"><div class="card-label" style="color:var(--green);">ASCENDING</div>'
            f'<div style="display:flex;justify-content:space-between;margin-top:0.3rem;"><span class="card-sub">Extreme</span><span style="font-family:JetBrains Mono;color:rgba(0,232,143,0.4);font-size:0.85rem;">{ae_9}</span></div>'
            f'<div style="display:flex;justify-content:space-between;"><span class="card-sub">Ceiling</span><span style="font-family:JetBrains Mono;color:var(--green);font-size:1.1rem;font-weight:700;">{s9["asc_ceiling"]:,.2f}</span></div>'
            f'<div style="display:flex;justify-content:space-between;"><span class="card-sub">Floor</span><span style="font-family:JetBrains Mono;color:var(--green);font-size:1.1rem;font-weight:700;">{s9["asc_floor"]:,.2f}</span></div></div>'
            f'<div style="border-left:3px solid var(--red);padding-left:1rem;"><div class="card-label" style="color:var(--red);">DESCENDING</div>'
            f'<div style="display:flex;justify-content:space-between;margin-top:0.3rem;"><span class="card-sub">Ceiling</span><span style="font-family:JetBrains Mono;color:var(--red);font-size:1.1rem;font-weight:700;">{s9["desc_ceiling"]:,.2f}</span></div>'
            f'<div style="display:flex;justify-content:space-between;"><span class="card-sub">Floor</span><span style="font-family:JetBrains Mono;color:var(--red);font-size:1.1rem;font-weight:700;">{s9["desc_floor"]:,.2f}</span></div>'
            f'<div style="display:flex;justify-content:space-between;"><span class="card-sub">Extreme</span><span style="font-family:JetBrains Mono;color:rgba(255,68,102,0.4);font-size:0.85rem;">{de_9}</span></div></div>'
            f'</div></div>', unsafe_allow_html=True)

        is_historical = trading_date != date.today()
        if is_historical:
            st.markdown('<div class="card-label" style="margin-top:0.5rem;">SIMULATE: SPX at 9 AM</div>', unsafe_allow_html=True)
            price_rth = st.number_input("SPX at 9 AM", format="%.2f", key="sim_price", label_visibility="collapsed")
        else:
            price_rth = spx_price if spx_price > 0 else (es_price - offset if es_price > 0 else 0)

        if price_rth > 0:
            rth_assess = assess_ascending_day(price_rth, s9) if day_type_lower == "ascending" else assess_descending_day(price_rth, s9)
            st.markdown(f'<div class="prophet-card"><div class="card-label">POSITION — SPX @ {price_rth:,.2f}</div><div style="font-family:Sora;font-size:1.1rem;font-weight:700;color:var(--teal);margin-top:0.5rem;">{rth_assess.zone_label}</div><div class="card-sub">Nearest: {rth_assess.nearest_line} ({rth_assess.nearest_distance:.2f} pts)</div></div>', unsafe_allow_html=True)
            for s in rth_assess.scenarios:
                render_scenario_card(s, trading_date, current_price=price_rth)

        rth_times = [("8:30", dtime(8,30)), ("★ 9:00", dtime(9,0)), ("9:30", dtime(9,30)), ("10:00", dtime(10,0)), ("10:30", dtime(10,30)), ("11:00", dtime(11,0)), ("11:30", dtime(11,30)), ("12:00", dtime(12,0)), ("12:30", dtime(12,30)), ("1:00", dtime(13,0))]
        st.markdown('<div class="card-label" style="margin-top:1rem;">RTH PROJECTIONS — SPX</div>', unsafe_allow_html=True)
        st.dataframe(make_projection_table(channels, trading_date, rth_times, offset), use_container_width=True, hide_index=True)

    # ═══ PROJECTIONS ═══
    with tab_proj:
        st.markdown('<div class="card-label">FULL ES PROJECTION TABLE</div>', unsafe_allow_html=True)
        eve_times = [(fmt_hour(h, m), dtime(h, m)) for h in range(17, 24) for m in (0, 30)]
        morn_times = [(fmt_hour(h, m), dtime(h, m)) for h in range(0, 14) for m in (0, 30)]
        eve_df = make_projection_table(channels, asian_date, eve_times)
        morn_df = make_projection_table(channels, trading_date, morn_times)
        full_df = pd.concat([eve_df, morn_df], ignore_index=True) if not eve_df.empty else morn_df
        st.dataframe(full_df, use_container_width=True, hide_index=True, height=600)

        v9w = get_channel_values_at_time(channels, CT.localize(datetime.combine(trading_date, dtime(9, 0))))
        aw, dw = abs(v9w['asc_ceiling'] - v9w['asc_floor']), abs(v9w['desc_ceiling'] - v9w['desc_floor'])
        st.markdown(f'<div class="prophet-card"><div class="card-label">CHANNEL WIDTHS AT 9 AM</div><div style="display:flex;gap:2rem;margin-top:0.5rem;"><div><span class="card-sub">Ascending: </span><span style="font-family:JetBrains Mono;color:var(--green);font-weight:600;">{aw:.2f} pts</span></div><div><span class="card-sub">Descending: </span><span style="font-family:JetBrains Mono;color:var(--red);font-weight:600;">{dw:.2f} pts</span></div></div></div>', unsafe_allow_html=True)

    # ─── CROSS MONITOR ───
    st.markdown('<div class="card-label" style="margin:1.5rem 0 0.5rem;">ENTRY CONFIRMATION</div>', unsafe_allow_html=True)
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
                    col = "var(--green)" if cx.cross_type == "bullish" else "var(--red)"
                    st.markdown(f'<div style="padding:0.4rem 0;border-bottom:1px solid var(--border);font-family:JetBrains Mono;font-size:0.78rem;"><span style="color:{col};">{d}</span> {cx.timestamp.strftime("%I:%M %p")} | Div: {cx.divergence:.1f} | {cx.nearest_hour} | {v}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="prophet-card"><div class="card-label">8/50 CROSS MONITOR</div><div class="card-sub">Waiting for ES 1-min data...</div></div>', unsafe_allow_html=True)

    # ─── DEBUG ───
    with st.expander("🔧 Anchor Debug"):
        for ap in channels.anchor_points:
            st.markdown(f'<div style="padding:0.3rem 0;font-family:JetBrains Mono;font-size:0.8rem;"><span style="color:var(--teal);">{ap.label}</span> | {ap.price:,.2f} | {ap.timestamp.strftime("%b %d %Y, %I:%M %p CT")}</div>', unsafe_allow_html=True)
        test_t = CT.localize(datetime.combine(trading_date, dtime(9, 0)))
        tb = count_blocks(channels.anchor_points[0].timestamp, test_t)
        st.markdown(f'<div style="color:var(--gold);font-family:JetBrains Mono;font-size:0.75rem;">Blocks to 9 AM = {tb:.0f} | Δ = {SLOPE*tb:.2f} pts</div>', unsafe_allow_html=True)

    st.markdown('<div style="text-align:center;padding:1.5rem 0 1rem;margin-top:1.5rem;border-top:1px solid var(--border);"><div style="font-family:Sora;font-size:0.7rem;color:var(--t3);letter-spacing:0.1em;">SPX PROPHET — NEXT GEN | BUILT FOR PRECISION</div></div>', unsafe_allow_html=True)

    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()

if __name__ == "__main__":
    main()
