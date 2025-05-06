import slskd_api
import shutil
import time
import os
import re

class SlskdUtils:
    client: slskd_api.SlskdClient

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

        # wait for the download to be completed
        # TODO: refactor this whole block of code to analyze the download object and get the state from there
        download_state = self.client.transfers.get_download(download_user, file_id)["state"]
        num_retries = 0
        while not "Completed" in download_state:
            if time_limit and num_retries > time_limit:
                print(f"download took longer than {time_limit % 60} minutes - skipping - this is only for debugging and we need to look at the downloads status")
                break

            download_state = self.client.transfers.get_download(download_user, file_id)["state"]
            print(download_state)
            time.sleep(1)
            num_retries += 1

        # this moves the file from where it was downloaded to the specified output path
        if download_state == "Completed, Succeeded":
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
            print(f"Download failed: {download_state}")
            return None
        
    def attempt_downloads(self, search_results, max_retries):
        for attempt_count, (file_data, file_user) in enumerate(search_results):
            if attempt_count > max_retries:
                print(f"Max retries ({max_retries}) reached for your query")
                return (None, None, None)
            
            try:
                print(f"Attempting to download {file_data['filename']} from user: {file_user}...")
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

        print(f"Searching for: '{search_query}'")
        while self.client.searches.state(search_id)["isComplete"] == False:
            print("Searching...")
            time.sleep(1)

        results = self.client.searches.search_responses(search_id)
        print(f"Found {len(results)} results")

        return results
