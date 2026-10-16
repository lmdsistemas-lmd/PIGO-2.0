"""Explicit Firebird driver boundary; synchronization code only consumes DB-API."""
from abc import ABC, abstractmethod


class FirebirdConnectionProvider(ABC):
    name = "abstract"

    @abstractmethod
    def connect(self, settings):
        raise NotImplementedError


class FDBProvider(FirebirdConnectionProvider):
    name = "fdb"

    def __init__(self):
        import fdb
        self.driver = fdb
        self.loaded_client = None

    def connect(self, settings):
        client = settings.get("client_path")
        if client and self.loaded_client != client:
            self.driver.load_api(client)
            self.loaded_client = client
        return self.driver.connect(
            host=settings["host"], port=settings["port"],
            database=settings["database"], user=settings["user"],
            password=settings["password"], charset=settings["charset"],
        )


class FirebirdDriverProvider(FirebirdConnectionProvider):
    name = "firebird-driver"

    def __init__(self):
        from firebird.driver import connect, driver_config
        from firebird.driver.fbapi import load_api
        self._connect = connect
        self._config = driver_config
        self._load_api = load_api
        self.loaded_client = None

    def connect(self, settings):
        client = settings.get("client_path")
        if client and self.loaded_client != client:
            self._load_api(client)
            self.loaded_client = client
        server = settings["host"]
        port = settings["port"]
        database = settings["database"]
        dsn = f"{server}/{port}:{database}"
        return self._connect(
            dsn, user=settings["user"], password=settings["password"],
            charset=settings["charset"],
        )


def create_provider(name):
    providers = {"fdb": FDBProvider, "firebird-driver": FirebirdDriverProvider}
    try:
        return providers[str(name or "fdb").lower()]()
    except KeyError as exc:
        raise ValueError(f"Driver Firebird nao suportado: {name}") from exc
