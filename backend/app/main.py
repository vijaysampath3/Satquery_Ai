"""
SatQuery AI — FastAPI Backend Application Entry Point.

Registers model wrappers with ModelRegistry and serves the Analysis & Health API.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api.routes import router
from app.utils.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("🚀 Starting SatQuery AI backend...")

    # ── Register Model Wrappers ──
    from app.models.registry import ModelRegistry
    from app.models.vqa import QwenVLMWrapper
    from app.models.grounding import GroundingModel, SegmentationModel
    from app.models.change_detection import ChangeDetectionModel
    from app.models.change_vqa import ChangeVQAModel
    from app.models.optical_sar import OpticalSARFusionModel
    from app.models.oil_spill import OilSpillDetectorModel

    registry = ModelRegistry()

    # VQA + Captioning + Change Description (Qwen2.5-VL / VLM Engine)
    registry.register("rs_vlm", lambda: QwenVLMWrapper(), vram_gb=5.5)

    # Grounding (Grounding DINO + SAM / RS Fallback)
    registry.register("grounding_dino", lambda: GroundingModel(), vram_gb=0.7)
    registry.register("sam", lambda: SegmentationModel(), vram_gb=0.35)

    # Change Detection (Alignment, Difference, NDVI Divergence)
    registry.register("change_detection", lambda: ChangeDetectionModel(), vram_gb=0.15)

    # Change VQA
    registry.register("change_vqa", lambda: ChangeVQAModel(), vram_gb=5.5)

    # Optical-SAR Multimodal Fusion
    registry.register("optical_sar_fusion", lambda: OpticalSARFusionModel(), vram_gb=0.5)

    # Oil Spill Detection (Sentinel-1 SAR Backscatter Engine)
    registry.register("oil_spill_detector", lambda: OilSpillDetectorModel(), vram_gb=0.1)

    app.state.model_registry = registry

    logger.info(
        f"Registered {len(registry.list_all())} models: "
        f"{[m['name'] for m in registry.list_all()]}"
    )
    logger.info("✅ SatQuery AI backend initialized")

    yield

    # Shutdown
    logger.info("Stopping SatQuery AI backend...")
    registry.unload_all()


app = FastAPI(
    title="SatQuery AI",
    description="Multimodal Remote-Sensing Intelligence Assistant — SIH 2026 / ISRO-SAC",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static evidence results directory
app.mount("/results", StaticFiles(directory=str(settings.RESULTS_DIR)), name="results")

# Include API routes
app.include_router(router, prefix="/api")
