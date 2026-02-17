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


def try_yt_dlp_search(url, output_folder):
    """Method 2: Use spotdl to get track info, then download via yt-dlp YouTube search"""
    logger.info("Trying Method 2: spotdl info + yt-dlp download")

    try:
        # First, use spotdl to get track info (doesn't hit rate limit as hard)
        info_cmd = [
            sys.executable,
            "-m",
            "spotdl",
            "url",
            url,
        ]
        logger.info(f"Getting track info: {' '.join(info_cmd)}")
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
                    success_count += 1
            if success_count > 0:
                logger.info(f"yt-dlp downloaded {success_count}/{len(yt_urls)} tracks")
                return True

        # Fallback: try YouTube search with the URL as query (may not work well)
        logger.info("No YouTube URLs from spotdl, trying direct YouTube search")
        cli_cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", f"{output_folder}/%(artist)s/%(album)s/%(track_number)s - %(title)s.%(ext)s",
            f"ytsearch:{url}",
        ]
        logger.info(f"Running: {' '.join(cli_cmd)}")
        result = subprocess.run(cli_cmd, capture_output=True, text=True, timeout=300)
        if result.stdout:
            logger.info(f"yt-dlp stdout: {result.stdout[:500]}")
        if result.stderr:
            logger.info(f"yt-dlp stderr: {result.stderr[:500]}")
        if result.returncode == 0:
            logger.info("yt-dlp completed successfully")
            return True
        logger.info(f"yt-dlp failed with return code {result.returncode}")
        return False
    except subprocess.TimeoutExpired:
        logger.info("yt-dlp timed out")
        return False
    except Exception as e:
        logger.info(f"yt-dlp search failed: {e}")
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
