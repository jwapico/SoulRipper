import urllib.parse
from typing import Union
import httpx

from .base import BaseApi

class TransfersApi(BaseApi):
    """
    Async methods for handling transfers using httpx.
    """

    async def cancel_download(self, username: str, id: str, remove: bool = False) -> bool:
        """
        Cancels a download. Raises on failure.
        Returns True only if successful.
        """
        url = f"{self.api_url}/transfers/downloads/{urllib.parse.quote(username)}/{id}"
        response = await self.client.delete(url, params={"remove": remove})
        response.raise_for_status()
        return True

    async def get_download(self, username: str, id: str) -> dict:
        """
        Gets a download. Raises on failure.
        """
        url = f"{self.api_url}/transfers/downloads/{urllib.parse.quote(username)}/{id}"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def remove_completed_downloads(self) -> bool:
        """
        Removes completed downloads. Raises on failure.
        Returns True only if successful.
        """
        response = await self.client.delete(f"{self.api_url}/transfers/downloads/all/completed")
        response.raise_for_status()
        return True

    async def cancel_upload(self, username: str, id: str, remove: bool = False) -> bool:
        """
        Cancels an upload. Raises on failure.
        Returns True only if successful.
        """
        url = f"{self.api_url}/transfers/uploads/{urllib.parse.quote(username)}/{id}"
        response = await self.client.delete(url, params={"remove": remove})
        response.raise_for_status()
        return True

    async def get_upload(self, username: str, id: str) -> dict:
        """
        Gets an upload. Raises on failure.
        """
        url = f"{self.api_url}/transfers/uploads/{urllib.parse.quote(username)}/{id}"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def remove_completed_uploads(self) -> bool:
        """
        Removes completed uploads. Raises on failure.
        Returns True only if successful.
        """
        response = await self.client.delete(f"{self.api_url}/transfers/uploads/all/completed")
        response.raise_for_status()
        return True

    async def enqueue(self, username: str, files: list) -> bool:
        """
        Enqueues downloads. Raises on failure.
        Returns True only if successful.
        """
        url = f"{self.api_url}/transfers/downloads/{urllib.parse.quote(username)}"
        response = await self.client.post(url, json=files)
        response.raise_for_status()
        return True

    async def get_downloads(self, username: str) -> dict:
        """
        Gets downloads for a user. Raises on failure.
        """
        url = f"{self.api_url}/transfers/downloads/{urllib.parse.quote(username)}"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def get_all_downloads(self, includeRemoved: bool = False) -> list:
        """
        Gets all downloads. Raises on failure.
        """
        response = await self.client.get(
            f"{self.api_url}/transfers/downloads/",
            params={"includeRemoved": includeRemoved}
        )
        response.raise_for_status()
        return response.json()

    async def get_queue_position(self, username: str, id: str) -> Union[int, str]:
        """
        Gets queue position. Returns int or error string.
        """
        url = f"{self.api_url}/transfers/downloads/{urllib.parse.quote(username)}/{id}/position"
        response = await self.client.get(url)
        try:
            response.raise_for_status()
            return response.json()  # Returns int for success
        except httpx.HTTPStatusError:
            return response.json()  # Returns error message string

    async def get_all_uploads(self, includeRemoved: bool = False) -> list:
        """
        Gets all uploads. Raises on failure.
        """
        response = await self.client.get(
            f"{self.api_url}/transfers/uploads/",
            params={"includeRemoved": includeRemoved}
        )
        response.raise_for_status()
        return response.json()

    async def get_uploads(self, username: str) -> dict:
        """
        Gets uploads for a user. Raises on failure.
        """
        url = f"{self.api_url}/transfers/uploads/{urllib.parse.quote(username)}"
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()