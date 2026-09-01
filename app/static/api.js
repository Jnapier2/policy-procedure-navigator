"use strict";
// v0.3.2 compatibility recovery for a stale locally cached pre-consolidation UI.
if (!window.__policyNavigatorUiRecovery) {
  window.__policyNavigatorUiRecovery = true;
  window.location.replace("/?build=PP-GKWA-0.3.2-B20260831-EXPORTENTRY1&recovery=legacy-api");
}
