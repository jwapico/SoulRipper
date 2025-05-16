import sqlalchemy as sqla
from sqlalchemy.orm import relationship, Mapped, mapped_column

from .base import Base

# table with info about every single artist in the library
class Artists(Base):
    __tablename__ = "artists"
    id:             Mapped[int] = mapped_column(sqla.Integer, primary_key=True)
    spotify_id:     Mapped[str] = mapped_column(sqla.String, nullable=True, unique=True)
    name:           Mapped[str] = mapped_column(sqla.String, nullable=True, unique=False)
    track_artists   = relationship("TrackArtists", back_populates="artist", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Artist(id={self.id}, "
            f"name='{self.name}', "
            f"spotify_id='{self.spotify_id}')>"
        )