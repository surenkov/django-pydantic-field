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


def is_forward_ref(type_):
    if isinstance(type_, (str, t.ForwardRef)):
        return True

    origin = t.get_origin(type_)
    if origin is None:
        return False

    type_args = t.get_args(type_)
    return is_forward_ref(origin) or any(map(is_forward_ref, type_args))
