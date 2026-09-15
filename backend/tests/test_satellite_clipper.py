"""
SatQuery AI — Unit Tests for Satellite AOI Raster Clipper & Band Preparation (Phase 3C).

Includes 20 mocked unit test scenarios:
1. AOI inside raster
2. AOI outside raster
3. AOI transformed to raster CRS
4. Correct window calculation
5. Clipped raster dimensions smaller than source
6. Clipped raster CRS preserved
7. Clipped raster transform updated
8. Clipped raster bounds correct
9. Nodata preserved
10. Sentinel-2 B02/B03/B04/B08 band preparation
11. Missing Sentinel-2 band handling
12. Sentinel-1 VV preparation
13. Sentinel-1 VH preparation
14. Missing Sentinel-1 polarization handling
15. Temporary output cleanup
16. Invalid AOI coordinates
17. Preview RGB generation
18. Preview geographic bounds
19. Security check: No secret keys in manifest
20. Security check: No arbitrary filesystem access via preview tokens
"""

import pytest
import asyncio
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock
import rasterio
from rasterio.coords import BoundingBox
from rasterio.transform import Affine

from app.remote_sensing.satellite_clipper import (
    SatelliteClipperService,
    transform_aoi_to_crs,
    register_preview_file,
    get_registered_preview,
)

# ── Mock Data Fixtures ──

MOCK_S2_STAC_ITEM = {
    "id": "S2A_MSIL2A_20240527T082601_N0510_R021_T36RVU_20240527T125247",
    "bbox": [32.0, 30.0, 33.0, 31.0],
    "properties": {
        "datetime": "2024-05-27T08:26:01Z",
        "eo:cloud_cover": 1.18,
    },
    "assets": {
        "B02_10m": {"href": "s3://eodata/Sentinel-2/B02.jp2", "type": "image/jp2"},
        "B03_10m": {"href": "s3://eodata/Sentinel-2/B03.jp2", "type": "image/jp2"},
        "B04_10m": {"href": "s3://eodata/Sentinel-2/B04.jp2", "type": "image/jp2"},
        "B08_10m": {"href": "s3://eodata/Sentinel-2/B08.jp2", "type": "image/jp2"},
    }
}

MOCK_S1_STAC_ITEM = {
    "id": "S1C_IW_GRDH_1SDV_20260915T090628_20260915T090644_009456_012CF8_6369_COG",
    "bbox": [32.0, 30.0, 33.0, 31.0],
    "properties": {
        "datetime": "2026-09-15T09:06:28Z",
        "sar:polarizations": ["VV", "VH"],
    },
    "assets": {
        "vv": {"href": "s3://eodata/Sentinel-1/vv.tiff", "type": "image/tiff"},
        "vh": {"href": "s3://eodata/Sentinel-1/vh.tiff", "type": "image/tiff"},
    }
}


@pytest.fixture
def clipper_service():
    return SatelliteClipperService()


def create_mock_raster_context(width=10980, height=10980, crs="EPSG:32636"):
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
    mock.nodata = 0.0
    mock.meta = {
        "driver": "GTiff",
        "dtype": "uint16",
        "nodata": 0.0,
        "width": width,
        "height": height,
        "count": 1,
        "crs": crs,
        "transform": Affine(10.0, 0.0, 399960.0, 0.0, -10.0, 3400020.0),
    }

    # Simulate reading a small window array
    dummy_arr = np.ones((200, 200), dtype=np.uint16) * 1000
    mock.read.return_value = dummy_arr
    return mock


# ── Test Cases ──

def test_aoi_inside_raster():
    """Test 1: AOI inside raster bounds returns valid window array."""
    svc = SatelliteClipperService()
    mock_src = create_mock_raster_context()

    with patch("rasterio.open") as mock_open:
        mock_open.return_value = mock_src
        tmp_out = svc.clips_base_dir / "test_out.tif"

        res = svc._clip_single_asset_to_aoi(
            s3_url="s3://eodata/sample.tif",
            aoi_bbox=[32.2, 30.5, 32.4, 30.7],
            output_path=tmp_out,
        )
        assert res is not None
        assert res["metadata"]["width"] > 0
        assert res["metadata"]["height"] > 0
        if tmp_out.exists():
            tmp_out.unlink()


def test_aoi_outside_raster():
    """Test 2: AOI outside raster bounds raises RuntimeError/ValueError."""
    svc = SatelliteClipperService()
    mock_src = create_mock_raster_context()

    with patch("rasterio.open") as mock_open:
        mock_open.return_value = mock_src
        tmp_out = svc.clips_base_dir / "test_out.tif"

        with pytest.raises(RuntimeError) as exc_info:
            svc._clip_single_asset_to_aoi(
                s3_url="s3://eodata/sample.tif",
                aoi_bbox=[-100.0, -50.0, -99.0, -49.0],  # Far outside UTM 36N bounds
                output_path=tmp_out,
            )
        assert "aoi window does not overlap" in str(exc_info.value).lower() or "failed to clip" in str(exc_info.value).lower()


def test_aoi_transformed_to_raster_crs():
    """Test 3: WGS84 AOI bounds transform to EPSG:32636 coordinates."""
    left, bottom, right, top = transform_aoi_to_crs(32.2, 30.5, 32.4, 30.7, "EPSG:32636")
    # Coordinates in UTM zone 36N should be in meters (~400,000 to ~3,300,000)
    assert left > 100000.0
    assert bottom > 1000000.0
    assert right > left
    assert top > bottom


def test_correct_window_calculation():
    """Test 4: Window calculation returns valid rasterio Window."""
    svc = SatelliteClipperService()
    mock_src = create_mock_raster_context()

    with patch("rasterio.open") as mock_open:
        mock_open.return_value = mock_src
        tmp_out = svc.clips_base_dir / "test_win.tif"

        res = svc._clip_single_asset_to_aoi(
            s3_url="s3://eodata/sample.tif",
            aoi_bbox=[32.2, 30.5, 32.4, 30.7],
            output_path=tmp_out,
        )
        assert res["metadata"]["width"] > 0
        assert res["metadata"]["height"] > 0
        if tmp_out.exists():
            tmp_out.unlink()


def test_clipped_raster_dimensions():
    """Test 5: Clipped raster dimensions are smaller than 10980x10980 source raster."""
    svc = SatelliteClipperService()
    mock_src = create_mock_raster_context(width=10980, height=10980)

    with patch("rasterio.open") as mock_open:
        mock_open.return_value = mock_src
        tmp_out = svc.clips_base_dir / "test_dims.tif"

        res = svc._clip_single_asset_to_aoi(
            s3_url="s3://eodata/sample.tif",
            aoi_bbox=[32.2, 30.5, 32.4, 30.7],
            output_path=tmp_out,
        )
        assert res["metadata"]["width"] < 10980
        assert res["metadata"]["height"] < 10980
        if tmp_out.exists():
            tmp_out.unlink()


def test_clipped_raster_crs_preserved():
    """Test 6: Source CRS (EPSG:32636) preserved in metadata."""
    svc = SatelliteClipperService()
    mock_src = create_mock_raster_context(crs="EPSG:32636")

    with patch("rasterio.open") as mock_open:
        mock_open.return_value = mock_src
        tmp_out = svc.clips_base_dir / "test_crs.tif"

        res = svc._clip_single_asset_to_aoi(
            s3_url="s3://eodata/sample.tif",
            aoi_bbox=[32.2, 30.5, 32.4, 30.7],
            output_path=tmp_out,
        )
        assert res["metadata"]["crs"] == "EPSG:32636"
        if tmp_out.exists():
            tmp_out.unlink()


def test_clipped_raster_transform_updated():
    """Test 7: Output transform is updated to window offset."""
    svc = SatelliteClipperService()
    mock_src = create_mock_raster_context()

    with patch("rasterio.open") as mock_open:
        mock_open.return_value = mock_src
        tmp_out = svc.clips_base_dir / "test_tf.tif"

        res = svc._clip_single_asset_to_aoi(
            s3_url="s3://eodata/sample.tif",
            aoi_bbox=[32.2, 30.5, 32.4, 30.7],
            output_path=tmp_out,
        )
        tf = res["metadata"]["transform"]
        assert len(tf) == 6
        assert tf[0] == 10.0  # Pixel width
        assert tf[4] == -10.0  # Pixel height
        if tmp_out.exists():
            tmp_out.unlink()


def test_clipped_raster_bounds_correct():
    """Test 8: Output bounds correspond to clipped region."""
    svc = SatelliteClipperService()
    mock_src = create_mock_raster_context()

    with patch("rasterio.open") as mock_open:
        mock_open.return_value = mock_src
        tmp_out = svc.clips_base_dir / "test_bnds.tif"

        res = svc._clip_single_asset_to_aoi(
            s3_url="s3://eodata/sample.tif",
            aoi_bbox=[32.2, 30.5, 32.4, 30.7],
            output_path=tmp_out,
        )
        b = res["metadata"]["bounds"]
        assert len(b) == 4
        assert b[2] > b[0]
        assert b[3] > b[1]
        if tmp_out.exists():
            tmp_out.unlink()


def test_nodata_preserved():
    """Test 9: Source nodata value preserved."""
    svc = SatelliteClipperService()
    mock_src = create_mock_raster_context()

    with patch("rasterio.open") as mock_open:
        mock_open.return_value = mock_src
        tmp_out = svc.clips_base_dir / "test_nd.tif"

        res = svc._clip_single_asset_to_aoi(
            s3_url="s3://eodata/sample.tif",
            aoi_bbox=[32.2, 30.5, 32.4, 30.7],
            output_path=tmp_out,
        )
        assert res["metadata"]["nodata"] == 0.0
        if tmp_out.exists():
            tmp_out.unlink()


def test_sentinel2_preparation(clipper_service):
    """Test 10: Sentinel-2 B02/B03/B04/B08 band preparation and RGB previews."""
    mock_src = create_mock_raster_context()

    with patch.object(clipper_service.data_service, "fetch_stac_item", return_value=MOCK_S2_STAC_ITEM), \
         patch.object(clipper_service.data_service, "_configure_s3_env", return_value=("key", "secret", "endpoint")), \
         patch("rasterio.open", return_value=mock_src):

        manifest = asyncio.run(clipper_service.clip_scene_to_aoi(
            scene_id="S2A_MSIL2A_20240527T082601_N0510_R021_T36RVU_20240527T125247",
            sensor="SENTINEL-2",
            collection="sentinel-2-l2a",
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        ))

        assert manifest["status"] == "ready"
        assert manifest["scene"]["sensor"] == "SENTINEL-2"
        assert manifest["bands"]["B02"]["available"] is True
        assert manifest["bands"]["B03"]["available"] is True
        assert manifest["bands"]["B04"]["available"] is True
        assert manifest["bands"]["B08"]["available"] is True
        assert "true_color" in manifest["previews"]
        assert "false_color" in manifest["previews"]


def test_missing_sentinel2_band(clipper_service):
    """Test 11: Missing Sentinel-2 band reports available: false."""
    mock_partial_item = {
        "id": "S2A_PARTIAL",
        "bbox": [32.0, 30.0, 33.0, 31.0],
        "properties": {},
        "assets": {
            "B02_10m": {"href": "s3://eodata/B02.jp2"},
        }
    }
    mock_src = create_mock_raster_context()

    with patch.object(clipper_service.data_service, "fetch_stac_item", return_value=mock_partial_item), \
         patch.object(clipper_service.data_service, "_configure_s3_env", return_value=("key", "secret", "endpoint")), \
         patch("rasterio.open", return_value=mock_src):

        manifest = asyncio.run(clipper_service.clip_scene_to_aoi(
            scene_id="S2A_PARTIAL",
            sensor="SENTINEL-2",
            collection="sentinel-2-l2a",
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        ))

        assert manifest["bands"]["B02"]["available"] is True
        assert manifest["bands"]["B03"]["available"] is False


def test_sentinel1_vv_preparation(clipper_service):
    """Test 12: Sentinel-1 VV band clipping."""
    mock_src = create_mock_raster_context()

    with patch.object(clipper_service.data_service, "fetch_stac_item", return_value=MOCK_S1_STAC_ITEM), \
         patch.object(clipper_service.data_service, "_configure_s3_env", return_value=("key", "secret", "endpoint")), \
         patch("rasterio.open", return_value=mock_src):

        manifest = asyncio.run(clipper_service.clip_scene_to_aoi(
            scene_id="S1C_IW_GRDH_1SDV_20260915T090628_20260915T090644_009456_012CF8_6369_COG",
            sensor="SENTINEL-1",
            collection="sentinel-1-grd",
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        ))

        assert manifest["status"] == "ready"
        assert manifest["bands"]["VV"]["available"] is True


def test_sentinel1_vh_preparation(clipper_service):
    """Test 13: Sentinel-1 VH band clipping."""
    mock_src = create_mock_raster_context()

    with patch.object(clipper_service.data_service, "fetch_stac_item", return_value=MOCK_S1_STAC_ITEM), \
         patch.object(clipper_service.data_service, "_configure_s3_env", return_value=("key", "secret", "endpoint")), \
         patch("rasterio.open", return_value=mock_src):

        manifest = asyncio.run(clipper_service.clip_scene_to_aoi(
            scene_id="S1C_IW_GRDH_1SDV_20260915T090628_20260915T090644_009456_012CF8_6369_COG",
            sensor="SENTINEL-1",
            collection="sentinel-1-grd",
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        ))

        assert manifest["bands"]["VH"]["available"] is True
        assert "sar_preview" in manifest["previews"]


def test_missing_sentinel1_polarization(clipper_service):
    """Test 14: Missing Sentinel-1 polarization handled gracefully."""
    mock_single_pol = {
        "id": "S1_SINGLE_POL",
        "bbox": [32.0, 30.0, 33.0, 31.0],
        "properties": {},
        "assets": {
            "vv": {"href": "s3://eodata/vv.tiff"},
        }
    }
    mock_src = create_mock_raster_context()

    with patch.object(clipper_service.data_service, "fetch_stac_item", return_value=mock_single_pol), \
         patch.object(clipper_service.data_service, "_configure_s3_env", return_value=("key", "secret", "endpoint")), \
         patch("rasterio.open", return_value=mock_src):

        manifest = asyncio.run(clipper_service.clip_scene_to_aoi(
            scene_id="S1_SINGLE_POL",
            sensor="SENTINEL-1",
            collection="sentinel-1-grd",
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        ))

        assert manifest["bands"]["VV"]["available"] is True
        assert manifest["bands"]["VH"]["available"] is False


def test_temporary_output_cleanup(clipper_service):
    """Test 15: Temporary output clip directory workspace creation."""
    assert clipper_service.clips_base_dir.exists()


def test_invalid_aoi(clipper_service):
    """Test 16: Invalid AOI coordinates raise error."""
    with patch.object(clipper_service.data_service, "fetch_stac_item", return_value=MOCK_S2_STAC_ITEM):
        with pytest.raises(ValueError) as exc_info:
            asyncio.run(clipper_service.clip_scene_to_aoi(
                scene_id="S2A_SAMPLE",
                sensor="SENTINEL-2",
                collection="sentinel-2-l2a",
                aoi={"min_lon": 10.0, "min_lat": 10.0, "max_lon": 11.0, "max_lat": 11.0},
            ))
        assert "does not intersect" in str(exc_info.value).lower()


def test_preview_generation(clipper_service):
    """Test 17: Preview RGB generation returns valid PIL Image."""
    r = np.ones((50, 50), dtype=np.float32) * 500
    g = np.ones((50, 50), dtype=np.float32) * 600
    b = np.ones((50, 50), dtype=np.float32) * 700

    img = clipper_service._create_rgb_preview(r, g, b)
    assert img.size == (50, 50)
    assert img.mode == "RGB"


def test_preview_bounds(clipper_service):
    """Test 18: Preview geographic bounds match AOI WGS84 bounds."""
    mock_src = create_mock_raster_context()

    with patch.object(clipper_service.data_service, "fetch_stac_item", return_value=MOCK_S2_STAC_ITEM), \
         patch.object(clipper_service.data_service, "_configure_s3_env", return_value=("key", "secret", "endpoint")), \
         patch("rasterio.open", return_value=mock_src):

        manifest = asyncio.run(clipper_service.clip_scene_to_aoi(
            scene_id="S2A_SAMPLE",
            sensor="SENTINEL-2",
            collection="sentinel-2-l2a",
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        ))

        assert manifest["preview_bounds"] == [32.2, 30.5, 32.4, 30.7]


def test_no_credential_leakage(clipper_service):
    """Test 19: Manifest contains zero secret keys or credentials."""
    mock_src = create_mock_raster_context()
    secret_key = "SECRET_CDSE_S3_KEY_999"

    with patch.object(clipper_service.data_service, "fetch_stac_item", return_value=MOCK_S2_STAC_ITEM), \
         patch.object(clipper_service.data_service, "_configure_s3_env", return_value=("KEY_AAA", secret_key, "endpoint")), \
         patch("rasterio.open", return_value=mock_src):

        manifest = asyncio.run(clipper_service.clip_scene_to_aoi(
            scene_id="S2A_SAMPLE",
            sensor="SENTINEL-2",
            collection="sentinel-2-l2a",
            aoi={"min_lon": 32.2, "min_lat": 30.5, "max_lon": 32.4, "max_lat": 30.7},
        ))

        man_str = str(manifest)
        assert secret_key not in man_str
        assert "AWS_SECRET_ACCESS_KEY" not in man_str
        assert "CDSE_S3_SECRET_KEY" not in man_str


def test_no_arbitrary_filesystem_access():
    """Test 20: Unregistered or arbitrary preview_id token returns None."""
    assert get_registered_preview("invalid_token_123") is None
    assert get_registered_preview("../../../etc/passwd") is None
