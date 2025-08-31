#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the script directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d "spotdl_venv" ]; then
    echo "Virtual environment not found. Please run setup_spotdl.sh first."
    exit 1
fi

# Activate the virtual environment
source spotdl_venv/bin/activate

# Run the mail watcher with the default output folder (/srv/media/Music/)
python mail_watcher.py --output-folder /srv/media/Music/

# Deactivate the virtual environment
deactivate
