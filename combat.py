"""Weapons and hit-probability model."""

WEAPONS = {
    "PL-5E (short range)": {"short": "PL-5E", "range_km": 20, "ammo": 2, "pk": 0.75, "mass_kg": 83},
    "SD-10 (medium range)": {"short": "SD-10", "range_km": 70, "ammo": 2, "pk": 0.65, "mass_kg": 199},
}


def hit_probability(weapon_name: str, range_km: float, evasive: bool = False) -> float:
    """Probability of kill (Pk).

    Starts from the missile's base Pk, drops as the target gets near the edge of
    the missile's range (less energy left), and is reduced if the enemy manoeuvres.
    """
    w = WEAPONS[weapon_name]
    frac = min(range_km / w["range_km"], 1.0)
    pk = w["pk"] * (1 - 0.5 * frac ** 2)
    if evasive:
        pk -= 0.15
    return max(0.05, min(pk, 0.95))


def best_target(targets, weapon_name: str, radar_range_km: float):
    """Closest target that is inside both radar and missile range, else None."""
    reach = min(WEAPONS[weapon_name]["range_km"], radar_range_km)
    candidates = [t for t in targets if t["range_km"] <= reach]
    return min(candidates, key=lambda t: t["range_km"]) if candidates else None
