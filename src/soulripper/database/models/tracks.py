import sqlalchemy as sqla

from database.models.base import Base

# table with info about every single track and file in the library
# TODO: add downloaded_with column to indicate whether the track was downloaded with slskd or yt-dlp
# TODO: i think the date_liked_spotify field is reduntant since we should have a playlist for every track that was liked on spotify with the date added there
class Tracks(Base):
    __tablename__ = "tracks"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=True, unique=True)
    filepath = sqla.Column(sqla.String, nullable=True)
    title = sqla.Column(sqla.String, nullable=True)
    track_artists = sqla.orm.relationship("TrackArtists", back_populates="track", cascade="all, delete-orphan")
    artists = sqla.orm.relationship("Artists", secondary="track_artists", viewonly=True)
    album = sqla.Column(sqla.String, nullable=True)
    release_date = sqla.Column(sqla.String, nullable=True)
    explicit = sqla.Column(sqla.Boolean, nullable=True)
    date_liked_spotify = sqla.Column(sqla.String, nullable=True)
    comments = sqla.Column(sqla.String, nullable=True)
    playlist_tracks = sqla.orm.relationship("PlaylistTracks", back_populates="track", cascade="all, delete-orphan")

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