import imaplib
import email
from time import sleep

from pathlib import Path
import shutil
import subprocess
from datetime import datetime
import argparse
import sys

import logging

import os

cwd = os.getcwd()

# Use the script's directory for log file
SCRIPT_DIR = Path(__file__).parent.absolute()

LOG_FILE_PATH = SCRIPT_DIR / "mail_watcher_process_log.txt"

# Create a custom logger
logger = logging.getLogger("custom_logger")
logger.setLevel(logging.INFO)

# Create handlers
file_handler = logging.FileHandler(LOG_FILE_PATH)
console_handler = logging.StreamHandler()

# Create a formatter
formatter = logging.Formatter("%(asctime)s : %(message)s", datefmt="%m-%d %H:%M")

file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Configuration
IMAP_SERVER = "imap.gmail.com"
EMAIL = "plexspotdownloader@gmail.com"
PASSWORD = "xwiw vqgg hthn uuim"


def try_spotdl(url, output_folder):
    """Method 1: Try spotdl (Python)"""
    logger.info("Trying Method 1: spotdl (Python)")
    cli_cmd = [
        sys.executable,
        "-m",
        "spotdl",
        "download",
        url,
        "--output",
        f"{output_folder}/{{artist}}/{{album}}/{{track-number}} - {{title}}.{{output-ext}}",
    ]
    logger.info(f"Running: {' '.join(cli_cmd)}")
    try:
        result = subprocess.run(cli_cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        logger.info("spotdl timed out after 30s (likely rate limited)")
        return False

    # Log the output
    if result.stdout:
        logger.info(f"spotdl stdout: {result.stdout[:500]}")
    if result.stderr:
        logger.info(f"spotdl stderr: {result.stderr[:500]}")

    # Check for rate limit or API errors (even if return code is 0)
    all_output = (result.stderr or "") + (result.stdout or "")

    # Check for rate limit messages
    if "rate" in all_output.lower() and "limit" in all_output.lower():
        logger.info("spotdl hit rate limit (detected in output)")
        return False
    if "Retry will occur after" in all_output:
        logger.info("spotdl hit rate limit (retry message detected)")
        return False
    if "403" in all_output:
        logger.info("spotdl got 403 error")
        return False
    if "SpotifyException" in all_output or "user may not be registered" in all_output:
        logger.info("spotdl failed with Spotify API error")
        return False

    # Check return code
    if result.returncode != 0:
        logger.info(f"spotdl failed with return code {result.returncode}")
        return False

    logger.info("spotdl completed successfully")
    return True


def get_youtube_url_from_odesli(spotify_url):
    """Use Odesli/Songlink API to convert Spotify URL to YouTube URL"""
    import urllib.request
    import urllib.parse
    import json

    try:
        encoded_url = urllib.parse.quote(spotify_url, safe='')
        api_url = f"https://api.song.link/v1-alpha.1/links?url={encoded_url}"
        logger.info(f"Querying Odesli API: {api_url}")

        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())

        # Try to get YouTube Music URL first, then regular YouTube
        if 'linksByPlatform' in data:
            if 'youtubeMusic' in data['linksByPlatform']:
                return data['linksByPlatform']['youtubeMusic']['url']
            if 'youtube' in data['linksByPlatform']:
                return data['linksByPlatform']['youtube']['url']
        return None
    except Exception as e:
        logger.info(f"Odesli API error: {e}")
        return None


def get_spotify_anonymous_token():
    """Get an anonymous access token from Spotify's web player"""
    import urllib.request
    import json

    try:
        req = urllib.request.Request(
            "https://open.spotify.com/get_access_token?reason=transport&productType=web_player",
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return data.get('accessToken')
    except Exception as e:
        logger.info(f"Failed to get Spotify anonymous token: {e}")
        return None


def get_album_tracks_from_spotify(album_id):
    """Get track IDs from a Spotify album using anonymous web API"""
    import urllib.request
    import json

    token = get_spotify_anonymous_token()
    if not token:
        return []

    try:
        req = urllib.request.Request(
            f"https://api.spotify.com/v1/albums/{album_id}/tracks?limit=50",
            headers={
                'Authorization': f'Bearer {token}',
                'User-Agent': 'Mozilla/5.0'
            }
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())

        track_urls = []
        for item in data.get('items', []):
            track_id = item.get('id')
            if track_id:
                track_urls.append(f"https://open.spotify.com/track/{track_id}")

        logger.info(f"Found {len(track_urls)} tracks in album")
        return track_urls
    except Exception as e:
        logger.info(f"Failed to get album tracks: {e}")
        return []


def extract_spotify_id(url):
    """Extract the Spotify ID and type (track/album/playlist) from a URL"""
    import re
    # Clean URL parameters
    clean_url = url.split('?')[0]

    # Match patterns like /track/ID, /album/ID, /playlist/ID
    match = re.search(r'/(track|album|playlist)/([a-zA-Z0-9]+)', clean_url)
    if match:
        return match.group(1), match.group(2)
    return None, None


def download_track_via_yt_dlp(yt_url, output_folder):
    """Download a single track via yt-dlp"""
    cli_cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", f"{output_folder}/%(artist)s/%(album)s/%(track_number)s - %(title)s.%(ext)s",
        yt_url,
    ]
    logger.info(f"Downloading: {yt_url}")
    result = subprocess.run(cli_cmd, capture_output=True, text=True, timeout=300)
    if result.returncode == 0:
        return True
    if result.stderr:
        logger.info(f"yt-dlp error: {result.stderr[:200]}")
    return False


def try_yt_dlp_search(url, output_folder):
    """Method 2: Use Odesli API to get YouTube URL, then download via yt-dlp.
    For albums: extract track list via Spotify anonymous API, then convert each track."""
    logger.info("Trying Method 2: Odesli API + yt-dlp download")

    try:
        # Check if this is an album or playlist
        url_type, spotify_id = extract_spotify_id(url)
        logger.info(f"Detected Spotify {url_type}: {spotify_id}")

        if url_type == 'album':
            # Get all tracks from the album
            track_urls = get_album_tracks_from_spotify(spotify_id)
            if track_urls:
                logger.info(f"Processing {len(track_urls)} tracks from album")
                success_count = 0
                for i, track_url in enumerate(track_urls):
                    logger.info(f"Track {i+1}/{len(track_urls)}: {track_url}")
                    yt_url = get_youtube_url_from_odesli(track_url)
                    if yt_url:
                        if download_track_via_yt_dlp(yt_url, output_folder):
                            success_count += 1
                    else:
                        logger.info(f"Could not get YouTube URL for track {i+1}")
                    # Small delay to be nice to Odesli API
                    sleep(0.5)

                if success_count > 0:
                    logger.info(f"Album download: {success_count}/{len(track_urls)} tracks successful")
                    return True
                logger.info("Album download failed - no tracks downloaded")
            else:
                logger.info("Could not get track list from album")

        # For single tracks (or if album extraction failed)
        yt_url = get_youtube_url_from_odesli(url)
        if yt_url:
            logger.info(f"Got YouTube URL from Odesli: {yt_url}")
            if download_track_via_yt_dlp(yt_url, output_folder):
                logger.info("yt-dlp completed successfully")
                return True
            logger.info("yt-dlp download failed")

        # Fallback: try spotdl url command (may timeout if rate limited)
        logger.info("Trying spotdl url command for YouTube URLs...")
        info_cmd = [
            sys.executable,
            "-m",
            "spotdl",
            "url",
            url,
        ]
        info_result = subprocess.run(info_cmd, capture_output=True, text=True, timeout=30)

        # Extract YouTube URLs from spotdl output
        yt_urls = []
        for line in info_result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('http') and ('youtube.com' in line or 'youtu.be' in line):
                yt_urls.append(line)

        if yt_urls:
            logger.info(f"Found {len(yt_urls)} YouTube URLs from spotdl")
            success_count = 0
            for yt_url in yt_urls:
                if download_track_via_yt_dlp(yt_url, output_folder):
                    success_count += 1
            if success_count > 0:
                logger.info(f"yt-dlp downloaded {success_count}/{len(yt_urls)} tracks")
                return True

        logger.info("All fallback methods failed")
        return False
    except subprocess.TimeoutExpired:
        logger.info("Download timed out")
        return False
    except Exception as e:
        logger.info(f"yt-dlp fallback failed: {e}")
        return False


def process_email(subject, body, output_folder):
    """Define actions when an email is received. Try multiple download methods."""
    msg = f"New Email Received!\nSubject: {subject}\nBody: {body}"
    logger.info(msg)
    logger.info(f"Processing URL: {body}")

    # List of download methods to try in order
    methods = [
        ("spotdl", try_spotdl),
        ("yt-dlp search", try_yt_dlp_search),
    ]

    success = False
    for method_name, method_func in methods:
        try:
            logger.info(f"Attempting download with: {method_name}")
            if method_func(body, output_folder):
                logger.info(f"SUCCESS: Downloaded with {method_name}")
                success = True
                break
            else:
                logger.info(f"FAILED: {method_name} did not work, trying next method...")
        except Exception as e:
            logger.info(f"ERROR: {method_name} raised exception: {e}")
            continue

    if success:
        logger.info(f"Process completed successfully for {body}")
    else:
        logger.info(f"ALL METHODS FAILED for {body}")


def check_email(output_folder):
    """Check inbox for new emails."""
    with imaplib.IMAP4_SSL(IMAP_SERVER) as mail:
        logger.info(f"logging in as {EMAIL}")
        mail.login(EMAIL, PASSWORD)
        mail.select("inbox")

        result, data = mail.search(None, "(UNSEEN)")
        logger.info(f"searching for unseen emails: result={result}, data={data}")
        if result == "OK":
            for num in data[0].split():
                result, msg_data = mail.fetch(num, "(RFC822)")
                if result == "OK":
                    msg = email.message_from_bytes(msg_data[0][1])
                    subject = msg["subject"]
                    if msg.is_multipart():
                        body = msg.get_payload(0).get_payload(decode=True).decode()
                    else:
                        body = msg.get_payload(decode=True).decode()
                    process_email(subject, body.strip(), output_folder)
                    # Mark the email as seen
                    mail.store(num, "+FLAGS", "\\Seen")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mail watcher for Spotify downloader")
    parser.add_argument(
        "--output-folder",
        "-o",
        default="/srv/media/Music/",
        help="Output folder for downloaded music (default: /srv/media/Music/)",
    )
    args = parser.parse_args()

    logger.info(f"starting (cwd : {cwd})")
    logger.info(f"output folder: {args.output_folder}")
    check_email(args.output_folder)
