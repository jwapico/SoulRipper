from sqlalchemy.orm import Session
import sqlalchemy as sqla
import os
import argparse
import dotenv

import database.services.local_sync
import database.services.spotify_sync
from spotify.client import SpotifyClient
from downloaders.soulseek import SoulseekDownloader
from database.models.base import Base
import database.services
import utils.config
from utils.config import AppConfig
import downloaders.orchestrator

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
#           - once they verify the track, we change the filename to be {title} - {artists} rather than however it was downloaded
#               - write the original filename in the comments field of the database AND file metadata
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
    app_config: AppConfig = utils.config.load_config_file(CONFIG_FILEPATH)

    dotenv.load_dotenv()
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # connect to spotify API
    spotify_client = SpotifyClient(config_filepath=CONFIG_FILEPATH)

    # we communicate with slskd through port 5030, you can visit localhost:5030 to see the web front end. its at slskd:5030 in the docker container though
    SLSKD_API_KEY = os.getenv("SLSKD_API_KEY")
    slskd_client = SoulseekDownloader(SLSKD_API_KEY)

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
    Base.metadata.create_all(db_engine)

    # populate the database with metadata found from files in the users output directory
    database.services.local_sync.add_local_library_to_db(sql_session, OUTPUT_PATH)

    if NEW_TRACK_FILEPATH:
        database.services.local_sync.add_local_track_to_db(sql_session, NEW_TRACK_FILEPATH)

    # if a search query is provided, download the track
    if SEARCH_QUERY:
        output_path = downloaders.orchestrator.download_from_search_query(slskd_client, SEARCH_QUERY, OUTPUT_PATH, YOUTUBE_ONLY)
        # TODO: get metadata and insert into database

    # get all playlists from spotify and add them to the database
    if DOWNLOAD_ALL_PLAYLISTS:
        all_playlists_metadata = spotify_client.get_all_playlists()
        for playlist_metadata in all_playlists_metadata:
            database.services.spotify_sync.update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata)

        # TODO: actually download the playlists

    # if the update liked flag is provided, download all liked songs from spotify
    if DOWNLOAD_LIKED:
        downloaders.orchestrator.download_liked_songs(slskd_client, spotify_client, sql_session, OUTPUT_PATH, YOUTUBE_ONLY)
    
    # if a playlist url is provided, download the playlist
    # TODO: refactor this function
    if SPOTIFY_PLAYLIST_URL:
        downloaders.orchestrator.download_playlist_from_spotify_url(slskd_client, spotify_client, sql_session, SPOTIFY_PLAYLIST_URL, OUTPUT_PATH)
        pass

if __name__ == "__main__":
    main()