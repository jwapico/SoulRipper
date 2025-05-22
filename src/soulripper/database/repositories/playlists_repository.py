import logging
from typing import Optional, List, Tuple
import datetime
import sqlalchemy as sqla
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Playlists, PlaylistTracks
from ..schemas import TrackData, PlaylistData
from .tracks_repository import TracksRepository
from .artists_repository import ArtistsRepository

logger = logging.getLogger(__name__)

class PlaylistsRepository():
    @classmethod
    async def get_playlist_by_spotify_id(cls, sql_session: AsyncSession, spotify_id: str) -> Optional[Playlists]:
        """
        Gets an ORM Playlists row from spotify_id

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            spotify_id (str): The Spotify ID of the playlist you want to look up

        Returns:
            Optional[Playlists]: The matching playlist row, or None
        """
        stmt = sqla.select(Playlists).where(Playlists.spotify_id == spotify_id)
        result = await sql_session.execute(stmt)
        return result.scalars().first()
        
    @classmethod
    async def search_for_playlist_by_title(cls, sql_session: AsyncSession, playlist_name: str) -> Optional[Playlists]:
        """
        Gets an ORM Playlists row searching by playlist name

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            playlist_name (str): The name of the playlist you want to look up

        Returns:
            Optional[Playlists]: The matching playlist row, or None
        """
        stmt = sqla.select(Playlists).where(Playlists.name == playlist_name)
        result = await sql_session.execute(stmt)
        return result.scalars().first()
    
    @classmethod
    async def get_playlist_track_rows(cls, sql_session: AsyncSession, playlist_id: int) -> Optional[List[PlaylistTracks]]:
        """
        Gets a list of ORM Playlists rows from a playlist

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            playlist_id (int): The ID of the playlist you want to retrieve all the Tracks from

        Returns:
            Optional[List[Playlists]]: A list of matching playlist rows, or None
        """
        stmt = sqla.select(PlaylistTracks).where(PlaylistTracks.playlist_id == playlist_id)
        result = await sql_session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def add_playlist(cls, sql_session: AsyncSession, spotify_id: Optional[str], name: str, description: str) -> Playlists:
        """
        Adds a new row to the Playlists table

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            spotify_id (str): The Spotify ID of the playlist you want to add
            name (str): The name of the playlist you want to add
            description (str): The description of the playlist you want to add 

        Returns:
            Playlists: The new Playlists row
        """
        # if there is an existing playlist with an identical spotify_id or title, return that 
        if spotify_id is not None:
            existing_playlist = await PlaylistsRepository.get_playlist_by_spotify_id(sql_session=sql_session, spotify_id=spotify_id) or await PlaylistsRepository.search_for_playlist_by_title(sql_session=sql_session, playlist_name=name)
            if existing_playlist:
                return existing_playlist

        # create, add, flush, and return the new playlist
        new_playlist = Playlists(
            spotify_id=spotify_id, 
            name=name, 
            description=description
        )

        sql_session.add(new_playlist)
        await sql_session.flush()

        return new_playlist

    @classmethod
    async def add_tracks_to_playlist(cls, sql_session: AsyncSession, playlist_track_data: List[Tuple[TrackData, datetime.datetime]], playlist_row: Playlists) -> None:
        """
        Adds a list of tracks (with their added timestamps) to the PlaylistTracks association table

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            playlist_track_data (List[Tuple[TrackData, datetime.datetime]]): The list of TrackData along with its data added
            playlist_row (Playlists): The ORM Playlists row you want to add the tracks to

        Returns:
            None
        """
        # first add all the tracks to the Tracks table
        await TracksRepository.bulk_add_tracks(sql_session, [track_data for track_data, _ in playlist_track_data])
        
        # make a dict of existing associations where the key is the playlist_id and track_id so we can check for duplicates
        stmt = sqla.select(PlaylistTracks.playlist_id, PlaylistTracks.track_id)
        result = await sql_session.execute(stmt)
        existing_assoc_keys = {(row.playlist_id, row.track_id) for row in result}

        # for each track in the playlist, create a new PlaylistTracks association entry 
        for track_data, date_added in playlist_track_data:
            track_row = await TracksRepository.get_existing_track(sql_session, track_data)

            if track_row is None:
                logger.error(f"couldnt find track in Tracks table even though it should have been bulk added. TrackData: {track_data}")
                track_row = await TracksRepository.add_track(sql_session, track_data)

            if track_row is not None:
                key = (playlist_row.id, track_row.id)
                if key not in existing_assoc_keys:
                    existing_assoc_keys.add(key)
                    new_assoc = PlaylistTracks(playlist_id=playlist_row.id, track_id=track_row.id, added_at=date_added)
                    sql_session.add(new_assoc)
                    
            else:
                logger.error(f"track_row was not actually created after calling TracksRepository.add_track() with track_data: {track_data}")
                continue

        await sql_session.commit()

    @classmethod
    async def get_track_data(cls, sql_session: AsyncSession, playlist_id: int) -> List[TrackData]:
        playlist_tracks = await cls.get_playlist_track_rows(sql_session, playlist_id)

        if playlist_tracks is None:
            logger.info(f"No tracks found for playlist with id: {playlist_id}")
            return []
        
        tracks_data: List[TrackData] = []
        for playlist_track in playlist_tracks:
            track = await TracksRepository.get_track_from_id(sql_session, playlist_track.track_id)
            artist_rows = await ArtistsRepository.get_artists_for_track_id(sql_session, playlist_track.track_id)

            if track:
                artists = [(artist.name, artist.spotify_id) for artist in artist_rows] if artist_rows else None

                tracks_data.append(
                    TrackData(
                        filepath=track.filepath,
                        title=track.title,
                        artists=artists,
                        album=track.album,
                        spotify_id=track.spotify_id,
                        explicit=track.explicit,
                        comments=track.comments,
                        release_date=track.release_date
                    )
                )

        return tracks_data
    
    @classmethod
    async def get_all_playlists(cls, sql_session: AsyncSession) -> Optional[List[PlaylistData]]:
        result = await sql_session.execute(sqla.select(Playlists))
        playlist_rows = result.scalars().all()

        playlists = []
        for playlist in playlist_rows:
            playlist_data = await cls.get_playlist_data(sql_session, playlist.id)
            playlists.append(playlist_data)

        return playlists
    
    @classmethod
    async def get_playlist_data(cls, sql_session: AsyncSession, playlist_id: int) -> Optional[PlaylistData]:
        stmt = sqla.select(Playlists).where(Playlists.id == playlist_id)
        result = await sql_session.execute(stmt)
        playlist_row = result.scalars().one()
        tracks = await cls.get_track_data(sql_session, playlist_id)

        if playlist_row:
            return PlaylistData(
                id=playlist_row.id,
                spotify_id=playlist_row.spotify_id,
                name=playlist_row.name,
                description=playlist_row.description,
                tracks=tracks
            )
