"""
Oil Spill Detector Model Wrapper — Sentinel-1 SAR Analysis.

Supports action:
  - detect_oil_spill: Runs deterministic SAR image processing for slick candidates,
    generates visual evidence (mask, overlay, SAR scene), and returns structured statistics.
"""

import numpy as np
from PIL import Image
from loguru import logger

from app.models.base import BaseModelWrapper
from app.remote_sensing.oil_spill import detect_oil_spill
from app.remote_sensing.visualization import ensure_results_dir, save_array_to_png


class OilSpillDetectorModel(BaseModelWrapper):
    """
    Model wrapper for Sentinel-1 SAR Oil Spill Slick Detection.
    """

    def run(self, action: str, context: dict) -> dict:
        image_paths = context.get("images", [])
        request_id = context.get("request_id", "demo")
        query = context.get("query", "")
        metadata = context.get("metadata", {})

        if not image_paths:
            raise ValueError("Oil spill detection requires at least 1 Sentinel-1 SAR image.")

        primary_path = image_paths[0]
        logger.info(f"[{request_id}] Executing oil spill detection on '{primary_path}'")

        # Execute deterministic SAR oil spill processing pipeline
        result = detect_oil_spill(primary_path, metadata=metadata, query=query)

        # Generate visual evidence images if valid SAR data
        evidence_images = []
        if result["is_valid_sar"]:
            out_dir = ensure_results_dir(request_id)

            # 1. SAR Scene
            if result.get("sar_display") is not None:
                sar_path = out_dir / "sar_composite.png"
                Image.fromarray(result["sar_display"]).save(str(sar_path))
                evidence_images.append({
                    "url": f"/results/{request_id}/sar_composite.png",
                    "caption": "Sentinel-1 SAR Scene",
                })

            # 2. Oil Spill Mask
            if result.get("mask") is not None:
                mask_colored = np.zeros((*result["mask"].shape[:2], 3), dtype=np.uint8)
                mask_colored[result["mask"] > 0] = (255, 0, 128) # Magenta/Crimson highlight
                mask_colored[result["mask"] == 0] = (30, 30, 30) # Dark gray background
                mask_path = out_dir / "oil_spill_mask.png"
                Image.fromarray(mask_colored).save(str(mask_path))
                evidence_images.append({
                    "url": f"/results/{request_id}/oil_spill_mask.png",
                    "caption": f"Potential Slick Mask ({result['candidate_count']} candidates)",
                })

            # 3. Oil Spill Overlay
            if result.get("overlay") is not None:
                overlay_path = out_dir / "oil_spill_overlay.png"
                Image.fromarray(result["overlay"]).save(str(overlay_path))
                evidence_images.append({
                    "url": f"/results/{request_id}/oil_spill_overlay.png",
                    "caption": "Candidate Oil Slick Overlay",
                })

        return {
            "task": "OIL_SPILL",
            "type": "oil_spill_detection",
            "analysis_mode": result.get("analysis_mode", "Sentinel-1 SAR"),
            "detected": result["detected"],
            "candidate_count": result["candidate_count"],
            "affected_pixel_count": result["affected_pixel_count"],
            "affected_percentage": result["affected_percentage"],
            "sea_pixel_count": result["sea_pixel_count"],
            "total_pixels": result["total_pixels"],
            "regions": result["regions"],
            "method": result["method"],
            "warning": result["warning"],
            "answer": result["answer"],
            "status_text": result["status_text"],
            "input_badge": result["input_badge"],
            "evidence_images": evidence_images,
        }
