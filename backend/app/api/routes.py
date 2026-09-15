"""
API Routes for SatQuery AI.

Provides endpoints:
  - POST /api/analyze: Main natural-language agentic analysis endpoint
  - POST /api/demo: Local Demo Mode analysis
  - GET  /api/health: System & model component health monitor
  - POST /api/spatial/scenes/search: Real Sentinel-1/2 Copernicus STAC Scene Discovery
"""

import uuid
import tempfile
from pathlib import Path
from typing import Optional
from loguru import logger

from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import FileResponse
from app.utils.config import settings
from app.agent.validator import InputValidator
from app.agent.router import RuleBasedRouter
from app.agent.executor import PipelineExecutor
from app.output.trace import TraceBuilder
from app.output.integrator import OutputIntegrator
from app.api.schemas import SpatialSceneSearchRequest, SpatialSceneAccessRequest, SpatialSceneClipRequest, SpatialSceneAnalyzeRequest
from app.remote_sensing.satellite_catalog import SatelliteCatalogService
from app.remote_sensing.satellite_data import SatelliteDataService
from app.remote_sensing.satellite_clipper import SatelliteClipperService, get_registered_preview


router = APIRouter()



@router.post("/analyze")
async def analyze(
    request: Request,
    images: list[UploadFile] = File(...),
    query: str = Form(...),
    modalities: str = Form(default="optical"),
    dates: Optional[str] = Form(default=None),
):
    """
    Main natural language analysis endpoint.
    Accepts 1-2 satellite image(s) + query. Agent classifies intent,
    executes pipeline, generates visual evidence, and returns trace.
    """
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] New request — Query: '{query}' | Images: {len(images)}")

    # 1. Save uploaded files to temp directory
    image_paths = []
    for i, img_file in enumerate(images):
        suffix = Path(img_file.filename).suffix or ".tif"
        tmp_dir = Path(tempfile.mkdtemp(prefix="satquery_"))
        tmp_path = tmp_dir / f"image_{i}{suffix}"
        content = await img_file.read()
        tmp_path.write_bytes(content)
        image_paths.append(str(tmp_path))

    # 2. Parse metadata
    modality_list = [m.strip() for m in modalities.split(",")]
    date_list = [d.strip() for d in dates.split(",")] if dates else []
    metadata = {
        "modalities": modality_list,
        "dates": date_list,
    }

    # 3. Validate query & images
    validator = InputValidator()
    query_valid, query_error = validator.validate_query(query)
    if not query_valid:
        raise HTTPException(status_code=422, detail={"errors": [query_error]})

    validation = validator.validate(image_paths, metadata)
    if not validation.is_valid:
        raise HTTPException(status_code=422, detail={"errors": validation.errors})

    # 4. Route task
    input_info = {
        "num_images": validation.num_images,
        "modalities": validation.modalities,
        "is_temporal": validation.is_temporal,
        "is_cross_modal": validation.is_cross_modal,
    }
    router_inst = RuleBasedRouter()
    decision = router_inst.route(query, input_info)

    # 5. Execute pipeline
    registry = request.app.state.model_registry
    executor = PipelineExecutor(registry)
    step_results = executor.execute(
        decision.pipeline, image_paths, query, request_id, metadata=metadata
    )

    # 6. Build trace & integrate output
    trace = TraceBuilder().build(validation, decision, step_results)
    output = await OutputIntegrator().integrate_async(
        step_results, decision.task_type, query, request_id
    )

    return {
        "task": decision.task_type.value,
        "answer": output["answer"],
        "confidence": output["confidence"],
        "status_text": output["status_text"],
        "input_badge": output.get("input_badge", "Input: Remote Sensing Image"),
        "evidence": output["evidence"],
        "change_metrics": output.get("change_metrics"),
        "target_analysis": output.get("target_analysis"),
        "built_up_analysis": output.get("built_up_analysis"),
        "vegetation_analysis": output.get("vegetation_analysis"),
        "water_analysis": output.get("water_analysis"),
        "execution_trace": trace,
    }


@router.post("/demo")
async def run_demo(
    request: Request,
    demo_type: str = Form(default="single"),  # single, change, multimodal
    query: str = Form(default="Describe this image"),
):
    """
    Local Demo Mode endpoint.
    Executes instantly using pre-bundled local sample GeoTIFF datasets.
    """
    request_id = f"demo_{demo_type}_{str(uuid.uuid4())[:4]}"
    demo_base = settings.BASE_DIR / "data" / "demo"

    if demo_type == "change":
        img1 = demo_base / "change" / "date1.tif"
        img2 = demo_base / "change" / "date2.tif"
        image_paths = [str(img1), str(img2)]
        metadata = {"modalities": ["optical", "optical"], "dates": ["2023-01-01", "2024-01-01"]}
        if query == "Describe this image":
            query = "What changed between these two dates?"

    elif demo_type == "multimodal":
        img1 = demo_base / "multimodal" / "optical.tif"
        img2 = demo_base / "multimodal" / "sar.tif"
        image_paths = [str(img1), str(img2)]
        metadata = {"modalities": ["optical", "sar"]}
        if query == "Describe this image":
            query = "Use optical and SAR images together to analyze this region"

    else:  # single
        img1 = demo_base / "single" / "sample.tif"
        image_paths = [str(img1)]
        metadata = {"modalities": ["optical"]}

    validator = InputValidator()
    validation = validator.validate(image_paths, metadata)

    router_inst = RuleBasedRouter()
    input_info = {
        "num_images": validation.num_images,
        "modalities": validation.modalities,
        "is_temporal": validation.is_temporal,
        "is_cross_modal": validation.is_cross_modal,
    }
    decision = router_inst.route(query, input_info)

    registry = request.app.state.model_registry
    executor = PipelineExecutor(registry)
    step_results = executor.execute(
        decision.pipeline, image_paths, query, request_id
    )

    trace = TraceBuilder().build(validation, decision, step_results)
    output = await OutputIntegrator().integrate_async(
        step_results, decision.task_type, query, request_id
    )

    return {
        "demo_mode": True,
        "demo_type": demo_type,
        "task": decision.task_type.value,
        "answer": output["answer"],
        "confidence": output["confidence"],
        "status_text": output["status_text"],
        "input_badge": output.get("input_badge", "Input: Multispectral GeoTIFF"),
        "evidence": output["evidence"],
        "change_metrics": output.get("change_metrics"),
        "execution_trace": trace,
    }


@router.get("/health")
async def health(request: Request):
    """
    System & Component Health Status Endpoint.
    Returns readiness status of API, Qwen VLM, Grounding, Change Detection, and Processors.
    """
    registry = request.app.state.model_registry

    return {
        "status": "healthy",
        "system_components": {
            "api": "Ready",
            "qwen_vlm": "Ready (Fallback VLM Active)" if getattr(registry.get("rs_vlm"), "_fallback_mode", False) else "Ready (Qwen2.5-VL GPU)",
            "grounding": "Ready (Remote Sensing Fallback)",
            "change_detection": "Ready (Alignment & Spectral Divergence)",
            "oil_spill_detection": "Ready (Sentinel-1 SAR Backscatter Analysis)",
            "optical_processor": "Ready (Rasterio / Percentile Norm)",
            "sar_processor": "Ready (VV/VH Radar Composite)",
            "copernicus_stac_catalog": "Ready (stac.dataspace.copernicus.eu/v1)",
        },
        "models_loaded": registry.list_loaded(),
        "registered_models": registry.list_all(),
    }


# ── Phase 3A: Spatial Scene Discovery Endpoint ──

@router.post("/spatial/scenes/search")
async def search_spatial_scenes(req: SpatialSceneSearchRequest):
    """
    Real Satellite Scene Discovery Endpoint (Phase 3A).
    Queries Copernicus Data Space Ecosystem (CDSE) STAC API v1 for real Sentinel-1 & Sentinel-2 scenes.
    """
    # 1. BBOX Validation
    bbox = req.bbox
    if bbox.min_lon >= bbox.max_lon:
        raise HTTPException(
            status_code=422,
            detail={"errors": ["Invalid BBOX: min_lon must be strictly less than max_lon."]},
        )
    if bbox.min_lat >= bbox.max_lat:
        raise HTTPException(
            status_code=422,
            detail={"errors": ["Invalid BBOX: min_lat must be strictly less than max_lat."]},
        )
    if not (-180.0 <= bbox.min_lon <= 180.0 and -180.0 <= bbox.max_lon <= 180.0):
        raise HTTPException(
            status_code=422,
            detail={"errors": ["Invalid BBOX: Longitude values must be between -180 and 180 degrees."]},
        )
    if not (-90.0 <= bbox.min_lat <= 90.0 and -90.0 <= bbox.max_lat <= 90.0):
        raise HTTPException(
            status_code=422,
            detail={"errors": ["Invalid BBOX: Latitude values must be between -90 and 90 degrees."]},
        )

    # 2. Sensor Validation
    sensor_upper = req.sensor.upper().strip()
    if sensor_upper not in ["SENTINEL-1", "SENTINEL-2"]:
        raise HTTPException(
            status_code=422,
            detail={"errors": [f"Invalid sensor '{req.sensor}'. Supported sensors: 'SENTINEL-1' and 'SENTINEL-2'."]},
        )

    # 3. Date Validation
    if req.date_end and req.date_start > req.date_end:
        raise HTTPException(
            status_code=422,
            detail={"errors": ["Invalid Date Range: date_start cannot be after date_end."]},
        )

    catalog_service = SatelliteCatalogService()
    try:
        results = await catalog_service.search_scenes(
            min_lon=bbox.min_lon,
            min_lat=bbox.min_lat,
            max_lon=bbox.max_lon,
            max_lat=bbox.max_lat,
            sensor=sensor_upper,
            date_start=req.date_start,
            date_end=req.date_end,
            cloud_cover_max=req.cloud_cover_max,
            limit=req.limit,
        )
        return results

    except ValueError as ve:
        raise HTTPException(status_code=422, detail={"errors": [str(ve)]})
    except RuntimeError as re:
        raise HTTPException(status_code=502, detail={"errors": [str(re)]})
    except Exception as e:
        logger.error(f"[Spatial Scene Search Error] {e}")
        raise HTTPException(status_code=500, detail={"errors": [f"Satellite catalog search failed: {str(e)}"]})


# ── Phase 3B: Authenticated Satellite Scene Access Endpoint ──

@router.post("/spatial/scenes/access")
async def access_spatial_scene(req: SpatialSceneAccessRequest):
    """
    Authenticated Satellite Scene Access & Raster Validation Endpoint (Phase 3B).
    Resolves STAC Item by scene_id, authenticates against CDSE S3, opens and validates
    geospatial raster metadata via rasterio, and verifies AOI intersection.
    """
    scene_id = req.scene_id.strip()
    if not scene_id:
        raise HTTPException(
            status_code=422,
            detail={"errors": ["Missing required field 'scene_id'."]},
        )

    sensor_upper = req.sensor.upper().strip()
    if sensor_upper not in ["SENTINEL-1", "SENTINEL-2"]:
        raise HTTPException(
            status_code=422,
            detail={"errors": [f"Invalid sensor '{req.sensor}'. Supported sensors: 'SENTINEL-1' and 'SENTINEL-2'."]},
        )

    expected_collection = "sentinel-2-l2a" if sensor_upper == "SENTINEL-2" else "sentinel-1-grd"
    if req.collection != expected_collection:
        raise HTTPException(
            status_code=422,
            detail={"errors": [f"Collection mismatch: sensor '{sensor_upper}' requires collection '{expected_collection}', got '{req.collection}'."]},
        )

    aoi_dict = None
    if req.aoi:
        aoi_dict = {
            "min_lon": req.aoi.min_lon,
            "min_lat": req.aoi.min_lat,
            "max_lon": req.aoi.max_lon,
            "max_lat": req.aoi.max_lat,
        }

    data_service = SatelliteDataService()
    try:
        res = await data_service.access_and_validate_scene(
            scene_id=scene_id,
            sensor=sensor_upper,
            collection=req.collection,
            aoi=aoi_dict,
        )
        return res

    except ValueError as ve:
        raise HTTPException(status_code=422, detail={"errors": [str(ve)]})
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail={"errors": [str(pe)]})
    except RuntimeError as re:
        raise HTTPException(status_code=502, detail={"errors": [str(re)]})
    except Exception as e:
        logger.error(f"[Spatial Scene Access Error] {e}")
        raise HTTPException(status_code=500, detail={"errors": [f"Failed to access satellite scene: {str(e)}"]})


# ── Phase 3C: AOI Clipping & Band Preparation Endpoints ──

@router.post("/spatial/scenes/clip")
async def clip_spatial_scene(req: SpatialSceneClipRequest):
    """
    AOI Raster Clipping & Band Preparation Endpoint (Phase 3C).
    Transforms WGS84 AOI bounds to raster CRS, calculates window, executes windowed read
    of ONLY required pixels, writes single-band GeoTIFFs, and generates visualization previews.
    """
    scene_id = req.scene_id.strip()
    if not scene_id:
        raise HTTPException(status_code=422, detail={"errors": ["Missing required field 'scene_id'."]})

    sensor_upper = req.sensor.upper().strip()
    if sensor_upper not in ["SENTINEL-1", "SENTINEL-2"]:
        raise HTTPException(status_code=422, detail={"errors": [f"Invalid sensor '{req.sensor}'. Supported: 'SENTINEL-1', 'SENTINEL-2'."]})

    expected_collection = "sentinel-2-l2a" if sensor_upper == "SENTINEL-2" else "sentinel-1-grd"
    if req.collection != expected_collection:
        raise HTTPException(
            status_code=422,
            detail={"errors": [f"Collection mismatch: sensor '{sensor_upper}' requires '{expected_collection}', got '{req.collection}'."]},
        )

    aoi = req.aoi
    if aoi.min_lon >= aoi.max_lon or aoi.min_lat >= aoi.max_lat:
        raise HTTPException(status_code=422, detail={"errors": ["Invalid AOI coordinates: min must be strictly less than max."]})

    aoi_dict = {
        "min_lon": aoi.min_lon,
        "min_lat": aoi.min_lat,
        "max_lon": aoi.max_lon,
        "max_lat": aoi.max_lat,
    }

    clipper_service = SatelliteClipperService()
    try:
        manifest = await clipper_service.clip_scene_to_aoi(
            scene_id=scene_id,
            sensor=sensor_upper,
            collection=req.collection,
            aoi=aoi_dict,
        )
        return manifest

    except ValueError as ve:
        raise HTTPException(status_code=422, detail={"errors": [str(ve)]})
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail={"errors": [str(pe)]})
    except RuntimeError as re:
        raise HTTPException(status_code=502, detail={"errors": [str(re)]})
    except Exception as e:
        logger.error(f"[Spatial Scene Clip Error] {e}")
        raise HTTPException(status_code=500, detail={"errors": [f"Failed to clip satellite scene to AOI: {str(e)}"]})


@router.get("/spatial/scenes/preview/{preview_id}")
async def get_scene_preview(preview_id: str):
    """
    Secure Preview Image Endpoint.
    Validates preview_id token against registry and serves preview file.
    Prevents directory traversal and arbitrary filesystem access.
    """
    file_path = get_registered_preview(preview_id)
    if not file_path or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Requested preview image not found or expired.")

    return FileResponse(path=str(file_path), media_type="image/png")


@router.post("/spatial/scenes/analyze")
async def analyze_spatial_scene(req: SpatialSceneAnalyzeRequest, request: Request):
    """
    Phase 3D-1: Connects REAL Sentinel-2 AOI prepared datasets to Qwen2.5-VL for VQA / Captioning.

    Constraints & Design:
    1. Reuses existing Phase 3C prepared clip (does NOT re-download or re-clip).
    2. Validates sensor == "SENTINEL-2".
    3. Uses Phase 3C true_color.png RGB preview as Qwen2.5-VL visual input.
    4. Routes via RuleBasedRouter -> PipelineExecutor -> ModelRegistry -> QwenVLMWrapper -> OutputIntegrator.
    5. Restricts execution ONLY to VQA and Captioning tasks. Rejects other task types with 400.
    6. Preserves geospatial context (scene_id, AOI, CRS, bounds) and returns normalized response.
    """
    scene_id = req.scene_id.strip()
    if not scene_id:
        raise HTTPException(status_code=422, detail={"errors": ["Missing required field 'scene_id'."]})

    sensor_upper = req.sensor.upper().strip()
    if sensor_upper != "SENTINEL-2":
        raise HTTPException(
            status_code=422,
            detail={"errors": [f"Phase 3D-1 supports ONLY Sentinel-2 satellite analysis, got '{req.sensor}'."]},
        )

    aoi = req.aoi
    if aoi.min_lon >= aoi.max_lon or aoi.min_lat >= aoi.max_lat:
        raise HTTPException(status_code=422, detail={"errors": ["Invalid AOI coordinates: min must be strictly less than max."]})

    aoi_dict = {
        "min_lon": aoi.min_lon,
        "min_lat": aoi.min_lat,
        "max_lon": aoi.max_lon,
        "max_lat": aoi.max_lat,
    }

    # 1. Locate existing Phase 3C prepared clip manifest
    clipper_service = SatelliteClipperService()
    clip_manifest = clipper_service.get_prepared_clip(scene_id, aoi_dict)

    if not clip_manifest:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "Spatial scene has not been clipped to AOI yet. Please clip the scene before asking AI.",
            },
        )

    tc_path_str = clip_manifest.get("true_color_path")
    if not tc_path_str or not Path(tc_path_str).exists():
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "Required True Color RGB visual preview is missing from the prepared scene clip.",
            },
        )

    # 2. Query Routing via RuleBasedRouter
    router_inst = RuleBasedRouter()
    input_info = {
        "num_images": 1,
        "modalities": ["optical"],
        "is_temporal": False,
        "is_cross_modal": False,
    }
    decision = router_inst.route(req.query, input_info)

    # 3. Enforce Strict Supported Scope (VQA, CAPTION, GROUNDING)
    from app.agent.router import TaskType
    if decision.task_type not in (TaskType.VQA, TaskType.CAPTION, TaskType.GROUNDING):
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": (
                    f"Task type '{decision.task_type.value}' is not supported in spatial scene analysis. "
                    "Supported task types are Sentinel-2 VQA, Captioning, and Grounding."
                ),
            },
        )

    # 4. Pipeline Execution via existing Agent Architecture
    request_id = f"spatial_ai_{uuid.uuid4().hex[:8]}"
    registry = getattr(request.app.state, "model_registry", None)
    if registry is None or not registry.list_all():
        from app.models.registry import ModelRegistry
        from app.models.vqa import QwenVLMWrapper
        from app.models.grounding import GroundingModel, SegmentationModel
        registry = ModelRegistry()
        registry.register("rs_vlm", lambda: QwenVLMWrapper(), vram_gb=5.5)
        registry.register("grounding_dino", lambda: GroundingModel(), vram_gb=0.7)
        registry.register("sam", lambda: SegmentationModel(), vram_gb=0.35)

    executor = PipelineExecutor(registry)

    spatial_metadata = {
        "scene_id": scene_id,
        "sensor": "SENTINEL-2",
        "collection": req.collection,
        "aoi": aoi_dict,
        "crs": clip_manifest.get("output", {}).get("crs", "EPSG:4326"),
        "transform": clip_manifest.get("output", {}).get("transform"),
        "bounds": clip_manifest.get("preview_bounds") or [aoi.min_lon, aoi.min_lat, aoi.max_lon, aoi.max_lat],
        "dimensions": clip_manifest.get("output", {}).get("dimensions"),
        "visual_source": {
            "type": "sentinel-2-true-color",
            "bands": ["B04", "B03", "B02"],
        },
    }

    step_results = executor.execute(
        decision.pipeline, [tc_path_str], req.query, request_id, metadata=spatial_metadata
    )

    # 5. Synthesize Output via OutputIntegrator
    output = await OutputIntegrator().integrate_async(
        step_results, decision.task_type, req.query, request_id
    )

    # Build execution trace
    from app.agent.validator import ValidationResult
    dummy_val = ValidationResult(
        is_valid=True,
        num_images=1,
        format_info=[{"format": "png", "width": 100, "height": 100}],
        modalities=["optical"],
        is_temporal=False,
        is_cross_modal=False,
    )
    trace = TraceBuilder().build(dummy_val, decision, step_results)

    # Attach AOI preview evidence image
    evidence = output.get("evidence") or {"images": [], "regions": []}
    preview_url = clip_manifest.get("preview_url")
    if preview_url:
        evidence["images"].insert(0, {
            "type": "sentinel2_aoi_preview",
            "url": preview_url,
            "caption": f"Sentinel-2 L2A True Color AOI Clip ({scene_id[:20]}...)",
        })

    grounding_data = None
    if decision.task_type == TaskType.GROUNDING:
        target_an = output.get("target_analysis") or {}
        g_target_type = target_an.get("target_type") or output.get("target_type") or "generic"
        grounding_data = {
            "target": target_an.get("target", req.query),
            "target_type": g_target_type,
            "detections": output.get("evidence", {}).get("regions", []),
            "target_analysis": target_an,
            "built_up_analysis": output.get("built_up_analysis"),
            "vegetation_analysis": output.get("vegetation_analysis"),
        }

    return {
        "status": "success",
        "task": decision.task_type.value,
        "sensor": "SENTINEL-2",
        "scene_id": scene_id,
        "aoi": aoi_dict,
        "query": req.query,
        "answer": output["answer"],
        "confidence": output["confidence"],
        "status_text": output["status_text"],
        "input_badge": "Input: Real Sentinel-2 AOI Clip (B04, B03, B02 RGB)",
        "evidence": evidence,
        "grounding": grounding_data,
        "visual_source": {
            "type": "sentinel-2-true-color",
            "bands": ["B04", "B03", "B02"],
        },
        "preview_url": preview_url,
        "execution_trace": trace,
    }



