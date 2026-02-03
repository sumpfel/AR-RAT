#!/bin/bash

# Extension UUID must match metadata.json
UUID="spherefocus@sumpfel.github.com"
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/$UUID"
SOURCE_DIR=$(dirname "$(readlink -f "$0")")"/gnome-extension"

echo "Installing SphereFocus ($UUID)..."

# CLEAN INSTALL: Remove existing directory
if [ -d "$EXTENSION_DIR" ]; then
    echo "removing old installation..."
    rm -rf "$EXTENSION_DIR"
fi

# Create destination directory
mkdir -p "$EXTENSION_DIR"

# Copy files
cp -r "$SOURCE_DIR"/* "$EXTENSION_DIR"/

echo "Files copied to $EXTENSION_DIR"

# Enable extension
echo "Enabling extension..."
gnome-extensions enable "$UUID"

echo "--------------------------------------------------------"
echo "Installation Complete!"
echo "If this is the first install, you MUST restart GNOME Shell:"
echo "  - Wayland: Log out and Log in."
echo "  - X11: Press Alt+F2, type 'r', and hit Enter."
echo "--------------------------------------------------------"
