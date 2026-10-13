# Mini Rehoboam

A miniature Rehoboam (Westworld S3) watching **Stillwater**, a small fictional city of ~40,000.
Opus generates an evidence-cited Archive of 12 case subjects, predicts each life path and death, and
plans interventions on an escalating ladder (Nudge → Narrow → Isolate → Discredit → Reassign). A
deterministic tick loop scores predictions, rolls rule-based compliance and escalates against defiers.
Three linked views: the eclipse **prediction circle**, an **OPUS profile** card per subject, and a 3D
**white architectural model** of the city.

## Setup
```
pip install -r requirements.txt
cp .env.example .env        # then put your ANTHROPIC_API_KEY in .env (gitignored)
```
Replay mode needs no key.

## Run
```
python -m rehoboam serve                 # dashboard at http://localhost:8000 (newest run, else the sample fixture)
python -m rehoboam seed --run myrun      # Pass 1: Archive (one Opus call, ~4-5 min)
python -m rehoboam predict --run myrun   # Pass 2: tick 0 predictions (12 parallel calls, cached prefix)
python -m rehoboam disrupt factory_closure --run myrun   # queue a disruption for the next tick
python -m rehoboam tick --run myrun      # Pass 3 plan → apply → re-predict → snapshot (~3-6 min)
python -m rehoboam demo                  # full scripted run into runs/demo
python -m rehoboam demo --replay demo    # replay runs/demo's recorded calls into runs/demo_replay (no API)
python -m rehoboam runs                  # list runs
```
Every model call is recorded to `runs/<run>/calls/<pass>__<key>.json`; snapshots to `runs/<run>/tick_NN.json`.
A live run reuses existing recordings, so an interrupted run resumes where it stopped.

## Dashboard
- Header: stability, active loop, accuracy, tick scrubber (←/→), CITIZEN | SYSTEM toggle (C/S), TICK and DISRUPT (live runs).
- Click a subject anywhere (3D capsule, circle flare, feed line, gallery card) to select it everywhere. Esc deselects.
- `D` drawer (heatmap / gallery / archive), `F` final screen.
- URL params: `run`, `tick`, `view`, `select`, `tab`, `drawer`, `final`, `skip=world,circle` (debug).

## Layout
- `rehoboam/` — `config.py`, `schemas.py` (all JSON shapes), `llm.py` (single call wrapper: stream, schema, refusal
  fallback, record/replay), `prompts/`, `archive.py` / `predict.py` / `plan.py` (passes), `validate.py`, `sim.py`,
  `metrics.py`, `disruptions.py`, `geo.py` (shared compass geography), `state.py`, `runner.py`, `cli.py`, `server.py`.
- `web/` — no build step; Three.js vendored in `web/vendor/three` (r186). `world.js`, `circle.js`, `profile.js`,
  `views.js`, `app.js`.
- `docs/CONTRACT.md` — frozen state JSON + module APIs. `TASKS.md` — checklist.

## Notes
- Model: `claude-opus-5-5` with server-side refusal fallback (`fallbacks="default"`). The plan pass sometimes trips a
  mid-stream false-positive classifier; `llm.py` retries and the request is then served by the fallback model
  (recorded in each call file's `model` / `fallbacks`).
- Stillwater and its residents are entirely fictional; this is an art piece about algorithmic control.
