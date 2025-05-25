import os
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from soulripper.database.models.tracks import Tracks
from soulripper.utils import extract_file_metadata

from ..schemas import TrackData
from ..repositories import TracksRepository

logger = logging.getLogger(__name__)

class LocalSynchronizer():
    def __init__(self, sql_session: AsyncSession):
        self._sql_session = sql_session

    # TODO: this function technically kinda works but we need a better way to extract metadata from the files - most files (all downloaded by yt-dlp) have None for all fields except filepath :/
    #   - maybe we can extract info from filename
    #   - we should probably populate metadata using TrackData from database or Spotify API - this is a lot of work dgaf rn lol
    async def add_local_library_to_db(self, music_dir: str, valid_extensions: List[str]) -> None:
        """
        Adds all songs in the music directory to the database

        Args:
            music_dir (str): the directory to add songs from
        """
        logger.info("Scanning local library...")

        total_added_files = 0
        for root, _, files in os.walk(music_dir):
            for filename in files:
                file_extension = os.path.splitext(filename)[1]
                if file_extension in valid_extensions:
                    filepath = os.path.abspath(os.path.join(root, filename))
                    local_track = await self.add_local_track_to_db(filepath)

                    if local_track:
                        total_added_files += 1

        logger.info(f"Done scanning local library. {total_added_files} files found.")

    async def add_local_track_to_db(self, filepath: str) -> Optional[Tracks]:
        if not os.path.exists(filepath):
            logger.warning(f"The file you tried to add ({filepath}) does not exist, skipping...")
            return None

        file_track_data = extract_file_metadata(filepath)

        if file_track_data is None:
            file_track_data = TrackData(filepath=filepath, comments="WARNING: Error while extracting metadata. This likely means the file is corrupted or empty")

        new_track_row = await TracksRepository.add_track(self._sql_session, file_track_data)
        await self._sql_session.commit()

        return new_track_row