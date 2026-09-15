"""
SatQuery AI — Unit Tests for Authenticated Satellite Data Access & Raster Validation (Phase 3B).

Includes unit tests for:
1. Valid Sentinel-2 scene access
2. Valid Sentinel-1 scene access
3. Missing credentials handling
4. Invalid credentials handling
5. STAC scene not found
6. Invalid sensor name
7. Invalid collection mismatch
8. Missing raster asset
9. Invalid raster exception handling
10. Dynamic raster metadata extraction
11. AOI intersecting scene
12. AOI outside scene bounds
13. Temporary storage lifecycle
14. Security check: No secret keys in API response
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
import rasterio
from rasterio.coords import BoundingBox
from rasterio.transform import Affine

from app.remote_sensing.satellite_data import SatelliteDataService, check_bbox_intersection


# ── Fixtures & Mock Data ──

MOCK_S2_ITEM = {
    "id": "S2A_MSIL2A_20240527T082601_N0510_R021_T36RVU_20240527T125247",
    "bbox": [32.0, 30.0, 33.0, 31.0],
    "properties": {
        "datetime": "2024-05-27T08:26:01Z",
        "eo:cloud_cover": 1.18,
        "platform": "SENTINEL-2A",
    },
    "assets": {
        "B02_10m": {
            "href": "s3://eodata/Sentinel-2/MSI/L2A/2024/05/27/sample_B02.jp2",
            "type": "image/jp2",
            "roles": ["data"],
        },
        "thumbnail": {
            "href": "https://download.dataspace.copernicus.eu/preview.png",
        }
    }
}

MOCK_S1_ITEM = {
    "id": "S1C_IW_GRDH_1SDV_20260915T090628_20260915T090644_009456_012CF8_6369_COG",
    "bbox": [32.0, 30.0, 33.0, 31.0],
    "properties": {
        "datetime": "2026-09-15T09:06:28Z",
        "platform": "SENTINEL-1C",
        "sat:orbit_state": "descending",
        "sar:polarizations": ["VV", "VH"],
    },
    "assets": {
        "vv": {
            "href": "s3://eodata/Sentinel-1/SAR/sample_vv.tiff",
            "type": "image/tiff",
            "roles": ["data"],
        }
    }
}


@pytest.fixture
def data_service():
    return SatelliteDataService()


def create_mock_raster(width=10980, height=10980, crs="EPSG:32636"):
    mock = MagicMock()
    mock.__enter__.return_value = mock
    mock.width = width
    mock.height = height
    mock.count = 1
    mock.dtypes = ["uint16"]
    mock.crs = crs
    mock.bounds = BoundingBox(399960.0, 3290220.0, 509760.0, 3400020.0)
    mock.transform = Affine(10.0, 0.0, 399960.0, 0.0, -10.0, 3400020.0)
    mock.res = (10.0, 10.0)
    mock.nodata = 0
    mock.descriptions = ["Blue Band"]
    return mock



# ── Test Cases ──

def test_valid_sentinel2_scene_access(data_service):
    """Test 1: Valid Sentinel-2 scene access with mocked STAC item and rasterio."""
    mock_raster = create_mock_raster()

    with patch.object(data_service, "fetch_stac_item", return_value=MOCK_S2_ITEM), \
         patch.object(data_service, "_configure_s3_env", return_value=("key", "secret", "endpoint")), \
         patch("rasterio.open", return_value=mock_raster):

        res = asyncio.run(data_service.access_and_validate_scene(
            scene_id="S2A_MSIL2A_20240527T082601_N0510_R021_T36RVU_20240527T125247",
            sensor="SENTINEL-2",
            collection="sentinel-2-l2a",
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        ))

        assert res["status"] == "ready"
        assert res["scene"]["sensor"] == "SENTINEL-2"
        assert res["asset"]["key"] == "B02_10m"
        assert res["raster"]["width"] == 10980
        assert res["raster"]["crs"] == "EPSG:32636"
        assert res["aoi_intersection"]["intersects"] is True


def test_valid_sentinel1_scene_access(data_service):
    """Test 2: Valid Sentinel-1 scene access with mocked STAC item."""
    mock_raster = create_mock_raster(width=25330, height=11187, crs="EPSG:4326")

    with patch.object(data_service, "fetch_stac_item", return_value=MOCK_S1_ITEM), \
         patch.object(data_service, "_configure_s3_env", return_value=("key", "secret", "endpoint")), \
         patch("rasterio.open", return_value=mock_raster):

        res = asyncio.run(data_service.access_and_validate_scene(
            scene_id="S1C_IW_GRDH_1SDV_20260915T090628_20260915T090644_009456_012CF8_6369_COG",
            sensor="SENTINEL-1",
            collection="sentinel-1-grd",
        ))

        assert res["status"] == "ready"
        assert res["scene"]["sensor"] == "SENTINEL-1"
        assert res["asset"]["key"] == "vv"
        assert res["raster"]["width"] == 25330


def test_missing_credentials(data_service):
    """Test 3: Missing CDSE S3 credentials raises PermissionError."""
    with patch.object(data_service, "fetch_stac_item", return_value=MOCK_S2_ITEM), \
         patch.object(data_service, "_configure_s3_env", return_value=("", "", "endpoint")):

        with pytest.raises(PermissionError) as exc_info:
            asyncio.run(data_service.access_and_validate_scene(
                scene_id="S2A_SAMPLE",
                sensor="SENTINEL-2",
                collection="sentinel-2-l2a",
            ))
        assert "credentials missing" in str(exc_info.value).lower()


def test_invalid_credentials(data_service):
    """Test 4: Invalid CDSE credentials error handling."""
    with patch.object(data_service, "fetch_stac_item", return_value=MOCK_S2_ITEM), \
         patch.object(data_service, "_configure_s3_env", return_value=("bad_key", "bad_secret", "endpoint")), \
         patch("rasterio.open", side_effect=PermissionError("AWS Access Denied")):

        with pytest.raises(PermissionError) as exc_info:
            asyncio.run(data_service.access_and_validate_scene(
                scene_id="S2A_SAMPLE",
                sensor="SENTINEL-2",
                collection="sentinel-2-l2a",
            ))
        assert "authentication failed" in str(exc_info.value).lower()


def test_scene_not_found(data_service):
    """Test 5: STAC item not found raises ValueError."""
    with patch.object(data_service, "fetch_stac_item", side_effect=ValueError("Selected satellite scene 'NONEXISTENT' could not be resolved.")):
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(data_service.access_and_validate_scene(
                scene_id="NONEXISTENT",
                sensor="SENTINEL-2",
                collection="sentinel-2-l2a",
            ))
        assert "nonexistent" in str(exc_info.value).lower()


def test_invalid_sensor(data_service):
    """Test 6: Unsupported sensor name raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        asyncio.run(data_service.access_and_validate_scene(
            scene_id="S2A_SAMPLE",
            sensor="LANDSAT-8",
            collection="sentinel-2-l2a",
        ))
    assert "invalid sensor" in str(exc_info.value).lower()


def test_invalid_collection_mismatch(data_service):
    """Test 7: Collection mismatch raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        asyncio.run(data_service.access_and_validate_scene(
            scene_id="S2A_SAMPLE",
            sensor="SENTINEL-2",
            collection="sentinel-1-grd",
        ))
    assert "mismatch" in str(exc_info.value).lower()


def test_missing_asset(data_service):
    """Test 8: STAC item with missing raster assets raises ValueError."""
    mock_empty_item = {
        "id": "S2A_EMPTY",
        "bbox": [32.0, 30.0, 33.0, 31.0],
        "properties": {},
        "assets": {},
    }
    with patch.object(data_service, "fetch_stac_item", return_value=mock_empty_item):
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(data_service.access_and_validate_scene(
                scene_id="S2A_EMPTY",
                sensor="SENTINEL-2",
                collection="sentinel-2-l2a",
            ))
        assert "no asset links" in str(exc_info.value).lower()


def test_invalid_raster(data_service):
    """Test 9: rasterio open failure raises RuntimeError."""
    with patch.object(data_service, "fetch_stac_item", return_value=MOCK_S2_ITEM), \
         patch.object(data_service, "_configure_s3_env", return_value=("key", "secret", "endpoint")), \
         patch("rasterio.open", side_effect=Exception("Corrupt raster header")):

        with pytest.raises(RuntimeError) as exc_info:
            asyncio.run(data_service.access_and_validate_scene(
                scene_id="S2A_SAMPLE",
                sensor="SENTINEL-2",
                collection="sentinel-2-l2a",
            ))
        assert "failed to read satellite raster asset" in str(exc_info.value).lower()


def test_raster_metadata_extraction():
    """Test 10: Dynamic raster metadata field extraction logic."""
    mock_raster = create_mock_raster(width=1000, height=1000, crs="EPSG:32636")

    svc = SatelliteDataService()
    with patch.object(svc, "_configure_s3_env", return_value=("key", "secret", "endpoint")), \
         patch("rasterio.open", return_value=mock_raster):

        meta = svc.validate_raster_asset("s3://eodata/sample.tif")
        assert meta["width"] == 1000
        assert meta["height"] == 1000
        assert meta["band_count"] == 1
        assert meta["dtype"] == "uint16"
        assert meta["crs"] == "EPSG:32636"
        assert meta["resolution"] == [10.0, 10.0]


def test_aoi_intersecting():
    """Test 11: AOI bounding box intersection verification (True case)."""
    aoi_bbox = [32.2, 30.5, 32.4, 30.7]
    scene_bbox = [32.0, 30.0, 33.0, 31.0]
    assert check_bbox_intersection(aoi_bbox, scene_bbox) is True


def test_aoi_outside_scene(data_service):
    """Test 12: AOI completely outside scene bounding box raises ValueError."""
    aoi_outside = [10.0, 10.0, 11.0, 11.0]  # Far from scene_bbox [32.0, 30.0, 33.0, 31.0]
    with patch.object(data_service, "fetch_stac_item", return_value=MOCK_S2_ITEM):
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(data_service.access_and_validate_scene(
                scene_id="S2A_SAMPLE",
                sensor="SENTINEL-2",
                collection="sentinel-2-l2a",
                aoi={"min_lon": 10.0, "min_lat": 10.0, "max_lon": 11.0, "max_lat": 11.0},
            ))
        assert "does not intersect" in str(exc_info.value).lower()


def test_temp_storage_cleanup(data_service):
    """Test 13: Temporary storage working directory lifecycle."""
    assert data_service.temp_dir.exists()
    test_file = data_service.temp_dir / "test_transient.tmp"
    test_file.write_text("transient_data")
    assert test_file.exists()
    test_file.unlink()
    assert not test_file.exists()


def test_security_secret_not_exposed(data_service):
    """Test 14: Security verification that API response dict contains no secrets."""
    mock_raster = create_mock_raster()
    secret_key_val = "SECRET_CDSE_KEY_XYZ_123"

    with patch.object(data_service, "fetch_stac_item", return_value=MOCK_S2_ITEM), \
         patch.object(data_service, "_configure_s3_env", return_value=("CDSE_KEY_XYZ", secret_key_val, "endpoint")), \
         patch("rasterio.open", return_value=mock_raster):

        res = asyncio.run(data_service.access_and_validate_scene(
            scene_id="S2A_SAMPLE",
            sensor="SENTINEL-2",
            collection="sentinel-2-l2a",
        ))

        res_str = str(res)
        assert secret_key_val not in res_str
        assert "AWS_SECRET_ACCESS_KEY" not in res_str
        assert "CDSE_S3_SECRET_KEY" not in res_str
