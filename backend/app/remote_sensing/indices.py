"""
Spectral & Radar Index Calculators.

Provides RGB composite, Color Infrared (CIR), Sentinel-1 SAR composite (VV/VH/ratio),
and Normalized Difference Vegetation Index (NDVI) functions.
Reuses logic from Satquery_AI_v1.
"""

import numpy as np
from app.remote_sensing.preprocessing import normalize_img


def get_rgb(s2_data) -> np.ndarray:
    """
    Extract True Color RGB composite [B04, B03, B02].
    Accepts dictionary of band arrays or 3+ channel 3D numpy array.
    Returns normalized HxWx3 array in float range [0.0, 1.0].
    """
    if isinstance(s2_data, dict):
        if "B04" in s2_data and "B03" in s2_data and "B02" in s2_data:
            stacked = np.stack([s2_data["B04"], s2_data["B03"], s2_data["B02"]], axis=-1)
            return normalize_img(stacked)
        elif len(s2_data) > 0:
            first_band = next(iter(s2_data.values()))
            if isinstance(first_band, np.ndarray) and first_band.ndim >= 2:
                h, w = first_band.shape[:2]
                b3 = s2_data.get("B03", first_band)
                b4 = s2_data.get("B04", b3)
                b2 = s2_data.get("B02", b3)
                stacked = np.stack([b4, b3, b2], axis=-1)
                return normalize_img(stacked)

    if isinstance(s2_data, np.ndarray):
        if s2_data.ndim == 2:
            stacked = np.stack([s2_data] * 3, axis=-1)
            return normalize_img(stacked)
        if s2_data.ndim == 3:
            if s2_data.shape[2] >= 3:
                return normalize_img(s2_data[:, :, :3])
            elif s2_data.shape[0] >= 3:
                stacked = np.moveaxis(s2_data[:3], 0, -1)
                return normalize_img(stacked)

    # Generic fallback array
    return np.zeros((120, 120, 3), dtype=np.float32)


def get_false_color(s2_data) -> np.ndarray:
    """
    Color Infrared (CIR) composite [B08 (NIR), B04 (Red), B03 (Green)].
    Highlights healthy vegetation in bright red.
    """
    if isinstance(s2_data, dict):
        b8 = s2_data.get("B08", s2_data.get("B8", None))
        b4 = s2_data.get("B04", s2_data.get("B4", None))
        b3 = s2_data.get("B03", s2_data.get("B3", None))

        if b8 is not None and b4 is not None and b3 is not None:
            stacked = np.stack([b8, b4, b3], axis=-1)
            return normalize_img(stacked)

    # Default to RGB if NIR band missing
    return get_rgb(s2_data)


def get_sar_composite(s1_data) -> np.ndarray:
    """
    Radar Composite [VV, VH, VV/VH ratio].
    VV: Vertical transmit / Vertical receive (surface roughness/water).
    VH: Vertical transmit / Horizontal receive (volume scattering/vegetation/structures).
    Ratio: Highlights structural boundaries.
    """
    if isinstance(s1_data, dict):
        vv = s1_data.get("VV", None)
        vh = s1_data.get("VH", None)
        if vv is not None and vh is not None:
            vv_f = vv.astype(np.float32)
            vh_f = vh.astype(np.float32)
            ratio = np.clip(vv_f / (vh_f + 1e-6), -10.0, 10.0)
            stacked = np.stack([vv_f, vh_f, ratio], axis=-1)
            return normalize_img(stacked)

    if isinstance(s1_data, np.ndarray) and s1_data.ndim == 3 and s1_data.shape[2] >= 2:
        vv = s1_data[:, :, 0]
        vh = s1_data[:, :, 1]
        ratio = np.clip(vv / (vh + 1e-6), -10.0, 10.0)
        stacked = np.stack([vv, vh, ratio], axis=-1)
        return normalize_img(stacked)

    # Fallback
    return np.zeros((120, 120, 3), dtype=np.float32)


def get_ndvi(s2_data) -> np.ndarray:
    """
    Calculates Normalized Difference Vegetation Index (NDVI) or Visual Greenness Index.
    For multispectral data with NIR (B08) and Red (B04): True NDVI = (NIR - Red) / (NIR + Red).
    For 3-band RGB visual imagery: Visual Vegetation Index (Greenness Heuristic).
    """
    arr, _ = get_ndvi_info(s2_data)
    return arr


def get_ndvi_info(s2_data) -> tuple[np.ndarray, dict]:
    """
    Calculates vegetation index array and returns scientific metadata info.

    Returns:
        (ndvi_array, info_dict)
        where info_dict has: is_true_ndvi, type_label, bands_used.
    """
    if isinstance(s2_data, dict):
        b8 = s2_data.get("B08", s2_data.get("B8", None))
        b4 = s2_data.get("B04", s2_data.get("B4", None))
        if b8 is not None and b4 is not None:
            b8_f = b8.astype(np.float32)
            b4_f = b4.astype(np.float32)
            ndvi = (b8_f - b4_f) / (b8_f + b4_f + 1e-8)
            info = {
                "is_true_ndvi": True,
                "type_label": "True NDVI (NIR B08 - Red B04)",
                "bands_used": "Red (B04), NIR (B08)",
            }
            return np.clip(ndvi, -1.0, 1.0), info

    if isinstance(s2_data, np.ndarray):
        if s2_data.ndim == 3 and s2_data.shape[2] >= 4:
            # 4+ Band GeoTIFF (Assuming Red=Band 0, NIR=Band 3)
            r = s2_data[:, :, 0].astype(np.float32)
            nir = s2_data[:, :, 3].astype(np.float32)
            ndvi = (nir - r) / (nir + r + 1e-8)
            info = {
                "is_true_ndvi": True,
                "type_label": "True NDVI (NIR Band 4 - Red Band 1)",
                "bands_used": "Red (Band 1), NIR (Band 4)",
            }
            return np.clip(ndvi, -1.0, 1.0), info

        if s2_data.ndim == 3 and s2_data.shape[2] == 3:
            # 3-channel RGB imagery (JPEG/PNG) — Heuristic visual greenness
            r = s2_data[:, :, 0].astype(np.float32)
            g = s2_data[:, :, 1].astype(np.float32)
            nir_est = g * 1.2
            vvi = (nir_est - r) / (nir_est + r + 1e-8)
            info = {
                "is_true_ndvi": False,
                "type_label": "Visual Vegetation Index (RGB Greenness Heuristic)",
                "bands_used": "Red (Channel 1), Green x1.2 (Channel 2)",
            }
            return np.clip(vvi, -1.0, 1.0), info

    # Fallback default for dictionary or unrecognized array shapes
    if isinstance(s2_data, dict):
        rgb = get_rgb(s2_data)
        return get_ndvi_info(rgb)

    h, w = (s2_data.shape[:2]) if isinstance(s2_data, np.ndarray) and s2_data.ndim >= 2 else (120, 120)
    zero_vvi = np.zeros((h, w), dtype=np.float32)
    info = {
        "is_true_ndvi": False,
        "type_label": "Visual Vegetation Index (Default)",
        "bands_used": "None",
    }
    return zero_vvi, info


def get_ndbi(s2_data) -> np.ndarray | None:
    """
    Calculates Normalized Difference Built-up Index (NDBI) when SWIR (B11) & NIR (B08) exist.
    NDBI = (SWIR - NIR) / (SWIR + NIR).
    Returns float array or None if bands are missing or for RGB imagery.
    """
    arr, _ = get_ndbi_info(s2_data)
    return arr


def get_ndbi_info(s2_data) -> tuple[np.ndarray | None, dict]:
    """
    Calculates Normalized Difference Built-up Index (NDBI) when SWIR (B11) & NIR (B08) exist.
    NDBI = (SWIR B11 - NIR B08) / (SWIR B11 + NIR B08 + 1e-8).

    Returns:
        (ndbi_array or None, info_dict)
        where info_dict has: is_true_ndbi (bool), method (str), bands_used (str).
    """
    if isinstance(s2_data, dict):
        b11 = s2_data.get("B11", s2_data.get("B11_20m", None))
        b8 = s2_data.get("B08", s2_data.get("B8", s2_data.get("B8A", None)))
        if b11 is not None and b8 is not None:
            b11_f = b11.astype(np.float32)
            b8_f = b8.astype(np.float32)
            ndbi = (b11_f - b8_f) / (b11_f + b8_f + 1e-8)
            info = {
                "is_true_ndbi": True,
                "method": "NDBI-based built-up analysis",
                "bands_used": "SWIR (B11), NIR (B08)",
            }
            return np.clip(ndbi, -1.0, 1.0), info

    if isinstance(s2_data, np.ndarray) and s2_data.ndim == 3 and s2_data.shape[2] >= 11:
        swir = s2_data[:, :, 10].astype(np.float32)
        nir = s2_data[:, :, 7].astype(np.float32)
        ndbi = (swir - nir) / (swir + nir + 1e-8)
        info = {
            "is_true_ndbi": True,
            "method": "NDBI-based built-up analysis",
            "bands_used": "SWIR (Band 11), NIR (Band 8)",
        }
        return np.clip(ndbi, -1.0, 1.0), info

    # For RGB visual imagery (JPEG/PNG) or missing B11/B08: NDBI is NOT calculated
    return None, {
        "is_true_ndbi": False,
        "method": "RGB built-up screening",
        "bands_used": "None",
    }

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


def detect_water(s2_data, metadata: dict = None) -> tuple[np.ndarray, dict]:
    """
    Centralized, unified water detector for SatQuery AI.
    Used by VQA, Captioning, and Grounding pipelines.

    Strategy:
      - For 3-channel RGB visual imagery (JPEG/PNG): Multi-evidence scoring approach using
        Blue Dominance, RGB Water Color Index (RGBWI = (B - R)/(B + R)), HSV Blue/Cyan Hue,
        and Dark Water Support (MUST NOT independently classify pixels as water).
      - For Multispectral GeoTIFFs: NDWI = (Green B03 - NIR B08) / (Green B03 + NIR B08).
      - Applies spatial morphology & connected-component noise filtering (area >= 150 px).

    Returns:
        (water_mask, method_info_dict)
        where water_mask is uint8 array (1=water, 0=non-water).
    """
    is_rgb = False
    if metadata:
        is_rgb = metadata.get("is_rgb", False) or metadata.get("input_type") == "Input: RGB Visual (JPEG/PNG)"

    if isinstance(s2_data, np.ndarray) and s2_data.ndim == 3 and s2_data.shape[2] == 3:
        is_rgb = True

    # ── 1. Multispectral GeoTIFF NDWI ──
    if isinstance(s2_data, dict) and "B03" in s2_data and "B08" in s2_data:
        g = s2_data["B03"].astype(np.float32)
        nir = s2_data["B08"].astype(np.float32)
        ndwi = (g - nir) / (g + nir + 1e-8)
        raw_mask = (ndwi > 0.0).astype(np.uint8)
        method_name = "Multispectral NDWI (B03 Green + B08 NIR)"
        cleaned_mask = _spatial_cleanup_water(raw_mask)
        return cleaned_mask, {"method": method_name, "is_rgb": False}

    # ── 2. RGB Visual Multi-Evidence Scoring ──
    if is_rgb and isinstance(s2_data, np.ndarray) and s2_data.ndim == 3:
        r = s2_data[:, :, 0].astype(np.float32)
        g = s2_data[:, :, 1].astype(np.float32)
        b = s2_data[:, :, 2].astype(np.float32)

        # Scale to [0.0, 1.0] if range is [0, 255]
        if np.max(b) > 1.5:
            r /= 255.0
            g /= 255.0
            b /= 255.0

        # Evidence 1: Blue Dominance (B must exceed R and G)
        e1_blue_dom = (b > r * 1.10) & (b > g * 1.02) & ((b - r) > 0.04)

        # Evidence 2: RGB Water Color Index (RGBWI = (B - R) / (B + R + 1e-6))
        rgbwi = (b - r) / (b + r + 1e-6)
        e2_rgbwi = (rgbwi > 0.12) & (b > g * 0.98)

        # Evidence 3: HSV Blue/Cyan Hue & Saturation
        if OPENCV_AVAILABLE:
            rgb_uint8 = (normalize_img(s2_data) * 255).astype(np.uint8)
            hsv = cv2.cvtColor(rgb_uint8, cv2.COLOR_RGB2HSV)
            h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
            # OpenCV Hue 0-180. Blue/Cyan hue is roughly 85 to 135
            e3_hsv = (h >= 85) & (h <= 135) & (s >= 25) & (v >= 25) & (b > g * 0.95)
        else:
            max_c = np.maximum(r, np.maximum(g, b))
            min_c = np.minimum(r, np.minimum(g, b))
            denom = max_c - min_c + 1e-6
            h_approx = np.where(max_c == b, 4.0 + (r - g) / denom, 0.0) / 6.0
            e3_hsv = (h_approx >= 0.50) & (h_approx <= 0.75) & (denom > 0.10) & (b > g * 0.95)

        # Evidence 4: Dark Water Supporting Condition (MUST NOT independently classify pixels)
        brightness = (r + g + b) / 3.0
        e4_dark_water = (brightness < 0.40) & (b > r * 1.20) & (b > g * 1.0) & (b > 0.15)

        # Score combination (candidate pixels require score >= 2)
        score = e1_blue_dom.astype(int) + e2_rgbwi.astype(int) + e3_hsv.astype(int) + e4_dark_water.astype(int)
        raw_mask = (score >= 2).astype(np.uint8)

        cleaned_mask = _spatial_cleanup_water(raw_mask)
        method_name = "RGB Blue-Dominance + HSV Visual Heuristic"
        return cleaned_mask, {"method": method_name, "is_rgb": True}

    # Fallback default
    if isinstance(s2_data, dict):
        h, w = 120, 120
        for v in s2_data.values():
            if isinstance(v, np.ndarray) and v.ndim >= 2:
                h, w = v.shape[:2]
                break
    elif isinstance(s2_data, np.ndarray) and s2_data.ndim >= 2:
        h, w = s2_data.shape[:2]
    else:
        h, w = (120, 120)
    return np.zeros((h, w), dtype=np.uint8), {"method": "Default Water Detector", "is_rgb": is_rgb}


def _spatial_cleanup_water(mask: np.ndarray) -> np.ndarray:
    """
    Applies spatial morphological opening/closing and removes isolated noise (<150 px).
    Ensures identical cleaned mask across statistics, grounding, and visualization.
    """
    if mask is None or mask.size == 0 or not np.any(mask):
        return mask

    if OPENCV_AVAILABLE:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)

        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned)
        final_mask = np.zeros_like(cleaned)
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] >= 150:
                final_mask[labels == i] = 1
        return final_mask

    return mask


def calculate_sequential_land_cover(s2_data, metadata: dict = None) -> dict:
    """
    Calculates sequential water-first land cover percentages.

    Order:
      1. water_mask = detect_water(...)
      2. non_water_mask = ~water_mask
      3. veg_mask = (vvi > 0.28) & non_water_mask
      4. built_mask = (built_condition) & non_water_mask
    """
    water_mask, water_info = detect_water(s2_data, metadata)
    total_pixels = int(water_mask.size)

    if total_pixels == 0:
        return {
            "water_percentage": 0.0,
            "vegetation_percentage": 0.0,
            "built_percentage": 0.0,
            "water_mask": water_mask,
            "water_method": water_info["method"],
            "is_rgb": water_info["is_rgb"],
        }

    water_pixels = int(np.count_nonzero(water_mask))
    water_pct = round((water_pixels / total_pixels) * 100.0, 1)

    non_water_mask = (water_mask == 0)

    ndvi = get_ndvi(s2_data)
    rgb = get_rgb(s2_data)

    veg_candidate = ndvi > 0.28
    veg_mask = veg_candidate & non_water_mask
    veg_pixels = int(np.count_nonzero(veg_mask))
    veg_pct = round((veg_pixels / total_pixels) * 100.0, 1)

    if isinstance(s2_data, np.ndarray) and s2_data.ndim == 3:
        arr_norm = s2_data / 255.0 if np.max(s2_data) > 1.5 else s2_data
        brightness = np.mean(arr_norm[:, :, :3], axis=2)
    elif rgb is not None and rgb.ndim == 3:
        brightness = np.mean(rgb, axis=2)
    else:
        brightness = np.zeros_like(ndvi)

    built_candidate = (ndvi < 0.20) & (brightness > 0.40)
    built_mask = built_candidate & non_water_mask
    built_pixels = int(np.count_nonzero(built_mask))
    built_pct = round((built_pixels / total_pixels) * 100.0, 1)


    return {
        "water_percentage": water_pct,
        "vegetation_percentage": veg_pct,
        "built_percentage": built_pct,
        "water_mask": water_mask,
        "water_method": water_info["method"],
        "is_rgb": water_info["is_rgb"],
    }



