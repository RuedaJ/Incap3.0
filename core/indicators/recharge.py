
"""Groundwater recharge / infiltration indicators."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class RechargeInputs:
    awc_mm: np.ndarray
    land_cover: np.ndarray
    nodata: float = -9999.0


def recharge_index(inputs: RechargeInputs) -> np.ndarray:
    """Compute a simple groundwater recharge index in [0, 1].

    Higher values mean higher expected potential recharge / infiltration.
    This uses normalised AWC and a land-cover modifier.
    """

    nodata = inputs.nodata
    out = np.full_like(inputs.awc_mm, nodata, dtype="float32")
    mask = (inputs.awc_mm != nodata) & (inputs.land_cover != nodata)
    if not np.any(mask):
        return out

    awc = inputs.awc_mm[mask].astype("float32")
    awc_norm = (awc - awc.min()) / (awc.max() - awc.min() + 1e-6)

    lc = inputs.land_cover[mask]
    modifier = np.ones_like(awc_norm, dtype="float32")
    # forest and grassland enhance, urban reduces
    forest = (lc >= 311) & (lc <= 313)
    grass = (lc >= 321) & (lc <= 335)
    urban = (lc >= 111) & (lc <= 142)

    modifier[forest | grass] = 1.1
    modifier[urban] = 0.7

    val = awc_norm * modifier
    val = val / (val.max() + 1e-6)
    out[mask] = val
    return out
