from dataclasses import dataclass

@dataclass
class TrackData:
    """
    this dataclass contains ALL relevant information about a track in the library

    Attributes:
        filepath (str): the file path of the track
        spotify_id (str): the Spotify ID of the track
        title (str): the title of the track
        artists (list[(str, str)]): a list of each artists name and id for the track
        album (str): the album of the track
        release_date (str): the release date of the track
        explicit (bool): whether the track is explicit or not
        comments (str): any comments about the track
    """
    filepath: str = None
    spotify_id: str = None
    title: str = None
    artists: list[(str, str)] = None
    album: str = None
    release_date: str = None
    explicit: bool = None
    comments: str = None

    def __repr__(self):
        return (
            f"TrackData(title='{self.title}', album='{self.album}', "
            f"artists={[name for name, _ in self.artists] if self.artists else None}, "
            f"release_date='{self.release_date}', explicit={self.explicit})"
        )

    def __hash__(self):
        if self.spotify_id is not None:
            return hash(self.spotify_id)
        else:
            return hash((self.title, self.album, self.filepath))

    def __eq__(self, other):
        if not isinstance(other, TrackData):
            return False
        if self.spotify_id is not None and other.spotify_id is not None:
            return self.spotify_id == other.spotify_id
        else:
            return (self.title, self.album, self.filepath) == (other.title, other.album, other.filepath)