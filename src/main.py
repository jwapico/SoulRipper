import time
import slskd_api
import subprocess
import re
import os
import json
import argparse
import dotenv
import shutil
import sqlalchemy as sqla
import sqlalchemy.orm
import mutagen

from spotify_utils import SpotifyUtils
import souldb as SoulDB

# TODO:
#   - better search for soulseek given song title and artist
#   - create and sync database with spotify info
#   - create and sync database with local music directory
#   - better user interface - gui or otherwise
#       - some sort of config file for api keys, directory paths, etc
#       - make cli better
#   - error handling in download functions and probably other places
#   - restructure this file - there are too many random ahh functions
#       - maybe incapsulate into class or just make a utils file
#           - shared variables so we dont have to pass shi around so much
#   - create a TODO.md file for project management and big plans outside of databases final project (due apr 30 :o)
#       - talk to colton eoghan and other potential users about high level design

def main():
    # collect commandline arguments
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("pos_output_path", nargs="?", default=os.getcwd(), help="The output directory in which your files will be downloaded")
    parser.add_argument("--output-path", dest="output_path", help="The output directory in which your files will be downloaded")
    parser.add_argument("--search-query", dest="search_query", help="The output directory in which your files will be downloaded")
    parser.add_argument("--playlist-url", dest="playlist_url", help="URL of Spotify playlist")
    args = parser.parse_args()
    SEARCH_QUERY = args.search_query
    SPOTIFY_PLAYLIST_URL = args.playlist_url
    OUTPUT_PATH = os.path.abspath(args.output_path or args.pos_output_path)
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # we communicate with slskd through port 5030, you can visit localhost:5030 to see the web front end. its at slskd:5030 in the docker container though
    dotenv.load_dotenv()
    SLSKD_API_KEY = os.getenv("SLSKD_API_KEY")
    slskd_client = slskd_api.SlskdClient("http://slskd:5030", SLSKD_API_KEY)

    # connect to spotify API
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
    spotify_utils = SpotifyUtils(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI,  spotify_scope="user-library-read playlist-modify-public")
    # spotify_utils = SpotifyUtils(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI)
    
    # if a search query is provided, download the track
    if SEARCH_QUERY:
        output_path = download_track(slskd_client, SEARCH_QUERY, OUTPUT_PATH)
        # TODO: get metadata and insert into database
        
    if SPOTIFY_PLAYLIST_URL:
        download_playlist(slskd_client, spotify_utils, SPOTIFY_PLAYLIST_URL, OUTPUT_PATH)

    # create the engine with the local soul.db file
    engine = sqla.create_engine("sqlite:///assets/soul.db", echo = True)

    # drop everything in the database
    metadata = sqla.MetaData()
    metadata.reflect(bind=engine)
    metadata.drop_all(engine)

    # initialize the tables defined in souldb.py and create a session
    SoulDB.Base.metadata.create_all(engine)
    session = sqlalchemy.orm.sessionmaker(bind=engine)
    sql_session = session()

    # add_tracks_from_music_dir("music", sql_session)
    # createAllPlaylists(spotify_utils, engine)

# TODO: if no output path is provided use the name of the playlist in project dir
def download_playlist(slskd_client, spotify_utils: SpotifyUtils, playlist_url: str, output_path: str):
    """
    Downloads a playlist from spotify

    Args:
        playlist_url (str): the url of the playlist
        output_path (str): the directory to download the songs to
    """

    playlist_id = spotify_utils.get_playlist_id_from_url(playlist_url)
    playlist_tracks = spotify_utils.get_all_playlist_tracks(playlist_id)

    for track in playlist_tracks:
        track_added_date = track["added_at"]
        explicit = track["track"]["explicit"]
        track_name = track["track"]["name"]
        artists = [artist["name"] for artist in track["track"]["artists"]]
        album = track["track"]["album"]["name"]
        release_date = track["track"]["album"]["release_date"]
        # TODO: implement this function - need to also create table for liked songs (will be of type Playlist tho)
        # date_liked = get_date_liked(track["track"]["id"])

        filepath = download_track(slskd_client, track_name, output_path)

        # SoulDB.Tracks.add_track(sql_session, file)


















    # # get the playlist id from the url
    # playlist_id = spotify_utils.get_playlist_id(playlist_url)
    # all_songs = spotify_utils.get_all_playlist_tracks(playlist_id)

    # for song in all_songs:
    #     track_name = song["track"]["name"]
    #     artist_name = song["track"]["artists"][0]["name"]
    #     search_query = f"{track_name} {artist_name}"
    #     download_track(slskd_client, search_query, output_path)

def extract_metadata(filepath: str) -> dict:
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

def add_tracks_from_music_dir(music_dir: str, sql_session):
    """
    Adds all songs in the music directory to the database

    Args:
        music_dir (str): the directory to add songs from
    """
    for root, dirs, files in os.walk(music_dir):
        for file in files:
            if file.endswith(".mp3") or file.endswith(".flac") or file.endswith(".wav"):
                filepath = os.path.abspath(os.path.join(root, file))
                file_metadata = extract_metadata(filepath)
                title  = file_metadata.get("title")
                artist = file_metadata.get("artist")
                album  = file_metadata.get("album")
                genre  = file_metadata.get("genre")
                date   = file_metadata.get("date")
                length = file_metadata.get("length")
                SoulDB.Tracks.add_track(sql_session, filepath, title, artist, date, None, None, None)

def createAllPlaylists(spotify_utils, engine):
    all_playlists = spotify_utils.get_all_playlists()
    save_json(all_playlists,"allPlaylists.json")

    playlist_titles = []
    first = True
    for playlist in all_playlists:
        
        all_songs = spotify_utils.get_all_playlist_tracks(playlist["id"])
        playlistName = playlist["name"]
        if first == True: 
            save_json(all_songs, f"allSongs{playlistName}")
            save_json(spotify_utils.get_track(all_songs[0]['track']['id']), "Footage!")
        playlist_titles.append(playlistName)
        first = False
    # SoulDB.createPlaylistTables(playlist_titles, engine)
    
def download_track(slskd_client, search_query: str, output_path: str) -> str:
    """
    Downloads a track from soulseek or youtube, only downloading from youtube if the query is not found on soulseek

    Args:
        search_query (str): the song to download, can be a search query
        output_path (str): the directory to download the song to

    Returns:
        str: the path to the downloaded file
    """
    download_path = download_track_slskd(slskd_client, search_query, output_path)

    if download_path is None:
        download_path = download_track_ytdlp(search_query, output_path)

    return download_path

def download_track_slskd(slskd_client, search_query: str, output_path: str) -> str:       
    """
    Attempts to download a track from soulseek

    Args:
        search_query (str): the song to download, can be a search query
        output_path (str): the directory to download the song to

    Returns:
        str|None: the path to the downloaded song or None of the download was unsuccessful
    """

    search_results = search_slskd(slskd_client, search_query)
    if search_results:
        highest_quality_file, highest_quality_file_user = select_best_search_candidate(search_results)

        print(f"Downloading {highest_quality_file['filename']} from user: {highest_quality_file_user}...")
        slskd_client.transfers.enqueue(highest_quality_file_user, [highest_quality_file])

        # for some reason enqueue doesn't give us the id of the download so we have to get it ourselves, the bool returned by enqueue is also not accurate. There may be a better way to do this but idc TODO
        for download in slskd_client.transfers.get_all_downloads():
            for directory in download["directories"]:
                for file in directory["files"]:
                    if file["filename"] == highest_quality_file["filename"]:
                        new_download = download

        # python src/main.py --search-query "Arya (With Nigo) - Nigo, A$AP Rocky"
        if len(new_download["directories"]) > 1 or len(new_download["directories"][0]["files"]) > 1:
            raise Exception(f"bug: more than one file candidate in new_download: \n\n{pprint(new_download)}")

        directory = new_download["directories"][0]
        file = directory["files"][0]
        download_id = file["id"]

        # wait for the download to be completed
        download_state = slskd_client.transfers.get_download(highest_quality_file_user, download_id)["state"]
        while not "Completed" in download_state:
            print(download_state)
            time.sleep(1)
            download_state = slskd_client.transfers.get_download(highest_quality_file_user, download_id)["state"]

        # TODO: if the download failed, retry from a different user, maybe next highest quality file. add max_retries arg to specify max number of retries before returning None
        print(download_state)

        # this moves the file from where it was downloaded to the specified output path
        if download_state == "Completed, Succeeded":
            containing_dir_name = os.path.basename(directory["directory"].replace("\\", "/"))
            filename = os.path.basename(file["filename"].replace("\\", "/"))

            source_path = os.path.join(f"assets/downloads/{containing_dir_name}/{filename}")
            dest_path = os.path.join(f"{output_path}/{filename}")
            shutil.move(source_path, dest_path)

        return dest_path

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

def search_slskd(slskd_client, search_query: str) -> list:
    """
    Searches for a track on soulseek

    Args:
        search_query (str): the query to search for

    Returns:
        list: a list of search results
    """
    search = slskd_client.searches.search_text(search_query)
    search_id = search["id"]

    print(f"Searching for: '{search_query}'")
    while slskd_client.searches.state(search_id)["isComplete"] == False:
        print("Searching...")
        time.sleep(1)

    results = slskd_client.searches.search_responses(search_id)
    print(f"Found {len(results)} results")

    return results

def select_best_search_candidate(search_results):
    """
    Returns the search result with the highest quality flac or mp3 file.

    Args:
        search_results: search responses in the format of slskd.searches.search_responses()
    
    Returns:
        (highest_quality_file, highest_quality_file_user: str): The file data for the best candidate, and the username of its owner
    """

    relevant_results = []
    highest_quality_file = {"size": 0}
    highest_quality_file_user = ""

    for result in search_results:
        for file in result["files"]:
            # this extracts the file extension
            match = re.search(r'\.([a-zA-Z0-9]+)$', file["filename"])
            file_extension = match.group(1)

            if file_extension in ["flac", "mp3"] and result["fileCount"] > 0 and result["hasFreeUploadSlot"] == True:
                relevant_results.append(result)
            
                # TODO: may want a more sophisticated way of selecting the best file in the future
                if file["size"] > highest_quality_file["size"]:
                    highest_quality_file = file
                    highest_quality_file_user = result["username"]

    return highest_quality_file, highest_quality_file_user

def pprint(data):
    print(json.dumps(data, indent=4))

def save_json(data, filepath="debug.json"):
    with open(filepath, "w") as file:
        json.dump(data, file)

if __name__ == "__main__":
    main()