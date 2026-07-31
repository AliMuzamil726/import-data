"""Vegetation-index computation.

Two paths are supported:

* **NDVI** — the correct calculation, ``(NIR - Red) / (NIR + Red)``. Needs a red
  band and a near-infrared band, which is what Sentinel-2 / Landsat / a NIR-capable
  drone gives you.
* **VARI** — ``(G - R) / (G + R - B)``, a visible-band proxy used when only an
  ordinary RGB photo is available. It correlates with canopy greenness but is not
  NDVI, so it is labelled separately everywhere it appears.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import numpy as np
from django.core.files.base import ContentFile
from PIL import Image

MAX_SIDE = 1600  # downsample very large rasters before processing

# Class boundaries on the index scale.
CRITICAL_MAX = 0.15
POOR_MAX = 0.30
MODERATE_MAX = 0.50

# Colour ramp applied to the overlay, from critical to healthy.
RAMP = np.array(
    [
        [178, 24, 43],    # critical
        [234, 88, 12],    # poor
        [245, 158, 11],   # moderate
        [124, 198, 123],  # healthy
        [30, 86, 49],     # very healthy
    ],
    dtype=np.uint8,
)


@dataclass
class IndexResult:
    index_used: str
    mean: float
    minimum: float
    maximum: float
    healthy_pct: float
    moderate_pct: float
    poor_pct: float
    critical_pct: float
    health_score: float
    overlay: ContentFile

    @property
    def band(self) -> str:
        """Map the mean index onto the health bands used across the platform."""
        if self.mean >= MODERATE_MAX:
            return "healthy"
        if self.mean >= POOR_MAX:
            return "moderate"
        if self.mean >= CRITICAL_MAX:
            return "poor"
        return "critical"


def _load_gray(file_field) -> np.ndarray:
    with Image.open(file_field) as image:
        image = image.convert("F")
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.BILINEAR)
        return np.asarray(image, dtype=np.float32)


def _load_rgb(file_field) -> np.ndarray:
    with Image.open(file_field) as image:
        image = image.convert("RGB")
        image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.BILINEAR)
        return np.asarray(image, dtype=np.float32)


def _colourise(index: np.ndarray) -> ContentFile:
    """Render the index array as a colour PNG for the map overlay."""
    normalised = np.clip((index + 1.0) / 2.0, 0.0, 1.0)
    positions = np.linspace(0.0, 1.0, len(RAMP))
    rgb = np.stack(
        [np.interp(normalised, positions, RAMP[:, channel]) for channel in range(3)],
        axis=-1,
    ).astype(np.uint8)

    alpha = np.where(np.isnan(index), 0, 210).astype(np.uint8)
    rgba = np.dstack([rgb, alpha])

    buffer = BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return ContentFile(buffer.read())


def compute_index(record) -> IndexResult:
    """Compute NDVI from band pairs, or VARI from a single RGB image."""
    if record.red_band and record.nir_band:
        red = _load_gray(record.red_band)
        nir = _load_gray(record.nir_band)
        if red.shape != nir.shape:
            raise ValueError(
                f"Band sizes differ: red is {red.shape[1]}×{red.shape[0]}, "
                f"NIR is {nir.shape[1]}×{nir.shape[0]}. Upload matching rasters."
            )
        denominator = nir + red
        index = np.divide(
            nir - red, denominator, out=np.zeros_like(denominator), where=denominator != 0
        )
        label = "NDVI"
    elif record.rgb_image:
        rgb = _load_rgb(record.rgb_image)
        r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
        denominator = g + r - b
        index = np.divide(
            g - r, denominator, out=np.zeros_like(denominator), where=denominator != 0
        )
        label = "VARI"
    else:
        raise ValueError("Upload a red + NIR band pair, or a single RGB image.")

    index = np.clip(index, -1.0, 1.0)
    total = index.size or 1

    critical = float((index < CRITICAL_MAX).sum() / total * 100)
    poor = float(((index >= CRITICAL_MAX) & (index < POOR_MAX)).sum() / total * 100)
    moderate = float(((index >= POOR_MAX) & (index < MODERATE_MAX)).sum() / total * 100)
    healthy = float((index >= MODERATE_MAX).sum() / total * 100)

    score = (healthy * 1.0 + moderate * 0.7 + poor * 0.35 + critical * 0.05)

    return IndexResult(
        index_used=label,
        mean=round(float(index.mean()), 4),
        minimum=round(float(index.min()), 4),
        maximum=round(float(index.max()), 4),
        healthy_pct=round(healthy, 2),
        moderate_pct=round(moderate, 2),
        poor_pct=round(poor, 2),
        critical_pct=round(critical, 2),
        health_score=round(score, 1),
        overlay=_colourise(index),
    )
