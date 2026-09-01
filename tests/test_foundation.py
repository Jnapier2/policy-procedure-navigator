from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.database import Database
from app.diagnostics import build_export20
from app.ingest import ingest_file
from app.retrieval import RetrievalCache
from app.service import PolicyService


def _fresh_db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "state" / "policy_navigator.db")
    result = db.initialize()
    assert result["schema_version"] == Database.SCHEMA_VERSION
    return db


def test_database_schema_pragmas_and_health_are_ready(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    health = db.health()
    assert health["ok"] is True
    assert health["quick_check"] == "ok"
    assert health["schema_version"] == Database.SCHEMA_VERSION
    assert health["journal_mode"].casefold() == "wal"
    assert health["busy_timeout_ms"] == 15000
    assert health["foreign_keys"] is True


def test_existing_database_gets_project_local_pre_migration_backup(tmp_path: Path) -> None:
    path = tmp_path / "state" / "policy_navigator.db"
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE legacy_marker(value TEXT NOT NULL)")
        conn.execute("INSERT INTO legacy_marker VALUES ('before-migration')")
        conn.execute("PRAGMA user_version = 0")
    db = Database(path)
    result = db.initialize()
    backup = result["migration_backup"]
    assert backup and backup["ok"] is True
    backup_path = Path(backup["path"])
    assert backup_path.parent == tmp_path / "backups" / "database"
    with sqlite3.connect(backup_path) as conn:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT value FROM legacy_marker").fetchone()[0] == "before-migration"
    assert db.health()["schema_version"] == Database.SCHEMA_VERSION


def test_backup_restore_is_integrity_checked_and_backups_are_bounded(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    with db.connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS restore_probe(value TEXT NOT NULL)")
        conn.execute("INSERT INTO restore_probe VALUES ('kept')")
    backup = db.backup_database("unit_test")
    assert backup["ok"] is True
    with db.connect() as conn:
        conn.execute("INSERT INTO restore_probe VALUES ('discarded-after-backup')")
    restored = db.restore_database(Path(backup["path"]))
    assert restored["ok"] is True
    with db.connect() as conn:
        values = [row[0] for row in conn.execute("SELECT value FROM restore_probe ORDER BY rowid")]
    assert values == ["kept"]
    for index in range(10):
        assert db.backup_database(f"retention_{index}")["ok"] is True
    managed_backups = list((tmp_path / "backups" / "database").glob("policy_navigator_*.db"))
    assert 1 <= len(managed_backups) <= 8


def test_incremental_ingestion_skips_unchanged_and_bumps_generation_on_change(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    source = tmp_path / "vendor_policy.md"
    source.write_text("# Vendor Approval\nA manager and Procurement must approve a new vendor before engagement.\n", encoding="utf-8")
    metadata = {
        "policy_family": "vendor-approval",
        "allowed_roles": "employee,procurement,admin",
        "classification": "internal",
        "status": "active",
        "version": "1.0",
        "authority_rank": 90,
    }
    first = ingest_file(db, source, metadata)
    second = ingest_file(db, source, metadata)
    assert first["skipped_unchanged"] is False
    assert second["skipped_unchanged"] is True
    assert second["corpus_generation"] == first["corpus_generation"]
    source.write_text("# Vendor Approval\nA manager, Procurement, and Legal must approve a new vendor before engagement.\n", encoding="utf-8")
    third = ingest_file(db, source, metadata)
    assert third["skipped_unchanged"] is False
    assert third["corpus_generation"] == first["corpus_generation"] + 1


def test_retrieval_cache_is_role_and_corpus_scoped() -> None:
    cache = RetrievalCache(max_entries=8)
    payload = {"evidence": [{"document_id": "restricted-doc"}]}
    assert cache.get("employee", 1, "Vendor security", 9, True) is None
    cache.put("employee", 1, "Vendor security", 9, True, payload)
    employee = cache.get("employee", 1, "  vendor   SECURITY ", 9, True)
    assert employee == payload
    employee["evidence"].clear()
    assert cache.get("employee", 1, "vendor security", 9, True) == payload
    assert cache.get("security", 1, "vendor security", 9, True) is None
    assert cache.get("employee", 2, "vendor security", 9, True) is None


def test_policy_service_cache_hits_then_invalidates_after_ingestion(service: PolicyService, db: Database, tmp_path: Path) -> None:
    question = "What approvals are required before engaging a new vendor?"
    first = service.ask(question, "ava.employee", persist=False)
    second = service.ask(question, "ava.employee", persist=False)
    assert first["performance"]["retrieval_cache_hit"] is False
    assert second["performance"]["retrieval_cache_hit"] is True

    source = tmp_path / "new_vendor_notice.md"
    source.write_text("# Vendor Notice\nProcurement must record the request before vendor engagement.\n", encoding="utf-8")
    ingest_file(
        db,
        source,
        {
            "policy_family": "vendor-notice",
            "allowed_roles": "employee,procurement,admin",
            "classification": "internal",
            "status": "active",
            "version": "1.0",
            "authority_rank": 60,
        },
    )
    third = service.ask(question, "ava.employee", persist=False)
    assert third["performance"]["retrieval_cache_hit"] is False
    assert third["performance"]["corpus_generation"] > first["performance"]["corpus_generation"]


def test_audit_chain_remains_linear_across_independent_connections(tmp_path: Path) -> None:
    path = tmp_path / "state" / "policy_navigator.db"
    Database(path).initialize()

    def append(index: int) -> str:
        db = Database(path)
        return db.append_audit("test", "concurrent_event", {"index": index})["event_hash"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        hashes = list(pool.map(append, range(24)))
    assert len(set(hashes)) == 24
    result = Database(path).verify_audit_chain()
    assert result == {"ok": True, "events": 24, "broken_at": None, "reason": None}


def test_export_lock_is_not_removed_by_non_owner(settings, db: Database) -> None:
    lock = settings.state_dir / "diagnostic_export.lock"
    lock.write_text(json.dumps({"owner": "foreign-owner", "pid": 123, "created_at": "2026-08-29T00:00:00+00:00"}), encoding="utf-8")
    result = build_export20(settings, db=db, trigger="lock-owner-test")
    assert result["ok"] is False
    assert result["reason"] == "exporter_already_active"
    assert json.loads(lock.read_text(encoding="utf-8"))["owner"] == "foreign-owner"


def test_schema_v3_adds_list_performance_indexes(tmp_path: Path) -> None:
    db = _fresh_db(tmp_path)
    with db.connect() as conn:
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {
        "idx_documents_authority_title",
        "idx_reviews_created",
        "idx_audit_occurred",
        "idx_queries_occurred",
        "idx_feedback_created",
        "idx_evaluations_created",
    }.issubset(indexes)


def test_local_benchmark_is_keyless_bounded_and_read_only(service: PolicyService, db: Database) -> None:
    from app.benchmark import run_local_benchmark

    before = db.metrics()["queries"]
    result = run_local_benchmark(service, warm_rounds=2)
    after = db.metrics()["queries"]
    assert result["mode"] == "keyless-local"
    assert result["network_used"] is False
    assert result["credentials_required"] is False
    assert result["requests"] == 15
    assert result["cache"]["hit_rate"] > 0
    assert after == before


def test_demo_reset_preserves_upload_files_and_creates_backup(settings, db: Database) -> None:
    from app.seed import reset_demo_database

    upload = settings.uploads_dir / "recruiter_note.txt"
    upload.write_text("preserve me", encoding="utf-8")
    db.record_evaluation("test-before-reset", [{"passed": True}])
    result = reset_demo_database(db, settings)
    assert result["ok"] is True
    assert result["uploads_preserved"] is True
    assert upload.read_text(encoding="utf-8") == "preserve me"
    assert result["backup"]["ok"] is True
    assert Path(result["backup"]["path"]).is_file()
    assert len(db.list_documents()) >= 8
    assert db.verify_audit_chain()["ok"] is True
