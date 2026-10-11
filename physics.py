"""Flight physics engine for the JF-17 simulator (simplified model)."""
import math

FT_TO_M = 0.3048
MAX_ALT_FT = 50_000
FUEL_CAPACITY_KG = 2300.0  # approx. internal fuel
AFTERBURNER_THRESHOLD = 90  # throttle % above which afterburner lights
MAX_MACH_AB = 1.6
MAX_MACH_DRY = 0.95


def temperature_k(alt_ft: float) -> float:
    """ISA temperature: lapse rate up to 11 km, constant above."""
    h = alt_ft * FT_TO_M
    return 288.15 - 0.0065 * h if h <= 11_000 else 216.65


def speed_of_sound_ms(alt_ft: float) -> float:
    return math.sqrt(1.4 * 287.05 * temperature_k(alt_ft))


def air_density_ratio(alt_ft: float) -> float:
    """Rough density ratio (sea level = 1.0)."""
    return math.exp(-alt_ft * FT_TO_M / 9000)


def engine_efficiency(alt_ft: float) -> float:
    """Thin air reduces engine performance, but never below 55%."""
    return 0.55 + 0.45 * math.sqrt(air_density_ratio(alt_ft))


def afterburner_on(throttle: float) -> bool:
    return throttle > AFTERBURNER_THRESHOLD


def compute_mach(throttle: float, alt_ft: float) -> float:
    eff = engine_efficiency(alt_ft)
    if afterburner_on(throttle):
        # blend from dry max to full afterburner between 90% and 100%
        frac = (throttle - AFTERBURNER_THRESHOLD) / (100 - AFTERBURNER_THRESHOLD)
        mach = MAX_MACH_DRY + frac * (MAX_MACH_AB - MAX_MACH_DRY)
        mach = MAX_MACH_DRY + (mach - MAX_MACH_DRY) * eff
        return round(max(mach, MAX_MACH_DRY * eff), 2)
    mach = (throttle / AFTERBURNER_THRESHOLD) * MAX_MACH_DRY * eff
    return round(mach, 2)


def speed_kmh(mach: float, alt_ft: float) -> float:
    return round(mach * speed_of_sound_ms(alt_ft) * 3.6)


def fuel_burn_kg_per_min(throttle: float, alt_ft: float) -> float:
    if afterburner_on(throttle):
        return 250.0
    # idle 15 kg/min up to ~60 kg/min at military power; thin air = slightly less burn
    burn = 15 + 45 * (throttle / AFTERBURNER_THRESHOLD)
    return round(burn * (0.8 + 0.2 * air_density_ratio(alt_ft)), 1)


def endurance_min(fuel_kg: float, burn_per_min: float) -> float:
    return round(fuel_kg / burn_per_min, 1) if burn_per_min > 0 else 0.0
