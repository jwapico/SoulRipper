import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dataclasses import dataclass
from typing import Tuple, List, Optional, Dict
import logging
import time
import re

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
            current_user = self.spotipy_client.current_user()
            if current_user:
                self.USER_ID = current_user["id"]
            else:
                raise Exception("Could not get the current user for your Spotify credentials. Please double check that you have everything correct.")

        except spotipy.SpotifyException as e:
            logger.warning(f"Spotify API Error, sleeping... error: {e}")
            time.sleep(1)

    def get_playlist_id_from_name(self, playlist_name: str) -> Optional[str]:
        all_playlists = self.get_all_playlists()

        if all_playlists:
            for playlist in all_playlists:
                if playlist["name"] == playlist_name:
                    return playlist["id"]

    def get_all_playlists(self) -> Optional[List[Dict]]:
        playlists_info = self.spotipy_client.user_playlists(self.USER_ID, limit=1)

        if playlists_info:
            num_playlists = playlists_info["total"]

            all_playlists = []
            offset = 0

            while offset < num_playlists:
                new_playlists = self.spotipy_client.user_playlists(self.USER_ID, limit=50, offset=offset)
                if new_playlists:
                    all_playlists.extend(new_playlists["items"])
                    offset += 50

            return all_playlists
    
    def get_playlist_info(self, playlist_id: str) -> Optional[Dict[str, str]]:
        playlist_info = self.spotipy_client.playlist(playlist_id)

        if playlist_info:
            playlist_name = playlist_info["name"]
            playlist_description = playlist_info["description"]

            return {
                "name": playlist_name,
                "description": playlist_description,
            }
        
        else:
            logger.warning(f"Could not retreive info for playlist with id: {playlist_id}")
            return None

    def get_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        all_tracks = []
        offset = 0

        while True:
            try:
                response = self.spotipy_client.playlist_items(offset=offset, playlist_id=playlist_id)

                if response:
                    all_tracks.extend(response["items"])
                    offset += 100

                    if len(response["items"]) < 100:
                        break

            except spotipy.SpotifyException as e:
                logger.error(f"Spotify error, sleeping and trying again: {e}")
                time.sleep(5)
                continue
            
        return all_tracks

    def get_playlist_id_from_url(self, playlist_url: str) -> str:
        match = re.search(r"playlist/([a-zA-Z0-9]+)", playlist_url)
            
        if not match:
            raise ValueError("Invalid Spotify playlist link")
        
        playlist_id = match.group(1)

        return playlist_id
    
    def get_liked_tracks(self) -> List[Dict]:
        all_tracks = []
        offset = 0

        while True:
            try:
                response = self.spotipy_client.current_user_saved_tracks(limit=50, offset=offset)

                if response:
                    all_tracks.extend(response["items"])
                    offset += 50

                    if len(response["items"]) < 50:
                        break

            except spotipy.SpotifyException as e:
                logger.error(f"Spotify API error: {e}\nSleeping and retrying...")
                time.sleep(5)
                continue
            
        return all_tracks
    
    def get_track(self, id: str) -> Optional[Dict]:
        return self.spotipy_client.track(id)
    
    def get_user_info(self) -> Optional[Tuple[str, str]]:
        profile = self.spotipy_client.current_user()

        if profile:
            return (profile["id"], profile["display_name"])