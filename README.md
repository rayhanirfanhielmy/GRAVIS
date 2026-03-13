# GRAVIS: Gravity Reduction And Visualization System 🌍⚡

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

**GRAVIS** is an open-source, GUI-based Python application designed to integrate, automate, and streamline the entire workflow of gravity data reduction, terrain correction, and derivative analysis. 

Developed by **Rayhan Irfan Hielmy** (2026, Indonesia).

---

## ✨ Key Features
- **Integrated Pipeline:** Go from raw Free-Air Anomaly (FAA) to Complete Bouguer Anomaly (CBA) in one seamless GUI.
- **Automated Density Estimation:** Computes the optimum density using Parasnis and Nettleton methods via numerical roots.
- **Fast Terrain Correction:** Utilizes batch sampling via `rasterio` for high-speed elevation extraction and Hammer Chart correction.
- **Interactive Slicing & Spectrum:** Click directly on the anomaly map to slice a 2D profile, automatically connected to 1D FFT Power Spectrum analysis for Cutoff Wavenumber estimation.
- **Advanced Filtering:** Moving Average (MA), Polynomial Regression, First Horizontal Derivative (FHD), and Second Vertical Derivative (SVD).

## 🚀 Installation Guide

Because GRAVIS relies on robust geospatial libraries like `PyGMT` and `Rasterio`, it is highly recommended to use **Conda/Miniconda** to avoid dependency issues.

1. **Clone this repository:**
   ```bash
   git clone https://github.com/rayhanirfanhielmy/GRAVIS.git
   cd GRAVIS
   ```

2. **Create the Conda environment:**
   ```bash
   conda env create -f environment.yml
   ```

3. **Activate the environment:**
   ```bash
   conda activate gravis_env
   ```

## 💻 How to Use
Simply run the Launcher script to open the Graphical User Interface (GUI):

```bash
python App_Launcher.py
```
*Tip: Ensure you have your `FAA.xlsx` and DEM files ready. You can test the application using the files provided in the `sample_data/` folder.*

## 📂 Output Structure
GRAVIS automatically organizes your processed data into three clean directories:
* `output_figures/`: Contains all high-resolution maps and plots (`.png`).
* `output_results/`: Contains all processed data tables (`.xlsx`, `.dat`, `.csv`).
* `output_tif/`: Contains all georeferenced raster grids (`.tif`) ready for QGIS/ArcGIS.

## 📜 Citation
If you use GRAVIS in your research, please cite the following paper:
> **

## ⚖️ License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
