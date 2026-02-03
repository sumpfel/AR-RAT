#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting AR-RAT Setup..."

# List of directories to set up
DIRS=("CAM-INPUT" "SENSORFUSION")

for dir in "${DIRS[@]}"; do
    echo "--------------------------------------------------"
    echo "Setting up $dir..."
    
    if [ -d "$dir" ]; then
        cd "$dir"
        
        # Create virtual environment if it doesn't exist
        if [ ! -d ".venv" ]; then
            echo "Creating virtual environment in $dir..."
            python3 -m venv .venv
        else
            echo "Virtual environment already exists in $dir."
        fi
        
        # Install requirements
        if [ -f "requirements.txt" ]; then
            echo "Installing requirements from requirements.txt..."
            ./.venv/bin/pip install --upgrade pip
            ./.venv/bin/pip install -r requirements.txt
        else
            echo "No requirements.txt found in $dir."
        fi
        
        cd ..
    else
        echo "Warning: Directory $dir not found!"
    fi
done

echo "--------------------------------------------------"
echo "Setup complete! You can now run the modules."
echo "To run CAM-INPUT: cd CAM-INPUT && ./.venv/bin/python main.py"
echo "To run SENSORFUSION: cd SENSORFUSION && ./.venv/bin/python main.py"
