
"""Soil erodibility (K-factor) indicators.

This module provides helper functions to work with soil erodibility
rasters such as those published for the European Soil Data Centre
(ESDAC), including:

* K_factor_with_Ksat.tif
* K_factor_soiltexture_Wischmeier.tif
* K_GloSEM_factor.tif
* K_factor_with_Ksat_error.tif
* K_factor_soiltexture_Wischmeier_error.tif

The functions are intentionally lightweight and focus on:

* loading K-factor variants when available in a site configuration,
* normalising K-factor values to [0, 1] for comparability,
* deriving simple uncertainty metrics from error rasters.

These indicators can then be consumed by TNFD / ES4 / SBTN pipelines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional

import numpy as np
import rasterio


@dataclass
class KFactorRasters:
    """Container holding optional K-factor rasters for a site.

    All arrays share the same shape; any that are unavailable are set to None.
    """

    k_ksat: Optional[np.ndarray] = None
    k_wisch: Optional[np.ndarray] = None
    k_glosem: Optional[np.ndarray] = None
    k_ksat_error: Optional[np.ndarray] = None
    k_wisch_error: Optional[np.ndarray] = None
    nodata: float = -9999.0


def _load_optional(path: Optional[str]) -> Optional[np.ndarray]:
    if not path:
        return None
    try:
        with rasterio.open(path) as ds:
            return ds.read(1)
    except Exception:
        return None


def load_k_factors(site_cfg: Mapping[str, object], nodata: float = -9999.0) -> KFactorRasters:
    """Load K-factor rasters from a site configuration mapping.

    Expected keys (all optional):

    * 'k_ksat': path to K_factor_with_Ksat.tif
    * 'k_wischmeier': path to K_factor_soiltexture_Wischmeier.tif
    * 'k_glosem': path to K_GloSEM_factor.tif
    * 'k_ksat_error': path to K_factor_with_Ksat_error.tif
    * 'k_wischmeier_error': path to K_factor_soiltexture_Wischmeier_error.tif
    """

    return KFactorRasters(
        k_ksat=_load_optional(site_cfg.get("k_ksat")),
        k_wisch=_load_optional(site_cfg.get("k_wischmeier")),
        k_glosem=_load_optional(site_cfg.get("k_glosem")),
        k_ksat_error=_load_optional(site_cfg.get("k_ksat_error")),
        k_wisch_error=_load_optional(site_cfg.get("k_wischmeier_error")),
        nodata=nodata,
    )


def _normalise(arr: np.ndarray, nodata: float) -> np.ndarray:
    out = np.full_like(arr, nodata, dtype="float32")
    mask = arr != nodata
    if not np.any(mask):
        return out
    data = arr[mask].astype("float32")
    lo = float(np.nanpercentile(data, 2))
    hi = float(np.nanpercentile(data, 98))
    if hi <= lo:
        out[mask] = 0.5
        return out
    tmp = (data - lo) / (hi - lo)
    tmp = np.clip(tmp, 0.0, 1.0)
    out[mask] = tmp
    return out


def normalised_k_maps(k: KFactorRasters) -> Dict[str, np.ndarray]:
    """Return normalised K-factor variants in [0, 1] where available."""

    out: Dict[str, np.ndarray] = {}
    if k.k_ksat is not None:
        out["k_ksat"] = _normalise(k.k_ksat, k.nodata)
    if k.k_wisch is not None:
        out["k_wischmeier"] = _normalise(k.k_wisch, k.nodata)
    if k.k_glosem is not None:
        out["k_glosem"] = _normalise(k.k_glosem, k.nodata)
    return out


def uncertainty_width(error_raster: Optional[np.ndarray], nodata: float) -> Optional[float]:
    """Compute a simple measure of uncertainty width for a K error raster.

    The provided error rasters represent 90% prediction intervals (PI).
    Here we summarise their width as the 90th - 10th percentile of the
    error magnitude distribution (ignoring nodata).
    """

    if error_raster is None:
        return None
    mask = error_raster != nodata
    if not np.any(mask):
        return None
    data = np.abs(error_raster[mask].astype("float32"))
    p10 = float(np.nanpercentile(data, 10))
    p90 = float(np.nanpercentile(data, 90))
    return p90 - p10
