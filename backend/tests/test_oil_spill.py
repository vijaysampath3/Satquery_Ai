"""
Oil Spill Detection Pipeline Test Suite for SatQuery AI.

Tests:
  1. Router queries: "Detect oil spills", "Highlight the oil spill area", "Where is the oil slick?" -> TaskType.OIL_SPILL
  2. Router query: "Describe this image" -> TaskType.CAPTION (unchanged)
  3. Colorful RGB PNG + oil-spill query -> capability warning, no SAR processing
  4. Sentinel-1 SAR Visual PNG screenshot -> OIL_SPILL executes ("Sentinel-1 SAR visual screening" mode)
  5. SAR Visual PNG evidence -> sar_composite.png, oil_spill_mask.png, oil_spill_overlay.png generated
  6. No fabricated km2 for PNG screenshot when geospatial resolution is unavailable
  7. Sentinel-1 SAR GeoTIFF -> existing VV/VH algorithm executes ("Sentinel-1 SAR VV/VH" mode)
  8. End-to-end model wrapper execution and evidence generation
"""

import os
import pytest
import numpy as np
from PIL import Image
from pathlib import Path

from app.agent.router import RuleBasedRouter, TaskType
from app.remote_sensing.oil_spill import detect_oil_spill
from app.models.oil_spill import OilSpillDetectorModel


@pytest.fixture
def synthetic_colorful_rgb_image(tmp_path):
    """Create a synthetic colorful 3-band RGB PNG image."""
    h, w = 200, 200
    img_arr = np.zeros((h, w, 3), dtype=np.uint8)
    img_arr[:, :, 0] = 200  # Bright Red
    img_arr[:, :, 1] = 50   # Green
    img_arr[:, :, 2] = 50   # Blue
    img_file = tmp_path / "colorful_landscape.png"
    Image.fromarray(img_arr).save(img_file)
    return str(img_file)


@pytest.fixture
def synthetic_sar_visual_png_with_slick(tmp_path):
    """Create a synthetic grayscale SAR visual PNG image with a dark slick region."""
    h, w = 200, 200
    # Grayscale sea background (R=G=B=120)
    sar_arr = np.ones((h, w, 3), dtype=np.uint8) * 120
    # Land (R=G=B=220 on right 15%)
    sar_arr[:, 170:, :] = 220
    # Dark oil slick candidate patch (top-left 40x40 patch, low intensity R=G=B=20)
    sar_arr[30:70, 30:70, :] = 20

    img_file = tmp_path / "sentinel1_visual_screenshot.png"
    Image.fromarray(sar_arr).save(img_file)
    return str(img_file)


@pytest.fixture
def synthetic_sar_geotiff_with_slick(tmp_path):
    """Create a synthetic SAR GeoTIFF image (open sea + dark oil slick spot)."""
    h, w = 200, 200
    sar_arr = np.ones((h, w), dtype=np.uint8) * 120
    sar_arr[:, 180:] = 220
    sar_arr[30:70, 30:70] = 20

    img_file = tmp_path / "sentinel1_sar_slick.tif"
    Image.fromarray(sar_arr).save(img_file)
    return str(img_file)


@pytest.fixture
def synthetic_sar_image_uniform_sea(tmp_path):
    """Create a synthetic SAR image of uniform open sea with no slick candidate."""
    h, w = 200, 200
    np.random.seed(42)
    noise = np.random.randint(-5, 6, size=(h, w))
    sar_arr = np.clip(120 + noise, 0, 255).astype(np.uint8)

    img_file = tmp_path / "sentinel1_sar_uniform.tif"
    Image.fromarray(sar_arr).save(img_file)
    return str(img_file)


# ── Test 1: Natural-Language Router Queries ──
def test_router_oil_spill_queries():
    router = RuleBasedRouter()
    queries = [
        "Detect oil spills",
        "Highlight the oil spill area",
        "Where is the oil slick?",
        "Is there an oil spill?",
    ]
    for q in queries:
        decision = router.route(q, {"num_images": 1})
        assert decision.task_type == TaskType.OIL_SPILL, f"Failed for query: '{q}'"
        assert "oil_spill_detector" in decision.models


# ── Test 2: Non-oil query "Describe this image" ──
def test_router_non_oil_query_unchanged():
    router = RuleBasedRouter()
    decision = router.route("Describe this image", {"num_images": 1})
    assert decision.task_type == TaskType.CAPTION
    assert decision.task_type != TaskType.OIL_SPILL


# ── Test 3: Colorful RGB PNG + oil-spill query -> capability warning, no SAR processing ──
def test_colorful_rgb_png_gives_capability_warning(synthetic_colorful_rgb_image):
    meta = {"modality": "optical", "is_rgb": True, "input_type": "Input: RGB Visual (JPEG/PNG)"}
    res = detect_oil_spill(synthetic_colorful_rgb_image, metadata=meta, query="Detect oil spills")

    assert res["is_valid_sar"] is False
    assert res["detected"] is False
    assert res["candidate_count"] == 0
    assert "Oil-spill analysis requires suitable Sentinel-1 SAR imagery." in res["warning"]
    assert "RGB visual image" in res["answer"]


# ── Test 4 & 5 & 6: Sentinel-1 SAR visual PNG screenshot execution & evidence ──
def test_sar_visual_png_screening_execution(synthetic_sar_visual_png_with_slick):
    meta = {"modality": "sar", "modalities": ["sar"]}
    res = detect_oil_spill(synthetic_sar_visual_png_with_slick, metadata=meta, query="Highlight the oil spill area")

    assert res["is_valid_sar"] is True
    assert res["analysis_mode"] == "Sentinel-1 SAR visual screening"
    assert res["detected"] is True
    assert res["candidate_count"] >= 1
    assert res["affected_pixel_count"] > 0
    assert res["affected_percentage"] > 0.0
    assert res["has_geospatial_resolution"] is False
    assert "expert verification is required" in res["warning"].lower()

    # Verify no fabricated km² in candidate region dicts
    for reg in res["regions"]:
        assert "area_km2" not in reg, "CRITICAL: km² fabricated for PNG screenshot when geospatial resolution is unavailable!"
        assert "pixel_count" in reg
        assert "bbox" in reg


# ── Test 7: SAR GeoTIFF VV/VH Mode ──
def test_sar_geotiff_vv_vh_execution(synthetic_sar_geotiff_with_slick):
    res = detect_oil_spill(synthetic_sar_geotiff_with_slick, query="Highlight the oil spill area")

    assert res["is_valid_sar"] is True
    assert res["analysis_mode"] == "Sentinel-1 SAR VV/VH"
    assert res["detected"] is True
    assert res["candidate_count"] >= 1
    assert res["has_geospatial_resolution"] is True
    assert "area_km2" in res["regions"][0]
    assert "expert verification is required" in res["warning"].lower()


# ── Test 8: Uniform SAR input -> detected = False ──
def test_sar_input_uniform_sea_no_candidate(synthetic_sar_image_uniform_sea):
    res = detect_oil_spill(synthetic_sar_image_uniform_sea, query="Is there an oil spill?")

    assert res["is_valid_sar"] is True
    assert res["detected"] is False
    assert res["candidate_count"] == 0
    assert res["affected_pixel_count"] == 0
    assert "No potential oil-spill candidates detected" in res["answer"]


# ── Test 9: End-to-End Model Wrapper & Evidence Files for SAR Visual PNG ──
def test_oil_spill_model_wrapper_sar_visual_png(synthetic_sar_visual_png_with_slick):
    model = OilSpillDetectorModel()
    context = {
        "images": [synthetic_sar_visual_png_with_slick],
        "query": "Where is the oil slick?",
        "request_id": "test_sar_visual_req",
        "metadata": {"modalities": ["sar"]},
    }
    out = model.run(action="detect_oil_spill", context=context)

    assert out["task"] == "OIL_SPILL"
    assert out["analysis_mode"] == "Sentinel-1 SAR visual screening"
    assert out["detected"] is True
    assert len(out["evidence_images"]) == 3

    urls = [e["url"] for e in out["evidence_images"]]
    assert any("sar_composite.png" in u for u in urls), "sar_composite.png missing from evidence"
    assert any("oil_spill_mask.png" in u for u in urls), "oil_spill_mask.png missing from evidence"
    assert any("oil_spill_overlay.png" in u for u in urls), "oil_spill_overlay.png missing from evidence"
