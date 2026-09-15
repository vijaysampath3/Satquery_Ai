"""
SatQuery AI — Real Live Integration Test for Authenticated Sentinel Scene Asset Access & Raster Validation.

Performs live end-to-end integration test against Copernicus Data Space Ecosystem (CDSE):
STAC Item -> authenticated CDSE asset resolution -> rasterio.open -> dynamic geospatial metadata extraction.
"""

import os
import pytest
import asyncio
from app.remote_sensing.satellite_catalog import SatelliteCatalogService
from app.remote_sensing.satellite_data import SatelliteDataService


def test_live_cdse_sentinel2_raster_access():
    """
    Live Integration Test 1: Sentinel-2 L2A.
    1. Search CDSE STAC for a real Sentinel-2 scene over Suez Canal.
    2. Invoke SatelliteDataService to authenticate against CDSE S3.
    3. Open real raster asset via rasterio.
    4. Validate dynamic metadata: width, height, crs, dtype, bounds, resolution.
    """
    access_key = os.environ.get("CDSE_S3_ACCESS_KEY")
    secret_key = os.environ.get("CDSE_S3_SECRET_KEY")

    if not access_key or not secret_key:
        pytest.skip("CDSE S3 credentials not present in backend .env. Skipping live CDSE test.")

    async def _run():
        catalog_svc = SatelliteCatalogService()
        search_res = await catalog_svc.search_scenes(
            min_lon=32.2,
            min_lat=30.5,
            max_lon=32.4,
            max_lat=30.7,
            sensor="SENTINEL-2",
            date_start="2024-01-01",
            date_end="2024-05-30",
            cloud_cover_max=100.0,
            limit=1,
        )

        if not search_res.get("scenes"):
            pytest.skip("No real Sentinel-2 scene discovered in CDSE STAC search window.")

        target_scene = search_res["scenes"][0]
        scene_id = target_scene["id"]
        sensor = target_scene["sensor"]
        collection = target_scene["collection"]

        data_svc = SatelliteDataService()
        access_res = await data_svc.access_and_validate_scene(
            scene_id=scene_id,
            sensor=sensor,
            collection=collection,
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        )

        assert access_res["status"] == "ready"
        assert access_res["scene"]["id"] == scene_id
        assert access_res["asset"]["key"] in ["B02_10m", "B02", "TCI_10m", "visual", "B03_10m", "B04_10m", "B08_10m"]
        assert access_res["raster"]["width"] > 0
        assert access_res["raster"]["height"] > 0
        assert access_res["raster"]["band_count"] >= 1
        assert access_res["raster"]["dtype"] is not None
        assert access_res["raster"]["crs"] is not None or len(access_res["raster"]["bounds"]) == 4
        assert access_res["aoi_intersection"]["intersects"] is True

    asyncio.run(_run())


def test_live_cdse_sentinel1_raster_access():
    """
    Live Integration Test 2: Sentinel-1 SAR GRD.
    1. Search CDSE STAC for a real Sentinel-1 scene over Suez Canal.
    2. Invoke SatelliteDataService to authenticate against CDSE S3.
    3. Open real SAR raster asset via rasterio.
    4. Validate dynamic metadata.
    """
    access_key = os.environ.get("CDSE_S3_ACCESS_KEY")
    secret_key = os.environ.get("CDSE_S3_SECRET_KEY")

    if not access_key or not secret_key:
        pytest.skip("CDSE S3 credentials not present in backend .env. Skipping live CDSE test.")

    async def _run():
        catalog_svc = SatelliteCatalogService()
        search_res = await catalog_svc.search_scenes(
            min_lon=32.2,
            min_lat=30.5,
            max_lon=32.4,
            max_lat=30.7,
            sensor="SENTINEL-1",
            date_start="2024-01-01",
            date_end="2024-05-30",
            limit=1,
        )

        if not search_res.get("scenes"):
            pytest.skip("No real Sentinel-1 scene discovered in CDSE STAC search window.")

        target_scene = search_res["scenes"][0]
        scene_id = target_scene["id"]
        sensor = target_scene["sensor"]
        collection = target_scene["collection"]

        data_svc = SatelliteDataService()
        access_res = await data_svc.access_and_validate_scene(
            scene_id=scene_id,
            sensor=sensor,
            collection=collection,
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        )

        assert access_res["status"] == "ready"
        assert access_res["scene"]["id"] == scene_id
        assert access_res["asset"]["key"] in ["vv", "vh", "measurement"]
        assert access_res["raster"]["width"] > 0
        assert access_res["raster"]["height"] > 0
        assert access_res["raster"]["band_count"] >= 1

    asyncio.run(_run())
