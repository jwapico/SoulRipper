import logging
import sys
import os

def init_logger(log_filepath: str, log_level: int, db_echo: bool, silence_other_packages: bool = True):
    """
    Initializes a logger for soulripper using the logging package. Is accessed with `logger = logging.getLogger(__name__)`

    Args:
        log_filepath (str): The output path of the log file
        log_level (int): The desired log level
        db_echo (bool): Whether or not to silence sqlalchemy logs
        silence_other_packages (bool): Whether or not to silence logs from other packages
    """
    # create the file if it doesn't already exist
    if not os.path.exists(log_filepath):
        os.makedirs(os.path.dirname(log_filepath), exist_ok=True)
        with open(log_filepath, "x"):
            pass

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_filepath),
            logging.StreamHandler()
        ]
    )

    if db_echo:
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    if silence_other_packages:
        logging.getLogger("spotipy").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("pyventus").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)

    # send logs to stderr, this is to keep stdout clean for our cli printing logic
    handler = logging.StreamHandler(sys.stderr)
    logging.getLogger(__name__).handlers[:] = [handler]
