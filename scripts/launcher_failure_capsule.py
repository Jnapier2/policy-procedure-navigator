from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.3.2"
BUILD_ID = "PP-GKWA-0.3.2-B20260831-EXPORTENTRY1"

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:sk|rk|pk)-(?:proj-)?[A-Za-z0-9_-]{16,}\b"), "[REDACTED_SECRET]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "[REDACTED_EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)"), "[REDACTED_PHONE]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[REDACTED_IP]"),
]


def sanitize(text: str) -> str:
    result = text
    for pattern, replacement in _PATTERNS:
        result = pattern.sub(replacement, result)
    home = str(Path.home())
    if home and home not in {"/", "."}:
        result = result.replace(home, "[REDACTED_HOME]")
    result = result.replace(str(ROOT), "[PROJECT_ROOT]")
    return result


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cached_identity() -> dict[str, Any]:
    path = ROOT / "state" / "runtime_identity_result.json"
    if not path.is_file():
        return {
            "ok": False,
            "cache_available": False,
            "managed_file_rehash_performed": False,
            "errors": ["No completed runtime-identity result was cached."],
        }
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("cache root is not an object")
        value["cache_available"] = True
        value["managed_file_rehash_performed"] = False
        return value
    except Exception as exc:
        return {
            "ok": False,
            "cache_available": False,
            "managed_file_rehash_performed": False,
            "errors": [f"Runtime-identity cache read failed: {type(exc).__name__}"],
        }


def create_fallback_export(capsule_path: Path, trigger: str, fingerprint: str) -> dict[str, Any]:
    started = time.perf_counter()
    state_dir = ROOT / "state"
    temp_dir = ROOT / "temp"
    exports_dir = ROOT / "exports"
    state_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)
    lock_path = state_dir / "diagnostic_export.lock"
    lock_fd: int | None = None
    stage: Path | None = None
    temp_zip: Path | None = None
    try:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, f"{os.getpid()} fallback".encode("utf-8"))
        except FileExistsError:
            if time.time() - lock_path.stat().st_mtime <= 180:
                return {"ok": False, "reason": "exporter_already_active"}
            lock_path.unlink(missing_ok=True)
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, f"{os.getpid()} fallback_recovered_stale_lock".encode("utf-8"))

        run_id = uuid.uuid4().hex[:12]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stage = temp_dir / f"launcher_export20_{run_id}"
        stage.mkdir(parents=True)
        shutil.copy2(capsule_path, stage / "01_CRASH_CAPSULE_REDACTED.json")
        atomic_json(
            stage / "02_RUNTIME_IDENTITY_RESULT.json",
            cached_identity(),
        )
        atomic_json(
            stage / "03_TRANSFER_SUMMARY.json",
            {
                "canonical_project": "Professional Portfolio — Governed AI Knowledge & Workflow Assistant",
                "display_name": "Policy and Procedure Navigator",
                "version": VERSION,
                "build_id": BUILD_ID,
                "canonical_entrypoint": "PolicyNavigator.bat",
                "trigger": sanitize(trigger)[:160],
                "fingerprint": fingerprint,
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "collector": "stdlib launcher fallback",
                "managed_file_rehash_performed": False,
                "network_actions": False,
                "copyright": "Copyright © 2026 Gateway Information Group LLC. All rights reserved.",
            },
        )
        atomic_text(
            stage / "04_RECOVERY_NOTES.txt",
            "Preserve this archive and sidecar. Run PolicyNavigator.bat doctor when dependencies are available.\n"
            "Do not edit VERSION.txt, MANIFEST.json, MANIFEST.sha256, or PACKAGE_METADATA.json to force a pass.\n"
            "Restore the exact unmodified release if managed-file identity fails.\n",
        )
        static = [
            ("05_VERSION.txt", ROOT / "VERSION.txt"),
            ("06_PACKAGE_METADATA.json", ROOT / "PACKAGE_METADATA.json"),
            ("07_MANIFEST.json", ROOT / "MANIFEST.json"),
            ("08_MANIFEST.sha256", ROOT / "MANIFEST.sha256"),
            ("09_QUICK_START.md", ROOT / "QUICK_START.md"),
            ("10_KNOWN_GOOD_STATE.md", ROOT / "KNOWN_GOOD_STATE.md"),
            ("11_RELEASE_GUIDE.md", ROOT / "RELEASE_GUIDE.md"),
            ("12_FIELD_REPAIR_REPORT.md", ROOT / "FIELD_REPAIR_REPORT.md"),
        ]
        for name, source in static:
            if source.is_file() and source.stat().st_size <= 2 * 1024 * 1024:
                shutil.copy2(source, stage / name)

        entries = sorted(path for path in stage.iterdir() if path.is_file())[:20]
        temp_zip = temp_dir / f"PolicyNavigator_EXPORT20_{stamp}_{fingerprint}.zip.tmp"
        final_zip = exports_dir / f"PolicyNavigator_EXPORT20_{stamp}_{fingerprint}.zip"
        with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for entry in entries:
                archive.write(entry, arcname=entry.name)
        with zipfile.ZipFile(temp_zip, "r") as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f"ZIP integrity failure at {bad}")
            if len(archive.infolist()) > 20:
                raise RuntimeError("Export20 entry limit exceeded")
        os.replace(temp_zip, final_zip)
        temp_zip = None
        digest = sha256_file(final_zip)
        atomic_text(final_zip.with_suffix(final_zip.suffix + ".sha256.txt"), f"{digest}  {final_zip.name}\n")
        return {
            "ok": True,
            "path": str(final_zip),
            "sha256": digest,
            "entry_count": len(entries),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "managed_file_rehash_performed": False,
        }
    except Exception as exc:
        return {
            "ok": False,
            "reason": type(exc).__name__,
            "detail": sanitize(str(exc))[:500],
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "managed_file_rehash_performed": False,
        }
    finally:
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except OSError:
                pass
        lock_path.unlink(missing_ok=True)
        if temp_zip:
            temp_zip.unlink(missing_ok=True)
        if stage:
            shutil.rmtree(stage, ignore_errors=True)


def create_launcher_failure(trigger: str, message: str) -> dict[str, Any]:
    sanitized_message = sanitize(message)[:1000]
    fingerprint = hashlib.sha256(f"{trigger}|{sanitized_message}|{VERSION}|{BUILD_ID}".encode()).hexdigest()[:20]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = ROOT / "diagnostics" / "capsules" / f"launcher_capsule_{stamp}_{fingerprint}.json"
    capsule = {
        "schema_version": "1.0",
        "run_id": uuid.uuid4().hex,
        "version": VERSION,
        "build_id": BUILD_ID,
        "trigger": sanitize(trigger)[:160],
        "severity": "Critical",
        "fingerprint": fingerprint,
        "occurred_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "message": sanitized_message,
        "python": sys.version.split()[0],
        "platform": platform.system(),
        "project_root_name": ROOT.name,
        "cwd_is_project_root": Path.cwd().resolve() == ROOT.resolve(),
        "runtime_identity": cached_identity(),
        "intended_recovery": "Preserve this capsule and Export20. Restore the unmodified release or run PolicyNavigator.bat doctor when available.",
        "export_result": None,
    }
    atomic_json(path, capsule)
    export_result = create_fallback_export(path, trigger, fingerprint)
    capsule["export_result"] = export_result
    atomic_json(path, capsule)
    return {"capsule_path": str(path), "export": export_result}


def safe_create_launcher_failure(trigger: str, message: str) -> dict[str, Any]:
    try:
        result = create_launcher_failure(trigger, message)
        return {"ok": True, "collector": "stdlib_launcher_fallback", **result}
    except Exception as exc:
        return {
            "ok": False,
            "collector": "stdlib_launcher_fallback",
            "reason": type(exc).__name__,
            "detail": sanitize(str(exc))[:500],
        }


def main() -> int:
    trigger = sys.argv[1] if len(sys.argv) > 1 else "launcher_failure"
    message = sys.argv[2] if len(sys.argv) > 2 else "Launcher reported a critical failure."
    result = safe_create_launcher_failure(trigger, message)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
