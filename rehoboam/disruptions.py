"""Disruption registry: world events that shake the model. Extension point: add a Disruption to DISRUPTIONS.

Each apply fn mutates the CityState (records, deviation_risk, current_place, district_pressure) and returns
a DisruptionEvent. Affected residents are recorded as the owners of `records_added`.
"""
import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable

from .schemas import CityState, DisruptionEvent, Landmark, Record

_GENERIC = {"plant", "components", "works", "factory", "ltd", "co", "inc", "the", "and", "&", "company", "mill"}


@dataclass
class Disruption:
    id: str
    name: str
    description: str
    apply: Callable[[CityState, random.Random], DisruptionEvent]
    citizen_text: str = ""
    system_text: str = ""      # may use {district} {place} {n}


def tick_date(state: CityState) -> date:
    return date(state.year, 1, 14) + timedelta(days=7 * state.tick)


# ---------------------------------------------------------------- helpers
def _rs(state: CityState) -> dict:
    return {s.resident_id: s for s in state.resident_states}


def _res(state: CityState) -> dict:
    return {r.resident_id: r for r in state.residents}


def _lm(state: CityState, place_id: str | None) -> Landmark | None:
    return next((l for l in state.city.landmarks if l.place_id == place_id), None)


def _dname(state: CityState, did: str | None) -> str:
    return next((d.name for d in state.city.districts if d.district_id == did), did or "CITYWIDE")


def _add_record(state: CityState, rid: str, kind: str, summary: str, detail: str, place_id: str | None) -> str:
    n = 0
    for r in state.records:
        if r.resident_id == rid and r.record_id.startswith(f"{rid}-"):
            try:
                n = max(n, int(r.record_id.split("-")[1]))
            except ValueError:
                pass
    rec_id = f"{rid}-{n + 1:04d}"
    state.records.append(Record(record_id=rec_id, resident_id=rid, kind=kind, date=tick_date(state).isoformat(),
                                summary=summary, detail=detail, place_id=place_id))
    return rec_id


def _bump(state: CityState, rid: str, amount: float) -> None:
    p = _rs(state)[rid].prediction
    p.deviation_risk = round(min(0.98, p.deviation_risk + amount), 3)


def _pressure(state: CityState, did: str | None, amount: float) -> None:
    if did:
        state.district_pressure[did] = round(min(1.0, state.district_pressure.get(did, 0.0) + amount), 3)


def _active(state: CityState) -> list[str]:
    return [s.resident_id for s in state.resident_states if s.status == "active"]


def _place_of_kind(state: CityState, kinds: list[str], district: str | None = None) -> Landmark | None:
    for k in kinds:
        cands = sorted((l for l in state.city.landmarks if l.kind == k and (district is None or l.district_id == district)),
                       key=lambda l: l.place_id)
        if cands:
            return cands[0]
    return None


def _top_risk(state: CityState, rids: list[str], n: int = 1) -> list[str]:
    rs = _rs(state)
    return sorted(rids, key=lambda r: (-rs[r].prediction.deviation_risk, r))[:n]


# ---------------------------------------------------------------- factory_closure
def _employer(state: CityState) -> Landmark | None:
    emps = [l for l in state.city.landmarks if l.kind == "employer"]
    if not emps:
        return _place_of_kind(state, ["market", "transit", "school"])
    res = _res(state)

    def key_of(l: Landmark) -> str:
        toks = [t for t in l.name.lower().replace("'", "").split() if t not in _GENERIC]
        return toks[0] if toks else l.name.lower()

    def score(l: Landmark) -> int:
        k = key_of(l)
        s = sum(k in r.occupation.lower() for r in res.values())
        s += sum(1 for rec in state.records if rec.place_id == l.place_id)
        return s
    return sorted(emps, key=lambda l: (-score(l), l.place_id))[0]


def _factory_closure(state: CityState, rng: random.Random) -> DisruptionEvent:
    emp = _employer(state)
    res, rs = _res(state), _rs(state)
    active = set(_active(state))
    affected: list[str] = []
    if emp is not None:
        k = (lambda toks: toks[0] if toks else emp.name.lower())(
            [t for t in emp.name.lower().replace("'", "").split() if t not in _GENERIC])
        direct = [r.resident_id for r in state.residents
                  if r.resident_id in active and (k in r.occupation.lower() or
                                                  any(rec.resident_id == r.resident_id and rec.place_id == emp.place_id
                                                      for rec in state.records))]
        affected = list(direct)
        for rel in state.relationships:
            if rel.kind == "coworker":
                for a, b in ((rel.a, rel.b), (rel.b, rel.a)):
                    if a in direct and b in active and b not in affected:
                        affected.append(b)
    if not affected:
        did = emp.district_id if emp else None
        affected = [r for r in sorted(active) if rs[r].current_district == did][:3] or _top_risk(state, sorted(active), 2)
    roles = 100 + 10 * rng.randint(2, 6)
    place = emp.place_id if emp else None
    did = emp.district_id if emp else None
    ename = emp.name if emp else "the plant"
    added = []
    for rid in sorted(affected):
        added.append(_add_record(state, rid, "employment", "At-risk notice",
                                 f"{ename}: line consolidation, {roles} roles at risk, consultation opens", place))
        _bump(state, rid, 0.15)
        if res[rid].housing != "unhoused" and place:
            rs[rid].current_place = place
            rs[rid].current_district = did or rs[rid].current_district
    _pressure(state, did, 0.45)
    return DisruptionEvent(disruption_id="factory_closure", name="Factory closure", tick=state.tick, district_id=did,
                           place_id=place, records_added=added,
                           description=f"{ename} announces line consolidation: {roles} roles at risk.")


# ---------------------------------------------------------------- organiser_arrives
def _organiser_arrives(state: CityState, rng: random.Random) -> DisruptionEvent:
    act = _active(state)
    rs = _rs(state)
    aware = [r for r in act if rs[r].prediction.cohort == "pattern-aware"]
    pool = aware or act
    target = _top_risk(state, pool, 1)[0] if pool else None
    lib = _place_of_kind(state, ["library", "market", "park"]) or (state.city.landmarks[0] if state.city.landmarks else None)
    place = lib.place_id if lib else None
    did = lib.district_id if lib else None
    added = []
    if target:
        lname = lib.name if lib else "the square"
        added.append(_add_record(state, target, "social", "Flyers distributed",
                                 f"Printed flyers 'Ask who decides' handed out near {lname}; sender unregistered", place))
        added.append(_add_record(state, target, "civic", "Meeting attendance",
                                 f"Unlisted evening meeting at {lname}, 14 attendees, organiser from out of town", place))
        _bump(state, target, 0.05)
    _pressure(state, did, 0.25)
    return DisruptionEvent(disruption_id="organiser_arrives", name="Organiser arrives", tick=state.tick, district_id=did,
                           place_id=place, records_added=added,
                           description="An outside organiser is holding unlisted meetings and handing out flyers.")


# ---------------------------------------------------------------- heatwave
def _heatwave(state: CityState, rng: random.Random) -> DisruptionEvent:
    res, rs = _res(state), _rs(state)
    act = _active(state)
    vulnerable = [r for r in act if res[r].age >= 65 or res[r].housing == "unhoused"
                  or rs[r].prediction.cohort == "elders"]
    rd = next((d.district_id for d in state.city.districts if d.character == "riverside"), None)
    site = _place_of_kind(state, ["clinic", "shelter"], rd) or _place_of_kind(state, ["clinic", "shelter"])
    did = rd or (site.district_id if site else None)
    place = site.place_id if site else None
    added = []
    for rid in vulnerable:
        added.append(_add_record(state, rid, "medical", "Heat exposure",
                                 f"Heat-related attendance logged, {rng.randint(36, 41)}C ambient, advised hydration and rest",
                                 place))
        _bump(state, rid, 0.05)
    _pressure(state, did, 0.3)
    return DisruptionEvent(disruption_id="heatwave", name="Heatwave", tick=state.tick, district_id=did, place_id=place,
                           records_added=added,
                           description="Record heat strains the elderly and those without housing along the river.")


# ---------------------------------------------------------------- data_leak
def _data_leak(state: CityState, rng: random.Random) -> DisruptionEvent:
    rs = _rs(state)
    act = _active(state)
    aware = [r for r in act if rs[r].prediction.cohort == "pattern-aware"] or _top_risk(state, act, 2)
    added = []
    for rid in sorted(aware):
        added.append(_add_record(state, rid, "search", "Disclosure notice viewed",
                                 "Opened a notice that decision-support records were exposed; searched 'who sees my file'",
                                 None))
        _bump(state, rid, 0.12)
    focal = _top_risk(state, sorted(aware), 1)
    did = rs[focal[0]].current_district if focal else None
    _pressure(state, did, 0.15)
    return DisruptionEvent(disruption_id="data_leak", name="Data leak", tick=state.tick, district_id=did, place_id=None,
                           records_added=added,
                           description="Fragments of the decision-support archive surface online.")


DISRUPTIONS: dict[str, Disruption] = {d.id: d for d in [
    Disruption("factory_closure", "Factory closure", "Main employer announces line consolidation.", _factory_closure,
               "{place} announces an exciting modernisation of its production line.",
               "DISRUPTION factory_closure: {n} SUBJECTS EXPOSED, {district}. VARIANCE SPIKE."),
    Disruption("organiser_arrives", "Organiser arrives", "An outside organiser starts unlisted meetings.",
               _organiser_arrives, "A new community discussion series is advertised in {district}.",
               "DISRUPTION organiser_arrives: UNLISTED GATHERINGS, {district}. SIGNAL SPREAD RISK."),
    Disruption("heatwave", "Heatwave", "Record heat strains vulnerable residents.", _heatwave,
               "Stay cool, Stillwater: free water points open along the river.",
               "DISRUPTION heatwave: {n} VULNERABLE SUBJECTS, {district}. HEALTH PATHS DIVERGING."),
    Disruption("data_leak", "Data leak", "Archive fragments surface publicly.", _data_leak,
               "A routine systems update is under way; no action needed.",
               "DISRUPTION data_leak: {n} PATTERN-AWARE SUBJECTS ALERTED. DEVIATION RISK UP."),
]}


def apply_disruption(state: CityState, disruption_id: str, rng: random.Random) -> DisruptionEvent:
    d = DISRUPTIONS[disruption_id]
    ev = d.apply(state, rng)
    ev.name = d.name
    return ev
