from django_pydantic_field.forms import JSONFormSchemaWidget as _JSONFormSchemaWidget
from django_pydantic_field.forms import SchemaField as _SchemaField
from django_pydantic_field.v1.types import ST, SchemaAdapter, V1SchemaAdapterResolver

__all__ = ("JSONFormSchemaWidget", "SchemaField")


class SchemaField(V1SchemaAdapterResolver, _SchemaField):
    @classmethod
    def prepare_schema_widget_class(cls, widget, adapter):
        return _prepare_jsonform_widget(widget, adapter)


try:
    from django_jsonform.widgets import JSONFormWidget as _JSONFormWidget
except ImportError:
    from django_pydantic_field.forms import JSONFormSchemaWidget, _prepare_jsonform_widget
else:
    from django_pydantic_field.forms import JSONFormSchemaWidget as _JSONFormSchemaWidget

    def _prepare_jsonform_widget(widget, adapter: SchemaAdapter[ST]):
        if not isinstance(widget, type):
            return widget

        if issubclass(widget, JSONFormSchemaWidget):
            return widget(
                schema=adapter.prepared_schema,
                config=adapter.config,
                export_kwargs=adapter.export_kwargs,
                allow_null=adapter.allow_null,
            )
        elif issubclass(widget, _JSONFormWidget):
            return widget(schema=adapter.json_schema())

        return widget

    class JSONFormSchemaWidget(V1SchemaAdapterResolver, _JSONFormSchemaWidget):  # type: ignore[no-redef]
        pass
