# app.py
# The main window. Owns all widgets and coordinates between user actions
# and the ffmpeg_utils conversion layer.

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path

from theme import (
    BG_DARK, BG_CARD, BG_INPUT, ACCENT, ACCENT_DIM,
    SUCCESS, ERROR, WARNING, TEXT_PRI, TEXT_SEC, BORDER,
    FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_MONO, FONT_BTN, FONT_BADGE,
)
from ffmpeg_utils import find_ffmpeg, label_to_crf, run_conversion


class AviConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AVI Converter")
        self.geometry("820x640")
        self.minsize(720, 560)
        self.configure(bg=BG_DARK)
        self.resizable(True, True)

        self._ffmpeg_path = find_ffmpeg()
        self._folder_path = tk.StringVar()
        self._output_path = tk.StringVar()
        self._quality     = tk.StringVar(value="High (CRF 18)")
        self._delete_orig = tk.BooleanVar(value=False)
        self._converting  = False
        self._stop_flag   = False
        self._file_items  = {}  # filename -> (row_frame, status_label, progressbar)

        self._build_ui()
        self._check_ffmpeg_banner()

    # ------------------------------------------------------------------
    # FFmpeg status banner
    # ------------------------------------------------------------------

    def _check_ffmpeg_banner(self):
        if self._ffmpeg_path:
            self._set_status(f"FFmpeg found: {self._ffmpeg_path}", SUCCESS)
        else:
            self._set_status(
                "FFmpeg not found. Place ffmpeg.exe next to this script or add it to PATH.",
                WARNING,
            )

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self._build_header()
        self._build_status_bar()
        self._build_settings_card()
        self._build_file_list()
        self._build_controls()
        self._apply_progressbar_style()

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_CARD, pady=18)
        hdr.pack(fill="x")
        tk.Label(hdr, text="AVI to MP4 Converter",
                 font=FONT_TITLE, bg=BG_CARD, fg=TEXT_PRI).pack(side="left", padx=28)
        tk.Label(hdr, text=" BATCH ", font=FONT_BADGE,
                 bg=ACCENT, fg="white", padx=6, pady=2).pack(side="left", padx=4, pady=6)

    def _build_status_bar(self):
        self._status_lbl = tk.Label(self, text="", font=FONT_SUB,
                                    bg=BG_DARK, fg=TEXT_SEC, anchor="w")
        self._status_lbl.pack(fill="x", padx=28, pady=(10, 0))

    def _build_settings_card(self):
        card = tk.Frame(self, bg=BG_CARD, bd=0, relief="flat", padx=20, pady=16)
        card.pack(fill="x", padx=20, pady=(8, 4))

        self._row_picker(card, "Input Folder:",  self._folder_path, self._browse_input,  0)
        self._row_picker(card, "Output Folder:", self._output_path, self._browse_output, 1,
                         hint="(leave blank = same as input)")
        self._row_options(card)

    def _build_file_list(self):
        list_hdr = tk.Frame(self, bg=BG_DARK)
        list_hdr.pack(fill="x", padx=20, pady=(10, 2))
        tk.Label(list_hdr, text="FILES TO CONVERT", font=FONT_LABEL,
                 bg=BG_DARK, fg=TEXT_SEC).pack(side="left")
        self._count_lbl = tk.Label(list_hdr, text="", font=FONT_BADGE,
                                   bg=BG_DARK, fg=ACCENT)
        self._count_lbl.pack(side="left", padx=8)

        outer = tk.Frame(self, bg=BORDER, bd=1, relief="flat")
        outer.pack(fill="both", expand=True, padx=20, pady=(0, 4))

        self._canvas = tk.Canvas(outer, bg=BG_INPUT, bd=0, highlightthickness=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._file_frame = tk.Frame(self._canvas, bg=BG_INPUT)
        self._canvas_win = self._canvas.create_window((0, 0), window=self._file_frame, anchor="nw")
        self._file_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>",     self._on_canvas_configure)

        self._show_empty_message("No AVI files loaded yet.\nUse the folder picker above to scan for files.")

    def _build_controls(self):
        ctrl = tk.Frame(self, bg=BG_DARK, pady=12)
        ctrl.pack(fill="x", padx=20)

        self._overall_bar = ttk.Progressbar(ctrl, mode="determinate",
                                            style="Overall.Horizontal.TProgressbar")
        self._overall_bar.pack(fill="x", pady=(0, 8))

        btn_row = tk.Frame(ctrl, bg=BG_DARK)
        btn_row.pack(fill="x")

        self._scan_btn    = self._btn(btn_row, "Scan Folder",  ACCENT,   self._scan_folder)
        self._convert_btn = self._btn(btn_row, "Convert All",  SUCCESS,  self._start_conversion)
        self._stop_btn    = self._btn(btn_row, "Stop",         ERROR,    self._stop_conversion)

        self._scan_btn.pack(side="left",    padx=(0, 8))
        self._convert_btn.pack(side="left", padx=(0, 8))
        self._stop_btn.pack(side="left")

        self._convert_btn.configure(state="disabled")
        self._stop_btn.configure(state="disabled")

        self._progress_lbl = tk.Label(btn_row, text="", font=FONT_SUB, bg=BG_DARK, fg=TEXT_SEC)
        self._progress_lbl.pack(side="right")

    # ------------------------------------------------------------------
    # Reusable widget helpers
    # ------------------------------------------------------------------

    def _row_picker(self, parent, label, var, cmd, row, hint=""):
        tk.Label(parent, text=label, font=FONT_LABEL,
                 bg=BG_CARD, fg=TEXT_SEC, width=14, anchor="w"
                 ).grid(row=row, column=0, sticky="w", pady=5)

        entry = tk.Entry(parent, textvariable=var, font=FONT_MONO,
                         bg=BG_INPUT, fg=TEXT_PRI, insertbackground=TEXT_PRI,
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=BORDER, highlightcolor=ACCENT)
        entry.grid(row=row, column=1, sticky="ew", padx=(0, 8), ipady=6)

        if hint:
            entry.config(fg=TEXT_SEC)
            entry.insert(0, hint)

            def on_focus_in(e, en=entry, h=hint):
                if en.get() == h:
                    en.delete(0, "end")
                    en.config(fg=TEXT_PRI)

            def on_focus_out(e, en=entry, h=hint):
                if not en.get():
                    en.insert(0, h)
                    en.config(fg=TEXT_SEC)

            entry.bind("<FocusIn>",  on_focus_in)
            entry.bind("<FocusOut>", on_focus_out)
            var.set("")

        tk.Button(parent, text="Browse", font=FONT_LABEL,
                  bg=ACCENT_DIM, fg="white", relief="flat",
                  padx=10, pady=4, cursor="hand2", command=cmd
                  ).grid(row=row, column=2, sticky="ew")
        parent.columnconfigure(1, weight=1)

    def _row_options(self, parent):
        tk.Label(parent, text="Quality:", font=FONT_LABEL,
                 bg=BG_CARD, fg=TEXT_SEC, width=14, anchor="w"
                 ).grid(row=2, column=0, sticky="w", pady=5)

        opts = ["Lossless (CRF 0)", "High (CRF 18)", "Medium (CRF 23)", "Low (CRF 28)"]
        menu = tk.OptionMenu(parent, self._quality, *opts)
        menu.config(bg=BG_INPUT, fg=TEXT_PRI, activebackground=ACCENT,
                    activeforeground="white", relief="flat", font=FONT_SUB,
                    highlightthickness=1, highlightbackground=BORDER, bd=0)
        menu["menu"].config(bg=BG_INPUT, fg=TEXT_PRI,
                            activebackground=ACCENT, activeforeground="white")
        menu.grid(row=2, column=1, sticky="w", padx=(0, 8), pady=5)

        tk.Checkbutton(parent, text="Delete original AVI after conversion",
                       variable=self._delete_orig, font=FONT_SUB,
                       bg=BG_CARD, fg=TEXT_SEC, activebackground=BG_CARD,
                       activeforeground=TEXT_PRI, selectcolor=BG_INPUT,
                       cursor="hand2", relief="flat"
                       ).grid(row=2, column=2, sticky="w")

    def _btn(self, parent, text, color, cmd):
        return tk.Button(parent, text=text, font=FONT_BTN,
                         bg=color, fg="white", relief="flat",
                         activebackground=color, activeforeground="white",
                         padx=18, pady=8, cursor="hand2", bd=0, command=cmd)

    def _apply_progressbar_style(self):
        s = ttk.Style(self)
        s.theme_use("default")
        for name, thickness in (("Overall", 6), ("File", 4)):
            s.configure(f"{name}.Horizontal.TProgressbar",
                        troughcolor=BG_INPUT, background=ACCENT,
                        bordercolor=BORDER, lightcolor=ACCENT,
                        darkcolor=ACCENT, thickness=thickness)

    # ------------------------------------------------------------------
    # Canvas scroll helpers
    # ------------------------------------------------------------------

    def _on_frame_configure(self, event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._canvas_win, width=event.width)

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    def _set_status(self, msg, color=TEXT_SEC):
        self._status_lbl.config(text=msg, fg=color)

    # ------------------------------------------------------------------
    # Folder browsing
    # ------------------------------------------------------------------

    def _browse_input(self):
        d = filedialog.askdirectory(title="Select folder with AVI files")
        if d:
            self._folder_path.set(d)
            self._scan_folder()

    def _browse_output(self):
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self._output_path.set(d)

    # ------------------------------------------------------------------
    # File scanning
    # ------------------------------------------------------------------

    def _scan_folder(self):
        folder = self._folder_path.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("No folder", "Please select a valid folder first.")
            return

        avi_files = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() == ".avi")

        for w in self._file_frame.winfo_children():
            w.destroy()
        self._file_items.clear()

        if not avi_files:
            self._show_empty_message("No AVI files found in this folder.")
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

    def _show_empty_message(self, text):
        tk.Label(self._file_frame, text=text, font=FONT_SUB,
                 bg=BG_INPUT, fg=TEXT_SEC, justify="center", pady=40
                 ).pack(expand=True)

    def _add_file_row(self, path: Path):
        size_mb = path.stat().st_size / (1024 * 1024)

        row = tk.Frame(self._file_frame, bg=BG_INPUT, pady=6, padx=12)
        row.pack(fill="x", pady=1)

        info = tk.Frame(row, bg=BG_INPUT)
        info.pack(fill="x")

        tk.Label(info, text=path.name, font=FONT_SUB,
                 bg=BG_INPUT, fg=TEXT_PRI, anchor="w").pack(side="left")
        tk.Label(info, text=f"  {size_mb:.1f} MB", font=FONT_BADGE,
                 bg=BG_INPUT, fg=TEXT_SEC).pack(side="left")

        status_lbl = tk.Label(info, text="Queued", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_SEC)
        status_lbl.pack(side="right")

        bar = ttk.Progressbar(row, mode="indeterminate",
                              style="File.Horizontal.TProgressbar", length=200)
        bar.pack(fill="x", pady=(4, 0))

        self._file_items[path.name] = (row, status_lbl, bar)

    # ------------------------------------------------------------------
    # Conversion orchestration
    # ------------------------------------------------------------------

    def _start_conversion(self):
        if not self._ffmpeg_path:
            messagebox.showerror(
                "FFmpeg not found",
                "Place ffmpeg.exe next to this script or add it to your system PATH.",
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

        threading.Thread(target=self._conversion_worker, daemon=True).start()

    def _stop_conversion(self):
        self._stop_flag = True
        self._set_status("Stopping after current file...", WARNING)

    def _conversion_worker(self):
        folder  = self._folder_path.get()
        out_dir = self._output_path.get().strip()
        if not out_dir or out_dir == "(leave blank = same as input)":
            out_dir = folder

        os.makedirs(out_dir, exist_ok=True)

        files = list(self._file_items.keys())
        total = len(files)
        done  = 0
        errors = 0
        crf   = label_to_crf(self._quality.get())

        for fname in files:
            if self._stop_flag:
                break

            _, status_lbl, bar = self._file_items[fname]
            in_path  = Path(folder) / fname
            out_path = Path(out_dir) / (in_path.stem + ".mp4")

            self._ui(status_lbl.config, text="Converting...", fg=ACCENT)
            self._ui(bar.config, mode="indeterminate")
            self._ui(bar.start, 12)
            self._ui(self._set_status, f"Converting {fname}  ({done + 1}/{total})...", ACCENT)

            success, error_msg = run_conversion(
                self._ffmpeg_path, str(in_path), str(out_path), crf
            )

            self._ui(bar.stop)
            self._ui(bar.config, mode="determinate", value=100 if success else 0)

            if success:
                self._ui(status_lbl.config, text="Done", fg=SUCCESS)
                if self._delete_orig.get():
                    try:
                        in_path.unlink()
                    except Exception:
                        pass
                done += 1
            else:
                self._ui(status_lbl.config, text="Error", fg=ERROR)
                self._ui(self._set_status, f"Error on {fname}: {error_msg}", ERROR)
                errors += 1

            pct = int((done + errors) / total * 100)
            self._ui(self._overall_bar.config, value=pct)
            self._ui(self._progress_lbl.config, text=f"{done + errors}/{total}  ok:{done}  fail:{errors}")

        self._converting = False
        self._ui(self._scan_btn.configure,    state="normal")
        self._ui(self._convert_btn.configure, state="normal")
        self._ui(self._stop_btn.configure,    state="disabled")

        if self._stop_flag:
            self._ui(self._set_status, "Conversion stopped by user.", WARNING)
        elif errors == 0:
            self._ui(self._set_status, f"All {done} file(s) converted successfully.", SUCCESS)
        else:
            self._ui(self._set_status, f"Done. {done} succeeded, {errors} failed.", WARNING)

    # ------------------------------------------------------------------
    # Thread-safe UI update helper
    # ------------------------------------------------------------------

    def _ui(self, fn, *args, **kwargs):
        """Schedule a UI call from the worker thread back onto the main thread."""
        self.after(0, lambda: fn(*args, **kwargs))
