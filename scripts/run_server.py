from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

from app.config import load_settings  # noqa: E402
from app.database import Database  # noqa: E402
from app.diagnostics import capture_critical, configure_logging  # noqa: E402
from app.integrity import cache_integrity_result, verify_release  # noqa: E402
from scripts.launcher_failure_capsule import safe_create_launcher_failure  # noqa: E402


def main() -> int:
    integrity = None
    settings = None
    try:
        integrity = verify_release(ROOT, strict=True)
        settings = load_settings()
        cache_integrity_result(settings.state_dir, integrity)
        configure_logging(settings)
        # Import application code only after release identity and governed settings are available.
        from app.main import create_app

        application = create_app(integrity=integrity, settings=settings)
        uvicorn.run(
            application,
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level.lower(),
            reload=False,
            access_log=True,
        )
        return 0
    except KeyboardInterrupt:
        return 0
    except BaseException as exc:
        if settings is not None:
            db = None
            try:
                db = Database(settings.db_path)
            except Exception:
                db = None
            diagnostic = capture_critical(
                settings,
                exc,
                "startup_or_server_abort",
                db=db,
                active_mode="launcher",
                runtime_identity=integrity.to_dict() if integrity else None,
            )
        else:
            diagnostic = safe_create_launcher_failure(
                "server_settings_abort",
                f"Server startup failed before governed settings were available ({type(exc).__name__}).",
            )
        print(json.dumps({"ok": False, "exception_type": type(exc).__name__, "diagnostic": diagnostic}, indent=2), file=sys.stderr)
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
