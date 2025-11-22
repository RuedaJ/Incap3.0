
"""Streamlit Nature Risk Dashboard page.

This page wires the TNFD, ES4 and SBTN core pipelines into a simple
visual dashboard. It is intentionally lightweight and focuses on
transparency and traceability of indicators and scores.
"""

import yaml
import numpy as np
import pandas as pd
import streamlit as st

from core.pipelines.tnfd_pipeline import run_tnfd_pipeline
from core.pipelines.es4_pipeline import run_es4_pipeline
from core.pipelines.sbtn_pipeline import run_sbtn_baseline


def load_sites_config(path: str = "config/datasets.yaml"):
    with open(path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("sites", {})


st.set_page_config(page_title="Nature Risk Dashboard", layout="wide")

st.title("Nature Risk Dashboard")

sites = load_sites_config()
if not sites:
    st.warning("No sites found in config/datasets.yaml. Use the Dataset Builder page to create one.")
    st.stop()

site_name = st.selectbox("Select site", options=sorted(sites.keys()))
site_cfg = sites[site_name]

st.markdown(f"**Selected site:** `{site_name}`")

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

col1, col2, col3 = st.columns(3)

with st.spinner("Running TNFD pipeline..."):
    tnfd_res = run_tnfd_pipeline(site_cfg, sample_points=sample_points)

with st.spinner("Running ES4 pipeline..."):
    es4_res = run_es4_pipeline(site_cfg, receptors=sample_points)

with st.spinner("Running SBTN baseline..."):
    sbtn_res = run_sbtn_baseline(site_cfg)

site_scores = tnfd_res["site_scores"]

with col1:
    st.subheader("TNFD Site Score")
    if site_scores:
        st.metric("Composite score", f"{site_scores.get('composite_score', float('nan')):.2f}")
        for k, v in site_scores.items():
            if k == "composite_score":
                continue
            st.write(f"{k}: {v:.2f}")
    else:
        st.info("No TNFD scores available.")

with col2:
    st.subheader("SBTN Baseline")
    nf = sbtn_res.get("natural_fraction", float("nan"))
    st.metric("Natural land fraction", f"{nf:.2f}")
    st.caption("Share of natural / semi-natural land within the AOI.")

with col3:
    st.subheader("ES4 Hazard Overview")
    classified = es4_res.get("classified", {})
    for name, arr in classified.items():
        mask = arr > 0
        if np.any(mask):
            st.write(f"{name} mean hazard class: {arr[mask].mean():.2f}")

st.markdown("---")
st.subheader("Indicator Distributions")

indicators = tnfd_res["indicators"]
ind_name = st.selectbox("Select indicator to inspect", options=list(indicators.keys()))
arr = indicators[ind_name]
flat = arr[(arr != -9999.0)].flatten()
if flat.size > 0:
    st.bar_chart(pd.Series(flat).clip(lower=np.percentile(flat, 2), upper=np.percentile(flat, 98)))
else:
    st.info("No valid data for this indicator.")
