import sqlalchemy as sqla
from sqlalchemy.orm import relationship, mapped_column, Mapped

from .base import Base

# association table that creates a many-to-many relationship between playlists and tracks with extra attributes
class PlaylistTracks(Base):
    __tablename__ = "playlist_tracks"
    id:             Mapped[int] = mapped_column(sqla.Integer, primary_key=True, autoincrement=True)
    playlist_id:    Mapped[int] = mapped_column(sqla.Integer, sqla.ForeignKey("playlists.id"), nullable=False)
    track_id:       Mapped[int] = mapped_column(sqla.Integer, sqla.ForeignKey("tracks.id"), nullable=False)
    added_at:       Mapped[sqla.DateTime] = mapped_column(sqla.DateTime(timezone=True), nullable=False, server_default=sqla.sql.func.now())
    playlist        = relationship("Playlists", back_populates="playlist_tracks")
    track           = relationship("Tracks", back_populates="playlist_tracks")

    def __repr__(self):
        return (
            f"<PlaylistTrack(id={self.id}, "
            f"playlist_id={self.playlist_id}, "
            f"track_id={self.track_id}, "
            f"added_at='{self.added_at}')>"
        )