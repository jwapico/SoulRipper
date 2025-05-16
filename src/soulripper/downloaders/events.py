from dataclasses import dataclass
from pyventus.events import AsyncIOEventEmitter
from typing import Optional

event_bus = AsyncIOEventEmitter(debug=False)

@dataclass
class SoulseekDownloadStartEvent:
    download_file_id: str
    download_filename: str
    download_user: str

@dataclass
class SoulseekDownloadUpdateEvent:
    download_file_id: str
    download_filename: str
    percent_complete: float

@dataclass
class SoulseekDownloadEndEvent:
    download_file_id: str
    end_state: str
    final_filepath: Optional[str]

@dataclass
class SoulseekSearchStartEvent:
    search_id: int
    search_query: str

@dataclass
class SoulseekSearchUpdateEvent:
    search_id: int
    search_query: str
    num_found_files: int

@dataclass
class SoulseekSearchEndEvent:
    search_id: int
    search_query: str
    num_relevant_files: int