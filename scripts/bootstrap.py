from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import load_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.diagnostics import capture_critical, configure_logging  # noqa: E402
from app.integrity import cache_integrity_result, verify_release  # noqa: E402
from app.seed import bootstrap_database  # noqa: E402
from scripts.launcher_failure_capsule import safe_create_launcher_failure  # noqa: E402


def main() -> int:
    integrity = None
    settings = None
    db = None
    try:
        integrity = verify_release(ROOT, strict=True)
        settings = load_settings()
        cache_integrity_result(settings.state_dir, integrity)
        configure_logging(settings)
        db = Database(settings.db_path)
        result = bootstrap_database(db, settings)
        print(json.dumps(result, indent=2))
        return 0
    except BaseException as exc:
        if settings is not None:
            diagnostic = capture_critical(
                settings,
                exc,
                "startup_bootstrap_abort",
                db=db,
                active_mode="bootstrap",
                runtime_identity=integrity.to_dict() if integrity else None,
            )
        else:
            diagnostic = safe_create_launcher_failure(
                "startup_settings_abort",
                f"Startup failed before governed settings were available ({type(exc).__name__}).",
            )
        print(json.dumps({"ok": False, "exception_type": type(exc).__name__, "diagnostic": diagnostic}, indent=2), file=sys.stderr)
        return 6


if __name__ == "__main__":
    raise SystemExit(main())
