from __future__ import annotations

import typing as ty

from django_pydantic_field.compat.typing import get_args
from django_pydantic_field.v2 import types

if ty.TYPE_CHECKING:
    from collections.abc import Mapping

    RequestResponseContext = Mapping[str, ty.Any]


class AnnotatedAdapterMixin(ty.Generic[types.ST]):
    media_type: ty.ClassVar[str]
    schema_context_key: ty.ClassVar[str] = "response_schema"
    schema_context_keys: ty.ClassVar[tuple[str, ...]] = ()
    config_context_key: ty.ClassVar[str] = "response_schema_config"
    config_context_keys: ty.ClassVar[tuple[str, ...]] = ()

    def get_adapter(self, ctx: RequestResponseContext) -> types.SchemaAdapter[types.ST] | None:
        adapter = self._make_adapter_from_context(ctx)
        if adapter is None:
            adapter = self._make_adapter_from_annotation(ctx)

        return adapter

    def _get_context_schema(self, ctx: RequestResponseContext) -> ty.Any:
        keys = self.schema_context_keys or (self.schema_context_key,)
        return next((ctx[key] for key in keys if ctx.get(key) is not None), None)

    def _get_context_config(self, ctx: RequestResponseContext) -> ty.Any:
        keys = self.config_context_keys or (self.config_context_key,)
        return next((ctx[key] for key in keys if ctx.get(key) is not None), None)

    def _build_adapter(self, schema: ty.Any, ctx: RequestResponseContext) -> types.SchemaAdapter[types.ST]:
        parent = ctx.get("view")
        config = self._get_context_config(ctx)
        export_kwargs = types.SchemaAdapter.extract_export_kwargs(dict(ctx))
        return types.SchemaAdapter(schema, config, type(parent) if parent else None, None, **export_kwargs)

    def _make_adapter_from_context(self, ctx: RequestResponseContext) -> types.SchemaAdapter[types.ST] | None:
        schema = self._get_context_schema(ctx)
        if schema is None:
            return None
        return self._build_adapter(schema, ctx)

    def _make_adapter_from_annotation(self, ctx: RequestResponseContext) -> types.SchemaAdapter[types.ST] | None:
        try:
            schema = get_args(self.__orig_class__)[0]  # type: ignore
        except (AttributeError, IndexError):
            return None
        return self._build_adapter(schema, ctx)
