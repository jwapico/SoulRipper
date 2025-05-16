from dataclasses import dataclass
from typing import List

# dataclass containing all the configuration data our app needs
@dataclass()
class AppParams:
    output_path: str
    database_path: str
    soulseek_only: bool
    youtube_only: bool
    youtube_cookie_filepath: str
    max_download_retries: int
    inactive_download_timeout: int
    spotify_scope: str
    log_enabled: bool
    log_level: int
    log_filepath: str
    db_echo: bool
    valid_music_extensions: List[str]

