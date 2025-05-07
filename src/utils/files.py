import mutagen
import json

from database.schemas.track import TrackData

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

