# Release Notes — Policy and Procedure Navigator 0.3.2

**Build:** `PP-GKWA-0.3.2-B20260831-EXPORTENTRY1`  
**Baseline:** Gateway shared defaults v2.17.13  
**Mode:** keyless local recruiter demo

## Maintenance objective

Version 0.3.2 preserves the exact v0.3.1 UI-recovery/recruiter-demo foundation and adds the requested standalone support-export BAT without creating a second export implementation.

## Changes

- Added root `EXPORT_SUPPORT.bat` for simple double-click support collection.
- The BAT is ASCII/CRLF, root-relative, space-safe, and forwards exactly once to `PolicyNavigator.bat export`.
- `scripts/export20.py` remains the only active exporter backend.
- Extended launcher-registry integrity so action-specific BATs must be explicitly registered, managed, root-level BAT/CMD files mapped to a valid action.
- `DOCTOR.bat` and `RUN_EVALUATIONS.bat` remain retired.
- Removed `EXPORT_SUPPORT.bat` from legacy-overlay retirement handling because it is now a deliberate managed action entrypoint.
- Preserved keyless operation, browser cache recovery, occupied-port fallback, schema-3 persistence, deterministic evaluations, audit chain, and Export20 safety limits.

## Rollback

Preserve v0.3.1 SHA-256 `9f560bdce55d3a5119bbb3b0fc6226b27a23802cc56b4ec49052fd82bc1f9560` until this exact v0.3.2 package passes native Windows launch/export validation with normal protections enabled.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
