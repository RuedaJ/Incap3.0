import streamlit as st
import pathlib
import sys
import os

# ----------------------------------------------------------
# Global Streamlit Configuration
# ----------------------------------------------------------
st.set_page_config(
    page_title="INCAP 3.0 — Nature & Water Screening Suite",
    layout="wide"
)

# ----------------------------------------------------------
# Robust Import Path Setup
# Ensures `core/` and shared modules load correctly
# ----------------------------------------------------------
APP_DIR = pathlib.Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("GDAL_CACHEMAX", "128")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.tiff,.vrt,.gpkg")

# ----------------------------------------------------------
# Main Landing Page Content
# ----------------------------------------------------------
st.title("🌍 INCAP 3.0 — Nature & Water Screening Suite")
st.markdown(
    """
Welcome to **INCAP 3.0**, an integrated environment for:
- ⚡ **Water Screening** (Legacy MVP)
- 🌱 **TNFD-ready nature risk screening**
- 🌿 **ES4 hazard assessment**
- 💧 **SBTN freshwater / land baseline**
- 🧭 **Dataset building & diagnostics**
- 🗺️ **Spatial portfolio analysis**

Use the **left sidebar** to navigate through the tools.

---

## 📚 Pages Available in This Suite

### 🔎 Diagnostics
- **01_Mini_Diagnostics** — Raster & vector checks  
- **02_DEM_Probe** — Inspect DEM values interactively  

### 🛠️ Build & Prepare Site Datasets
- **03_Dataset_Builder** — Upload AOI, DEM, CLC, AWC, Slope, K-factors (ZIP or TIFs)

### 🌿 Nature Screening Stack
- **04_Nature_Risk_Dashboard** — TNFD/ES4/SBTN compatible site-level analysis  
- **05_Asset_Scoring** — Per-asset TNFD & ES4 scoring  

### 💧 Water Screening (Legacy MVP)
- **00_Water_Screening** — Basic recharge classification and memo

---

If a page does not appear:
- Ensure it is stored in the `pages/` directory  
- The filename starts with a number prefix (e.g., `03_...`)  
    """
)

st.info("Load a page from the sidebar to begin.")
