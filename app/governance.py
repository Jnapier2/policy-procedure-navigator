from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from .database import Database


def _is_current(document: dict[str, Any]) -> bool:
    if document.get("status") != "active":
        return False
    expires_at = document.get("expires_at")
    if not expires_at:
        return True
    try:
        return date.fromisoformat(expires_at) >= date.today()
    except ValueError:
        return False


def analyze_authority(db: Database, evidence: list[dict[str, Any]], role: str) -> dict[str, Any]:
    families = sorted({item["policy_family"] for item in evidence})
    family_docs = db.get_documents_by_family(families)
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in family_docs:
        if role != "admin" and role not in document.get("allowed_roles", []):
            continue
        by_family[document["policy_family"]].append(document)

    warnings: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    excluded_documents: list[dict[str, str]] = []

    for family, documents in by_family.items():
        active = [document for document in documents if _is_current(document)]
        if len(active) > 1:
            conflicts.append(
                {
                    "family": family,
                    "severity": "high",
                    "message": f"Multiple current authoritative documents were found for {family}.",
                }
            )

        authoritative = sorted(active, key=lambda d: (d["authority_rank"], d["version"]), reverse=True)
        authority_controls = authoritative[0]["controls"] if authoritative else {}

        for document in documents:
            if document in authoritative[:1]:
                continue
            status = document.get("status", "unknown")
            excluded_documents.append(
                {
                    "document_id": document["id"],
                    "title": document["title"],
                    "status": status,
                    "version": document["version"],
                }
            )
            differing = []
            for key, value in document.get("controls", {}).items():
                if key in authority_controls and authority_controls[key] != value:
                    differing.append(f"{key}: {value} vs {authority_controls[key]}")
            if differing:
                warnings.append(
                    {
                        "family": family,
                        "severity": "medium" if status == "draft" else "low",
                        "message": (
                            f"{document['title']} ({status}, v{document['version']}) differs from the current authority "
                            f"and was excluded: {', '.join(differing)}."
                        ),
                    }
                )
            elif status in {"draft", "expired", "superseded"}:
                warnings.append(
                    {
                        "family": family,
                        "severity": "low",
                        "message": f"{document['title']} is {status} and was not treated as authoritative.",
                    }
                )

    return {
        "warnings": warnings,
        "conflicts": conflicts,
        "excluded_documents": excluded_documents,
        "families": families,
    }


def assess_confidence(
    question: str,
    evidence: list[dict[str, Any]],
    authority: dict[str, Any],
    permission_gap_detected: bool = False,
) -> dict[str, Any]:
    if permission_gap_detected:
        return {
            "score": 0.10,
            "label": "low",
            "insufficient_evidence": True,
            "reasons": [
                "The question depends on protected details that are not available to this role."
            ],
        }

    active = [
        item
        for item in evidence
        if item.get("status") == "active"
        and item.get("retrieval_score", 0) >= 0.26
        and item.get("query_coverage", 0) >= 0.25
    ]
    if not active:
        return {
            "score": 0.12,
            "label": "low",
            "insufficient_evidence": True,
            "reasons": ["No sufficiently relevant current authoritative evidence was found."],
        }

    top_score = max(item.get("retrieval_score", 0) for item in active)
    average_coverage = sum(item.get("query_coverage", 0) for item in active[:4]) / min(4, len(active))
    source_diversity = min(1.0, len({item["document_id"] for item in active}) / 3.0)
    authority_quality = sum(min(1.0, item.get("authority_rank", 50) / 100.0) for item in active[:4]) / min(4, len(active))

    score = 0.20 + 0.30 * top_score + 0.20 * average_coverage + 0.15 * source_diversity + 0.15 * authority_quality
    reasons: list[str] = []
    if authority.get("conflicts"):
        score -= 0.30
        reasons.append("Conflicting current authorities require human resolution.")
    if authority.get("warnings"):
        score -= min(0.12, 0.025 * len(authority["warnings"]))
        reasons.append("Non-authoritative or stale guidance was detected and excluded.")
    score = round(max(0.05, min(0.96, score)), 3)

    insufficient = score < 0.47 or bool(authority.get("conflicts"))
    label = "high" if score >= 0.78 else "medium" if score >= 0.55 else "low"
    if not reasons:
        reasons.append("Current permitted evidence is consistent and sufficiently relevant.")
    return {
        "score": score,
        "label": label,
        "insufficient_evidence": insufficient,
        "reasons": reasons,
    }
