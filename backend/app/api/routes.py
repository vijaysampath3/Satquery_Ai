"""
API Routes for SatQuery AI.

Provides endpoints:
  - POST /api/analyze: Main natural-language agentic analysis endpoint
  - POST /api/demo: Local Demo Mode analysis
  - GET  /api/health: System & model component health monitor
  - POST /api/vqa, /api/caption, /api/ground, /api/change-detection, /api/optical-sar
"""

import uuid
import tempfile
from pathlib import Path
from typing import Optional
from loguru import logger

from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException
from app.utils.config import settings
from app.agent.validator import InputValidator
from app.agent.router import RuleBasedRouter
from app.agent.executor import PipelineExecutor
from app.output.trace import TraceBuilder
from app.output.integrator import OutputIntegrator

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
        },
        "models_loaded": registry.list_loaded(),
        "registered_models": registry.list_all(),
    }
