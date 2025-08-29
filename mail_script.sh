#!/bin/bash
cd /DATA/Media/Music/spotify_albums_links/
source spotdl_venv/bin/activate
python mail_watcher.py
deactivate
