from __future__ import annotations

import typing as ty

import pydantic
from rest_framework import renderers

from .. import types
from . import mixins

if ty.TYPE_CHECKING:
    from collections.abc import Mapping

    RequestResponseContext = Mapping[str, ty.Any]

__all__ = ("SchemaRenderer",)


class SchemaRenderer(mixins.AnnotatedAdapterMixin[types.ST], renderers.JSONRenderer):
    schema_context_key = "renderer_schema"
    config_context_key = "renderer_config"

    def render(self, data: ty.Any, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get("response")
        if response is not None and response.exception:
            return super().render(data, accepted_media_type, renderer_context)

        adapter = self.get_adapter(renderer_context)
        if adapter is None and isinstance(data, pydantic.BaseModel):
            return self.render_pydantic_model(data, renderer_context)
        if adapter is None:
            raise RuntimeError("Schema should be either explicitly set with annotation or passed in the context")

        try:
            prep_data = adapter.validate_python(data)
            return adapter.dump_json(prep_data)
        except pydantic.ValidationError as exc:
            return exc.json(indent=True, include_input=True).encode()

    def render_pydantic_model(self, instance: pydantic.BaseModel, renderer_context: Mapping[str, ty.Any]):
        export_kwargs = types.SchemaAdapter.extract_export_kwargs(dict(renderer_context))
        export_kwargs.pop("strict", None)
        export_kwargs.pop("from_attributes", None)
        export_kwargs.pop("mode", None)

        json_dump = instance.model_dump_json(**export_kwargs)  # type: ignore
        return json_dump.encode()
