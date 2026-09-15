"""
Live integration test against official Copernicus Data Space Ecosystem (CDSE) STAC API v1.
Queries real Sentinel-1 and Sentinel-2 scenes for a known AOI (Suez Canal, Egypt).
"""

import pytest
import asyncio
from app.remote_sensing.satellite_catalog import SatelliteCatalogService


def test_live_copernicus_stac_sentinel2_search():
    """Live integration query for Sentinel-2 L2A scenes over Suez Canal."""
    service = SatelliteCatalogService(timeout_sec=25.0)

    # Known AOI: Suez Canal (min_lon=32.2, min_lat=30.5, max_lon=32.4, max_lat=30.7)
    res = asyncio.run(
        service.search_scenes(
            min_lon=32.2,
            min_lat=30.5,
            max_lon=32.4,
            max_lat=30.7,
            sensor="SENTINEL-2",
            date_start="2024-01-10",
            date_end="2024-01-25",
            cloud_cover_max=50.0,
            limit=5,
        )
    )

    assert res["sensor"] == "SENTINEL-2"
    assert res["collection"] == "sentinel-2-l2a"
    assert "count" in res
    assert isinstance(res["scenes"], list)

    if res["count"] > 0:
        first_scene = res["scenes"][0]
        assert "id" in first_scene
        assert first_scene["sensor"] == "SENTINEL-2"
        assert first_scene["collection"] == "sentinel-2-l2a"
        assert "datetime" in first_scene
        assert "date" in first_scene
        assert "platform" in first_scene


def test_live_copernicus_stac_sentinel1_search():
    """Live integration query for Sentinel-1 GRD scenes over Suez Canal."""
    service = SatelliteCatalogService(timeout_sec=25.0)

    res = asyncio.run(
        service.search_scenes(
            min_lon=32.2,
            min_lat=30.5,
            max_lon=32.4,
            max_lat=30.7,
            sensor="SENTINEL-1",
            date_start="2024-01-10",
            date_end="2024-01-25",
            limit=5,
        )
    )

    assert res["sensor"] == "SENTINEL-1"
    assert res["collection"] == "sentinel-1-grd"
    assert "count" in res
    assert isinstance(res["scenes"], list)

    if res["count"] > 0:
        first_scene = res["scenes"][0]
        assert "id" in first_scene
        assert first_scene["sensor"] == "SENTINEL-1"
        assert first_scene["collection"] == "sentinel-1-grd"
        assert "polarizations" in first_scene
