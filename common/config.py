import os as _os
import typing as _typing
from json import load as _json_load
from pathlib import Path as _Path

from yaml import safe_load as _yaml_load

from .credentials import get_secret as _get_secret


class UnsupportedFormat(Exception):
    ...


class RequiredValueNotFound(Exception):
    ...


def _load_yaml(fileobj: _typing.IO) -> _typing.Sequence | _typing.Mapping:
    return _yaml_load(fileobj)


def _load_json(fileobj: _typing.IO) -> _typing.Sequence | _typing.Mapping:
    return _json_load(fileobj)


_LOADERS = {
    '.yaml': _load_yaml,
    '.yml': _load_yaml,
    '.json': _load_json,
}


def _env_interpolator(inp: str) -> str:
    res = _os.getenv(inp)
    if res is None:
        raise RequiredValueNotFound(f'Required environment variable "{inp}" is not defined')
    return res


def _fs_interpolator(inp: str) -> _typing.Mapping | _typing.Sequence:
    path = _Path(inp)
    return load_config(path)


def _vault_interpolator(inp: str) -> str | _typing.Mapping:
    return _get_secret(inp)


_INTERPOLATORS = {
    'ENV->': _env_interpolator,
    # optional environment variable, literally just os.getenv
    'OENV->': _os.getenv,
    'FS->': _fs_interpolator,
    'VAULT->': _vault_interpolator,
}


_T = _typing.TypeVar('_T', _typing.Sequence, _typing.Mapping)


def _interpolate_variables(inp: _T) -> _T:
    if isinstance(inp, str):
        for k, v in _INTERPOLATORS.items():
            if inp.startswith(k):
                return v(inp.removeprefix(k))
    elif isinstance(inp, _typing.Mapping):
        newm = {}
        for k, v in inp.items():
            newm[k] = _interpolate_variables(v)
        return newm
    elif isinstance(inp, _typing.Sequence):
        news = []
        for el in inp:
            news.append(_interpolate_variables(el))
        return news
    return inp


def load_config(filename: str | _Path = 'config.yaml'):
    config_path = _Path(filename)
    if not config_path.exists():
        raise FileNotFoundError(f'File {filename} does not exist')
    if config_path.suffix not in _LOADERS:
        raise UnsupportedFormat(f'"{config_path.suffix}" is not a supported config format')
    with config_path.open('rb') as f:
        loaded = _LOADERS[config_path.suffix](f)
    return _interpolate_variables(loaded)
