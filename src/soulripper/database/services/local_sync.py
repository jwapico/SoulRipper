import os

from soulripper.utils import extract_file_metadata

from ..schemas import TrackData
from ..crud import get_existing_track, add_track

# TODO: this function technically kinda works but we need a better way to extract metadata from the files - most files (all downloaded by yt-dlp) have None for all fields except filepath :/
#   - maybe we can extract info from filename
#   - we should probably populate metadata using TrackData from database or Spotify API - this is a lot of work dgaf rn lol
def add_local_library_to_db(sql_session, music_dir: str):
    """
    Adds all songs in the music directory to the database

    Args:
        music_dir (str): the directory to add songs from
    """

    print(f"Scanning music library at {music_dir}...")

    for root, dirs, files in os.walk(music_dir):
        for file in files:
            # TODO: these extensions should be configured with the config file (still need to implement config file </3)
            if file.endswith(".mp3") or file.endswith(".flac") or file.endswith(".wav"):
                filepath = os.path.abspath(os.path.join(root, file))
                existing_track = get_existing_track(sql_session, TrackData(filepath=filepath))
                if existing_track is None:
                    add_local_track_to_db(sql_session, filepath)
                else:
                    print(f"track with filepath: {filepath} already found in database, skipping")
    sql_session.commit()

def add_local_track_to_db(sql_session, filepath: str):
    if not os.path.exists(filepath):
        print(f"File {filepath} does not exist, skipping...")
        return

    file_track_data: TrackData = extract_file_metadata(filepath)

    if file_track_data is None:
        print(f"No metadata found in file {filepath}, skipping...")
        file_track_data = TrackData(filepath=filepath, comments="WARNING: Error while extracting metadata. This likely means the file is corrupted or empty")

    print(f"Found track with data: {file_track_data}, adding to database...")

    existing_track = get_existing_track(sql_session, file_track_data)
    if existing_track is None:
        add_track(sql_session, file_track_data)
        sql_session.commit()