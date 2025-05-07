import sqlalchemy as sqla

from .base import Base

# table with info about every single artist in the library
class Artists(Base):
    __tablename__ = "artists"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=True, unique=True)
    name = sqla.Column(sqla.String, nullable=True, unique=False)
    track_artists = sqla.orm.relationship("TrackArtists", back_populates="artist", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Artist(id={self.id}, "
            f"name='{self.name}', "
            f"spotify_id='{self.spotify_id}')>"
        )