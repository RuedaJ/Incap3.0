
"""Landscape fragmentation and natural habitat indicators."""

from __future__ import annotations

from typing import Dict

import numpy as np


# Basic classification of CLC-like codes into natural vs modified.
def natural_mask(land_cover: np.ndarray, nodata: float) -> np.ndarray:
    """Return a boolean mask where True indicates natural/semi-natural cover."""

    mask_valid = land_cover != nodata
    natural = np.zeros_like(land_cover, dtype=bool)
    # CLC 3xx, 4xx often semi-natural / forest / wetlands
    natural[(land_cover >= 311) & (land_cover <= 399) & mask_valid] = True
    return natural


def natural_fraction(land_cover: np.ndarray, nodata: float) -> float:
    """Compute the fraction of natural / semi-natural land in the raster."""

    mask_valid = land_cover != nodata
    if not np.any(mask_valid):
        return float("nan")
    nat = natural_mask(land_cover, nodata)
    return float(nat.sum()) / float(mask_valid.sum())


def fragmentation_index(land_cover: np.ndarray, nodata: float, window: int = 3) -> np.ndarray:
    """Compute a simple local fragmentation index in [0, 1].

    For each pixel, compute the share of natural pixels in a window
    around it. Values near 1 indicate contiguous natural cover, values
    near 0 indicate highly fragmented or converted landscapes.
    """

    from scipy.ndimage import uniform_filter  # type: ignore

    out = np.full_like(land_cover, nodata, dtype="float32")
    nat = natural_mask(land_cover, nodata).astype("float32")
    mask_valid = land_cover != nodata
    if not np.any(mask_valid):
        return out

    density = uniform_filter(nat, size=window, mode="nearest")
    out[mask_valid] = density[mask_valid]
    return out
