import typing as ty

from . import types


class SchemaField:
    def __init__(*args, **kwargs):
        ...


class AutoSchema:
    def __init__(*args, **kwargs):
        ...


class SchemaParser(ty.Generic[types.ST]):
    def __init__(*args, **kwargs):
        ...


class SchemaRenderer(ty.Generic[types.ST]):
    def __init__(*args, **kwargs):
        ...
