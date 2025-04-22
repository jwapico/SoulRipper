# each row in the database should have:
# 	- filepath (str), title (str), artist (str), release date (str), genres (list[str]), explicit (bool), file format (str), file quality (int?), file size (int?), date liked in spotify (str), rating (int 1-5), comments (str)
# 	- should we add more info from VirtualDJ such as key, bpm, etc?

# from what ive read sqlalchemy works for both sqlite .db files and postgresql, so we can use it for working with the local database and the postgresql database on the mines server
# https://docs.sqlalchemy.org/en/20/intro.html
import sqlalchemy as sqla
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# table with info about every single track and file in the library 
class Tracks(Base):
    __tablename__ = "tracks"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=True, unique=True)
    filepath = sqla.Column(sqla.String, nullable=False)
    title = sqla.Column(sqla.String, nullable=False)
    track_artists = sqla.orm.relationship("TrackArtist", back_populates="track", cascade="all, delete-orphan")
    artists = sqla.orm.relationship("Artist", secondary="track_artists", viewonly=True)
    album = sqla.Column(sqla.String, nullable=True)
    release_date = sqla.Column(sqla.String, nullable=True)
    explicit = sqla.Column(sqla.Boolean, nullable=True)
    date_liked = sqla.Column(sqla.String, nullable=True)
    comments = sqla.Column(sqla.String, nullable=True)
    playlist_tracks = sqla.orm.relationship("PlaylistTracks", back_populates="track", cascade="all, delete-orphan")

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

        session.add(track)
        session.flush()

        # add artists to the Artist table if they don't already exist, and add them to the TrackArtist association table
        for name, spotify_id in artists:
            artist = session.query(Artist).filter_by(name=name).first()

            if artist is None:
                artist = Artist(name=name, spotify_id=spotify_id)
                session.add(artist)
                session.flush()

            track_artist_assoc = TrackArtist(track_id=track.id, artist_id=artist.id)
            session.add(track_artist_assoc)

        session.commit()

# table with info about every single playlist in the library
class Playlists(Base):
    __tablename__ = "playlists"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=False, unique=True)
    name = sqla.Column(sqla.String, nullable=False)
    description = sqla.Column(sqla.String, nullable=True)
    playlist_tracks = sqla.orm.relationship("PlaylistTracks", back_populates="playlist", cascade="all, delete-orphan")

    @classmethod
    def add_playlist(cls, session, spotify_id, name, description, track_info):
        new_playlist = cls(spotify_id=spotify_id, name=name, description=description)

        # get track objects for each id and add them with their date_added to the playlist_tracks association table
        tracks = session.query(Tracks).filter(Tracks.spotify_id.in_([track[0] for track in track_info])).all()
        track_map = {track.spotify_id: track for track in tracks}
        for spotify_id, date_added in track_info:
            track = track_map.get(spotify_id)
            if track:
                assoc = PlaylistTracks(track=track, added_at=date_added)
                new_playlist.playlist_tracks.append(assoc)

        session.add(new_playlist)
        session.commit()

# association table that creates a many-to-many relationship between playlists and tracks with extra attributes
class PlaylistTracks(Base):
    __tablename__ = "playlist_tracks"
    id = sqla.Column(sqla.Integer, primary_key=True, autoincrement=True)
    playlist_id = sqla.Column(sqla.Integer, sqla.ForeignKey("playlists.id"), nullable=False)
    track_id = sqla.Column(sqla.Integer, sqla.ForeignKey("tracks.id"), nullable=False)
    added_at = sqla.Column(sqla.String, nullable=False)
    playlist = sqla.orm.relationship("Playlists", back_populates="playlist_tracks")
    track = sqla.orm.relationship("Tracks", back_populates="playlist_tracks")

# table with info about every single artist in the library
class Artist(Base):
    __tablename__ = "artists"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=True, unique=True)
    name = sqla.Column(sqla.String, nullable=False, unique=True)
    track_artists = sqla.orm.relationship("TrackArtist", back_populates="artist", cascade="all, delete-orphan")

# association table that creates a simple many-to-many relationship between tracks and artists
class TrackArtist(Base):
    __tablename__ = "track_artists"
    id = sqla.Column(sqla.Integer, primary_key=True, autoincrement=True)
    track_id = sqla.Column(sqla.Integer, sqla.ForeignKey("tracks.id"), nullable=False)
    artist_id = sqla.Column(sqla.Integer, sqla.ForeignKey("artists.id"), nullable=False)
    track = sqla.orm.relationship("Tracks", back_populates="track_artists")
    artist = sqla.orm.relationship("Artist", back_populates="track_artists")

# table with info the user
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