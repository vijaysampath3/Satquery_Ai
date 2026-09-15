"""
RuleBasedRouter — Natural language query & input analysis classifier.

Classifies queries into 6 pipeline task types:
  - VQA: Single image visual question answering
  - CAPTION: Scene description
  - GROUNDING: Object/region highlighting & segmentation
  - CHANGE_DETECTION: Bi-temporal change detection & change map
  - CHANGE_VQA: Specific bi-temporal change question answering
  - OPTICAL_SAR: Multimodal Optical + SAR analysis
"""

from enum import Enum
from dataclasses import dataclass


class TaskType(Enum):
    """Supported task types for SatQuery AI pipeline."""
    VQA = "vqa"
    CAPTION = "caption"
    GROUNDING = "grounding"
    CHANGE_DETECTION = "change_detection"
    CHANGE_VQA = "change_vqa"
    OPTICAL_SAR = "optical_sar"
    OIL_SPILL = "oil_spill"


@dataclass
class RoutingDecision:
    """Routing Decision metadata for PipelineExecutor."""
    task_type: TaskType
    models: list[str]
    pipeline: list[dict]
    confidence: float
    reasoning: str


class RuleBasedRouter:
    """
    Deterministic task classifier using natural language keyword matching + input structure.
    Fast, reliable, CPU-friendly routing.
    """

    OIL_SPILL_KW = [
        "oil spill", "oil spills", "oil slick", "oil slicks",
        "oil leakage", "oil leak", "oil contaminated", "oil contamination",
        "oil-spill", "oil-slick",
    ]

    GROUNDING_KW = [
        "highlight", "show me", "locate", "find", "where is", "where are",
        "mark", "segment", "outline", "box", "identify region",
        "point out", "detect", "show the", "circle", "indicate",
    ]

    CAPTION_KW = [
        "describe", "caption", "summarize", "overview",
        "tell me about", "what does this show", "explain this",
        "what is in this", "give me a description", "summary",
    ]

    CHANGE_KW = [
        "change", "differ", "before", "after", "increase",
        "decrease", "grew", "expand", "transform", "evolve",
        "develop", "built", "construct", "demolish", "deforest",
        "urban", "sprawl", "flood", "recede", "shift",
    ]

    SPECIFIC_QUESTION_PREFIXES = [
        "has ", "is ", "did ", "does ", "how many", "how much",
        "was ", "were ", "are ", "have ", "can you tell",
    ]

    def route(self, query: str, input_info: dict) -> RoutingDecision:
        """
        Classify query + input_info into TaskType and build execution pipeline.
        """
        q = query.lower().strip()
        n = input_info.get("num_images", 1)
        mods = input_info.get("modalities", ["optical"])
        is_cross = input_info.get("is_cross_modal", False)

        # ── 0. Oil Spill Slick Candidate Detection ──
        if self._has_kw(q, self.OIL_SPILL_KW):
            return RoutingDecision(
                task_type=TaskType.OIL_SPILL,
                models=["oil_spill_detector"],
                pipeline=[
                    {"step": 1, "model": "oil_spill_detector", "action": "detect_oil_spill"},
                ],
                confidence=0.95,
                reasoning="Oil spill slick candidate detection request detected → Sentinel-1 SAR Oil Spill Pipeline",
            )

        # ── 1. Cross-modal Optical + SAR ──
        if is_cross or (n == 2 and set(mods) == {"optical", "sar"}) or ("sar" in q and "optical" in q) or "radar" in q:
            return RoutingDecision(
                task_type=TaskType.OPTICAL_SAR,
                models=["optical_sar_fusion", "rs_vlm"],
                pipeline=[
                    {"step": 1, "model": "optical_sar_fusion", "action": "fuse_modalities"},
                    {"step": 2, "model": "rs_vlm", "action": "analyze_fused"},
                ],
                confidence=0.95,
                reasoning="Cross-modal optical + SAR imagery detected → Multimodal Optical-SAR Fusion Pipeline",
            )

        # ── 2. Bi-temporal 2-image queries ──
        if n == 2:
            is_specific = any(q.startswith(w) for w in self.SPECIFIC_QUESTION_PREFIXES)
            if (is_specific or "?" in q) and q.strip("?") != "what changed" and self._has_kw(q, self.CHANGE_KW):
                return RoutingDecision(
                    task_type=TaskType.CHANGE_VQA,
                    models=["change_detection", "change_vqa"],
                    pipeline=[
                        {"step": 1, "model": "change_detection", "action": "generate_change_map"},
                        {"step": 2, "model": "change_vqa", "action": "describe_changes"},
                    ],
                    confidence=0.92,
                    reasoning="Bi-temporal input + specific change question → Change VQA Pipeline",
                )
            return RoutingDecision(
                task_type=TaskType.CHANGE_DETECTION,
                models=["change_detection", "rs_vlm"],
                pipeline=[
                    {"step": 1, "model": "change_detection", "action": "generate_change_map"},
                    {"step": 2, "model": "rs_vlm", "action": "describe_changes"},
                ],
                confidence=0.92,
                reasoning="Bi-temporal input detected → Change Detection & Analysis Pipeline",
            )

        # ── 3. Single image Grounding ──
        from app.remote_sensing.grounding import classify_target_type
        target_cat = classify_target_type(q)
        is_question = any(q.startswith(w) for w in self.SPECIFIC_QUESTION_PREFIXES) or q.startswith("what is") or q.startswith("what are")

        if self._has_kw(q, self.GROUNDING_KW) or (target_cat in ("vegetation", "water", "built_up") and not is_question):
            return RoutingDecision(
                task_type=TaskType.GROUNDING,
                models=["grounding_dino", "sam"],
                pipeline=[
                    {"step": 1, "model": "grounding_dino", "action": "detect_regions"},
                    {"step": 2, "model": "sam", "action": "segment_regions"},
                ],
                confidence=0.95,
                reasoning="Target region request detected → Grounding & Highlight Segmentation Pipeline",
            )

        # ── 4. Single image Captioning ──
        if self._has_kw(q, self.CAPTION_KW):
            return RoutingDecision(
                task_type=TaskType.CAPTION,
                models=["rs_vlm"],
                pipeline=[
                    {"step": 1, "model": "rs_vlm", "action": "generate_caption"},
                ],
                confidence=0.90,
                reasoning="Scene description request detected → VLM Captioning Pipeline",
            )

        # ── 5. Default: Single image VQA ──
        return RoutingDecision(
            task_type=TaskType.VQA,
            models=["rs_vlm"],
            pipeline=[
                {"step": 1, "model": "rs_vlm", "action": "answer_question"},
            ],
            confidence=0.88,
            reasoning="Visual question query detected → VQA Pipeline",
        )

    def _has_kw(self, query: str, keywords: list[str]) -> bool:
        return any(kw in query for kw in keywords)
