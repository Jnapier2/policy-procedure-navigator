# Architecture — Policy and Procedure Navigator 0.3.2

## System shape

```text
PolicyNavigator.bat
  -> scripts/windows_launcher.py
      -> fail-closed package identity
      -> project-local Python runtime validation/repair
      -> database bootstrap/migration
      -> safe loopback port selection
      -> scripts/run_server.py
          -> FastAPI application
              -> role authorization
              -> PII redaction
              -> SQLite FTS5 retrieval
              -> authority/conflict analysis
              -> deterministic evidence answer engine
              -> workflow/checklist generation
              -> query/audit persistence
```

The portfolio release is intentionally a single local application rather than a microservice system. The architecture favors inspectability, deterministic behavior, low startup friction, and strong governance boundaries.

## Trust boundaries

1. **Release boundary** — version, build, package ID, manifest sidecar, managed-file sizes/hashes, safe Windows paths, and launcher registry must agree before local configuration is loaded.
2. **Configuration boundary** — only loopback host, port, and log-level settings are accepted. Secret/provider settings are outside the supported configuration surface.
3. **Authorization boundary** — user role is applied before evidence is returned to the answer path.
4. **Evidence boundary** — only locally retrieved, permitted evidence can support an answer or checklist.
5. **Action boundary** — consequential recommendations become review cases; the answer path does not silently approve a workflow.
6. **Diagnostic boundary** — Critical diagnostics are bounded, redacted, project-local, and do not invoke network or repair actions.

## Keyless answer engine

`app/answer_engine.py` is the single active deterministic answer-synthesis implementation for the portfolio release. It selects concise evidence sentences or governed checklist items, cites locally assigned source identifiers, and abstains when current permitted evidence is inadequate. No network inference adapter is active or required.

## Persistence and concurrency

SQLite remains appropriate for the trusted-local portfolio workload:

- WAL journal mode.
- 15-second busy timeout.
- Foreign keys enabled.
- `synchronous=NORMAL`.
- In-memory temporary storage.
- `BEGIN IMMEDIATE` serialization for audit-chain appends.
- Schema version 3 indexes for document, review, audit, query, feedback, and evaluation list paths.
- SQLite backup API plus `quick_check` before backup publication.
- Project-local pre-migration and pre-demo-reset backups.

## Retrieval performance

- Source documents are fingerprinted; unchanged documents skip unnecessary reindexing.
- Corpus generation increments only when indexed content/governance metadata changes.
- Retrieval uses a bounded deep-copy LRU cache keyed by role, corpus generation, normalized question, limit, and authority mode.
- The bundled local benchmark clears the cache, measures cold requests, then measures bounded warm rounds without persisting the benchmark questions.

## API and UI

FastAPI provides the local API, static UI, OpenAPI docs, and separate liveness/readiness endpoints. Blocking database, parsing, evaluation, benchmark, reset, and diagnostic operations run in the thread pool rather than blocking the async event loop.

The landing view includes a four-step recruiter tour. This is presentation guidance only; it calls the same governed API used by ordinary interaction.

## Windows launcher

The package has one canonical launcher, `PolicyNavigator.bat`, plus one explicit export-only action entrypoint, `EXPORT_SUPPORT.bat`. Python orchestration remains centralized in `scripts/windows_launcher.py`; support-export implementation remains centralized in `scripts/export20.py`.

The launcher can:

- select a compatible local Python runtime;
- validate/rebuild only the project-local virtual environment;
- archive only exact known historical overlay leftovers, with a receipt, before the normal identity gate;
- reuse an already-ready identical local instance;
- select a bounded nearby loopback port when the preferred port is occupied without stopping the occupying process;
- preserve launcher logs/status and bounded failure evidence.

## Scale boundary

Do not add PostgreSQL, a vector service, distributed queues, or SSO merely to make the diagram larger. Those become appropriate only when a measured portfolio scenario needs production-scale concurrency, identity, tenant isolation, or corpus volume.

Copyright © 2026 Gateway Information Group LLC. All rights reserved.

## Local browser freshness boundary

The browser is a separate stateful runtime and can outlive an extracted application folder. To prevent old local HTML from referring to retired assets after an upgrade, the Windows launcher opens a build-qualified root URL, the server disables caching for `/` and `/assets/*`, and two field-proven legacy asset paths are logic-light recovery shims that redirect to the current build-qualified root. Current `index.html` references only `styles.css` and `app.js`; the legacy shims are not part of normal execution.

## Windows entrypoint topology

`PolicyNavigator.bat` is the canonical Windows launcher and owns Python discovery plus dispatch into `scripts/windows_launcher.py`. `EXPORT_SUPPORT.bat` is an explicit action-only forwarder requested for easier field support collection. It contains no Python, integrity, diagnostic, or ZIP logic and forwards once to `PolicyNavigator.bat export`. The authoritative export capability remains `scripts/export20.py` -> `app.diagnostics.build_export20`.

This preserves one implementation per capability while allowing one BAT/CMD name for the distinct export action. `DOCTOR.bat` and `RUN_EVALUATIONS.bat` remain retired.
