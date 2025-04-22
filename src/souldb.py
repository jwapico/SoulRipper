# each row in the database should have:
# 	- filepath (str), title (str), artist (str), release date (str), genres (list[str]), explicit (bool), file format (str), file quality (int?), file size (int?), date liked in spotify (str), rating (int 1-5), comments (str)
# 	- should we add more info from VirtualDJ such as key, bpm, etc?

# from what ive read sqlalchemy works for both sqlite .db files and postgresql, so we can use it for working with the local database and the postgresql database on the mines server
# https://docs.sqlalchemy.org/en/20/intro.html
import sqlalchemy as sqla
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# this table relates playlists to tracks - i think we need to append to it in either Playlists or Tracks like we are for track_artists in add_track
playlist_tracks = sqla.Table(
    "playlist_tracks",
    Base.metadata,
    sqla.Column("playlist_id", sqla.Integer, sqla.ForeignKey("playlists.id"), primary_key=True),
    sqla.Column("track_id", sqla.Integer, sqla.ForeignKey("tracks.id"), primary_key=True),
)

# this table relates tracks to artists
track_artists = sqla.Table(
    "track_artists",
    Base.metadata,
    sqla.Column("track_id", sqla.Integer, sqla.ForeignKey("tracks.id"), primary_key=True),
    sqla.Column("artist_id", sqla.Integer, sqla.ForeignKey("artists.id"), primary_key=True),
)

class Tracks(Base):
    __tablename__ = "tracks"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=True, unique=True)
    filepath = sqla.Column(sqla.String, nullable=False)
    title = sqla.Column(sqla.String, nullable=False)
    artist = sqla.orm.relationship("Artist", secondary=track_artists, backref="tracks")
    album = sqla.Column(sqla.String, nullable=True)
    release_date = sqla.Column(sqla.String, nullable=True)
    explicit = sqla.Column(sqla.Boolean, nullable=True)
    date_liked = sqla.Column(sqla.String, nullable=True)
    comments = sqla.Column(sqla.String, nullable=True)
    playlists = sqla.orm.relationship(
        "Playlists",
        secondary=playlist_tracks,
        back_populates="tracks",
        lazy="joined",
    )

    @classmethod
    def add_track(cls, session, spotify_id, filepath, title, artists, album, release_date, explicit, date_liked, comments):
        track = cls(
            spotify_id=spotify_id,
            filepath=filepath,
            title=title,
            album=album,
            release_date=release_date,
            explicit=explicit,
            date_liked=date_liked,
            comments=comments
        )

        # add artists to the Artist table if they don't already exist, and associate them to the track
        for name, spotify_id in artists:
            existing_artist = session.query(Artist).filter_by(name=name).first()

            if existing_artist is None:
                new_artist = Artist(name=name, spotify_id=spotify_id)
                session.add(new_artist)
                track.artist.append(new_artist)

        session.add(track)
        session.commit()

class Artist(Base):
    __tablename__ = "artists"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=True, unique=True)
    name = sqla.Column(sqla.String, nullable=False, unique=True)

class Playlists(Base):
    __tablename__ = "playlists"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=False, unique=True)
    name = sqla.Column(sqla.String, nullable=False)
    description = sqla.Column(sqla.String, nullable=True)
    tracks = sqla.orm.relationship(
        "Tracks",
        secondary=playlist_tracks,
        back_populates="playlists",
        lazy="joined",
    )

    @classmethod
    def add_playlist(cls, session, spotify_id, name, description):
        new_playlist = cls(spotify_id=spotify_id, name=name, description=description)
        session.add(new_playlist)
        session.commit()

# TODO: idk what should go here, or what the 3rd table should even include
# 	- maybe we should create a table for genres, though we could also just treat genres as playlists
class UserInfo(Base):
    __tablename__ = "user_info"
    id = sqla.Column(sqla.Integer, primary_key=True)
    username = sqla.Column(sqla.String, nullable=False, unique=True)
    spotify_id = sqla.Column(sqla.String, nullable=False, unique=True)
    spotify_client_id = sqla.Column(sqla.String, nullable=False, unique=True)
    spotify_client_secret = sqla.Column(sqla.String, nullable=False, unique=True)

    @classmethod
    def add_user(cls, session, username, spotify_id, spotify_client_id, spotify_client_secret):
        new_user = cls(username=username, spotify_id=spotify_id, spotify_client_id=spotify_client_id, spotify_client_secret=spotify_client_secret)
        session.add(new_user)
        session.commit()

def createPlaylistTables(playlists, engine):
    # dropAllPlaylists(playlists, engine)
    playlistTables = []
    for playlist in playlists:
        attr_dict = {'__tablename__': playlist, 'song_id': sqla.Column(sqla.Integer, primary_key=True)}
        playlistTables.append(type(playlist, (Base,), attr_dict))
    Base.metadata.create_all(bind=engine)

def dropAllPlaylists(playlists, engine):
    metadata = sqla.MetaData()
    metadata.reflect(bind=engine)
    tables_to_drop = []
    for playlist in playlists:
        table_to_drop = metadata.tables.get(playlist)
        if table_to_drop is not None:
            tables_to_drop.append(table_to_drop)
    Base.metadata.drop_all(engine, tables_to_drop, checkfirst=True)