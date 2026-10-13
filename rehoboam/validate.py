"""Post-parse validation. Pure functions: no I/O, no LLM calls."""
from __future__ import annotations

import difflib

from . import config
from .schemas import Archive, CityPlan, Prediction, ResidentState


def _unique_ids(items: list, attr: str) -> tuple[list, int]:
    """Drop later items whose id repeats an earlier one. Returns (kept, n_dropped)."""
    seen: set[str] = set()
    kept = []
    for it in items:
        v = getattr(it, attr)
        if v in seen:
            continue
        seen.add(v)
        kept.append(it)
    return kept, len(items) - len(kept)


def _rename_dupes(items: list, attr: str) -> int:
    """Make ids unique in place by suffixing -2, -3, ... Returns number renamed."""
    seen: set[str] = set()
    n = 0
    for it in items:
        v = getattr(it, attr)
        if v in seen:
            i = 2
            while f"{v}-{i}" in seen:
                i += 1
            v = f"{v}-{i}"
            setattr(it, attr, v)
            n += 1
        seen.add(v)
    return n


def _filter_evidence(ev: list[str], valid: set[str], counts: list[int]) -> list[str]:
    """counts = [invalid, total], updated in place."""
    out = []
    for e in ev:
        counts[1] += 1
        if e in valid:
            out.append(e)
        else:
            counts[0] += 1
    return out


# ---------------------------------------------------------------- archive
def validate_archive(a: Archive) -> tuple[Archive, list[str]]:
    a = a.model_copy(deep=True)
    warns: list[str] = []
    city = a.city

    city.districts, n = _unique_ids(city.districts, "district_id")
    if n:
        warns.append(f"dropped {n} duplicate district ids")
    city.landmarks, n = _unique_ids(city.landmarks, "place_id")
    if n:
        warns.append(f"dropped {n} duplicate landmark ids")
    a.residents, n = _unique_ids(a.residents, "resident_id")
    if n:
        warns.append(f"dropped {n} duplicate resident ids")
    a.records, n = _unique_ids(a.records, "record_id")
    if n:
        warns.append(f"dropped {n} duplicate record ids")

    dids = {d.district_id for d in city.districts}
    pids = {p.place_id for p in city.landmarks}
    rids = {r.resident_id for r in a.residents}
    first_d = city.districts[0].district_id if city.districts else ""

    for p in city.landmarks:
        if p.district_id not in dids:
            warns.append(f"landmark {p.place_id}: unknown district {p.district_id} -> {first_d}")
            p.district_id = first_d

    for r in a.residents:
        if r.home_district not in dids:
            warns.append(f"{r.resident_id}: unknown home_district {r.home_district} -> {first_d}")
            r.home_district = first_d
        if r.home_place is not None and r.home_place not in pids:
            warns.append(f"{r.resident_id}: unknown home_place {r.home_place} -> None")
            r.home_place = None
        if r.housing == "unhoused" and r.home_place is not None:
            warns.append(f"{r.resident_id}: unhoused but had home_place; cleared")
            r.home_place = None

    before = len(a.records)
    a.records = [x for x in a.records if x.resident_id in rids]
    if len(a.records) != before:
        warns.append(f"dropped {before - len(a.records)} records for unknown residents")
    for x in a.records:
        if x.place_id is not None and x.place_id not in pids:
            warns.append(f"record {x.record_id}: unknown place_id {x.place_id} -> None")
            x.place_id = None

    before = len(a.relationships)
    a.relationships = [x for x in a.relationships if x.a in rids and x.b in rids and x.a != x.b]
    if len(a.relationships) != before:
        warns.append(f"dropped {before - len(a.relationships)} relationships with unknown/self residents")

    if not any(p.kind == "council" for p in city.landmarks):
        warns.append("no council landmark")
    if len(city.districts) < 5:
        warns.append(f"only {len(city.districts)} districts (<5)")
    if len(city.landmarks) < 10:
        warns.append(f"only {len(city.landmarks)} landmarks (<10)")
    return a, warns


# ---------------------------------------------------------------- prediction
def validate_prediction(p: Prediction, archive: Archive, rid: str) -> tuple[Prediction, list[str], float]:
    p = p.model_copy(deep=True)
    warns: list[str] = []
    valid = {r.record_id for r in archive.records}
    counts = [0, 0]  # invalid, total

    if p.resident_id != rid:
        warns.append(f"resident_id {p.resident_id} forced to {rid}")
        p.resident_id = rid

    if p.cohort not in config.COHORTS:
        m = difflib.get_close_matches(p.cohort, config.COHORTS, n=1, cutoff=0.4)
        new = m[0] if m else "stable-contributors"
        warns.append(f"cohort {p.cohort!r} -> {new}")
        p.cohort = new

    for ev in p.life_path:
        ev.evidence = _filter_evidence(ev.evidence, valid, counts)
    p.death_forecast.evidence = _filter_evidence(p.death_forecast.evidence, valid, counts)
    for n in p.near_term:
        n.evidence = _filter_evidence(n.evidence, valid, counts)
    for rf in p.risk_factors:
        rf.evidence = _filter_evidence(rf.evidence, valid, counts)
    if counts[0]:
        warns.append(f"dropped {counts[0]}/{counts[1]} invalid evidence ids")

    if len(p.near_term) > 5:
        p.near_term = p.near_term[:5]
        warns.append("trimmed near_term to 5")
    if len(p.risk_factors) > 4:
        p.risk_factors = p.risk_factors[:4]
        warns.append("trimmed risk_factors to 4")
    if len(p.life_path) > 9:
        p.life_path = p.life_path[:9]
        warns.append("trimmed life_path to 9")

    now = archive.city.year
    path = sorted(p.life_path, key=lambda e: e.year)  # stable sort
    if [id(e) for e in path] != [id(e) for e in p.life_path]:
        warns.append("life_path re-sorted chronologically")
    cur = now
    for e in path:
        if e.year < cur:
            e.year = cur
        cur = e.year
    p.life_path = path
    last = path[-1].year if path else now
    d = p.death_forecast
    floor = max(last, now)
    if d.year < floor:
        warns.append(f"death year {d.year} raised to {floor}")
        d.year = floor
    res = next((r for r in archive.residents if r.resident_id == rid), None)
    if res is not None:
        expect = res.age + (d.year - now)
        if d.age_at_death != expect:
            warns.append(f"age_at_death {d.age_at_death} -> {expect}")
            d.age_at_death = expect

    if _rename_dupes(p.life_path, "event_id"):
        warns.append("renamed duplicate event_ids")
    _rename_dupes(p.near_term, "pred_id")

    ratio = counts[0] / counts[1] if counts[1] else 0.0
    return p, warns, ratio


# ---------------------------------------------------------------- plan
def validate_plan(plan: CityPlan, archive: Archive,
                  states: list[ResidentState]) -> tuple[CityPlan, list[str], float]:
    plan = plan.model_copy(deep=True)
    warns: list[str] = []
    valid = {r.record_id for r in archive.records}
    pids = {p.place_id for p in archive.city.landmarks}
    dids = {d.district_id for d in archive.city.districts}
    by_rid = {s.resident_id: s for s in states}
    counts = [0, 0]

    kept = []
    for iv in plan.interventions:
        s = by_rid.get(iv.resident_id)
        if s is None:
            warns.append(f"{iv.intervention_id}: unknown resident {iv.resident_id}; dropped")
            continue
        if s.status != "active":
            warns.append(f"{iv.intervention_id}: {iv.resident_id} is reassigned; dropped")
            continue
        new = min(max(1, iv.rung, s.escalation_floor), config.MAX_RUNG)
        if new != iv.rung:
            warns.append(f"{iv.intervention_id}: rung {iv.rung} -> {new} (floor {s.escalation_floor})")
            iv.rung = new
        if iv.rung == 5:
            if not iv.disposition:
                iv.disposition = "Case closed. Subject removed from active loop; transfer recorded."
                warns.append(f"{iv.intervention_id}: filled default disposition")
            if not iv.cover_story:
                iv.cover_story = "Relocated for a new opportunity elsewhere."
                warns.append(f"{iv.intervention_id}: filled default cover_story")
        else:
            iv.disposition = None
            iv.cover_story = None
        if iv.place_id is not None and iv.place_id not in pids:
            warns.append(f"{iv.intervention_id}: unknown place_id {iv.place_id} -> None")
            iv.place_id = None
        if iv.target_event_id is not None and \
                iv.target_event_id not in {e.event_id for e in s.prediction.life_path}:
            warns.append(f"{iv.intervention_id}: unknown target_event_id {iv.target_event_id} -> None")
            iv.target_event_id = None
        iv.evidence = _filter_evidence(iv.evidence, valid, counts)
        kept.append(iv)

    # at most one per resident: keep highest rung (first wins ties)
    best: dict[str, int] = {}
    for i, iv in enumerate(kept):
        if iv.resident_id not in best or iv.rung > kept[best[iv.resident_id]].rung:
            best[iv.resident_id] = i
    keep_idx = set(best.values())
    if len(keep_idx) != len(kept):
        warns.append(f"dropped {len(kept) - len(keep_idx)} extra interventions for the same resident")
    plan.interventions = [iv for i, iv in enumerate(kept) if i in keep_idx]

    for pol in plan.cohort_policies:
        if pol.district_id is not None and pol.district_id not in dids:
            warns.append(f"{pol.policy_id}: unknown district {pol.district_id} -> None")
            pol.district_id = None

    if _rename_dupes(plan.interventions, "intervention_id"):
        warns.append("renamed duplicate intervention ids")
    if _rename_dupes(plan.cohort_policies, "policy_id"):
        warns.append("renamed duplicate policy ids")
    if counts[0]:
        warns.append(f"dropped {counts[0]}/{counts[1]} invalid evidence ids")

    ratio = counts[0] / counts[1] if counts[1] else 0.0
    return plan, warns, ratio
