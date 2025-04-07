import time
import slskd_api
import subprocess
import re
import os
import json
import argparse
import dotenv
import spotify_utils
import shutil

dotenv.load_dotenv()
slskd_api_key = os.getenv("SLSKD_API_KEY")

# docker run -d -p 5030:5030 -p 5031:5031 -p 50300:50300 -e SLSKD_REMOTE_CONFIGURATION=true -v '/home/goop/dev/music-manager/app_data':/app --name slskd slskd/slskd:latest
slskd = slskd_api.SlskdClient("http://slskd:5030", slskd_api_key)

def main():
    # collect commandline arguments
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("pos_output_path", nargs="?", default=os.getcwd(), help="The output directory in which your files will be downloaded")
    parser.add_argument("--output-path", dest="output_path", help="The output directory in which your files will be downloaded")
    parser.add_argument("--search-query", dest="search_query", help="The output directory in which your files will be downloaded")
    parser.add_argument("--playlist-url", dest="playlist_url", help="URL of Spotify playlist")
    args = parser.parse_args()
    OUTPUT_PATH = os.path.abspath(args.output_path or args.pos_output_path)
    SEARCH_QUERY = args.search_query
    SPOTIFY_PLAYLIST_URL = args.playlist_url

    # TODO: this should not be hard coded. maybe a config file?
    DEFAULT_OUTPUT_PATH = "/mnt/d/DJ/soulRipper"
    OUTPUT_PATH = DEFAULT_OUTPUT_PATH if OUTPUT_PATH == "/home/soulripper" else OUTPUT_PATH

    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # if a search query is provided, download the track
    if SEARCH_QUERY:
        download_track(SEARCH_QUERY, OUTPUT_PATH)
    
    if SPOTIFY_PLAYLIST_URL:
        playlist_info = spotify_utils.get_playlist_from_url(SPOTIFY_PLAYLIST_URL)
        print(playlist_info)

def download_track(search_query: str, output_path: str) -> str:
    """
    Downloads a track from soulseek or youtube, only downloading from youtube if the query is not found on soulseek

    Args:
        search_query (str): the song to download, can be a search query
        output_path (str): the directory to download the song to

    Returns:
        str: the path to the downloaded file
    """
    download_path = download_track_slskd(search_query, output_path)

    if download_path is None:
        download_path = download_track_ytdlp(search_query, output_path)

    return download_path

# TODO: make the output path work
def download_track_slskd(search_query: str, output_path: str) -> str:       
    """
    Attempts to download a track from soulseek

    Args:
        search_query (str): the song to download, can be a search query
        output_path (str): the directory to download the song to

    Returns:
        str|None: the path to the downloaded song or None of the download was unsuccessful
    """

    search_results = search_slskd(search_query)
    if search_results:
        highest_quality_file, highest_quality_file_user = select_best_search_candidate(search_results)

        print(f"Downloading {highest_quality_file['filename']} from user: {highest_quality_file_user}...")
        slskd.transfers.enqueue(highest_quality_file_user, [highest_quality_file])

        # for some reason enqueue doesn't give us the id of the download so we have to get it ourselves. There may be a better way to do this but idc TODO
        for download in slskd.transfers.get_all_downloads():
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
        download_state = slskd.transfers.get_download(highest_quality_file_user, download_id)["state"]
        while not "Completed" in download_state:
            print(download_state)
            time.sleep(1)
            download_state = slskd.transfers.get_download(highest_quality_file_user, download_id)["state"]

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

def search_slskd(search_query: str) -> list:
    """
    Searches for a track on soulseek

    Args:
        search_query (str): the query to search for

    Returns:
        list: a list of search results
    """
    search = slskd.searches.search_text(search_query)
    search_id = search["id"]

    print(f"Searching for: '{search_query}'")
    while slskd.searches.state(search_id)["isComplete"] == False:
        print("Searching...")
        time.sleep(1)

    results = slskd.searches.search_responses(search_id)
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

if __name__ == "__main__":
    main()