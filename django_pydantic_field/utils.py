import sys
import typing as t


def get_annotated_type(cls, field, default=None) -> t.Any:
    try:
        annotations = cls.__annotations__
        return annotations[field]
    except (AttributeError, KeyError):
        return default


def get_model_namespace(cls) -> t.Dict[str, t.Any]:
    module = cls.__module__
    try:
        return vars(sys.modules[module])
    except KeyError:
        return {}
