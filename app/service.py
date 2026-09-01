from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from .answer_engine import generate_answer
from .config import Settings, read_json
from .database import Database
from .governance import analyze_authority, assess_confidence
from .pii import redact_pii
from .retrieval import RetrievalCache, retrieve
from .workflows import build_checklist, select_workflow


class PolicyService:
    def __init__(self, db: Database, settings: Settings):
        self.db = db
        self.settings = settings
        self.users = {user["id"]: user for user in read_json("config/users.json")["users"]}
        self.retrieval_cache = RetrievalCache(max_entries=128)

    def get_user(self, user_id: str) -> dict[str, Any]:
        user = self.users.get(user_id)
        if not user:
            raise ValueError("Unknown demo user")
        return user

    def ask(self, question: str, user_id: str, persist: bool = True) -> dict[str, Any]:
        overall_start = time.perf_counter()
        timings: dict[str, int] = {}
        user = self.get_user(user_id)

        stage = time.perf_counter()
        question_redaction = redact_pii(question)
        timings["redact"] = round((time.perf_counter() - stage) * 1000)

        stage = time.perf_counter()
        corpus_generation = self.db.corpus_generation()
        retrieval = self.retrieval_cache.get(
            user["role"], corpus_generation, question_redaction.text, 9, True
        )
        retrieval_cache_hit = retrieval is not None
        if retrieval is None:
            retrieval = retrieve(self.db, question_redaction.text, user["role"], limit=9)
            self.retrieval_cache.put(
                user["role"], corpus_generation, question_redaction.text, 9, True, retrieval
            )
        timings["retrieve"] = round((time.perf_counter() - stage) * 1000)

        evidence = retrieval["evidence"]
        relevant_evidence = [
            item
            for item in evidence
            if item.get("retrieval_score", 0) >= 0.26
            and item.get("query_coverage", 0) >= 0.25
        ]

        stage = time.perf_counter()
        authority = analyze_authority(self.db, relevant_evidence, user["role"])
        confidence = assess_confidence(
            question_redaction.text,
            relevant_evidence,
            authority,
            permission_gap_detected=retrieval["permission_gap_detected"],
        )
        workflow = select_workflow(question_redaction.text)
        checklist = build_checklist(workflow, relevant_evidence)
        cited_evidence = [item for item in relevant_evidence if item.get("status") == "active"]
        timings["governance"] = round((time.perf_counter() - stage) * 1000)

        stage = time.perf_counter()
        generation = generate_answer(
            self.settings,
            question_redaction.text,
            cited_evidence,
            checklist,
            confidence["insufficient_evidence"],
            authority,
        )
        timings["generate"] = round((time.perf_counter() - stage) * 1000)
        response_latency = round((time.perf_counter() - overall_start) * 1000)

        citations = []
        for index, item in enumerate(cited_evidence, start=1):
            source_id = f"S{index}"
            if confidence["insufficient_evidence"]:
                continue
            if generation.cited_source_ids and source_id not in generation.cited_source_ids:
                continue
            citations.append(
                {
                    "source_id": source_id,
                    "document_id": item["document_id"],
                    "title": item["title"],
                    "version": item["version"],
                    "status": item["status"],
                    "section": item["section"],
                    "excerpt": item["content"][:520],
                    "effective_date": item.get("effective_date"),
                    "expires_at": item.get("expires_at"),
                    "classification": item.get("classification"),
                    "retrieval_score": item.get("retrieval_score"),
                }
            )

        response = {
            "question": question_redaction.text,
            "answer": generation.answer,
            "confidence": confidence,
            "citations": citations,
            "authority": authority,
            "workflow": {
                "id": workflow["id"],
                "display_name": workflow["display_name"],
                "risk_level": workflow["risk_level"],
                "assigned_role": workflow["assigned_role"],
                "review_required": workflow["review_required"],
            } if workflow else None,
            "checklist": checklist,
            "provider": {
                "name": generation.provider,
                "model": generation.model,
                "prompt_version": generation.prompt_version,
                "latency_ms": generation.latency_ms,
                "total_latency_ms": response_latency,
                "input_tokens": generation.input_tokens,
                "output_tokens": generation.output_tokens,
                "estimated_cost_usd": generation.estimated_cost_usd,
                "fallback_reason": generation.fallback_reason,
                "permitted_evidence_chunk_count": len(cited_evidence),
            },
            "performance": {
                "stage_timings_ms": timings,
                "retrieval_cache_hit": retrieval_cache_hit,
                "retrieval_cache": self.retrieval_cache.stats(),
                "corpus_generation": corpus_generation,
            },
            "privacy": {
                "pii_redactions": question_redaction.counts,
                "redaction_count": question_redaction.total,
                "network_provider_used": False,
                "credentials_required": False,
            },
            "access": {
                "user_id": user["id"],
                "role": user["role"],
                "restricted_candidates_excluded": retrieval["restricted_candidate_count"],
                "permission_sensitive_evidence_gap": retrieval["permission_gap_detected"],
                "permission_sensitive_term_count": len(retrieval["permission_gap_terms"]),
            },
        }

        if persist:
            stage = time.perf_counter()
            query_id = self.db.record_query(
                {
                    "user_id": user_id,
                    "question_redacted": question_redaction.text,
                    "provider": generation.provider,
                    "model": generation.model,
                    "prompt_version": generation.prompt_version,
                    "confidence": confidence["score"],
                    "confidence_label": confidence["label"],
                    "insufficient_evidence": confidence["insufficient_evidence"],
                    "latency_ms": response_latency,
                    "input_tokens": generation.input_tokens,
                    "output_tokens": generation.output_tokens,
                    "estimated_cost_usd": generation.estimated_cost_usd,
                    "citation_count": len(citations),
                    "pii_redaction_count": question_redaction.total,
                    "response": response,
                }
            )
            response["query_run_id"] = query_id
            self.db.append_audit(
                actor=user_id,
                event_type="question_answered",
                entity_type="query_run",
                entity_id=query_id,
                payload={
                    "provider": generation.provider,
                    "model": generation.model,
                    "confidence": confidence["score"],
                    "insufficient_evidence": confidence["insufficient_evidence"],
                    "citation_count": len(citations),
                    "workflow": workflow["id"] if workflow else None,
                    "pii_redaction_count": question_redaction.total,
                    "restricted_candidates_excluded": retrieval["restricted_candidate_count"],
                    "permission_sensitive_evidence_gap": retrieval["permission_gap_detected"],
                    "retrieval_cache_hit": retrieval_cache_hit,
                    "corpus_generation": corpus_generation,
                },
            )
            timings["persist"] = round((time.perf_counter() - stage) * 1000)
            response["performance"]["request_total_ms"] = round((time.perf_counter() - overall_start) * 1000)
        else:
            response["performance"]["request_total_ms"] = response_latency
        return response

    def list_reviews(self, user_id: str) -> list[dict[str, Any]]:
        user = self.get_user(user_id)
        reviews = self.db.list_reviews()
        visible: list[dict[str, Any]] = []
        for review in reviews:
            if user["role"] != "admin" and not (
                review["created_by"] == user_id or review["assigned_role"] == user["role"]
            ):
                continue
            filtered = dict(review)
            if user["role"] != "admin":
                permitted_evidence = []
                for citation in review.get("evidence", []):
                    document = self.db.get_document(citation.get("document_id", ""))
                    if document and user["role"] in document.get("allowed_roles", []):
                        permitted_evidence.append(citation)
                filtered["evidence"] = permitted_evidence
            visible.append(filtered)
        return visible

    def create_review_from_query(self, query_run_id: str, user_id: str) -> dict[str, Any]:
        user = self.get_user(user_id)
        query = self.db.get_query(query_run_id)
        if not query:
            raise ValueError("Query run not found")
        if user["role"] != "admin" and query["user_id"] != user_id:
            raise PermissionError("A review may only be created from your own governed answer")
        response = query["response"]
        workflow = response.get("workflow")
        if not workflow or not workflow.get("review_required"):
            raise ValueError("This answer does not require a governed review workflow")
        review_id = self.db.create_review(
            {
                "created_by": user_id,
                "assigned_role": workflow["assigned_role"],
                "workflow_type": workflow["id"],
                "title": f"{workflow['display_name']} — review request",
                "risk_level": workflow["risk_level"],
                "question_redacted": query["question_redacted"],
                "checklist": response.get("checklist", []),
                "evidence": response.get("citations", []),
            }
        )
        self.db.append_audit(
            actor=user_id,
            event_type="review_created",
            entity_type="review",
            entity_id=review_id,
            payload={
                "query_run_id": query_run_id,
                "workflow": workflow["id"],
                "assigned_role": workflow["assigned_role"],
                "risk_level": workflow["risk_level"],
            },
        )
        return {"review_id": review_id, "status": "pending_review", "created_by": user["display_name"]}

    def update_review(self, review_id: str, user_id: str, status: str, decision_note: str | None) -> dict[str, Any]:
        user = self.get_user(user_id)
        if not user.get("can_review"):
            raise PermissionError("This user does not have review authority")
        review = self.db.get_review(review_id)
        if not review:
            raise ValueError("Review not found")
        if user["role"] != "admin" and review["assigned_role"] != user["role"]:
            raise PermissionError("This review is assigned to a different reviewer role")
        note_redaction = redact_pii(decision_note or "")
        if not self.db.update_review(review_id, status, note_redaction.text or None):
            raise ValueError("Review not found")
        self.db.append_audit(
            actor=user_id,
            event_type="review_status_changed",
            entity_type="review",
            entity_id=review_id,
            payload={
                "status": status,
                "decision_note_present": bool(note_redaction.text),
                "pii_redaction_count": note_redaction.total,
            },
        )
        return {"review_id": review_id, "status": status}

    def record_feedback(self, query_run_id: str, user_id: str, rating: int, correction: str | None) -> dict[str, Any]:
        user = self.get_user(user_id)
        query = self.db.get_query(query_run_id)
        if not query:
            raise ValueError("Query run not found")
        if user["role"] != "admin" and query["user_id"] != user_id:
            raise PermissionError("Feedback may only be recorded for your own governed answer")
        correction_redaction = redact_pii(correction or "")
        feedback_id = self.db.record_feedback(
            {
                "query_run_id": query_run_id,
                "user_id": user_id,
                "rating": rating,
                "correction_redacted": correction_redaction.text or None,
            }
        )
        self.db.append_audit(
            actor=user_id,
            event_type="answer_feedback_recorded",
            entity_type="feedback",
            entity_id=feedback_id,
            payload={
                "query_run_id": query_run_id,
                "rating": rating,
                "correction_submitted": bool(correction_redaction.text),
                "pii_redaction_count": correction_redaction.total,
            },
        )
        return {"feedback_id": feedback_id, "status": "open" if correction_redaction.text else "recorded"}
