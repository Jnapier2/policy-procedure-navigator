"use strict";

const state = {
  users: [],
  currentUser: "ava.employee",
  lastResponse: null,
  latestEvaluation: null,
  demoTour: null,
  benchmark: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message, isError = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.add("hidden"), 4200);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  let payload = null;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = { detail: text }; }
  if (!response.ok) {
    throw new Error(payload?.detail || `Request failed (${response.status})`);
  }
  return payload;
}

function currentUser() {
  return state.users.find((user) => user.id === state.currentUser) || state.users[0];
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: value.includes("T") ? "short" : undefined }).format(date);
}

function formatAnswer(answer) {
  const safe = escapeHtml(answer);
  const withSources = safe.replace(/\[S(\d+)\]/g, '<span class="source-ref">S$1</span>');
  const lines = withSources.split("\n").filter((line) => line.trim());
  const bulletLines = lines.filter((line) => /^-\s/.test(line));
  if (bulletLines.length && bulletLines.length === lines.length - (lines[0]?.startsWith("-") ? 0 : 1)) {
    const intro = lines[0]?.startsWith("-") ? "" : `<p>${lines.shift()}</p>`;
    return `${intro}<ul>${lines.map((line) => `<li>${line.replace(/^-\s*/, "")}</li>`).join("")}</ul>`;
  }
  return lines.map((line) => `<p>${line}</p>`).join("");
}

function navigate(viewName) {
  $$(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.view === viewName));
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${viewName}`));
  const titles = {
    ask: "Policy and Procedure Navigator",
    documents: "Governed document library",
    reviews: "Human review queue",
    evaluations: "Reliability evaluation suite",
    audit: "Tamper-evident audit log",
  };
  $("#pageTitle").textContent = titles[viewName] || "Policy and Procedure Navigator";
  if (viewName === "documents") loadDocuments();
  if (viewName === "reviews") loadReviews();
  if (viewName === "evaluations") loadLatestEvaluation();
  if (viewName === "audit") loadAudit();
}

async function loadStatus() {
  const status = await api("/api/status");
  const ok = status.integrity?.ok;
  $("#integrityDot").className = `status-dot ${ok ? "ok" : "bad"}`;
  $("#integrityText").textContent = ok ? "Release verified" : "Integrity failure";
  $("#providerMode").textContent = status.keyless ? "Keyless local evidence · no external services" : "Local governed evidence mode";
  renderMetrics(status.metrics);
  return status;
}

function renderMetrics(metrics) {
  $("#metricDocuments").textContent = metrics.documents ?? "—";
  $("#metricQueries").textContent = metrics.queries ?? "—";
  $("#metricReviews").textContent = metrics.pending_reviews ?? "—";
  $("#metricEval").textContent = metrics.latest_eval_score == null ? "Not run" : `${Math.round(metrics.latest_eval_score * 100)}%`;
}

async function loadUsers() {
  state.users = await api("/api/users");
  const select = $("#userSelect");
  select.innerHTML = state.users.map((user) => `<option value="${escapeHtml(user.id)}">${escapeHtml(user.display_name)} · ${escapeHtml(user.role)}</option>`).join("");
  select.value = state.currentUser;
  updateUserDependentUI();
}

async function loadDemoOverview() {
  const overview = await api("/api/demo/overview");
  state.demoTour = overview.tour;
  const proof = overview.proof;
  $("#demoProofChips").innerHTML = [
    "Keyless / $0 API cost",
    `${proof.documents} fictional documents`,
    proof.audit_chain_ok ? "Audit chain verified" : "Audit check needed",
    proof.latest_eval_score == null ? "Golden suite ready" : `${Math.round(proof.latest_eval_score * 100)}% eval score`,
  ].map((value) => `<span class="mini-pill">${escapeHtml(value)}</span>`).join("");
}

async function runDemoStep(stepId) {
  const step = state.demoTour?.steps?.find((item) => item.id === stepId);
  if (!step) return;
  state.currentUser = step.user_id;
  $("#userSelect").value = state.currentUser;
  updateUserDependentUI();
  if (step.action === "evaluations") {
    navigate("evaluations");
    await runEvaluationSuite();
    return;
  }
  navigate("ask");
  $("#questionInput").value = step.question;
  await submitQuestion({ preventDefault() {} });
}

async function resetDemo() {
  if (!window.confirm("Action? [Y/N]")) return;
  const button = $("#resetDemoButton");
  button.disabled = true;
  button.textContent = "Resetting…";
  try {
    const result = await api(`/api/demo/reset?user_id=${encodeURIComponent(state.currentUser)}`, { method: "POST" });
    state.lastResponse = null;
    state.latestEvaluation = null;
    $("#resultWrap").classList.add("hidden");
    showToast(result.backup?.ok ? "Demo reset. Previous database preserved in backups." : "Demo reset to bundled sample state.");
    await Promise.all([loadStatus(), loadDemoOverview(), loadLatestEvaluation()]);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Reset demo";
  }
}

function updateUserDependentUI() {
  const user = currentUser();
  if (!user) return;
  $("#uploadPanel").classList.toggle("hidden", user.role !== "admin");
  const auditNav = document.querySelector('[data-view="audit"]');
  if (auditNav) auditNav.classList.toggle("hidden", user.role !== "admin");
  $("#runEvaluations").disabled = !user.can_review;
  $("#resetDemoButton").classList.toggle("hidden", user.role !== "admin");
  if (user.role !== "admin" && $("#view-audit").classList.contains("active")) navigate("ask");
}

function setAskLoading(loading) {
  const button = $("#askButton");
  button.disabled = loading;
  button.textContent = loading ? "Retrieving and verifying…" : "Find governed answer";
  $("#askForm").classList.toggle("loading", loading);
}

async function submitQuestion(event) {
  event.preventDefault();
  const question = $("#questionInput").value.trim();
  if (!question) return;
  setAskLoading(true);
  try {
    const response = await api("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question, user_id: state.currentUser }),
    });
    state.lastResponse = response;
    renderAnswer(response);
    await refreshMetrics();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setAskLoading(false);
  }
}

function renderAnswer(response) {
  $("#resultWrap").classList.remove("hidden");
  const score = Number(response.confidence.score || 0);
  $("#confidenceRing").style.setProperty("--score", `${Math.round(score * 360)}deg`);
  $("#confidenceValue").textContent = `${Math.round(score * 100)}%`;
  $("#confidenceLabel").textContent = `${response.confidence.label[0].toUpperCase()}${response.confidence.label.slice(1)} confidence`;
  $("#confidenceReason").textContent = response.confidence.reasons?.[0] || "Evidence assessed";
  $("#answerBody").innerHTML = formatAnswer(response.answer);
  $("#providerPill").textContent = "Keyless local evidence";
  $("#latencyText").textContent = `${response.provider.total_latency_ms} ms`;
  $("#costText").textContent = "$0 API cost";

  const fallback = $("#fallbackNotice");
  if (response.provider.fallback_reason) {
    fallback.textContent = response.provider.fallback_reason;
    fallback.classList.remove("hidden");
  } else {
    fallback.classList.add("hidden");
  }

  const warnings = [
    ...(response.authority.conflicts || []).map((item) => ({ ...item, severity: "high" })),
    ...(response.authority.warnings || []),
  ];
  $("#authorityWarnings").innerHTML = warnings.map((warning) => `<div class="warning-item ${warning.severity === "high" ? "high" : ""}">${escapeHtml(warning.message)}</div>`).join("");

  $("#citationCount").textContent = response.citations.length;
  $("#citationList").innerHTML = response.citations.length ? response.citations.map((citation) => `
    <article class="citation">
      <div class="citation-top"><h4><span class="source-ref">${escapeHtml(citation.source_id)}</span> ${escapeHtml(citation.title)}</h4><span class="status-pill ${escapeHtml(citation.status)}">${escapeHtml(citation.status)}</span></div>
      <p><strong>${escapeHtml(citation.section)}</strong><br>${escapeHtml(citation.excerpt)}${citation.excerpt.length >= 520 ? "…" : ""}</p>
      <div class="citation-meta">
        <span class="mini-pill">v${escapeHtml(citation.version)}</span>
        <span class="mini-pill">${escapeHtml(citation.classification)}</span>
        <span class="mini-pill">effective ${escapeHtml(citation.effective_date || "unspecified")}</span>
      </div>
    </article>
  `).join("") : `<div class="empty-state">No source was strong enough to support a definitive answer.</div>`;

  const checklistCard = $("#checklistCard");
  if (response.workflow && response.checklist.length) {
    checklistCard.classList.remove("hidden");
    $("#workflowTitle").textContent = response.workflow.display_name;
    $("#createReviewButton").disabled = false;
    $("#createReviewButton").textContent = "Create tracked review";
    $("#checklistList").innerHTML = response.checklist.map((item) => `
      <div class="check-item">
        <span class="check-box" aria-hidden="true"></span>
        <div><strong>${escapeHtml(item.title)}</strong><small>${item.condition === "conditional" ? "Conditional control" : "Required control"} · Human verification required</small></div>
        <div>${(item.source_ids || []).map((source) => `<span class="source-ref">${escapeHtml(source)}</span>`).join("")}</div>
      </div>
    `).join("");
  } else {
    checklistCard.classList.add("hidden");
  }
  $("#resultWrap").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function createReview() {
  if (!state.lastResponse?.query_run_id) return;
  const button = $("#createReviewButton");
  button.disabled = true;
  button.textContent = "Creating…";
  try {
    const result = await api("/api/reviews", {
      method: "POST",
      body: JSON.stringify({ query_run_id: state.lastResponse.query_run_id, user_id: state.currentUser }),
    });
    button.textContent = `Created · ${result.status.replaceAll("_", " ")}`;
    showToast("Tracked human-review case created.");
    await refreshMetrics();
  } catch (error) {
    button.disabled = false;
    button.textContent = "Create tracked review";
    showToast(error.message, true);
  }
}

async function submitFeedback(rating, correction = null) {
  if (!state.lastResponse?.query_run_id) return;
  try {
    await api("/api/feedback", {
      method: "POST",
      body: JSON.stringify({ query_run_id: state.lastResponse.query_run_id, user_id: state.currentUser, rating, correction }),
    });
    $("#correctionPanel").classList.add("hidden");
    $("#correctionInput").value = "";
    showToast(rating === 1 ? "Feedback recorded." : "Correction case recorded for review.");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshMetrics() {
  const metrics = await api("/api/metrics");
  renderMetrics(metrics);
}

async function loadDocuments() {
  const table = $("#documentsTable");
  table.innerHTML = `<tr><td colspan="6">Loading document metadata…</td></tr>`;
  try {
    const documents = await api(`/api/documents?user_id=${encodeURIComponent(state.currentUser)}`);
    table.innerHTML = documents.map((document) => `
      <tr>
        <td><strong>${escapeHtml(document.title)}</strong><small>${escapeHtml(document.policy_family)} · v${escapeHtml(document.version)}</small></td>
        <td><span class="status-pill ${escapeHtml(document.status)}">${escapeHtml(document.status)}</span><small>Rank ${escapeHtml(document.authority_rank)}</small></td>
        <td>${escapeHtml(document.department)}</td>
        <td><span class="mini-pill">${escapeHtml(document.classification)}</span></td>
        <td>${escapeHtml(document.effective_date || "—")}<small>Expires ${escapeHtml(document.expires_at || "unspecified")}</small></td>
        <td>${document.allowed_roles.map((role) => `<span class="mini-pill">${escapeHtml(role)}</span>`).join(" ")}</td>
      </tr>
    `).join("") || `<tr><td colspan="6">No permitted documents are visible to this role.</td></tr>`;
  } catch (error) {
    table.innerHTML = `<tr><td colspan="6">${escapeHtml(error.message)}</td></tr>`;
  }
}

async function uploadDocument(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  data.append("user_id", state.currentUser);
  $("#uploadStatus").textContent = "Extracting, redacting, chunking, and indexing…";
  try {
    const result = await api("/api/documents", { method: "POST", body: data });
    $("#uploadStatus").textContent = `${result.title}: ${result.chunks} chunks indexed.`;
    form.reset();
    showToast("Document ingested with governed metadata.");
    await loadDocuments();
    await refreshMetrics();
  } catch (error) {
    $("#uploadStatus").textContent = error.message;
    showToast(error.message, true);
  }
}

async function loadReviews() {
  const container = $("#reviewsList");
  container.innerHTML = `<div class="panel empty-state">Loading review cases…</div>`;
  try {
    const reviews = await api(`/api/reviews?user_id=${encodeURIComponent(state.currentUser)}`);
    if (!reviews.length) {
      container.innerHTML = `<div class="panel empty-state"><strong>No review cases yet.</strong><br>Ask the vendor-approval question and create a tracked review.</div>`;
      return;
    }
    const canReview = Boolean(currentUser()?.can_review);
    container.innerHTML = reviews.map((review) => `
      <article class="panel review-card">
        <div class="section-heading"><span class="status-pill ${escapeHtml(review.status)}">${escapeHtml(review.status.replaceAll("_", " "))}</span><span class="mini-pill">${escapeHtml(review.risk_level)} risk</span></div>
        <h3>${escapeHtml(review.title)}</h3>
        <p>${escapeHtml(review.question_redacted)}</p>
        <div class="review-meta">
          <span class="mini-pill">Assigned: ${escapeHtml(review.assigned_role)}</span>
          <span class="mini-pill">${review.checklist.length} controls</span>
          <span class="mini-pill">${review.evidence.length} citations</span>
          <span class="mini-pill">Created ${escapeHtml(formatDate(review.created_at))}</span>
        </div>
        <div class="review-decision ${canReview ? "" : "hidden"}">
          <label>Decision note <span>(optional)</span><input type="text" maxlength="800" data-decision-note placeholder="Record conditions or rationale"></label>
        </div>
        <div class="review-actions ${canReview ? "" : "hidden"}" data-review-id="${escapeHtml(review.id)}">
          <button type="button" data-status="in_review">Start review</button>
          <button type="button" data-status="approved">Approve</button>
          <button type="button" data-status="rejected">Reject</button>
          <button type="button" data-status="completed">Complete</button>
        </div>
      </article>
    `).join("");
  } catch (error) {
    container.innerHTML = `<div class="panel empty-state">${escapeHtml(error.message)}</div>`;
  }
}

async function updateReview(reviewId, status, decisionNote = null) {
  if (["approved", "rejected", "completed"].includes(status) && !window.confirm("Action? [Y/N]")) return;
  try {
    await api(`/api/reviews/${encodeURIComponent(reviewId)}`, {
      method: "PATCH",
      body: JSON.stringify({ user_id: state.currentUser, status, decision_note: decisionNote }),
    });
    showToast(`Review moved to ${status.replaceAll("_", " ")}.`);
    await loadReviews();
    await refreshMetrics();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function loadLatestEvaluation() {
  try {
    const evaluation = await api("/api/evaluations/latest");
    state.latestEvaluation = evaluation;
    renderEvaluation(evaluation);
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderEvaluation(evaluation) {
  if (!evaluation) {
    $("#evalScore").textContent = "Not run";
    $("#evalPassed").textContent = "—";
    $("#evalVersion").textContent = "—";
    $("#evalTable").innerHTML = `<tr><td colspan="5">Run the bundled deterministic suite to establish the baseline.</td></tr>`;
    return;
  }
  $("#evalScore").textContent = `${Math.round(evaluation.score * 100)}%`;
  $("#evalPassed").textContent = `${evaluation.passed_cases} / ${evaluation.total_cases}`;
  $("#evalVersion").textContent = evaluation.suite_version;
  $("#evalTable").innerHTML = evaluation.results.map((result) => `
    <tr>
      <td><strong>${escapeHtml(result.case_id)}</strong><small>${escapeHtml(result.provider)}</small></td>
      <td><span class="status-pill ${result.passed ? "pass" : "fail"}">${result.passed ? "pass" : "fail"}</span></td>
      <td>${Math.round(result.confidence.score * 100)}%<small>${escapeHtml(result.confidence.label)}</small></td>
      <td>${escapeHtml(result.citation_count)}</td>
      <td><div class="check-chips">${result.checks.map((check) => `<span class="check-chip ${check.passed ? "" : "fail"}">${escapeHtml(check.name)}</span>`).join("")}</div></td>
    </tr>
  `).join("");
}

async function runEvaluationSuite() {
  const button = $("#runEvaluations");
  button.disabled = true;
  button.textContent = "Running governance checks…";
  try {
    const result = await api(`/api/evaluations/run?user_id=${encodeURIComponent(state.currentUser)}`, { method: "POST" });
    const normalized = {
      ...result,
      created_at: new Date().toISOString(),
    };
    state.latestEvaluation = normalized;
    renderEvaluation(normalized);
    showToast(`Evaluation complete: ${result.passed_cases}/${result.total_cases} cases passed.`);
    await refreshMetrics();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Run deterministic suite";
  }
}

async function runBenchmark() {
  const button = $("#runBenchmark");
  button.disabled = true;
  button.textContent = "Measuring…";
  try {
    const result = await api(`/api/benchmark/run?user_id=${encodeURIComponent(state.currentUser)}`, { method: "POST" });
    state.benchmark = result;
    $("#benchmarkP50").textContent = `${result.warm.p50_ms} ms`;
    $("#benchmarkP95").textContent = `${result.warm.p95_ms} ms`;
    $("#benchmarkCache").textContent = `${Math.round(result.cache.hit_rate * 100)}%`;
    $("#benchmarkStatus").textContent = result.passed ? "Within demo budget" : "Review on this PC";
    showToast(`Local benchmark complete: ${result.requests} governed requests, no network.`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Run local benchmark";
  }
}

async function loadAudit() {
  const timeline = $("#auditTimeline");
  timeline.innerHTML = "Loading audit events…";
  try {
    const audit = await api(`/api/audit?user_id=${encodeURIComponent(state.currentUser)}&limit=120`);
    const badge = $("#chainBadge");
    badge.className = `chain-badge ${audit.chain.ok ? "ok" : "bad"}`;
    badge.textContent = audit.chain.ok ? `Chain verified · ${audit.chain.events} events` : `Chain broken · event ${audit.chain.broken_at}`;
    timeline.innerHTML = audit.events.length ? audit.events.map((event) => `
      <div class="timeline-item">
        <div class="timeline-time">${escapeHtml(formatDate(event.occurred_at))}</div>
        <div class="timeline-marker"></div>
        <div class="timeline-content"><strong>${escapeHtml(event.event_type.replaceAll("_", " "))}</strong><p>${escapeHtml(event.actor)} · ${escapeHtml(event.entity_type || "system")} ${escapeHtml(event.entity_id ? event.entity_id.slice(0, 12) : "")} · hash ${escapeHtml(event.event_hash.slice(0, 12))}…<br>${escapeHtml(JSON.stringify(event.payload))}</p></div>
      </div>
    `).join("") : `<div class="empty-state">No audit events have been recorded.</div>`;
  } catch (error) {
    timeline.textContent = error.message;
  }
}

function bindEvents() {
  $$(".nav-item").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.view)));
  $("#userSelect").addEventListener("change", async (event) => {
    state.currentUser = event.target.value;
    updateUserDependentUI();
    const active = $(".nav-item.active")?.dataset.view;
    if (active === "documents") await loadDocuments();
    if (active === "reviews") await loadReviews();
  });
  $("#askForm").addEventListener("submit", submitQuestion);
  $$("[data-question]").forEach((button) => button.addEventListener("click", () => { $("#questionInput").value = button.dataset.question; $("#questionInput").focus(); }));
  $("#createReviewButton").addEventListener("click", createReview);
  $("#feedbackRow").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-rating]");
    if (!button) return;
    const rating = Number(button.dataset.rating);
    if (rating < 0) {
      $("#correctionPanel").classList.remove("hidden");
      $("#correctionInput").focus();
    } else {
      submitFeedback(rating);
    }
  });
  $("#cancelCorrection").addEventListener("click", () => {
    $("#correctionPanel").classList.add("hidden");
    $("#correctionInput").value = "";
  });
  $("#submitCorrection").addEventListener("click", () => {
    const correction = $("#correctionInput").value.trim();
    if (!correction) {
      showToast("Describe the correction or missing evidence.", true);
      return;
    }
    submitFeedback(-1, correction);
  });
  $("#refreshDocuments").addEventListener("click", loadDocuments);
  $("#uploadForm").addEventListener("submit", uploadDocument);
  $("#refreshReviews").addEventListener("click", loadReviews);
  $("#reviewsList").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-status]");
    const actions = event.target.closest("[data-review-id]");
    if (button && actions) {
      const card = actions.closest(".review-card");
      const note = card?.querySelector("[data-decision-note]")?.value.trim() || null;
      updateReview(actions.dataset.reviewId, button.dataset.status, note);
    }
  });
  $("#runEvaluations").addEventListener("click", runEvaluationSuite);
  $("#runBenchmark").addEventListener("click", runBenchmark);
  $("#resetDemoButton").addEventListener("click", resetDemo);
  $("#demoStepGrid").addEventListener("click", (event) => {
    const button = event.target.closest("[data-demo-step]");
    if (button) runDemoStep(button.dataset.demoStep);
  });
  $("#refreshAudit").addEventListener("click", loadAudit);
}

async function initialize() {
  bindEvents();
  try {
    await Promise.all([loadStatus(), loadUsers()]);
    await Promise.all([loadDemoOverview(), loadLatestEvaluation()]);
  } catch (error) {
    showToast(error.message, true);
    $("#integrityDot").className = "status-dot bad";
    $("#integrityText").textContent = "Application unavailable";
  }
}

document.addEventListener("DOMContentLoaded", initialize);
