from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Tuple, Optional
import logging
import datetime
import os

from soulripper.database.services import SpotifySynchronizer
from soulripper.database.repositories import TracksRepository, PlaylistsRepository, ArtistsRepository
from soulripper.database.schemas import TrackData, PlaylistData
from soulripper.spotify import SpotifyClient
from soulripper.downloaders import SoulseekDownloader, download_track_ytdlp
from soulripper.utils import AppParams

logger = logging.getLogger(__name__)

# TODO: downloads should happen concurrently: https://www.reddit.com/r/learnpython/comments/rlcbid/asyncio_make_2_functions_run_concurrently_without/
# TODO: download_track should take TrackData and construct a search query - downloading from a search query directly needs to exist but should not be the main method to download a track

class DownloadOrchestrator():
    def __init__(self, soulseek_downloader: SoulseekDownloader, spotify_client: SpotifyClient, spotify_synchronizer: SpotifySynchronizer, sql_session: AsyncSession, app_params: AppParams):
        # TODO: we may not need all of these member variables
        self._soulseek_downloader = soulseek_downloader
        self._spotify_client = spotify_client
        self._sql_session = sql_session
        self._app_params = app_params

    async def download_track(self, track_data: Optional[TrackData] = None, search_query: Optional[str] = None, update_db: Optional[bool] = False) -> Optional[str]:
        """
        Downloads a track from SoulSeek or Youtube, optionally updates the database with it.

        Args:
            track_data (Optional[TrackData]) = None: a TrackData object to construct the search query and update the db with
            search_query (Optional[str]) = None: a search query to use for soulseek and youtube
            update_db (Optional[bool]) = False: Whether or not to update the database

        Returns:
            str: 
        """
        # make sure we have either track data or a search query to work with
        if (track_data is None and search_query is None) or (track_data and search_query):
            raise Exception("Incorrect arguments, you mast pass either a TrackData OR search query")

        # construct the search query from the track data if track data was passed in
        if track_data:
            artists = ', '.join([artist[0] for artist in track_data.artists]) if track_data.artists else ""
            search_query = f"{track_data.title} - {artists}"

            # if an existing track has already been downloaded, return since we dont need to redownload it
            existing_track = await TracksRepository.get_existing_track(self._sql_session, track_data)
            if existing_track and existing_track.filepath:
                return existing_track.filepath
            
        # this is mainly for pylance
        assert search_query is not None

        # download the track from soulseek or youtube
        if self._app_params.youtube_only:
            download_path = await download_track_ytdlp(search_query, self._app_params.output_path)
        else:
            download_path = await self._soulseek_downloader.download_track(search_query, self._app_params.output_path, self._app_params.max_download_retries)
            if download_path is None:
                download_path = await download_track_ytdlp(search_query, self._app_params.output_path)

        # add a new row to the Tracks table with the new filepath if we got one
        if download_path and update_db:
            if track_data:
                track_data.filepath = download_path
            else:
                track_data = TrackData(filepath=download_path)

            await TracksRepository.add_track(self._sql_session, track_data)
            await self._sql_session.commit()

        return download_path

    async def download_playlist(self, playlist_id: int) -> None:
        """
        Downloads all the tracks of a playlist in the database

        Args:
            playlist_id (int): The id of the playlist to download
        """
        playlist_track_rows = await PlaylistsRepository.get_playlist_track_rows(self._sql_session, playlist_id)
        if playlist_track_rows is None:
            logger.error(f"Could not retreive playlist tracks from database. Playlist id: {playlist_id}")
            return
        
        playlist_track_data = await PlaylistsRepository.get_track_data(self._sql_session, playlist_id)
        if playlist_track_data is None:
            logger.error(f"Could not retreive track data for tracks in playlist. Playlist id: {playlist_id}")
            return

        for track_data in playlist_track_data:
            track_data.filepath = await self.download_track(track_data=track_data, update_db=True)

    async def download_all_playlists(self) -> None:
        """
        Downloads all of the tracks in all of the users playlists
        """
        playlists_data = await PlaylistsRepository.get_all_playlists(self._sql_session)
        if playlists_data:
            for playlist_data in playlists_data:
                if playlist_data.id:
                    await self.download_playlist(playlist_data.id)
    
    async def download_liked_songs(self) -> None:
        """
        Downloads all the users liked songs
        """
        liked_playlist_rows = await PlaylistsRepository.search_for_playlist_by_title(self._sql_session, "SPOTIFY_LIKED_SONGS")

        if liked_playlist_rows:
            await self.download_playlist(liked_playlist_rows.id)
        else:
            logger.error("No playlist row was not returned by update_db_with_spotify_liked_tracks")