from typing import Optional, List, Tuple
import sqlalchemy.orm
import sqlalchemy.exc
import logging

from ..models import Tracks, Artists, TrackArtists
from ..schemas import TrackData

logger = logging.getLogger(__name__)

class TracksRepository():
    @classmethod
    def get_track_from_id(cls, sql_session: sqlalchemy.orm.Session, track_id: int) -> Optional[Tracks]:
        """
        Gets an ORM Tracks row from a track id

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            track_id (int): The ID of the Track you want to retrieve

        Returns:
            Optional[Tracks]: The ORM Tracks row, or None
        """
        try:
            return sql_session.query(Tracks).filter_by(id=track_id).one()
        except sqlalchemy.exc.NoResultFound:
            return None
        
    @classmethod
    def search_tracks_by_title(cls, sql_session: sqlalchemy.orm.Session, track_title: str) -> Optional[List[Tracks]]:
        """
        Gets an ORM Tracks row from a track id

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            track_id (int): The ID of the Track you want to retrieve

        Returns:
            Optional[Tracks]: The ORM Tracks row, or None
        """
        try:
            return sql_session.query(Tracks).filter(Tracks.title.ilike(f"%{track_title}%")).all()
        except sqlalchemy.exc.NoResultFound:
            return None

    @classmethod
    def add_track(cls, sql_session: sqlalchemy.orm.Session, track_data: TrackData) -> Optional[Tracks]:
        """
        Adds a new track to the Tracks table

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            track_data (TrackData): The TrackData of the track you want to add

        Returns:
            Optional[Tracks]: The new ORM Tracks row, or None
        """
        # if there is an existing track, return that
        existing_track = cls.get_existing_track(sql_session, track_data)
        if existing_track:
            return existing_track
        
        # create add and flush the new Track
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

        # add artists to the Artist table if they don't already exist, and add associations to the TrackArtist table
        if track_data.artists is not None:
            cls.add_track_artists(sql_session, track, track_data.artists)

        return track
    
    @classmethod 
    def add_track_artists(cls, sql_session: sqlalchemy.orm.Session, track_row: Tracks,  artists: List[Tuple[str, Optional[str]]]):
        for name, spotify_id in artists:
            existing_artist = sql_session.query(Artists).filter_by(name=name).first()

            # if there is not already an Artists row with an identical name, create a new row and assoc
            if existing_artist is None:
                new_artist = Artists(name=name, spotify_id=spotify_id)
                sql_session.add(new_artist)
                sql_session.flush()
                track_artist_assoc = TrackArtists(track_id=track_row.id, artist_id=new_artist.id)
            else:
                # if there is an existing Artist with an idenctical name, create an assoc and update the spotify_id if necessary
                track_artist_assoc = TrackArtists(track_id=track_row.id, artist_id=existing_artist.id)
                if existing_artist.spotify_id is None and spotify_id is not None:
                    existing_artist.spotify_id = spotify_id

            track_row.track_artists.append(track_artist_assoc)
            sql_session.flush()

    @classmethod
    def modify_track(cls, sql_session: sqlalchemy.orm.Session, track_id: int, new_track_data: TrackData) -> None:
        """
        Modifies a track in the Tracks table with new TrackData

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            track_id (int): The ID of the track you want to modify
            new_track_data (TrackData): The new TrackData of the track you want to modify

        Returns:
            None
        """
        # get the existing track, update its fields with the new data if its there, and flush
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
    def remove_track(cls, sql_session: sqlalchemy.orm.Session, track_id: int) -> bool :
        """
        Removes a track from the Tracks table 

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            track_id (int): The ID of the track you want to remove

        Returns:
            bool: Whether or not the track was successfully removed
        """
        # get the track, delete it, and flush
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
    def get_existing_track(cls, session: sqlalchemy.orm.Session, track: TrackData) -> Optional[Tracks]:
        """
        Gets an existing track from the Tracks table. First searches by spotify_id, then by filepath, then by title and album. 

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            track (TrackData): The data of the track you want to search for

        Returns:
            Optional[Tracks]: A ORM Track row with matching data, or None
        """
        if track.spotify_id is not None:
            existing_track = session.query(Tracks).filter_by(spotify_id=track.spotify_id).first()
        elif track.filepath is not None:
            existing_track = session.query(Tracks).filter_by(filepath=track.filepath).first()
        else:
            existing_track = session.query(Tracks).filter_by(title=track.title, album=track.album).first()

        return existing_track

    @classmethod
    def bulk_add_tracks(cls, sql_session: sqlalchemy.orm.Session, track_data_list: List[TrackData]) -> None:
        """
        Adds a set of tracks to the Tracks table in an efficient manner

        Args: 
            sql_session (sqlalchemy.orm.Session): Your open SQLAlchemy Session
            track_data_list (Set[TrackData]): The set of TrackData you want to add

        Returns:
            None
        """
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
        new_tracks: List[TrackData] = []
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