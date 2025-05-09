from dataclasses import dataclass

@dataclass
class SoulseekDownloadStartEvent:
    download_file_id: int
    download_filename: str
    download_user: str

@dataclass
class SoulseekDownloadUpdateEvent:
    download_file_id: int
    percent_complete: float

@dataclass
class SoulseekDownloadEndEvent:
    download_file_id: int
    end_state: str
    final_filepath: str