import os
from typing import List
import logging

from soulripper.utils import extract_file_metadata

from ..schemas import TrackData
from ..repositories import get_existing_track, add_track

logger = logging.getLogger(__name__)

# TODO: we need to refactor this function so that the only way it interacts with the database is through our crud package. 
# 

# TODO: this function technically kinda works but we need a better way to extract metadata from the files - most files (all downloaded by yt-dlp) have None for all fields except filepath :/
#   - maybe we can extract info from filename
#   - we should probably populate metadata using TrackData from database or Spotify API - this is a lot of work dgaf rn lol
def add_local_library_to_db(sql_session, music_dir: str, valid_extensions: List[str]):
    """
    Adds all songs in the music directory to the database

    Args:
        music_dir (str): the directory to add songs from
    """

    for root, dirs, files in os.walk(music_dir):
        for filename in files:
            file_extension = os.path.splitext(filename)[1]
            if file_extension in valid_extensions:
                filepath = os.path.abspath(os.path.join(root, filename))
                existing_track = get_existing_track(sql_session, TrackData(filepath=filepath))
                if existing_track is None:
                    add_local_track_to_db(sql_session, filepath)

def add_local_track_to_db(sql_session, filepath: str):
    if not os.path.exists(filepath):
        logger.warning(f"The file you tried to add ({filepath}) does not exist, skipping...")
        return

    file_track_data: TrackData = extract_file_metadata(filepath)

    if file_track_data is None:
        logger.info(f"No metadata found in file {filepath}, skipping...")
        file_track_data = TrackData(filepath=filepath, comments="WARNING: Error while extracting metadata. This likely means the file is corrupted or empty")

    logger.info(f"Found track with data: {file_track_data}, adding to database...")

    existing_track = get_existing_track(sql_session, file_track_data)
    if existing_track is None:
        add_track(sql_session, file_track_data)