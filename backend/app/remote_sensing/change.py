"""
Bi-Temporal Change Detection Engine.

Performs:
  1. Geometric alignment & resolution matching
  2. Percentile normalization
  3. Spectral / image difference calculation
  4. NDVI divergence analysis (vegetation gain/loss)
  5. Temporal water-body change analysis (NDWI or RGB water screening)
  6. Adaptive thresholding & morphological filtering
  7. Quantitative metric calculation (changed pixels, change %, veg loss/gain %, water gain/loss %)
"""

import numpy as np
from PIL import Image
from loguru import logger

from app.remote_sensing.preprocessing import load_geotiff_with_metadata, normalize_img
from app.remote_sensing.indices import get_ndvi, get_rgb, detect_water, _spatial_cleanup_water

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


def align_images(img1: np.ndarray, img2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Ensure Image 1 and Image 2 have matching pixel dimensions.
    Resizes img2 to match img1 shape if dimensions differ.
    """
    if img1.shape[:2] == img2.shape[:2]:
        return img1, img2

    target_h, target_w = img1.shape[:2]
    logger.info(f"Resampling Image 2 ({img2.shape[:2]}) to match Image 1 ({target_h}, {target_w})")

    if OPENCV_AVAILABLE:
        if img2.ndim == 2:
            resized_2 = cv2.resize(img2, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        else:
            resized_2 = cv2.resize(img2, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        return img1, resized_2

    # PIL fallback
    pil_2 = Image.fromarray((normalize_img(img2) * 255).astype(np.uint8))
    pil_2_resized = pil_2.resize((target_w, target_h), Image.Resampling.BILINEAR)
    resized_2 = np.array(pil_2_resized).astype(np.float32) / 255.0

    return img1, resized_2


def _dict_to_norm_array(data: dict) -> np.ndarray:
    """Helper to convert dictionary of bands to normalized 3D RGB array matching original band dimensions."""
    if "B04" in data and "B03" in data and "B02" in data:
        stacked = np.stack([data["B04"], data["B03"], data["B02"]], axis=-1)
        return normalize_img(stacked)

    first_band = next(iter(data.values()))
    h, w = first_band.shape[:2]
    b_green = data.get("B03", first_band)
    b_red = data.get("B04", b_green)
    b_blue = data.get("B02", b_green)
    stacked = np.stack([b_red, b_green, b_blue], axis=-1)
    return normalize_img(stacked)


def compute_change_detection(source1, source2, query: str = "") -> dict:
    """
    Execute end-to-end baseline bi-temporal change detection pipeline.

    Args:
        source1: Filepath string or image array for Date 1.
        source2: Filepath string or image array for Date 2.
        query: Natural language query string (used for query awareness).

    Returns:
        Dict with keys:
            - change_mask (2D numpy array uint8: 1=changed, 0=unchanged)
            - ndvi_diff (2D numpy array float)
            - changed_pixels (int)
            - total_pixels (int)
            - change_percentage (float)
            - vegetation_loss_percentage (float)
            - vegetation_gain_percentage (float)
            - water_analysis (dict with before/after/gain/loss/changed metrics)
            - water_change_mask (2D numpy array uint8)
            - metadata_t1 (dict)
            - metadata_t2 (dict)
    """
    metadata_t1, metadata_t2 = {}, {}

    if isinstance(source1, str):
        arr1, metadata_t1 = load_geotiff_with_metadata(source1)
    else:
        arr1 = source1

    if isinstance(source2, str):
        arr2, metadata_t2 = load_geotiff_with_metadata(source2)
    else:
        arr2 = source2

    # Check if inputs contain true multispectral data with Green (B03) and NIR (B08)
    is_ms1 = isinstance(arr1, dict) and "B03" in arr1 and "B08" in arr1
    is_ms2 = isinstance(arr2, dict) and "B03" in arr2 and "B08" in arr2

    # Normalize inputs for spatial & image difference analysis
    norm1 = _dict_to_norm_array(arr1) if isinstance(arr1, dict) else normalize_img(arr1)
    norm2 = _dict_to_norm_array(arr2) if isinstance(arr2, dict) else normalize_img(arr2)

    # 1. Align dimensions in spatial coordinate system
    norm1, norm2 = align_images(norm1, norm2)

    # 2. Image difference calculation
    if norm1.ndim == 3 and norm2.ndim == 3:
        channel_diffs = [np.abs(norm2[:, :, c] - norm1[:, :, c]) for c in range(min(norm1.shape[2], norm2.shape[2]))]
        diff = np.mean(channel_diffs, axis=0)
    else:
        diff = np.abs(norm2 - norm1)

    # 3. NDVI Divergence if multi-channel or dictionary data available
    ndvi_t1 = get_ndvi(arr1 if isinstance(arr1, dict) else norm1)
    ndvi_t2 = get_ndvi(arr2 if isinstance(arr2, dict) else norm2)
    if ndvi_t1.shape[:2] != norm1.shape[:2]:
        ndvi_t1, _ = align_images(ndvi_t1, norm1)
    if ndvi_t2.shape[:2] != norm1.shape[:2]:
        ndvi_t2, _ = align_images(ndvi_t2, norm1)
    ndvi_diff = ndvi_t2 - ndvi_t1

    # 4. Temporal Water Change Analysis
    if is_ms1 and is_ms2:
        water_mode = "ndwi"
        method_label = "NDWI-based water analysis"
        g1, nir1 = arr1["B03"].astype(np.float32), arr1["B08"].astype(np.float32)
        g2, nir2 = arr2["B03"].astype(np.float32), arr2["B08"].astype(np.float32)
        ndwi1 = (g1 - nir1) / (g1 + nir1 + 1e-8)
        ndwi2 = (g2 - nir2) / (g2 + nir2 + 1e-8)
        before_water_mask = _spatial_cleanup_water((ndwi1 > 0.0).astype(np.uint8))
        after_water_mask = _spatial_cleanup_water((ndwi2 > 0.0).astype(np.uint8))
    else:
        water_mode = "rgb_screening"
        method_label = "RGB water-change screening"
        before_water_mask, _ = detect_water(norm1, metadata_t1)
        after_water_mask, _ = detect_water(norm2, metadata_t2)

    # Ensure water masks match target pixel dimensions
    if before_water_mask.shape[:2] != norm1.shape[:2]:
        before_water_mask, _ = align_images(before_water_mask, norm1)
        before_water_mask = (before_water_mask > 0.5).astype(np.uint8)
    if after_water_mask.shape[:2] != norm1.shape[:2]:
        after_water_mask, _ = align_images(after_water_mask, norm1)
        after_water_mask = (after_water_mask > 0.5).astype(np.uint8)

    # Temporal mask comparison on aligned spatial coordinate system
    water_gain_mask = ((after_water_mask == 1) & (before_water_mask == 0)).astype(np.uint8)
    water_loss_mask = ((before_water_mask == 1) & (after_water_mask == 0)).astype(np.uint8)
    water_persistent_mask = ((before_water_mask == 1) & (after_water_mask == 1)).astype(np.uint8)
    water_changed_mask = ((water_gain_mask == 1) | (water_loss_mask == 1)).astype(np.uint8)

    valid_pixels = int(norm1.shape[0] * norm1.shape[1])
    before_w_pixels = int(np.count_nonzero(before_water_mask))
    after_w_pixels = int(np.count_nonzero(after_water_mask))
    gain_w_pixels = int(np.count_nonzero(water_gain_mask))
    loss_w_pixels = int(np.count_nonzero(water_loss_mask))
    persistent_w_pixels = int(np.count_nonzero(water_persistent_mask))
    changed_w_pixels = int(np.count_nonzero(water_changed_mask))

    before_w_pct = round((before_w_pixels / valid_pixels) * 100.0, 2) if valid_pixels > 0 else 0.0
    after_w_pct = round((after_w_pixels / valid_pixels) * 100.0, 2) if valid_pixels > 0 else 0.0
    gain_w_pct = round((gain_w_pixels / valid_pixels) * 100.0, 2) if valid_pixels > 0 else 0.0
    loss_w_pct = round((loss_w_pixels / valid_pixels) * 100.0, 2) if valid_pixels > 0 else 0.0
    persistent_w_pct = round((persistent_w_pixels / valid_pixels) * 100.0, 2) if valid_pixels > 0 else 0.0
    changed_w_pct = round((changed_w_pixels / valid_pixels) * 100.0, 2) if valid_pixels > 0 else 0.0

    water_analysis = {
        "mode": water_mode,
        "method_label": method_label,
        "before_pixels": before_w_pixels,
        "after_pixels": after_w_pixels,
        "gain_pixels": gain_w_pixels,
        "loss_pixels": loss_w_pixels,
        "persistent_pixels": persistent_w_pixels,
        "changed_pixels": changed_w_pixels,
        "total_pixels": valid_pixels,
        "before_percentage": before_w_pct,
        "after_percentage": after_w_pct,
        "gain_percentage": gain_w_pct,
        "loss_percentage": loss_w_pct,
        "persistent_percentage": persistent_w_pct,
        "changed_percentage": changed_w_pct,
    }

    # 5. Adaptive Thresholding
    mean_diff = np.mean(diff)
    std_diff = np.std(diff)
    threshold = mean_diff + 1.2 * std_diff
    threshold = max(threshold, 0.15)  # Minimum threshold to avoid noise

    raw_mask = (diff > threshold).astype(np.uint8)

    # Combine with significant NDVI or water changes
    significant_ndvi_change = (np.abs(ndvi_diff) > 0.25).astype(np.uint8)
    combined_mask = np.logical_or(raw_mask, np.logical_or(significant_ndvi_change, water_changed_mask)).astype(np.uint8)

    # 6. Morphological Cleanup (remove isolated speckle noise)
    if OPENCV_AVAILABLE:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cleaned_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel)
        cleaned_mask = cv2.morphologyEx(cleaned_mask, cv2.MORPH_CLOSE, kernel)
    else:
        cleaned_mask = combined_mask

    # 7. Quantitative Statistics & Technical Parameters
    total_pixels = int(cleaned_mask.size)
    changed_pixels = int(np.count_nonzero(cleaned_mask))
    change_pct = round((changed_pixels / total_pixels) * 100.0, 2) if total_pixels > 0 else 0.0

    veg_loss_pixels = int(np.count_nonzero(ndvi_diff < -0.18))
    veg_gain_pixels = int(np.count_nonzero(ndvi_diff > 0.18))

    veg_loss_pct = round((veg_loss_pixels / total_pixels) * 100.0, 2) if total_pixels > 0 else 0.0
    veg_gain_pct = round((veg_gain_pixels / total_pixels) * 100.0, 2) if total_pixels > 0 else 0.0

    # Format technical alignment & spatial audit info
    t1_name = metadata_t1.get("filename", "T1 Image")
    t2_name = metadata_t2.get("filename", "T2 Image")
    dim_str = f"{norm1.shape[1]}x{norm1.shape[0]} px" if norm1.ndim >= 2 else "Unknown"
    crs_str = metadata_t1.get("crs") or metadata_t2.get("crs") or "Unprojected / Non-georeferenced Pixel Space"

    if norm1.shape[:2] != norm2.shape[:2]:
        alignment_status = f"Aligned via pixel space resampling (Resampled {t2_name} to match {t1_name} {dim_str})"
    else:
        alignment_status = f"Direct Spatial Alignment (Identical dimensions {dim_str})"

    has_crs = metadata_t1.get("crs") is not None and metadata_t2.get("crs") is not None
    if has_crs and metadata_t1.get("crs") == metadata_t2.get("crs"):
        spatial_note = f"Georeferenced match confirmed under {crs_str}."
    else:
        spatial_note = "Geographic/temporal alignment is based on pixel space resampling. Spatial correspondence is unverified without explicit CRS georeferencing."

    return {
        "change_mask": cleaned_mask,
        "diff_map": diff,
        "ndvi_diff": ndvi_diff,
        "changed_pixels": changed_pixels,
        "total_pixels": total_pixels,
        "change_percentage": change_pct,
        "vegetation_loss_percentage": veg_loss_pct,
        "vegetation_gain_percentage": veg_gain_pct,
        "water_analysis": water_analysis,
        "before_water_mask": before_water_mask,
        "after_water_mask": after_water_mask,
        "water_gain_mask": water_gain_mask,
        "water_loss_mask": water_loss_mask,
        "water_persistent_mask": water_persistent_mask,
        "water_change_mask": water_changed_mask,
        "t1": t1_name,
        "t2": t2_name,
        "image_dimensions": dim_str,
        "crs": crs_str,
        "alignment_status": alignment_status,
        "threshold": f"{threshold:.4f} (Adaptive: mean + 1.2*std)",
        "spatial_correspondence": spatial_note,
        "metadata_t1": metadata_t1,
        "metadata_t2": metadata_t2,
    }
