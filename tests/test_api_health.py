from __future__ import annotations

from fastapi.testclient import TestClient

from app import BUILD_ID, __version__
from app.main import create_app


def test_separate_liveness_readiness_and_status_endpoints(settings) -> None:
    with TestClient(create_app(settings=settings)) as client:
        live = client.get("/api/health/live")
        assert live.status_code == 200
        assert live.json() == {"status": "alive", "version": __version__, "build_id": BUILD_ID}

        ready = client.get("/api/health/ready")
        assert ready.status_code == 200, ready.text
        ready_payload = ready.json()
        assert ready_payload["ready"] is True
        assert ready_payload["integrity_ok"] is True
        assert ready_payload["database"]["ok"] is True
        assert ready_payload["audit_chain"]["ok"] is True

        status = client.get("/api/status")
        assert status.status_code == 200
        assert status.json()["status"] == "ready"


def test_recruiter_demo_overview_and_benchmark_are_keyless(settings) -> None:
    with TestClient(create_app(settings=settings)) as client:
        overview = client.get("/api/demo/overview")
        assert overview.status_code == 200, overview.text
        payload = overview.json()
        assert payload["proof"]["ready"] is True
        assert payload["proof"]["integrity_ok"] is True
        assert payload["proof"]["keyless"] is True
        assert payload["proof"]["network_required"] is False
        assert len(payload["tour"]["steps"]) == 4

        benchmark = client.post("/api/benchmark/run?user_id=admin.demo")
        assert benchmark.status_code == 200, benchmark.text
        result = benchmark.json()
        assert result["mode"] == "keyless-local"
        assert result["network_used"] is False
        assert result["credentials_required"] is False
        assert result["cases"] == 5
        assert result["requests"] == 25
        assert result["answers_checked"] == 25
        assert result["cache"]["hit_rate"] > 0
        assert set(result["checks"]) == {"warm_p95", "retrieve_p95", "total_elapsed"}


def test_admin_demo_reset_endpoint_preserves_upload_and_refreshes_status(settings) -> None:
    upload = settings.uploads_dir / "recruiter_keep.txt"
    upload.write_text("keep this recruiter demo upload", encoding="utf-8")
    with TestClient(create_app(settings=settings)) as client:
        reset = client.post("/api/demo/reset?user_id=admin.demo")
        assert reset.status_code == 200, reset.text
        payload = reset.json()
        assert payload["ok"] is True
        assert payload["uploads_preserved"] is True
        assert payload["backup"]["ok"] is True
        assert upload.read_text(encoding="utf-8") == "keep this recruiter demo upload"

        status = client.get("/api/status")
        assert status.status_code == 200
        assert status.json()["seed"]["signature"] == payload["seed"]["signature"]


def test_frontend_assets_are_complete_and_noncacheable(settings) -> None:
    import re
    from pathlib import Path
    from urllib.parse import urlsplit

    with TestClient(create_app(settings=settings)) as client:
        index = client.get("/")
        assert index.status_code == 200, index.text
        assert "no-store" in index.headers.get("cache-control", "").lower()
        html = index.text
        refs = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
        assert refs, "The recruiter UI must declare at least one local asset"
        for ref in refs:
            path = urlsplit(ref).path
            response = client.get(ref)
            assert response.status_code == 200, f"Missing frontend asset: {ref}"
            assert "no-store" in response.headers.get("cache-control", "").lower()
            assert (settings.root / "app" / "static" / Path(path).name).is_file()


def test_field_proven_stale_asset_names_self_recover(settings) -> None:
    with TestClient(create_app(settings=settings)) as client:
        for asset in ("/assets/api.js", "/assets/lineage.js"):
            response = client.get(asset)
            assert response.status_code == 200, asset
            assert "javascript" in response.headers.get("content-type", "").lower()
            assert "window.location.replace" in response.text
            assert BUILD_ID in response.text
            assert "no-store" in response.headers.get("cache-control", "").lower()
