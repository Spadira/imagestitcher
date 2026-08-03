"""
Generate THIRD-PARTY-LICENSES.txt by harvesting license files from the Python
environment this script runs in.

PyInstaller strips license text out of the packages it bundles, which leaves a
distributed .exe technically in breach of the (otherwise very permissive)
terms of Pillow, tkinterdnd2, Python and Tcl/Tk. Run this before shipping and
put the generated file next to the executable.

    python collect_licenses.py

Nothing here is copied from the internet: it reads the exact license text that
your installed packages shipped with, so it always matches the versions you
are actually bundling.
"""

import os
import sys
import sysconfig
from datetime import date

COMPONENTS = [
    ("Pillow", "pillow", "MIT-CMU", "https://python-pillow.github.io/"),
    ("tkinterdnd2", "tkinterdnd2", "MIT", "https://github.com/Eliav2/tkinterdnd2"),
    ("tkDnD", "tkinterdnd2", "BSD-style (George Petasis)",
     "https://github.com/petasis/tkdnd"),
]
LICENSE_NAMES = ("license", "licence", "copying", "notice", "license.terms")
OUTPUT = "THIRD-PARTY-LICENSES.txt"


def is_license_file(name):
    stem = name.lower()
    return any(stem.startswith(n) for n in LICENSE_NAMES)


def find_dist_info(dist_name):
    """Locate the *.dist-info directory for an installed distribution."""
    for root in sys.path:
        if not root or not os.path.isdir(root):
            continue
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for entry in entries:
            low = entry.lower()
            if low.endswith((".dist-info", ".egg-info")) and \
                    low.split("-")[0].replace("_", "") == dist_name.replace("-", ""):
                return os.path.join(root, entry)
    return None


def texts_from(directory):
    """Return [(filename, text), ...] for license-ish files under directory."""
    found = []
    if not directory or not os.path.isdir(directory):
        return found
    for dirpath, _dirnames, filenames in os.walk(directory):
        for name in filenames:
            if is_license_file(name):
                path = os.path.join(dirpath, name)
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as fh:
                        body = fh.read().strip()
                except OSError:
                    continue
                if body:
                    found.append((path, body))
    return found


def python_and_tk():
    """Python's own LICENSE.txt, which on Windows also covers bundled Tcl/Tk."""
    candidates = [
        os.path.join(sys.base_prefix, "LICENSE.txt"),
        os.path.join(sysconfig.get_path("stdlib"), "LICENSE.txt"),
        os.path.join(sys.base_prefix, "lib", "LICENSE.txt"),
    ]
    tcl = os.path.join(sys.base_prefix, "tcl")
    results = []
    for path in candidates:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                results.append((path, fh.read().strip()))
            break
    results.extend(texts_from(tcl))
    return results


def main():
    blocks = []
    missing = []

    for label, dist, spdx, url in COMPONENTS:
        info = find_dist_info(dist)
        found = texts_from(info)
        if not found:
            pkg_dir = None
            for root in sys.path:
                candidate = os.path.join(root or "", dist)
                if os.path.isdir(candidate):
                    pkg_dir = candidate
                    break
            found = texts_from(pkg_dir)
        if found:
            seen = set()
            for path, body in found:
                if body in seen:
                    continue
                seen.add(body)
                blocks.append((f"{label} ({spdx})\n{url}\nsource: {path}", body))
        else:
            missing.append(f"{label} ({spdx}) — {url}")

    for path, body in python_and_tk():
        blocks.append((f"Python / Tcl / Tk\nsource: {path}", body))
    if not any("Python" in head for head, _ in blocks):
        missing.append("Python and Tcl/Tk — https://docs.python.org/3/license.html")

    lines = [
        "THIRD-PARTY LICENSES",
        f"Generated {date.today().isoformat()} from {sys.version.split()[0]} "
        f"at {sys.base_prefix}",
        "",
        "This application bundles the components below. They are licensed by",
        "their own authors under their own terms, reproduced verbatim here.",
        "",
        "PyInstaller itself is GPL 2.0 with the Bootloader Exception, which",
        "expressly permits distributing bundles built from your own source",
        "under any license you choose. Its text is not required here unless",
        "you have modified and redistributed PyInstaller itself.",
        "",
    ]
    for head, body in blocks:
        lines += ["=" * 74, head, "=" * 74, "", body, "", ""]

    if missing:
        lines += ["=" * 74,
                  "NOT FOUND — add these manually before distributing:",
                  "=" * 74, ""]
        lines += [f"  - {m}" for m in missing]
        lines.append("")

    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"Wrote {OUTPUT} with {len(blocks)} license block(s).")
    if missing:
        print("\nWARNING — could not locate license text for:")
        for m in missing:
            print(f"  - {m}")
        print("\nFetch these from the project pages listed and paste them in.")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
