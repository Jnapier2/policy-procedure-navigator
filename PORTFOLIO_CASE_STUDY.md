# Portfolio Case Study — Governed Knowledge and Workflow Assistant

## Business problem

Organizations increasingly want fast answers from policies, procedures, contracts, and operational records, but a useful business system must also handle permissions, stale/conflicting guidance, evidence, review, and auditability.

## Demonstration solution

Policy and Procedure Navigator is a keyless local application using fictional vendor-governance documents and fictional employee roles. It demonstrates the governance layer around knowledge assistance rather than relying on a black-box chat interface.

A representative question is:

> What approvals are required before engaging a new vendor?

The application retrieves permitted documents, ranks active authority, identifies stale/conflicting guidance, produces a concise evidence-linked checklist, and lets the user create a tracked human-review case.

## Strong portfolio signals

- Permission-aware retrieval: an employee cannot retrieve restricted Security detail.
- Safe abstention: missing or inaccessible evidence produces an explicit insufficient-evidence result.
- Source evidence: material claims are tied to visible policy sections.
- Workflow control: consequential recommendations become review cases rather than silent automated approvals.
- Reliability evaluation: bundled golden questions validate authorization, citations, abstention, workflow routing, policy warnings, and redaction.
- Traceability: persisted actions are linked in a tamper-evident audit chain.
- Operational quality: release integrity, local diagnostics, backups, schema migration, cache invalidation, safe port recovery, and measured local latency are visible engineering concerns.

## Recruiter walkthrough

The landing page contains four one-click scenarios: grounded vendor approval, employee permission-boundary abstention, authorized Security evidence, and deterministic evaluation. A separate local benchmark reports warm p50/p95 latency without credentials or external services.

## Design decision: keyless demo

The local release intentionally avoids external inference credentials. That keeps the walkthrough reproducible, avoids account/setup friction, and makes the governance behavior itself the focus. A production implementation could integrate an approved model behind the same authorization, evidence, and action boundaries, but that infrastructure is outside the local demo.

## Skills demonstrated

Data governance, information architecture, retrieval, Python/FastAPI, SQLite/FTS5, authorization logic, audit design, workflow analysis, privacy redaction, evaluation design, Windows packaging, diagnostics, reliability engineering, and business-process translation.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
