from .fields import SchemaField as SchemaField

def __getattr__(name):
    if name == "_migration_serializers":
        module = __import__("django_pydantic_field._migration_serializers", fromlist=["*"])
        return module

    raise AttributeError(f"Module {__name__!r} has no attribute {name!r}")
