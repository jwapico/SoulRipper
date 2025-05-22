from dataclasses import dataclass
from typing import Optional, List

from .track import TrackData

@dataclass
class PlaylistData:
    id: Optional[int]
    spotify_id: Optional[str]
    name: Optional[str]
    description: Optional[str]
    tracks: Optional[List[TrackData]]

    def __repr__(self):
        return (
            f"<PlaylistData(id={self.id}, "
            f"spotify_id='{self.spotify_id}', "
            f"name='{self.name}', "
            f"description='{self.description}')>"
            f"tracks='{self.tracks}')>"
        )
