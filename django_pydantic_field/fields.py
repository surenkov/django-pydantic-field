import typing as t

from django.db.models.query_utils import DeferredAttribute
from django.db.models import JSONField

from . import base

__all__ = "PydanticSchemaField", "SchemaDeferredAttribute"


class SchemaDeferredAttribute(DeferredAttribute):
    """
    Forces Django to call to_python on fields when setting them.
    This is useful when you want to add some custom field data postprocessing.

    Should be added to field like a so:

    ```
    def contribute_to_class(self, cls, name, *args, **kwargs):
        super().contribute_to_class(cls, name,  *args, **kwargs)
        setattr(cls, name, SchemaDeferredAttribute(self))
    ```
    """

    def __set__(self, obj, value):
        obj.__dict__[self.field.attname] = self.field.to_python(value)


class PydanticSchemaField(base.SchemaWrapper[base.ST], JSONField):
    def __init__(
        self,
        schema: t.Type[base.ST],
        config: base.ConfigType = None,
        *args,
        error_handler=base.default_error_handler,
        **kwargs
    ):
        self.schema = schema
        self.config = config
        self.export_cfg = self._extract_export_kwargs(kwargs, dict.pop)

        field_schema = self._wrap_schema(schema, config)
        decoder = base.bind_cls(base.SchemaDecoder, schema=field_schema, error_handler=error_handler)
        encoder = base.bind_cls(base.SchemaEncoder, schema=field_schema, export_cfg=self.export_cfg)

        kwargs.update(decoder=decoder, encoder=encoder)
        super().__init__(*args, **kwargs)

    def __copy__(self):
        _, _, args, kwargs = self.deconstruct()
        return type(self)(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs.update(self.export_cfg, schema=self.schema, config=self.config)
        kwargs.pop("encoder")
        kwargs.pop("decoder")
        return name, path, args, kwargs

    def to_python(self, value) -> base.SchemaT:
        assert self.decoder is not None
        return self.decoder().decode(value)

    def contribute_to_class(self, cls, name, *args, **kwargs):
        super().contribute_to_class(cls, name, *args, **kwargs)
        setattr(cls, name, SchemaDeferredAttribute(self))
