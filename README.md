# Policy and Procedure Navigator

**Evidence-grounded policy answers with permission-aware retrieval and controlled workflows.**

Policy and Procedure Navigator shows how an organization can make knowledge assistance trustworthy rather than merely conversational. It uses fictional policies and users, runs entirely on the local computer, needs no credentials or external service, and produces answers only from permitted evidence.

Version **0.3.2** · build `PP-GKWA-0.3.2-B20260831-EXPORTENTRY1`

**Launch prerequisite:** Python 3.11 or newer. On a fresh computer, the first launch may need ordinary package-network access to install the exact locked runtime dependencies; no model/API credential is needed.

## Three-minute walkthrough

Double-click `PolicyNavigator.bat`. The home screen includes a four-step **3-minute recruiter tour**:

1. **Grounded answer** — ask what approvals are required before engaging a vendor and see citations plus a controlled checklist.
2. **Permission boundary** — ask an employee for restricted penetration-testing details and watch the application abstain without leaking the restricted source.
3. **Authorized view** — repeat the question as Security and see the permitted restricted evidence.
4. **Reliability proof** — run the deterministic golden evaluation suite.

The Evaluations view also includes a bounded **local performance benchmark** showing warm p50/p95 latency and retrieval-cache behavior on the current computer. It does not persist benchmark questions or use the network.

## What it demonstrates

- Permission-aware document retrieval before answering.
- Evidence-linked citations and explicit insufficient-evidence behavior.
- Current/draft/expired/superseded authority analysis.
- Human-review workflows for consequential recommendations.
- PII redaction before retrieval and audit storage.
- Deterministic golden evaluations for authorization, citations, abstention, workflow routing, authority warnings, and redaction.
- Tamper-evident hash-chained audit records.
- Incremental document ingestion and role/corpus-scoped retrieval caching.
- SQLite WAL persistence, integrity-tested backups, migration backups, and schema-3 query/list indexes.
- Separate liveness and readiness checks.
- One canonical Windows launcher plus one logic-free Export20 convenience BAT; older-folder overlay recovery and local-port fallback remain non-destructive.
- Project-local bounded Export20 diagnostics.
- OpenAPI documentation at `/api/docs`.

## Keyless by design

Release 0.3.2 preserves the v0.3.1 keyless design and intentionally removes the external model/provider path from the active portfolio build. There is no API key setup, no cloud account requirement, and no external inference cost.

The only supported local settings are:

```text
GKA_HOST=127.0.0.1
GKA_PORT=8765
GKA_LOG_LEVEL=INFO
```

`local\.env` is preferred. The exact root `.env` remains a compatibility location for older field installations, but unsupported secret/provider settings are ignored.

## Windows entrypoints

The canonical launcher remains:

```text
PolicyNavigator.bat
```

Supported canonical actions:

```text
PolicyNavigator.bat start
PolicyNavigator.bat doctor
PolicyNavigator.bat evaluations
PolicyNavigator.bat export
```

For easier support collection, v0.3.2 also includes one explicit action entrypoint:

```text
EXPORT_SUPPORT.bat
```

`EXPORT_SUPPORT.bat` contains no exporter logic; it forwards once to `PolicyNavigator.bat export`, which continues to dispatch to the single governed `scripts/export20.py` implementation. `DOCTOR.bat` and `RUN_EVALUATIONS.bat` remain retired. Exact known historical leftovers may be reversibly archived during upgrade recovery; modified or unknown files still fail closed.

## Browser freshness and upgrade recovery

The launcher opens a release-qualified local URL, and the server marks HTML/JavaScript/CSS responses `no-store`. This prevents an older browser document from surviving when a new release reuses the same loopback host and port. Two tiny compatibility recovery scripts exist only for the field-observed stale paths `/assets/api.js` and `/assets/lineage.js`; they redirect an old cached page to the current UI and are not referenced by the active interface.

## Stability foundation

- Release identity is verified before local settings are loaded.
- The launcher validates the exact locked runtime and repairs only its project-local virtual environment.
- An occupied preferred loopback port does not terminate another process: an identical ready build may be reused, otherwise a bounded nearby free port is selected for that run.
- SQLite uses WAL, a 15-second busy timeout, foreign keys, `synchronous=NORMAL`, and in-memory temporary storage.
- Schema version 3 adds indexes for document, review, audit, query, feedback, and evaluation list paths.
- Database migration and demo-reset operations create project-local integrity-tested backups first.
- Unchanged documents are not unnecessarily reindexed.
- Retrieval cache entries are scoped by role and corpus generation.
- Blocking file/database/evaluation/diagnostic work is kept off the async request loop.
- `/api/health/live` and `/api/health/ready` distinguish process life from operational readiness.

## Demo reset

The Demo Administrator view exposes **Reset demo**. It requires a terse confirmation, creates an integrity-tested database backup, resets generated database state to the bundled fictional sample, and preserves files under `local\uploads`.

## Project-local outputs

```text
.runtime\
local\
state\
logs\
temp\
exports\
diagnostics\
reports\
downloads\
backups\
```

The launcher derives the project root from its own location, not from the current working directory, Desktop, or Downloads.

## Production boundary

This is intentionally a trusted-local portfolio demonstration. Production deployment would require real identity/SSO, tenant isolation, managed persistence, formal records controls, malware/content scanning, enterprise deployment monitoring, API authentication/rate limits, and operational support controls. Those are deliberately not bundled into the recruiter demo because they would add setup friction without improving the local walkthrough.

See `QUICK_START.md`, `ARCHITECTURE.md`, `SECURITY_AND_LIMITATIONS.md`, `VERIFICATION_REPORT.md`, and `FILE_LEDGER.md` for implementation and verification detail.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
