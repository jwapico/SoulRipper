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

# if we find that functionality in these crud files is being duplicated across multiple models (i.e. we have duplicated get_by_id methods) we can make a BaseCRUD class that all models inherit from
# TODO: we may want to refactor this into a class at some point

class PlaylistsRepository():
    @classmethod
    def get_playlist_by_spotify_id(clc, sql_session: sqlalchemy.orm.Session, spotify_id: str) -> Optional[Playlists]:
        try:
            return sql_session.query(Playlists).filter_by(spotify_id=spotify_id).one()
        except sqlalchemy.exc.NoResultFound as e:
            return None
        
    @classmethod
    def search_for_playlist_by_title(clc, sql_session: sqlalchemy.orm.Session, playlist_name: str) -> Optional[Playlists]:
        try:
            return sql_session.query(Playlists).filter_by(name=playlist_name).one()
        except sqlalchemy.exc.NoResultFound as e:
            return None
    
    @classmethod
    def get_playlist_track_rows(clc, sql_session: sqlalchemy.orm.Session, playlist_id: int) -> Optional[List[Tracks]]:
        return sql_session.query(PlaylistTracks).filter_by(playlist_id=playlist_id).all()

    @classmethod
    def add_playlist(clc, sql_session: sqlalchemy.orm.Session, spotify_id: str, name: str, description: str) -> Playlists:
        existing_playlist = PlaylistsRepository.get_playlist_by_spotify_id(sql_session=sql_session, spotify_id=spotify_id) or PlaylistsRepository.search_for_playlist_by_title(sql_session=sql_session, playlist_name=name)

        if existing_playlist:
            return existing_playlist

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