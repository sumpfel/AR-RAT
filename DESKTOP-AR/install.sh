#!/bin/bash
set -e

echo "Setting up DESKTOP-AR..."

# Create venv if not exists
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

# Install dependencies
./.venv/bin/pip install pygame PyOpenGL PyOpenGL_accelerate numpy

echo "Setup complete. Run with: ./.venv/bin/python main.py"
