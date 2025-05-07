from dataclasses import dataclass
import yaml

# TODO: what else do we need
@dataclass
class AppConfig:
    output_path: str
    youtube_only: bool
    soulseek_only: bool
    max_download_retries: int
    inactive_download_timeout: int
    log_enabled: bool
    log_filepath: str

def load_config_file(config_filepath: str) -> AppConfig:
    with open(config_filepath, "r") as file:
        config = yaml.safe_load(file)

    if config is None:
        raise Exception("Error reading the config file: config is None")

    OUTPUT_PATH = config["paths"]["output_path"]
    YOUTUBE_ONLY = config["download_behavior"]["youtube_only"]
    SOULSEEK_ONLY = config["download_behavior"]["soulseek_only"]
    MAX_DOWNLOAD_RETRIES = config["download_behavior"]["max_retries"]
    INACTIVE_DOWNLOAD_TIMEOUT = config["download_behavior"]["inactive_download_timeout"]
    LOG_ENABLED = config["debug"]["log"]
    LOG_FILEPATH = config["debug"]["log_filepath"]

    return AppConfig(
        output_path=OUTPUT_PATH,
        youtube_only=YOUTUBE_ONLY,
        soulseek_only=SOULSEEK_ONLY,
        max_download_retries=MAX_DOWNLOAD_RETRIES,
        inactive_download_timeout=INACTIVE_DOWNLOAD_TIMEOUT,
        log_enabled=LOG_ENABLED,
        log_filepath=LOG_FILEPATH
    )