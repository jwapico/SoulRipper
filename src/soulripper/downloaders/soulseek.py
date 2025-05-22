from typing import Optional, Tuple, List, Dict
import rapidfuzz.fuzz
import slskd_api
import logging
import asyncio
import shutil
import time
import os
import re

from .events import (
    SoulseekDownloadStartEvent, 
    SoulseekDownloadUpdateEvent, 
    SoulseekDownloadEndEvent, 
    SoulseekSearchStartEvent, 
    SoulseekSearchUpdateEvent, 
    SoulseekSearchEndEvent,
    event_bus
)

from soulripper.utils.file_utils import extract_file_extension, extract_filename

logger = logging.getLogger(__name__)

class SoulseekDownloader:
    # we communicate with slskd through port 5030, you can visit localhost:5030 to see the web front end
    def __init__(self, api_key: str):
        self._client = slskd_api.SlskdClient("http://slskd:5030", api_key)

    # TODO: the output filename is wrong also ERROR HANDLING
    async def download_track(self, search_query: str, output_path: str, max_retries: int = 5, inactive_download_timeout: int = 5) -> Optional[str]:       
        """
        Attempts to download a track from soulseek

        Args:
            search_query (str): the song to download, can be a search query
            output_path (str): the directory to download the song to
            max_retries (int): the maximum number of times to retry the download from SoulSeek before giving up
            inactive_download_timeout (int): the number of minutes to wait for a download to complete before giving up

        Returns:
            str|None: the path to the downloaded song
        """

        # search slskd using the passed in query
        search_results = await self.search(search_query)
        if search_results is None:
            logger.info("No results found on Soulseek")
            return None
        
        # attempt to start the download
        download_file_id, download_filepath, download_user = await self.start_download(search_results, max_retries)
        if download_file_id is None or download_filepath is None or download_user is None:
            logger.warning(f"None field returned by attempt_downloads, cannot continue: {(download_file_id, download_filepath, download_user)}")
            return None

        download_filename = re.split(r'[\\/]', download_filepath)[-1]

        # now that we are confident the download started successfully, emit a SoulseekDownloadStartEvent on the main call loop
        event_bus.emit(
            SoulseekDownloadStartEvent(
                download_file_id=download_file_id,
                download_filename=download_filename,
                download_user=download_user
            )
        )

        # continuously check on the download while it is incomplete and break if it takes too long or an exception occurs
        start_time = time.time()
        percent_complete = 0.0
        slskd_download = None
        while percent_complete < 100:
            idle_time = time.time() - start_time
            slskd_download = await asyncio.to_thread(self._client.transfers.get_download, download_user, download_file_id)

            if slskd_download is not None:
                percent_complete = slskd_download["percentComplete"]

                if percent_complete > 0:
                    event_bus.emit(
                        SoulseekDownloadUpdateEvent(
                            download_file_id=download_file_id,
                            download_filename=download_filename,
                            percent_complete=percent_complete
                        )
                    )

                # if the download speed stays at 0 for longer than the inactive_download_timeout, break the waiting loop
                download_speed = slskd_download["averageSpeed"]
                if download_speed > 0:
                    start_time = time.time()
                else:
                    idle_time = time.time() - start_time
                    if idle_time > inactive_download_timeout * 60:
                        logging.info(f'Download was inactive for {inactive_download_timeout} minutes, skipping')
                        break

                # if something goes wrong on slskd's end an 'exception' field appears in the download - this is prolly bad so we break if this happens
                if "exception" in slskd_download.keys():
                    logging.info(f'Exception occured in the soulseek download: {slskd_download["exception"]}')
                    break

                await asyncio.sleep(.1)

        if slskd_download is not None:
            # move the file from where it was downloaded to the specified output path
            if slskd_download["state"] == "Completed, Succeeded":
                # by default slskd places downloads in assets/downloads/<containing folder name of file from user>/<file from user>
                containing_dir_name = os.path.basename(os.path.dirname(download_filepath.replace("\\", "/")))
                source_path = os.path.join(f"/home/soulripper/assets/downloads/{containing_dir_name}/{download_filename}")
                final_filepath = os.path.join(f"{output_path}/{download_filename}")

                if not os.path.exists(source_path):
                    logger.error(f"SLSKD download state is 'Completed, Succeeded' but the file was not found: {source_path}")
                    return None
                
                # TODO: refactor into function to use in youtube.py, also needs to change filename based on search query/TrackData and update comments and metadata fields
                os.makedirs(os.path.dirname(final_filepath), exist_ok=True)
                shutil.move(source_path, final_filepath)
            else:
                logger.info(f"Download failed: {slskd_download['state']}")
                final_filepath = None

                if slskd_download['state'] == "InProgress":
                    logger.critical(f"Something very sus has occured, download got to 100 but state is still InProgress. Full slskd_download data: {slskd_download}")

            event_bus.emit(
                SoulseekDownloadEndEvent(
                    download_file_id=download_file_id,
                    end_state=slskd_download["state"],
                    final_filepath=final_filepath
                )
            )

            return final_filepath
    
    async def start_download(self, search_results, max_retries) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        # attempt to download the each best search result until we reach max_retries or we run out of search_results
        for attempt_count, (file_data, file_user) in enumerate(search_results):
            if attempt_count > max_retries:
                logger.info(f"Max retries ({max_retries}) reached for your query, giving up on SoulSeek...")
                return (None, None, None)
            
            try:
                await asyncio.to_thread(self._client.transfers.enqueue, file_user, [file_data])
            except Exception as e:
                logger.info(f"Slskd error during transfer: {e}")
                continue

            filename = file_data["filename"]
            file_id = await self._search_file_id_from_filename(filename)
            return (file_id, filename, file_user)
    
        return (None, None, None)

    # TODO: better searching - need to extract artist and title from returned search data somehow - maybe from filepath 
    async def search(self, search_query: str) -> Optional[List]:
        """
        Searches for a track on soulseek

        Args:
            search_query (str): the query to search for

        Returns:
            list: a list of relevant search results
        """
        # start the slskd search and extract the id
        search = await asyncio.to_thread(self._client.searches.search_text, search_query)
        search_id = search["id"]

        # emit a search start event (these events are for printing and gui updates only)
        event_bus.emit(
            SoulseekSearchStartEvent(
                search_id=search_id, 
                search_query=search_query
            )
        )

        # while the search is not complete, send update events with info about how many files were found so far
        is_complete = False
        total_found_files = 0
        while is_complete == False:
            search_state = await asyncio.to_thread(self._client.searches.state, search_id)
            is_complete = search_state["isComplete"]
            num_found_files = search_state["fileCount"]

            if num_found_files > total_found_files:
                total_found_files = num_found_files
                event_bus.emit(
                    SoulseekSearchUpdateEvent(
                        search_id=search_id, 
                        search_query=search_query, 
                        num_found_files=num_found_files
                    )
                )

            await asyncio.sleep(.1)

        # now that the search is done we can gather results
        search_results = await asyncio.to_thread(self._client.searches.search_responses, search_id)

        # filter for just relevant results - audio files that are downloadable from the user sorted by quality
        relevant_results = await self.filter_search_results(search_results, search_query)
        if relevant_results is None:
            logger.info("No relevant results found on Soulseek")

        # finally, emit a search end event and return the results
        # TODO: i think this call_soon_threadsafe will be unnecessary once we refactor everything to use async
        event_bus.emit(
            SoulseekSearchEndEvent(
                search_id=search_id,
                search_query=search_query,
                num_relevant_files=len(relevant_results) if relevant_results else 0
            )
        )

        return relevant_results

    # TODO: we need to analyze the relevance of the results somehow
    #   - we are incorrectly downloading a lot of shit results
    #       - need relevance metric
    #   - for example, if the new file contains "remix" and the original file does not, we may want to remove it from the results
    #   - currently files are sorted in order of size - this is a mid way to do it 
    #   - we should give more options to the user - file types, size, quality, etc
    async def filter_search_results(self, search_results, search_query: str, file_extensions: List[str] = ["mp3", "flac"]) -> Optional[List[Dict]]:
        """
        Filters the search results to only include downloadable mp3 and flac files sorted by size

        Args:
            search_results: search responses in the format of slskd.searches.search_responses()
        
        Returns:
            List((highest_quality_file, highest_quality_file_user: str)): The file data for the best candidate, and the username of its owner
        """

        relevant_results = []

        for result in search_results:
            for file in result["files"]:
                file_extension = extract_file_extension(file["filename"])

                required_conditions = [
                    result["fileCount"] > 0 and
                    result["hasFreeUploadSlot"] and
                    file_extension in file_extensions
                ]

                if all(required_conditions):
                    relevant_results.append((file, result["username"]))

        relevant_results.sort(key=lambda result : self._score_file(result[0], search_query, file_extensions), reverse=True)

        if len(relevant_results) > 0:
            return relevant_results
        
        return None
    
    def _score_file(self, file_data, search_query: str, file_extensions: List[str]) -> int :
        filename = extract_filename(file_data["filename"])
        score = 0

        # subtract 100 for each disallowed term in the filename
        base_disallowed_terms = [
            "acapella", "instrumental", "stems", "intro", "edit", "edited", "clean", "remix", "mix", "transition", "stems", "club", "radio", 
            "snippet", "sample", "preview", "karaoke", "cover", "parody", "rework", "bootleg", "mashup", "live", "redo", "joint", "edition",
        ]
        disallowed_terms = [term for term in base_disallowed_terms if term not in search_query.lower()]
        for term in disallowed_terms:
            if term in filename.lower():
                score -= 100

        # subtract 10 for each random/unnecessary character in the filename
        clutter_characters = [char for char in "!@#$%^&*()+=[]{}<>|/?;:_-" if char not in search_query]
        for char in clutter_characters:
            if char in filename:
                score -= 10

        # file_extensions are ordered by priority, so we add more to the score for higher priority extensions
        file_extension = extract_file_extension(filename)
        if file_extension:
            priority = len(file_extensions) - file_extensions.index(file_extension)
            score += priority * 25

        # split query and filename into words, ignoring non-alphanumeric characters, and deduct points for extra words in the filaname not found in the query
        filename_words = re.findall(r"\b[\w']+\b", filename.lower())
        query_words = re.findall(r"\b[\w']+\b", search_query.lower())
        extra_words = [word for word in filename_words if word not in query_words]
        score -= len(extra_words) * 10

        # find the token set and levenshtein (edit distance) similarity
        token_set_similarity = rapidfuzz.fuzz.token_set_ratio(search_query, filename) / 100
        edit_dist = rapidfuzz.distance.Levenshtein.distance(search_query, filename)
        max_len = max(len(search_query), len(filename))
        levenshtein_similarity = 1 - (edit_dist / max_len)

        # normalize and scale the similarities by exponential functions and a linear constant
        score += round(((0.5 * levenshtein_similarity ** 2) + (0.5 * token_set_similarity ** 2)) ** 2.5 * 200)
        return score

    async def _search_file_id_from_filename(self, filename):
        """
        Gets the download object for a file from slskd

        Args:
            slskd_client: the slskd client
            file_data: slskd file data from the search results
        
        Returns:
            download: the download data for the file
        """

        for download in await asyncio.to_thread(self._client.transfers.get_all_downloads):
            for directory in download["directories"]:
                for file in directory["files"]:
                    if file["filename"] == filename:
                        return file["id"]

