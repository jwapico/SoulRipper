import sqlalchemy.orm
from typing import Optional, List

from ..models import Artists, TrackArtists

class ArtistsRepository:
    @classmethod
    def get_artists_for_track_id(clc, sql_session: sqlalchemy.orm.Session, track_id: int) -> Optional[List[Artists]]:
        track_artists_rows = sql_session.query(TrackArtists).filter_by(track_id=track_id).all()
        artist_rows = [sql_session.query(Artists).filter_by(id=track_artists_row.artist_id).one() for track_artists_row in track_artists_rows]

        return artist_rows