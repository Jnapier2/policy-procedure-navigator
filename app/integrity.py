from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from . import BUILD_ID, PACKAGE_ID, __version__


@dataclass
class IntegrityResult:
    ok: bool
    version: str
    build_id: str
    managed_files: int
    verified_files: int
    errors: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MUTABLE_TOP_LEVEL_DIRS = {
    ".git",
    ".runtime",
    ".venv",
    "local",
    "logs",
    "state",
    "temp",
    "exports",
    "diagnostics",
    "reports",
    "downloads",
    "backups",
}
_CACHE_DIR_NAMES = {".pytest_cache"}
_OS_METADATA_NAMES = {".ds_store", "desktop.ini", "thumbs.db"}
_RELEASE_CONTROL_NAMES = {"MANIFEST.json", "MANIFEST.sha256"}
_WINDOWS_INVALID_CHARS = frozenset('<>"|?*')
_WINDOWS_RESERVED_STEMS = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_sidecar(sidecar: Path) -> str:
    text = sidecar.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("MANIFEST.sha256 is empty")
    digest = text.split()[0].lower()
    if not _HEX_SHA256.fullmatch(digest):
        raise ValueError("MANIFEST.sha256 does not begin with a valid SHA-256 digest")
    return digest


def _manifest_path_error(raw: object) -> str | None:
    if not isinstance(raw, str) or not raw:
        return "path must be a non-empty string"
    if "\\" in raw:
        return "backslashes are not permitted; manifest paths must use forward slashes"
    if any(ord(character) < 32 for character in raw):
        return "control characters are not permitted"

    posix = PurePosixPath(raw)
    canonical = posix.as_posix()
    if posix.is_absolute():
        return "absolute paths are not permitted"
    if canonical != raw:
        return "path is not in canonical relative POSIX form"
    if any(part in {"", ".", ".."} for part in posix.parts):
        return "empty, current-directory, and parent-directory components are not permitted"

    for part in posix.parts:
        if part.endswith((" ", ".")):
            return "Windows-ambiguous trailing spaces or periods are not permitted"
        if ":" in part:
            return "colons are not permitted in Windows release paths"
        if any(character in _WINDOWS_INVALID_CHARS for character in part):
            return "Windows-invalid path characters are not permitted"
        stem = part.split(".", 1)[0].casefold()
        if stem in _WINDOWS_RESERVED_STEMS:
            return f"Windows reserved name is not permitted: {part}"
    return None


def _is_legacy_root_env(rel: Path) -> bool:
    # Only the exact root .env used by the 0.1.0/0.1.1 field installation is
    # mutable compatibility configuration. Other .env.* files remain managed
    # or are rejected as unlisted so executable-looking names cannot bypass the
    # release identity gate.
    return len(rel.parts) == 1 and rel.name.casefold() == ".env"


def _is_unmanaged_runtime_file(rel: Path) -> bool:
    if not rel.parts:
        return True
    if rel.parts[0] in _MUTABLE_TOP_LEVEL_DIRS:
        return True
    if any(part in _CACHE_DIR_NAMES for part in rel.parts[:-1]):
        return True
    if rel.name.casefold() in _OS_METADATA_NAMES:
        return True
    if _is_legacy_root_env(rel):
        return True
    if rel.name in _RELEASE_CONTROL_NAMES:
        return True
    if rel.suffix.lower() == ".pyc":
        return True
    return False


def _path_contains_symlink(root: Path, candidate: Path) -> bool:
    current = root
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return True
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _launcher_registry_errors(root: Path, metadata: dict, listed_managed: set[str] | None = None) -> tuple[list[str], dict]:
    errors: list[str] = []
    registry = metadata.get("launcher_registry")
    if not isinstance(registry, dict):
        return ["PACKAGE_METADATA.json launcher_registry is missing or invalid"], {"ok": False}
    canonical = str(registry.get("canonical_entrypoint") or metadata.get("canonical_entrypoint") or "")
    aliases = registry.get("approved_aliases", [])
    retired = registry.get("retired_entrypoints", [])
    action_entrypoints = registry.get("action_entrypoints", {})
    actions = registry.get("actions", {})
    if not canonical:
        errors.append("Launcher registry canonical_entrypoint is empty")
    if not isinstance(aliases, list) or not all(isinstance(item, str) and item for item in aliases):
        errors.append("Launcher registry approved_aliases must be a list of filenames")
        aliases = []
    if not isinstance(retired, list) or not all(isinstance(item, str) and item for item in retired):
        errors.append("Launcher registry retired_entrypoints must be a list of filenames")
        retired = []
    if not isinstance(action_entrypoints, dict) or not all(
        isinstance(filename, str) and filename and isinstance(action_id, str) and action_id
        for filename, action_id in action_entrypoints.items()
    ):
        errors.append("Launcher registry action_entrypoints must map BAT/CMD filenames to action IDs")
        action_entrypoints = {}
    if not isinstance(actions, dict) or not actions:
        errors.append("Launcher registry actions must be a non-empty object")
        actions = {}

    discovered = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.casefold() in {".bat", ".cmd"}
        and not _is_unmanaged_runtime_file(path.relative_to(root))
    )
    discovered_folded: dict[str, str] = {}
    for rel in discovered:
        folded = rel.casefold()
        prior = discovered_folded.get(folded)
        if prior and prior != rel:
            errors.append(f"Case-colliding BAT/CMD entrypoints: {prior} and {rel}")
        discovered_folded[folded] = rel

    approved = (
        {canonical.casefold()}
        | {str(item).casefold() for item in aliases}
        | {str(item).casefold() for item in action_entrypoints}
    )
    for rel in discovered:
        if rel.casefold() not in approved:
            errors.append(f"Unapproved BAT/CMD entrypoint present: {rel}")
    for expected in [canonical, *aliases, *action_entrypoints]:
        if expected and expected.casefold() not in discovered_folded:
            errors.append(f"Approved BAT/CMD entrypoint missing: {expected}")
    for filename, action_id in action_entrypoints.items():
        path_error = _manifest_path_error(filename)
        if path_error or PurePosixPath(filename).parent != PurePosixPath(".") or Path(filename).suffix.casefold() not in {".bat", ".cmd"}:
            errors.append(f"Action entrypoint {filename!r} is not a safe root BAT/CMD filename")
        if action_id not in actions:
            errors.append(f"Action entrypoint {filename} references unknown action: {action_id}")
        if listed_managed is not None and filename not in listed_managed:
            errors.append(f"Action entrypoint is not managed: {filename}")
    for retired_name in retired:
        if retired_name.casefold() in discovered_folded:
            errors.append(f"Retired launcher returned to active package: {discovered_folded[retired_name.casefold()]}")

    action_status: dict[str, dict] = {}
    for action_id, spec in actions.items():
        if not isinstance(action_id, str) or not isinstance(spec, dict):
            errors.append("Launcher action registry contains a malformed action")
            continue
        backend = str(spec.get("backend", ""))
        route = str(spec.get("route", action_id))
        backend_error = _manifest_path_error(backend) if backend else "backend path is empty"
        backend_ok = not backend_error and (root / PurePosixPath(backend)).is_file()
        if backend_error:
            errors.append(f"Launcher action {action_id} has invalid backend: {backend_error}")
        elif not backend_ok:
            errors.append(f"Launcher action {action_id} backend is missing: {backend}")
        if listed_managed is not None and backend and backend not in listed_managed:
            errors.append(f"Launcher action {action_id} backend is not managed: {backend}")
        action_status[action_id] = {"route": route, "backend": backend, "backend_ok": backend_ok}

    status = {
        "ok": not errors,
        "canonical_entrypoint": canonical,
        "approved_aliases": aliases,
        "retired_entrypoints": retired,
        "action_entrypoints": action_entrypoints,
        "discovered_bat_cmd": discovered,
        "active_bat_cmd_count": len(discovered),
        "actions": action_status,
        "errors": list(errors),
    }
    return errors, status


def launcher_registry_status(root: Path) -> dict:
    root = root.resolve()
    try:
        metadata = json.loads((root / "PACKAGE_METADATA.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
        listed = {str(item.get("path")) for item in manifest.get("managed_files", []) if isinstance(item, dict)}
        _, status = _launcher_registry_errors(root, metadata, listed)
        return status
    except Exception as exc:
        return {"ok": False, "errors": [f"Launcher registry could not be checked: {type(exc).__name__}"]}


def verify_release(root: Path, strict: bool = True) -> IntegrityResult:
    errors: list[str] = []
    root = root.resolve()
    version_path = root / "VERSION.txt"
    metadata_path = root / "PACKAGE_METADATA.json"
    manifest_path = root / "MANIFEST.json"
    sidecar_path = root / "MANIFEST.sha256"

    required = (version_path, metadata_path, manifest_path, sidecar_path)
    for path in required:
        if not path.is_file():
            errors.append(f"Missing required release-control file: {path.name}")

    if errors:
        return IntegrityResult(False, __version__, BUILD_ID, 0, 0, errors)

    try:
        version_text = version_path.read_text(encoding="utf-8").strip()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return IntegrityResult(False, __version__, BUILD_ID, 0, 0, [f"Release-control parse failure: {exc}"])

    try:
        expected_manifest_hash = _load_sidecar(sidecar_path)
    except Exception as exc:
        expected_manifest_hash = ""
        errors.append(f"MANIFEST.sha256 parse failure: {exc}")
    actual_manifest_hash = sha256_file(manifest_path)
    if expected_manifest_hash and expected_manifest_hash != actual_manifest_hash:
        errors.append("MANIFEST.json hash does not match MANIFEST.sha256")

    versions = {version_text, str(metadata.get("version", "")), str(manifest.get("version", "")), __version__}
    if len(versions) != 1:
        errors.append(f"Version mismatch across runtime and release controls: {sorted(versions)}")

    builds = {str(metadata.get("build_id", "")), str(manifest.get("build_id", "")), BUILD_ID}
    if len(builds) != 1:
        errors.append(f"Build mismatch across runtime and release controls: {sorted(builds)}")

    package_ids = {str(metadata.get("package_id", "")), str(manifest.get("package_id", "")), PACKAGE_ID}
    if "" in package_ids or len(package_ids) != 1:
        errors.append(f"Package-ID mismatch across runtime and release controls: {sorted(package_ids)}")

    entries = manifest.get("managed_files", [])
    if not isinstance(entries, list):
        errors.append("MANIFEST.json managed_files must be a list")
        entries = []
    declared_count = manifest.get("managed_file_count")
    if declared_count is not None and declared_count != len(entries):
        errors.append("MANIFEST.json managed_file_count does not match managed_files")

    seen: set[str] = set()
    seen_casefolded: dict[str, str] = {}
    verified = 0
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("MANIFEST.json managed_files entries must be objects")
            continue
        raw_rel = entry.get("path", "")
        path_error = _manifest_path_error(raw_rel)
        if path_error:
            errors.append(f"Unsafe managed path {raw_rel!r}: {path_error}")
            continue
        rel = str(raw_rel)
        folded = rel.casefold()
        if rel in seen:
            errors.append(f"Duplicate managed path: {rel}")
            continue
        if folded in seen_casefolded:
            errors.append(
                f"Case-colliding managed paths are unsafe on Windows: {seen_casefolded[folded]} and {rel}"
            )
            continue
        seen.add(rel)
        seen_casefolded[folded] = rel

        expected = str(entry.get("sha256", "")).lower()
        if not _HEX_SHA256.fullmatch(expected):
            errors.append(f"Managed file has invalid SHA-256 metadata: {rel}")
            continue
        expected_size = entry.get("size_bytes")
        if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size < 0:
            errors.append(f"Managed file has invalid size metadata: {rel}")
            continue

        candidate = root / PurePosixPath(rel)
        resolved_candidate = candidate.resolve()
        try:
            resolved_candidate.relative_to(root)
        except ValueError:
            errors.append(f"Managed path escapes project root: {rel}")
            continue
        if _path_contains_symlink(root, candidate):
            errors.append(f"Managed path contains a symbolic link: {rel}")
            continue
        if not candidate.is_file():
            errors.append(f"Managed file missing: {rel}")
            continue
        actual_size = candidate.stat().st_size
        if actual_size != expected_size:
            errors.append(f"Managed file size mismatch: {rel}")
            continue
        actual = sha256_file(candidate)
        if actual != expected:
            errors.append(f"Managed file hash mismatch: {rel}")
            continue
        verified += 1

    actual_paths = [path.relative_to(root).as_posix() for path in iter_managed_files(root)]
    actual_managed = set(actual_paths)
    listed_managed = set(seen)

    actual_casefolded: dict[str, str] = {}
    for rel in actual_paths:
        folded = rel.casefold()
        prior = actual_casefolded.get(folded)
        if prior and prior != rel:
            errors.append(f"Case-colliding package paths are unsafe on Windows: {prior} and {rel}")
        else:
            actual_casefolded[folded] = rel

    for rel in sorted(actual_managed - listed_managed):
        errors.append(f"Unlisted managed file present: {rel}")
    for rel in sorted(listed_managed - actual_managed):
        errors.append(f"Manifest entry is not an eligible managed file: {rel}")

    launcher_errors, _ = _launcher_registry_errors(root, metadata, listed_managed)
    errors.extend(launcher_errors)

    result = IntegrityResult(
        ok=not errors,
        version=version_text,
        build_id=str(metadata.get("build_id", BUILD_ID)),
        managed_files=len(entries),
        verified_files=verified,
        errors=errors,
    )
    if strict and not result.ok:
        detail = "; ".join(result.errors[:8])
        raise RuntimeError(f"Release integrity verification failed: {detail}")
    return result


def cache_integrity_result(state_dir: Path, result: IntegrityResult) -> Path:
    """Persist the completed identity result for bounded diagnostic reuse."""
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "runtime_identity_result.json"
    temp = path.with_suffix(path.suffix + ".tmp")
    payload = result.to_dict() | {"cache_schema_version": "1.0"}
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)
    return path


def load_cached_integrity(state_dir: Path) -> dict:
    path = state_dir / "runtime_identity_result.json"
    if not path.is_file():
        return {
            "ok": False,
            "cache_available": False,
            "managed_file_rehash_performed": False,
            "errors": ["No completed runtime-identity result was cached."],
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("cache root is not an object")
        payload["cache_available"] = True
        payload["managed_file_rehash_performed"] = False
        return payload
    except Exception as exc:
        return {
            "ok": False,
            "cache_available": False,
            "managed_file_rehash_performed": False,
            "errors": [f"Runtime-identity cache could not be read: {type(exc).__name__}"],
        }


def iter_managed_files(root: Path) -> Iterable[Path]:
    root = root.resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if _is_unmanaged_runtime_file(rel):
            continue
        yield path
