# File Ledger — Policy and Procedure Navigator 0.3.2

**Canonical project:** Professional Portfolio — Governed AI Knowledge & Workflow Assistant  
**Build:** `PP-GKWA-0.3.2-B20260831-EXPORTENTRY1`  
**Clean distribution files:** **91**  
**Immutable managed files:** **79**  
**Active BAT/CMD entrypoints:** **1 (`PolicyNavigator.bat`)**

This ledger indexes every file intended to ship in the clean release tree. Runtime-created state/log/export/backup contents are not shipped; only their `.gitkeep` placeholders are included. `MANIFEST.json` and `MANIFEST.sha256` are release-control files generated after the managed-file inventory and are intentionally outside the list they authenticate.

## Cleanup and lineage

- The active package contains no duplicate launcher aliases. `PolicyNavigator.bat` is the single BAT/CMD entrypoint.
- v0.3.0 replaced `app/ai.py` with `app/answer_engine.py`, `config/model_catalog.json` with `config/engine_catalog.json`, `config/prompts.json` with `config/answer_policy.json`, and `tests/test_foundation_v020.py` with version-neutral `tests/test_foundation.py`; those predecessor copies remain absent.
- v0.3.1 adds two field-proven stale-browser recovery shims (`app/static/api.js` and `app/static/lineage.js`). They are not referenced by current HTML and exist only to redirect cached retired UI documents to the current build-qualified root.
- Known 0.1.x overlay leftovers remain recoverable only through the exact-path/size/SHA allowlist in the pre-trust launcher; unknown or modified files are not deleted or moved.
- Final exact-duplicate, function-overlap, case-collision, unsafe-path, archive, cache, and symlink results are recorded in the release scan report.

## Complete packaged-file index

| Path | Category | Purpose | Identity | Lineage |
|---|---|---|---|---|
| `.env.example` | Release control | Optional non-secret local host/port/log-level configuration example. | Managed immutable | Updated in 0.3.0 |
| `.gitignore` | Release control | Excludes generated runtime/mutable data, caches, and local environment files from source control. | Managed immutable | Carried from 0.2.2 |
| `ARCHITECTURE.md` | Documentation/legal | Current keyless single-process architecture, trust boundaries, persistence, performance, and scale boundary. | Managed immutable | Updated in 0.3.0 |
| `CHANGELOG.md` | Documentation/legal | Preserved release history and upgrade decisions. | Managed immutable | Updated in 0.3.0 |
| `FILE_LEDGER.md` | Documentation/legal | No-omission packaged-file capability and lineage inventory. | Managed immutable | Updated in 0.3.0 |
| `KNOWN_GOOD_STATE.md` | Documentation/legal | Rollback lineage, current candidate identity, and promotion boundary. | Managed immutable | Updated in 0.3.0 |
| `LICENSE.txt` | Documentation/legal | First-party proprietary license/copyright notice. | Managed immutable | Carried from 0.2.2 |
| `MANIFEST.json` | Release/dependency control | Generated immutable managed-file inventory with sizes and SHA-256 hashes. | Release control | Updated in 0.3.0 |
| `MANIFEST.sha256` | Release/dependency control | SHA-256 sidecar authenticating MANIFEST.json. | Release control | Updated in 0.3.0 |
| `PACKAGE_METADATA.json` | Release/dependency control | Canonical identity, launcher registry, output roots, and release lineage. | Managed immutable | Updated in 0.3.0 |
| `PORTFOLIO_CASE_STUDY.md` | Documentation/legal | Business outcomes, walkthrough, and design rationale. | Managed immutable | Updated in 0.3.0 |
| `PolicyNavigator.bat` | Windows entrypoint | Only active BAT/CMD entrypoint; discovers Python and dispatches the governed launcher. | Managed immutable | Updated in 0.3.0 |
| `EXPORT_SUPPORT.bat` | Operations/action entrypoint | Logic-free convenience forwarder to `PolicyNavigator.bat export`; contains no exporter logic. | Managed immutable | Added in 0.3.2 |
| `QUICK_START.md` | Documentation/legal | Minimal Windows launch, recruiter tour, reset, maintenance, and recovery guide. | Managed immutable | Updated in 0.3.0 |
| `README.md` | Documentation/legal | Primary product/recruiter-demo overview. | Managed immutable | Updated in 0.3.0 |
| `RELEASE_NOTES.md` | Documentation/legal | 0.3.0 simplification, capability, cleanup, and rollback summary. | Managed immutable | Updated in 0.3.0 |
| `ROADMAP.md` | Documentation/legal | Optional portfolio polish plus deliberately deferred production complexity. | Managed immutable | Updated in 0.3.0 |
| `SBOM.json` | Release/dependency control | CycloneDX dependency inventory separating runtime and development-only packages. | Managed immutable | Updated in 0.3.0 |
| `SECURITY_AND_LIMITATIONS.md` | Documentation/legal | Implemented safeguards, local/keyless boundary, and production limitations. | Managed immutable | Updated in 0.3.0 |
| `THIRD_PARTY_NOTICES.md` | Documentation/legal | Dependency license and redistribution notice. | Managed immutable | Carried from 0.2.2 |
| `RELEASE_GUIDE.md` | Documentation/legal | Current release direction, safeguards, and rollback guidance. | Managed immutable | Added in 0.3.2 |
| `VERIFICATION_REPORT.md` | Documentation/legal | Source-freeze qualification evidence and exact-artifact verification procedure. | Managed immutable | Updated in 0.3.0 |
| `VERSION.txt` | Release/dependency control | Canonical running release version. | Managed immutable | Updated in 0.3.0 |
| `app/__init__.py` | Application | Package/version/build constants used by release identity and API status. | Managed immutable | Updated in 0.3.0 |
| `app/answer_engine.py` | Application | Single deterministic evidence-only answer synthesis implementation; no network inference. | Managed immutable | Added/renamed in 0.3.0 |
| `app/benchmark.py` | Application | Bounded read-only local governed-answer benchmark. | Managed immutable | Added/renamed in 0.3.0 |
| `app/config.py` | Application | Loopback-only keyless setting allowlist and project-local paths. | Managed immutable | Updated in 0.3.0 |
| `app/database.py` | Application | SQLite schema/WAL policy, backup/restore, audit/history/metrics, and schema upgrades. | Managed immutable | Updated in 0.3.0 |
| `app/diagnostics.py` | Application | Logging, redaction, Critical capsule, and bounded integrity-tested Export20. | Managed immutable | Updated in 0.3.0 |
| `app/evals.py` | Application | Golden-question evaluation execution and scoring. | Managed immutable | Updated in 0.3.0 |
| `app/governance.py` | Application | Authority/conflict/expiry analysis and confidence/abstention logic. | Managed immutable | Carried from 0.2.2 |
| `app/ingest.py` | Application | Bounded text/PDF/DOCX ingestion, validation, PII-aware indexing, fingerprints, and safe upload storage. | Managed immutable | Carried from 0.2.2 |
| `app/integrity.py` | Application | Fail-closed release identity, path/hash/size and launcher registry enforcement. | Managed immutable | Carried from 0.2.2 |
| `app/main.py` | Application | FastAPI app, health/status, recruiter tour, benchmark/reset, document/workflow/feedback APIs, and no-store local UI cache boundary. | Managed immutable | Updated in 0.3.1 |
| `app/pii.py` | Application | Deterministic PII and secret-pattern redaction. | Managed immutable | Carried from 0.2.2 |
| `app/retrieval.py` | Application | Role-aware FTS retrieval and bounded role/corpus-scoped cache. | Managed immutable | Updated in 0.3.0 |
| `app/schemas.py` | Application | Validated request models and controlled review statuses. | Managed immutable | Carried from 0.2.2 |
| `app/seed.py` | Application | Bundled fictional-data bootstrap and backed-up demo reset. | Managed immutable | Updated in 0.3.0 |
| `app/service.py` | Application | Governed ask/workflow/feedback orchestration and stage timing. | Managed immutable | Updated in 0.3.0 |
| `app/static/api.js` | Frontend compatibility boundary | Logic-light field-proven stale-browser recovery shim for retired `/assets/api.js`; redirects to the current build-qualified UI. | Managed immutable | Added in 0.3.1 |
| `app/static/app.js` | Frontend | Recruiter-tour browser behavior and answer/review/evaluation/benchmark/reset interactions. | Managed immutable | Carried from 0.3.0 |
| `app/static/index.html` | Frontend | Single-page local recruiter-demo interface with version-qualified active asset URLs. | Managed immutable | Updated in 0.3.1 |
| `app/static/lineage.js` | Frontend compatibility boundary | Logic-light field-proven stale-browser recovery shim for retired `/assets/lineage.js`; redirects to the current build-qualified UI. | Managed immutable | Added in 0.3.1 |
| `app/static/styles.css` | Frontend | Responsive visual styling for recruiter exploration. | Managed immutable | Updated in 0.3.0 |
| `app/workflows.py` | Application | Workflow selection and evidence-linked checklist construction. | Managed immutable | Carried from 0.2.2 |
| `backups/.gitkeep` | Mutable workspace placeholder | Preserves an approved empty project-local mutable directory without shipping runtime data. | Mutable placeholder | Carried from 0.2.2 |
| `config/answer_policy.json` | Governance/demo configuration | Versioned deterministic answer-policy rules/history. | Managed immutable | Added/renamed in 0.3.0 |
| `config/demo_tour.json` | Governance/demo configuration | Four guided recruiter scenarios and expected demonstrations. | Managed immutable | Added/renamed in 0.3.0 |
| `config/engine_catalog.json` | Governance/demo configuration | Versioned zero-cost/no-network local engine metadata. | Managed immutable | Added/renamed in 0.3.0 |
| `config/users.json` | Governance/demo configuration | Fictional demo personas, roles, and review authority. | Managed immutable | Carried from 0.2.2 |
| `config/workflow_templates.json` | Governance/demo configuration | Controlled workflow and evidence checklist templates. | Managed immutable | Carried from 0.2.2 |
| `data/demo_documents/data_privacy_review_standard_v1_8.md` | Fictional demo evidence | Fictional sample policy/procedure evidence used by the recruiter demonstration. | Managed immutable | Carried from 0.2.2 |
| `data/demo_documents/emergency_purchasing_exception_v1_4.md` | Fictional demo evidence | Fictional sample policy/procedure evidence used by the recruiter demonstration. | Managed immutable | Carried from 0.2.2 |
| `data/demo_documents/procurement_intake_procedure_v5_0.md` | Fictional demo evidence | Fictional sample policy/procedure evidence used by the recruiter demonstration. | Managed immutable | Carried from 0.2.2 |
| `data/demo_documents/third_party_security_standard_v2_1.md` | Fictional demo evidence | Fictional sample policy/procedure evidence used by the recruiter demonstration. | Managed immutable | Carried from 0.2.2 |
| `data/demo_documents/travel_expense_policy_v1_0.md` | Fictional demo evidence | Fictional sample policy/procedure evidence used by the recruiter demonstration. | Managed immutable | Carried from 0.2.2 |
| `data/demo_documents/vendor_management_policy_v2_9_expired.md` | Fictional demo evidence | Fictional sample policy/procedure evidence used by the recruiter demonstration. | Managed immutable | Carried from 0.2.2 |
| `data/demo_documents/vendor_management_policy_v3_2.md` | Fictional demo evidence | Fictional sample policy/procedure evidence used by the recruiter demonstration. | Managed immutable | Carried from 0.2.2 |
| `data/demo_documents/vendor_quick_guide_draft.md` | Fictional demo evidence | Fictional sample policy/procedure evidence used by the recruiter demonstration. | Managed immutable | Carried from 0.2.2 |
| `diagnostics/capsules/.gitkeep` | Mutable workspace placeholder | Preserves an approved empty project-local mutable directory without shipping runtime data. | Mutable placeholder | Carried from 0.2.2 |
| `downloads/.gitkeep` | Mutable workspace placeholder | Preserves an approved empty project-local mutable directory without shipping runtime data. | Mutable placeholder | Carried from 0.2.2 |
| `evals/golden_questions.json` | Evaluation corpus | Five expected governance/authorization/abstention/redaction cases. | Managed immutable | Carried from 0.2.2 |
| `exports/.gitkeep` | Mutable workspace placeholder | Preserves an approved empty project-local mutable directory without shipping runtime data. | Mutable placeholder | Carried from 0.2.2 |
| `local/.gitkeep` | Mutable workspace placeholder | Preserves an approved empty project-local mutable directory without shipping runtime data. | Mutable placeholder | Carried from 0.2.2 |
| `local/uploads/.gitkeep` | Mutable workspace placeholder | Preserves an approved empty project-local mutable directory without shipping runtime data. | Mutable placeholder | Carried from 0.2.2 |
| `logs/.gitkeep` | Mutable workspace placeholder | Preserves an approved empty project-local mutable directory without shipping runtime data. | Mutable placeholder | Carried from 0.2.2 |
| `pyproject.toml` | Release/dependency control | Build metadata and direct runtime/development dependencies. | Managed immutable | Updated in 0.3.0 |
| `reports/.gitkeep` | Mutable workspace placeholder | Preserves an approved empty project-local mutable directory without shipping runtime data. | Mutable placeholder | Carried from 0.2.2 |
| `requirements-dev.lock.txt` | Release/dependency control | Exact development/test lock, not installed by normal launch. | Managed immutable | Updated in 0.3.0 |
| `requirements.lock.txt` | Release/dependency control | Exact minimal runtime dependency lock. | Managed immutable | Updated in 0.3.0 |
| `scripts/__init__.py` | Operations/release | Operations package marker. | Managed immutable | Carried from 0.2.2 |
| `scripts/bootstrap.py` | Operations/release | Database/bootstrap action backend. | Managed immutable | Carried from 0.2.2 |
| `scripts/build_manifest.py` | Operations/release | Release-time manifest generator. | Managed immutable | Carried from 0.2.2 |
| `scripts/doctor.py` | Operations/release | Identity/dependency/SQLite/database/audit readiness action. | Managed immutable | Carried from 0.2.2 |
| `scripts/export20.py` | Operations/release | Manual bounded support-export action. | Managed immutable | Carried from 0.2.2 |
| `scripts/launcher_failure_capsule.py` | Operations/release | Dependency-free early-startup capsule/Export20 fallback. | Managed immutable | Updated in 0.3.0 |
| `scripts/run_evaluations.py` | Operations/release | Golden evaluation action backend. | Managed immutable | Carried from 0.2.2 |
| `scripts/run_server.py` | Operations/release | Canonical loopback Uvicorn server backend. | Managed immutable | Carried from 0.2.2 |
| `scripts/verify_release.py` | Operations/release | Standalone release-identity verifier. | Managed immutable | Carried from 0.2.2 |
| `scripts/windows_launcher.py` | Operations/release | Substantive Windows bootstrap/runtime/identity/overlay/port/readiness dispatcher with build-qualified browser launch URLs. | Managed immutable | Updated in 0.3.1 |
| `state/.gitkeep` | Mutable workspace placeholder | Preserves an approved empty project-local mutable directory without shipping runtime data. | Mutable placeholder | Carried from 0.2.2 |
| `temp/.gitkeep` | Mutable workspace placeholder | Preserves an approved empty project-local mutable directory without shipping runtime data. | Mutable placeholder | Carried from 0.2.2 |
| `tests/conftest.py` | Verification | Automated release regression coverage for conftest. | Managed immutable | Updated in 0.3.0 |
| `tests/test_api_health.py` | Verification | API plus frontend-asset completeness/no-store/stale-path recovery regression coverage. | Managed immutable | Updated in 0.3.1 |
| `tests/test_evaluations_and_diagnostics.py` | Verification | Automated release regression coverage for evaluations and diagnostics. | Managed immutable | Updated in 0.3.0 |
| `tests/test_foundation.py` | Verification | Automated release regression coverage for foundation. | Managed immutable | Added/renamed in 0.3.0 |
| `tests/test_governance.py` | Verification | Automated release regression coverage for governance. | Managed immutable | Carried from 0.2.2 |
| `tests/test_ingestion_validation.py` | Verification | Automated release regression coverage for ingestion validation. | Managed immutable | Carried from 0.2.2 |
| `tests/test_local_config.py` | Verification | Automated release regression coverage for local config. | Managed immutable | Updated in 0.3.0 |
| `tests/test_privacy_and_workflow.py` | Verification | Automated release regression coverage for privacy and workflow. | Managed immutable | Carried from 0.2.2 |
| `tests/test_release_integrity.py` | Verification | Automated release regression coverage for release integrity. | Managed immutable | Updated in 0.3.0 |
| `tests/test_windows_launcher.py` | Verification | Windows launcher, port recovery, overlay recovery, and build-qualified browser URL regression coverage. | Managed immutable | Updated in 0.3.1 |

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
