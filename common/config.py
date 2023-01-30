import os
import typing
from json import load as json_load
from pathlib import Path

from yaml import safe_load as yaml_load


class UnsupportedFormat(Exception):
    ...


class RequiredValueNotFound(Exception):
    ...


def load_yaml(fileobj: typing.IO) -> typing.Sequence | typing.Mapping:
    return yaml_load(fileobj)


def load_json(fileobj: typing.IO) -> typing.Sequence | typing.Mapping:
    return json_load(fileobj)


LOADERS = {
    '.yaml': load_yaml,
    '.yml': load_yaml,
    '.json': load_json,
}


def env_interpolator(inp: str, *_) -> str:
    res = os.getenv(inp)
    if res is None:
        raise RequiredValueNotFound(f'Required environment variable "{inp}" is not defined')
    return res


def oenv_interpolator(inp: str, *_) -> str | None:
    return os.getenv(inp)


def fs_interpolator(inp: str, vault_client) -> typing.Mapping | typing.Sequence:
    return load_config(inp, vault_client)


def vault_interpolator(inp: str, vault_client) -> str | typing.Mapping:
    if vault_client is None:
        raise ValueError('Vault client not supplied for config with vault interpolations')
    return vault_client.get_secret(inp)


async def async_vault_interpolator(inp: str, vault_client) -> str | typing.Mapping:
    if vault_client is None:
        raise ValueError('Vault client not supplied for config with vault interpolations')
    return await vault_client.get_secret(inp)


def fake_async_wrapper(f):
    async def inner():
        return f()

    return inner


INTERPOLATORS = {
    'ENV->': env_interpolator,
    'OENV->': oenv_interpolator,
    'FS->': fs_interpolator,
    'VAULT->': vault_interpolator,
}

ASYNC_INTERPOLATORS = {
    'ENV->': fake_async_wrapper(env_interpolator),
    'OENV->': fake_async_wrapper(oenv_interpolator),
    'FS->': fs_interpolator,
    'VAULT->': async_vault_interpolator,
}

T = typing.TypeVar('T', typing.Sequence, typing.Mapping)


def interpolate_variables(inp: T, vault_client) -> T:
    if isinstance(inp, str):
        for k, v in INTERPOLATORS.items():
            if inp.startswith(k):
                return v(inp.removeprefix(k), vault_client)
    elif isinstance(inp, typing.Mapping):
        newm = {}
        for k, v in inp.items():
            newm[k] = interpolate_variables(v, vault_client)
        return newm
    elif isinstance(inp, typing.Sequence):
        news = []
        for el in inp:
            news.append(interpolate_variables(el, vault_client))
        return news
    return inp


async def async_interpolate_variables(inp: T, vault_client) -> T:
    if isinstance(inp, str):
        for k, v in ASYNC_INTERPOLATORS.items():
            if inp.startswith(k):
                return await v(inp.removeprefix(k), vault_client)
    elif isinstance(inp, typing.Mapping):
        newm = {}
        for k, v in inp.items():
            newm[k] = await async_interpolate_variables(v, vault_client)
        return newm
    elif isinstance(inp, typing.Sequence):
        news = []
        for el in inp:
            news.append(await async_interpolate_variables(el, vault_client))
        return news
    return inp


def load_uninterpolated_config(filename):
    config_path = Path(filename)
    if not config_path.exists():
        raise FileNotFoundError(f'File {filename} does not exist')
    if config_path.suffix not in LOADERS:
        raise UnsupportedFormat(f'"{config_path.suffix}" is not a supported config format')
    with config_path.open('rb') as f:
        return LOADERS[config_path.suffix](f)


def load_config(filename: str | Path = 'config.yaml', vault_client=None):
    loaded = load_uninterpolated_config(filename)
    return interpolate_variables(loaded, vault_client)


async def async_load_config(filename: str | Path = 'config.yaml', vault_client=None):
    loaded = load_uninterpolated_config(filename)
    return await async_interpolate_variables(loaded, vault_client)
