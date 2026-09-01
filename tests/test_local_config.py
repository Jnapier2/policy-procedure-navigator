from __future__ import annotations

from pathlib import Path

from app import config


_SUPPORTED_KEYS = ("GKA_HOST", "GKA_PORT", "GKA_LOG_LEVEL")


def _clear(monkeypatch) -> None:
    for key in (*_SUPPORTED_KEYS, "UNSUPPORTED_SECRET_SETTING", "UNSUPPORTED_PROVIDER_TOGGLE", "UNSUPPORTED_PROVIDER_MODEL", "PYTHONPATH", "HTTP_PROXY"):
        monkeypatch.delenv(key, raising=False)


def test_local_env_loader_ignores_unknown_and_secret_keys(monkeypatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "GKA_PORT=9123\nPYTHONPATH=malicious-path\nHTTP_PROXY=http://example.invalid\nUNSUPPORTED_SECRET_SETTING=ignored-demo-secret\n",
        encoding="utf-8",
    )
    config._load_local_env(env_file)
    assert config.os.environ["GKA_PORT"] == "9123"
    assert "PYTHONPATH" not in config.os.environ
    assert "HTTP_PROXY" not in config.os.environ
    assert "UNSUPPORTED_SECRET_SETTING" not in config.os.environ


def test_legacy_root_env_is_supported_but_provider_keys_are_ignored(monkeypatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    (tmp_path / ".env").write_text(
        "GKA_PORT=9124\nUNSUPPORTED_PROVIDER_TOGGLE=true\nUNSUPPORTED_SECRET_SETTING=ignored-demo-secret\n",
        encoding="utf-8",
    )
    settings = config.load_settings()
    assert settings.port == 9124
    assert settings.keyless is True
    assert settings.provider_mode == "local-governed-evidence"
    assert "UNSUPPORTED_SECRET_SETTING" not in config.os.environ


def test_preferred_local_env_wins_over_legacy_root_env(monkeypatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    (tmp_path / "local").mkdir()
    (tmp_path / "local" / ".env").write_text("GKA_PORT=9125\n", encoding="utf-8")
    (tmp_path / ".env").write_text("GKA_PORT=9126\n", encoding="utf-8")
    settings = config.load_settings()
    assert settings.port == 9125


def test_env_loader_rejects_symlink_escape(monkeypatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    outside = tmp_path.parent / "outside-policy-navigator.env"
    outside.write_text("GKA_PORT=9127\n", encoding="utf-8")
    link = tmp_path / ".env"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        import pytest
        pytest.skip("Symbolic links are unavailable in this test environment")
    import pytest
    with pytest.raises(ValueError, match="symbolic link"):
        config._load_local_env(link)
