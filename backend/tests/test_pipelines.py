"""
Integration Tests for SatQuery AI Backend Pipelines.

Tests all 5 core capabilities + Demo Mode + Health Endpoint via FastAPI TestClient:
  1. Feature 1: Single-image VQA
  2. Feature 2: Image Captioning
  3. Feature 3: Target Grounding & Highlighting
  4. Feature 4: Bi-temporal Change Detection
  5. Feature 5: Multimodal Optical + SAR Analysis
"""

import sys
import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client):
    """Verify system health endpoint returns healthy status & component readiness."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "system_components" in data
    assert data["system_components"]["api"] == "Ready"


def test_demo_vqa_pipeline(client):
    """Test Feature 1 (VQA) via Demo Mode."""
    response = client.post(
        "/api/demo",
        data={"demo_type": "single", "query": "Is there water in this image?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task"] == "vqa"
    assert "OBSERVED:" in data["answer"] or "Model:" in data.get("status_text", "")
    assert "evidence" in data
    assert "execution_trace" in data


def test_demo_caption_pipeline(client):
    """Test Feature 2 (Captioning) via Demo Mode."""
    response = client.post(
        "/api/demo",
        data={"demo_type": "single", "query": "Describe this satellite image."},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task"] == "caption"
    assert "OBSERVED:" in data["answer"] or "Remote sensing" in data["answer"]


def test_demo_grounding_pipeline(client):
    """Test Feature 3 (Grounding & Highlighting) via Demo Mode."""
    response = client.post(
        "/api/demo",
        data={"demo_type": "single", "query": "Highlight the water bodies"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task"] == "grounding"
    assert len(data["evidence"]["images"]) > 0


def test_demo_change_detection_pipeline(client):
    """Test Feature 4 (Bi-temporal Change Detection) via Demo Mode."""
    response = client.post(
        "/api/demo",
        data={"demo_type": "change", "query": "What changed between these two dates?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task"] in ["change_detection", "change_vqa"]
    assert "evidence" in data
    assert len(data["evidence"]["images"]) > 0


def test_demo_optical_sar_pipeline(client):
    """Test Feature 5 (Multimodal Optical + SAR) via Demo Mode."""
    response = client.post(
        "/api/demo",
        data={"demo_type": "multimodal", "query": "Analyze using optical and SAR imagery together"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["task"] == "optical_sar"
    assert "evidence" in data
    assert len(data["evidence"]["images"]) > 0


def test_analyze_file_upload(client):
    """Test POST /api/analyze with sample GeoTIFF upload."""
    sample_path = Path(__file__).resolve().parent.parent.parent / "data" / "demo" / "single" / "sample.tif"
    assert sample_path.exists()

    with open(sample_path, "rb") as f:
        files = [("images", ("sample.tif", f, "image/tiff"))]
        data = {"query": "What land cover types are visible?", "modalities": "optical"}
        response = client.post("/api/analyze", files=files, data=data)

    assert response.status_code == 200
    result = response.json()
    assert "answer" in result
    assert "execution_trace" in result
    assert result["execution_trace"]["input_validation"]["compatible"] is True
