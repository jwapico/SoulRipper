from typing import Optional
import uuid

from .base import BaseApi

class SearchesApi(BaseApi):
    """
    Async class for handling search operations with httpx.
    """

    async def search_text(
        self,
        searchText: str,
        id: Optional[str] = None,
        fileLimit: int = 10000,
        filterResponses: bool = True,
        maximumPeerQueueLength: int = 1000000,
        minimumPeerUploadSpeed: int = 0,
        minimumResponseFileCount: int = 1,
        responseLimit: int = 100,
        searchTimeout: int = 15000
    ) -> dict:
        """
        Performs an async search. Raises `httpx.HTTPStatusError` on failure.
        """
        url = f"{self.api_url}/searches"

        try:
            id = str(uuid.UUID(id))
        except (ValueError, TypeError):
            id = str(uuid.uuid1())

        data = {
            "id": id,
            "fileLimit": fileLimit,
            "filterResponses": filterResponses,
            "maximumPeerQueueLength": maximumPeerQueueLength,
            "minimumPeerUploadSpeed": minimumPeerUploadSpeed,
            "minimumResponseFileCount": minimumResponseFileCount,
            "responseLimit": responseLimit,
            "searchText": searchText,
            "searchTimeout": searchTimeout,
        }
        
        response = await self.client.post(url, json=data)
        response.raise_for_status()
        return response.json()

    async def get_all(self) -> list:
        """
        Gets all searches. Raises on failure.
        """
        response = await self.client.get(f"{self.api_url}/searches")
        response.raise_for_status()
        return response.json()

    async def state(self, id: str, includeResponses: bool = False) -> dict:
        """
        Gets search state. Raises on failure.
        """
        response = await self.client.get(
            f"{self.api_url}/searches/{id}",
            params={"includeResponses": includeResponses}
        )
        response.raise_for_status()
        return response.json()

    async def stop(self, id: str) -> bool:
        """
        Stops a search. Raises on failure.
        Returns True only if successful.
        """
        response = await self.client.put(f"{self.api_url}/searches/{id}")
        response.raise_for_status()
        return True

    async def delete(self, id: str) -> bool:
        """
        Deletes a search. Raises on failure.
        Returns True only if successful.
        """
        response = await self.client.delete(f"{self.api_url}/searches/{id}")
        response.raise_for_status()
        return True

    async def search_responses(self, id: str) -> list:
        """
        Gets search responses. Raises on failure.
        """
        response = await self.client.get(f"{self.api_url}/searches/{id}/responses")
        response.raise_for_status()
        return response.json()