import sqlalchemy as sqla

from .base import Base

# association table that creates a simple many-to-many relationship between tracks and artists
class TrackArtists(Base):
    __tablename__ = "track_artists"
    id = sqla.Column(sqla.Integer, primary_key=True, autoincrement=True)
    track_id = sqla.Column(sqla.Integer, sqla.ForeignKey("tracks.id"), nullable=False)
    artist_id = sqla.Column(sqla.Integer, sqla.ForeignKey("artists.id"), nullable=False)
    track = sqla.orm.relationship("Tracks", back_populates="track_artists")
    artist = sqla.orm.relationship("Artists", back_populates="track_artists")

    def __repr__(self):
        return (
            f"<TrackArtists(id={self.id}, "
            f"track_id={self.track_id}, "
            f"artist_id={self.artist_id})>"
        )