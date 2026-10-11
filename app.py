import streamlit as st

import physics as ph
import radar as rd

st.set_page_config(page_title="JF-17 Thunder Cockpit", page_icon="✈️", layout="wide")

# ---------- Military dark theme ----------
st.markdown(
    """
    <style>
    .stApp { background-color: #020b05; color: #00ff66; font-family: 'Courier New', monospace; }
    h1, h2, h3, label, p, span, div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] { color: #00ff66 !important; }
    section[data-testid="stSidebar"] { background-color: #04140a; }
    .stButton>button { background-color: #0a3d1c; color: #00ff66; border: 1px solid #00ff66; width: 100%; }
    .stButton>button:hover { background-color: #00ff66; color: #020b05; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Session state ----------
def init_state():
    st.session_state.fuel = ph.FUEL_CAPACITY_KG
    st.session_state.ammo = {name: w["ammo"] for name, w in rd.WEAPONS.items()}
    st.session_state.targets = rd.generate_targets(5)
    st.session_state.log = ["Mission started. Radar active."]
    st.session_state.kills = 0


if "fuel" not in st.session_state:
    init_state()

# ---------- Cockpit controls ----------
st.title("✈️ JF-17 Thunder Glass Cockpit & Avionics Simulator")

left, right = st.columns([1, 2])

with left:
    st.subheader("🎛️ Pilot Controls")
    throttle = st.slider("Throttle (%)", 0, 100, 60)
    altitude = st.slider("Altitude (ft)", 0, ph.MAX_ALT_FT, 20_000, step=500)
    weapon = st.selectbox("Weapon", list(rd.WEAPONS.keys()))

    c1, c2 = st.columns(2)
    fire = c1.button("🚀 FIRE / ENGAGE")
    fly = c2.button("⏱️ Fly 1 min")
    if st.button("🔄 Reset Mission"):
        init_state()
        st.rerun()

# ---------- Physics ----------
ab = ph.afterburner_on(throttle)
mach = ph.compute_mach(throttle, altitude)
speed = ph.speed_kmh(mach, altitude)
burn = ph.fuel_burn_kg_per_min(throttle, altitude)

if fly:
    st.session_state.fuel = max(0.0, st.session_state.fuel - burn)
    st.session_state.log.append(f"Flew 1 min, burned {burn} kg fuel.")

fuel = st.session_state.fuel
fuel_pct = fuel / ph.FUEL_CAPACITY_KG

# ---------- Combat logic ----------
locked_id = None
w = rd.WEAPONS[weapon]
in_range = sorted(
    [t for t in st.session_state.targets if t["range_km"] <= w["range_km"]],
    key=lambda t: t["range_km"],
)
if in_range:
    locked_id = in_range[0]["id"]

if fire:
    if st.session_state.ammo[weapon] <= 0:
        left.error("No ammo left for this weapon!")
    elif not in_range:
        left.warning(f"No target within {weapon.split(' (')[0]} range ({w['range_km']} km).")
    else:
        tgt = in_range[0]
        st.session_state.targets = [t for t in st.session_state.targets if t["id"] != tgt["id"]]
        st.session_state.ammo[weapon] -= 1
        st.session_state.kills += 1
        st.session_state.log.append(
            f"{weapon.split(' (')[0]} fired at {tgt['id']} ({tgt['range_km']} km). Target neutralized."
        )
        left.success(f"🎯 Target Neutralized: {tgt['id']}")
        locked_id = None

left.caption(f"Missiles left: " + " | ".join(f"{k.split(' (')[0]}: {v}" for k, v in st.session_state.ammo.items()))
if locked_id:
    left.error(f"🔴 LOCK: {locked_id}")

# ---------- Dashboard ----------
with right:
    st.subheader("📊 Flight Data")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Mach", mach)
    m2.metric("Speed", f"{speed} km/h")
    m3.metric("Altitude", f"{altitude:,} ft")
    m4.metric("Engine", "AFTERBURNER 🔥" if ab else "NORMAL")

    m5, m6, m7 = st.columns(3)
    m5.metric("Fuel", f"{fuel:,.0f} kg")
    m6.metric("Burn rate", f"{burn} kg/min")
    m7.metric("Endurance", f"{ph.endurance_min(fuel, burn)} min")
    st.progress(fuel_pct, text=f"Fuel {fuel_pct:.0%}")

    if fuel_pct <= 0:
        st.error("🚨 FLAMEOUT: Fuel exhausted!")
    elif fuel_pct < 0.2:
        st.warning("⚠️ BINGO FUEL: return to base")

    st.plotly_chart(rd.build_radar(st.session_state.targets, locked_id), use_container_width=True)

    if not st.session_state.targets:
        st.success("✅ All hostile targets neutralized. Mission complete!")

    with st.expander("📜 Mission Log", expanded=True):
        for line in reversed(st.session_state.log[-8:]):
            st.write("•", line)
