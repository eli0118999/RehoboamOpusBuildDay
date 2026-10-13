"""ONE call wrapper: stream + structured parse + record/replay + stop-reason checks.

Usage:
    llm.configure(run_dir, replay=False)
    obj = llm.call("predict", "r07", system_text, blocks, Prediction, effort="medium")

Every live call is written to <run_dir>/calls/<pass>__<key>.json. In replay mode those files are
read back instead and no API key is needed. Cache layout: system text -> Archive block (marked with
cache_control by the caller via archive_block()) -> task text.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from . import config

log = logging.getLogger("rehoboam.llm")
T = TypeVar("T", bound=BaseModel)

_run_dir: Path | None = None
_replay = False
_fill_missing = False   # replay mode: make (and record) live calls for passes added after the recording
_client = None
_lock = threading.Lock()


MAX_ATTEMPTS = 3


class LLMError(RuntimeError):
    pass


class RefusalError(LLMError):
    pass


class MissingRecording(LLMError):
    pass


def configure(run_dir: Path | str, replay: bool = False, fill_missing: bool = False) -> None:
    global _run_dir, _replay, _fill_missing
    _run_dir = Path(run_dir)
    _replay = replay
    _fill_missing = fill_missing
    (_run_dir / "calls").mkdir(parents=True, exist_ok=True)


def is_replay() -> bool:
    return _replay


def _get_client():
    global _client
    with _lock:
        if _client is None:
            from dotenv import load_dotenv
            load_dotenv(config.ROOT / ".env")
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise LLMError("Set ANTHROPIC_API_KEY in .env (see README)")
            import anthropic
            _client = anthropic.Anthropic(max_retries=3, timeout=900)
        return _client


def text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def archive_block(archive_json: str) -> dict:
    """The big shared prefix block; cached so per-subject calls reuse it."""
    return {"type": "text", "text": "<archive>\n" + archive_json + "\n</archive>",
            "cache_control": {"type": "ephemeral"}}


def _path(pass_name: str, key: str) -> Path:
    if _run_dir is None:
        raise LLMError("llm.configure(run_dir) not called")
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    return _run_dir / "calls" / f"{pass_name}__{safe}.json"


def call(pass_name: str, key: str, system: str, blocks: list[dict], schema: type[T],
         effort: str = "medium") -> T:
    path = _path(pass_name, key)
    if _replay and not (path.exists() or _fill_missing):
        raise MissingRecording(f"no recording for {pass_name}/{key} at {path}")
    if (_replay or config.REUSE_RECORDINGS) and path.exists():
        # resume: a live run that crashed or was pre-seeded keeps its paid-for calls
        log.info("reusing recording %s/%s", pass_name, key)
        return schema.model_validate(json.loads(path.read_text(encoding="utf-8"))["output"])

    client = _get_client()
    import anthropic
    # Raw json_schema (not output_format=Model): the SDK's per-block parse aborts the stream when a
    # mid-stream refusal closes a partial text block, killing the server-side fallback continuation.
    # We join every text block across fallback boundaries and validate ourselves.
    kwargs = dict(
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": blocks}],
        output_config={"effort": effort,
                       "format": {"type": "json_schema", "schema": anthropic.transform_schema(schema)}},
    )
    if config.USE_FALLBACK:
        kwargs.update(betas=[config.FALLBACK_BETA], fallbacks="default")
    for attempt in range(1, MAX_ATTEMPTS + 1):
        log.info("call %s/%s effort=%s attempt=%d", pass_name, key, effort, attempt)
        with client.beta.messages.stream(**kwargs) as stream:
            msg = stream.get_final_message()
        usage = msg.usage.model_dump(mode="json") if msg.usage else {}
        if msg.stop_reason == "max_tokens":
            raise LLMError(f"{pass_name}/{key}: hit max_tokens ({config.MAX_TOKENS})")
        fallbacks = [b.model_dump(mode="json") for b in msg.content if b.type == "fallback"]
        if msg.stop_reason == "refusal":
            details = msg.stop_details.model_dump(mode="json") if getattr(msg, "stop_details", None) else None
            log.error("%s/%s refused: %s fallbacks=%s model=%s", pass_name, key, details, fallbacks, msg.model)
            if attempt == MAX_ATTEMPTS:
                raise RefusalError(f"{pass_name}/{key} refused: {details}")
            continue
        # Only text after the last fallback boundary belongs to the model that finished.
        last_fb = max((i for i, b in enumerate(msg.content) if b.type == "fallback"), default=-1)
        mid_stream = any(b.type == "text" for b in msg.content[:last_fb]) if last_fb >= 0 else False
        if fallbacks:
            log.warning("%s/%s fell back%s: %s (served by %s)", pass_name, key,
                        " mid-stream" if mid_stream else "", fallbacks, msg.model)
        if mid_stream and attempt < MAX_ATTEMPTS:
            # Under structured outputs the fallback restarts the JSON (often a stub). Retry: sticky
            # routing then serves the whole request from the fallback model from the first token.
            continue
        text = "".join(b.text for b in msg.content[last_fb + 1:] if b.type == "text")
        try:
            parsed = schema.model_validate_json(text)
            break
        except Exception as e:
            dump = path.with_suffix(f".failed{attempt}.json")
            dump.write_text(json.dumps({"stop_reason": msg.stop_reason, "model": msg.model, "usage": usage,
                                        "content": [b.model_dump(mode="json") for b in msg.content]},
                                       indent=1, ensure_ascii=False), encoding="utf-8")
            if attempt == MAX_ATTEMPTS:
                raise LLMError(f"{pass_name}/{key}: unparseable output (stop_reason={msg.stop_reason}), "
                               f"dumped to {dump}") from e
            log.warning("%s/%s unparseable on attempt %d, retrying", pass_name, key, attempt)

    rec = {"pass": pass_name, "key": key, "model": msg.model, "effort": effort, "stop_reason": msg.stop_reason,
           "fallbacks": fallbacks, "usage": usage, "output": parsed.model_dump(mode="json")}
    path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    log.info("done %s/%s in=%s out=%s cache_read=%s model=%s", pass_name, key, usage.get("input_tokens"),
             usage.get("output_tokens"), usage.get("cache_read_input_tokens"), msg.model)
    return parsed


def load_prompt(name: str) -> str:
    return (config.PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
