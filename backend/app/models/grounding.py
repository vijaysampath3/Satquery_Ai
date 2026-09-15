"""
Grounding & Segmentation Model Wrapper — Grounding DINO + SAM / RS Fallback.

Supports actions:
  - detect_regions: Target feature extraction & bounding box localization
  - segment_regions: Binary segmentation mask overlay generation
"""

from loguru import logger
from app.models.base import BaseModelWrapper
from app.remote_sensing.grounding import detect_target_regions, classify_target_type
from app.remote_sensing.visualization import generate_evidence_visualizations


class GroundingModel(BaseModelWrapper):
    """
    Grounding model for target object/region detection.
    Uses Grounding DINO when installed, or falls back to remote sensing spectral segmentation.
    """

    def __init__(self):
        self._fallback_mode = True

    def run(self, action: str, context: dict) -> dict:
        image_path = context["images"][0]
        query = context["query"]
        metadata = context.get("metadata")

        logger.info(f"Grounding model executing for query: '{query}'")

        # Run remote sensing region detection
        result = detect_target_regions(image_path, query, metadata=metadata)

        return {
            "type": "detections",
            "boxes": result["boxes"],
            "geo_boxes": result.get("geo_boxes", []),
            "scores": result["scores"],
            "labels": result["labels"],
            "mask": result.get("mask"),
            "target": result["target"],
            "target_type": result.get("target_type", classify_target_type(result.get("target", ""))),
            "water_mask": result.get("water_mask"),
            "water_method": result.get("water_method"),
            "vegetation_mask": result.get("vegetation_mask"),
            "vegetation_method": result.get("vegetation_method"),
            "built_up_mask": result.get("built_up_mask"),
            "built_up_method": result.get("built_up_method"),
            "target_analysis": result.get("target_analysis"),
            "vegetation_analysis": result.get("vegetation_analysis"),
            "built_up_analysis": result.get("built_up_analysis"),
            "is_fallback": result["is_fallback"],
        }


class SegmentationModel(BaseModelWrapper):
    """
    Segmentation model wrapper for mask generation and visual evidence rendering.
    """

    def run(self, action: str, context: dict) -> dict:
        image_paths = context["images"]
        query = context["query"]
        request_id = context.get("request_id", "demo")
        intermediate = context.get("intermediate", {})

        detections = intermediate.get("step_1", {})
        target = detections.get("target", "target region")
        target_type = detections.get("target_type", classify_target_type(target))
        boxes = detections.get("boxes", [])
        geo_boxes = detections.get("geo_boxes", [])

        # Generate visual evidence images
        evidence_images = generate_evidence_visualizations(
            image_paths=image_paths,
            task_type="grounding",
            intermediate_data=intermediate,
            request_id=request_id,
        )

        _geo_list = geo_boxes if (len(geo_boxes) == len(boxes)) else [None] * len(boxes)
        regions = []
        for _label, _score, _box, _geo in zip(
            detections.get("labels", []),
            detections.get("scores", []),
            detections.get("boxes", []),
            _geo_list,
        ):
            regions.append({
                "label": _label,
                "confidence": _score,
                "box": _box,
                "bbox": _box,
                "geo_bbox": _geo,
                "target_type": target_type,
            })

        target_analysis = detections.get("target_analysis", {
            "target": target,
            "target_type": target_type,
            "method": "Spectral & Brightness Reflectance",
            "mask_available": True,
        })
        built_up_analysis = detections.get("built_up_analysis")
        vegetation_analysis = detections.get("vegetation_analysis")

        if boxes:
            method = target_analysis.get("method", "Spectral Reflectance")
            if target_type == "built_up":
                ans = f"OBSERVED: Identified {len(boxes)} region(s) matching '{target}'.\nINFERRED: Potential built-up regions identified using {method}."
                if built_up_analysis and "built_up_percentage" in built_up_analysis:
                    ans += f"\nBuilt-up Coverage: {built_up_analysis['built_up_percentage']}%"
            elif target_type == "vegetation":
                ans = f"OBSERVED: Identified {len(boxes)} region(s) matching '{target}'.\nINFERRED: Vegetation features identified using {method}."
                if vegetation_analysis and "vegetation_percentage" in vegetation_analysis:
                    ans += f"\nVegetation Coverage: {vegetation_analysis['vegetation_percentage']}%"
            else:
                ans = f"OBSERVED: Identified {len(boxes)} region(s) matching '{target}'.\nINFERRED: Highlighted bounding boxes display the spatial distribution of target features."
        else:
            ans = f"OBSERVED: No distinct regions found matching '{target}'.\nINFERRED: No reliable grounding region was identified in this satellite scene."

        return {
            "answer": ans,
            "status_text": "TARGET GROUNDING COMPLETE (Spectral & Contour Segmentation)",
            "evidence_images": evidence_images,
            "regions": regions,
            "target_type": target_type,
            "target_analysis": target_analysis,
            "built_up_analysis": built_up_analysis,
            "vegetation_analysis": vegetation_analysis,
        }
