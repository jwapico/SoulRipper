import logging
from typing import Optional, List, Tuple
import datetime
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.exc

from ..models import Playlists, Tracks, PlaylistTracks
from ..schemas import TrackData
from .tracks_repository import TracksRepository

logger = logging.getLogger(__name__)

class PlaylistsRepository():
    @classmethod
    def get_playlist_by_spotify_id(clc, sql_session: sqlalchemy.orm.Session, spotify_id: str) -> Optional[Playlists]:
        """
        Gets an ORM Playlists row from spotify_id

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            spotify_id (str): The Spotify ID of the playlist you want to look up

        Returns:
            Optional[Playlists]: The matching playlist row, or None
        """
        try:
            return sql_session.query(Playlists).filter_by(spotify_id=spotify_id).one()
        except sqlalchemy.exc.NoResultFound:
            return None
        
    @classmethod
    def search_for_playlist_by_title(clc, sql_session: sqlalchemy.orm.Session, playlist_name: str) -> Optional[Playlists]:
        """
        Gets an ORM Playlists row searching by playlist name

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            playlist_name (str): The name of the playlist you want to look up

        Returns:
            Optional[Playlists]: The matching playlist row, or None
        """
        try:
            return sql_session.query(Playlists).filter_by(name=playlist_name).one()
        except sqlalchemy.exc.NoResultFound:
            return None
    
    @classmethod
    def get_playlist_track_rows(clc, sql_session: sqlalchemy.orm.Session, playlist_id: int) -> Optional[List[Tracks]]:
        """
        Gets a list of ORM Playlists rows from a playlist

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            playlist_id (int): The ID of the playlist you want to retrieve all the Tracks from

        Returns:
            Optional[List[Playlists]]: A list of matching playlist rows, or None
        """
        return sql_session.query(PlaylistTracks).filter_by(playlist_id=playlist_id).all()

    @classmethod
    def add_playlist(clc, sql_session: sqlalchemy.orm.Session, spotify_id: str, name: str, description: str) -> Playlists:
        """
        Adds a new row to the Playlists table

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            spotify_id (str): The Spotify ID of the playlist you want to add
            name (str): The name of the playlist you want to add
            description (str): The description of the playlist you want to add 

        Returns:
            Playlists: The new Playlists row
        """
        # if there is an existing playlist with an identical spotify_id or title, return that 
        existing_playlist = PlaylistsRepository.get_playlist_by_spotify_id(sql_session=sql_session, spotify_id=spotify_id) or PlaylistsRepository.search_for_playlist_by_title(sql_session=sql_session, playlist_name=name)
        if existing_playlist:
            return existing_playlist

        # create, add, flush, and return the new playlist
        new_playlist = Playlists(
            spotify_id=spotify_id, 
            name=name, 
            description=description
        )

        sql_session.add(new_playlist)
        sql_session.flush()

        return new_playlist

    @classmethod
    def add_tracks_to_playlist(clc, sql_session: sqlalchemy.orm.Session, playlist_track_data: List[Tuple[TrackData, datetime.datetime]], playlist_row: Playlists) -> None:
        """
        Adds a list of tracks (with their added timestamps) to the PlaylistTracks association table

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            playlist_track_data (List[Tuple[TrackData, datetime.datetime]]): The list of TrackData along with its data added
            playlist_row (Playlists): The ORM Playlists row you want to add the tracks to

        Returns:
            None
        """
        # first add all the tracks to the Tracks table
        TracksRepository.bulk_add_tracks(sql_session, [track_data for track_data, _ in playlist_track_data])
        
        # make a dict of existing associations where the key is the playlist_id and track_id so we can check for duplicates
        existing_assoc_keys = {
            (playlist_id, track_id)
            for playlist_id, track_id in sql_session.query(
                PlaylistTracks.playlist_id,
                PlaylistTracks.track_id
            ).all()
        }

        # for each track in the playlist, create a new PlaylistTracks association entry 
        for track_data, date_added in playlist_track_data:
            track_row = TracksRepository.get_existing_track(sql_session, track_data)

            if track_row is None:
                logger.error(f"couldnt find track in Tracks table even though it should have been bulk added. TrackData: {track_data}")
                track_row = TracksRepository.add_track(track_data)

            key = (playlist_row.id, track_row.id)
            if key not in existing_assoc_keys:
                existing_assoc_keys.add(key)
                playlist_row.playlist_tracks.append(
                    PlaylistTracks(
                        playlist_id=playlist_row.id,
                        track_id=track_row.id,
                        added_at=date_added
                    )
                )