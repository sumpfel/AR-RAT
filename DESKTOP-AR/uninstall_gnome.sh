#!/bin/bash
UUID="spherefocus@sumpfel.github.com"
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/$UUID"

echo "Uninstalling SphereFocus..."
gnome-extensions disable "$UUID"
rm -rf "$EXTENSION_DIR"

echo "Uninstalled. Please restart GNOME Shell."
