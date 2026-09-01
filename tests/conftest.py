from __future__ import annotations

from pathlib import Path

import pytest

from app.config import PROJECT_ROOT, Settings
from app.database import Database
from app.seed import bootstrap_database
from app.service import PolicyService


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    directories = {
        "state": tmp_path / "state",
        "logs": tmp_path / "logs",
        "temp": tmp_path / "temp",
        "exports": tmp_path / "exports",
        "diagnostics": tmp_path / "diagnostics",
        "uploads": tmp_path / "local" / "uploads",
    }
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    return Settings(
        root=PROJECT_ROOT,
        state_dir=directories["state"],
        logs_dir=directories["logs"],
        temp_dir=directories["temp"],
        exports_dir=directories["exports"],
        diagnostics_dir=directories["diagnostics"],
        uploads_dir=directories["uploads"],
        db_path=directories["state"] / "test.db",
        host="127.0.0.1",
        port=8765,
        log_level="INFO",
    )


@pytest.fixture()
def db(settings: Settings) -> Database:
    database = Database(settings.db_path)
    bootstrap_database(database, settings)
    return database


@pytest.fixture()
def service(db: Database, settings: Settings) -> PolicyService:
    return PolicyService(db, settings)
