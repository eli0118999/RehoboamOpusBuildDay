# Mini Rehoboam — Tasks

Plan: `inital-prompt-txt-here-is-shimmering-pebble.md`. Contract: `docs/CONTRACT.md`.

## Wave 0: contracts (Opus)
- [x] `.env` is gitignored (`git check-ignore -v .env`)
- [x] requirements.txt, .env.example, .gitignore
- [x] config.py (model, effort, cohorts, ladder, district bearings)
- [x] schemas.py (Archive, Prediction, CityPlan, CityState…)
- [x] geo.py (shared geography: district arcs, place/resident polar, coords)
- [x] llm.py (stream + parse + record/replay + refusal/max_tokens + fallbacks) — live smoke test passed
- [x] prompts: system.md, archive.md, predict.md, plan.md
- [x] docs/CONTRACT.md
- [x] web/fixtures/sample_state.json (12 subjects, 3 ticks; via scripts/make_sample_state.py)

## Wave 1: parallel subagents
- [x] passes (Sonnet): archive.py, predict.py, plan.py, validate.py + tests (21 tests pass, re-run by Opus)
- [x] sim (Sonnet): sim.py, metrics.py, state.py, disruptions.py + tests (17 tests; full suite 38 pass)
- [x] shell+card (Sonnet): index.html, style.css, theme.js, app.js, profile.js, views.js (Opus screenshots: r05 layered reveal, r08 ghost path)
- [x] circle (Sonnet): circle.js (hairline + A/B/C verified by agent screenshots; A seen in shell)
- [x] world (Sonnet): world.js (fixture + live tick 0/1 screenshots; label stacking + brighter system view after Opus review)
- [x] plumbing (Haiku): cli.py, server.py, __main__.py (verified: --help, /api/runs|ticks|state on sample, 503 on sample tick)
- [x] vendor/three: three@0.186.1 + addons (vendored by Opus to unblock world agent)
- [x] runner.py (Opus): orchestration glue for cli/server (replay writes to a separate run id so snapshots can be diffed)

## Wave 2: integration (Opus)
- [x] pytest green (38 passed)
- [x] live seed → predict → plan → tick (runs/live1: 6 ticks, factory_closure at t1, first reassignments at t5)
- [x] dashboard on real state (live1 tick 0 + circle state C on tick 1 screenshotted)
- [x] prompt tuning on real output (terse death causes/headlines; in-world actions only; explicit stability objective → Reassign)

- [x] README.md (setup, run, demo/replay, keys)
- [x] replay determinism: `demo --replay live1 --ticks 5` → ticks 0–5 byte-identical to live (minus run_id)
- [x] app.js `?skip=world,circle` debug param

## Wave 3: demo
- [x] record runs/demo/ (7 ticks: calm → factory_closure → escalation → 7 reassigned; self-contained calls + archive; built by replaying live1's recordings under final sim code)
- [x] final screen (`F` / `?final=1`): real circle centred + `Stability: 91.7%. Active loop: 5 of 12.`; hairline only when divergences = 0 (not reached in this run — not faked)
- [x] Haiku checker: pytest 38 ✔, node --check ✔, py compile ✔, API smoke ✔, no TODO/console.log/keys ✔; replay diff initially FAILED → runner stale-state bug fixed; demo vs demo_replay ticks 0–7 identical (re-verified by Opus, incl. replay over existing output)

## Found
- Fallback `fallbacks="default"` requires `client.beta.messages.stream` (SDK 1.13 supports `output_format` there too).
- Plan's `DISTRICT_ARCS` can't be static (district IDs come from the model) → config holds bearing per *character*; geo.py assigns arcs at runtime and stores them in `state.geo`.
- `home_place` for housed residents = nearest landmark (only landmarks are places).
- Open decision 5 (organiser): default to new records on an existing subject (no extra API call).
- Live Archive: 273s, 30K output tokens, 12 subjects/155 records, validate_archive clean. Predict ×12: 106s, cache_read 21.9K on calls 2–12 ✔.
- **Plan pass streamed JSON cut mid-string** (twice). Cause (inferred): with `output_format=Model` the SDK parses each text block at `content_block_stop`; a mid-stream refusal closes the partial block → parse error aborts the stream before the server-side fallback continues. Fix: raw `output_config.format` json_schema (`anthropic.transform_schema`), join all text blocks across `fallback` boundaries, validate with Pydantic; recordings now note `fallbacks` + serving model.
- runner bug fixed: disruption queue was popped before a tick succeeded (lost on failure); now cleared after save.
- llm.py: live mode reuses existing recordings (resumable runs; `config.REUSE_RECORDINGS`).
- Prompt tune: death `cause` ≤5 words, headlines ≤4 words (long causes cluttered the OPUS card).
- Headless Edge screenshots need an isolated `--user-data-dir` when another Edge instance is open (else it hangs).
- I ran a `taskkill //IM python.exe` with a window-title filter early on to stop a scratch server — it may have hit other python processes; avoid.
- Checker found: `demo --replay` into an existing output dir resumed from stale snapshots (tick() loads latest). Fixed: replay clears its own derived snapshots; live demo refuses to overwrite an existing run.
- Plan pass hit mid-stream `cyber` false positives on ticks 1, 3, 4, 5, 6 (served by claude-opus-4-8 after retry); ticks 2 and 7 served by claude-opus-5-5. Predict pass never refused.
- Citizen feed resolution text was one repeated template → now varies by the new path's first event kind.
- Final-screen polish: circle centred (instant resize, no blank canvas), 3D labels + feed hidden behind overlay.
- Demo arc reality: stability 78.4 → 91.7, active loop 12 → 5 (6 of 12 at tick 6). The circle never reached the perfect hairline: the plan keeps intervening and the rule-based sim keeps producing a little defiance, so 2–4 divergences persist. Options if wanted: a quiet "no-intervention" tick type, or lower spontaneous-deviation rate in sim.
- Open: 60 fps on real GPU unverified (only SwiftShader here); AO/tilt-shift stretch polish not done; three r186 removed PCFSoftShadowMap → PCFShadowMap used.
- Contract/plan deviations: vendor addons live under web/vendor/three/addons/ (import map maps `three/addons/`); `geo.py` + `runner.py` added; `CityState.district_pressure` added.
- [x] People as blinking dots (world.js): subjects = screen-space beacon dots (white core, dark rim, halo flash; blink rate ∝ deviation_risk, halo tinted by risk in System view); crowd = twinkling points. Retirement wireframe = geodesic dot. Final dot look not visually confirmed (screenshots stopped at user request).
- [x] Clearer labels + tooltips + futuristic HUD: 3D labels now 'SURNAME, First · rNN / RISK 62% · TIER IV · † 2041' (hover + click); glossary.js (62 terms) + tooltip.js (hover explanations on header, feed, circle, drawer, OPUS card, 3D labels); map key legend; plain-language wording (WEEK, FORECAST ACC., Rung 3 · Isolate, human disruption names); HUD restyle in System view, warmer Citizen view. Not visually verified (no screenshots per user).
- [x] Citizen-view contrast: peach-filled toggle/drawer tabs now use dark ink (#2a1709); outline buttons warm off-white; inactive toggle muted. Not visually verified (no screenshots per user).
- [x] DISRUPT dropdown was clipped by the header's overflow:hidden (added with the HUD sweep line) → overflow-x: clip / overflow-y: visible, header z-index 100, menu 200. Not visually verified (no screenshots per user).
- [x] Plain-English life projections: plain.py pass (Opus, low effort, recorded) translates headlines + death causes per week into state.plain (410 in demo, no pronouns); card/timeline/gallery show plain text, hover shows explanation + Rehoboam's term; predict.md asks for plain headlines. Demo rebuilt; replay identical ticks 0–7.
- Found: a CRLF/escape bug left a raw newline in a JS string (profile.js, views.js) → blank app. `node --check <file>` did NOT catch it; use `node --input-type=module --check < file`. Fixed with an NL constant.
- Found: shared headline translations leaked pronouns across people ('Separates from her husband' on a man's card) → plain prompt forbids names/pronouns.
