from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import BUILD_ID, __version__
from .config import PROJECT_ROOT, Settings, load_settings, read_json
from .database import Database
from .benchmark import run_local_benchmark
from .diagnostics import build_export20, capture_critical, configure_logging, install_exception_hooks
from .evals import run_evaluations
from .ingest import ALLOWED_EXTENSIONS, ingest_file, store_upload_without_overwrite
from .integrity import IntegrityResult, cache_integrity_result, verify_release
from .pii import redact_pii
from .schemas import AskRequest, FeedbackRequest, ReviewCreateRequest, ReviewUpdateRequest
from .seed import bootstrap_database, reset_demo_database
from .service import PolicyService

logger = logging.getLogger(__name__)


def _safe_filename(filename: str) -> str:
    base = Path(filename).name
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", base).strip(" .")
    return cleaned[:140] or "uploaded_document.txt"


def create_app(
    integrity: IntegrityResult | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    # Standalone callers verify here. The canonical server passes its already completed
    # release result/settings so app construction does not rehash the package a third time.
    if integrity is None:
        integrity = verify_release(PROJECT_ROOT, strict=True)
    if not integrity.ok:
        raise RuntimeError("Application creation requires a successful release-integrity result")
    if settings is None:
        # Supported local settings are read only after the release gate above.
        settings = load_settings()
    cache_integrity_result(settings.state_dir, integrity)
    configure_logging(settings)
    db = Database(settings.db_path)
    seed_result = bootstrap_database(db, settings)
    service = PolicyService(db, settings)
    install_exception_hooks(settings, db, runtime_identity=integrity.to_dict())

    app = FastAPI(
        title="Policy and Procedure Navigator API",
        description="Evidence-grounded policy answers, permission-aware retrieval, evaluation, and controlled workflows.",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.state.integrity = integrity
    app.state.settings = settings
    app.state.db = db
    app.state.service = service
    app.state.seed_result = seed_result

    @app.middleware("http")
    async def prevent_stale_local_ui(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path == "/" or path.startswith("/assets/"):
            # Portfolio builds are frequently extracted over the same local URL.
            # Never allow an older HTML/JS document to survive a release upgrade.
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    def require_user(user_id: str) -> dict[str, Any]:
        try:
            return service.get_user(user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    app.mount("/assets", StaticFiles(directory=settings.root / "app" / "static"), name="assets")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled request error on %s", request.url.path)
        result = await run_in_threadpool(
            capture_critical,
            settings,
            exc,
            "unhandled_http_exception",
            db,
            "api",
            integrity.to_dict(),
        )
        return JSONResponse(
            status_code=500,
            content={
                "detail": "A critical application error was contained. A local diagnostic capsule was created.",
                "diagnostic_capsule": result.get("capsule_path"),
            },
        )

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(settings.root / "app" / "static" / "index.html")

    def readiness_snapshot() -> dict[str, Any]:
        db_health = db.health()
        audit = db.verify_audit_chain()
        ready = bool(integrity.ok and db_health.get("ok") and audit.get("ok"))
        return {
            "ready": ready,
            "status": "ready" if ready else "not_ready",
            "version": __version__,
            "build_id": BUILD_ID,
            "integrity_ok": integrity.ok,
            "database": db_health,
            "audit_chain": audit,
        }

    @app.get("/api/health/live")
    async def liveness() -> dict[str, Any]:
        return {"status": "alive", "version": __version__, "build_id": BUILD_ID}

    @app.get("/api/health/ready")
    async def readiness() -> JSONResponse:
        payload = await run_in_threadpool(readiness_snapshot)
        return JSONResponse(status_code=200 if payload["ready"] else 503, content=payload)

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        metrics, ready = await run_in_threadpool(lambda: (db.metrics(), readiness_snapshot()))
        return {
            "status": ready["status"],
            "canonical_project": "Professional Portfolio — Governed AI Knowledge & Workflow Assistant",
            "display_name": "Policy and Procedure Navigator",
            "version": __version__,
            "build_id": BUILD_ID,
            "provider_mode": settings.provider_mode,
            "keyless": settings.keyless,
            "network_provider_enabled": False,
            "credentials_required": False,
            "integrity": integrity.to_dict(),
            "seed": seed_result,
            "metrics": metrics,
            "database": ready["database"],
            "audit_chain": ready["audit_chain"],
        }

    @app.get("/api/users")
    async def users() -> list[dict[str, Any]]:
        return list(service.users.values())

    @app.get("/api/demo/overview")
    async def demo_overview() -> dict[str, Any]:
        metrics, ready, evaluation = await run_in_threadpool(
            lambda: (db.metrics(), readiness_snapshot(), db.latest_evaluation())
        )
        return {
            "tour": read_json("config/demo_tour.json"),
            "proof": {
                "ready": ready["ready"],
                "integrity_ok": integrity.ok,
                "keyless": True,
                "network_required": False,
                "documents": metrics["documents"],
                "chunks": metrics["chunks"],
                "audit_chain_ok": ready["audit_chain"]["ok"],
                "latest_eval_score": evaluation["score"] if evaluation else None,
            },
        }

    @app.post("/api/demo/reset")
    async def demo_reset(user_id: str = "admin.demo") -> dict[str, Any]:
        user = require_user(user_id)
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Demo Administrator is required to reset local demo state")
        result = await run_in_threadpool(reset_demo_database, db, settings)
        service.retrieval_cache.clear(reset_counters=True)
        app.state.seed_result = result["seed"]
        return result

    @app.post("/api/benchmark/run")
    async def benchmark_run(user_id: str = "admin.demo") -> dict[str, Any]:
        require_user(user_id)
        return await run_in_threadpool(run_local_benchmark, service)

    @app.get("/api/documents")
    async def documents(user_id: str = "ava.employee") -> list[dict[str, Any]]:
        user = require_user(user_id)
        result = []
        document_rows = await run_in_threadpool(db.list_documents)
        for document in document_rows:
            allowed = user["role"] == "admin" or user["role"] in document["allowed_roles"]
            if not allowed:
                continue
            result.append(
                {
                    "id": document["id"],
                    "title": document["title"],
                    "source_filename": document["source_filename"],
                    "policy_family": document["policy_family"],
                    "department": document["department"],
                    "classification": document["classification"],
                    "effective_date": document["effective_date"],
                    "expires_at": document["expires_at"],
                    "status": document["status"],
                    "version": document["version"],
                    "authority_rank": document["authority_rank"],
                    "allowed_roles": document["allowed_roles"],
                    "description": document["metadata"].get("description", ""),
                }
            )
        return result

    @app.post("/api/documents")
    async def upload_document(
        user_id: Annotated[str, Form()] = "admin.demo",
        file: UploadFile = File(...),
        title: Annotated[str | None, Form()] = None,
        policy_family: Annotated[str | None, Form()] = None,
        department: Annotated[str | None, Form()] = None,
        classification: Annotated[str, Form()] = "internal",
        allowed_roles: Annotated[str, Form()] = "employee,procurement,legal,security,admin",
        effective_date: Annotated[str | None, Form()] = None,
        expires_at: Annotated[str | None, Form()] = None,
        status_value: Annotated[str, Form(alias="status")] = "active",
        version: Annotated[str, Form()] = "1.0",
        authority_rank: Annotated[int, Form()] = 50,
    ) -> dict[str, Any]:
        user = require_user(user_id)
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Only the demo administrator may ingest documents")
        safe_name = _safe_filename(file.filename or "uploaded_document.txt")
        suffix = Path(safe_name).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail=f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
        content = await file.read(settings.max_upload_bytes + 1)
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="Document exceeds the 15 MB demonstration limit")
        try:
            destination = await run_in_threadpool(store_upload_without_overwrite, settings.uploads_dir, safe_name, content)
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Document could not be stored safely") from exc
        try:
            result = await run_in_threadpool(
                ingest_file,
                db,
                destination,
                {
                    "title": title,
                    "policy_family": policy_family,
                    "department": department,
                    "classification": classification,
                    "allowed_roles": allowed_roles,
                    "effective_date": effective_date,
                    "expires_at": expires_at,
                    "status": status_value,
                    "version": version,
                    "authority_rank": authority_rank,
                },
                True,
            )
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"Document ingestion failed: {type(exc).__name__}") from exc
        await run_in_threadpool(
            db.append_audit,
            user_id,
            "document_ingested",
            {
                "title": result["title"],
                "chunks": result["chunks"],
                "pii_redactions": result["pii_redactions"],
                "classification": classification,
                "status": status_value,
            },
            "document",
            result["document_id"],
        )
        return result

    @app.post("/api/ask")
    async def ask(payload: AskRequest) -> dict[str, Any]:
        require_user(payload.user_id)
        try:
            return await run_in_threadpool(service.ask, payload.question, payload.user_id, True)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/reviews")
    async def reviews(user_id: str = "ava.employee") -> list[dict[str, Any]]:
        require_user(user_id)
        try:
            return await run_in_threadpool(service.list_reviews, user_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/reviews")
    async def create_review(payload: ReviewCreateRequest) -> dict[str, Any]:
        require_user(payload.user_id)
        try:
            return await run_in_threadpool(service.create_review_from_query, payload.query_run_id, payload.user_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/reviews/{review_id}")
    async def update_review(review_id: str, payload: ReviewUpdateRequest) -> dict[str, Any]:
        require_user(payload.user_id)
        try:
            return await run_in_threadpool(service.update_review, review_id, payload.user_id, payload.status, payload.decision_note)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/feedback")
    async def feedback(payload: FeedbackRequest) -> dict[str, Any]:
        require_user(payload.user_id)
        try:
            return await run_in_threadpool(
                service.record_feedback, payload.query_run_id, payload.user_id, payload.rating, payload.correction
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/evaluations/run")
    async def evaluations_run(user_id: str = "admin.demo") -> dict[str, Any]:
        user = require_user(user_id)
        if not user.get("can_review"):
            raise HTTPException(status_code=403, detail="Reviewer authority is required")
        return await run_in_threadpool(run_evaluations, db, service, True)

    @app.get("/api/evaluations/latest")
    async def evaluations_latest() -> dict[str, Any] | None:
        return await run_in_threadpool(db.latest_evaluation)

    @app.get("/api/audit")
    async def audit(user_id: str = "admin.demo", limit: int = 100) -> dict[str, Any]:
        user = require_user(user_id)
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Administrator authority is required")
        bounded_limit = max(1, min(limit, 500))
        return await run_in_threadpool(
            lambda: {"chain": db.verify_audit_chain(), "events": db.list_audit(bounded_limit)}
        )

    @app.get("/api/metrics")
    async def metrics() -> dict[str, Any]:
        return await run_in_threadpool(db.metrics)

    @app.get("/api/governance/config")
    async def governance_config() -> dict[str, Any]:
        return await run_in_threadpool(
            lambda: {
                "answer_policy_history": read_json("config/answer_policy.json"),
                "engine_catalog": read_json("config/engine_catalog.json"),
                "workflow_templates": read_json("config/workflow_templates.json"),
                "audit_chain": db.verify_audit_chain(),
            }
        )

    @app.post("/api/diagnostics/export20")
    async def export20(user_id: str = "admin.demo") -> dict[str, Any]:
        user = require_user(user_id)
        if user["role"] != "admin":
            raise HTTPException(status_code=403, detail="Administrator authority is required")
        result = await run_in_threadpool(build_export20, settings, db, None, "manual_api")
        await run_in_threadpool(
            db.append_audit,
            user_id,
            "diagnostic_export_requested",
            {key: value for key, value in result.items() if key != "path"}
            | {"path_present": bool(result.get("path"))},
            "diagnostic_export",
            None,
        )
        return result

    @app.post("/api/privacy/redact-preview")
    async def redaction_preview(text: str = Form(...)) -> dict[str, Any]:
        result = await run_in_threadpool(redact_pii, text)
        return {"redacted_text": result.text, "counts": result.counts, "total": result.total}

    return app

