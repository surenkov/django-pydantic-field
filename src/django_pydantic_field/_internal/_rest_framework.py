from __future__ import annotations

import contextlib
import typing as ty

from django.core.exceptions import FieldDoesNotExist

from django_pydantic_field._internal._annotation_utils import get_annotated_type
from django_pydantic_field.compat.pydantic import PYDANTIC_V1, PYDANTIC_V2


def register_serializer_field() -> None:
    with contextlib.suppress(ImportError):
        from rest_framework.serializers import ModelSerializer

        from django_pydantic_field.fields import PydanticSchemaField

        mapping = ModelSerializer.serializer_field_mapping

        if PYDANTIC_V2:
            from django_pydantic_field.v2.rest_framework.fields import SchemaField as SchemaFieldV2

            mapping[PydanticSchemaField] = SchemaFieldV2

            with contextlib.suppress(ImportError):
                from django_pydantic_field.v1.fields import PydanticSchemaField as PydanticSchemaFieldV1
                from django_pydantic_field.v1.rest_framework import SchemaField as SchemaFieldV1

                mapping[PydanticSchemaFieldV1] = SchemaFieldV1
        elif PYDANTIC_V1:
            from django_pydantic_field.v1.fields import PydanticSchemaField as PydanticSchemaFieldV1
            from django_pydantic_field.v1.rest_framework import SchemaField as SchemaFieldV1

            mapping[PydanticSchemaField] = SchemaFieldV1
            mapping[PydanticSchemaFieldV1] = SchemaFieldV1


def bind_serializer_field(field: ty.Any, field_name: str, parent: ty.Any) -> None:
    if field.adapter.is_bound:
        return

    from django_pydantic_field.fields import PydanticSchemaField

    parent_cls = type(parent)
    model = getattr(getattr(parent, "Meta", None), "model", None)
    model_field: PydanticSchemaField[ty.Any] | None = None
    if model is not None and hasattr(model, "_meta") and field.source:
        with contextlib.suppress(FieldDoesNotExist):
            candidate = model._meta.get_field(field.source)
            if isinstance(candidate, PydanticSchemaField):
                model_field = candidate

    if model_field is None:
        field.adapter.bind(parent_cls, field_name)
        return

    has_serializer_schema = field.schema is not None or get_annotated_type(parent_cls, field_name) is not None
    schema = field.schema if has_serializer_schema else model_field.schema
    config = field.config if field.config is not None else model_field.config
    export_kwargs = {**model_field.export_kwargs, **field.export_kwargs}

    if has_serializer_schema:
        parent_type, attname = parent_cls, field_name
    else:
        parent_type, attname = model_field.adapter.parent_type, model_field.adapter.attname

    adapter_cls = type(field.adapter)
    field.schema = schema
    field.config = config
    field.export_kwargs = export_kwargs
    if hasattr(field, "export_params"):
        field.export_params = export_kwargs
    field.adapter = adapter_cls(
        schema,
        config,
        parent_type,
        attname,
        field.allow_null,
        **export_kwargs,
    )
