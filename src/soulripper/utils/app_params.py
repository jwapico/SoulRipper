from dataclasses import dataclass

# TODO: what else do we need
@dataclass
class AppParams:
    output_path: str
    youtube_only: bool
    soulseek_only: bool
    max_download_retries: int
    inactive_download_timeout: int
    log_enabled: bool
    log_filepath: str

