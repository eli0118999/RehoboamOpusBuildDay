"""Orchestration glue: seed -> predict -> (disrupt -> plan -> apply -> re-predict -> finalize)*.

cli.py and server.py call only these functions. Replay: `start(out_id, replay=src_id)` reads recorded
calls from runs/<src_id>/calls/ and writes snapshots to runs/<out_id>/, so a replay can be diffed
against the original run.
"""
from __future__ import annotations

import json
import logging
import time

from . import config, llm
from .plain import plainify

log = logging.getLogger("rehoboam.runner")

# Demo script: disruptions queued before the given tick runs.
DEMO_SCRIPT = {1: ["factory_closure"]}


def _dir(run_id: str):
    return config.RUNS_DIR / run_id


def start(run_id: str | None = None, replay: bool | str = False, fill_missing: bool = False) -> str:
    """Configure the LLM layer for a run. replay=True replays the run's own calls; replay='src' replays src's."""
    run_id = run_id or time.strftime("run_%Y%m%d_%H%M%S")
    _dir(run_id).mkdir(parents=True, exist_ok=True)
    if replay:
        src = run_id if replay is True else str(replay)
        if not (_dir(src) / "calls").exists():
            raise FileNotFoundError(f"no recorded calls in runs/{src}/calls")
        llm.configure(_dir(src), replay=True, fill_missing=fill_missing)
    else:
        llm.configure(_dir(run_id), replay=False)
    log.info("run %s (%s)", run_id, f"replay of {replay if replay is not True else run_id}" if replay else "live")
    return run_id


def seed(run_id: str):
    from . import state
    from .archive import generate_archive
    path = _dir(run_id) / "archive.json"
    if path.exists():
        log.info("archive exists for %s, reusing", run_id)
        return state.load_archive(run_id)
    a = generate_archive()
    state.save_archive(run_id, a)
    log.info("archive: %d residents, %d records", len(a.residents), len(a.records))
    return a


def predict(run_id: str):
    from . import sim, state
    from .predict import predict_many
    a = state.load_archive(run_id)
    preds = predict_many(a, [r.resident_id for r in a.residents], 0)
    st = sim.initial_state(a, preds, run_id, config.SEED)
    plainify(st)
    state.save_state(st)
    _status(st)
    return st


def _queue_path(run_id: str):
    return _dir(run_id) / "queue.json"


def queue_disruption(run_id: str, disruption_id: str) -> None:
    from .disruptions import DISRUPTIONS
    if disruption_id not in DISRUPTIONS:
        raise KeyError(f"unknown disruption {disruption_id!r}; known: {sorted(DISRUPTIONS)}")
    p = _queue_path(run_id)
    q = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    q.append(disruption_id)
    p.write_text(json.dumps(q), encoding="utf-8")
    log.info("queued %s for next tick of %s", disruption_id, run_id)


def _peek_queue(run_id: str) -> list[str]:
    p = _queue_path(run_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _clear_queue(run_id: str) -> None:
    _queue_path(run_id).unlink(missing_ok=True)


def tick(run_id: str):
    from . import sim, state
    from .plan import make_plan
    from .predict import archive_of, predict_many
    prev = state.load_state(run_id)
    st = sim.begin_tick(prev, _peek_queue(run_id))
    plan = make_plan(st)
    rids = sim.apply_plan(st, plan)
    preds = {}
    if rids:
        states = {rs.resident_id: rs for rs in st.resident_states}
        preds = predict_many(archive_of(st), rids, st.tick, states)
    st = sim.finalize(st, preds)
    plainify(st)
    state.save_state(st)
    _clear_queue(run_id)  # only once the tick is safely on disk
    _status(st)
    return st


def demo(run_id: str = "demo", replay: bool | str = False, ticks: int = 4, fill_missing: bool = False):
    """Calm start -> factory_closure -> escalation. Live by default; replay=src writes to run_id."""
    if replay is True:
        replay = run_id
    if replay and replay == run_id:
        run_id = f"{replay}_replay"
    out = _dir(run_id)
    stale = sorted(out.glob("tick_*.json")) if out.exists() else []
    if stale and not replay:
        raise FileExistsError(f"runs/{run_id} already has snapshots; use a new --run id, or --replay {run_id}")
    for f in stale + [out / "queue.json"]:  # replay output is derived; start clean so tick() can't resume stale state
        f.unlink(missing_ok=True)
    start(run_id, replay=replay, fill_missing=fill_missing)
    if replay:  # the archive is part of the recording
        src_archive = _dir(str(replay)) / "archive.json"
        (_dir(run_id) / "archive.json").write_bytes(src_archive.read_bytes())
    seed(run_id)
    st = predict(run_id)
    for t in range(1, ticks + 1):
        for d in DEMO_SCRIPT.get(t, []):
            queue_disruption(run_id, d)
        st = tick(run_id)
    return st


def _status(st) -> None:
    m = st.metrics
    acc = f"{m.accuracy:.2f}" if m.accuracy is not None else "-"
    msg = (f"[{st.run_id}] tick {st.tick:02d}  STABILITY {m.stability:.1f}%  ACTIVE LOOP {m.active}/{m.total}  "
           f"ACCURACY {acc}  interventions {m.interventions}  defiances {m.defiances}  divergences {len(st.divergences)}")
    log.info(msg)
    print(msg, flush=True)
