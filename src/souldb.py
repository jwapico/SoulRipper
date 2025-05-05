# each row in the database should have:
# 	- filepath (str), title (str), artist (str), release date (str), genres (list[str]), explicit (bool), file format (str), file quality (int?), file size (int?), date liked in spotify (str), rating (int 1-5), comments (str)
# 	- should we add more info from VirtualDJ such as key, bpm, etc?

# from what ive read sqlalchemy works for both sqlite .db files and postgresql, so we can use it for working with the local database and the postgresql database on the mines server
# https://docs.sqlalchemy.org/en/20/intro.html
import sqlalchemy as sqla
from sqlalchemy.orm import declarative_base
from dataclasses import dataclass

Base = declarative_base()

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

    def __repr__(self):
        return (
            f"TrackData(title='{self.title}', album='{self.album}', "
            f"artists={[name for name, _ in self.artists] if self.artists else None}, "
            f"release_date='{self.release_date}', explicit={self.explicit})"
        )

    def __hash__(self):
        if self.spotify_id is not None:
            return hash(self.spotify_id)
        else:
            return hash((self.title, self.album, self.filepath))

    def __eq__(self, other):
        if not isinstance(other, TrackData):
            return False
        if self.spotify_id is not None and other.spotify_id is not None:
            return self.spotify_id == other.spotify_id
        else:
            return (self.title, self.album, self.filepath) == (other.title, other.album, other.filepath)

# table with info about every single track and file in the library
# TODO: add downloaded_with column to indicate whether the track was downloaded with slskd or yt-dlp
# TODO: i think the date_liked_spotify field is reduntant since we should have a playlist for every track that was liked on spotify with the date added there
class Tracks(Base):
    __tablename__ = "tracks"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=True, unique=True)
    filepath = sqla.Column(sqla.String, nullable=True)
    title = sqla.Column(sqla.String, nullable=True)
    track_artists = sqla.orm.relationship("TrackArtist", back_populates="track", cascade="all, delete-orphan")
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

    @classmethod
    def add_track(cls, session, track_data: TrackData):
        existing_track = get_existing_track(session, track_data)
        
        if existing_track:
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
        if track_data.artists is not None:
            for name, spotify_id in track_data.artists:
                existing_artist = session.query(Artists).filter_by(name=name).first()

                if existing_artist is None:
                    new_artist = Artists(name=name, spotify_id=spotify_id)
                    session.add(new_artist)
                    session.flush()
                    track_artist_assoc = TrackArtist(track_id=track.id, artist_id=new_artist.id)
                else:
                    track_artist_assoc = TrackArtist(track_id=track.id, artist_id=existing_artist.id)

                track.track_artists.append(track_artist_assoc)

        session.flush()
        return track
    
    @classmethod
    def bulk_add_tracks(cls, session, track_data_list: set[TrackData]):
        # Preload existing artists
        existing_artists = {
            artist.name: artist
            for artist in session.query(Artists).all()
        }

        new_tracks = []
        new_track_artist_associations = []

        for track_data in track_data_list:
            # Create new Track object
            track = Tracks(
                spotify_id=track_data.spotify_id,
                filepath=track_data.filepath,
                title=track_data.title,
                album=track_data.album,
                release_date=track_data.release_date,
                explicit=track_data.explicit,
                date_liked_spotify=track_data.date_liked_spotify,
                comments=track_data.comments
            )
            new_tracks.append(track)

            # Link artists
            if track_data.artists:
                for name, artist_spotify_id in track_data.artists:
                    artist = existing_artists.get(name)
                    if artist is None:
                        artist = Artists(name=name, spotify_id=artist_spotify_id)
                        session.add(artist)
                        # session.flush()  # Get the new artist.id
                        existing_artists[name] = artist  # Add to cache

                    assoc = TrackArtist(track=track, artist=artist)
                    new_track_artist_associations.append(assoc)

        # Now add everything in one shot
        session.add_all(new_tracks)
        session.add_all(new_track_artist_associations)
        session.flush()

        print(f"Inserted {len(new_tracks)} new tracks.")


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

    @classmethod
    def add_playlist(cls, session, spotify_id, name, description):
        # create the new_playlist table, add it and flush it so we can access the generated id
        new_playlist = cls(spotify_id=spotify_id, name=name, description=description)
        session.add(new_playlist)
        session.flush()

        return new_playlist

# association table that creates a many-to-many relationship between playlists and tracks with extra attributes
class PlaylistTracks(Base):
    __tablename__ = "playlist_tracks"
    id = sqla.Column(sqla.Integer, primary_key=True, autoincrement=True)
    playlist_id = sqla.Column(sqla.Integer, sqla.ForeignKey("playlists.id"), nullable=False)
    track_id = sqla.Column(sqla.Integer, sqla.ForeignKey("tracks.id"), nullable=False)
    added_at = sqla.Column(sqla.String, nullable=False)
    playlist = sqla.orm.relationship("Playlists", back_populates="playlist_tracks")
    track = sqla.orm.relationship("Tracks", back_populates="playlist_tracks")

    def __repr__(self):
        return (
            f"<PlaylistTrack(id={self.id}, "
            f"playlist_id={self.playlist_id}, "
            f"track_id={self.track_id}, "
            f"added_at='{self.added_at}')>"
        )

# table with info about every single artist in the library
class Artists(Base):
    __tablename__ = "artists"
    id = sqla.Column(sqla.Integer, primary_key=True)
    spotify_id = sqla.Column(sqla.String, nullable=True, unique=True)
    name = sqla.Column(sqla.String, nullable=True, unique=False)
    track_artists = sqla.orm.relationship("TrackArtist", back_populates="artist", cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"<Artist(id={self.id}, "
            f"name='{self.name}', "
            f"spotify_id='{self.spotify_id}')>"
        )

# association table that creates a simple many-to-many relationship between tracks and artists
class TrackArtist(Base):
    __tablename__ = "track_artists"
    id = sqla.Column(sqla.Integer, primary_key=True, autoincrement=True)
    track_id = sqla.Column(sqla.Integer, sqla.ForeignKey("tracks.id"), nullable=False)
    artist_id = sqla.Column(sqla.Integer, sqla.ForeignKey("artists.id"), nullable=False)
    track = sqla.orm.relationship("Tracks", back_populates="track_artists")
    artist = sqla.orm.relationship("Artists", back_populates="track_artists")

    def __repr__(self):
        return (
            f"<TrackArtist(id={self.id}, "
            f"track_id={self.track_id}, "
            f"artist_id={self.artist_id})>"
        )

# table with info the user
class UserInfo(Base):
    __tablename__ = "user_info"
    id = sqla.Column(sqla.Integer, primary_key=True)
    username = sqla.Column(sqla.String, nullable=False, unique=True)
    spotify_id = sqla.Column(sqla.String, nullable=False, unique=True)
    spotify_client_id = sqla.Column(sqla.String, nullable=False, unique=True)
    spotify_client_secret = sqla.Column(sqla.String, nullable=False, unique=True)

    def __repr__(self):
        return (
            f"<UserInfo(id={self.id}, "
            f"username='{self.username}', "
            f"spotify_id='{self.spotify_id}', "
            f"spotify_client_id='{self.spotify_client_id}', "
            f"spotify_client_secret='{self.spotify_client_secret}')>"
        )

    @classmethod
    def add_user(cls, session, username, spotify_id, spotify_client_id, spotify_client_secret):
        new_user = cls(username=username, spotify_id=spotify_id, spotify_client_id=spotify_client_id, spotify_client_secret=spotify_client_secret)
        session.add(new_user)
        session.flush()

# TODO: We need a better way of checking for existing tracks when spotify_id and filepath is None
def get_existing_track(session, track: TrackData):
    if track.spotify_id is not None:
        existing_track = session.query(Tracks).filter_by(spotify_id=track.spotify_id).first()
    elif track.filepath is not None:
        existing_track = session.query(Tracks).filter_by(filepath=track.filepath).first()
    else:
        existing_track = session.query(Tracks).filter_by(title=track.title, album=track.album).first()

    return existing_track
