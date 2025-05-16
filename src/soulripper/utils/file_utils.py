import mutagen._file
from typing import Optional
import yaml
import json
import logging

from soulripper.database.schemas import TrackData
from soulripper.utils.app_params import AppParams

logger = logging.getLogger(__name__)

# TODO: look at metadata to see what else we can extract - it's different for each file :( - need to find file with great metadata as example
def extract_file_metadata(filepath: str) -> Optional[TrackData]:
    """
    Extracts metadata from a file using mutagen

    Args:
        filepath (str): the path to the file

    Returns:
        dict: a dictionary of metadata
    """

    try:
        file_metadata = mutagen._file.File(filepath)
    except Exception as e:
        logger.error(f"Error reading metadata of file {filepath}: {e}")
        return None

    if file_metadata:
        title = file_metadata.get("title", [None])[0]
        artists = file_metadata.get("artist", [None])[0]
        album = file_metadata.get("album", [None])[0]
        release_date = file_metadata.get("date", [None])[0]

        track_data = TrackData(
            filepath=filepath,
            title=title,
            artists=[(artist, None) for artist in artists.split(",")] if artists else [],
            album=album,
            release_date=release_date,
            spotify_id=None,
            explicit=None,
            comments=None
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
    DATABASE_PATH = config.get("paths", {}).get("database_path", "/home/soulripper/assets/soul.db")
    SOULSEEK_ONLY = config.get("download_behavior", {}).get("soulseek_only", False)
    YOUTUBE_ONLY = config.get("download_behavior", {}).get("youtube_only", False)
    YOUTUBE_COOKIE_FILEPATH = config.get("paths", {}).get("youtube_cookie_filepath", None)
    MAX_DOWNLOAD_RETRIES = config.get("download_behavior", {}).get("max_retries", 5)
    INACTIVE_DOWNLOAD_TIMEOUT = config.get("download_behavior", {}).get("inactive_download_timeout", 10)
    SPOTIFY_SCOPE = config.get("privacy", {}).get("spotify_scope", "user-library-read user-read-private playlist-read-collaborative playlist-read-private")
    LOG_ENABLED = config.get("debug", {}).get("log", False)
    LOG_FILEPATH = config.get("debug", {}).get("log_filepath", "/home/soulripper/debug/log.txt")
    DB_ECHO = config.get("debug", {}).get("db_echo", False)
    EXTENSIONS = config.get("audio", {}).get("valid_extensions", [".mp3", ".flac", ".wav"])
    LOG_LEVEL_STR = config.get("debug", {}).get("log_level", "INFO")

    match LOG_LEVEL_STR:
        case "DEBUG":
            LOG_LEVEL = logging.DEBUG
        case "INFO":
            LOG_LEVEL = logging.INFO
        case "WARNING":
            LOG_LEVEL = logging.WARNING
        case "ERROR":
            LOG_LEVEL = logging.ERROR
        case "CRITICAL":
            LOG_LEVEL = logging.CRITICAL
        case _:
            LOG_LEVEL = logging.INFO

    return AppParams(
        output_path=OUTPUT_PATH,
        database_path=DATABASE_PATH,
        soulseek_only=SOULSEEK_ONLY,
        youtube_only=YOUTUBE_ONLY,
        youtube_cookie_filepath=YOUTUBE_COOKIE_FILEPATH,
        max_download_retries=MAX_DOWNLOAD_RETRIES,
        inactive_download_timeout=INACTIVE_DOWNLOAD_TIMEOUT,
        spotify_scope=SPOTIFY_SCOPE,
        log_enabled=LOG_ENABLED,
        log_level=LOG_LEVEL,
        log_filepath=LOG_FILEPATH,
        db_echo=DB_ECHO,
        valid_music_extensions=EXTENSIONS,
    )