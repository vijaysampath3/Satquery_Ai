/**
 * SatQuery AI API Client.
 * Communicates with FastAPI backend for remote sensing analysis, health monitoring,
 * and Copernicus STAC satellite scene discovery.
 */

const API_BASE = 'http://localhost:8000';

export async function analyzeScene({ files, query, modalities = [], dates = [] }) {
  if (!files || files.length === 0) {
    throw new Error('Please upload at least 1 satellite image.');
  }
  if (!query || !query.trim()) {
    throw new Error('Please enter a query or question about your satellite imagery.');
  }

  const formData = new FormData();
  files.forEach((f) => formData.append('images', f));
  formData.append('query', query.trim());
  formData.append('modalities', modalities.length > 0 ? modalities.join(',') : 'optical');

  if (dates && dates.length > 0) {
    formData.append('dates', dates.join(','));
  }

  const response = await fetch(`${API_BASE}/api/analyze`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMsg =
      errorData.detail?.errors?.join(', ') ||
      errorData.detail ||
      `Analysis failed (HTTP ${response.status})`;
    throw new Error(errorMsg);
  }

  const data = await response.json();

  // Normalize evidence image URLs to absolute backend URLs
  if (data.evidence && Array.isArray(data.evidence.images)) {
    data.evidence.images = data.evidence.images.map((img) => ({
      ...img,
      url: img.url.startsWith('http') ? img.url : `${API_BASE}${img.url}`,
    }));
  }

  return data;
}

/**
 * Phase 3A: Discovers real Sentinel-1 and Sentinel-2 scenes via Copernicus STAC API.
 */
export async function searchSatelliteScenes({
  bbox,
  crs = 'EPSG:4326',
  sensor = 'SENTINEL-2',
  date_start = '2024-01-15',
  date_end = null,
  cloud_cover_max = 30.0,
  limit = 10,
}) {
  if (!bbox || bbox.min_lon === undefined || bbox.min_lat === undefined || bbox.max_lon === undefined || bbox.max_lat === undefined) {
    throw new Error('Select an area on the map before searching satellite scenes.');
  }

  const payload = {
    bbox: {
      min_lon: Number(bbox.min_lon),
      min_lat: Number(bbox.min_lat),
      max_lon: Number(bbox.max_lon),
      max_lat: Number(bbox.max_lat),
    },
    crs,
    sensor,
    date_start,
    date_end,
    cloud_cover_max: Number(cloud_cover_max),
    limit: Number(limit),
  };

  const response = await fetch(`${API_BASE}/api/spatial/scenes/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMsg =
      errorData.detail?.errors?.join(', ') ||
      errorData.detail ||
      `Scene search failed (HTTP ${response.status})`;
    throw new Error(errorMsg);
  }

  return await response.json();
}

/**
 * Phase 3B: Authenticated access and dynamic raster validation for selected Sentinel scene.
 */
export async function accessSatelliteScene({ scene_id, sensor = 'SENTINEL-2', collection = 'sentinel-2-l2a', aoi = null }) {
  if (!scene_id) {
    throw new Error('Scene ID is required to access satellite raster data.');
  }

  const payload = {
    scene_id,
    sensor,
    collection,
    aoi: aoi ? {
      min_lon: Number(aoi.min_lon),
      min_lat: Number(aoi.min_lat),
      max_lon: Number(aoi.max_lon),
      max_lat: Number(aoi.max_lat),
    } : null,
  };

  const response = await fetch(`${API_BASE}/api/spatial/scenes/access`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMsg =
      errorData.detail?.errors?.join(', ') ||
      errorData.detail ||
      `Satellite scene access failed (HTTP ${response.status})`;
    throw new Error(errorMsg);
  }

  return await response.json();
}

/**
 * Phase 3C: Windowed AOI raster clipping and band preparation.
 */
export async function clipSatelliteScene({ scene_id, sensor = 'SENTINEL-2', collection = 'sentinel-2-l2a', aoi }) {
  if (!scene_id) {
    throw new Error('Scene ID is required to clip satellite raster data.');
  }
  if (!aoi || aoi.min_lon === undefined || aoi.min_lat === undefined || aoi.max_lon === undefined || aoi.max_lat === undefined) {
    throw new Error('Valid Area of Interest (AOI) coordinates are required for raster clipping.');
  }

  const payload = {
    scene_id,
    sensor,
    collection,
    aoi: {
      min_lon: Number(aoi.min_lon),
      min_lat: Number(aoi.min_lat),
      max_lon: Number(aoi.max_lon),
      max_lat: Number(aoi.max_lat),
    },
  };

  const response = await fetch(`${API_BASE}/api/spatial/scenes/clip`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMsg =
      errorData.detail?.errors?.join(', ') ||
      errorData.detail ||
      `Satellite raster clipping failed (HTTP ${response.status})`;
    throw new Error(errorMsg);
  }

  const data = await response.json();
  if (data.preview_url && !data.preview_url.startsWith('http')) {
    data.preview_url = `${API_BASE}${data.preview_url}`;
  }
  if (data.previews) {
    Object.keys(data.previews).forEach((k) => {
      if (data.previews[k] && !data.previews[k].startsWith('http')) {
        data.previews[k] = `${API_BASE}${data.previews[k]}`;
      }
    });
  }
  return data;
}


/**
 * Phase 3D-1: Connects REAL Sentinel-2 AOI dataset to Qwen2.5-VL VQA & Captioning.
 */
export async function analyzeSatelliteScene({ scene_id, sensor = 'SENTINEL-2', collection = 'sentinel-2-l2a', aoi, query }) {
  if (!scene_id) {
    throw new Error('Select and clip a satellite scene before asking AI.');
  }
  if (!query || !query.trim()) {
    throw new Error('Please enter a question or prompt for AI analysis.');
  }
  if (!aoi || aoi.min_lon === undefined || aoi.min_lat === undefined || aoi.max_lon === undefined || aoi.max_lat === undefined) {
    throw new Error('Valid Area of Interest (AOI) coordinates are required.');
  }

  const payload = {
    scene_id,
    sensor,
    collection,
    aoi: {
      min_lon: Number(aoi.min_lon),
      min_lat: Number(aoi.min_lat),
      max_lon: Number(aoi.max_lon),
      max_lat: Number(aoi.max_lat),
    },
    query: query.trim(),
  };

  const response = await fetch(`${API_BASE}/api/spatial/scenes/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMsg =
      errorData.detail?.message ||
      errorData.detail?.errors?.join(', ') ||
      errorData.detail ||
      `Spatial AI analysis failed (HTTP ${response.status})`;
    throw new Error(errorMsg);
  }

  const data = await response.json();

  if (data.preview_url && !data.preview_url.startsWith('http')) {
    data.preview_url = `${API_BASE}${data.preview_url}`;
  }
  if (data.evidence && Array.isArray(data.evidence.images)) {
    data.evidence.images = data.evidence.images.map((img) => ({
      ...img,
      url: img.url.startsWith('http') ? img.url : `${API_BASE}${img.url}`,
    }));
  }

  return data;
}


export async function fetchHealth() {
  try {
    const response = await fetch(`${API_BASE}/api/health`);
    if (!response.ok) return { status: 'offline' };
    return await response.json();
  } catch (error) {
    return { status: 'offline', error: error.message };
  }
}

