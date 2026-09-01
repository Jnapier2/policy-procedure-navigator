from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from app import BUILD_ID, __version__
from app.integrity import launcher_registry_status, verify_release
from scripts import launcher_failure_capsule, windows_launcher


ROOT = Path(__file__).resolve().parents[1]


class _CaptureLog:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def event(self, level: str, message: str) -> None:
        self.events.append((level, message))


def _copy_release(target: Path) -> None:
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns(
            ".runtime",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            "*.pyc",
            "state",
            "logs",
            "temp",
            "exports",
            "diagnostics",
            "local",
            "reports",
            "downloads",
            "backups",
        ),
    )


def test_one_active_batch_entrypoint_and_action_registry() -> None:
    batch_files = sorted(
        path.name for path in ROOT.iterdir() if path.is_file() and path.suffix.casefold() in {".bat", ".cmd"}
    )
    assert batch_files == ["EXPORT_SUPPORT.bat", "PolicyNavigator.bat"]
    primary = (ROOT / "PolicyNavigator.bat").read_bytes()
    assert primary.decode("ascii")
    assert b"\r\n" in primary
    assert primary.count(b"\n") == primary.count(b"\r\n")
    assert b'\\"' not in primary
    assert b"pause\r\n" in primary
    assert b"scripts\\windows_launcher.py" in primary

    status = launcher_registry_status(ROOT)
    assert status["ok"], status
    assert status["active_bat_cmd_count"] == 2
    assert status["canonical_entrypoint"] == "PolicyNavigator.bat"
    assert status["approved_aliases"] == []
    assert status["action_entrypoints"] == {"EXPORT_SUPPORT.bat": "export"}
    assert set(status["actions"]) == {"start", "doctor", "evaluations", "export"}
    for retired in ("DOCTOR.bat", "RUN_EVALUATIONS.bat"):
        assert not (ROOT / retired).exists()
    export_forwarder = (ROOT / "EXPORT_SUPPORT.bat").read_bytes()
    assert export_forwarder.decode("ascii")
    assert export_forwarder.count(b"\n") == export_forwarder.count(b"\r\n")
    assert export_forwarder.count(b"PolicyNavigator.bat") == 1
    assert b'PolicyNavigator.bat\" export' in export_forwarder
    assert b"python" not in export_forwarder.lower()
    assert b'scripts\\' not in export_forwarder.lower()

def test_runtime_probe_accepts_the_exact_verified_dependency_environment() -> None:
    expected = windows_launcher._requirements_versions(ROOT / "requirements.lock.txt")
    command = [sys.executable, "-c", windows_launcher._runtime_probe_script(expected)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_server_target_uses_valid_non_secret_host_and_port_settings(monkeypatch, tmp_path) -> None:
    local = tmp_path / "local"
    local.mkdir()
    (local / ".env").write_text(
        "UNSUPPORTED_SECRET_SETTING=must-not-be-read-by-this-helper\nGKA_HOST=localhost\nGKA_PORT=9123\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(windows_launcher, "ROOT", tmp_path)
    monkeypatch.delenv("GKA_HOST", raising=False)
    monkeypatch.delenv("GKA_PORT", raising=False)
    url, host, port = windows_launcher._server_target()
    assert url == "http://127.0.0.1:9123"
    assert host == "localhost"
    assert port == 9123


def test_invalid_port_falls_back_without_mutating_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(windows_launcher, "ROOT", tmp_path)
    monkeypatch.setenv("GKA_PORT", "not-a-port")
    before = dict(os.environ)
    url, host, port = windows_launcher._server_target()
    assert url.endswith(":8765")
    assert host == "127.0.0.1"
    assert port == 8765
    assert os.environ["GKA_PORT"] == before["GKA_PORT"]


def test_server_target_accepts_legacy_root_env(monkeypatch, tmp_path) -> None:
    (tmp_path / ".env").write_text("GKA_HOST=localhost\nGKA_PORT=9124\n", encoding="utf-8")
    monkeypatch.setattr(windows_launcher, "ROOT", tmp_path)
    monkeypatch.delenv("GKA_HOST", raising=False)
    monkeypatch.delenv("GKA_PORT", raising=False)
    url, host, port = windows_launcher._server_target()
    assert url == "http://127.0.0.1:9124"
    assert host == "localhost"
    assert port == 9124


def test_server_target_prefers_local_env_over_legacy_root_env(monkeypatch, tmp_path) -> None:
    local = tmp_path / "local"
    local.mkdir()
    (local / ".env").write_text("GKA_PORT=9125\n", encoding="utf-8")
    (tmp_path / ".env").write_text("GKA_PORT=9126\n", encoding="utf-8")
    monkeypatch.setattr(windows_launcher, "ROOT", tmp_path)
    monkeypatch.delenv("GKA_HOST", raising=False)
    monkeypatch.delenv("GKA_PORT", raising=False)
    url, host, port = windows_launcher._server_target()
    assert url == "http://127.0.0.1:9125"
    assert host == "127.0.0.1"
    assert port == 9125


def test_dependency_free_fallback_identity_matches_release() -> None:
    assert launcher_failure_capsule.VERSION == __version__
    assert launcher_failure_capsule.BUILD_ID == BUILD_ID


def test_exact_legacy_forwarders_are_archived_before_integrity_gate(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    legacy = {
        "DOCTOR.bat": b'@echo off\r\ncall "%~dp0PolicyNavigator.bat" doctor\r\nexit /b %ERRORLEVEL%\r\n',
        "RUN_EVALUATIONS.bat": b'@echo off\r\ncall "%~dp0PolicyNavigator.bat" evaluations\r\nexit /b %ERRORLEVEL%\r\n',
    }
    for relative, content in legacy.items():
        (target / relative).write_bytes(content)

    log = _CaptureLog()
    repair = windows_launcher._archive_known_legacy_overlay(target, log)
    assert repair["ok"] is True
    assert repair["repaired"] is True
    assert sorted(repair["moved"]) == sorted(legacy)
    for relative, content in legacy.items():
        assert not (target / relative).exists()
        archived = Path(str(repair["backup_dir"])) / relative
        assert archived.read_bytes() == content
    assert (Path(str(repair["backup_dir"])) / "REPAIR_RECEIPT.json").is_file()
    result = verify_release(target, strict=False)
    assert result.ok, result.errors


def test_modified_legacy_launcher_is_not_moved_and_still_fails_closed(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    returned = target / "DOCTOR.bat"
    returned.write_bytes(b'@echo off\r\nrem modified unknown copy\r\nexit /b 0\r\n')
    log = _CaptureLog()
    repair = windows_launcher._archive_known_legacy_overlay(target, log)
    assert repair["ok"] is False
    assert repair["repaired"] is False
    assert returned.is_file()
    result = verify_release(target, strict=False)
    assert result.ok is False
    assert any("DOCTOR.bat" in error for error in result.errors)


def test_unknown_unlisted_file_is_never_archived_by_overlay_repair(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    unknown = target / "unknown_helper.bat"
    unknown.write_bytes(b"@echo off\r\nexit /b 0\r\n")
    log = _CaptureLog()
    repair = windows_launcher._archive_known_legacy_overlay(target, log)
    assert repair["ok"] is True
    assert repair["repaired"] is False
    assert unknown.is_file()
    result = verify_release(target, strict=False)
    assert result.ok is False
    assert any("unknown_helper.bat" in error for error in result.errors)


def test_server_target_reuses_exact_ready_build(monkeypatch) -> None:
    monkeypatch.setattr(windows_launcher, "_server_target", lambda: ("http://127.0.0.1:8765", "127.0.0.1", 8765))
    monkeypatch.setattr(
        windows_launcher,
        "_status_payload",
        lambda _url: {"status": "ready", "version": __version__, "build_id": BUILD_ID},
    )
    monkeypatch.setattr(windows_launcher, "_port_available_for_bind", lambda _host, _port: False)
    log = _CaptureLog()
    target = windows_launcher._resolve_server_target(log, {"version": __version__, "build_id": BUILD_ID})
    assert target.reused_existing is True
    assert target.fallback_used is False
    assert target.port == 8765


def test_busy_default_port_selects_bounded_free_fallback_without_stopping_process(monkeypatch) -> None:
    monkeypatch.setattr(windows_launcher, "_server_target", lambda: ("http://127.0.0.1:8765", "127.0.0.1", 8765))
    monkeypatch.setattr(windows_launcher, "_status_payload", lambda _url: None)
    monkeypatch.setattr(windows_launcher, "_port_available_for_bind", lambda _host, port: port not in {8765, 8766})
    log = _CaptureLog()
    target = windows_launcher._resolve_server_target(log, {"version": __version__, "build_id": BUILD_ID})
    assert target.reused_existing is False
    assert target.fallback_used is True
    assert target.requested_port == 8765
    assert target.port == 8767
    assert target.url == "http://127.0.0.1:8767"
    messages = "\n".join(message for _level, message in log.events)
    assert "no process was stopped" in messages.lower()
    assert "was not changed" in messages.lower()


def test_different_policy_navigator_release_on_requested_port_uses_fallback(monkeypatch) -> None:
    monkeypatch.setattr(windows_launcher, "_server_target", lambda: ("http://127.0.0.1:8765", "127.0.0.1", 8765))
    monkeypatch.setattr(
        windows_launcher,
        "_status_payload",
        lambda _url: {"status": "ready", "version": "0.1.2", "build_id": "OLD-BUILD"},
    )
    monkeypatch.setattr(windows_launcher, "_port_available_for_bind", lambda _host, port: port != 8765)
    log = _CaptureLog()
    target = windows_launcher._resolve_server_target(log, {"version": __version__, "build_id": BUILD_ID})
    assert target.fallback_used is True
    assert target.port == 8766
    assert any("0.1.2 / OLD-BUILD" in message for _level, message in log.events)


def test_port_fallback_exhaustion_fails_without_killing_any_process(monkeypatch) -> None:
    monkeypatch.setattr(windows_launcher, "_server_target", lambda: ("http://127.0.0.1:8765", "127.0.0.1", 8765))
    monkeypatch.setattr(windows_launcher, "_status_payload", lambda _url: None)
    monkeypatch.setattr(windows_launcher, "_port_available_for_bind", lambda _host, _port: False)
    log = _CaptureLog()
    try:
        windows_launcher._resolve_server_target(log, {"version": __version__, "build_id": BUILD_ID})
    except windows_launcher.LauncherFailure as exc:
        assert exc.stage == "port_fallback_exhausted"
        assert exc.exit_code == 8
        assert "No process was stopped" in str(exc)
    else:
        raise AssertionError("Expected port_fallback_exhausted")


def test_port_ownership_is_checked_before_http_reuse_probe(monkeypatch) -> None:
    events: list[str] = []
    monkeypatch.setattr(windows_launcher, "_server_target", lambda: ("http://127.0.0.1:8765", "127.0.0.1", 8765))

    def bindable(_host: str, port: int) -> bool:
        events.append(f"bind:{port}")
        return port != 8765

    def status(_url: str):
        assert events == ["bind:8765"]
        events.append("http")
        return None

    monkeypatch.setattr(windows_launcher, "_port_available_for_bind", bindable)
    monkeypatch.setattr(windows_launcher, "_status_payload", status)
    target = windows_launcher._resolve_server_target(_CaptureLog(), {"version": __version__, "build_id": BUILD_ID})
    assert target.fallback_used is True
    assert target.port == 8766
    assert events == ["bind:8765", "http", "bind:8766"]


def test_bind_probe_detects_non_http_owned_port() -> None:
    import socket

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        port = listener.getsockname()[1]
        assert windows_launcher._port_available_for_bind("127.0.0.1", port) is False
    finally:
        listener.close()


def test_browser_url_is_release_qualified_to_avoid_stale_local_ui_cache() -> None:
    base = "http://127.0.0.1:8766"
    result = windows_launcher._browser_url(base, {"version": __version__, "build_id": BUILD_ID})
    assert result.startswith(base + "/?build=")
    assert "PP-GKWA-0.3.2-B20260831-EXPORTENTRY1" in result
