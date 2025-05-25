from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Tuple
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

# TODO: a lot of this code (and sync services) need to be refactored
# TODO: should this be a class?
# TODO: downloads should happen concurrently: https://www.reddit.com/r/learnpython/comments/rlcbid/asyncio_make_2_functions_run_concurrently_without/

class DownloadOrchestrator():
    def __init__(self, soulseek_downloader: SoulseekDownloader, spotify_client: SpotifyClient, spotify_synchronizer: SpotifySynchronizer, sql_session: AsyncSession, app_params: AppParams):
        self._soulseek_downloader = soulseek_downloader
        self._spotify_synchronizer = spotify_synchronizer
        self._spotify_client = spotify_client
        self._sql_session = sql_session
        self._app_params = app_params

    async def download_track(self, search_query: str) -> str:
        """
        Downloads a track from soulseek or youtube, only downloading from youtube if the query is not found on soulseek

        Args:
            search_query (str): the song to download, can be a search query
            output_path (str): the directory to download the song to

        Returns:
            str: the path to the downloaded file
        """
        if self._app_params.youtube_only:
            return await download_track_ytdlp(search_query, self._app_params.output_path)

        download_path = await self._soulseek_downloader.download_track(search_query, self._app_params.output_path, self._app_params.max_download_retries)

        if download_path is None:
            download_path = await download_track_ytdlp(search_query, self._app_params.output_path)

        # TODO: make sure database is updated

        return download_path

    async def download_liked_songs(self) -> bool:
        # TODO: this function takes a while to run, we should find a way to check if there any changes before calling it
        # add the users liked songs to the database
        liked_playlist = await self._spotify_synchronizer.update_db_with_spotify_liked_tracks()

        if liked_playlist is None:
            logger.error("No playlist row was not returned by update_db_with_spotify_liked_tracks")
            return False
        
        liked_playlist_tracks_rows = await PlaylistsRepository.get_playlist_track_rows(self._sql_session, liked_playlist.id)

        if liked_playlist_tracks_rows is None:
            logger.error("Could not retreive liked playlist tracks from database.")
            return False

        try:
            # TODO: maybe we should be using the download_track function with a TrackData instead of the search query, hard to get TrackData though since also need to get artists
            #    - we should write a get_trackdata classmethod that will do all this for us
            for playlist_track_row in liked_playlist_tracks_rows:
                track_id = playlist_track_row.track_id
                track_row = await TracksRepository.get_track_from_id(sql_session=self._sql_session, track_id=track_id)

                if track_row is not None:
                    if track_row.filepath is None:
                        artist_rows = await ArtistsRepository.get_artists_for_track_id(self._sql_session, track_id)
                        if artist_rows is not None:
                            track_artists = ", ".join([artist_row.name for artist_row in artist_rows])

                            search_query = f"{track_row.title} - {track_artists}"

                            filepath = await self.download_track(search_query)
                            track_row.filepath = filepath
                            await self._sql_session.commit()

        except Exception as e:
            await self._sql_session.rollback()
            raise e

        return True
        
    # TODO: bruhhhhhhhhhhh the spotify api current_user_saved_tracks() function doesn't return local files FUCK SPOTIFYU there has to be a workaround
    async def download_liked_tracks_from_spotify_data(self):
        liked_tracks_data = await self._spotify_client.get_liked_tracks()
        relevant_tracks_data: List[Tuple[TrackData, datetime.datetime]] = self._spotify_synchronizer.get_track_data_from_playlist(liked_tracks_data)

        track_rows_and_data = []
        for track, _ in relevant_tracks_data:
            existing_track = await TracksRepository.get_existing_track(self._sql_session, track)
            if existing_track is None:
                filepath = await self.download_from_track_data(track)
                track.filepath = filepath

                track_row = await TracksRepository.add_track(self._sql_session, track)
                track_rows_and_data.append((track_row, track))

        await PlaylistsRepository.add_playlist(self._sql_session, spotify_id=None, name="SPOTIFY_LIKED_SONGS", description="User liked songs on Spotify - This playlist is generated by SoulRipper")

    # TODO: this is where better search will happen - construct query from trackdata
    async def download_from_track_data(self, track: TrackData) -> str:
        artists = ', '.join([artist[0] for artist in track.artists]) if track.artists else ""
        search_query = f"{track.title} - {artists}"
        download_path = await self.download_track(search_query)
        return download_path

    async def download_all_playlists(self):
        playlists_data = await PlaylistsRepository.get_all_playlists(self._sql_session)

        if playlists_data:
            for playlist_data in playlists_data:
                if playlist_data.id:
                    await self.download_playlist(playlist_data.id)

    async def download_playlist(self, playlist_id: int) -> None:
        """
        Downloads all the tracks of a playlist in the database

        Args:
            self._sql_session (AsyncSession): The sqlalchemy AsyncSession
            playlist_id (int): The id of the playlist to download
        """

        playlist_track_rows = await PlaylistsRepository.get_playlist_track_rows(self._sql_session, playlist_id)

        if playlist_track_rows is None:
            logger.error(f"Could not retreive playlist tracks from database. Playlist id: {playlist_id}")
            return
        
        playlist_track_data = await PlaylistsRepository.get_track_data(self._sql_session, playlist_id)

        if playlist_track_data:
            for track in playlist_track_data:
                search_query = f"{track.title} - {', '.join([artist[0] for artist in track.artists]) if track.artists else ''}"
                output_filepath = await self.download_track(search_query)
                # TODO: set filepath field in db