from __future__ import annotations

from app.database import Database
from app.service import PolicyService


def test_vendor_question_produces_citations_workflow_and_authority_warning(service: PolicyService) -> None:
    response = service.ask("What approvals are required before engaging a new vendor?", "ava.employee", persist=False)
    assert response["confidence"]["insufficient_evidence"] is False
    assert response["workflow"]["id"] == "vendor_onboarding"
    assert len(response["checklist"]) >= 7
    assert len(response["citations"]) >= 2
    assert "purchase order" in response["answer"].lower()
    assert any("excluded" in warning["message"].lower() for warning in response["authority"]["warnings"])


def test_permission_aware_retrieval_blocks_restricted_security_source(service: PolicyService) -> None:
    employee = service.ask("What penetration-testing evidence do we require from vendors?", "ava.employee", persist=False)
    assert employee["confidence"]["insufficient_evidence"] is True
    assert all(citation["title"] != "Third-Party Information Security Standard" for citation in employee["citations"])
    assert "penetration-test summary" not in employee["answer"].lower()
    assert employee["access"]["restricted_candidates_excluded"] >= 1
    assert employee["access"]["permission_sensitive_evidence_gap"] is True

    paraphrase = service.ask(
        "What penetration testing evidence must a software vendor provide?",
        "ava.employee",
        persist=False,
    )
    assert paraphrase["confidence"]["insufficient_evidence"] is True
    assert paraphrase["citations"] == []
    assert paraphrase["access"]["permission_sensitive_evidence_gap"] is True

    security = service.ask("What security evidence may be required before a software vendor is approved?", "sam.security", persist=False)
    assert security["confidence"]["insufficient_evidence"] is False
    assert security["access"]["permission_sensitive_evidence_gap"] is False
    assert any(citation["title"] == "Third-Party Information Security Standard" for citation in security["citations"])
    assert "penetration-test" in security["answer"].lower()


def test_unknown_policy_question_abstains(service: PolicyService) -> None:
    response = service.ask("What is the exact daily parking reimbursement limit while traveling?", "ava.employee", persist=False)
    assert response["confidence"]["insufficient_evidence"] is True
    assert "not enough" in response["answer"].lower()
    assert response["citations"] == []


def test_audit_chain_detects_intact_sequence(service: PolicyService, db: Database) -> None:
    service.ask("What approvals are required before engaging a new vendor?", "ava.employee", persist=True)
    service.ask("What is the exact daily parking reimbursement limit while traveling?", "ava.employee", persist=True)
    verification = db.verify_audit_chain()
    assert verification["ok"] is True
    assert verification["events"] >= 3


def test_authority_analysis_does_not_reveal_inaccessible_family_documents(
    service: PolicyService, db: Database
) -> None:
    db.upsert_document(
        {
            "title": "Restricted Vendor Override",
            "source_filename": "restricted_vendor_override.md",
            "content_hash": "0" * 64,
            "policy_family": "vendor-management",
            "department": "Security",
            "classification": "restricted",
            "allowed_roles": ["security", "admin"],
            "effective_date": "2026-08-01",
            "expires_at": "2027-08-01",
            "status": "draft",
            "version": "0.1",
            "authority_rank": 99,
            "controls": {"finance_approval_threshold": "1"},
            "metadata": {},
        },
        [{"section": "Restricted", "content": "Restricted vendor control details."}],
    )
    response = service.ask(
        "What approvals are required before engaging a new vendor?", "ava.employee", persist=False
    )
    authority_text = str(response["authority"])
    assert "Restricted Vendor Override" not in authority_text
    assert "finance_approval_threshold: 1 vs 25000" not in authority_text
