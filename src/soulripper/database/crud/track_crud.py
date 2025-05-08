from sqlalchemy.orm import Session

from ..models import Tracks, Artists, TrackArtists
from ..schemas import TrackData

# if we find that functionality in these crud files is being duplicated across multiple models (i.e. we have duplicated get_by_id methods) we can make a BaseCRUD class that all models inherit from

# TODO: We need a better way of checking for existing tracks when spotify_id and filepath is None
def get_existing_track(session: Session, track: TrackData):
    if track.spotify_id is not None:
        existing_track = session.query(Tracks).filter_by(spotify_id=track.spotify_id).first()
    elif track.filepath is not None:
        existing_track = session.query(Tracks).filter_by(filepath=track.filepath).first()
    else:
        existing_track = session.query(Tracks).filter_by(title=track.title, album=track.album).first()

    return existing_track

def add_track(session: Session, track_data: TrackData):
    existing_track = get_existing_track(session, track_data)
    
    if existing_track:
        print(f"Track ({track_data.title} - {track_data.artists}) already exists in the database - not adding")
        return existing_track
    
    track = Tracks(
        spotify_id=track_data.spotify_id,
        filepath=track_data.filepath,
        title=track_data.title,
        album=track_data.album,
        release_date=track_data.release_date,
        explicit=track_data.explicit,
        date_liked_spotify=track_data.date_liked_spotify,
        comments=track_data.comments
    )

    session.add(track)
    session.flush()

    # add artists to the Artist table if they don't already exist, and add them to the TrackArtist association table
    if track_data.artists is not None:
        for name, spotify_id in track_data.artists:
            existing_artist = session.query(Artists).filter_by(name=name).first()

            if existing_artist is None:
                new_artist = Artists(name=name, spotify_id=spotify_id)
                session.add(new_artist)
                session.flush()
                track_artist_assoc = TrackArtists(track_id=track.id, artist_id=new_artist.id)
            else:
                track_artist_assoc = TrackArtists(track_id=track.id, artist_id=existing_artist.id)

            track.track_artists.append(track_artist_assoc)

    session.commit()
    return track

def bulk_add_tracks(session, track_data_list: set[TrackData]):
    existing_artists = {
        artist.name: artist
        for artist in session.query(Artists).all()
    }

    new_tracks = []
    new_track_artist_associations = []

    for track_data in track_data_list:
        track = Tracks(
            spotify_id=track_data.spotify_id,
            filepath=track_data.filepath,
            title=track_data.title,
            album=track_data.album,
            release_date=track_data.release_date,
            explicit=track_data.explicit,
            date_liked_spotify=track_data.date_liked_spotify,
            comments=track_data.comments
        )

        new_tracks.append(track)

        # Link artists
        if track_data.artists:
            for name, artist_spotify_id in track_data.artists:
                artist = existing_artists.get(name)
                if artist is None:
                    artist = Artists(name=name, spotify_id=artist_spotify_id)
                    session.add(artist)
                    session.flush()
                    existing_artists[name] = artist

                assoc = TrackArtists(track=track, artist=artist)
                new_track_artist_associations.append(assoc)

    # Now add everything in one shot
    session.add_all(new_tracks)
    session.add_all(new_track_artist_associations)
    session.flush()

    print(f"Inserted {len(new_tracks)} new tracks.")

def search_for_track(sql_session, track_title):
    results = sql_session.query(Tracks).filter(
        Tracks.title.ilike(f"%{track_title}%")
    ).all()

    return results

def modify_track(sql_session, track_id, new_track_data: TrackData):
    existing_track = sql_session.query(Tracks).filter_by(id=track_id).one()
    
    existing_track.spotify_id = new_track_data.spotify_id if new_track_data.spotify_id is not None else existing_track.spotify_id
    existing_track.filepath = new_track_data.filepath if new_track_data.filepath is not None else existing_track.filepath
    existing_track.title = new_track_data.title if new_track_data.title is not None else existing_track.title
    existing_track.album = new_track_data.album if new_track_data.album is not None else existing_track.album
    existing_track.release_date = new_track_data.release_date if new_track_data.release_date is not None else existing_track.release_date
    existing_track.explicit = new_track_data.explicit if new_track_data.explicit is not None else existing_track.explicit
    existing_track.date_liked_spotify = new_track_data.date_liked_spotify if new_track_data.date_liked_spotify is not None else existing_track.date_liked_spotify
    existing_track.comments = new_track_data.comments if new_track_data.comments is not None else existing_track.comments

def remove_track(sql_session, track_id) -> bool :
    existing_track = sql_session.query(Tracks).filter_by(id=track_id).one()

    if existing_track:
        sql_session.delete(existing_track)
        sql_session.flush()
        print("Successfully removed the track")
        return True
    else:
        print("Could not find the track you were trying to remove")
        return False