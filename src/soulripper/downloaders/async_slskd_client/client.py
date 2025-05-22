import httpx
from urllib.parse import urljoin
from functools import reduce
from typing import Optional
from base64 import b64encode

from .apis import (
    SessionApi,
    ApplicationApi,
    OptionsApi,
    SearchesApi,
    TransfersApi
)

API_VERSION = 'v0'

class AsyncSlsksdClient:
    def __init__(
            self,
            host: str,
            api_key: Optional[str] = None,
            url_base: Optional[str] = '/',
            username: Optional[str] = None,
            password: Optional[str] = None,
            token: Optional[str] = None,
            verify_ssl: Optional[bool] = True,
            timeout: Optional[float] = None
    ):
        self.api_url = reduce(urljoin, [f'{host}/', f'{url_base}/', f'api/{API_VERSION}'])
        self.host = host
        self.api_key = api_key
        self.url_base = url_base
        self.username = username
        self.password = password
        self.token = token
        self.verify_ssl = verify_ssl if verify_ssl else True
        self.timeout = timeout
        self.client = None

    async def __aenter__(self):
        headers = {'accept': '*/*'}

        if self.api_key:
            headers['X-API-Key'] = self.api_key
        elif self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        elif self.username and self.password:
            async with httpx.AsyncClient(verify=self.verify_ssl, timeout=self.timeout) as temp_client:
                session_api = SessionApi(self.api_url, temp_client)
                login_response = await session_api.login(self.username, self.password)
                headers['Authorization'] = f'Bearer {login_response["token"]}'

        self.client = httpx.AsyncClient(
            headers=headers,
            verify=self.verify_ssl,
            timeout=self.timeout
        )

        base_args = (self.api_url, self.client)

        self.application = ApplicationApi(*base_args)
        self.options = OptionsApi(*base_args)
        self.searches = SearchesApi(*base_args)
        self.session = SessionApi(*base_args)
        self.transfers = TransfersApi(*base_args)

        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.client:
            await self.client.aclose()