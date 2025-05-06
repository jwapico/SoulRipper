from sqlalchemy.orm import Session
import sqlalchemy as sqla
from spotify_client import SpotifyClient
from typing import Tuple
import subprocess
import time
import re
import os
import json
import yaml
import argparse
import mutagen
import dotenv
import time

from slskd_utils import SlskdUtils
import souldb as SoulDB

# TODO's (~ roughly in order of importance):
#   - REFACTOR DOWNLOADING FUNCTIONS (in progress)
#       - we should populate the database with TrackData from spotify first, then download Null filepath entries after
#   - REFACTOR DATABASE CODE
#       - only call sql_session.commit() after a meaningful unit of work - atomicity
#       - we should also be wrapping ALL database operations in a try-except block, and calling sql_session.rollback() if we catch an exception
#       - we should prolly also remove the UserInfo table and stop storing api keys in the database lol
#   - better search and selection for soulseek AND yt-dlp given song title and artist
#   - better USER INTERFACE - GUI 
#       - some sort of config file for api keys, directory paths, etc
#       - we should keep a cli but make it better, the long flags are annoying as fuck
#           - maybe reimplement the infinite prompting thing from the submission
#       - we should have a way for the user to verify that each downloaded track is correct
#           - show them the target track (spotify data), and what was actually downloaded, filepath, metadata, etc
#           - allow them to change metadata fields
#           - walk them through each downloaded track in their library one by one
#       - basically just redesign spotify lmao - i want to be able to manipulate playlists and what not
#           - im pretty sure we have read write permissions for playlists
#           - better shuffle (can have multiple different options)
#           - more ways to sort
#           - more options for columns & data shown in playlist/album view
#           - tagging system
#           - theres also a way to stream songs directly from spotify??? 
#               - https://developer.spotify.com/documentation/web-playback-sdk
#           - if we are including a player (we should) we could record statistics (better than spotify)
#           - we could go very crazy with this
#               - could embed/display wikipedia data to make the experience educational ts
#                   - basically just include the sidebar on wikipedia that displays basic facts about the artist/album
#                   - https://en.wikipedia.org/api/rest_v1/
#                   - https://pypi.org/project/Wikipedia-API/ 
#               - weird idea for playlists: more than one song can follow another
#                   - basically playlists are trees now :o
#                   - ui would prolly be nested drop downs
#       - FLUTTER !!!
#           - https://docs.flutter.dev/
#           - https://docs.flutter.dev/get-started/codelab
#           - https://docs.flutter.dev/get-started/install/linux/web
#           - we should make sure we have the back end right before we start on the front end
#   - TODO.md file for project management and big plans
#       - talk to colton eoghan and other potential users about high level design
#   - youtube playlist functionality
#       - https://developers.google.com/youtube/v3/docs/playlists/list
#   - refactor date_liked_spotify out of the Tracks table, can get this info by looking at the date_added field of the SPOTIFY_LIKED_SONGS playlist
#       - although maybe we should keep it as a dedicated field if we feel that it is used often enough, running search queries each time could be cumbersome
#   - restructure this file - there are too many random ahh functions
#   - pass through ssh keys in docker so git works in vscode
#   - write an actual README.md
#   - better syncing with local music directory
#       - get a songs metadata using an api such as:
#           - https://www.discogs.com/developers/
#           - big list here: https://soundcharts.com/blog/music-data-api
#   - error handling in download functions and probably other places
#       - we can write error logging to the comment field of a track
#           - we should prollt create a seperate column for this
#   - virtualdj xml playlist integration (i already have code for this from a previous project i tihnk)
#   - parallelize downloads
#       - threading :D, i think slskd can also parallelize downloads, but it may be better to use threading, idk tho
#   - the print statements in lower level functions should be changed to logging/debug statements
#       - anytime a bare print statement & return None combo appears we should be writing whatever relevant data to a log file
#   - better print statements in download and search functions - should track progress (look at slskd data) instead of printing the state on a new line each time lol
#   - type annotations for ALL functions args and return values
#   - cleanup comments & add more

#   - this list is getting long as shit lmfao

# TODO: we should clean up main - move some shit into helper functions, also still need to restructure this file </3
def main():
    # collect commandline arguments
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("pos_output_path", nargs="?", default=os.getcwd(), help="The output directory in which your files will be downloaded")
    parser.add_argument("--output-path", type=str, dest="output_path", help="The output directory in which your files will be downloaded")
    parser.add_argument("--search-query", type=str, dest="search_query", help="The output directory in which your files will be downloaded")
    parser.add_argument("--playlist-url", type=str, dest="playlist_url", help="URL of Spotify playlist")
    parser.add_argument("--download-liked", action="store_true", help="Will download the database with all your liked songs from Spotify")
    parser.add_argument("--download-all-playlists", action="store_true", help="Will download the database with all your playlists from Spotify")
    parser.add_argument("--debug", action="store_true", help="Enable debug statements")
    parser.add_argument("--drop-database", action="store_true", help="Drop the database before running the program")
    parser.add_argument("--max-retries", type=int, default=5, help="The maximum number of retries for downloading a track")
    parser.add_argument("--add-track", type=str, help="Add a track to the database - provide the filepath")
    parser.add_argument("--yt", action="store_true", help="Download exclusively from Youtube")
    args = parser.parse_args()
    OUTPUT_PATH = os.path.abspath(args.output_path or args.pos_output_path)
    SEARCH_QUERY = args.search_query
    SPOTIFY_PLAYLIST_URL = args.playlist_url
    DOWNLOAD_LIKED = args.download_liked
    DOWNLOAD_ALL_PLAYLISTS = args.download_all_playlists
    DEBUG = args.debug
    DROP_DATABASE = args.drop_database
    # TODO: refactor code to use this value (i think its used in download_track only - will need to be passed down thru other functions tho - need to refactor this file for shared variables)
    MAX_RETRIES = args.max_retries
    NEW_TRACK_FILEPATH = args.add_track
    YOUTUBE_ONLY = args.yt

    CONFIG_FILEPATH = "/home/soulripper/config.yaml"
    load_config_file(CONFIG_FILEPATH)

    dotenv.load_dotenv()
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # connect to spotify API
    spotify_client = SpotifyClient(config_filepath=CONFIG_FILEPATH)

    # we communicate with slskd through port 5030, you can visit localhost:5030 to see the web front end. its at slskd:5030 in the docker container though
    SLSKD_API_KEY = os.getenv("SLSKD_API_KEY")
    slskd_client = SlskdUtils(SLSKD_API_KEY)

    # create the engine with the local soul.db file and create a session
    db_engine = sqla.create_engine("sqlite:///assets/soul.db", echo=DEBUG)
    sessionmaker = sqla.orm.sessionmaker(bind=db_engine)
    sql_session: Session = sessionmaker()

    # if the flag was provided drop everything in the database
    if DROP_DATABASE:
        if not DEBUG:
            input("Warning: This will drop all tables in the database. Press enter to continue...")

        metadata = sqla.MetaData()
        metadata.reflect(bind=db_engine)
        metadata.drop_all(db_engine)

    # initialize the tables defined in souldb.py
    SoulDB.Base.metadata.create_all(db_engine)

    # populate the database with metadata found from files in the users output directory
    scan_music_library(sql_session, OUTPUT_PATH)

    if NEW_TRACK_FILEPATH:
        add_new_track_to_db(sql_session, NEW_TRACK_FILEPATH)

    # if a search query is provided, download the track
    if SEARCH_QUERY:
        output_path = download_from_search_query(slskd_client, SEARCH_QUERY, OUTPUT_PATH, YOUTUBE_ONLY)
        # TODO: get metadata and insert into database

    # get all playlists from spotify and add them to the database
    if DOWNLOAD_ALL_PLAYLISTS:
        all_playlists_metadata = spotify_client.get_all_playlists()
        for playlist_metadata in all_playlists_metadata:
            update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata)

    # if the update liked flag is provided, download all liked songs from spotify
    if DOWNLOAD_LIKED:
        download_liked_songs(slskd_client, spotify_client, sql_session, OUTPUT_PATH, YOUTUBE_ONLY)
    
    # if a playlist url is provided, download the playlist
    if SPOTIFY_PLAYLIST_URL:
        # TODO: refactor this function
        # download_playlist(slskd_client, spotify_client, sql_session, SPOTIFY_PLAYLIST_URL, OUTPUT_PATH)
        pass

# ===========================================
#          main database functions
# ===========================================

# TODO: this function technically kinda works but we need a better way to extract metadata from the files - most files (all downloaded by yt-dlp) have None for all fields except filepath :/
#   - maybe we can extract info from filename
#   - we should probably populate metadata using TrackData from database or Spotify API - this is a lot of work dgaf rn lol
def scan_music_library(sql_session, music_dir: str):
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
                existing_track = SoulDB.get_existing_track(sql_session, SoulDB.TrackData(filepath=filepath))
                if existing_track is None:
                    add_new_track_to_db(sql_session, filepath)
                else:
                    print(f"track with filepath: {filepath} already found in database, skipping")
    sql_session.commit()

def add_new_track_to_db(sql_session, filepath: str):
    if not os.path.exists(filepath):
        print(f"File {filepath} does not exist, skipping...")
        return

    file_track_data: SoulDB.TrackData = extract_file_metadata(filepath)

    if file_track_data is None:
        print(f"No metadata found in file {filepath}, skipping...")
        file_track_data = SoulDB.TrackData(filepath=filepath, comments="WARNING: Error while extracting metadata. This likely means the file is corrupted or empty")

    print(f"Found track with data: {file_track_data}, adding to database...")

    existing_track = SoulDB.get_existing_track(sql_session, file_track_data)
    if existing_track is None:
        SoulDB.Tracks.add_track(sql_session, file_track_data)
        sql_session.commit()

def update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata):
    print(f"Updating database with tracks from playlist {playlist_metadata['name']}...")

    playlist_tracks = spotify_client.get_playlist_tracks(playlist_metadata['id'])
    relevant_tracks_data: list[SoulDB.TrackData] = spotify_client.get_data_from_playlist(playlist_tracks)

    # create and flush the playlist since we need its id for the playlist_tracks association table
    playlist_row = sql_session.query(SoulDB.Playlists).filter_by(spotify_id=playlist_metadata['id']).first()
    if playlist_row is None:
        playlist_row = SoulDB.Playlists.add_playlist(sql_session, playlist_metadata['id'], playlist_metadata['name'], playlist_metadata['description'])
        sql_session.add(playlist_row)
        sql_session.flush()

    # add each track in the playlist to the database if it doesn't already exist
    # for track_data in relevant_tracks_data:
    add_track_data_to_playlist(sql_session, relevant_tracks_data, playlist_row)
    sql_session.commit()

# TODO: this function takes a while to run, we should find a way to check if there any changes before calling it
def update_db_with_spotify_liked_tracks(spotify_client: SpotifyClient, sql_session):
    liked_tracks_data = spotify_client.get_liked_tracks()
    relevant_tracks_data: list[SoulDB.TrackData] = spotify_client.get_track_data_from_playlist(liked_tracks_data)

    liked_playlist = sql_session.query(SoulDB.Playlists).filter_by(name="SPOTIFY_LIKED_SONGS").first()
    if liked_playlist is None:
        liked_playlist = SoulDB.Playlists.add_playlist(sql_session, spotify_id=None, name="SPOTIFY_LIKED_SONGS", description="User liked songs on Spotify - This playlist is generated by SoulRipper")
        sql_session.add(liked_playlist)
        sql_session.flush()

    # add each track in the users liked songs to the database if it doesn't already exist
    add_track_data_to_playlist(sql_session, relevant_tracks_data, liked_playlist)

    sql_session.commit()
    return liked_playlist

# TODO: we should be using lists not sets, a playlist can have multiple identical tracks and thats okay
def add_track_data_to_playlist(sql_session, track_data_list: list[SoulDB.TrackData], playlist_row: SoulDB.Playlists):
    existing_spotify_ids = set(
        spotify_id for (spotify_id,) in sql_session.query(SoulDB.Tracks.spotify_id).filter(SoulDB.Tracks.spotify_id.isnot(None))
    )
    existing_non_spotify_tracks = set(
        (title, album, filepath) for (title, album, filepath) in sql_session.query(
            SoulDB.Tracks.title, SoulDB.Tracks.album, SoulDB.Tracks.filepath
        ).filter(SoulDB.Tracks.spotify_id.is_(None))
    )

    new_tracks = set()
    seen_spotify_ids = set()
    seen_non_spotify = set()

    for track_data in track_data_list:
        if track_data.spotify_id:
            if track_data.spotify_id in existing_spotify_ids or track_data.spotify_id in seen_spotify_ids:
                continue
            seen_spotify_ids.add(track_data.spotify_id)
        else:
            key = (track_data.title, track_data.album, track_data.filepath)
            if key in existing_non_spotify_tracks or key in seen_non_spotify:
                continue
            seen_non_spotify.add(key)
        new_tracks.add(track_data)
            
    SoulDB.Tracks.bulk_add_tracks(sql_session,new_tracks)
    
    existing_assoc_keys = set(
        (playlist_id, track_id)
        for playlist_id, track_id in sql_session.query(
            SoulDB.PlaylistTracks.playlist_id,
            SoulDB.PlaylistTracks.track_id
        ).all()
    )
    for track_data in track_data_list:
        track = SoulDB.get_existing_track(sql_session,track_data)
        if track:
            assoc = SoulDB.PlaylistTracks(track_id=track.id, playlist_id=playlist_row.id, added_at=track.date_liked_spotify)
            if (assoc.playlist_id, assoc.track_id) not in existing_assoc_keys:
                existing_assoc_keys.add(assoc)
                playlist_row.playlist_tracks.append(assoc)
        else:
            print("Error")

# ===========================================
#             downloading functions
# ===========================================

def download_liked_songs(slskd_client: SlskdUtils, spotify_client: SpotifyClient, sql_session: Session, output_path: str, youtube_only: bool):
    # TODO: this function takes a while to run, we should find a way to check if there any changes before calling it
    # add the users liked songs to the database
    liked_playlist = update_db_with_spotify_liked_tracks(spotify_client, sql_session)

    if liked_playlist is None:
        raise Exception("Error in update_db_with_spotify_liked_tracks(), the playlist row was not returned")
    
    liked_playlist_tracks_rows = sql_session.query(SoulDB.PlaylistTracks).filter_by(playlist_id=liked_playlist.id).all()

    try:
        # TODO: maybe we should be using the download_track function with a TrackData instead of the search query, hard to get TrackData though since also need to get artists
        #    - we should write a get_trackdata classmethod that will do all this for us
        for playlist_track_row in liked_playlist_tracks_rows:
            track_id = playlist_track_row.track_id
            track_row = sql_session.query(SoulDB.Tracks).filter_by(id=track_id).one()

            if track_row.filepath is None:
                track_artists_rows = sql_session.query(SoulDB.TrackArtist).filter_by(track_id=track_id).all()
                artist_rows = [sql_session.query(SoulDB.Artists).filter_by(id=track_artists_row.artist_id).one() for track_artists_row in track_artists_rows]
                track_artists = ", ".join([artist_row.name for artist_row in artist_rows])

                search_query = f"{track_row.title} - {track_artists}"

                filepath = download_from_search_query(slskd_client, search_query, output_path, youtube_only)
                track_row.filepath = filepath
                sql_session.commit()

    except Exception as e:
        sql_session.rollback()
        raise e
    
# TODO: bruhhhhhhhhhhh the spotify api current_user_saved_tracks() function doesn't return local files FUCK SPOTIFYU there has to be a workaround
def download_liked_tracks_from_spotify_data(slskd_client: SlskdUtils, spotify_client: SpotifyClient, sql_session, output_path: str):
    liked_tracks_data = spotify_client.get_liked_tracks()
    relevant_tracks_data: list[SoulDB.TrackData] = spotify_client.get_track_data_from_playlist(liked_tracks_data)

    track_rows_and_data = []
    for track in relevant_tracks_data:
        existing_track = SoulDB.get_existing_track(sql_session, track)
        if existing_track is None:
            filepath = download_track(slskd_client, track, output_path)
            track.filepath = filepath

            track_row = SoulDB.Tracks.add_track(sql_session, track)
            track_rows_and_data.append((track_row, track))

    existing_liked_playlist = sql_session.query(SoulDB.Playlists).filter_by(name="SPOTIFY_LIKED_SONGS")
    if existing_liked_playlist is None:
        SoulDB.Playlists.add_playlist(sql_session, spotify_id=None, name="SPOTIFY_LIKED_SONGS", description="User liked songs on Spotify - This playlist is generated by SoulRipper", track_rows_and_data=track_rows_and_data)

def download_playlist_from_spotify_url(slskd_client: SlskdUtils, spotify_client: SpotifyClient, sql_session, playlist_url: str, output_path: str):
    """
    Downloads a playlist from spotify

    Args:
        playlist_url (str): the url of the playlist
        output_path (str): the directory to download the songs to
    """

    playlist_id = spotify_client.get_playlist_id_from_url(playlist_url)
    playlist_tracks = spotify_client.get_playlist_tracks(playlist_id)
    playlist_info = spotify_client.get_playlist_info(playlist_id)

    output_path = os.path.join(output_path, playlist_info["name"])
    os.makedirs(output_path, exist_ok=True)

    relevant_tracks_data: list[SoulDB.TrackData] = spotify_client.get_track_data_from_playlist(playlist_tracks)

    track_rows_and_data = []
    for track_data in relevant_tracks_data:
        existing_track_row = SoulDB.get_existing_track(sql_session, track_data)
        # TODO: need better searching !
        if existing_track_row is None:
            filepath = download_track(slskd_client, track_data, output_path)
            track_data.filepath = filepath
            new_track_row = SoulDB.Tracks.add_track(sql_session, track_data)
            track_rows_and_data.append((new_track_row, track_data))
        else:
            print(f"Track ({track_data.title} - {track_data.artists}) already exists in the database, skipping download.")
            if existing_track_row.filepath is None:
                existing_track_row.filepath = download_track(slskd_client, track_data, output_path)
                sql_session.commit()
            track_rows_and_data.append((existing_track_row, track_data))
    # add the playlist to the database if it doesn't already exist
    existing_playlist = sql_session.query(SoulDB.Playlists).filter_by(spotify_id=playlist_id).first()
    if existing_playlist is None:
        SoulDB.Playlists.add_playlist(sql_session, playlist_id, playlist_info["name"], playlist_info["description"], track_rows_and_data)

# TODO: this is where better search will happen - construct query from trackdata
def download_track(slskd_client: SlskdUtils, track: SoulDB.TrackData, output_path: str) -> str:
    search_query = f"{track.title} - {', '.join([artist[0] for artist in track.artists])}"
    download_path = download_from_search_query(slskd_client, search_query, output_path)
    return download_path

# TODO: need to embed metadata into the file after it downloads
def download_track_ytdlp(search_query: str, output_path: str) -> str :
    """
    Downloads a track from youtube using yt-dlp
    
    Args:
        search_query (str): the query to search for
        output_path (str): the directory to download the song to

    Returns:
        str: the path to the downloaded song
    """

    # TODO: fix empty queries with non english characters ctrl f '大掃除' in sldl_helper.log 
    search_query = f"ytsearch:{search_query}".encode("utf-8").decode()
    ytdlp_output = ""

    print(f"Downloading from yt-dlp: {search_query}")

    # download the file using yt-dlp and necessary flags
    process = subprocess.Popen([
        "yt-dlp",
        search_query,
        # TODO: this should be better
        # "--cookies-from-browser", "firefox:~/snap/firefox/common/.mozilla/firefox/fpmcru3a.default",
        "--cookies", "assets/cookies.txt",
        "-x", "--audio-format", "mp3",
        "--embed-thumbnail", "--add-metadata",
        "--paths", output_path,
        "-o", "%(title)s.%(ext)s"
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    # print and append the output of yt-dlp to the log file
    for line in iter(process.stdout.readline, ''):
        print(line, end='')
        ytdlp_output += line

    process.stdout.close()
    process.wait()

    # this extracts the filepath of the new file from the yt-dlp output, TODO: theres prolly a better way to do this
    file_path_pattern = r'\[EmbedThumbnail\] ffmpeg: Adding thumbnail to "([^"]+)"'
    match = re.search(file_path_pattern, ytdlp_output)
    download_path = match.group(1) if match else ""

    return download_path

def download_from_search_query(slskd_client: SlskdUtils, search_query: str, output_path: str, youtube_only: bool) -> str:
    """
    Downloads a track from soulseek or youtube, only downloading from youtube if the query is not found on soulseek

    Args:
        search_query (str): the song to download, can be a search query
        output_path (str): the directory to download the song to

    Returns:
        str: the path to the downloaded file
    """
    if youtube_only:
        return download_track_ytdlp(search_query, output_path)

    download_path = slskd_client.download_track(search_query, output_path)

    if download_path is None:
        download_path = download_track_ytdlp(search_query, output_path)

    return download_path

# ===========================================
#             helper functions
# ===========================================

def pprint(data):
    print(json.dumps(data, indent=4))

def save_json(data, filename="debug/debug.json"):
    with open(f"debug/{filename}", "w") as file:
        json.dump(data, file)

def load_config_file(config_filepath: str) -> Tuple[str, int, bool, bool, str]:
    with open(config_filepath, "r") as file:
        config = yaml.safe_load(file)

    if config is None:
        raise Exception("Error reading the config file: config is None")

    OUTPUT_PATH = config["output_path"]
    MAX_RETRIES = config["download_behavior"]["max_retries"]
    YOUTUBE_ONLY = config["download_behavior"]["youtube_only"]
    LOG_ENABLED = config["debug"]["log"]
    LOG_FILEPATH = config["debug"]["log_filepath"]

    return (
        OUTPUT_PATH, 
        MAX_RETRIES, 
        YOUTUBE_ONLY, 
        LOG_ENABLED,
        LOG_FILEPATH
    )

# TODO: look at metadata to see what else we can extract - it's different for each file :( - need to find file with great metadata as example
def extract_file_metadata(filepath: str) -> SoulDB.TrackData:
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

        track_data = SoulDB.TrackData(
            filepath=filepath,
            title=title,
            artists=[(artist, None) for artist in artists.split(",")] if artists else [(None, None)],
            album=album,
            release_date=release_date,
            spotify_id=None
        )

        return track_data

# ===========================================
#       interesting and complex queries
# ===========================================

# TODO: we need to figure out which we want to keep and which are useless, we may also want to add more

def execute_all_interesting_queries(sql_session):
    input("Executing all interesting and complex queries, press enter to begin")

    get_missing_tracks(sql_session)
    input("Press enter to execute next query")
    get_tracks_by_artist(sql_session, "Kendrick Lamar")
    input("Press enter to execute next query")
    get_tracks_by_album(sql_session, "good kid, m.A.A.d city")
    input("Press enter to execute next query")
    get_favorite_artists(sql_session)
    input("Press enter to execute next query")
    get_num_unique_tracks(sql_session)
    input("Press enter to execute next query")
    get_num_unique_artists(sql_session)
    input("Press enter to execute next query")
    get_num_unique_albums(sql_session)
    input("Press enter to execute next query")
    get_favorite_tracks(sql_session)
    input("Press enter to execute next query")
    get_average_tracks_per_playlist(sql_session)
    input("Press enter to execute next query")
    get_playlists_with_above_avg_track_count(sql_session)
    input("Press enter to execute next query")
    get_top_3_tracks_per_artist(sql_session)

# Simple filter query
def get_missing_tracks(sql_session):
    query = """
    SELECT *
    FROM tracks
    WHERE filepath IS NULL;
    """

    result = sql_session.execute(sqla.text(query)).fetchall()
    print(f"Found {len(result)} missing tracks (filepath is null)")
    return result

# Join + filter
def get_tracks_by_artist(sql_session, artist_name):
    query = """
    SELECT t.*
    FROM tracks t
    JOIN track_artists ta ON t.id = ta.track_id
    JOIN artists a ON ta.artist_id = a.id
    WHERE a.name = :artist;
    """

    result = sql_session.execute(sqla.text(query), {"artist": artist_name}).fetchall()
    print(f"Found {len(result)} tracks by artist {artist_name}")
    return result

# Simple filter query
def get_tracks_by_album(sql_session, album_name):
    query = """
    SELECT *
    FROM tracks
    WHERE album = :album;
    """

    result = sql_session.execute(sqla.text(query), {"album": album_name}).fetchall()
    print(f"Found {len(result)} tracks in album {album_name}")
    return result

# Grouping & aggregation
def get_favorite_artists(sql_session):
    stmt = sqla.text("""
    SELECT
        a.name AS artist,
        COUNT(*) AS count
    FROM artists a
    JOIN track_artists ta ON a.id = ta.artist_id
    JOIN tracks t ON ta.track_id = t.id
    GROUP BY a.name
    ORDER BY count DESC
    LIMIT 10;
    """)

    result = sql_session.execute(stmt).fetchall()
    print(f"Top 10 favorite artists: {[result[0] for result in result]}")
    return result

# Aggregation
def get_num_unique_tracks(sql_session):
    query = """
    SELECT COUNT(DISTINCT title) AS count
    FROM tracks;
    """

    result = sql_session.execute(sqla.text(query)).fetchone()
    print(f"Number of unique tracks: {result[0]}")
    return result

# Aggregation
def get_num_unique_artists(sql_session):
    stmt = sqla.text("""
    SELECT
    COUNT(DISTINCT a.id) AS count
    FROM artists a;
    """)

    result = sql_session.execute(stmt).fetchone()
    print(f"Number of unique artists: {result[0]}")
    return result

# Aggregation
def get_num_unique_albums(sql_session):
    query = """
    SELECT COUNT(DISTINCT album) AS count
    FROM tracks;
    """

    result = sql_session.execute(sqla.text(query)).fetchone()
    print(f"Number of unique albums: {result[0]}")
    return result

# Grouping & aggregation
def get_favorite_tracks(sql_session):
    query = """
    SELECT
        t.title,
        COUNT(pt.playlist_id) AS num_playlists
    FROM tracks t
    LEFT JOIN playlist_tracks pt
    ON t.id = pt.track_id
    GROUP BY t.id, t.title
    ORDER BY num_playlists DESC
    LIMIT 10;
    """

    result = sql_session.execute(sqla.text(query)).fetchall()
    print(f"Top 10 favorite tracks: {[result[0] for result in result]}")
    return result

# Subquery
def get_average_tracks_per_playlist(sql_session):
    query = """
    SELECT AVG(sub.track_count) AS avg_tracks_per_playlist
        FROM (
            SELECT COUNT(*) AS track_count
            FROM playlist_tracks
            GROUP BY playlist_id
        ) AS sub;
    """

    result = sql_session.execute(sqla.text(query)).fetchone()
    print(f"Average number of tracks per playlist: {result[0]}")
    return result

# CTE 
def get_playlists_with_above_avg_track_count(sql_session):
    stmt = sqla.text("""
    WITH playlist_counts AS (
        SELECT
            playlist_id,
            COUNT(track_id) AS cnt
        FROM playlist_tracks
        GROUP BY playlist_id
    ), average_count AS (
        SELECT AVG(cnt) AS avg_cnt
        FROM playlist_counts
    )
    SELECT
        p.name AS playlist_name,
        pc.cnt AS track_count
    FROM playlist_counts pc
    JOIN playlists p
    ON p.id = pc.playlist_id
    CROSS JOIN average_count av
    WHERE pc.cnt > av.avg_cnt
    ORDER BY pc.cnt DESC;
    """)

    result = sql_session.execute(stmt).fetchall()
    print(f"Playlists with above-average track count: {[row.playlist_name for row in result]}")
    return result

# Window function
def get_top_3_tracks_per_artist(sql_session):
    start_time = time.perf_counter()
    stmt = sqla.text("""
    SELECT 
        artist_name,
        track_title,
        num_playlists
    FROM (
        SELECT
            a.name AS artist_name,
            t.title AS track_title,
            COUNT(pt.playlist_id) AS num_playlists,
            ROW_NUMBER() OVER (
                PARTITION BY a.id
                ORDER BY COUNT(pt.playlist_id) DESC
            ) AS rn
        FROM artists a
        JOIN track_artists ta ON a.id = ta.artist_id
        JOIN tracks t ON ta.track_id = t.id
        LEFT JOIN playlist_tracks pt ON t.id = pt.track_id
        GROUP BY a.id, t.id
    ) sub
    WHERE rn <= 3
    ORDER BY artist_name, num_playlists DESC;
    """)
    
    rows = sql_session.execute(stmt).fetchall()

# WHERE rn <= 3
    # Print each row as (artist, track, count)
    for artist, track, count in rows:
        if None not in (artist, track, count):
            print(f"{artist or '<Unknown Artist>':40} | {track:75} | in {count} playlists")
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    print("Seconds: ", execution_time)
    
    return rows

# ===========================================
#             user interaction
# ===========================================

# TODO: we need to figure out how user interaction will look lol

def execute_user_interaction(sql_session, db_engine, spotify_client):
        # this code is trash dw its okay :)
    prompt = """\n\nWelcome to SoulRipper, please select one of the following options:

    1: Update the database with all of your data from Spotify (playlists and liked songs)
    2: Update the database with just your playlists from Spotify
    3: Update the database with your liked songs from Spotify
    4: Add a new track to the database
    5: Modify a track in the database
    6: Remove a track from the database
    7: Search for a track in the database
    8: Display some statistics about your library
    9: Drop the database
    q: Close the program

Enter your choice here: """

    while True:
        choice = input(prompt)

        match choice:
            case "1":
                sql_session.commit()
                
                all_playlists_metadata = spotify_client.get_all_playlists()
                for playlist_metadata in all_playlists_metadata:
                    update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata)
                update_db_with_spotify_liked_tracks(spotify_client, sql_session)
                sql_session.flush()
                sql_session.commit()
                continue

            case "2":
                all_playlists_metadata = spotify_client.get_all_playlists()
                for playlist_metadata in all_playlists_metadata:
                    update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata)
                sql_session.flush()
                sql_session.commit()
                continue

            case "3":
                update_db_with_spotify_liked_tracks(spotify_client, sql_session)
                sql_session.flush()
                sql_session.commit()
                continue

            case "4":
                filepath = input("Please enter the filepath of your new track: ")
                filepath = filepath.strip().strip("'\"")
                add_new_track_to_db(sql_session, filepath)
                continue
            
            case "5":
                try:
                    track_id = int(input("Enter the ID of the track you'd like to modify: "))
                    track_row = sql_session.query(SoulDB.Tracks).filter_by(id=track_id).one()
                    print(f"\nCurrent track data:")
                    print(f"Title: {track_row.title}")
                    print(f"Filepath: {track_row.filepath}")
                    print(f"Album: {track_row.album}")
                    print(f"Release Date: {track_row.release_date}")
                    print(f"Explicit: {track_row.explicit}")
                    print(f"Date Liked: {track_row.date_liked_spotify}")
                    print(f"Comments: {track_row.comments}\n")

                    modify_field = input("Enter the name of the field you'd like to modify (e.g., 'title', 'filepath', 'album', 'release_date', 'explicit', 'comments'): ").strip()
                    if not hasattr(track_row, modify_field):
                        print(f"Field '{modify_field}' does not exist on Tracks.")
                        continue

                    new_value = input(f"Enter the new value for {modify_field}: ").strip()

                    # Handle booleans properly
                    if modify_field.lower() == "explicit":
                        new_value = new_value.lower() in ("true", "yes", "1")

                    setattr(track_row, modify_field, new_value)

                    sql_session.flush()
                    sql_session.commit()
                    print(f"Track (ID {track_id}) updated successfully!\n")

                except Exception as e:
                    print(f"An error occurred: {e}\n")

                continue
                        
            case "6":
                track_id = input("Enter the id of the track you'd like to remove: ")
                remove_track(sql_session, track_id)
                continue
            
            case "7":
                title = input("Enter the title of the track you'd like to search for: ")
                results = search_for_track(sql_session, title)

                if results == []:
                    print("No matching tracks found...")
                    continue

                for track in results:
                    print(f"ID: {track.id}")
                    print(f"Title: {track.title}")
                    print(f"Filepath: {track.filepath}")
                    print(f"Album: {track.album}")
                    print(f"Release Date: {track.release_date}")
                    print(f"Explicit: {track.explicit}")
                    print(f"Date Liked: {track.date_liked_spotify}")
                    print(f"Comments: {track.comments}")
                    print("-" * 40)

                continue
            
            case "8":
                execute_all_interesting_queries(sql_session)
                continue
            
            case "9":
                confirmation = input("Are you sure you want to drop all tables in the database? Type 'yes' to confirm: ")
                if confirmation == "yes":
                    sql_session.close()
                    metadata = sqla.MetaData()
                    metadata.reflect(bind=db_engine)
                    metadata.drop_all(db_engine)
                    print("Database dropped successfully. Closing the program.")
                    return
                else:
                    print("Not dropping the database...")
                continue

            case "q":
                return
            
            case _:
                print("Invalid input, try again")
                continue

def search_for_track(sql_session, track_title):
    results = sql_session.query(SoulDB.Tracks).filter(
        SoulDB.Tracks.title.ilike(f"%{track_title}%")
    ).all()

    return results

def modify_track(sql_session, track_id, new_track_data: SoulDB.TrackData):
    existing_track = sql_session.query(SoulDB.Tracks).filter_by(id=track_id).one()
    
    existing_track.spotify_id = new_track_data.spotify_id if new_track_data.spotify_id is not None else existing_track.spotify_id
    existing_track.filepath = new_track_data.filepath if new_track_data.filepath is not None else existing_track.filepath
    existing_track.title = new_track_data.title if new_track_data.title is not None else existing_track.title
    existing_track.album = new_track_data.album if new_track_data.album is not None else existing_track.album
    existing_track.release_date = new_track_data.release_date if new_track_data.release_date is not None else existing_track.release_date
    existing_track.explicit = new_track_data.explicit if new_track_data.explicit is not None else existing_track.explicit
    existing_track.date_liked_spotify = new_track_data.date_liked_spotify if new_track_data.date_liked_spotify is not None else existing_track.date_liked_spotify
    existing_track.comments = new_track_data.comments if new_track_data.comments is not None else existing_track.comments

def remove_track(sql_session, track_id) -> bool :
    existing_track = sql_session.query(SoulDB.Tracks).filter_by(id=track_id).one()

    if existing_track:
        sql_session.delete(existing_track)
        sql_session.flush()
        print("Successfully removed the track")
        return True
    else:
        print("Could not find the track you were trying to remove")
        return False

if __name__ == "__main__":
    main()