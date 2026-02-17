#!/bin/bash
# Pi Startup Script - Clone repo, setup venv, configure cron
# Run this at boot via systemd

set -e

REPO_URL="https://github.com/sebjuan/plex_downloder.git"
INSTALL_DIR="/home/seb/plex_downloader"
MUSIC_OUTPUT="/mnt/media/Music"
VENV_NAME="spotdl_venv"
LOG_FILE="/home/seb/plex_downloader_startup.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "=== Starting plex_downloader setup ==="

# Remove old installation and clone fresh
if [ -d "$INSTALL_DIR" ]; then
    log "Removing old installation..."
    rm -rf "$INSTALL_DIR"
fi

log "Cloning fresh repo from $REPO_URL..."
git clone "$REPO_URL" "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Setup virtual environment (always create fresh - cloned venv is macOS-specific)
log "Setting up virtual environment..."
rm -rf "$VENV_NAME"
python3 -m venv "$VENV_NAME"
log "Virtual environment created"

# Use venv's pip directly (avoids externally-managed-environment issues)
VENV_PIP="$INSTALL_DIR/$VENV_NAME/bin/pip"
VENV_PYTHON="$INSTALL_DIR/$VENV_NAME/bin/python"

log "Installing dependencies..."
"$VENV_PIP" install --upgrade pip -q
if [ -f "requirements.txt" ]; then
    "$VENV_PIP" install -r requirements.txt -q
else
    "$VENV_PIP" install spotdl -q
    "$VENV_PIP" install -U yt-dlp -q
fi

# Setup ffmpeg for spotdl (only if not already done)
if ! "$VENV_PYTHON" -m spotdl --help > /dev/null 2>&1; then
    log "Setting up spotdl ffmpeg..."
    "$VENV_PYTHON" -m spotdl --download-ffmpeg
fi

# Setup cron job (every 3 minutes)
CRON_CMD="*/3 * * * * cd $INSTALL_DIR && $INSTALL_DIR/$VENV_NAME/bin/python mail_watcher.py -o $MUSIC_OUTPUT >> /home/seb/mail_watcher_cron.log 2>&1"

log "Setting up cron job..."
# Remove old cron entries for this script and add new one
(crontab -l 2>/dev/null | grep -v "mail_watcher.py"; echo "$CRON_CMD") | crontab -

log "Cron job configured: every 3 minutes"
log "Music output folder: $MUSIC_OUTPUT"
log "=== Setup complete ==="

# Run once immediately
log "Running mail_watcher once now..."
cd "$INSTALL_DIR"
"$INSTALL_DIR/$VENV_NAME/bin/python" mail_watcher.py -o "$MUSIC_OUTPUT" || true

log "Done!"
