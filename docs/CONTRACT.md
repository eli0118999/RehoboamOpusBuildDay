# Mini Rehoboam — Frozen Contract

**Read-only for subagents.** If something here seems wrong, report it in your final message instead
of working around it. Source of truth for every JSON shape: `rehoboam/schemas.py`.

## 1. State JSON

One snapshot = `CityState` (schemas.py) = `runs/<run_id>/tick_NN.json` = `GET /api/state?tick=N`.

Top-level keys:
```
run_id, tick, year, seed
city            {name, year, population, description, districts[], landmarks[]}
residents[]     static identity (name, age, housing, citizen_bio, home_district, home_place…)
records[]       Archive records (evidence IDs like "r07-0012")
relationships[] {a, b, kind, strength, note}
resident_states[]  per-subject sim state; .prediction is the full Prediction (life_path, death_forecast,
                near_term, classification, risk_factors, recommendation, scores…); .prior_paths[] are older
                life_paths (draw ghosted); .interventions_applied[] full history; .status "active"|"reassigned";
                .disposition/.cover_story set when reassigned; .variance; .escalation_floor; .defiance_count;
                .current_place / .current_district (where the capsule stands this tick)
plan            CityPlan applied THIS tick, or null at tick 0: {directive_summary, cohort_policies[], interventions[]}
outcomes[]      {intervention_id, resident_id, rung, p_comply, roll, complied, note}
near_term_results[]  resolved predictions from the previous tick
metrics         {stability 0-100, variance_mean, accuracy|null, brier|null, active, total, reassigned, interventions, defiances}
district_dissent  {district_id: 0-1}
cohort_dissent    {cohort: 0-1}
divergences[]   see §3
ring_rotation_deg  float, grows a few degrees per tick
events_feed[]   {feed_id, tick, kind, resident_id?, district_id?, place_id?, citizen_text, system_text}
disruptions[]   disruptions applied this tick
geo             {origin_lat, origin_lon, district_arcs, place_polar, resident_polar}  see §2
```

**Fixture:** `web/fixtures/sample_state.json` is `{"run_id": "sample", "ticks": [CityState, CityState, CityState]}`
(tick 0 calm with a state-B divergence; tick 1 `factory_closure` + state-C divergence + two defiances;
tick 2 r05 reassigned + state-A divergence + r08 re-routed with a ghost path). Regenerate with
`python scripts/make_sample_state.py` (orchestrator only).

## 2. Shared geography (never re-derive; read `state.geo`)

- **Bearing** = degrees clockwise from north (0 = 12 o'clock, 90 = 3 o'clock). **Radius** = fraction of plinth radius, 0 = council tower, 1 = plinth edge.
- `geo.district_arcs[district_id] = [start_deg, end_deg]`, clockwise from start to end (may wrap past 360).
- `geo.place_polar[place_id] = [bearing, radius]`. The council landmark is `[0, 0]`.
- `geo.resident_polar[resident_id] = [bearing, radius]` for this tick (already fanned out when several subjects share a place).
- **3D mapping** (world.js): `x = sin(bearing)·radius·R`, `z = −cos(bearing)·radius·R`, where `R` is the plinth radius in world units. North is −Z.
- **Circle mapping** (circle.js): `x = cx + sin(θ)·ρ`, `y = cy − cos(θ)·ρ`, θ = bearing (+ view rotation, see §3).
- So a divergence at 4 o'clock on the circle sits at that bearing from the tower in the 3D city.

## 3. Divergences → circle

`Divergence = {divergence_id, status, district_id, focal_resident, focal_coords, angle_deg, arc_spread_deg,
outward, inward, severity, resident_ids[], place_label, spread_label}`

- `status` → label text: `analysis_required` → `ANALYSIS REQUIRED:`; `divergence` → `DIVERGENCE:`;
  `elevated_scrutiny` → `ELEVATED SCRUTINY:`; `special_circumstances` → `SPECIAL CIRCUMSTANCES:` (second line may read `INTERVENTION IN PROGRESS`).
- `severity` (0-1) drives the look continuously: **0** (or no divergences) → perfect hairline ring;
  **~0.2-0.45** → state **B** (minor divergence: thin clean ring, fibrous spikes); **~0.45-0.7** → state **A**
  (special circumstances: thick uneven smoky ring, heavier bottom-left, few spikes); **≥0.7** → state **C**
  (major: black crescent displaced left, pale disc shoved right, radial streaks, inward bleed).
- `outward` = how far ink bleeds out; `inward` = how far it creeps into the disc; `arc_spread_deg` = angular width.
- `spread_label` is pre-formatted (`"9 ARC DEGREES"`, `"2.3 ARC MINUTES"`); empty string = concentrated → show coordinates only.
- `place_label` is pre-formatted (`"MILL DISTRICT, STILLWATER"`); `focal_coords` like `"41.1670° N, 72.3230° W"`.
- Per-subject variance for background corona: `resident_states[i].variance` at `geo.resident_polar[rid][0]`.
- **Rotation:** geography is drawn unrotated by default (bearing match with 3D). `ring_rotation_deg` rotates the ink
  *texture/noise phase* (the clock). `circle.focus(rid)` temporarily rotates the whole drawing so that subject's bearing
  sits under the label leader; `circle.focus(null)` eases back to 0.

## 4. HTTP API (server.py)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/runs` | `[{run_id, ticks: [0,1,…]}]` (always includes `"sample"`, served from the fixture) |
| GET | `/api/ticks?run=ID` | `{run_id, ticks: [ints], latest: int}` |
| GET | `/api/state?run=ID&tick=N` | `CityState` (tick defaults to latest; run defaults to the newest run, else `sample`) |
| POST | `/api/tick?run=ID` | runs one live tick, returns the new `CityState` (503 + `{error}` if unavailable, e.g. replay/sample) |
| POST | `/api/disrupt/{disruption_id}?run=ID` | queues a disruption for the next tick, returns `{queued: id}` |
| GET | `/` | serves `web/` statically (`index.html`) |

**Front-end fallback:** if `/api/ticks` fails (opened from a plain static server), `app.js` loads
`fixtures/sample_state.json` and serves ticks from it locally. All views must work in that mode.

## 5. Front-end module API

ES modules, no build step. `index.html` has an import map: `"three": "./vendor/three/three.module.js"`,
`"three/addons/": "./vendor/three/addons/"` (so `three/addons/controls/OrbitControls.js`,
`three/addons/renderers/CSS2DRenderer.js`).

`view` is always `"citizen"` or `"system"`. `rid` is a resident_id or `null`.

```js
// web/world.js  (owner: world agent)
export function createWorld(containerEl, { onSelect }) → {
  setState(state, { animate = true } = {}),   // build city once (seeded from state.seed + city), then update subjects/overlays
  focus(rid),          // fly camera to subject (null → back to orbit)
  setView(view),       // ~1s light/fog/overlay fade
  highlightCohort(cohort | null),
  resize(),
}
// web/circle.js  (owner: circle agent)
export function createCircle(canvasEl, { onSelect }) → {
  setState(state), focus(rid), setView(view), resize(),
}
// web/profile.js  (owner: shell agent)
export function createProfile(containerEl, { onSelect, onOpenCircle }) → {
  setState(state), focus(rid), setView(view), close(),
}
// web/views.js  (owner: shell agent) — pure render helpers returning DOM/SVG elements
export function lifePathSVG(prediction, priorPaths, { width, height }) → SVGElement
export function archiveTable(records, { residentId, highlight }) → HTMLElement
export function cohortHeatmap(state, { onCohort }) → HTMLElement
export function gallery(state, { view, onSelect }) → HTMLElement
// web/theme.js  (owner: shell agent)
export const THEME = { bg:'#0B0D10', plinth:'#D9D9D6', building:'#F2F2EE', cyan:'#6FE7FF', amber:'#FFB347',
  red:'#FF4D4D', cardOrange:'#FF8A3D', cardBgTop:'#0a1018', cardBgBottom:'#14202c', circleField:'#e6e6e4',
  circleInk:'#0a0a0a', citizenKey:'#FFC89A', systemKey:'#E6EEFF', mono:'"JetBrains Mono","IBM Plex Mono",Consolas,monospace',
  condensed:'"Barlow Condensed","Roboto Condensed","Arial Narrow",sans-serif' }
export function riskColor(deviation_risk) → css colour (white → amber → red)
```

`app.js` owns: fetching state, the tick scrubber, the Citizen/System toggle, and **linked selection** —
any `onSelect(rid)` from any module calls `app.select(rid)` which calls `world.focus`, `circle.focus`,
`profile.focus` and highlights the feed line. Esc → `select(null)`.

**DOM (index.html, shell agent):** `#header`, `#stage` (world container, fills the main area),
`#circle-panel` containing `<canvas id="circle">` (light inset, top-left), `#card` (OPUS card, slides in
from the right), `#feed` (bottom strip), `#drawer` (population/heatmap/gallery, toggled), `body.view-citizen`
or `body.view-system` class.

## 6. Display rules every view obeys

- **Reassigned subjects:** surface label is always `REASSIGNED` (feed, 3D label, gallery stamp, header count).
  Citizen view shows only `cover_story`. `disposition` appears ONLY on the OPUS card in System view
  (struck-through classification, grey `STATUS: REASSIGNED`, small grey `Disposition: …`). No red there.
- **Citizen view:** no scores, classifications, risk factors, dispositions or overlays; feed shows `citizen_text`;
  card becomes "Stillwater Connect" (first name, `citizen_bio`, this week's `citizen_story` items).
- **System view:** everything; feed shows `system_text`.
- **Colour only encodes data** in the 3D world. No bloom, no textures.
- Bundled fonts are not guaranteed; always use the fallback stacks in THEME. No CDNs (must run offline on stage).

## 7. Backend module API (Python)

All functions are pure-ish over `CityState`/`Archive` objects; only `state.py` and `llm.py` touch disk.
`archive_of(state)` = `Archive(city=state.city, residents=state.residents, records=state.records, relationships=state.relationships)`.

```python
# rehoboam/archive.py   (passes agent)
def generate_archive(n: int = config.N_SUBJECTS, year: int = config.YEAR) -> Archive   # llm pass "archive", key "seed"; validated

# rehoboam/predict.py   (passes agent)
def predict_one(archive: Archive, rid: str, tick: int, rs: ResidentState | None = None) -> Prediction
    # rs carries interventions_applied (→ interventions_block), recompute_pending + deviation_note (→ recompute_block,
    # effort config.EFFORT["recompute"]), current_place. llm pass "predict", key f"t{tick:02d}_{rid}".
def predict_many(archive: Archive, rids: list[str], tick: int, states: dict[str, ResidentState] | None = None) -> dict[str, Prediction]
    # first call alone (warms the cache), rest on a ThreadPool(config.MAX_WORKERS); each validated

# rehoboam/plan.py      (passes agent)
def make_plan(state: CityState) -> CityPlan      # llm pass "plan", key f"t{state.tick:02d}"; validated against floors

# rehoboam/validate.py  (passes agent)
def validate_archive(a: Archive) -> tuple[Archive, list[str]]                      # (fixed object, warnings)
def validate_prediction(p: Prediction, archive: Archive, rid: str) -> tuple[Prediction, list[str], float]  # float = invalid-citation ratio
def validate_plan(plan: CityPlan, archive: Archive, states: list[ResidentState]) -> tuple[CityPlan, list[str], float]

# rehoboam/sim.py       (sim agent) — deterministic given state.seed + tick
def initial_state(archive: Archive, preds: dict[str, Prediction], run_id: str, seed: int = config.SEED) -> CityState   # tick 0, metrics/divergences/geo filled
def begin_tick(prev: CityState, disruption_ids: list[str]) -> CityState    # deep copy, tick+1, clear per-tick fields, apply disruptions
def apply_plan(state: CityState, plan: CityPlan) -> list[str]              # sim steps 1-3 (comply/defy, resolve near_term, move); mutates; returns rids to re-predict
def finalize(state: CityState, new_preds: dict[str, Prediction]) -> CityState   # steps 4-6: swap paths (old → prior_paths), metrics, dissent, divergences, rotation, geo, feed

# rehoboam/metrics.py   (sim agent)
def subject_variance(p: Prediction) -> float
def compute_metrics(state: CityState) -> Metrics
def district_dissent(state: CityState) -> dict[str, float]
def cohort_dissent(state: CityState) -> dict[str, float]
def brier(results: list[NearTermOutcome]) -> float | None
def compute_divergences(state: CityState) -> list[Divergence]

# rehoboam/disruptions.py (sim agent) — registry, the extension point
DISRUPTIONS: dict[str, Disruption]      # "factory_closure", "organiser_arrives", "heatwave", "data_leak"…
def apply_disruption(state: CityState, disruption_id: str, rng: random.Random) -> DisruptionEvent

# rehoboam/state.py     (sim agent)
def run_dir(run_id: str) -> Path
def save_state(state: CityState) -> Path          # runs/<run_id>/tick_NN.json
def load_state(run_id: str, tick: int | None = None) -> CityState   # None → latest; run_id "sample" → fixture
def list_ticks(run_id: str) -> list[int]
def list_runs() -> list[dict]                     # [{run_id, ticks}], includes "sample"
def save_archive(run_id: str, a: Archive) -> Path; def load_archive(run_id: str) -> Archive

# rehoboam/runner.py    (orchestrator) — what cli.py and server.py call
def start(run_id: str | None = None, replay: bool = False) -> str          # configures llm, returns run_id
def seed(run_id: str) -> Archive
def predict(run_id: str) -> CityState                                       # tick 0
def tick(run_id: str) -> CityState                                          # plan → apply → re-predict → finalize → save
def queue_disruption(run_id: str, disruption_id: str) -> None
def demo(run_id: str = "demo", replay: bool = False, ticks: int = 4) -> CityState
```
