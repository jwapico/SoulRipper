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
#   - figure out how to link tracks to playlists
#   - create and sync database with local music directory
#   - create and sync database with spotify info
#   - better search for soulseek given song title and artist
#   - better user interface - gui or otherwise
#       - some sort of config file for api keys, directory paths, etc
#       - make cli better
#   - error handling in download functions and probably other places
#   - restructure this file - there are too many random ahh functions
#       - maybe incapsulate into class or just make a utils file
#           - shared variables so we dont have to pass shi around so much
#   - create a TODO.md file for project management and big plans outside of databases final project (due apr 30 :o)
#       - talk to colton eoghan and other potential users about high level design
#   - parallelize downloads

def main():
    # collect commandline arguments
    # TODO: add --max-retries argument
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
    SPOTIFY_USER_ID, SPOTIFY_USERNAME = spotify_utils.get_user_info()

    # create the engine with the local soul.db file
    engine = sqla.create_engine("sqlite:///assets/soul.db", echo = False)

    # drop everything in the database for debugging
    metadata = sqla.MetaData()
    metadata.reflect(bind=engine)
    metadata.drop_all(engine)

    # initialize the tables defined in souldb.py and create a session
    SoulDB.Base.metadata.create_all(engine)
    session = sqlalchemy.orm.sessionmaker(bind=engine)
    sql_session = session()

    # add the user to the database if they don't already exist
    existing_user = sql_session.query(SoulDB.UserInfo).filter_by(spotify_id=SPOTIFY_USER_ID).first()
    if existing_user is None:
        SoulDB.UserInfo.add_user(sql_session, SPOTIFY_USERNAME, SPOTIFY_USER_ID, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)

    # if a search query is provided, download the track
    if SEARCH_QUERY:
        output_path = download_track(slskd_client, SEARCH_QUERY, OUTPUT_PATH)
        # TODO: get metadata and insert into database
    
    # if a playlist url is provided, download the playlist
    if SPOTIFY_PLAYLIST_URL:
        download_playlist(slskd_client, spotify_utils, sql_session, SPOTIFY_PLAYLIST_URL, OUTPUT_PATH)

    # add_tracks_from_music_dir("music", sql_session)
    # createAllPlaylists(spotify_utils, engine)

def download_playlist(slskd_client, spotify_utils: SpotifyUtils, sql_session, playlist_url: str, output_path: str):
    """
    Downloads a playlist from spotify

    Args:
        playlist_url (str): the url of the playlist
        output_path (str): the directory to download the songs to
    """

    playlist_id = spotify_utils.get_playlist_id_from_url(playlist_url)
    playlist_tracks = spotify_utils.get_playlist_tracks(playlist_id)
    playlist_info = spotify_utils.get_playlist_info(playlist_id)

    output_path = os.path.join(output_path, playlist_info["name"])
    os.makedirs(output_path, exist_ok=True)

    # add each track to the Tracks database if it doesn't already exist
    tracks_info = []
    for track in playlist_tracks:
        spotify_id = track["track"]["id"]
        track_added_date = track["added_at"]
        explicit = track["track"]["explicit"]
        title = track["track"]["name"]
        artists = [(artist["name"], artist["id"]) for artist in track["track"]["artists"]]
        album = track["track"]["album"]["name"]
        release_date = track["track"]["album"]["release_date"]
        date_liked = get_date_liked(track["track"]["id"])
        filepath = download_track(slskd_client, f"{title} - {', '.join([artist[0] for artist in artists])}", output_path)

        SoulDB.Tracks.add_track(sql_session, spotify_id, filepath, title, artists, album, release_date, explicit, date_liked, None)
        tracks_info.append((spotify_id, track_added_date))

    SoulDB.Playlists.add_playlist(sql_session, playlist_id, playlist_info["name"], playlist_info["description"], tracks_info)

# TODO: implement this function - need to also create table for liked songs (will be of type Playlist tho)
def get_date_liked(track_id: str) -> str:
    """
    Gets the date a track was liked from user spotify liked songs

    Args:
        track_id (str): the id of the track

    Returns:
        str: the date the track was liked
    """

    return None

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

# TODO: finish this function - need to add artists to Artists table
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
                # TODO: look at metadata to see what else we can extract - it's different for each file :(
                file_metadata = extract_metadata(filepath)
                title  = file_metadata.get("title")
                artist = file_metadata.get("artist")
                album  = file_metadata.get("album")
                genre  = file_metadata.get("genre")
                date   = file_metadata.get("date")
                length = file_metadata.get("length")
                SoulDB.Tracks.add_track(sql_session, filepath, title, artist, album, date, None, None, None)
    
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

# TODO: the output filename is wrong also ERROR HANDLING
def download_track_slskd(slskd_client, search_query: str, output_path: str, max_retries=5) -> str:       
    """
    Attempts to download a track from soulseek

    Args:
        search_query (str): the song to download, can be a search query
        output_path (str): the directory to download the song to

    Returns:
        str|None: the path to the downloaded song or None of the download was unsuccessful
    """

    # search slskd for the track and filter the results if there are any
    search_results = search_slskd(slskd_client, search_query)
    if search_results is None:
        print("No results found on Soulseek")
        return None

    relevant_results = filter_search_results(search_results)
    if relevant_results is None:
        print("No relevant results found on Soulseek")
        return None
    
    # attempt to download the track from slskd
    download_result = attempt_downloads(slskd_client, relevant_results, max_retries)
    if download_result is None:
        print("Unable to download track from Soulseek")
        return None

    download_user, file_data, file_id, download_info = download_result
    download, download_dir, download_file = get_slskd_download_from_file_id(slskd_client, file_id)

    # wait for the download to be completed
    # TODO: refactor this whole block of code to analyze the download object and get the state from there
    download_state = slskd_client.transfers.get_download(download_user, file_id)["state"]
    num_retries = 0
    while not "Completed" in download_state:
        if num_retries > 120:
            print("download took longer than 2 minutes - skipping - this is only for debugging and we need to look at the downloads status")
            break

        download_state = slskd_client.transfers.get_download(download_user, file_id)["state"]
        print(download_state)
        time.sleep(1)
        num_retries += 1

    # this moves the file from where it was downloaded to the specified output path
    if download_state == "Completed, Succeeded":
        containing_dir_name = os.path.basename(download_dir["directory"].replace("\\", "/"))
        filename = os.path.basename(download_file["filename"].replace("\\", "/"))

        source_path = os.path.join(f"assets/downloads/{containing_dir_name}/{filename}")
        dest_path = os.path.join(f"{output_path}/{filename}")

        if not os.path.exists(source_path):
            print(f"ERROR: slskd download state is 'Completed, Succeeded' but the file was not found: {source_path}")
            return None

        shutil.move(source_path, dest_path)
        return dest_path
    else:
        print(f"Download failed: {download_state}")
        return None


    # highest_quality_file, highest_quality_file_user = relevant_results[0]

    # print(f"Downloading {highest_quality_file['filename']} from user: {highest_quality_file_user}...")

    # # TODO: wrap this in a try except block and if it errors move on the next file - I think select_best_search_candidate needs to be refactored to return a list
    # try:
    #     slskd_client.transfers.enqueue(highest_quality_file_user, [highest_quality_file])
    # except Exception as e:
    #     print(f"Error when downloading the track from slskd: {e}")
    #     # TODO: maybe retry with next user or file
    #     return None

    # # for some reason enqueue doesn't give us the id of the download so we have to get it ourselves, the bool returned by enqueue is also not accurate. There may be a better way to do this but idc TODO
    # for download in slskd_client.transfers.get_all_downloads():
    #     for directory in download["directories"]:
    #         for file in directory["files"]:
    #             if file["filename"] == highest_quality_file["filename"]:
    #                 new_download = download

    # # python src/main.py --search-query "Arya (With Nigo) - Nigo, A$AP Rocky"
    # if len(new_download["directories"]) > 1 or len(new_download["directories"][0]["files"]) > 1:
    #     print(f"bug: more than one file candidate in new_download: \n\n{pprint(new_download)}")

    # directory = new_download["directories"][0]
    # file = directory["files"][0]
    # download_id = file["id"]

    # # wait for the download to be completed
    # download_state = slskd_client.transfers.get_download(highest_quality_file_user, download_id)["state"]
    # while not "Completed" in download_state:
    #     print(download_state)
    #     time.sleep(1)
    #     download_state = slskd_client.transfers.get_download(highest_quality_file_user, download_id)["state"]

    # # TODO: if the download failed, retry from a different user, maybe next highest quality file. add max_retries arg to specify max number of retries before returning None
    # print(download_state)

    # # this moves the file from where it was downloaded to the specified output path
    # if download_state == "Completed, Succeeded":
    #     containing_dir_name = os.path.basename(directory["directory"].replace("\\", "/"))
    #     filename = os.path.basename(file["filename"].replace("\\", "/"))

    #     source_path = os.path.join(f"assets/downloads/{containing_dir_name}/{filename}")
    #     dest_path = os.path.join(f"{output_path}/{filename}")

    #     if not os.path.exists(source_path):
    #         print(f"ERROR: slskd download state is 'Completed, Succeeded' but the file was not found: {source_path}")
    #         return None

    #     shutil.move(source_path, dest_path)
    #     return dest_path
    # else:
    #     print(f"Download failed: {download_state}")
    #     return None

# TODO: the print statements in these lower level functions should be changed to logging/debug statements but idk how to do that and dc rn 

def attempt_downloads(slskd_client, search_results, max_retries):
    for attempt_count, (file_data, file_user) in enumerate(search_results):
        if attempt_count > max_retries:
            print(f"Max retries ({max_retries}) reached for your query")
            return (None, None, None)
        
        try:
            print(f"Attempting to download {file_data['filename']} from user: {file_user}...")
            slskd_client.transfers.enqueue(file_user, [file_data])
        except Exception as e:
            print(f"Error during transfer: {e}")
            continue

        download_info, file_id = get_slskd_download_from_filename(slskd_client, file_data["filename"])

        if download_info is None:
            print(f"Error: could not find download for '{file_data['filename']}' from user '{file_user}'")
        
        return (file_user, file_data, file_id, download_info)

def get_slskd_download_from_filename(slskd_client, filename):
    """
    Gets the download object for a file from slskd

    Args:
        slskd_client: the slskd client
        file_data: slskd file data from the search results
    
    Returns:
        download: the download data for the file
    """

    for download in slskd_client.transfers.get_all_downloads():
        for directory in download["directories"]:
            for file in directory["files"]:
                if file["filename"] == filename:
                    return (download, file["id"])

def get_slskd_download_from_file_id(slskd_client, file_id):
    """
    Gets the download object for a file from slskd

    Args:
        slskd_client: the slskd client
        file_id: the id of the file
    
    Returns:
        download: the download data for the file
    """

    for download in slskd_client.transfers.get_all_downloads():
        for directory in download["directories"]:
            for file in directory["files"]:
                if file["id"] == file_id:
                    return (download, directory, file)
    for download in slskd_client.transfers.get_all_downloads():
        for directory in download["directories"]:
            for file in directory["files"]:
                if file["id"] == file_id:
                    return (download, directory, file)

def filter_search_results(search_results):
    """
    Filters the search results to only include downloadable mp3 and flac files sorted by size

    Args:
        search_results: search responses in the format of slskd.searches.search_responses()
    
    Returns:
        List((highest_quality_file, highest_quality_file_user: str)): The file data for the best candidate, and the username of its owner
    """

    relevant_results = []

    for result in search_results:
        for file in result["files"]:
            # this extracts the file extension
            match = re.search(r'\.([a-zA-Z0-9]+)$', file["filename"])

            if match is None:
                print(f"Skipping due to invalid file extension: {file['filename']}")
                continue

            file_extension = match.group(1)

            if file_extension in ["flac", "mp3"] and result["fileCount"] > 0 and result["hasFreeUploadSlot"] == True:
                relevant_results.append((file, result["username"]))
            
    relevant_results.sort(key=lambda candidate : candidate[0]["size"], reverse=True)

    # return highest_quality_file, highest_quality_file_user
    return relevant_results

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

# TODO: cleanup printing and better searching - need to extract artist and title from search data
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

def pprint(data):
    print(json.dumps(data, indent=4))

def save_json(data, filepath="debug.json"):
    with open(filepath, "w") as file:
        json.dump(data, file)

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

if __name__ == "__main__":
    main()