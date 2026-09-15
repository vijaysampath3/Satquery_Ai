"""
SatQuery AI — Authenticated Satellite Data Access & Raster Validation Service.

Phase 3B: Authenticated Sentinel Scene Asset Access & Raster Validation.

Integrates with Copernicus Data Space Ecosystem (CDSE) S3 object storage
using backend credentials to resolve STAC Item assets, perform authenticated
raster opening, validate geospatial metadata using rasterio, and verify AOI intersection.
"""

import os
import httpx
import tempfile
import rasterio
from pathlib import Path
from typing import Optional, Dict, Any, List
from loguru import logger

from app.utils.config import settings

CDSE_STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"

COLLECTION_MAP = {
    "SENTINEL-2": "sentinel-2-l2a",
    "SENTINEL-1": "sentinel-1-grd",
}


def check_bbox_intersection(
    aoi_bbox: List[float], scene_bbox: Optional[List[float]]
) -> bool:
    """
    Checks if user AOI bounding box [min_lon, min_lat, max_lon, max_lat]
    intersects satellite scene bounding box [min_lon, min_lat, max_lon, max_lat].
    """
    if not scene_bbox or len(scene_bbox) < 4 or not aoi_bbox or len(aoi_bbox) < 4:
        return True  # If scene bbox missing, assume intersection for safety

    a_min_lon, a_min_lat, a_max_lon, a_max_lat = aoi_bbox[:4]
    s_min_lon, s_min_lat, s_max_lon, s_max_lat = scene_bbox[:4]

    # No intersection if one box is completely to the left, right, top, or bottom of the other
    if (
        a_max_lon < s_min_lon
        or a_min_lon > s_max_lon
        or a_max_lat < s_min_lat
        or a_min_lat > s_max_lat
    ):
        return False
    return True


class SatelliteDataService:
    """
    Authenticated CDSE Satellite Data Access & Raster Validation Service.
    """

    def __init__(self, timeout_sec: float = 20.0):
        self.timeout = timeout_sec
        self.temp_dir = Path(settings.TEMP_DIR) / "satellite_access"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _configure_s3_env(self) -> tuple[str, str, str]:
        """
        Loads CDSE credentials from settings / os.environ and configures AWS S3 GDAL env vars.
        Returns access_key, secret_key, endpoint.
        Does NOT log or return secrets.
        """
        access_key = settings.CDSE_S3_ACCESS_KEY or os.environ.get("CDSE_S3_ACCESS_KEY", "")
        secret_key = settings.CDSE_S3_SECRET_KEY or os.environ.get("CDSE_S3_SECRET_KEY", "")
        endpoint = settings.CDSE_S3_ENDPOINT or os.environ.get("CDSE_S3_ENDPOINT", "eodata.dataspace.copernicus.eu")

        if not access_key or not secret_key:
            logger.warning("[CDSE Auth] Missing CDSE_S3_ACCESS_KEY or CDSE_S3_SECRET_KEY in backend configuration.")

        # Set GDAL AWS S3 environment variables for rasterio
        os.environ["AWS_ACCESS_KEY_ID"] = access_key
        os.environ["AWS_SECRET_ACCESS_KEY"] = secret_key
        os.environ["AWS_S3_ENDPOINT"] = endpoint
        os.environ["AWS_VIRTUAL_HOSTING"] = "FALSE"
        os.environ["AWS_HTTPS"] = "YES"

        return access_key, secret_key, endpoint

    async def fetch_stac_item(self, scene_id: str, collection: str) -> dict:
        """
        Queries CDSE STAC API by scene_id and collection to retrieve official STAC Item.
        """
        payload = {
            "collections": [collection],
            "ids": [scene_id],
            "limit": 1,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url=CDSE_STAC_SEARCH_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
            except httpx.TimeoutException:
                raise RuntimeError("Timeout communicating with Copernicus STAC catalog service.")
            except Exception as e:
                raise RuntimeError(f"Network error querying STAC catalog: {str(e)}")

        if response.status_code != 200:
            raise RuntimeError(f"STAC search API returned HTTP {response.status_code}")

        res_data = response.json()
        features = res_data.get("features", [])
        if not features:
            raise ValueError(f"Selected satellite scene '{scene_id}' could not be resolved from collection '{collection}'.")

        return features[0]

    def select_best_asset(self, item: dict, sensor: str) -> tuple[str, dict]:
        """
        Dynamically inspects STAC Item assets and selects the appropriate available raster asset.
        Returns (asset_key, asset_object).
        """
        assets = item.get("assets", {})
        if not assets:
            raise ValueError(f"No asset links available in STAC Item for scene '{item.get('id')}'.")

        sensor_upper = sensor.upper().strip()

        if sensor_upper == "SENTINEL-2":
            # Priority order for Sentinel-2 measurement raster assets
            preferred_keys = [
                "B02_10m", "B02", "B02_20m", "B02_60m",
                "TCI_10m", "visual", "TCI_20m",
                "B03_10m", "B03", "B04_10m", "B04", "B08_10m", "B08"
            ]
            for key in preferred_keys:
                if key in assets and isinstance(assets[key], dict):
                    return key, assets[key]

        elif sensor_upper == "SENTINEL-1":
            # Priority order for Sentinel-1 measurement raster assets
            preferred_keys = ["vv", "vh", "measurement"]
            for key in preferred_keys:
                if key in assets and isinstance(assets[key], dict):
                    return key, assets[key]

        # Fallback to any raster asset with data role or image type
        for key, obj in assets.items():
            if isinstance(obj, dict):
                media_type = str(obj.get("type", "")).lower()
                roles = obj.get("roles", [])
                if "image" in media_type or "tiff" in media_type or "jp2" in media_type or "data" in roles:
                    return key, obj

        # If no raster asset matches, pick the first available asset
        first_key = list(assets.keys())[0]
        return first_key, assets[first_key]

    def resolve_asset_s3_url(self, asset_obj: dict) -> str:
        """
        Resolves official S3 URL for asset access from STAC metadata.
        Checks alternate s3 href first, then href property.
        """
        # 1. Check alternate s3 href
        alternate = asset_obj.get("alternate", {})
        if isinstance(alternate, dict) and "s3" in alternate:
            s3_href = alternate["s3"].get("href")
            if s3_href and s3_href.startswith("s3://"):
                return s3_href

        # 2. Check main href
        href = asset_obj.get("href", "")
        if href.startswith("s3://"):
            return href

        # 3. If href contains path starting with /eodata/
        if "/eodata/" in href:
            path_part = href.split("/eodata/")[1]
            return f"s3://eodata/{path_part}"

        return href

    def validate_raster_asset(self, asset_url: str) -> dict:
        """
        Performs authenticated raster access using rasterio and reads dynamic geospatial metadata.
        """
        access_key, secret_key, endpoint = self._configure_s3_env()

        if not access_key or not secret_key:
            raise PermissionError("CDSE S3 access credentials missing or not configured in backend .env.")

        try:
            with rasterio.open(asset_url) as src:
                crs_str = str(src.crs) if src.crs else None
                bounds_list = [
                    round(float(src.bounds.left), 4),
                    round(float(src.bounds.bottom), 4),
                    round(float(src.bounds.right), 4),
                    round(float(src.bounds.top), 4),
                ]
                transform_list = [float(val) for val in src.transform[:6]]
                resolution_tuple = [round(abs(float(src.res[0])), 4), round(abs(float(src.res[1])), 4)]
                band_desc = [str(d) if d else f"Band {i+1}" for i, d in enumerate(src.descriptions or [])]

                return {
                    "width": int(src.width),
                    "height": int(src.height),
                    "band_count": int(src.count),
                    "dtype": str(src.dtypes[0]),
                    "crs": crs_str,
                    "bounds": bounds_list,
                    "transform": transform_list,
                    "resolution": resolution_tuple,
                    "nodata": float(src.nodata) if src.nodata is not None else None,
                    "band_descriptions": band_desc,
                }
        except PermissionError as pe:
            logger.error(f"[Raster Access Auth Error] {pe}")
            raise PermissionError("Authentication failed accessing CDSE raster asset with configured S3 credentials.")
        except Exception as e:
            logger.error(f"[Raster Access Error] Failed to open raster '{asset_url[:80]}...': {e}")
            raise RuntimeError(f"Failed to read satellite raster asset: {str(e)}")

    async def access_and_validate_scene(
        self,
        scene_id: str,
        sensor: str,
        collection: str,
        aoi: Optional[dict] = None,
    ) -> dict:
        """
        Full Phase 3B Workflow:
        1. Validate sensor & collection pairing.
        2. Resolve STAC Item from CDSE API.
        3. Verify AOI spatial intersection with scene bounds.
        4. Dynamically select appropriate available raster asset.
        5. Perform authenticated rasterio access & extract real geospatial metadata.
        6. Return normalized response schema WITHOUT exposing secrets.
        """
        sensor_upper = sensor.upper().strip()
        expected_collection = COLLECTION_MAP.get(sensor_upper)

        if not expected_collection:
            raise ValueError(f"Invalid sensor '{sensor}'. Supported sensors: 'SENTINEL-1' and 'SENTINEL-2'.")

        if collection != expected_collection:
            raise ValueError(
                f"Mismatch: sensor '{sensor_upper}' requires collection '{expected_collection}', "
                f"but got '{collection}'."
            )

        # 1. Resolve STAC Item
        stac_item = await self.fetch_stac_item(scene_id, collection)
        scene_bbox = stac_item.get("bbox")
        props = stac_item.get("properties", {})

        # 2. AOI Intersection Verification
        intersects = True
        aoi_bbox = None
        if aoi and isinstance(aoi, dict):
            aoi_bbox = [
                float(aoi.get("min_lon", -180)),
                float(aoi.get("min_lat", -90)),
                float(aoi.get("max_lon", 180)),
                float(aoi.get("max_lat", 90)),
            ]
            intersects = check_bbox_intersection(aoi_bbox, scene_bbox)
            if not intersects:
                raise ValueError(
                    f"Selected Area of Interest (AOI) {aoi_bbox} does not intersect "
                    f"the bounding box of satellite scene '{scene_id}' ({scene_bbox})."
                )

        # 3. Dynamic Asset Selection
        asset_key, asset_obj = self.select_best_asset(stac_item, sensor_upper)
        asset_url = self.resolve_asset_s3_url(asset_obj)

        # 4. Authenticated Raster Validation
        raster_metadata = self.validate_raster_asset(asset_url)

        # Extract EO Metadata
        cloud_cover = props.get("eo:cloud_cover") or props.get("cloud_cover")
        if cloud_cover is not None:
            cloud_cover = round(float(cloud_cover), 2)

        polarizations = props.get("sar:polarizations") or props.get("polarizations") or []
        if isinstance(polarizations, str):
            polarizations = [polarizations]

        preview_url = None
        assets_dict = stac_item.get("assets", {})
        if "thumbnail" in assets_dict and isinstance(assets_dict["thumbnail"], dict):
            preview_url = assets_dict["thumbnail"].get("href")

        return {
            "status": "ready",
            "scene": {
                "id": scene_id,
                "sensor": sensor_upper,
                "collection": collection,
                "datetime": props.get("datetime") or props.get("start_datetime") or "",
                "cloud_cover": cloud_cover,
                "platform": str(props.get("platform") or sensor_upper).upper(),
                "orbit_direction": props.get("sat:orbit_state") or props.get("orbit_direction"),
                "polarizations": polarizations,
                "bbox": scene_bbox,
            },
            "asset": {
                "key": asset_key,
                "type": asset_obj.get("type", "image/tiff"),
                "roles": asset_obj.get("roles", ["data"]),
                "s3_href": asset_url,
                "title": asset_obj.get("title") or asset_key,
            },
            "raster": raster_metadata,
            "aoi_intersection": {
                "intersects": intersects,
                "aoi_bbox": aoi_bbox,
                "scene_bbox": scene_bbox,
            },
            "preview_url": preview_url,
        }
