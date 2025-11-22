
"""ESG / TNFD / ES4 / SBTN risk scoring utilities.

This module translates continuous indicators (runoff, erosion, recharge,
fragmentation, etc.) into categorical risk classes using thresholds
defined in YAML configuration files under ``config/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol
import yaml


@dataclass
class ThresholdDef:
    bins: List[float]
    labels: List[str]


def load_thresholds(path: str) -> Dict[str, ThresholdDef]:
    """Load threshold definitions from a YAML file."""

    with open(path, "r") as f:
        raw = yaml.safe_load(f) or {}
    out: Dict[str, ThresholdDef] = {}
    for name, cfg in raw.get("indicators", {}).items():
        out[name] = ThresholdDef(bins=list(cfg.get("bins", [])), labels=list(cfg.get("labels", [])))
    return out


def classify_indicator(arr: np.ndarray, thr: ThresholdDef, nodata: float) -> np.ndarray:
    """Classify a continuous indicator array into integer classes.

    Returns an array with values 1..N (for each label) and 0 for nodata.
    """

    out = np.zeros_like(arr, dtype="int16")
    mask = arr != nodata
    if not np.any(mask):
        return out
    vals = arr[mask].astype("float32")
    idx = np.digitize(vals, thr.bins, right=False)
    out[mask] = idx + 1  # start classes at 1
    return out


def aggregate_site_score(classified_layers: Dict[str, np.ndarray], weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """Aggregate classified indicator rasters into simple site scores.

    Returns mean class per indicator and a weighted composite score.
    """

    scores: Dict[str, float] = {}
    total_weight = 0.0
    composite = 0.0
    for name, arr in classified_layers.items():
        mask = arr > 0
        if not np.any(mask):
            continue
        mean_class = float(arr[mask].mean())
        scores[f"{name}_mean_class"] = mean_class
        w = 1.0
        if weights and name in weights:
            w = float(weights[name])
        composite += w * mean_class
        total_weight += w
    scores["composite_score"] = composite / total_weight if total_weight > 0 else float("nan")
    return scores


def sample_rasters_at_points(
    rasters: Dict[str, rasterio.io.DatasetReader],
    points: pd.DataFrame,
    x_col: str,
    y_col: str,
    nodata: float,
) -> pd.DataFrame:
    """Sample multiple rasters at point locations (lon/lat or projected).

    Parameters
    ----------
    rasters:
        Mapping of indicator name -> open rasterio dataset.
    points:
        DataFrame with coordinate columns.
    x_col, y_col:
        Names of columns holding x/y or lon/lat.
    nodata:
        Nodata value to use if sampling fails.
    """

    out = points.copy()
    for name, ds in rasters.items():
        vals = []
        for _, row in points.iterrows():
            try:
                r, c = rowcol(ds.transform, row[x_col], row[y_col])
                if 0 <= r < ds.height and 0 <= c < ds.width:
                    v = ds.read(1)[r, c]
                else:
                    v = nodata
            except Exception:
                v = nodata
            vals.append(v)
        out[name] = vals
    return out


def classify_points(df: pd.DataFrame, thresholds: Dict[str, ThresholdDef], nodata: float) -> pd.DataFrame:
    """Classify per-point indicator values into risk classes."""

    out = df.copy()
    for name, thr in thresholds.items():
        if name not in out.columns:
            continue
        vals = out[name].values.astype("float32")
        classes = np.zeros_like(vals, dtype="int16")
        mask = vals != nodata
        if np.any(mask):
            idx = np.digitize(vals[mask], thr.bins, right=False)
            classes[mask] = idx + 1
        out[f"{name}_class"] = classes
    return out
