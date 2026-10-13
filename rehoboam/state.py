"""Disk I/O for runs: tick snapshots, archives, the bundled sample fixture. UTF-8 everywhere."""
import json
import re
from pathlib import Path

from . import config
from .schemas import Archive, CityState

_TICK_RE = re.compile(r"^tick_(\d+)\.json$")


def run_dir(run_id: str) -> Path:
    return config.RUNS_DIR / run_id


def _sample_ticks() -> list[dict]:
    data = json.loads(config.SAMPLE_STATE.read_text(encoding="utf-8"))
    return data["ticks"]


def save_state(state: CityState) -> Path:
    d = run_dir(state.run_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"tick_{state.tick:02d}.json"
    path.write_text(state.model_dump_json(indent=1), encoding="utf-8")
    return path


def list_ticks(run_id: str) -> list[int]:
    if run_id == "sample":
        return [int(t["tick"]) for t in _sample_ticks()]
    d = run_dir(run_id)
    if not d.is_dir():
        return []
    out = []
    for p in d.iterdir():
        m = _TICK_RE.match(p.name)
        if m:
            out.append(int(m.group(1)))
    return sorted(out)


def load_state(run_id: str, tick: int | None = None) -> CityState:
    ticks = list_ticks(run_id)
    if not ticks:
        raise FileNotFoundError(f"no ticks for run '{run_id}'")
    if tick is None:
        tick = ticks[-1]
    if tick not in ticks:
        raise FileNotFoundError(f"run '{run_id}' has no tick {tick}")
    if run_id == "sample":
        raw = next(t for t in _sample_ticks() if int(t["tick"]) == tick)
        return CityState.model_validate(raw)
    path = run_dir(run_id) / f"tick_{tick:02d}.json"
    return CityState.model_validate_json(path.read_text(encoding="utf-8"))


def list_runs() -> list[dict]:
    runs = [{"run_id": "sample", "ticks": list_ticks("sample")}]
    if config.RUNS_DIR.is_dir():
        for d in sorted(config.RUNS_DIR.iterdir()):
            if not d.is_dir() or d.name.startswith("_") or d.name == "sample":
                continue
            ticks = list_ticks(d.name)
            if ticks:
                runs.append({"run_id": d.name, "ticks": ticks})
    return runs


def save_archive(run_id: str, a: Archive) -> Path:
    d = run_dir(run_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "archive.json"
    path.write_text(a.model_dump_json(indent=1), encoding="utf-8")
    return path


def load_archive(run_id: str) -> Archive:
    if run_id == "sample":
        t = _sample_ticks()[0]
        return Archive(city=t["city"], residents=t["residents"], records=t["records"],
                       relationships=t["relationships"])
    return Archive.model_validate_json((run_dir(run_id) / "archive.json").read_text(encoding="utf-8"))
