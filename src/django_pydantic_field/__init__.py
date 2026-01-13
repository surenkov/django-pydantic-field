from .fields import SchemaField as SchemaField


def __getattr__(name):
    if name == "_migration_serializers":
        from .compat import django

        return django

    raise AttributeError(f"Module {__name__!r} has no attribute {name!r}")
