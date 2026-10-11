"""KLJ-7 radar display and target generation."""
import random
import plotly.graph_objects as go

RADAR_RANGE_KM = 100
WEAPONS = {
    "PL-5E (short range)": {"range_km": 20, "ammo": 2},
    "SD-10 (medium range)": {"range_km": 70, "ammo": 2},
}


def generate_targets(n: int = 5, seed=None):
    rng = random.Random(seed)
    return [
        {
            "id": f"BOGEY-{i + 1}",
            "bearing": rng.randint(0, 359),
            "range_km": rng.randint(10, RADAR_RANGE_KM - 5),
        }
        for i in range(n)
    ]


def build_radar(targets, locked_id=None):
    fig = go.Figure()
    if targets:
        colors = ["red" if t["id"] == locked_id else "#00ff66" for t in targets]
        fig.add_trace(
            go.Scatterpolar(
                r=[t["range_km"] for t in targets],
                theta=[t["bearing"] for t in targets],
                mode="markers+text",
                text=[t["id"] for t in targets],
                textposition="top center",
                textfont=dict(color="#00ff66", size=10),
                marker=dict(size=12, color=colors, symbol="diamond"),
                hovertemplate="%{text}<br>%{r} km @ %{theta}°<extra></extra>",
                name="Targets",
            )
        )
    # own aircraft at centre
    fig.add_trace(
        go.Scatterpolar(r=[0], theta=[0], mode="markers",
                        marker=dict(size=10, color="cyan", symbol="triangle-up"),
                        name="JF-17", hoverinfo="skip")
    )
    grid = dict(gridcolor="#0a5c2a", linecolor="#0a5c2a", color="#00ff66")
    fig.update_layout(
        polar=dict(
            bgcolor="#020b05",
            radialaxis=dict(range=[0, RADAR_RANGE_KM], tickvals=[25, 50, 75, 100],
                            ticksuffix=" km", **grid),
            angularaxis=dict(direction="clockwise", rotation=90,
                             tickvals=list(range(0, 360, 30)), **grid),
        ),
        paper_bgcolor="#020b05",
        showlegend=False,
        margin=dict(l=40, r=40, t=30, b=30),
        height=520,
        title=dict(text="KLJ-7 RADAR", font=dict(color="#00ff66")),
    )
    return fig
