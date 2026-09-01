from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import BUILD_ID, PACKAGE_ID, __version__  # noqa: E402
from app.integrity import iter_managed_files, sha256_file  # noqa: E402


def _write_atomic(path: Path, text: str) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temp, path)


def main() -> int:
    version_text = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
    metadata = json.loads((ROOT / "PACKAGE_METADATA.json").read_text(encoding="utf-8"))
    if version_text != __version__ or str(metadata.get("version", "")) != __version__:
        raise RuntimeError("Version disagreement prevents manifest generation")
    if str(metadata.get("build_id", "")) != BUILD_ID:
        raise RuntimeError("Build disagreement prevents manifest generation")
    if str(metadata.get("package_id", "")) != PACKAGE_ID:
        raise RuntimeError("Package-ID disagreement prevents manifest generation")

    managed_files = []
    for source in iter_managed_files(ROOT):
        relative = source.relative_to(ROOT).as_posix()
        managed_files.append(
            {
                "path": relative,
                "size_bytes": source.stat().st_size,
                "sha256": sha256_file(source),
            }
        )

    manifest = {
        "schema_version": "1.1",
        "package_id": PACKAGE_ID,
        "version": __version__,
        "build_id": BUILD_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hash_algorithm": "SHA-256",
        "managed_file_count": len(managed_files),
        "managed_files": managed_files,
    }
    manifest_path = ROOT / "MANIFEST.json"
    _write_atomic(manifest_path, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    digest = sha256_file(manifest_path)
    _write_atomic(ROOT / "MANIFEST.sha256", f"{digest}  MANIFEST.json\n")
    print(json.dumps({"ok": True, "managed_files": len(managed_files), "manifest_sha256": digest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
