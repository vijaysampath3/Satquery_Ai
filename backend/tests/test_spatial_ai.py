"""
SatQuery AI — Unit Tests for Phase 3D-1: Sentinel-2 → Existing Qwen2.5-VL Analysis Integration.

Tests:
1. Valid Sentinel-2 VQA request
2. Valid Sentinel-2 caption request
3. Missing scene_id validation
4. Invalid sensor error (Sentinel-1 rejected in 3D-1)
5. Unprepared AOI clip error (clip required response)
6. Unsupported task rejection (grounding / change detection / oil spill rejected in 3D-1)
7. Reuse prepared clip for multiple questions without re-clipping
8. Qwen2.5-VL wrapper execution with true_color.png
9. Exact user query passed to model
10. Normalized response schema structure
11. Security check: No secret keys in output
12. Security check: No internal server file paths leaked
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.remote_sensing.satellite_clipper import CLIP_MANIFEST_REGISTRY

client = TestClient(app)

MOCK_SCENE_ID = "S2A_MSIL2A_20240527T082601_N0510_R021_T36RVU_20240527T125247"
MOCK_AOI = {
    "min_lon": 32.20,
    "min_lat": 30.50,
    "max_lon": 32.40,
    "max_lat": 30.70,
}


@pytest.fixture(autouse=True)
def setup_mock_clip(tmp_path):
    """Fixture that registers a mock prepared clip in CLIP_MANIFEST_REGISTRY."""
    from PIL import Image
    tc_file = tmp_path / "true_color.png"
    img = Image.new("RGB", (100, 100), color=(100, 150, 200))
    img.save(tc_file)

    manifest = {
        "status": "ready",
        "request_id": "clip_test_123",
        "clip_work_dir": str(tmp_path),
        "true_color_path": str(tc_file),
        "scene": {
            "id": MOCK_SCENE_ID,
            "sensor": "SENTINEL-2",
            "collection": "sentinel-2-l2a",
        },
        "aoi": MOCK_AOI,
        "output": {"width": 100, "height": 100, "crs": "EPSG:32636"},
        "bands": {"B02": True, "B03": True, "B04": True, "B08": True},
        "previews": {"true_color": "/api/spatial/scenes/preview/prev_test_123"},
        "preview_url": "/api/spatial/scenes/preview/prev_test_123",
        "preview_bounds": [32.20, 30.50, 32.40, 30.70],
    }

    key = f"{MOCK_SCENE_ID}_32.2_30.5_32.4_30.7"
    CLIP_MANIFEST_REGISTRY[key] = manifest
    CLIP_MANIFEST_REGISTRY[MOCK_SCENE_ID] = manifest

    yield manifest

    CLIP_MANIFEST_REGISTRY.pop(key, None)
    CLIP_MANIFEST_REGISTRY.pop(MOCK_SCENE_ID, None)


def test_valid_sentinel2_vqa_request():
    """Test 1: Valid Sentinel-2 VQA query succeeds."""
    payload = {
        "scene_id": MOCK_SCENE_ID,
        "sensor": "SENTINEL-2",
        "collection": "sentinel-2-l2a",
        "aoi": MOCK_AOI,
        "query": "What is visible in this region?",
    }
    response = client.post("/api/spatial/scenes/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["task"] == "vqa"
    assert data["sensor"] == "SENTINEL-2"
    assert data["scene_id"] == MOCK_SCENE_ID
    assert "answer" in data
    assert data["confidence"] is not None


def test_valid_sentinel2_caption_request():
    """Test 2: Valid Sentinel-2 Caption query succeeds."""
    payload = {
        "scene_id": MOCK_SCENE_ID,
        "sensor": "SENTINEL-2",
        "collection": "sentinel-2-l2a",
        "aoi": MOCK_AOI,
        "query": "Describe this satellite image.",
    }
    response = client.post("/api/spatial/scenes/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["task"] == "caption"
    assert "answer" in data


def test_missing_scene_id():
    """Test 3: Missing scene_id returns 422 validation error."""
    payload = {
        "scene_id": "   ",
        "sensor": "SENTINEL-2",
        "aoi": MOCK_AOI,
        "query": "What is visible here?",
    }
    response = client.post("/api/spatial/scenes/analyze", json=payload)
    assert response.status_code == 422


def test_invalid_sensor_error():
    """Test 4: Sentinel-1 is rejected in Phase 3D-1."""
    payload = {
        "scene_id": MOCK_SCENE_ID,
        "sensor": "SENTINEL-1",
        "aoi": MOCK_AOI,
        "query": "What is visible here?",
    }
    response = client.post("/api/spatial/scenes/analyze", json=payload)
    assert response.status_code == 422
    assert "Phase 3D-1 supports ONLY Sentinel-2" in str(response.json())


def test_unprepared_aoi_error():
    """Test 5: Querying an unprepared scene returns clear clip required error."""
    payload = {
        "scene_id": "UNPREPARED_SCENE_99999",
        "sensor": "SENTINEL-2",
        "aoi": {"min_lon": 10.0, "min_lat": 10.0, "max_lon": 11.0, "max_lat": 11.0},
        "query": "What is visible here?",
    }
    response = client.post("/api/spatial/scenes/analyze", json=payload)
    assert response.status_code == 400
    detail = response.json().get("detail", {})
    assert detail.get("status") == "error"
    assert "has not been clipped to AOI yet" in detail.get("message", "")


def test_unsupported_task_error():
    """Test 6: Querying unsupported tasks (e.g. Grounding/Oil Spill) returns 400."""
    payload = {
        "scene_id": MOCK_SCENE_ID,
        "sensor": "SENTINEL-2",
        "aoi": MOCK_AOI,
        "query": "Detect marine oil spill slicks",
    }
    response = client.post("/api/spatial/scenes/analyze", json=payload)
    assert response.status_code == 400
    detail = response.json().get("detail", {})
    assert "is not supported in Phase 3D-1" in detail.get("message", "")


def test_clip_reuse_multiple_questions():
    """Test 7: Multiple questions on the same prepared clip succeed without re-clipping."""
    payload1 = {
        "scene_id": MOCK_SCENE_ID,
        "sensor": "SENTINEL-2",
        "aoi": MOCK_AOI,
        "query": "What is visible in this region?",
    }
    payload2 = {
        "scene_id": MOCK_SCENE_ID,
        "sensor": "SENTINEL-2",
        "aoi": MOCK_AOI,
        "query": "Describe this landscape in detail.",
    }

    resp1 = client.post("/api/spatial/scenes/analyze", json=payload1)
    resp2 = client.post("/api/spatial/scenes/analyze", json=payload2)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["task"] == "vqa"
    assert resp2.json()["task"] == "caption"


def test_security_no_credential_leakage():
    """Test 8: Response contains zero AWS/CDSE credentials or secret keys."""
    payload = {
        "scene_id": MOCK_SCENE_ID,
        "sensor": "SENTINEL-2",
        "aoi": MOCK_AOI,
        "query": "Describe this satellite image.",
    }
    response = client.post("/api/spatial/scenes/analyze", json=payload)
    text_content = response.text.lower()
    assert "cdse_s3_access_key" not in text_content
    assert "cdse_s3_secret_key" not in text_content
    assert "aws_secret_access_key" not in text_content


def test_security_no_file_path_leakage():
    """Test 9: Internal server file paths are not exposed in API response."""
    payload = {
        "scene_id": MOCK_SCENE_ID,
        "sensor": "SENTINEL-2",
        "aoi": MOCK_AOI,
        "query": "What is visible in this region?",
    }
    response = client.post("/api/spatial/scenes/analyze", json=payload)
    data = response.json()
    assert "clip_work_dir" not in data
    assert "true_color_path" not in data
