from pyventus.events import EventLinker
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine, AsyncEngine
import dotenv
import alive_progress
from alive_progress import config_handler
import logging
import asyncio
import argparse
import sys
import os

from soulripper.database import Base, LocalSynchronizer, SpotifySynchronizer
from soulripper.utils import AppParams
from soulripper.spotify import SpotifyClient, SpotifyUserData
from soulripper.downloaders import (
    SoulseekDownloader, 
    DownloadOrchestrator,
    SoulseekDownloadStartEvent, 
    SoulseekDownloadUpdateEvent, 
    SoulseekDownloadEndEvent, 
    SoulseekSearchStartEvent, 
    SoulseekSearchUpdateEvent, 
    SoulseekSearchEndEvent
)

logger = logging.getLogger(__name__)

class CLIOrchestrator():
    def __init__(self, app_params: AppParams):
        self._app_params: AppParams = app_params

        self._spotify_client: SpotifyClient
        self._soulseek_downloader: SoulseekDownloader
        self._db_session_maker: async_sessionmaker[AsyncSession]
        self._db_engine: AsyncEngine

        # these are just for terminal/printing state
        self._spinner_task = None
        self._spinner_running = False
        self._num_found_files: int

        # this is config for the download bar, it forces us to use a context
        self._download_bar = None
        self._download_bar_ctx = None
        self._update_terminal_size()

        # attach download event listeners
        EventLinker.on(SoulseekDownloadStartEvent)(self._on_soulseek_download_start)
        EventLinker.on(SoulseekDownloadUpdateEvent)(self._on_soulseek_download_update)
        EventLinker.on(SoulseekDownloadEndEvent)(self._on_soulseek_download_end)

        # attach search event listeners
        EventLinker.on(SoulseekSearchStartEvent)(self._on_soulseek_search_start)
        EventLinker.on(SoulseekSearchUpdateEvent)(self._on_soulseek_search_update)
        EventLinker.on(SoulseekSearchEndEvent)(self._on_soulseek_search_end)

        # async sqlalchemy initialization
        self._db_engine = create_async_engine(f"sqlite+aiosqlite:///{self._app_params.database_path}", echo=self._app_params.db_echo)
        self._db_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(bind=self._db_engine, expire_on_commit=False, class_=AsyncSession)

    async def run(self):
        """Spins up a new asyncio coroutine that manages the CLI - also executes some database initialization steps"""
        args = self._parse_cmdline_args()
        dotenv.load_dotenv()   

        SEARCH_QUERY = args.search_query
        SPOTIFY_PLAYLIST_URL = args.playlist_url
        DOWNLOAD_LIKED = args.download_liked
        DOWNLOAD_ALL_PLAYLISTS = args.download_all_playlists
        NEW_TRACK_FILEPATH = args.add_track
        DROP_DATABASE = args.drop_database

        # spotify init
        SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
        SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
        SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
        if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET and SPOTIFY_REDIRECT_URI:
            spotify_user_data = SpotifyUserData(
                CLIENT_ID=SPOTIFY_CLIENT_ID, 
                CLIENT_SECRET=SPOTIFY_CLIENT_SECRET, 
                REDIRECT_URI=SPOTIFY_REDIRECT_URI, 
                SCOPE=self._app_params.spotify_scope
            )
            self._spotify_client = await SpotifyClient.init(spotify_user_data)
        else:
            raise Exception("You need to set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and SPOTIFY_REDIRECT_URI in your .env file")

        # slskd init
        SLSKD_API_KEY = os.getenv("SLSKD_API_KEY")
        if SLSKD_API_KEY:
            self._soulseek_downloader = SoulseekDownloader(SLSKD_API_KEY)
        else:
            raise Exception("You need to set SLSKD_API_KEY in your .env file")
        
        # create new db session and call different code depending on args
        async with self._db_session_maker() as session:
            async with self._soulseek_downloader as soulseek_downloader:
                self._local_synchronizer = LocalSynchronizer(session)
                self._spotify_synchronizer = SpotifySynchronizer(session, self._spotify_client)
                self._download_orchestrator = DownloadOrchestrator(self._soulseek_downloader, self._spotify_client, self._spotify_synchronizer, session, self._app_params)

                if DROP_DATABASE:
                    input("Warning: This will drop all tables in the database. Press enter to continue...")

                    async with self._db_engine.begin() as conn:
                        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn))
                        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn))
                else:
                    await self._local_synchronizer.add_local_library_to_db(self._app_params.output_path, self._app_params.valid_music_extensions)

                # manual way to add a new local track to the database
                if NEW_TRACK_FILEPATH:
                    await self._local_synchronizer.add_local_track_to_db(NEW_TRACK_FILEPATH)

                # attempts a soulseek then youtube download for the given search query
                if SEARCH_QUERY:
                    await self._download_orchestrator.download_track(search_query=SEARCH_QUERY, update_db=True)

                # gets all playlists from spotify, adds them to the database, then downloads each track
                if DOWNLOAD_ALL_PLAYLISTS:
                    await self._spotify_synchronizer.update_db_with_all_playlists()
                    await self._download_orchestrator.download_all_playlists()

                # downloads all the users liked songs from spotify
                if DOWNLOAD_LIKED:
                    await self._spotify_synchronizer.update_db_with_spotify_liked_tracks()
                    await self._download_orchestrator.download_liked_songs()
                
                # if a playlist url is provided, download the playlist
                if SPOTIFY_PLAYLIST_URL:
                    playlist_id = self._spotify_client.extract_playlist_id_from_url(SPOTIFY_PLAYLIST_URL)
                    playlist_metadata = await self._spotify_client.get_playlist_info(playlist_id)

                    if playlist_metadata:
                        playlist_row = await self._spotify_synchronizer.update_db_with_spotify_playlist(playlist_metadata)
                        await self._download_orchestrator.download_playlist(playlist_row.id)

    def _parse_cmdline_args(self) -> argparse.Namespace:
        """creates an argparse parser, adds all the arguments, and updates _app_params with parsed values. returns the args"""

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

        self._app_params.output_path = os.path.abspath(args.output_path) if args.output_path else self._app_params.output_path
        self._app_params.log_enabled = args.log if args.log else self._app_params.log_enabled
        self._app_params.max_download_retries = args.max_retries if args.max_retries else self._app_params.max_download_retries
        self._app_params.youtube_only = args.yt if args.yt else self._app_params.youtube_only
        
        return args
    
    # printing utilitiy: (TODO: printing needs to be refactored)

    async def _spinnup_spinner(self, event: SoulseekSearchStartEvent):
        """starts a new async coroutine which simply updates the console with a spinning earth emoji"""
        update_counter = 0
        spinner_frames = ['🌍', '🌏','🌎']
        while self._spinner_running:
            frame = spinner_frames[update_counter % len(spinner_frames)]
            self._update_last_line(f"{frame} Searching Soulseek for: '{event.search_query}' | Total files found: {self._num_found_files}")
            update_counter += 1
            await asyncio.sleep(0.25)

    def _update_last_line(self, new_line: str) -> None : 
        """moves the cursor up one line to replace the previous line printed with new_line"""
        sys.stdout.write("\r\x1b[2K" + new_line)
        sys.stdout.flush()

    def _update_terminal_size(self) -> None:
        """update the length gloal config of alive progress to be the 50% the size of the terminal. For some reason it specefies the length of the bar not the entire text"""
        new_len = os.get_terminal_size().columns - int(os.get_terminal_size().columns / 2)
        config_handler.set_global(length=new_len, bar='notes') # type: ignore

    # event handlers:

    async def _on_soulseek_download_start(self, event: SoulseekDownloadStartEvent):
        """initializes a progress bar for the download"""
        self._update_terminal_size()

        self._download_bar_ctx = alive_progress.alive_bar(100, manual=True, title=f"Downlading '{event.download_filename}'", monitor="{count}%")
        self._download_bar = self._download_bar_ctx.__enter__()

    async def _on_soulseek_download_update(self, event: SoulseekDownloadUpdateEvent):
        """updates the progress bar"""
        if self._download_bar is not None:
            self._download_bar(round(event.percent_complete / 100, 2))

    async def _on_soulseek_download_end(self, event: SoulseekDownloadEndEvent):
        """cleans up the progress bar"""
        if self._download_bar is not None:
            if event.end_state == "Completed, Succeeded":
                self._download_bar(1.0)
            else:
                self._download_bar(0.0)
        if self._download_bar_ctx is not None:
            self._download_bar_ctx.__exit__(None, None, None)

        self._download_bar = None
        self._download_bar_ctx = None

    async def _on_soulseek_search_start(self, event: SoulseekSearchStartEvent):
        """initializes a new earth spinner and does some printing"""

        self._update_last_line(f"Searching Soulseek for: '{event.search_query}'")
        self._num_found_files = 0
        self._spinner_running = True
        self._spinner_task = asyncio.create_task(self._spinnup_spinner(event=event))

    async def _on_soulseek_search_update(self, event: SoulseekSearchUpdateEvent):
        """updates the number of found files"""
        self._num_found_files = event.num_found_files

    async def _on_soulseek_search_end(self, event: SoulseekSearchEndEvent):
        """stops the spinner and does some printing"""
        self._spinner_running = False
        if self._spinner_task:
            await self._spinner_task

        self._update_last_line(f"🌐 Soulseek search finished. Query: {event.search_query} | Relevant files found: {event.num_relevant_files}\n")

