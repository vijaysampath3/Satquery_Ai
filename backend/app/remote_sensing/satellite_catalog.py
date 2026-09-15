"""
SatQuery AI — Satellite Data Catalog Discovery Service.

Interacts directly with the official Copernicus Data Space Ecosystem (CDSE) STAC API v1
to discover real Sentinel-1 GRD and Sentinel-2 L2A satellite scenes.

Base Endpoint: https://stac.dataspace.copernicus.eu/v1/search
Collections:
  - Sentinel-2: sentinel-2-l2a
  - Sentinel-1: sentinel-1-grd
"""

import httpx
from typing import Optional
from datetime import datetime, timezone
from loguru import logger

CDSE_STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"

COLLECTION_MAP = {
    "SENTINEL-2": "sentinel-2-l2a",
    "SENTINEL-1": "sentinel-1-grd",
}


def construct_geojson_polygon(min_lon: float, min_lat: float, max_lon: float, max_lat: float) -> dict:
    """Constructs a 5-point closed GeoJSON Polygon from bounding box coordinates."""
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat],
            ]
        ],
    }


def format_iso_datetime_range(date_start: str, date_end: Optional[str] = None) -> str:
    """
    Formats ISO8601 UTC datetime range string for STAC API requests.
    Single date '2024-01-15' -> '2024-01-15T00:00:00Z/2024-01-15T23:59:59Z'
    Range '2024-01-15' -> '2024-01-20' -> '2024-01-15T00:00:00Z/2024-01-20T23:59:59Z'
    """
    start_str = date_start.strip()
    if "T" not in start_str:
        start_str = f"{start_str}T00:00:00Z"

    end_str = (date_end or date_start).strip()
    if "T" not in end_str:
        end_str = f"{end_str}T23:59:59Z"

    return f"{start_str}/{end_str}"


def _normalize_stac_feature(feature: dict, sensor_type: str) -> dict:
    """
    Normalizes raw CDSE STAC feature into clean frontend response schema.
    Only includes properties and asset URLs that actually exist.
    """
    props = feature.get("properties", {})
    assets = feature.get("assets", {})
    feature_id = feature.get("id", "UNKNOWN_SCENE")

    # Acquisition datetime
    dt_str = props.get("datetime") or props.get("start_datetime") or ""
    date_formatted = dt_str.split("T")[0] if "T" in dt_str else dt_str

    # Cloud cover (Sentinel-2)
    cloud_cover = props.get("eo:cloud_cover")
    if cloud_cover is None:
        cloud_cover = props.get("cloud_cover") or props.get("cloudCover")
    if cloud_cover is not None:
        cloud_cover = round(float(cloud_cover), 2)

    # Platform & Orbit
    platform = props.get("platform") or props.get("constellation") or ("Sentinel-2" if sensor_type == "SENTINEL-2" else "Sentinel-1")
    orbit_direction = props.get("sat:orbit_state") or props.get("orbit_direction") or props.get("orbitState")
    relative_orbit = props.get("sat:relative_orbit") or props.get("relative_orbit")

    # Polarizations (Sentinel-1 SAR)
    polarizations = props.get("sar:polarizations") or props.get("polarizations") or []
    if isinstance(polarizations, str):
        polarizations = [polarizations]

    # Asset extraction (thumbnail, visual, metadata)
    extracted_assets = {}
    if "thumbnail" in assets and isinstance(assets["thumbnail"], dict):
        extracted_assets["thumbnail"] = assets["thumbnail"].get("href")
    elif "rendered_preview" in assets and isinstance(assets["rendered_preview"], dict):
        extracted_assets["thumbnail"] = assets["rendered_preview"].get("href")

    if "visual" in assets and isinstance(assets["visual"], dict):
        extracted_assets["visual"] = assets["visual"].get("href")
    elif "TCI" in assets and isinstance(assets["TCI"], dict):
        extracted_assets["visual"] = assets["TCI"].get("href")

    if "Product" in assets and isinstance(assets["Product"], dict):
        extracted_assets["metadata"] = assets["Product"].get("href")
    elif "safe_manifest" in assets and isinstance(assets["safe_manifest"], dict):
        extracted_assets["metadata"] = assets["safe_manifest"].get("href")

    collection_name = COLLECTION_MAP.get(sensor_type, "sentinel-2-l2a" if sensor_type == "SENTINEL-2" else "sentinel-1-grd")

    return {
        "id": feature_id,
        "sensor": sensor_type,
        "collection": collection_name,
        "datetime": dt_str,
        "date": date_formatted,
        "cloud_cover": cloud_cover,
        "platform": str(platform).upper(),
        "orbit_direction": orbit_direction,
        "relative_orbit": relative_orbit,
        "polarizations": polarizations,
        "bbox": feature.get("bbox"),
        "geometry": feature.get("geometry"),
        "assets": extracted_assets,
    }


class SatelliteCatalogService:
    """Service for discovering real Sentinel-1 and Sentinel-2 scenes from CDSE STAC API."""

    def __init__(self, timeout_sec: float = 20.0):
        self.timeout = timeout_sec

    async def search_scenes(
        self,
        min_lon: float,
        min_lat: float,
        max_lon: float,
        max_lat: float,
        sensor: str = "SENTINEL-2",
        date_start: str = "2024-01-15",
        date_end: Optional[str] = None,
        cloud_cover_max: float = 30.0,
        limit: int = 10,
    ) -> dict:
        """
        Executes STAC query against CDSE API for real satellite scene discovery.
        """
        sensor_upper = sensor.upper().strip()
        if sensor_upper not in COLLECTION_MAP:
            raise ValueError(f"Unsupported sensor type: '{sensor}'. Must be SENTINEL-1 or SENTINEL-2.")

        collection = COLLECTION_MAP[sensor_upper]
        bbox_list = [float(min_lon), float(min_lat), float(max_lon), float(max_lat)]
        intersects_geom = construct_geojson_polygon(min_lon, min_lat, max_lon, max_lat)
        datetime_interval = format_iso_datetime_range(date_start, date_end)

        stac_payload = {
            "collections": [collection],
            "intersects": intersects_geom,
            "datetime": datetime_interval,
            "limit": min(limit * 2, 100),  # Request extra for client cloud filtering
        }

        logger.info(
            f"[STAC Search] Querying CDSE STAC | Sensor: {sensor_upper} | Collection: {collection} | "
            f"BBOX: {bbox_list} | Datetime: {datetime_interval}"
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    url=CDSE_STAC_SEARCH_URL,
                    json=stac_payload,
                    headers={"Content-Type": "application/json"},
                )
            except httpx.TimeoutException:
                logger.error("[STAC Search] Connection timed out while querying CDSE STAC API.")
                raise RuntimeError("Copernicus STAC catalog service request timed out. Please try again.")
            except Exception as e:
                logger.error(f"[STAC Search] Network failure querying CDSE STAC: {e}")
                raise RuntimeError(f"Failed to communicate with Copernicus STAC catalog: {str(e)}")

        if response.status_code != 200:
            logger.error(f"[STAC Search] CDSE API error HTTP {response.status_code}: {response.text[:300]}")
            raise RuntimeError(f"Copernicus STAC search returned HTTP {response.status_code}")

        res_data = response.json()
        raw_features = res_data.get("features", [])
        logger.info(f"[STAC Search] Discovered {len(raw_features)} raw scenes from CDSE STAC.")

        normalized_scenes = []
        for feat in raw_features:
            norm = _normalize_stac_feature(feat, sensor_upper)

            # Filter Sentinel-2 by cloud cover if threshold is set
            if sensor_upper == "SENTINEL-2" and norm["cloud_cover"] is not None:
                if norm["cloud_cover"] > cloud_cover_max:
                    continue

            normalized_scenes.append(norm)

        # Sort Sentinel-2 by cloud cover ascending, Sentinel-1 by datetime descending
        if sensor_upper == "SENTINEL-2":
            normalized_scenes.sort(key=lambda s: s["cloud_cover"] if s["cloud_cover"] is not None else 999.0)
        else:
            normalized_scenes.sort(key=lambda s: s["datetime"], reverse=True)

        final_scenes = normalized_scenes[:limit]

        return {
            "count": len(final_scenes),
            "total_discovered": len(raw_features),
            "sensor": sensor_upper,
            "collection": collection,
            "query": {
                "bbox": bbox_list,
                "date_start": date_start,
                "date_end": date_end or date_start,
                "cloud_cover_max": cloud_cover_max if sensor_upper == "SENTINEL-2" else None,
                "limit": limit,
            },
            "scenes": final_scenes,
        }
