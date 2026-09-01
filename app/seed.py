from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import Settings
from .database import Database
from .ingest import ingest_file


def _demo_signature(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def bootstrap_database(db: Database, settings: Settings) -> dict[str, Any]:
    migration = db.initialize()
    demo_paths = sorted((settings.root / "data" / "demo_documents").glob("*"))
    demo_paths = [path for path in demo_paths if path.suffix.lower() in {".md", ".txt", ".pdf", ".docx"}]
    signature = _demo_signature(demo_paths)
    state_path = settings.state_dir / "demo_seed_state.json"
    prior: dict[str, Any] = {}
    if state_path.exists():
        try:
            prior = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            prior = {}
    existing_count = len(db.list_documents())
    if prior.get("signature") == signature and existing_count >= len(demo_paths):
        return {"seeded": False, "documents": existing_count, "signature": signature, "migration": migration}

    results = [ingest_file(db, path, redact_before_index=True) for path in demo_paths]
    state_path.write_text(
        json.dumps({"signature": signature, "document_count": len(results)}, indent=2),
        encoding="utf-8",
    )
    db.append_audit(
        actor="system",
        event_type="demo_documents_seeded",
        entity_type="document_collection",
        payload={
            "document_count": len(results),
            "chunk_count": sum(result["chunks"] for result in results),
            "pii_redactions": sum(sum(result["pii_redactions"].values()) for result in results),
            "signature": signature[:16],
        },
    )
    return {"seeded": True, "documents": len(results), "results": results, "signature": signature, "migration": migration}


def reset_demo_database(db: Database, settings: Settings) -> dict[str, Any]:
    """Reset only generated database/demo-seed state after creating a verified backup.

    User-uploaded source files under local/uploads are preserved. The backup is
    project-local and integrity-checked by Database.backup_database().
    """
    backup = db.prepare_demo_reset()
    (settings.state_dir / "demo_seed_state.json").unlink(missing_ok=True)
    seeded = bootstrap_database(db, settings)
    db.append_audit(
        actor="admin.demo",
        event_type="demo_state_reset",
        entity_type="demo_environment",
        payload={
            "backup_created": bool(backup.get("ok")),
            "user_upload_files_preserved": True,
            "seed_signature": seeded.get("signature", "")[:16],
        },
    )
    return {"ok": True, "backup": backup, "seed": seeded, "uploads_preserved": True}
