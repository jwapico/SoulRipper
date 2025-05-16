import sqlalchemy as sqla
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

# table with info about every single playlist in the library
class Playlists(Base):
    __tablename__ = "playlists"
    id:                 Mapped[int] = mapped_column(sqla.Integer, primary_key=True)
    spotify_id:         Mapped[str] = mapped_column(sqla.String, nullable=True, unique=True)
    name:               Mapped[str] = mapped_column(sqla.String, nullable=False)
    description:        Mapped[str] = mapped_column(sqla.String, nullable=True)
    playlist_tracks     = relationship("PlaylistTracks", back_populates="playlist", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Playlist(id={self.id}, "
            f"spotify_id='{self.spotify_id}', "
            f"name='{self.name}', "
            f"description='{self.description}')>"
        )