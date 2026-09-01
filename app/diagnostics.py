from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sys
import threading
import time
import traceback
import uuid
import zipfile
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import BUILD_ID, __version__
from .config import Settings
from .database import Database, utc_now
from .integrity import load_cached_integrity, sha256_file
from .pii import redact_pii

_LOG_BUFFER: deque[str] = deque(maxlen=400)
_EXPORTING = threading.local()
_EXPORT_PROCESS_LOCK = threading.Lock()
_MAX_LOG_TAIL_CHARS = 64 * 1024
_MAX_STAGE_BYTES = 8 * 1024 * 1024
_MAX_ZIP_BYTES = 10 * 1024 * 1024
_EXPORT_BUDGET_SECONDS = 8.0


class RingBufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            _LOG_BUFFER.append(self.format(record))
        except Exception:
            pass


def configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    if getattr(root, "_gka_configured", False):
        return
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    file_handler = logging.FileHandler(settings.logs_dir / "policy_navigator.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    ring_handler = RingBufferHandler()
    ring_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    root.addHandler(ring_handler)
    root.addHandler(console_handler)
    root._gka_configured = True  # type: ignore[attr-defined]


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _sanitize_text(text: str, settings: Settings | None = None) -> str:
    sanitized = redact_pii(text).text
    home = str(Path.home())
    if home and home not in {"/", "."}:
        sanitized = sanitized.replace(home, "[REDACTED_HOME]")
    if settings:
        sanitized = sanitized.replace(str(settings.root), "[PROJECT_ROOT]")
    return sanitized


def _fingerprint(exc: BaseException, trigger: str) -> str:
    trace = traceback.extract_tb(exc.__traceback__)
    top = trace[-1] if trace else None
    material = "|".join(
        [
            trigger,
            type(exc).__name__,
            str(exc)[:400],
            f"{Path(top.filename).name}:{top.lineno}:{top.name}" if top else "no-trace",
            __version__,
            BUILD_ID,
        ]
    )
    return hashlib.sha256(material.encode("utf-8", errors="replace")).hexdigest()[:20]


def _redacted_config_summary(settings: Settings) -> dict[str, Any]:
    host_summary = "loopback" if settings.host in {"127.0.0.1", "localhost", "::1"} else "[REDACTED_HOST]"
    return {
        "provider_mode": settings.provider_mode,
        "keyless": True,
        "network_provider_enabled": False,
        "credentials_required": False,
        "host": host_summary,
        "port": settings.port,
        "project_root": ".",
        "mutable_roots": ["local", "state", "logs", "temp", "exports", "diagnostics"],
    }


def _database_summary(db: Database | None) -> dict[str, Any]:
    if not db or not db.path.exists():
        return {"available": False}
    try:
        return {
            "available": True,
            "metrics": db.metrics(),
            "audit_chain": db.verify_audit_chain(),
            "health": db.health(),
            "corpus_generation": db.corpus_generation(),
        }
    except Exception as exc:
        return {"available": False, "error": type(exc).__name__}


def _runtime_identity_summary(settings: Settings, supplied: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(supplied) if supplied else load_cached_integrity(settings.state_dir)
    result["managed_file_rehash_performed"] = False
    result["evidence_source"] = "supplied_completed_result" if supplied else "project_local_cache"
    return result


def _retention_cleanup(
    settings: Settings,
    max_count: int = 12,
    max_age_days: int = 30,
    max_total_mb: int = 250,
) -> None:
    files = sorted(
        settings.exports_dir.glob("PolicyNavigator_EXPORT20_*.zip"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    total = 0
    for index, path in enumerate(files):
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        size = path.stat().st_size
        should_keep = index == 0 or (
            index < max_count
            and modified >= cutoff
            and total + size <= max_total_mb * 1024 * 1024
        )
        if should_keep:
            total += size
            continue
        try:
            path.unlink()
            path.with_suffix(path.suffix + ".sha256.txt").unlink(missing_ok=True)
        except OSError:
            pass


def _write_stage_text(stage: Path, name: str, text: str) -> Path:
    destination = stage / name
    destination.write_text(text, encoding="utf-8")
    return destination


def _write_stage_json(stage: Path, name: str, payload: dict[str, Any]) -> Path:
    return _write_stage_text(stage, name, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _stage_size(stage: Path) -> int:
    return sum(path.stat().st_size for path in stage.iterdir() if path.is_file())



def _launcher_consolidation_summary(settings: Settings) -> dict[str, Any]:
    """Read the verified release registry for diagnostic reporting; never invent launcher state."""
    try:
        metadata = json.loads((settings.root / "PACKAGE_METADATA.json").read_text(encoding="utf-8"))
        registry = metadata.get("launcher_registry") or {}
        actions = registry.get("actions") or {}
        return {
            "canonical_entrypoint": registry.get("canonical_entrypoint"),
            "active_bat_cmd_count": len(
                [
                    path
                    for path in settings.root.iterdir()
                    if path.is_file() and path.suffix.casefold() in {".bat", ".cmd"}
                ]
            ),
            "actions": sorted(actions),
            "retired_launchers": list(registry.get("retired_entrypoints") or []),
            "approved_aliases": list(registry.get("approved_aliases") or []),
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"status": "unavailable"}

def build_export20(
    settings: Settings,
    db: Database | None = None,
    capsule_path: Path | None = None,
    trigger: str = "manual",
    fingerprint: str | None = None,
    runtime_identity: dict[str, Any] | None = None,
    max_seconds: float = _EXPORT_BUDGET_SECONDS,
) -> dict[str, Any]:
    """Create a bounded, redacted, read-only diagnostic archive.

    This function intentionally reuses the last completed runtime-identity result;
    it never rescans or rehashes the managed package.
    """
    if getattr(_EXPORTING, "active", False):
        return {"ok": False, "reason": "recursive_export_suppressed"}
    _EXPORTING.active = True
    started = time.perf_counter()
    run_id = uuid.uuid4().hex[:12]
    lock_path = settings.state_dir / "diagnostic_export.lock"
    lock_fd: int | None = None
    lock_owner = f"{os.getpid()}:{uuid.uuid4().hex}"
    process_lock_acquired = _EXPORT_PROCESS_LOCK.acquire(timeout=min(2.0, max(0.1, max_seconds / 4)))
    if not process_lock_acquired:
        _EXPORTING.active = False
        return {"ok": False, "reason": "exporter_thread_contention"}
    stage: Path | None = None
    temp_zip: Path | None = None

    def budget_available() -> bool:
        return (time.perf_counter() - started) < max_seconds

    try:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, json.dumps({"owner": lock_owner, "pid": os.getpid(), "created_at": utc_now()}).encode("utf-8"))
        except FileExistsError:
            try:
                if time.time() - lock_path.stat().st_mtime > 180:
                    lock_path.unlink()
                    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(lock_fd, json.dumps({"owner": lock_owner, "pid": os.getpid(), "created_at": utc_now(), "recovered_stale_lock": True}).encode("utf-8"))
                else:
                    return {"ok": False, "reason": "exporter_already_active"}
            except OSError:
                return {"ok": False, "reason": "exporter_lock_unavailable"}

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stage = settings.temp_dir / f"export20_{run_id}"
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)

        trigger_safe = _sanitize_text(trigger, settings)[:160]
        _write_stage_json(
            stage,
            "01_TRANSFER_SUMMARY.json",
            {
                "canonical_project": "Professional Portfolio — Governed AI Knowledge & Workflow Assistant",
                "display_name": "Policy and Procedure Navigator",
                "core_descriptor": "Evidence-grounded policy answers with permission-aware retrieval and controlled workflows",
                "version": __version__,
                "build_id": BUILD_ID,
                "canonical_entrypoint": "PolicyNavigator.bat",
                "trigger": trigger_safe,
                "fingerprint": fingerprint,
                "generated_at": utc_now(),
                "sensitivity": "redacted local diagnostic",
                "managed_file_rehash_performed": False,
                "launcher_consolidation": _launcher_consolidation_summary(settings),
                "recovery": "Run PolicyNavigator.bat doctor, then restore the unmodified release if identity verification fails.",
                "copyright": "Copyright © 2026 Gateway Information Group LLC. All rights reserved.",
            },
        )
        _write_stage_json(
            stage,
            "02_RUNTIME_IDENTITY_RESULT.json",
            _runtime_identity_summary(settings, runtime_identity),
        )
        _write_stage_json(stage, "03_CONFIG_SUMMARY_REDACTED.json", _redacted_config_summary(settings))
        _write_stage_json(stage, "04_DATABASE_SUMMARY.json", _database_summary(db))
        log_tail = _sanitize_text("\n".join(_LOG_BUFFER), settings)[-_MAX_LOG_TAIL_CHARS:]
        _write_stage_text(stage, "05_LOG_TAIL_REDACTED.txt", log_tail)
        _write_stage_text(
            stage,
            "06_RECOVERY_NOTES.txt",
            "1. Preserve this archive and its SHA-256 sidecar.\n"
            "2. Run PolicyNavigator.bat doctor.\n"
            "3. Review the crash capsule and redacted log tail.\n"
            "4. Do not edit release-control files to force a pass.\n"
            "5. Restore the exact unmodified release when managed-file identity fails.\n",
        )

        if capsule_path and capsule_path.is_file() and budget_available():
            capsule_text = _sanitize_text(capsule_path.read_text(encoding="utf-8", errors="replace"), settings)
            _write_stage_text(stage, "07_CRASH_CAPSULE_REDACTED.json", capsule_text[:512 * 1024])

        if db and budget_available():
            try:
                latest_eval = db.latest_evaluation()
            except Exception:
                latest_eval = None
            if latest_eval:
                _write_stage_json(stage, "08_LATEST_EVALUATION.json", latest_eval)

        static_candidates = [
            ("09_VERSION.txt", settings.root / "VERSION.txt"),
            ("10_PACKAGE_METADATA.json", settings.root / "PACKAGE_METADATA.json"),
            ("11_MANIFEST.json", settings.root / "MANIFEST.json"),
            ("12_MANIFEST.sha256", settings.root / "MANIFEST.sha256"),
            ("13_CHANGELOG.md", settings.root / "CHANGELOG.md"),
            ("14_KNOWN_GOOD_STATE.md", settings.root / "KNOWN_GOOD_STATE.md"),
            ("15_QUICK_START.md", settings.root / "QUICK_START.md"),
            ("16_SBOM.json", settings.root / "SBOM.json"),
            ("17_GOLDEN_QUESTIONS.json", settings.root / "evals" / "golden_questions.json"),
            ("18_SECURITY_AND_LIMITATIONS.md", settings.root / "SECURITY_AND_LIMITATIONS.md"),
            ("19_RELEASE_GUIDE.md", settings.root / "RELEASE_GUIDE.md"),
            ("20_FILE_LEDGER.md", settings.root / "FILE_LEDGER.md"),
        ]
        for target_name, candidate in static_candidates:
            if not budget_available() or len(list(stage.iterdir())) >= 20:
                break
            try:
                if not candidate.is_file() or candidate.stat().st_size > 2 * 1024 * 1024:
                    continue
                if _stage_size(stage) + candidate.stat().st_size > _MAX_STAGE_BYTES:
                    continue
                shutil.copy2(candidate, stage / target_name)
            except OSError:
                continue

        entries = sorted(path for path in stage.iterdir() if path.is_file())[:20]
        if not entries:
            raise RuntimeError("No diagnostic entries were staged")
        if _stage_size(stage) > _MAX_STAGE_BYTES:
            raise RuntimeError("Diagnostic staging size limit exceeded")
        if not budget_available():
            raise TimeoutError("Diagnostic collection exceeded its time budget")

        suffix = fingerprint or run_id
        temp_zip = settings.temp_dir / f"PolicyNavigator_EXPORT20_{stamp}_{suffix}.zip.tmp"
        final_zip = settings.exports_dir / f"PolicyNavigator_EXPORT20_{stamp}_{suffix}.zip"
        with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for entry in entries:
                archive.write(entry, arcname=entry.name)
        if temp_zip.stat().st_size > _MAX_ZIP_BYTES:
            raise RuntimeError("Diagnostic ZIP size limit exceeded")
        with zipfile.ZipFile(temp_zip, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f"ZIP integrity failure at {bad}")
            if len(archive.infolist()) > 20:
                raise RuntimeError("Export20 entry limit exceeded")
        os.replace(temp_zip, final_zip)
        temp_zip = None
        digest = sha256_file(final_zip)
        sidecar = final_zip.with_suffix(final_zip.suffix + ".sha256.txt")
        sidecar.write_text(f"{digest}  {final_zip.name}\n", encoding="utf-8")
        _retention_cleanup(settings)
        return {
            "ok": True,
            "path": str(final_zip),
            "sha256": digest,
            "entry_count": len(entries),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "trigger": trigger_safe,
            "managed_file_rehash_performed": False,
        }
    except Exception as exc:
        return {
            "ok": False,
            "reason": type(exc).__name__,
            "detail": _sanitize_text(str(exc), settings)[:500],
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "managed_file_rehash_performed": False,
        }
    finally:
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except OSError:
                pass
        try:
            if lock_path.exists():
                payload = json.loads(lock_path.read_text(encoding="utf-8", errors="replace"))
                if payload.get("owner") == lock_owner:
                    lock_path.unlink(missing_ok=True)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        if process_lock_acquired:
            _EXPORT_PROCESS_LOCK.release()
        if temp_zip:
            try:
                temp_zip.unlink(missing_ok=True)
            except OSError:
                pass
        if stage:
            shutil.rmtree(stage, ignore_errors=True)
        _EXPORTING.active = False


def capture_critical(
    settings: Settings,
    exc: BaseException,
    trigger: str,
    db: Database | None = None,
    active_mode: str = "server",
    runtime_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    fingerprint = _fingerprint(exc, trigger)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    capsule_path = settings.diagnostics_dir / "capsules" / f"crash_capsule_{stamp}_{fingerprint}.json"
    trace_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)[-20:]
    capsule = {
        "schema_version": "1.0",
        "run_id": uuid.uuid4().hex,
        "version": __version__,
        "build_id": BUILD_ID,
        "trigger": _sanitize_text(trigger, settings)[:160],
        "severity": "Critical",
        "fingerprint": fingerprint,
        "occurred_at": utc_now(),
        "active_mode": active_mode,
        "exception_type": type(exc).__name__,
        "exception_message": _sanitize_text(str(exc), settings)[:1000],
        "traceback_redacted": [_sanitize_text(line, settings)[:2000] for line in trace_lines],
        "recent_log_tail_redacted": [
            _sanitize_text(line, settings)[:2000] for line in list(_LOG_BUFFER)[-120:]
        ],
        "runtime_identity": _runtime_identity_summary(settings, runtime_identity),
        "last_progress": "terminal error captured",
        "intended_recovery": "Preserve capsule, verify release identity, run doctor, then inspect Export20.",
        "export_result": None,
        "suppression_count": 0,
        "capture_elapsed_ms": None,
    }
    _atomic_json(capsule_path, capsule)

    suppression_path = settings.state_dir / "diagnostic_suppression.json"
    state: dict[str, Any] = {}
    if suppression_path.exists():
        try:
            state = json.loads(suppression_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    previous = state.get(fingerprint, {})
    now = time.time()
    if now - float(previous.get("last_export_epoch", 0)) < 600:
        count = int(previous.get("suppression_count", 0)) + 1
        state[fingerprint] = {
            "last_export_epoch": previous.get("last_export_epoch", now),
            "suppression_count": count,
        }
        _atomic_json(suppression_path, state)
        capsule["suppression_count"] = count
        capsule["export_result"] = {"ok": False, "reason": "fingerprint_cooldown_suppression"}
        capsule["capture_elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        _atomic_json(capsule_path, capsule)
        return {"capsule_path": str(capsule_path), "export": capsule["export_result"]}

    export_result = build_export20(
        settings,
        db=db,
        capsule_path=capsule_path,
        trigger=trigger,
        fingerprint=fingerprint,
        runtime_identity=runtime_identity,
    )
    state[fingerprint] = {
        "last_export_epoch": now if export_result.get("ok") else previous.get("last_export_epoch", 0),
        "suppression_count": int(previous.get("suppression_count", 0)),
    }
    _atomic_json(suppression_path, state)
    capsule["export_result"] = export_result
    capsule["capture_elapsed_ms"] = round((time.perf_counter() - started) * 1000)
    _atomic_json(capsule_path, capsule)
    return {"capsule_path": str(capsule_path), "export": export_result}


def install_exception_hooks(
    settings: Settings,
    db: Database | None = None,
    runtime_identity: dict[str, Any] | None = None,
) -> None:
    original = sys.excepthook

    def handle(exc_type, exc, tb):  # type: ignore[no-untyped-def]
        if isinstance(exc, KeyboardInterrupt):
            original(exc_type, exc, tb)
            return
        try:
            capture_critical(
                settings,
                exc,
                "uncaught_fatal_exception",
                db=db,
                runtime_identity=runtime_identity,
            )
        finally:
            original(exc_type, exc, tb)

    sys.excepthook = handle

    if hasattr(threading, "excepthook"):
        original_thread = threading.excepthook

        def handle_thread(args):  # type: ignore[no-untyped-def]
            try:
                if not isinstance(args.exc_value, KeyboardInterrupt):
                    capture_critical(
                        settings,
                        args.exc_value,
                        "uncaught_thread_exception",
                        db=db,
                        runtime_identity=runtime_identity,
                    )
            finally:
                original_thread(args)

        threading.excepthook = handle_thread
