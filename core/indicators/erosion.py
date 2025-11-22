
"""Soil erosion potential indicators.

Simple screening indices for erosion potential, combining slope,
infiltration / AWC, and optionally land cover. These follow the
conceptual structure of RUSLE-like models (LSK factors) but are
deliberately simplified for portfolio screening use.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class ErosionInputs:
    slope_deg: np.ndarray
    awc_mm: np.ndarray
    land_cover: np.ndarray
    nodata: float = -9999.0


def erosion_potential(inputs: ErosionInputs) -> np.ndarray:
    """Compute a relative erosion potential index in [0, 1].

    This uses:
    * slope factor ~ tan(slope)
    * inverse AWC (lower capacity -> higher erosion)
    * a simple land-cover protection factor.
    """

    nodata = inputs.nodata
    out = np.full_like(inputs.slope_deg, nodata, dtype="float32")

    mask = (inputs.slope_deg != nodata) & (inputs.awc_mm != nodata) & (inputs.land_cover != nodata)
    if not np.any(mask):
        return out

    slope_rad = np.deg2rad(inputs.slope_deg[mask].astype("float32"))
    slope_factor = np.tan(slope_rad)
    slope_factor = slope_factor / (slope_factor.max() + 1e-6)

    awc = inputs.awc_mm[mask].astype("float32")
    awc_norm = (awc - awc.min()) / (awc.max() - awc.min() + 1e-6)
    awc_inv = 1.0 - awc_norm

    lc = inputs.land_cover[mask]
    protection = np.full_like(awc_inv, 0.5, dtype="float32")
    # crude CLC-inspired rules: forest protects, bare / urban expose
    forest = (lc >= 311) & (lc <= 313)
    urban = (lc >= 111) & (lc <= 142)
    bare = (lc >= 331) & (lc <= 335)

    protection[forest] = 0.2
    protection[urban | bare] = 0.8

    val = slope_factor * (0.5 * awc_inv + 0.5 * protection)
    val = val / (val.max() + 1e-6)
    out[mask] = val
    return out
