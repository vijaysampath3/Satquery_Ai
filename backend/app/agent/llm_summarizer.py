import json
import os
import requests
import httpx
from loguru import logger
from app.utils.config import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Primary OpenRouter model endpoint (Google Gemma 4 26B A4B)
MODEL_CANDIDATES = [
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-26b-a4b-it",
    "google/gemma-4-31b-it:free",
]


def _clean_llm_output(content: str) -> str:
    """Removes internal thinking process logs, scratchpad leaks, or prompt artifacts from LLM response."""
    if not content:
        return ""

    # Strip <think>...</think> blocks if present
    if "<think>" in content and "</think>" in content:
        content = content.split("</think>")[-1].strip()

    # If response contains internal thinking process headers, extract starting from OBSERVED: or INFERRED:
    for header in ["OBSERVED:", "INFERRED:"]:
        if header in content:
            idx = content.find(header)
            if idx > 0 and any(keyword in content[:idx].lower() for keyword in ["thinking", "process", "prompt", "analyze user input"]):
                content = content[idx:].strip()
                break

    return content.strip()


def _build_prompts(raw_answer: str, query: str = "") -> tuple[str, str, dict]:
    system_prompt = (
        "You are an expert satellite remote sensing intelligence assistant explaining satellite image analysis results to users.\n"
        "Your goal is to provide a simple, easy to understand, yet detailed explanation of the results using clear bullet points and appropriate side headings.\n\n"
        "STRICT FORMAT & CONTENT RULES:\n"
        "1. Structure your output into two main sections starting with the exact headers 'OBSERVED:' and 'INFERRED:'.\n"
        "2. UNDER OBSERVED:\n"
        "   - Use clear side headings (e.g., ### Technical Metrics & Image Parameters, ### Detection & Statistical Breakdown).\n"
        "   - Provide detailed, easy-to-understand bullet points for image dimensions, compared pixels, algorithm thresholds, change percentages, and category losses/gains.\n"
        "   - Retain 100% precision on all numbers, percentages, and sensor facts.\n"
        "3. UNDER INFERRED:\n"
        "   - Use clear side headings (e.g., ### Environmental & Physical Impact, ### Potential Confounding Factors, ### Actionable Follow-Up Steps).\n"
        "   - Explain real-world physical implications (e.g., causes for vegetation loss/gain like drought, harvesting, rainfall) in simple language.\n"
        "   - Detail potential look-alikes or confounding features (cloud/terrain shadows, moisture variations, atmospheric haze) in clear points.\n"
        "   - Detail sensor modality context (optical RGB visual reflectance vs SAR radar wave dampening/dark patches).\n"
        "   - Under '### Actionable Follow-Up Steps', list clear, actionable bullet points for next steps.\n"
        "4. Tone must be crystal clear, engaging, highly detailed, easy for non-technical users to grasp, and structured point-by-point with appropriate side headings.\n"
    )

    user_prompt = f"User Query: {query or 'Analyze satellite image'}\n\nTechnical Observations:\n{raw_answer}"

    api_key = (settings.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")).strip()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return system_prompt, user_prompt, headers


async def async_generate_llm_overview(raw_answer: str, query: str = "", task_type: str = "") -> str:
    """
    Non-blocking async call to OpenRouter via httpx.AsyncClient.
    Converts raw technical observations into a user-friendly summary without freezing the FastAPI event loop.
    """
    if not raw_answer or "Pipeline execution encountered an error" in raw_answer:
        return raw_answer

    api_key = (settings.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")).strip()
    if not api_key:
        logger.warning(
            "OPENROUTER_API_KEY is missing or empty. Skipping OpenRouter API requests and utilizing deterministic fallback."
        )
        return raw_answer

    system_prompt, user_prompt, headers = _build_prompts(raw_answer, query)

    async with httpx.AsyncClient(timeout=60.0) as client:
        for model_name in MODEL_CANDIDATES:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            }

            try:
                logger.info(f"Calling OpenRouter model '{model_name}' (async, timeout=60s)...")
                response = await client.post(
                    url=OPENROUTER_URL,
                    headers=headers,
                    json=payload,
                )

                if response.status_code == 200:
                    res_data = response.json()
                    choices = res_data.get("choices", [])
                    if choices:
                        message = choices[0].get("message", {})
                        content = (message.get("content") or "").strip()
                        content = _clean_llm_output(content)

                        if content and ("OBSERVED:" in content or "INFERRED:" in content):
                            logger.success(f"Successfully generated LLM summary via '{model_name}'")
                            return content
                        elif content:
                            logger.success(f"Generated overview via '{model_name}'")
                            return f"OBSERVED:\n- {content}"
                else:
                    logger.warning(f"OpenRouter API ({model_name}) returned status code {response.status_code}: {response.text}")
            except Exception as e:
                logger.warning(f"OpenRouter request to '{model_name}' failed ({e}); trying next candidate model...")

    logger.warning("All OpenRouter candidate models timed out or failed; utilizing deterministic result fallback.")
    return raw_answer


def generate_llm_overview(raw_answer: str, query: str = "", task_type: str = "") -> str:
    """
    Synchronous fallback call to OpenRouter via requests & json.
    Used for CLI scripts, background workers, or unit tests.
    """
    if not raw_answer or "Pipeline execution encountered an error" in raw_answer:
        return raw_answer

    api_key = (settings.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")).strip()
    if not api_key:
        logger.warning(
            "OPENROUTER_API_KEY is missing or empty. Skipping OpenRouter API requests and utilizing deterministic fallback."
        )
        return raw_answer

    system_prompt, user_prompt, headers = _build_prompts(raw_answer, query)

    for model_name in MODEL_CANDIDATES:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        try:
            logger.info(f"Calling OpenRouter model '{model_name}' (sync, timeout=60s)...")
            response = requests.post(
                url=OPENROUTER_URL,
                headers=headers,
                data=json.dumps(payload),
                timeout=60,
            )

            if response.status_code == 200:
                res_data = response.json()
                choices = res_data.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    content = (message.get("content") or "").strip()
                    content = _clean_llm_output(content)

                    if content and ("OBSERVED:" in content or "INFERRED:" in content):
                        logger.success(f"Successfully generated simple LLM summary via '{model_name}'")
                        return content
                    elif content:
                        logger.success(f"Generated overview via '{model_name}'")
                        return f"OBSERVED:\n- {content}"
            else:
                logger.warning(f"OpenRouter API ({model_name}) returned status code {response.status_code}: {response.text}")
        except Exception as e:
            logger.warning(f"OpenRouter request to '{model_name}' failed ({e}); trying next candidate model...")

    logger.warning("All OpenRouter candidate models timed out or failed; utilizing deterministic result fallback.")
    return raw_answer
