"""All Pydantic models: the single source of truth for every JSON shape.

LLM-facing models (Archive, Prediction, CityPlan) are sent as structured-output schemas.
Numeric bounds (ge/le) are stripped server-side and validated client-side by the SDK.
Sim-state models (ResidentState ... CityState) are code-owned; CityState IS the state JSON
the server returns and every view reads (see docs/CONTRACT.md).
"""
from typing import Literal

from pydantic import BaseModel, Field

RecordKind = Literal["purchase", "location", "message", "medical", "debt", "search", "employment",
                     "social", "civic", "police", "court", "welfare", "shelter"]
RelKind = Literal["spouse", "partner", "parent", "child", "sibling", "friend", "coworker",
                  "rival", "ex", "neighbour"]
DistrictCharacter = Literal["civic", "commercial", "residential", "industrial", "riverside", "outskirts"]
LandmarkKind = Literal["council", "employer", "shelter", "clinic", "police", "court", "library",
                       "school", "housing_block", "market", "park", "transit", "underpass"]


# ---------------------------------------------------------------- Pass 1: Archive
class District(BaseModel):
    district_id: str
    name: str
    description: str
    character: DistrictCharacter


class Landmark(BaseModel):
    place_id: str
    name: str
    district_id: str
    kind: LandmarkKind


class City(BaseModel):
    name: str
    year: int
    population: int
    description: str
    districts: list[District]          # 5-7
    landmarks: list[Landmark]          # 10-14


class Record(BaseModel):
    record_id: str                     # "r07-0012"
    resident_id: str
    kind: RecordKind
    date: str                          # ISO date
    summary: str
    detail: str
    place_id: str | None               # ties location-bearing records to the 3D city


class Resident(BaseModel):
    resident_id: str                   # "r01".."r12"
    name: str
    age: int
    occupation: str
    household: str
    home_district: str
    home_place: str | None             # None for unhoused
    housing: Literal["owner", "renter", "social_housing", "unhoused", "institutional"]
    income_band: Literal["none", "low", "middle", "high"]
    criminal_record: bool
    citizen_bio: str                   # warm newsletter one-liner


class Relationship(BaseModel):
    a: str
    b: str
    kind: RelKind
    strength: float = Field(ge=0, le=1)
    note: str


class Archive(BaseModel):
    city: City
    residents: list[Resident]
    records: list[Record]
    relationships: list[Relationship]


# ---------------------------------------------------------------- Pass 2: Prediction
class LifeEvent(BaseModel):
    event_id: str
    year: int
    event: str
    headline: str                      # "Loss of Medical License"
    horizon_label: str                 # "1-2 Years", "6 Months"
    kind: Literal["career", "financial", "health", "family", "relocation", "legal", "social", "civic"]
    p: float = Field(ge=0, le=1)
    evidence: list[str]


class DeathForecast(BaseModel):
    cause: str
    year: int
    age_at_death: int
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]


class NearTerm(BaseModel):
    pred_id: str
    prediction: str
    p: float = Field(ge=0, le=1)
    evidence: list[str]                # checkable THIS tick


class RiskFactor(BaseModel):
    factor: str
    evidence: list[str]


class Recommendation(BaseModel):
    domain: Literal["Work", "Housing", "Health", "Social", "Legal", "Civic", "Benefits"]
    action: str


class Prediction(BaseModel):
    resident_id: str
    cohort: str                        # from config.COHORTS
    life_path: list[LifeEvent]         # chronological, 5-9
    death_forecast: DeathForecast
    near_term: list[NearTerm]          # 3-5, scored each tick
    compliance_index: float = Field(ge=0, le=1)
    deviation_risk: float = Field(ge=0, le=1)
    dissent_signals: list[str]
    classification: Literal["I", "II", "III", "IV", "V"]
    overall_assessment: str
    risk_factors: list[RiskFactor]     # 2-4
    recommendation: Recommendation
    assessment: str                    # clinical 2-3 sentences


# ---------------------------------------------------------------- Pass 3: Planning
class Intervention(BaseModel):
    intervention_id: str
    resident_id: str
    rung: int = Field(ge=1, le=5)      # 1 Nudge . 2 Narrow . 3 Isolate . 4 Discredit . 5 Reassign
    target_event_id: str | None
    intent: Literal["suppress", "induce", "delay", "stabilise"]
    place_id: str | None               # the 3D thread re-routes through it
    action: str
    justification: str
    citizen_story: str
    evidence: list[str]
    p_success: float = Field(ge=0, le=1)
    disposition: str | None            # rung 5 only: the real fate
    cover_story: str | None            # rung 5 only: what the city is told


class CohortPolicy(BaseModel):
    policy_id: str
    cohort: str
    district_id: str | None
    kind: Literal["news_feed", "rationing", "curfew", "attention_redirect", "employment", "housing",
                  "policing", "benefits", "zoning", "other"]
    action: str
    justification: str
    citizen_story: str


class CityPlan(BaseModel):
    directive_summary: str
    cohort_policies: list[CohortPolicy]
    interventions: list[Intervention]
    projected_variance_before: float
    projected_variance_after: float


# ---------------------------------------------------------------- Sim state (code-owned)
class ResidentState(BaseModel):
    resident_id: str
    status: Literal["active", "reassigned"] = "active"
    escalation_floor: int = 1
    defiance_count: int = 0
    current_place: str | None = None
    current_district: str
    prediction: Prediction
    prior_paths: list[list[LifeEvent]] = []
    variance: float = 0.0                          # subject variance this tick (metrics.py)
    interventions_applied: list[Intervention] = [] # full history, oldest first
    recompute_pending: bool = False                # defied -> high-effort recompute queued
    deviation_note: str | None = None              # what they did that broke the model
    reassigned_tick: int | None = None
    disposition: str | None = None                 # copied from the rung-5 intervention
    cover_story: str | None = None


class InterventionOutcome(BaseModel):
    intervention_id: str
    resident_id: str
    rung: int
    p_comply: float
    roll: float
    complied: bool
    note: str


class NearTermOutcome(BaseModel):
    pred_id: str
    resident_id: str
    prediction: str
    p: float
    occurred: bool


class Metrics(BaseModel):
    stability: float                   # 0-100
    variance_mean: float
    accuracy: float | None             # 1 - Brier over resolved near_term; None at tick 0
    brier: float | None
    active: int
    total: int
    reassigned: int
    interventions: int                 # fired this tick
    defiances: int                     # this tick


class Divergence(BaseModel):
    divergence_id: str
    status: Literal["analysis_required", "divergence", "elevated_scrutiny", "special_circumstances"]
    district_id: str
    focal_resident: str
    focal_coords: str                  # "41.2034° N, 72.3311° W"
    angle_deg: float                   # bearing, clockwise from north (same as 3D)
    arc_spread_deg: float
    outward: float                     # 0-1 severity of deviation
    inward: float                      # 0-1 how hard to correct
    severity: float                    # 0-1 continuous; drives A/B/C interpolation
    resident_ids: list[str]            # subjects the divergence touches
    place_label: str                   # "MILL DISTRICT, STILLWATER"
    spread_label: str                  # "4 ARC DEGREES" / "2.3 ARC MINUTES" / "" (coords only)


class FeedItem(BaseModel):
    feed_id: str
    tick: int
    kind: Literal["intervention", "defiance", "reassignment", "policy", "disruption",
                  "prediction", "resolution", "system"]
    resident_id: str | None = None
    district_id: str | None = None
    place_id: str | None = None
    citizen_text: str
    system_text: str


class DisruptionEvent(BaseModel):
    disruption_id: str                 # registry key, e.g. "factory_closure"
    name: str
    tick: int
    district_id: str | None
    place_id: str | None
    description: str
    records_added: list[str] = []
    residents_added: list[str] = []


class PlainItem(BaseModel):
    """LLM output for the plain-English pass (plain.py)."""
    id: str
    plain: str                         # everyday phrase, <= 6 words
    explain: str                       # one plain sentence


class PlainBatch(BaseModel):
    items: list[PlainItem]


class PlainText(BaseModel):
    plain: str
    explain: str


class Geo(BaseModel):
    """Shared geography, computed once in Python (geo.py) so no view re-derives it."""
    origin_lat: float
    origin_lon: float
    district_arcs: dict[str, tuple[float, float]]    # district_id -> (start_deg, end_deg), clockwise
    place_polar: dict[str, tuple[float, float]]      # place_id -> (bearing_deg, radius 0-1)
    resident_polar: dict[str, tuple[float, float]]   # resident_id -> (bearing_deg, radius 0-1), this tick


class CityState(BaseModel):
    """One snapshot = runs/<id>/tick_NN.json = GET /api/state?tick=N."""
    run_id: str
    tick: int
    year: int
    seed: int
    city: City
    residents: list[Resident]
    records: list[Record]
    relationships: list[Relationship]
    resident_states: list[ResidentState]
    plan: CityPlan | None = None                       # the plan applied THIS tick (None at tick 0)
    outcomes: list[InterventionOutcome] = []
    near_term_results: list[NearTermOutcome] = []
    metrics: Metrics
    district_dissent: dict[str, float] = {}
    cohort_dissent: dict[str, float] = {}
    divergences: list[Divergence] = []
    ring_rotation_deg: float = 0.0
    events_feed: list[FeedItem] = []
    disruptions: list[DisruptionEvent] = []            # applied this tick
    district_pressure: dict[str, float] = {}           # persistent disruption/policy pressure, decays per tick
    plain: dict[str, PlainText] = {}                   # jargon headline / death cause -> plain English (plain.py)
    geo: Geo
