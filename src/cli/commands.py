import sqlalchemy as sqla
from sqlalchemy.orm import Session
import os

import database.crud
import database.queries
import database.models as SoulDB

def execute_user_interaction(sql_session, db_engine, spotify_client):
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
                    database.crud.update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata)
                database.crud.update_db_with_spotify_liked_tracks(spotify_client, sql_session)
                sql_session.flush()
                sql_session.commit()
                continue

            case "2":
                all_playlists_metadata = spotify_client.get_all_playlists()
                for playlist_metadata in all_playlists_metadata:
                    database.crud.update_db_with_spotify_playlist(sql_session, spotify_client, playlist_metadata)
                sql_session.flush()
                sql_session.commit()
                continue

            case "3":
                database.crud.update_db_with_spotify_liked_tracks(spotify_client, sql_session)
                sql_session.flush()
                sql_session.commit()
                continue

            case "4":
                filepath = input("Please enter the filepath of your new track: ")
                filepath = filepath.strip().strip("'\"")
                database.crud.add_new_track_to_db(sql_session, filepath)
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
                database.crud.remove_track(sql_session, track_id)
                continue
            
            case "7":
                title = input("Enter the title of the track you'd like to search for: ")
                results = database.crud.search_for_track(sql_session, title)

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
                database.queries.execute_all_interesting_queries(sql_session)
                continue
            
            case "9":
                confirmation = input("Are you sure you want to drop all tables in the database? Type 'yes' to confirm: ")
                if confirmation == "yes":
                    sql_session.close()
                    metadata = sqla.MetaData()
                    metadata.reflect(bind=db_engine)
                    metadata.drop_all(db_engine)
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

