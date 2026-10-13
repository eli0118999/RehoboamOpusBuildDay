"""Pass 2: per-subject life-path prediction. All model calls go through llm.call."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from . import config, llm
from .schemas import Archive, CityState, Prediction, ResidentState
from .validate import validate_prediction

log = logging.getLogger("rehoboam.predict")

RETRY_THRESHOLD = 0.2


# ---------------------------------------------------------------- shared helpers
def archive_of(state: CityState) -> Archive:
    return Archive(city=state.city, residents=state.residents, records=state.records,
                   relationships=state.relationships)


def archive_json(archive: Archive) -> str:
    """Compact and deterministic: byte-identical across calls so the prompt cache hits."""
    return archive.model_dump_json()


def system_prompt() -> str:
    return llm.load_prompt("system").format(population=config.POPULATION)


def collect_evidence(obj) -> list[str]:
    """Every id found under an 'evidence' key anywhere in a pydantic model (pre-validation)."""
    out: list[str] = []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "evidence" and isinstance(v, list):
                    out.extend(e for e in v if isinstance(e, str))
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj.model_dump())
    return out


def invalid_evidence(obj, archive: Archive) -> list[str]:
    valid = {r.record_id for r in archive.records}
    return [e for e in collect_evidence(obj) if e not in valid]


def retry_block(bad: list[str]) -> dict:
    ids = ", ".join(sorted(set(bad)))
    return llm.text_block(
        f"Your previous answer cited record IDs that do not exist in the Archive: {ids}. "
        "Cite only record IDs that appear verbatim in the Archive above (format rNN-NNNN). "
        "If no record supports a claim, cite fewer records rather than inventing IDs.")


# ---------------------------------------------------------------- prediction
def _interventions_block(rs: ResidentState | None) -> str:
    if rs is None or not rs.interventions_applied:
        return ""
    lines = []
    for iv in rs.interventions_applied:
        name = config.LADDER.get(iv.rung, "?")
        lines.append(f"- {iv.intervention_id}: rung {iv.rung} {name}; intent {iv.intent}; "
                     f"target {iv.target_event_id}; action: {iv.action}")
    return ("\nInterventions already applied to this subject:\n" + "\n".join(lines) +
            "\nTheir effects belong in the path.")


def _recompute_block(rs: ResidentState | None, tick: int) -> str:
    if rs is None or not rs.recompute_pending:
        return ""
    return (f"\nThis subject deviated from prediction at tick {tick}: {rs.deviation_note}. "
            "Recompute under heightened scrutiny: re-read every record, weight recent behaviour, "
            "distrust previously stable traits, and reassess dissent.")


def _current_place(archive: Archive, rs: ResidentState | None) -> str:
    if rs is not None and rs.current_place:
        for p in archive.city.landmarks:
            if p.place_id == rs.current_place:
                return f"{p.name} ({p.place_id})"
        return rs.current_place
    return "no fixed location"


def predict_one(archive: Archive, rid: str, tick: int, rs: ResidentState | None = None) -> Prediction:
    recompute = bool(rs is not None and rs.recompute_pending)
    task = llm.load_prompt("predict").format(
        rid=rid, tick=tick, year=archive.city.year + tick // 52,
        current_place=_current_place(archive, rs),
        cohorts=", ".join(config.COHORTS),
        interventions_block=_interventions_block(rs),
        recompute_block=_recompute_block(rs, tick))
    effort = config.EFFORT["recompute" if recompute else "predict"]
    system = system_prompt()
    blocks = [llm.archive_block(archive_json(archive)), llm.text_block(task)]
    key = f"t{tick:02d}_{rid}"

    raw = llm.call("predict", key, system, blocks, Prediction, effort)
    bad = invalid_evidence(raw, archive)
    best, warns, ratio = validate_prediction(raw, archive, rid)
    if ratio > RETRY_THRESHOLD:
        log.warning("%s: %.0f%% invalid citations, retrying", key, ratio * 100)
        raw2 = llm.call("predict", key + "_retry", system, blocks + [retry_block(bad)], Prediction, effort)
        p2, w2, r2 = validate_prediction(raw2, archive, rid)
        if r2 < ratio:
            best, warns, ratio = p2, w2, r2
    for w in warns:
        log.info("%s: %s", key, w)
    return best


def predict_many(archive: Archive, rids: list[str], tick: int,
                 states: dict[str, ResidentState] | None = None) -> dict[str, Prediction]:
    states = states or {}
    out: dict[str, Prediction] = {}
    if not rids:
        return out
    first, rest = rids[0], rids[1:]
    out[first] = predict_one(archive, first, tick, states.get(first))  # warms the cache
    if rest:
        with ThreadPoolExecutor(config.MAX_WORKERS) as ex:
            futs = {r: ex.submit(predict_one, archive, r, tick, states.get(r)) for r in rest}
            for r in rest:
                out[r] = futs[r].result()
    return {r: out[r] for r in rids}
