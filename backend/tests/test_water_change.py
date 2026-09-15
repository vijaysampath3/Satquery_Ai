"""
Unit tests for Temporal Water Change Detection Pipeline.
Verifies NDWI vs RGB screening, temporal mask comparison (gain/loss/changed),
geospatial area constraints, visual evidence map generation, and router integration.
"""

import os
from pathlib import Path
import numpy as np
import pytest

from app.remote_sensing.change import compute_change_detection
from app.remote_sensing.visualization import generate_evidence_visualizations
from app.agent.router import RuleBasedRouter, TaskType


def test_multispectral_water_change_ndwi():
    """Test 1 & 2: Multispectral data with B03 & B08 triggers NDWI mode."""
    shape = (100, 100)
    # T1: Dry ground
    b03_t1 = np.full(shape, 100, dtype=np.uint16)
    b08_t1 = np.full(shape, 200, dtype=np.uint16) # NDWI < 0

    # T2: Flooded (high Green, low NIR)
    b03_t2 = np.full(shape, 300, dtype=np.uint16)
    b08_t2 = np.full(shape, 100, dtype=np.uint16) # NDWI > 0

    s1 = {"B03": b03_t1, "B08": b08_t1}
    s2 = {"B03": b03_t2, "B08": b08_t2}

    res = compute_change_detection(s1, s2, query="Can you detect waterbodies changes?")
    wm = res["water_analysis"]

    assert wm["mode"] == "ndwi"
    assert "NDWI" in wm["method_label"]
    assert wm["gain_pixels"] > 0
    assert wm["changed_pixels"] == wm["gain_pixels"] + wm["loss_pixels"]


def test_missing_b03_b08_rgb_screening():
    """Test 3 & 4: RGB array without B03/B08 uses RGB screening and NEVER claims NDWI."""
    shape = (100, 100, 3)
    rgb1 = np.zeros(shape, dtype=np.uint8)
    rgb1[:, :] = (100, 100, 100)

    # Water-like blue image in Date 2
    rgb2 = np.zeros(shape, dtype=np.uint8)
    rgb2[:, :] = (30, 80, 200)

    res = compute_change_detection(rgb1, rgb2, query="Did the water bodies change?")
    wm = res["water_analysis"]

    assert wm["mode"] == "rgb_screening"
    assert wm["mode"] != "ndwi"
    assert "RGB" in wm["method_label"]


def test_water_gain_and_loss_pixel_math():
    """Test 5, 6, & 7: Verify exact water gain, loss, and changed pixel calculations."""
    shape = (50, 50, 3)

    # T1: Water on left half
    t1 = np.zeros(shape, dtype=np.uint8)
    t1[:, :25] = (30, 80, 200) # Water

    # T2: Water on right half
    t2 = np.zeros(shape, dtype=np.uint8)
    t2[:, 25:] = (30, 80, 200) # Water

    res = compute_change_detection(t1, t2, query="detect water changes")
    wm = res["water_analysis"]

    # Left half lost water, Right half gained water
    assert wm["loss_pixels"] > 0
    assert wm["gain_pixels"] > 0
    assert wm["changed_pixels"] == wm["gain_pixels"] + wm["loss_pixels"]
    assert res["water_change_mask"].shape == (50, 50)


def test_water_change_evidence_image_generated(tmp_path):
    """Test 8: Verify water_change_map.png is generated."""
    shape = (60, 60, 3)
    t1 = np.full(shape, 100, dtype=np.uint8)
    t2 = np.full(shape, 100, dtype=np.uint8)
    t2[10:30, 10:30] = (30, 80, 220)

    res = compute_change_detection(t1, t2, query="water change")
    intermediate = {"step_1": res}

    # Save mock image files for visualization generator
    from PIL import Image
    f1 = str(tmp_path / "img1.png")
    f2 = str(tmp_path / "img2.png")
    Image.fromarray(t1).save(f1)
    Image.fromarray(t2).save(f2)

    ev_list = generate_evidence_visualizations(
        image_paths=[f1, f2],
        task_type="change_detection",
        intermediate_data=intermediate,
        request_id="test_water_ev",
    )

    urls = [e["url"] for e in ev_list]
    assert any("water_change_map.png" in u for u in urls)


def test_general_change_preserves_vegetation():
    """Test 9: General change detection query preserves vegetation metrics."""
    shape = (40, 40, 3)
    t1 = np.full(shape, 50, dtype=np.uint8)
    t2 = np.full(shape, 150, dtype=np.uint8)

    res = compute_change_detection(t1, t2, query="What changed?")

    assert "vegetation_loss_percentage" in res
    assert "vegetation_gain_percentage" in res
    assert "change_percentage" in res
    assert "water_analysis" in res


def test_water_specific_query_routes_to_change_detection():
    """Test 10: Water-specific queries with 2 images route to CHANGE_DETECTION or CHANGE_VQA."""
    router = RuleBasedRouter()
    water_queries = [
        "Can you detect waterbodies changes?",
        "Did the water bodies change?",
        "Where did water expand?",
        "Where did water disappear?",
        "Show water changes",
        "Detect water changes",
        "Did the lake get larger?",
        "Detect flood water changes",
        "Compare the water bodies",
        "How did the water bodies change?",
    ]

    for q in water_queries:
        decision = router.route(q, {"num_images": 2, "modalities": ["optical", "optical"]})
        assert decision.task_type in (TaskType.CHANGE_DETECTION, TaskType.CHANGE_VQA)
        assert decision.pipeline[0]["model"] == "change_detection"


def test_no_fabricated_km2_for_rgb():
    """Test 11 & 12: RGB PNG/JPEG does not fabricate km² values."""
    shape = (50, 50, 3)
    t1 = np.zeros(shape, dtype=np.uint8)
    t2 = np.zeros(shape, dtype=np.uint8)

    res = compute_change_detection(t1, t2, query="detect flood water changes")
    wm = res["water_analysis"]

    # Verify pixels & percentages exist, but no km2 field exists in wm
    assert "gain_pixels" in wm
    assert "gain_percentage" in wm
    assert "area_km2" not in wm
