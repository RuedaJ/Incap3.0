import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
import tempfile, os, yaml

from core.io_utils import load_points
from core.raster_ops import sample_raster_at_points, extract_elevation, slope_percent_3x3
from core.land_cover import CLC_NAMES, WATER_BODIES, WETLANDS

# -----------------------------
# Water Screening Logic
# -----------------------------

def classify_recharge(awc_mm, slope_percent, thr):
    hi = thr["recharge"]["high"]; med = thr["recharge"]["medium"]
    if (awc_mm is not None and awc_mm > hi["awc_min"]) and (slope_percent is not None and slope_percent < hi["slope_max"]):
        return "High"
    if (awc_mm is not None and awc_mm >= med["awc_min"]) or (slope_percent is not None and slope_percent <= med["slope_max"]):
        return "Medium"
    return "Low"

def analyze(gdf, dem, awc, clc, slope=None):
    gdf = gdf.to_crs(4326) if gdf.crs else gdf.set_crs(4326)

    # slope
    if slope:
        slope_vals = sample_raster_at_points(gdf, slope)
    else:
        slope_vals = [slope_percent_3x3(dem, geom.x, geom.y) for geom in gdf.geometry]

    # elevation
    elevs = [extract_elevation(dem, geom.x, geom.y) for geom in gdf.geometry]

    # awc + clc
    awc_vals = sample_raster_at_points(gdf, awc)
    clc_vals = sample_raster_at_points(gdf, clc)

    out = gdf.copy()
    out["latitude"] = out.geometry.y
    out["longitude"] = out.geometry.x
    out["elevation_m"] = elevs
    out["slope_percent"] = slope_vals
    out["awc_mm"] = awc_vals
    out["land_cover_code"] = clc_vals
    out["land_cover_name"] = [
        CLC_NAMES.get(int(c), "Unknown") if c is not None and not np.isnan(c) else "Unknown"
        for c in clc_vals
    ]
    out["near_water"] = [
        int(c) in WATER_BODIES if c is not None and not np.isnan(c) else False
        for c in clc_vals
    ]
    out["near_wetland"] = [
        int(c) in WETLANDS if c is not None and not np.isnan(c) else False
        for c in clc_vals
    ]

    # recharge class
    thr = {
        "recharge": {
            "high": {"awc_min": 150, "slope_max": 5},
            "medium": {"awc_min": 50, "slope_max": 15},
        }
    }
    out["recharge_class"] = [
        classify_recharge(a, s, thr) for a, s in zip(awc_vals, slope_vals)
    ]

    return out

# -----------------------------
# PAGE LAYOUT
# -----------------------------

st.title("💧 Water Screening — Lite MVP")

st.write(
    "Upload portfolio sites and screening-grade layers to generate a simple recharge & water proximity memo."
)

# ------------------------------------
# 1) Upload Panel
# ------------------------------------
with st.expander("📥 Upload Inputs", expanded=True):
    sites_up = st.file_uploader("Sites (CSV or GeoJSON)", type=["csv", "geojson"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        dem_up = st.file_uploader("DEM (.tif)", type=["tif", "tiff"])
    with c2:
        awc_up = st.file_uploader("AWC (.tif)", type=["tif", "tiff"])
    with c3:
        clc_up = st.file_uploader("CLC2018 (.tif)", type=["tif", "tiff"])
    with c4:
        slope_up = st.file_uploader(
            "Slope raster (optional, percent)", type=["tif", "tiff"]
        )

# ------------------------------------
# 2) Analysis Panel
# ------------------------------------
with st.expander("🚀 Run Screening", expanded=False):

    if st.button("Run Water Screening", type="primary"):

        if not (sites_up and dem_up and awc_up and clc_up):
            st.error("Please upload sites, DEM, AWC, and CLC.")
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                dem_path = os.path.join(tmpdir, "dem.tif"); open(dem_path, "wb").write(dem_up.getbuffer())
                awc_path = os.path.join(tmpdir, "awc.tif"); open(awc_path, "wb").write(awc_up.getbuffer())
                clc_path = os.path.join(tmpdir, "clc.tif"); open(clc_path, "wb").write(clc_up.getbuffer())

                slope_path = None
                if slope_up:
                    slope_path = os.path.join(tmpdir, "slope_pct.tif")
                    open(slope_path, "wb").write(slope_up.getbuffer())

                gdf = load_points(sites_up)

                with st.spinner("Processing…"):
                    results = analyze(gdf, dem_path, awc_path, clc_path, slope=slope_path)

            st.session_state["ws_results"] = results
            st.success("Water Screening complete.")

# ------------------------------------
# 3) Results Panel
# ------------------------------------
with st.expander("📊 Results & Memo", expanded=False):

    results = st.session_state.get("ws_results")

    if results is None:
        st.info("Run the screening first.")
    else:
        st.subheader("Executive Summary")

        n = len(results)
        pct_low = (results["recharge_class"].eq("Low").mean() * 100.0) if n else 0
        pct_near_water = (results["near_water"].mean() * 100.0) if n else 0
        dominant_lc = (
            results["land_cover_name"].mode().iat[0]
            if n and not results["land_cover_name"].isna().all()
            else "Unknown"
        )

        st.info(
            f"**Sites analyzed:** {n}\n\n"
            f"**Low recharge:** {pct_low:.1f}%\n"
            f"**Near water bodies:** {pct_near_water:.1f}%\n"
            f"**Dominant land cover:** {dominant_lc}"
        )

        st.subheader("Detailed Results")
        st.dataframe(results.drop(columns=["geometry"]))

        st.download_button(
            "⬇️ Download CSV",
            results.drop(columns=["geometry"]).to_csv(index=False).encode("utf-8"),
            "water_screening_results.csv",
        )

        try:
            gjson = gpd.GeoDataFrame(
                results, geometry=results.geometry, crs="EPSG:4326"
            ).to_json().encode("utf-8")
            st.download_button(
                "⬇️ Download GeoJSON",
                gjson,
                "water_screening.geojson",
                "application/geo+json",
            )
        except Exception as e:
            st.warning(f"GeoJSON export failed: {e}")
