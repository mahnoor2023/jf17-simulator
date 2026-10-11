import random
import time

import plotly.graph_objects as go
import streamlit as st

import combat as cb
import physics as ph
import radar as rd

st.set_page_config(page_title="JF-17 Thunder Cockpit", page_icon="✈️", layout="wide")

# ---------- Military dark theme ----------
st.markdown(
    """
    <style>
    .stApp, header[data-testid="stHeader"] { background-color: #020b05; }
    .stApp { color: #00ff66; font-family: 'Courier New', monospace; }
    h1, h2, h3, label, p, span, div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] { color: #00ff66 !important; }
    .stButton>button { background-color: #0a3d1c; color: #00ff66; border: 1px solid #00ff66; width: 100%; }
    .stButton>button:hover { background-color: #00ff66; color: #020b05; }
    .stButton>button:hover span, .stButton>button:hover p { color: #020b05 !important; }
    [data-testid="stProgressBarTrack"] > div { background-color: #00ff66 !important; }
    [data-testid="stMetricValue"] { font-size: 1.45rem; }
    [data-testid="stMetricValue"] > div { white-space: normal !important; overflow: visible !important; text-overflow: clip !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

DEFAULT_ALT_FT = 20_000
SWEEP_STEP_DEG = 36  # radar beam moves this much on every update


# ---------- Session state ----------
def init_state(difficulty: str):
    ss = st.session_state
    store_kg = sum(w["ammo"] * w["mass_kg"] for w in cb.WEAPONS.values())
    ss.sim = ph.new_state(DEFAULT_ALT_FT, 0.7, store_kg)
    ss.ammo = {name: w["ammo"] for name, w in cb.WEAPONS.items()}
    ss.targets = rd.update_relative(rd.generate_targets(difficulty), 0.0, 0.0)
    ss.log = [f"Mission started ({difficulty}). {len(ss.targets)} bogeys on radar."]
    ss.score = 0
    ss.kills = 0
    ss.misses = 0
    ss.t = 0.0
    ss.sweep = 0.0
    ss.history = []
    ss.shot_down = False
    ss.last_tick = time.time()
    ss.difficulty_applied = difficulty


def advance(dt: float, throttle: float, altitude: float, heading: float):
    """Move the simulation forward by dt seconds."""
    ss = st.session_state
    if ss.shot_down or not ss.targets:
        return
    ph.step(ss.sim, throttle, altitude, heading, dt)
    for t in rd.advance_targets(ss.targets, ss.sim["x"], ss.sim["y"], dt):
        ss.log.append(f"{t['id']} flew out of the area.")
    ss.t += dt
    ss.sweep = (ss.sweep + SWEEP_STEP_DEG) % 360

    # aggressive enemies inside 20 km may shoot us down
    for t in ss.targets:
        if t["aggressive"] and t["range_km"] < 20 and random.random() < min(0.5, 0.03 * dt):
            ss.shot_down = True
            ss.log.append(f"{t['id']} fired at close range. JF-17 HIT!")
            break

    a = ph.atmosphere(altitude)[2]
    ss.history.append((ss.t, ss.sim["speed"] / a, 100 * ss.sim["fuel"] / ph.FUEL_CAPACITY_KG))
    ss.history = ss.history[-400:]


# ---------- Page ----------
st.title("✈️ JF-17 Thunder Glass Cockpit & Avionics Simulator")
st.caption("Version 2 · advanced flight model: thrust vs drag, weight, G-limited turns, moving enemies, missile hit chance")

left, right = st.columns([1, 2])

with left:
    st.subheader("🎛️ Pilot Controls")
    difficulty = st.selectbox("Difficulty", list(rd.DIFFICULTY.keys()))
    if "sim" not in st.session_state or difficulty != st.session_state.difficulty_applied:
        init_state(difficulty)

    throttle = st.slider("Throttle (%)", 0, 100, 60)
    altitude = st.slider("Altitude (ft)", 0, ph.MAX_ALT_FT, DEFAULT_ALT_FT, step=500)
    heading = st.slider("Target heading (°)", 0, 359, 0, step=5)
    weapon = st.selectbox("Weapon", list(cb.WEAPONS.keys()))
    timescale = st.select_slider("Time speed", options=[1, 2, 5, 10], value=1, format_func=lambda x: f"{x}x")
    auto = st.toggle("▶ Auto-run (real time)", value=False)

    c1, c2 = st.columns(2)
    fire = c1.button("🚀 FIRE / ENGAGE")
    step10 = c2.button("⏱️ Step +10 s")
    if st.button("🔄 Reset Mission"):
        init_state(difficulty)
        st.rerun()

ss = st.session_state

if step10:
    advance(10.0, throttle, altitude, heading)

# ---------- Combat: FIRE ----------
w = cb.WEAPONS[weapon]
if fire:
    tgt = cb.best_target(ss.targets, weapon, rd.RADAR_RANGE_KM)
    if ss.shot_down:
        left.error("You were shot down. Press Reset Mission.")
    elif ss.ammo[weapon] <= 0:
        left.error(f"No {w['short']} left!")
    elif tgt is None:
        left.warning(f"No target within {w['short']} range ({w['range_km']} km).")
    else:
        ss.ammo[weapon] -= 1
        ss.sim["store_kg"] = max(0.0, ss.sim["store_kg"] - w["mass_kg"])
        pk = cb.hit_probability(weapon, tgt["range_km"], tgt["evasive"])
        if random.random() < pk:
            ss.targets = [t for t in ss.targets if t["id"] != tgt["id"]]
            ss.kills += 1
            ss.score += 100
            ss.log.append(f"{w['short']} hit {tgt['id']} at {tgt['range_km']:.0f} km (Pk {pk:.0%}). Target neutralized.")
            left.success(f"🎯 Target Neutralized: {tgt['id']}")
        else:
            ss.misses += 1
            ss.score -= 20
            ss.log.append(f"{w['short']} MISSED {tgt['id']} at {tgt['range_km']:.0f} km (Pk {pk:.0%}).")
            left.error(f"❌ Missed {tgt['id']}! Missile wasted.")

left.caption("Missiles left: " + " | ".join(f"{cb.WEAPONS[k]['short']}: {v}" for k, v in ss.ammo.items()))


# ---------- Live cockpit (refreshes every second when Auto-run is on) ----------
@st.fragment(run_every=1.0 if auto else None)
def cockpit():
    now = time.time()
    if auto:
        advance(min(now - ss.last_tick, 3.0) * timescale, throttle, altitude, heading)
    ss.last_tick = now

    sim = ss.sim
    info = ph.telemetry(sim, throttle, altitude)
    fuel_pct = sim["fuel"] / ph.FUEL_CAPACITY_KG

    st.subheader("📊 Flight Data")
    m = st.columns(5)
    m[0].metric("Mach", f"{info['mach']:.2f}")
    m[1].metric("Speed", f"{info['speed_kmh']:,.0f} km/h")
    m[2].metric("Altitude", f"{altitude:,} ft")
    m[3].metric("Heading", f"{sim['heading']:.0f}°")
    m[4].metric("Engine", "AFTERBURNER 🔥" if info["afterburner"] else ("FLAMEOUT" if sim["flameout"] else "NORMAL"))

    m = st.columns(5)
    m[0].metric("Thrust", f"{info['thrust_kn']:.0f} kN")
    m[1].metric("Drag", f"{info['drag_kn']:.0f} kN")
    m[2].metric("T/W ratio", f"{info['twr']:.2f}")
    m[3].metric("G-load", f"{info['g']:.1f} g")
    m[4].metric("Turn rate", f"{info['turn_rate']:.1f} °/s")

    m = st.columns(5)
    m[0].metric("Fuel", f"{sim['fuel']:,.0f} kg")
    m[1].metric("Burn rate", f"{info['burn_kg_min']:.0f} kg/min")
    m[2].metric("Endurance", f"{info['endurance_min']:.0f} min")
    m[3].metric("Weight", f"{info['weight_kg']:,.0f} kg")
    m[4].metric("Score", f"{ss.score}", f"{ss.kills} kills · {ss.misses} misses")
    st.progress(fuel_pct, text=f"Fuel {fuel_pct:.0%}   |   Mission time {ss.t:,.0f} s")

    # --- warnings
    if ss.shot_down:
        st.error("💥 YOU WERE SHOT DOWN. Mission failed. Press Reset Mission.")
    elif not ss.targets:
        st.success(f"✅ All hostile targets neutralized. Mission complete! Score: {ss.score}")
    elif sum(ss.ammo.values()) == 0:
        st.warning("⚠️ OUT OF WEAPONS. Return to base.")
    if sim["flameout"]:
        st.error("🚨 FLAMEOUT: fuel exhausted, engine has no thrust!")
    elif fuel_pct < 0.2:
        st.warning("⚠️ BINGO FUEL: return to base")
    if info["stall_warning"]:
        st.warning(f"⚠️ STALL WARNING: speed is close to stall speed ({info['stall_kmh']:.0f} km/h). Add throttle or descend.")
    if any(t["aggressive"] and t["range_km"] < 30 for t in ss.targets):
        st.warning("⚠️ THREAT: hostile fighter within 30 km. Engage or break away!")

    # --- targeting
    tgt = cb.best_target(ss.targets, weapon, rd.RADAR_RANGE_KM)
    if tgt:
        pk = cb.hit_probability(weapon, tgt["range_km"], tgt["evasive"])
        st.error(f"🔴 LOCK: {tgt['id']} | {tgt['range_km']:.0f} km | hit chance (Pk) {pk:.0%}")
    else:
        st.info(f"No target inside {w['short']} range ({w['range_km']} km).")

    st.plotly_chart(rd.build_radar(ss.targets, tgt["id"] if tgt else None, ss.sweep, sim["heading"]), key="radar")

    if len(ss.history) > 1:
        t, mach, fuel = zip(*ss.history)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t, y=mach, name="Mach", line=dict(color="#00ff66")))
        fig.add_trace(go.Scatter(x=t, y=fuel, name="Fuel %", yaxis="y2", line=dict(color="#ffb000")))
        fig.update_layout(
            height=220, margin=dict(l=40, r=40, t=30, b=30), paper_bgcolor="#020b05", plot_bgcolor="#020b05",
            font=dict(color="#00ff66"), title=dict(text="Mach and fuel over mission time (s)", font=dict(color="#00ff66")),
            xaxis=dict(gridcolor="#0a5c2a"), yaxis=dict(title="Mach", gridcolor="#0a5c2a"),
            yaxis2=dict(title="Fuel %", overlaying="y", side="right", range=[0, 100]),
            legend=dict(orientation="h", y=1.15),
        )
        st.plotly_chart(fig, key="history", theme=None)

    with st.expander("📜 Mission Log", expanded=True):
        for line in reversed(ss.log[-8:]):
            st.write("•", line)


with right:
    cockpit()
