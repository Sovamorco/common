import warnings
from json import JSONDecodeError

from aiohttp import ClientSession
from hvac import utils

from .vault_client import *


class AsyncJSONAdapter(ModJSONAdapter):
    session: ClientSession

    def __init__(self, *args, **kwargs):
        session = kwargs.pop("session", None)
        if session is None:
            session = ClientSession()
            session.verify = None
        super().__init__(*args, **kwargs, session=session)
        cert = self._kwargs.pop("cert", None)
        if cert is not None:
            self._kwargs["ssl"] = cert
        verify = self._kwargs.pop("verify", None)
        if verify is not None:
            self._kwargs["ssl"] = verify
        proxies = self._kwargs.pop("proxies", None)
        if proxies is not None and len(proxies) > 0:
            if len(proxies) > 1:
                warnings.warn("Can only use 1 proxy in async client, ignoring the rest")
            self._kwargs["proxy"] = next(proxies.values())

    async def get(self, url, **kwargs):
        """Performs a GET request.

        :param url: Partial URL path to send the request to. This will be joined to the end of the instance's base_uri
            attribute.
        :type url: str | unicode
        :param kwargs: Additional keyword arguments to include in the requests call.
        :type kwargs: dict
        :return: The response of the request.
        :rtype: requests.Response
        """
        return await self.request("get", url, **kwargs)

    async def post(self, url, **kwargs):
        """Performs a POST request.

        :param url: Partial URL path to send the request to. This will be joined to the end of the instance's base_uri
            attribute.
        :type url: str | unicode
        :param kwargs: Additional keyword arguments to include in the requests call.
        :type kwargs: dict
        :return: The response of the request.
        :rtype: requests.Response
        """
        return await self.request("post", url, **kwargs)

    async def put(self, url, **kwargs):
        """Performs a PUT request.

        :param url: Partial URL path to send the request to. This will be joined to the end of the instance's base_uri
            attribute.
        :type url: str | unicode
        :param kwargs: Additional keyword arguments to include in the requests call.
        :type kwargs: dict
        :return: The response of the request.
        :rtype: requests.Response
        """
        return await self.request("put", url, **kwargs)

    async def delete(self, url, **kwargs):
        """Performs a DELETE request.

        :param url: Partial URL path to send the request to. This will be joined to the end of the instance's base_uri
            attribute.
        :type url: str | unicode
        :param kwargs: Additional keyword arguments to include in the requests call.
        :type kwargs: dict
        :return: The response of the request.
        :rtype: requests.Response
        """
        return await self.request("delete", url, **kwargs)

    async def list(self, url, **kwargs):
        """Performs a LIST request.

        :param url: Partial URL path to send the request to. This will be joined to the end of the instance's base_uri
            attribute.
        :type url: str | unicode
        :param kwargs: Additional keyword arguments to include in the requests call.
        :type kwargs: dict
        :return: The response of the request.
        :rtype: requests.Response
        """
        return await self.request("list", url, **kwargs)

    async def head(self, url, **kwargs):
        """Performs a HEAD request.

        :param url: Partial URL path to send the request to. This will be joined to the end of the instance's base_uri
            attribute.
        :type url: str | unicode
        :param kwargs: Additional keyword arguments to include in the requests call.
        :type kwargs: dict
        :return: The response of the request.
        :rtype: requests.Response
        """
        return await self.request("head", url, **kwargs)

    async def login(self, url, use_token=True, **kwargs):
        """Perform a login request.

        Associated request is typically to a path prefixed with '/v1/auth') and optionally stores the client token sent
            in the resulting Vault response for use by the :py:meth:`hvac.adapters.Adapter` instance under the _adapater
            Client attribute.

        :param url: Path to send the authentication request to.
        :type url: str | unicode
        :param use_token: if True, uses the token in the response received from the auth request to set the 'token'
            attribute on the the :py:meth:`hvac.adapters.Adapter` instance under the _adapater Client attribute.
        :type use_token: bool
        :param kwargs: Additional keyword arguments to include in the params sent with the request.
        :type kwargs: dict
        :return: The response of the auth request.
        :rtype: ClientResponse
        """
        response = await self.post(url, **kwargs)

        if use_token:
            self.token = self.get_login_token(response)

        return response

    async def request(self, method, url, headers=None, raise_exception=True, **kwargs):
        """Main method for routing HTTP requests to the configured Vault base_uri.

        :param method: HTTP method to use with the request. E.g., GET, POST, etc.
        :type method: str
        :param url: Partial URL path to send the request to. This will be joined to the end of the instance's base_uri
            attribute.
        :type url: str | unicode
        :param headers: Additional headers to include with the request.
        :type headers: dict
        :param raise_exception: If True, raise an exception via utils.raise_for_error(). Set this parameter to False to
            bypass this functionality.
        :type raise_exception: bool
        :param kwargs: Additional keyword arguments to include in the requests call.
        :type kwargs: dict
        :return: Dict on HTTP 200 with JSON body, otherwise the response object.
        :rtype: dict | ClientResponse
        """

        self.token_uses += 1

        while "//" in url:
            # Vault CLI treats a double forward slash ('//') as a single forward slash for a given path.
            # To avoid issues with the requests module's redirection logic, we perform the same translation here.
            url = url.replace("//", "/")

        url = self.urljoin(self.base_uri, url)

        if not headers:
            headers = {}

        if self.request_header:
            headers["X-Vault-Request"] = "true"

        if self.token:
            headers["X-Vault-Token"] = self.token

        if self.namespace:
            headers["X-Vault-Namespace"] = self.namespace

        wrap_ttl = kwargs.pop("wrap_ttl", None)
        if wrap_ttl:
            headers["X-Vault-Wrap-TTL"] = str(wrap_ttl)

        _kwargs = self._kwargs.copy()
        _kwargs.update(kwargs)

        if self.strict_http and method.lower() in ("list",):
            # Entry point for standard HTTP substitution
            params = _kwargs.get()
            if method.lower() == "list":
                method = "get"
                params.update({"list": "true"})
            _kwargs["params"] = params

        response = await self.session.request(
            method=method,
            url=url,
            headers=headers,
            allow_redirects=self.allow_redirects,
            **_kwargs,
        )

        if not response.ok and (raise_exception and not self.ignore_exceptions):
            text = errors = None
            if response.headers.get("Content-Type") == "application/json":
                try:
                    errors = (await response.json()).get()
                except (JSONDecodeError, TypeError):
                    pass
            if errors is None:
                text = response.text
            utils.raise_for_error(method, url, response.status, text, errors=errors)

        if response.status == 200:
            try:
                return await response.json()
            except ValueError:
                pass

        return response

    async def close(self):
        await self.session.close()


class AsyncVaultClient(VaultClient):
    def __init__(self, *args, **kwargs):
        adapter = kwargs.pop("adapter", None)
        if adapter is None:
            adapter = AsyncJSONAdapter
        super().__init__(*args, **kwargs, adapter=adapter)

    async def userpass_login(self):
        lease_started = time()
        response = await self.hvac_client.auth.userpass.login(**self.parameters)
        self._process_login_response(lease_started, response)

    async def approle_login(self):
        lease_started = time()
        response = await self.hvac_client.auth.approle.login(**self.parameters)
        self._process_login_response(lease_started, response)

    async def workload_login(self):
        super().workload_login()

    async def refresh_login(self):
        if self.time_to_refresh:
            await self.login()

    async def get_secret(self, *args, **kwargs):
        await self.refresh_login()
        response = await self._prepare_get_secret_request(*args, **kwargs)
        return self._process_get_secret_response(response)

    async def get_database_connection_profile(self, *args, **kwargs):
        await self.refresh_login()
        response = await self._prepare_get_database_credentials_request(*args, **kwargs)
        return self._process_get_database_connection_profile_response(response)
