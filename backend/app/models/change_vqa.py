"""
Change VQA Model Wrapper — Answers specific questions about detected bi-temporal changes.
"""

from loguru import logger
from app.models.base import BaseModelWrapper
from app.models.vqa import QwenVLMWrapper


class ChangeVQAModel(BaseModelWrapper):
    """
    Bi-temporal Question Answering wrapper.
    Combines Change Detection quantitative metrics with VLM natural language reasoning.
    """

    def __init__(self):
        self.vlm = QwenVLMWrapper()

    def run(self, action: str, context: dict) -> dict:
        logger.info("Executing Change VQA pipeline step")
        return self.vlm.run(action="describe_changes", context=context)
