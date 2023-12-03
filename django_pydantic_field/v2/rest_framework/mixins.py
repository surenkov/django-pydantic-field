from __future__ import annotations

import typing as ty

from ...compat.typing import get_args
from .. import types

if ty.TYPE_CHECKING:
    from collections.abc import Mapping

    RequestResponseContext = Mapping[str, ty.Any]


class AnnotatedAdapterMixin(ty.Generic[types.ST]):
    schema_context_key: ty.ClassVar[str] = "response_schema"
    config_context_key: ty.ClassVar[str] = "response_schema_config"

    def get_adapter(self, ctx: RequestResponseContext) -> types.SchemaAdapter[types.ST] | None:
        adapter = self._make_adapter_from_context(ctx)
        if adapter is None:
            adapter = self._make_adapter_from_annotation(ctx)

        return adapter

    def _make_adapter_from_context(self, ctx: RequestResponseContext) -> types.SchemaAdapter[types.ST] | None:
        schema = ctx.get(self.schema_context_key)
        if schema is not None:
            config = ctx.get(self.config_context_key)
            export_kwargs = types.SchemaAdapter.extract_export_kwargs(dict(ctx))
            return types.SchemaAdapter(schema, config, type(ctx.get("view")), None, **export_kwargs)

        return schema

    def _make_adapter_from_annotation(self, ctx: RequestResponseContext) -> types.SchemaAdapter[types.ST] | None:
        try:
            schema = get_args(self.__orig_class__)[0]  # type: ignore
        except (AttributeError, IndexError):
            return None

        config = ctx.get(self.config_context_key)
        export_kwargs = types.SchemaAdapter.extract_export_kwargs(dict(ctx))
        return types.SchemaAdapter(schema, config, type(ctx.get("view")), None, **export_kwargs)
