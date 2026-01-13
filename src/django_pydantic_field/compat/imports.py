import functools
import importlib
import types

from .pydantic import PYDANTIC_V1, PYDANTIC_V2, PYDANTIC_VERSION

__all__ = ("compat_dir", "compat_getattr")


def compat_getattr(module_name: str):
    module = _import_compat_module(module_name)
    return functools.partial(getattr, module)


def compat_dir(module_name: str):
    compat_module = _import_compat_module(module_name)
    module_ns = vars(compat_module)

    if "__dir__" in module_ns:
        return module_ns["__dir__"]

    if "__all__" in module_ns:
        return functools.partial(list, module_ns["__all__"])

    return functools.partial(dir, compat_module)


def _import_compat_module(module_name: str) -> types.ModuleType:
    try:
        package, _, module = module_name.partition(".")
    except ValueError:
        package, module = module_name, ""

    module_path_parts = [package]
    if PYDANTIC_V2:
        module_path_parts.append("v2")
    elif PYDANTIC_V1:
        module_path_parts.append("v1")
    else:
        raise RuntimeError(f"Pydantic {PYDANTIC_VERSION} is not supported")

    if module:
        module_path_parts.append(module)

    module_path = ".".join(module_path_parts)
    return importlib.import_module(module_path)
