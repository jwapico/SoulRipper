import sqlalchemy as sqla
from sqlalchemy.orm import Session
import argparse
import os

from soulripper.database import update_db_with_spotify_playlist
from soulripper.database import add_local_library_to_db, add_local_track_to_db
from soulripper.database import Base
from soulripper.utils import AppParams
from soulripper.spotify import SpotifyClient
from soulripper.downloaders import SoulseekDownloader, download_from_search_query, download_liked_songs, download_playlist_from_spotify_url

class CLIOrchestrator():
    def __init__(self, spotify_client: SpotifyClient, sql_session: Session, db_engine: sqla.Engine, soulseek_downloader: SoulseekDownloader, app_params: AppParams = None):
        self.spotify_client = spotify_client
        self.sql_session = sql_session
        self.db_engine=db_engine
        self.soulseek_downloader = soulseek_downloader
        self.app_params = app_params

    def run(self):
        args = self.parse_cmdline_args()

        SEARCH_QUERY = args.search_query
        SPOTIFY_PLAYLIST_URL = args.playlist_url
        DOWNLOAD_LIKED = args.download_liked
        DOWNLOAD_ALL_PLAYLISTS = args.download_all_playlists
        DROP_DATABASE = args.drop_database
        NEW_TRACK_FILEPATH = args.add_track

        # if the flag was provided drop everything in the database
        if DROP_DATABASE:
            input("Warning: This will drop all tables in the database. Press enter to continue...")

            metadata = sqla.MetaData()
            metadata.reflect(bind=self.db_engine)
            metadata.drop_all(self.db_engine)

        # initialize the tables defined in souldb.py
        Base.metadata.create_all(self.db_engine)

        # populate the database with metadata found from files in the users output directory
        add_local_library_to_db(self.sql_session, self.app_params.output_path, self.app_params.valid_music_extensions)

        if NEW_TRACK_FILEPATH:
            add_local_track_to_db(self.sql_session, NEW_TRACK_FILEPATH)

        # if a search query is provided, download the track
        if SEARCH_QUERY:
            output_path = download_from_search_query(self.soulseek_downloader, SEARCH_QUERY, self.app_params.output_path, self.app_params.youtube_only, self.app_params.youtube_only)
            # TODO: get metadata and insert into database

        # get all playlists from spotify and add them to the database
        if DOWNLOAD_ALL_PLAYLISTS:
            all_playlists_metadata = self.spotify_client.get_all_playlists()
            for playlist_metadata in all_playlists_metadata:
                update_db_with_spotify_playlist(self.sql_session, self.spotify_client, playlist_metadata)

            # TODO: actually download the playlists

        # if the update liked flag is provided, download all liked songs from spotify
        if DOWNLOAD_LIKED:
            download_liked_songs(self.soulseek_downloader, self.spotify_client, self.sql_session, self.app_params.output_path, self.app_params.youtube_only)
        
        # if a playlist url is provided, download the playlist
        # TODO: refactor this function
        if SPOTIFY_PLAYLIST_URL:
            download_playlist_from_spotify_url(self.soulseek_downloader, self.spotify_client, self.sql_session, SPOTIFY_PLAYLIST_URL, self.app_params.output_path)
            pass

    def parse_cmdline_args(self) -> argparse.Namespace:
        # add all the arguments
        parser = argparse.ArgumentParser(description="")
        parser.add_argument("--output-path", type=str, dest="output_path", help="The output directory in which your files will be downloaded")
        parser.add_argument("--search-query", type=str, dest="search_query", help="The output directory in which your files will be downloaded")
        parser.add_argument("--playlist-url", type=str, dest="playlist_url", help="URL of Spotify playlist")
        parser.add_argument("--download-liked", action="store_true", help="Will download the database with all your liked songs from Spotify")
        parser.add_argument("--download-all-playlists", action="store_true", help="Will download the database with all your playlists from Spotify")
        parser.add_argument("--log", action="store_true", help="Enable log statements")
        parser.add_argument("--drop-database", action="store_true", help="Drop the database before running the program")
        parser.add_argument("--max-retries", type=int, default=5, help="The maximum number of retries for downloading a track")
        parser.add_argument("--add-track", type=str, help="Add a track to the database - provide the filepath")
        parser.add_argument("--yt", action="store_true", help="Download exclusively from Youtube")

        args = parser.parse_args()

        # update our relevant app_params with the new args
        self.app_params.output_path = os.path.abspath(args.output_path) if args.output_path else self.app_params.output_path
        self.app_params.log_enabled = args.log if args.log else self.app_params.log_enabled
        self.app_params.max_download_retries = args.max_retries if args.max_retries else self.app_params.max_download_retries
        self.app_params.youtube_only = args.yt if args.yt else self.app_params.youtube_only
        
        return args