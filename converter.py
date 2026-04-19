import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import os
import shutil
from pathlib import Path
import time

# ─── Theme Colors ────────────────────────────────────────────────────────────
BG_DARK    = "#0f1117"
BG_CARD    = "#1a1d2e"
BG_INPUT   = "#12141f"
ACCENT     = "#6c63ff"
ACCENT_DIM = "#4b44c9"
SUCCESS    = "#22c55e"
ERROR      = "#ef4444"
WARNING    = "#f59e0b"
TEXT_PRI   = "#e2e8f0"
TEXT_SEC   = "#94a3b8"
BORDER     = "#2d3148"

FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_SUB    = ("Segoe UI", 10)
FONT_LABEL  = ("Segoe UI", 9, "bold")
FONT_MONO   = ("Consolas", 9)
FONT_BTN    = ("Segoe UI", 10, "bold")
FONT_BADGE  = ("Segoe UI", 8, "bold")


class AviConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AVI Converter")
        self.geometry("820x640")
        self.minsize(720, 560)
        self.configure(bg=BG_DARK)
        self.resizable(True, True)

        self._ffmpeg_path = self._find_ffmpeg()
        self._folder_path = tk.StringVar()
        self._output_path = tk.StringVar()
        self._quality     = tk.StringVar(value="High (CRF 18)")
        self._delete_orig = tk.BooleanVar(value=False)
        self._converting  = False
        self._stop_flag   = False
        self._file_items  = {}   # filename → (row_frame, status_label, bar)

        self._build_ui()
        self._check_ffmpeg_banner()

    # ──────────────────────────────────────────────────────────────────────────
    # FFmpeg detection
    # ──────────────────────────────────────────────────────────────────────────
    def _find_ffmpeg(self):
        # 1. Same directory as this script
        local = Path(__file__).parent / "ffmpeg.exe"
        if local.exists():
            return str(local)
        # 2. System PATH
        found = shutil.which("ffmpeg")
        if found:
            return found
        # 3. Known WinGet install location
        winget = Path(r"C:\Users\gumba\AppData\Local\Microsoft\WinGet\Packages"
                      r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
                      r"\ffmpeg-8.1-full_build\bin\ffmpeg.exe")
        if winget.exists():
            return str(winget)
        return None

    def _check_ffmpeg_banner(self):
        if self._ffmpeg_path:
            self._set_status(f"FFmpeg found: {self._ffmpeg_path}", SUCCESS)
        else:
            self._set_status(
                "⚠  FFmpeg not found. Place ffmpeg.exe next to this script or add it to PATH.",
                WARNING,
            )

    # ──────────────────────────────────────────────────────────────────────────
    # UI Construction
    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG_CARD, pady=18)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚡ AVI → MP4 Converter",
                 font=FONT_TITLE, bg=BG_CARD, fg=TEXT_PRI).pack(side="left", padx=28)
        badge = tk.Label(hdr, text=" BATCH ", font=FONT_BADGE,
                         bg=ACCENT, fg="white", padx=6, pady=2)
        badge.pack(side="left", padx=4, pady=6)

        # ── Status bar (top) ─────────────────────────────────────────────────
        self._status_lbl = tk.Label(self, text="", font=FONT_SUB,
                                    bg=BG_DARK, fg=TEXT_SEC, anchor="w")
        self._status_lbl.pack(fill="x", padx=28, pady=(10, 0))

        # ── Settings card ───────────────────────────────────────────────────
        card = tk.Frame(self, bg=BG_CARD, bd=0, relief="flat",
                        padx=20, pady=16)
        card.pack(fill="x", padx=20, pady=(8, 4))

        self._row_picker(card, "Input Folder:",  self._folder_path,
                         self._browse_input, 0)
        self._row_picker(card, "Output Folder:", self._output_path,
                         self._browse_output, 1,
                         hint="(leave blank = same as input)")
        self._row_options(card)

        # ── File list ────────────────────────────────────────────────────────
        list_hdr = tk.Frame(self, bg=BG_DARK)
        list_hdr.pack(fill="x", padx=20, pady=(10, 2))
        tk.Label(list_hdr, text="FILES TO CONVERT", font=FONT_LABEL,
                 bg=BG_DARK, fg=TEXT_SEC).pack(side="left")
        self._count_lbl = tk.Label(list_hdr, text="", font=FONT_BADGE,
                                   bg=BG_DARK, fg=ACCENT)
        self._count_lbl.pack(side="left", padx=8)

        # Scrollable canvas
        outer = tk.Frame(self, bg=BORDER, bd=1, relief="flat")
        outer.pack(fill="both", expand=True, padx=20, pady=(0, 4))

        self._canvas = tk.Canvas(outer, bg=BG_INPUT, bd=0,
                                 highlightthickness=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical",
                                 command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._file_frame = tk.Frame(self._canvas, bg=BG_INPUT)
        self._canvas_win = self._canvas.create_window(
            (0, 0), window=self._file_frame, anchor="nw")
        self._file_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._empty_lbl = tk.Label(
            self._file_frame,
            text="No AVI files loaded yet.\nUse the folder picker above to scan for files.",
            font=FONT_SUB, bg=BG_INPUT, fg=TEXT_SEC,
            justify="center", pady=40,
        )
        self._empty_lbl.pack(expand=True)

        # ── Bottom controls ──────────────────────────────────────────────────
        ctrl = tk.Frame(self, bg=BG_DARK, pady=12)
        ctrl.pack(fill="x", padx=20)

        self._overall_bar = ttk.Progressbar(ctrl, mode="determinate",
                                            style="Overall.Horizontal.TProgressbar")
        self._overall_bar.pack(fill="x", pady=(0, 8))

        btn_row = tk.Frame(ctrl, bg=BG_DARK)
        btn_row.pack(fill="x")

        self._scan_btn = self._btn(btn_row, "🔍  Scan Folder",
                                   ACCENT, self._scan_folder)
        self._scan_btn.pack(side="left", padx=(0, 8))

        self._convert_btn = self._btn(btn_row, "▶  Convert All",
                                      SUCCESS, self._start_conversion)
        self._convert_btn.pack(side="left", padx=(0, 8))
        self._convert_btn.configure(state="disabled")

        self._stop_btn = self._btn(btn_row, "■  Stop",
                                   ERROR, self._stop_conversion)
        self._stop_btn.pack(side="left")
        self._stop_btn.configure(state="disabled")

        self._progress_lbl = tk.Label(btn_row, text="", font=FONT_SUB,
                                      bg=BG_DARK, fg=TEXT_SEC)
        self._progress_lbl.pack(side="right")

        self._style()

    # ──────────────────────────────────────────────────────────────────────────
    # Helper widgets
    # ──────────────────────────────────────────────────────────────────────────
    def _row_picker(self, parent, label, var, cmd, row, hint=""):
        tk.Label(parent, text=label, font=FONT_LABEL,
                 bg=BG_CARD, fg=TEXT_SEC, width=14, anchor="w"
                 ).grid(row=row, column=0, sticky="w", pady=5)
        entry = tk.Entry(parent, textvariable=var, font=FONT_MONO,
                         bg=BG_INPUT, fg=TEXT_PRI, insertbackground=TEXT_PRI,
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=BORDER,
                         highlightcolor=ACCENT)
        entry.grid(row=row, column=1, sticky="ew", padx=(0, 8), ipady=6)
        if hint:
            entry.config(fg=TEXT_SEC)
            entry.insert(0, hint)

            def _on_focus_in(e, en=entry, h=hint, v=var):
                if en.get() == h:
                    en.delete(0, "end")
                    en.config(fg=TEXT_PRI)

            def _on_focus_out(e, en=entry, h=hint, v=var):
                if not en.get():
                    en.insert(0, h)
                    en.config(fg=TEXT_SEC)

            entry.bind("<FocusIn>",  _on_focus_in)
            entry.bind("<FocusOut>", _on_focus_out)
            var.set("")   # keep var empty for logic

        tk.Button(parent, text="Browse", font=FONT_LABEL,
                  bg=ACCENT_DIM, fg="white", relief="flat",
                  padx=10, pady=4, cursor="hand2", command=cmd
                  ).grid(row=row, column=2, sticky="ew")
        parent.columnconfigure(1, weight=1)

    def _row_options(self, parent):
        row = 2
        tk.Label(parent, text="Quality:", font=FONT_LABEL,
                 bg=BG_CARD, fg=TEXT_SEC, width=14, anchor="w"
                 ).grid(row=row, column=0, sticky="w", pady=5)
        opts = ["Lossless (CRF 0)", "High (CRF 18)",
                "Medium (CRF 23)", "Low (CRF 28)"]
        menu = tk.OptionMenu(parent, self._quality, *opts)
        menu.config(bg=BG_INPUT, fg=TEXT_PRI, activebackground=ACCENT,
                    activeforeground="white", relief="flat",
                    font=FONT_SUB, highlightthickness=1,
                    highlightbackground=BORDER, bd=0)
        menu["menu"].config(bg=BG_INPUT, fg=TEXT_PRI,
                            activebackground=ACCENT,
                            activeforeground="white")
        menu.grid(row=row, column=1, sticky="w", padx=(0, 8), pady=5)

        chk = tk.Checkbutton(parent, text="Delete original AVI after conversion",
                             variable=self._delete_orig,
                             font=FONT_SUB, bg=BG_CARD, fg=TEXT_SEC,
                             activebackground=BG_CARD, activeforeground=TEXT_PRI,
                             selectcolor=BG_INPUT, cursor="hand2",
                             relief="flat")
        chk.grid(row=row, column=2, sticky="w")

    def _btn(self, parent, text, color, cmd):
        return tk.Button(
            parent, text=text, font=FONT_BTN,
            bg=color, fg="white", relief="flat",
            activebackground=color, activeforeground="white",
            padx=18, pady=8, cursor="hand2", bd=0,
            command=cmd,
        )

    def _style(self):
        s = ttk.Style(self)
        s.theme_use("default")
        s.configure("Overall.Horizontal.TProgressbar",
                    troughcolor=BG_INPUT, background=ACCENT,
                    bordercolor=BORDER, lightcolor=ACCENT,
                    darkcolor=ACCENT, thickness=6)
        s.configure("File.Horizontal.TProgressbar",
                    troughcolor=BG_INPUT, background=ACCENT,
                    bordercolor=BORDER, lightcolor=ACCENT,
                    darkcolor=ACCENT, thickness=4)

    # ──────────────────────────────────────────────────────────────────────────
    # Canvas scroll helpers
    # ──────────────────────────────────────────────────────────────────────────
    def _on_frame_configure(self, event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_win, width=event.width)

    # ──────────────────────────────────────────────────────────────────────────
    # Status bar
    # ──────────────────────────────────────────────────────────────────────────
    def _set_status(self, msg, color=TEXT_SEC):
        self._status_lbl.config(text=msg, fg=color)

    # ──────────────────────────────────────────────────────────────────────────
    # Browse folder
    # ──────────────────────────────────────────────────────────────────────────
    def _browse_input(self):
        d = filedialog.askdirectory(title="Select folder with AVI files")
        if d:
            self._folder_path.set(d)
            self._scan_folder()

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self._output_path.set(d)

    # ──────────────────────────────────────────────────────────────────────────
    # Scan folder for AVI files
    # ──────────────────────────────────────────────────────────────────────────
    def _scan_folder(self):
        folder = self._folder_path.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("No folder", "Please select a valid folder first.")
            return

        avi_files = sorted(
            p for p in Path(folder).iterdir()
            if p.suffix.lower() == ".avi"
        )

        # Clear existing list
        for w in self._file_frame.winfo_children():
            w.destroy()
        self._file_items.clear()

        if not avi_files:
            self._empty_lbl = tk.Label(
                self._file_frame,
                text="No AVI files found in this folder.",
                font=FONT_SUB, bg=BG_INPUT, fg=TEXT_SEC,
                justify="center", pady=40,
            )
            self._empty_lbl.pack(expand=True)
            self._count_lbl.config(text="")
            self._convert_btn.configure(state="disabled")
            self._set_status("No AVI files found.", WARNING)
            return

        for path in avi_files:
            self._add_file_row(path)

        cnt = len(avi_files)
        self._count_lbl.config(text=f"{cnt} file{'s' if cnt != 1 else ''}")
        self._convert_btn.configure(state="normal")
        self._overall_bar["value"] = 0
        self._set_status(f"Found {cnt} AVI file(s) ready to convert.", SUCCESS)

    def _add_file_row(self, path: Path):
        size_mb = path.stat().st_size / (1024 * 1024)
        row = tk.Frame(self._file_frame, bg=BG_INPUT, pady=6, padx=12)
        row.pack(fill="x", pady=1)

        info = tk.Frame(row, bg=BG_INPUT)
        info.pack(fill="x")

        tk.Label(info, text=path.name, font=FONT_SUB,
                 bg=BG_INPUT, fg=TEXT_PRI, anchor="w"
                 ).pack(side="left")
        size_lbl = tk.Label(info, text=f"  {size_mb:.1f} MB",
                            font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SEC)
        size_lbl.pack(side="left")

        status_lbl = tk.Label(info, text="Queued", font=FONT_BADGE,
                              bg=BG_INPUT, fg=TEXT_SEC)
        status_lbl.pack(side="right")

        bar = ttk.Progressbar(row, mode="indeterminate",
                              style="File.Horizontal.TProgressbar",
                              length=200)
        bar.pack(fill="x", pady=(4, 0))

        self._file_items[path.name] = (row, status_lbl, bar)

    # ──────────────────────────────────────────────────────────────────────────
    # Conversion
    # ──────────────────────────────────────────────────────────────────────────
    def _get_crf(self):
        q = self._quality.get()
        if "0"  in q: return "0"
        if "18" in q: return "18"
        if "23" in q: return "23"
        return "28"

    def _start_conversion(self):
        if not self._ffmpeg_path:
            messagebox.showerror(
                "FFmpeg not found",
                "Place ffmpeg.exe next to this script or add it to your system PATH."
            )
            return
        if not self._file_items:
            messagebox.showinfo("Nothing to do", "Scan a folder first.")
            return

        self._converting = True
        self._stop_flag  = False
        self._scan_btn.configure(state="disabled")
        self._convert_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._overall_bar["value"] = 0

        thread = threading.Thread(target=self._conversion_worker, daemon=True)
        thread.start()

    def _stop_conversion(self):
        self._stop_flag = True
        self._set_status("Stopping after current file…", WARNING)

    def _conversion_worker(self):
        folder   = self._folder_path.get()
        out_dir  = self._output_path.get().strip()
        if not out_dir or out_dir == "(leave blank = same as input)":
            out_dir = folder

        os.makedirs(out_dir, exist_ok=True)

        files    = list(self._file_items.keys())
        total    = len(files)
        done     = 0
        errors   = 0
        crf      = self._get_crf()

        for fname in files:
            if self._stop_flag:
                break

            row, status_lbl, bar = self._file_items[fname]
            in_path  = Path(folder) / fname
            out_path = Path(out_dir) / (Path(fname).stem + ".mp4")

            self._ui(status_lbl.config, text="Converting…", fg=ACCENT)
            self._ui(bar.config, mode="indeterminate")
            self._ui(bar.start, 12)
            self._ui(self._set_status,
                     f"Converting {fname}  ({done+1}/{total})…", ACCENT)

            success = self._run_ffmpeg(str(in_path), str(out_path), crf)

            self._ui(bar.stop)
            self._ui(bar.config, mode="determinate", value=100)

            if success:
                self._ui(status_lbl.config, text="✓ Done", fg=SUCCESS)
                if self._delete_orig.get():
                    try:
                        in_path.unlink()
                    except Exception:
                        pass
                done += 1
            else:
                self._ui(status_lbl.config, text="✗ Error", fg=ERROR)
                self._ui(bar.config, value=0)
                errors += 1

            pct = int((done + errors) / total * 100)
            self._ui(self._overall_bar.config, value=pct)
            self._ui(self._progress_lbl.config,
                     text=f"{done+errors}/{total}  ✓{done}  ✗{errors}")

        # Done
        self._converting = False
        self._ui(self._scan_btn.configure, state="normal")
        self._ui(self._convert_btn.configure, state="normal")
        self._ui(self._stop_btn.configure, state="disabled")

        if self._stop_flag:
            self._ui(self._set_status, "Conversion stopped by user.", WARNING)
        elif errors == 0:
            self._ui(self._set_status,
                     f"✅  All {done} file(s) converted successfully!", SUCCESS)
        else:
            self._ui(self._set_status,
                     f"Done — {done} succeeded, {errors} failed.", WARNING)

    def _run_ffmpeg(self, inp: str, out: str, crf: str) -> bool:
        cmd = [
            self._ffmpeg_path,
            "-y",               # overwrite output
            "-i", inp,
            "-c:v", "libx264",
            "-crf", crf,
            "-preset", "medium",
            "-pix_fmt", "yuv420p",   # ← force compatible pixel format for all AVI types
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            out,
        ]
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0:
                # Show last meaningful FFmpeg error line in the status bar
                err_lines = result.stderr.decode("utf-8", errors="ignore").strip().splitlines()
                err_msg = next(
                    (l for l in reversed(err_lines) if l.strip() and not l.startswith("  ")),
                    "Unknown FFmpeg error"
                )
                self._ui(self._set_status, f"✗ {Path(inp).name}: {err_msg}", ERROR)
                return False
            return True
        except Exception as e:
            self._ui(self._set_status, f"✗ Exception: {e}", ERROR)
            return False

    # ──────────────────────────────────────────────────────────────────────────
    # Thread-safe UI update
    # ──────────────────────────────────────────────────────────────────────────
    def _ui(self, fn, *args, **kwargs):
        self.after(0, lambda: fn(*args, **kwargs))


if __name__ == "__main__":
    app = AviConverterApp()
    app.mainloop()
