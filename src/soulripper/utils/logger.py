import logging

def init_logger(log_filepath: str, log_level: int, db_echo: bool):
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