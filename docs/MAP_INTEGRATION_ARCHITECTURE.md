# SatQuery AI — Phase 0: Project Audit & Map Integration Architecture

**Document Version:** 1.0.0  
**Date:** September 15, 2026  
**Status:** Audit Completed / Map Integration Design Phase  

---

## Executive Summary

This document presents the Phase 0 architecture audit for **SatQuery AI**, a multimodal remote sensing intelligence platform built for SIH 2026 / ISRO-SAC. SatQuery AI currently features an agentic natural language query engine capable of single-image visual question answering (VQA), scene captioning, object/target grounding and segmentation, bi-temporal change detection, optical-SAR cross-modal fusion, and Sentinel-1 SAR marine oil spill detection.

The system is fully operational with a Vite + React frontend (styled using modular Vanilla CSS) and a FastAPI backend powered by an internal model registry (Qwen2.5-VL GPU VLM engine with deterministic fallback, spectral/radar heuristics, and OpenRouter LLM summarizer).

This audit documents the current codebase, delineates untouched core components vs. safe extension points, and details the technical design for integrating interactive geospatial map functionalities (AOI selection, location search, satellite tile layers, and bi-temporal comparison).

---

## 1. Current Architecture Audit

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                 FRONTEND LAYER                                   │
│  React 18 + Vite | Vanilla CSS (Dark Theme) | React Router v6                      │
│                                                                                  │
│  Pages: Landing (`/`), Workspace (`/workspace`)                                  │
│  Components: Sidebar, Chat, Composer, Message, AnalysisResult, EvidenceGallery,  │
│              TechnicalDetails, FormattedEvidenceText, EmptyWorkspace, Navbar     │
│  API Client: `src/api/satquery.js` (POST /api/analyze, GET /api/health)           │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │ HTTP (FormData / Multipart)
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                 BACKEND LAYER                                    │
│  FastAPI Entrypoint: `backend/app/main.py` | Prefixes: `/api`                    │
│                                                                                  │
│  ├── Routes (`app/api/routes.py`): POST /api/analyze, POST /api/demo, GET /health │
│  ├── Input Validation (`app/agent/validator.py`): Format & spatial validation   │
│  ├── Agent Router (`app/agent/router.py`): Keyword & metadata classifier        │
│  ├── Pipeline Executor (`app/agent/executor.py`): Multi-step execution engine    │
│  ├── Model Registry (`app/models/registry.py`): Dynamic VRAM manager & loader   │
│  ├── Models (`app/models/`): Qwen2.5-VL, Grounding DINO/SAM, Change Det, Oil Spill│
│  ├── Preprocessing & Indices (`app/remote_sensing/`): Rasterio GeoTIFF parser,   │
│  │   NDVI, NDWI, NDBI, SAR composite, spatial morphology, visualization overlays │
│  └── Output Integrator (`app/output/integrator.py` + `app/agent/llm_summarizer.py`) │
│      Synthesizes OBSERVED metrics & INFERRED domain reasoning into response      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 Frontend Structure
- **Framework:** React 18.3.1 + Vite 6.0.3 + React Router DOM 6.28.0.
- **Styling Paradigm:** Pure Vanilla CSS with CSS custom properties (`global.css`, `landing.css`, `workspace.css`). No TailwindCSS is present or configured. Theme uses dark glassmorphism, cyan (`#06b6d4`) accents, purple (`#8b5cf6`) glows, and smooth transitions.
- **Pages:**
  - `Landing.jsx` (`/`): Public product landing page showcasing features, hero layout, sample use cases, and workspace navigation button.
  - `Workspace.jsx` (`/workspace`): Main application workspace managing chat sessions, image attachments (max 2 images), query composition, backend health polling every 15s, and rendering chat messages.
- **Components:**
  - `Sidebar.jsx`: Session management, new analysis trigger, navigation, and sidebar toggle.
  - `Chat.jsx`: Message history rendering, auto-scrolling, composer anchoring, system status indicator.
  - `Composer.jsx`: Multi-image attachment preview, modality toggle (Optical / SAR), natural language query input box.
  - `Message.jsx`: User & assistant chat bubble wrapper.
  - `AnalysisResult.jsx`: Primary result card rendering answer text, input badge, confidence percentage, task badge, and tab triggers.
  - `EvidenceGallery.jsx`: Renders generated visual evidence maps (NDVI, change maps, grounding masks, SAR composites) with full-screen zoom modal.
  - `TechnicalDetails.jsx`: Collapsible accordions for Execution Trace, Change Metrics, Target Analysis, and Land Cover breakdown.
  - `FormattedEvidenceText.jsx`: Parses Markdown & OBSERVED/INFERRED sections with structured headers and bullet styling.
  - `EmptyWorkspace.jsx`: Placeholder screen when starting a new session.
- **API Service File (`src/api/satquery.js`):**
  - `analyzeScene({ files, query, modalities, dates })`: Posts multipart `FormData` to `http://localhost:8000/api/analyze`. Normalizes relative evidence image URLs (`/results/...`) to absolute backend URLs (`http://localhost:8000/results/...`).
  - `fetchHealth()`: Fetches backend component readiness status from `GET /api/health`.
- **State Management:** Local React `useState` hooks in `Workspace.jsx`. Manages `sessions` array, `activeSessionId`, `attachments` array (`file`, `name`, `size`, `modality`, `thumbUrl`), `queryText`, `isAnalyzing` boolean, and `systemStatus` object.

### 1.2 Backend Structure
- **Framework:** FastAPI 0.115.0 + Uvicorn 0.30.0 + Pydantic 2.9.0 + Loguru 0.7.0.
- **Entrypoint (`backend/app/main.py`):**
  - Uses FastAPI async lifespan manager to register model wrappers in `ModelRegistry` on startup and unloads them on shutdown.
  - Mounts static directory `/results` serving generated PNG evidence visual maps.
  - Includes route router under `/api`.
- **Endpoints (`backend/app/api/routes.py`):**
  - `POST /api/analyze`: Accepts 1–2 satellite images + query text + modalities + dates. Executes validation -> routing -> execution -> trace building -> output integration.
  - `POST /api/demo`: Runs analysis on pre-bundled local sample GeoTIFF datasets (`data/demo/single/sample.tif`, `data/demo/change/`, `data/demo/multimodal/`).
  - `GET /api/health`: Returns readiness status of API, Qwen VLM (GPU or Fallback), Grounding, Change Detection, Oil Spill Detector, and Preprocessors.
- **Input Validation (`backend/app/agent/validator.py`):**
  - Validates image presence, file formats, array loadability, spatial coordinate system consistency, resolution ratio compatibility, and query string minimum length.
- **Agent Router (`backend/app/agent/router.py`):**
  - `RuleBasedRouter` classifies inputs & queries into 7 discrete task types:
    1. `TaskType.OIL_SPILL`: Keyword search for oil slick/spill -> Sentinel-1 SAR pipeline.
    2. `TaskType.OPTICAL_SAR`: 2-image optical + SAR or cross-modal query -> Fusion pipeline.
    3. `TaskType.CHANGE_VQA`: 2 bi-temporal images + specific change question -> Change map + Change VQA.
    4. `TaskType.CHANGE_DETECTION`: 2 bi-temporal images -> Change map + VLM description.
    5. `TaskType.GROUNDING`: Target highlight keywords ("highlight", "show me", "locate") -> Grounding DINO + SAM segmentation.
    6. `TaskType.CAPTION`: Scene description keywords ("describe", "summarize") -> VLM captioning.
    7. `TaskType.VQA`: Default single image question answering -> VLM VQA.
- **Pipeline Executor (`backend/app/agent/executor.py`):**
  - Sequentially steps through routing plan steps. Calls `registry.get(model_name)` and `model.run(action, context)`. Stores intermediate results in `context["intermediate"]` for downstream steps.
- **Model Registry (`backend/app/models/registry.py`):**
  - Thread-safe registry tracking VRAM allocations per model wrapper. Automatically unloads lowest priority models when VRAM limits are reached.
- **Output Integrator (`backend/app/output/integrator.py` & `backend/app/agent/llm_summarizer.py`):**
  - Combines execution outputs into unified schema. Calls `async_generate_llm_overview()` which prompts OpenRouter LLMs (Google Gemma 4 26B) to format technical outputs into structured **OBSERVED:** (technical metrics) and **INFERRED:** (environmental impact, confounding factors, actionable next steps) sections.

### 1.3 Existing AI Models
1. **Qwen2.5-VL (`backend/app/models/vqa.py`):**
   - High-capacity Vision-Language Model loaded on GPU when weights exist.
   - Handles single image VQA, captioning, bi-temporal change description, and post-fusion analysis.
   - When GPU/weights are absent, operates in **Remote Sensing VLM Engine Fallback Mode**, computing exact spectral land cover metrics (NDVI, NDWI, NDBI) and returning evidence-backed text explanations.
2. **Grounding DINO + SAM (`backend/app/models/grounding.py`):**
   - Object detection and segment mask generation wrapper.
   - Operates with spectral target classification heuristics for vegetation, water, and built-up areas.
3. **Change Detection Model (`backend/app/models/change_detection.py`):**
   - Bi-temporal image alignment, pixel diffing, NDVI divergence, NDWI water-change tracking, and adaptive threshold change mask generation.
4. **Optical-SAR Fusion Model (`backend/app/models/optical_sar.py`):**
   - Multimodal optical RGB + SAR radar composite fusion (VV/VH backscatter ratio).
5. **Sentinel-1 SAR Oil Spill Detector (`backend/app/models/oil_spill.py` & `app/remote_sensing/oil_spill.py`):**
   - Analyzes Sentinel-1 SAR backscatter for dark slick candidate detection, wind speed screening (3–12 m/s), land masking, adaptive Lee speckle filtering, thresholding, morphological opening/closing, and geometric feature extraction (area, perimeter, compactness, elongation, slickness index).

### 1.4 Existing Satellite & Geospatial Functionality
- **GeoTIFF & Metadata Handling (`backend/app/remote_sensing/preprocessing.py`):**
  - Reads GeoTIFF files using `rasterio` (with PIL fallback).
  - Preserves metadata dictionary: `crs` (e.g. `EPSG:4326`, `EPSG:32643`), `transform` (Affine 6-tuple), `bounds` (`[left, bottom, right, top]`), `resolution` (`[res_x, res_y]`), `width`, `height`, and band counts.
  - Applies 2%-98% percentile dynamic range normalization (`normalize_img`).
- **Spectral Indices (`backend/app/remote_sensing/indices.py`):**
  - **RGB Composite:** `[B04, B03, B02]` True Color.
  - **Color Infrared (CIR):** `[B08, B04, B03]` False Color.
  - **SAR Composite:** `[VV, VH, VV/VH ratio]`.
  - **NDVI:** True NDVI `(B08 - B04)/(B08 + B04)` or Visual Vegetation Index fallback for RGB.
  - **NDWI:** `(B03 - B08)/(B03 + B08)` for water body detection.
  - **NDBI:** `(B11 - B08)/(B11 + B08)` for built-up surface identification.
  - **Water Detection Heuristic:** `detect_water()` with spatial morphology connected-component noise cleanup (minimum blob size 150 px).
- **Change Analytics (`backend/app/remote_sensing/change.py`):**
  - Computes spatial correspondence ratio, resampled image dimension matching, total changed pixels, percentage area changed, vegetation loss/gain percentages, and water body expansion/recession metrics.

---

## 2. Existing Upload & Analysis Workflow

```
1. USER ATTACHES IMAGE & ENTERS QUERY
   └─ Composer.jsx: User selects 1-2 GeoTIFF/PNG/JPEG files.
   └─ User selects modality (optical / sar).
   └─ User types question: "Identify water body changes".

2. FRONTEND DISPATCH
   └─ Workspace.jsx -> analyzeScene() in src/api/satquery.js.
   └─ Construct FormData: 'images', 'query', 'modalities'.
   └─ POST request to http://localhost:8000/api/analyze.

3. BACKEND INGESTION & TEMPORARY STORAGE
   └─ routes.py: Writes uploaded images to temp dir (/tmp/satquery_xxxx/).
   └─ Extracts metadata: modalities, dates.

4. INPUT VALIDATION
   └─ InputValidator.validate(): Loads images via load_geotiff_with_metadata().
   └─ Checks format, dimensions, band counts, CRS, bounds.

5. AGENT ROUTING
   └─ RuleBasedRouter.route(): Analyzes query string + input metadata.
   └─ Assigns TaskType (e.g., CHANGE_DETECTION).
   └─ Generates multi-step execution plan.

6. PIPELINE EXECUTION
   └─ PipelineExecutor.execute(): Executes steps sequentially.
   └─ Loads models via ModelRegistry (auto VRAM management).
   └─ Saves generated evidence visual maps into static directory /results/.

7. OUTPUT INTEGRATION & LLM SUMMARIZATION
   └─ OutputIntegrator.integrate_async(): Gathers step outputs.
   └─ Calls async_generate_llm_overview() via OpenRouter API.
   └─ Formats response into structured OBSERVED & INFERRED markdown sections.

8. FRONTEND RENDERING
   └─ Workspace.jsx receives JSON payload.
   └─ Appends assistant message to chat history.
   └─ Renders text answer (FormattedEvidenceText), visual evidence (EvidenceGallery),
      and technical metrics/trace (TechnicalDetails).
```

---

## 3. Proposed Map Integration Architecture

The upcoming map integration will introduce an interactive geospatial map interface to SatQuery AI, enabling users to explore satellite basemaps, search global locations, draw Areas of Interest (AOIs), select Sentinel-1/Sentinel-2 acquisition dates, preview map layers, and seamlessly dispatch spatial bounding boxes or clipped satellite scenes directly into the existing AI analysis engine.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 SATQUERY AI WORKSPACE LAYOUT                                │
│                                                                                             │
│  ┌──────────────────────┐  ┌─────────────────────────────────┐  ┌────────────────────────┐  │
│  │   SIDEBAR NAVIGATION │  │     INTERACTIVE MAP VIEW        │  │   AI CHAT & ANALYTICS  │  │
│  │                      │  │  (Leaflet / OpenStreetMap / OS) │  │                        │  │
│  │  • Session History   │  │                                 │  │  • Query Composer      │  │
│  │  • Mode Switcher:    │  │  • Location Search Bar (Nominatim)│ • Natural Language Chat│  │
│  │    [Chat] [Map]      │  │  • Bounding Box AOI Selector   │  │  • OBSERVED / INFERRED │  │
│  │    [Split View]      │  │  • Sentinel-1/2 Date Selector   │  │  • Evidence Maps       │  │
│  │  • Preset Datasets   │  │  • Layer Control (RGB/NDVI/SAR) │  │  • Technical Metrics   │  │
│  │  • System Status     │  │  • Dual-Date Split Comparison   │  │  • PDF Report Export   │  │
│  └──────────────────────┘  └─────────────────────────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Proposed Data Flow with Spatial Map Integration

```
1. USER SELECTS AOI ON MAP
   └─ User searches location (e.g. "Suez Canal") or draws box on MapContainer.
   └─ Map returns BoundingBox: { min_lon, min_lat, max_lon, max_lat }, CRS: EPSG:4326.

2. SATELLITE DATA SELECTION / PREVIEW
   └─ User selects acquisition dates (T1: 2024-01-10, T2: 2024-05-15) & Modality (Optical / SAR).
   └─ Fronted requests metadata/preview tiles from backend POST /api/spatial/preview.

3. AOI EXTRACT & ANALYZE DISPATCH
   └─ User clicks "Analyze Selected AOI" in map toolbar or types a query in Chat.
   └─ Frontend passes spatial parameters (bbox, dates, modalities, query) to API.
   └─ If local raster exists: backend clips raster to bbox.
   └─ If remote dataset selected: backend fetches/crops Sentinel-1/2 tile for bbox.

4. SEAMLESS PIPELINE EXECUTION
   └─ Clipped GeoTIFF paths passed to existing InputValidator & PipelineExecutor.
   └─ Backend preserves exact spatial bounds & transform in output metadata.

5. SPATIAL RESULTS OVERLAY
   └─ Generated evidence maps (e.g. Change Mask PNG, NDVI geotiff, Oil Spill Polygons)
      are returned to frontend with GeoJSON / BoundingBox metadata.
   └─ Map adds AI Evidence Layer directly on top of the interactive satellite basemap.
```

---

## 4. Components & Files Impact Matrix

To ensure absolute safety and maintain 100% existing functionality, files are categorized into **Files to Modify**, **New Files to Create**, and **Files to Keep Untouched**.

### 4.1 Files That MUST Remain UNTOUCHED
> [!IMPORTANT]
> The following core engine files must NOT be modified or refactored. Their internal logic, schemas, and algorithm contracts are strictly preserved.

- `backend/app/agent/router.py` (RuleBasedRouter keyword classification contracts)
- `backend/app/agent/executor.py` (PipelineExecutor step execution loop)
- `backend/app/agent/validator.py` (InputValidator validation rules)
- `backend/app/agent/llm_summarizer.py` (OpenRouter OBSERVED/INFERRED prompt formatting)
- `backend/app/models/registry.py` (ModelRegistry VRAM management)
- `backend/app/models/vqa.py` (QwenVLMWrapper & fallback heuristics)
- `backend/app/models/grounding.py` (Grounding DINO & SAM wrappers)
- `backend/app/models/change_detection.py` (Bi-temporal change model wrapper)
- `backend/app/models/oil_spill.py` (Sentinel-1 oil spill model wrapper)
- `backend/app/output/integrator.py` (OutputIntegrator response builder)
- `backend/app/remote_sensing/indices.py` (NDVI, NDWI, NDBI, SAR formulas & water detector)
- `backend/app/remote_sensing/oil_spill.py` (Sentinel-1 dark slick radar detection algorithm)
- `frontend/src/components/AnalysisResult.jsx` (Result presentation component)
- `frontend/src/components/EvidenceGallery.jsx` (Evidence modal gallery)
- `frontend/src/components/TechnicalDetails.jsx` (Accordion trace viewer)
- `frontend/src/components/FormattedEvidenceText.jsx` (Markdown OBSERVED/INFERRED parser)

### 4.2 Files That Will Be MODIFIED (Safe Extension Points)

#### `frontend/package.json`
- **Addition:** Add Leaflet map dependencies:
  - `leaflet` (^1.9.4)
  - `react-leaflet` (^4.2.1)
  - `leaflet-geosearch` or custom Nominatim geocoding hook
  - `@types/leaflet` (devDependency)

#### `frontend/src/pages/Workspace.jsx`
- **Extension:** Introduce workspace view modes (`split`, `chat-only`, `map-only`).
- **State Additions:** Add state for `spatialAOI` (`bbox`, `coordinates`), `mapLayers`, and `isMapActive`.
- **Integration:** Render map component alongside or integrated with Chat component.

#### `frontend/src/api/satquery.js`
- **Extension:** Add helper function `analyzeSpatialAOI({ bbox, query, dates, modalities })` and `fetchSpatialTilePreview({ bbox, date, modality })`. Maintain existing `analyzeScene()` completely untouched.

#### `frontend/src/styles/workspace.css`
- **Extension:** Add grid/flex split layouts for side-by-side Map + Chat view, map floating control styles, and map popup themes matching the dark UI palette.

#### `backend/app/api/routes.py`
- **Extension:** Add optional spatial parameters (`bbox`, `geojson`) to `POST /api/analyze` or add non-breaking endpoint `POST /api/spatial/analyze`. Existing upload behavior remains 100% backward compatible.

#### `backend/app/remote_sensing/preprocessing.py`
- **Extension:** Add helper function `crop_geotiff_by_bbox(image_path, bbox_coords)` using `rasterio.mask` or pixel bounding box calculation.

### 4.3 NEW Files to Create

```
frontend/src/
├── components/
│   ├── Map/
│   │   ├── MapContainer.jsx      # Primary Leaflet map wrapper & tile layer switcher
│   │   ├── AOISelector.jsx       # Bounding box drawing tool & coordinate input
│   │   ├── LocationSearch.jsx    # Nominatim geocoding search bar
│   │   ├── LayerControl.jsx      # Satellite base maps (Esri, OSM, Sentinel tiles) & overlay manager
│   │   ├── SplitMapViewer.jsx    # Dual-map swipe container for bi-temporal date comparison
│   │   └── MapToolbar.jsx        # Quick actions: "Analyze AOI", "Clear Box", "Center View"
│   └── SpatialAnalysisPanel.jsx  # Floating map panel for date range selection & satellite metadata
backend/app/api/
└── spatial_routes.py             # Optional spatial API endpoints (AOI clipping, tile metadata)
```

---

## 5. Safest Integration Points

### 5.1 Interactive Map Integration
- **Frontend Container:** Embed `MapContainer.jsx` into `Workspace.jsx`. Controlled via a view-mode toggle in `Sidebar.jsx` or top navigation bar (`Chat View` | `Split View` | `Map View`).
- **Basemaps:** Use standard public XYZ tile services:
  - Esri World Imagery (`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`)
  - CartoDB Dark Matter (`https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png`)
  - OpenStreetMap (`https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`)

### 5.2 Location Search
- **Geocoding Service:** OpenStreetMap Nominatim API (`https://nominatim.openstreetmap.org/search?format=json&q=...`). Free, no API key required, reliable for global city/region/feature geocoding.

### 5.3 AOI Selection
- **Bounding Box Tool:** Leaflet Draw box plugin or lightweight custom rectangle click-drag handler. Exports bounding box:
  ```json
  {
    "min_lon": 32.30,
    "min_lat": 30.50,
    "max_lon": 32.60,
    "max_lat": 30.80,
    "crs": "EPSG:4326"
  }
  ```

### 5.4 Satellite Data Selection & Dates
- **Temporal Selector:** Date range pickers in `SpatialAnalysisPanel.jsx` allowing users to set Date 1 ($T_1$) and Date 2 ($T_2$) for change detection analysis.
- **Sensor Modality Selector:** Radios for Optical (Sentinel-2 MSI) vs. SAR (Sentinel-1 C-band Synthetic Aperture Radar).

### 5.5 Map Layers & Overlays
- **Overlay Manager:** When `POST /api/analyze` finishes processing an AOI, the returned evidence image URL (`/results/change_map_xxxx.png` or `grounding_mask_xxxx.png`) is bound as a Leaflet `L.imageOverlay` using the raster's geospatial bounding box `[left, bottom, right, top]`.

### 5.6 Single Image vs. Two-Image Comparison
- **Single Image Analysis:** AOI box clips single satellite scene -> routes to VQA, Captioning, or Grounding pipeline.
- **Two-Image Comparison:** Dual-date picker captures $T_1$ and $T_2$ rasters -> renders split-screen map slider (`SplitMapViewer.jsx`) -> routes to `CHANGE_DETECTION` or `CHANGE_VQA` pipeline.

---

## 6. Identified Risks & Mitigation Strategies

| Risk Factor | Impact | Level | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Tailwind vs. Vanilla CSS Conflict** | UI Layout Breaking | **High** | Do NOT introduce Tailwind. Build all map control styles using modular Vanilla CSS rules extending `workspace.css` and `global.css`. |
| **Leaflet CSS Tile Misalignment** | Map tiles render broken / distorted | **Medium** | Ensure `import 'leaflet/dist/leaflet.css';` is explicitly imported in `main.jsx` or `MapContainer.jsx`, and set container height to `100%`. |
| **GeoTIFF Coordinate Bounding Box Mismatch** | Evidence maps misplaced on map | **High** | Validate CRS transforms in `preprocessing.py`. Convert raster bounds to `EPSG:4326` (WGS84 lat/lon) before returning to frontend `L.imageOverlay`. |
| **Backend Raster Clipping Performance** | Memory spill during large AOI clip | **Medium** | Restrict maximum AOI size on frontend (e.g. max $50 \times 50\text{ km}^2$). Use `rasterio.windows.from_bounds()` for windowed reading without loading full scene into memory. |
| **Breakage of Existing Upload Flow** | Chat upload stops working | **Critical** | Keep `POST /api/analyze` backwards compatible. All spatial parameters (`bbox`, `geojson`) will be optional fields. |

---

## 7. Recommended Implementation Plan

Implementation should proceed in 4 incremental, non-breaking steps:

### Phase 1: Frontend Geospatial Foundation
1. Install Leaflet dependencies (`leaflet`, `react-leaflet`).
2. Create `src/components/Map/MapContainer.jsx` with dark mode tile layers and view switcher in `Workspace.jsx`.
3. Add `LocationSearch.jsx` using Nominatim API.
4. Add `AOISelector.jsx` for bounding box drawing and coordinate state tracking.

### Phase 2: Backend Spatial Support
1. Extend `preprocessing.py` with `crop_geotiff_by_bbox()` and coordinate bounding box extractor (`EPSG:4326`).
2. Update `POST /api/analyze` route to accept optional spatial bounding box metadata in form payload.
3. Ensure evidence images returned in output payload contain `bbox_wgs84` bounds for overlay mapping.

### Phase 3: Spatial Overlay & Result Integration
1. Implement automatic map overlay rendering in `Workspace.jsx` when evidence results arrive.
2. Build `LayerControl.jsx` allowing users to toggle visual overlays (NDVI heatmaps, Change Masks, Grounding Polygons) on top of the interactive map.

### Phase 4: Bi-Temporal Split View & Polish
1. Implement `SplitMapViewer.jsx` for side-by-side date comparison slider ($T_1$ vs. $T_2$).
2. Perform end-to-end verification across single image VQA, Grounding, Change Detection, and Oil Spill pipelines.

---

## Conclusion & Summary

The SatQuery AI project audit confirms a clean, modular, and well-tested architecture. The separation between the frontend components, rule-based agent router, model registry, and execution engine allows interactive map functionalities to be integrated smoothly without modifying core AI logic or disrupting existing file upload workflows.
