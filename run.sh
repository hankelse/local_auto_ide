#!/usr/bin/env bash
# Launch the editor using the project's virtual environment.
# The venv is built from a Homebrew Python with a modern Tcl/Tk (see README),
# which macOS's built-in Python lacks.
cd "$(dirname "$0")"
exec ./venv/bin/python main.py
