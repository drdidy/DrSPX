import streamlit as st
import math
from datetime import datetime, date, time, timedelta

SLOPE = 0.475  # pts / 30-min block

# ---------- utilities ----------

def half_hour_times():
    return [time(h, m) for h in range(24) for m in (0, 30)]

def fmt_t(t: time) -> str:
    return t.strftime("%H:%M")

def to_time(s: str) -> time:
    h, m = map(int, s.split(":"))
    return time(h, m)

def parse_dt_from_date_time(d: date, t: time) -> datetime:
    return datetime.combine(d, t)

def blocks_between(t1: datetime, t2: datetime) -> int:
    if t2 <= t1:
        return 0
    blocks = 0
    cur = t1
    while cur < t2:
        nxt = cur + timedelta(minutes=30)
        if not (16 <= cur.hour < 17):  # skip maintenance hour
            blocks += 1
        cur = nxt
    return blocks

def project_from_anchor(anchor_price, anchor_time, target_time, sign):
    b = blocks_between(anchor_time, target_time)
    return anchor_price + sign * SLOPE * b

def calc_T(hours_left):      # convert hours → year fraction
    return max(hours_left, 0.05) / (24 * 365)

def hours_until_close(now_dt):
    close = now_dt.replace(hour=15, minute=15, second=0, microsecond=0)
    delta = (close - now_dt).total_seconds() / 3600
    return max(delta, 0.1)

# ---------- Black-Scholes ----------

def N(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))

def bs_call(S, K, T, r, v):
    if T <= 0 or v <= 0: return max(S - K, 0)
    d1 = (math.log(S / K) + (r + 0.5*v**2)*T) / (v*math.sqrt(T))
    d2 = d1 - v*math.sqrt(T)
    return S*N(d1) - K*math.exp(-r*T)*N(d2)

def bs_put(S, K, T, r, v):
    if T <= 0 or v <= 0: return max(K - S, 0)
    d1 = (math.log(S / K) + (r + 0.5*v**2)*T) / (v*math.sqrt(T))
    d2 = d1 - v*math.sqrt(T)
    return K*math.exp(-r*T)*N(-d2) - S*N(-d1)

def iv_for_strike(curve, strike, atm):
    if not curve: return atm
    s = str(int(strike))
    if s in curve: return curve[s]
    nearest = min(curve.keys(), key=lambda k: abs(int(k) - strike))
    return curve[nearest]

# ---------- state helpers ----------

def init_state():
    ss = st.session_state
    ss.setdefault("weekly_segments", [])
    ss.setdefault("daily_compass", {})
    ss.setdefault("signals", [])
    ss.setdefault("iv_snapshot", {})

# ---------- weekly rails ----------

def get_weekly_rails_at(dt_obj):
    ss = st.session_state
    if not ss.weekly_segments: return None, None
    active = None
    for seg in ss.weekly_segments:
        first_anchor = min(datetime.fromisoformat(seg["sky_time"]),
                           datetime.fromisoformat(seg["base_time"]))
        if first_anchor <= dt_obj:
            if active is None or first_anchor > datetime.fromisoformat(active["sky_time"]):
                active = seg
    if active is None: return None, None
    sign = 1 if active["direction"] == "up" else -1
    sky = project_from_anchor(active["sky_price"],
                              datetime.fromisoformat(active["sky_time"]),
                              dt_obj, sign)
    base = project_from_anchor(active["base_price"],
                               datetime.fromisoformat(active["base_time"]),
                               dt_obj, sign)
    return sky, base

def auto_update_signals(spot, now_dt):
    ss = st.session_state
    sky, base = get_weekly_rails_at(now_dt)
    if sky is None: return
    for s in ss.signals:
        if s["status"] != "active": continue
        if s["type"] == "long" and spot >= sky:
            s["status"] = "completed"; s["completed_at"] = now_dt.isoformat()
        if s["type"] == "short" and spot <= base:
            s["status"] = "completed"; s["completed_at"] = now_dt.isoformat()

# ---------- pages ----------

def page_weekly_setup():
    st.header("Weekly Setup")
    init_state(); ss = st.session_state

    st.caption("Separate anchors for Skyline and Baseline (each 30-min slot).")
    week_date = st.date_input("Anchor date", value=date.today())

    c1, c2 = st.columns(2)
    with c1:
        sky_price = st.number_input("Skyline anchor price", value=6880.0)
        sky_time = st.selectbox("Skyline anchor time", [fmt_t(t) for t in half_hour_times()], index=17)
    with c2:
        base_price = st.number_input("Baseline anchor price", value=6820.0)
        base_time = st.selectbox("Baseline anchor time", [fmt_t(t) for t in half_hour_times()], index=19)

    direction = st.selectbox("Weekly direction", ["up", "down"])

    if st.button("Save weekly segment"):
        seg = {
            "name": f"Seg {len(ss.weekly_segments)+1}",
            "sky_time": parse_dt_from_date_time(week_date, to_time(sky_time)).isoformat(timespec="minutes"),
            "sky_price": sky_price,
            "base_time": parse_dt_from_date_time(week_date, to_time(base_time)).isoformat(timespec="minutes"),
            "base_price": base_price,
            "direction": direction
        }
        ss.weekly_segments.append(seg)

    if ss.weekly_segments:
        st.subheader("Weekly Segments")
        st.table(ss.weekly_segments)

def page_daily_compass():
    st.header("Daily Compass & Signals")
    init_state(); ss = st.session_state

    trade_date = st.date_input("Trading date", value=date.today())

    c1, c2 = st.columns(2)
    with c1:
        prev_price = st.number_input("Prev-day pivot price", value=6850.0)
        prev_time = st.selectbox("Prev pivot time", [fmt_t(t) for t in half_hour_times()], index=29)
    with c2:
        new_price = st.number_input("New session pivot (5 PM)", value=6862.0)
        new_time = st.selectbox("New session pivot time", [fmt_t(t) for t in half_hour_times()], index=34)

    if st.button("Generate Lines"):
        ref_dt = parse_dt_from_date_time(trade_date, time(8,30))
        pprev = parse_dt_from_date_time(trade_date - timedelta(days=1), to_time(prev_time))
        pnew  = parse_dt_from_date_time(trade_date - timedelta(days=1), to_time(new_time))
        up1 = project_from_anchor(prev_price, pprev, ref_dt, 1)
        dn1 = project_from_anchor(prev_price, pprev, ref_dt, -1)
        up2 = project_from_anchor(new_price, pnew, ref_dt, 1)
        dn2 = project_from_anchor(new_price, pnew, ref_dt, -1)
        lvls = sorted([up1, dn1, up2, dn2], reverse=True)
        ss.daily_compass = {"date": trade_date.isoformat(),
                            "lines": {"outer_sky":lvls[0],"inner_sky":lvls[1],
                                      "inner_ground":lvls[2],"outer_ground":lvls[3]}}
    if ss.daily_compass:
        l = ss.daily_compass["lines"]
        st.table({"Line":["Outer Sky","Inner Sky","Inner Ground","Outer Ground"],
                  "Level":[round(l["outer_sky"],2),round(l["inner_sky"],2),
                           round(l["inner_ground"],2),round(l["outer_ground"],2)],
                  "Role":["Ctx","Sell zone","Buy zone","Ctx"]})

    st.subheader("Signal Entry")
    sig_type = st.selectbox("Signal",["None","Long from Inner Ground","Short from Inner Sky"])
    trig_time = st.selectbox("Trigger time",[fmt_t(t) for t in half_hour_times()],index=17)
    if st.button("Add Signal") and sig_type!="None":
        sig={"date":trade_date.isoformat(),"trigger_time":trig_time,"status":"active"}
        if sig_type.startswith("Long"): sig.update({"type":"long","from":"Inner Ground","to":"Skyline"})
        else: sig.update({"type":"short","from":"Inner Sky","to":"Baseline"})
        ss.signals.append(sig)
    if ss.signals: st.table(ss.signals)

def page_0dte_lab():
    st.header("0 DTE Options Lab")
    init_state(); ss = st.session_state

    # IV snapshot
    st.subheader("IV Snapshot")
    c1,c2=st.columns(2)
    with c1:
        snap_date=st.date_input("Snapshot date",value=date.today())
        spot=st.number_input("Spot price now",value=float(ss.iv_snapshot.get("spot",6720)))
        atm_iv=st.number_input("ATM IV (%)",value=float(ss.iv_snapshot.get("atm_iv",20)))
    with c2:
        rate=st.number_input("Risk-free rate (%)",value=float(ss.iv_snapshot.get("rate",4.9)))
        iv_text=st.text_area("Strike:IV%",value=ss.iv_snapshot.get("raw_text",""))
    if st.button("Save Snapshot"):
        iv_curve={}
        for line in iv_text.splitlines():
            if ":" in line:
                k,v=line.split(":"); iv_curve[k.strip()]=float(v.strip())/100
        ss.iv_snapshot={"date":snap_date.isoformat(),"spot":spot,"atm_iv":atm_iv/100,
                        "rate":rate/100,"iv_curve":iv_curve,"raw_text":iv_text}

    if not ss.daily_compass or not ss.iv_snapshot:
        st.info("Need Daily Compass + IV Snapshot first."); return

    # current time
    st.subheader("Current Time")
    cur_date=st.date_input("Current date",value=date.fromisoformat(ss.daily_compass["date"]))
    cur_time=st.selectbox("Time slot",[fmt_t(t) for t in half_hour_times()],index=17)
    now_dt=parse_dt_from_date_time(cur_date,to_time(cur_time))
    auto_update_signals(spot,now_dt)

    # weekly rails
    sky,base=get_weekly_rails_at(now_dt)
    if not sky:
        st.warning("Define weekly segment first."); return
    st.table({"Name":["Skyline","Baseline"],
              "Level":[round(sky,2),round(base,2)],
              "Dist from spot":[round(sky-spot,2),round(spot-base,2)]})

    hrs_left=st.number_input("Hours left until expiry",value=float(round(hours_until_close(now_dt),2)))
    T=calc_T(hrs_left)

    # signal context
    act=[s for s in ss.signals if s["status"]=="active"]
    sig=act[-1] if act else None
    if sig: st.write("Active signal:",sig)
    else: st.info("No active signal — manual mode.")

    iv_curve=ss.iv_snapshot["iv_curve"]; atm=ss.iv_snapshot["atm_iv"]; r=ss.iv_snapshot["rate"]

    if sig and sig["type"]=="long":
        opt_type="call"; tgt,opp=sky,base
        lbl_tgt,lbl_opp="If Skyline hits","If Baseline hits"
    elif sig and sig["type"]=="short":
        opt_type="put"; tgt,opp=base,sky
        lbl_tgt,lbl_opp="If Baseline hits","If Skyline hits"
    else:
        opt_type=st.selectbox("Option type",["call","put"])
        tgt=st.number_input("Target SPX",value=spot+30)
        opp=st.number_input("Opposite SPX",value=spot-30)
        lbl_tgt,lbl_opp="If target hits","If opposite hits"

    # contracts
    strikes=st.text_input("Strikes (comma separated)")
    if st.button("Evaluate") and strikes:
        rows=[]
        for s_str in strikes.split(","):
            try: K=float(s_str.strip())
            except: continue
            v=iv_for_strike(iv_curve,K,atm)
            if opt_type=="call":
                now=bs_call(spot,K,T,r,v); t=bs_call(tgt,K,T,r,v); o=bs_call(opp,K,T,r,v)
            else:
                now=bs_put(spot,K,T,r,v); t=bs_put(tgt,K,T,r,v); o=bs_put(opp,K,T,r,v)
            if now<=0: continue
            rows.append({"Strike":K,"Type":opt_type,"Now":round(now,2),
                         lbl_tgt:round(t,2),lbl_opp:round(o,2),
                         "%"+lbl_tgt:round((t-now)/now*100,1),
                         "%"+lbl_opp:round((o-now)/now*100,1)})
        if rows: st.table(rows)

# ---------- main ----------

def main():
    init_state()
    page=st.sidebar.selectbox("Page",["Weekly Setup","Daily Compass","0 DTE Lab"])
    if page=="Weekly Setup": page_weekly_setup()
    elif page=="Daily Compass": page_daily_compass()
    else: page_0dte_lab()

if __name__=="__main__":
    main()