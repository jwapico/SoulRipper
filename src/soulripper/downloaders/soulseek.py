import slskd_api
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
import logging
import shutil
import time
import os
import re

logger = logging.getLogger(__name__)

class SoulseekDownloader:
    def __init__(self, api_key: str):
        self.client = slskd_api.SlskdClient("http://slskd:5030", api_key)

    # TODO: the output filename is wrong also ERROR HANDLING
    def download_track(self, search_query: str, output_path: str, max_retries: int = 5, inactive_download_timeout: int = 10) -> str:       
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
        search_results = self.search(search_query)
        if search_results is None:
            logger.info("No results found on Soulseek")
            return None
        
        # attempt to start the download
        download_file_id, download_filepath, download_username = self.start_download(search_results, max_retries)
        if None in (download_file_id, download_filepath, download_username):
            logger.info(f"None field returned by attempt_downloads, cannot continue: {(download_file_id, download_filepath, download_username)}")
            return None

        # there prolly many more hidden bugs when it comes to wacky filenames
        download_filename = re.split(r'[\\/]', download_filepath)[-1]
        safe_filename = download_filename.replace("{", "[").replace("}", "]")

        # this is just style config for the rich progress bar
        rich_console = Console()
        rich_progress_bar = Progress(
            TextColumn(f"[light_steel_blue]Downloading:[/light_steel_blue] [bright_white]{safe_filename}"),
            BarColumn(
                bar_width=None,
                complete_style="green",
                finished_style="green",
                pulse_style="deep_pink4",
                style="deep_pink4"
            ),
            TaskProgressColumn(style="green"),
            TimeRemainingColumn(),
            expand=True,
            console=rich_console
        )     

        # this scope is just for the rich progress bar idk exactly how it works 
        with rich_progress_bar as rich_progress:
            task = rich_progress.add_task("Downloading", total=100)

            # continuously check on the download while it is incomplete, update the progress bar, and break if it takes too long or an exception occurs
            start_time = time.time()
            percent_complete = 0.0
            slskd_download = None
            while percent_complete < 100:
                # update the download, progress bar, and timer
                slskd_download = self.client.transfers.get_download(download_username, download_file_id)
                percent_complete = round(slskd_download["percentComplete"], 2)
                rich_progress.update(task, completed=percent_complete)
                elapsed_time = time.time() - start_time

                # if the download has taken longer than the timeout time AND the download is still at 0%, give up and break
                # TODO: we prolly need a better way of doing this, what if the download goes stale at 50%? i think there is way to look at transfer rates
                if elapsed_time > inactive_download_timeout * 60 and percent_complete == 0.0:
                    logging.info(f'Download was inactive for {inactive_download_timeout} minutes, skipping')
                    break

                # if something goes wrong on slskd's end an 'exception' field appears in the download - this is bad so we break if this happens
                if "exception" in slskd_download.keys():
                    logging.info(f'Exception occured in the soulseek download: {slskd_download["exception"]}')
                    break

                time.sleep(.1)
    
        # move the file from where it was downloaded to the specified output path
        if slskd_download["state"] == "Completed, Succeeded":
            # by default slskd places downloads in assets/downloads/<containing folder name of file from user>/<file from user>
            containing_dir_name = os.path.basename(os.path.dirname(download_filepath.replace("\\", "/")))
            # TODO: we prolly should not be hard coding these paths - it may be fine bc docker but idk if we want to use docker long term
            source_path = os.path.join(f"/home/soulripper/assets/downloads/{containing_dir_name}/{download_filename}")
            dest_path = os.path.join(f"{output_path}/{download_filename}")

            if not os.path.exists(source_path):
                logger.error(f"SLSKD download state is 'Completed, Succeeded' but the file was not found: {source_path}")
                return None

            shutil.move(source_path, dest_path)
            return dest_path
        else:
            logger.info(f"Download failed: {slskd_download['state']}")

            if slskd_download['state'] == "InProgress":
                raise Exception("DEBUG: Something sus has occured, download got to 100 but state is still InProgress")

            return None
    
    def start_download(self, search_results, max_retries):
        # attempt to download the each best search result until we reach max_retries or we run out of search_results
        for attempt_count, (file_data, file_user) in enumerate(search_results):
            if attempt_count > max_retries:
                logger.info(f"Max retries ({max_retries}) reached for your query, giving up on SoulSeek...")
                return (None, None, None)
            
            try:
                self.client.transfers.enqueue(file_user, [file_data])
            except Exception as e:
                logger.error(f"Error during transfer: {e}")
                continue

            filename = file_data["filename"]
            file_id = self.search_file_id_from_filename(filename)
            return (file_id, filename, file_user)
    
        return (None, None, None)

    # TODO: better searching - need to extract artist and title from returned search data somehow - maybe from filepath 
    def search(self, search_query: str) -> list:
        """
        Searches for a track on soulseek

        Args:
            search_query (str): the query to search for

        Returns:
            list: a list of relevant search results
        """
        search = self.client.searches.search_text(search_query)
        search_id = search["id"]

        rich_console = Console()

        with rich_console.status(f"[light_steel_blue]Searching SoulSeek for:[/light_steel_blue] [bright_white]{search_query}[/bright_white]", spinner="earth") as status:
            while True:
                search_state = self.client.searches.state(search_id)
                num_found_files = search_state["fileCount"]
                is_complete = search_state["isComplete"]

                if is_complete:
                    break

                status.update(f"[light_steel_blue]Searching SoulSeek for:[/light_steel_blue] [bright_white]{search_query}[/bright_white] [light_steel_blue]| Total Files found[/light_steel_blue]: [bright_white]{num_found_files}[/bright_white]")
                time.sleep(.1)

        search_results = self.client.searches.search_responses(search_id)

        # filter for just relevant results - audio files that are downloadable from the user
        relevant_results = self.filter_search_results(search_results)
        if relevant_results is None:
            logger.info("No relevant results found on Soulseek")
            return None

        rich_console.print(f"[light_steel_blue]Search complete for:[/light_steel_blue] [bright_white]{search_query}[/bright_white] [light_steel_blue]| Relevant Files found[/light_steel_blue]: [bright_white]{len(relevant_results)}[/bright_white]")
        return relevant_results

    # TODO: we need to analyze the relevance of the results somehow
    #   - we are incorrectly downloading a lot of shit results
    #       - need relevance metric
    #   - for example, if the new file contains "remix" and the original file does not, we may want to remove it from the results
    #   - currently files are sorted in order of size - this is a mid way to do it 
    #   - we should give more options to the user - file types, size, quality, etc
    def filter_search_results(self, search_results):
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
                # this extracts the file extension
                match = re.search(r'\.([a-zA-Z0-9]+)$', file["filename"])

                if match is None:
                    logger.debug(f"Skipping due to invalid file extension: {file['filename']}")
                    continue

                file_extension = match.group(1)

                if file_extension in ["flac", "mp3"] and result["fileCount"] > 0 and result["hasFreeUploadSlot"] == True:
                    relevant_results.append((file, result["username"]))
                
        relevant_results.sort(key=lambda candidate : candidate[0]["size"], reverse=True)

        if len(relevant_results) > 0:
            return relevant_results
        
        return None

    def search_file_id_from_filename(self, filename):
        """
        Gets the download object for a file from slskd

        Args:
            slskd_client: the slskd client
            file_data: slskd file data from the search results
        
        Returns:
            download: the download data for the file
        """

        for download in self.client.transfers.get_all_downloads():
            for directory in download["directories"]:
                for file in directory["files"]:
                    if file["filename"] == filename:
                        return file["id"]

