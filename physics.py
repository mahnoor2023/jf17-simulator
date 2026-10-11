"""Advanced flight physics for the JF-17 simulator (point-mass model).

Forces: thrust (with altitude lapse and ram effect) vs drag (parasite + wave
+ induced). Speed is a *state* that accelerates until thrust equals drag, so
top speed, energy loss in turns and fuel burn all come out of the physics.
Altitude is set by the pilot (autopilot holds it); heading turns are limited
by G and by the wing's lift (CL max).
"""
import math

G = 9.80665
FT_TO_M = 0.3048
MAX_ALT_FT = 50_000

# --- Approximate public JF-17 Block-II data -------------------------------
EMPTY_KG = 6_586.0
FUEL_CAPACITY_KG = 2_300.0
WING_AREA = 24.4            # m^2
THRUST_DRY_N = 49_400.0     # RD-93, dry
THRUST_AB_N = 81_300.0      # RD-93, afterburner
AB_THRESHOLD = 90           # throttle % where afterburner lights
TSFC_DRY = 2.3e-5           # kg fuel per N thrust per second
TSFC_AB = 5.6e-5
IDLE_FRAC = 0.05
CD0 = 0.020                 # zero-lift drag coefficient
K_INDUCED = 0.12            # induced drag factor
CL_MAX = 1.2
TURN_G = 6.0                # pilot's normal max turning load factor
MIN_SPEED_MS = 90.0
MAX_MACH = 1.6              # airframe / air-intake limit


# --- Atmosphere -----------------------------------------------------------
def atmosphere(alt_ft: float):
    """ISA: returns (temperature K, density kg/m3, speed of sound m/s)."""
    h = alt_ft * FT_TO_M
    if h <= 11_000:
        t = 288.15 - 0.0065 * h
        rho = 1.225 * (t / 288.15) ** 4.2559
    else:
        t = 216.65
        rho = 0.3639 * math.exp(-(h - 11_000) / 6341.6)
    return t, rho, math.sqrt(1.4 * 287.05 * t)


# --- Engine ---------------------------------------------------------------
def afterburner_on(throttle: float) -> bool:
    return throttle > AB_THRESHOLD


def _base_thrust_and_tsfc(throttle: float):
    if throttle > AB_THRESHOLD:
        frac = (throttle - AB_THRESHOLD) / (100 - AB_THRESHOLD)
        return (THRUST_DRY_N + frac * (THRUST_AB_N - THRUST_DRY_N),
                TSFC_DRY + frac * (TSFC_AB - TSFC_DRY))
    return (THRUST_DRY_N * (IDLE_FRAC + (1 - IDLE_FRAC) * throttle / AB_THRESHOLD),
            TSFC_DRY)


def available_thrust(throttle: float, alt_ft: float, mach: float):
    """Returns (thrust N, fuel flow kg/s). Thin air lowers thrust; ram helps a bit."""
    _, rho, _ = atmosphere(alt_ft)
    sigma = rho / 1.225
    base, tsfc = _base_thrust_and_tsfc(throttle)
    thrust = base * sigma ** 0.8 * (1 + 0.2 * mach)
    return thrust, max(thrust * tsfc, 0.02)


# --- Aerodynamics ---------------------------------------------------------
def wave_drag_cd(mach: float) -> float:
    """Transonic drag rise: starts at M0.85, peaks at M1.1, then decays."""
    if mach < 0.85:
        return 0.0
    if mach < 1.10:
        x = (mach - 0.85) / 0.25
        return 0.035 * x * x * (3 - 2 * x)
    return 0.035 * math.exp(-1.5 * (mach - 1.10))


def drag_n(speed: float, alt_ft: float, weight_n: float, load_factor: float = 1.0) -> float:
    _, rho, a = atmosphere(alt_ft)
    q = 0.5 * rho * speed ** 2
    cl = load_factor * weight_n / (q * WING_AREA)
    cd = CD0 + wave_drag_cd(speed / a) + K_INDUCED * cl ** 2
    return q * WING_AREA * cd


def stall_speed(alt_ft: float, weight_n: float, load_factor: float = 1.0) -> float:
    _, rho, _ = atmosphere(alt_ft)
    return math.sqrt(2 * load_factor * weight_n / (rho * WING_AREA * CL_MAX))


# --- State ----------------------------------------------------------------
def new_state(alt_ft: float = 20_000, mach: float = 0.7, store_kg: float = 0.0) -> dict:
    _, _, a = atmosphere(alt_ft)
    return {
        "speed": mach * a,          # true airspeed, m/s
        "fuel": FUEL_CAPACITY_KG,
        "store_kg": store_kg,       # weapons on board
        "heading": 0.0,             # degrees, 0 = north, clockwise
        "x": 0.0, "y": 0.0,         # world position, km
        "g": 1.0,                   # current load factor
        "turn_rate": 0.0,           # deg/s
        "flameout": False,
    }


def mass_kg(state: dict) -> float:
    return EMPTY_KG + state["fuel"] + state["store_kg"]


def telemetry(state: dict, throttle: float, alt_ft: float) -> dict:
    """Instantaneous numbers for the dashboard (no time advance)."""
    _, _, a = atmosphere(alt_ft)
    v = state["speed"]
    mach = v / a
    weight = mass_kg(state) * G
    thrust, flow = available_thrust(throttle, alt_ft, mach)
    if state["flameout"] or state["fuel"] <= 0:
        thrust, flow = 0.0, 0.0
    drag = drag_n(v, alt_ft, weight, state["g"])
    vs = stall_speed(alt_ft, weight, state["g"])
    return {
        "mach": mach,
        "speed_kmh": v * 3.6,
        "thrust_kn": thrust / 1000,
        "drag_kn": drag / 1000,
        "burn_kg_min": flow * 60,
        "weight_kg": mass_kg(state),
        "twr": thrust / weight,
        "g": state["g"],
        "turn_rate": state["turn_rate"],
        "stall_kmh": vs * 3.6,
        "stall_warning": v < 1.15 * vs,
        "afterburner": afterburner_on(throttle) and not state["flameout"],
        "endurance_min": (state["fuel"] / flow / 60) if flow > 0 else 0.0,
    }


def step(state: dict, throttle: float, alt_ft: float, target_heading: float, dt: float) -> None:
    """Advance the aircraft by dt seconds (sub-stepped for stability)."""
    if dt <= 0:
        return
    n_sub = max(1, math.ceil(dt / 0.5))
    h = dt / n_sub
    for _ in range(n_sub):
        _, rho, a = atmosphere(alt_ft)
        v = state["speed"]
        mass = mass_kg(state)
        weight = mass * G
        q = 0.5 * rho * v * v

        # --- turning: limited by pilot G and by lift available
        err = (target_heading - state["heading"] + 180) % 360 - 180
        n_aero = CL_MAX * q * WING_AREA / weight
        n_max = min(TURN_G, n_aero)
        if n_max > 1.0 and abs(err) > 0.01:
            omega_max = G * math.sqrt(n_max ** 2 - 1) / v          # rad/s
            d_turn = math.copysign(min(omega_max * h, math.radians(abs(err))), err)
            omega = d_turn / h
            n = math.sqrt(1 + (v * omega / G) ** 2)
        else:
            d_turn, omega, n = 0.0, 0.0, 1.0
        state["heading"] = (state["heading"] + math.degrees(d_turn)) % 360
        state["g"] = n
        state["turn_rate"] = abs(math.degrees(omega))

        # --- forces
        thrust, flow = available_thrust(throttle, alt_ft, v / a)
        if state["fuel"] <= 0:
            state["flameout"] = True
        if state["flameout"]:
            thrust, flow = 0.0, 0.0
        drag = drag_n(v, alt_ft, weight, n)
        v += (thrust - drag) / mass * h
        v_min = max(MIN_SPEED_MS, stall_speed(alt_ft, weight, n))
        state["speed"] = min(max(v, v_min), MAX_MACH * a)

        # --- position and fuel
        state["x"] += state["speed"] * math.sin(math.radians(state["heading"])) * h / 1000
        state["y"] += state["speed"] * math.cos(math.radians(state["heading"])) * h / 1000
        state["fuel"] = max(0.0, state["fuel"] - flow * h)


def max_mach(throttle: float, alt_ft: float) -> float:
    """Equilibrium Mach (thrust = drag) in level flight. Handy for testing."""
    s = new_state(alt_ft, 0.6)
    for _ in range(40):                 # 40 x 15 s, refuelled so it never flames out
        s["fuel"] = 1_200.0
        step(s, throttle, alt_ft, 0.0, 15)
    return s["speed"] / atmosphere(alt_ft)[2]
