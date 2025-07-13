# Dr Didy SPX Forecast – v1.4.7
#
# cosmetic patch: colourful, larger anchor-cards

import json, base64, streamlit as st
from datetime import datetime, date, time, timedelta
from copy import deepcopy
import pandas as pd

# ——— business constants unchanged —————————————————————————
PAGE_TITLE, PAGE_ICON = "DRSPX Forecast", "📈"
VERSION  = "1.4.7"
FIXED_CL_SLOPE = -0.5250
BASE_SLOPES = {...}                    #  ← keep same dict as before
ICONS      = {...}                    #  ← keep same dict as before
# ---------------------------------------------------------------------------

# ——— plain CSS re-skin ———————————————————————————————
CARD_CSS = """
<style>
/* base */
.cards{display:flex;gap:1rem;overflow-x:auto;margin-bottom:1rem}
.card{flex:1;min-width:220px;padding:1.4rem;border-radius:12px;
      display:flex;align-items:center;box-shadow:0 6px 18px rgba(0,0,0,.1)}
.ic  {width:3rem;height:3rem;border-radius:12px;
      display:flex;align-items:center;justify-content:center;
      font-size:1.9rem;color:#fff;margin-right:.85rem}
.ttl {font-size:.95rem;opacity:.75}
.val {font-size:2rem;font-weight:800;letter-spacing:-.5px}

/* colour themes */
.card.high {background:rgba(16,185,129,.12)}
.card.high .ic  {background:#10b981}
.card.close{background:rgba(59,130,246,.12)}
.card.close.ic  {background:#3b82f6}
.card.low  {background:rgba(239,68,68,.12)}
.card.low  .ic  {background:#ef4444}

/* dark mode adjust */
body.dark .card.high  {background:rgba(16,185,129,.2)}
body.dark .card.close {background:rgba(59,130,246,.2)}
body.dark .card.low   {background:rgba(239,68,68,.2)}

@media (max-width:480px){
  .card{min-width:180px;padding:1.1rem}
  .ic{width:2.6rem;height:2.6rem;font-size:1.6rem}
  .val{font-size:1.6rem}
}
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

# ——— helper to emit a coloured card ————————————————————
def coloured_card(kind:str, icon:str, title:str, value:float):
    html=f"""
    <div class="card {kind}">
      <div class="ic">{icon}</div>
      <div><div class="ttl">{title}</div><div class="val">{value:.2f}</div></div>
    </div>"""
    st.markdown(html, unsafe_allow_html=True)

# ========== everything else is identical to v1.4.6 ==========
# !! Replace the *three* old card lines in the SPX Mon/Wed/Fri block:

    st.markdown('<div class="cards">', unsafe_allow_html=True)
    coloured_card("high" , "▲", "High Anchor" , hp)
    coloured_card("close", "■", "Close Anchor", cp)
    coloured_card("low"  , "▼", "Low Anchor"  , lp)
    st.markdown('</div>', unsafe_allow_html=True)

# And in each stock tab (low / high cards) you can call:

    coloured_card("low" , "▼", "Low Anchor",  lp)
    coloured_card("high", "▲", "High Anchor", hp)

# ============================================================

# (Everything else – tables, slots, slopes – stays the same code you already have.)