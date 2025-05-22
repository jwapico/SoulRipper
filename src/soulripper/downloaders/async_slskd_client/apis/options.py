import httpx

from .base import BaseApi

class OptionsApi(BaseApi):
    """
    Async methods to interact with the Options API using httpx.
    """

    async def get(self) -> dict:
        """
        Gets current application options.
        Raises `httpx.HTTPStatusError` on failure.
        """
        url = self.api_url + '/options'
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def get_startup(self) -> dict:
        """
        Gets startup options.
        Raises `httpx.HTTPStatusError` on failure.
        """
        url = self.api_url + '/options/startup'
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def debug(self) -> str:
        """
        Gets debug view of options (requires token auth).
        Raises `httpx.HTTPStatusError` on failure.
        """
        url = self.api_url + '/options/debug'
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def yaml_location(self) -> str:
        """
        Gets YAML config path (requires token auth).
        Raises `httpx.HTTPStatusError` on failure.
        """
        url = self.api_url + '/options/yaml/location'
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def download_yaml(self) -> str:
        """
        Gets YAML config as text (requires token auth).
        Raises `httpx.HTTPStatusError` on failure.
        """
        url = self.api_url + '/options/yaml'
        response = await self.client.get(url)
        response.raise_for_status()
        return response.json()

    async def upload_yaml(self, yaml_content: str) -> bool:
        """
        Uploads new YAML config (requires token auth).
        Raises `httpx.HTTPStatusError` on failure.
        """
        url = self.api_url + '/options/yaml'
        response = await self.client.post(url, json=yaml_content)
        response.raise_for_status()
        return True

    async def validate_yaml(self, yaml_content: str) -> str:
        """
        Validates YAML config (requires token auth).
        Returns empty string if valid, error message otherwise.
        """
        url = self.api_url + '/options/yaml/validate'
        response = await self.client.post(url, json=yaml_content)
        try:
            response.raise_for_status()
            return ""
        except httpx.HTTPStatusError as e:
            return e.response.text