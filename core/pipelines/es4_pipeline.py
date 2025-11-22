
"""ES4-oriented hazard and exposure pipeline.

Focuses on physical hazards (slope, flood/erosion) and exposure of
receptor points (e.g. communities, assets).
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional

import numpy as np
import pandas as pd
import rasterio

from core.indicators.hydrology import HydroInputs, runoff_coefficient, flood_susceptibility
from core.indicators.erosion import ErosionInputs, erosion_potential
from core.indicators.esg_risk_scoring import sample_rasters_at_points, classify_points, load_thresholds


def run_es4_pipeline(site_cfg: Mapping[str, str], receptors: Optional[pd.DataFrame] = None, scoring_cfg_path: str = "config/scoring_es4.yaml") -> Dict[str, object]:
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

        hydro_inputs = HydroInputs(slope_deg=slope_deg, awc_mm=awc, land_cover=lc, nodata=nodata)
        runoff = runoff_coefficient(hydro_inputs)
        flood = flood_susceptibility(runoff, nodata)

        ero_inputs = ErosionInputs(slope_deg=slope_deg, awc_mm=awc, land_cover=lc, nodata=nodata)
        erosion_idx = erosion_potential(ero_inputs)

    indicators = {
        "slope": slope_deg,
        "runoff": runoff,
        "flood": flood,
        "erosion": erosion_idx,
    }

    thr = load_thresholds(scoring_cfg_path)
    classified = {}
    for name, arr in indicators.items():
        if name in thr:
            from core.indicators.esg_risk_scoring import classify_indicator
            classified[name] = classify_indicator(arr, thr[name], nodata=-9999.0)

    receptor_scores: Optional[pd.DataFrame] = None
    if receptors is not None and not receptors.empty:
        from rasterio.io import MemoryFile

        # Use runoff, flood, erosion as hazard layers
        tmp_rasters: Dict[str, rasterio.io.DatasetReader] = {}
        with rasterio.open(dem_path) as dem_ds:
            transform = dem_ds.transform
            crs = dem_ds.crs

        for name, arr in indicators.items():
            memfile = MemoryFile()
            with memfile.open(
                driver="GTiff",
                height=arr.shape[0],
                width=arr.shape[1],
                count=1,
                dtype=arr.dtype,
                transform=transform,
                crs=crs,
                nodata=-9999.0,
            ) as ds:
                ds.write(arr.astype("float32"), 1)
            tmp_rasters[name] = memfile.open()

        pts_with_vals = sample_rasters_at_points(tmp_rasters, receptors, x_col="longitude", y_col="latitude", nodata=-9999.0)
        receptor_scores = classify_points(pts_with_vals, thr, nodata=-9999.0)

        for ds in tmp_rasters.values():
            ds.close()

    return {
        "indicators": indicators,
        "classified": classified,
        "receptor_scores": receptor_scores,
    }
