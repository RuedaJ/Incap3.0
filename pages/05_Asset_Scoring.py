
"""Streamlit Asset Scoring page.

Displays per-asset nature-related risk scores derived from the TNFD
and ES4 pipelines, aligned with EU-oriented best practice for
portfolio screening.
"""

import yaml
import pandas as pd
import streamlit as st

from core.pipelines.tnfd_pipeline import run_tnfd_pipeline
from core.pipelines.es4_pipeline import run_es4_pipeline


def load_sites_config(path: str = "config/datasets.yaml"):
    with open(path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("sites", {})


st.set_page_config(page_title="Asset Scoring", layout="wide")

st.title("Asset-level Nature Risk Scoring")

sites = load_sites_config()
if not sites:
    st.warning("No sites found in config/datasets.yaml. Use the Dataset Builder page to create one.")
    st.stop()

site_name = st.selectbox("Select site", options=sorted(sites.keys()))
site_cfg = sites[site_name]

sample_points = None
sample_points_path = site_cfg.get("sample_points")
if sample_points_path:
    try:
        if sample_points_path.lower().endswith(".csv"):
            sample_points = pd.read_csv(sample_points_path)
        else:
            sample_points = pd.read_json(sample_points_path)
    except Exception:
        sample_points = None

if sample_points is None or sample_points.empty:
    st.info("This site has no sample points configured. Add a 'sample_points' file in the Dataset Builder.")
    st.stop()

with st.spinner("Running TNFD and ES4 pipelines for assets..."):
    tnfd_res = run_tnfd_pipeline(site_cfg, sample_points=sample_points)
    es4_res = run_es4_pipeline(site_cfg, receptors=sample_points)

asset_scores = tnfd_res.get("asset_scores")
receptor_scores = es4_res.get("receptor_scores")

if asset_scores is None:
    st.info("No asset scores available.")
    st.stop()

merged = asset_scores.copy()
if receptor_scores is not None:
    # avoid column clashes; suffix ES4-specific classes
    es4_cols = [c for c in receptor_scores.columns if c not in ("longitude", "latitude")]
    for c in es4_cols:
        merged[f"es4_{c}"] = receptor_scores[c].values

st.subheader(f"Asset scores for site: {site_name}")
st.dataframe(merged)

csv = merged.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download scores as CSV",
    data=csv,
    file_name=f"{site_name}_asset_nature_risk_scores.csv",
    mime="text/csv",
)
