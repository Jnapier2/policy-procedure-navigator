from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from .config import Settings
from .retrieval import tokenize


@dataclass
class GenerationResult:
    answer: str
    caveats: list[str]
    cited_source_ids: list[str]
    provider: str
    model: str | None
    prompt_version: str
    latency_ms: int
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    fallback_reason: str | None = None


def _best_sentences(
    question_redacted: str,
    evidence: list[dict[str, Any]],
    max_sentences: int = 3,
    max_per_document: int = 2,
) -> list[tuple[str, str]]:
    query_tokens = set(tokenize(question_redacted))
    priority = re.compile(
        r"\b(required|require|must|before|approval|review|authorized|purchase order|signed|exception)\b",
        re.IGNORECASE,
    )
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    sequence = 0

    for index, item in enumerate(evidence, start=1):
        if item.get("status") != "active":
            continue
        context_tokens = set(tokenize(f"{item['title']} {item['section']}"))
        for sentence_index, sentence in enumerate(re.split(r"(?<=[.!?])\s+", item["content"])):
            cleaned = sentence.strip(" -\n")
            key = re.sub(r"\W+", " ", cleaned.lower()).strip()
            if len(cleaned) < 35 or key in seen:
                continue
            sentence_tokens = set(tokenize(cleaned))
            matched_tokens = query_tokens & (sentence_tokens | context_tokens)
            if query_tokens and not matched_tokens:
                continue
            seen.add(key)
            sentence_overlap = len(query_tokens & sentence_tokens)
            context_overlap = len(query_tokens & context_tokens)
            base_score = (
                2.5 * sentence_overlap
                + 1.25 * context_overlap
                + (1.0 if priority.search(cleaned) else 0.0)
                + float(item.get("retrieval_score", 0))
            )
            candidates.append(
                {
                    "base_score": base_score,
                    "sequence": sequence,
                    "sentence_index": sentence_index,
                    "text": cleaned,
                    "source_id": f"S{index}",
                    "document_id": item["document_id"],
                    "matched_tokens": matched_tokens,
                }
            )
            sequence += 1

    selected: list[tuple[str, str]] = []
    document_counts: dict[str, int] = {}
    covered_tokens: set[str] = set()
    remaining = list(candidates)
    while remaining and len(selected) < max_sentences:
        eligible = [
            candidate
            for candidate in remaining
            if document_counts.get(candidate["document_id"], 0) < max_per_document
        ]
        if not eligible:
            break
        best = max(
            eligible,
            key=lambda candidate: (
                4.0 * len(candidate["matched_tokens"] - covered_tokens) + candidate["base_score"],
                len(candidate["matched_tokens"] - covered_tokens),
                candidate["base_score"],
                -candidate["sequence"],
                -candidate["sentence_index"],
            ),
        )
        selected.append((best["text"], best["source_id"]))
        covered_tokens.update(best["matched_tokens"])
        document_counts[best["document_id"]] = document_counts.get(best["document_id"], 0) + 1
        remaining.remove(best)
    return selected


def deterministic_answer(
    question_redacted: str,
    evidence: list[dict[str, Any]],
    checklist: list[dict[str, Any]],
    insufficient_evidence: bool,
    authority: dict[str, Any],
) -> GenerationResult:
    start = time.perf_counter()
    if insufficient_evidence:
        answer = (
            "There is not enough current, permitted, and consistent evidence to answer this definitively. "
            "No consequential action should be taken from this response. Route the question to the responsible policy owner or reviewer."
        )
        cited: list[str] = []
    elif checklist:
        lines = [
            "Before engaging a new vendor, complete the governed approval path below. "
            "The evidence does not authorize work to begin merely because an intake was submitted."
        ]
        for item in checklist:
            sources = " ".join(f"[{source_id}]" for source_id in item["source_ids"])
            lines.append(f"- {item['title']}. {sources}".rstrip())
        answer = "\n".join(lines)
        cited = list(dict.fromkeys(source_id for item in checklist for source_id in item["source_ids"]))
    else:
        sentences = _best_sentences(question_redacted, evidence)
        if not sentences:
            answer = (
                "There is not enough current, permitted evidence to answer this definitively. "
                "Please route the question to the responsible policy owner."
            )
            cited = []
        else:
            answer = "\n".join(f"- {sentence} [{source_id}]" for sentence, source_id in sentences)
            cited = list(dict.fromkeys(source_id for _, source_id in sentences))

    caveats = [warning["message"] for warning in authority.get("warnings", [])[:3]]
    caveats.extend(conflict["message"] for conflict in authority.get("conflicts", [])[:3])
    return GenerationResult(
        answer=answer,
        caveats=caveats,
        cited_source_ids=cited,
        provider="local-governed-evidence",
        model=None,
        prompt_version="policy-answer-v1.0.0",
        latency_ms=round((time.perf_counter() - start) * 1000),
    )


def generate_answer(
    settings: Settings,
    question_redacted: str,
    evidence: list[dict[str, Any]],
    checklist: list[dict[str, Any]],
    insufficient_evidence: bool,
    authority: dict[str, Any],
) -> GenerationResult:
    # settings is retained in the signature to keep the service boundary stable.
    # The local release is intentionally deterministic and credential-free.
    _ = settings
    return deterministic_answer(question_redacted, evidence, checklist, insufficient_evidence, authority)
