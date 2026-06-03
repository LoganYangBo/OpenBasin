"""Application factory and routes.

Device authentication: every ingest request carries an ``X-Device-Token``
header. The server rejects any token not present in ``config.yaml`` — unknown
devices never reach the pipeline. The event body is an AES-256-GCM envelope
decrypted with that device's key.

No telemetry, ever — there are no outbound calls here other than to the user's
configured LLM (during extraction) and action targets.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import Depends, FastAPI, Header, HTTPException

from server import __version__
from server.api.schemas import (
    Envelope,
    HealthResponse,
    PlainEvent,
    ReloadResponse,
)
from server.config import Config, DeviceConfig, load_config
from server.db import EventStore
from server.extract import Extractor, LLMClient
from server.models import IngestResult, SignalEvent
from server.pipeline import PipelineEngine, load_pipelines
from server.sources import (
    EmailSource,
    NotificationSource,
    SmsSource,
    SourceError,
    get_source,
    register_source,
)
from server.transport import EnvelopeError, decrypt_envelope

log = logging.getLogger("openbasin.api")


@dataclass
class AppState:
    config: Config
    store: EventStore
    engine: PipelineEngine


def _register_sources() -> None:
    register_source(SmsSource())
    register_source(EmailSource())
    register_source(NotificationSource())


def build_state(config: Config) -> AppState:
    _register_sources()
    store = EventStore(config.db.path)
    extractor = Extractor(LLMClient(config.llm))
    pipelines = load_pipelines(config.server.pipelines_dir)
    engine = PipelineEngine(pipelines, extractor, store, secrets=config.secrets)
    log.info("OpenBasin ready: %d pipelines, %d devices", len(pipelines), len(config.devices))
    return AppState(config=config, store=store, engine=engine)


def create_app(config: Config | None = None) -> FastAPI:
    cfg = config or load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.ob = build_state(cfg)
        yield
        app.state.ob.store.close()

    app = FastAPI(title="OpenBasin", version=__version__, lifespan=lifespan)

    # -- auth dependency --------------------------------------------------
    def authenticate(x_device_token: str = Header(default="")) -> DeviceConfig:
        device = app.state.ob.config.device_by_token(x_device_token)
        if device is None:
            # Unregistered device — reject before any processing.
            raise HTTPException(status_code=401, detail="Unknown or missing device token")
        return device

    # -- ingestion --------------------------------------------------------
    async def _ingest(payload: dict, signal_type: str, device_id: str) -> IngestResult:
        payload = {**payload, "signal_type": signal_type}
        try:
            source = get_source(signal_type)
            event: SignalEvent = source.normalize(payload, device_id)
        except SourceError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if not app.state.ob.store.insert(event):
            return IngestResult(event_id=event.event_id, accepted=True, duplicate=True)

        fired = await app.state.ob.engine.process(event)
        return IngestResult(event_id=event.event_id, accepted=True, matched_pipelines=fired)

    @app.post("/v1/events", response_model=IngestResult)
    async def ingest_encrypted(
        envelope: Envelope, device: DeviceConfig = Depends(authenticate)
    ) -> IngestResult:
        if envelope.device_id != device.device_id:
            raise HTTPException(status_code=403, detail="Envelope device_id does not match token")
        try:
            payload = decrypt_envelope(envelope.model_dump(), device.aes_key)
        except EnvelopeError as exc:
            raise HTTPException(status_code=400, detail=f"Decryption failed: {exc}") from exc

        signal_type = payload.get("signal_type")
        if not signal_type:
            raise HTTPException(status_code=422, detail="Decrypted payload missing signal_type")
        return await _ingest(payload, signal_type, device.device_id)

    @app.post("/v1/events/plain", response_model=IngestResult)
    async def ingest_plain(
        body: PlainEvent, device: DeviceConfig = Depends(authenticate)
    ) -> IngestResult:
        """Unencrypted ingest for local sources and testing. Still token-gated."""
        return await _ingest(body.payload, body.signal_type, device.device_id)

    # -- operations -------------------------------------------------------
    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        ob = app.state.ob
        return HealthResponse(
            version=__version__,
            pipelines=len(ob.engine.pipelines),
            events_stored=ob.store.count(),
            devices=len(ob.config.devices),
        )

    @app.post("/v1/reload", response_model=ReloadResponse)
    async def reload(device: DeviceConfig = Depends(authenticate)) -> ReloadResponse:
        ob = app.state.ob
        pipelines = load_pipelines(ob.config.server.pipelines_dir)
        ob.engine.reload(pipelines)
        return ReloadResponse(reloaded=True, pipelines=len(pipelines))

    @app.get("/v1/events/recent")
    async def recent(
        limit: int = 50, device: DeviceConfig = Depends(authenticate)
    ) -> list[dict]:
        return app.state.ob.store.recent(limit=limit)

    return app
