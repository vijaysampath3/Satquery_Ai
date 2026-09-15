"""
Unit tests for SatelliteCatalogService (Copernicus STAC Scene Discovery).
Uses mocked STAC API HTTP responses for fast, deterministic unit testing.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.remote_sensing.satellite_catalog import (
    SatelliteCatalogService,
    construct_geojson_polygon,
    format_iso_datetime_range,
    _normalize_stac_feature,
)

# Mocked CDSE STAC API payload for Sentinel-2
MOCK_STAC_S2_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "id": "S2A_MSIL2A_20240115T083251_N0510_R021_T36RVV",
            "properties": {
                "datetime": "2024-01-15T08:32:51.123Z",
                "eo:cloud_cover": 12.5,
                "platform": "sentinel-2a",
                "sat:relative_orbit": 21,
            },
            "bbox": [32.2, 30.5, 32.4, 30.7],
            "geometry": {"type": "Polygon", "coordinates": [[[32.2, 30.5], [32.4, 30.5], [32.4, 30.7], [32.2, 30.7], [32.2, 30.5]]]},
            "assets": {
                "thumbnail": {"href": "https://stac.dataspace.copernicus.eu/thumb.png"},
                "visual": {"href": "https://stac.dataspace.copernicus.eu/visual.tif"},
                "Product": {"href": "https://stac.dataspace.copernicus.eu/manifest.safe"},
            },
        },
        {
            "id": "S2B_MSIL2A_20240115T090000_N0510_R021_T36RVV",
            "properties": {
                "datetime": "2024-01-15T09:00:00.000Z",
                "eo:cloud_cover": 45.0,  # Exceeds 30% max cloud cover
                "platform": "sentinel-2b",
                "sat:relative_orbit": 21,
            },
            "bbox": [32.2, 30.5, 32.4, 30.7],
            "geometry": {"type": "Polygon", "coordinates": [[[32.2, 30.5], [32.4, 30.5], [32.4, 30.7], [32.2, 30.7], [32.2, 30.5]]]},
            "assets": {
                "thumbnail": {"href": "https://stac.dataspace.copernicus.eu/thumb2.png"},
            },
        },
    ],
}

# Mocked CDSE STAC API payload for Sentinel-1 GRD
MOCK_STAC_S1_RESPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "id": "S1A_IW_GRDH_1SDV_20240115T034458",
            "properties": {
                "datetime": "2024-01-15T03:44:58.079Z",
                "platform": "sentinel-1a",
                "sat:orbit_state": "descending",
                "sar:polarizations": ["VV", "VH"],
                "sat:relative_orbit": 94,
            },
            "bbox": [32.2, 30.5, 32.4, 30.7],
            "geometry": {"type": "Polygon", "coordinates": [[[32.2, 30.5], [32.4, 30.5], [32.4, 30.7], [32.2, 30.7], [32.2, 30.5]]]},
            "assets": {
                "thumbnail": {"href": "https://stac.dataspace.copernicus.eu/s1_thumb.png"},
                "vv": {"href": "https://stac.dataspace.copernicus.eu/vv.tif"},
                "vh": {"href": "https://stac.dataspace.copernicus.eu/vh.tif"},
            },
        }
    ],
}


def test_helpers():
    """Test geometry and datetime helper formatting."""
    poly = construct_geojson_polygon(32.2, 30.5, 32.4, 30.7)
    assert poly["type"] == "Polygon"
    assert poly["coordinates"][0][0] == [32.2, 30.5]
    assert poly["coordinates"][0][4] == [32.2, 30.5]

    dt_str = format_iso_datetime_range("2024-01-15")
    assert dt_str == "2024-01-15T00:00:00Z/2024-01-15T23:59:59Z"

    dt_range = format_iso_datetime_range("2024-01-15", "2024-01-20")
    assert dt_range == "2024-01-15T00:00:00Z/2024-01-20T23:59:59Z"


def test_sentinel2_scene_search_and_cloud_filtering():
    """Test 1 & 5: Sentinel-2 search and cloud cover filtering."""
    service = SatelliteCatalogService()

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_STAC_S2_RESPONSE
        mock_post.return_value = mock_response

        res = asyncio.run(
            service.search_scenes(
                min_lon=32.2,
                min_lat=30.5,
                max_lon=32.4,
                max_lat=30.7,
                sensor="SENTINEL-2",
                date_start="2024-01-15",
                cloud_cover_max=30.0,
                limit=10,
            )
        )

        assert res["sensor"] == "SENTINEL-2"
        assert res["collection"] == "sentinel-2-l2a"
        assert res["count"] == 1  # 45% cloud scene filtered out
        assert res["scenes"][0]["id"] == "S2A_MSIL2A_20240115T083251_N0510_R021_T36RVV"
        assert res["scenes"][0]["cloud_cover"] == 12.5
        assert res["scenes"][0]["assets"]["thumbnail"] == "https://stac.dataspace.copernicus.eu/thumb.png"


def test_sentinel1_scene_search_without_cloud_filter():
    """Test 2 & 6: Sentinel-1 search without cloud cover filtering."""
    service = SatelliteCatalogService()

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_STAC_S1_RESPONSE
        mock_post.return_value = mock_response

        res = asyncio.run(
            service.search_scenes(
                min_lon=32.2,
                min_lat=30.5,
                max_lon=32.4,
                max_lat=30.7,
                sensor="SENTINEL-1",
                date_start="2024-01-15",
                limit=10,
            )
        )

        assert res["sensor"] == "SENTINEL-1"
        assert res["collection"] == "sentinel-1-grd"
        assert res["count"] == 1
        assert res["scenes"][0]["polarizations"] == ["VV", "VH"]
        assert res["scenes"][0]["orbit_direction"] == "descending"


def test_empty_result():
    """Test 7: Empty STAC query result."""
    service = SatelliteCatalogService()

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"type": "FeatureCollection", "features": []}
        mock_post.return_value = mock_response

        res = asyncio.run(
            service.search_scenes(
                min_lon=32.2,
                min_lat=30.5,
                max_lon=32.4,
                max_lat=30.7,
                sensor="SENTINEL-2",
                date_start="2024-01-15",
            )
        )

        assert res["count"] == 0
        assert res["scenes"] == []


def test_invalid_sensor():
    """Test 8: Invalid sensor type raises ValueError."""
    service = SatelliteCatalogService()
    with pytest.raises(ValueError, match="Unsupported sensor type"):
        asyncio.run(
            service.search_scenes(
                min_lon=32.2,
                min_lat=30.5,
                max_lon=32.4,
                max_lat=30.7,
                sensor="LANDSAT-99",
                date_start="2024-01-15",
            )
        )
