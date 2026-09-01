# Known-Good / Rollback State — Policy and Procedure Navigator

## Preserved rollback lineage

- **v0.1.2** — older Windows support-evidence rollback source. Exact release SHA-256: `ace1d77085506b018ad4db82bd8aff3faf987cc45c88f4a1e486c2ab8d79df73`.
- **v0.2.2** — port-recovery predecessor. Exact release SHA-256: `fe813201e76206a62e8f4e3e1fb8b06d46f4935a570a91cb9723a9e08447a2f5`.
- **v0.3.1** — exact-package-verified UI-recovery predecessor. Exact release SHA-256: `9f560bdce55d3a5119bbb3b0fc6226b27a23802cc56b4ec49052fd82bc1f9560`. Native browser rendering on the user machine was the remaining qualification gate before this maintenance branch.
- **v0.3.0** — keyless recruiter-demo predecessor. Exact release SHA-256: `035bedaf6d4b234dedc45c0fc0d64461ee3084fccb898845c62f686024e2f17e`. Windows field evidence reached 77/77 integrity, schema-3 bootstrap, safe fallback port 8766, Uvicorn readiness, and HTTP 200 readiness; the browser then requested stale retired assets `/assets/api.js` and `/assets/lineage.js`, so UI qualification was not complete.

## Current candidate

Policy and Procedure Navigator v0.3.2 / `PP-GKWA-0.3.2-B20260831-EXPORTENTRY1`.

This release preserves the v0.3.1 keyless/browser-recovery foundations and adds a requested logic-free `EXPORT_SUPPORT.bat` action entrypoint while keeping one authoritative exporter implementation.

## Promotion gate

Do not call v0.3.2 Windows known-good until the exact final ZIP is run on Windows with normal protections enabled and completes:

```text
PolicyNavigator.bat evaluations
PolicyNavigator.bat doctor
PolicyNavigator.bat export
PolicyNavigator.bat start
```

Acceptance includes 5/5 golden evaluations, Doctor ready, valid Export20, browser launch with no missing local assets, recruiter-tour scenarios, optional local benchmark, and clean shutdown. Preserve v0.3.1 as the immediate source rollback and v0.1.2 as the older Windows support-evidence lineage until then.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
