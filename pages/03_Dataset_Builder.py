import os
import pathlib
import yaml
import streamlit as st

BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
DATA_ROOT = BASE_DIR / "data"
CONFIG_PATH = BASE_DIR / "config" / "datasets.yaml"

st.title("Dataset Builder")
st.write(
    "Create or update named datasets using local raster/vector files. "
    "Datasets are saved in `config/datasets.yaml` and files are stored under `data/<dataset_name>`."
)

dataset_name = st.text_input("Dataset Name (e.g. girona_olot)", value="")

if not dataset_name:
    st.info("Pick a dataset name to enable uploads.")
    st.stop()

dataset_dir = DATA_ROOT / dataset_name
dataset_dir.mkdir(exist_ok=True)

st.subheader("Upload spatial layers")

aoi = st.file_uploader("AOI polygon (GeoJSON/GeoPackage)", type=["geojson", "gpkg", "json"])
dem = st.file_uploader("DEM (GeoTIFF)", type=["tif", "tiff"])
awc = st.file_uploader("AWC / Infiltration Raster (GeoTIFF)", type=["tif", "tiff"])
clc = st.file_uploader("Land Cover / CLC Raster (GeoTIFF)", type=["tif", "tiff"])
slope = st.file_uploader("Slope Raster (optional)", type=["tif", "tiff"])
sample_pts = st.file_uploader("Sample Points (optional CSV/GeoJSON)", type=["csv", "geojson", "json"])

def _save_uploaded(uploaded_file, dest_path: pathlib.Path):
    if uploaded_file is None:
        return None
    with open(dest_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest_path

if st.button("Save Dataset", type="primary"):
    paths = {}

    if aoi:
        p = _save_uploaded(aoi, dataset_dir / "aoi.geojson")
        paths["aoi"] = str(p.relative_to(BASE_DIR))
    if dem:
        p = _save_uploaded(dem, dataset_dir / "dem.tif")
        paths["dem"] = str(p.relative_to(BASE_DIR))
    if awc:
        p = _save_uploaded(awc, dataset_dir / "awc.tif")
        paths["awc"] = str(p.relative_to(BASE_DIR))
    if clc:
        p = _save_uploaded(clc, dataset_dir / "clc.tif")
        paths["clc"] = str(p.relative_to(BASE_DIR))
    if slope:
        p = _save_uploaded(slope, dataset_dir / "slope.tif")
        paths["slope"] = str(p.relative_to(BASE_DIR))
    if sample_pts:
        suffix = pathlib.Path(sample_pts.name).suffix or ".csv"
        p = _save_uploaded(sample_pts, dataset_dir / f"sample_points{suffix}")
        paths["sample_points"] = str(p.relative_to(BASE_DIR))

    # Merge into datasets.yaml
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            try:
                cfg = yaml.safe_load(f) or {}
            except Exception:
                cfg = {}
    else:
        cfg = {}

    sites = cfg.get("sites", {})
    if dataset_name in sites:
        sites[dataset_name].update(paths)
    else:
        sites[dataset_name] = paths
    cfg["sites"] = sites

    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    st.success(f"Dataset '{dataset_name}' saved to config/datasets.yaml.")
    st.json(paths)
