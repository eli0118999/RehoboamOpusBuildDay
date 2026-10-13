"""Pass 1: generate the founding Archive."""
from __future__ import annotations

import logging

from . import config, llm
from .predict import system_prompt
from .schemas import Archive
from .validate import validate_archive

log = logging.getLogger("rehoboam.archive")


def generate_archive(n: int = config.N_SUBJECTS, year: int = config.YEAR) -> Archive:
    task = llm.load_prompt("archive").format(
        n=n, population=config.POPULATION, year=year, year_start=year - 3)
    raw = llm.call("archive", "seed", system_prompt(), [llm.text_block(task)], Archive,
                   config.EFFORT["archive"])
    fixed, warns = validate_archive(raw)
    for w in warns:
        log.warning("archive: %s", w)
    return fixed
