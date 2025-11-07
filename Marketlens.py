import streamlit as st
import math
from datetime import datetime, date, time, timedelta

SLOPE = 0.475  # points per 30 min

# --------------- helpers ---------------

def init_state():
    ss = st.session_state
    ss.setdefault("weekly_segments", [])
    ss.setdefault("daily_compass", {})
    ss.setdefault("signals", [])
    ss.setdefault("iv_snapshot", {})

def half_hour_times():
    return [time(h, m) for h in range(24) for m in (0, 30)]

def fmt_t(t: time) -> str:
    return t.strftime("%H:%M")

def parse_dt_from_date_time(d: date, t: time) -> datetime:
    return datetime.combine(d, t)

def bs_call_price(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    N1 = 0.5 * (1 + math.erf(d1 / math.sqrt(2)))
    N2 = 0.5 * (1 + math.erf(d2 / math.sqrt(2)))
    return S * N1 - K * math.exp(-r * T) * N2

def bs_put_price(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0:
        return max(K - S, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    N1 = 0.5 * (1 + math.erf(-d1 / math.sqrt(2)))
    N2 = 0.5 * (1 + math.erf(-d2 / math.sqrt(2)))
    return K * math.exp(-r * T) * N2 - S * N1

def get_iv_for_strike(iv_curve, strike, atm_iv):
    if not iv_curve:
        return atm_iv
    s = str(int(strike))
    if s in iv_curve:
        return iv_curve[s]
    nearest = min(iv_curve.keys(), key=lambda k: abs(int(k) - strike))
    return iv_curve[nearest]

def blocks_between(t1: datetime, t2: datetime) -> int:
    if t2 <= t1:
        return 0
    blocks = 0
    current = t1
    while current < t2:
        nxt = current + timedelta(minutes=30)
        if not (16 <= current.hour < 17):
            blocks += 1
        current = nxt
    return blocks

def project_from_anchor(anchor_price, anchor_time: datetime, target_time: datetime, direction_sign: int):
    b = blocks_between(anchor_time, target_time)
    return anchor_price + direction_sign * SLOPE * b

def get_weekly_rails_at(dt_obj: datetime):
    ss = st.session_state
    if not ss.weekly_segments:
        return None, None
    active = None
    for seg in ss.weekly_segments:
        stime = datetime.fromisoformat(seg["start_time"])
        if stime <= dt_obj:
            if active is None or stime > datetime.fromisoformat(active["start_time"]):
                active = seg
    if active is None:
        return None, None
    stime = datetime.fromisoformat(active["start_time"])
    sign = 1 if active["direction"] == "up" else -1
    sky = project_from_anchor(active["skyline_start"], stime, dt_obj, sign)
    base = project_from_anchor(active["baseline_start"], stime, dt_obj, sign)
    return sky, base

def auto_update_signals(current_spx, now_dt: datetime):
    ss = st.session_state
    sky, base = get_weekly_rails_at(now_dt)
    if sky is None or base is None:
        return
    for s in ss.signals:
        if s.get("status") != "active":
            continue
        if s["type"] == "long" and current_spx >= sky:
            s["status"] = "completed"
            s["completed_at"] = now_dt.isoformat()
        if s["type"] == "short" and current_spx <= base:
            s["status"] = "completed"
            s["completed_at"] = now_dt.isoformat()

def hours_until_close(now_dt: datetime) -> float:
    close = now_dt.replace(hour=15, minute=15, second=0, microsecond=0)
    delta_hrs = (close - now_dt).total_seconds() / 3600.0
    return max(delta_hrs, 0.1)

def calc_T(hours_left: float) -> float:
    return max(hours_left, 0.05) / (24.0 * 365.0)

# --------------- pages ---------------

def page_weekly_setup():
    st.header("Weekly Setup")

    init_state()
    ss = st.session_state

    st.caption("Set this once per weekly segment. No typing timestamps.")

    col1, col2 = st.columns(2)
    with col1:
        week_start_date = st.date_input("Segment start date", value=date.today())
        start_time_choice = st.selectbox(
            "Start time (30 min slots)",
            [fmt_t(t) for t in half_hour_times()],
            index=17  # 08:30 as a common start
        )
    with col2:
        direction = st.selectbox("Direction", ["up", "down"])
        sky_start = st.number_input("Skyline start price", value=6880.0)
        base_start = st.number_input("Baseline start price", value=6820.0)

    if st.button("Save weekly segment"):
        h, m = map(int, start_time_choice.split(":"))
        dt_start = parse_dt_from_date_time(week_start_date, time(h, m))
        ss.weekly_segments.append({
            "name": f"Seg {len(ss.weekly_segments)+1}",
            "start_time": dt_start.isoformat(timespec="minutes"),
            "skyline_start": sky_start,
            "baseline_start": base_start,
            "direction": direction
        })

    if ss.weekly_segments:
        st.subheader("Weekly segments")
        st.table(ss.weekly_segments)

def page_daily_compass():
    st.header("Daily Compass and Signals")

    init_state()
    ss = st.session_state

    st.caption("Pick pivots using only price and 30 min time slots.")

    trade_date = st.date_input("Trading date", value=date.today())

    col1, col2 = st.columns(2)
    with col1:
        pprev_price = st.number_input("Previous day last pivot price", value=6850.0)
        pprev_time_choice = st.selectbox(
            "Previous pivot time",
            [fmt_t(t) for t in half_hour_times()],
            index=29  # 14:30 default
        )
    with col2:
        pnew_price = st.number_input("New session pivot price (5 pm pivot)", value=6862.0)
        pnew_time_choice = st.selectbox(
            "New session pivot time",
            [fmt_t(t) for t in half_hour_times()],
            index=34  # 17:00 default
        )

    if st.button("Generate daily lines"):
        try:
            # use 08:30 of trade_date as reference
            ref_dt = parse_dt_from_date_time(trade_date, time(8, 30))

            pprev_h, pprev_m = map(int, pprev_time_choice.split(":"))
            pprev_dt = parse_dt_from_date_time(trade_date - timedelta(days=1), time(pprev_h, pprev_m))

            pnew_h, pnew_m = map(int, pnew_time_choice.split(":"))
            # pivot at 17:00 of previous calendar day for the new session start
            pnew_dt = parse_dt_from_date_time(trade_date - timedelta(days=1), time(pnew_h, pnew_m))

            up1 = project_from_anchor(pprev_price, pprev_dt, ref_dt, 1)
            dn1 = project_from_anchor(pprev_price, pprev_dt, ref_dt, -1)
            up2 = project_from_anchor(pnew_price, pnew_dt, ref_dt, 1)
            dn2 = project_from_anchor(pnew_price, pnew_dt, ref_dt, -1)

            levels = [up1, dn1, up2, dn2]
            sorted_levels = sorted(levels, reverse=True)

            lines = {
                "outer_sky": sorted_levels[0],
                "inner_sky": sorted_levels[1],
                "inner_ground": sorted_levels[2],
                "outer_ground": sorted_levels[3]
            }

            ss.daily_compass = {
                "date": trade_date.isoformat(),
                "p_prev": {"time": pprev_time_choice, "price": pprev_price},
                "p_new": {"time": pnew_time_choice, "price": pnew_price},
                "lines": lines
            }

        except Exception as e:
            st.error(f"Error generating lines: {e}")

    if ss.daily_compass:
        st.subheader("Daily compass at 08:30")
        lines = ss.daily_compass["lines"]
        st.table({
            "Line": ["Outer Sky", "Inner Sky", "Inner Ground", "Outer Ground"],
            "Level": [
                round(lines["outer_sky"], 2),
                round(lines["inner_sky"], 2),
                round(lines["inner_ground"], 2),
                round(lines["outer_ground"], 2)
            ],
            "Role": ["Context", "Sell zone", "Buy zone", "Context"],
            "Target": ["", "Baseline", "Skyline", ""]
        })

    st.subheader("Signal entry")

    sig_type = st.selectbox("Signal type", ["None", "Long from Inner Ground", "Short from Inner Sky"])
    trigger_time_choice = st.selectbox(
        "Signal trigger time",
        [fmt_t(t) for t in half_hour_times()],
        index=17  # default 08:30
    )

    if st.button("Add signal") and sig_type != "None" and ss.daily_compass:
        base = {
            "date": ss.daily_compass["date"],
            "trigger_time": trigger_time_choice,
            "status": "active"
        }
        if sig_type.startswith("Long"):
            base.update({"type": "long", "from_line": "Inner Ground", "to_rail": "Skyline"})
        else:
            base.update({"type": "short", "from_line": "Inner Sky", "to_rail": "Baseline"})
        ss.signals.append(base)

    if ss.signals:
        st.subheader("Signals")
        st.table(ss.signals)

def page_0dte_lab():
    st.header("0DTE Options Lab")

    init_state()
    ss = st.session_state

    st.subheader("Daily IV snapshot")

    col1, col2 = st.columns(2)
    with col1:
        snap_date = st.date_input(
            "Snapshot date",
            value=date.fromisoformat(ss.iv_snapshot.get("date", date.today().isoformat()))
            if ss.iv_snapshot.get("date") else date.today()
        )
        spot = st.number_input("Spot price now", value=float(ss.iv_snapshot.get("spot", 6720.0)))
        atm_iv = st.number_input("ATM IV (percent)", value=float(ss.iv_snapshot.get("atm_iv", 20.0)))
    with col2:
        rate = st.number_input("Risk free rate (percent)", value=float(ss.iv_snapshot.get("rate", 4.9)))
        iv_text = st.text_area(
            "Per strike IV (strike:iv%, one per line)",
            value=ss.iv_snapshot.get("raw_text", "")
        )

    if st.button("Save IV snapshot"):
        iv_curve = {}
        for line in iv_text.splitlines():
            if ":" in line:
                k, v = line.split(":")
                try:
                    iv_curve[k.strip()] = float(v.strip()) / 100.0
                except:
                    pass
        ss.iv_snapshot = {
            "date": snap_date.isoformat(),
            "spot": spot,
            "atm_iv": atm_iv / 100.0,
            "rate": rate / 100.0,
            "iv_curve": iv_curve,
            "raw_text": iv_text
        }

    if not ss.iv_snapshot:
        st.info("Enter and save IV snapshot to continue.")
        return

    if not ss.daily_compass:
        st.info("Set up the Daily Compass first.")
        return

    # current time using date + dropdown
    st.subheader("Current time")
    col_ct1, col_ct2 = st.columns(2)
    with col_ct1:
        cur_date = st.date_input(
            "Current date",
            value=date.fromisoformat(ss.daily_compass["date"])
        )
    with col_ct2:
        cur_time_choice = st.selectbox(
            "Current time (30 min slots)",
            [fmt_t(t) for t in half_hour_times()],
            index=17  # 08:30 default
        )

    h_now, m_now = map(int, cur_time_choice.split(":"))
    now_dt = parse_dt_from_date_time(cur_date, time(h_now, m_now))

    # update signals
    auto_update_signals(spot, now_dt)

    # weekly frame at now
    sky, base = get_weekly_rails_at(now_dt)
    if sky is None or base is None:
        st.info("Define weekly segments to see Skyline and Baseline.")
        return

    st.subheader("Weekly frame")
    st.table({
        "Name": ["Skyline", "Baseline"],
        "Level": [round(sky, 2), round(base, 2)],
        "Distance from spot": [round(sky - spot, 2), round(spot - base, 2)]
    })

    # time to expiry
    auto_hours = hours_until_close(now_dt)
    hours_left = st.number_input(
        "Hours left until expiry",
        value=float(round(auto_hours, 2))
    )
    T = calc_T(hours_left)

    # active signal
    st.subheader("Active signal")
    active_signals = [s for s in ss.signals if s["status"] == "active"]
    signal = active_signals[-1] if active_signals else None
    if signal:
        st.write(signal)
    else:
        st.write("No active signal. You can still test calls or puts.")

    iv_curve = ss.iv_snapshot["iv_curve"]
    atm_iv_val = ss.iv_snapshot["atm_iv"]
    rate_val = ss.iv_snapshot["rate"]

    # targets based on signal
    if signal and signal["type"] == "long":
        target_spx = sky
        opp_spx = base
        opt_type = "call"
        label_target = "If Skyline hits"
        label_opp = "If Baseline hits"
    elif signal and signal["type"] == "short":
        target_spx = base
        opp_spx = sky
        opt_type = "put"
        label_target = "If Baseline hits"
        label_opp = "If Skyline hits"
    else:
        opt_type = st.selectbox("Option type", ["call", "put"])
        target_spx = st.number_input("Target SPX", value=spot + 30.0)
        opp_spx = st.number_input("Opposite SPX", value=spot - 30.0)
        label_target = "If target hits"
        label_opp = "If opposite hits"

    st.subheader("Contract candidates")

    strikes_text = st.text_input("Strikes (comma separated)")

    if st.button("Evaluate contracts") and strikes_text:
        rows = []
        for s_str in strikes_text.split(","):
            s_str = s_str.strip()
            if not s_str:
                continue
            try:
                K = float(s_str)
            except:
                continue

            sigma = get_iv_for_strike(iv_curve, K, atm_iv_val)

            if opt_type == "call":
                now_price = bs_call_price(spot, K, T, rate_val, sigma)
                at_target = bs_call_price(target_spx, K, T, rate_val, sigma)
                at_opp = bs_call_price(opp_spx, K, T, rate_val, sigma)
            else:
                now_price = bs_put_price(spot, K, T, rate_val, sigma)
                at_target = bs_put_price(target_spx, K, T, rate_val, sigma)
                at_opp = bs_put_price(opp_spx, K, T, rate_val, sigma)

            if now_price <= 0:
                continue

            pct_target = (at_target - now_price) / now_price * 100.0
            pct_opp = (at_opp - now_price) / now_price * 100.0

            rows.append({
                "Strike": K,
                "Type": opt_type,
                "Now": round(now_price, 2),
                label_target: round(at_target, 2),
                label_opp: round(at_opp, 2),
                "% " + label_target: round(pct_target, 1),
                "% " + label_opp: round(pct_opp, 1)
            })

        if rows:
            st.table(rows)

# --------------- main ---------------

def main():
    init_state()
    page = st.sidebar.selectbox(
        "Page",
        ["Weekly Setup", "Daily Compass", "0DTE Lab"]
    )
    if page == "Weekly Setup":
        page_weekly_setup()
    elif page == "Daily Compass":
        page_daily_compass()
    else:
        page_0dte_lab()

if __name__ == "__main__":
    main()