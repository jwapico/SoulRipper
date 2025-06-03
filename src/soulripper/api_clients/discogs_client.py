import discogs_client

class DiscogsClient:
    def __init__(self, user_token: str):
        self._client = discogs_client.Client("soulripper/0.1", user_token=user_token)