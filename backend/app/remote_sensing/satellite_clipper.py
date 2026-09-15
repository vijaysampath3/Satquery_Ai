"""
SatQuery AI — Satellite AOI Raster Clipper & Band Preparation Service (Phase 3C).

Performs windowed AOI raster reading, CRS transformation, single-band GeoTIFF clipping,
2%-98% percentile display scaling, RGB/SAR preview generation, and secure preview registry mapping.
"""

import os
import uuid
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds, Window
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from PIL import Image
from loguru import logger

from app.utils.config import settings
from app.remote_sensing.satellite_data import SatelliteDataService, check_bbox_intersection
from app.remote_sensing.preprocessing import normalize_img

# In-memory registry mapping secure preview tokens to file paths
PREVIEW_REGISTRY: Dict[str, Path] = {}
CLIP_MANIFEST_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_preview_file(preview_file: Path) -> str:
    """Registers a preview image path and returns a secure preview_id token."""
    preview_id = f"prev_{uuid.uuid4().hex[:12]}"
    PREVIEW_REGISTRY[preview_id] = preview_file
    return preview_id


def get_registered_preview(preview_id: str) -> Optional[Path]:
    """Retrieves validated file path for a registered preview_id token."""
    return PREVIEW_REGISTRY.get(preview_id)


def transform_aoi_to_crs(
    min_lon: float, min_lat: float, max_lon: float, max_lat: float, target_crs_str: str
) -> Tuple[float, float, float, float]:
    """
    Transforms WGS84 (EPSG:4326) AOI bounds to target raster CRS bounds.
    """
    if not target_crs_str or "4326" in target_crs_str.upper():
        return (min_lon, min_lat, max_lon, max_lat)

    try:
        left, bottom, right, top = transform_bounds(
            "EPSG:4326",
            target_crs_str,
            min_lon,
            min_lat,
            max_lon,
            max_lat,
        )
        l_min, l_max = min(left, right), max(left, right)
        b_min, b_max = min(bottom, top), max(bottom, top)
        return (l_min, b_min, l_max, b_max)
    except Exception as e:
        logger.warning(f"[CRS Transform] Failed to transform WGS84 bounds to {target_crs_str}: {e}")
        return (min_lon, min_lat, max_lon, max_lat)


class SatelliteClipperService:
    """
    AOI Raster Clipping & Band Preparation Service for Sentinel-1 & Sentinel-2.
    """

    def __init__(self, timeout_sec: float = 20.0):
        self.data_service = SatelliteDataService(timeout_sec=timeout_sec)
        self.clips_base_dir = Path(settings.TEMP_DIR) / "satellite_clips"
        self.clips_base_dir.mkdir(parents=True, exist_ok=True)

    async def clip_scene_to_aoi(
        self,
        scene_id: str,
        sensor: str,
        collection: str,
        aoi: Dict[str, float],
    ) -> Dict[str, Any]:
        """
        Phase 3C Main Entry Point:
        1. Resolve STAC Item and assets via SatelliteDataService.
        2. Verify AOI spatial intersection.
        3. Transform AOI to raster CRS and compute pixel window.
        4. Execute windowed reading to read ONLY intersecting pixels.
        5. Write clipped single-band GeoTIFFs with updated transform & bounds.
        6. Generate True Color / False Color / SAR visualization previews.
        7. Register previews securely and return Analysis-Ready Dataset Manifest.
        """
        sensor_upper = sensor.upper().strip()

        # 1. Resolve STAC Item details
        stac_item = await self.data_service.fetch_stac_item(scene_id, collection)
        scene_bbox = stac_item.get("bbox")
        props = stac_item.get("properties", {})
        assets = stac_item.get("assets", {})

        # 2. AOI Bounding Box Validation
        min_lon = float(aoi["min_lon"])
        min_lat = float(aoi["min_lat"])
        max_lon = float(aoi["max_lon"])
        max_lat = float(aoi["max_lat"])
        aoi_bbox = [min_lon, min_lat, max_lon, max_lat]

        if not check_bbox_intersection(aoi_bbox, scene_bbox):
            raise ValueError(
                f"Selected Area of Interest (AOI) {aoi_bbox} does not intersect "
                f"the satellite scene bounds {scene_bbox}."
            )

        request_id = f"clip_{uuid.uuid4().hex[:10]}"
        clip_work_dir = self.clips_base_dir / request_id
        clip_work_dir.mkdir(parents=True, exist_ok=True)

        # Configure S3 Auth
        self.data_service._configure_s3_env()

        prepared_bands = {}
        preview_tokens = {}
        output_metadata = {}
        band_arrays = {}

        if sensor_upper == "SENTINEL-2":
            target_bands = {
                "B02": ["B02_10m", "B02", "B02_20m"],
                "B03": ["B03_10m", "B03", "B03_20m"],
                "B04": ["B04_10m", "B04", "B04_20m"],
                "B08": ["B08_10m", "B08"],
            }

            for band_name, candidate_keys in target_bands.items():
                found_key = next((k for k in candidate_keys if k in assets), None)
                if not found_key:
                    prepared_bands[band_name] = {"available": False}
                    continue

                asset_obj = assets[found_key]
                s3_url = self.data_service.resolve_asset_s3_url(asset_obj)

                clip_res = self._clip_single_asset_to_aoi(
                    s3_url=s3_url,
                    aoi_bbox=aoi_bbox,
                    scene_bbox=scene_bbox,
                    output_path=clip_work_dir / f"{band_name}.tif",
                )

                if clip_res:
                    prepared_bands[band_name] = {
                        "available": True,
                        "asset_key": found_key,
                        "file": f"{band_name}.tif",
                    }
                    band_arrays[band_name] = clip_res["array"]
                    if not output_metadata:
                        output_metadata = clip_res["metadata"]

            # Generate RGB / False Color Previews if bands present
            if "B04" in band_arrays and "B03" in band_arrays and "B02" in band_arrays:
                tc_img = self._create_rgb_preview(
                    r=band_arrays["B04"],
                    g=band_arrays["B03"],
                    b=band_arrays["B02"],
                )
                tc_path = clip_work_dir / "true_color.png"
                tc_img.save(tc_path)
                preview_tokens["true_color"] = f"/api/spatial/scenes/preview/{register_preview_file(tc_path)}"

            if "B08" in band_arrays and "B04" in band_arrays and "B03" in band_arrays:
                fc_img = self._create_rgb_preview(
                    r=band_arrays["B08"],
                    g=band_arrays["B04"],
                    b=band_arrays["B03"],
                )
                fc_path = clip_work_dir / "false_color.png"
                fc_img.save(fc_path)
                preview_tokens["false_color"] = f"/api/spatial/scenes/preview/{register_preview_file(fc_path)}"

        elif sensor_upper == "SENTINEL-1":
            target_bands = {
                "VV": ["vv", "measurement"],
                "VH": ["vh"],
            }

            for band_name, candidate_keys in target_bands.items():
                found_key = next((k for k in candidate_keys if k in assets), None)
                if not found_key:
                    prepared_bands[band_name] = {"available": False}
                    continue

                asset_obj = assets[found_key]
                s3_url = self.data_service.resolve_asset_s3_url(asset_obj)

                clip_res = self._clip_single_asset_to_aoi(
                    s3_url=s3_url,
                    aoi_bbox=aoi_bbox,
                    scene_bbox=scene_bbox,
                    output_path=clip_work_dir / f"{band_name}.tif",
                )

                if clip_res:
                    prepared_bands[band_name] = {
                        "available": True,
                        "asset_key": found_key,
                        "file": f"{band_name}.tif",
                    }
                    band_arrays[band_name] = clip_res["array"]
                    if not output_metadata:
                        output_metadata = clip_res["metadata"]

            # Generate SAR Preview
            if "VV" in band_arrays or "VH" in band_arrays:
                vv_arr = band_arrays.get("VV")
                vh_arr = band_arrays.get("VH")
                if vv_arr is None:
                    vv_arr = vh_arr
                if vh_arr is None:
                    vh_arr = vv_arr

                sar_img = self._create_rgb_preview(
                    r=vv_arr,
                    g=vh_arr,
                    b=np.where(vh_arr > 0, vv_arr / (vh_arr + 1e-6), 0),
                )
                sar_path = clip_work_dir / "sar_preview.png"
                sar_img.save(sar_path)
                preview_tokens["sar_preview"] = f"/api/spatial/scenes/preview/{register_preview_file(sar_path)}"

        if not output_metadata:
            raise RuntimeError(f"Failed to clip any satellite raster bands for scene '{scene_id}'.")

        main_preview_url = preview_tokens.get("true_color") or preview_tokens.get("sar_preview") or preview_tokens.get("false_color")
        true_color_file = clip_work_dir / "true_color.png"

        manifest = {
            "status": "ready",
            "request_id": request_id,
            "clip_work_dir": str(clip_work_dir),
            "true_color_path": str(true_color_file) if true_color_file.exists() else None,
            "scene": {
                "id": scene_id,
                "sensor": sensor_upper,
                "collection": collection,
                "datetime": props.get("datetime") or props.get("start_datetime") or "",
                "cloud_cover": props.get("eo:cloud_cover") or props.get("cloud_cover"),
            },
            "aoi": {
                "min_lon": min_lon,
                "min_lat": min_lat,
                "max_lon": max_lon,
                "max_lat": max_lat,
            },
            "output": output_metadata,
            "bands": prepared_bands,
            "previews": preview_tokens,
            "preview_url": main_preview_url,
            "preview_bounds": [min_lon, min_lat, max_lon, max_lat],
        }

        # Save manifest.json to clip_work_dir
        import json
        manifest_path = clip_work_dir / "manifest.json"
        try:
            manifest_path.write_text(json.dumps(manifest, indent=2))
        except Exception as e:
            logger.warning(f"Failed to write clip manifest.json: {e}")

        # Register in CLIP_MANIFEST_REGISTRY
        registry_key = f"{scene_id}_{round(min_lon, 4)}_{round(min_lat, 4)}_{round(max_lon, 4)}_{round(max_lat, 4)}"
        CLIP_MANIFEST_REGISTRY[registry_key] = manifest
        CLIP_MANIFEST_REGISTRY[scene_id] = manifest

        return manifest

    def get_prepared_clip(
        self, scene_id: str, aoi: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """
        Phase 3D-1: Finds an existing prepared clip for the requested scene_id + AOI.
        Reuses local disk assets without downloading or clipping S3 rasters again.
        """
        min_lon = round(float(aoi["min_lon"]), 4)
        min_lat = round(float(aoi["min_lat"]), 4)
        max_lon = round(float(aoi["max_lon"]), 4)
        max_lat = round(float(aoi["max_lat"]), 4)
        registry_key = f"{scene_id}_{min_lon}_{min_lat}_{max_lon}_{max_lat}"

        # 1. Check in-memory registry
        if registry_key in CLIP_MANIFEST_REGISTRY:
            m = CLIP_MANIFEST_REGISTRY[registry_key]
            if m.get("true_color_path") and Path(m["true_color_path"]).exists():
                return m

        if scene_id in CLIP_MANIFEST_REGISTRY:
            m = CLIP_MANIFEST_REGISTRY[scene_id]
            if m.get("true_color_path") and Path(m["true_color_path"]).exists():
                return m

        # 2. Check disk in self.clips_base_dir
        import json
        if self.clips_base_dir.exists():
            for clip_dir in self.clips_base_dir.glob("clip_*"):
                manifest_file = clip_dir / "manifest.json"
                tc_file = clip_dir / "true_color.png"
                if manifest_file.exists() and tc_file.exists():
                    try:
                        m = json.loads(manifest_file.read_text())
                        if m.get("scene", {}).get("id") == scene_id:
                            m_aoi = m.get("aoi", {})
                            if (
                                abs(float(m_aoi.get("min_lon", 0)) - min_lon) < 0.05
                                and abs(float(m_aoi.get("min_lat", 0)) - min_lat) < 0.05
                                and abs(float(m_aoi.get("max_lon", 0)) - max_lon) < 0.05
                                and abs(float(m_aoi.get("max_lat", 0)) - max_lat) < 0.05
                            ):
                                m["true_color_path"] = str(tc_file)
                                CLIP_MANIFEST_REGISTRY[registry_key] = m
                                return m
                    except Exception:
                        pass
        return None

    def _clip_single_asset_to_aoi(
        self,
        s3_url: str,
        aoi_bbox: List[float],
        scene_bbox: Optional[List[float]] = None,
        output_path: Optional[Path] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Opens S3 raster, calculates pixel window for projected OR unprojected rasters,
        reads windowed array, updates transform, writes clipped GeoTIFF.
        """
        min_lon, min_lat, max_lon, max_lat = aoi_bbox[:4]

        try:
            with rasterio.open(s3_url) as src:
                src_crs = str(src.crs) if src.crs else "EPSG:4326"
                full_window = Window(0, 0, src.width, src.height)

                # Compute pixel window
                if src.crs and "4326" not in str(src.crs).upper():
                    # 1. Projected CRS (e.g. UTM)
                    t_left, t_bottom, t_right, t_top = transform_aoi_to_crs(
                        min_lon, min_lat, max_lon, max_lat, str(src.crs)
                    )
                    raw_window = from_bounds(t_left, t_bottom, t_right, t_top, transform=src.transform)
                    window = raw_window.intersection(full_window)

                else:
                    # 2. Geographic CRS or Unprojected (e.g. Sentinel-1 GRD image coordinates)
                    if scene_bbox and len(scene_bbox) >= 4:
                        s_min_lon, s_min_lat, s_max_lon, s_max_lat = scene_bbox[:4]
                        lon_span = max(1e-5, s_max_lon - s_min_lon)
                        lat_span = max(1e-5, s_max_lat - s_min_lat)

                        rel_min_x = max(0.0, min(1.0, (min_lon - s_min_lon) / lon_span))
                        rel_max_x = max(0.0, min(1.0, (max_lon - s_min_lon) / lon_span))
                        rel_min_y = max(0.0, min(1.0, (min_lat - s_min_lat) / lat_span))
                        rel_max_y = max(0.0, min(1.0, (max_lat - s_min_lat) / lat_span))

                        col_off = int(rel_min_x * src.width)
                        row_off = int((1.0 - rel_max_y) * src.height)
                        win_width = max(1, int((rel_max_x - rel_min_x) * src.width))
                        win_height = max(1, int((rel_max_y - rel_min_y) * src.height))

                        window = Window(col_off, row_off, win_width, win_height).intersection(full_window)
                    else:
                        window = full_window

                win_col_off = int(np.floor(window.col_off))
                win_row_off = int(np.floor(window.row_off))
                win_width = int(np.ceil(window.width))
                win_height = int(np.ceil(window.height))

                if win_width <= 0 or win_height <= 0:
                    raise ValueError("AOI window does not overlap raster bounds.")

                final_window = Window(win_col_off, win_row_off, win_width, win_height).intersection(full_window)
                win_width = int(final_window.width)
                win_height = int(final_window.height)

                if win_width <= 0 or win_height <= 0:
                    raise ValueError("AOI window does not overlap raster bounds.")

                # 4. Windowed Read (ONLY required pixels)
                arr = src.read(1, window=final_window)

                # 5. Compute updated transform & bounds for clipped output
                clipped_transform = rasterio.windows.transform(final_window, src.transform)
                c_left, c_bottom, c_right, c_top = rasterio.windows.bounds(final_window, src.transform)

                # 6. Write clipped single-band GeoTIFF
                out_meta = src.meta.copy()
                out_meta.update({
                    "height": win_height,
                    "width": win_width,
                    "transform": clipped_transform,
                    "count": 1,
                    "driver": "GTiff",
                })

                with rasterio.open(output_path, "w", **out_meta) as dst:
                    dst.write(arr, 1)

                logger.info(
                    f"[AOI Clip] Success | Source: {src.width}x{src.height} -> Clipped: {win_width}x{win_height} | "
                    f"Saved to: {output_path.name}"
                )

                metadata_summary = {
                    "crs": src_crs,
                    "width": win_width,
                    "height": win_height,
                    "original_dimensions": [src.width, src.height],
                    "resolution": [round(abs(float(src.res[0])), 4), round(abs(float(src.res[1])), 4)],
                    "bounds": [round(c_left, 4), round(c_bottom, 4), round(c_right, 4), round(c_top, 4)],
                    "transform": [float(v) for v in clipped_transform[:6]],
                    "dtype": str(src.dtypes[0]),
                    "nodata": float(src.nodata) if src.nodata is not None else None,
                }

                return {
                    "array": arr,
                    "metadata": metadata_summary,
                }

        except Exception as e:
            logger.error(f"[AOI Clip Error] Failed to clip asset '{s3_url[:60]}...': {e}")
            raise RuntimeError(f"Failed to clip satellite raster asset to AOI: {str(e)}")

    def _create_rgb_preview(
        self, r: np.ndarray, g: np.ndarray, b: np.ndarray
    ) -> Image.Image:
        """
        Normalizes 3 arrays with 2%-98% percentile scaling and converts to 8-bit RGB Image.
        """
        r_norm = (normalize_img(r) * 255.0).astype(np.uint8)
        g_norm = (normalize_img(g) * 255.0).astype(np.uint8)
        b_norm = (normalize_img(b) * 255.0).astype(np.uint8)

        rgb_stack = np.dstack([r_norm, g_norm, b_norm])
        return Image.fromarray(rgb_stack)
