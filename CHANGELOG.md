# Changelog

## 0.3.2 — 2026-08-31

- Added explicit `EXPORT_SUPPORT.bat` action entrypoint by user request.
- Kept support-export implementation centralized in `scripts/export20.py`; the new BAT only forwards to `PolicyNavigator.bat export`.
- Extended release-integrity launcher registry with explicit action-entrypoint mapping/validation.
- Removed `EXPORT_SUPPORT.bat` from retired/legacy-overlay treatment; `DOCTOR.bat` and `RUN_EVALUATIONS.bat` remain retired.
- Revalidated the exact v0.3.1 upload/sidecar/CRC and 67-test baseline before branching.

## 0.3.1 — 2026-08-31

- Reconciled Windows field output showing 77/77 integrity, exact runtime validation, schema-3 bootstrap, fallback-port recovery to 8766, Uvicorn startup, and HTTP 200 readiness before the browser requested retired `/assets/api.js` and `/assets/lineage.js`.
- Confirmed the active v0.3.0 `index.html` references only `/assets/styles.css` and `/assets/app.js`, isolating the field failure to stale local browser document state rather than missing active package assets.
- Added build-qualified browser launch URLs and no-store headers for the local HTML/static UI boundary.
- Version-qualified the active CSS/JavaScript references.
- Added logic-light compatibility recovery shims for the two exact field-observed stale asset paths; the active UI does not reference them.
- Added regression coverage that verifies every current local asset returns HTTP 200 and that stale asset requests self-recover instead of 404.
- Preserved the keyless recruiter-demo architecture, one active BAT, fail-closed release identity, non-destructive occupied-port fallback, schema-3 database foundation, and project-local diagnostics.

## 0.3.0 — 2026-08-31

- Reframed the active portfolio release as a zero-credential, local recruiter demonstration.
- Removed the external inference/provider call path and its runtime-only HTTP dependencies.
- Reduced supported local configuration to loopback host, port, and log level; unsupported provider/secret keys are ignored.
- Added a four-step recruiter quick tour covering grounded answers, permission-aware abstention, authorized restricted evidence, and deterministic evaluation.
- Added an Admin-only demo reset with an integrity-tested pre-reset database backup; user upload files are preserved.
- Added a bounded read-only local benchmark with cold/warm p50/p95 latency, stage timing, and retrieval-cache measurements.
- Advanced SQLite to schema version 3 and added indexes for documents, reviews, audit events, query history, feedback, and evaluation history.
- Preserved one active BAT, exact-hash legacy-overlay recovery, non-destructive port fallback, release identity, migration backups, cache invalidation, audit serialization, liveness/readiness, and Export20.
- Updated recruiter-facing copy and documentation to emphasize governance, verification, workflow, and reproducibility rather than model-provider setup.
- Renamed the active deterministic implementation/configuration paths to `app/answer_engine.py`, `config/engine_catalog.json`, and `config/answer_policy.json`; no legacy duplicate copies remain.
- Renamed the version-specific foundation regression file to `tests/test_foundation.py` and added API-level recruiter tour, benchmark, and backed-up reset coverage.
- Refreshed demo-reset status state after reseeding so the live status endpoint cannot report stale bootstrap metadata.
- Final exact-package gate found and fixed a saturated/non-HTTP listener edge case by checking bind ownership before attempting HTTP reuse classification.

## 0.2.2 — 2026-08-31

- Reconciled Windows logs showing v0.2.1 completed exact legacy-overlay repair, 75/75 release integrity, exact dependency validation, schema-2 database bootstrap, and then stopped solely because loopback port 8765 was occupied.
- Added bounded non-destructive loopback port recovery: reuse an already-ready identical build, otherwise select the first free nearby port for this run without terminating any process or rewriting `GKA_PORT`.
- Added compatibility probing for older Policy Navigator `/api/status` endpoints when classifying an occupied requested port.
- Passed the resolved host/port to the child server through process-local environment overrides so the application and readiness probe cannot diverge.
- Added selected/requested port metadata to readiness status evidence.
- Stopped treating exhausted local-port availability as a Critical crash condition; it now records normal launcher evidence without generating an automatic Export20.
- Added regression coverage for exact-build reuse, generic port collision fallback, different-release fallback, and bounded fallback exhaustion.
- Updated runtime/fallback/package identity to `PP-GKWA-0.2.2-B20260831-PORTRECOVERY1`.

## 0.2.1 — 2026-08-31

- Reconciled Windows Export20 evidence showing 0.2.0 verified all 75 managed files before failing on exact older 0.1.x overlay leftovers.
- Added reversible exact-hash legacy-overlay archival for preserved `DOCTOR.bat`, `RUN_EVALUATIONS.bat`, `EXPORT_SUPPORT.bat`, and the 0.1.2 `FIELD_REPAIR_REPORT.md`.
- Added repair receipts under project-local `backups/legacy_overlay`; no known leftover is deleted.
- Preserved fail-closed behavior for modified, symlinked, unknown, or otherwise unlisted files.
- Added field-overlay regression coverage and retained one active `PolicyNavigator.bat`.
- Updated runtime/fallback/package identity to `PP-GKWA-0.2.1-B20260831-OVERLAYRECOVERY1`.

## 0.2.0 — 2026-08-29

- Aligned the exact v0.1.2 source with Gateway shared project defaults v2.17.13 (source ZIP SHA-256 `63bda0b5f61ba44f18f55c5b75512085ed3a2fe67c575e3406a5877ecd5f4566`).
- Consolidated Windows actions onto the single canonical `PolicyNavigator.bat`; retired the three historical utility BAT filenames from the active package and added launcher-registry fail-closed self-tests.
- Added package-ID agreement to runtime identity and stopped globally exempting unlisted ZIP files from the managed-file gate.
- Added SQLite schema version 2, pre-migration verified backups, WAL/busy-timeout/foreign-key health, atomic migration transaction, online backup/restore verification, streaming backup hashing, and bounded program-created backup retention.
- Added incremental ingestion fingerprints plus corpus-generation invalidation.
- Added a bounded role/corpus-scoped deep-copy retrieval LRU cache and stage timing.
- Added explicit optional-provider timeouts, bounded transient retry, circuit breaker, and strict citation-set validation with governed local fallback.
- Serialized hash-chain appends across independent SQLite connections with `BEGIN IMMEDIATE`.
- Added separate liveness/readiness endpoints and moved blocking API work to the thread pool.
- Reused the server's already-completed integrity/settings result during FastAPI construction, removing a redundant third managed-file hash pass from canonical startup.
- Hardened Export20 process/thread locking with owner tokens and non-owner deletion protection; launcher consolidation evidence is read from release metadata instead of duplicated constants.
- Expanded regression coverage for clean database creation/migration/backup/restore, incremental ingestion, cache scoping/invalidation, provider failures, concurrent audit append, Export20 lock ownership, unlisted ZIP rejection, package-ID mismatch, retired-launcher return, and health endpoints.
- Removed a fresh-install schema defect found during release-gate review (duplicate `provider` column declaration) before packaging.

## 0.1.2 — 2026-08-28

Windows field repair and integrity hardening.

- Accepted the exact legacy root `.env` as mutable compatibility configuration after full immutable release verification; retained `local\.env` as the preferred location and precedence authority.
- Added visible `local` and `local\uploads` workspace placeholders.
- Limited local environment loading to supported application keys and rejected symlinked env files.
- Corrected mutable-directory classification so only intended top-level runtime directories are excluded; nested package code remains managed.
- Added canonical path, Windows-invalid/reserved-name, size, SHA-256 metadata, duplicate, case-collision, and symlink enforcement to release verification.
- Kept `.env.py` and other `.env.*` files outside the compatibility exception.
- Aligned the dependency-free emergency capsule version/build with release controls and added regression coverage.
- Added field-repair evidence to bounded diagnostics.
- Corrected the dated standard short-context GPT-5.6 Luna cost catalog and added estimator coverage.
- Added Windows field evidence, recovery, and promotion documentation.

## 0.1.1 — 2026-08-28

Launcher visibility and Windows startup repair.

- Replaced multi-stage BAT implementation with one minimal canonical `PolicyNavigator.bat`; Doctor, Evaluations, and Export BATs are logic-free forwarders.
- Converted all BAT files to ASCII with CRLF line endings for predictable `cmd.exe` parsing.
- Removed the invalid Unix-style `\"` browser quoting from the Windows command path.
- Moved hashing, runtime creation, dependency validation, bootstrap dispatch, health polling, browser opening, and failure reporting into one standard-library Python launcher.
- Added Python 3.11–3.14 discovery with a preference for the previously verified Python 3.13 runtime and common per-user install locations.
- Added persistent `launcher_latest.log` and `LATEST_LAUNCH_STATUS.txt`; every nonzero path now pauses instead of disappearing.
- Added incomplete-runtime preservation/repair, exact locked-version/import validation, path-length warnings, and non-destructive port-conflict handling.
- Changed the ZIP root directory to the shorter `PolicyNavigator` execution folder to reduce Windows path-length risk while preserving the professional display/project names.
- Added launcher regression tests for BAT encoding/forwarding, exact dependency probing, and non-secret host/port discovery.

## 0.1.0 — 2026-08-28

Initial runnable portfolio MVP.

- Added a Windows-first root-relative launcher and project-local runtime.
- Added fail-closed release identity and managed-file verification.
- Added Markdown, text, PDF, and DOCX ingestion with bounded extraction, DOCX table support, metadata validation, and no silent overwrite of same-named uploaded files.
- Added SQLite/FTS5 indexing and role-aware retrieval.
- Added a permission-sensitive topic-gap guard, normalized hyphenated concepts, and a shared relevance boundary so broad accessible policy text cannot answer around protected details or appear as weak citations.
- Added current, draft, expired, and superseded authority analysis with control-difference warnings.
- Added confidence, explicit abstention, evidence citations, and a vendor-approval checklist.
- Added a controlled human review queue with creator/assigned-role visibility, evidence re-filtering, assigned-role decision authority, inline notes, and one terse confirmation for consequential decisions.
- Added deterministic generation and an optional OpenAI Responses/Structured Outputs adapter with untrusted-document boundaries, disabled response storage, bounded output, and validated source identifiers.
- Added prompt/model history, latency/token/cost metrics, PII redaction, inline feedback and correction capture, and hash-chained audit logging.
- Added a deterministic golden-question evaluation suite.
- Added a bounded Critical-error crash capsule and Export20 diagnostics using cached identity evidence, redacted traces, cooldown suppression, same-computer locking, size/time limits, integrity-tested atomic ZIP finalization, and no error-path managed-file rehash.
- Added a standard-library fallback for settings or startup failures before the rich collector is ready, then consolidated bootstrap and server behavior into one implementation.
- Enforced loopback-only server binding and bounded port/log-level validation for the unauthenticated local release.
- Added a compact SBOM, separated runtime/development locks, a proprietary first-party license notice, documentation, tests, and a portfolio case study.
- Added browser-runtime verification and repaired the metrics refresh regression found during visual testing.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
