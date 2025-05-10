import sqlalchemy as sqla
from sqlalchemy.orm import Session
from pyventus.events import EventLinker
import logging
import asyncio
import argparse
import sys
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

class CLIOrchestrator():
    def __init__(self, spotify_client: SpotifyClient, sql_session: Session, db_engine: sqla.Engine, soulseek_downloader: SoulseekDownloader, app_params: AppParams = None):
        self._spotify_client = spotify_client
        self._sql_session = sql_session
        self._db_engine = db_engine
        self._soulseek_downloader = soulseek_downloader
        self._app_params = app_params

        self._event_loop = asyncio.AbstractEventLoop
        self._spinner_task = None
        self._spinner_running = False
        self._num_found_files: int

        # attach download event listeners
        EventLinker.on(SoulseekDownloadStartEvent)(self._on_soulseek_download_start)
        EventLinker.on(SoulseekDownloadUpdateEvent)(self._on_soulseek_download_update)
        EventLinker.on(SoulseekDownloadEndEvent)(self._on_soulseek_download_end)

        # attach search event listeners
        EventLinker.on(SoulseekSearchStartEvent)(self._on_soulseek_search_start)
        EventLinker.on(SoulseekSearchUpdateEvent)(self._on_soulseek_search_update)
        EventLinker.on(SoulseekSearchEndEvent)(self._on_soulseek_search_end)

    def run(self):
        """Spins up a new asyncio coroutine that manages the CLI"""

        args = self.parse_cmdline_args()
        DROP_DATABASE = args.drop_database

        # if the flag was provided drop everything in the database
        if DROP_DATABASE:
            input("Warning: This will drop all tables in the database. Press enter to continue...")

            metadata = sqla.MetaData()
            metadata.reflect(bind=self._db_engine)
            metadata.drop_all(self._db_engine)

        # initialize the tables defined in souldb.py
        Base.metadata.create_all(self._db_engine)

        # TODO: experiment with this in and out of async function to see if things are dramatically faster inside
        add_local_library_to_db(self._sql_session, self._app_params.output_path, self._app_params.valid_music_extensions)

        # now enter our main logic from an async function
        asyncio.run(self.async_run(args=args))

    async def async_run(self, args: argparse.Namespace):
        # connect the downloader to the event loop - TODO: i think this will be unnecessary once we refactor everything to use async
        self._event_loop = asyncio.get_event_loop()
        self._soulseek_downloader.event_loop = self._event_loop

        SEARCH_QUERY = args.search_query
        SPOTIFY_PLAYLIST_URL = args.playlist_url
        DOWNLOAD_LIKED = args.download_liked
        DOWNLOAD_ALL_PLAYLISTS = args.download_all_playlists
        NEW_TRACK_FILEPATH = args.add_track

        # populate the database with metadata found from files in the users output directory

        if NEW_TRACK_FILEPATH:
            await asyncio.to_thread(add_local_track_to_db, self._sql_session, NEW_TRACK_FILEPATH)

        # if a search query is provided, download the track
        if SEARCH_QUERY:
            output_path = await asyncio.to_thread(download_from_search_query, self._soulseek_downloader, SEARCH_QUERY, self._app_params.output_path, self._app_params.youtube_only, self._app_params.max_download_retries)
            # TODO: get metadata and insert into database

        # get all playlists from spotify and add them to the database
        if DOWNLOAD_ALL_PLAYLISTS:
            all_playlists_metadata = await asyncio.to_thread(self._spotify_client.get_all_playlists)
            for playlist_metadata in all_playlists_metadata:
                await asyncio.to_thread(update_db_with_spotify_playlist, self._sql_session, self._spotify_client, playlist_metadata)

            # TODO: actually download the playlists

        # if the update liked flag is provided, download all liked songs from spotify
        if DOWNLOAD_LIKED:
            await asyncio.to_thread(download_liked_songs, self._soulseek_downloader, self._spotify_client, self._sql_session, self._app_params.output_path, self._app_params.youtube_only)
        
        # if a playlist url is provided, download the playlist
        # TODO: refactor this function
        if SPOTIFY_PLAYLIST_URL:
            await asyncio.to_thread(download_playlist_from_spotify_url, self._soulseek_downloader, self._spotify_client, self._sql_session, SPOTIFY_PLAYLIST_URL, self._app_params.output_path)

    async def _on_soulseek_search_start(self, event: SoulseekSearchStartEvent):
        self.update_last_line(f"Searching Soulseek for: '{event.search_query}'")
        self._num_found_files = 0
        self._spinner_running = True
        self._spinner_task = asyncio.create_task(self._spinnup_spinner(event=event))

    async def _on_soulseek_search_update(self, event: SoulseekSearchUpdateEvent):
        self._num_found_files = event.num_found_files

    async def _on_soulseek_search_end(self, event: SoulseekSearchEndEvent):
        self._spinner_running = False
        if self._spinner_task:
            await self._spinner_task

        self.update_last_line(f"🌐 Soulseek search finished. Query: {event.search_query} | Relevant files found: {event.num_relevant_files}\n")

    async def _on_soulseek_download_start(self, event: SoulseekDownloadStartEvent):
        self.update_last_line(f"Soulseek download started, filename: {event.download_filename}, user: {event.download_user}")

    async def _on_soulseek_download_update(self, event: SoulseekDownloadUpdateEvent):
        self.update_last_line(f"Soulseek download updated, filename: {event.download_filename} | percent downloaded: {round(event.percent_complete, 2)}")

    async def _on_soulseek_download_end(self, event: SoulseekDownloadEndEvent):
        self.update_last_line(f"Soulseek download finished, filepath: {event.final_filepath}, state: {event.end_state}\n\n")

    async def _spinnup_spinner(self, event: SoulseekSearchStartEvent):
        update_counter = 0
        spinner_frames = ['🌍', '🌏','🌎']
        while self._spinner_running:
            frame = spinner_frames[update_counter % len(spinner_frames)]
            self.update_last_line(f"{frame} Searching Soulseek for: '{event.search_query}' | Total files found: {self._num_found_files}")
            update_counter += 1
            await asyncio.sleep(0.25)

    def update_last_line(self, new_line: str) -> None : 
        """moves the cursor up one line to replace the previous line printed with new_line"""
        sys.stdout.write("\r\x1b[2K" + new_line)
        sys.stdout.flush()  

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
