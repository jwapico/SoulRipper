from sqlalchemy.ext.asyncio import AsyncSession
import sqlalchemy as sqla
from typing import Optional, List

from ..models import Artists, TrackArtists

class ArtistsRepository:
    @classmethod
    async def get_artists_for_track_id(cls, sql_session: AsyncSession, track_id: int) -> Optional[List[Artists]]:
        """
        Gets a list of ORM Artist rows that were on a track with track_id 

        Args: 
            sql_session (sqlalchemy.ext.asyncio.AsyncSession): Your open SQLAlchemy Session
            track_id (int): The Tracks id that you want to retreive Artists for

        Returns:
            Optional[List[Artists]]: A list of ORM Artists rows, or None
        """
        stmt = sqla.select(TrackArtists.artist_id).where(TrackArtists.track_id == track_id)
        result = await sql_session.execute(stmt)
        artist_ids = result.scalars().all()

        if not artist_ids:
            return None

        artists_stmt = sqla.select(Artists).where(Artists.id.in_(artist_ids))
        artists_result = await sql_session.execute(artists_stmt)
        return list(artists_result.scalars().all())