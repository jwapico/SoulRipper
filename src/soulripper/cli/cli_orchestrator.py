import rich.progress
import sqlalchemy as sqla
from sqlalchemy.orm import Session
from pyventus.events import EventLinker
from typing import Dict
import logging
import argparse
import os

import rich
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)

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

class CLIOrchestrator():
    def __init__(self, spotify_client: SpotifyClient, sql_session: Session, db_engine: sqla.Engine, soulseek_downloader: SoulseekDownloader, app_params: AppParams = None):
        self._spotify_client = spotify_client
        self._sql_session = sql_session
        self._db_engine = db_engine
        self._soulseek_downloader = soulseek_downloader
        self._app_params = app_params

        # dicts that keep track of download and search tasks for rich - they map the download file id and search id from soulseek to task id
        self._download_tasks: Dict[str, rich.progress.TaskID]  = {}
        self._search_tasks: Dict[str, rich.progress.TaskID] = {}

        # attach download event listeners
        EventLinker.on(SoulseekDownloadStartEvent)(self._on_soulseek_download_start)
        EventLinker.on(SoulseekDownloadUpdateEvent)(self._on_soulseek_download_update)
        EventLinker.on(SoulseekDownloadEndEvent)(self._on_soulseek_download_end)

        # attach search event listeners
        EventLinker.on(SoulseekSearchStartEvent)(self._on_soulseek_search_start)
        EventLinker.on(SoulseekSearchUpdateEvent)(self._on_soulseek_search_update)
        EventLinker.on(SoulseekSearchEndEvent)(self._on_soulseek_search_end)

        # style config for rich
        self._console = Console()
        self._progress = Progress(
            SpinnerColumn(spinner_name="earth"),
            TextColumn("{task.description}"),
            BarColumn(
                bar_width=None,
                complete_style="green",
                finished_style="green",
                pulse_style="deep_pink4",
                style="deep_pink4"
            ),
            TaskProgressColumn(style="green"),
            TimeRemainingColumn(),
            console=self._console,
            refresh_per_second=10,
            expand=True
        )

    def run(self):
        self._progress.start()

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
            metadata.reflect(bind=self._db_engine)
            metadata.drop_all(self._db_engine)

        # initialize the tables defined in souldb.py
        Base.metadata.create_all(self._db_engine)

        # populate the database with metadata found from files in the users output directory
        add_local_library_to_db(self._sql_session, self._app_params.output_path, self._app_params.valid_music_extensions)

        if NEW_TRACK_FILEPATH:
            add_local_track_to_db(self._sql_session, NEW_TRACK_FILEPATH)

        # if a search query is provided, download the track
        if SEARCH_QUERY:
            output_path = download_from_search_query(self._soulseek_downloader, SEARCH_QUERY, self._app_params.output_path, self._app_params.youtube_only, self._app_params.youtube_only)
            # TODO: get metadata and insert into database

        # get all playlists from spotify and add them to the database
        if DOWNLOAD_ALL_PLAYLISTS:
            all_playlists_metadata = self._spotify_client.get_all_playlists()
            for playlist_metadata in all_playlists_metadata:
                update_db_with_spotify_playlist(self._sql_session, self._spotify_client, playlist_metadata)

            # TODO: actually download the playlists

        # if the update liked flag is provided, download all liked songs from spotify
        if DOWNLOAD_LIKED:
            download_liked_songs(self._soulseek_downloader, self._spotify_client, self._sql_session, self._app_params.output_path, self._app_params.youtube_only)
        
        # if a playlist url is provided, download the playlist
        # TODO: refactor this function
        if SPOTIFY_PLAYLIST_URL:
            download_playlist_from_spotify_url(self._soulseek_downloader, self._spotify_client, self._sql_session, SPOTIFY_PLAYLIST_URL, self._app_params.output_path)
            pass

        self._progress.stop()

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
        self._app_params.output_path = os.path.abspath(args.output_path) if args.output_path else self._app_params.output_path
        self._app_params.log_enabled = args.log if args.log else self._app_params.log_enabled
        self._app_params.max_download_retries = args.max_retries if args.max_retries else self._app_params.max_download_retries
        self._app_params.youtube_only = args.yt if args.yt else self._app_params.youtube_only
        
        return args
    
    async def _on_soulseek_download_start(self, event: SoulseekDownloadStartEvent):
        """Create a new progress bar for this download."""
        task_id = self._progress.add_task(
            description=f"[light_steel_blue]Downloading:[/light_steel_blue] [bright_white]{event.download_filename}[/bright_white]",
            total=100.0,
        )
        self._download_tasks[event.download_file_id] = task_id

    async def _on_soulseek_download_update(self, event: SoulseekDownloadUpdateEvent):
        """Advance the download bar to the new percent complete."""
        task_id = self._download_tasks.get(event.download_file_id)
        if task_id is not None:
            self._progress.update(task_id, completed=event.percent_complete)

    async def _on_soulseek_download_end(self, event: SoulseekDownloadEndEvent):
        """Finalize and remove the download bar."""
        task_id = self._download_tasks.pop(event.download_file_id, None)
        if task_id is not None:
            self._progress.update(task_id, completed=100.0)
            # self._progress.remove_task(task_id)

    async def _on_soulseek_search_start(self, event: SoulseekSearchStartEvent):
        """Create an indeterminate spinner for the search."""
        task_id = self._progress.add_task(
            description=f"[light_steel_blue]Searching Soulseek for:[/light_steel_blue] [bright_white]“{event.search_query}”[/bright_white]",
            total=None,
        )
        self._search_tasks[event.search_id] = task_id

    async def _on_soulseek_search_update(self, event: SoulseekSearchUpdateEvent):
        """Update the search spinner’s description with count so far."""
        task_id = self._search_tasks.get(event.search_id)
        if task_id is not None:
            self._progress.update(
                task_id,
                description=f"[light_steel_blue]Searching Soulseek for:[/light_steel_blue] [bright_white]“{event.search_query}”[/bright_white] [light_steel_blue]Found[/light_steel_blue] [bright_white]{event.num_found_files}[/bright_white] [light_steel_blue]files[/light_steel_blue]",
            )

    async def _on_soulseek_search_end(self, event: SoulseekSearchEndEvent):
        """Remove the search spinner when complete."""
        task_id = self._search_tasks.pop(event.search_id, None)
        if task_id is not None:
            self._progress.remove_task(task_id)

        self._console.print(f"[light_steel_blue]Finished Soulseek search for: [/light_steel_blue][bright_white]“{event.search_query}”[/bright_white] [light_steel_blue]Found[/light_steel_blue] [bright_white]{event.num_relevant_files}[/bright_white] [light_steel_blue]files[/light_steel_blue]")