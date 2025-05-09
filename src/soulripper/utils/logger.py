import logging

def init_logger(log_filepath: str, log_level: int, db_echo: bool, silence_other_packages: bool = True):
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