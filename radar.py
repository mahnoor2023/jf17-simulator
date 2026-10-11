"""KLJ-7 radar: moving enemy aircraft and the radar display."""
import math
import random

import plotly.graph_objects as go

RADAR_RANGE_KM = 100
ESCAPE_RANGE_KM = 250   # targets beyond this are considered gone

DIFFICULTY = {
    "Easy": {"n": 4, "mach": (0.5, 0.8), "aggressive": False, "evasive": False},
    "Hard": {"n": 7, "mach": (0.7, 1.2), "aggressive": True, "evasive": True},
}


def generate_targets(difficulty: str = "Easy", own_x: float = 0.0, own_y: float = 0.0, seed=None):
    cfg = DIFFICULTY[difficulty]
    rng = random.Random(seed)
    targets = []
    for i in range(cfg["n"]):
        bearing = rng.uniform(0, 360)
        dist = rng.uniform(30, 90)
        targets.append({
            "id": f"BOGEY-{i + 1}",
            "x": own_x + dist * math.sin(math.radians(bearing)),
            "y": own_y + dist * math.cos(math.radians(bearing)),
            "heading": rng.uniform(0, 360),
            "mach": rng.uniform(*cfg["mach"]),
            "aggressive": cfg["aggressive"],
            "evasive": cfg["evasive"],
        })
    return targets


def update_relative(targets, own_x: float, own_y: float):
    """Fill in range_km and bearing (from own aircraft, north-up) for each target."""
    for t in targets:
        dx, dy = t["x"] - own_x, t["y"] - own_y
        t["range_km"] = math.hypot(dx, dy)
        t["bearing"] = math.degrees(math.atan2(dx, dy)) % 360
    return targets


def advance_targets(targets, own_x: float, own_y: float, dt: float):
    """Move every enemy for dt seconds. Aggressive ones turn toward us (3 deg/s).

    Returns the list of targets that flew out of range (escaped)."""
    escaped = []
    for t in targets:
        if t["aggressive"]:
            update_relative([t], own_x, own_y)
            want = t["bearing"] + 180            # bearing from the target to us
            err = (want - t["heading"] + 180) % 360 - 180
            t["heading"] = (t["heading"] + max(-3 * dt, min(3 * dt, err))) % 360
        speed_kms = t["mach"] * 0.295             # ~295 m/s speed of sound at altitude
        t["x"] += speed_kms * math.sin(math.radians(t["heading"])) * dt
        t["y"] += speed_kms * math.cos(math.radians(t["heading"])) * dt
    update_relative(targets, own_x, own_y)
    for t in list(targets):
        if t["range_km"] > ESCAPE_RANGE_KM:
            escaped.append(t)
            targets.remove(t)
    return escaped


def visible(targets):
    return [t for t in targets if t["range_km"] <= RADAR_RANGE_KM]


def build_radar(targets, locked_id=None, sweep_deg: float = 0.0, heading_deg: float = 0.0):
    fig = go.Figure()

    # sweeping beam: a fading wedge behind a bright line
    arc = [sweep_deg - 30 * i / 10 for i in range(11)]
    fig.add_trace(go.Scatterpolar(
        r=[0] + [RADAR_RANGE_KM] * 11 + [0], theta=[sweep_deg] + arc + [sweep_deg],
        mode="lines", fill="toself", fillcolor="rgba(0,255,102,0.10)",
        line=dict(width=0), hoverinfo="skip"))
    fig.add_trace(go.Scatterpolar(
        r=[0, RADAR_RANGE_KM], theta=[sweep_deg, sweep_deg], mode="lines",
        line=dict(color="#00ff66", width=2), hoverinfo="skip"))

    vis = visible(targets)
    if vis:
        # blips are bright right after the beam passes and fade until the next sweep
        colors = []
        for t in vis:
            age = (sweep_deg - t["bearing"]) % 360
            alpha = round(max(0.3, 1 - age / 360), 2)
            colors.append("rgba(255,40,40,1)" if t["id"] == locked_id else f"rgba(0,255,102,{alpha})")
        fig.add_trace(go.Scatterpolar(
            r=[t["range_km"] for t in vis], theta=[t["bearing"] for t in vis],
            mode="markers+text", text=[t["id"] for t in vis], textposition="top center",
            textfont=dict(color="#00ff66", size=10),
            marker=dict(size=12, color=colors, symbol="diamond"),
            customdata=[[t["mach"], t["heading"]] for t in vis],
            hovertemplate="%{text}<br>%{r:.0f} km @ %{theta:.0f}°<br>Mach %{customdata[0]:.2f}, heading %{customdata[1]:.0f}°<extra></extra>"))

    # own aircraft and its heading line
    fig.add_trace(go.Scatterpolar(
        r=[0, 18], theta=[heading_deg, heading_deg], mode="lines",
        line=dict(color="cyan", width=2, dash="dot"), hoverinfo="skip"))
    fig.add_trace(go.Scatterpolar(
        r=[0], theta=[0], mode="markers", marker=dict(size=10, color="cyan", symbol="triangle-up"),
        hoverinfo="skip"))

    grid = dict(gridcolor="#0a5c2a", linecolor="#0a5c2a", color="#00ff66")
    fig.update_layout(
        polar=dict(
            bgcolor="#020b05",
            radialaxis=dict(range=[0, RADAR_RANGE_KM], tickvals=[25, 50, 75, 100], ticksuffix=" km", **grid),
            angularaxis=dict(direction="clockwise", rotation=90,
                             tickvals=list(range(0, 360, 30)), **grid)),
        paper_bgcolor="#020b05", showlegend=False,
        margin=dict(l=40, r=40, t=40, b=30), height=520,
        title=dict(text="KLJ-7 RADAR (north-up)", font=dict(color="#00ff66")),
    )
    return fig
