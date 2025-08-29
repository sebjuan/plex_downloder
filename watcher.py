###################################################################
## NOTE  rm -df ~/.spotdl/ and then spotdl --download-ffmpeg   
# 
# 
# pip install -U yt-dlp
# 
# ####
###################################################################
from pathlib import Path
import shutil  # For moving files
import subprocess
from datetime import datetime

import logging

import os
cwd = os.getcwd()


# Define the folder variable
#folder = "/DATA/Media/Music/spotify_albums_links"
folder = ""
#destination_folder = folder  

# Path to the links, downloaded links, and log files
LINKS_FILE_PATH = Path(folder) / "links.txt"
DONLOADED_LINKS_FILEPATH = Path(folder) / "downloaded_links.txt"
LOG_FILE_PATH = Path(folder) / "process_log.txt"

# Create a custom logger
logger = logging.getLogger("custom_logger")
logger.setLevel(logging.INFO)

# Create handlers
file_handler = logging.FileHandler(LOG_FILE_PATH)  # Log to a file
console_handler = logging.StreamHandler()  # Log to the console

# Create a formatter
formatter = logging.Formatter('%(asctime)s : %(message)s', datefmt='%m-%d %H:%M')

file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)


# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)



def read_links(links_file_path=LINKS_FILE_PATH):
    with links_file_path.open('r') as f:
        return [l.strip() for l in f.readlines()]

def update_links(links,links_file_path=LINKS_FILE_PATH):
    with links_file_path.open('w') as f:
        f.writelines(links)

def write_links(links,links_file_path=DONLOADED_LINKS_FILEPATH):
    with links_file_path.open('a') as f:
        f.writelines([l + "\n" for l in links])



# STARTING
logger.info(f"starting (cwd : {cwd})")

# READ LINKS
link_file_lines = read_links()
logger.info(f"found {len(link_file_lines)} links")


original_links = set(link_file_lines)
downloaded_links = set()

# Process each link
for url in link_file_lines:
    if not url:
        # STARTING
        logger.info("Missing URL in link entry")
        continue

    logger.info(f"Processing URL: {url}")
    cli_cmd = ["python", "-m", "spotdl", "--output", "'{artist}/{album}/{track-number} - {title}.{output-ext}'", url]
    #cli_cmd = ["python3", "-m", "spotdl", "--output", "{artist}/{album}/{track-number} - {title}.{output-ext}", url]
    logger.info(f"Running {cli_cmd}")

    result = subprocess.run(cli_cmd)#, cwd=folder)

    print(f"result : {result}")

    # Check if the subprocess completed successfully
    if result.returncode == 0:
        logger.info(f"Process completed successfully for {url}")
        downloaded_links.add(url)
        write_links(url)
    
    else:
        logger.info(f"Process failed with return code {result.returncode} for {url}")



links_not_downloaded = original_links - downloaded_links

print(downloaded_links)
print(links_not_downloaded)

update_links(links_not_downloaded)
# cli_cmd = ["/DATA/Media/Music/spotify_albums_links/spotdl_venv/bin/python3",  "-m",  "spotdl", "--output",  "{artist}/{album}/{track-number} - {title}.{output-ext}", url]
