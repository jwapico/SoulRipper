import time
import slskd_api
import subprocess
import re
import os
import json
import argparse
import dotenv
import shutil
import time
import sqlalchemy as sqla
from sqlalchemy.orm import Session
import mutagen

from spotify_utils import SpotifyUtils
from slskd_utils import SlskdUtils
import souldb as SoulDB

# TODO:
#   - REFACTOR DOWNLOADING FUNCTIONS
#       - we should populate the database with TrackData from spotify first, then download Null filepath entries after
#   - better syncing with local music directory
#   - create and sync database with ALL spotify data
#   - better search for soulseek given song title and artist
#   - better user interface - gui or otherwise
#       - some sort of config file for api keys, directory paths, etc
#       - make cli better
#   - error handling in download functions and probably other places
#   - restructure this file - there are too many random ahh functions
#       - maybe encapsulate into class or just have shared variables?
#   - create a TODO.md file for project management and big plans outside of databases final project (due apr 30 :o)
#       - talk to colton eoghan and other potential users about high level design
#   - parallelize downloads (threading :D)
#   - the print statements in lower level functions should be changed to logging/debug statements
#   - we need to implement atomicity in the database functions - the Table classmethods such NOT be calling session.commit()
#   - type annotations for ALL functions args and return values
#   - cleanup comments & add more
#   - get a songs metadata using an api such as:
#       - https://www.discogs.com/developers/
#       - big list here: https://soundcharts.com/blog/music-data-api

def main():
    # collect commandline arguments
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("pos_output_path", nargs="?", default=os.getcwd(), help="The output directory in which your files will be downloaded")
    parser.add_argument("--output-path", type=str, dest="output_path", help="The output directory in which your files will be downloaded")
    parser.add_argument("--search-query", type=str, dest="search_query", help="The output directory in which your files will be downloaded")
    parser.add_argument("--playlist-url", type=str, dest="playlist_url", help="URL of Spotify playlist")
    parser.add_argument("--update-liked", action="store_true", help="Will download all liked songs from Spotify")
    parser.add_argument("--debug", action="store_true", help="Enable debug statements")
    parser.add_argument("--drop-database", action="store_true", help="Drop the database before running the program")
    parser.add_argument("--max-retries", type=int, default=5, help="The maximum number of retries for downloading a track")
    args = parser.parse_args()
    OUTPUT_PATH = os.path.abspath(args.output_path or args.pos_output_path)
    SEARCH_QUERY = args.search_query
    SPOTIFY_PLAYLIST_URL = args.playlist_url
    UPDATE_LIKED = args.update_liked
    DEBUG = args.debug
    DROP_DATABASE = args.drop_database
    # TODO: refactor code to use this value (i think its used in download_track only - will need to be passed down thru other functions tho - need to refactor this file for shared variables)
    MAX_RETRIES = args.max_retries

    dotenv.load_dotenv()
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # we communicate with slskd through port 5030, you can visit localhost:5030 to see the web front end. its at slskd:5030 in the docker container though
    SLSKD_API_KEY = os.getenv("SLSKD_API_KEY")
    slskd_client = SlskdUtils(SLSKD_API_KEY)

    # connect to spotify API
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
    # if DEBUG:
    #     spotify_client = SpotifyUtils(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI,  spotify_scope="user-library-read playlist-modify-public")
    # else:
        # spotify_client = SpotifyUtils(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI)
    spotify_client = SpotifyUtils(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI)
    SPOTIFY_USER_ID, SPOTIFY_USERNAME = spotify_client.get_user_info()

    # create the engine with the local soul.db file - need to change this for final submission
    engine = sqla.create_engine("sqlite:///assets/soul.db", echo=DROP_DATABASE)

    # if the flag was provided drop everything in the database
    if DROP_DATABASE:
        if not DEBUG:
            input("Warning: This will drop all tables in the database. Press enter to continue...")

        metadata = sqla.MetaData()
        metadata.reflect(bind=engine)
        metadata.drop_all(engine)

    # initialize the tables defined in souldb.py and create a session
    SoulDB.Base.metadata.create_all(engine)
    session = sqla.orm.sessionmaker(bind=engine)
    sql_session: Session = session()

    # add the user to the database if they don't already exist
    matching_user = sql_session.query(SoulDB.UserInfo).filter_by(spotify_id=SPOTIFY_USER_ID).first()
    if matching_user is None:
        SoulDB.UserInfo.add_user(sql_session, SPOTIFY_USERNAME, SPOTIFY_USER_ID, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)

    # populate the database with metadata found from files in the users output directory
    # scan_music_library(sql_session, OUTPUT_PATH)

    # if a search query is provided, download the track
    if SEARCH_QUERY:
        output_path = download_from_search_query(slskd_client, SEARCH_QUERY, OUTPUT_PATH)
        # TODO: get metadata and insert into database

    # if the update liked flag is provided, download all liked songs from spotify
    if UPDATE_LIKED:
        download_liked_tracks(slskd_client, spotify_client, sql_session, OUTPUT_PATH)
    
    # if a playlist url is provided, download the playlist
    if SPOTIFY_PLAYLIST_URL:
        download_playlist(slskd_client, spotify_client, sql_session, SPOTIFY_PLAYLIST_URL, OUTPUT_PATH)

    start_time = time.time()
    update_db_with_all_spotify_data(sql_session, spotify_client)
    sql_session.commit()
    end_time = time.time()
    print(f"Time taken to update database with all spotify data: {(end_time - start_time) / 60} min")

    # add_playlists(spotify_client, sql_session)
    # add_tracks_from_music_dir("music", sql_session)
    # createAllPlaylists(spotify_client, engine, sql_session)
 
def download_entire_library(slskd_client: SlskdUtils, sql_session: Session, output_path: str):
    pass

# TODO: this function technically kinda works but we need a better way to extract metadata from the files - most files (all downloaded by yt-dlp) have None for all fields except filepath :/
#   - maybe we can extract info from filename
#   - we should probably populate metadata using TrackData from database or Spotify API - this is a lot of work dgaf rn lol
def scan_music_library(sql_session, music_dir: str):
    """
    Adds all songs in the music directory to the database

    Args:
        music_dir (str): the directory to add songs from
    """
    for root, dirs, files in os.walk(music_dir):
        for file in files:
            # TODO: these extensions should be configured with the config file (still need to implement config file </3)
            if file.endswith(".mp3") or file.endswith(".flac") or file.endswith(".wav"):
                filepath = os.path.abspath(os.path.join(root, file))
                # TODO: look at metadata to see what else we can extract - it's different for each file :( - need to find file with great metadata as example
                file_metadata = extract_file_metadata(filepath)
                title  = file_metadata.get("title")
                artists = file_metadata.get("artist")
                album  = file_metadata.get("album")
                date   = file_metadata.get("date")

                artists = [(artist, None) for artist in artists.split(",")] if artists else [(None, None)]
                track_data = SoulDB.TrackData(filepath=filepath, title=title, artists=artists, album=album, release_date=date)
    
                existing_track = SoulDB.get_existing_track(sql_session, track_data)
                if existing_track is None:
                    SoulDB.Tracks.add_track(sql_session, track_data)

def update_db_with_all_spotify_data(sql_session, spotify_client):
    """
    Updates the database with the data from spotify

    Args:
        sql_session (Session): the sql session to use
        spotify_client (SpotifyUtils): the spotify client to use
    """

    update_db_with_spotify_playlists(spotify_client, sql_session)
    update_db_with_spotify_liked_tracks(spotify_client, sql_session)

# TODO: this function is slow - maybe we can make it better for that one deliverable
def update_db_with_spotify_playlists(spotify_client: SpotifyUtils, session):
    all_playlists = spotify_client.get_all_playlists()

    # for debugging - if it does ur whole library it will be slow as shit, for me it took
    # all_playlists = all_playlists[:5]

    for playlist in all_playlists:
        playlist_tracks = spotify_client.get_playlist_tracks(playlist['id'])
        relevant_tracks_data: list[SoulDB.TrackData] = spotify_client.get_data_from_playlist(playlist_tracks)

        # create and flush the playlist since we need its id for the playlist_tracks association table
        matching_playlist = session.query(SoulDB.Playlists).filter_by(spotify_id=playlist['id']).first()
        if matching_playlist is None:
            new_playlist = SoulDB.Playlists.add_playlist(session, playlist['id'], playlist['name'], playlist['description'], None)
            session.add(new_playlist)
            session.flush()

        # add each track in the playlist to the database if it doesn't already exist
        track_rows_and_data = []
        for track_data in relevant_tracks_data:
            existing_track_row = SoulDB.get_existing_track(session, track_data)
            if existing_track_row is None:
                track_data.filepath = None
                new_track_row = SoulDB.Tracks.add_track(session, track_data)
                playlist_track_assoc = SoulDB.PlaylistTracks(track_id=new_track_row.id, playlist_id=playlist['id'], added_at=track_data.date_liked_spotify)
            else:
                track_rows_and_data.append((existing_track_row, track_data))
                playlist_track_assoc = SoulDB.PlaylistTracks(track_id=existing_track_row.id, playlist_id=playlist['id'], added_at=track_data.date_liked_spotify)

            # add the track to the playlist_tracks association table
            if matching_playlist:
                matching_playlist.playlist_tracks.append(playlist_track_assoc)
            else:
                new_playlist.playlist_tracks.append(playlist_track_assoc)

def update_db_with_spotify_liked_tracks(spotify_client: SpotifyUtils, sql_session):
    liked_tracks_data = spotify_client.get_liked_tracks()
    relevant_tracks_data: list[SoulDB.TrackData] = spotify_client.get_data_from_playlist(liked_tracks_data)

    liked_playlist = sql_session.query(SoulDB.Playlists).filter_by(name="SPOTIFY_LIKED_SONGS").first()
    if liked_playlist is None:
        liked_playlist = SoulDB.Playlists.add_playlist(sql_session, spotify_id=None, name="SPOTIFY_LIKED_SONGS", description="User liked songs on Spotify - This playlist is generated by SoulRipper")
        sql_session.add(liked_playlist)
        sql_session.flush()

    # add each track in the users liked songs to the database if it doesn't already exist
    # TODO: we can prolly optimize this for fp deliverable
    track_rows_and_data = []
    for track_data in relevant_tracks_data:
        # prolly a faster way than doing this
        existing_track_row = SoulDB.get_existing_track(sql_session, track_data)
        if existing_track_row:
            playlist_track_assoc = SoulDB.PlaylistTracks(track_id=existing_track_row.id, playlist_id=liked_playlist.id, added_at=track_data.date_liked_spotify)
            track_rows_and_data.append((existing_track_row, track_data))
        else:
            # our add_track function is prolly also dookie
            new_track_row = SoulDB.Tracks.add_track(sql_session, track_data)
            playlist_track_assoc = SoulDB.PlaylistTracks(track_id=new_track_row.id, playlist_id=liked_playlist.id, added_at=track_data.date_liked_spotify)
            track_rows_and_data.append((new_track_row, track_data))
            

        liked_playlist.playlist_tracks.append(playlist_track_assoc)

# TODO: both of these functions need to be rewritten since we are now downloading by searching the database for null filepaths (W)

# TODO: bruhhhhhhhhhhh the spotify api current_user_saved_tracks() function doesn't return local files FUCK SPOTIFYU there has to be a workaround
def download_liked_tracks(slskd_client: SlskdUtils, spotify_client: SpotifyUtils, sql_session, output_path: str):
    liked_tracks_data = spotify_client.get_liked_tracks()
    relevant_tracks_data: list[SoulDB.TrackData] = spotify_client.get_data_from_playlist(liked_tracks_data)

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

def download_playlist(slskd_client: SlskdUtils, spotify_client: SpotifyUtils, sql_session, playlist_url: str, output_path: str):
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

    relevant_tracks_data: list[SoulDB.TrackData] = spotify_client.get_data_from_playlist(playlist_tracks)

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

def download_from_search_query(slskd_client: SlskdUtils, search_query: str, output_path: str) -> str:
    """
    Downloads a track from soulseek or youtube, only downloading from youtube if the query is not found on soulseek

    Args:
        search_query (str): the song to download, can be a search query
        output_path (str): the directory to download the song to

    Returns:
        str: the path to the downloaded file
    """
    download_path = slskd_client.download_track(search_query, output_path)

    if download_path is None:
        download_path = download_track_ytdlp(search_query, output_path)

    return download_path

# def createAllPlaylists(spotify_client, engine):
#     all_playlists = spotify_client.get_all_playlists()
#     save_json(all_playlists,"allPlaylists.json")

#     playlist_titles = []
#     first = True
#     for playlist in all_playlists:
        
#         all_songs = spotify_client.get_all_playlist_tracks(playlist["id"])
#         playlistName = playlist["name"]
#         if first == True: 
#             save_json(all_songs, f"allSongs{playlistName}")
#             save_json(spotify_client.get_track(all_songs[0]['track']['id']), "Footage!")
#         playlist_titles.append(playlistName)
#         first = False
#     # SoulDB.createPlaylistTables(playlist_titles, engine)

def pprint(data):
    print(json.dumps(data, indent=4))

def save_json(data, filename="debug/debug.json"):
    with open(f"debug/{filename}", "w") as file:
        json.dump(data, file)

def extract_file_metadata(filepath: str) -> dict:
    """
    Extracts metadata from a file using mutagen

    Args:
        filepath (str): the path to the file

    Returns:
        dict: a dictionary of metadata
    """
    audio = mutagen.File(filepath)

    if not audio:
        return None

    return {
        "title":  audio.get("title", [None])[0],
        "artist": audio.get("artist", [None])[0],
        "album":  audio.get("album", [None])[0],
        "genre":  audio.get("genre", [None])[0],
        "date":   audio.get("date", [None])[0],
        "track":  audio.get("tracknumber", [None])[0],
        "length": int(audio.info.length) if audio.info else None,
    }

# TODO: these functions arent being used, do we still need them?

def createAllPlaylists(spotify_client, engine, session):
    all_playlists = spotify_client.get_all_playlists()
    save_json(all_playlists,"allPlaylists.json")

    playlist_titles = []
    playlist_songs = {}
    
    for playlist in all_playlists:
        all_songs = spotify_client.get_playlist_tracks(playlist["id"])
        playlist_title = playlist["name"]
        playlist_songs[playlist_title] = []
        for song in all_songs:
            id = song['track']['id']
            if id != None:
                add_track_from_data(song['track'], session, spotify_client)
                playlist_songs[playlist_title].append(id)
        playlist_titles.append(playlist_title)
        # if i == 2:
        #     break
    playlist_dict = SoulDB.createPlaylistTables(playlist_titles, playlist_songs, engine, session)
    
    # results = session.query(playlist_dict["Gym?!"]).all()
    # for r in results:
    #     print(r.song_id)
    
def add_track_from_data(track, session, client):
    # track = client.get_track(id)
    artists = [(artist["name"], artist["id"]) for artist in track["artists"]]
    SoulDB.Tracks.add_track(session=session, spotify_id=track['id'],title=track['name'],artists=artists,release_date=track['album']['release_date'],explicit=track['explicit'], album=track['album']['name'])

if __name__ == "__main__":
    main()