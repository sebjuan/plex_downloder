#!/bin/bash

# chmod +x setup_spotdl.sh

# Name of the virtual environment
VENV_NAME="spotdl_venv"

# Create the virtual environment in the current folder if it doesn't exist
if [ ! -d "$VENV_NAME" ]; then
    echo "Virtual environment '$VENV_NAME' does not exist. Creating and setting up..."
    python3 -m venv "$VENV_NAME"
    echo "Virtual environment '$VENV_NAME' created in current folder."
    
    # Activate the virtual environment
    source "$VENV_NAME/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install dependencies from requirements.txt
    if [ -f "requirements.txt" ]; then
        echo "Installing dependencies from requirements.txt..."
        pip install -r requirements.txt
    else
        echo "requirements.txt not found, installing core dependencies..."
        # Fallback to manual installation
        pip install spotdl
        pip install -U yt-dlp
    fi
    
    # Download ffmpeg for spotdl if needed
    echo "Setting up spotdl..."
    python -m spotdl --download-ffmpeg
    
    # Deactivate the virtual environment
    deactivate
    
    echo "Setup complete. To use the venv, run:"
    echo "source $VENV_NAME/bin/activate"
else
    echo "Virtual environment '$VENV_NAME' already exists. Nothing to do."
    echo "To use the existing venv, run:"
    echo "source $VENV_NAME/bin/activate"
fi

echo "Setup complete. To use the venv, run:"
echo "source $VENV_NAME/bin/activate"