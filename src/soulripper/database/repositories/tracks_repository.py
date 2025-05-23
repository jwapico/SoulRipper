from typing import Optional, List, Tuple
import sqlalchemy as sqla
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from ..models import Tracks, Artists, TrackArtists
from ..schemas import TrackData

logger = logging.getLogger(__name__)

# TODO: Refactor all repositories so the respective schema is the only way to read and write to the database 

class TracksRepository():
    @classmethod
    async def get_track_from_id(cls, sql_session: AsyncSession, track_id: int) -> Optional[Tracks]:
        """
        Gets an ORM Tracks row from a track id

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            track_id (int): The ID of the Track you want to retrieve

        Returns:
            Optional[Tracks]: The ORM Tracks row, or None
        """
        stmt = sqla.select(Tracks).where(Tracks.id == track_id)
        result = await sql_session.execute(stmt)
        return result.scalars().first()
        
    @classmethod
    async def search_tracks_by_title(cls, sql_session: AsyncSession, track_title: str) -> Optional[List[Tracks]]:
        """
        Gets an ORM Tracks row from a track id

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            track_id (int): The ID of the Track you want to retrieve

        Returns:
            Optional[Tracks]: The ORM Tracks row, or None
        """
        stmt = sqla.select(Tracks).where(Tracks.title.ilike(f"%{track_title}%"))
        result = await sql_session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def add_track(cls, sql_session: AsyncSession, track_data: TrackData) -> Optional[Tracks]:
        """
        Adds a new track to the Tracks table

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            track_data (TrackData): The TrackData of the track you want to add

        Returns:
            Optional[Tracks]: The new ORM Tracks row, or None
        """
        # if there is an existing track, return that
        existing_track = await cls.get_existing_track(sql_session, track_data)
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
        await sql_session.flush()

        # add artists to the Artist table if they don't already exist, and add associations to the TrackArtist table
        if track_data.artists is not None:
            await cls.add_track_artists(sql_session, track, track_data.artists)

        return track
    
    @classmethod 
    async def add_track_artists(cls, sql_session: AsyncSession, track_row: Tracks,  artists: List[Tuple[str, Optional[str]]]):
        for name, spotify_id in artists:
            stmt = sqla.select(Artists).where(Artists.name == name)
            result = await sql_session.execute(stmt)
            existing_artist = result.scalars().first()

            # if there is not already an Artists row with an identical name, create a new row and assoc
            if existing_artist is None:
                new_artist = Artists(name=name, spotify_id=spotify_id)
                sql_session.add(new_artist)
                await sql_session.flush()
                track_artist_assoc = TrackArtists(track_id=track_row.id, artist_id=new_artist.id)
                sql_session.add(track_artist_assoc)
            else:
                # if there is an existing Artist with an idenctical name, create an assoc and update the spotify_id if necessary
                track_artist_assoc = TrackArtists(track_id=track_row.id, artist_id=existing_artist.id)
                sql_session.add(track_artist_assoc)
                if existing_artist.spotify_id is None and spotify_id is not None:
                    existing_artist.spotify_id = spotify_id

            await sql_session.flush()

    @classmethod
    async def modify_track(cls, sql_session: AsyncSession, track_id: int, new_track_data: TrackData) -> None:
        """
        Modifies a track in the Tracks table with new TrackData

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            track_id (int): The ID of the track you want to modify
            new_track_data (TrackData): The new TrackData of the track you want to modify

        Returns:
            None
        """
        # get the existing track, update its fields with the new data if its there, and flush
        target_track = await cls.get_track_from_id(sql_session, track_id)

        if target_track:
            target_track.spotify_id = new_track_data.spotify_id if new_track_data.spotify_id is not None else target_track.spotify_id
            target_track.filepath = new_track_data.filepath if new_track_data.filepath is not None else target_track.filepath
            target_track.title = new_track_data.title if new_track_data.title is not None else target_track.title
            target_track.album = new_track_data.album if new_track_data.album is not None else target_track.album
            target_track.release_date = new_track_data.release_date if new_track_data.release_date is not None else target_track.release_date
            target_track.explicit = new_track_data.explicit if new_track_data.explicit is not None else target_track.explicit
            target_track.comments = new_track_data.comments if new_track_data.comments is not None else target_track.comments

            await sql_session.flush()

    @classmethod
    async def remove_track(cls, sql_session: AsyncSession, track_id: int) -> bool :
        """
        Removes a track from the Tracks table 

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            track_id (int): The ID of the track you want to remove

        Returns:
            bool: Whether or not the track was successfully removed
        """
        # get the track, delete it, and flush
        target_track = await cls.get_track_from_id(sql_session, track_id)

        if target_track:
            await sql_session.delete(target_track)
            await sql_session.flush()
            logger.info(f"Successfully removed the track with id: {track_id}")
            return True
        else:
            logger.info(f"Could not find the track you were trying to remove, track_id = {track_id}")
            return False
        
    # TODO: We need a better way of checking for existing tracks when spotify_id and filepath is None
    @classmethod
    async def get_existing_track(cls, session: AsyncSession, track: TrackData) -> Optional[Tracks]:
        """
        Gets an existing track from the Tracks table. First searches by spotify_id, then by filepath, then by title and album. 

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            track (TrackData): The data of the track you want to search for

        Returns:
            Optional[Tracks]: A ORM Track row with matching data, or None
        """
        if track.spotify_id is not None:
            stmt = sqla.select(Tracks).where(Tracks.spotify_id == track.spotify_id)
        elif track.filepath is not None:
            stmt = sqla.select(Tracks).where(Tracks.filepath == track.filepath)
        else:
            stmt = sqla.select(Tracks).where((Tracks.title == track.title) & (Tracks.album == track.album))

        result = await session.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def bulk_add_tracks(cls, sql_session: AsyncSession, track_data_list: List[TrackData]) -> None:
        """
        Adds a set of tracks to the Tracks table in an efficient manner

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            track_data_list (Set[TrackData]): The set of TrackData you want to add

        Returns:
            None
        """
        # get all of the existing spotify ids of tracks in the database so we can make sure we don't re add them
        stmt = sqla.select(Tracks.spotify_id).where(Tracks.spotify_id.isnot(None))
        result = await sql_session.execute(stmt)
        existing_spotify_ids = {sid for (sid,) in result.all()}

        # make a with keys holding unique information on title, album, and filepath so we can make sure we don't re add local tracks 
        stmt = sqla.select(Tracks.title, Tracks.album, Tracks.filepath).where(Tracks.spotify_id.is_(None))
        result = await sql_session.execute(stmt)
        existing_local_tracks = {(track.title, track.album, track.filepath) for track in result.all()}

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
        stmt = sqla.select(Artists)
        result = await sql_session.execute(stmt)
        existing_artists = {artist.name: artist for artist in result.scalars().all()}

        # for each new track, create and append a new orm Track object
        orm_tracks = []
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

        # add and flush the new tracks so we can access their ids in the artist assoc creation process
        sql_session.add_all(orm_tracks)
        await sql_session.flush()

        # for each track, we also need to create a new artist association if the artist doesn't already exist for each artist
        orm_artist_assocs = []
        for i, track in enumerate(orm_tracks):
            track_data = new_tracks[i]
            if track_data.artists:
                for name, artist_spotify_id in track_data.artists:
                    artist = existing_artists.get(name)
                    
                    # create and append a new orm TrackArtists assoc if the artist wasn't already in the database
                    if artist is None:
                        artist = Artists(name=name, spotify_id=artist_spotify_id)
                        sql_session.add(artist)
                        await sql_session.flush()
                        existing_artists[name] = artist

                    assoc = TrackArtists(track_id=track.id, artist_id=artist.id)
                    orm_artist_assocs.append(assoc)

        # now add everything in one shot
        sql_session.add_all(orm_artist_assocs)
        await sql_session.flush()
        logger.info(f"Inserted {len(new_tracks)} new tracks.")