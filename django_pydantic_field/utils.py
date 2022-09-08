import sys
import typing as t


def get_annotated_type(cls, field, default=None) -> t.Optional[t.Type]:
    annotations = t.get_type_hints(cls)
    return annotations.get(field, default)


def get_model_namespace(cls) -> t.Dict[str, t.Any]:
    module = cls.__module__
    try:
        return vars(sys.modules[module])
    except KeyError:
        return {}
