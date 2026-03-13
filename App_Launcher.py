import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import sys
from PIL import Image, ImageTk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")
DIR_RES = os.path.join(BASE_DIR, "output_results")

class GravityGUI:
    def __init__(self, root):
        self.root = root
        # NAMA APLIKASI DI WINDOW TITLE
        self.root.title("GRAVIS: Gravity Reduction & Visualization System | By Rayhan Irfan Hielmy (2026)")
        self.root.geometry("1300x850") 
        
        self.v_grid = tk.StringVar(value="250") 
        
        self.v_step1_faa = tk.StringVar(value="")
        self.dem_files = []
        
        self.v_step2_faa_utm = tk.StringVar(value="")
        self.v_rho = tk.StringVar(value="2.67")
        
        self.v_step3_faa_utm = tk.StringVar(value="")
        self.v_step4_sba = tk.StringVar(value="")
        
        self.v_step5_file = tk.StringVar(value="") 
        self.v_poly = tk.StringVar(value="2")
        self.v_win = tk.StringVar(value="15")
        
        self.v_step6_file = tk.StringVar(value="") 
        
        self.v_step7_dat = tk.StringVar(value="")
        self.v_reg_cut = tk.StringVar(value="0") 
        
        self.image_labels = []
        self.setup_ui()
        self.clean_plots()

    def browse(self, var, multi=False, is_dat=False):
        if multi:
            files = filedialog.askopenfilenames(filetypes=[("TIFF files", "*.tif")])
            if files: 
                self.dem_files = list(files)
                self.dem_label.config(text=f"{len(files)} DEMs selected")
        elif is_dat:
            file = filedialog.askopenfilename(filetypes=[("DAT files", "*.dat")])
            if file: var.set(os.path.abspath(file))
        else:
            file = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
            if file: var.set(os.path.abspath(file)) 

    def clean_plots(self):
        if os.path.exists('temp_plots_list.txt'): os.remove('temp_plots_list.txt')

    def display_images(self, append=False):
        if not append:
            for widget in self.img_inner.winfo_children(): widget.destroy()
            self.image_labels.clear()
            
        if not os.path.exists("temp_plots_list.txt"): return
        
        with open("temp_plots_list.txt", "r") as f:
            imgs = [line.strip() for line in f if line.strip()]
            
        start_idx = len(self.image_labels) if append else 0
            
        for p in imgs[start_idx:]:
            if os.path.exists(p):
                try:
                    img = Image.open(p)
                    w_pct = 600 / float(img.size[0]) 
                    img = img.resize((600, int(float(img.size[1]) * w_pct)), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    lbl = tk.Label(self.img_inner, image=photo, bg="white")
                    lbl.image = photo; lbl.pack(pady=10)
                    self.image_labels.append(photo)
                except: pass
        self.img_canvas.update_idletasks()
        self.img_canvas.config(scrollregion=self.img_canvas.bbox("all"))

    def run_cmd(self, task, args_list, clean=True):
        if clean: self.clean_plots()
        
        self.status.set(f"Status: Running {task}...")
        self.terminal.insert(tk.END, f"\n{'='*60}\n>> Task: {task.upper()}...\n")
        self.terminal.see(tk.END); self.root.update()
        
        cmd = [sys.executable, MAIN_SCRIPT, "--task", task] + args_list
        env = os.environ.copy(); env["MPLBACKEND"] = "TkAgg"
        
        process = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None: break
            if output:
                self.terminal.insert(tk.END, output)
                self.terminal.see(tk.END); self.root.update()
        
        rc = process.poll()
        if rc == 0:
            self.display_images(append=not clean)
            
            # --- AUTO FILL LOGIC ---
            if task == 'step1':
                out_utm = os.path.join(DIR_RES, "FAA_UTM.xlsx")
                self.v_step2_faa_utm.set(out_utm)
                self.v_step3_faa_utm.set(out_utm)
            elif task == 'sba':
                out_sba = os.path.join(DIR_RES, "SBA.xlsx")
                self.v_step4_sba.set(out_sba)
            elif task == 'cba':
                out_cba = os.path.join(DIR_RES, "CBA.xlsx")
                self.v_step5_file.set(out_cba)
                self.v_step6_file.set(out_cba)
            elif task == 'filter':
                out_filt = os.path.join(DIR_RES, "Filtered_and_Derivatives.xlsx")
                self.v_step6_file.set(out_filt)

            # --- VALUE CAPTURE ---
            if os.path.exists("temp_val.txt"):
                with open("temp_val.txt", "r") as f: val = f.read().strip()
                if task in ['parasnis', 'nettleton']: self.v_rho.set(f"{float(val):.3f}")
                elif task == 'spectrum': self.v_win.set(val)
                os.remove("temp_val.txt")
                
            if os.path.exists("temp_dat_file.txt"):
                with open("temp_dat_file.txt", "r") as f: val = f.read().strip()
                self.v_step7_dat.set(val)
                os.remove("temp_dat_file.txt")
            
            self.status.set("Status: Ready.")
            return True
        else:
            self.status.set("Status: Error.")
            messagebox.showerror("Error", f"Failed to execute {task}. Check terminal logs.")
            return False

    def setup_ui(self):
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        left_container = ttk.Frame(main_paned, width=470)
        main_paned.add(left_container, weight=1)
        
        canvas = tk.Canvas(left_container)
        scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=450)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # NAMA APLIKASI DI HEADER PANEL KIRI
        ttk.Label(scrollable_frame, text="GRAVIS Pipeline", font=("Arial", 16, "bold"), foreground="#2c3e50").pack(pady=(10, 0))
        ttk.Label(scrollable_frame, text="Gravity Reduction And Visualization System", font=("Arial", 10, "italic"), foreground="#34495e").pack(pady=(0, 5))

        # CREDITS WATERMARK (DIPINDAH KE ATAS)
        ttk.Label(scrollable_frame, text="Developed by:", font=("Arial", 9)).pack(pady=(5, 0))
        ttk.Label(scrollable_frame, text="Rayhan Irfan Hielmy", font=("Arial", 11, "bold"), foreground="#2980b9").pack()
        ttk.Label(scrollable_frame, text="© 2026 | Indonesia", font=("Arial", 9, "italic")).pack(pady=(0, 15))

        # Global Settings
        fg = ttk.LabelFrame(scrollable_frame, text="Global Settings", padding=5); fg.pack(fill=tk.X, pady=2)
        rg = ttk.Frame(fg); rg.pack(fill=tk.X, pady=2)
        ttk.Label(rg, text="Map Grid Resolution:").pack(side=tk.LEFT)
        ttk.Entry(rg, textvariable=self.v_grid, width=8).pack(side=tk.LEFT, padx=5)

        # Stage 1
        f1 = ttk.LabelFrame(scrollable_frame, text="Stage 1: Elevation & UTM", padding=5); f1.pack(fill=tk.X, pady=2)
        r = ttk.Frame(f1); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text="FAA File:").pack(side=tk.LEFT); ttk.Entry(r, textvariable=self.v_step1_faa, width=12).pack(side=tk.LEFT, padx=5); ttk.Button(r, text="Browse", command=lambda: self.browse(self.v_step1_faa)).pack(side=tk.LEFT)
        r = ttk.Frame(f1); r.pack(fill=tk.X, pady=2)
        ttk.Button(r, text="Browse DEMs", command=lambda: self.browse(None, True)).pack(side=tk.LEFT); self.dem_label = ttk.Label(r, text="0 DEM selected"); self.dem_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(f1, text="Extract Elevation & UTM", command=lambda: self.run_cmd('step1', ['--input1', self.v_step1_faa.get(), '--dems'] + self.dem_files)).pack(fill=tk.X, pady=2)

        # Stage 2
        f2 = ttk.LabelFrame(scrollable_frame, text="Stage 2: Density Estimation", padding=5); f2.pack(fill=tk.X, pady=2)
        r = ttk.Frame(f2); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text="FAA_UTM:").pack(side=tk.LEFT); ttk.Entry(r, textvariable=self.v_step2_faa_utm, width=12).pack(side=tk.LEFT, padx=5); ttk.Button(r, text="Browse", command=lambda: self.browse(self.v_step2_faa_utm)).pack(side=tk.LEFT)
        r = ttk.Frame(f2); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text="Est. Density (ρ):").pack(side=tk.LEFT); ttk.Entry(r, textvariable=self.v_rho, width=6).pack(side=tk.LEFT, padx=5); ttk.Label(r, text="(Auto)").pack(side=tk.LEFT)
        ttk.Button(f2, text="Parasnis Method", command=lambda: self.run_cmd('parasnis', ['--input1', self.v_step2_faa_utm.get()])).pack(fill=tk.X, pady=2)
        ttk.Button(f2, text="Nettleton Method", command=lambda: self.run_cmd('nettleton', ['--input1', self.v_step2_faa_utm.get()])).pack(fill=tk.X, pady=2)

        # Stage 3
        f3 = ttk.LabelFrame(scrollable_frame, text="Stage 3: Simple Bouguer Anomaly (SBA)", padding=5); f3.pack(fill=tk.X, pady=2)
        r = ttk.Frame(f3); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text="FAA_UTM:").pack(side=tk.LEFT); ttk.Entry(r, textvariable=self.v_step3_faa_utm, width=12).pack(side=tk.LEFT, padx=5); ttk.Button(r, text="Browse", command=lambda: self.browse(self.v_step3_faa_utm)).pack(side=tk.LEFT)
        ttk.Button(f3, text="Calculate SBA", command=lambda: self.run_cmd('sba', ['--input1', self.v_step3_faa_utm.get(), '--rho', self.v_rho.get(), '--res', self.v_grid.get()])).pack(fill=tk.X, pady=2)

        # Stage 4
        f4 = ttk.LabelFrame(scrollable_frame, text="Stage 4: Complete Bouguer Anomaly (TC & CBA)", padding=5); f4.pack(fill=tk.X, pady=2)
        r = ttk.Frame(f4); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text="SBA File:").pack(side=tk.LEFT); ttk.Entry(r, textvariable=self.v_step4_sba, width=12).pack(side=tk.LEFT, padx=5); ttk.Button(r, text="Browse", command=lambda: self.browse(self.v_step4_sba)).pack(side=tk.LEFT)
        ttk.Button(f4, text="Calculate TC & CBA", command=lambda: self.run_cmd('cba', ['--input1', self.v_step4_sba.get(), '--rho', self.v_rho.get(), '--res', self.v_grid.get()])).pack(fill=tk.X, pady=2)

        # Stage 5
        f5 = ttk.LabelFrame(scrollable_frame, text="Stage 5: Filtering & Derivatives", padding=5); f5.pack(fill=tk.X, pady=2)
        r = ttk.Frame(f5); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text="Data File:").pack(side=tk.LEFT); ttk.Entry(r, textvariable=self.v_step5_file, width=12).pack(side=tk.LEFT, padx=5); ttk.Button(r, text="Browse", command=lambda: self.browse(self.v_step5_file)).pack(side=tk.LEFT)
        r = ttk.Frame(f5); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text="Poly O:").pack(side=tk.LEFT); ttk.Entry(r, textvariable=self.v_poly, width=3).pack(side=tk.LEFT, padx=2)
        ttk.Label(r, text="MA Win:").pack(side=tk.LEFT); ttk.Entry(r, textvariable=self.v_win, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Button(f5, text="Run Filters (Poly, MA, FHD, SVD)", command=lambda: self.run_cmd('filter', ['--input1', self.v_step5_file.get(), '--res', self.v_grid.get(), '--poly', self.v_poly.get(), '--window', self.v_win.get()])).pack(fill=tk.X, pady=2)

        # Stage 6
        f6 = ttk.LabelFrame(scrollable_frame, text="Stage 6: Interactive Map Slicing", padding=5); f6.pack(fill=tk.X, pady=2)
        r = ttk.Frame(f6); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text="Data File:").pack(side=tk.LEFT); ttk.Entry(r, textvariable=self.v_step6_file, width=12).pack(side=tk.LEFT, padx=5); ttk.Button(r, text="Browse", command=lambda: self.browse(self.v_step6_file)).pack(side=tk.LEFT)
        r = ttk.Frame(f6); r.pack(fill=tk.X, pady=2)
        self.cbox_map = ttk.Combobox(r, values=['SBA', 'CBA', 'Poly_Res', 'MA_Res', 'FHD', 'SVD'], width=10)
        self.cbox_map.set('CBA'); self.cbox_map.pack(side=tk.LEFT, padx=5)
        ttk.Button(r, text="Interactive Map Slice", command=lambda: self.run_cmd('interactive', ['--input1', self.v_step6_file.get(), '--target_map', self.cbox_map.get(), '--res', self.v_grid.get()])).pack(side=tk.LEFT, expand=True, fill=tk.X)

        # Stage 7
        f7 = ttk.LabelFrame(scrollable_frame, text="Stage 7: Spectrum Analysis", padding=5); f7.pack(fill=tk.X, pady=2)
        r = ttk.Frame(f7); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text=".dat File:").pack(side=tk.LEFT); ttk.Entry(r, textvariable=self.v_step7_dat, width=12).pack(side=tk.LEFT, padx=5); ttk.Button(r, text="Browse", command=lambda: self.browse(self.v_step7_dat, is_dat=True)).pack(side=tk.LEFT)
        r = ttk.Frame(f7); r.pack(fill=tk.X, pady=2)
        ttk.Label(r, text="Reg Cut Index:").pack(side=tk.LEFT); ttk.Entry(r, textvariable=self.v_reg_cut, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Button(f7, text="Run Spectrum", command=lambda: self.run_cmd('spectrum', ['--input1', self.v_step7_dat.get(), '--reg_cut', self.v_reg_cut.get()])).pack(fill=tk.X, pady=2)

        self.status = tk.StringVar(value="Status: Ready.")
        ttk.Label(scrollable_frame, textvariable=self.status, foreground="blue", font=("Arial", 10, "italic")).pack(pady=10)

        # ====== PANEL KANAN ======
        right_paned = ttk.PanedWindow(main_paned, orient=tk.VERTICAL)
        main_paned.add(right_paned, weight=3)
        
        term_frame = ttk.LabelFrame(right_paned, text="Terminal Output (Live)")
        right_paned.add(term_frame, weight=1)
        term_scroll = ttk.Scrollbar(term_frame)
        term_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.terminal = tk.Text(term_frame, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 10), yscrollcommand=term_scroll.set)
        self.terminal.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        term_scroll.config(command=self.terminal.yview)
        
        # Sapaan di Terminal
        self.terminal.insert(tk.END, "============================================================\n")
        self.terminal.insert(tk.END, "            WELCOME TO GRAVIS PIPELINE\n")
        self.terminal.insert(tk.END, "  Gravity Reduction And Visualization System\n")
        self.terminal.insert(tk.END, "  Author: Rayhan Irfan Hielmy (2026, Indonesia)\n")
        self.terminal.insert(tk.END, "============================================================\n\n")
        
        img_frame = ttk.LabelFrame(right_paned, text="Visualization Output")
        right_paned.add(img_frame, weight=3)
        self.img_canvas = tk.Canvas(img_frame, bg="white")
        scroll_y = ttk.Scrollbar(img_frame, orient="vertical", command=self.img_canvas.yview)
        self.img_inner = ttk.Frame(self.img_canvas, style="White.TFrame")
        self.img_inner.bind("<Configure>", lambda e: self.img_canvas.configure(scrollregion=self.img_canvas.bbox("all")))
        self.img_canvas.create_window((0, 0), window=self.img_inner, anchor="n")
        self.img_canvas.configure(yscrollcommand=scroll_y.set)
        self.img_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        ttk.Style().configure("White.TFrame", background="white")

if __name__ == "__main__":
    root = tk.Tk()
    app = GravityGUI(root)
    root.mainloop()
