import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import re

class SpotifyClient:
    CLIENT_ID: str
    CLIENT_SECRET: str
    REDIRECT_URI: str
    SPOTIFY_SCOPE: str
    USER_ID: None
    spotipy_client: None

    def __init__(self, client_id, client_secret, redirect_uri, spotify_scope="user-library-read user-read-private playlist-read-collaborative playlist-read-private"):
        self.CLIENT_ID = client_id
        self.CLIENT_SECRET = client_secret
        self.REDIRECT_URI = redirect_uri
        self.SPOTIFY_SCOPE = spotify_scope

        load_dotenv()
        self.spotipy_client = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                scope=self.SPOTIFY_SCOPE,
                client_id=self.CLIENT_ID,
                client_secret=self.CLIENT_SECRET,
                redirect_uri=self.REDIRECT_URI,
                open_browser=False
            )
        )

        self.USER_ID = self.spotipy_client.current_user()["id"]

    def get_playlist_id(self, playlist_name):
        for playlist in self.get_all_playlists():
            if playlist["name"] == playlist_name:
                return playlist["id"]

        return -1

    def get_all_playlists(self):
        playlists_info = self.spotipy_client.user_playlists(self.USER_ID, limit=1)
        num_playlists = playlists_info["total"]

        all_playlists = []
        offset = 0

        while offset < num_playlists:
            new_playlists = self.spotipy_client.user_playlists(self.USER_ID, limit=50, offset=offset)
            all_playlists.extend(new_playlists["items"])
            offset += 50

        return all_playlists

    def get_all_playlist_tracks(self, playlist_id):
        all_tracks = []
        offset = 0

        while True:
            response = self.spotipy_client.playlist_items(playlist_id=playlist_id, offset=offset)
            all_tracks.extend(response["items"])
            offset += 100

            if len(response["items"]) < 100:
                break
            
        return all_tracks

    def get_playlist_from_url(self, playlist_url: str):
        match = re.search(r"playlist/([a-zA-Z0-9]+)", playlist_url)
            
        if not match:
            raise ValueError("Invalid Spotify playlist link")
        
        playlist_id = match.group(1)

        return self.spotipy_client.playlist(playlist_id)
    
    def get_liked_songs(self):
        all_tracks = []
        offset = 0

        while True:
            response = self.spotipy_client.current_user_saved_tracks(limit=50, offset=offset)
            all_tracks.extend(response["items"])
            offset += 50

            if len(response["items"]) < 50:
                break
            
        return all_tracks