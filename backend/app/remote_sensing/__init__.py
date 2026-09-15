"""
Remote Sensing Processing Module for SatQuery AI.

Provides reusable preprocessing, spectral indices, bi-temporal change detection,
target grounding/segmentation, and visual evidence utilities.
"""

from app.remote_sensing.preprocessing import (
    normalize_img,
    load_band_array,
    read_bands_from_uploads,
    load_geotiff_with_metadata,
    check_band_sanity,
)
from app.remote_sensing.indices import (
    get_rgb,
    get_false_color,
    get_sar_composite,
    get_ndvi,
)
from app.remote_sensing.change import (
    align_images,
    compute_change_detection,
)
from app.remote_sensing.grounding import (
    detect_target_regions,
)
from app.remote_sensing.visualization import (
    generate_evidence_visualizations,
)

__all__ = [
    "normalize_img",
    "load_band_array",
    "read_bands_from_uploads",
    "load_geotiff_with_metadata",
    "check_band_sanity",
    "get_rgb",
    "get_false_color",
    "get_sar_composite",
    "get_ndvi",
    "align_images",
    "compute_change_detection",
    "detect_target_regions",
    "generate_evidence_visualizations",
]
