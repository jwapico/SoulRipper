import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from database.models import TrackData
from dataclasses import dataclass
import yaml
import time
import re
import os

# immutable dataclass containg the users spotify config information
@dataclass(frozen=True)
class SpotifyUserData:
    CLIENT_ID: str
    CLIENT_SECRET: str
    REDIRECT_URI: str
    SCOPE: str

class SpotifyClient():
    # whenever a new SpotifyClient gets instantiated, we use the users API config to initialize self.spotipy_client, and set self.USER_ID as instance variables
    def __init__(self, user_data: SpotifyUserData = None, config_filepath: str = None):
        if config_filepath is None and user_data is None:
            raise Exception("You need to provide either a config.yaml filepath or a SpotifyUserData instance when initializing the SpotifyClient")

        # if SpotifyUserData was not passed in manually, we extract from the .env and config.yaml files
        if user_data is None:
            # the spotify scope is found in the yaml file
            with open(config_filepath, "r") as file:
                config = yaml.safe_load(file)

                if config is None:
                    raise Exception("Error reading the config file: config is None")

            # API configuration is found the .env file
            load_dotenv()
            CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
            CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
            REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
            SPOTIFY_SCOPE = config["spotify_scope"]

            if None in (CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SPOTIFY_SCOPE):
                raise Exception(f"One or more of the fields needed for SpotifyUserData is None, make sure you have your .env and config.yaml files configured correctly.\nExtracted SpotifyUserData: {user_data}")

            user_data = SpotifyUserData(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, SPOTIFY_SCOPE)

        self.spotipy_client = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                scope=user_data.SCOPE,
                client_id=user_data.CLIENT_ID,
                client_secret=user_data.CLIENT_SECRET,
                redirect_uri=user_data.REDIRECT_URI,
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
    
    def get_playlist_info(self, playlist_id):
        playlist_info = self.spotipy_client.playlist(playlist_id)
        playlist_name = playlist_info["name"]
        playlist_description = playlist_info["description"]

        return {
            "name": playlist_name,
            "description": playlist_description,
        }

    def get_playlist_tracks(self, playlist_id):
        all_tracks = []
        offset = 0

        while True:
            try:
                response = self.spotipy_client.playlist_items(offset=offset, playlist_id=playlist_id)
                all_tracks.extend(response["items"])
                offset += 100

                if len(response["items"]) < 100:
                    break
            except Exception as e:
                print(f"Spotify error, sleeping and trying again: {e}")
                time.sleep(5)
                continue
            
        return all_tracks

    def get_playlist_id_from_url(self, playlist_url: str):
        match = re.search(r"playlist/([a-zA-Z0-9]+)", playlist_url)
            
        if not match:
            raise ValueError("Invalid Spotify playlist link")
        
        playlist_id = match.group(1)

        return playlist_id
    
    def get_liked_tracks(self):
        all_tracks = []
        offset = 0

        while True:
            try:
                response = self.spotipy_client.current_user_saved_tracks(limit=50, offset=offset)
                all_tracks.extend(response["items"])
                offset += 50

                if len(response["items"]) < 50:
                    break

            except Exception as e:
                print(f"Spotify API error: {e}\nSleeping and retrying...")
                time.sleep(5)
                continue
            
        return all_tracks
    
    def get_track(self, id):
        return self.spotipy_client.track(id)
    
    def get_user_info(self):
        profile = self.spotipy_client.current_user()

        return (profile["id"], profile["display_name"])
    
    def get_track_data_from_playlist(self, tracks) -> list[TrackData]:
        relevant_data = []
        for track in tracks:
            spotify_id = track["track"]["id"]
            title = track["track"]["name"]
            artists = [(artist["name"], artist["id"]) for artist in track["track"]["artists"]]
            album = track["track"]["album"]["name"]
            release_date = track["track"]["album"]["release_date"]
            track_added_date = track["added_at"]
            explicit = track["track"]["explicit"]

            track_data = TrackData(
                spotify_id=spotify_id,
                title=title,
                artists=artists,
                album=album,
                release_date=release_date,
                date_liked_spotify=track_added_date,
                explicit=explicit
            )

            relevant_data.append(track_data)
        
        return relevant_data