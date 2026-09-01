from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.config import PROJECT_ROOT
from app.integrity import _manifest_path_error, sha256_file, verify_release


def _copy_release(target: Path) -> None:
    shutil.copytree(
        PROJECT_ROOT,
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


def _rewrite_manifest_sidecar(root: Path, manifest: dict) -> None:
    path = root / "MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    digest = sha256_file(path)
    (root / "MANIFEST.sha256").write_text(f"{digest}  MANIFEST.json\n", encoding="utf-8")


def test_release_integrity_manifest_matches_package() -> None:
    result = verify_release(PROJECT_ROOT, strict=False)
    assert result.ok, result.errors
    assert result.managed_files == result.verified_files


def test_release_integrity_accepts_legacy_root_env_without_reading_it(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    (target / ".env").write_bytes(b"UNSUPPORTED_SECRET_SETTING=not-a-real-key\xff\xfe\n")
    result = verify_release(target, strict=False)
    assert result.ok, result.errors


def test_env_prefixed_executable_is_not_treated_as_mutable_config(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    (target / ".env.py").write_text("VALUE = 1\n", encoding="utf-8")
    result = verify_release(target, strict=False)
    assert result.ok is False
    assert any("Unlisted managed file present: .env.py" == error for error in result.errors)


def test_release_integrity_rejects_unlisted_managed_file(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    (target / "unlisted_module.py").write_text("VALUE = 1\n", encoding="utf-8")
    result = verify_release(target, strict=False)
    assert result.ok is False
    assert any("Unlisted managed file present" in error for error in result.errors)


def test_nested_directory_named_local_does_not_hide_unlisted_code(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    hidden = target / "app" / "local" / "unlisted_module.py"
    hidden.parent.mkdir()
    hidden.write_text("VALUE = 1\n", encoding="utf-8")
    result = verify_release(target, strict=False)
    assert result.ok is False
    assert any("app/local/unlisted_module.py" in error for error in result.errors)


def test_manifest_size_metadata_is_enforced(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    manifest = json.loads((target / "MANIFEST.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["managed_files"] if item["path"] == "README.md")
    entry["size_bytes"] += 1
    _rewrite_manifest_sidecar(target, manifest)
    result = verify_release(target, strict=False)
    assert result.ok is False
    assert any("Managed file size mismatch: README.md" == error for error in result.errors)


def test_manifest_path_rules_reject_windows_unsafe_and_case_ambiguous_forms() -> None:
    assert _manifest_path_error("app/main.py") is None
    assert _manifest_path_error("../outside.py") is not None
    assert _manifest_path_error("app\\main.py") is not None
    assert _manifest_path_error("app//main.py") is not None
    assert _manifest_path_error("CON.txt") is not None
    assert _manifest_path_error("app/bad?.py") is not None
    assert _manifest_path_error("app/trailing. ") is not None


def test_manifest_rejects_case_colliding_paths(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    manifest = json.loads((target / "MANIFEST.json").read_text(encoding="utf-8"))
    source = next(item for item in manifest["managed_files"] if item["path"] == "README.md")
    manifest["managed_files"].append({**source, "path": "readme.md"})
    manifest["managed_file_count"] = len(manifest["managed_files"])
    _rewrite_manifest_sidecar(target, manifest)
    result = verify_release(target, strict=False)
    assert result.ok is False
    assert any("Case-colliding managed paths" in error for error in result.errors)


def test_unlisted_root_zip_is_not_silently_excluded(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    (target / "unexpected_payload.zip").write_bytes(b"PK\x03\x04not-a-release-asset")
    result = verify_release(target, strict=False)
    assert result.ok is False
    assert any("Unlisted managed file present: unexpected_payload.zip" == error for error in result.errors)


def test_retired_launcher_return_fails_even_when_manifested(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    returned = target / "DOCTOR.bat"
    returned.write_bytes(b"@echo off\r\nexit /b 0\r\n")
    manifest = json.loads((target / "MANIFEST.json").read_text(encoding="utf-8"))
    manifest["managed_files"].append({
        "path": "DOCTOR.bat",
        "size_bytes": returned.stat().st_size,
        "sha256": sha256_file(returned),
    })
    manifest["managed_file_count"] = len(manifest["managed_files"])
    _rewrite_manifest_sidecar(target, manifest)
    result = verify_release(target, strict=False)
    assert result.ok is False
    assert any("Retired launcher returned to active package: DOCTOR.bat" == error for error in result.errors)


def test_manifest_package_id_must_match_runtime_and_metadata(tmp_path: Path) -> None:
    target = tmp_path / "release"
    _copy_release(target)
    manifest = json.loads((target / "MANIFEST.json").read_text(encoding="utf-8"))
    manifest["package_id"] = "gateway.professional-portfolio.wrong-package"
    _rewrite_manifest_sidecar(target, manifest)
    result = verify_release(target, strict=False)
    assert result.ok is False
    assert any("Package-ID mismatch" in error for error in result.errors)
