from __future__ import annotations

from typing import Any

from .config import read_json


def load_workflows() -> list[dict[str, Any]]:
    return read_json("config/workflow_templates.json")["workflows"]


def select_workflow(question: str) -> dict[str, Any] | None:
    lowered = question.lower()
    for workflow in load_workflows():
        if any(trigger in lowered for trigger in workflow["triggers"]):
            return workflow
    return None


def build_checklist(workflow: dict[str, Any] | None, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not workflow:
        return []
    active = [item for item in evidence if item.get("status") == "active"]
    checklist: list[dict[str, Any]] = []
    for step in workflow["steps"]:
        source_ids: list[str] = []
        for index, item in enumerate(active, start=1):
            searchable = f"{item['title']} {item['section']} {item['content']}".lower()
            if any(term.lower() in searchable for term in step.get("evidence_terms", [])):
                source_ids.append(f"S{index}")
        checklist.append(
            {
                "id": step["id"],
                "title": step["title"],
                "condition": step["condition"],
                "status": "not_started",
                "source_ids": list(dict.fromkeys(source_ids))[:3],
                "human_verification_required": True,
            }
        )
    return checklist
