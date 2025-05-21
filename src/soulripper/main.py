from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import asyncio
import sys
import os
import dotenv

from soulripper.database import Base
from soulripper.downloaders import SoulseekDownloader
from soulripper.spotify import SpotifyClient, SpotifyUserData
from soulripper.utils import AppParams, extract_app_params, init_logger
from soulripper.cli import CLIOrchestrator

# TODO: everything async!
# TODO: we can probably push off some init stuff until we know we need it

async def main():
    app_params: AppParams = extract_app_params("/home/soulripper/config.yaml")

    init_logger(app_params.log_filepath, app_params.log_level, app_params.db_echo)

    # initialize the spotify client from the users api keys and config
    dotenv.load_dotenv()   
    SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
    if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET and SPOTIFY_REDIRECT_URI:
        spotify_user_data = SpotifyUserData(
            CLIENT_ID=SPOTIFY_CLIENT_ID, 
            CLIENT_SECRET=SPOTIFY_CLIENT_SECRET, 
            REDIRECT_URI=SPOTIFY_REDIRECT_URI, 
            SCOPE=app_params.spotify_scope
        )
        spotify_client = await SpotifyClient.init(spotify_user_data)
    else:
        raise Exception("You need to set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, and SPOTIFY_REDIRECT_URI in your .env file")

    # we communicate with slskd through port 5030, you can visit localhost:5030 to see the web front end. its at slskd:5030 in the docker container though
    SLSKD_API_KEY = os.getenv("SLSKD_API_KEY")
    if SLSKD_API_KEY:
        soulseek_downloader = SoulseekDownloader(SLSKD_API_KEY)
    else:
        raise Exception("You need to set SLSKD_API_KEY in your .env file")

    # create the engine with the local soul.db file and create a session
    db_engine = create_async_engine(f"sqlite+aiosqlite:///{app_params.database_path}", echo=app_params.db_echo)
    async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)

    # initialize the tables defined in souldb.py
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # if any cmdline arguments were passed, run the CLI Orchestrator
    if len(sys.argv) > 1:
        cli_orchestrator = CLIOrchestrator(
            spotify_client=spotify_client, 
            db_session_maker=async_session_maker,
            db_engine=db_engine,
            soulseek_downloader=soulseek_downloader, 
            app_params=app_params
        )

        await cli_orchestrator.run()

def soulrip():
    asyncio.run(main())

if __name__ == "__main__":
    soulrip()