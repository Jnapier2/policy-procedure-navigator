from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import load_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.diagnostics import build_export20, configure_logging  # noqa: E402
from app.integrity import cache_integrity_result, verify_release  # noqa: E402
from app.seed import bootstrap_database  # noqa: E402


def main() -> int:
    integrity = verify_release(ROOT, strict=True)
    settings = load_settings()
    cache_integrity_result(settings.state_dir, integrity)
    configure_logging(settings)
    db = Database(settings.db_path)
    bootstrap_database(db, settings)
    result = build_export20(
        settings, db=db, trigger="manual_cli", runtime_identity=integrity.to_dict()
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
