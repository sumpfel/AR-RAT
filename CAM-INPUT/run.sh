#!/bin/bash
# Forces Qt to use X11 (xcb) if Wayland plugin is missing
export QT_QPA_PLATFORM=xcb
./.venv/bin/python3 main.py "$@"
