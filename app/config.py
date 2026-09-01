from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# The portfolio demo is intentionally keyless. Only local host/port/logging
# preferences are accepted from project-local configuration files.
_LOCAL_ENV_KEYS = frozenset({"GKA_HOST", "GKA_PORT", "GKA_LOG_LEVEL"})


def _load_local_env(path: Path, allowed_keys: frozenset[str] = _LOCAL_ENV_KEYS) -> None:
    """Load only supported non-secret settings from a project-local env file.

    The caller must complete release-integrity verification first. Unknown keys
    are ignored so a local settings file cannot inject arbitrary process behavior.
    """
    if not path.is_file():
        return
    if path.is_symlink():
        raise ValueError(f"Project-local environment file cannot be a symbolic link: {path.name}")
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("Project-local environment file must remain inside the project root") from exc
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in allowed_keys or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
_ALLOWED_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _validated_host(value: str | None) -> str:
    host = (value or "127.0.0.1").strip().lower()
    if host not in _LOOPBACK_HOSTS:
        raise ValueError("This local release permits loopback-only hosting")
    return host


def _validated_port(value: str | None) -> int:
    try:
        port = int(value or "8765")
    except ValueError as exc:
        raise ValueError("GKA_PORT must be an integer between 1024 and 65535") from exc
    if not 1024 <= port <= 65535:
        raise ValueError("GKA_PORT must be between 1024 and 65535")
    return port


def _validated_log_level(value: str | None) -> str:
    level = (value or "INFO").strip().upper()
    if level not in _ALLOWED_LOG_LEVELS:
        raise ValueError(f"GKA_LOG_LEVEL must be one of: {', '.join(sorted(_ALLOWED_LOG_LEVELS))}")
    return level


@dataclass(frozen=True)
class Settings:
    root: Path
    state_dir: Path
    logs_dir: Path
    temp_dir: Path
    exports_dir: Path
    diagnostics_dir: Path
    uploads_dir: Path
    db_path: Path
    host: str
    port: int
    log_level: str
    max_upload_bytes: int = 15 * 1024 * 1024
    prompt_version: str = "policy-answer-v1.0.0"

    @property
    def provider_mode(self) -> str:
        return "local-governed-evidence"

    @property
    def keyless(self) -> bool:
        return True


def load_settings() -> Settings:
    # The caller must run release-integrity verification before this function.
    # local/.env is preferred; exact root .env remains a read-only compatibility
    # location for earlier field installs. Secret/provider keys are ignored.
    _load_local_env(PROJECT_ROOT / "local" / ".env")
    _load_local_env(PROJECT_ROOT / ".env")
    for directory in (
        PROJECT_ROOT / "state",
        PROJECT_ROOT / "logs",
        PROJECT_ROOT / "temp",
        PROJECT_ROOT / "exports",
        PROJECT_ROOT / "diagnostics",
        PROJECT_ROOT / "local" / "uploads",
        PROJECT_ROOT / "backups",
        PROJECT_ROOT / "reports",
        PROJECT_ROOT / "downloads",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    return Settings(
        root=PROJECT_ROOT,
        state_dir=PROJECT_ROOT / "state",
        logs_dir=PROJECT_ROOT / "logs",
        temp_dir=PROJECT_ROOT / "temp",
        exports_dir=PROJECT_ROOT / "exports",
        diagnostics_dir=PROJECT_ROOT / "diagnostics",
        uploads_dir=PROJECT_ROOT / "local" / "uploads",
        db_path=PROJECT_ROOT / "state" / "policy_navigator.db",
        host=_validated_host(os.getenv("GKA_HOST")),
        port=_validated_port(os.getenv("GKA_PORT")),
        log_level=_validated_log_level(os.getenv("GKA_LOG_LEVEL")),
    )


def read_json(relative_path: str) -> Any:
    return json.loads((PROJECT_ROOT / relative_path).read_text(encoding="utf-8"))
