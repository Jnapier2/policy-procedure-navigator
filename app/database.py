from __future__ import annotations

import hashlib
import json
import sqlite3
import os
import shutil
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .integrity import sha256_file


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    SCHEMA_VERSION = 3

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
        self._backup_dir = self.path.parent.parent / "backups" / "database"

    @staticmethod
    def _configure_connection(conn: sqlite3.Connection) -> None:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 15000")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA temp_store = MEMORY")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        self._configure_connection(conn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _database_has_schema(self) -> bool:
        if not self.path.is_file() or self.path.stat().st_size == 0:
            return False
        try:
            with self.connect() as conn:
                return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone() is not None
        except sqlite3.DatabaseError:
            return False

    def _prune_database_backups(self, max_count: int = 8) -> None:
        """Bound only application-created database backups; never touch unknown files."""
        if not self._backup_dir.is_dir():
            return
        candidates = sorted(
            (
                path
                for path in self._backup_dir.glob("policy_navigator_*.db")
                if path.is_file() and not path.is_symlink()
            ),
            key=lambda path: (path.stat().st_mtime, path.name),
            reverse=True,
        )
        for stale in candidates[max_count:]:
            try:
                stale.unlink()
            except OSError:
                pass

    def backup_database(self, reason: str = "manual") -> dict[str, Any]:
        if not self.path.is_file():
            return {"ok": False, "reason": "database_missing"}
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        safe_reason = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in reason)[:40] or "backup"
        final = self._backup_dir / f"policy_navigator_{stamp}_{safe_reason}.db"
        temp = final.with_suffix(".db.tmp")
        temp.unlink(missing_ok=True)
        with self._write_lock:
            source = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
            target = sqlite3.connect(temp, timeout=15, check_same_thread=False)
            try:
                self._configure_connection(source)
                source.backup(target)
                target.commit()
                check = target.execute("PRAGMA quick_check").fetchone()[0]
                if check != "ok":
                    raise sqlite3.DatabaseError(f"backup quick_check failed: {check}")
            finally:
                target.close()
                source.close()
        os.replace(temp, final)
        digest = sha256_file(final)
        self._prune_database_backups()
        return {"ok": True, "path": str(final), "sha256": digest, "reason": safe_reason}

    def restore_database(self, backup_path: Path) -> dict[str, Any]:
        backup_path = backup_path.resolve()
        backup_root = self._backup_dir.resolve()
        try:
            backup_path.relative_to(backup_root)
        except ValueError as exc:
            raise ValueError("Database restore source must be a project-local backup") from exc
        if not backup_path.is_file() or backup_path.is_symlink():
            raise ValueError("Database backup is unavailable or unsafe")
        verify = sqlite3.connect(backup_path)
        try:
            if verify.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("Backup failed quick_check")
        finally:
            verify.close()
        safety = self.backup_database("pre_restore") if self.path.exists() else {"ok": False, "reason": "database_missing"}
        temp = self.path.with_suffix(".restore.tmp")
        temp.unlink(missing_ok=True)
        shutil.copyfile(backup_path, temp)
        os.replace(temp, self.path)
        health = self.health()
        if not health["ok"]:
            raise sqlite3.DatabaseError("Restored database failed health verification")
        return {"ok": True, "restored_from": str(backup_path), "safety_backup": safety, "health": health}

    def prepare_demo_reset(self) -> dict[str, Any]:
        """Back up the live database, then remove only app-generated DB files.

        User uploads and unknown files are intentionally outside this operation.
        """
        backup = self.backup_database("pre_demo_reset") if self.path.exists() else {"ok": False, "reason": "database_missing"}
        with self._write_lock:
            for candidate in (
                self.path,
                self.path.with_name(self.path.name + "-wal"),
                self.path.with_name(self.path.name + "-shm"),
            ):
                candidate.unlink(missing_ok=True)
        return backup

    def initialize(self) -> dict[str, Any]:
        with self._write_lock:
            prior_version = 0
            if self.path.exists():
                try:
                    with self.connect() as conn:
                        prior_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
                except sqlite3.DatabaseError:
                    prior_version = 0
            migration_backup = None
            if prior_version < self.SCHEMA_VERSION and self._database_has_schema():
                migration_backup = self.backup_database(f"pre_migration_v{prior_version}_to_v{self.SCHEMA_VERSION}")
            with self.connect() as conn:
                conn.execute("PRAGMA journal_mode = WAL")
                conn.executescript(
                    """
                BEGIN IMMEDIATE;

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_filename TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    policy_family TEXT NOT NULL,
                    department TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    allowed_roles TEXT NOT NULL,
                    effective_date TEXT,
                    expires_at TEXT,
                    status TEXT NOT NULL,
                    version TEXT NOT NULL,
                    authority_rank INTEGER NOT NULL DEFAULT 50,
                    controls_json TEXT NOT NULL DEFAULT '{}',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    section TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    word_count INTEGER NOT NULL,
                    UNIQUE(document_id, chunk_index)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id UNINDEXED,
                    document_id UNINDEXED,
                    title,
                    section,
                    content,
                    tokenize='porter unicode61'
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    entity_type TEXT,
                    entity_id TEXT,
                    payload_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS query_runs (
                    id TEXT PRIMARY KEY,
                    occurred_at TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    question_redacted TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT,
                    prompt_version TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    confidence_label TEXT NOT NULL,
                    insufficient_evidence INTEGER NOT NULL,
                    latency_ms INTEGER NOT NULL,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    estimated_cost_usd REAL NOT NULL DEFAULT 0,
                    citation_count INTEGER NOT NULL,
                    pii_redaction_count INTEGER NOT NULL,
                    response_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    assigned_role TEXT NOT NULL,
                    workflow_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    question_redacted TEXT NOT NULL,
                    checklist_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    decision_note TEXT
                );

                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    query_run_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    correction_redacted TEXT,
                    status TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    suite_version TEXT NOT NULL,
                    total_cases INTEGER NOT NULL,
                    passed_cases INTEGER NOT NULL,
                    score REAL NOT NULL,
                    results_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_documents_authority_title
                    ON documents(authority_rank DESC, title ASC, id ASC);
                CREATE INDEX IF NOT EXISTS idx_reviews_created
                    ON reviews(created_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_audit_occurred
                    ON audit_events(occurred_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_queries_occurred
                    ON query_runs(occurred_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_feedback_created
                    ON feedback(created_at DESC, id DESC);
                CREATE INDEX IF NOT EXISTS idx_evaluations_created
                    ON evaluation_runs(created_at DESC, id DESC);
                """
                )
                conn.execute(
                    "INSERT INTO app_state(key, value, updated_at) VALUES ('corpus_generation','0',?) "
                    "ON CONFLICT(key) DO NOTHING",
                    (utc_now(),),
                )
                conn.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
            return {
                "schema_version": self.SCHEMA_VERSION,
                "prior_schema_version": prior_version,
                "migration_backup": migration_backup,
            }

    def health(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"ok": False, "reason": "database_missing", "schema_version": None}
        try:
            with self.connect() as conn:
                quick = conn.execute("PRAGMA quick_check").fetchone()[0]
                schema = int(conn.execute("PRAGMA user_version").fetchone()[0])
                journal = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                busy = int(conn.execute("PRAGMA busy_timeout").fetchone()[0])
                foreign_keys = int(conn.execute("PRAGMA foreign_keys").fetchone()[0])
            return {
                "ok": quick == "ok" and schema == self.SCHEMA_VERSION and foreign_keys == 1,
                "quick_check": quick,
                "schema_version": schema,
                "expected_schema_version": self.SCHEMA_VERSION,
                "journal_mode": journal,
                "busy_timeout_ms": busy,
                "foreign_keys": bool(foreign_keys),
            }
        except sqlite3.DatabaseError as exc:
            return {"ok": False, "reason": type(exc).__name__, "schema_version": None}

    def corpus_generation(self) -> int:
        try:
            with self.connect() as conn:
                row = conn.execute("SELECT value FROM app_state WHERE key='corpus_generation'").fetchone()
            return int(row["value"]) if row else 0
        except (sqlite3.DatabaseError, ValueError, TypeError):
            return 0

    @staticmethod
    def _bump_corpus_generation(conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT value FROM app_state WHERE key='corpus_generation'").fetchone()
        current = int(row["value"]) if row else 0
        updated = current + 1
        conn.execute(
            "INSERT INTO app_state(key,value,updated_at) VALUES ('corpus_generation',?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (str(updated), utc_now()),
        )
        return updated

    def find_document_by_source(self, source_filename: str, policy_family: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE source_filename=? AND policy_family=?",
                (source_filename, policy_family),
            ).fetchone()
        return self._doc_row(row) if row else None

    def upsert_document(self, document: dict[str, Any], chunks: list[dict[str, Any]]) -> str:
        now = utc_now()
        document_id = document.get("id") or str(uuid.uuid4())
        with self._write_lock, self.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM documents WHERE source_filename = ? AND policy_family = ?",
                (document["source_filename"], document["policy_family"]),
            ).fetchone()
            if existing:
                document_id = existing["id"]
                chunk_ids = [r["id"] for r in conn.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,))]
                for chunk_id in chunk_ids:
                    conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk_id,))
                conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            conn.execute(
                """
                INSERT INTO documents (
                    id, title, source_filename, content_hash, policy_family, department,
                    classification, allowed_roles, effective_date, expires_at, status,
                    version, authority_rank, controls_json, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title, source_filename=excluded.source_filename,
                    content_hash=excluded.content_hash, policy_family=excluded.policy_family,
                    department=excluded.department, classification=excluded.classification,
                    allowed_roles=excluded.allowed_roles, effective_date=excluded.effective_date,
                    expires_at=excluded.expires_at, status=excluded.status, version=excluded.version,
                    authority_rank=excluded.authority_rank, controls_json=excluded.controls_json,
                    metadata_json=excluded.metadata_json, updated_at=excluded.updated_at
                """,
                (
                    document_id,
                    document["title"],
                    document["source_filename"],
                    document["content_hash"],
                    document["policy_family"],
                    document["department"],
                    document["classification"],
                    json.dumps(document["allowed_roles"]),
                    document.get("effective_date"),
                    document.get("expires_at"),
                    document["status"],
                    document["version"],
                    int(document.get("authority_rank", 50)),
                    json.dumps(document.get("controls", {}), sort_keys=True),
                    json.dumps(document.get("metadata", {}), sort_keys=True),
                    now,
                    now,
                ),
            )
            for idx, chunk in enumerate(chunks):
                chunk_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO chunks (id, document_id, section, chunk_index, content, word_count) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        chunk_id,
                        document_id,
                        chunk["section"],
                        idx,
                        chunk["content"],
                        len(chunk["content"].split()),
                    ),
                )
                conn.execute(
                    "INSERT INTO chunks_fts (chunk_id, document_id, title, section, content) VALUES (?, ?, ?, ?, ?)",
                    (chunk_id, document_id, document["title"], chunk["section"], chunk["content"]),
                )
            self._bump_corpus_generation(conn)
        return document_id

    def list_documents(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY authority_rank DESC, title ASC"
            ).fetchall()
        return [self._doc_row(row) for row in rows]

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        return self._doc_row(row) if row else None

    def get_documents_by_family(self, families: list[str]) -> list[dict[str, Any]]:
        if not families:
            return []
        marks = ",".join("?" for _ in families)
        with self.connect() as conn:
            rows = conn.execute(f"SELECT * FROM documents WHERE policy_family IN ({marks})", families).fetchall()
        return [self._doc_row(row) for row in rows]

    def search_fts(self, expression: str, limit: int = 80) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT f.chunk_id, f.document_id, f.title, f.section, f.content,
                       d.allowed_roles, d.policy_family, d.department, d.classification,
                       d.effective_date, d.expires_at, d.status, d.version,
                       d.authority_rank, d.controls_json, d.source_filename,
                       bm25(chunks_fts) AS bm25_score
                FROM chunks_fts f
                JOIN documents d ON d.id = f.document_id
                WHERE chunks_fts MATCH ?
                ORDER BY bm25(chunks_fts)
                LIMIT ?
                """,
                (expression, limit),
            ).fetchall()
        return [self._evidence_row(row) for row in rows]

    def all_chunks(self, limit: int = 1000) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id AS chunk_id, c.document_id, d.title, c.section, c.content,
                       d.allowed_roles, d.policy_family, d.department, d.classification,
                       d.effective_date, d.expires_at, d.status, d.version,
                       d.authority_rank, d.controls_json, d.source_filename,
                       0.0 AS bm25_score
                FROM chunks c JOIN documents d ON d.id = c.document_id
                ORDER BY d.authority_rank DESC, d.title, c.chunk_index
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._evidence_row(row) for row in rows]

    def append_audit(
        self,
        actor: str,
        event_type: str,
        payload: dict[str, Any],
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        event_id = str(uuid.uuid4())
        occurred_at = utc_now()
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        with self._write_lock:
            conn = sqlite3.connect(self.path, timeout=15, check_same_thread=False, isolation_level=None)
            self._configure_connection(conn)
            try:
                # BEGIN IMMEDIATE serializes the hash-chain head across processes, not only threads.
                conn.execute("BEGIN IMMEDIATE")
                prior = conn.execute("SELECT event_hash FROM audit_events ORDER BY rowid DESC LIMIT 1").fetchone()
                prev_hash = prior["event_hash"] if prior else "0" * 64
                material = "|".join([prev_hash, occurred_at, actor, event_type, entity_type or "", entity_id or "", payload_json])
                event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
                conn.execute(
                    "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (event_id, occurred_at, actor, event_type, entity_type, entity_id, payload_json, prev_hash, event_hash),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
        return {
            "id": event_id,
            "occurred_at": occurred_at,
            "actor": actor,
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
            "prev_hash": prev_hash,
            "event_hash": event_hash,
        }

    def list_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM audit_events ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [
            {
                "id": r["id"],
                "occurred_at": r["occurred_at"],
                "actor": r["actor"],
                "event_type": r["event_type"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "payload": json.loads(r["payload_json"]),
                "prev_hash": r["prev_hash"],
                "event_hash": r["event_hash"],
            }
            for r in rows
        ]

    def verify_audit_chain(self) -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM audit_events ORDER BY rowid ASC").fetchall()
        expected_prev = "0" * 64
        for index, row in enumerate(rows):
            if row["prev_hash"] != expected_prev:
                return {"ok": False, "events": len(rows), "broken_at": index, "reason": "previous hash mismatch"}
            material = "|".join(
                [
                    row["prev_hash"], row["occurred_at"], row["actor"], row["event_type"],
                    row["entity_type"] or "", row["entity_id"] or "", row["payload_json"],
                ]
            )
            actual = hashlib.sha256(material.encode("utf-8")).hexdigest()
            if actual != row["event_hash"]:
                return {"ok": False, "events": len(rows), "broken_at": index, "reason": "event hash mismatch"}
            expected_prev = actual
        return {"ok": True, "events": len(rows), "broken_at": None, "reason": None}

    def record_query(self, record: dict[str, Any]) -> str:
        query_id = record.get("id") or str(uuid.uuid4())
        with self._write_lock, self.connect() as conn:
            conn.execute(
                """
                INSERT INTO query_runs (
                    id, occurred_at, user_id, question_redacted, provider, model,
                    prompt_version, confidence, confidence_label, insufficient_evidence,
                    latency_ms, input_tokens, output_tokens, estimated_cost_usd,
                    citation_count, pii_redaction_count, response_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query_id, utc_now(), record["user_id"], record["question_redacted"],
                    record["provider"], record.get("model"), record["prompt_version"],
                    record["confidence"], record["confidence_label"],
                    int(record["insufficient_evidence"]), record["latency_ms"],
                    int(record.get("input_tokens", 0)), int(record.get("output_tokens", 0)),
                    float(record.get("estimated_cost_usd", 0)), record["citation_count"],
                    record.get("pii_redaction_count", 0), json.dumps(record["response"], ensure_ascii=False),
                ),
            )
        return query_id

    def get_query(self, query_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM query_runs WHERE id = ?", (query_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data["response"] = json.loads(data.pop("response_json"))
        return data

    def metrics(self) -> dict[str, Any]:
        with self.connect() as conn:
            q = conn.execute(
                """
                SELECT COUNT(*) count, COALESCE(AVG(latency_ms),0) avg_latency,
                       COALESCE(AVG(confidence),0) avg_confidence,
                       COALESCE(SUM(estimated_cost_usd),0) total_cost,
                       COALESCE(SUM(input_tokens + output_tokens),0) total_tokens,
                       COALESCE(SUM(insufficient_evidence),0) abstentions
                FROM query_runs
                """
            ).fetchone()
            docs = conn.execute("SELECT COUNT(*) count FROM documents").fetchone()["count"]
            chunks = conn.execute("SELECT COUNT(*) count FROM chunks").fetchone()["count"]
            reviews = conn.execute("SELECT COUNT(*) count FROM reviews WHERE status IN ('pending_review','in_review')").fetchone()["count"]
            eval_row = conn.execute("SELECT score, created_at FROM evaluation_runs ORDER BY rowid DESC LIMIT 1").fetchone()
        return {
            "queries": q["count"],
            "avg_latency_ms": round(q["avg_latency"], 1),
            "avg_confidence": round(q["avg_confidence"], 3),
            "total_cost_usd": round(q["total_cost"], 6),
            "total_tokens": q["total_tokens"],
            "abstentions": q["abstentions"],
            "documents": docs,
            "chunks": chunks,
            "pending_reviews": reviews,
            "latest_eval_score": round(eval_row["score"], 3) if eval_row else None,
            "latest_eval_at": eval_row["created_at"] if eval_row else None,
        }

    def create_review(self, review: dict[str, Any]) -> str:
        review_id = review.get("id") or str(uuid.uuid4())
        now = utc_now()
        with self._write_lock, self.connect() as conn:
            conn.execute(
                """
                INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id, now, now, review["created_by"], review["assigned_role"],
                    review["workflow_type"], review["title"], review.get("status", "pending_review"),
                    review.get("risk_level", "medium"), review["question_redacted"],
                    json.dumps(review.get("checklist", []), ensure_ascii=False),
                    json.dumps(review.get("evidence", []), ensure_ascii=False),
                    review.get("decision_note"),
                ),
            )
        return review_id

    @staticmethod
    def _decode_review(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["checklist"] = json.loads(item.pop("checklist_json"))
        item["evidence"] = json.loads(item.pop("evidence_json"))
        return item

    def list_reviews(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM reviews ORDER BY rowid DESC").fetchall()
        return [self._decode_review(row) for row in rows]

    def get_review(self, review_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        return self._decode_review(row) if row else None

    def update_review(self, review_id: str, status: str, decision_note: str | None) -> bool:
        with self._write_lock, self.connect() as conn:
            cur = conn.execute(
                "UPDATE reviews SET status = ?, decision_note = ?, updated_at = ? WHERE id = ?",
                (status, decision_note, utc_now(), review_id),
            )
        return cur.rowcount > 0

    def record_feedback(self, payload: dict[str, Any]) -> str:
        feedback_id = str(uuid.uuid4())
        with self._write_lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO feedback VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    feedback_id, utc_now(), payload["query_run_id"], payload["user_id"],
                    int(payload["rating"]), payload.get("correction_redacted"),
                    "open" if payload.get("correction_redacted") else "recorded",
                ),
            )
        return feedback_id

    def record_evaluation(self, suite_version: str, results: list[dict[str, Any]]) -> str:
        run_id = str(uuid.uuid4())
        passed = sum(1 for result in results if result["passed"])
        score = passed / len(results) if results else 0.0
        with self._write_lock, self.connect() as conn:
            conn.execute(
                "INSERT INTO evaluation_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                (run_id, utc_now(), suite_version, len(results), passed, score, json.dumps(results, ensure_ascii=False)),
            )
        return run_id

    def latest_evaluation(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM evaluation_runs ORDER BY rowid DESC LIMIT 1").fetchone()
        if not row:
            return None
        data = dict(row)
        data["results"] = json.loads(data.pop("results_json"))
        return data

    @staticmethod
    def _doc_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["allowed_roles"] = json.loads(data["allowed_roles"])
        data["controls"] = json.loads(data.pop("controls_json"))
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return data

    @staticmethod
    def _evidence_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["allowed_roles"] = json.loads(data["allowed_roles"])
        data["controls"] = json.loads(data.pop("controls_json"))
        return data
