# Quick Image Stitcher

Combine any number of images onto one canvas with a configurable black
separator bar. Built for manga/comic page spreads and multi-page scans.

## Features

- Drag and drop any number of images (dropped batches sort naturally, so
  `page2` lands before `page10`)
- Three layouts: **Row**, **Column**, or **Grid** with an adjustable column count
- **Reverse order** toggle for right-to-left reading order
- Per-image 90 degree rotation; reorder or remove any image
- Black bar width set in *actual output pixels*, with a live preview rendered
  at true scale so what you see is what gets saved
- Images centred within their row/column, so mismatched page sizes do not
  produce a lopsided seam
- EXIF orientation respected on load
- Default filename combines the first and last image names

## Run from source

```
pip install pillow tkinterdnd2
python stitcher.py
```

Requires Python 3.10 or newer with Tk (the standard python.org installer
includes it).

## Build a Windows executable

Double-click `build.bat`, or run it from a terminal. Output lands in `dist\`.

Two notes on the build:

- `--collect-all tkinterdnd2` is mandatory. tkinterdnd2 wraps a compiled Tcl
  extension that PyInstaller's import scanner cannot see, so without that flag
  you get a clean build that dies at launch with a Tcl error.
- The script defaults to `--onedir` (a folder). Set `ONEFILE=1` at the top of
  `build.bat` for a single `.exe` instead — more portable, but slower to start
  and far more likely to trip antivirus heuristics.

## Keyboard

| Key | Action |
| --- | --- |
| `R` | Rotate the selected image 90 degrees |
| `Delete` | Remove the selected image |
| Double-click a thumbnail | Rotate it |
| Double-click the preview | Open the file browser |

## Licensing

This project is under the **Quick Image Stitcher Non-Commercial License**
(see `LICENSE.txt`). Free for personal, educational and non-profit use;
commercial use requires written permission.

Images you produce with it are entirely yours, with no restrictions.

Before distributing a build, run `python collect_licenses.py` to regenerate
`THIRD-PARTY-LICENSES.txt`. PyInstaller strips license text out of the
packages it bundles, and Pillow, tkinterdnd2, Python and Tcl/Tk all require
their notices to travel with the binary.

## Layout maths

`grid_geometry()` and `compose()` in `stitcher.py` are pure functions with no
Tk dependency, so the layout engine can be tested without a display. Columns
are sized independently — each column is as wide as its own widest image,
rather than every column matching the widest image overall.
