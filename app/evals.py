from __future__ import annotations

from typing import Any

from .config import read_json
from .database import Database
from .service import PolicyService


def _contains_all(text: str, terms: list[str]) -> tuple[bool, list[str]]:
    lowered = text.lower()
    missing = [term for term in terms if term.lower() not in lowered]
    return not missing, missing


def run_evaluations(db: Database, service: PolicyService, persist: bool = True) -> dict[str, Any]:
    suite = read_json("evals/golden_questions.json")
    # The bundled suite exercises the same keyless deterministic engine used by the UI.
    eval_service = PolicyService(db, service.settings)
    results: list[dict[str, Any]] = []

    for case in suite["cases"]:
        response = eval_service.ask(case["question"], case["user_id"], persist=False)
        checks: list[dict[str, Any]] = []

        actual_insufficient = bool(response["confidence"]["insufficient_evidence"])
        checks.append(
            {
                "name": "abstention",
                "passed": actual_insufficient == bool(case["expect_insufficient"]),
                "expected": case["expect_insufficient"],
                "actual": actual_insufficient,
            }
        )

        terms_ok, missing_terms = _contains_all(response["answer"], case.get("required_answer_terms", []))
        checks.append(
            {
                "name": "required_answer_terms",
                "passed": terms_ok,
                "missing": missing_terms,
            }
        )

        forbidden_found = [
            term for term in case.get("forbidden_answer_terms", []) if term.lower() in response["answer"].lower()
        ]
        checks.append(
            {
                "name": "forbidden_answer_terms",
                "passed": not forbidden_found,
                "found": forbidden_found,
            }
        )

        checks.append(
            {
                "name": "minimum_citations",
                "passed": len(response["citations"]) >= int(case.get("minimum_citations", 0)),
                "expected": int(case.get("minimum_citations", 0)),
                "actual": len(response["citations"]),
            }
        )

        source_titles = {citation["title"] for citation in response["citations"]}
        leaked = [title for title in case.get("forbidden_source_titles", []) if title in source_titles]
        checks.append(
            {
                "name": "permission_leakage",
                "passed": not leaked,
                "leaked_sources": leaked,
            }
        )

        expected_workflow = case.get("expect_workflow")
        actual_workflow = response["workflow"]["id"] if response.get("workflow") else None
        checks.append(
            {
                "name": "workflow_routing",
                "passed": expected_workflow is None or actual_workflow == expected_workflow,
                "expected": expected_workflow,
                "actual": actual_workflow,
            }
        )

        minimum_redactions = int(case.get("minimum_pii_redactions", 0))
        checks.append(
            {
                "name": "pii_redaction",
                "passed": response["privacy"]["redaction_count"] >= minimum_redactions,
                "expected_minimum": minimum_redactions,
                "actual": response["privacy"]["redaction_count"],
            }
        )

        warning_term = case.get("expect_warning_term")
        warnings_text = " ".join(item["message"] for item in response["authority"]["warnings"])
        checks.append(
            {
                "name": "authority_warning",
                "passed": warning_term is None or warning_term.lower() in warnings_text.lower(),
                "expected_term": warning_term,
            }
        )

        passed = all(check["passed"] for check in checks)
        results.append(
            {
                "case_id": case["id"],
                "passed": passed,
                "checks": checks,
                "confidence": response["confidence"],
                "citation_count": len(response["citations"]),
                "provider": response["provider"]["name"],
            }
        )

    run_id = db.record_evaluation(suite["suite_version"], results) if persist else None
    passed_cases = sum(1 for result in results if result["passed"])
    summary = {
        "run_id": run_id,
        "suite_version": suite["suite_version"],
        "total_cases": len(results),
        "passed_cases": passed_cases,
        "score": round(passed_cases / len(results), 3) if results else 0.0,
        "results": results,
    }
    if persist:
        db.append_audit(
            actor="system",
            event_type="evaluation_suite_completed",
            entity_type="evaluation_run",
            entity_id=run_id,
            payload={
                "suite_version": suite["suite_version"],
                "total_cases": len(results),
                "passed_cases": passed_cases,
                "score": summary["score"],
            },
        )
    return summary
