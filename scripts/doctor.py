from __future__ import annotations

import json
import platform
import sqlite3
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import load_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.integrity import cache_integrity_result, launcher_registry_status, verify_release  # noqa: E402
from app.seed import bootstrap_database  # noqa: E402


def _locked_requirements() -> dict[str, str]:
    expected: dict[str, str] = {}
    for raw in (ROOT / "requirements.lock.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, pinned = line.split("==", 1)
        expected[name.strip()] = pinned.strip()
    return expected


def main() -> int:
    integrity = verify_release(ROOT, strict=False)
    cache_integrity_result(ROOT / "state", integrity)
    checks: dict[str, object] = {
        "python": sys.version,
        "platform": platform.platform(),
        "project_root": str(ROOT),
        "integrity": integrity.to_dict(),
        "launcher_registry": launcher_registry_status(ROOT),
        "packages": {},
        "sqlite_fts5": False,
        "database": None,
    }
    package_ok = True
    for package, expected in _locked_requirements().items():
        try:
            actual = version(package)
        except PackageNotFoundError:
            actual = "MISSING"
        ok = actual == expected
        package_ok = package_ok and ok
        checks["packages"][package] = {"expected": expected, "actual": actual, "ok": ok}  # type: ignore[index]

    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE test_fts USING fts5(content)")
        checks["sqlite_fts5"] = True
    finally:
        conn.close()

    integrity_ok = bool(checks["integrity"]["ok"])  # type: ignore[index]
    launcher_ok = bool(checks["launcher_registry"].get("ok"))  # type: ignore[union-attr]
    database_ok = False
    if integrity_ok and package_ok and checks["sqlite_fts5"] and launcher_ok:
        settings = load_settings()
        db = Database(settings.db_path)
        seed = bootstrap_database(db, settings)
        health = db.health()
        audit = db.verify_audit_chain()
        checks["database"] = {
            "seed": seed,
            "health": health,
            "metrics": db.metrics(),
            "audit_chain": audit,
            "corpus_generation": db.corpus_generation(),
        }
        database_ok = bool(health.get("ok") and audit.get("ok"))
    checks["ready"] = bool(integrity_ok and package_ok and checks["sqlite_fts5"] and launcher_ok and database_ok)
    print(json.dumps(checks, indent=2))
    return 0 if checks["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
