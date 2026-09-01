from __future__ import annotations

import zipfile

from app.config import Settings
from app.database import Database
from app.diagnostics import build_export20
from app.evals import run_evaluations
from app.service import PolicyService


def test_golden_evaluation_suite_passes(db: Database, service: PolicyService) -> None:
    result = run_evaluations(db, service, persist=False)
    assert result["score"] == 1.0, result


def test_export20_is_bounded_and_integrity_tested(settings: Settings, db: Database) -> None:
    result = build_export20(settings, db=db, trigger="test")
    assert result["ok"] is True, result
    assert result["entry_count"] <= 20
    with zipfile.ZipFile(result["path"], "r") as archive:
        assert archive.testzip() is None
        assert len(archive.infolist()) <= 20


def test_critical_capsule_redacts_sensitive_text_and_suppresses_repeat(settings: Settings, db: Database) -> None:
    from pathlib import Path
    import json

    from app.diagnostics import capture_critical

    def make_error() -> RuntimeError:
        return RuntimeError(
            "Contact owner@example.com from 127.0.0.1 using sk-proj-AAAAAAAAAAAAAAAAAAAA"
        )

    first = capture_critical(settings, make_error(), "unit_test_critical", db=db, active_mode="test")
    assert first["export"]["ok"] is True
    capsule_text = Path(first["capsule_path"]).read_text(encoding="utf-8")
    assert "owner@example.com" not in capsule_text
    assert "127.0.0.1" not in capsule_text
    assert "sk-proj-AAAAAAAAAAAAAAAAAAAA" not in capsule_text
    capsule = json.loads(capsule_text)
    assert capsule["runtime_identity"]["managed_file_rehash_performed"] is False

    second = capture_critical(settings, make_error(), "unit_test_critical", db=db, active_mode="test")
    assert second["export"]["ok"] is False
    assert second["export"]["reason"] == "fingerprint_cooldown_suppression"


def test_keyless_answer_engine_has_zero_external_cost(service: PolicyService) -> None:
    result = service.ask("What approvals are required before engaging a new vendor?", "ava.employee", persist=False)
    assert result["provider"]["name"] == "local-governed-evidence"
    assert result["provider"]["estimated_cost_usd"] == 0.0
    assert result["privacy"]["network_provider_used"] is False
    assert result["privacy"]["credentials_required"] is False
