from os import getenv
from time import time
from typing import Mapping, Type

from hvac import Client as HVACClient
from hvac.adapters import JSONAdapter

from .config import load_config


class VaultLoginError(ValueError):
    pass


class ModJSONAdapter(JSONAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token_uses = 0

    def request(self, *args, **kwargs):
        self.token_uses += 1
        return super().request(*args, **kwargs)


class VaultClient:
    def __init__(self, host, method, parameters, adapter=ModJSONAdapter, **kwargs):
        self.host = host
        self.method = method
        self.parameters = parameters
        self.hvac_client = HVACClient(url=self.host, adapter=adapter, **kwargs)

        self.token_expires_at = 0
        self.max_uses = 1

    @classmethod
    def from_env(cls: Type["VaultClient"]) -> "VaultClient":
        return create_uninitialized_client(cls)

    def _process_login_response(self, lease_started, response):
        if not isinstance(response, Mapping):
            raise VaultLoginError("Login response should be a Mapping")

        self.token_expires_at = lease_started + response["auth"]["lease_duration"]
        self.max_uses = response["auth"]["num_uses"]
        self.hvac_client.adapter.token_uses = 0

    def userpass_login(self):
        lease_started = time()
        response = self.hvac_client.auth.userpass.login(**self.parameters)
        self._process_login_response(lease_started, response)

    def approle_login(self):
        lease_started = time()
        response = self.hvac_client.auth.approle.login(**self.parameters)
        self._process_login_response(lease_started, response)

    # workload login sets token expiration to -1 to never refresh (does not need logging in).
    def workload_login(self):
        self.token_expires_at = -1
        self.max_uses = 0

    @property
    def login_methods(self):
        return {
            "userpass": self.userpass_login,
            "approle": self.approle_login,
            "workload": self.workload_login,
        }

    def login(self):
        if self.method not in self.login_methods:
            raise VaultLoginError(f"Login method {self.method} not supported")

        return self.login_methods[self.method]()

    @property
    def time_to_refresh(self):
        return (
            self.token_expires_at is not None and self.token_expires_at < time()
        ) or (
            self.max_uses is not None
            and self.max_uses <= self.hvac_client.adapter.token_uses
        )

    def refresh_login(self):
        if self.time_to_refresh:
            self.login()

    @staticmethod
    def _process_get_secret_response(response):
        data = response["data"]["data"]
        if len(data) == 1 and list(data.keys())[0] == "value":
            data = data["value"]
        return data

    def _prepare_get_secret_request(self, key, **kwargs):
        return self.hvac_client.secrets.kv.v2.read_secret_version(path=key, **kwargs)

    def get_secret(self, *args, **kwargs):
        self.refresh_login()
        response = self._prepare_get_secret_request(*args, **kwargs)
        return self._process_get_secret_response(response)

    def _prepare_get_database_credentials_request(self, name, **kwargs):
        return self.hvac_client.secrets.database.generate_credentials(name, **kwargs)

    @staticmethod
    def _process_get_database_connection_profile_response(response):
        return response["data"], response["lease_duration"]

    def get_database_connection_profile(self, *args, **kwargs):
        self.refresh_login()
        response = self._prepare_get_database_credentials_request(*args, **kwargs)
        return self._process_get_database_connection_profile_response(response)

    def close(self):
        return self.hvac_client.adapter.close()


def load_workload_identity():
    return {
        "host": None,
        "method": "workload",
        "parameters": {},
    }


def create_uninitialized_client(cls):
    creds_path = getenv("VAULT_CONFIG")
    if creds_path is not None:
        config = load_config(creds_path)
    else:
        config = load_workload_identity()

    return cls(
        config.pop("host"),
        config.pop("method"),
        config.pop("parameters"),
        **config,
    )
