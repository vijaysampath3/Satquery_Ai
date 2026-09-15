"""
SatQuery AI — Real Live Integration Test for Phase 3C AOI Raster Clipping & Band Preparation.

Performs live end-to-end integration test against Copernicus Data Space Ecosystem (CDSE):
Real STAC Item -> authenticated CDSE asset -> windowed AOI raster read -> clipped GeoTIFF -> preview generation.
Verifies actual pixel reduction between full scene and clipped AOI.
"""

import os
import pytest
import asyncio
from app.remote_sensing.satellite_catalog import SatelliteCatalogService
from app.remote_sensing.satellite_clipper import SatelliteClipperService


def test_live_cdse_sentinel2_aoi_clipping():
    """
    Live Integration Test 1: Real Sentinel-2 L2A AOI Windowed Clipping.
    1. Search CDSE STAC for a real Sentinel-2 scene over Suez Canal.
    2. Invoke SatelliteClipperService to transform AOI, compute window, and read windowed raster.
    3. Verify clipped output dimensions are substantially smaller than original scene dimensions.
    4. Verify RGB preview generation.
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

        clipper_svc = SatelliteClipperService()
        clip_res = await clipper_svc.clip_scene_to_aoi(
            scene_id=scene_id,
            sensor=sensor,
            collection=collection,
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        )

        assert clip_res["status"] == "ready"
        assert clip_res["scene"]["id"] == scene_id

        out_meta = clip_res["output"]
        orig_w, orig_h = out_meta["original_dimensions"]
        clip_w, clip_h = out_meta["width"], out_meta["height"]

        print(f"\n[Sentinel-2 Pixel Reduction] Original Scene: {orig_w}x{orig_h} -> Clipped AOI: {clip_w}x{clip_h}")

        assert clip_w < orig_w
        assert clip_h < orig_h
        assert clip_w > 0 and clip_h > 0
        assert clip_res["preview_url"] is not None

    asyncio.run(_run())


def test_live_cdse_sentinel1_aoi_clipping():
    """
    Live Integration Test 2: Real Sentinel-1 SAR AOI Windowed Clipping.
    1. Search CDSE STAC for a real Sentinel-1 scene over Suez Canal.
    2. Invoke SatelliteClipperService to clip VV/VH SAR bands.
    3. Verify clipped output dimensions are smaller than original scene dimensions.
    4. Verify SAR preview generation.
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

        clipper_svc = SatelliteClipperService()
        clip_res = await clipper_svc.clip_scene_to_aoi(
            scene_id=scene_id,
            sensor=sensor,
            collection=collection,
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        )

        assert clip_res["status"] == "ready"
        assert clip_res["scene"]["id"] == scene_id

        out_meta = clip_res["output"]
        orig_w, orig_h = out_meta["original_dimensions"]
        clip_w, clip_h = out_meta["width"], out_meta["height"]

        print(f"\n[Sentinel-1 Pixel Reduction] Original Scene: {orig_w}x{orig_h} -> Clipped AOI: {clip_w}x{clip_h}")

        assert clip_w < orig_w
        assert clip_h < orig_h
        assert clip_w > 0 and clip_h > 0
        assert clip_res["preview_url"] is not None

    asyncio.run(_run())
