from typing import Optional
import logging
import asyncio
import re

logger = logging.getLogger(__name__)

# TODO: parse the stdout output and publish download events

# TODO: need to embed metadata into the file after it downloads
async def download_track_ytdlp(search_query: str, output_path: str) -> Optional[str] :
    """
    Downloads a track from youtube using yt-dlp
    
    Args:
        search_query (str): the query to search for
        output_path (str): the directory to download the song to

    Returns:
        str: the path to the downloaded song
    """

    # TODO: fix empty queries with non english characters ctrl f '大掃除' in sldl_helper.log 
    search_query = f"ytsearch:{search_query}".encode("utf-8").decode()
    ytdlp_output = ""

    logger.info(f"Downloading from yt-dlp: {search_query}")

    # download the file using yt-dlp and necessary flags
    process = await asyncio.create_subprocess_exec(
        "yt-dlp",
        search_query,
        # TODO: this should be better
        # "--cookies-from-browser", "firefox:~/snap/firefox/common/.mozilla/firefox/fpmcru3a.default",
        "--cookies", "/home/soulripper/assets/cookies.txt",
        "-x", "--audio-format", "mp3",
        "--embed-thumbnail", "--add-metadata",
        "--paths", output_path,
        "-o", "%(title)s.%(ext)s",
        stdout=asyncio.subprocess.PIPE, 
        stderr=asyncio.subprocess.STDOUT
    )

    # log and save the output since we need to search it for the filepath
    if process.stdout is not None:
        async for line_bytes in process.stdout:
            line = line_bytes.decode().rstrip()
            if line:
                logger.info(line)
                ytdlp_output += line

        await process.wait()

    # this extracts the filepath of the new file from the yt-dlp output, TODO: theres prolly a better way to do this
    file_path_pattern = r'\[EmbedThumbnail\] ffmpeg: Adding thumbnail to "([^"]+)"'
    match = re.search(file_path_pattern, ytdlp_output)
    download_path = match.group(1) if match else None

    return download_path
