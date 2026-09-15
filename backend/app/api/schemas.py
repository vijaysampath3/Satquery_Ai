"""
API Schemas — Pydantic request/response models.

Agreed contract between M1 (Backend), M2 (Frontend), M3 (Agent).
"""

from pydantic import BaseModel, Field
from typing import Optional, Any


class EvidenceImage(BaseModel):
    """A generated evidence image (change map, overlay, etc.)."""
    type: str
    url: str
    caption: str


class BoundingRegion(BaseModel):
    """A detected bounding region with label and confidence."""
    bbox: list[float]
    label: str
    confidence: float


class Evidence(BaseModel):
    """Collection of evidence: images and detected regions."""
    images: list[EvidenceImage] = []
    regions: list[BoundingRegion] = []


class PipelineStep(BaseModel):
    """A single step in the execution pipeline."""
    step: int
    model: str
    action: str
    status: str
    time_ms: float
    error: Optional[str] = None


class ValidationInfo(BaseModel):
    """Input validation details for the execution trace."""
    image_count: int
    format: list[str]
    modality: list[str]
    temporal: bool
    cross_modal: bool
    compatible: bool
    warnings: list[str] = []


class ExecutionTrace(BaseModel):
    """Full execution trace — makes agent decisions transparent."""
    input_validation: ValidationInfo
    detected_task: str
    task_confidence: float
    reasoning: str
    selected_models: list[dict]
    pipeline_steps: list[PipelineStep]
    total_time_ms: float


class AnalysisResponse(BaseModel):
    """Complete API response for POST /api/analyze."""
    answer: str
    confidence: float
    evidence: Evidence
    execution_trace: ExecutionTrace


class HealthResponse(BaseModel):
    """Response for GET /api/health."""
    status: str
    models_loaded: list[str]
    gpu_available: bool
    gpu_memory_used: Optional[str] = None
    registered_models: Optional[list[dict]] = None


# ── Phase 3A: Spatial Scene Discovery Schemas ──

class BBoxModel(BaseModel):
    """Bounding box coordinates in WGS84 EPSG:4326."""
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


class SpatialSceneSearchRequest(BaseModel):
    """Request payload for POST /api/spatial/scenes/search."""
    bbox: BBoxModel
    crs: str = Field(default="EPSG:4326")
    sensor: str = Field(default="SENTINEL-2", description="SENTINEL-2 or SENTINEL-1")
    date_start: str = Field(default="2024-01-15", description="Start date YYYY-MM-DD")
    date_end: Optional[str] = Field(default=None, description="End date YYYY-MM-DD")
    cloud_cover_max: float = Field(default=30.0, description="Max cloud cover percentage for Sentinel-2")
    limit: int = Field(default=10, description="Max scenes to return")


# ── Phase 3B: Spatial Scene Access & Raster Validation Schemas ──

class SpatialSceneAccessRequest(BaseModel):
    """Request payload for POST /api/spatial/scenes/access."""
    scene_id: str = Field(..., description="Copernicus STAC Scene ID")
    sensor: str = Field(default="SENTINEL-2", description="SENTINEL-2 or SENTINEL-1")
    collection: str = Field(default="sentinel-2-l2a", description="sentinel-2-l2a or sentinel-1-grd")
    aoi: Optional[BBoxModel] = Field(default=None, description="Area of Interest bounding box")


class RasterMetadataModel(BaseModel):
    """Validated dynamic geospatial raster metadata."""
    width: int
    height: int
    band_count: int
    dtype: str
    crs: Optional[str] = None
    bounds: list[float]
    transform: list[float]
    resolution: list[float]
    nodata: Optional[float] = None
    band_descriptions: list[str] = []


class SpatialSceneAccessResponse(BaseModel):
    """Response payload for POST /api/spatial/scenes/access."""
    status: str = Field(..., description="'ready' or 'error'")
    scene: dict
    asset: dict
    raster: RasterMetadataModel
    aoi_intersection: dict
    preview_url: Optional[str] = None


# ── Phase 3C: Spatial Scene AOI Clipping & Preparation Schemas ──

class SpatialSceneClipRequest(BaseModel):
    """Request payload for POST /api/spatial/scenes/clip."""
    scene_id: str = Field(..., description="Copernicus STAC Scene ID")
    sensor: str = Field(default="SENTINEL-2", description="SENTINEL-2 or SENTINEL-1")
    collection: str = Field(default="sentinel-2-l2a", description="sentinel-2-l2a or sentinel-1-grd")
    aoi: BBoxModel = Field(..., description="Area of Interest bounding box")


class SpatialSceneClipResponse(BaseModel):
    """Response payload for POST /api/spatial/scenes/clip."""
    status: str = Field(..., description="'ready' or 'error'")
    request_id: str
    scene: dict
    aoi: dict
    output: dict
    bands: dict
    previews: dict
    preview_url: Optional[str] = None

# ── Phase 3D-1: Spatial Scene Analysis Schemas ──

class SpatialSceneAnalyzeRequest(BaseModel):
    """Request payload for POST /api/spatial/scenes/analyze."""
    scene_id: str = Field(..., description="Copernicus STAC Scene ID")
    sensor: str = Field(default="SENTINEL-2", description="Must be SENTINEL-2 for Phase 3D-1")
    collection: str = Field(default="sentinel-2-l2a", description="sentinel-2-l2a")
    aoi: BBoxModel = Field(..., description="Area of Interest bounding box")
    query: str = Field(..., description="Natural language question or instruction")


