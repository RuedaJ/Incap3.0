
"""TNFD-oriented nature risk pipeline.

This pipeline computes hydrological, erosion, recharge and fragmentation
indicators for a given site, and aggregates them into simple TNFD-style
risk scores at site and asset level.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional

import numpy as np
import pandas as pd
import rasterio

from core.indicators.hydrology import HydroInputs, runoff_coefficient, flood_susceptibility
from core.indicators.erosion import ErosionInputs, erosion_potential
from core.indicators.recharge import RechargeInputs, recharge_index
from core.indicators.fragmentation import fragmentation_index
from core.indicators.esg_risk_scoring import (
    load_thresholds,
    classify_indicator,
    aggregate_site_score,
    sample_rasters_at_points,
    classify_points,
)


def _load_raster(path: str):
    return rasterio.open(path)


def run_tnfd_pipeline(site_cfg: Mapping[str, str], sample_points: Optional[pd.DataFrame] = None, scoring_cfg_path: str = "config/scoring_tnfd.yaml") -> Dict[str, object]:
    """Run the TNFD screening pipeline for a site.

    Parameters
    ----------
    site_cfg:
        Mapping of logical layer names (e.g. 'dem', 'awc', 'clc') to file paths.
    sample_points:
        Optional DataFrame with at least 'longitude' and 'latitude' columns.
    scoring_cfg_path:
        Path to the TNFD scoring configuration YAML.
    """

    dem_path = site_cfg.get("dem")
    awc_path = site_cfg.get("awc")
    lc_path = site_cfg.get("clc")

    if not (dem_path and awc_path and lc_path):
        raise ValueError("Site configuration must define 'dem', 'awc' and 'clc' paths.")

    with _load_raster(dem_path) as dem_ds, _load_raster(awc_path) as awc_ds, _load_raster(lc_path) as lc_ds:
        dem = dem_ds.read(1)
        # approximate slope in degrees from elevation differences
        # This is a simple placeholder; consider precomputing slope with gdaldem.
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

        rech_inputs = RechargeInputs(awc_mm=awc, land_cover=lc, nodata=nodata)
        rech_idx = recharge_index(rech_inputs)

        frag_idx = fragmentation_index(lc, nodata)

    indicators = {
        "runoff": runoff,
        "flood": flood,
        "erosion": erosion_idx,
        "recharge": rech_idx,
        "fragmentation": frag_idx,
    }

    # Classification and site score
    thr = load_thresholds(scoring_cfg_path)
    classified = {}
    for name, arr in indicators.items():
        if name in thr:
            classified[name] = classify_indicator(arr, thr[name], nodata=-9999.0)

    site_scores = aggregate_site_score(classified)

    asset_scores: Optional[pd.DataFrame] = None
    if sample_points is not None and not sample_points.empty:
        # Save indicator rasters to temporary in-memory datasets for sampling
        tmp_rasters: Dict[str, rasterio.io.DatasetReader] = {}
        with _load_raster(dem_path) as dem_ds:
            transform = dem_ds.transform
            crs = dem_ds.crs

        # For sampling, we write arrays into MemoryFile datasets
        from rasterio.io import MemoryFile

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
                ds.write(arr, 1)
            tmp_rasters[name] = memfile.open()

        pts_with_vals = sample_rasters_at_points(tmp_rasters, sample_points, x_col="longitude", y_col="latitude", nodata=-9999.0)
        asset_scores = classify_points(pts_with_vals, thr, nodata=-9999.0)

        # Close MemoryFiles
        for ds in tmp_rasters.values():
            ds.close()

    return {
        "indicators": indicators,
        "classified": classified,
        "site_scores": site_scores,
        "asset_scores": asset_scores,
    }
