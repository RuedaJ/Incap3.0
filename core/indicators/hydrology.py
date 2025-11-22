
"""Hydrology-related indicator calculations for nature risk assessments.

This module implements simple, transparent hydrological indicators using
raster inputs (DEM-derived slope, available water capacity / infiltration,
and land cover). It is designed to align with EU good practice for
physical risk and water dependency screening (e.g. EEA, JRC, INSPIRE
data models), but uses lightweight empirical formulas suitable for
portfolio-scale screening.

All functions operate on NumPy arrays with a common shape. Nodata handling
is explicit: values equal to `nodata` are ignored in calculations and
propagated to outputs.

Assumptions
----------
* Slope is given in degrees.
* AWC / infiltration is in mm (or a comparable positive quantity).
* Land cover is an integer-coded raster (e.g. CLC classes).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np


@dataclass
class HydroInputs:
    """Container for hydrological input rasters.

    Attributes
    ----------
    slope_deg : np.ndarray
        Slope in degrees.
    awc_mm : np.ndarray
        Available water capacity or infiltration proxy in mm.
    land_cover : np.ndarray
        Integer land cover codes (e.g. CLC).
    nodata : float
        Nodata value used in rasters.
    """

    slope_deg: np.ndarray
    awc_mm: np.ndarray
    land_cover: np.ndarray
    nodata: float = -9999.0


def _normalise(arr: np.ndarray, nodata: float, vmin: Optional[float] = None, vmax: Optional[float] = None) -> np.ndarray:
    """Normalise an array to [0, 1] ignoring nodata.

    Parameters
    ----------
    arr:
        Input array.
    nodata:
        Nodata value.
    vmin, vmax:
        Optional explicit min / max. If not provided, computed from valid data.
    """
    out = np.full_like(arr, nodata, dtype="float32")
    mask = arr != nodata
    if not np.any(mask):
        return out

    data = arr[mask].astype("float32")
    lo = float(vmin) if vmin is not None else float(np.nanpercentile(data, 2))
    hi = float(vmax) if vmax is not None else float(np.nanpercentile(data, 98))
    if hi <= lo:
        out[mask] = 0.0
    else:
        tmp = (data - lo) / (hi - lo)
        tmp = np.clip(tmp, 0.0, 1.0)
        out[mask] = tmp
    return out


def runoff_coefficient(inputs: HydroInputs) -> np.ndarray:
    """Compute a dimensionless runoff coefficient in [0, 1].

    A higher value means more rapid surface runoff and lower effective
    infiltration. This is a simple empirical index combining:

    * normalised slope (steeper -> more runoff),
    * inverted normalised AWC (lower AWC -> more runoff),
    * a land-cover factor (urban > cropland > forest).

    This is not a hydrological model, but a transparent screening index
    that can feed TNFD, ES4 and SBTN-style risk assessments.
    """

    nodata = inputs.nodata
    slope_n = _normalise(inputs.slope_deg, nodata, vmin=0.0, vmax=35.0)
    # Higher AWC => less runoff, so invert
    awc_n = _normalise(inputs.awc_mm, nodata)
    awc_inv = np.where(awc_n != nodata, 1.0 - awc_n, nodata)

    lc_factor = land_cover_runoff_factor(inputs.land_cover, nodata)

    out = np.full_like(inputs.slope_deg, nodata, dtype="float32")
    mask = (slope_n != nodata) & (awc_inv != nodata) & (lc_factor != nodata)
    if not np.any(mask):
        return out

    # weights chosen for interpretability, not calibration
    w_slope, w_awc, w_lc = 0.4, 0.3, 0.3
    val = w_slope * slope_n[mask] + w_awc * awc_inv[mask] + w_lc * lc_factor[mask]
    out[mask] = np.clip(val, 0.0, 1.0)
    return out


def land_cover_runoff_factor(lc: np.ndarray, nodata: float) -> np.ndarray:
    """Map land cover codes to a qualitative runoff factor in [0, 1].

    This function assumes CLC-like codes but is intentionally simple and
    can be updated to reflect local classifications. Typical mapping:

    * artificial surfaces -> high runoff (~0.9)
    * cropland -> medium-high runoff (~0.6)
    * grassland / shrubland -> medium (~0.4)
    * forest -> low (~0.2)
    * water / wetlands -> medium (context dependent)
    """
    out = np.full_like(lc, nodata, dtype="float32")
    mask = lc != nodata
    if not np.any(mask):
        return out

    # Default medium
    out[mask] = 0.5

    # Very simple CLC-inspired grouping
    urban = (lc >= 111) & (lc <= 142)
    cropland = (lc >= 211) & (lc <= 244)
    forest = (lc >= 311) & (lc <= 313)
    shrub_grass = (lc >= 321) & (lc <= 335)
    water = (lc >= 511) & (lc <= 523)

    out[urban & mask] = 0.9
    out[cropland & mask] = 0.6
    out[forest & mask] = 0.2
    out[shrub_grass & mask] = 0.4
    out[water & mask] = 0.5

    return out


def flood_susceptibility(runoff: np.ndarray, nodata: float, flow_acc: Optional[np.ndarray] = None) -> np.ndarray:
    """Compute a simple flood susceptibility index in [0, 1].

    If flow accumulation is provided it is used to upweight areas with
    high contributing area; otherwise, the runoff coefficient alone is used.
    """

    out = np.full_like(runoff, nodata, dtype="float32")
    mask = runoff != nodata
    if not np.any(mask):
        return out

    val = runoff.astype("float32")
    if flow_acc is not None:
        # normalise flow accumulation and combine
        facc_n = _normalise(flow_acc, nodata)
        comb_mask = mask & (facc_n != nodata)
        if np.any(comb_mask):
            tmp = 0.6 * val[comb_mask] + 0.4 * facc_n[comb_mask]
            val[comb_mask] = np.clip(tmp, 0.0, 1.0)

    out[mask] = val[mask]
    return out
