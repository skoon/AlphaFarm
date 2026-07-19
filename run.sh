#!/usr/bin/env bash
# Launcher for WSL/Linux shells.
#
# The project's main .venv is Windows-format (created by uv on Windows). If uv
# under WSL touches it, it tries to tear it down and rebuild it as a Linux venv
# and fails with "Input/output error (os error 5)" — corrupting the Windows venv
# in the process. This script points WSL's uv at its own separate environment
# (.venv-wsl) so the two never collide.
#
# Note: the window opens via WSLg; running natively on Windows (PowerShell:
# `uv run python main.py`) is smoother.
cd "$(dirname "$0")" || exit 1
export UV_PROJECT_ENVIRONMENT=.venv-wsl
exec uv run python main.py "$@"
