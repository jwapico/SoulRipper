import rich.layout
import rich.status
import sqlalchemy as sqla
from sqlalchemy.orm import Session
from pyventus.events import EventLinker
from typing import Dict
import threading
import rich.progress
from rich.live import Live
import rich.console
import logging
import argparse
import os

from soulripper.database import update_db_with_spotify_playlist
from soulripper.database import add_local_library_to_db, add_local_track_to_db
from soulripper.database import Base
from soulripper.utils import AppParams
from soulripper.spotify import SpotifyClient
from soulripper.downloaders import (
    SoulseekDownloader, 
    download_from_search_query, 
    download_liked_songs, 
    download_playlist_from_spotify_url, 
    SoulseekDownloadStartEvent, 
    SoulseekDownloadUpdateEvent, 
    SoulseekDownloadEndEvent, 
    SoulseekSearchStartEvent, 
    SoulseekSearchUpdateEvent, 
    SoulseekSearchEndEvent
)

logger = logging.getLogger(__name__)

# TODO: Implement event bus
#   - https://github.com/mdapena/pyventus

class CLIOrchestrator():
    def __init__(self, spotify_client: SpotifyClient, sql_session: Session, db_engine: sqla.Engine, soulseek_downloader: SoulseekDownloader, app_params: AppParams = None):
        self.spotify_client = spotify_client
        self.sql_session = sql_session
        self.db_engine = db_engine
        self.soulseek_downloader = soulseek_downloader
        self.app_params = app_params

        EventLinker.on(SoulseekDownloadStartEvent)(self._on_soulseek_download_start)
        EventLinker.on(SoulseekDownloadUpdateEvent)(self._on_soulseek_download_update)
        EventLinker.on(SoulseekDownloadEndEvent)(self._on_soulseek_download_end)

        EventLinker.on(SoulseekSearchStartEvent)(self._on_soulseek_search_start)
        EventLinker.on(SoulseekSearchUpdateEvent)(self._on_soulseek_search_update)
        EventLinker.on(SoulseekSearchEndEvent)(self._on_soulseek_search_end)

        # TODO: fix this bullshit FUCK
        self._rich_console = rich.console.Console()
        self._rich_progress = rich.progress.Progress(
            rich.progress.SpinnerColumn(spinner_name="earth"),
            rich.progress.TextColumn("{task.description}"),
            rich.progress.BarColumn(
                bar_width=None,
                complete_style="green",
                finished_style="green",
                pulse_style="deep_pink4",
                style="deep_pink4"
            ),
            rich.progress.TaskProgressColumn(style="green"),
            rich.progress.TimeRemainingColumn(),
            expand=True,
            console=self._rich_console,
            refresh_per_second=10,
        )
        self._rich_progress.start()

        self._soulseek_downloads: Dict[str, rich.progress.TaskID] = {}
        self._search_task_id: rich.progress.TaskID = None

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
    
    # TODO: FIX ALA DEE HOE
    # FUCK

    def _on_soulseek_download_start(self, download_start_event: SoulseekDownloadStartEvent):
        tid = self._rich_progress.add_task(f"Downloading {download_start_event.download_filename}", total=100)
        self._soulseek_downloads[download_start_event.download_file_id] = tid

    def _on_soulseek_download_update(self, download_update_event: SoulseekDownloadUpdateEvent):
        tid = self._soulseek_downloads.get(download_update_event.download_file_id)
        if tid is not None:
            self._rich_progress.update(tid, completed=download_update_event.percent_complete)


    def _on_soulseek_download_end(self, download_end_event: SoulseekDownloadEndEvent):
        tid = self._soulseek_downloads.pop(download_end_event.download_file_id, None)
        if tid is not None:
            self._rich_progress.update(tid, completed=100)
            self._rich_progress.remove_task(tid)

    def _on_soulseek_search_start(self, search_start: SoulseekSearchStartEvent):
        self._search_task_id = self._rich_progress.add_task(
            f"Searching SoulSeek for: {search_start.search_query}", total=None
        )

    def _on_soulseek_search_update(self, search_update: SoulseekSearchUpdateEvent):
        self._rich_progress.update(
            self._search_task_id,
            description=f"Found {search_update.num_found_files} files for: {search_update.search_query}"
        )

    def _on_soulseek_search_end(self, search_end: SoulseekSearchEndEvent):
        self._rich_progress.update(self._search_task_id, description=f"Search complete: {search_end.search_query}")
        self._rich_progress.remove_task(self._search_task_id)
        self._search_task_id = None

        self._rich_console.print(f"[green]✔ Found {search_end.num_relevant_files} relevant files for {search_end.search_query}[/]")