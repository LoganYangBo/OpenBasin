"""Load pipeline YAML files from a directory tree."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from server.pipeline.models import Pipeline

log = logging.getLogger("openbasin.pipeline")


def load_pipelines(directory: str | Path) -> list[Pipeline]:
    """Recursively load every ``*.yaml`` / ``*.yml`` file under ``directory``.

    A malformed pipeline is logged and skipped rather than crashing the server —
    one broken file should not take down ingestion for all the others.
    """
    root = Path(directory)
    if not root.exists():
        log.warning("Pipelines directory %s does not exist; no pipelines loaded.", root)
        return []

    pipelines: list[Pipeline] = []
    for path in sorted([*root.rglob("*.yaml"), *root.rglob("*.yml")]):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not data:
                continue
            pipelines.append(Pipeline.model_validate(data))
            log.info("Loaded pipeline %s from %s", data.get("name"), path)
        except Exception as exc:  # noqa: BLE001 — one bad file must not abort the rest
            log.error("Skipping invalid pipeline %s: %s", path, exc)
    return pipelines
