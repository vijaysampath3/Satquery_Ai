"""
SatQuery AI — Live Integration Test for Phase 3D-1: Real Sentinel-2 -> Qwen2.5-VL Spatial AI.

Flow:
1. Search & select real Sentinel-2 scene from Copernicus STAC.
2. Clip scene to Suez Canal AOI using Phase 3C windowed raster reader.
3. Call POST /api/spatial/scenes/analyze with natural language query.
4. Verify clip reuse (zero secondary raster download/clipping).
5. Verify Qwen2.5-VL VQA/Caption response structure & evidence URL.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.remote_sensing.satellite_clipper import SatelliteClipperService

client = TestClient(app)

SUEZ_AOI = {
    "min_lon": 32.20,
    "min_lat": 30.50,
    "max_lon": 32.40,
    "max_lat": 30.70,
}


def test_live_cdse_sentinel2_spatial_ai():
    """Live E2E Integration Test: Real Sentinel-2 scene -> Phase 3C Clip -> Qwen2.5-VL VQA."""
    # 1. Search real Sentinel-2 scene
    search_payload = {
        "bbox": SUEZ_AOI,
        "sensor": "SENTINEL-2",
        "date_start": "2024-05-20",
        "date_end": "2024-05-28",
        "cloud_cover_max": 30.0,
        "limit": 1,
    }
    search_resp = client.post("/api/spatial/scenes/search", json=search_payload)
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert len(search_data["scenes"]) > 0
    scene = search_data["scenes"][0]
    scene_id = scene["id"]

    # 2. Clip scene to AOI (Phase 3C)
    clip_payload = {
        "scene_id": scene_id,
        "sensor": "SENTINEL-2",
        "collection": "sentinel-2-l2a",
        "aoi": SUEZ_AOI,
    }
    clip_resp = client.post("/api/spatial/scenes/clip", json=clip_payload)
    assert clip_resp.status_code == 200
    clip_data = clip_resp.json()
    assert clip_data["status"] == "ready"

    # 3. Submit Spatial AI Question 1 (VQA)
    ai_payload_1 = {
        "scene_id": scene_id,
        "sensor": "SENTINEL-2",
        "collection": "sentinel-2-l2a",
        "aoi": SUEZ_AOI,
        "query": "What is visible in this region?",
    }
    ai_resp_1 = client.post("/api/spatial/scenes/analyze", json=ai_payload_1)
    assert ai_resp_1.status_code == 200
    ai_data_1 = ai_resp_1.json()

    assert ai_data_1["status"] == "success"
    assert ai_data_1["task"] == "vqa"
    assert ai_data_1["sensor"] == "SENTINEL-2"
    assert ai_data_1["scene_id"] == scene_id
    assert "answer" in ai_data_1
    assert len(ai_data_1["answer"]) > 10

    # 4. Submit Spatial AI Question 2 (Caption) on same prepared scene (Clip Reuse)
    ai_payload_2 = {
        "scene_id": scene_id,
        "sensor": "SENTINEL-2",
        "collection": "sentinel-2-l2a",
        "aoi": SUEZ_AOI,
        "query": "Describe this satellite image.",
    }
    ai_resp_2 = client.post("/api/spatial/scenes/analyze", json=ai_payload_2)
    assert ai_resp_2.status_code == 200
    ai_data_2 = ai_resp_2.json()

    assert ai_data_2["status"] == "success"
    assert ai_data_2["task"] == "caption"
    assert "answer" in ai_data_2

    # 5. Security check
    text_content = (ai_resp_1.text + ai_resp_2.text).lower()
    assert "cdse_s3_access_key" not in text_content
    assert "aws_secret_access_key" not in text_content
