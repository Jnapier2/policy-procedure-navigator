# Public Source Inventory — Policy and Procedure Navigator 0.3.2

The current public source identifies its immutable managed files in [MANIFEST.json](MANIFEST.json), including each relative path, byte size, and SHA-256. [MANIFEST.sha256](MANIFEST.sha256) records the manifest digest. These files are the authoritative current inventory; historical distribution counts describe their original archives.

## Entrypoints and implementation

- PolicyNavigator.bat is the canonical Windows launcher. It discovers Python and dispatches the registered application and maintenance actions.
- EXPORT_SUPPORT.bat is a separate export-only action entrypoint. It forwards once to PolicyNavigator.bat export and contains no exporter logic.
- scripts/windows_launcher.py implements governed startup and dispatch; scripts/export20.py calls the normal support-export implementation.
- DOCTOR.bat and RUN_EVALUATIONS.bat remain retired. Unknown or modified files do not become approved launchers.

The launcher registry and action mapping are recorded in [PACKAGE_METADATA.json](PACKAGE_METADATA.json). The two approved BAT files have distinct roles, not two application implementations.

## Inventory boundaries

The managed inventory covers application code, bundled fictional policies, configuration examples, runtime and test dependency locks, tests, documentation, rights notices, and release verification tools. The manifest and its checksum are release-control records outside the payload they authenticate.

Generated runtime configuration, databases, logs, exports, diagnostics, caches, and backups are excluded from the immutable inventory. Their presence is not evidence of a new software release.

See [current capabilities and evaluation limits](ROADMAP.md), [third-party notices](THIRD_PARTY_NOTICES.md), and the [historical verification report](VERIFICATION_REPORT.md). Current source changes do not replace the checksums or acceptance records of earlier release archives.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
