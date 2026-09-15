import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.utils.config import settings
from app.agent.llm_summarizer import generate_llm_overview, async_generate_llm_overview
from app.output.integrator import OutputIntegrator
from app.agent.executor import StepResult


def test_generate_llm_overview_missing_api_key(monkeypatch):
    """When OPENROUTER_API_KEY is not set, generate_llm_overview should return raw_answer without calling OpenRouter."""
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    raw = "OBSERVED:\n- Detected 5 water bodies."
    res = generate_llm_overview(raw_answer=raw, query="Highlight water")
    assert res == raw


@pytest.mark.anyio
async def test_async_generate_llm_overview_missing_api_key(monkeypatch):
    """Async variant returns raw_answer without calling OpenRouter when API key is missing."""
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    raw = "OBSERVED:\n- Detected 5 water bodies."
    res = await async_generate_llm_overview(raw_answer=raw, query="Highlight water")
    assert res == raw


def test_generate_llm_overview_with_mocked_success(monkeypatch):
    """When OPENROUTER_API_KEY is set and API returns 200, overview should return LLM response."""
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key-123")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "OBSERVED:\n- Clean summary content.\n\nINFERRED:\n- High confidence water detection."
                }
            }
        ]
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        res = generate_llm_overview(raw_answer="Raw evidence", query="Highlight water")
        assert "Clean summary content" in res
        mock_post.assert_called_once()
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer test-key-123"


@pytest.mark.anyio
async def test_async_generate_llm_overview_with_mocked_success(monkeypatch):
    """Async variant uses httpx.AsyncClient and returns LLM response when status is 200."""
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key-123")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "OBSERVED:\n- Async clean summary.\n\nINFERRED:\n- Water detected."
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
        res = await async_generate_llm_overview(raw_answer="Raw evidence", query="Highlight water")
        assert "Async clean summary" in res
        mock_post.assert_called_once()


@pytest.mark.anyio
async def test_output_integrator_integrate_async(monkeypatch):
    """Test OutputIntegrator.integrate_async executes non-blocking async LLM summary."""
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-key-123")
    
    mock_step = StepResult(
        step_num=1,
        model_name="test_model",
        action="detect",
        output={"answer": "OBSERVED:\n- Found 100 pixels.", "confidence": 0.95},
        time_ms=10.0,
        success=True,
    )

    with patch("app.output.integrator.async_generate_llm_overview", new_callable=AsyncMock) as mock_overview:
        mock_overview.return_value = "OBSERVED:\n- Async overview summary."
        integrator = OutputIntegrator()
        res = await integrator.integrate_async([mock_step], "water", "Highlight water")
        assert res["answer"] == "OBSERVED:\n- Async overview summary."
        mock_overview.assert_called_once()
