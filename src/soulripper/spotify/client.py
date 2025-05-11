import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dataclasses import dataclass
import logging
import time
import re

from soulripper.database.schemas import TrackData

logger = logging.getLogger(__name__)

# immutable dataclass containg the users spotify config information
@dataclass(frozen=True)
class SpotifyUserData:
    CLIENT_ID: str
    CLIENT_SECRET: str
    REDIRECT_URI: str
    SCOPE: str

class SpotifyClient():
    def __init__(self, user_data: SpotifyUserData):
        self.spotipy_client = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                scope=user_data.SCOPE,
                client_id=user_data.CLIENT_ID,
                client_secret=user_data.CLIENT_SECRET,
                redirect_uri=user_data.REDIRECT_URI,
                open_browser=True
            )
        )

        try:
            self.USER_ID = self.spotipy_client.current_user()["id"]
        except Exception as e:
            logger.warning(f"Spotify API Error, sleeping... error: {e}")
            time.sleep(1)

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
                logger.error(f"Spotify error, sleeping and trying again: {e}")
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
                logger.error(f"Spotify API error: {e}\nSleeping and retrying...")
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
            if track["track"] is None:
                logger.warning(f"track field of spotify track empty for some reason, skipping...\nempty data: {track}")
                continue

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