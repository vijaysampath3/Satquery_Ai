"""
Oil Spill Detection Engine for Sentinel-1 SAR Imagery.

Supports two scientific execution modes:
  1. GeoTIFF Mode ("Analysis mode: Sentinel-1 SAR VV/VH"):
     Full VV/VH calibrated radar backscatter analysis with geospatial resolution.
  2. Visual Screening Mode ("Analysis mode: Sentinel-1 SAR visual screening"):
     Grayscale SAR intensity screening for PNG/JPEG screenshots/proxies without inventing km².

Uses scientifically cautious terminology: "potential oil-spill candidate" / "oil-slick-like dark region".
"""

from pathlib import Path
from typing import Optional, Union
import numpy as np
from loguru import logger

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

from app.remote_sensing.preprocessing import load_geotiff_with_metadata, normalize_img


def detect_oil_spill(
    image_source: Union[str, Path, np.ndarray],
    metadata: Optional[dict] = None,
    query: str = "",
) -> dict:
    """
    Detect potential oil-spill slick candidates in Sentinel-1 SAR imagery (GeoTIFF or SAR visual PNG/JPEG).

    Args:
        image_source: File path (str/Path) or numpy array of SAR image.
        metadata: Optional image metadata dictionary.
        query: User query string.

    Returns:
        Structured dictionary compatible with PipelineExecutor output.
    """
    if metadata is None:
        metadata = {}

    path_str = str(image_source) if isinstance(image_source, (str, Path)) else ""
    p_obj = Path(path_str) if path_str else None
    ext = p_obj.suffix.lower() if p_obj else ""

    # Extract modality info from metadata or query
    modalities = metadata.get("modalities", ["optical"])
    modality_str = str(metadata.get("modality", modalities[0] if modalities else "optical")).lower()
    is_explicit_sar = (
        modality_str in ["sar", "radar"]
        or "sar" in modalities
        or "radar" in modalities
        or metadata.get("is_sar_visual", False)
        or any(k in path_str.lower() for k in ["sar", "sentinel1", "s1", "vv", "vh", "radar"])
    )

    # Load image array if path was provided
    loaded_meta = {}
    if isinstance(image_source, (str, Path)):
        try:
            arr, loaded_meta = load_geotiff_with_metadata(str(image_source), modality=modality_str)
            for k, v in loaded_meta.items():
                if k not in metadata or metadata[k] is None:
                    metadata[k] = v
        except Exception as e:
            logger.error(f"Failed to load SAR image {image_source}: {e}")
            return _non_sar_capability_response()
    else:
        arr = image_source

    if arr is None or arr.size == 0:
        return _non_sar_capability_response()

    # Check if input is standard colorful RGB image without SAR indication
    is_rgb_visual = metadata.get("is_rgb", False) or metadata.get("input_type") == "Input: RGB Visual (JPEG/PNG)"
    is_near_grayscale = False

    if arr.ndim == 3 and arr.shape[2] >= 3:
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        diff_rg = float(np.mean(np.abs(r - g)))
        diff_gb = float(np.mean(np.abs(g - b)))
        if diff_rg < 12.0 and diff_gb < 12.0:
            is_near_grayscale = True

    # Check if image can be processed as SAR (GeoTIFF or SAR Visual)
    is_oil_query = any(k in query.lower() for k in ["oil", "spill", "slick", "leak", "contaminated"])
    if is_rgb_visual and ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
        if not is_explicit_sar and not (is_near_grayscale and is_oil_query):
            return _non_sar_capability_response()

    # ── Determine Execution Mode & Modality Badge ──
    is_geotiff = ext in [".tif", ".tiff", ".geotiff"] or (metadata.get("crs") is not None and not metadata.get("is_sar_visual"))

    if is_geotiff:
        analysis_mode = "Sentinel-1 SAR VV/VH"
        method_name = "Sentinel-1 SAR backscatter analysis"
        input_badge = metadata.get("input_type", "Input: Sentinel-1 SAR GeoTIFF")
        status_text = "Sentinel-1 SAR VV/VH Backscatter Engine"
        has_geo_res = True
    else:
        analysis_mode = "Sentinel-1 SAR visual screening"
        method_name = "Sentinel-1 SAR visual screening"
        input_badge = "Input: Sentinel-1 SAR Visual (PNG/JPEG)"
        status_text = "Sentinel-1 SAR Visual Screening Engine"
        has_geo_res = False

    # ── Extract Intensity / Backscatter Channel ──
    vh_arr = None
    if arr.ndim == 2:
        intensity_arr = arr.astype(np.float32)
    elif arr.ndim == 3:
        if arr.shape[2] == 1:
            intensity_arr = arr[:, :, 0].astype(np.float32)
        elif arr.shape[2] == 2 and is_geotiff:
            intensity_arr = arr[:, :, 0].astype(np.float32)
            vh_arr = arr[:, :, 1].astype(np.float32)
        elif arr.shape[2] >= 3:
            # Convert RGB to grayscale intensity proxy
            intensity_arr = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.float32)
        else:
            intensity_arr = arr[:, :, 0].astype(np.float32)
    else:
        intensity_arr = arr.astype(np.float32)

    h, w = intensity_arr.shape[:2]
    total_pixels = h * w
    intensity_norm = normalize_img(intensity_arr)

    # ── Identify Sea/Water Analysis Region ──
    land_mask = intensity_norm > 0.65
    sea_mask = ~land_mask
    sea_pixel_count = int(np.count_nonzero(sea_mask))

    if sea_pixel_count < 50:
        sea_mask = np.ones((h, w), dtype=bool)
        sea_pixel_count = total_pixels

    # ── Detect Dark Slick Candidate Regions ──
    raw_std = float(np.std(intensity_arr))
    raw_range = float(np.max(intensity_arr) - np.min(intensity_arr))

    # Reject uniform low-variance images (e.g. noise-only scenes)
    if raw_range < 15.0 or raw_std < 4.0:
        final_mask = np.zeros((h, w), dtype=np.uint8)
        sar_display_2d = (intensity_norm * 255).astype(np.uint8)
        sar_display = np.stack([sar_display_2d] * 3, axis=-1)
        ans = (
            f"OBSERVED: No potential oil-spill candidates detected in the analyzed scene (Analysis mode: {analysis_mode}).\n"
            f"- Analyzed Sea Area: {sea_pixel_count:,} pixels\n"
            f"- Intensity Distribution: Uniform open sea radar return\n"
            f"INFERRED: Intensity distribution across the sea surface appears uniform with no prominent wave-dampened dark slicks observed. "
            f"Dark SAR regions can also result from calm water, wind shadows and other look-alikes; expert verification is required."
        )
        return {
            "task": "OIL_SPILL",
            "analysis_mode": analysis_mode,
            "detected": False,
            "candidate_count": 0,
            "affected_pixel_count": 0,
            "affected_percentage": 0.0,
            "sea_pixel_count": sea_pixel_count,
            "total_pixels": total_pixels,
            "regions": [],
            "mask": final_mask,
            "overlay": sar_display,
            "sar_display": sar_display,
            "method": method_name,
            "warning": "Potential oil-spill candidates require expert verification. Dark SAR regions can also result from calm water, wind shadows and other look-alikes; expert verification is required.",
            "answer": ans,
            "status_text": status_text,
            "input_badge": input_badge,
            "is_valid_sar": True,
            "has_geospatial_resolution": has_geo_res,
        }

    sea_values = intensity_norm[sea_mask]
    sea_mean = float(np.mean(sea_values))
    sea_std = float(np.std(sea_values))

    dark_thresh = max(0.01, sea_mean - 1.15 * sea_std) if sea_std > 0.01 else max(0.01, sea_mean * 0.70)
    candidate_raw = (intensity_norm < dark_thresh) & sea_mask

    if vh_arr is not None:
        vh_norm = normalize_img(vh_arr)
        vh_thresh = max(0.01, float(np.mean(vh_norm[sea_mask])) * 0.85)
        candidate_raw = candidate_raw & (vh_norm < vh_thresh)

    # ── Morphological Cleanup & Connected Components ──
    mask_uint8 = candidate_raw.astype(np.uint8)
    if OPENCV_AVAILABLE:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cleaned = cv2.morphologyEx(mask_uint8, cv2.MORPH_OPEN, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
    else:
        cleaned = mask_uint8

    candidate_regions = []
    final_mask = np.zeros((h, w), dtype=np.uint8)

    if OPENCV_AVAILABLE:
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cleaned)
        region_id = 1
        for i in range(1, num_labels):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if area < 20 or area > (sea_pixel_count * 0.50):
                continue

            x1 = int(stats[i, cv2.CC_STAT_LEFT])
            y1 = int(stats[i, cv2.CC_STAT_TOP])
            width_r = int(stats[i, cv2.CC_STAT_WIDTH])
            height_r = int(stats[i, cv2.CC_STAT_HEIGHT])
            x2 = x1 + width_r
            y2 = y1 + height_r

            cx = float(centroids[i][0])
            cy = float(centroids[i][1])

            region_mask = (labels == i)
            region_mean_bs = float(np.mean(intensity_norm[region_mask]))
            contrast_ratio = round(float((sea_mean - region_mean_bs) / (sea_mean + 1e-6)), 2)

            if contrast_ratio < 0.15:
                continue

            final_mask[region_mask] = 255
            region_dict = {
                "id": region_id,
                "type": "potential oil-spill candidate" if has_geo_res else "oil-slick-like dark region",
                "bbox": [x1, y1, x2, y2],
                "centroid": [round(cx, 1), round(cy, 1)],
                "pixel_count": area,
                "contrast_ratio": contrast_ratio,
            }
            # Only include km² if geospatial resolution is available
            if has_geo_res:
                region_dict["area_km2"] = round(area * 0.0001, 3)

            candidate_regions.append(region_dict)
            region_id += 1
    else:
        if np.any(cleaned):
            final_mask = cleaned * 255
            area = int(np.count_nonzero(cleaned))
            region_dict = {
                "id": 1,
                "type": "potential oil-spill candidate" if has_geo_res else "oil-slick-like dark region",
                "bbox": [0, 0, w, h],
                "centroid": [w / 2.0, h / 2.0],
                "pixel_count": area,
                "contrast_ratio": 0.40,
            }
            if has_geo_res:
                region_dict["area_km2"] = round(area * 0.0001, 3)
            candidate_regions.append(region_dict)

    candidate_count = len(candidate_regions)
    affected_pixel_count = int(np.count_nonzero(final_mask))
    affected_percentage = round((affected_pixel_count / max(1, sea_pixel_count)) * 100.0, 2)
    detected = candidate_count > 0

    # ── Visual Overlay Generation ──
    sar_display_2d = (intensity_norm * 255).astype(np.uint8)
    sar_display = np.stack([sar_display_2d] * 3, axis=-1)

    overlay = sar_display.copy()
    if detected:
        slick_indices = final_mask > 0
        overlay[slick_indices, 0] = np.clip(overlay[slick_indices, 0] * 0.4 + 255 * 0.6, 0, 255).astype(np.uint8)
        overlay[slick_indices, 1] = np.clip(overlay[slick_indices, 1] * 0.3 + 30 * 0.7, 0, 255).astype(np.uint8)
        overlay[slick_indices, 2] = np.clip(overlay[slick_indices, 2] * 0.4 + 120 * 0.6, 0, 255).astype(np.uint8)

        if OPENCV_AVAILABLE:
            for r in candidate_regions:
                bx1, by1, bx2, by2 = r["bbox"]
                cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (255, 0, 128), 2)
                label = f"Candidate #{r['id']}"
                cv2.putText(overlay, label, (bx1, max(15, by1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # ── Formulate Scientifically Cautious Response Text ──
    disclaimer = "Dark SAR regions can also result from calm water, wind shadows and other look-alikes; expert verification is required."

    if detected:
        if has_geo_res:
            total_area_km2 = sum(r.get("area_km2", 0.0) for r in candidate_regions)
            area_str = f"**{affected_pixel_count:,}** pixels (~{total_area_km2:.2f} km²)"
        else:
            area_str = f"**{affected_pixel_count:,}** pixels"

        ans = (
            f"OBSERVED: Potential oil-spill candidate detected in the scene (Analysis mode: {analysis_mode}).\n"
            f"- Identified Candidates: **{candidate_count}** potential oil-spill candidate(s)\n"
            f"- Affected Area: {area_str}\n"
            f"- Sea Surface Coverage: **{affected_percentage}%** of analyzed sea area\n"
            f"INFERRED: Highlighted mask displays low-intensity dark regions on sea surface where wave dampening is observed. "
            f"{disclaimer}"
        )
    else:
        ans = (
            f"OBSERVED: No potential oil-spill candidates detected in the analyzed scene (Analysis mode: {analysis_mode}).\n"
            f"- Analyzed Sea Area: {sea_pixel_count:,} pixels\n"
            f"- Intensity Distribution: Uniform open sea radar return\n"
            f"INFERRED: Intensity distribution across the sea surface appears uniform with no prominent wave-dampened dark slicks observed. "
            f"{disclaimer}"
        )

    return {
        "task": "OIL_SPILL",
        "analysis_mode": analysis_mode,
        "detected": detected,
        "candidate_count": candidate_count,
        "affected_pixel_count": affected_pixel_count,
        "affected_percentage": affected_percentage,
        "sea_pixel_count": sea_pixel_count,
        "total_pixels": total_pixels,
        "regions": candidate_regions,
        "mask": final_mask,
        "overlay": overlay,
        "sar_display": sar_display,
        "method": method_name,
        "warning": f"Potential oil-spill candidates require expert verification. {disclaimer}",
        "answer": ans,
        "status_text": status_text,
        "input_badge": input_badge,
        "is_valid_sar": True,
        "has_geospatial_resolution": has_geo_res,
    }


def _non_sar_capability_response() -> dict:
    """Return clear capability message when user uploads ordinary RGB JPEG/PNG for oil spill analysis."""
    disclaimer = "Dark SAR regions can also result from calm water, wind shadows and other look-alikes; expert verification is required."
    return {
        "task": "OIL_SPILL",
        "analysis_mode": "None",
        "detected": False,
        "candidate_count": 0,
        "affected_pixel_count": 0,
        "affected_percentage": 0.0,
        "sea_pixel_count": 0,
        "total_pixels": 0,
        "regions": [],
        "mask": None,
        "overlay": None,
        "sar_display": None,
        "method": "Sentinel-1 SAR backscatter analysis",
        "warning": f"Oil-spill analysis requires suitable Sentinel-1 SAR imagery. {disclaimer}",
        "answer": (
            "OBSERVED: Uploaded input is an ordinary RGB visual image.\n"
            "INFERRED: Oil-spill analysis requires suitable Sentinel-1 SAR imagery."
        ),
        "status_text": "Status: Modality Mismatch Error",
        "input_badge": "Input: RGB Visual (JPEG/PNG)",
        "is_valid_sar": False,
        "has_geospatial_resolution": False,
    }
