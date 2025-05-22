from .base import BaseApi

class ApplicationApi(BaseApi):
    """
    Async methods to interact with the Application API using httpx.
    """

    async def state(self) -> dict:
        """
        Gets the current state of the application.
        Raises `httpx.HTTPStatusError` on failure.
        """
        url = self.api_url + '/application'
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def stop(self) -> bool:
        """
        Stops the application. Raises on failure.
        Returns `True` only if successful (2xx response).
        """
        url = self.api_url + '/application'
        response = await self.client.delete(url)
        response.raise_for_status()
        return True

    async def restart(self) -> bool:
        """
        Restarts the application. Raises on failure.
        Returns `True` only if successful.
        """
        url = self.api_url + '/application'
        response = await self.client.put(url)
        response.raise_for_status()
        return True

    async def version(self) -> str:
        """
        Gets the current application version.
        Raises `httpx.HTTPStatusError` on failure.
        """
        url = self.api_url + '/application/version'
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def check_updates(self, forceCheck: bool = False) -> dict:
        """
        Checks for updates. Raises on failure.
        """
        url = self.api_url + '/application/version/latest'
        params = {'forceCheck': forceCheck}
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def gc(self) -> bool:
        """
        Forces garbage collection. Raises on failure.
        Returns `True` only if successful.
        """
        url = self.api_url + '/application/gc'
        response = await self.client.post(url)
        response.raise_for_status()
        return True