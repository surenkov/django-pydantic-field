from __future__ import annotations

import typing as ty

from django.core.serializers.json import DjangoJSONEncoder
from pydantic import TypeAdapter, ValidationError
from typing_extensions import TypedDict

from .type_utils import SchemaT

if ty.TYPE_CHECKING:
    from pydantic.type_adapter import IncEx


class ExportParams(TypedDict, total=False):
    include: IncEx
    exclude: IncEx
    exclude_defaults: bool
    exclude_none: bool
    exclude_unset: bool
    by_alias: bool


class SchemaEncoder(DjangoJSONEncoder, ty.Generic[SchemaT]):
    def __init__(
        self,
        *args,
        adapter: TypeAdapter[SchemaT],
        export_params: ExportParams | None = None,
        raise_errors: bool = False,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.adapter: TypeAdapter[SchemaT] = adapter
        self.export_params: ExportParams = export_params or {}
        self.raise_errors: bool = raise_errors

    def encode(self, obj: ty.Any) -> str:
        try:
            raw_data = self.adapter.dump_json(obj, indent=self.indent, **self.export_params)
            data = raw_data.decode()
        except ValidationError:
            if self.raise_errors:
                raise
            data = super().encode(obj)
        return data


class SchemaDecoder(ty.Generic[SchemaT]):
    def __init__(self, adapter: TypeAdapter[SchemaT], strict: bool = False, **_kwargs):
        self.adapter: TypeAdapter[SchemaT] = adapter
        self.strict: bool = strict

    def decode(self, obj: ty.Any) -> SchemaT:
        if isinstance(obj, (str, bytes)):
            value = self.adapter.validate_json(obj, strict=self.strict)
        else:
            value = self.adapter.validate_python(obj, strict=self.strict)
        return value


def prepare_export_params(ctx: dict, extractor=dict.get) -> ExportParams:
    export_params = ((param, extractor(ctx, param, None)) for param in ExportParams.__annotations__.keys())
    return ty.cast(ExportParams, {k: v for k, v in export_params if v is not None})
