"""
InputValidator — Format, count, modality, and GeoTIFF validation for uploaded images.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from PIL import Image
from loguru import logger

from app.remote_sensing.preprocessing import load_geotiff_with_metadata


@dataclass
class ValidationResult:
    """Result of input validation — passed to router and trace builder."""
    is_valid: bool
    num_images: int
    modalities: list[str]
    is_temporal: bool
    is_cross_modal: bool
    format_info: list[dict]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class InputValidator:
    """
    Validates user-uploaded images before routing.
    Enforces image count, formats (.tif, .tiff, .geotiff, .png, .jpg, .jpeg),
    and readability via GeoTIFF / PIL parser.
    """

    VALID_EXTENSIONS = {".tif", ".tiff", ".geotiff", ".png", ".jpg", ".jpeg"}
    MAX_IMAGE_SIZE_MB = 50
    MAX_DIMENSION = 8192

    def validate(
        self,
        image_paths: list[str],
        metadata: Optional[dict] = None,
    ) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        format_info: list[dict] = []

        modalities = (
            metadata.get("modalities", ["optical"]) if metadata else ["optical"]
        )

        # Count check
        if len(image_paths) == 0:
            errors.append("No images provided. Please upload 1 or 2 satellite images.")
        if len(image_paths) > 2:
            errors.append(
                f"Maximum 2 images allowed, but {len(image_paths)} were provided. "
                "Upload 1 image for VQA/grounding, or 2 for change detection/cross-modal."
            )

        # Per-image checks
        for i, path in enumerate(image_paths):
            p = Path(path)
            img_label = f"Image {i + 1}"

            ext = p.suffix.lower()
            if ext not in self.VALID_EXTENSIONS:
                errors.append(
                    f"{img_label}: Unsupported format '{ext}'. "
                    f"Accepted: {', '.join(sorted(self.VALID_EXTENSIONS))}"
                )
                continue

            try:
                size_mb = p.stat().st_size / (1024 * 1024)
                if size_mb > self.MAX_IMAGE_SIZE_MB:
                    errors.append(
                        f"{img_label}: File too large ({size_mb:.1f} MB). Maximum: {self.MAX_IMAGE_SIZE_MB} MB."
                    )
                    continue
            except OSError as e:
                errors.append(f"{img_label}: Cannot access file — {e}")
                continue

            # Readability check using GeoTIFF / PIL parser
            try:
                mod = modalities[i] if i < len(modalities) else "optical"
                arr, geo_meta = load_geotiff_with_metadata(str(path), modality=mod)
                width = geo_meta.get("width", 0)
                height = geo_meta.get("height", 0)
                bands = geo_meta.get("bands", 1)

                if width > self.MAX_DIMENSION or height > self.MAX_DIMENSION:
                    warnings.append(
                        f"{img_label}: Large image ({width}×{height}). May be resampled during inference."
                    )

                format_info.append({
                    "filename": p.name,
                    "size": [width, height],
                    "bands": bands,
                    "format": ext,
                    "file_size_mb": round(size_mb, 2),
                    "crs": geo_meta.get("crs"),
                    "input_type": geo_meta.get("input_type"),
                })

            except Exception as e:
                errors.append(f"{img_label}: Cannot read image — {e}")

        while len(modalities) < len(image_paths):
            modalities.append("optical")
        modalities = modalities[: len(image_paths)]

        is_cross = (
            len(image_paths) == 2
            and len(modalities) >= 2
            and set(modalities[:2]) == {"optical", "sar"}
        )
        is_temporal = len(image_paths) == 2 and not is_cross

        if is_temporal:
            dates = metadata.get("dates", []) if metadata else []
            if not dates or len(dates) < 2:
                warnings.append(
                    "Bi-temporal input detected but no dates provided. Results may be less accurate."
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            num_images=len(image_paths),
            modalities=modalities,
            is_temporal=is_temporal,
            is_cross_modal=is_cross,
            format_info=format_info,
            errors=errors,
            warnings=warnings,
        )

    def validate_query(self, query: str) -> tuple[bool, str]:
        if not query or not query.strip():
            return False, "Query cannot be empty. Please ask a question about the satellite image(s)."

        if len(query.strip()) < 3:
            return False, "Query too short. Please provide a meaningful question."

        if len(query) > 2000:
            return False, "Query too long (max 2000 characters)."

        return True, ""
