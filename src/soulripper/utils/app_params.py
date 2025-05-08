from dataclasses import dataclass

# immutable dataclass containing all the configuration data our app needs
@dataclass(frozen=True)
class AppParams:
    OUTPUT_PATH: str
    SOULSEEK_ONLY: bool
    YOUTUBE_ONLY: bool
    YOUTUBE_COOKIE_FILEPATH: str
    MAX_DOWNLOAD_RETRIES: int
    INACTIVE_DOWNLOAD_TIMEOUT: int
    SPOTIFY_SCOPE: str
    LOG_ENABLED: bool
    LOG_FILEPATH: str

