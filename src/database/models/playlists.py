import sqlalchemy as sqla

from database.models.base import Base

# table with info about every single playlist in the library
class Playlists(Base):
    __tablename__ = "playlists"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=True, unique=True)
    name = sqla.Column(sqla.String, nullable=False)
    description = sqla.Column(sqla.String, nullable=True)
    playlist_tracks = sqla.orm.relationship("PlaylistTracks", back_populates="playlist", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Playlist(id={self.id}, "
            f"spotify_id='{self.spotify_id}', "
            f"name='{self.name}', "
            f"description='{self.description}')>"
        )