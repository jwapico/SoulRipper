import logging
from typing import Optional, List
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
            logger.warning(f"No playlist with spotify id: {spotify_id} found, returning None {e}")
            sql_session.rollback()
            return None
        
    @classmethod
    def search_for_playlist_by_title(clc, sql_session: sqlalchemy.orm.Session, playlist_name: str) -> Optional[Playlists]:
        try:
            return sql_session.query(Playlists).filter_by(name=playlist_name).one()
        except sqlalchemy.exc.NoResultFound as e:
            logger.warning(f"No playlist with playlist_name: {playlist_name} found, returning None {e}")
            sql_session.rollback()
            return None
    
    @classmethod
    def get_playlist_track_rows(clc, sql_session: sqlalchemy.orm.Session, playlist_id: int) -> Optional[List[Tracks]]:
        return sql_session.query(PlaylistTracks).filter_by(playlist_id=playlist_id).all()

    @classmethod
    def add_playlist(clc, sql_session: sqlalchemy.orm.Session, spotify_id: str, name: str, description: str) -> Playlists:
        existing_playlist = PlaylistsRepository.get_playlist_by_spotify_id(sql_session=sql_session, spotify_id=spotify_id) or PlaylistsRepository.search_for_playlist_by_title(sql_session=sql_session, playlist_name=name)

        if existing_playlist:
            logger.warning(f"Found an existing playlist with identical spotify_id ({spotify_id}) or name ({name}), returning that one")
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
    def add_track_data_to_playlist(clc, sql_session: sqlalchemy.orm.Session, track_data_list: list[TrackData], playlist_row: Playlists) -> None:
        existing_spotify_ids = set(spotify_id for spotify_id in sql_session.query(Tracks.spotify_id).filter(Tracks.spotify_id.isnot(None)))

        existing_non_spotify_tracks = set(
            (title, album, filepath) for (title, album, filepath) in sql_session.query(
                Tracks.title, Tracks.album, Tracks.filepath
            ).filter(Tracks.spotify_id.is_(None))
        )

        new_tracks = set()
        seen_spotify_ids = set()
        seen_non_spotify = set()

        for track_data in track_data_list:
            if track_data.spotify_id:
                if track_data.spotify_id in existing_spotify_ids or track_data.spotify_id in seen_spotify_ids:
                    continue
                seen_spotify_ids.add(track_data.spotify_id)
            else:
                key = (track_data.title, track_data.album, track_data.filepath)
                if key in existing_non_spotify_tracks or key in seen_non_spotify:
                    continue
                seen_non_spotify.add(key)
            new_tracks.add(track_data)
                
        TracksRepository.bulk_add_tracks(sql_session,new_tracks)
        
        existing_assoc_keys = set(
            (playlist_id, track_id)
            for playlist_id, track_id in sql_session.query(
                PlaylistTracks.playlist_id,
                PlaylistTracks.track_id
            ).all()
        )
        for track_data in track_data_list:
            track = TracksRepository.get_existing_track(sql_session,track_data)
            if track:
                assoc = PlaylistTracks(track_id=track.id, playlist_id=playlist_row.id, added_at=track.date_liked_spotify)
                if (assoc.playlist_id, assoc.track_id) not in existing_assoc_keys:
                    existing_assoc_keys.add(assoc)
                    playlist_row.playlist_tracks.append(assoc)
            else:
                logger.debug(f"track_data is empty in track_data_list: {track_data_list}")