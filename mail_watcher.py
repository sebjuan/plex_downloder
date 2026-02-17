import imaplib
import email
from time import sleep

from pathlib import Path
import shutil  # For moving files
import subprocess
from datetime import datetime
import argparse
import sys

import logging

import os

cwd = os.getcwd()


# Define the folder variable
# folder = "/DATA/Media/Music/spotify_albums_links"
folder = ""
# destination_folder = folder

# Path to the links, downloaded links, and log files
# LINKS_FILE_PATH = Path(folder) / "links.txt"
# DONLOADED_LINKS_FILEPATH = Path(folder) / "downloaded_links.txt"
LOG_FILE_PATH = Path(folder) / "mail_watcher_process_log.txt"

# Create a custom logger
logger = logging.getLogger("custom_logger")
logger.setLevel(logging.INFO)

# Create handlers
file_handler = logging.FileHandler(LOG_FILE_PATH)  # Log to a file
console_handler = logging.StreamHandler()  # Log to the console

# Create a formatter
formatter = logging.Formatter("%(asctime)s : %(message)s", datefmt="%m-%d %H:%M")

file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)


# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)


# Configuration
IMAP_SERVER = "imap.gmail.com"  # Replace with your email provider's IMAP server
EMAIL = "plexspotdownloader@gmail.com"
PASSWORD = "xwiw vqgg hthn uuim"
# CHECK_INTERVAL = 30  # Seconds


def process_email(subject, body, output_folder):
    """Define actions when an email is received."""
    msg = f"New Email Received!\nSubject: {subject}\nBody: {body}"
    logger.info(msg)
    logger.info(f"Processing URL: {body}")

    cli_cmd = [
        sys.executable,
        "-m",
        "spotdl",
        "download",
        body,
        "--output",
        f"{output_folder}/{{artist}}/{{album}}/{{track-number}} - {{title}}.{{output-ext}}",
    ]

    """cli_cmd = [
        "python",
        "-m",
        "spotdl",
        "download",  # operation must come first
        body,  # Spotify URL
        "--output",
        "{artist}/{album}/{track-number} - {title}.{output-ext}",  # no extra quotes
        #"--lyrics-provider",
        "None",  # split into separate elements
    ]"""

    # cli_cmd = ["python3", "-m", "spotdl", "--output", "{artist}/{album}/{track-number} - {title}.{output-ext}", url]
    logger.info(f"Running {cli_cmd}")

    result = subprocess.run(cli_cmd)  # , cwd=folder)

    print(f"result : {result}")

    # Check if the subprocess completed successfully
    if result.returncode == 0:
        logger.info(f"Process completed successfully for {body}")

    else:
        logger.info(f"Process failed with return code {result.returncode} for {body}")


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
