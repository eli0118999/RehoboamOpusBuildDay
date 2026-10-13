"""Command-line entry point: `python -m rehoboam <subcommand>`.

Runner / state / plan / llm are imported lazily so `--help` works even before they exist.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

from . import config

log = logging.getLogger("rehoboam")


# ---------------------------------------------------------------- helpers
def _new_run_id() -> str:
    return datetime.now().strftime("run-%Y%m%d-%H%M%S")


def _run_for(args, parser: argparse.ArgumentParser) -> str:
    """Resolve the run id: subcommand --run, else the global --replay RUN."""
    run = getattr(args, "run", None) or args.replay
    if not run:
        parser.error("--run ID is required (or pass the global --replay RUN)")
    return run


def _status(state) -> str:
    m = state.metrics
    return (f"[{state.run_id}] tick {state.tick} year {state.year}: "
            f"stability {m.stability:.1f} | active {m.active}/{m.total} | "
            f"reassigned {m.reassigned} | interventions {m.interventions} | "
            f"defiances {m.defiances}")


def _print_state(state) -> None:
    print(_status(state))


def _list_runs() -> list[dict]:
    try:
        from . import state as state_mod
    except ImportError:
        state_mod = None
    if state_mod is not None:
        return state_mod.list_runs()
    runs = []
    if config.RUNS_DIR.exists():
        for d in sorted(config.RUNS_DIR.iterdir()):
            if d.is_dir():
                ticks = sorted(int(p.stem.split("_")[1]) for p in d.glob("tick_*.json"))
                if ticks:
                    runs.append({"run_id": d.name, "ticks": ticks})
    return runs


def _configure_llm(run: str, replay: bool) -> None:
    """Point the llm cache/replay at the run folder (make_plan needs this without runner.start)."""
    from . import llm
    llm.configure(config.RUNS_DIR / run, replay)


# ---------------------------------------------------------------- subcommands
def cmd_seed(args, parser) -> int:
    from . import runner
    run = args.run or args.replay or _new_run_id()
    runner.start(run, replay=_is_replay(args))
    archive = runner.seed(run)
    print(f"seeded run {run}: {archive.city.name}, {len(archive.residents)} residents, "
          f"{len(archive.records)} records")
    return 0


def cmd_predict(args, parser) -> int:
    from . import runner
    run = _run_for(args, parser)
    runner.start(run, replay=_is_replay(args))
    _print_state(runner.predict(run))
    return 0


def cmd_plan(args, parser) -> int:
    from . import plan, state as state_mod
    run = _run_for(args, parser)
    _configure_llm(run, _is_replay(args))
    city_state = state_mod.load_state(run)
    p = plan.make_plan(city_state)
    print(p.model_dump_json(indent=2))
    return 0


def cmd_tick(args, parser) -> int:
    from . import runner
    run = _run_for(args, parser)
    runner.start(run, replay=_is_replay(args))
    for _ in range(args.n):
        _print_state(runner.tick(run))
    return 0


def cmd_disrupt(args, parser) -> int:
    from . import runner
    run = _run_for(args, parser)
    runner.start(run, replay=_is_replay(args))
    runner.queue_disruption(run, args.disruption_id)
    print(f"queued disruption {args.disruption_id} for next tick of {run}")
    return 0


def cmd_demo(args, parser) -> int:
    from . import runner
    # --replay RUN (on demo or globally) reads recorded calls from runs/RUN, so that is the run id.
    source = args.demo_replay or args.replay
    run = source or args.run
    state = runner.demo(run_id=run, replay=source is not None, ticks=args.ticks)
    _print_state(state)
    return 0


def cmd_serve(args, parser) -> int:
    import uvicorn
    print(f"serving Mini Rehoboam on http://{args.host}:{args.port}")
    uvicorn.run("rehoboam.server:app", host=args.host, port=args.port, log_level="info")
    return 0


def cmd_runs(args, parser) -> int:
    runs = _list_runs()
    if not runs:
        print("no runs found")
        return 0
    for r in runs:
        ticks = r.get("ticks", [])
        span = f"ticks {ticks[0]}..{ticks[-1]} ({len(ticks)})" if ticks else "no ticks"
        print(f"{r['run_id']}\t{span}")
    return 0


def _is_replay(args) -> bool:
    return args.replay is not None


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m rehoboam",
        description="Mini Rehoboam: predictive-policing simulation CLI.",
    )
    parser.add_argument("--replay", metavar="RUN", default=None,
                        help="use recorded LLM calls from runs/RUN instead of calling the API")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("seed", help="generate the archive for a new run")
    p.add_argument("--run", metavar="ID", default=None, help="run id (default: timestamped)")
    p.set_defaults(func=cmd_seed)

    p = sub.add_parser("predict", help="run tick-0 predictions for a run")
    p.add_argument("--run", metavar="ID", required=False)
    p.set_defaults(func=cmd_predict)

    p = sub.add_parser("plan", help="print the plan for the next tick without applying it")
    p.add_argument("--run", metavar="ID", required=False)
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("tick", help="advance a run by one or more ticks")
    p.add_argument("--run", metavar="ID", required=False)
    p.add_argument("--n", type=int, default=1, help="number of ticks (default 1)")
    p.set_defaults(func=cmd_tick)

    p = sub.add_parser("disrupt", help="queue a disruption for the next tick")
    p.add_argument("disruption_id", help="registry key, e.g. factory_closure")
    p.add_argument("--run", metavar="ID", required=False)
    p.set_defaults(func=cmd_disrupt)

    p = sub.add_parser("demo", help="run a short scripted demo")
    p.add_argument("--run", metavar="ID", default="demo", help="run id (default: demo)")
    p.add_argument("--replay", dest="demo_replay", metavar="RUN", default=None,
                   help="replay recorded calls from runs/RUN")
    p.add_argument("--ticks", type=int, default=4, help="number of ticks (default 4)")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("serve", help="start the web server (uvicorn rehoboam.server:app)")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--host", default="127.0.0.1")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("runs", help="list runs and their ticks")
    p.set_defaults(func=cmd_runs)

    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rc = args.func(args, parser)
    except ImportError as e:
        print(f"error: module not available yet ({e})", file=sys.stderr)
        sys.exit(2)
    except Exception as e:  # keep CLI failures short; full trace at DEBUG
        log.debug("command failed", exc_info=True)
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    sys.exit(rc)


if __name__ == "__main__":
    main()
