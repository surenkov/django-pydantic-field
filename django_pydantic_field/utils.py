import sys
import typing as t


def get_annotated_type(obj, field, default=None) -> t.Any:
    try:
        if isinstance(obj, type):
            annotations = obj.__dict__["__annotations__"]
        else:
            annotations = obj.__annotations__

        return annotations[field]
    except (AttributeError, KeyError):
        return default


def get_local_namespace(cls) -> t.Dict[str, t.Any]:
    try:
        module = cls.__module__
        return vars(sys.modules[module])
    except (KeyError, AttributeError):
        return {}
