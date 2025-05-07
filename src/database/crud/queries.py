import sqlalchemy as sqla

# TODO: we need to figure out which we want to keep and which are useless, we may also want to add more

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

    for artist, track, count in rows:
        if None not in (artist, track, count):
            print(f"{artist or '<Unknown Artist>':40} | {track:75} | in {count} playlists")
    
    return rows