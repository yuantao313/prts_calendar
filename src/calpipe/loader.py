"""Dynamic loading of DataSource implementations from arbitrary .py scripts."""
from __future__ import annotations

import importlib.util
import inspect
import sys
from types import ModuleType

from calpipe.base import DataSource


def load_source_class(script_path: str) -> type[DataSource]:
    """
    Import *script_path* as a module and return the first DataSource subclass found.
    Raises ValueError if none is found.
    """
    module = _import_module_from_path(script_path)

    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if obj is DataSource:
            continue
        if issubclass(obj, DataSource):
            return obj

    raise ValueError(
        f"{script_path} 中未找到 DataSource 子类。"
        " 请确保文件中定义了一个继承 DataSource 的类。"
    )


def _import_module_from_path(path: str) -> ModuleType:
    path_hash = str(abs(hash(path)) % (10 ** 8))
    module_name = f"_datasource_{path_hash}"

    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法从路径加载模块: {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
