/**
 * SatQuery AI API Client.
 * Communicates with FastAPI backend for remote sensing analysis & health monitoring.
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

export async function fetchHealth() {
  try {
    const response = await fetch(`${API_BASE}/api/health`);
    if (!response.ok) return { status: 'offline' };
    return await response.json();
  } catch (error) {
    return { status: 'offline', error: error.message };
  }
}
