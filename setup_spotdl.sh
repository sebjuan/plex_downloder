#!/bin/bash

# chmod +x setup_spotdl.sh

# Name of the virtual environment
VENV_NAME="spotdl_venv"

# Create the virtual environment in the current folder if it doesn't exist
if [ ! -d "$VENV_NAME" ]; then
    python3 -m venv "$VENV_NAME"
    echo "Virtual environment '$VENV_NAME' created in current folder."
else
    echo "Virtual environment '$VENV_NAME' already exists."
fi

# Activate the virtual environment
source "$VENV_NAME/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Install spotdl
pip install spotdl

pip install -U yt-dlp

# Deactivate the virtual environment
deactivate

echo "Setup complete. To use the venv, run:"
echo "source $VENV_NAME/bin/activate"