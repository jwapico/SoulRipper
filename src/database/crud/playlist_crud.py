from database.models.playlists import Playlists
from database.models.tracks import Tracks
from database.models.playlist_tracks import PlaylistTracks
from database.schemas.track import TrackData
import database.crud.track_crud

# if we find that functionality in these crud files is being duplicated across multiple models (i.e. we have duplicated get_by_id methods) we can make a BaseCRUD class that all models inherit from

def add_playlist(session, spotify_id, name, description):
    new_playlist = Playlists(
        spotify_id=spotify_id, 
        name=name, 
        description=description
    )

    session.add(new_playlist)
    session.flush()

    return new_playlist

# TODO: we should be using lists not sets, a playlist can have multiple identical tracks and thats okay
def add_track_data_to_playlist(sql_session, track_data_list: list[TrackData], playlist_row: Playlists):
    existing_spotify_ids = set(
        spotify_id for (spotify_id,) in sql_session.query(Tracks.spotify_id).filter(Tracks.spotify_id.isnot(None))
    )
    existing_non_spotify_tracks = set(
        (title, album, filepath) for (title, album, filepath) in sql_session.query(
            Tracks.title, Tracks.album, Tracks.filepath
        ).filter(Tracks.spotify_id.is_(None))
    )

    new_tracks = set()
    seen_spotify_ids = set()
    seen_non_spotify = set()

    for track_data in track_data_list:
        if track_data.spotify_id:
            if track_data.spotify_id in existing_spotify_ids or track_data.spotify_id in seen_spotify_ids:
                continue
            seen_spotify_ids.add(track_data.spotify_id)
        else:
            key = (track_data.title, track_data.album, track_data.filepath)
            if key in existing_non_spotify_tracks or key in seen_non_spotify:
                continue
            seen_non_spotify.add(key)
        new_tracks.add(track_data)
            
    database.crud.track_crud.bulk_add_tracks(sql_session,new_tracks)
    
    existing_assoc_keys = set(
        (playlist_id, track_id)
        for playlist_id, track_id in sql_session.query(
            PlaylistTracks.playlist_id,
            PlaylistTracks.track_id
        ).all()
    )
    for track_data in track_data_list:
        track = database.crud.track_crud.get_existing_track(sql_session,track_data)
        if track:
            assoc = PlaylistTracks(track_id=track.id, playlist_id=playlist_row.id, added_at=track.date_liked_spotify)
            if (assoc.playlist_id, assoc.track_id) not in existing_assoc_keys:
                existing_assoc_keys.add(assoc)
                playlist_row.playlist_tracks.append(assoc)
        else:
            print("Error")