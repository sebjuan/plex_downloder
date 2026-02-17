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

# Define the folder variable
folder = ""

LOG_FILE_PATH = Path(folder) / "mail_watcher_process_log.txt"

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

    # Check for rate limit or API errors
    if result.returncode != 0:
        error_output = result.stderr + result.stdout
        if "rate" in error_output.lower() or "403" in error_output or "limit" in error_output.lower():
            logger.info(f"spotdl failed with rate limit/API error")
            return False
        if "SpotifyException" in error_output or "user may not be registered" in error_output:
            logger.info(f"spotdl failed with Spotify API error")
            return False
        logger.info(f"spotdl failed with return code {result.returncode}")
        return False

    logger.info(f"spotdl completed successfully")
    return True


def try_yt_dlp_search(url, output_folder):
    """Method 3: Extract track info and search YouTube directly with yt-dlp"""
    logger.info("Trying Method 3: yt-dlp direct search")

    # Extract track/album ID from Spotify URL
    # For now, just try to search YouTube for the URL content
    # This is a fallback that may not work perfectly

    try:
        # Use yt-dlp to search YouTube Music
        cli_cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", f"{output_folder}/%(artist)s/%(album)s/%(track_number)s - %(title)s.%(ext)s",
            f"ytsearch:{url}",  # Search YouTube for the URL
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
