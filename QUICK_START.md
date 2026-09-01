# Quick Start — Policy and Procedure Navigator 0.3.2

**Prerequisite:** Python 3.11 or newer. Python 3.13 is the current field-tested family. The first launch may need normal package-network access to install the exact locked Python dependencies; the demonstration itself is keyless and makes no external inference calls.

## Fastest recruiter demo

1. Extract the release to a stable folder, for example:

```text
C:\Bots\Portfolio\PolicyNavigator
```

2. Double-click:

```text
PolicyNavigator.bat
```

3. The launcher verifies the release, validates/repairs its project-local Python runtime, bootstraps the fictional sample database, starts on a safe loopback port, and opens the browser.

4. Use the **Recruiter quick tour** on the home screen. No API key or cloud account is required.

## Recommended 3-minute walkthrough

- Click **1 · Grounded answer**. Review the evidence-linked vendor approval checklist.
- Click **Create tracked review** to show controlled workflow initiation.
- Click **2 · Permission boundary**. The employee view should abstain from restricted Security detail.
- Click **3 · Authorized view**. The Security role should receive the permitted source.
- Click **4 · Reliability proof**. The deterministic evaluation suite should pass all bundled cases.
- Optionally click **Run local benchmark** to show measured p50/p95 performance with no network calls.

## Maintenance actions

The package has one canonical launcher plus one export-only convenience entrypoint:

```text
PolicyNavigator.bat doctor
PolicyNavigator.bat evaluations
PolicyNavigator.bat export
PolicyNavigator.bat start

EXPORT_SUPPORT.bat
```

Double-click `EXPORT_SUPPORT.bat` when you only need a redacted support package. It forwards to the same governed export action; there is no second exporter implementation.

## Port handling

If the preferred port is occupied, do not stop the other program. The launcher can reuse an already-ready identical build or choose a bounded nearby loopback port and open the actual selected URL.

## Browser/UI recovery

The launcher opens a release-qualified URL and the local UI is served with no-store headers. If an older browser tab had cached retired JavaScript names, the v0.3.2 compatibility shims redirect that stale document to the current interface instead of leaving a blank page. A normal refresh is safe; no browser cache clearing should be required.

## Demo reset

Select **Demo Administrator** to reveal **Reset demo**. The reset creates a verified database backup before rebuilding the fictional sample state. Files under `local\uploads` are preserved.

## Local configuration

No `.env` file is required. Optional settings:

```text
GKA_HOST=127.0.0.1
GKA_PORT=8765
GKA_LOG_LEVEL=INFO
```

Preferred location:

```text
local\.env
```

Unsupported credential/provider settings are ignored in this keyless release.

## Failure evidence

If startup stops, preserve:

```text
logs\launcher_latest.log
logs\LATEST_LAUNCH_STATUS.txt
```

and run either:

```text
EXPORT_SUPPORT.bat
```

or:

```text
PolicyNavigator.bat export
```

Do not modify `VERSION.txt`, `MANIFEST.json`, `MANIFEST.sha256`, or `PACKAGE_METADATA.json` to force a pass. Keep Norton, SmartScreen, and normal Windows protections enabled.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.
