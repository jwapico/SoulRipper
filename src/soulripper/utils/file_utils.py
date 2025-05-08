import mutagen
import yaml
import json

from soulripper.database.schemas import TrackData
from soulripper.utils.app_params import AppParams

# TODO: look at metadata to see what else we can extract - it's different for each file :( - need to find file with great metadata as example
def extract_file_metadata(filepath: str) -> TrackData:
    """
    Extracts metadata from a file using mutagen

    Args:
        filepath (str): the path to the file

    Returns:
        dict: a dictionary of metadata
    """

    try:
        file_metadata = mutagen.File(filepath)
    except Exception as e:
        print(f"Error reading metadata of file {filepath}: {e}")
        return None

    if file_metadata:
        title = file_metadata.get("title", [None])[0]
        artists = file_metadata.get("artist", [None])[0]
        album = file_metadata.get("album", [None])[0]
        release_date = file_metadata.get("date", [None])[0]

        track_data = TrackData(
            filepath=filepath,
            title=title,
            artists=[(artist, None) for artist in artists.split(",")] if artists else [(None, None)],
            album=album,
            release_date=release_date,
            spotify_id=None
        )

        return track_data

def save_json(data, filename="debug/debug.json"):
    with open(f"debug/{filename}", "w") as file:
        json.dump(data, file)

def extract_app_params(config_filepath: str) -> AppParams:
    with open(config_filepath, "r") as file:
        config = yaml.safe_load(file)

    if config is None:
        raise Exception("Error reading the config file: config is None")

    OUTPUT_PATH = config["paths"]["output_path"]
    SOULSEEK_ONLY = config["download_behavior"]["soulseek_only"]
    YOUTUBE_ONLY = config["download_behavior"]["youtube_only"]
    YOUTUBE_COOKIE_FILEPATH = config["paths"]["youtube_cookie_filepath"]
    MAX_DOWNLOAD_RETRIES = config["download_behavior"]["max_retries"]
    INACTIVE_DOWNLOAD_TIMEOUT = config["download_behavior"]["inactive_download_timeout"]
    SPOTIFY_SCOPE = config["privacy"]["spotify_scope"]
    LOG_ENABLED = config["debug"]["log"]
    LOG_FILEPATH = config["debug"]["log_filepath"]

    return AppParams(
        output_path=OUTPUT_PATH,
        soulseek_only=SOULSEEK_ONLY,
        youtube_only=YOUTUBE_ONLY,
        youtube_cookie_filepath=YOUTUBE_COOKIE_FILEPATH,
        max_download_retries=MAX_DOWNLOAD_RETRIES,
        inactive_download_timeout=INACTIVE_DOWNLOAD_TIMEOUT,
        spotify_scope=SPOTIFY_SCOPE,
        log_enabled=LOG_ENABLED,
        log_filepath=LOG_FILEPATH
    )