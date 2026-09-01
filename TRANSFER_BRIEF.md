# Transfer Brief — Policy and Procedure Navigator

**Current candidate:** 0.3.2 / `PP-GKWA-0.3.2-B20260831-EXPORTENTRY1`  
**Operating baseline:** Gateway shared defaults v2.17.13

## Current direction

The user prioritized an easy portfolio/recruiter demo over external model setup. Version 0.3.2 preserves the v0.3.1 keyless/browser-recovery simplification and keeps the governance/business-analysis value while removing credential/provider friction from the active runtime.

## Preserved foundations

One canonical launcher plus one logic-free export action BAT, release integrity, project-local runtime/state, exact-hash overlay recovery, bounded port fallback, SQLite WAL/backups, permission-aware retrieval, corpus-scoped cache, human review, PII redaction, deterministic evaluations, audit chain, liveness/readiness, and Export20 remain.

## Current maintenance delta

- Added `EXPORT_SUPPORT.bat` as a root-relative, ASCII/CRLF action forwarder to `PolicyNavigator.bat export`.
- Kept `scripts/export20.py` as the only active support-export implementation.
- Extended launcher-registry integrity checks so action-specific BATs are explicit, managed, root-level, and mapped to a registered action.
- Preserved all v0.3.1 keyless recruiter-demo/UI-recovery foundations.

## Preserved v0.3.x foundations

- Four-step recruiter quick tour.
- Admin-only backed-up demo reset preserving `local/uploads`.
- Bounded local performance benchmark.
- Schema version 3 list/history indexes.
- Runtime dependency simplification; external inference HTTP client moved out of runtime and retained only for development TestClient support.
- Supported configuration reduced to host/port/log level.

## Rollback

Preserve exact v0.3.1 SHA-256 `9f560bdce55d3a5119bbb3b0fc6226b27a23802cc56b4ec49052fd82bc1f9560` until native Windows qualification of the exact v0.3.2 artifact. v0.1.2 remains the older Windows support-evidence rollback lineage.

## Next pass

If recruiter feedback indicates value, prioritize presentation improvements such as a recorded walkthrough or policy-version comparison. Do not add cloud/service complexity without a demonstrated portfolio benefit.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
