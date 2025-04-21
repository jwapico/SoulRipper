# each row in the database should have:
# 	- filepath (str), title (str), artist (str), release date (str), genres (list[str]), explicit (bool), file format (str), file quality (int?), file size (int?), date liked in spotify (str), rating (int 1-5), comments (str)
# 	- should we add more info from VirtualDJ such as key, bpm, etc?

# from what ive read sqlalchemy works for both sqlite .db files and postgresql, so we can use it for working with the local database and the postgresql database on the mines server
# https://docs.sqlalchemy.org/en/20/intro.html
import sqlalchemy as sql
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def createPlaylistTables(playlists, engine):
    dropAllPlaylists(playlists, engine)
    playlistTables = []
    for playlist in playlists:
        attr_dict = {'__tablename__': playlist, 'id': sql.Column(sql.Integer, primary_key=True),'songId': sql.Column(sql.Integer)}
        playlistTables.append(type(playlist, (Base,), attr_dict))
    Base.metadata.create_all(bind=engine)

def dropAllPlaylists(playlists, engine):
    metadata = sql.MetaData()
    metadata.reflect(bind=engine)
    tables_to_drop = []
    for playlist in playlists:
        table_to_drop = metadata.tables.get(playlist)
        if table_to_drop is not None:
            tables_to_drop.append(table_to_drop)
    Base.metadata.drop_all(engine, tables_to_drop, checkfirst=True)

class Tracks(Base):
    __tablename__ = "tracks"
    id = sql.Column(sql.Integer, primary_key=True)
    filepath = sql.Column(sql.String, nullable=False)
    title = sql.Column(sql.String, nullable=False)
    artist = sql.Column(sql.String, nullable=False)
    release_date = sql.Column(sql.String, nullable=True)
    explicit = sql.Column(sql.Boolean, nullable=True)
    date_liked = sql.Column(sql.String, nullable=True)
    comments = sql.Column(sql.String, nullable=True)

    @classmethod
    def add_track(cls, session, filepath, title, artist, release_date, explicit, date_liked, comments):
        new_track = cls(filepath=filepath, title=title, artist=artist, release_date=release_date, explicit=explicit, date_liked=date_liked, comments=comments)
        session.add(new_track)
        session.commit()

class Playlists(Base):
    __tablename__ = "playlists"
    id = sql.Column(sql.Integer, primary_key=True)
    name = sql.Column(sql.String, nullable=False)
    date_created = sql.Column(sql.String, nullable=True)
    comments = sql.Column(sql.String, nullable=True)

    @classmethod
    def add_playlist(cls, session, name, date_created, comments):
        new_playlist = cls(name=name, date_created=date_created, comments=comments)
        session.add(new_playlist)
        session.commit()

# TODO: idk what should go here, or what the 3rd table should even include
# 	- maybe we should create a table for genres, though we could also just treat genres as playlists
class UserInfo(Base):
    __tablename__ = "user_info"
    id = sql.Column(sql.Integer, primary_key=True)
    username = sql.Column(sql.String, nullable=False)
    spotify_client_id = sql.Column(sql.String, nullable=True)
    spotify_client_secret = sql.Column(sql.String, nullable=True)

    @classmethod
    def add_user(cls, session, username, spotify_client_id, spotify_client_secret):
        new_user = cls(username=username, spotify_client_id=spotify_client_id, spotify_client_secret=spotify_client_secret)
        session.add(new_user)
        session.commit()