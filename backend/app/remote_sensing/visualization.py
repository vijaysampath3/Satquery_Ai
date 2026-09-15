"""
Visual Evidence Generator for SatQuery AI.

Generates and saves visual evidence images to the backend /results directory:
  - True Color RGB (Date 1 & Date 2)
  - False Color CIR (Color Infrared)
  - SAR Composite (VV/VH/ratio)
  - NDVI Heatmap
  - Target Grounding Bounding Box & Mask Overlay
  - Bi-Temporal Change Map Overlay
  - Temporal Water Change Map Overlay (Gain, Loss, Persistent Water)
"""

import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from loguru import logger

from app.remote_sensing.preprocessing import load_geotiff_with_metadata, normalize_img
from app.remote_sensing.indices import get_rgb, get_false_color, get_sar_composite, get_ndvi

from app.utils.config import settings

RESULTS_DIR = settings.RESULTS_DIR


def ensure_results_dir(request_id: str = "") -> Path:
    """Ensure results folder exists for request."""
    out_dir = RESULTS_DIR / request_id if request_id else RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def save_array_to_png(arr: np.ndarray, out_path: Path, cmap: str = None):
    """Save 2D or 3D numpy array to PNG image."""
    try:
        if arr.ndim == 3 and arr.shape[2] == 3:
            img = Image.fromarray((normalize_img(arr) * 255).astype(np.uint8))
        elif arr.ndim == 2:
            if cmap == "RdYlGn":
                norm = (np.clip(arr, -1.0, 1.0) + 1.0) / 2.0
                r = (1.0 - norm) * 255
                g = norm * 255
                b = np.zeros_like(norm)
                rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
                img = Image.fromarray(rgb)
            elif cmap == "coolwarm":
                norm = (np.clip(arr, -0.5, 0.5) + 0.5)
                r = norm * 255
                g = (1.0 - np.abs(norm - 0.5) * 2) * 200
                b = (1.0 - norm) * 255
                rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
                img = Image.fromarray(rgb)
            else:
                img = Image.fromarray((normalize_img(arr) * 255).astype(np.uint8))
        else:
            img = Image.fromarray((normalize_img(arr) * 255).astype(np.uint8))

        img.save(str(out_path))
    except Exception as e:
        logger.error(f"Failed to save image to {out_path}: {e}")


def generate_evidence_visualizations(
    image_paths: list[str],
    task_type: str,
    intermediate_data: dict,
    request_id: str = "demo",
) -> list[dict]:
    """
    Generate all relevant evidence images for the given task and return URL info list.

    Returns:
        List of dicts: [{"url": "/results/req_id/filename.png", "caption": "..."}]
    """
    out_dir = ensure_results_dir(request_id)
    evidence_list = []

    if not image_paths:
        return evidence_list

    primary_path = image_paths[0]
    arr_t1, meta_t1 = load_geotiff_with_metadata(primary_path)
    is_ms = meta_t1.get("is_multispectral", False)

    # 1. Date 1 True Color RGB
    rgb_path = out_dir / "rgb.png"
    rgb_arr = get_rgb(arr_t1)
    save_array_to_png(rgb_arr, rgb_path)
    evidence_list.append({
        "url": f"/results/{request_id}/rgb.png",
        "caption": "Date 1 True Color RGB" if len(image_paths) >= 2 else "True Color RGB",
    })

    # Date 2 True Color RGB (if second image available)
    if len(image_paths) >= 2:
        arr_t2, meta_t2 = load_geotiff_with_metadata(image_paths[1])
        rgb_arr_2 = get_rgb(arr_t2)
        rgb_path_2 = out_dir / "rgb_t2.png"
        save_array_to_png(rgb_arr_2, rgb_path_2)
        evidence_list.append({
            "url": f"/results/{request_id}/rgb_t2.png",
            "caption": "Date 2 True Color RGB",
        })

    # 2. Single Image Target-Aware Feature Mask Evidence
    step1 = intermediate_data.get("step_1", {})
    target = step1.get("target", "Target").lower()
    from app.remote_sensing.grounding import classify_target_type
    target_type = step1.get("target_type") or classify_target_type(target)

    if len(image_paths) == 1:
        if target_type == "water":
            from app.remote_sensing.indices import detect_water
            water_mask = step1.get("water_mask")
            if water_mask is None:
                water_mask, water_info = detect_water(arr_t1, meta_t1)
                water_method = water_info.get("method", "Visual / NDWI Heuristic")
            else:
                water_method = step1.get("water_method", "Visual / NDWI Heuristic")

            if water_mask is not None:
                c_h, c_w = water_mask.shape[:2]
                w_colored = np.zeros((c_h, c_w, 3), dtype=np.uint8)
                w_colored[water_mask > 0] = (0, 150, 255)
                w_colored[water_mask == 0] = (40, 40, 40)
                w_path = out_dir / "water_mask.png"
                Image.fromarray(w_colored).save(str(w_path))
                evidence_list.append({
                    "url": f"/results/{request_id}/water_mask.png",
                    "caption": f"Water Mask ({water_method})",
                })

        elif target_type == "vegetation":
            veg_mask = step1.get("vegetation_mask")
            if veg_mask is None and step1.get("target_type") == "vegetation":
                veg_mask = step1.get("mask")
            if veg_mask is None:
                from app.remote_sensing.indices import get_ndvi, detect_water
                w_mask, _ = detect_water(arr_t1, meta_t1)
                ndvi = get_ndvi(arr_t1)
                veg_threshold = 0.35 if is_ms else 0.05
                veg_mask = (ndvi > veg_threshold) & (w_mask == 0)

            if veg_mask is not None:
                c_h, c_w = veg_mask.shape[:2]
                v_colored = np.zeros((c_h, c_w, 3), dtype=np.uint8)
                v_colored[veg_mask > 0] = (0, 220, 100)
                v_colored[veg_mask == 0] = (40, 40, 40)
                v_path = out_dir / "vegetation_mask.png"
                Image.fromarray(v_colored).save(str(v_path))

                target_an = step1.get("target_analysis", {})
                method_used = target_an.get("method", "") or step1.get("vegetation_method", "")
                is_ms_veg = meta_t1.get("is_multispectral", False) or (isinstance(arr_t1, dict) and "B04" in arr_t1 and "B08" in arr_t1) or "NDVI" in method_used
                caption = "Vegetation Mask (NDVI-based vegetation analysis)" if is_ms_veg else "Vegetation Mask (RGB vegetation screening)"
                evidence_list.append({
                    "url": f"/results/{request_id}/vegetation_mask.png",
                    "caption": caption,
                })

        elif target_type == "built_up":
            b_mask = step1.get("built_up_mask")
            if b_mask is None and step1.get("target_type") == "built_up":
                b_mask = step1.get("mask")
            if b_mask is None:
                from app.remote_sensing.indices import get_ndvi, detect_water, get_ndbi_info
                w_mask, _ = detect_water(arr_t1, meta_t1)
                ndvi = get_ndvi(arr_t1)
                ndbi, ndbi_info = get_ndbi_info(arr_t1)
                if ndbi_info["is_true_ndbi"] and ndbi is not None:
                    b_mask = (ndbi > 0.0) & (w_mask == 0) & (ndvi < 0.30)
                else:
                    brightness = np.mean(rgb_arr, axis=2)
                    b_mask = (ndvi < 0.15) & (brightness > 0.40) & (w_mask == 0)

            if b_mask is not None:
                c_h, c_w = b_mask.shape[:2]
                b_colored = np.zeros((c_h, c_w, 3), dtype=np.uint8)
                b_colored[b_mask > 0] = (255, 170, 0)
                b_colored[b_mask == 0] = (40, 40, 40)
                b_path = out_dir / "built_up_mask.png"
                Image.fromarray(b_colored).save(str(b_path))

                target_an = step1.get("target_analysis", {})
                method_used = target_an.get("method", "") or step1.get("built_up_method", "")
                is_ndbi = (isinstance(arr_t1, dict) and "B11" in arr_t1 and ("B08" in arr_t1 or "B8" in arr_t1)) or "NDBI" in method_used
                caption = "Built-up Mask (NDBI-based built-up analysis)" if is_ndbi else "Built-up Mask (RGB built-up screening)"
                evidence_list.append({
                    "url": f"/results/{request_id}/built_up_mask.png",
                    "caption": caption,
                })

    # 3. Grounding Bounding Box Overlay
    if "grounding" in task_type:
        boxes = step1.get("boxes", [])
        labels = step1.get("labels", [])
        scores = step1.get("scores", [])
        target_name = step1.get("target", "Target")

        if boxes:
            overlay_img = Image.fromarray((rgb_arr * 255).astype(np.uint8)).convert("RGB")
            draw = ImageDraw.Draw(overlay_img)

            for box, label, score in zip(boxes, labels, scores):
                x1, y1, x2, y2 = [int(c) for c in box]
                draw.rectangle([x1, y1, x2, y2], outline=(0, 150, 255), width=3)
                text = f"{label} ({score:.2f})"
                draw.rectangle([x1, max(0, y1 - 18), x1 + len(text) * 8, y1], fill=(0, 120, 255))
                draw.text((x1 + 2, max(0, y1 - 16)), text, fill="white")

            ground_path = out_dir / "grounding_overlay.png"
            overlay_img.save(str(ground_path))
            evidence_list.append({
                "url": f"/results/{request_id}/grounding_overlay.png",
                "caption": f"Highlighted Target: {target_name}",
            })

    # 4. Change Map & Water Change Map
    if "change" in task_type or len(image_paths) >= 2:
        change_info = intermediate_data.get("step_1", {})
        change_mask = change_info.get("change_mask", None)

        if change_mask is not None:
            c_h, c_w = change_mask.shape[:2]
            colored_map = np.zeros((c_h, c_w, 3), dtype=np.uint8)
            colored_map[change_mask > 0] = (255, 60, 60)      # Red = Changed
            colored_map[change_mask == 0] = (200, 200, 200)   # Gray = Unchanged

            cmap_path = out_dir / "change_map.png"
            Image.fromarray(colored_map).save(str(cmap_path))
            evidence_list.append({
                "url": f"/results/{request_id}/change_map.png",
                "caption": f"Change Map ({change_info.get('change_percentage', 0)}% area changed)",
            })

        # Temporal Water Change Map
        water_gain_mask = change_info.get("water_gain_mask")
        water_loss_mask = change_info.get("water_loss_mask")
        water_persistent_mask = change_info.get("water_persistent_mask")

        if water_gain_mask is not None and water_loss_mask is not None:
            c_h, c_w = water_gain_mask.shape[:2]
            w_map = np.zeros((c_h, c_w, 3), dtype=np.uint8)

            # Background: Neutral dark gray (35, 35, 40)
            w_map[:, :] = (35, 35, 40)

            # Persistent water: Dark Blue (0, 70, 200)
            if water_persistent_mask is not None:
                w_map[water_persistent_mask > 0] = (0, 70, 200)

            # Water gain: Bright Cyan / Blue (0, 220, 255)
            w_map[water_gain_mask > 0] = (0, 220, 255)

            # Water loss: Red (255, 50, 50)
            w_map[water_loss_mask > 0] = (255, 50, 50)

            w_change_path = out_dir / "water_change_map.png"
            img_w_change = Image.fromarray(w_map)
            img_w_change.save(str(w_change_path))

            wm_info = change_info.get("water_analysis", {})
            gain_p = wm_info.get("gain_percentage", 0.0)
            loss_p = wm_info.get("loss_percentage", 0.0)
            mode_p = "NDWI" if wm_info.get("mode") == "ndwi" else "RGB Screening"

            evidence_list.append({
                "url": f"/results/{request_id}/water_change_map.png",
                "caption": f"Water Change Map (Gain: {gain_p}%, Loss: {loss_p}%, Mode: {mode_p})",
            })

    # 5. True NDVI Heatmap ONLY for Multispectral GeoTIFF
    if is_ms:
        ndvi_arr = get_ndvi(arr_t1)
        ndvi_path = out_dir / "ndvi.png"
        save_array_to_png(ndvi_arr, ndvi_path, cmap="RdYlGn")
        evidence_list.append({
            "url": f"/results/{request_id}/ndvi.png",
            "caption": "True NDVI Vegetation Index Map (B04 Red, B08 NIR)",
        })

    # 6. SAR Composite
    if len(image_paths) >= 2 and ("sar" in task_type or "optical_sar" in task_type):
        sar_arr, _ = load_geotiff_with_metadata(image_paths[1])
        sar_comp = get_sar_composite(sar_arr)
        sar_path = out_dir / "sar_composite.png"
        save_array_to_png(sar_comp, sar_path)
        evidence_list.append({
            "url": f"/results/{request_id}/sar_composite.png",
            "caption": "Sentinel-1 SAR Radar Composite",
        })

    return evidence_list
