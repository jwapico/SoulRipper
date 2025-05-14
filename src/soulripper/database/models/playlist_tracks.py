import time
import sqlalchemy as sqla

from .base import Base

# association table that creates a many-to-many relationship between playlists and tracks with extra attributes
class PlaylistTracks(Base):
    __tablename__ = "playlist_tracks"
    id = sqla.Column(sqla.Integer, primary_key=True, autoincrement=True)
    playlist_id = sqla.Column(sqla.Integer, sqla.ForeignKey("playlists.id"), nullable=False)
    track_id = sqla.Column(sqla.Integer, sqla.ForeignKey("tracks.id"), nullable=False)
    added_at = sqla.Column(sqla.DateTime(timezone=True), nullable=False, server_default=sqla.sql.func.now())
    playlist = sqla.orm.relationship("Playlists", back_populates="playlist_tracks")
    track = sqla.orm.relationship("Tracks", back_populates="playlist_tracks")

    def __repr__(self):
        return (
            f"<PlaylistTrack(id={self.id}, "
            f"playlist_id={self.playlist_id}, "
            f"track_id={self.track_id}, "
            f"added_at='{self.added_at}')>"
        )