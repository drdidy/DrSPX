# Dr Didy Forecast  – v1.4.3
# (mobile-friendly CSS, optional delta charts, no “Done!” banner)

import json, base64, altair as alt
from datetime import datetime, date, time, timedelta
from copy import deepcopy
import pandas as pd
import streamlit as st

# ───────────────────── CONSTANTS & DEFAULTS ───────────────────────────────────
PAGE_TITLE, PAGE_ICON, LAYOUT, SIDEBAR = "Dr Didy Forecast", "📈", "wide", "expanded"
VERSION = "1.4.3"
FIXED_CL_SLOPE = -0.5250

BASE_SLOPES = {
    "SPX_HIGH": -0.2792, "SPX_CLOSE": -0.2792, "SPX_LOW": -0.2792,
    "TSLA": -0.1508, "NVDA": -0.0485, "AAPL": -0.075, "MSFT": -0.1964,
    "AMZN": -0.0782, "GOOGL": -0.0485,
}
STRATS = {k: deepcopy(BASE_SLOPES) for k in ["Mon/Wed/Fri", "Tuesday", "Thursday"]}

ICONS = {"SPX": "🧭", "TSLA": "🚗", "NVDA": "🧠", "AAPL": "🍎",
         "MSFT": "🪟", "AMZN": "📦", "GOOGL": "🔍"}
CB = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948", "#af7aa1"]

# ───────────────────── INITIAL SESSION STATE ──────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.update(theme="Light",
                            slopes=deepcopy(BASE_SLOPES),
                            presets={}, mobile=False)

# restore state from query-string
q = st.query_params
if q.get("s"):
    try:
        st.session_state.slopes.update(json.loads(base64.b64decode(q["s"][0]).decode()))
    except Exception:
        pass

# ────────────────────────── PAGE CONFIG ───────────────────────────────────────
st.set_page_config(PAGE_TITLE, PAGE_ICON, LAYOUT, initial_sidebar_state=SIDEBAR)

# ───────────────────────────── CSS ────────────────────────────────────────────
GRADIENT = "linear-gradient(90deg,#0062E6 0%,#33AEFF 100%)"
COMMON_CSS = f"""
<style>
html,body{{font-family:'Inter',sans-serif}}
:root{{--radius:8px;--shadow:0 4px 12px rgba(0,0,0,.06)}}

.hdr{{background:{GRADIENT};color:#fff;padding:1rem;border-radius:var(--radius);
      box-shadow:var(--shadow);margin-bottom:1rem}}
.cards{{display:flex;gap:1rem;overflow-x:auto;margin-bottom:1rem}}
.card{{flex:1;min-width:160px;background:var(--card-bg);border-radius:var(--radius);
       padding:1rem;display:flex;align-items:center;transition:.2s;box-shadow:var(--shadow)}}
.card:hover{{transform:translateY(-2px);box-shadow:0 8px 18px rgba(0,0,0,.12)}}
.ic{{font-size:1.8rem;margin-right:.5rem}} .ttl{{font-size:.85rem;opacity:.7}}
.val{{font-size:1.25rem;font-weight:700}}
body.light{{--card-bg:#f5f5f5}} body.dark{{--card-bg:#1e293b;background:#0f172a;color:#e2e8f0}}
body.dark .hdr{{background:linear-gradient(90deg,#3677FF 0%,#7695FF 100%)}}

/* mobile tweaks */
@media (max-width:480px){{
  .hdr{{padding:.6rem 1rem}}
  .card{{padding:.6rem;min-width:120px}}
  .val{{font-size:1.1rem}}
  body{{padding-bottom:80px}}  /* Streamlit Cloud bar */
}}
</style>
"""
st.markdown(COMMON_CSS, unsafe_allow_html=True)

# switch theme class
st.session_state.theme = st.sidebar.radio(
    "🎨 Theme", ["Light", "Dark"],
    index=0 if st.session_state.theme == "Light" else 1
)
st.markdown(f"<body class='{st.session_state.theme.lower()}'>", unsafe_allow_html=True)

# ───────────────────────── SIDEBAR CONTROLS ───────────────────────────────────
fcast_date = st.sidebar.date_input("Forecast Date", date.today() + timedelta(days=1))
weekday = fcast_date.weekday()
day_grp = "Tuesday" if weekday == 1 else "Thursday" if weekday == 3 else "Mon/Wed/Fri"

st.session_state.mobile = st.sidebar.checkbox("📱 Mobile mode", st.session_state.mobile)

with st.sidebar.expander("📉 Slopes"):
    for k, v in st.session_state.slopes.items():
        st.session_state.slopes[k] = st.slider(k, -1.0, 1.0, v, 0.0001)

with st.sidebar.expander("💾 Presets"):
    pn = st.text_input("Preset name")
    if st.button("Save current"):
        st.session_state.presets[pn] = deepcopy(st.session_state.slopes)
    if st.session_state.presets:
        sel = st.selectbox("Load preset", list(st.session_state.presets))
        if st.button("Load"):
            st.session_state.slopes.update(st.session_state.presets[sel])

# share-link suffix
enc = base64.b64encode(json.dumps(st.session_state.slopes).encode()).decode()
st.sidebar.text_input("🔗 Share-link suffix", f"?s={enc}", disabled=True)

# ──────────────────────── TIME & BLOCK HELPERS ────────────────────────────────
def timeslots():
    start = datetime(2025, 1, 1, 7, 30)
    return [(start + timedelta(minutes=30*i)).strftime("%H:%M") for i in range(15)]

def blocks_spx(a, t):
    b = 0
    while a < t:
        if a.hour != 16:
            b += 1
        a += timedelta(minutes=30)
    return b

blk_stock = lambda a, t: max(0, int((t - a).total_seconds() // 1800))

def build_line(price, slope, anchor, fd, spx=True):
    rows = []
    for s in timeslots():
        h, m = map(int, s.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = blocks_spx(anchor, tgt) if spx else blk_stock(anchor, tgt)
        rows.append({"Time": s, "Projected": round(price + slope * b, 2)})
    return pd.DataFrame(rows)

def build_fan(price, slope, anchor, fd, spx=True):
    rows = []
    for s in timeslots():
        h, m = map(int, s.split(":"))
        tgt = datetime.combine(fd, time(h, m))
        b = blocks_spx(anchor, tgt) if spx else blk_stock(anchor, tgt)
        rows.append({"Time": s,
                     "Entry": round(price + slope * b, 2),
                     "Exit":  round(price - slope * b, 2)})
    return pd.DataFrame(rows)

def delta_chart(df, col, field="Projected"):
    base = df[field].iloc[0]
    ddf = df.assign(delta=df[field] - base)
    return alt.Chart(ddf).mark_line(color=col).encode(
        x="Time", y=alt.Y("delta:Q", title="Δ vs anchor"), tooltip=["Time", field]
    )

# responsive cols
def cols(n): return (st,) if st.session_state.mobile else st.columns(n)

# ───────────────────────── HEADER & TABS ──────────────────────────────────────
st.markdown(f'<div class="hdr"><h2>{PAGE_ICON} Dr Didy Forecast</h2></div>', unsafe_allow_html=True)
tabs = st.tabs([f"{ICONS[t]} {t}" for t in ICONS])

# ─────────────────────────── SPX TAB ──────────────────────────────────────────
with tabs[0]:
    st.write(f"### {ICONS['SPX']} SPX Forecast ({day_grp})")
    c1, c2, c3 = cols(3)
    hp, ht = c1.number_input("High Price", 6185.8), c1.time_input("High Time", time(11, 30))
    cp, ct = c2.number_input("Close Price", 6170.2), c2.time_input("Close Time", time(15, 0))
    lp, lt = c3.number_input("Low Price", 6130.4),  c3.time_input("Low Time",  time(13, 30))

    # Tuesday UI
    if day_grp == "Tuesday":
        st.subheader("Overnight Contract Line")
        o1, o2 = cols(2)
        cl1_t, cl1_p = o1.time_input("Low-1 Time", time(2)),  o1.number_input("Low-1 Price", 6100.0)
        cl2_t, cl2_p = o2.time_input("Low-2 Time", time(3, 30)), o2.number_input("Low-2 Price", 6120.0)
        cl_t, cl_p = st.time_input("Contract Low Time", time(7, 30)), st.number_input("Contract Low Price", 5.0)

    # Thursday UI
    if day_grp == "Thursday":
        st.subheader("Overnight Contract Line")
        p1, p2 = cols(2)
        ol1_t, ol1_p = p1.time_input("Low-1 Time", time(2)),  p1.number_input("Low-1 Price", 6100.0)
        ol2_t, ol2_p = p2.time_input("Low-2 Time", time(3, 30)), p2.number_input("Low-2 Price", 6120.0)
        b_t, b_p = st.time_input("Bounce Low Time", time(7, 30)), st.number_input("Bounce Low Price", 6100.0)

    if st.button("Run Forecast"):
        prog = st.progress(0.0)
        ah, ac, al = [datetime.combine(fcast_date - timedelta(days=1), t) for t in (ht, ct, lt)]

        # Tuesday logic
        if day_grp == "Tuesday":
            dt1, dt2 = datetime.combine(fcast_date - timedelta(days=1), cl1_t), datetime.combine(fcast_date - timedelta(days=1), cl2_t)
            alt_slope = (cl2_p - cl1_p) / (blocks_spx(dt1, dt2) or 1)

            st.write("#### Contract Line (2-pt)")
            df = build_line(cl1_p, alt_slope, dt1, fcast_date)
            st.dataframe(df, use_container_width=True)
            if st.toggle("👁️ Show chart", key="tue_contract", value=not st.session_state.mobile):
                st.altair_chart(delta_chart(df, CB[0]), use_container_width=True)
            prog.progress(0.4)

            st.write("#### Fixed SPX Line")
            df2 = build_line(cl_p, FIXED_CL_SLOPE, datetime.combine(fcast_date, cl_t), fcast_date)
            st.dataframe(df2, use_container_width=True)
            if st.toggle("👁️ Show chart", key="tue_fixed", value=False):
                st.altair_chart(delta_chart(df2, CB[1]), use_container_width=True)
            prog.progress(0.8)

        # Thursday logic
        elif day_grp == "Thursday":
            dt1, dt2 = datetime.combine(fcast_date - timedelta(days=1), ol1_t), datetime.combine(fcast_date - timedelta(days=1), ol2_t)
            alt_slope = (ol2_p - ol1_p) / (blocks_spx(dt1, dt2) or 1)

            st.write("#### Contract Line (2-pt)")
            df = build_line(ol1_p, alt_slope, dt1, fcast_date)
            st.dataframe(df, use_container_width=True)
            if st.toggle("👁️ Show chart", key="thu_contract", value=not st.session_state.mobile):
                st.altair_chart(delta_chart(df, CB[0]), use_container_width=True)
            prog.progress(0.5)

            st.write("#### Bounce-Low Line")
            df2 = build_line(b_p, st.session_state.slopes["SPX_LOW"],
                             datetime.combine(fcast_date - timedelta(days=1), b_t), fcast_date)
            st.dataframe(df2, use_container_width=True)
            if st.toggle("👁️ Show chart", key="thu_bounce", value=False):
                st.altair_chart(delta_chart(df2, CB[1]), use_container_width=True)
            prog.progress(0.8)

        # Mon/Wed/Fri logic
        else:
            st.markdown('<div class="cards">', unsafe_allow_html=True)
            for t, v, ic in [("High", hp, "🔼"), ("Close", cp, "⏹️"), ("Low", lp, "🔽")]:
                st.markdown(f'<div class="card"><span class="ic">{ic}</span>'
                            f'<div><div class="ttl">{t} Anchor</div><div class="val">{v:.2f}</div></div></div>',
                            unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            for t, v, s, anc, col, key in [
                ("High", hp, "SPX_HIGH", ah, CB[0], "fan_high"),
                ("Close", cp, "SPX_CLOSE", ac, CB[1], "fan_close"),
                ("Low", lp, "SPX_LOW", al, CB[2], "fan_low")]:
                st.write(f"#### {t} Anchor Fan")
                df = build_fan(v, st.session_state.slopes[s], anc, fcast_date)
                st.dataframe(df, use_container_width=True)
                if st.toggle("👁️ Show chart", key=key, value=False):
                    base = df["Entry"].iloc[0]
                    ddf = df.assign(EntryΔ=df["Entry"] - base,
                                    ExitΔ=df["Exit"] - base)
                    ch = alt.Chart(ddf).transform_fold(["EntryΔ", "ExitΔ"]).mark_line().encode(
                        x="Time", y=alt.Y("value:Q", title="Δ vs anchor"), color="key:N")
                    st.altair_chart(ch, use_container_width=True)
            prog.progress(0.9)

        prog.empty()

# ───────────────────────── OTHER TICKER TABS ──────────────────────────────────
def stock_tab(idx, tic, col):
    with tabs[idx]:
        st.write(f"### {ICONS[tic]} {tic}")
        a, b = cols(2)
        lp, lt = a.number_input("Prev-day Low", key=f"{tic}lp"), a.time_input("Low Time", time(7, 30), key=f"{tic}lt")
        hp, ht = b.number_input("Prev-day High", key=f"{tic}hp"), b.time_input("High Time", time(7, 30), key=f"{tic}ht")
        if st.button("Generate", key=f"go{tic}"):
            low_anchor, high_anchor = datetime.combine(fcast_date, lt), datetime.combine(fcast_date, ht)
            df_low  = build_fan(lp, st.session_state.slopes[tic], low_anchor,  fcast_date, spx=False)
            df_high = build_fan(hp, st.session_state.slopes[tic], high_anchor, fcast_date, spx=False)
            st.dataframe(df_low, use_container_width=True)
            st.dataframe(df_high, use_container_width=True)
            if st.toggle("👁️ Show chart", key=f"{tic}_chart", value=False):
                d_low  = df_low.assign(EntryΔ=df_low["Entry"] - df_low["Entry"].iloc[0])
                d_high = df_high.assign(EntryΔ=df_high["Entry"] - df_high["Entry"].iloc[0])
                layer = alt.layer(
                    alt.Chart(d_low ).mark_line(strokeDash=[3, 3], color=col).encode(x="Time", y="EntryΔ"),
                    alt.Chart(d_high).mark_line(color=col).encode(x="Time", y="EntryΔ")
                )
                st.altair_chart(layer, use_container_width=True)

for i, (tic, col) in enumerate(zip(list(ICONS)[1:], CB[1:]), 1):
    stock_tab(i, tic, col)

# ───────────────────────── FOOTER ─────────────────────────────────────────────
st.markdown(f"<hr><center style='font-size:.8rem'>v{VERSION} • {datetime.now():%Y-%m-%d %H:%M:%S}</center>",
            unsafe_allow_html=True)