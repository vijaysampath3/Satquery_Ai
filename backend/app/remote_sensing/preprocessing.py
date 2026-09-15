"""
Preprocessing Utilities for Satellite Imagery.

Handles rasterio GeoTIFF parsing, geospatial metadata preservation,
band identification, 2%-98% percentile normalization, and band sanity validation.
Reuses and standardizes logic from Satquery_AI_v1.
"""

import os
import tempfile
import numpy as np
from pathlib import Path
from PIL import Image
from loguru import logger

# Try rasterio for GeoTIFFs, fallback to PIL if not installed or corrupted
try:
    import rasterio
    RASTERIO_AVAILABLE = True
except ImportError:
    RASTERIO_AVAILABLE = False

S2_BANDS = ["B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"]
S1_BANDS = ["VV", "VH"]


def normalize_img(arr: np.ndarray) -> np.ndarray:
    """
    Percentile stretch (2nd to 98th percentile) and clip array into [0.0, 1.0].
    Preserves satellite dynamic range while removing outliers.
    """
    if arr is None or arr.size == 0:
        return arr
    arr_float = arr.astype(np.float32)
    # Filter out NaNs if present
    valid_mask = ~np.isnan(arr_float)
    if not np.any(valid_mask):
        return np.zeros_like(arr_float)

    p2, p98 = np.nanpercentile(arr_float, 2), np.nanpercentile(arr_float, 98)
    if p98 == p2:
        if p98 > 1.0:
            return np.clip(arr_float / 255.0, 0.0, 1.0)
        return arr_float

    clipped = np.clip((arr_float - p2) / (p98 - p2), 0.0, 1.0)
    return clipped


def load_geotiff_with_metadata(image_path: str, modality: str = "optical") -> tuple[np.ndarray, dict]:
    """
    Load a GeoTIFF image file using rasterio (or PIL fallback) and preserve geospatial metadata.

    Returns:
        (image_array, metadata_dict)
        where metadata_dict includes: crs, transform, bounds, resolution, width, height, bands.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image path does not exist: {image_path}")

    metadata = {
        "path": str(path),
        "filename": path.name,
        "format": path.suffix.lower().lstrip("."),
        "crs": None,
        "transform": None,
        "bounds": None,
        "resolution": None,
        "width": 0,
        "height": 0,
        "bands": 1,
    }

    if RASTERIO_AVAILABLE and path.suffix.lower() in [".tif", ".tiff", ".geotiff"]:
        try:
            with rasterio.open(str(path)) as src:
                arr = src.read()  # Shape: (count, height, width)
                metadata["width"] = src.width
                metadata["height"] = src.height
                metadata["bands"] = src.count
                metadata["crs"] = str(src.crs) if src.crs else "EPSG:4326 (Default)"
                metadata["transform"] = list(src.transform) if src.transform else None
                metadata["bounds"] = [src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top] if src.bounds else None
                metadata["resolution"] = [src.res[0], src.res[1]] if src.res else None

                if arr.shape[0] == 1:
                    arr_out = arr[0].astype(np.float32)
                else:
                    arr_out = np.moveaxis(arr, 0, -1).astype(np.float32)

                if metadata["bands"] >= 4:
                    metadata["input_type"] = "Input: Multispectral GeoTIFF (4+ Bands: B04 Red, B08 NIR)"
                    metadata["is_multispectral"] = True
                    metadata["is_rgb"] = False
                elif metadata["bands"] == 3:
                    metadata["input_type"] = "Input: RGB GeoTIFF (3-Band Visual)"
                    metadata["is_multispectral"] = False
                    metadata["is_rgb"] = True
                else:
                    metadata["input_type"] = f"Input: GeoTIFF ({metadata['bands']}-Band Raster)"
                    metadata["is_multispectral"] = False
                    metadata["is_rgb"] = False

                return arr_out, metadata

        except Exception as e:
            logger.warning(f"Rasterio failed to load {image_path}: {e}. Falling back to PIL.")

    # Fallback using PIL
    pil_img = Image.open(str(path))
    arr_out = np.array(pil_img).astype(np.float32)
    metadata["width"] = pil_img.width
    metadata["height"] = pil_img.height
    metadata["bands"] = arr_out.shape[2] if arr_out.ndim == 3 else 1

    # Classify input type
    fmt = path.suffix.lower()
    is_sar_modality = str(modality).lower() in ["sar", "radar"] or any(k in path.name.lower() for k in ["sar", "sentinel1", "s1", "vv", "vh", "radar"])

    if fmt in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
        if is_sar_modality:
            metadata["input_type"] = "Input: Sentinel-1 SAR Visual (PNG/JPEG)"
            metadata["is_multispectral"] = False
            metadata["is_rgb"] = False
            metadata["is_sar_visual"] = True
        else:
            metadata["input_type"] = "Input: RGB Visual (JPEG/PNG)"
            metadata["is_multispectral"] = False
            metadata["is_rgb"] = True
    elif metadata["bands"] >= 4:
        metadata["input_type"] = "Input: Multispectral GeoTIFF (4+ Bands: B04 Red, B08 NIR)"
        metadata["is_multispectral"] = True
        metadata["is_rgb"] = False
    elif metadata["bands"] in [1, 2]:
        metadata["input_type"] = f"Input: GeoTIFF ({metadata['bands']}-Band Raster)"
        metadata["is_multispectral"] = False
        metadata["is_rgb"] = False
    else:
        metadata["input_type"] = f"Input: {metadata['format'].upper()} Image ({metadata['bands']}-Band)"
        metadata["is_multispectral"] = False
        metadata["is_rgb"] = metadata["bands"] == 3

    return arr_out, metadata



def load_band_array(source) -> np.ndarray:
    """Load a single-band raster array from a file path or uploaded bytes file object."""
    if isinstance(source, (str, Path)):
        arr, _ = load_geotiff_with_metadata(str(source))
        return arr

    # If it's a file-like object with getbuffer / read
    if hasattr(source, "getbuffer"):
        buf = source.getbuffer()
    elif hasattr(source, "read"):
        buf = source.read()
    else:
        buf = source

    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp.write(buf)
        tmp_path = tmp.name

    try:
        arr, _ = load_geotiff_with_metadata(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return arr


def read_bands_from_uploads(files, target_band_names: list[str]) -> dict:
    """
    Maps uploaded file objects or paths to standard Sentinel-1/Sentinel-2 band names.
    E.g. maps 'B2.tif' or 'patch_B02.tif' -> 'B02'.
    """
    band_map = {}
    for f in files:
        filename = f.name if hasattr(f, "name") else str(f)
        name_upper = Path(filename).name.upper()
        name_no_ext = Path(name_upper).stem.strip()

        # Handle B2 -> B02 single digit mapping
        if name_no_ext in ["B2", "B3", "B4", "B5", "B6", "B7", "B8"]:
            name_no_ext = name_no_ext.replace("B", "B0")

        for target_band in target_band_names:
            if target_band == name_no_ext or f"_{target_band}" in name_no_ext or f"-{target_band}" in name_no_ext:
                band_map[target_band] = f
            elif target_band in name_upper:
                if target_band == "B08" and "B8A" in name_upper:
                    continue
                if target_band not in band_map:
                    band_map[target_band] = f

    return band_map


def check_band_sanity(band_arrays: dict) -> list[str]:
    """Inspects arrays for NaNs, constant placeholder values, or zero variances."""
    warnings = []
    for band_name, arr in band_arrays.items():
        if arr is None or arr.size == 0:
            warnings.append(f"{band_name}: empty band array")
            continue
        if np.isnan(arr).any():
            warnings.append(f"{band_name}: contains NaN values")
        elif np.std(arr) < 1e-6:
            val = float(arr.flat[0]) if arr.size > 0 else 0.0
            warnings.append(f"{band_name}: constant value ({val:.2f}) — placeholder band detected")

    return warnings
