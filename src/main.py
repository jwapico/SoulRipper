import time
import os
import json
import argparse
import dotenv
import time
import sqlalchemy as sqla
from sqlalchemy.orm import Session
import mutagen

from spotify_utils import SpotifyUtils
import souldb as SoulDB

# TODO:
#   - better syncing with local music directory
#   - better user interface - gui or otherwise
#       - some sort of config file for api keys, directory paths, etc
#       - make cli better
#   - restructure this file - there are too many random ahh functions
#       - maybe encapsulate into class or just have shared variables?
#   - create a TODO.md file for project management and big plans outside of databases final project (due apr 30 :o)
#       - talk to colton eoghan and other potential users about high level design
#   - the print statements in lower level functions should be changed to logging/debug statements
#   - we need to implement atomicity in the database functions - the Table classmethods such NOT be calling session.commit()
#   - type annotations for ALL functions args and return values
#   - cleanup comments & add more
#   - get a songs metadata using an api such as:
#       - https://www.discogs.com/developers/
#       - big list here: https://soundcharts.com/blog/music-data-api









# TODO: i THINK this is all of the main database code we need to our submission, the only thing missing at the time of writing is the performance tuning stuff
# heavy on the 'i think' tho we should prolly discuss this as a group
#   - currently all we do is populate the database with the users local music directory as well as their stuff from spotify, then display some statistics
#       - tho we do have functionality for a user to add a new track through --add-track (let me know if anyone has any more ideas for submission functionality)

def main():
    # collect commandline arguments
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("pos_music_dir", nargs="?", default=os.getcwd(), help="The location of your music directory")
    parser.add_argument("--music-dir", type=str, dest="music_dir", help="The location of your music directory")
    parser.add_argument("--debug", action="store_true", help="Enable debug statements")
    parser.add_argument("--drop-database", action="store_true", help="Drop the database before running the program")
    parser.add_argument("--add-track", type=str, help="Add a track to the database - provide the filepath")
    args = parser.parse_args()
    DEBUG = args.debug
    DROP_DATABASE = args.drop_database
    OUTPUT_PATH = args.music_dir if args.music_dir else args.pos_music_dir
    NEW_TRACK_FILEPATH = args.add_track

    dotenv.load_dotenv()

    # connect to spotify API
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
    spotify_client = SpotifyUtils(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI)
    SPOTIFY_USER_ID, SPOTIFY_USERNAME = spotify_client.get_user_info()

    # create the engine with the local soul.db file - need to change this for final submission
    # engine = sqla.create_engine("sqlite:///assets/soul.db", echo=DEBUG)
    engine = sqla.create_engine("sqlite:///assets/soul.db", echo=False)

    # if the flag was provided drop everything in the database
    if DROP_DATABASE:
        if not DEBUG:
            input("Warning: This will drop all tables in the database. Press enter to continue...")

        metadata = sqla.MetaData()
        metadata.reflect(bind=engine)
        metadata.drop_all(engine)

    # initialize the tables defined in souldb.py and create a session
    SoulDB.Base.metadata.create_all(engine)
    session = sqla.orm.sessionmaker(bind=engine)
    sql_session: Session = session()

    # add the user to the database if they don't already exist
    matching_user = sql_session.query(SoulDB.UserInfo).filter_by(spotify_id=SPOTIFY_USER_ID).first()
    if matching_user is None:
        SoulDB.UserInfo.add_user(sql_session, SPOTIFY_USERNAME, SPOTIFY_USER_ID, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)

    if NEW_TRACK_FILEPATH:
        add_new_track_to_db(sql_session, NEW_TRACK_FILEPATH)

    # populate the database with metadata found from files in the users output directory
    scan_music_library(sql_session, OUTPUT_PATH)
    sql_session.commit()
    
    start_time = time.perf_counter()
    # get all playlists from spotify and add them to the database
    all_playlists_metadata = spotify_client.get_all_playlists()
    for playlist_metadata in all_playlists_metadata:
        update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata)

    # add the users liked songs to the database
    

    update_db_with_spotify_liked_tracks(spotify_client, sql_session)

    sql_session.flush()
    sql_session.commit()
    
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    print(f"Seconds: {execution_time}")
    
    execute_all_interesting_queries(sql_session)

# ===========================================
#          main database functions
# ===========================================

# TODO: this function technically kinda works but we need a better way to extract metadata from the files - most files (all downloaded by yt-dlp) have None for all fields except filepath :/
#   - maybe we can extract info from filename
#   - we should probably populate metadata using TrackData from database or Spotify API - this is a lot of work dgaf rn lol
def scan_music_library(sql_session, music_dir: str):
    """
    Adds all songs in the music directory to the database

    Args:
        music_dir (str): the directory to add songs from
    """
    print(f"Scanning music library at {music_dir}...")

    for root, dirs, files in os.walk(music_dir):
        for file in files:
            # TODO: these extensions should be configured with the config file (still need to implement config file </3)
            if file.endswith(".mp3") or file.endswith(".flac") or file.endswith(".wav"):
                filepath = os.path.abspath(os.path.join(root, file))
                add_new_track_to_db(sql_session, filepath)

    sql_session.flush()

def add_new_track_to_db(sql_session, filepath: str):
    if not os.path.exists(filepath):
        print(f"File {filepath} does not exist, skipping...")
        return

    file_track_data = extract_file_metadata(filepath)

    if file_track_data is None:
        print(f"No metadata found in file {filepath}, skipping...")
        file_track_data = SoulDB.TrackData(filepath=filepath, comments="WARNING: Error while extracting metadata. This likely means the file is corrupted or empty")

    print(f"Found track with data: {file_track_data}, adding to database...")

    existing_track = SoulDB.get_existing_track(sql_session, file_track_data)
    if existing_track is None:
        SoulDB.Tracks.add_track(sql_session, file_track_data)

def update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata):
    print(f"Updating database with tracks from playlist {playlist_metadata['name']}...")

    playlist_tracks = spotify_client.get_playlist_tracks(playlist_metadata['id'])
    relevant_tracks_data: list[SoulDB.TrackData] = spotify_client.get_data_from_playlist(playlist_tracks)

    # create and flush the playlist since we need its id for the playlist_tracks association table
    playlist_row = sql_session.query(SoulDB.Playlists).filter_by(spotify_id=playlist_metadata['id']).first()
    if playlist_row is None:
        playlist_row = SoulDB.Playlists.add_playlist(sql_session, playlist_metadata['id'], playlist_metadata['name'], playlist_metadata['description'])
        sql_session.add(playlist_row)
        sql_session.flush()

    # add each track in the playlist to the database if it doesn't already exist
    # for track_data in relevant_tracks_data:
    add_track_data_to_playlist(sql_session, relevant_tracks_data, playlist_row)
    sql_session.flush()

def update_db_with_spotify_liked_tracks(spotify_client: SpotifyUtils, sql_session):
    liked_tracks_data = spotify_client.get_liked_tracks()
    relevant_tracks_data: list[SoulDB.TrackData] = spotify_client.get_data_from_playlist(liked_tracks_data)

    liked_playlist = sql_session.query(SoulDB.Playlists).filter_by(name="SPOTIFY_LIKED_SONGS").first()
    if liked_playlist is None:
        liked_playlist = SoulDB.Playlists.add_playlist(sql_session, spotify_id=None, name="SPOTIFY_LIKED_SONGS", description="User liked songs on Spotify - This playlist is generated by SoulRipper")
        sql_session.add(liked_playlist)
        sql_session.flush()

    # add each track in the users liked songs to the database if it doesn't already exist
    # TODO: we can prolly optimize this for fp deliverable
    # for track_data in relevant_tracks_data:
    add_track_data_to_playlist(sql_session, relevant_tracks_data, liked_playlist)

def add_track_data_to_playlist(sql_session, track_data_list: list[SoulDB.TrackData], playlist_row: SoulDB.Playlists):
    existing_spotify_ids = set(
        spotify_id for (spotify_id,) in sql_session.query(SoulDB.Tracks.spotify_id).filter(SoulDB.Tracks.spotify_id.isnot(None))
    )
    existing_non_spotify_tracks = set(
        (title, album, filepath) for (title, album, filepath) in sql_session.query(
            SoulDB.Tracks.title, SoulDB.Tracks.album, SoulDB.Tracks.filepath
        ).filter(SoulDB.Tracks.spotify_id.is_(None))
    )

    new_tracks = set()
    seen_spotify_ids = set()
    seen_non_spotify = set()

    for track_data in track_data_list:
        if track_data.spotify_id:
            if track_data.spotify_id in existing_spotify_ids or track_data.spotify_id in seen_spotify_ids:
                continue
            seen_spotify_ids.add(track_data.spotify_id)
        else:
            key = (track_data.title, track_data.album, track_data.filepath)
            if key in existing_non_spotify_tracks or key in seen_non_spotify:
                continue
            seen_non_spotify.add(key)
        new_tracks.add(track_data)
            
    SoulDB.Tracks.bulk_add_tracks(sql_session,new_tracks)
    
    existing_assoc_keys = set(
        (playlist_id, track_id)
        for playlist_id, track_id in sql_session.query(
            SoulDB.PlaylistTracks.playlist_id,
            SoulDB.PlaylistTracks.track_id
        ).all()
    )
    for track_data in track_data_list:
        track = SoulDB.get_existing_track(sql_session,track_data)
        if track:
            assoc = SoulDB.PlaylistTracks(track_id=track.id, playlist_id=playlist_row.id, added_at=track.date_liked_spotify)
            if (assoc.playlist_id, assoc.track_id) not in existing_assoc_keys:
                existing_assoc_keys.add(assoc)
                playlist_row.playlist_tracks.append(assoc)
        else:
            print("Error")

# ===========================================
#       interesting and complex queries
# ===========================================

def execute_all_interesting_queries(sql_session):
    input("Executing all interesting and complex queries, press enter to begin")

    get_missing_tracks(sql_session)
    input("Press enter to execute next query")
    get_tracks_by_artist(sql_session, "Kendrick Lamar")
    input("Press enter to execute next query")
    get_tracks_by_album(sql_session, "good kid, m.A.A.d city")
    input("Press enter to execute next query")
    get_favorite_artists(sql_session)
    input("Press enter to execute next query")
    get_num_unique_tracks(sql_session)
    input("Press enter to execute next query")
    get_num_unique_artists(sql_session)
    input("Press enter to execute next query")
    get_num_unique_albums(sql_session)
    input("Press enter to execute next query")
    get_favorite_tracks(sql_session)
    input("Press enter to execute next query")
    get_average_tracks_per_playlist(sql_session)
    input("Press enter to execute next query")
    get_playlists_with_above_avg_track_count(sql_session)
    input("Press enter to execute next query")
    get_top_3_tracks_per_artist(sql_session)

# Simple filter query
def get_missing_tracks(sql_session):
    query = """
    SELECT *
    FROM tracks
    WHERE filepath IS NULL;
    """

    result = sql_session.execute(sqla.text(query)).fetchall()
    print(f"Found {len(result)} missing tracks (filepath is null)")
    return result

# Join + filter
def get_tracks_by_artist(sql_session, artist_name):
    query = """
    SELECT t.*
    FROM tracks t
    JOIN track_artists ta ON t.id = ta.track_id
    JOIN artists a ON ta.artist_id = a.id
    WHERE a.name = :artist;
    """

    result = sql_session.execute(sqla.text(query), {"artist": artist_name}).fetchall()
    print(f"Found {len(result)} tracks by artist {artist_name}")
    return result

# Simple filter query
def get_tracks_by_album(sql_session, album_name):
    query = """
    SELECT *
    FROM tracks
    WHERE album = :album;
    """

    result = sql_session.execute(sqla.text(query), {"album": album_name}).fetchall()
    print(f"Found {len(result)} tracks in album {album_name}")
    return result

# Grouping & aggregation
def get_favorite_artists(sql_session):
    stmt = sqla.text("""
    SELECT
        a.name AS artist,
        COUNT(*) AS count
    FROM artists a
    JOIN track_artists ta ON a.id = ta.artist_id
    JOIN tracks t ON ta.track_id = t.id
    GROUP BY a.name
    ORDER BY count DESC
    LIMIT 10;
    """)

    result = sql_session.execute(stmt).fetchall()
    print(f"Top 10 favorite artists: {[result[0] for result in result]}")
    return result

# Aggregation
def get_num_unique_tracks(sql_session):
    query = """
    SELECT COUNT(DISTINCT title) AS count
    FROM tracks;
    """

    result = sql_session.execute(sqla.text(query)).fetchone()
    print(f"Number of unique tracks: {result[0]}")
    return result

# Aggregation
def get_num_unique_artists(sql_session):
    stmt = sqla.text("""
    SELECT
    COUNT(DISTINCT a.id) AS count
    FROM artists a;
    """)

    result = sql_session.execute(stmt).fetchone()
    print(f"Number of unique artists: {result[0]}")
    return result

# Aggregation
def get_num_unique_albums(sql_session):
    query = """
    SELECT COUNT(DISTINCT album) AS count
    FROM tracks;
    """

    result = sql_session.execute(sqla.text(query)).fetchone()
    print(f"Number of unique albums: {result[0]}")
    return result

# Grouping & aggregation
def get_favorite_tracks(sql_session):
    query = """
    SELECT
        t.title,
        COUNT(pt.playlist_id) AS num_playlists
    FROM tracks t
    LEFT JOIN playlist_tracks pt
    ON t.id = pt.track_id
    GROUP BY t.id, t.title
    ORDER BY num_playlists DESC
    LIMIT 10;
    """

    result = sql_session.execute(sqla.text(query)).fetchall()
    print(f"Top 10 favorite tracks: {[result[0] for result in result]}")
    return result

# Subquery
def get_average_tracks_per_playlist(sql_session):
    query = """
    SELECT AVG(sub.track_count) AS avg_tracks_per_playlist
        FROM (
            SELECT COUNT(*) AS track_count
            FROM playlist_tracks
            GROUP BY playlist_id
        ) AS sub;
    """

    result = sql_session.execute(sqla.text(query)).fetchone()
    print(f"Average number of tracks per playlist: {result[0]}")
    return result

# CTE 
def get_playlists_with_above_avg_track_count(sql_session):
    stmt = sqla.text("""
    WITH playlist_counts AS (
        SELECT
            playlist_id,
            COUNT(track_id) AS cnt
        FROM playlist_tracks
        GROUP BY playlist_id
    ), average_count AS (
        SELECT AVG(cnt) AS avg_cnt
        FROM playlist_counts
    )
    SELECT
        p.name AS playlist_name,
        pc.cnt AS track_count
    FROM playlist_counts pc
    JOIN playlists p
    ON p.id = pc.playlist_id
    CROSS JOIN average_count av
    WHERE pc.cnt > av.avg_cnt
    ORDER BY pc.cnt DESC;
    """)

    result = sql_session.execute(stmt).fetchall()
    print(f"Playlists with above-average track count: {[row.playlist_name for row in result]}")
    return result

# Window function
def get_top_3_tracks_per_artist(sql_session):
    start_time = time.perf_counter()
    stmt = sqla.text("""
    SELECT 
        artist_name,
        track_title,
        num_playlists
    FROM (
        SELECT
            a.name AS artist_name,
            t.title AS track_title,
            COUNT(pt.playlist_id) AS num_playlists,
            ROW_NUMBER() OVER (
                PARTITION BY a.id
                ORDER BY COUNT(pt.playlist_id) DESC
            ) AS rn
        FROM artists a
        JOIN track_artists ta ON a.id = ta.artist_id
        JOIN tracks t ON ta.track_id = t.id
        LEFT JOIN playlist_tracks pt ON t.id = pt.track_id
        GROUP BY a.id, t.id
    ) sub
    WHERE rn <= 3
    ORDER BY artist_name, num_playlists DESC;
    """)
    
    rows = sql_session.execute(stmt).fetchall()

# WHERE rn <= 3
    # Print each row as (artist, track, count)
    for artist, track, count in rows:
        if None not in (artist, track, count):
            print(f"{artist or '<Unknown Artist>':40} | {track:75} | in {count} playlists")
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    print("Seconds: ", execution_time)
    
    return rows

# ===========================================
#             helper functions
# ===========================================

def pprint(data):
    print(json.dumps(data, indent=4))

def save_json(data, filename="debug/debug.json"):
    with open(f"debug/{filename}", "w") as file:
        json.dump(data, file)

# TODO: look at metadata to see what else we can extract - it's different for each file :( - need to find file with great metadata as example
def extract_file_metadata(filepath: str) -> SoulDB.TrackData:
    """
    Extracts metadata from a file using mutagen

    Args:
        filepath (str): the path to the file

    Returns:
        dict: a dictionary of metadata
    """

    try:
        file_metadata = mutagen.File(filepath)
    except Exception as e:
        print(f"Error reading metadata of file {filepath}: {e}")
        return None

    if file_metadata:
        title = file_metadata.get("title", [None])[0]
        artists = file_metadata.get("artist", [None])[0]
        album = file_metadata.get("album", [None])[0]
        release_date = file_metadata.get("date", [None])[0]

        track_data = SoulDB.TrackData(
            filepath=filepath,
            title=title,
            artists=[(artist, None) for artist in artists.split(",")] if artists else [(None, None)],
            album=album,
            release_date=release_date,
        )

        return track_data

if __name__ == "__main__":
    main()