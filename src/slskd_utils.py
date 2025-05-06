import slskd_api
from rich.console import Console, Style
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
import shutil
import time
import os
import re

class SlskdUtils:
    def __init__(self, api_key: str):
        self.client = slskd_api.SlskdClient("http://slskd:5030", api_key)

    # TODO: the output filename is wrong also ERROR HANDLING
    def download_track(self, search_query: str, output_path: str, max_retries=5, time_limit=None) -> str:       
        """
        Attempts to download a track from soulseek

        Args:
            search_query (str): the song to download, can be a search query
            output_path (str): the directory to download the song to

        Returns:
            str|None: the path to the downloaded song or None of the download was unsuccessful
        """

        # search slskd for the track and filter the results if there are any
        search_results = self.search(search_query)
        if search_results is None:
            print("No results found on Soulseek")
            return None

        relevant_results = self.filter_search_results(search_results)
        if relevant_results is None:
            print("No relevant results found on Soulseek")
            return None
        
        # attempt to download the track from slskd
        download_result = self.attempt_downloads(relevant_results, max_retries)
        if download_result is None or all(result is None for result in download_result):
            print("Unable to download track from Soulseek")
            return None

        download_user, file_data, file_id, download_info = download_result
        download, download_dir, download_file = self.get_download_from_file_id(file_id)
        filename = re.split(r'[\\/]', file_data["filename"])[-1]

        # this is style config for the rich progress bar
        rich_console = Console()
        rich_progress_bar = Progress(
            TextColumn(f"[light_steel_blue]Downloading:[/light_steel_blue] [bright_white]{filename}"),
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
            task = rich_progress.add_task("", total=100)
            percent_complete = 0.0
            while percent_complete < 100:
                slskd_download = self.client.transfers.get_download(download_user, file_id)
                percent_complete = round(slskd_download["percentComplete"], 2)
                rich_progress.update(task, completed=percent_complete)
                time.sleep(.1)

                if "exception" in slskd_download.keys():
                    print(f'Exception occured in the download: {slskd_download["exception"]}')
                    break
    
        # move the file from where it was downloaded to the specified output path
        if slskd_download["state"] == "Completed, Succeeded":
            containing_dir_name = os.path.basename(download_dir["directory"].replace("\\", "/"))
            filename = os.path.basename(download_file["filename"].replace("\\", "/"))

            source_path = os.path.join(f"assets/downloads/{containing_dir_name}/{filename}")
            dest_path = os.path.join(f"{output_path}/{filename}")

            if not os.path.exists(source_path):
                print(f"ERROR: slskd download state is 'Completed, Succeeded' but the file was not found: {source_path}")
                return None

            shutil.move(source_path, dest_path)
            return dest_path
        else:
            print(f"Download failed: {slskd_download['state']}")
            return None
        
    def attempt_downloads(self, search_results, max_retries):
        for attempt_count, (file_data, file_user) in enumerate(search_results):
            if attempt_count > max_retries:
                print(f"Max retries ({max_retries}) reached for your query")
                return (None, None, None)
            
            try:
                self.client.transfers.enqueue(file_user, [file_data])
            except Exception as e:
                print(f"Error during transfer: {e}")
                continue

            download_info, file_id = self.get_download_from_filename(file_data["filename"])

            if download_info is None:
                print(f"Error: could not find download for '{file_data['filename']}' from user '{file_user}'")
            
            return (file_user, file_data, file_id, download_info)

    def get_download_from_filename(self, filename):
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
                        return (download, file["id"])

    def get_download_from_file_id(self, file_id):
        """
        Gets the download object for a file from slskd

        Args:
            slskd_client: the slskd client
            file_id: the id of the file
        
        Returns:
            download: the download data for the file
        """

        for download in self.client.transfers.get_all_downloads():
            for directory in download["directories"]:
                for file in directory["files"]:
                    if file["id"] == file_id:
                        return (download, directory, file)

    @classmethod
    # TODO: we need to analyze the quality of the results somehow
    #   - for example, if the new file contains "remix" and the original file does not, we should remove it from the query
    #   - we are incorrectly downloading a lot of shit results
    def filter_search_results(clc, search_results):
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
                    print(f"Skipping due to invalid file extension: {file['filename']}")
                    continue

                file_extension = match.group(1)

                if file_extension in ["flac", "mp3"] and result["fileCount"] > 0 and result["hasFreeUploadSlot"] == True:
                    relevant_results.append((file, result["username"]))
                
        relevant_results.sort(key=lambda candidate : candidate[0]["size"], reverse=True)

        return relevant_results

    # TODO: cleanup printing and better searching - need to extract artist and title from search data
    def search(self, search_query: str) -> list:
        """
        Searches for a track on soulseek

        Args:
            search_query (str): the query to search for

        Returns:
            list: a list of search results
        """
        search = self.client.searches.search_text(search_query)
        search_id = search["id"]

        rich_console = Console()

        with rich_console.status(f"[light_steel_blue]Searching slskd for:[/light_steel_blue] [bright_white]{search_query}[/bright_white]", spinner="earth") as status:
            while True:
                search_state = self.client.searches.state(search_id)
                num_found_files = search_state["fileCount"]
                is_complete = search_state["isComplete"]
                if is_complete:
                    break
                status.update(f"[light_steel_blue]Searching slskd for:[/light_steel_blue] [bright_white]{search_query}[/bright_white] [light_steel_blue]| files found[/light_steel_blue]: [bright_white]{num_found_files}[/bright_white]")
                time.sleep(.1)

        search_results = self.client.searches.search_responses(search_id)
        rich_console.print(f"[light_steel_blue]Search complete for:[/light_steel_blue] [bright_white]{search_query}[/bright_white] [light_steel_blue]| files found[/light_steel_blue]: [bright_white]{len(search_results)}[/bright_white]")
        return search_results
