import os
import sys
import argparse
import uuid
import tempfile
import math
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import linregress
from scipy.interpolate import griddata
from scipy.signal import convolve2d
from scipy.ndimage import gaussian_filter
from scipy.fft import fft, fftfreq
from scipy import stats

import rasterio
from rasterio.merge import merge
from rasterio.transform import from_origin
import pygmt
import rioxarray
from pyproj import Transformer

# ==================== FOLDER SETUP (3 FOLDERS) ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_FIGS = os.path.join(BASE_DIR, "output_figures")
DIR_RES = os.path.join(BASE_DIR, "output_results")
DIR_TIF = os.path.join(BASE_DIR, "output_tif") # Folder khusus TIF

os.makedirs(DIR_FIGS, exist_ok=True)
os.makedirs(DIR_RES, exist_ok=True)
os.makedirs(DIR_TIF, exist_ok=True)

PLOTS_LIST_FILE = 'temp_plots_list.txt'

def register_plot(fname):
    with open(PLOTS_LIST_FILE, 'a') as f: f.write(fname + '\n')

def save_tif(xi, yi, zi, title):
    clean_title = title.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_").replace(":", "")
    fname = os.path.join(DIR_TIF, f"{clean_title}.tif")
    pixel_width = (xi.max() - xi.min()) / (xi.shape[1] - 1)
    pixel_height = (yi.max() - yi.min()) / (yi.shape[0] - 1)
    transform = from_origin(xi.min(), yi.max(), pixel_width, pixel_height)
    zi_flipped = np.flipud(zi)
    with rasterio.open(
        fname, 'w', driver='GTiff', height=zi.shape[0], width=zi.shape[1],
        count=1, dtype=str(zi.dtype), crs=None, transform=transform
    ) as dst:
        dst.write(np.nan_to_num(zi_flipped).astype(zi.dtype), 1)
    print(f"   -> Saved Grid (.tif): {fname}")

def save_map(xi, yi, zi, title, z_label, cmap='jet', is_svd=False):
    plt.figure(figsize=(10, 8))
    contour = plt.contourf(xi, yi, zi, levels=30, cmap=cmap)
    plt.colorbar(contour, label=z_label)
    #if is_svd: plt.contour(xi, yi, zi, levels=[0], colors='black', linewidths=1.5, linestyles='dashed')
    plt.title(title, fontsize=14, pad=15)
    plt.xlabel('Easting UTM (m)', fontsize=12)
    plt.ylabel('Northing UTM (m)', fontsize=12)
    plt.gca().set_aspect('equal', adjustable='box')
    plt.tight_layout()
    
    fname = os.path.join(DIR_FIGS, f"plot_{uuid.uuid4().hex[:8]}.png")
    plt.savefig(fname, dpi=150, bbox_inches='tight')
    plt.close('all')
    register_plot(fname)
    save_tif(xi, yi, zi, title)

def grid_data(x, y, z, res):
    xi = np.linspace(x.min(), x.max(), res)
    yi = np.linspace(y.min(), y.max(), res)
    xi, yi = np.meshgrid(xi, yi)
    try: zi = griddata((x, y), z, (xi, yi), method='cubic')
    except: zi = griddata((x, y), z, (xi, yi), method='linear')
    if np.isnan(zi).any():
        zi_near = griddata((x, y), z, (xi, yi), method='nearest')
        zi = np.where(np.isnan(zi), zi_near, zi)
    return xi, yi, zi

# ==================== STAGE FUNCTIONS ====================

def run_step1(input_faa, dem_files):
    print("1. Mosaic DEM & Elevation Extraction...")
    # DEM sekarang masuk ke folder DIR_TIF
    mosaic_out = os.path.join(DIR_TIF, 'DEMNAS_MOSAIC.tif')
    dem_utm_out = os.path.join(DIR_TIF, 'DEM_UTM.tif')
    
    src_files = [rasterio.open(fp) for fp in dem_files]
    try:
        mosaic, out_trans = merge(src_files)
        out_meta = src_files[0].meta.copy()
        out_meta.update({"driver": "GTiff", "height": mosaic.shape[1], "width": mosaic.shape[2], "transform": out_trans})
        with rasterio.open(mosaic_out, "w", **out_meta) as dest: dest.write(mosaic)
    finally:
        for src in src_files: src.close()

    data = pd.read_excel(input_faa)
    track_result = pygmt.grdtrack(points=data[["Longitude", "Latitude"]], grid=mosaic_out, newcolname="Elevation")
    data["Elevation"] = track_result["Elevation"]

    center_lon, center_lat = data['Longitude'].mean(), data['Latitude'].mean()
    utm_zone = int((center_lon + 180) / 6) + 1
    hemisphere = 'N' if center_lat >= 0 else 'S'
    epsg_code = 32600 + utm_zone if center_lat >= 0 else 32700 + utm_zone
    print(f"   -> Detected UTM Zone: {utm_zone}{hemisphere} (EPSG: {epsg_code})")

    dem = rioxarray.open_rasterio(mosaic_out, masked=True)

    dem = rioxarray.open_rasterio(mosaic_out, masked=True)
    if dem.rio.crs is None: dem.rio.write_crs("EPSG:4326", inplace=True)
    dem_utm = dem.rio.reproject(f"EPSG:{epsg_code}")
    dem_utm.rio.to_raster(dem_utm_out)
    dem.close(); dem_utm.close()

    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg_code}", always_xy=True)
    utmx, utmy = transformer.transform(data['Longitude'].values, data['Latitude'].values)
    data['UTMX'], data['UTMY'] = utmx, utmy
    
    final_excel = os.path.join(DIR_RES, "FAA_UTM.xlsx")
    data.to_excel(final_excel, index=False)

    print("2. Visualizing Map (PyGMT)...")
    region = [data["Longitude"].min() - 0.01, data["Longitude"].max() + 0.01, data["Latitude"].min() - 0.01, data["Latitude"].max() + 0.01]
    fig = pygmt.Figure()
    pygmt.makecpt(cmap="geo", series="-500/3000/500", continuous=True)
    fig.basemap(region=region, projection="M5i", frame=["af", "+tFAA and Topography"])
    fig.grdimage(grid=mosaic_out, cmap=True, shading=True)
    fig.coast(shorelines=True, resolution="i")
    with tempfile.NamedTemporaryFile(suffix=".cpt", delete=False) as tmp_cpt: cpt_file = tmp_cpt.name
    pygmt.makecpt(cmap="viridis", series=[data["FAA"].min(), data["FAA"].max()], output=cpt_file)
    fig.plot(x=data["Longitude"], y=data["Latitude"], style="c0.25c", fill=data["FAA"], cmap=cpt_file, pen="black")
    fig.colorbar(position="JMR+o0.5c/0c+w5c/0.3c", cmap=cpt_file, frame='af+l"FAA (mGal)"')
    
    fname = os.path.join(DIR_FIGS, f"plot_pygmt_{uuid.uuid4().hex[:8]}.png")
    fig.savefig(fname)
    register_plot(fname)
    os.remove(cpt_file)

def run_parasnis(input_faa_utm):
    data = pd.read_excel(input_faa_utm)
    x_val = 0.04192 * data['Elevation']
    slope, intercept, _, _, _ = linregress(x_val, data['FAA'])
    with open('temp_val.txt', 'w') as f: f.write(str(slope))
    
    plt.figure(figsize=(8, 6))
    plt.scatter(x_val, data['FAA'], color='blue', alpha=0.6, edgecolors='k')
    plt.plot(x_val, slope * x_val + intercept, color='red', linewidth=2, label=f'$\\rho$ = {slope:.2f}')
    plt.title('Parasnis Density Estimation')
    plt.xlabel('0.04192 x Elevation'); plt.ylabel('FAA (mGal)')
    plt.legend()
    fname = os.path.join(DIR_FIGS, f"plot_{uuid.uuid4().hex[:8]}.png")
    plt.savefig(fname); plt.close()
    register_plot(fname)

def run_nettleton(input_faa_utm):
    data = pd.read_excel(input_faa_utm)
    rho_vals = np.arange(1.0, 3.2, 0.1)
    k_vals = [np.corrcoef(data['FAA'] - (0.04192 * r * data['Elevation']), data['Elevation'])[0, 1] for r in rho_vals]
    coeffs = np.polyfit(rho_vals, k_vals, 3)
    roots = np.roots(np.poly1d(coeffs))
    real_roots = roots[np.isreal(roots)].real
    valid = [r for r in real_roots if 1.0 <= r <= 3.0]
    opt_rho = min(valid, key=lambda x: abs(x - 2.67)) if valid else 2.67
    with open('temp_val.txt', 'w') as f: f.write(str(opt_rho))
    
    plt.figure(figsize=(8, 6))
    plt.plot(rho_vals, k_vals, 'bo')
    xp = np.linspace(1.0, 3.1, 100)
    plt.plot(xp, np.poly1d(coeffs)(xp), 'r--')
    plt.axhline(0, color='k'); plt.plot(opt_rho, 0, 'g*', markersize=12, label=f'$\\rho$ = {opt_rho:.2f}')
    plt.title('Nettleton Method'); plt.xlabel('Density'); plt.ylabel('Correlation (K)'); plt.legend()
    fname = os.path.join(DIR_FIGS, f"plot_{uuid.uuid4().hex[:8]}.png")
    plt.savefig(fname); plt.close()
    register_plot(fname)

def run_sba(input_faa_utm, rho, res):
    print(f"Calculating SBA using Density: {rho}")
    data = pd.read_excel(input_faa_utm)
    data['SBA'] = data['FAA'] - (0.04192 * rho * data['Elevation'])
    data.to_excel(os.path.join(DIR_RES, "SBA.xlsx"), index=False)
    xi, yi, zi = grid_data(data['UTMX'], data['UTMY'], data['SBA'], res)
    save_map(xi, yi, zi, f'Simple Bouguer Anomaly (Rho={rho})', 'mGal')

def run_cba(input_sba, rho, res):
    print(f"Calculating CBA using Density: {rho}")
    
    # Membaca file DEM dari folder TIF
    dem_file = os.path.join(DIR_TIF, "DEM_UTM.tif")
    if not os.path.exists(dem_file): raise FileNotFoundError("DEM_UTM.tif not found in output_tif folder.")
    
    df = pd.read_excel(input_sba)
    headers = list(df.columns) + ["Center_Elevation"]
    
    config = {
        16.6: 6,      # Zona B
        53.3: 6,      # Zona C
        170.1: 8,     # Zona D
        390.1: 12,    # Zona E
        894.9: 16,    # Zona F
        1529.6: 24,   # Zona G
        2614.4: 36,   # Zona H
        4468.9: 48,   # Zona I
        6565.4: 60,   # Zona J
        9901.8: 72   # Zona K
        #14742.6: 90,  # Zona L use if you need
        #21943.4: 120  # Zona M
    }
    
    dx_list, dy_list = [], []
    for rad, num in config.items():
        for ang in np.linspace(0, 360, num, endpoint=False):
            dx_list.append(rad * np.cos(np.radians(ang)))
            dy_list.append(rad * np.sin(np.radians(ang)))
            headers.append(f"{rad}m_{int(ang)}deg")
    
    coords = []
    for _, row in df.iterrows():
        coords.append((row["UTMX"], row["UTMY"]))
        for dx, dy in zip(dx_list, dy_list): 
            coords.append((row["UTMX"] + dx, row["UTMY"] + dy))
        
    elevs = []
    print("Extracting terrain heights... ")
    with rasterio.open(dem_file) as dem:
        for val in dem.sample(coords): 
            elevs.append(round(float(val[0]), 2))
    
    elevs_reshaped = np.array(elevs).reshape(len(df), 1 + len(dx_list))
    df_elevs = pd.DataFrame(elevs_reshaped, columns=headers[len(df.columns):])
    df_final = pd.concat([df, df_elevs], axis=1)
    
    G_RHO = 2 * np.pi * 6.6743e-11 * (rho * 1000) / 100000
    tc_total = np.zeros(len(df_final))
    r_in = 0.0
    
    print("Calculating Terrain Correction (Hammer Method)...")
    for r_out, n in config.items():
        cols = [c for c in df_final.columns if c.startswith(f"{r_out}m_")]
        
        tc_zone = np.zeros(len(df_final))
        
        for col in cols:
            z_diff = np.abs(df_final[col] - df_final['Center_Elevation'])
            
            tc_sector = (G_RHO / n) * (r_out - r_in + np.sqrt(r_in**2 + z_diff**2) - np.sqrt(r_out**2 + z_diff**2)) * 1e10
            tc_zone += tc_sector
            
        tc_total += tc_zone
        r_in = r_out
        print(f"   -> Zone {r_out}m processed.")
        
    df_final['Total_TC'] = tc_total
    df_final['CBA'] = df_final['SBA'] + df_final['Total_TC']
    
    cba_cols = ['Longitude', 'Latitude', 'UTMX', 'UTMY', 'Center_Elevation', 'FAA', 'SBA', 'Total_TC', 'CBA']
    df_final[cba_cols].to_excel(os.path.join(DIR_RES, 'CBA.xlsx'), index=False)
    
    print("Gridding and saving CBA map...")
    xi, yi, zi = grid_data(df_final['UTMX'], df_final['UTMY'], df_final['CBA'], res)
    save_map(xi, yi, zi, 'Complete Bouguer Anomaly (CBA)', 'mGal')
    print("CBA processing complete!")
    
def run_filters(input_file, res, poly_order, window):
    print(f"Processing Filters on: {input_file}")
    df = pd.read_excel(input_file)
    target = 'CBA' if 'CBA' in df.columns else 'SBA'
    
    xi, yi, zi = grid_data(df['UTMX'], df['UTMY'], df[target], res)
    
    xn, yn = (df['UTMX'] - df['UTMX'].mean()) / df['UTMX'].std(), (df['UTMY'] - df['UTMY'].mean()) / df['UTMY'].std()
    X_mat = np.column_stack([(xn**(d-i))*(yn**i) for d in range(poly_order+1) for i in range(d+1)])
    coeffs, _, _, _ = np.linalg.lstsq(X_mat, df[target], rcond=None)
    poly_reg = X_mat @ coeffs
    poly_res = df[target] - poly_reg
    _, _, z_preg = grid_data(df['UTMX'], df['UTMY'], poly_reg, res)
    _, _, z_pres = grid_data(df['UTMX'], df['UTMY'], poly_res, res)
    
    ker = np.ones((window, window))
    val_mask = ~np.isnan(zi)
    count = convolve2d(val_mask, ker, mode='same', boundary='fill', fillvalue=0)
    sum_zi = convolve2d(np.nan_to_num(zi), ker, mode='same', boundary='fill', fillvalue=0)
    ma_reg = np.divide(sum_zi, count, out=np.zeros_like(sum_zi), where=(count!=0))
    ma_res = zi - ma_reg
    
    z_smooth = gaussian_filter(zi, sigma=3)
    dx, dy = xi[0,1]-xi[0,0], yi[1,0]-yi[0,0]
    dzdx, dzdy = np.gradient(z_smooth, dx, axis=1), np.gradient(z_smooth, dy, axis=0)
    fhd = np.sqrt(dzdx**2 + dzdy**2)
    svd = -(np.gradient(dzdx, dx, axis=1) + np.gradient(dzdy, dy, axis=0))
    
    pd.DataFrame({
        'UTMX': xi.flatten(), 'UTMY': yi.flatten(), f'{target}': zi.flatten(),
        'Poly_Reg': z_preg.flatten(), 'Poly_Res': z_pres.flatten(),
        'MA_Reg': ma_reg.flatten(), 'MA_Res': ma_res.flatten(), 'FHD': fhd.flatten(), 'SVD': svd.flatten()
    }).to_excel(os.path.join(DIR_RES, 'Filtered_and_Derivatives.xlsx'), index=False)
    
    save_map(xi, yi, z_preg, f'Polynomial Regional (O: {poly_order})', 'mGal')
    save_map(xi, yi, z_pres, 'Polynomial Residual', 'mGal', 'Spectral_r')
    save_map(xi, yi, ma_reg, f'MA Regional (W: {window})', 'mGal')
    save_map(xi, yi, ma_res, 'MA Residual', 'mGal', 'Spectral_r')
    save_map(xi, yi, fhd, 'First Horizontal Derivative (FHD)', 'mGal/m', 'rainbow')
    save_map(xi, yi, svd, 'Second Vertical Derivative (SVD)', 'mGal/m²', 'rainbow', True)

def run_interactive(input_file, target_map, res):
    print(f"Preparing Map for Slicing: {target_map}")
    df = pd.read_excel(input_file)
    
    if target_map not in df.columns:
        print(f"\n[ERROR] Map '{target_map}' not found in the selected file!")
        print(f"Available columns: {list(df.columns)}")
        sys.exit(1)
        
    xi, yi, zi = grid_data(df['UTMX'], df['UTMY'], df[target_map], res)
    
    plt.figure(figsize=(10, 8))
    cmap = 'rainbow' if 'FHD' in target_map or 'SVD' in target_map else 'jet'
    plt.contourf(xi, yi, zi, levels=50, cmap=cmap)
    plt.colorbar(label=target_map)
    plt.title(f'Interactive Slice: {target_map}\nClick 2 points, then press ENTER')
    
    print("\n[ACTION REQUIRED] >> Please click 2 points on the Map Window!")
    pts = plt.ginput(2, timeout=0)
    plt.close()
    
    if len(pts) == 2:
        print("Processing slice data...")
        x_l = np.linspace(pts[0][0], pts[1][0], max(res, 500))
        y_l = np.linspace(pts[0][1], pts[1][1], max(res, 500))
        z_line = griddata((xi.flatten(), yi.flatten()), zi.flatten(), (x_l, y_l), method='cubic')
        dist = np.sqrt((x_l - pts[0][0])**2 + (y_l - pts[0][1])**2)
        
        out = pd.DataFrame({'Dist_m': dist, 'UTMX': x_l, 'UTMY': y_l, f'{target_map}_val': z_line}).dropna()
        out_file = os.path.join(DIR_RES, f'slice_{target_map}.dat')
        out.to_csv(out_file, index=False)
        print(f"✅ Data saved to: {out_file}")
        
        with open('temp_dat_file.txt', 'w') as f: f.write(out_file)

        # Plot Map with Line
        plt.figure(figsize=(10, 8))
        plt.contourf(xi, yi, zi, levels=50, cmap=cmap)
        plt.colorbar(label=target_map)
        plt.plot(x_l, y_l, 'w--', lw=2.5)
        plt.scatter([pts[0][0], pts[1][0]], [pts[0][1], pts[1][1]], c='magenta', s=100, marker='*')
        plt.title(f'{target_map} Map with Profile Line')
        plt.gca().set_aspect('equal', adjustable='box')
        plt.tight_layout()
        fname1 = os.path.join(DIR_FIGS, f"plot_{uuid.uuid4().hex[:8]}.png")
        plt.savefig(fname1, dpi=150, bbox_inches='tight'); plt.close()
        register_plot(fname1)

        # Plot Curve
        plt.figure(figsize=(10, 4))
        plt.plot(out['Dist_m'], out[f'{target_map}_val'], '-k', lw=2)
        plt.fill_between(out['Dist_m'], out[f'{target_map}_val'], out[f'{target_map}_val'].min(), color='skyblue', alpha=0.4)
        plt.xlabel('Distance (m)')
        plt.ylabel(f'{target_map}')
        plt.title(f'Profile Plot: {target_map}')
        plt.grid(True, ls='--', alpha=0.7)
        plt.xlim(out['Dist_m'].min(), out['Dist_m'].max())
        plt.tight_layout()
        fname2 = os.path.join(DIR_FIGS, f"plot_{uuid.uuid4().hex[:8]}.png")
        plt.savefig(fname2, dpi=150, bbox_inches='tight'); plt.close()
        register_plot(fname2)
    else:
        print("Slicing cancelled.")

def run_spectrum(input_dat, reg_cut):
    print(f"Loading slice profile data from {input_dat}...")
    df_slice = pd.read_csv(input_dat)
    
    g_col = [col for col in df_slice.columns if col not in ['Distance', 'Dist_m', 'UTMX', 'UTMY']][0]
    dist_col = 'Dist_m' if 'Dist_m' in df_slice.columns else 'Distance'
    
    dist = df_slice[dist_col].values
    g_vals = df_slice[g_col].values
    dx = dist[1] - dist[0]
    
    fft_mag = np.abs(fft(g_vals))
    k_all = 2 * np.pi * fftfreq(len(g_vals), d=dx)
    half = len(g_vals) // 2
    k = k_all[1:half]
    lnA = np.log(fft_mag[1:half])
    
    df_fft = pd.DataFrame({'Wavenumber (k)': k, 'Ln A': lnA})
    fft_csv = os.path.join(DIR_RES, 'fft_result.csv')
    df_fft.to_csv(fft_csv, index=False)
    
    print("\n================ FFT RESULTS ================")
    print(df_fft.head(25).to_string())
    print(f"...(Full data saved to {fft_csv})")
    print("=============================================\n")
    
    if reg_cut <= 0:
        print("[INFO] Please review the table above, set 'Reg Cut Index' in GUI, and Run Spectrum again.")
        plt.figure(figsize=(8, 6))
        plt.plot(k, lnA, 'b-')
        plt.title(f'Log Magnitude FFT (Raw) - {g_col}')
        plt.xlabel('Wavenumber (k)')
        plt.ylabel('Ln A')
        plt.grid()
        fname = os.path.join(DIR_FIGS, f"plot_{uuid.uuid4().hex[:8]}.png")
        plt.savefig(fname, dpi=150, bbox_inches='tight'); plt.close()
        register_plot(fname)
        return

    print(f"Using Manual Reg Cut Index: {reg_cut}")
    
    k_reg_cut = k[0:reg_cut]
    lnA_reg_cut = lnA[0:reg_cut] 

    k_res_cut = k[reg_cut:len(k)]
    lnA_res_cut = lnA[reg_cut:len(k)] 

    a_reg, b_reg, _, _, _ = stats.linregress(k_reg_cut, lnA_reg_cut)
    a_res, b_res, _, _, _ = stats.linregress(k_res_cut, lnA_res_cut)

    lnA_reg_fit = a_reg * k_reg_cut + b_reg
    lnA_res_fit = a_res * k_res_cut + b_res
    
    try:
        k_int = (b_res - b_reg) / (a_reg - a_res)
        win_exact = (2 * np.pi / k_int) / dx
        win = math.floor(win_exact) if math.floor(win_exact)%2 != 0 else math.floor(win_exact)-1
        if abs(win_exact - (win+2)) < abs(win_exact - win): win += 2
        with open('temp_val.txt', 'w') as f: f.write(str(win))
        print(f"✅ Suggested MA Window Size: {win}")
    except Exception as e:
        print(f"Warning: Could not calculate window intersection ({e})")

    plt.figure(figsize=(8, 6))
    plt.scatter(k_reg_cut, lnA_reg_cut, color='blue', label='Regional Data')
    plt.plot(k_reg_cut, lnA_reg_fit, '--', color='blue', label='Regional Regression')
    plt.scatter(k_res_cut, lnA_res_cut, color='red', label='Residual Data')
    plt.plot(k_res_cut, lnA_res_fit, '--', color='red', label='Residual Regression')

    plt.legend()
    plt.xlabel('Wavenumber (k)')
    plt.ylabel('ln A')
    plt.title('Log Magnitude FFT with Linear Regression')
    plt.grid()
    plt.text(0.5, 0.5, f'Regional: y = {a_reg:.3f}x + {b_reg:.3f}', transform=plt.gca().transAxes, color='blue', fontsize=12)
    plt.text(0.5, 0.45, f'Residual: y = {a_res:.3f}x + {b_res:.3f}', transform=plt.gca().transAxes, color='red', fontsize=12)
    
    fname = os.path.join(DIR_FIGS, f"plot_{uuid.uuid4().hex[:8]}.png")
    plt.savefig(fname, dpi=150, bbox_inches='tight'); plt.close()
    register_plot(fname)

if __name__ == '__main__':
    start_time = time.time()
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', required=True)
    parser.add_argument('--input1')
    parser.add_argument('--dems', nargs='+')
    parser.add_argument('--rho', type=float)
    parser.add_argument('--res', type=int)
    parser.add_argument('--poly', type=int)
    parser.add_argument('--window', type=int)
    parser.add_argument('--target_map')
    parser.add_argument('--reg_cut', type=int, default=0)
    args = parser.parse_args()

    if args.task == 'step1': run_step1(args.input1, args.dems)
    elif args.task == 'parasnis': run_parasnis(args.input1)
    elif args.task == 'nettleton': run_nettleton(args.input1)
    elif args.task == 'sba': run_sba(args.input1, args.rho, args.res)
    elif args.task == 'cba': run_cba(args.input1, args.rho, args.res)
    elif args.task == 'filter': run_filters(args.input1, args.res, args.poly, args.window)
    elif args.task == 'interactive': run_interactive(args.input1, args.target_map, args.res)
    elif args.task == 'spectrum': run_spectrum(args.input1, args.reg_cut)
    
    print(f"\n⏱ Execution Time: {time.time() - start_time:.2f} seconds")
