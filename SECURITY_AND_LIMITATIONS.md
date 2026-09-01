# Security and Limitations — Policy and Procedure Navigator 0.3.2

## Implemented safeguards

- Fail-closed immutable release identity before supported local settings are loaded.
- One canonical BAT/CMD launcher plus one explicit export-only convenience BAT; export logic remains single-implementation.
- Root-relative project-local runtime/state/output locations.
- Loopback-only HTTP service.
- Non-destructive occupied-port fallback; no unrelated process is terminated.
- Role filtering before evidence reaches the answer engine.
- Restricted-source permission-gap detection that can force abstention without exposing restricted text.
- Current/draft/expired/superseded authority checks.
- Evidence-linked answers and checklists.
- Common PII/secret-pattern redaction before retrieval and audit storage.
- Human review for consequential workflow decisions.
- Tamper-evident hash-chained audit events with cross-connection serialization.
- Bounded document parsing limits for text/PDF/DOCX.
- Exclusive upload storage so an existing user file is not overwritten.
- Integrity-tested project-local database backups.
- Safe demo reset that backs up generated database state and preserves `local/uploads`.
- Bounded, redacted Export20 diagnostics.

## Keyless/network boundary

The 0.3.2 portfolio application does not require or enable an external inference provider. Unsupported credential/provider settings in local `.env` files are ignored. The local benchmark also performs no network calls.

Normal first-run dependency installation may require package-network access if the locked Python packages are not already cached. Runtime policy answers themselves are local.

## Data boundary

The bundled content and identities are fictional demonstration data. Uploaded files remain local to the extracted project folder, but this is not a production document-management system.

## Deliberate non-capabilities

This package does not claim production-grade:

- SSO/SAML/OIDC or enterprise directory authorization;
- multi-tenant isolation;
- managed secrets;
- malware scanning/content-disarm;
- records retention/legal hold;
- enterprise backup infrastructure;
- API authentication/rate limiting;
- public internet deployment hardening;
- high-availability/distributed persistence.

## Demo reset

Reset is an Admin-only local demo action. It creates an integrity-tested database backup before rebuilding the bundled sample database. It does not delete user-uploaded source files or unknown files. The UI requires a terse confirmation before the reset request.

## Diagnostics

Critical diagnostic collection is bounded and project-local. It does not call network services, Drive, repair functions, or managed-file rehash operations in the Critical path. Normal operational conditions such as an exhausted fallback port range are not treated as Critical crashes.

## Windows qualification

Container verification does not replace native Windows/Norton qualification. Keep Norton, SmartScreen, and normal OS protections enabled. Do not change release metadata or weaken security controls to force startup.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.

## Local browser cache boundary

The local interface is intentionally served with no-store/no-cache headers and is opened using a build-qualified URL. This is a reliability control, not a browser-security bypass. Norton, SmartScreen, browser protections, and HTTPS-upgrade behavior remain untouched. Field-observed stale requests for `/assets/api.js` and `/assets/lineage.js` are handled only by local redirect shims to the current interface.
