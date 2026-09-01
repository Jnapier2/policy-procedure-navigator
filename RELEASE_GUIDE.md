# Release Guide — Policy and Procedure Navigator

**Current release:** 0.3.2 / `PP-GKWA-0.3.2-B20260831-EXPORTENTRY1`

## Product direction

The current release prioritizes a fast, credential-free local demonstration of evidence-grounded answers, permission-aware retrieval, controlled workflows, human review, and repeatable evaluations.

## Release foundations

- One canonical launcher and one logic-free support-export action.
- Fail-closed release integrity and exact-hash recovery checks.
- Project-local runtime state, bounded port fallback, SQLite WAL mode, and backups.
- Corpus-scoped cache, PII redaction, deterministic evaluations, and a hash-chained audit trail.
- Bounded diagnostics with one authoritative Export20 implementation.

## Version 0.3.2 changes

- Added `EXPORT_SUPPORT.bat` as a root-relative, ASCII/CRLF action forwarder to `PolicyNavigator.bat export`.
- Kept `scripts/export20.py` as the only support-export implementation.
- Extended launcher-registry integrity checks so action-specific BAT files are explicit, managed, root-level, and mapped to registered actions.
- Preserved the keyless local experience and browser-recovery controls introduced in v0.3.1.

## Rollback

Preserve the exact v0.3.1 package until native Windows qualification of the exact v0.3.2 artifact. Do not mix managed files between versions; recover from a complete verified archive.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
