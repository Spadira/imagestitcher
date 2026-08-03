"""
Quick Image Stitcher — combine any number of images onto a single canvas
with a configurable black separator bar.

Copyright (c) 2026. Released under the Stitcher Non-Commercial License;
see LICENSE.txt. Free for personal use, commercial use requires permission.
"""

import math
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox

from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image, ImageTk, ImageOps

try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    RESAMPLE = Image.LANCZOS

APP_NAME = "Quick Image Stitcher"
BG = "#2b2b2b"
PANEL_BG = "#3c3f41"
ACCENT = "#4CAF50"
PREVIEW_W, PREVIEW_H = 700, 380
THUMB = 74
NAME_PART_LIMIT = 24
IMAGE_TYPES = [("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif"),
               ("All files", "*.*")]


# --------------------------------------------------------------------------
# Pure layout helpers — no Tk dependency, so they can be tested in isolation.
# --------------------------------------------------------------------------

def grid_geometry(sizes, gap, cols):
    """Place `sizes` [(w, h), ...] into a `cols`-wide grid, row-major.

    Every cell in a column is as wide as that column's widest image, and
    every cell in a row as tall as that row's tallest, with images centred
    inside their cell. Returns (total_w, total_h, [(x, y), ...]).
    """
    n = len(sizes)
    if n == 0:
        return 0, 0, []
    cols = max(1, min(int(cols), n))
    rows = math.ceil(n / cols)

    col_w = [0] * cols
    row_h = [0] * rows
    for i, (w, h) in enumerate(sizes):
        r, c = divmod(i, cols)
        col_w[c] = max(col_w[c], w)
        row_h[r] = max(row_h[r], h)

    xs, acc = [], 0
    for c in range(cols):
        xs.append(acc)
        acc += col_w[c] + gap
    ys, acc = [], 0
    for r in range(rows):
        ys.append(acc)
        acc += row_h[r] + gap

    places = []
    for i, (w, h) in enumerate(sizes):
        r, c = divmod(i, cols)
        places.append((xs[c] + (col_w[c] - w) // 2,
                       ys[r] + (row_h[r] - h) // 2))

    total_w = sum(col_w) + gap * (cols - 1)
    total_h = sum(row_h) + gap * (rows - 1)
    return total_w, total_h, places


def compose(images, gap, cols, bg=(0, 0, 0)):
    """Paste `images` onto one canvas using grid_geometry."""
    total_w, total_h, places = grid_geometry([im.size for im in images], gap, cols)
    canvas = Image.new("RGB", (max(total_w, 1), max(total_h, 1)), bg)
    for im, (x, y) in zip(images, places):
        canvas.paste(im.convert("RGB"), (x, y))
    return canvas


def natural_key(path):
    """Sort key so page2 lands before page10."""
    name = os.path.basename(path).lower()
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


def shorten(stem, limit=NAME_PART_LIMIT):
    """Over the limit, keep head and tail — page numbers live at the end."""
    if len(stem) <= limit:
        return stem
    half = limit // 2
    return stem[:half] + stem[-half:]


# --------------------------------------------------------------------------

class Item:
    """One loaded image plus its rotation state."""

    def __init__(self, path, image):
        self.path = path
        self.image = image      # EXIF-corrected original, never mutated
        self.rot = 0            # clockwise degrees

    def oriented(self):
        return self.image if self.rot == 0 else self.image.rotate(-self.rot, expand=True)


class StitcherApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("940x760")
        self.minsize(760, 620)
        self.configure(bg=BG)

        self.items = []
        self.selected = None
        self.mode_var = tk.StringVar(value="row")
        self.cols_var = tk.IntVar(value=2)
        self.gap_var = tk.IntVar(value=0)
        self.reverse_var = tk.BooleanVar(value=False)

        self._preview_photo = None
        self._thumb_photos = {}
        self._scaled_cache = {}
        self._pending = None

        self._build_preview()
        self._build_filmstrip()
        self._build_controls()

        self.bind("<Delete>", lambda e: self.remove_selected())
        self.bind("r", lambda e: self.rotate_selected())
        self.refresh()

    # ---------------- UI construction ----------------
    def _build_preview(self):
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(padx=16, pady=(14, 6))
        self.canvas = tk.Canvas(wrap, width=PREVIEW_W, height=PREVIEW_H,
                                bg="#1e1e1e", highlightthickness=1,
                                highlightbackground="#555")
        self.canvas.pack()
        self.canvas.drop_target_register(DND_FILES)
        self.canvas.dnd_bind("<<Drop>>", self.on_drop)
        self.canvas.bind("<Double-Button-1>", lambda e: self.add_files())

        self.dim_label = tk.Label(self, text="", bg=BG, fg="#9a9a9a",
                                  font=("Segoe UI", 9))
        self.dim_label.pack()

    def _build_filmstrip(self):
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="x", padx=16, pady=(8, 4))

        self.strip_canvas = tk.Canvas(wrap, height=THUMB + 26, bg=BG,
                                      highlightthickness=0)
        hbar = tk.Scrollbar(wrap, orient="horizontal",
                            command=self.strip_canvas.xview)
        self.strip_canvas.configure(xscrollcommand=hbar.set)
        self.strip_canvas.pack(fill="x")
        hbar.pack(fill="x")

        self.strip = tk.Frame(self.strip_canvas, bg=BG)
        self.strip_canvas.create_window((0, 0), window=self.strip, anchor="nw")
        self.strip.bind("<Configure>", lambda e: self.strip_canvas.configure(
            scrollregion=self.strip_canvas.bbox("all")))
        for w in (self.strip_canvas, self.strip):
            w.drop_target_register(DND_FILES)
            w.dnd_bind("<<Drop>>", self.on_drop)

    def _build_controls(self):
        bar = tk.Frame(self, bg=BG)
        bar.pack(pady=(4, 2))
        for text, cmd in (("◀ Move", self.move_left), ("⟳ Rotate", self.rotate_selected),
                          ("✕ Remove", self.remove_selected), ("Move ▶", self.move_right)):
            tk.Button(bar, text=text, command=cmd, font=("Segoe UI", 9),
                      width=10).pack(side="left", padx=3)

        layout = tk.Frame(self, bg=BG)
        layout.pack(pady=(10, 2))
        tk.Label(layout, text="Layout:", bg=BG, fg="white",
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 6))
        for label, value in (("Row", "row"), ("Column", "column"), ("Grid", "grid")):
            tk.Radiobutton(layout, text=label, value=value, variable=self.mode_var,
                           command=self.refresh, bg=BG, fg="white", selectcolor="#1e1e1e",
                           activebackground=BG, activeforeground="white",
                           font=("Segoe UI", 9)).pack(side="left")
        tk.Label(layout, text="  Columns:", bg=BG, fg="white",
                 font=("Segoe UI", 9)).pack(side="left")
        tk.Spinbox(layout, from_=1, to=12, width=3, textvariable=self.cols_var,
                   command=self.refresh, font=("Segoe UI", 9)).pack(side="left", padx=4)
        tk.Checkbutton(layout, text="Reverse order", variable=self.reverse_var,
                       command=self.refresh, bg=BG, fg="white", selectcolor="#1e1e1e",
                       activebackground=BG, activeforeground="white",
                       font=("Segoe UI", 9)).pack(side="left", padx=(12, 0))

        self.slider = tk.Scale(self, from_=0, to=500, orient="horizontal",
                               label="Black Bar Width (Actual Pixels)",
                               variable=self.gap_var, command=self.on_gap,
                               bg=BG, fg="white", troughcolor="#1e1e1e",
                               highlightthickness=0, length=340)
        self.slider.pack(pady=(6, 4))

        actions = tk.Frame(self, bg=BG)
        actions.pack(pady=(0, 6))
        tk.Button(actions, text="Add Images…", command=self.add_files,
                  font=("Segoe UI", 10)).pack(side="left", padx=6)
        tk.Button(actions, text="Clear", command=self.clear_all,
                  font=("Segoe UI", 10)).pack(side="left", padx=6)
        tk.Button(actions, text="Stitch and Save", command=self.stitch_and_save,
                  bg=ACCENT, fg="white", font=("Segoe UI", 10, "bold"),
                  bd=0, padx=14, pady=5).pack(side="left", padx=6)

        tk.Label(self, text="Drag images anywhere  •  click a thumbnail to select  •  "
                            "R rotates, Delete removes",
                 bg=BG, fg="#7a7a7a", font=("Segoe UI", 8)).pack(pady=(0, 10))

    # ---------------- input ----------------
    def on_drop(self, event):
        try:
            files = [f for f in self.tk.splitlist(event.data) if f]
        except Exception:
            files = [event.data.strip("{}")]
        self.add_paths(sorted(files, key=natural_key))

    def add_files(self):
        paths = filedialog.askopenfilenames(filetypes=IMAGE_TYPES)
        if paths:
            self.add_paths(sorted(paths, key=natural_key))

    def add_paths(self, paths):
        failed = []
        for path in paths:
            try:
                img = ImageOps.exif_transpose(Image.open(path))
                img.load()
            except Exception:
                failed.append(os.path.basename(path))
                continue
            self.items.append(Item(path, img))
        if self.items and self.selected is None:
            self.selected = 0
        if failed:
            messagebox.showwarning("Skipped", "Could not load:\n" + "\n".join(failed))
        self.refresh()

    # ---------------- item operations ----------------
    def rotate_selected(self):
        if self.selected is None:
            return
        item = self.items[self.selected]
        item.rot = (item.rot + 90) % 360
        self.refresh()

    def remove_selected(self):
        if self.selected is None:
            return
        self.items.pop(self.selected)
        if not self.items:
            self.selected = None
        else:
            self.selected = min(self.selected, len(self.items) - 1)
        self.refresh()

    def move_left(self):
        self._move(-1)

    def move_right(self):
        self._move(1)

    def _move(self, delta):
        i = self.selected
        if i is None:
            return
        j = i + delta
        if 0 <= j < len(self.items):
            self.items[i], self.items[j] = self.items[j], self.items[i]
            self.selected = j
            self.refresh()

    def select(self, index):
        self.selected = index
        self.refresh()

    def clear_all(self):
        self.items.clear()
        self.selected = None
        self.refresh()

    # ---------------- composition ----------------
    def effective_cols(self):
        mode = self.mode_var.get()
        if mode == "column":
            return 1
        if mode == "grid":
            return max(1, self.cols_var.get())
        return max(1, len(self.items))

    def ordered(self):
        items = list(reversed(self.items)) if self.reverse_var.get() else self.items
        return [it.oriented() for it in items]

    def _scaled(self, images, scale):
        key = round(scale, 4)
        cache = self._scaled_cache.setdefault(key, {})
        out = []
        for idx, im in enumerate(images):
            hit = cache.get(idx)
            if hit is None or hit[0] is not im:
                small = im.resize((max(1, round(im.width * scale)),
                                   max(1, round(im.height * scale))), RESAMPLE)
                cache[idx] = (im, small)
                hit = cache[idx]
            out.append(hit[1])
        return out

    # ---------------- rendering ----------------
    def on_gap(self, _=None):
        if self._pending:
            self.after_cancel(self._pending)
        self._pending = self.after(70, self.render_preview)

    def refresh(self):
        self._scaled_cache.clear()
        self.render_filmstrip()
        self.render_preview()

    def render_filmstrip(self):
        for child in self.strip.winfo_children():
            child.destroy()
        self._thumb_photos.clear()

        if not self.items:
            tk.Label(self.strip, text="No images yet — drag some in, or use Add Images…",
                     bg=BG, fg="#7a7a7a", font=("Segoe UI", 9)).pack(pady=24)
            return

        for i, item in enumerate(self.items):
            im = item.oriented().copy()
            im.thumbnail((THUMB, THUMB), RESAMPLE)
            photo = ImageTk.PhotoImage(im)
            self._thumb_photos[i] = photo

            cell = tk.Frame(self.strip, bg=ACCENT if i == self.selected else BG)
            cell.pack(side="left", padx=4, pady=4)
            lbl = tk.Label(cell, image=photo, bg=PANEL_BG, bd=0)
            lbl.pack(padx=2, pady=2)
            lbl.bind("<Button-1>", lambda e, n=i: self.select(n))
            lbl.bind("<Double-Button-1>", lambda e, n=i: (self.select(n),
                                                          self.rotate_selected()))
            tk.Label(cell, text=str(i + 1), bg=cell["bg"], fg="white",
                     font=("Segoe UI", 8)).pack()

    def render_preview(self):
        self.canvas.delete("all")
        images = self.ordered()
        if not images:
            self.canvas.create_text(PREVIEW_W // 2, PREVIEW_H // 2,
                                    text="Drag images here", fill="#666666",
                                    font=("Segoe UI", 14))
            self.dim_label.config(text="")
            return

        gap = self.gap_var.get()
        cols = self.effective_cols()
        full_w, full_h, _ = grid_geometry([im.size for im in images], gap, cols)
        scale = min(PREVIEW_W / full_w, PREVIEW_H / full_h, 1.0)

        preview = compose(self._scaled(images, scale), round(gap * scale), cols)
        self._preview_photo = ImageTk.PhotoImage(preview)
        self.canvas.create_image(PREVIEW_W // 2, PREVIEW_H // 2,
                                 image=self._preview_photo)
        self.dim_label.config(
            text=f"{len(images)} image{'s' if len(images) != 1 else ''}  →  "
                 f"{full_w} × {full_h} px   (preview at {scale * 100:.0f}%)")

    # ---------------- output ----------------
    def default_filename(self):
        stems = [os.path.splitext(os.path.basename(it.path))[0] for it in self.items]
        if len(stems) == 1:
            return f"{shorten(stems[0])}.png"
        name = f"{shorten(stems[0])}+{shorten(stems[-1])}"
        if len(stems) > 2:
            name += f"_{len(stems)}"
        return name + ".png"

    def stitch_and_save(self):
        if not self.items:
            messagebox.showwarning("Warning", "Add at least one image first.")
            return
        try:
            out = compose(self.ordered(), self.gap_var.get(), self.effective_cols())
            save_path = filedialog.asksaveasfilename(
                initialdir=os.path.dirname(self.items[0].path),
                initialfile=self.default_filename(),
                defaultextension=".png",
                filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg")],
            )
            if save_path:
                out.save(save_path)
                messagebox.showinfo("Success", f"Saved {out.width} × {out.height} image.")
        except MemoryError:
            messagebox.showerror("Error", "Out of memory — the combined image is too "
                                          "large. Try fewer or smaller images.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stitch images:\n{e}")


if __name__ == "__main__":
    StitcherApp().mainloop()
