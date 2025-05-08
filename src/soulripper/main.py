from sqlalchemy.orm import Session
import sqlalchemy as sqla
import sys
import os
import argparse
import dotenv

from soulripper.database.models import Base
from soulripper.database.services import add_local_track_to_db, add_local_library_to_db, update_db_with_spotify_playlist
from soulripper.downloaders import SoulseekDownloader, download_from_search_query, download_liked_songs, download_playlist_from_spotify_url
from soulripper.spotify import SpotifyClient, SpotifyUserData
from soulripper.utils import AppParams, extract_app_params
from soulripper.cli import CLIOrchestrator

# TODO's (~ roughly in order of importance):
#   - REFACTOR DOWNLOADING FUNCTIONS (in progress)
#       - we should populate the database with TrackData from spotify first, then download Null filepath entries after
#   - REFACTOR DATABASE CODE
#       - only call sql_session.commit() after a meaningful unit of work - atomicity
#       - we should also be wrapping ALL database operations in a try-except block, and calling sql_session.rollback() if we catch an exception
#       - we should prolly also remove the UserInfo table and stop storing api keys in the database lol
#   - better search and selection for soulseek AND yt-dlp given song title and artist
#   - better USER INTERFACE - GUI 
#       - we should keep a cli but make it better, the long flags are annoying as fuck
#           - maybe reimplement the infinite prompting thing from the submission
#       - we should have a way for the user to verify that each downloaded track is correct
#           - show them the target track (spotify data), and what was actually downloaded, filepath, metadata, etc
#           - allow them to change metadata fields
#           - walk them through each downloaded track in their library one by one
#           - once they verify the track, we change the filename to be {title} - {artists} rather than however it was downloaded
#               - write the original filename in the comments field of the database AND file metadata
#       - basically just redesign spotify lmao - i want to be able to manipulate playlists and what not
#           - im pretty sure we have read write permissions for playlists
#           - better shuffle (can have multiple different options)
#           - more ways to sort
#           - more options for columns & data shown in playlist/album view
#           - tagging system
#           - theres also a way to stream songs directly from spotify??? 
#               - https://developer.spotify.com/documentation/web-playback-sdk
#           - if we are including a player (we should) we could record statistics (better than spotify)
#           - we could go very crazy with this
#               - could embed/display wikipedia data to make the experience educational ts
#                   - basically just include the sidebar on wikipedia that displays basic facts about the artist/album
#                   - https://en.wikipedia.org/api/rest_v1/
#                   - https://pypi.org/project/Wikipedia-API/ 
#               - weird idea for playlists: more than one song can follow another
#                   - basically playlists are trees now :o
#                   - ui would prolly be nested drop downs
#       - FLUTTER !!!
#           - we need to write a REST API wrapper for our core functionality
#           - https://docs.flutter.dev/
#           - https://docs.flutter.dev/get-started/codelab
#           - https://docs.flutter.dev/get-started/install/linux/web
#           - we should make sure we have the back end right before we start on the front end
#   - TODO.md file for project management and big plans
#       - talk to colton eoghan and other potential users about high level design
#   - youtube playlist functionality
#       - https://developers.google.com/youtube/v3/docs/playlists/list
#   - refactor date_liked_spotify out of the Tracks table, can get this info by looking at the date_added field of the SPOTIFY_LIKED_SONGS playlist
#       - although maybe we should keep it as a dedicated field if we feel that it is used often enough, running search queries each time could be cumbersome
#   - restructure this file - there are too many random ahh functions
#   - pass through ssh keys in docker so git works in vscode
#   - write an actual README.md
#   - better syncing with local music directory
#       - get a songs metadata using an api such as:
#           - https://www.discogs.com/developers/
#           - big list here: https://soundcharts.com/blog/music-data-api
#   - error handling in download functions and probably other places
#       - we can write error logging to the comment field of a track
#           - we should prollt create a seperate column for this
#   - virtualdj xml playlist integration (i already have code for this from a previous project i tihnk)
#   - parallelize downloads
#       - threading :D, i think slskd can also parallelize downloads, but it may be better to use threading, idk tho
#   - the print statements in lower level functions should be changed to logging/debug statements
#       - anytime a bare print statement & return None combo appears we should be writing whatever relevant data to a log file
#   - better print statements in download and search functions - should track progress (look at slskd data) instead of printing the state on a new line each time lol
#   - type annotations for ALL functions args and return values
#   - cleanup comments & add more

#   - this list is getting long as shit lmfao

# TODO: we should clean up main - move some shit into helper functions, also still need to restructure this file </3
def main():
    app_params: AppParams = extract_app_params("/home/soulripper/config.yaml")

    # initialize the spotify client from the users api keys and config
    dotenv.load_dotenv()   
    spotify_user_data = SpotifyUserData(
        CLIENT_ID=os.getenv("SPOTIFY_CLIENT_ID"), 
        CLIENT_SECRET=os.getenv("SPOTIFY_CLIENT_SECRET"), 
        REDIRECT_URI=os.getenv("SPOTIFY_REDIRECT_URI"), 
        SCOPE=app_params.spotify_scope
    )
    spotify_client = SpotifyClient(spotify_user_data)

    # we communicate with slskd through port 5030, you can visit localhost:5030 to see the web front end. its at slskd:5030 in the docker container though
    soulseek_downloader = SoulseekDownloader(os.getenv("SLSKD_API_KEY"))

    # create the engine with the local soul.db file and create a session
    db_engine = sqla.create_engine("sqlite:////home/soulripper/assets/soul.db", echo=app_params.db_echo)
    sessionmaker = sqla.orm.sessionmaker(bind=db_engine)
    sql_session: Session = sessionmaker()

    # initialize the tables defined in souldb.py
    Base.metadata.create_all(db_engine)

    # populate the database with metadata found from files in the users output directory
    add_local_library_to_db(sql_session, app_params.output_path)

    # if any cmdline arguments were passed, run the CLIOrchestrator
    if len(sys.argv) > 1:
        cli_orchestrator = CLIOrchestrator(
            spotify_client=spotify_client, 
            sql_session=sql_session,
            db_engine=db_engine,
            soulseek_downloader=soulseek_downloader, 
            app_params=app_params
        )

        cli_orchestrator.run()

if __name__ == "__main__":
    main()