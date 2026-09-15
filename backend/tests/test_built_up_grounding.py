import numpy as np
import pytest
from PIL import Image

from app.remote_sensing.grounding import detect_target_regions, classify_target_type
from app.remote_sensing.indices import get_ndbi_info
from app.remote_sensing.visualization import generate_evidence_visualizations


def test_built_up_query_classification():
    """Test 1: Built-up query variations classify to target_type == 'built_up'."""
    queries = [
        "Highlight built-up areas",
        "Highlight built up areas",
        "Show built-up regions",
        "Find urban areas",
        "Locate built-up areas",
        "Where are the buildings?",
        "Show urban regions",
        "Identify developed areas",
        "Highlight urban areas",
        "Find built up regions",
    ]
    for q in queries:
        det = detect_target_regions(np.zeros((50, 50, 3), dtype=np.uint8), q)
        assert det["target_type"] == "built_up", f"Failed for query: {q}"


def test_built_up_query_generates_built_up_mask(tmp_path):
    """Test 2: Built-up query generates built_up_mask.png."""
    shape = (60, 60, 3)
    rgb = np.full(shape, 100, dtype=np.uint8)
    rgb[10:40, 10:40] = (220, 210, 200) # Bright built-like area

    f_img = str(tmp_path / "test_built.png")
    Image.fromarray(rgb).save(f_img)

    det = detect_target_regions(f_img, "Highlight built-up areas")
    assert det["target_type"] == "built_up"

    ev_list = generate_evidence_visualizations(
        image_paths=[f_img],
        task_type="grounding",
        intermediate_data={"step_1": det},
        request_id="test_built_grounding",
    )

    urls = [e["url"] for e in ev_list]
    assert any("built_up_mask.png" in u for u in urls)


def test_built_up_query_does_not_use_water_mask(tmp_path):
    """Test 3: Built-up query does NOT use water_mask.png as the target mask."""
    shape = (50, 50, 3)
    rgb = np.full(shape, 100, dtype=np.uint8)
    rgb[10:40, 10:40] = (200, 200, 200)

    f_img = str(tmp_path / "test_built_no_water.png")
    Image.fromarray(rgb).save(f_img)

    det = detect_target_regions(f_img, "Highlight built-up areas")
    ev_list = generate_evidence_visualizations(
        image_paths=[f_img],
        task_type="grounding",
        intermediate_data={"step_1": det},
        request_id="test_built_no_water",
    )

    urls = [e["url"] for e in ev_list]
    assert not any("water_mask.png" in u for u in urls)


def test_built_up_query_does_not_use_veg_mask(tmp_path):
    """Test 4: Built-up query does NOT use vegetation_mask.png as the target mask."""
    shape = (50, 50, 3)
    rgb = np.full(shape, 100, dtype=np.uint8)
    rgb[10:40, 10:40] = (200, 200, 200)

    f_img = str(tmp_path / "test_built_no_veg.png")
    Image.fromarray(rgb).save(f_img)

    det = detect_target_regions(f_img, "Highlight built-up areas")
    ev_list = generate_evidence_visualizations(
        image_paths=[f_img],
        task_type="grounding",
        intermediate_data={"step_1": det},
        request_id="test_built_no_veg",
    )

    urls = [e["url"] for e in ev_list]
    assert not any("vegetation_mask.png" in u for u in urls)


def test_multispectral_ndbi_built_up_mode(tmp_path):
    """Test 5: Multispectral Sentinel-2 data with B08 (NIR) & B11 (SWIR) uses NDBI built-up mode."""
    shape = (50, 50)
    b08 = np.full(shape, 100, dtype=np.uint16)
    b11 = np.full(shape, 600, dtype=np.uint16) # High SWIR -> High NDBI

    ms_dict = {"B08": b08, "B11": b11}
    det = detect_target_regions(ms_dict, "Highlight built-up areas")
    assert det["target_type"] == "built_up"
    assert det["target_analysis"]["method"] == "NDBI-based built-up analysis"

    f_img = str(tmp_path / "test_ms_built.png")
    Image.fromarray(np.zeros((50, 50, 3), dtype=np.uint8)).save(f_img)

    ev_list = generate_evidence_visualizations(
        image_paths=[f_img],
        task_type="grounding",
        intermediate_data={"step_1": det},
        request_id="test_ms_built_ev",
    )

    captions = [e["caption"] for e in ev_list]
    built_caption = next((c for c in captions if "Built-up Mask" in c), "")
    assert "NDBI" in built_caption or "NDBI-based" in built_caption


def test_missing_b08_b11_does_not_calc_ndbi():
    """Test 6: Missing B08 or B11 band does NOT calculate NDBI."""
    shape = (50, 50)
    ms_dict = {"B04": np.full(shape, 100, dtype=np.uint16), "B08": np.full(shape, 200, dtype=np.uint16)}
    ndbi_arr, info = get_ndbi_info(ms_dict)
    assert ndbi_arr is None
    assert info["is_true_ndbi"] is False


def test_rgb_png_built_up_screening_mode(tmp_path):
    """Test 7 & 8: RGB PNG/JPEG uses RGB built-up screening and does NOT claim NDBI."""
    shape = (60, 60, 3)
    rgb = np.full(shape, 100, dtype=np.uint8)
    rgb[15:45, 15:45] = (210, 200, 190)

    f_img = str(tmp_path / "test_rgb_built.png")
    Image.fromarray(rgb).save(f_img)

    det = detect_target_regions(f_img, "Highlight built-up areas")
    assert det["target_analysis"]["method"] == "RGB built-up screening"

    ev_list = generate_evidence_visualizations(
        image_paths=[f_img],
        task_type="grounding",
        intermediate_data={"step_1": det},
        request_id="test_rgb_built_ev",
    )

    captions = [e["caption"] for e in ev_list]
    built_caption = next((c for c in captions if "Built-up Mask" in c), "")
    assert "RGB built-up screening" in built_caption
    assert "NDBI" not in built_caption


def test_built_up_mask_contains_detected_regions(tmp_path):
    """Test 9: Built-up mask contains actual detected regions."""
    shape = (60, 60, 3)
    rgb = np.full(shape, 80, dtype=np.uint8)
    rgb[15:45, 15:45] = (220, 210, 200)

    f_img = str(tmp_path / "test_built_regions.png")
    Image.fromarray(rgb).save(f_img)

    det = detect_target_regions(f_img, "Highlight built-up areas")
    assert det["built_up_analysis"] is not None
    assert det["built_up_analysis"]["built_up_pixels"] > 0
    assert det["built_up_analysis"]["built_up_percentage"] > 0.0


def test_grounding_overlay_still_generated_for_built_up(tmp_path):
    """Test 10: Grounding bounding box overlay image is still generated for built-up."""
    shape = (60, 60, 3)
    rgb = np.full(shape, 80, dtype=np.uint8)
    rgb[15:45, 15:45] = (220, 210, 200)

    f_img = str(tmp_path / "test_built_overlay.png")
    Image.fromarray(rgb).save(f_img)

    det = detect_target_regions(f_img, "Highlight built-up areas")
    ev_list = generate_evidence_visualizations(
        image_paths=[f_img],
        task_type="grounding",
        intermediate_data={"step_1": det},
        request_id="test_built_overlay",
    )

    urls = [e["url"] for e in ev_list]
    captions = [e["caption"] for e in ev_list]

    assert any("grounding_overlay.png" in u for u in urls)
    assert any("Highlighted Target:" in c for c in captions)


def test_e2e_highlight_build_up_area_api(tmp_path):
    """End-to-End API Integration Test for 'highlight build-up area'."""
    from fastapi.testclient import TestClient
    from app.main import app

    shape = (60, 60, 3)
    rgb = np.full(shape, 80, dtype=np.uint8)
    rgb[15:45, 15:45] = (220, 210, 200)

    f_img = str(tmp_path / "e2e_build_up.png")
    Image.fromarray(rgb).save(f_img)

    with TestClient(app) as client:
        with open(f_img, "rb") as f:
            resp = client.post(
                "/api/analyze",
                data={"query": "highlight build-up area"},
                files=[("images", ("e2e_build_up.png", f, "image/png"))],
            )

    assert resp.status_code == 200
    data = resp.json()

    assert data["target_analysis"]["target_type"] == "built_up"
    assert data["target_analysis"]["method"] == "RGB built-up screening"

    ev_urls = [e["url"] for e in data["evidence"]["images"]]
    ev_captions = [e["caption"] for e in data["evidence"]["images"]]

    assert any("built_up_mask.png" in u for u in ev_urls), f"built_up_mask.png missing from evidence: {ev_urls}"
    assert any("Built-up Mask" in c for c in ev_captions), f"Built-up Mask caption missing: {ev_captions}"
    assert any("grounding_overlay.png" in u for u in ev_urls), f"grounding_overlay.png missing: {ev_urls}"

