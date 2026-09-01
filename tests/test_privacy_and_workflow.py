from __future__ import annotations

from app.pii import redact_pii
from app.service import PolicyService


def test_common_pii_is_redacted() -> None:
    result = redact_pii("Email jordan.smith@example.com or call 312-555-0199. SSN 123-45-6789.")
    assert result.total == 3
    assert "jordan.smith@example.com" not in result.text
    assert "312-555-0199" not in result.text
    assert "123-45-6789" not in result.text


def test_query_log_stores_redacted_question(service: PolicyService) -> None:
    response = service.ask(
        "My email is jordan.smith@example.com and phone is 312-555-0199. What approvals are required for a new vendor?",
        "marcus.procurement",
        persist=True,
    )
    assert response["privacy"]["redaction_count"] >= 2
    assert "jordan.smith@example.com" not in response["question"]


def test_review_requires_authorized_reviewer(service: PolicyService) -> None:
    response = service.ask("What approvals are required before engaging a new vendor?", "ava.employee", persist=True)
    review = service.create_review_from_query(response["query_run_id"], "ava.employee")
    assert review["status"] == "pending_review"
    try:
        service.update_review(review["review_id"], "ava.employee", "approved", "Looks good")
    except PermissionError:
        pass
    else:
        raise AssertionError("Employee unexpectedly received review authority")
    updated = service.update_review(review["review_id"], "marcus.procurement", "approved", "Evidence reviewed")
    assert updated["status"] == "approved"


def test_review_queue_and_decisions_are_role_scoped(service: PolicyService) -> None:
    employee_response = service.ask(
        "What approvals are required before engaging a new vendor?", "ava.employee", persist=True
    )
    employee_review = service.create_review_from_query(employee_response["query_run_id"], "ava.employee")

    assert any(item["id"] == employee_review["review_id"] for item in service.list_reviews("ava.employee"))
    assert any(item["id"] == employee_review["review_id"] for item in service.list_reviews("marcus.procurement"))
    assert all(item["id"] != employee_review["review_id"] for item in service.list_reviews("lena.legal"))

    try:
        service.update_review(employee_review["review_id"], "lena.legal", "approved", "Not assigned")
    except PermissionError:
        pass
    else:
        raise AssertionError("An unassigned reviewer role unexpectedly changed the case")


def test_cross_user_query_actions_are_blocked(service: PolicyService) -> None:
    response = service.ask(
        "What approvals are required before engaging a new vendor?", "ava.employee", persist=True
    )
    try:
        service.create_review_from_query(response["query_run_id"], "marcus.procurement")
    except PermissionError:
        pass
    else:
        raise AssertionError("A different user unexpectedly created a review from another user's query")

    try:
        service.record_feedback(response["query_run_id"], "marcus.procurement", 1, None)
    except PermissionError:
        pass
    else:
        raise AssertionError("A different user unexpectedly submitted feedback for another user's query")
