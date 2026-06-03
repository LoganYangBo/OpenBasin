"""The pipeline engine — orchestrates the four stages per event.

For each incoming :class:`SignalEvent`:

1. **trigger** — collect pipelines whose trigger matches (type/app/keyword).
2. **extract** — run the LLM once per matching pipeline to fill its schema.
3. **conditions** — evaluate gating expressions against the extracted fields.
4. **actions** — execute each configured action; failures are logged, not fatal.

Actions within a pipeline run concurrently; a failing action never aborts its
siblings or other pipelines. Every action outcome is written to ``action_log``.
"""

from __future__ import annotations

import asyncio
import logging

from server.actions import ActionContext, ActionError, build_action
from server.db import EventStore
from server.extract import Extractor
from server.extract.prompts import get_prompt
from server.models import SignalEvent
from server.pipeline.conditions import ConditionError, all_pass
from server.pipeline.models import Pipeline

log = logging.getLogger("openbasin.engine")


class PipelineEngine:
    def __init__(
        self,
        pipelines: list[Pipeline],
        extractor: Extractor,
        store: EventStore,
        secrets: dict[str, str] | None = None,
    ) -> None:
        self.pipelines = pipelines
        self.extractor = extractor
        self.store = store
        self.secrets = secrets or {}

    def reload(self, pipelines: list[Pipeline]) -> None:
        self.pipelines = pipelines
        log.info("Reloaded %d pipelines", len(pipelines))

    def matching(self, event: SignalEvent) -> list[Pipeline]:
        return [p for p in self.pipelines if p.trigger.matches(event)]

    async def process(self, event: SignalEvent) -> list[str]:
        """Process one event through every matching pipeline.

        Returns the names of pipelines that fired at least to the action stage.
        """
        matched = self.matching(event)
        if not matched:
            return []
        results = await asyncio.gather(
            *(self._run_pipeline(p, event) for p in matched), return_exceptions=True
        )
        fired = []
        for pipeline, result in zip(matched, results, strict=False):
            if isinstance(result, Exception):
                log.error("Pipeline %s errored: %s", pipeline.name, result)
            elif result:
                fired.append(pipeline.name)
        return fired

    async def _run_pipeline(self, pipeline: Pipeline, event: SignalEvent) -> bool:
        # --- extract -----------------------------------------------------
        schema = dict(pipeline.extract.schema_)
        instructions = pipeline.extract.instructions or ""
        if pipeline.extract.prompt:
            try:
                prompt_def = get_prompt(pipeline.extract.prompt)
                # A named prompt supplies a schema + instructions; the pipeline's
                # own schema overrides on key conflicts.
                merged = dict(prompt_def.get("schema", {}))
                merged.update(schema)
                schema = merged
                instructions = instructions or prompt_def.get("instructions", "")
            except KeyError as exc:
                log.error("Pipeline %s: %s", pipeline.name, exc)

        fields: dict = {}
        if schema:
            try:
                fields = await self.extractor.extract(event, schema, instructions)
            except Exception as exc:  # noqa: BLE001 — LLM/parse failures must not crash ingest
                log.error("Pipeline %s extraction failed: %s", pipeline.name, exc)
                return False

        # --- conditions --------------------------------------------------
        if pipeline.conditions:
            try:
                if not all_pass(pipeline.conditions, fields):
                    log.info("Pipeline %s: conditions not met, skipping actions", pipeline.name)
                    return False
            except ConditionError as exc:
                log.error("Pipeline %s condition error: %s", pipeline.name, exc)
                return False

        # --- actions -----------------------------------------------------
        ctx = ActionContext(event=event, fields=fields)
        await asyncio.gather(
            *(self._run_action(pipeline, cfg, ctx) for cfg in pipeline.actions)
        )
        return True

    async def _run_action(self, pipeline: Pipeline, cfg: dict, ctx: ActionContext) -> None:
        action_type = cfg.get("type", "?")
        try:
            action = build_action(cfg, self.secrets)
            detail = await action.run(ctx)
            self.store.log_action(ctx.event.event_id, pipeline.name, action_type, True, detail)
            log.info("Pipeline %s action %s ok: %s", pipeline.name, action_type, detail)
        except ActionError as exc:
            self.store.log_action(ctx.event.event_id, pipeline.name, action_type, False, str(exc))
            log.error("Pipeline %s action %s failed: %s", pipeline.name, action_type, exc)
        except Exception as exc:  # noqa: BLE001 — never let one action kill the batch
            self.store.log_action(ctx.event.event_id, pipeline.name, action_type, False, str(exc))
            log.exception("Pipeline %s action %s crashed", pipeline.name, action_type)
