#!/bin/bash
# Forces Qt to use X11 (xcb) if Wayland plugin is missing
export QT_QPA_PLATFORM=xcb
python3 main.py "$@"
