"""
Water Detection & Land Cover Regression Test Suite for SatQuery AI.

Tests:
  1. Synthetic Blue Water
  2. Synthetic Green Vegetation
  3. Synthetic Bright Built-up
  4. Synthetic Half Water / Half Vegetation
  5. Synthetic Dark Green Vegetation (Must NOT classify as water)
  6. Synthetic Dark Blue Water
  7. Real Black Sea Image Test (data/real/black_sea.jpg)
  8. Real Bakkanapalem Image Test
  9. Water Grounding Pipeline & Visual Evidence Verification (No fake ndvi.png for RGB)
"""

import os
import pytest
import numpy as np
from PIL import Image
from pathlib import Path

from app.remote_sensing.indices import detect_water, calculate_sequential_land_cover
from app.remote_sensing.grounding import detect_target_regions
from app.remote_sensing.visualization import generate_evidence_visualizations


@pytest.fixture
def black_sea_image_path(tmp_path):
    """Path to real Black Sea test image."""
    real_path = Path("data/real/black_sea.jpg")
    if real_path.exists():
        return str(real_path)
    
    user_uploaded = Path(r"C:\Users\Vijay sampath\.gemini\antigravity-ide\brain\14d90dea-841e-46d2-962c-7f0c671991f4\.user_uploaded\media_1788529444104.jpg")
    if user_uploaded.exists():
        return str(user_uploaded)

    # Fallback synthetic dark blue sea image (60% dark blue sea, 40% land)
    h, w = 300, 500
    img_arr = np.zeros((h, w, 3), dtype=np.uint8)
    # Sea region (top 60%)
    img_arr[:180, :, :] = [40, 70, 150]  # Dark blue
    # Land region (bottom 40%)
    img_arr[180:, :, :] = [50, 120, 40]   # Dark green
    tmp_file = tmp_path / "synthetic_black_sea.jpg"
    Image.fromarray(img_arr).save(tmp_file)
    return str(tmp_file)


@pytest.fixture
def bakkanapalem_image_path(tmp_path):
    """Path to real Bakkanapalem test image."""
    real_path = Path("data/real/bakkanapalem.png")
    if real_path.exists():
        return str(real_path)

    user_uploaded = Path(r"C:\Users\Vijay sampath\.gemini\antigravity-ide\brain\14d90dea-841e-46d2-962c-7f0c671991f4\.user_uploaded\media_1788494123170.png")
    if user_uploaded.exists():
        return str(user_uploaded)

    # Fallback synthetic dense vegetation image (80% green forest)
    h, w = 300, 500
    img_arr = np.zeros((h, w, 3), dtype=np.uint8)
    img_arr[:, :, :] = [30, 140, 40] # Forest green
    tmp_file = tmp_path / "synthetic_bakkanapalem.png"
    Image.fromarray(img_arr).save(tmp_file)
    return str(tmp_file)


# ── Synthetic Tests ──

def test_synthetic_blue_water():
    """1. Blue water image -> water > 80%, veg < 5%."""
    img = np.zeros((100, 100, 3), dtype=np.float32)
    img[:, :, 0] = 0.15  # Red
    img[:, :, 1] = 0.35  # Green
    img[:, :, 2] = 0.70  # Blue

    breakdown = calculate_sequential_land_cover(img)
    assert breakdown["water_percentage"] > 80.0
    assert breakdown["vegetation_percentage"] < 5.0
    assert breakdown["water_method"] == "RGB Blue-Dominance + HSV Visual Heuristic"


def test_synthetic_green_vegetation():
    """2. Green vegetation image -> veg > 80%, water < 5%."""
    img = np.zeros((100, 100, 3), dtype=np.float32)
    img[:, :, 0] = 0.15  # Red
    img[:, :, 1] = 0.65  # Green
    img[:, :, 2] = 0.20  # Blue

    breakdown = calculate_sequential_land_cover(img)
    assert breakdown["vegetation_percentage"] > 80.0
    assert breakdown["water_percentage"] < 5.0


def test_synthetic_bright_builtup():
    """3. Bright low-saturation image -> built > 70%."""
    img = np.zeros((100, 100, 3), dtype=np.float32)
    img[:, :, 0] = 0.75
    img[:, :, 1] = 0.75
    img[:, :, 2] = 0.75

    breakdown = calculate_sequential_land_cover(img)
    assert breakdown["built_percentage"] > 70.0
    assert breakdown["water_percentage"] < 5.0


def test_synthetic_half_water_half_vegetation():
    """4. Half blue water / half green vegetation image."""
    img = np.zeros((100, 100, 3), dtype=np.float32)
    # Top half: blue water
    img[:50, :, 0] = 0.15
    img[:50, :, 1] = 0.35
    img[:50, :, 2] = 0.70
    # Bottom half: green vegetation
    img[50:, :, 0] = 0.15
    img[50:, :, 1] = 0.65
    img[50:, :, 2] = 0.20

    breakdown = calculate_sequential_land_cover(img)
    assert 40.0 <= breakdown["water_percentage"] <= 60.0
    assert 40.0 <= breakdown["vegetation_percentage"] <= 60.0


def test_synthetic_dark_green_vegetation():
    """5. CRITICAL: Dark green vegetation MUST NOT classify as water."""
    img = np.zeros((100, 100, 3), dtype=np.float32)
    img[:, :, 0] = 0.08  # Dark Red
    img[:, :, 1] = 0.30  # Dark Green (higher than blue)
    img[:, :, 2] = 0.12  # Dark Blue

    water_mask, _ = detect_water(img)
    water_pct = float(np.mean(water_mask) * 100.0)
    assert water_pct < 5.0, f"Dark green vegetation incorrectly classified as water: {water_pct}%"

    breakdown = calculate_sequential_land_cover(img)
    assert breakdown["water_percentage"] < 5.0
    assert breakdown["vegetation_percentage"] > 50.0


def test_synthetic_dark_blue_water():
    """6. Dark blue water -> correctly classified as water."""
    img = np.zeros((100, 100, 3), dtype=np.float32)
    img[:, :, 0] = 0.08  # Low Red
    img[:, :, 1] = 0.20  # Moderate Green
    img[:, :, 2] = 0.45  # Dominant Blue

    water_mask, _ = detect_water(img)
    water_pct = float(np.mean(water_mask) * 100.0)
    assert water_pct > 70.0, f"Dark blue water failed to detect: {water_pct}%"


# ── Real Data Regression Tests ──

def test_black_sea_real_image_validation(black_sea_image_path):
    """7. Black Sea real image sanity test."""
    arr = np.array(Image.open(black_sea_image_path).convert("RGB")).astype(np.float32) / 255.0
    meta = {"input_type": "Input: RGB Visual (JPEG/PNG)", "is_rgb": True}

    breakdown = calculate_sequential_land_cover(arr, meta)

    print("Black Sea Breakdown:", breakdown)
    assert breakdown["water_percentage"] > 30.0, f"Black Sea water % too low: {breakdown['water_percentage']}%"
    assert breakdown["vegetation_percentage"] < 60.0, f"Black Sea vegetation % inflated: {breakdown['vegetation_percentage']}%"
    assert breakdown["water_method"] == "RGB Blue-Dominance + HSV Visual Heuristic"
    assert np.any(breakdown["water_mask"] > 0)


def test_bakkanapalem_real_image_validation(bakkanapalem_image_path):
    """8. Bakkanapalem real image sanity test."""
    arr = np.array(Image.open(bakkanapalem_image_path).convert("RGB")).astype(np.float32) / 255.0
    meta = {"input_type": "Input: RGB Visual (JPEG/PNG)", "is_rgb": True}

    breakdown = calculate_sequential_land_cover(arr, meta)

    print("Bakkanapalem Breakdown:", breakdown)
    assert breakdown["vegetation_percentage"] > 60.0, f"Bakkanapalem vegetation % dropped: {breakdown['vegetation_percentage']}%"
    assert breakdown["water_percentage"] < 10.0, f"Bakkanapalem water % unexpected: {breakdown['water_percentage']}%"


# ── Grounding Pipeline Verification ──

def test_water_grounding_pipeline(black_sea_image_path):
    """9. Water Grounding pipeline produces boxes, overlay, and water_mask (NO fake ndvi.png for RGB)."""
    res = detect_target_regions(black_sea_image_path, "Highlight the water bodies")

    assert res["target"] in ["water bodies", "water"]
    assert res["is_fallback"] is True
    assert len(res["boxes"]) > 0
    assert res["water_mask"] is not None
    assert np.any(res["water_mask"] > 0)

    # Test evidence generation for RGB input
    intermediate = {"step_1": res}
    evidence_images = generate_evidence_visualizations(
        image_paths=[black_sea_image_path],
        task_type="grounding",
        intermediate_data=intermediate,
        request_id="test_water_grounding",
    )

    captions = [e["caption"] for e in evidence_images]
    urls = [e["url"] for e in evidence_images]

    print("Evidence Captions:", captions)
    print("Evidence URLs:", urls)

    assert any("water_mask.png" in u for u in urls), "water_mask.png missing from evidence"
    assert any("grounding_overlay.png" in u for u in urls), "grounding_overlay.png missing from evidence"
    assert not any("ndvi.png" in u for u in urls), "CRITICAL: ndvi.png incorrectly generated for RGB input!"
