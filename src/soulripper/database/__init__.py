# CRUD Helpers (atomic database operations)
from .repositories import (
    search_for_track, 
    modify_track, 
    remove_track, 
    add_track, 
    bulk_add_tracks, 
    get_existing_track, 
    add_playlist, 
    add_track_data_to_playlist,
    execute_all_interesting_queries
) 

# sqlalchemy ORM models
from .models import (
    Tracks,
    Artists,
    Playlists,
    PlaylistTracks,
    TrackArtists, 
    Base
)

# dataclasses
from .schemas import (
    TrackData,
    ArtistData,
    PlaylistData
)

# high level services manipulating the database (business logic)
from .services import (
    add_local_track_to_db,
    add_local_library_to_db,
    update_db_with_spotify_playlist,
    update_db_with_spotify_liked_tracks,
)

__all__ = [
    # crud imports
    "add_playlist", "add_track_data_to_playlist", "add_track", "modify_track", "remove_track", "search_for_track", "get_existing_track", "bulk_add_tracks", "execute_all_interesting_queries",

    # model imports
    "Tracks", "Artists", "Playlists", "PlaylistTracks", "TrackArtists", "Base",

    # schema imports
    "TrackData", "ArtistData", "PlaylistData",

    # service imports
    "add_local_track_to_db", "add_local_library_to_db", "update_db_with_spotify_playlist", "update_db_with_spotify_liked_tracks"
]