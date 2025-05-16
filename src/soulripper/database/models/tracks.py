import sqlalchemy as sqla
from sqlalchemy.orm import mapped_column, relationship, Mapped

from .base import Base

# table with info about every single track and file in the library
# TODO: add downloaded_with column to indicate whether the track was downloaded with slskd or yt-dlp
# TODO: i think the date_liked_spotify field is reduntant since we should have a playlist for every track that was liked on spotify with the date added there
class Tracks(Base):
    __tablename__ = "tracks"
    id:               Mapped[int] = mapped_column(sqla.Integer, primary_key=True)
    spotify_id:       Mapped[str] = mapped_column(sqla.String, nullable=True, unique=True)
    filepath:         Mapped[str] = mapped_column(sqla.String, nullable=True)
    title:            Mapped[str] = mapped_column(sqla.String, nullable=True)
    album:            Mapped[str] = mapped_column(sqla.String, nullable=True)
    release_date:     Mapped[str] = mapped_column(sqla.String, nullable=True)
    explicit:         Mapped[bool] = mapped_column(sqla.Boolean, nullable=True)
    comments:         Mapped[str] = mapped_column(sqla.String, nullable=True)
    playlist_tracks  = relationship("PlaylistTracks", back_populates="track", cascade="all, delete-orphan")
    track_artists    = relationship("TrackArtists", back_populates="track", cascade="all, delete-orphan")
    artists          = relationship("Artists", secondary="track_artists", viewonly=True)

    def __repr__(self):
        return (
            f"<Track(id={self.id}, "
            f"spotify_id='{self.spotify_id}', "
            f"filepath='{self.filepath}', "
            f"title='{self.title}', "
            f"album='{self.album}', "
            f"release_date='{self.release_date}', "
            f"explicit={self.explicit}, "
            f"date_liked_spotify='{self.date_liked_spotify}', "
            f"comments='{self.comments}')>"
        )