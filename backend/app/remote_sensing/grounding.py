"""
Remote Sensing Grounding & Region Detection Engine.

Provides deterministic remote-sensing algorithmic fallback for target region detection
(water bodies, built-up areas, vegetation, agricultural land, infrastructure).
Extracts bounding boxes [x1, y1, x2, y2] and binary segmentation masks.
"""

import numpy as np
from PIL import Image
from loguru import logger

from app.remote_sensing.preprocessing import load_geotiff_with_metadata, normalize_img
from app.remote_sensing.indices import get_ndvi, get_rgb

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


def extract_target_keyword(query: str) -> str:
    """Extract clean target name from natural language query."""
    q = query.lower().strip()
    prefixes = [
        "highlight the ", "show me the ", "locate the ", "find the ",
        "where is the ", "where are the ", "identify the ", "mark the ",
        "highlight ", "show ", "locate ", "find ", "detect ",
    ]
    for p in prefixes:
        if q.startswith(p):
            target = q[len(p):].rstrip("?.! ")
            return target

    return q.rstrip("?.! ")


def classify_target_type(target_keyword: str) -> str:
    """Classify target keyword into a target_type category (handling spelling variations & typos)."""
    t_lower = target_keyword.lower().strip()
    if any(k in t_lower for k in ["water", "lake", "river", "pond", "sea", "ocean", "stream", "reservoir"]):
        return "water"
    elif any(k in t_lower for k in ["vegetat", "vegitat", "vegi", "vege", "forest", "tree", "plant", "green", "canopy", "foliage", "arable", "crop", "farm", "field", "agriculture"]):
        return "vegetation"
    elif any(k in t_lower for k in ["built", "build", "urban", "building", "structure", "city", "house", "road", "pavement", "infrastructure", "developed", "development"]):
        return "built_up"
    else:
        return "generic"


def reproject_points_to_wgs84(coords: list[tuple[float, float]], src_crs_str: str | None) -> list[tuple[float, float]]:
    """Reproject (x, y) coordinates from src_crs_str to EPSG:4326 (WGS84 lon, lat)."""
    if not src_crs_str or "4326" in str(src_crs_str):
        return coords
    try:
        from rasterio.warp import transform as transform_crs
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        lons, lats = transform_crs(str(src_crs_str), "EPSG:4326", xs, ys)
        return list(zip(lons, lats))
    except Exception:
        try:
            from pyproj import Transformer
            transformer = Transformer.from_crs(str(src_crs_str), "EPSG:4326", always_xy=True)
            res = []
            for x, y in coords:
                lon, lat = transformer.transform(x, y)
                res.append((lon, lat))
            return res
        except Exception:
            return coords


def convert_pixel_bbox_to_geo_bbox(
    bbox: list[float],
    transform: list[float] | None,
    crs_str: str | None,
    aoi: dict | None = None,
    img_width: int = 0,
    img_height: int = 0,
) -> list[float]:
    """
    Convert pixel bounding box [x1, y1, x2, y2] to geographic WGS84 bounding box [min_lon, min_lat, max_lon, max_lat]
    using clipped raster Affine transform and CRS reprojection to EPSG:4326.
    """
    x1, y1, x2, y2 = bbox
    min_lon, min_lat, max_lon, max_lat = None, None, None, None

    if transform and len(transform) >= 6:
        a, b, c, d, e, f = transform[:6]
        X1 = a * x1 + b * y1 + c
        Y1 = d * x1 + e * y1 + f
        X2 = a * x2 + b * y2 + c
        Y2 = d * x2 + e * y2 + f

        coords = [(X1, Y1), (X2, Y2), (X1, Y2), (X2, Y1)]
        reprojected = reproject_points_to_wgs84(coords, crs_str)
        lons = [pt[0] for pt in reprojected]
        lats = [pt[1] for pt in reprojected]

        min_lon, max_lon = min(lons), max(lons)
        min_lat, max_lat = min(lats), max(lats)

    if min_lon is None and aoi and img_width > 0 and img_height > 0:
        aoi_min_lon = aoi.get("min_lon", -180.0)
        aoi_max_lon = aoi.get("max_lon", 180.0)
        aoi_min_lat = aoi.get("min_lat", -90.0)
        aoi_max_lat = aoi.get("max_lat", 90.0)

        min_lon = aoi_min_lon + (x1 / img_width) * (aoi_max_lon - aoi_min_lon)
        max_lon = aoi_min_lon + (x2 / img_width) * (aoi_max_lon - aoi_min_lon)
        max_lat = aoi_max_lat - (y1 / img_height) * (aoi_max_lat - aoi_min_lat)
        min_lat = aoi_max_lat - (y2 / img_height) * (aoi_max_lat - aoi_min_lat)

    if min_lon is None:
        return [0.0, 0.0, 0.0, 0.0]

    if aoi:
        min_lon = max(min_lon, aoi.get("min_lon", min_lon))
        max_lon = min(max_lon, aoi.get("max_lon", max_lon))
        min_lat = max(min_lat, aoi.get("min_lat", min_lat))
        max_lat = min(max_lat, aoi.get("max_lat", max_lat))

    return [round(min_lon, 6), round(min_lat, 6), round(max_lon, 6), round(max_lat, 6)]


def detect_target_regions(source, target_keyword: str, metadata: dict | None = None) -> dict:
    """
    Detect requested target features (water, vegetation, built-up, agriculture) using
    remote-sensing spectral index thresholding & contour extraction.

    Args:
        source: File path string or image numpy array.
        target_keyword: Extracted target class query.
        metadata: Optional metadata dictionary containing transform, crs, aoi, etc.

    Returns:
        Dict with keys:
            - boxes (list[list[float]]): Bounding boxes [x1, y1, x2, y2]
            - scores (list[float]): Confidence scores
            - labels (list[str]): Detected label strings
            - mask (2D numpy array uint8): Binary segmentation mask
            - target (str): Cleaned target string
            - target_type (str): "water", "vegetation", "built_up", or "generic"
            - target_analysis (dict): Metadata describing target analysis method
            - built_up_analysis (dict|None): Coverage details for built-up target
            - is_fallback (bool): True (indicating deterministic RS fallback)
    """
    target = extract_target_keyword(target_keyword)
    target_type = classify_target_type(target)

    if isinstance(source, str):
        arr, meta = load_geotiff_with_metadata(source)
    else:
        arr = source
        meta = {}

    rgb = get_rgb(arr)
    ndvi = get_ndvi(arr)

    h, w = rgb.shape[:2]
    if ndvi.shape[:2] != (h, w):
        from app.remote_sensing.change import align_images
        ndvi, _ = align_images(ndvi, rgb)

    binary_mask = np.zeros((h, w), dtype=np.uint8)

    # ── Spectral / Index Rules ──
    water_method = ""
    veg_method = ""
    built_up_method = ""
    if target_type == "water":
        from app.remote_sensing.indices import detect_water
        water_mask, water_info = detect_water(arr, meta)
        if water_mask.shape[:2] != (h, w):
            from app.remote_sensing.change import align_images
            water_mask, _ = align_images(water_mask, rgb)
            water_mask = (water_mask > 0.5).astype(np.uint8)
        binary_mask = water_mask
        water_method = water_info.get("method", "RGB Blue-Dominance + HSV Visual Heuristic")

    elif target_type == "vegetation":
        from app.remote_sensing.indices import detect_water
        w_mask, _ = detect_water(arr, meta)
        if w_mask.shape[:2] != (h, w):
            from app.remote_sensing.change import align_images
            w_mask, _ = align_images(w_mask, rgb)
            w_mask = (w_mask > 0.5).astype(np.uint8)
        is_ms = meta.get("is_multispectral", False) or (isinstance(source, dict) and "B04" in source and "B08" in source)
        veg_threshold = 0.35 if is_ms else 0.05
        veg_mask = (ndvi > veg_threshold) & (w_mask == 0)
        binary_mask[veg_mask] = 1
        veg_method = "NDVI-based vegetation analysis" if is_ms else "RGB vegetation screening"

    elif target_type == "built_up":
        from app.remote_sensing.indices import detect_water, get_ndbi_info
        w_mask, _ = detect_water(arr, meta)
        if w_mask.shape[:2] != (h, w):
            from app.remote_sensing.change import align_images
            w_mask, _ = align_images(w_mask, rgb)
            w_mask = (w_mask > 0.5).astype(np.uint8)

        ndbi, ndbi_info = get_ndbi_info(arr)
        if ndbi_info["is_true_ndbi"] and ndbi is not None:
            if ndbi.shape[:2] != (h, w):
                from app.remote_sensing.change import align_images
                ndbi, _ = align_images(ndbi, rgb)
            built_mask = (ndbi > 0.0) & (w_mask == 0) & (ndvi < 0.30)
            built_up_method = "NDBI-based built-up analysis"
        else:
            brightness = np.mean(rgb, axis=2)
            built_mask = (ndvi < 0.15) & (brightness > 0.40) & (w_mask == 0)
            built_up_method = "RGB built-up screening"

        binary_mask[built_mask] = 1

    else:
        # Generic saliency / brightness deviation fallback
        gray = np.mean(rgb, axis=2)
        mean_v = np.mean(gray)
        std_v = np.std(gray)
        saliency_mask = np.abs(gray - mean_v) > (1.0 * std_v)
        binary_mask[saliency_mask] = 1

    # ── Morphological Cleanup & Contour Box Extraction ──
    boxes = []
    scores = []
    labels = []

    if OPENCV_AVAILABLE and np.any(binary_mask):
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        cleaned = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Filter tiny noise (<150 px or min area ratio)
            if area >= max(150.0, float(h * w * 0.001)):
                x, y, box_w, box_h = cv2.boundingRect(cnt)
                x1, y1, x2, y2 = float(x), float(y), float(x + box_w), float(y + box_h)
                boxes.append([x1, y1, x2, y2])
                # Calculate confidence based on target pixel density within box
                box_region = cleaned[int(y1):int(y2), int(x1):int(x2)]
                density = np.mean(box_region) if box_region.size > 0 else 0.5
                score = round(min(0.95, max(0.60, float(0.65 + density * 0.3))), 2)
                scores.append(score)
                labels.append(target.capitalize())

    # Fallback box if no contours found but mask has positive pixels
    if not boxes and np.any(binary_mask):
        pos_y, pos_x = np.where(binary_mask > 0)
        x1, y1 = float(np.min(pos_x)), float(np.min(pos_y))
        x2, y2 = float(np.max(pos_x)), float(np.max(pos_y))
        boxes.append([x1, y1, x2, y2])
        scores.append(0.75)
        labels.append(target.capitalize())

    is_ms = meta.get("is_multispectral", False) or (isinstance(source, dict) and "B04" in source and "B08" in source)
    if target_type == "vegetation":
        method = veg_method or ("NDVI-based vegetation analysis" if is_ms else "RGB vegetation screening")
    elif target_type == "water":
        method = water_method or "Spectral Reflectance"
    elif target_type == "built_up":
        method = built_up_method or "RGB built-up screening"
    else:
        method = "Spectral & Brightness Reflectance"

    built_up_pixels = int(np.sum(binary_mask > 0)) if target_type == "built_up" else 0
    total_pixels = int(binary_mask.size) if binary_mask.size > 0 else 0
    built_up_percentage = round((built_up_pixels / total_pixels * 100.0), 2) if total_pixels > 0 else 0.0

    built_up_analysis = {
        "method": method,
        "built_up_pixels": built_up_pixels,
        "built_up_percentage": built_up_percentage,
    } if target_type == "built_up" else None

    veg_pixels = int(np.sum(binary_mask > 0)) if target_type == "vegetation" else 0
    veg_percentage = round((veg_pixels / total_pixels * 100.0), 2) if total_pixels > 0 else 0.0

    vegetation_analysis = {
        "method": method,
        "vegetation_pixels": veg_pixels,
        "vegetation_percentage": veg_percentage,
    } if target_type == "vegetation" else None

    target_analysis = {
        "target": target,
        "target_type": target_type,
        "method": method,
        "mask_available": bool(np.any(binary_mask)),
    }

    meta_data = metadata or {}
    transform = meta.get("transform") or meta_data.get("transform")
    crs = meta.get("crs") or meta_data.get("crs")
    aoi = meta_data.get("aoi") or meta.get("aoi")

    geo_boxes = [
        convert_pixel_bbox_to_geo_bbox(box, transform, crs, aoi, w, h)
        for box in boxes
    ]

    return {
        "boxes": boxes,
        "geo_boxes": geo_boxes,
        "scores": scores,
        "labels": labels,
        "mask": binary_mask,
        "water_mask": binary_mask if target_type == "water" else None,
        "water_method": water_method,
        "vegetation_mask": binary_mask if target_type == "vegetation" else None,
        "vegetation_method": veg_method,
        "built_up_mask": binary_mask if target_type == "built_up" else None,
        "built_up_method": built_up_method,
        "target": target,
        "target_type": target_type,
        "target_analysis": target_analysis,
        "vegetation_analysis": vegetation_analysis,
        "built_up_analysis": built_up_analysis,
        "is_fallback": True,
    }
