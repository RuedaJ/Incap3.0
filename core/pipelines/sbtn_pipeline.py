
"""SBTN-oriented baseline pipeline.

Computes simple baseline indicators for land system change and
freshwater dependency using land cover, AWC / recharge and erosion.
"""

from __future__ import annotations

from typing import Dict, Mapping

import numpy as np
import rasterio

from core.indicators.recharge import RechargeInputs, recharge_index
from core.indicators.fragmentation import natural_fraction, fragmentation_index
from core.indicators.erosion import ErosionInputs, erosion_potential


def run_sbtn_baseline(site_cfg: Mapping[str, str]) -> Dict[str, object]:
    dem_path = site_cfg.get("dem")
    awc_path = site_cfg.get("awc")
    lc_path = site_cfg.get("clc")

    if not (dem_path and awc_path and lc_path):
        raise ValueError("Site configuration must define 'dem', 'awc' and 'clc' paths.")

    with rasterio.open(dem_path) as dem_ds, rasterio.open(awc_path) as awc_ds, rasterio.open(lc_path) as lc_ds:
        dem = dem_ds.read(1)
        gy, gx = np.gradient(dem.astype("float32"))
        slope_rad = np.arctan(np.hypot(gx, gy))
        slope_deg = np.degrees(slope_rad)

        awc = awc_ds.read(1)
        lc = lc_ds.read(1)
        nodata = -9999.0

        rech_inputs = RechargeInputs(awc_mm=awc, land_cover=lc, nodata=nodata)
        rech_idx = recharge_index(rech_inputs)

        frag_idx = fragmentation_index(lc, nodata)
        nat_frac = natural_fraction(lc, nodata)

        ero_inputs = ErosionInputs(slope_deg=slope_deg, awc_mm=awc, land_cover=lc, nodata=nodata)
        erosion_idx = erosion_potential(ero_inputs)

    return {
        "recharge_index": rech_idx,
        "fragmentation_index": frag_idx,
        "natural_fraction": nat_frac,
        "erosion_index": erosion_idx,
    }
