"""FastAPI app serving the API in docs/CONTRACT.md §4 and the static web/ folder.

Run with: python -m uvicorn rehoboam.server:app --port 8774
"""
from __future__ import annotations

import json
import logging
import re
import threading
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import config

log = logging.getLogger("rehoboam.server")

SAMPLE = "sample"
_TICK_RE = re.compile(r"^tick_(\d+)\.json$")

app = FastAPI(title="Mini Rehoboam", docs_url="/api/docs", openapi_url="/api/openapi.json")

_tick_lock = threading.Lock()          # only one live tick at a time
_started_runs: set[str] = set()        # runner.start() is called once per run
_started_lock = threading.Lock()


# ---------------------------------------------------------------- storage access
def _state_mod():
    """state.py if the sim agent has written it, else None (built-in fallback below)."""
    try:
        from . import state as state_mod
        return state_mod
    except ImportError:
        return None


def _sample_doc() -> dict:
    return json.loads(config.SAMPLE_STATE.read_text(encoding="utf-8"))


def _run_path(run: str) -> Path:
    return config.RUNS_DIR / run


def _tick_files(run: str) -> dict[int, Path]:
    d = _run_path(run)
    if not d.is_dir():
        return {}
    out: dict[int, Path] = {}
    for p in d.iterdir():
        m = _TICK_RE.match(p.name)
        if m:
            out[int(m.group(1))] = p
    return out


def _list_runs() -> list[dict]:
    sm = _state_mod()
    if sm is not None:
        runs = [dict(r) for r in sm.list_runs()]
    else:
        runs = []
        if config.RUNS_DIR.is_dir():
            for d in config.RUNS_DIR.iterdir():
                if d.is_dir():
                    ticks = sorted(_tick_files(d.name))
                    if ticks:
                        runs.append({"run_id": d.name, "ticks": ticks})
    if not any(r["run_id"] == SAMPLE for r in runs):
        runs.append({"run_id": SAMPLE, "ticks": _sample_ticks()})
    return runs


def _sample_ticks() -> list[int]:
    return [int(t["tick"]) for t in _sample_doc().get("ticks", [])]


def _ticks_for(run: str) -> list[int] | None:
    if run == SAMPLE:
        return _sample_ticks()
    files = _tick_files(run)
    if not files and not _run_path(run).is_dir():
        return None
    return sorted(files)


def _default_run() -> str:
    """Newest run folder with tick files, not starting with '_'; else the sample."""
    best, best_mtime = SAMPLE, -1.0
    if config.RUNS_DIR.is_dir():
        for d in config.RUNS_DIR.iterdir():
            if not d.is_dir() or d.name.startswith("_"):
                continue
            files = _tick_files(d.name)
            if not files:
                continue
            mtime = d.stat().st_mtime
            if mtime > best_mtime:
                best, best_mtime = d.name, mtime
    return best


def _read_state_text(run: str, tick: int | None) -> str | None:
    """Return the stored JSON text for one tick, or None if it does not exist."""
    if run == SAMPLE:
        ticks = _sample_doc().get("ticks", [])
        if not ticks:
            return None
        if tick is None:
            tick = max(int(t["tick"]) for t in ticks)
        for t in ticks:
            if int(t["tick"]) == tick:
                return json.dumps(t)
        return None
    files = _tick_files(run)
    if not files:
        return None
    if tick is None:
        tick = max(files)
    path = files.get(tick)
    if path is None:
        return None
    return path.read_text(encoding="utf-8")


def _to_jsonable(state) -> dict:
    if hasattr(state, "model_dump"):
        return state.model_dump(mode="json")
    return state


# ---------------------------------------------------------------- live runner access
def _start_once(run: str) -> None:
    from . import runner
    with _started_lock:
        if run in _started_runs:
            return
        runner.start(run, replay=False)
        _started_runs.add(run)


def _tick_blocking(run: str) -> dict:
    _start_once(run)
    from . import runner
    return _to_jsonable(runner.tick(run))


# ---------------------------------------------------------------- routes
@app.middleware("http")
async def no_cache_api(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/api/runs")
def get_runs():
    return JSONResponse(_list_runs())


@app.get("/api/ticks")
def get_ticks(run: str | None = None):
    run = run or _default_run()
    ticks = _ticks_for(run)
    if ticks is None:
        return JSONResponse({"error": f"unknown run '{run}'"}, status_code=404)
    return JSONResponse({"run_id": run, "ticks": ticks,
                         "latest": ticks[-1] if ticks else None})


@app.get("/api/state")
def get_state(run: str | None = None, tick: int | None = None):
    run = run or _default_run()
    text = _read_state_text(run, tick)
    if text is None:
        where = f"tick {tick}" if tick is not None else "any tick"
        return JSONResponse({"error": f"no state for run '{run}', {where}"}, status_code=404)
    return JSONResponse(json.loads(text))


@app.post("/api/tick")
async def post_tick(run: str | None = None):
    run = run or _default_run()
    if run == SAMPLE:
        return JSONResponse({"error": "the sample fixture cannot be ticked; pick a live run"},
                            status_code=503)
    if not _tick_lock.acquire(blocking=False):
        return JSONResponse({"error": "a tick is already running"}, status_code=409)
    try:
        body = await run_in_threadpool(_tick_blocking, run)
        return JSONResponse(body)
    except Exception as e:
        log.exception("tick failed for run %s", run)
        return JSONResponse({"error": str(e) or e.__class__.__name__}, status_code=503)
    finally:
        _tick_lock.release()


@app.post("/api/disrupt/{disruption_id}")
async def post_disrupt(disruption_id: str, run: str | None = None):
    run = run or _default_run()
    if run == SAMPLE:
        return JSONResponse({"error": "the sample fixture cannot take disruptions"},
                            status_code=503)

    def _queue() -> None:
        from . import runner
        _start_once(run)
        runner.queue_disruption(run, disruption_id)

    try:
        await run_in_threadpool(_queue)
    except Exception as e:
        log.exception("disruption %s failed for run %s", disruption_id, run)
        return JSONResponse({"error": str(e) or e.__class__.__name__}, status_code=503)
    return JSONResponse({"queued": disruption_id})


# Static site last, so /api/* routes take precedence.
app.mount("/", StaticFiles(directory=str(config.WEB_DIR), html=True), name="web")
