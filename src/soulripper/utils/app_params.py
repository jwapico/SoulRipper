from dataclasses import dataclass

# immutable dataclass containing all the configuration data our app needs
@dataclass()
class AppParams:
    output_path: str
    soulseek_only: bool
    youtube_only: bool
    youtube_cookie_filepath: str
    max_download_retries: int
    inactive_download_timeout: int
    spotify_scope: str
    log_enabled: bool
    log_filepath: str

