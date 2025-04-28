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
    parser.add_argument("--use-ada", action="store_true", help="Connect the cloud ada database")
    args = parser.parse_args()
    DEBUG = args.debug
    DROP_DATABASE = args.drop_database
    OUTPUT_PATH = args.music_dir if args.music_dir else args.pos_music_dir
    NEW_TRACK_FILEPATH = args.add_track
    USE_ADA = args.use_ada

    dotenv.load_dotenv()

    # connect to spotify API
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
    ADA_USERNAME = os.getenv("ada_username")
    ADA_PASSWORD = os.getenv("ada_pwd")
    spotify_client = SpotifyUtils(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI)
    SPOTIFY_USER_ID, SPOTIFY_USERNAME = spotify_client.get_user_info()

    if USE_ADA:
        mines_database_url = f"postgresql://{ADA_USERNAME}:{ADA_PASSWORD}@ada.mines.edu/csci403"
        engine = sqla.create_engine(mines_database_url, echo=False)
        # Set schema for Ada database
        SoulDB.Base.metadata.schema = 'group38'
    else:
        # create the engine with the local soul.db file - need to change this for final submission
        engine = sqla.create_engine("sqlite:///assets/soul.db", echo=DEBUG)

    # initialize the tables defined in souldb.py and create a session
    session = sqla.orm.sessionmaker(bind=engine)
    sql_session: Session = session()

    if USE_ADA:
        sql_session.execute(sqla.text("SET search_path TO group38"))

    # if the flag was provided drop everything in the database
    if DROP_DATABASE:
        if not DEBUG:
            input("Warning: This will drop all tables in the database. Press enter to continue...")

        if USE_ADA:
            # Drop and recreate schema atomically
            sql_session.execute(sqla.text("DROP SCHEMA IF EXISTS group38 CASCADE"))
            sql_session.execute(sqla.text("CREATE SCHEMA group38"))
            sql_session.commit()  # Commit schema changes first!
        else:
            metadata = sqla.MetaData()
            metadata.reflect(bind=engine)
            metadata.drop_all(engine)

    sql_session.commit()
    # Create tables only AFTER schema changes are committed
    SoulDB.Base.metadata.create_all(engine)
    sql_session.commit()

    # add the user to the database if they don't already exist
    matching_user = sql_session.query(SoulDB.UserInfo).filter_by(spotify_id=SPOTIFY_USER_ID).first()
    if matching_user is None:
        SoulDB.UserInfo.add_user(sql_session, SPOTIFY_USERNAME, SPOTIFY_USER_ID, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)

    scan_music_library(sql_session, OUTPUT_PATH)

    # this code is trash dw its okay :)
    prompt = """\n\nWelcome to SoulRipper, please select one of the following options:

    1: Update the database with all of your data from Spotify (playlists and liked songs)
    2: Update the database with just your playlists from Spotify
    3: Update the database with your liked songs from Spotify
    4: Add a new track to the database
    5: Modify a track in the database
    6: Remove a track from the database
    7: Search for a track in the database
    8: Display some statistics about your library
    9: Drop the database
    q: Close the program

Enter your choice here: """

    while True:
        choice = input(prompt)

        match choice:
            case "1":
                sql_session.commit()
                
                all_playlists_metadata = spotify_client.get_all_playlists()
                for playlist_metadata in all_playlists_metadata:
                    update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata)
                update_db_with_spotify_liked_tracks(spotify_client, sql_session)
                sql_session.flush()
                sql_session.commit()
                continue

            case "2":
                all_playlists_metadata = spotify_client.get_all_playlists()
                for playlist_metadata in all_playlists_metadata:
                    update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata)
                sql_session.flush()
                sql_session.commit()
                continue

            case "3":
                update_db_with_spotify_liked_tracks(spotify_client, sql_session)
                sql_session.flush()
                sql_session.commit()
                continue

            case "4":
                filepath = input("Please enter the filepath of your new track: ")
                filepath = filepath.strip().strip("'\"")
                add_new_track_to_db(sql_session, filepath)
                continue
            
            case "5":
                try:
                    track_id = int(input("Enter the ID of the track you'd like to modify: "))
                    track_row = sql_session.query(SoulDB.Tracks).filter_by(id=track_id).one()
                    print(f"\nCurrent track data:")
                    print(f"Title: {track_row.title}")
                    print(f"Filepath: {track_row.filepath}")
                    print(f"Album: {track_row.album}")
                    print(f"Release Date: {track_row.release_date}")
                    print(f"Explicit: {track_row.explicit}")
                    print(f"Date Liked: {track_row.date_liked_spotify}")
                    print(f"Comments: {track_row.comments}\n")

                    modify_field = input("Enter the name of the field you'd like to modify (e.g., 'title', 'filepath', 'album', 'release_date', 'explicit', 'comments'): ").strip()
                    if not hasattr(track_row, modify_field):
                        print(f"Field '{modify_field}' does not exist on Tracks.")
                        continue

                    new_value = input(f"Enter the new value for {modify_field}: ").strip()

                    # Handle booleans properly
                    if modify_field.lower() == "explicit":
                        new_value = new_value.lower() in ("true", "yes", "1")

                    setattr(track_row, modify_field, new_value)

                    sql_session.flush()
                    sql_session.commit()
                    print(f"Track (ID {track_id}) updated successfully!\n")

                except Exception as e:
                    print(f"An error occurred: {e}\n")

                continue
                        
            case "6":
                track_id = input("Enter the id of the track you'd like to remove: ")
                remove_track(sql_session, track_id)
                continue
            
            case "7":
                title = input("Enter the title of the track you'd like to search for: ")
                results = search_for_track(sql_session, title)

                if results == []:
                    print("No matching tracks found...")
                    continue

                for track in results:
                    print(f"ID: {track.id}")
                    print(f"Title: {track.title}")
                    print(f"Filepath: {track.filepath}")
                    print(f"Album: {track.album}")
                    print(f"Release Date: {track.release_date}")
                    print(f"Explicit: {track.explicit}")
                    print(f"Date Liked: {track.date_liked_spotify}")
                    print(f"Comments: {track.comments}")
                    print("-" * 40)

                continue
            
            case "8":
                execute_all_interesting_queries(sql_session)
                continue
            
            case "9":
                confirmation = input("Are you sure you want to drop all tables in the database? Type 'yes' to confirm: ")
                if confirmation == "yes":
                    sql_session.close()
                    metadata = sqla.MetaData()
                    metadata.reflect(bind=engine)
                    metadata.drop_all(engine)
                    print("Database dropped successfully. Closing the program.")
                    return
                else:
                    print("Not dropping the database...")
                continue

            case "q":
                return
            
            case _:
                print("Invalid input, try again")
                continue

    # if NEW_TRACK_FILEPATH:
    #     add_new_track_to_db(sql_session, NEW_TRACK_FILEPATH)

    # # populate the database with metadata found from files in the users output directory
    # scan_music_library(sql_session, OUTPUT_PATH)
    # sql_session.commit()
    
    # start_time = time.perf_counter()
    # # get all playlists from spotify and add them to the database
    # all_playlists_metadata = spotify_client.get_all_playlists()
    # for playlist_metadata in all_playlists_metadata:
    #     update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata)

    # # add the users liked songs to the database
    

    # update_db_with_spotify_liked_tracks(spotify_client, sql_session)
    # sql_session.flush()
    # sql_session.commit()
    
    # end_time = time.perf_counter()
    # execution_time = end_time - start_time
    # print(f"Seconds: {execution_time}")
    
    # execute_all_interesting_queries(sql_session)

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
    for track_data in relevant_tracks_data:
        add_track_data_to_playlist(sql_session, track_data, playlist_row)
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
    for track_data in relevant_tracks_data:
        add_track_data_to_playlist(sql_session, track_data, liked_playlist)

def add_track_data_to_playlist(sql_session, track_data: SoulDB.TrackData, playlist_row: SoulDB.Playlists):
    # prolly a faster way than doing this
    existing_track_row = SoulDB.get_existing_track(sql_session, track_data)
    if existing_track_row:
        playlist_track_assoc = SoulDB.PlaylistTracks(track_id=existing_track_row.id, playlist_id=playlist_row.id, added_at=track_data.date_liked_spotify)
    else:
        print(f"Adding track {track_data.title} to playlist {playlist_row.name}...")
        # our add_track function is prolly also dookie
        new_track_row = SoulDB.Tracks.add_track(sql_session, track_data)
        playlist_track_assoc = SoulDB.PlaylistTracks(track_id=new_track_row.id, playlist_id=playlist_row.id, added_at=track_data.date_liked_spotify)

    existing_assoc = sql_session.query(SoulDB.PlaylistTracks).filter_by(
        playlist_id=playlist_row.id,
        track_id=(new_track_row.id if existing_track_row is None else existing_track_row.id),
        added_at=track_data.date_liked_spotify
    ).first()

    if existing_assoc is None:
        playlist_row.playlist_tracks.append(playlist_track_assoc)

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

    # Print each row as (artist, track, count)
    for artist, track, count in rows:
        print(f"{artist or '<Unknown Artist>':40} | {track:75} | in {count} playlists")

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
    
# ===========================================
#             user interaction
# ===========================================

def search_for_track(sql_session, track_title):
    results = sql_session.query(SoulDB.Tracks).filter(
        SoulDB.Tracks.title.ilike(f"%{track_title}%")
    ).all()

    return results


def modify_track(sql_session, track_id, new_track_data: SoulDB.TrackData):
    existing_track = sql_session.query(SoulDB.Tracks).filter_by(id=track_id).one()
    
    existing_track.spotify_id = new_track_data.spotify_id if new_track_data.spotify_id is not None else existing_track.spotify_id
    existing_track.filepath = new_track_data.filepath if new_track_data.filepath is not None else existing_track.filepath
    existing_track.title = new_track_data.title if new_track_data.title is not None else existing_track.title
    existing_track.album = new_track_data.album if new_track_data.album is not None else existing_track.album
    existing_track.release_date = new_track_data.release_date if new_track_data.release_date is not None else existing_track.release_date
    existing_track.explicit = new_track_data.explicit if new_track_data.explicit is not None else existing_track.explicit
    existing_track.date_liked_spotify = new_track_data.date_liked_spotify if new_track_data.date_liked_spotify is not None else existing_track.date_liked_spotify
    existing_track.comments = new_track_data.comments if new_track_data.comments is not None else existing_track.comments


def remove_track(sql_session, track_id) -> bool :
    existing_track = sql_session.query(SoulDB.Tracks).filter_by(id=track_id).one()

    if existing_track:
        sql_session.delete(existing_track)
        sql_session.flush()
        print("Successfully removed the track")
        return True
    else:
        print("Could not find the track you were trying to remove")
        return False


if __name__ == "__main__":
    main()