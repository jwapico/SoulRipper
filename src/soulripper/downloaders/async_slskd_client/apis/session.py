import httpx

from .base import BaseApi

class SessionApi(BaseApi):
    """
    Async methods to interact with the Session API using httpx.
    """

    async def auth_valid(self) -> bool:
        """
        Checks if authentication is valid without raising exceptions.
        Returns `True` if valid (2xx response), `False` otherwise.
        """
        url = self.api_url + '/session'
        try:
            response = await self.client.get(url)
            return response.is_success
        except httpx.HTTPStatusError:
            return False

    async def login(self, username: str, password: str) -> dict:
        """
        Logs in and returns session info (including token).
        Raises `httpx.HTTPStatusError` on failure.
        """
        url = self.api_url + '/session'
        data = {
            'username': username,
            'password': password
        }
        response = await self.client.post(url, json=data)
        response.raise_for_status()
        return response.json()

    async def security_enabled(self) -> bool:
        """
        Checks if security is enabled.
        Raises `httpx.HTTPStatusError` on failure.
        """
        url = self.api_url + '/session/enabled'
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()