"""The deterministic simulation: no API calls, no global random. Every decision draws from
random.Random(f"{seed}:{tick}:{key}") so results are order-independent and replay byte-identically.

Tick flow (runner.py): begin_tick -> make_plan -> apply_plan -> predict(rids) -> finalize.
"""
import random
from datetime import date

from . import config, disruptions, geo, metrics
from .schemas import (
    Archive, CityState, CityPlan, DisruptionEvent, FeedItem, Intervention, InterventionOutcome, Metrics,
    NearTermOutcome, Prediction, ResidentState,
)

LOCATION_WINDOW_DAYS = 10   # after tick 0, a location record older than this no longer pins a subject in place


# ---------------------------------------------------------------- small helpers
def _rng(state: CityState, key: str) -> random.Random:
    return random.Random(f"{state.seed}:{state.tick}:{key}")


def archive_of(state: CityState) -> Archive:
    return Archive(city=state.city, residents=state.residents, records=state.records,
                   relationships=state.relationships)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _landmark(state: CityState, pid: str | None):
    return next((l for l in state.city.landmarks if l.place_id == pid), None)


def _place_name(state: CityState, pid: str | None, did: str | None = None) -> str:
    lm = _landmark(state, pid)
    if lm:
        return lm.name
    return _district_name(state, did) if did else "an unrecorded location"


def _district_name(state: CityState, did: str | None) -> str:
    return next((d.name for d in state.city.districts if d.district_id == did), did or "Stillwater")


def _surname(state: CityState, rid: str) -> str:
    r = next((r for r in state.residents if r.resident_id == rid), None)
    return r.name.split()[-1].upper() if r else rid.upper()


def _closest_tie(state: CityState, rid: str) -> str:
    best = None
    for rel in state.relationships:
        if rid in (rel.a, rel.b):
            other = rel.b if rel.a == rid else rel.a
            if best is None or (rel.strength, other) > (best[0], best[1]):
                best = (rel.strength, other)
    if best is None:
        return "no known contacts"
    r = next((r for r in state.residents if r.resident_id == best[1]), None)
    return r.name if r else best[1]


def _feed(state: CityState, kind: str, citizen: str, system: str, rid: str | None = None,
          did: str | None = None, pid: str | None = None) -> None:
    state.events_feed.append(FeedItem(
        feed_id=f"t{state.tick}-f{len(state.events_feed) + 1}", tick=state.tick, kind=kind, resident_id=rid,
        district_id=did, place_id=pid, citizen_text=citizen, system_text=system))


def _latest_place(state: CityState, rid: str) -> str | None:
    recs = [r for r in state.records if r.resident_id == rid and r.place_id]
    if not recs:
        return None
    latest = max(recs, key=lambda r: (r.date, r.record_id))
    if state.tick > 0:
        try:
            age = (disruptions.tick_date(state) - date.fromisoformat(latest.date[:10])).days
            if age > LOCATION_WINDOW_DAYS:
                return None
        except ValueError:
            pass
    return latest.place_id


def _drift_places(state: CityState) -> list[str]:
    out = []
    for kind in config.UNHOUSED_DRIFT_KINDS:
        out += sorted(l.place_id for l in state.city.landmarks if l.kind == kind)
    return out


def _set_place(state: CityState, rs: ResidentState, pid: str | None, home_district: str) -> None:
    rs.current_place = pid
    lm = _landmark(state, pid)
    rs.current_district = lm.district_id if lm else home_district


def _refresh(state: CityState) -> None:
    """Variance, metrics, dissent, geo and divergences from the current predictions."""
    for rs in state.resident_states:
        rs.variance = 0.0 if rs.status == "reassigned" else metrics.subject_variance(rs.prediction)
    state.metrics = metrics.compute_metrics(state)
    state.district_dissent = metrics.district_dissent(state)
    state.cohort_dissent = metrics.cohort_dissent(state)
    state.geo = geo.build_geo(archive_of(state), state.resident_states)
    state.divergences = metrics.compute_divergences(state)


# ---------------------------------------------------------------- initial_state
def initial_state(archive: Archive, preds: dict[str, Prediction], run_id: str, seed: int = config.SEED) -> CityState:
    drift_probe = CityState.model_construct(seed=seed, tick=0, city=archive.city)
    drift = _drift_places(drift_probe)
    states = []
    for res in archive.residents:
        recs = [r for r in archive.records if r.resident_id == res.resident_id and r.place_id]
        place = max(recs, key=lambda r: (r.date, r.record_id)).place_id if recs else res.home_place
        if place is None and res.housing == "unhoused" and drift:
            place = random.Random(f"{seed}:0:init:{res.resident_id}").choice(drift)
        lm = next((l for l in archive.city.landmarks if l.place_id == place), None)
        states.append(ResidentState(resident_id=res.resident_id, current_place=place,
                                    current_district=lm.district_id if lm else res.home_district,
                                    prediction=preds[res.resident_id]))
    state = CityState(
        run_id=run_id, tick=0, year=archive.city.year, seed=seed, city=archive.city, residents=archive.residents,
        records=archive.records, relationships=archive.relationships, resident_states=states,
        metrics=Metrics(stability=100, variance_mean=0, accuracy=None, brier=None, active=0, total=0,
                        reassigned=0, interventions=0, defiances=0),
        geo=geo.build_geo(archive, states))
    _feed(state, "system", "Welcome to Stillwater Connect: your city, this week.",
          f"ARCHIVE SEALED. {len(states)} SUBJECTS IN ACTIVE LOOP. BASELINE PROJECTIONS COMPUTED.")
    _refresh(state)
    return state


# ---------------------------------------------------------------- begin_tick
def begin_tick(prev: CityState, disruption_ids: list[str]) -> CityState:
    state = prev.model_copy(deep=True)
    state.tick = prev.tick + 1
    state.plan = None
    state.outcomes = []
    state.near_term_results = []
    state.events_feed = []
    state.disruptions = []
    state.divergences = []
    state.district_pressure = {k: round(v * 0.6, 4) for k, v in state.district_pressure.items() if v * 0.6 >= 0.005}
    for did in disruption_ids:
        if did not in disruptions.DISRUPTIONS:
            _feed(state, "system", "", f"UNKNOWN DISRUPTION {did} IGNORED.")
            continue
        ev: DisruptionEvent = disruptions.apply_disruption(state, did, _rng(state, f"disruption:{did}"))
        state.disruptions.append(ev)
        d = disruptions.DISRUPTIONS[did]
        place = _place_name(state, ev.place_id, ev.district_id)
        n = len(metrics.affected_by_disruption(state, ev))
        fmt = dict(place=place, district=_district_name(state, ev.district_id).upper(), n=n)
        _feed(state, "disruption", d.citizen_text.format(**{**fmt, "district": _district_name(state, ev.district_id)}),
              d.system_text.format(**fmt), did=ev.district_id, pid=ev.place_id)
    return state


# ---------------------------------------------------------------- apply_plan
_DEFY_NOTES = [
    "Ignored rung {rung} measure; was observed at {place} with {tie}.",
    "Declined rung {rung} measure and spent the day at {place} with {tie}.",
    "Rung {rung} measure not followed; contacted {tie} near {place} instead.",
    "Disregarded rung {rung} instruction; seen at {place}, in company of {tie}.",
]
_SPONT_NOTES = [
    "Unmodelled departure from routine near {place}; last contact {tie}.",
    "Pattern break: unscheduled visit to {place}; contact with {tie}.",
    "Behaviour outside forecast band at {place}; associated with {tie}.",
]
_COMPLY_NOTES = [
    "Complied with rung {rung} measure.",
    "Followed rung {rung} guidance without incident.",
    "Accepted rung {rung} measure; routine unchanged.",
]
_CITY_NEWS = [
    "{district} community noticeboard has been refreshed this week.",
    "Neighbourhood updates for {district} are now on Stillwater Connect.",
    "A quiet week in {district}: see what's on.",
]


def _apply_effect(rs: ResidentState, iv: Intervention) -> None:
    ev = next((e for e in rs.prediction.life_path if e.event_id == iv.target_event_id), None)
    if ev is None:
        return
    p = ev.p
    if iv.intent == "suppress":
        ev.p = p * 0.5
    elif iv.intent == "induce":
        ev.p = p + (1 - p) * 0.5
    elif iv.intent == "delay":
        ev.year += 1
        ev.p = p * 0.85
    else:  # stabilise: halfway to the nearer of 0 / 1
        target = 0.0 if p < 0.5 else 1.0
        ev.p = p + (target - p) * 0.5
    ev.p = round(_clamp(ev.p), 4)


def apply_plan(state: CityState, plan: CityPlan) -> list[str]:
    state.plan = plan
    rs_by = {s.resident_id: s for s in state.resident_states}
    res_by = {r.resident_id: r for r in state.residents}
    fired_place: dict[str, str | None] = {}
    fired: set[str] = set()
    defiers: list[str] = []
    reassigned_now: list[str] = []
    deferred_feed: list[tuple] = []

    # cohort policies
    for pol in plan.cohort_policies:
        if pol.district_id:
            state.district_pressure[pol.district_id] = round(
                min(1.0, state.district_pressure.get(pol.district_id, 0.0) + 0.08), 4)
        where = _district_name(state, pol.district_id).upper() if pol.district_id else "CITYWIDE"
        _feed(state, "policy", pol.citizen_story,
              f"POLICY {pol.policy_id} {pol.kind.upper()} · {where} · {pol.cohort.upper()}", did=pol.district_id)

    # 1. interventions
    for iv in plan.interventions:
        rs = rs_by.get(iv.resident_id)
        if rs is None or rs.status == "reassigned":
            continue
        rid = iv.resident_id
        rng = _rng(state, f"comply:{iv.intervention_id}:{rid}")
        p_comply = 1.0 if iv.rung >= 5 else (
            config.RUNG_BASE_COMPLY[iv.rung] * (0.5 + 0.5 * rs.prediction.compliance_index))
        roll = rng.random()
        complied = iv.rung >= 5 or roll < p_comply
        rs.interventions_applied.append(iv)
        fired.add(rid)
        fired_place[rid] = iv.place_id
        if iv.rung >= 5:
            rs.status = "reassigned"
            rs.reassigned_tick = state.tick
            rs.disposition = iv.disposition
            rs.cover_story = iv.cover_story
            rs.escalation_floor = 5
            rs.recompute_pending = False
            reassigned_now.append(rid)
            note = "REASSIGNED."
            if iv.place_id:
                _set_place(state, rs, iv.place_id, res_by[rid].home_district)
            deferred_feed.append(("reassign", rid, iv))
        elif complied:
            _apply_effect(rs, iv)
            note = rng.choice(_COMPLY_NOTES).format(rung=iv.rung)
            _feed(state, "intervention", iv.citizen_story,
                  f"{rid} RUNG {iv.rung} {config.LADDER[iv.rung].upper()}: {iv.action}",
                  rid=rid, did=_landmark(state, iv.place_id).district_id if _landmark(state, iv.place_id) else rs.current_district,
                  pid=iv.place_id)
        else:
            rs.defiance_count += 1
            rs.escalation_floor = max(rs.escalation_floor, min(5, iv.rung + 1))
            rs.prediction.deviation_risk = round(
                min(0.98, rs.prediction.deviation_risk + config.DEFIANCE_DEVIATION_BUMP), 3)
            rs.recompute_pending = True
            where = _place_name(state, iv.place_id or rs.current_place, rs.current_district)
            note = rng.choice(_DEFY_NOTES).format(rung=iv.rung, place=where, tie=_closest_tie(state, rid))
            rs.deviation_note = note
            defiers.append(rid)
            _feed(state, "intervention", iv.citizen_story,
                  f"{rid} RUNG {iv.rung} {config.LADDER[iv.rung].upper()}: {iv.action}",
                  rid=rid, pid=iv.place_id, did=rs.current_district)
            _feed(state, "defiance", rng.choice(_CITY_NEWS).format(district=_district_name(state, rs.current_district)),
                  f"{rid} {_surname(state, rid)} DEFIED RUNG {iv.rung}. FLOOR → {rs.escalation_floor}. "
                  f"RECOMPUTE AT HIGH EFFORT.", rid=rid, pid=iv.place_id, did=rs.current_district)
        state.outcomes.append(InterventionOutcome(
            intervention_id=iv.intervention_id, resident_id=rid, rung=iv.rung, p_comply=round(p_comply, 3),
            roll=round(roll, 3), complied=complied, note=note))
    n_active = sum(s.status == "active" for s in state.resident_states)
    for _, rid, iv in deferred_feed:
        _feed(state, "reassignment", iv.cover_story or "", f"{rid} {_surname(state, rid)}: REASSIGNED. "
              f"ACTIVE LOOP {n_active}/{len(state.resident_states)}.", rid=rid, pid=iv.place_id,
              did=rs_by[rid].current_district)

    # 2. resolve the PREVIOUS prediction's near_term (the prediction still held is last tick's)
    for rs in state.resident_states:
        if rs.status != "active":
            continue
        for nt in rs.prediction.near_term:
            rng = _rng(state, f"nt:{rs.resident_id}:{nt.pred_id}")
            q = _clamp(nt.p - 0.15 * rs.prediction.deviation_risk + rng.gauss(0, 0.08))
            state.near_term_results.append(NearTermOutcome(
                pred_id=nt.pred_id, resident_id=rs.resident_id, prediction=nt.prediction, p=nt.p,
                occurred=rng.random() < q))

    # 3. move subjects
    drift = _drift_places(state)
    for rs in sorted(state.resident_states, key=lambda s: s.resident_id):
        rid = rs.resident_id
        if rs.status == "reassigned":
            continue
        res = res_by[rid]
        if fired_place.get(rid):
            pid = fired_place[rid]
        elif res.housing == "unhoused":
            rng = _rng(state, f"drift:{rid}")
            others = [p for p in drift if p != rs.current_place]
            pid = rs.current_place
            if others and (rs.current_place not in drift or rng.random() < 0.5):
                pid = rng.choice(others)
        else:
            pid = _latest_place(state, rid) or res.home_place
        _set_place(state, rs, pid if pid else rs.current_place, res.home_district)

    # spontaneous deviation
    spont: list[str] = []
    for rs in sorted(state.resident_states, key=lambda s: s.resident_id):
        rid = rs.resident_id
        if rs.status != "active" or rid in fired:
            continue
        rng = _rng(state, f"spont:{rid}")
        if rng.random() < rs.prediction.deviation_risk * 0.12:
            note = rng.choice(_SPONT_NOTES).format(place=_place_name(state, rs.current_place, rs.current_district),
                                                   tie=_closest_tie(state, rid))
            rs.recompute_pending = True
            rs.deviation_note = note
            spont.append(rid)
            _feed(state, "prediction", rng.choice(_CITY_NEWS).format(district=_district_name(state, rs.current_district)),
                  f"{rid} {_surname(state, rid)}: {metrics.ANALYSIS_MARK}. {note}", rid=rid,
                  pid=rs.current_place, did=rs.current_district)

    # 4. rids to re-predict
    out = set(fired) | set(defiers) | set(spont)
    for ev in state.disruptions:
        out |= set(metrics.affected_by_disruption(state, ev))
    return sorted(r for r in out if r in rs_by and rs_by[r].status == "active")


# ---------------------------------------------------------------- finalize
_CITIZEN_RESOLUTION = {
    "career": "{first} is exploring some new work opportunities in {district}.",
    "financial": "{first} has a fresh budgeting plan from the community advice desk.",
    "health": "{first} has a new care plan in place, with support close to home.",
    "family": "{first} is spending more time with family this season.",
    "relocation": "{first} is weighing a fresh start, with the city's help.",
    "legal": "{first} has caught up on paperwork with the help of a caseworker.",
    "social": "{first} has been getting out and about around {district}.",
    "civic": "{first} has been taking part in local life in {district}.",
}


def _first_name(state: CityState, rid: str) -> str:
    r = next((r for r in state.residents if r.resident_id == rid), None)
    return r.name.split()[0] if r else rid


def finalize(state: CityState, new_preds: dict[str, Prediction]) -> CityState:
    rerouted: list[str] = []
    for rid in sorted(new_preds):
        rs = next((s for s in state.resident_states if s.resident_id == rid), None)
        if rs is None or rs.status == "reassigned":
            continue
        new = new_preds[rid]
        old_path = [e.model_dump() for e in rs.prediction.life_path]
        if old_path != [e.model_dump() for e in new.life_path]:
            rs.prior_paths = (rs.prior_paths + [rs.prediction.life_path])[-3:]
            rerouted.append(rid)
        rs.prediction = new
    pending = [s for s in state.resident_states if s.recompute_pending]
    _refresh(state)                       # divergences see recompute_pending / defiance as elevated scrutiny
    for s in pending:
        s.recompute_pending = False
    state.ring_rotation_deg = round(
        state.ring_rotation_deg + config.RING_ROTATION_PER_TICK * (1 + state.metrics.variance_mean), 3)
    by = {s.resident_id: s for s in state.resident_states}
    for rid in rerouted:
        rs = by[rid]
        head = rs.prediction.life_path[0].headline if rs.prediction.life_path else "NEW PATH"
        kind = rs.prediction.life_path[0].kind if rs.prediction.life_path else "social"
        first = _first_name(state, rid)
        _feed(state, "resolution",
              _CITIZEN_RESOLUTION.get(kind, "{first} has a lot to look forward to this season.").format(
                  first=first, district=_district_name(state, rs.current_district)),
              f"{rid} {_surname(state, rid)}: PATH RE-ROUTED: '{head}'", rid=rid, pid=rs.current_place,
              did=rs.current_district)
    return state
