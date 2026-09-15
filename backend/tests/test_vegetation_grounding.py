"""
Unit tests for Target-Aware Grounding & Vegetation Mask Evidence Generation.
Verifies target_type classification, vegetation mask evidence generation,
multispectral (NDVI) vs RGB vegetation screening modes, and evidence gallery selection.
"""

from pathlib import Path
import numpy as np
import pytest

from app.remote_sensing.grounding import detect_target_regions, classify_target_type
from app.remote_sensing.visualization import generate_evidence_visualizations


def test_target_type_classification():
    """Test 1: Target type classification logic including spelling variations."""
    assert classify_target_type("Highlight vegetation") == "vegetation"
    assert classify_target_type("Highlight vegitation") == "vegetation"
    assert classify_target_type("locate forest area") == "vegetation"
    assert classify_target_type("show vegitation") == "vegetation"
    assert classify_target_type("Highlight water") == "water"
    assert classify_target_type("find lake") == "water"
    assert classify_target_type("Highlight built-up areas") == "built_up"
    assert classify_target_type("locate houses") == "built_up"
    assert classify_target_type("highlight ships") == "generic"


def test_vegetation_query_generates_vegetation_mask(tmp_path):
    """Test 2 & 3: Vegetation query generates vegetation_mask.png and NOT water_mask.png."""
    shape = (80, 80, 3)
    img_arr = np.zeros(shape, dtype=np.uint8)
    # Green vegetation region
    img_arr[20:60, 20:60] = (20, 220, 40)

    from PIL import Image
    f_img = str(tmp_path / "test_veg.png")
    Image.fromarray(img_arr).save(f_img)

    det = detect_target_regions(f_img, "Highlight vegetation")
    assert det["target_type"] == "vegetation"

    intermediate = {"step_1": det}
    ev_list = generate_evidence_visualizations(
        image_paths=[f_img],
        task_type="grounding",
        intermediate_data=intermediate,
        request_id="test_veg_ev",
    )

    urls = [e["url"] for e in ev_list]
    captions = [e["caption"] for e in ev_list]

    # Verify vegetation_mask.png is in evidence, and water_mask.png is NOT
    assert any("vegetation_mask.png" in u for u in urls)
    assert not any("water_mask.png" in u for u in urls)
    assert any("Vegetation Mask" in c for c in captions)
    assert any("Highlighted Target" in c for c in captions)


def test_multispectral_ndvi_vegetation_mode(tmp_path):
    """Test 4: Multispectral Sentinel-2 data (B04 & B08) uses NDVI vegetation analysis mode."""
    shape = (50, 50)
    b04 = np.full(shape, 100, dtype=np.uint16)
    b08 = np.full(shape, 600, dtype=np.uint16) # High NIR -> High NDVI

    ms_dict = {"B04": b04, "B08": b08}
    det = detect_target_regions(ms_dict, "Highlight vegetation")
    det["target_type"] = "vegetation"

    # Save mock image for visualization
    from PIL import Image
    f_img = str(tmp_path / "test_ms.png")
    Image.fromarray(np.zeros((50, 50, 3), dtype=np.uint8)).save(f_img)

    ev_list = generate_evidence_visualizations(
        image_paths=[f_img],
        task_type="grounding",
        intermediate_data={"step_1": det},
        request_id="test_ms_veg",
    )

    captions = [e["caption"] for e in ev_list]
    veg_caption = next((c for c in captions if "Vegetation Mask" in c), "")
    assert "NDVI" in veg_caption or "NDVI-based" in veg_caption


def test_rgb_vegetation_screening_mode(tmp_path):
    """Test 5 & 6: RGB image uses RGB vegetation screening and NEVER claims NDVI."""
    shape = (50, 50, 3)
    rgb = np.zeros(shape, dtype=np.uint8)
    rgb[:, :] = (30, 200, 50) # Green

    from PIL import Image
    f_img = str(tmp_path / "test_rgb.png")
    Image.fromarray(rgb).save(f_img)

    det = detect_target_regions(f_img, "Highlight vegetation")
    assert det["target_type"] == "vegetation"

    ev_list = generate_evidence_visualizations(
        image_paths=[f_img],
        task_type="grounding",
        intermediate_data={"step_1": det},
        request_id="test_rgb_veg",
    )

    captions = [e["caption"] for e in ev_list]
    veg_caption = next((c for c in captions if "Vegetation Mask" in c), "")
    assert "RGB vegetation screening" in veg_caption
    assert "NDVI" not in veg_caption


def test_water_query_generates_water_mask(tmp_path):
    """Test 7: Water query generates water_mask.png and NOT vegetation_mask.png."""
    shape = (50, 50, 3)
    rgb = np.zeros(shape, dtype=np.uint8)
    rgb[:, :] = (20, 80, 220) # Blue water

    from PIL import Image
    f_img = str(tmp_path / "test_water.png")
    Image.fromarray(rgb).save(f_img)

    det = detect_target_regions(f_img, "Highlight water")
    assert det["target_type"] == "water"

    ev_list = generate_evidence_visualizations(
        image_paths=[f_img],
        task_type="grounding",
        intermediate_data={"step_1": det},
        request_id="test_water_grounding",
    )

    urls = [e["url"] for e in ev_list]
    assert any("water_mask.png" in u for u in urls)
    assert not any("vegetation_mask.png" in u for u in urls)


def test_built_up_query_generates_built_up_mask(tmp_path):
    """Test 8: Built-up query generates built_up_mask.png."""
    shape = (50, 50, 3)
    rgb = np.full(shape, 200, dtype=np.uint8) # High brightness

    from PIL import Image
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
    assert not any("water_mask.png" in u for u in urls)


def test_grounding_overlay_still_generated(tmp_path):
    """Test 9: Grounding bounding box overlay image is still generated."""
    shape = (60, 60, 3)
    rgb = np.full(shape, 100, dtype=np.uint8)
    rgb[10:40, 10:40] = (20, 200, 30)

    from PIL import Image
    f_img = str(tmp_path / "test_overlay.png")
    Image.fromarray(rgb).save(f_img)

    det = detect_target_regions(f_img, "Highlight vegetation")

    ev_list = generate_evidence_visualizations(
        image_paths=[f_img],
        task_type="grounding",
        intermediate_data={"step_1": det},
        request_id="test_overlay_ev",
    )

    urls = [e["url"] for e in ev_list]
    assert any("grounding_overlay.png" in u for u in urls)


def test_vegetation_end_to_end_model_pipeline(tmp_path):
    """Test 10: Full end-to-end model pipeline execution for GroundingModel + SegmentationModel + Integrator."""
    from app.models.grounding import GroundingModel, SegmentationModel
    from app.output.integrator import OutputIntegrator
    from app.agent.executor import StepResult

    shape = (80, 80, 3)
    rgb = np.zeros(shape, dtype=np.uint8)
    rgb[10:70, 10:70] = (30, 210, 40) # Green vegetation

    from PIL import Image
    f_img = str(tmp_path / "e2e_veg.png")
    Image.fromarray(rgb).save(f_img)

    context = {"images": [f_img], "query": "Highlight vegetation", "request_id": "e2e_veg_test"}
    gm = GroundingModel()
    step1_out = gm.run("detect_regions", context)

    assert step1_out["target_type"] == "vegetation"
    assert step1_out.get("vegetation_mask") is not None
    assert step1_out.get("vegetation_analysis") is not None

    context["intermediate"] = {"step_1": step1_out}
    sm = SegmentationModel()
    step2_out = sm.run("segment_regions", context)

    assert "evidence_images" in step2_out
    urls = [e["url"] for e in step2_out["evidence_images"]]
    assert any("vegetation_mask.png" in u for u in urls)
    assert not any("water_mask.png" in u for u in urls)

    sr1 = StepResult(step_num=1, model_name="grounding", action="detect_regions", output=step1_out, time_ms=10.0, success=True)
    sr2 = StepResult(step_num=2, model_name="segmentation", action="segment_regions", output=step2_out, time_ms=10.0, success=True)

    integrator = OutputIntegrator()
    final_output = integrator.integrate([sr1, sr2], task_type="grounding", query="Highlight vegetation")

    assert final_output.get("target_analysis") is not None
    assert final_output["target_analysis"]["target_type"] == "vegetation"
    assert final_output.get("vegetation_analysis") is not None
    assert final_output["vegetation_analysis"]["vegetation_percentage"] > 0
    ev_urls = [img["url"] for img in final_output["evidence"]["images"]]
    assert any("vegetation_mask.png" in u for u in ev_urls)
    assert not any("water_mask.png" in u for u in ev_urls)


def test_vegetation_evidence_order(tmp_path):
    """Test 11: Verify correct order of evidence images: RGB -> vegetation_mask -> grounding_overlay."""
    from app.models.grounding import GroundingModel, SegmentationModel

    shape = (80, 80, 3)
    rgb = np.zeros(shape, dtype=np.uint8)
    rgb[10:70, 10:70] = (30, 210, 40)

    from PIL import Image
    f_img = str(tmp_path / "order_veg.png")
    Image.fromarray(rgb).save(f_img)

    context = {"images": [f_img], "query": "Highlight vegetation", "request_id": "order_veg_test"}
    gm = GroundingModel()
    step1_out = gm.run("detect_regions", context)
    context["intermediate"] = {"step_1": step1_out}

    sm = SegmentationModel()
    step2_out = sm.run("segment_regions", context)

    images = step2_out["evidence_images"]
    assert len(images) >= 3
    assert "rgb.png" in images[0]["url"]
    assert "vegetation_mask.png" in images[1]["url"]
    assert "grounding_overlay.png" in images[2]["url"]

