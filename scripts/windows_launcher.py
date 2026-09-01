from __future__ import annotations

"""Windows-first launcher orchestration for Policy and Procedure Navigator.

This module intentionally uses only the Python standard library. It performs the
release-integrity gate before loading supported local application settings.
bearing local environment file, then creates/repairs the project-local runtime,
installs the locked dependency set, and dispatches the requested operation.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / ".runtime"
VENV_DIR = RUNTIME_DIR / "venv"
REQUIREMENTS = ROOT / "requirements.lock.txt"
REQUIREMENTS_MARKER = RUNTIME_DIR / "requirements.sha256"
LOGS_DIR = ROOT / "logs"
STATE_DIR = ROOT / "state"
DIAGNOSTICS_DIR = ROOT / "diagnostics"
LATEST_LOG = LOGS_DIR / "launcher_latest.log"
LATEST_STATUS = LOGS_DIR / "LATEST_LAUNCH_STATUS.txt"
PORT_FALLBACK_ATTEMPTS = 24
RUNTIME_IMPORTS = ("fastapi", "uvicorn", "pydantic", "pypdf", "docx", "multipart")
_NONCRITICAL_OPERATIONAL_FAILURES = {"port_fallback_exhausted"}

# Exact first-party files that can survive when a newer release is extracted
# over a 0.1.x installation.  These are not aliases and are never executed by
# the current release.  The launcher may archive only these exact byte hashes
# before the normal full release-integrity gate.  Unknown or modified files are
# intentionally left in place so verify_release() fails closed.
_KNOWN_LEGACY_OVERLAY_FILES: dict[str, frozenset[tuple[int, str]]] = {
    "DOCTOR.bat": frozenset(
        {
            (73, "741997818a7078d1ec94ed2f02c3b7787cb37697836af1a3cd122634fde14064"),  # 0.1.0
            (73, "6ed38c3ddcf0b7b91ac49ad40ae99098de2f40ca5679ed6d8d82b139ba781424"),  # 0.1.1/0.1.2
        }
    ),
    "RUN_EVALUATIONS.bat": frozenset(
        {
            (78, "9c8fe1af72d1538e01dc2520ef8ef75bf21be6e0cd85eb54d1624591849a69d1"),  # 0.1.0
            (78, "b44225d1c5b25364a2a56fe47a373ebd3a26f57c64fe0d2fb8079c036752580d"),  # 0.1.1/0.1.2
        }
    ),
    "FIELD_REPAIR_REPORT.md": frozenset(
        {
            (6356, "242b9717c22c9bd04179b2cc5e1b35c350884f48bb5d0d54f6acb5ca5d6d0871"),  # 0.1.2
        }
    ),
}


class LauncherFailure(RuntimeError):
    """Expected launcher failure with a stable stage and exit code."""

    def __init__(self, stage: str, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.stage = stage
        self.exit_code = exit_code


class TeeLog:
    def __init__(self) -> None:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")
        self.path = LOGS_DIR / f"launcher_{timestamp}.log"
        self._handles = [
            self.path.open("w", encoding="utf-8", newline="\n"),
            LATEST_LOG.open("w", encoding="utf-8", newline="\n"),
        ]
        self._lock = threading.Lock()

    def write(self, text: str = "") -> None:
        rendered = text.rstrip("\r\n")
        with self._lock:
            print(rendered, flush=True)
            for handle in self._handles:
                handle.write(rendered + "\n")
                handle.flush()

    def event(self, level: str, message: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.write(f"[{level}] {stamp} {message}")

    def close(self) -> None:
        with self._lock:
            for handle in self._handles:
                try:
                    handle.flush()
                    handle.close()
                except Exception:
                    pass
            self._handles.clear()


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    lines: tuple[str, ...]


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _archive_known_legacy_overlay(root: Path, log: TeeLog) -> dict[str, object]:
    """Reversibly archive exact 0.1.x leftovers before full identity checking.

    This is deliberately narrower than general cleanup.  It acts only on
    root-level files whose size and SHA-256 exactly match immutable files from
    the preserved 0.1.x releases.  A modified candidate, symlink, directory,
    or unknown extra is never moved and will remain visible to the subsequent
    fail-closed release-integrity gate.
    """

    present: list[tuple[str, Path, int, str]] = []
    rejected: list[str] = []
    for relative, accepted in _KNOWN_LEGACY_OVERLAY_FILES.items():
        source = root / relative
        if not source.exists() and not source.is_symlink():
            continue
        if source.is_symlink() or not source.is_file():
            rejected.append(f"{relative}: not a regular non-symlink file")
            continue
        try:
            size = source.stat().st_size
            digest = _sha256(source)
        except OSError as exc:
            rejected.append(f"{relative}: could not verify ({type(exc).__name__})")
            continue
        if (size, digest) not in accepted:
            rejected.append(f"{relative}: content does not match a preserved 0.1.x release")
            continue
        present.append((relative, source, size, digest))

    if rejected:
        for item in rejected:
            log.event("WARN", f"Legacy overlay repair refused {item}")
        return {
            "ok": False,
            "repaired": False,
            "reason": "legacy_overlay_candidate_not_exact",
            "rejected": rejected,
            "moved": [],
        }
    if not present:
        return {"ok": True, "repaired": False, "reason": "no_known_legacy_overlay", "moved": []}

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f_UTC")
    backup_dir = root / "backups" / "legacy_overlay" / f"{timestamp}_{uuid.uuid4().hex[:8]}"
    moved: list[tuple[str, Path, Path, int, str]] = []
    try:
        backup_dir.mkdir(parents=True, exist_ok=False)
        for relative, source, size, digest in present:
            destination = backup_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
            moved.append((relative, source, destination, size, digest))
    except OSError as exc:
        rollback_errors: list[str] = []
        for relative, source, destination, _size, _digest in reversed(moved):
            try:
                if destination.exists() and not source.exists():
                    os.replace(destination, source)
            except OSError as rollback_exc:
                rollback_errors.append(f"{relative}: {type(rollback_exc).__name__}")
        log.event("WARN", f"Legacy overlay repair could not complete: {type(exc).__name__}: {exc}")
        return {
            "ok": False,
            "repaired": False,
            "reason": "legacy_overlay_archive_failure",
            "error_type": type(exc).__name__,
            "rollback_errors": rollback_errors,
            "moved": [],
        }

    receipt = {
        "schema_version": "1.0",
        "action": "archive_exact_known_legacy_overlay",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_family": "Policy Navigator 0.1.x preserved first-party artifacts",
        "project_root": str(root),
        "backup_dir": str(backup_dir),
        "files": [
            {
                "path": relative,
                "size_bytes": size,
                "sha256": digest,
                "archived_path": str(destination),
            }
            for relative, _source, destination, size, digest in moved
        ],
    }
    try:
        _atomic_text(backup_dir / "REPAIR_RECEIPT.json", json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
    except OSError as exc:
        # The actual files are safely preserved.  A receipt failure is logged,
        # but does not reverse a successful same-volume archival operation.
        log.event("WARN", f"Legacy overlay repair receipt could not be written: {type(exc).__name__}")

    log.event(
        "REPAIR",
        f"Archived {len(moved)} exact legacy overlay file(s) to {backup_dir}. No unknown files were changed.",
    )
    for relative, _source, _destination, _size, digest in moved:
        log.event("REPAIR", f"Archived known legacy file: {relative} sha256={digest}")
    return {
        "ok": True,
        "repaired": True,
        "reason": "exact_known_legacy_overlay_archived",
        "backup_dir": str(backup_dir),
        "moved": [relative for relative, *_rest in moved],
    }


def _runtime_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _safe_command_display(command: Sequence[str | os.PathLike[str]]) -> str:
    pieces: list[str] = []
    for value in command:
        text = os.fspath(value)
        if any(character.isspace() for character in text) or '"' in text:
            pieces.append('"' + text.replace('"', '\\"') + '"')
        else:
            pieces.append(text)
    return " ".join(pieces)


def _run_logged(
    command: Sequence[str | os.PathLike[str]],
    log: TeeLog,
    *,
    label: str,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    display_command: str | None = None,
) -> CommandResult:
    rendered = [os.fspath(part) for part in command]
    display = display_command or _safe_command_display(rendered)
    log.event("RUN", f"{label}: {display}")
    try:
        process = subprocess.Popen(
            rendered,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        log.event("ERROR", f"{label} could not start: {type(exc).__name__}: {exc}")
        return CommandResult(127, ())

    lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        clean = line.rstrip("\r\n")
        lines.append(clean)
        log.write(clean)
    returncode = process.wait()
    log.event("RESULT", f"{label} exited with code {returncode}")
    return CommandResult(returncode, tuple(lines))


def _write_status(
    *,
    ok: bool,
    stage: str,
    message: str,
    log: TeeLog,
    exit_code: int,
    diagnostic: dict[str, object] | None = None,
) -> None:
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ok": ok,
        "stage": stage,
        "message": message,
        "exit_code": exit_code,
        "project_root": str(ROOT),
        "bootstrap_python": sys.executable,
        "bootstrap_python_version": platform.python_version(),
        "platform": platform.platform(),
        "launcher_log": str(log.path),
        "latest_log": str(LATEST_LOG),
        "diagnostic": diagnostic or {},
    }
    _atomic_text(LATEST_STATUS, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def _capture_launcher_failure(stage: str, message: str, log: TeeLog) -> dict[str, object]:
    try:
        sys.path.insert(0, str(ROOT))
        from scripts.launcher_failure_capsule import safe_create_launcher_failure

        result = safe_create_launcher_failure(stage, message)
        if isinstance(result, dict):
            log.event("DIAGNOSTIC", json.dumps(result, ensure_ascii=False))
            return result
    except BaseException as exc:
        log.event("WARN", f"Failure capsule could not be created: {type(exc).__name__}")
    return {"ok": False, "reason": "launcher_failure_capsule_unavailable"}


def _verify_release(log: TeeLog) -> dict[str, object]:
    sys.path.insert(0, str(ROOT))
    from app.integrity import cache_integrity_result, verify_release

    result = verify_release(ROOT, strict=False)
    cache_integrity_result(STATE_DIR, result)
    payload = result.to_dict()
    log.event(
        "INTEGRITY",
        f"managed={payload['managed_files']} verified={payload['verified_files']} ok={payload['ok']}",
    )
    if not result.ok:
        for error in result.errors:
            log.event("ERROR", error)
        raise LauncherFailure(
            "runtime_identity_failure",
            "Release integrity verification failed before supported local settings were loaded.",
            3,
        )
    return payload


def _requirements_versions(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise LauncherFailure(
                "dependency_lock_parse_failure",
                f"Unsupported dependency lock entry: {line}",
                5,
            )
        name, version = line.split("==", 1)
        versions[name.strip().lower()] = version.strip()
    if not versions:
        raise LauncherFailure("dependency_lock_parse_failure", "The dependency lock is empty.", 5)
    return versions


def _runtime_probe_script(expected: dict[str, str]) -> str:
    encoded = json.dumps(expected, sort_keys=True)
    imports = json.dumps(RUNTIME_IMPORTS)
    return (
        "import importlib, importlib.metadata as m, json, sys; "
        f"expected=json.loads({encoded!r}); imports=json.loads({imports!r}); "
        "bad=[]; "
        "[(bad.append(f'{n}={m.version(n)} expected {v}') if m.version(n)!=v else None) "
        "for n,v in expected.items()]; "
        "[importlib.import_module(n) for n in imports]; "
        "print(json.dumps({'python':sys.version.split()[0],'mismatches':bad})); "
        "raise SystemExit(0 if not bad else 2)"
    )


def _runtime_is_ready(runtime_python: Path, expected: dict[str, str], log: TeeLog) -> bool:
    if not runtime_python.is_file():
        log.event("RUNTIME", "Project-local Python executable is absent.")
        return False
    result = _run_logged(
        [runtime_python, "-c", _runtime_probe_script(expected)],
        log,
        label="runtime validation",
        display_command=f'{runtime_python} -c <exact dependency version/import validation>',
    )
    return result.returncode == 0


def _archive_broken_runtime(log: TeeLog) -> None:
    if not VENV_DIR.exists():
        return
    backups = ROOT / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")
    destination = backups / f"runtime_venv_failed_{stamp}"
    try:
        VENV_DIR.replace(destination)
        log.event("RECOVERY", f"Preserved the incomplete runtime at {destination}")
    except OSError:
        shutil.rmtree(VENV_DIR, ignore_errors=True)
        log.event("RECOVERY", "Removed an unusable generated runtime after backup rename was unavailable.")


def _ensure_runtime(log: TeeLog) -> Path:
    if sys.version_info < (3, 11):
        raise LauncherFailure(
            "unsupported_bootstrap_python",
            f"Python {platform.python_version()} is too old; Python 3.11 or newer is required.",
            2,
        )
    if not REQUIREMENTS.is_file():
        raise LauncherFailure("dependency_lock_missing", "requirements.lock.txt is missing.", 5)

    expected = _requirements_versions(REQUIREMENTS)
    expected_hash = _sha256(REQUIREMENTS)
    runtime_python = _runtime_python()
    installed_hash = ""
    if REQUIREMENTS_MARKER.is_file():
        installed_hash = REQUIREMENTS_MARKER.read_text(encoding="utf-8", errors="replace").strip().lower()

    if installed_hash == expected_hash and _runtime_is_ready(runtime_python, expected, log):
        log.event("RUNTIME", "Existing project-local runtime matches the locked dependency set.")
        return runtime_python

    if VENV_DIR.exists() and not runtime_python.is_file():
        _archive_broken_runtime(log)
    elif runtime_python.is_file():
        log.event("SETUP", "The existing runtime is incomplete or stale; dependency repair will run in place.")

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if not runtime_python.is_file():
        log.event("SETUP", f"Creating project-local runtime with {sys.executable}")
        result = _run_logged(
            [sys.executable, "-m", "venv", VENV_DIR],
            log,
            label="virtual environment creation",
        )
        if result.returncode != 0 or not runtime_python.is_file():
            _archive_broken_runtime(log)
            raise LauncherFailure(
                "runtime_creation_failure",
                "The project-local Python runtime could not be created. Review launcher_latest.log for the exact Python error.",
                4,
            )

    pip_check = _run_logged(
        [runtime_python, "-m", "pip", "--version"],
        log,
        label="pip availability check",
    )
    if pip_check.returncode != 0:
        ensurepip = _run_logged(
            [runtime_python, "-m", "ensurepip", "--upgrade"],
            log,
            label="pip repair",
        )
        if ensurepip.returncode != 0:
            raise LauncherFailure(
                "pip_bootstrap_failure",
                "The local runtime was created, but pip could not be initialized.",
                5,
            )

    log.event("SETUP", "Installing the exact locked dependency set. First launch may require internet access.")
    install = _run_logged(
        [
            runtime_python,
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-input",
            "--prefer-binary",
            "--retries",
            "3",
            "--timeout",
            "30",
            "-r",
            REQUIREMENTS,
        ],
        log,
        label="locked dependency installation",
    )
    if install.returncode != 0:
        raise LauncherFailure(
            "dependency_install_failure",
            "Locked dependency installation failed. The full pip error is preserved in logs\\launcher_latest.log.",
            5,
        )

    if not _runtime_is_ready(runtime_python, expected, log):
        raise LauncherFailure(
            "dependency_validation_failure",
            "Dependency installation completed, but the installed versions or imports did not validate.",
            5,
        )

    _atomic_text(REQUIREMENTS_MARKER, expected_hash + "\n")
    log.event("SETUP", "Project-local runtime installation and validation completed.")
    return runtime_python


def _run_utility(runtime_python: Path, relative_script: str, log: TeeLog, label: str) -> int:
    result = _run_logged([runtime_python, ROOT / relative_script], log, label=label)
    if result.returncode != 0:
        raise LauncherFailure(
            f"{label.lower().replace(' ', '_')}_failure",
            f"{label} stopped with exit code {result.returncode}.",
            result.returncode if 1 <= result.returncode <= 125 else 70,
        )
    return 0


def _status_payload(url: str, timeout: float = 1.0) -> dict[str, object] | None:
    # Newer releases expose /api/health/ready. Older Policy Navigator builds
    # may expose only /api/status, so probe that as a compatibility fallback.
    # This is intentionally read-only and loopback-only; it does not stop or
    # mutate the process currently holding the port.
    for suffix in ("/api/health/ready", "/api/status"):
        try:
            with urllib.request.urlopen(url.rstrip("/") + suffix, timeout=timeout) as response:
                if response.status != 200:
                    continue
                value = json.loads(response.read().decode("utf-8"))
                if isinstance(value, dict):
                    return value
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            continue
    return None


def _port_available_for_bind(host: str, port: int) -> bool:
    """Return True only when this process can bind the requested loopback port.

    Binding is a stronger availability test than connecting: a non-HTTP listener
    with a saturated accept queue can make a connect probe time out or fail even
    though the port is still owned. The probe never listens, accepts, terminates,
    or mutates the occupying process.
    """
    bind_host = "127.0.0.1" if host == "localhost" else host
    family = socket.AF_INET6 if ":" in bind_host else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as probe:
            # On Windows, request exclusive ownership for the availability probe
            # when the platform exposes SO_EXCLUSIVEADDRUSE. Do not enable
            # SO_REUSEADDR; successful bind must mean the launcher can own it.
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                try:
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                except OSError:
                    pass
            probe.bind((bind_host, port))
            return True
    except OSError:
        return False


def _url_for_target(host: str, port: int) -> str:
    if host == "::1":
        browser_host = "[::1]"
    elif host == "localhost":
        browser_host = "127.0.0.1"
    else:
        browser_host = host
    return f"http://{browser_host}:{port}"


def _browser_url(base_url: str, expected_identity: dict[str, object]) -> str:
    """Return a release-qualified UI URL so stale browser documents cannot mask an upgrade."""
    build = str(expected_identity.get("build_id") or expected_identity.get("version") or "current")
    query = urllib.parse.urlencode({"build": build})
    return f"{base_url.rstrip('/')}/?{query}"


def _first_available_fallback_port(host: str, requested_port: int, attempts: int = PORT_FALLBACK_ATTEMPTS) -> int | None:
    """Return a nearby free loopback port without touching the occupying process."""

    checked: set[int] = {requested_port}
    for offset in range(1, max(1, attempts) + 1):
        candidate = requested_port + offset
        if candidate > 65535:
            candidate = 1024 + (candidate - 65536)
        if candidate in checked or not 1024 <= candidate <= 65535:
            continue
        checked.add(candidate)
        if _port_available_for_bind(host, candidate):
            return candidate
    return None


@dataclass(frozen=True)
class ResolvedServerTarget:
    url: str
    host: str
    port: int
    requested_port: int
    reused_existing: bool
    fallback_used: bool


def _resolve_server_target(log: TeeLog, expected_identity: dict[str, object]) -> ResolvedServerTarget:
    requested_url, host, requested_port = _server_target()

    # Determine ownership before making any HTTP request. A connect-first probe
    # can be fooled by a non-HTTP listener whose accept queue is saturated.
    if _port_available_for_bind(host, requested_port):
        return ResolvedServerTarget(
            requested_url,
            host,
            requested_port,
            requested_port,
            False,
            False,
        )

    # The port is definitely unavailable to this process. Only now perform the
    # read-only HTTP probe that can identify an already-running exact build.
    existing = _status_payload(requested_url)
    if existing and existing.get("status") == "ready":
        same_version = existing.get("version") == expected_identity.get("version")
        same_build = existing.get("build_id") == expected_identity.get("build_id")
        if same_version and same_build:
            log.event("READY", f"This exact build is already responding at {requested_url}")
            return ResolvedServerTarget(
                requested_url,
                host,
                requested_port,
                requested_port,
                True,
                False,
            )

    alternate = _first_available_fallback_port(host, requested_port)
    if alternate is None:
        raise LauncherFailure(
            "port_fallback_exhausted",
            f"Port {requested_port} and the next {PORT_FALLBACK_ATTEMPTS} local fallback ports are in use. No process was stopped.",
            8,
        )

    if existing:
        version = str(existing.get("version") or "unknown")
        build = str(existing.get("build_id") or "unknown")
        log.event(
            "PORT",
            f"Requested port {requested_port} is occupied by another Policy Navigator response ({version} / {build}). Selected {alternate} for this run; no process was stopped.",
        )
    else:
        log.event(
            "PORT",
            f"Requested port {requested_port} is occupied by another process. Selected {alternate} for this run; no process was stopped.",
        )
    log.event(
        "PORT",
        "The fallback is process-local only; GKA_PORT in local\\.env or the legacy root .env was not changed.",
    )
    return ResolvedServerTarget(
        _url_for_target(host, alternate),
        host,
        alternate,
        requested_port,
        False,
        True,
    )


def _stream_server(process: subprocess.Popen[str], log: TeeLog) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        log.write(line.rstrip("\r\n"))


def _server_target() -> tuple[str, str, int]:
    """Read only non-secret host/port settings after integrity verification."""
    values: dict[str, str] = {}
    # Preferred local path first. Root .env remains a compatibility fallback for
    # earlier field installations; overlapping values from local\\.env win.
    for env_path in (ROOT / "local" / ".env", ROOT / ".env"):
        if not env_path.is_file():
            continue
        try:
            for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                if key in {"GKA_HOST", "GKA_PORT"} and key not in values:
                    values[key] = value.strip().strip('"').strip("'")
        except OSError:
            pass
    configured_host = os.getenv("GKA_HOST") or values.get("GKA_HOST") or "127.0.0.1"
    host = configured_host.strip().lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        host = "127.0.0.1"
    raw_port = os.getenv("GKA_PORT") or values.get("GKA_PORT") or "8765"
    try:
        port = int(raw_port)
    except ValueError:
        port = 8765
    if not 1024 <= port <= 65535:
        port = 8765
    return _url_for_target(host, port), host, port


def _start_server(
    runtime_python: Path,
    log: TeeLog,
    *,
    open_browser: bool,
    expected_identity: dict[str, object],
) -> int:
    target = _resolve_server_target(log, expected_identity)
    url, host, port = target.url, target.host, target.port
    browser_url = _browser_url(url, expected_identity)
    if target.reused_existing:
        if open_browser:
            try:
                opened = webbrowser.open(browser_url, new=2)
                if not opened:
                    log.event("WARN", f"The default browser did not open automatically. Open {browser_url} manually.")
            except Exception as exc:
                log.event("WARN", f"Browser open failed ({type(exc).__name__}). Open {browser_url} manually.")
        return 0

    command = [runtime_python, ROOT / "scripts" / "run_server.py"]
    log.event("RUN", f"local server: {_safe_command_display(command)}")
    server_env = os.environ.copy()
    # The chosen target is an ephemeral launcher decision. Environment
    # overrides ensure app.config sees the same host/port without modifying the
    # user's project-local configuration file.
    server_env["GKA_HOST"] = host
    server_env["GKA_PORT"] = str(port)
    try:
        process = subprocess.Popen(
            [os.fspath(part) for part in command],
            cwd=str(ROOT),
            env=server_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        raise LauncherFailure(
            "server_process_creation_failure",
            f"The local server process could not be created: {type(exc).__name__}.",
            70,
        ) from exc

    output_thread = threading.Thread(target=_stream_server, args=(process, log), daemon=True)
    output_thread.start()
    deadline = time.monotonic() + 60.0
    ready = False
    try:
        while time.monotonic() < deadline:
            code = process.poll()
            if code is not None:
                output_thread.join(timeout=2)
                raise LauncherFailure(
                    "server_startup_failure",
                    f"The local server exited during startup with code {code}.",
                    code if 1 <= code <= 125 else 70,
                )
            status = _status_payload(url, timeout=0.75)
            if status and status.get("status") == "ready":
                ready = True
                break
            time.sleep(0.35)
    except KeyboardInterrupt:
        log.event("STOP", "Stop requested while the local server was starting.")
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        output_thread.join(timeout=2)
        return 0

    if not ready:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
        raise LauncherFailure(
            "server_readiness_timeout",
            f"The server did not report ready at {url} within 60 seconds.",
            9,
        )

    log.event("READY", f"Policy and Procedure Navigator is available at {browser_url}")
    _write_status(
        ok=True,
        stage="server_ready",
        message=f"Policy and Procedure Navigator is ready at {browser_url}",
        log=log,
        exit_code=0,
        diagnostic={
            "integrity": expected_identity,
            "server": {
                "url": url,
                "browser_url": browser_url,
                "requested_port": target.requested_port,
                "selected_port": target.port,
                "fallback_used": target.fallback_used,
            },
        },
    )
    log.write("[INFO] Keep this window open. Press Ctrl+C once to stop the local server.")
    if open_browser:
        try:
            opened = webbrowser.open(browser_url, new=2)
            if not opened:
                log.event("WARN", f"The default browser did not open automatically. Open {browser_url} manually.")
        except Exception as exc:
            log.event("WARN", f"Browser open failed ({type(exc).__name__}). Open {browser_url} manually.")

    stopped_by_user = False
    try:
        returncode = process.wait()
    except KeyboardInterrupt:
        stopped_by_user = True
        log.event("STOP", "Stop requested from the launcher console.")
        process.terminate()
        try:
            returncode = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait(timeout=5)
    finally:
        output_thread.join(timeout=2)

    if stopped_by_user:
        log.event("STOP", "Local server stopped normally after the user request.")
        return 0
    if returncode not in (0, -15):
        raise LauncherFailure(
            "server_runtime_failure",
            f"The local server exited unexpectedly with code {returncode}.",
            returncode if 1 <= returncode <= 125 else 70,
        )
    log.event("STOP", "Local server stopped normally.")
    return 0


def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Policy Navigator Windows launcher")
    parser.add_argument(
        "mode",
        nargs="?",
        default="start",
        choices=("start", "doctor", "evaluations", "export"),
    )
    parser.add_argument("--no-browser", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)
    log = TeeLog()
    integrity: dict[str, object] | None = None
    overlay_repair: dict[str, object] = {
        "ok": True,
        "repaired": False,
        "reason": "not_run",
        "moved": [],
    }
    log.write("=" * 68)
    log.write("Policy and Procedure Navigator - governed Windows launcher")
    log.write("=" * 68)
    log.event("ROOT", str(ROOT))
    log.event("PYTHON", f"{sys.executable} ({platform.python_version()})")
    if len(str(ROOT)) > 150:
        log.event(
            "WARN",
            "The extraction path is unusually long. A short location such as C:\\Portfolio\\PolicyNavigator is recommended if pip reports a path error.",
        )
    if "v0.1." in ROOT.name.casefold():
        log.event(
            "INFO",
            "The folder name contains an older release label. Folder names do not control runtime identity; VERSION/MANIFEST/PACKAGE_METADATA do.",
        )

    try:
        overlay_repair = _archive_known_legacy_overlay(ROOT, log)
        integrity = _verify_release(log)
        legacy_env = ROOT / ".env"
        if legacy_env.is_file():
            preferred_env = ROOT / "local" / ".env"
            if preferred_env.is_file():
                log.event(
                    "CONFIG",
                    "Legacy root .env detected. local\\.env has precedence; no credential values were printed or moved.",
                )
            else:
                log.event(
                    "CONFIG",
                    "Legacy root .env detected and accepted for v0.1.0/v0.1.1 compatibility. local\\.env is preferred for future configuration.",
                )
        runtime_python = _ensure_runtime(log)
        if args.mode == "doctor":
            exit_code = _run_utility(runtime_python, "scripts/doctor.py", log, "Doctor")
        elif args.mode == "evaluations":
            exit_code = _run_utility(runtime_python, "scripts/run_evaluations.py", log, "Evaluations")
        elif args.mode == "export":
            exit_code = _run_utility(runtime_python, "scripts/export20.py", log, "Support export")
        else:
            _run_utility(runtime_python, "scripts/bootstrap.py", log, "Database bootstrap")
            exit_code = _start_server(
                runtime_python,
                log,
                open_browser=not args.no_browser,
                expected_identity=integrity,
            )
        _write_status(
            ok=True,
            stage=args.mode,
            message="Operation completed successfully.",
            log=log,
            exit_code=exit_code,
            diagnostic={"integrity": integrity or {}, "legacy_overlay_repair": overlay_repair},
        )
        return exit_code
    except KeyboardInterrupt:
        log.event("STOP", "Launcher stop requested before an operation completed.")
        _write_status(
            ok=True,
            stage="user_stop",
            message="The launcher was stopped by the user.",
            log=log,
            exit_code=0,
            diagnostic={"integrity": integrity or {}, "legacy_overlay_repair": overlay_repair},
        )
        return 0
    except LauncherFailure as exc:
        log.event("ERROR", f"{exc.stage}: {exc}")
        if exc.stage in _NONCRITICAL_OPERATIONAL_FAILURES:
            failure_diagnostic = {
                "ok": True,
                "created": False,
                "reason": "noncritical_operational_failure",
            }
            log.event("INFO", "No Critical crash capsule/Export20 was created for this recoverable operational condition.")
        else:
            failure_diagnostic = _capture_launcher_failure(exc.stage, str(exc), log)
        diagnostic = {
            "failure": failure_diagnostic,
            "legacy_overlay_repair": overlay_repair,
        }
        _write_status(
            ok=False,
            stage=exc.stage,
            message=str(exc),
            log=log,
            exit_code=exc.exit_code,
            diagnostic=diagnostic,
        )
        log.write("")
        log.write(f"[RECOVERY] Full launcher log: {LATEST_LOG}")
        log.write(f"[RECOVERY] Status summary: {LATEST_STATUS}")
        return exc.exit_code
    except BaseException as exc:
        stage = "unhandled_launcher_failure"
        message = f"Unexpected launcher failure: {type(exc).__name__}: {exc}"
        log.event("ERROR", message)
        failure_diagnostic = _capture_launcher_failure(stage, message, log)
        diagnostic = {
            "failure": failure_diagnostic,
            "legacy_overlay_repair": overlay_repair,
        }
        _write_status(
            ok=False,
            stage=stage,
            message=message,
            log=log,
            exit_code=70,
            diagnostic=diagnostic,
        )
        log.write(f"[RECOVERY] Full launcher log: {LATEST_LOG}")
        return 70
    finally:
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
