import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import re

# TODO: literally fucking everything inside of docker FUCK WINDOWS FUCK WINDOWS FUCK WINDOWS FUCK WINDOWS

load_dotenv()

CLIENT_ID = os.getenv("client_id")
CLIENT_SECRET = os.getenv("client_secret")
REDIRECT_URI = os.getenv("redirect_uri")
SPOTIFY_SCOPE = "user-library-read playlist-modify-public"
spotipy_client = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        scope=SPOTIFY_SCOPE,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        open_browser=False
    )
)
USER_ID = spotipy_client.current_user()["id"]

def get_playlist_id(playlist_name):
    for playlist in get_all_playlists():
        if playlist["name"] == playlist_name:
            return playlist["id"]

    return -1

def get_all_playlists():
    playlists_info = spotipy_client.user_playlists(USER_ID, limit=1)
    num_playlists = playlists_info["total"]

    all_playlists = []
    offset = 0

    while offset < num_playlists:
        new_playlists = spotipy_client.user_playlists(USER_ID, limit=50, offset=offset)
        all_playlists.extend(new_playlists["items"])
        offset += 50

    return all_playlists

def get_all_playlist_tracks(playlist_id):
    all_tracks = []
    offset = 0

    while True:
        response = spotipy_client.playlist_items(playlist_id=playlist_id, offset=offset)
        all_tracks.extend(response["items"])
        offset += 100

        if len(response["items"]) < 100:
            break
        
    return all_tracks

def get_playlist_from_url(playlist_url: str):
	match = re.search(r"playlist/([a-zA-Z0-9]+)", playlist_url)
		
	if not match:
		raise ValueError("Invalid Spotify playlist link")
     
	playlist_id = match.group(1)

	return spotipy_client.playlist(playlist_id)
