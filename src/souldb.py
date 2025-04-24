# each row in the database should have:
# 	- filepath (str), title (str), artist (str), release date (str), genres (list[str]), explicit (bool), file format (str), file quality (int?), file size (int?), date liked in spotify (str), rating (int 1-5), comments (str)
# 	- should we add more info from VirtualDJ such as key, bpm, etc?

# from what ive read sqlalchemy works for both sqlite .db files and postgresql, so we can use it for working with the local database and the postgresql database on the mines server
# https://docs.sqlalchemy.org/en/20/intro.html
import sqlalchemy as sqla
from sqlalchemy.orm import declarative_base
from dataclasses import dataclass

Base = declarative_base()

def add_song_to_playlist(playlist, songId, session):
    # new_track = playlist(song_id = songId)
    # session.add(new_track)
    # session.commit()
    
    stmt = sqla.insert(playlist).values(
                song_id=songId,
            ).prefix_with("OR IGNORE")  # SQLite only

    session.execute(stmt)
    session.commit()

@dataclass
class TrackData:
    """
    this dataclass contains ALL relevant information about a track in the library

    Attributes:
        filepath (str): the file path of the track
        spotify_id (str): the Spotify ID of the track
        title (str): the title of the track
        artists (list[(str, str)]): a list of each artists name and id for the track
        album (str): the album of the track
        release_date (str): the release date of the track
        date_liked_spotify (str): the date the track was liked on Spotify
        explicit (bool): whether the track is explicit or not
        comments (str): any comments about the track
    """
    filepath: str = None
    spotify_id: str = None
    title: str = None
    artists: list[(str, str)] = None
    album: str = None
    release_date: str = None
    date_liked_spotify: str = None
    explicit: bool = None
    comments: str = None

# table with info about every single track and file in the library
# TODO: add downloaded_with column to indicate whether the track was downloaded with slskd or yt-dlp
class Tracks(Base):
    __tablename__ = "tracks"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=True, unique=True)
    filepath = sqla.Column(sqla.String, nullable=True)
    title = sqla.Column(sqla.String, nullable=False)
    track_artists = sqla.orm.relationship("TrackArtist", back_populates="track", cascade="all, delete-orphan")
    artists = sqla.orm.relationship("Artist", secondary="track_artists", viewonly=True)
    album = sqla.Column(sqla.String, nullable=True)
    release_date = sqla.Column(sqla.String, nullable=True)
    explicit = sqla.Column(sqla.Boolean, nullable=True)
    date_liked_spotify = sqla.Column(sqla.String, nullable=True)
    comments = sqla.Column(sqla.String, nullable=True)
    playlist_tracks = sqla.orm.relationship("PlaylistTracks", back_populates="track", cascade="all, delete-orphan")

    @classmethod
    def add_track(cls, session, track_data: TrackData):
        if track_data.spotify_id is None:
            existing_track = session.query(Tracks).filter_by(filepath=track_data.filepath).first()
        else:
            existing_track = session.query(Tracks).filter_by(spotify_id=track_data.spotify_id).first()

        if existing_track is not None:
            print(f"Track ({track_data.title} - {track_data.artists}) already exists in the database - not adding")
            return existing_track
        
        track = cls(
            spotify_id=track_data.spotify_id,
            filepath=track_data.filepath,
            title=track_data.title,
            album=track_data.album,
            release_date=track_data.release_date,
            explicit=track_data.explicit,
            date_liked_spotify=track_data.date_liked_spotify,
            comments=track_data.comments
        )

        session.add(track)
        session.flush()

        # add artists to the Artist table if they don't already exist, and add them to the TrackArtist association table
        for name, spotify_id in track_data.artists:
            existing_artist = session.query(Artist).filter_by(name=name).first()

            if existing_artist is None:
                new_artist = Artist(name=name, spotify_id=spotify_id)
                session.add(new_artist)
                session.flush()
                track_artist_assoc = TrackArtist(track_id=track.id, artist_id=new_artist.id)
            else:
                track_artist_assoc = TrackArtist(track_id=track.id, artist_id=existing_artist.id)

            track.track_artists.append(track_artist_assoc)

        session.commit()
        return track

# table with info about every single playlist in the library
class Playlists(Base):
    __tablename__ = "playlists"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=False, unique=True)
    name = sqla.Column(sqla.String, nullable=False)
    description = sqla.Column(sqla.String, nullable=True)
    playlist_tracks = sqla.orm.relationship("PlaylistTracks", back_populates="playlist", cascade="all, delete-orphan")

    @classmethod
    def add_playlist(cls, session, spotify_id, name, description, track_rows_and_data):
        # create the new_playlist table, add it and flush it so we can access the generated id
        new_playlist = cls(spotify_id=spotify_id, name=name, description=description)
        session.add(new_playlist)
        session.flush()

        # get track objects for each id and add them with their date_added to the playlist_tracks association table
        # TODO: we need to do this each time a track is added, not all at the end of the playlist - i think this is a larger refactor and dgaf rn B=D
        for track_row, track_data in track_rows_and_data:
            playlist_track_assoc = PlaylistTracks(track_id=track_row.id, playlist_id=new_playlist.id, added_at=track_data.date_liked_spotify)
            new_playlist.playlist_tracks.append(playlist_track_assoc)

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

def createPlaylistTables(playlists, playlist_songs, engine, session):
    # dropAllPlaylists(playlists, engine)
    playlist_tables = []
    tables_dict = {}
    for playlist in playlists:
        attr_dict = {'__tablename__': playlist, 'song_id': sqla.Column(sqla.String, primary_key=True)}
        current_playlist = type(playlist, (Base,), attr_dict)
        playlist_tables.append(current_playlist)
        tables_dict[playlist] = current_playlist
        
    Base.metadata.create_all(bind=engine)
    for playlist in playlists:
        for song in playlist_songs[playlist]:
            add_song_to_playlist(tables_dict[playlist], song, session)
        
    return tables_dict

def dropAllPlaylists(playlists, engine):
    metadata = sqla.MetaData()
    metadata.reflect(bind=engine)
    tables_to_drop = []
    for playlist in playlists:
        table_to_drop = metadata.tables.get(playlist)
        if table_to_drop is not None:
            tables_to_drop.append(table_to_drop)
    Base.metadata.drop_all(engine, tables_to_drop, checkfirst=True)

def get_existing_track(session, track: TrackData):
    if track.spotify_id is not None:
        existing_track = session.query(Tracks).filter_by(spotify_id=track.spotify_id).first()
    else:
        existing_track = session.query(Tracks).filter_by(filepath=track.filepath, date_liked_spotify=track.date_liked_spotify).first()

    return existing_track

# class Tracks(Base):
#     __tablename__ = "tracks"
#     id = sql.Column(sql.Integer, primary_key=True)
#     filepath = sql.Column(sql.String, nullable=False)
#     title = sql.Column(sql.String, nullable=False)
#     artist = sql.Column(sql.String, nullable=False)
#     release_date = sql.Column(sql.String, nullable=True)
#     explicit = sql.Column(sql.Boolean, nullable=True)
#     date_liked_spotify = sql.Column(sql.String, nullable=True)
#     comments = sql.Column(sql.String, nullable=True)

#     @classmethod
#     def add_track(cls, session, filepath, title, artist, release_date, explicit, date_liked_spotify, comments):
#         new_track = cls(filepath=filepath, title=title, artist=artist, release_date=release_date, explicit=explicit, date_liked_spotify=date_liked_spotify, comments=comments)
#         session.add(new_track)
#         session.commit()

# class Playlists(Base):
#     __tablename__ = "playlists"
#     id = sql.Column(sql.Integer, primary_key=True)
#     name = sql.Column(sql.String, nullable=False)
#     date_created = sql.Column(sql.String, nullable=True)
#     comments = sql.Column(sql.String, nullable=True)

#     @classmethod
#     def add_playlist(cls, session, name, date_created, comments):
#         new_playlist = cls(name=name, date_created=date_created, comments=comments)
#         session.add(new_playlist)
#         session.commit()

# # TODO: idk what should go here, or what the 3rd table should even include
# # 	- maybe we should create a table for genres, though we could also just treat genres as playlists
# class UserInfo(Base):
#     __tablename__ = "user_info"
#     id = sql.Column(sql.Integer, primary_key=True)
#     username = sql.Column(sql.String, nullable=False)
#     spotify_client_id = sql.Column(sql.String, nullable=True)
#     spotify_client_secret = sql.Column(sql.String, nullable=True)

#     @classmethod
#     def add_user(cls, session, username, spotify_client_id, spotify_client_secret):
#         new_user = cls(username=username, spotify_client_id=spotify_client_id, spotify_client_secret=spotify_client_secret)
#         session.add(new_user)
#         session.commit()