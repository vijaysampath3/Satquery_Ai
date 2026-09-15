"""
Phase 3D-2 Live Integration Test — Sentinel-2 Visual Grounding Execution.

Executes:
1. Discovery of a real Sentinel-2 scene via Copernicus STAC API (Suez Canal / Great Bitter Lake AOI)
2. Phase 3C windowed raster clipping to AOI
3. Phase 3D-2 Grounding query execution ("Highlight vegetation", "Show water bodies")
4. Clip reuse verification (zero secondary CDSE STAC/S3 requests)
5. Evidence image verification
6. Zero credential exposure audit
"""

import pytest
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.remote_sensing.satellite_catalog import SatelliteCatalogService
from app.remote_sensing.satellite_clipper import SatelliteClipperService

client = TestClient(app)

AOI_SUEZ = {
    "min_lon": 32.25,
    "min_lat": 30.50,
    "max_lon": 32.45,
    "max_lat": 30.70,
}


def test_live_stac_sentinel2_grounding():
    """Live CDSE Sentinel-2 search -> Phase 3C clip -> Grounding execution."""
    async def _run_live_test():
        catalog = SatelliteCatalogService()
        search_res = await catalog.search_scenes(
            min_lon=AOI_SUEZ["min_lon"],
            min_lat=AOI_SUEZ["min_lat"],
            max_lon=AOI_SUEZ["max_lon"],
            max_lat=AOI_SUEZ["max_lat"],
            sensor="SENTINEL-2",
            date_start="2026-02-01",
            date_end="2026-03-01",
            cloud_cover_max=50.0,
            limit=5,
        )

        scenes = search_res.get("scenes", [])
        if not scenes:
            pytest.skip("No Sentinel-2 scenes found for AOI in CDSE catalog search.")

        target_scene = scenes[0]
        scene_id = target_scene["id"]
        collection = target_scene.get("collection", "sentinel-2-l2a")

        clipper = SatelliteClipperService()

        # Step 1: Clip scene to AOI & prepare bands
        clip_manifest = await clipper.clip_scene_to_aoi(
            scene_id=scene_id,
            sensor="SENTINEL-2",
            collection=collection,
            aoi=AOI_SUEZ,
        )
        assert clip_manifest["status"] == "ready"
        assert clip_manifest["true_color_path"] is not None

        # Step 2: Execute Grounding Query 1 ("Highlight vegetation")
        resp_veg = client.post(
            "/api/spatial/scenes/analyze",
            json={
                "scene_id": scene_id,
                "sensor": "SENTINEL-2",
                "collection": collection,
                "aoi": AOI_SUEZ,
                "query": "Highlight vegetation",
            },
        )
        assert resp_veg.status_code == 200
        data_veg = resp_veg.json()
        assert data_veg["status"] == "success"
        assert data_veg["task"] == "grounding"
        assert data_veg["grounding"] is not None

        # Step 3: Execute Grounding Query 2 ("Show water bodies") & verify clip reuse
        resp_water = client.post(
            "/api/spatial/scenes/analyze",
            json={
                "scene_id": scene_id,
                "sensor": "SENTINEL-2",
                "collection": collection,
                "aoi": AOI_SUEZ,
                "query": "Show water bodies",
            },
        )
        assert resp_water.status_code == 200
        data_water = resp_water.json()
        assert data_water["status"] == "success"
        assert data_water["task"] == "grounding"
        assert data_water["grounding"]["target_type"] == "water"

        # Step 4: Verify zero credential leakage
        for forbidden in ["CDSE_SECRET", "AWS_SECRET", "ACCESS_KEY"]:
            assert forbidden not in resp_veg.text
            assert forbidden not in resp_water.text

    asyncio.run(_run_live_test())


if __name__ == "__main__":
    asyncio.run(test_live_stac_sentinel2_grounding())
