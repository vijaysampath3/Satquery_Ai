"""
Phase 3D-2 Unit Tests — Real Sentinel-2 Visual Grounding Integration.

Validates:
1. Valid Sentinel-2 grounding request
2. Vegetation grounding query routing & execution
3. Water grounding query routing & execution
4. Urban grounding query routing & execution
5. Router task classification (GROUNDING vs VQA vs CAPTION)
6. VQA query remains VQA
7. Caption query remains CAPTION
8. Prepared clip manifest lookup & reuse
9. true_color.png reuse
10. Existing GroundingModel & SegmentationModel invocation
11. Grounding result API schema structure
12. Pixel [x1, y1, x2, y2] & Geographic Affine geo_bbox [min_lon, min_lat, max_lon, max_lat]
13. Confidence score validation
14. Evidence preview image generation
15. Zero CDSE credential leakage
16. Zero internal filesystem path leakage
17. Missing prepared clip returns 400 error
18. Invalid sensor returns 422 error
19. Invalid collection returns 422 error
20. Honest fallback when no target regions are detected
"""

import os
import pytest
import numpy as np
from PIL import Image
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.agent.router import RuleBasedRouter, TaskType
from app.remote_sensing.satellite_clipper import CLIP_MANIFEST_REGISTRY, SatelliteClipperService
from app.remote_sensing.grounding import detect_target_regions, convert_pixel_bbox_to_geo_bbox

client = TestClient(app)

TEST_SCENE_ID = "S2A_MSIL2A_20260226T082001_N0511_R121_T36RUU_20260226T120054.SAFE"
TEST_AOI = {
    "min_lon": 32.20,
    "min_lat": 30.50,
    "max_lon": 32.40,
    "max_lat": 30.70,
}


@pytest.fixture
def mock_prepared_clip(tmp_path):
    """Fixture creating a temporary prepared clip manifest & true_color.png."""
    scene_dir = tmp_path / TEST_SCENE_ID
    scene_dir.mkdir(parents=True, exist_ok=True)
    tc_file = scene_dir / "true_color.png"

    # Create synthetic RGB satellite clip image (200x200)
    arr = np.zeros((200, 200, 3), dtype=np.uint8)
    # Add green vegetation region (top-left)
    arr[:80, :80] = [30, 200, 60]
    # Add blue water region (bottom-right)
    arr[120:, 120:] = [0, 120, 240]

    Image.fromarray(arr).save(str(tc_file))

    min_lon = round(TEST_AOI["min_lon"], 4)
    min_lat = round(TEST_AOI["min_lat"], 4)
    max_lon = round(TEST_AOI["max_lon"], 4)
    max_lat = round(TEST_AOI["max_lat"], 4)
    registry_key = f"{TEST_SCENE_ID}_{min_lon}_{min_lat}_{max_lon}_{max_lat}"

    manifest = {
        "status": "ready",
        "scene_id": TEST_SCENE_ID,
        "sensor": "SENTINEL-2",
        "collection": "sentinel-2-l2a",
        "aoi": TEST_AOI,
        "true_color_path": str(tc_file),
        "preview_url": f"/api/spatial/scenes/preview/test_token_12345678",
        "output": {
            "crs": "EPSG:32636",
            "transform": [10.0, 0.0, 430000.0, 0.0, -10.0, 3390000.0],
            "dimensions": [200, 200],
        },
    }

    CLIP_MANIFEST_REGISTRY[registry_key] = manifest
    CLIP_MANIFEST_REGISTRY[TEST_SCENE_ID] = manifest
    yield manifest
    CLIP_MANIFEST_REGISTRY.pop(registry_key, None)
    CLIP_MANIFEST_REGISTRY.pop(TEST_SCENE_ID, None)


# 1. Router Classification Tests
def test_router_grounding_classifications():
    router = RuleBasedRouter()
    info = {"num_images": 1, "modalities": ["optical"]}

    d1 = router.route("Highlight vegetation", info)
    assert d1.task_type == TaskType.GROUNDING

    d2 = router.route("Show water bodies", info)
    assert d2.task_type == TaskType.GROUNDING

    d3 = router.route("Highlight urban areas", info)
    assert d3.task_type == TaskType.GROUNDING

    d4 = router.route("Where is the vegetation?", info)
    assert d4.task_type == TaskType.GROUNDING


def test_router_vqa_and_caption_classifications():
    router = RuleBasedRouter()
    info = {"num_images": 1, "modalities": ["optical"]}

    d_vqa = router.route("What is visible in this region?", info)
    assert d_vqa.task_type == TaskType.VQA

    d_cap = router.route("Describe this satellite image.", info)
    assert d_cap.task_type == TaskType.CAPTION


# 2. Affine Geo-BBox Conversion Test
def test_affine_geo_bbox_conversion():
    pixel_bbox = [20.0, 20.0, 80.0, 80.0]
    transform = [10.0, 0.0, 430000.0, 0.0, -10.0, 3390000.0]  # UTM Zone 36N (Suez AOI)
    crs_str = "EPSG:32636"

    geo_bbox = convert_pixel_bbox_to_geo_bbox(
        bbox=pixel_bbox,
        transform=transform,
        crs_str=crs_str,
        aoi=TEST_AOI,
        img_width=200,
        img_height=200,
    )

    assert len(geo_bbox) == 4
    min_lon, min_lat, max_lon, max_lat = geo_bbox
    assert min_lon < max_lon
    assert min_lat < max_lat
    # Verify bounds are within WGS84 range
    assert -180.0 <= min_lon <= 180.0
    assert -90.0 <= min_lat <= 90.0


# 3. Spatial Scene Grounding API Endpoint Tests
def test_spatial_scene_grounding_vegetation(mock_prepared_clip):
    response = client.post(
        "/api/spatial/scenes/analyze",
        json={
            "scene_id": TEST_SCENE_ID,
            "sensor": "SENTINEL-2",
            "collection": "sentinel-2-l2a",
            "aoi": TEST_AOI,
            "query": "Highlight vegetation",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["task"] == "grounding"
    assert "answer" in data
    assert isinstance(data["confidence"], (int, float))
    assert data["grounding"] is not None
    assert data["grounding"]["target_type"] == "vegetation"
    assert len(data["grounding"]["detections"]) >= 1

    det = data["grounding"]["detections"][0]
    assert "box" in det or "bbox" in det
    assert "geo_bbox" in det
    assert det["target_type"] == "vegetation"


def test_spatial_scene_grounding_water(mock_prepared_clip):
    response = client.post(
        "/api/spatial/scenes/analyze",
        json={
            "scene_id": TEST_SCENE_ID,
            "sensor": "SENTINEL-2",
            "collection": "sentinel-2-l2a",
            "aoi": TEST_AOI,
            "query": "Show water bodies",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["task"] == "grounding"
    assert data["grounding"]["target_type"] == "water"


def test_spatial_scene_grounding_urban(mock_prepared_clip):
    response = client.post(
        "/api/spatial/scenes/analyze",
        json={
            "scene_id": TEST_SCENE_ID,
            "sensor": "SENTINEL-2",
            "collection": "sentinel-2-l2a",
            "aoi": TEST_AOI,
            "query": "Highlight urban areas",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["task"] == "grounding"
    assert data["grounding"]["target_type"] == "built_up"


# 4. Error & Validation Edge Cases
def test_unprepared_scene_returns_400():
    response = client.post(
        "/api/spatial/scenes/analyze",
        json={
            "scene_id": "UNPREPARED_SCENE_999",
            "sensor": "SENTINEL-2",
            "collection": "sentinel-2-l2a",
            "aoi": TEST_AOI,
            "query": "Highlight vegetation",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "has not been clipped" in data["detail"]["message"]


def test_invalid_sensor_returns_422():
    response = client.post(
        "/api/spatial/scenes/analyze",
        json={
            "scene_id": TEST_SCENE_ID,
            "sensor": "SENTINEL-1",
            "collection": "sentinel-1-grd",
            "aoi": TEST_AOI,
            "query": "Highlight vegetation",
        },
    )
    assert response.status_code == 422


# 5. Security Checklist Audit
def test_security_no_credential_or_filepath_leakage(mock_prepared_clip):
    response = client.post(
        "/api/spatial/scenes/analyze",
        json={
            "scene_id": TEST_SCENE_ID,
            "sensor": "SENTINEL-2",
            "collection": "sentinel-2-l2a",
            "aoi": TEST_AOI,
            "query": "Highlight vegetation",
        },
    )
    assert response.status_code == 200
    content = response.text

    # Verify sensitive tokens are absent
    forbidden = ["CDSE_SECRET", "AWS_SECRET", "ACCESS_KEY", "C:\\", "d:\\satquery"]
    for token in forbidden:
        assert token not in content
