
import os
import pathlib
import zipfile
import yaml
import streamlit as st

st.warning("K-factor-enabled Dataset Builder loaded")


BASE_DIR = pathlib.Path(__file__).resolve().parents[1]
DATA_ROOT = BASE_DIR / "data"
CONFIG_PATH = BASE_DIR / "config" / "datasets.yaml"

st.title("Dataset Builder")

st.write(
    "Create or update named datasets using local raster/vector files. "
    "Files are stored under `data/<dataset_name>` and registered in "
    "`config/datasets.yaml` for reuse in all analysis pages."
)

dataset_name = st.text_input("Dataset Name (e.g. girona_olot)", value="")

if not dataset_name:
    st.info("Pick a dataset name to enable uploads.")
    st.stop()

dataset_dir = DATA_ROOT / dataset_name
dataset_dir.mkdir(parents=True, exist_ok=True)

st.subheader("Core spatial layers")

aoi = st.file_uploader("AOI polygon (GeoJSON/GeoPackage)", type=["geojson", "gpkg", "json"])
dem = st.file_uploader("DEM (GeoTIFF)", type=["tif", "tiff"])
awc = st.file_uploader("AWC / Infiltration Raster (GeoTIFF)", type=["tif", "tiff"])
clc = st.file_uploader("Land Cover / CLC Raster (GeoTIFF)", type=["tif", "tiff"])
slope = st.file_uploader("Slope Raster (optional)", type=["tif", "tiff"])
sample_pts = st.file_uploader("Sample Points (optional CSV/GeoJSON)", type=["csv", "geojson", "json"])

st.subheader("Soil erodibility (K-factor) rasters")

k_zip = st.file_uploader(
    "ZIP bundle with K-factor rasters (optional)",
    type=["zip"],
    help="If provided, the ZIP should contain files named like "
         "`K_factor_with_Ksat.tif`, `K_factor_soiltexture_Wischmeier.tif`, "
         "`K_GloSEM_factor.tif`, and their corresponding *_error.tif files."
)

st.caption(
    "Alternatively, you can upload each K-factor raster individually if you "
    "do not have a consolidated ZIP."
)

k_ksat = st.file_uploader("K_factor_with_Ksat.tif (optional)", type=["tif", "tiff"])
k_wisch = st.file_uploader("K_factor_soiltexture_Wischmeier.tif (optional)", type=["tif", "tiff"])
k_glosem = st.file_uploader("K_GloSEM_factor.tif (optional)", type=["tif", "tiff"])
k_ksat_err = st.file_uploader("K_factor_with_Ksat_error.tif (optional)", type=["tif", "tiff"])
k_wisch_err = st.file_uploader("K_factor_soiltexture_Wischmeier_error.tif (optional)", type=["tif", "tiff"])


def _save_uploaded(uploaded_file, dest_path: pathlib.Path):
    if uploaded_file is None:
        return None
    with open(dest_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return dest_path


def _extract_k_from_zip(zip_file, dest_dir: pathlib.Path):
    """Extract known K-factor rasters from an uploaded ZIP file.

    Returns a mapping of logical keys to relative paths that can be
    stored in datasets.yaml.
    """

    logical_paths = {}
    with zipfile.ZipFile(zip_file) as z:
        for member in z.namelist():
            lower = member.lower()
            if not lower.endswith(".tif"):
                continue
            if "k_factor_with_ksat_error" in lower:
                key = "k_ksat_error"
            elif "k_factor_with_ksat" in lower:
                key = "k_ksat"
            elif "k_factor_soiltexture_wischmeier_error" in lower:
                key = "k_wischmeier_error"
            elif "k_factor_soiltexture_wischmeier" in lower:
                key = "k_wischmeier"
            elif "k_glosem_factor" in lower:
                key = "k_glosem"
            else:
                continue

            dest_path = dest_dir / os.path.basename(member)
            with z.open(member) as src, open(dest_path, "wb") as dst:
                dst.write(src.read())
            logical_paths[key] = dest_path
    return logical_paths


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

    # Handle K-factor rasters
    k_paths = {}

    if k_zip is not None:
        # Use an in-memory buffer for the uploaded ZIP
        temp_zip_path = dataset_dir / "_tmp_kbundle.zip"
        _save_uploaded(k_zip, temp_zip_path)
        with open(temp_zip_path, "rb") as fh:
            k_paths = _extract_k_from_zip(fh, dataset_dir)
        temp_zip_path.unlink(missing_ok=True)

    # Individual uploads override anything from ZIP
    if k_ksat is not None:
        p = _save_uploaded(k_ksat, dataset_dir / "K_factor_with_Ksat.tif")
        k_paths["k_ksat"] = p
    if k_wisch is not None:
        p = _save_uploaded(k_wisch, dataset_dir / "K_factor_soiltexture_Wischmeier.tif")
        k_paths["k_wischmeier"] = p
    if k_glosem is not None:
        p = _save_uploaded(k_glosem, dataset_dir / "K_GloSEM_factor.tif")
        k_paths["k_glosem"] = p
    if k_ksat_err is not None:
        p = _save_uploaded(k_ksat_err, dataset_dir / "K_factor_with_Ksat_error.tif")
        k_paths["k_ksat_error"] = p
    if k_wisch_err is not None:
        p = _save_uploaded(k_wisch_err, dataset_dir / "K_factor_soiltexture_Wischmeier_error.tif")
        k_paths["k_wischmeier_error"] = p

    if k_paths:
        # Convert to relative paths for YAML
        paths.update({key: str(path.relative_to(BASE_DIR)) for key, path in k_paths.items()})

    # Merge into datasets.yaml
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}

    sites = cfg.get("sites", {})
    if dataset_name in sites:
        sites[dataset_name].update(paths)
    else:
        sites[dataset_name] = paths
    cfg["sites"] = sites

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

    st.success(f"Dataset '{dataset_name}' saved to config/datasets.yaml.")
    st.json(paths)
