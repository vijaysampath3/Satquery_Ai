"""
Optical-SAR Multimodal Fusion Model Wrapper.

Combines Sentinel-2 optical imagery with Sentinel-1 SAR radar imagery to perform
dual-modality terrain, moisture, and structural analysis.
"""

import numpy as np
from loguru import logger
from app.models.base import BaseModelWrapper
from app.remote_sensing.preprocessing import load_geotiff_with_metadata
from app.remote_sensing.indices import get_rgb, get_sar_composite, get_ndvi
from app.remote_sensing.visualization import generate_evidence_visualizations
from app.models.vqa import QwenVLMWrapper


class OpticalSARFusionModel(BaseModelWrapper):
    """
    Multimodal Optical + SAR Fusion Model wrapper.
    Processes 12-channel Sentinel-1/Sentinel-2 input representations,
    computes radar/spectral features, and renders dual visual evidence.
    """

    def __init__(self):
        self.vlm = QwenVLMWrapper()

    def run(self, action: str, context: dict) -> dict:
        image_paths = context["images"]
        request_id = context.get("request_id", "demo")

        optical_path = image_paths[0]
        sar_path = image_paths[1] if len(image_paths) > 1 else optical_path

        logger.info(f"Executing Optical-SAR fusion on '{optical_path}' + '{sar_path}'")

        arr_opt, meta_opt = load_geotiff_with_metadata(optical_path)
        arr_sar, meta_sar = load_geotiff_with_metadata(sar_path)

        rgb = get_rgb(arr_opt)
        ndvi = get_ndvi(arr_opt)
        sar_comp = get_sar_composite(arr_sar)

        intermediate_step = {
            "step_1": {
                "optical_meta": meta_opt,
                "sar_meta": meta_sar,
                "veg_pct": round(float(np.mean(ndvi > 0.3) * 100.0), 1),
                "water_pct": round(float(np.mean(ndvi < -0.05) * 100.0), 1),
            }
        }

        # Generate dual evidence images (RGB, SAR composite, NDVI)
        evidence_images = generate_evidence_visualizations(
            image_paths=[optical_path, sar_path],
            task_type="optical_sar",
            intermediate_data=intermediate_step,
            request_id=request_id,
        )

        vlm_res = self.vlm.run(action="analyze_fused", context=context)

        return {
            "type": "optical_sar_fusion",
            "answer": vlm_res["answer"],
            "status_text": vlm_res.get("status_text", "FALLBACK ENGINE: Multimodal Optical + SAR Feature Fusion Engine"),
            "input_badge": "Input: Sentinel-1 SAR + Sentinel-2 Optical",
            "evidence_images": evidence_images,
        }

