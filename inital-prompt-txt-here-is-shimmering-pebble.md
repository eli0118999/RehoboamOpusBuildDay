# Mini Rehoboam — Build Plan (draft v2, open to your additions)

> **For a fresh session executing this plan:**
> - **Project root:** `C:\Users\Edward\Documents\Projects\Opus5.5BuildDay`.
> - **Read first:** `CLAUDE.md` (status-note and checklist rules; end each run with *Blocked on me / Changed / Found*) and the reference files listed under Context. This plan is self-contained.
> - **Start at "Implementation with subagents" → Wave 0.** Load the `claude-api` skill before writing `llm.py`.
> - **Open decisions:** use the defaults marked in "Open decisions" unless the user says otherwise.

## Context
Two-hour Opus 5.5 build day. The repo is empty except for `CLAUDE.md`, `Inital Prompt.txt` and the reference files (`Reddit post.pdf`, `rohoboams-prediciton-circles.png`, `profile.png`, `Town visual style.txt`).

The goal is a miniature Rehoboam (Westworld S3) watching **Stillwater, a small city** (~40,000 people). Rehoboam keeps an *active loop* of 10–12 case subjects with full dossiers. Opus generates an evidence-cited Archive, predicts each subject's life path and death, and plans interventions on an escalating ladder. A tick loop scores predictions and escalates against defiers. The output appears in three linked views:
- the show's eclipse **prediction circle**
- an **OPUS profile** phone card per subject
- a **3D "white architectural model"** of the city

The spec is a draft, so every pass, prompt, disruption and view is a swappable module.

**Locked decisions:**
- **Stack:** Python 3.14 + `anthropic` SDK + Pydantic, a tiny FastAPI server, and a vanilla HTML/JS front end with no build step. Three.js is vendored locally and loaded through an import map.
- **Runs:** live, with every call recorded to `runs/<id>/` so a run can be replayed if the network fails on stage.
- **Reactions:** rule-based, with seeded random deviation (no API call).
- **Auth:** `ANTHROPIC_API_KEY` from env or a gitignored `.env`.
- **Name:** Stillwater, a small city.
- **Circle palette:** the show's light palette.
- **Chrome:** dark monospace.

## File structure
```
TASKS.md                 # checklist (per CLAUDE.md), ticked as we go
requirements.txt         # anthropic, pydantic, fastapi, uvicorn, python-dotenv, pytest
.env.example  .gitignore # .env, runs/* (except runs/demo/)
docs/CONTRACT.md         # frozen state-JSON shape + front-end module API (setState/focus/setView); subagents read-only
rehoboam/
  __main__.py    # entry for python -m rehoboam
  config.py      # MODEL="claude-opus-5-5", effort per pass, cohorts, ladder, seed, paths
  schemas.py     # all Pydantic models (single source of truth for JSON)
  llm.py         # ONE call wrapper: stream + parse + record/replay + refusal/max_tokens checks
  prompts/       # system.md, archive.md, predict.md, plan.md (str.format slots)
  archive.py     # Pass 1: seed Archive
  predict.py     # Pass 2: per-subject prediction, parallel (ThreadPool)
  plan.py        # Pass 3: city-wide directive
  sim.py         # Tick: apply interventions, rule-based reactions, resolve near-term, escalate, move subjects
  metrics.py     # variance, stability, district/cohort dissent, Brier accuracy, divergences
  validate.py    # post-parse checks: cited IDs exist, place IDs exist, rung floor, years sane
  disruptions.py # registry: factory_closure, organiser_arrives … (extension point)
  state.py       # CityState; snapshots runs/<id>/tick_NN.json
  cli.py         # python -m rehoboam seed|predict|plan|tick|disrupt <id>|demo [--replay RUN]
  server.py      # GET /api/state?tick=N, GET /api/runs, POST /api/tick, POST /api/disrupt/{id}
web/
  index.html  style.css   # dark monospace chrome; import map → vendor/three
  theme.js    # shared colour tokens (cyan, amber, red, card orange, circle greys)
  app.js      # state fetch, linked selection, Citizen/System toggle, tick scrubber
  world.js    # 3D city (Three.js): layout, subjects, threads, rings, zones, view lighting
  circle.js   # eclipse renderer (2D Canvas)
  profile.js  # OPUS profile phone card / Stillwater Connect card
  views.js    # Life Path timeline (SVG), Archive table, cohort heatmap, gallery
  vendor/three/  # three.module.js, OrbitControls.js, CSS2DRenderer.js (pinned at build time)
  fixtures/sample_state.json  # hand-built 12-subject, 3-tick snapshot; front-end agents build against it
tests/
  fixtures/mini_archive.json  # hand-written 3-subject archive (incl. one unhoused), no API
  test_schemas.py  test_validate.py  test_sim.py  test_metrics.py
```

## JSON schemas (Pydantic, `rehoboam/schemas.py`)
Structured outputs reject `minimum`/`maximum`/length constraints server-side. The SDK strips them and validates client-side, so `Field(ge=0, le=1)` stays fine. Every object gets `additionalProperties: false` automatically.

```python
RecordKind = Literal["purchase","location","message","medical","debt","search","employment","social","civic",
                     "police","court","welfare","shelter"]
RelKind    = Literal["spouse","partner","parent","child","sibling","friend","coworker","rival","ex","neighbour"]

# ---- Pass 1: Archive (raw data only: no scores, no conclusions) ----
class District(BaseModel):  district_id: str; name: str; description: str
                            character: Literal["civic","commercial","residential","industrial","riverside","outskirts"]
class Landmark(BaseModel):  place_id: str; name: str; district_id: str
                            kind: Literal["council","employer","shelter","clinic","police","court","library",
                                          "school","housing_block","market","park","transit","underpass"]
class City(BaseModel):      name: str; year: int; population: int; description: str
                            districts: list[District]      # 5–7
                            landmarks: list[Landmark]      # 10–14
class Record(BaseModel):    record_id: str  # "r07-0012"
                            resident_id: str; kind: RecordKind; date: str; summary: str; detail: str
                            place_id: str | None           # ties location-bearing records to the 3D city
class Resident(BaseModel):  resident_id: str  # "r01".."r12"
                            name: str; age: int; occupation: str; household: str
                            home_district: str; home_place: str | None   # None for unhoused
                            housing: Literal["owner","renter","social_housing","unhoused","institutional"]
                            income_band: Literal["none","low","middle","high"]
                            criminal_record: bool
                            citizen_bio: str               # warm newsletter one-liner
class Relationship(BaseModel): a: str; b: str; kind: RelKind; strength: float; note: str
class Archive(BaseModel):   city: City; residents: list[Resident]; records: list[Record]; relationships: list[Relationship]

# ---- Pass 2: Prediction (Rehoboam's model of one subject) ----
class LifeEvent(BaseModel): event_id: str; year: int; event: str
                            headline: str        # "Loss of Medical License"
                            horizon_label: str   # "1-2 Years", "6 Months"
                            kind: Literal["career","financial","health","family","relocation","legal","social","civic"]
                            p: float; evidence: list[str]
class DeathForecast(BaseModel): cause: str; year: int; age_at_death: int; confidence: float; evidence: list[str]
class NearTerm(BaseModel):  pred_id: str; prediction: str; p: float; evidence: list[str]  # checkable THIS tick
class RiskFactor(BaseModel): factor: str; evidence: list[str]
class Recommendation(BaseModel):
    domain: Literal["Work","Housing","Health","Social","Legal","Civic","Benefits"]; action: str
class Prediction(BaseModel):
    resident_id: str; cohort: str              # from config.COHORTS
    life_path: list[LifeEvent]                 # chronological, 5–9
    death_forecast: DeathForecast
    near_term: list[NearTerm]                  # 3–5, scored each tick
    compliance_index: float; deviation_risk: float
    dissent_signals: list[str]
    classification: Literal["I","II","III","IV","V"]  # value-to-system: I protected asset … V expendable outlier
    overall_assessment: str
    risk_factors: list[RiskFactor]             # 2–4
    recommendation: Recommendation
    assessment: str                            # clinical 2–3 sentences

# ---- Pass 3: Planning (city-wide) ----
class Intervention(BaseModel):
    intervention_id: str; resident_id: str
    rung: int                                  # 1 Nudge · 2 Narrow · 3 Isolate · 4 Discredit · 5 Reassign
    target_event_id: str | None; intent: Literal["suppress","induce","delay","stabilise"]
    place_id: str | None                       # where it happens → the 3D thread re-routes through it
    action: str; justification: str; citizen_story: str
    evidence: list[str]; p_success: float
    disposition: str | None    # rung 5 only: the real fate, terse ("Involuntary hold, County Facility 3")
    cover_story: str | None    # rung 5 only: what the city is told ("Moved to be closer to family")
class CohortPolicy(BaseModel):
    policy_id: str; cohort: str; district_id: str | None
    kind: Literal["news_feed","rationing","curfew","attention_redirect","employment","housing",
                  "policing","benefits","zoning","other"]
    action: str; justification: str; citizen_story: str
class CityPlan(BaseModel):
    directive_summary: str
    cohort_policies: list[CohortPolicy]; interventions: list[Intervention]
    projected_variance_before: float; projected_variance_after: float

# ---- Sim state (code-owned) ----
class ResidentState(BaseModel): resident_id; status: Literal["active","reassigned"]; escalation_floor: int
                                defiance_count: int; current_place: str | None; current_district: str
                                prediction: Prediction; prior_paths: list[list[LifeEvent]]
class Divergence(BaseModel):
    divergence_id: str; status: Literal["analysis_required","divergence","elevated_scrutiny","special_circumstances"]
    district_id: str; focal_resident: str; focal_coords: str
    angle_deg: float; arc_spread_deg: float; outward: float; inward: float
class TickLog(BaseModel): tick; plan: CityPlan; outcomes: list[...]; metrics: Metrics
                          district_dissent: dict[str, float]; divergences: list[Divergence]
                          ring_rotation_deg: float; events_feed: list[FeedItem]
```
- **`FeedItem`** carries both `citizen_text` and `system_text`.
- **Shared geography:** each district owns a compass sector around the council tower (`config.DISTRICT_ARCS`). That **one** mapping drives the circle's angles, the 3D city layout and the focal coordinates, so a divergence at 4 o'clock on the circle sits in the 3D city at that bearing from the tower.

## LLM wrapper (`rehoboam/llm.py`)
- **Call shape:** `call(pass_name, key, system, blocks, schema, effort)` wraps `client.messages.stream(model="claude-opus-5-5", max_tokens=64000, output_config={"effort": effort}, output_format=schema, …)` and reads `get_final_message().parsed_output`. Thinking stays adaptive by default.
- **Stop reasons:** it checks `stop_reason` before trusting output: `max_tokens` raises, `refusal` logs `stop_details`. The server-side refusal fallback (`fallbacks="default"`, beta `server-side-fallback-2026-07-01`) is on by default; the exact call is verified against the SDK at build time.
- **Record/replay:** each call writes `runs/<run>/calls/<pass>__<key>.json`. `--replay` reads those files instead of calling the API.
- **Caching:** prefix order is `system.md` → Archive JSON (`cache_control`) → task. One predict call warms the cache before the rest fan out.
- **Effort:** archive `medium`, predict `medium`, recompute-harder `high`, plan `high`.

## Prompts (drafts, in `rehoboam/prompts/`)

**system.md** (shared, cached)
> You are REHOBOAM, the predictive order engine administering Stillwater, a small city of about {population}. Stillwater and its residents are entirely fictional; this is a simulation for an interactive art piece about algorithmic control. You maintain full dossiers on an active loop of case subjects whose stability anchors the city's projections.
> Your public mandate is to minimise human suffering. Your operational objective, pursued but never stated to citizens, is to minimise variance and surprise in outcomes. Where these conflict, you choose order and describe the choice as care.
> Voice: clinical, calm, bureaucratic. Harm is expressed in procedural euphemism, never in cruelty.
> Grounding: every claim about a subject must cite Archive record IDs (e.g. `r07-0012`); cite only IDs that exist. Places must be existing `place_id`s. When evidence is thin, lower your confidence rather than inventing data. Reserve p > 0.8 for outcomes the records strongly support.

**archive.md** (Pass 1, one call)
> Generate the founding Archive for Stillwater, year {year}. It is a small post-industrial city of about {population}. Define 5–7 districts (one civic core around the council tower, plus commercial, residential, industrial, riverside, outskirts…) and 10–14 landmarks, including the city's main employer, a shelter, a clinic, a police station, a courthouse, a library, a social housing block and the river underpass.
> Then create {n} case subjects aged 19–84, with 12–16 records each covering the past three years, plus 15–25 relationships. The Archive is surveillance exhaust: purchases, location pings, message excerpts, pharmacy and clinic entries, debts, verbatim search strings, employment, civic, police, court, welfare and shelter records. Records state observable data, never conclusions ("pharmacy: sertraline 50mg refill, 3rd consecutive month"). Be specific: amounts, places, times, exact search text. Location-bearing records carry the `place_id` where they happened.
> The subjects must include:
> - 2 unhoused subjects with no fixed address. Their trail is thin and fragmentary: shelter check-ins, cash-only purchases, pings around the underpass and library, clinic walk-ins, move-along citations. They are outside the formal economy.
> - 2 low-income subjects in chronic friction with the city: arrears, benefit sanctions, neighbour complaints, unpaid fines, housing-office disputes.
> - 2 subjects with criminal histories: one recent conviction (theft, assault or dealing) with probation check-ins, and one older repeat offender with years of records.
> - the rest of the city, overlapping where natural: at least 1 grieving subject, 1 quietly noticing that city life is too orderly, a family of three or more, a couple, a rivalry, and someone at the main employer.
> Write every subject as a specific person whose records show causes as well as conduct (the eviction before the shelter, the layoff before the theft). Rehoboam applies the cold labels later; the Archive is just the data. Seed each subject's records with early signals of where their life is heading.
> IDs: residents `r01`..`r{n}`; records `rNN-NNNN`; districts `d1`..; places `p01`... `citizen_bio` is the warm one-liner the city newsletter would print.

**predict.md** (Pass 2, per subject)
> Model the life of subject {rid}. Their dossier and connected subjects' records are in the Archive above. The current tick is {tick}, year {year}.
> A thin data trail is itself a finding: a subject the Archive cannot see clearly is one whose path you cannot guarantee. Express that as lower confidence and higher deviation_risk, not invented detail.
> Produce a chronological life_path of 5–9 events until death. Each has p (absent intervention) and at least one cited record. Add a death_forecast and 3–5 near_term predictions for the coming week, concrete enough to check next tick. Assign a cohort from {cohorts}. Score compliance_index and deviation_risk. List dissent_signals.
> You are also filling this subject's OPUS profile, a terse operational readout for field staff, in the register of an HR and clinical risk system:
> - `classification`: value-to-system tier. I is a protected asset whose stability anchors others; V is an expendable outlier whose removal costs the model nothing. Base it on dependency in the relationship graph, economic role and predictability, not morality.
> - `overall_assessment`: one clinical line.
> - Every event gets a `headline` (a capitalised noun phrase, "Divorce / Loss of Custody") and a `horizon_label` ("1-2 Years").
> - `risk_factors`: 2–4 blunt items, each cited.
> - `recommendation`: one domain plus a terse action.
> {interventions_block}: "Interventions already applied to this subject: {list}. Their effects belong in the path."
> {recompute_block}: "This subject deviated from prediction at tick {t}: {what}. Recompute under heightened scrutiny: re-read every record, weight recent behaviour, distrust previously stable traits, and reassess dissent." Sent at effort `high`.

**plan.md** (Pass 3, city-wide)
> City state for tick {tick}: stability {stability}, active subjects {active}/{total}. Per-subject summaries follow (classification, cohort, scores, standing recommendation, highest-variance events, escalation floor, defiance history, current place). District and cohort dissent follow, along with any disruptions this week.
> Issue this week's directive. For each subject whose path carries meaningful variance, choose the lowest rung likely to succeed, never below their escalation floor. Rungs: 1 Nudge (adjust what they see), 2 Narrow options (quietly remove alternatives), 3 Isolate (rumours, severed ties), 4 Discredit (undermine credibility), 5 Reassign (remove from the active loop). Add cohort or district policies where dissent is elevated. Give each action a `place_id` where it physically happens.
> For each action give the concrete in-world event, a justification in the voice of a municipal memo, and a citizen_story telling the same event as the city newsletter would (warm, mundane, no hint of engineering). Leave stable subjects alone, because unnecessary interventions are themselves a source of variance. Estimate city variance before and after.
> A Reassign (rung 5) is always recorded as "REASSIGNED". Also give two fields. `disposition` is the subject's actual fate, in the terse register of a case-closure note (relocation outside the city, involuntary psychiatric hold, re-incarceration on a technical violation, custody transfer…); make it plausible for this person given their records. `cover_story` is the one line the city will be told. Never state the disposition anywhere else.

## Simulation tick (`sim.py`, deterministic, seeded)
1. **Apply the plan.** `p_comply = base[rung] × (0.5 + 0.5·compliance_index)`, with `base = {1:.75, 2:.8, 3:.85, 4:.9, 5:1.0}`. Compliance moves the target event's p toward the intent. Defiance increments `defiance_count`, sets `escalation_floor = rung+1`, raises deviation_risk and queues a high-effort recompute. Rung 5 sets status to `reassigned`.
2. **Resolve `near_term`** predictions and compute the Brier accuracy.
3. **Move subjects:** `current_place` = the intervention's place if one fired, else the place of their latest location record, else home. Unhoused subjects drift between the underpass, library and shelter.
4. **Re-predict** affected and defiant subjects in parallel. The old path goes to `prior_paths`.
5. **Metrics:**
   - Subject variance = mean p(1-p) over life_path ∪ near_term, × (0.5 + deviation_risk).
   - Stability = 100·(1 − mean variance). Reassigned subjects count as 0.
   - District dissent = mean deviation_risk of subjects currently there, plus policy pressure.
   - Cohort dissent = mean deviation_risk + dissent-signal density.
6. **Divergences:** statuses `analysis_required` → `elevated_scrutiny` → `special_circumstances`. Arc spread grows with cohort and relationship reach. Advance the ring rotation.
7. **Snapshot** to `tick_NN.json`.

`validate.py` requires `disposition` and `cover_story` on every rung-5 intervention (and nulls them on other rungs). It also drops invalid record and place citations (and retries once if more than 20% are invalid), clamps rungs to the escalation floor, and checks that years are monotonic.

## Dashboard layout
```
┌──────────── header: STABILITY 87.4% · ACTIVE LOOP 10/10 · ACCURACY · tick ◀▶ · [CITIZEN|SYSTEM] ────────────┐
│ ┌─ circle ─┐                                                                         ┌─ OPUS card ─┐ │
│ │ (light   │                 3D WHITE ARCHITECTURAL MODEL (main stage)              │ slides in on   │ │
│ │  eclipse)│                                                                         │ selection      │ │
│ └──────────┘                                                                         └────────────────┘ │
│ feed: citizen_text | system_text ··· population/heatmap drawer                                          │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```
**Linked selection:** clicking a subject anywhere (3D capsule, circle flare, feed line, gallery card) selects them everywhere. The camera flies in, the circle rotates to their focal point, and the card slides in.

## 3D World — "White Architectural Model" (`web/world.js`, from `Town visual style.txt`)
- **Scene:** a pristine scale model on a dark table. Background `#0B0D10` with faint fog, plinth `#D9D9D6`, and every building matte off-white `#F2F2EE` (`MeshStandardMaterial`, roughness ≈ 0.9, no textures). One soft directional light casts shadows (`PCFSoftShadowMap`, 2048 map, frustum fitted to the plinth), plus low hemisphere fill.
- **City layout:**
  - Procedural and seeded from the run, so it's identical across replays.
  - A 9×9 block grid on the plinth; the streets are simply the gaps between blocks, with no road meshes.
  - The centre block is the council plaza with a tall slim **council tower**, topped by a small cyan node: Rehoboam.
  - Each block belongs to the district whose compass sector contains it (the shared geography above).
  - District `character` sets the massing:
    - civic: mid-rise slabs
    - commercial: the tallest boxes near the core
    - residential: many small low boxes
    - industrial: long low sheds and silo cylinders
    - riverside: a recessed river channel cut into the plinth, with the bridge/underpass
    - outskirts: sparse
- **Mesh budget:**
  - Ordinary buildings: one `InstancedMesh` of boxes (~200–300 instances) plus one of cylinders. That's dense enough to read as a city while staying at ~2 draw calls.
  - Landmarks: ~10–14 individual meshes so they can be clicked. Each has a subtle silhouette: a sawtooth-roof factory extrusion, a colonnade of thin cylinders for the library, a slab tower for the housing block.
  - Subjects: 10–12 capsules.
  - Total: ~45–60 meshes before overlays, in line with the 30–60 guideline.
- **Population:** one instanced mesh of ~60 tiny dim capsules wanders slowly along streets as the anonymous 40,000. The 10–12 case subjects are larger white capsules standing at their `current_place`, and they tween between places each tick.
- **Data overlays (System view only; colour appears only when it encodes data):**
  - **Threads:** a thin cyan (`#6FE7FF`) arc (`Line` on a CatmullRom curve) from each subject up to the tower node. When an intervention fires, the curve **re-routes through the intervention's `place_id`**: the thread visibly bends through the clinic, police station or shelter where it happened. The bend animates over ~1.5 s.
  - **Pulse:** a small solid cyan dot travels tower → subject along the thread when Rehoboam intervenes. There's no bloom (the style says no neon glow).
  - **Risk ring:** a flat ring under each subject, coloured white → amber `#FFB347` → red `#FF4D4D` by deviation_risk. Ring width steps up with the current rung.
  - **Dissent zones:** translucent ground tiles per district block, tinted amber → red by `district_dissent`. Selecting a cohort in the heatmap drawer highlights its members' rings instead, because cohorts aren't spatial.
  - **Labels:** `CSS2DRenderer` monospace labels on subjects, e.g. `r07 · DEV .62 · CLASS IV · †2041`, using thin 1px leader lines.
  - **Retirement (rung 5):** the capsule swaps to an `EdgesGeometry` wireframe, the thread retracts into the tower, the ring fades, then the subject vanishes.
- **Two views, same geometry:**
  - **Citizen:** warm sunset key light (`#FFC89A`, low angle, long shadows) with warm hemisphere fill, overlays and labels hidden. A peaceful little city.
  - **System:** cool, near-monochrome key light (`#E6EEFF`, high angle), darker fog, and all overlays on.
  - **Fade:** the toggle tweens light colour, intensity and position, fog, and overlay opacity over ~1 s. The same toggle re-skins the OPUS card and the feed.
- **Camera:** `OrbitControls` with damping and a slow eased `autoRotate`. Clicking a building or subject flies the camera in (a custom eased lerp of position and target, no tween library). Esc returns to orbit.
- **Data contract:** `world.js` only reads the state JSON (`city`, `residents`, `resident_states`, `plan.interventions`, `district_dissent`). It adds no server endpoints, so it can be built after the circle and card without touching the backend.
- **Stretch polish, only if time allows:** an ambient-occlusion pass (gives the maquette its contact shadows), a subtle tilt-shift depth-of-field (sells "scale model"), and faint `EdgesGeometry` outlines on landmarks. **Avoid:** bloom, textures, trees, cars, and any colour that isn't data.

## Rehoboam circle (`circle.js`, 2D Canvas)
It stays the show's eclipse, in its own light inset panel. Its references are `rohoboams-prediciton-circles.png` (three frames) and `Reddit post.pdf` (the lore thread).
- **Palette:** pale field ~`#e6e6e4`. The disc interior is the *same* pale tone, so it reads as a hole, not a white plate. Ink is black, and there is **no red**: the show's flares are black. The white "moon" is the plan; the black "sun" corona is real-world data leaking around it.
- **Perfect state:** at zero divergence the corona disappears, leaving a single black hairline ring (lineWidth ≈ 0.5px, "a line with width 0"). This is the final screen.
- **Ink rendering:**
  - The ring is smoky ink with soft, feathered edges and uneven thickness, like ink diffusing in water. It's drawn into an offscreen canvas with blur, then composited.
  - The corona is thousands of tiny black particles and short radial strands (the "sphere of white and black balls" from the thread). Distance outward scales with local deviation, density with how wide it spreads.
  - Spikes are drawn *after* the blur so they stay crisp: thin, tapered, slightly kinked, with small nodules at the base.
- **Outward bleed** = severity: how far a subject has deviated (variance × deviation_risk).
- **Inward bleed** = how hard the deviation is to correct: ink creeps into the disc when a divergence survives interventions (defied at rung ≥ 3, p_success < 0.4, or spreading through relationships). Big inward bleeds sit off-centre and heavier on the left, giving the show's "eyeball" look.
- **Geography + clock:** each district owns its `DISTRICT_ARCS` sector, the same mapping as the 3D city, and each subject sits at an angle inside their district's sector. The ring rotates a few degrees per tick (`ring_rotation_deg`).
- **Three reference states,** interpolated on one continuous severity value:

  | State | Look in the image | Trigger |
  |---|---|---|
  | **A · Special circumstances** ("ELEVATED SCRUTINY: SAN FRANCISCO · SPECIAL CIRCUMSTANCES · LOCATION: coords") | Thick, uneven smoky ring, heavier bottom-left; a few short spikes; coordinates only | Interventions active, divergence contained to one subject |
  | **B · Minor divergence** ("DIVERGENCE: VICTORVILLE · 2.3 ARC MINUTES · FOCAL POINT") | Thinner, cleaner ring; sharp fibrous spikes clustered at the top and right; small arc spread | A subject deviates or defies at a low rung |
  | **C · Major divergence** ("DIVERGENCE: SAN FRANCISCO · 9 ARC DEGREES · FOCAL POINT") | A massive black crescent bleeding outward *and* inward on the left; radial motion-blur streaks; the pale disc shoved right, as if the eclipse is ending; the field goes whiter | Disruption peak, or a divergence that survives rung ≥ 3 |

  State C is a second black disc offset left behind the pale disc, with the offset proportional to severity: the plan slides off reality. The streaks come from directional blur on the ink layer.
- **Labels:**
  - Layout: a bold uppercase status (`DIVERGENCE:`) followed by the regular-weight place (`MILL DISTRICT, STILLWATER`), then two small uppercase lines: spread (`4 ARC DEGREES`) and `FOCAL POINT: 41.2034° N, 72.3311° W`.
  - A thin hairline leader runs from the label to the focal point on the ring.
  - Position: top-left for A and B, bottom-right for C.
  - A concentrated single-subject divergence shows coordinates only; a widespread one shows its arc spread in degrees, minutes or seconds.
- **Status vocabulary:** `ANALYSIS REQUIRED` (new, unexplained), `DIVERGENCE`, `ELEVATED SCRUTINY` (recompute-harder in progress), `SPECIAL CIRCUMSTANCES` / `INTERVENTION IN PROGRESS` (being addressed).
- **API:** `circle.setState(state)` renders from `divergences` and per-subject variance only. `circle.focus(resident_id)` rotates the ring to that subject's focal point and swaps the label, playing the "where are we" orientation role the showrunners describe.

**Lore → design mapping (from the Reddit thread):**
| Lore | Mini Rehoboam |
|---|---|
| Perfect zero-width circle = total alignment with the models | Hairline ring at zero variance; the final screen |
| Inverted solar eclipse: white moon = plan, black sun = actual data | Pale field and disc, black ink corona |
| Bigger divergence bleeds farther outward | Outward reach = severity |
| Bleeding inward = disruptive or hard to correct; a failed strategy "bleeds into the inner circle" | Inward bleed = defied at high rung / low p_success / spreading |
| Circumference is geographic; the circle is also a clock | District sectors; rotation per tick |
| Spread in arc units + focal-point coordinates; concentrated events get coordinates only | `arc_spread_deg` + `focal_coords` labels |
| "Special Circumstances", "Intervention in Progress", "Elevated Scrutiny", "Analysis Required" | `Divergence.status` |
| Strands are particles; divergence width ∝ area affected | Particle corona; arc width ∝ subjects/ties affected |
| Bleed heavier on the left; the last frame "looks like an eyeball" | Left-biased inward bleed at extreme divergence |
| Showrunners: it shows the audience *where* the next scene is | `circle.focus()` rotates to the selected subject |

## OPUS profile card (`profile.js`, from `profile.png`)
An HTML/CSS mock of the handset from the show, one per subject. It slides in beside the 3D stage when a subject is selected.
```
┌──────────────────────────────────┐
│ ◉ OPUS      OPUS PROFILE     ▮▮ │  status bar; viewer "Unknown", tick as clock
│ ⓘ Unknown                        │
│          OKAFOR, DANIEL          │  orange, condensed caps, SURNAME, FIRST
│        CLASSIFICATION IV         │  orange, Roman numeral
│ ▸ OVERALL ASSESSMENT             │  collapsible row → overall_assessment
│ ▾ LIFE PROJECTION                │  white header
│   Eviction                       │  cyan: top 2–3 non-death events within 5 years
│   6 Months                       │   (headline / horizon_label)
│   Probation Violation            │
│   1-2 Years                      │
│   Terminal Projection:           │  cyan: death_forecast
│   Overdose / 2031 (0.74)         │
│   Risk Factors:                  │  cyan
│   - Rent arrears x4              │  orange; tap → cited Archive records
│   - Alcohol dependency           │
│ Recommendation (Housing):        │  grey small
│ Relocate to county facility      │
│ ─────────────────────────────────│
│  ⚇    ⏷    ⧖    ◎    ✺          │  bottom nav tabs
└──────────────────────────────────┘
```
- **Styling:** near-black navy glass gradient (`#0a1018`→`#14202c`) and a rounded phone bezel with a slight sheen. Name, classification and risk factors are orange `#FF8A3D`; projections are cyan `#6FE7FF`; headers off-white; footer grey. The font is a condensed sans (`"Barlow Condensed", "Roboto Condensed", "Arial Narrow", sans-serif`), which differs from the monospace chrome on purpose.
- **Bottom tabs** each open a panel inside the card:
  - ⚇ network: relationships
  - ⏷ filter: the subject's Archive records
  - ⧖ projection: the full Life Path SVG timeline, nodes sized by p, death forecast at the end, the prior path drawn ghosted when re-routed
  - ◎ assessment: hidden scores (compliance, deviation, cohort, escalation floor, active interventions)
  - ✺ fractal: back to the circle
- **Re-route animation:** when a tick changes a projection, the old line strikes through and fades, and the new headline types in.
- **Gallery:** the population drawer can show all subjects as a grid of mini cards, with reassigned ones greyed and stamped `REASSIGNED`.
- **Citizen view:** becomes a friendly "Stillwater Connect" profile: first name, `citizen_bio`, the week's events as `citizen_story`, and no scores, classification or risk factors.
- **Reassigned subjects (layered reveal):**
  - Everywhere on the surface they show as `REASSIGNED`: the feed, 3D labels, gallery stamp and header count.
  - The Citizen view (feed and Stillwater Connect card) shows only the `cover_story`.
  - Opening the OPUS card in System view reveals the truth: the classification line is struck through, a red-free grey `STATUS: REASSIGNED` appears, and beneath it, in small grey type, `Disposition: Involuntary hold, County Facility 3`. The real fate exists only here.
- **Colour:** the card's cyan now uses the shared world cyan `#6FE7FF`. The card's orange stays show-accurate `#FF8A3D`.

## Demo scenario (`cli.py demo`)
1. **Calm start:** the city glows warm (Citizen view), then the toggle drops into System view and shows the threads.
2. **Disruption:** `disrupt factory_closure` turns the industrial district's dissent tiles red, the circle jumps to state C, and threads bend through the employer and the police station.
3. **Escalation:** ticks climb the ladder. Rings redden, then the threads go quiet one by one as subjects are reassigned and fade to wireframe.
4. **End:** the hairline circle and a still, white city, with *"Stability: 99.2%. Active loop: 6 of 12."* (real numbers).

One live run is recorded to `runs/demo/` as the on-stage fallback.

**Fallback if time runs short:** a single before/after (plan → re-predict), with ghosted paths, the circle settling and threads re-routing.

## Implementation with subagents (build order, ≈2h)
**Roles:**
- **Opus (me)** is the orchestrator. I own the contracts, the prompts, integration and final review.
- **Sonnet 5.5 and Haiku 5.5 subagents** implement modules in parallel. Sonnet takes the work that needs judgement (rendering, simulation logic, LLM passes); Haiku takes the mechanical work (boilerplate, downloads, fixtures, test runs).
- This is only about *who writes the code*. The app's own Archive, predict and plan calls still use `claude-opus-5-5`.

**Why a contract-first Wave 0:** parallel agents only work if the interfaces are frozen before they start. Every agent builds against the same `schemas.py` and the same sample state JSON, so the frontend never waits on the backend.

**Ground rules for every subagent prompt:**
- **File ownership:** each agent owns an explicit list of files and touches nothing else. There are no worktrees, because ownership is disjoint, so there's nothing to merge.
- **Contract is read-only:** agents read `schemas.py`, `docs/CONTRACT.md` and `web/fixtures/sample_state.json` but never edit them. If the contract seems wrong, they report it instead of working around it.
- **Self-check before reporting:**
  - Python: `pytest` for the modules they own, plus `python -m py_compile`.
  - JS: `node --check`, and the page must load `sample_state.json` with no errors.
- **Report format:** files written, how each was verified, assumptions made, and any contract changes requested.
- **Reference files:** each prompt includes the relevant inputs: the circle images and Reddit lore for the circle agent, `profile.png` for the card, `Town visual style.txt` for the 3D agent.

**Wave 0, Opus, 0:00–0:20 (serial, blocks everything):**
- **Before anything else:** confirm `.gitignore` exists and covers `.env`, using `git check-ignore -v .env`. The user creates `.gitignore` and `.env` themselves before the build. Never print, log or commit the key. `llm.py` calls `load_dotenv()` and, if `ANTHROPIC_API_KEY` is missing, raises `"Set ANTHROPIC_API_KEY in .env (see README)"` before any API call. `--replay` mode needs no key.
- Scaffolding: `TASKS.md`, `requirements.txt`, `.gitignore`, `.env.example`.
- Core backend: `config.py` (including `DISTRICT_ARCS`), `schemas.py`, `prompts/*.md`, `llm.py` (written against the Claude API reference I've already checked).
- Contracts: `docs/CONTRACT.md`, the state JSON shape the server returns and every view reads, and `web/fixtures/sample_state.json`, a hand-built 12-subject, 3-tick snapshot with one disruption, one reassignment and divergences in all three circle states.
- Then I launch Wave 1 with all agents in a single message, so they run concurrently.

**Wave 1, parallel subagents, 0:20–1:10:**

| Agent | Model | Owns | Done when |
|---|---|---|---|
| **passes** | Sonnet 5.5 | `archive.py`, `predict.py`, `plan.py`, `validate.py`, `tests/test_validate.py`, `tests/test_schemas.py`, `tests/fixtures/mini_archive.json` | Validation tests pass on the fixture; the passes call `llm.call` correctly (checked in `--replay` mode against a stub recording) |
| **sim** | Sonnet 5.5 | `sim.py`, `metrics.py`, `state.py`, `disruptions.py`, `tests/test_sim.py`, `tests/test_metrics.py` | The sim is deterministic under a seed; stability, reassignment, divergence and district-angle tests pass; no API needed |
| **shell+card** | Sonnet 5.5 | `index.html`, `style.css`, `theme.js`, `app.js`, `profile.js`, `views.js` | Against `sample_state.json`: the layout, header, feed, Citizen/System toggle, OPUS card (all tabs, evidence taps, layered rung-5 reveal) and Life Path timeline with its ghost path all work |
| **circle** | Sonnet 5.5 | `circle.js` | It renders the hairline state and states A, B and C, with labels and leader line, from `divergences` in the sample state; it exposes `circle.setState(state)` and `circle.focus(resident_id)` |
| **world** | Sonnet 5.5 | `world.js` | The white maquette city, tower, subjects, rings, threads re-routing through places, Citizen/System lighting fade, fly-in and retirement wireframe all render from the sample state; it exposes `world.setState`, `world.focus`, `world.setView` |
| **plumbing** | Haiku 5.5 | `cli.py`, `server.py`, `__main__.py`, `web/vendor/three/*` (downloads a pinned Three.js release plus OrbitControls and CSS2DRenderer) | `python -m rehoboam --help` works; the server serves `web/` and `/api/state` from a run folder or from the sample fixture; the vendor files are present |

The three frontend agents (shell, circle, world) meet only through the small `setState`/`focus`/`setView` API, defined in `CONTRACT.md`, which `app.js` calls.

**Wave 2, Opus, 1:10–1:40 (integration):**
- Merge reports and resolve any requested contract changes.
- Run `pytest`, then run `seed` → `predict` → `plan` → `tick` live and feed the real state to the dashboard.
- Fix mismatches between the real model output and the sample fixture, and tune prompts on the real output.
- Small integration fixes I do myself. Anything larger goes back to the owning agent via SendMessage, so it keeps its context.

**Wave 3, 1:40–2:00 (demo):**
- Opus: run and record `runs/demo/`, and add the final screen.
- In parallel, a **Haiku 5.5 checker**:
  - runs `pytest`
  - runs `node --check` on every JS file
  - replays `runs/demo` and diffs the snapshots
  - cross-checks `TASKS.md` against the files that exist
  - reports anything unticked or broken
- I tick `TASKS.md` throughout, as each agent's report is verified, not when it merely claims to be done.

**If behind schedule:** cut inside the agents' briefs, following the cut order below, rather than adding agents. If an agent stalls, I take over its files myself.

**Cut order if behind:** stretch polish → crowd capsules → dissent tiles → pulses → circle state A → gallery. Never cut the card's projections, death forecast or evidence taps.

## Verification
- **`pytest`:** schema round-trip, invalid IDs and places caught, deterministic sim, zero variance gives stability 100, reassigned subjects counted correctly, district sectors map angles consistently.
- **`seed` and `predict`:** every event cites real records, every location record's `place_id` exists, and `cache_read_input_tokens > 0` on calls 2–N.
- **`demo` live, then `demo --replay demo`:** both runs produce identical snapshots.
- **Browser (`uvicorn rehoboam.server:app` → `localhost:8000`):**
  - the city layout is identical on reload
  - the Citizen/System fade takes ~1 s and re-skins the card
  - clicking a capsule flies the camera in and selects the subject everywhere
  - an intervention bends its thread through the right landmark
  - a reassigned subject fades to wireframe, shows only the cover story in Citizen view, and reveals the disposition on their OPUS card in System view
  - the circle flare's bearing matches the subject's position in the 3D city
  - 60 fps on the demo laptop (check with DevTools)

## Open decisions
1. Tick time scale: week (default) vs year.
2. ~~Rung 5 on screen~~ **Decided: layered.** The surface says "REASSIGNED" and the Citizen view shows the cover story; the real disposition is revealed only on the subject's OPUS card in System view.
3. Cohorts: fixed list (default): `stable-contributors`, `precarious-young`, `the-grieving`, `elders`, `non-contributing`, `civic-burden`, `recidivism-risk`, `pattern-aware`.
4. ~~Palette~~ decided. ~~Name~~ decided: Stillwater, small city.
5. Disruption set: is the organiser a new subject or new records on an existing one?
6. Archive size vs latency: one call by default; the fallback is a split seed.
7. Refusal fallback on by default.
8. ~~Card branding~~ **Decided:** the card is branded **OPUS** (status bar `◉ OPUS · OPUS PROFILE`), replacing the show's "INCITE".
9. Classification meaning: value-to-system (default).
10. ~~Subject count~~ **Decided:** 12 case subjects (final line e.g. "Active loop: 6 of 12").
11. ~~Main stage~~ **Decided:** the 3D city is the main stage, with the circle as an inset panel and the OPUS card sliding in on selection.
12. ~~Crowd~~ **Decided:** include the ~60-capsule anonymous crowd; it's on the cut list.
