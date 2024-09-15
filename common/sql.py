from copy import deepcopy
from time import time

import pymysql
from pymysql.cursors import DictCursor

from .vault_client import VaultClient


class SQLClient:
    def __init__(self, config, vault_client: VaultClient | None = None):
        self.config = deepcopy(config)
        self.config["autocommit"] = self.config.get("autocommit", True)
        self.vault_client = vault_client
        self.role_name = self.config.pop("role_name", None)
        self.expires_at = None if self.role_name is None else 0

    @property
    def time_to_refresh(self):
        return self.expires_at is not None and self.expires_at - time() < 60

    def refresh(self):
        if not self.time_to_refresh:
            return
        lease_started = time()
        credentials, lease_duration = self.vault_client.get_database_connection_profile(
            self.role_name
        )
        self.config["user"] = credentials["username"]
        self.config["password"] = credentials["password"]
        self.expires_at = lease_started + lease_duration

    def sql_req(
        self, query, *params, fetch_one=False, fetch_all=False, last_row_id=False
    ):
        self.refresh()
        with pymysql.connect(**self.config) as conn:
            with conn.cursor(DictCursor) as cur:
                cur.execute(query, params)
                if fetch_one:
                    return cur.fetchone()
                elif fetch_all:
                    return cur.fetchall()
                elif last_row_id:
                    return cur.lastrowid
