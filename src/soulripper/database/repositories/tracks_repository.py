from typing import Optional, List
import sqlalchemy.orm
import sqlalchemy.exc
import logging

from ..models import Tracks, Artists, TrackArtists
from ..schemas import TrackData

logger = logging.getLogger(__name__)

class TracksRepository():
    @classmethod
    def get_track_from_id(clc, sql_session: sqlalchemy.orm.Session, track_id: int) -> Optional[Tracks]:
        try:
            return sql_session.query(Tracks).filter_by(id=track_id).one()
        except sqlalchemy.exc.NoResultFound as e:
            logger.warning(f"No track with track_id: {track_id} found, returning None {e}")
            sql_session.rollback()
            return None
        
    @classmethod
    def search_tracks_by_title(clc, sql_session: sqlalchemy.orm.Session, track_title: str) -> Optional[List[Tracks]]:
        results = sql_session.query(Tracks).filter(Tracks.title.ilike(f"%{track_title}%")).all()
        return results

    @classmethod
    def add_track(clc, sql_session: sqlalchemy.orm.Session, track_data: TrackData) -> Optional[Tracks]:
        existing_track = clc.get_existing_track(sql_session, track_data)
        
        if existing_track:
            return existing_track
        
        track = Tracks(
            spotify_id=track_data.spotify_id,
            filepath=track_data.filepath,
            title=track_data.title,
            album=track_data.album,
            release_date=track_data.release_date,
            explicit=track_data.explicit,
            comments=track_data.comments
        )

        sql_session.add(track)
        sql_session.flush()

        # add artists to the Artist table if they don't already exist, and add them to the TrackArtist association table
        if track_data.artists is not None:
            for name, spotify_id in track_data.artists:
                existing_artist = sql_session.query(Artists).filter_by(name=name).first()

                if existing_artist is None:
                    new_artist = Artists(name=name, spotify_id=spotify_id)
                    sql_session.add(new_artist)
                    sql_session.flush()
                    track_artist_assoc = TrackArtists(track_id=track.id, artist_id=new_artist.id)
                else:
                    track_artist_assoc = TrackArtists(track_id=track.id, artist_id=existing_artist.id)

                track.track_artists.append(track_artist_assoc)

        return track

    @classmethod
    def modify_track(clc, sql_session: sqlalchemy.orm.Session, track_id: int, new_track_data: TrackData) -> None:
        existing_track = sql_session.query(Tracks).filter_by(id=track_id).one()
        
        existing_track.spotify_id = new_track_data.spotify_id if new_track_data.spotify_id is not None else existing_track.spotify_id
        existing_track.filepath = new_track_data.filepath if new_track_data.filepath is not None else existing_track.filepath
        existing_track.title = new_track_data.title if new_track_data.title is not None else existing_track.title
        existing_track.album = new_track_data.album if new_track_data.album is not None else existing_track.album
        existing_track.release_date = new_track_data.release_date if new_track_data.release_date is not None else existing_track.release_date
        existing_track.explicit = new_track_data.explicit if new_track_data.explicit is not None else existing_track.explicit
        existing_track.comments = new_track_data.comments if new_track_data.comments is not None else existing_track.comments

        sql_session.flush()

    @classmethod
    def remove_track(clc, sql_session: sqlalchemy.orm.Session, track_id: int) -> bool :
        track = sql_session.query(Tracks).filter_by(id=track_id).one()

        if track:
            sql_session.delete(track)
            sql_session.flush()
            logger.info(f"Successfully removed the track with id: {track_id}")
            return True
        else:
            logger.info(f"Could not find the track you were trying to remove, track_id = {track_id}")
            return False
        
    # TODO: We need a better way of checking for existing tracks when spotify_id and filepath is None
    @classmethod
    def get_existing_track(clc, session: sqlalchemy.orm.Session, track: TrackData) -> Optional[Tracks]:
        if track.spotify_id is not None:
            existing_track = session.query(Tracks).filter_by(spotify_id=track.spotify_id).first()
        elif track.filepath is not None:
            existing_track = session.query(Tracks).filter_by(filepath=track.filepath).first()
        else:
            existing_track = session.query(Tracks).filter_by(title=track.title, album=track.album).first()

        return existing_track

    @classmethod
    def bulk_add_tracks(clc, sql_session: sqlalchemy.orm.Session, track_data_list: set[TrackData]) -> None:
        # get all of the existing spotify ids of tracks in the database so we can make sure we don't re add them
        existing_spotify_ids = {
            sid 
            for (sid,) in sql_session.query(Tracks.spotify_id).filter(Tracks.spotify_id.isnot(None)).all()}

        # make a with keys holding unique information on title, album, and filepath so we can make sure we don't re add local tracks 
        existing_local_tracks = {
            (track.title, track.album, track.filepath)
            for track in sql_session.query(Tracks.title, Tracks.album, Tracks.filepath).filter(Tracks.spotify_id.is_(None)).all()
        }

        # build a list of new_tracks which are not already present in the database/found in the dicts above 
        new_tracks = []
        for track_data in track_data_list:
            if track_data.spotify_id is None:
                key = (track_data.title, track_data.album, track_data.filepath)
                if key not in existing_local_tracks:
                    existing_local_tracks.add(key)
                    new_tracks.append(track_data)
            else:
                if track_data.spotify_id not in existing_spotify_ids:
                    existing_spotify_ids.add(track_data.spotify_id)
                    new_tracks.append(track_data)

        # create a dict of all artists with their names as keys so we can make sure we aren't adding duplicates 
        existing_artists = {
            artist.name: artist
            for artist in sql_session.query(Artists).all()
        }

        # initialize empty arrays for orm track rows and orm associations
        orm_tracks = []
        orm_artist_assocs = []

        # for each new track, create and append a new orm Track object, as well as create a new artist association if the artist doesn't already exist for each artist
        for track_data in new_tracks:
            track = Tracks(
                spotify_id=track_data.spotify_id,
                filepath=track_data.filepath,
                title=track_data.title,
                album=track_data.album,
                release_date=track_data.release_date,
                explicit=track_data.explicit,
                comments=track_data.comments
            )

            orm_tracks.append(track)

            # create and append a new orm TrackArtists assoc if the artist wasn't already in the database
            if track_data.artists:
                for name, artist_spotify_id in track_data.artists:
                    artist = existing_artists.get(name)
                    if artist is None:
                        artist = Artists(name=name, spotify_id=artist_spotify_id)
                        sql_session.add(artist)
                        sql_session.flush()
                        existing_artists[name] = artist

                    assoc = TrackArtists(track=track, artist=artist)
                    orm_artist_assocs.append(assoc)

        # now add everything in one shot
        sql_session.add_all(orm_tracks)
        sql_session.add_all(orm_artist_assocs)
        sql_session.flush()
        logger.info(f"Inserted {len(new_tracks)} new tracks.")