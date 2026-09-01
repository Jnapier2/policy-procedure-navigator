# Verification Report — Policy and Procedure Navigator 0.3.2

**Canonical project:** Professional Portfolio — Governed AI Knowledge & Workflow Assistant  
**Build:** `PP-GKWA-0.3.2-B20260831-EXPORTENTRY1`  
**Operating baseline:** Gateway shared defaults v2.17.13  
**Immediate source predecessor:** exact v0.3.1 ZIP SHA-256 `9f560bdce55d3a5119bbb3b0fc6226b27a23802cc56b4ec49052fd82bc1f9560`

## Maintenance objective

The v0.3.1 upload and sidecar were rechecked before branching: the sidecar matches the release ZIP, ZIP CRC is clean, the archive has one `PolicyNavigator/` root, and the unmodified v0.3.1 source passes the 67-test regression suite.

Version 0.3.2 adds the requested `EXPORT_SUPPORT.bat` without creating a second exporter implementation.

## Export entrypoint architecture

- `PolicyNavigator.bat` remains the canonical launcher and owns Python discovery plus governed dispatch.
- `EXPORT_SUPPORT.bat` is an explicit action entrypoint for the `export` action only.
- The forwarder is ASCII/CRLF, derives its root from `%~dp0`, and calls `PolicyNavigator.bat export` exactly once.
- It contains no Python invocation, ZIP logic, manifest logic, scanning, redaction, or export implementation.
- `scripts/export20.py` remains the only normal support-export backend and calls `app.diagnostics.build_export20`.
- The dependency-free fallback exporter in `scripts/launcher_failure_capsule.py` remains an intentionally isolated emergency boundary used only when the normal runtime cannot be trusted or started.
- `DOCTOR.bat` and `RUN_EVALUATIONS.bat` remain retired.

## Release-integrity controls

The launcher registry now supports explicit action-specific BAT/CMD entrypoints. Such files must be:

- explicitly mapped to a registered action;
- safe root-level BAT/CMD paths;
- included in the immutable managed-file manifest;
- distinct from retired launcher names.

Unknown or modified BAT/CMD files remain fail-closed.

## Source-freeze qualification

Before final archive assembly, the v0.3.2 source passes:

- automated pytest suite: **67/67 passed**;
- golden governed evaluation suite: **5/5 passed**, score **1.0**;
- release identity: **80/80 managed files** after manifest regeneration;
- launcher registry: **2 root BAT/CMD files with distinct roles**, one canonical launcher and one export-only action entrypoint;
- Python compilation for application/operational/test code;
- current UI asset completeness/no-store checks;
- stale-browser recovery checks;
- keyless recruiter overview, benchmark, backed-up demo reset, and governed answer paths;
- occupied-port fallback/exact-build reuse behavior;
- fail-closed release-identity behavior and bounded Export20 diagnostics.

## Structural expectations

The clean release contains **92 distribution files** and **80 immutable managed files** after generated runtime/test residue is removed. There are no exact duplicate non-placeholder files, case-colliding release paths, nested ZIP payloads, packaged bytecode, or symlinks.

The two BAT/CMD files are intentionally different capabilities at the entrypoint layer:

```text
PolicyNavigator.bat    canonical application launcher/dispatcher
EXPORT_SUPPORT.bat     logic-free export-action convenience forwarder
```

No model/API credential, cloud account, process termination, browser-security exception, Norton/SmartScreen exception, or second support-export implementation was added.

## Exact-archive gate

Because this report is itself managed, the exact archive SHA-256 and final fresh-extraction results are recorded in the external release receipt/full-scan report supplied beside the ZIP. The exact-package gate must re-run release identity, all 67 tests, 5/5 evaluations, Doctor, the governed export backend, archive CRC, duplicate/path scans, and post-run identity.

## Remaining physical-Windows gate

Do not label v0.3.2 Windows known-good until the exact final ZIP is run on Windows with Norton/SmartScreen and normal browser protections enabled, `PolicyNavigator.bat` renders the recruiter interface, and `EXPORT_SUPPORT.bat` creates a valid project-local redacted Export20 package.

Preserve v0.3.1 as the immediate rollback candidate and v0.1.2 as the older Windows support-evidence rollback lineage until field acceptance.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
