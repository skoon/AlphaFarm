"""Build a standalone AlphaFarm executable for the current platform.

PyInstaller cannot cross-compile: run this on Windows to get the Windows .exe and on
Linux to get the Linux binary. CI (.github/workflows/build.yml) does both automatically.

Usage:
    uv run --group build python build.py          # build dist/alphafarm[.exe]
    uv run --group build python build.py --zip     # also package a release archive
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "alphafarm"

PLATFORM_TAG = {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}.get(
    platform.system(), platform.system().lower()
)


def _add_data(src: str) -> str:
    # PyInstaller wants "SRC<sep>DEST"; the separator is os.pathsep (';' win, ':' posix).
    return f"{ROOT / src}{os.pathsep}{src}"


def build() -> Path:
    try:
        import PyInstaller.__main__ as pyi
    except ImportError:
        sys.exit(
            "PyInstaller is not installed. Run with the build group:\n"
            "    uv run --group build python build.py"
        )

    # Keep intermediate build artifacts out of the project root.
    work = ROOT / "build"
    dist = ROOT / "dist"

    args = [
        "main.py",
        "--name", APP_NAME,
        "--onefile",
        "--noconfirm",
        "--clean",
        "--windowed",                       # no console window (no-op on Linux)
        "--add-data", _add_data("data"),
        "--add-data", _add_data("assets"),
        "--exclude-module", "pytest",
        "--exclude-module", "tkinter",
        "--distpath", str(dist),
        "--workpath", str(work),
        "--specpath", str(work),
    ]
    print("Running PyInstaller:\n  " + " ".join(args) + "\n")
    pyi.run(args)

    exe_name = f"{APP_NAME}.exe" if PLATFORM_TAG == "windows" else APP_NAME
    exe_path = dist / exe_name
    if not exe_path.exists():
        sys.exit(f"Build finished but {exe_path} was not produced.")
    return exe_path


def make_archive(exe_path: Path) -> Path:
    """Bundle the binary (+ README) into a platform-tagged release archive."""
    staging = exe_path.parent / f"{APP_NAME}-{PLATFORM_TAG}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    shutil.copy2(exe_path, staging / exe_path.name)
    readme = ROOT / "README.md"
    if readme.exists():
        shutil.copy2(readme, staging / "README.md")

    fmt = "zip" if PLATFORM_TAG == "windows" else "gztar"
    archive = shutil.make_archive(str(staging), fmt, root_dir=staging.parent,
                                  base_dir=staging.name)
    shutil.rmtree(staging)
    return Path(archive)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", action="store_true",
                        help="also produce a platform-tagged release archive")
    opts = parser.parse_args()

    exe_path = build()
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"\nBuilt {exe_path}  ({size_mb:.1f} MB)")

    if opts.zip:
        archive = make_archive(exe_path)
        print(f"Packaged {archive}")


if __name__ == "__main__":
    main()
