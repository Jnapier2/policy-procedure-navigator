from __future__ import annotations

import statistics
import time
from typing import Any

from .service import PolicyService

_BENCHMARK_CASES = [
    ("ava.employee", "What approvals are required before engaging a new vendor?"),
    ("ava.employee", "What penetration testing evidence must a software vendor provide?"),
    ("sam.security", "What penetration testing evidence must a software vendor provide?"),
    ("ava.employee", "What is the exact daily parking reimbursement limit while traveling?"),
    ("marcus.procurement", "When is an emergency purchasing exception allowed?"),
]


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def run_local_benchmark(service: PolicyService, warm_rounds: int = 4) -> dict[str, Any]:
    """Run a bounded, read-only benchmark over bundled fictional scenarios.

    The benchmark never calls a network provider and never persists query/audit rows.
    It measures the exact governed service path on the current local machine.
    """
    warm_rounds = max(1, min(int(warm_rounds), 8))
    service.retrieval_cache.clear(reset_counters=True)

    cold_samples: list[float] = []
    warm_samples: list[float] = []
    stage_samples: dict[str, list[float]] = {"redact": [], "retrieve": [], "governance": [], "generate": []}
    answers_checked = 0
    start = time.perf_counter()

    for user_id, question in _BENCHMARK_CASES:
        result = service.ask(question, user_id, persist=False)
        cold_samples.append(float(result["performance"]["request_total_ms"]))
        for stage, value in result["performance"]["stage_timings_ms"].items():
            if stage in stage_samples:
                stage_samples[stage].append(float(value))
        answers_checked += 1

    for _ in range(warm_rounds):
        for user_id, question in _BENCHMARK_CASES:
            result = service.ask(question, user_id, persist=False)
            warm_samples.append(float(result["performance"]["request_total_ms"]))
            for stage, value in result["performance"]["stage_timings_ms"].items():
                if stage in stage_samples:
                    stage_samples[stage].append(float(value))
            answers_checked += 1

    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
    all_samples = cold_samples + warm_samples
    stats = service.retrieval_cache.stats()
    requests = len(all_samples)
    cache_total = stats["hits"] + stats["misses"]
    cache_hit_rate = (stats["hits"] / cache_total) if cache_total else 0.0

    # Generous local-demo budgets are signals, not hardware guarantees.
    budgets = {
        "warm_p95_ms": 500.0,
        "retrieve_p95_ms": 250.0,
        "benchmark_total_ms": 8000.0,
    }
    stage_summary = {
        name: {
            "p50_ms": round(statistics.median(values), 2) if values else 0.0,
            "p95_ms": round(_percentile(values, 0.95), 2),
        }
        for name, values in stage_samples.items()
    }
    checks = {
        "warm_p95": round(_percentile(warm_samples, 0.95), 2) <= budgets["warm_p95_ms"],
        "retrieve_p95": stage_summary["retrieve"]["p95_ms"] <= budgets["retrieve_p95_ms"],
        "total_elapsed": elapsed_ms <= budgets["benchmark_total_ms"],
    }
    return {
        "mode": "keyless-local",
        "network_used": False,
        "credentials_required": False,
        "cases": len(_BENCHMARK_CASES),
        "requests": requests,
        "answers_checked": answers_checked,
        "cold": {
            "p50_ms": round(statistics.median(cold_samples), 2),
            "p95_ms": round(_percentile(cold_samples, 0.95), 2),
        },
        "warm": {
            "p50_ms": round(statistics.median(warm_samples), 2),
            "p95_ms": round(_percentile(warm_samples, 0.95), 2),
        },
        "stage_timings": stage_summary,
        "cache": {**stats, "hit_rate": round(cache_hit_rate, 3)},
        "elapsed_ms": elapsed_ms,
        "budgets": budgets,
        "checks": checks,
        "passed": all(checks.values()),
    }
