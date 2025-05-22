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

# Repository Helpers (direct database operations)
from .repositories import (
    TracksRepository,
    PlaylistsRepository,
    execute_all_interesting_queries
) 

# high level services manipulating the database (business logic)
from .services import (
    add_local_track_to_db,
    add_local_library_to_db,
    update_db_with_spotify_playlist,
    update_db_with_spotify_liked_tracks,
    update_db_with_all_playlists
)

__all__ = [
    # model imports
    "Tracks",
     "Artists",
     "Playlists",
     "PlaylistTracks",
     "TrackArtists",
     "Base",
    
    # schema imports
    "TrackData",
     "ArtistData",
     "PlaylistData",
    
    # repository imports
    "TracksRepository",
     "PlaylistsRepository",
     "execute_all_interesting_queries",
    
    # service imports
    "add_local_track_to_db",
     "add_local_library_to_db",
     "update_db_with_spotify_playlist",
     "update_db_with_spotify_liked_tracks",
     "update_db_with_all_playlists",
]