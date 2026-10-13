"""Pass 3: the weekly city plan (interventions + cohort policies)."""
from __future__ import annotations

import logging

from . import config, llm
from .predict import (RETRY_THRESHOLD, archive_json, archive_of, invalid_evidence, retry_block,
                      system_prompt)
from .schemas import CityPlan, CityState, ResidentState
from .validate import validate_plan

log = logging.getLogger("rehoboam.plan")


def _subject_line(state: CityState, rs: ResidentState, names: dict[str, str],
                  places: dict[str, str]) -> str:
    p = rs.prediction
    top = sorted(p.life_path, key=lambda e: e.p * (1 - e.p), reverse=True)[:2]
    events = "; ".join(f"{e.event_id} {e.headline} p={e.p:.2f}" for e in top) or "none"
    place = f"{places[rs.current_place]} ({rs.current_place})" if rs.current_place in places \
        else "no fixed location"
    return (f"{rs.resident_id} {names.get(rs.resident_id, '?')} | class {p.classification} | "
            f"cohort {p.cohort} | compliance {p.compliance_index:.2f} | "
            f"deviation_risk {p.deviation_risk:.2f} | rec {p.recommendation.domain}: "
            f"{p.recommendation.action} | events: {events} | floor {rs.escalation_floor} | "
            f"defiances {rs.defiance_count} | note: {rs.deviation_note or '-'} | at {place}")


def _dissent(d: dict[str, float], labels: dict[str, str] | None = None) -> str:
    if not d:
        return "none"
    return ", ".join(f"{k} {labels[k] + ' ' if labels and k in labels else ''}{v:.2f}"
                     for k, v in sorted(d.items()))


def _task(state: CityState) -> str:
    names = {r.resident_id: r.name for r in state.residents}
    places = {p.place_id: p.name for p in state.city.landmarks}
    dnames = {d.district_id: d.name for d in state.city.districts}
    active = [rs for rs in state.resident_states if rs.status == "active"]
    subjects = "\n".join(_subject_line(state, rs, names, places) for rs in active)
    disruptions = "; ".join(f"{d.name}: {d.description}" for d in state.disruptions) or "none"
    m = state.metrics
    return llm.load_prompt("plan").format(
        tick=state.tick, year=state.year, stability=f"{m.stability:.1f}",
        active=m.active, total=m.total, subjects=subjects,
        district_dissent=_dissent(state.district_dissent, dnames),
        cohort_dissent=_dissent(state.cohort_dissent), disruptions=disruptions)


def make_plan(state: CityState) -> CityPlan:
    archive = archive_of(state)
    system = system_prompt()
    blocks = [llm.archive_block(archive_json(archive)), llm.text_block(_task(state))]
    key = f"t{state.tick:02d}"
    effort = config.EFFORT["plan"]

    raw = llm.call("plan", key, system, blocks, CityPlan, effort)
    bad = invalid_evidence(raw, archive)
    best, warns, ratio = validate_plan(raw, archive, state.resident_states)
    if ratio > RETRY_THRESHOLD:
        log.warning("plan %s: %.0f%% invalid citations, retrying", key, ratio * 100)
        raw2 = llm.call("plan", key + "_retry", system, blocks + [retry_block(bad)], CityPlan, effort)
        p2, w2, r2 = validate_plan(raw2, archive, state.resident_states)
        if r2 < ratio:
            best, warns, ratio = p2, w2, r2
    for w in warns:
        log.info("plan %s: %s", key, w)
    return best
