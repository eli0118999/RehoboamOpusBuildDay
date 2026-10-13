"""Central knobs. Everything tunable lives here so passes, sim and views stay swappable."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"
WEB_DIR = ROOT / "web"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
SAMPLE_STATE = WEB_DIR / "fixtures" / "sample_state.json"

# ---- model ----
MODEL = "claude-opus-5-5"
MAX_TOKENS = 64000
EFFORT = {"archive": "medium", "predict": "medium", "recompute": "high", "plan": "high"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"
USE_FALLBACK = True
MAX_WORKERS = 6
REUSE_RECORDINGS = True   # live mode reuses an existing calls/<pass>__<key>.json (resumable runs)

# ---- world ----
CITY_NAME = "Stillwater"
POPULATION = 40_000
YEAR = 2053
N_SUBJECTS = 12
SEED = 7
TICK_UNIT = "week"
ORIGIN_LAT = 41.2034   # council tower, fictional
ORIGIN_LON = -72.3311
DEG_PER_UNIT_RADIUS = 0.045   # ~5 km from tower to plinth edge

COHORTS = [
    "stable-contributors", "precarious-young", "the-grieving", "elders",
    "non-contributing", "civic-burden", "recidivism-risk", "pattern-aware",
]

# ---- escalation ladder ----
LADDER = {1: "Nudge", 2: "Narrow", 3: "Isolate", 4: "Discredit", 5: "Reassign"}
RUNG_BASE_COMPLY = {1: 0.75, 2: 0.80, 3: 0.85, 4: 0.90, 5: 1.0}
MAX_RUNG = 5

# ---- shared geography ----
# Bearings are degrees clockwise from north (0 = 12 o'clock, 90 = 3 o'clock).
# Each district character has a preferred bearing; geo.assign_district_arcs() sorts the
# Archive's districts by it and hands each an equal compass sector. That one mapping
# drives the circle's angles, the 3D layout and the focal coordinates.
DISTRICT_BEARING = {
    "civic": 0.0, "commercial": 60.0, "residential": 120.0,
    "industrial": 180.0, "riverside": 240.0, "outskirts": 300.0,
}
# Radial band (fraction of plinth radius) where each character's landmarks sit.
DISTRICT_RADIUS = {
    "civic": (0.12, 0.35), "commercial": (0.25, 0.5), "residential": (0.4, 0.75),
    "industrial": (0.5, 0.85), "riverside": (0.45, 0.8), "outskirts": (0.7, 0.95),
}
# Unhoused subjects drift between these landmark kinds.
UNHOUSED_DRIFT_KINDS = ["underpass", "library", "shelter"]

# ---- sim ----
RING_ROTATION_PER_TICK = 4.0
DEFIANCE_DEVIATION_BUMP = 0.12
