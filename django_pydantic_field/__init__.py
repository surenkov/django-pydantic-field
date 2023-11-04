from .fields import SchemaField as SchemaField

def __getattr__(name):
    if name == "_migration_serializers":
        import warnings
        from .compat import django

        DEPRECATION_MSG = (
            "Module 'django_pydantic_field._migration_serializers' is deprecated "
            "and will be removed in version 1.0.0. "
            "Please replace it with 'django_pydantic_field.compat.django' in migrations."
        )
        warnings.warn(DEPRECATION_MSG, category=DeprecationWarning)
        return django

    raise AttributeError(f"Module {__name__!r} has no attribute {name!r}")
