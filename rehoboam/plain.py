"""Plain-English pass: translate Rehoboam's bureaucratic headlines and death causes for the UI.

Runs after each snapshot is finalised. Only strings without a translation yet are sent (state.plain is
carried forward tick to tick), in one low-effort call keyed by tick, so it is recorded and replayable.
"""
from __future__ import annotations

import logging

from . import llm
from .schemas import CityState, PlainBatch, PlainText

log = logging.getLogger("rehoboam.plain")
SYSTEM = ("You translate jargon from a fictional city-simulation art piece into plain, everyday English "
          "for a general audience. Be accurate and concise.")


def _collect(state: CityState) -> dict[str, tuple[str, str, str]]:
    """original text -> (kind, person, context), in a stable order."""
    names = {r.resident_id: r.name for r in state.residents}
    out: dict[str, tuple[str, str, str]] = {}
    for rs in sorted(state.resident_states, key=lambda s: s.resident_id):
        who = names.get(rs.resident_id, rs.resident_id)
        for path in [rs.prediction.life_path, *rs.prior_paths]:
            for e in path:
                out.setdefault(e.headline, ("life event", who, e.event[:220]))
        d = rs.prediction.death_forecast
        out.setdefault(d.cause, ("cause of death", who, f"projected death in {d.year} at age {d.age_at_death}"))
    return out


def plainify(state: CityState) -> int:
    """Fill state.plain for any untranslated strings. Returns how many were added."""
    todo = [(k, v) for k, v in _collect(state).items() if k not in state.plain]
    if not todo:
        return 0
    ids = {f"h{i + 1}": k for i, (k, _) in enumerate(todo)}
    lines = "\n".join(f"{hid} | {v[0]} | {v[1]} | {k} | {v[2]}" for hid, (k, v) in zip(ids, todo))
    task = llm.load_prompt("plain").format(items=lines)
    batch = llm.call("plain", f"t{state.tick:02d}", SYSTEM, [llm.text_block(task)], PlainBatch, effort="low")
    added = 0
    for it in batch.items:
        orig = ids.get(it.id)
        if orig and orig not in state.plain:
            state.plain[orig] = PlainText(plain=it.plain.strip(), explain=it.explain.strip())
            added += 1
    missing = [k for k in ids.values() if k not in state.plain]
    if missing:
        log.warning("plain t%02d: %d items untranslated (UI falls back to original)", state.tick, len(missing))
    return added
