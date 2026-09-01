from __future__ import annotations

import copy
import math
import re
import threading
from collections import Counter, OrderedDict
from datetime import date
from typing import Any

from .database import Database

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "before", "by", "do", "for",
    "from", "how", "i", "in", "is", "it", "of", "on", "or", "our", "the",
    "to", "what", "when", "which", "who", "with", "we", "you", "may",
    "must", "provide", "provided", "provides", "require", "required", "requires",
}

# High-information concepts are used only for the permission-gap guard. Broad
# workflow words stay available to normal retrieval but do not independently
# prove that a role can answer a narrower protected-topic question.
_ANCHOR_STOPWORDS = _STOPWORDS | {
    "approval", "approved", "company", "data", "detail", "details", "document",
    "engage", "evidence", "information", "may", "must", "new", "policy",
    "procedure", "provide", "require", "software", "third", "party", "vendor",
}
_CONCEPT_NORMALIZATION = {
    "approvals": "approval",
    "approved": "approval",
    "documents": "document",
    "engaging": "engage",
    "provides": "provide",
    "provided": "provide",
    "requiring": "require",
    "requires": "require",
    "required": "require",
    "testing": "test",
    "tests": "test",
    "vendors": "vendor",
}


class RetrievalCache:
    """Bounded role- and corpus-scoped cache for deterministic retrieval results."""

    def __init__(self, max_entries: int = 128):
        self.max_entries = max(8, int(max_entries))
        self._items: OrderedDict[tuple[str, int, str, int, bool], dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def normalize_question(question: str) -> str:
        return " ".join(question.casefold().split())[:4000]

    def get(
        self, role: str, corpus_generation: int, question: str, limit: int, include_non_authoritative: bool
    ) -> dict[str, Any] | None:
        key = (role, int(corpus_generation), self.normalize_question(question), int(limit), bool(include_non_authoritative))
        with self._lock:
            value = self._items.pop(key, None)
            if value is None:
                self.misses += 1
                return None
            self._items[key] = value
            self.hits += 1
            return copy.deepcopy(value)

    def put(
        self, role: str, corpus_generation: int, question: str, limit: int, include_non_authoritative: bool, value: dict[str, Any]
    ) -> None:
        key = (role, int(corpus_generation), self.normalize_question(question), int(limit), bool(include_non_authoritative))
        with self._lock:
            self._items.pop(key, None)
            self._items[key] = copy.deepcopy(value)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"entries": len(self._items), "max_entries": self.max_entries, "hits": self.hits, "misses": self.misses}

    def clear(self, reset_counters: bool = False) -> None:
        with self._lock:
            self._items.clear()
            if reset_counters:
                self.hits = 0
                self.misses = 0


def tokenize(text: str) -> list[str]:
    raw_tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
    tokens = [_CONCEPT_NORMALIZATION.get(token, token) for token in raw_tokens]
    return [token for token in tokens if token not in _STOPWORDS and len(token) > 1]


def _concept_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
    normalized = {_CONCEPT_NORMALIZATION.get(token, token) for token in tokens}
    return {token for token in normalized if len(token) > 1}


def _fts_expression(tokens: list[str]) -> str:
    unique = list(dict.fromkeys(tokens))[:16]
    return " OR ".join(f'"{token.replace(chr(34), "")}"' for token in unique)


def _role_allowed(item: dict[str, Any], role: str) -> bool:
    return role == "admin" or role in item.get("allowed_roles", [])


def _candidate_is_current(item: dict[str, Any]) -> bool:
    if item.get("status") != "active":
        return False
    expires_at = item.get("expires_at")
    if not expires_at:
        return True
    try:
        return date.fromisoformat(expires_at) >= date.today()
    except ValueError:
        return False


def _permission_gap_terms(candidates: list[dict[str, Any]], question: str, role: str) -> list[str]:
    """Detect material query concepts supported only by inaccessible current sources.

    This does not expose restricted content. It supplies a conservative signal to
    the confidence layer so a broad permitted document cannot answer around a
    protected detail merely because both documents mention the same vendor.
    """
    query_concepts = _concept_tokens(question) - _ANCHOR_STOPWORDS
    if not query_concepts or role == "admin":
        return []

    permitted_hits = {term: set() for term in query_concepts}
    restricted_hits = {term: set() for term in query_concepts}
    for item in candidates:
        if not _candidate_is_current(item):
            continue
        item_concepts = _concept_tokens(f"{item['title']} {item['section']} {item['content']}")
        matched = query_concepts & item_concepts
        if not matched:
            continue
        target = permitted_hits if _role_allowed(item, role) else restricted_hits
        for term in matched:
            target[term].add(item["document_id"])

    return sorted(
        term
        for term in query_concepts
        if restricted_hits[term] and not permitted_hits[term]
    )


def _status_weight(item: dict[str, Any]) -> float:
    status = item.get("status", "active")
    weight = {"active": 1.0, "draft": 0.48, "expired": 0.28, "superseded": 0.20}.get(status, 0.35)
    expires_at = item.get("expires_at")
    if expires_at:
        try:
            if date.fromisoformat(expires_at) < date.today() and status == "active":
                weight *= 0.45
        except ValueError:
            weight *= 0.85
    return weight


def _coverage(query_tokens: list[str], content: str) -> float:
    if not query_tokens:
        return 0.0
    content_tokens = set(tokenize(content))
    return len(set(query_tokens) & content_tokens) / len(set(query_tokens))


def _term_density(query_tokens: list[str], content: str) -> float:
    if not query_tokens:
        return 0.0
    words = tokenize(content)
    if not words:
        return 0.0
    counts = Counter(words)
    hits = sum(min(counts[token], 3) for token in set(query_tokens))
    return min(1.0, hits / max(2.0, len(set(query_tokens)) * 1.5))


def retrieve(
    db: Database,
    question: str,
    role: str,
    limit: int = 8,
    include_non_authoritative: bool = True,
) -> dict[str, Any]:
    query_tokens = tokenize(question)
    candidates: list[dict[str, Any]] = []
    if query_tokens:
        expression = _fts_expression(query_tokens)
        try:
            candidates = db.search_fts(expression, limit=100)
        except Exception:
            candidates = []
    if not candidates:
        candidates = db.all_chunks(limit=1000)

    permission_gap_terms = _permission_gap_terms(candidates, question, role)
    permitted: list[dict[str, Any]] = []
    restricted_count = 0
    for rank, item in enumerate(candidates):
        if not _role_allowed(item, role):
            restricted_count += 1
            continue
        coverage = _coverage(query_tokens, item["content"] + " " + item["title"] + " " + item["section"])
        density = _term_density(query_tokens, item["content"])
        rank_quality = 1.0 / math.sqrt(rank + 1)
        authority = min(1.0, max(0.1, float(item.get("authority_rank", 50)) / 100.0))
        lexical_relevance = 0.65 * coverage + 0.35 * density
        score = (
            0.68 * lexical_relevance
            + 0.12 * rank_quality
            + 0.10 * authority
            + 0.10 * _status_weight(item)
        )
        if lexical_relevance == 0:
            score *= 0.30
        scored = dict(item)
        scored["retrieval_score"] = round(score, 4)
        scored["query_coverage"] = round(coverage, 4)
        if include_non_authoritative or item.get("status") == "active":
            permitted.append(scored)

    permitted.sort(
        key=lambda item: (
            item["retrieval_score"],
            _status_weight(item),
            item.get("authority_rank", 0),
        ),
        reverse=True,
    )

    # Preserve source diversity before filling with additional chunks.
    selected: list[dict[str, Any]] = []
    seen_docs: set[str] = set()
    for item in permitted:
        if item["document_id"] not in seen_docs:
            selected.append(item)
            seen_docs.add(item["document_id"])
            if len(selected) >= max(3, limit // 2):
                break
    selected_chunk_ids = {row["chunk_id"] for row in selected}
    for item in permitted:
        if item["chunk_id"] in selected_chunk_ids:
            continue
        selected.append(item)
        selected_chunk_ids.add(item["chunk_id"])
        if len(selected) >= limit:
            break

    return {
        "evidence": selected,
        "query_tokens": query_tokens,
        "restricted_candidate_count": restricted_count,
        "permitted_candidate_count": len(permitted),
        "permission_gap_detected": bool(permission_gap_terms),
        "permission_gap_terms": permission_gap_terms,
    }
