from __future__ import annotations

import typing as ty

from django_pydantic_field.compat.pydantic import ConfigType
from django_pydantic_field.v1.utils import get_local_namespace, inherit_configs

import pydantic
from pydantic.typing import display_as_type

ST = ty.TypeVar("ST", bound="SchemaT")


if ty.TYPE_CHECKING:
    from pydantic.dataclasses import DataclassClassOrWrapper

    SchemaT = ty.Union[
        pydantic.BaseModel,
        DataclassClassOrWrapper,
        ty.Sequence[ty.Any],
        ty.Mapping[str, ty.Any],
        ty.Set[ty.Any],
        ty.FrozenSet[ty.Any],
    ]

    ModelType = ty.Type[pydantic.BaseModel]


def wrap_schema(
    schema: ty.Union[ty.Type["ST"], ty.ForwardRef],
    config: ty.Optional["ConfigType"] = None,
    allow_null: bool = False,
    **kwargs,
) -> "ModelType":
    type_name = _get_field_schema_name(schema)
    params = _get_field_schema_params(schema, config, allow_null, **kwargs)
    return pydantic.create_model(type_name, **params)


def prepare_schema(schema: "ModelType", owner: ty.Any = None) -> None:
    namespace = get_local_namespace(owner)
    schema.update_forward_refs(**namespace)  # type: ignore[deprecated]


def extract_export_kwargs(ctx: dict, extractor=dict.get) -> ty.Dict[str, ty.Any]:
    """Extract ``BaseModel.json()`` kwargs from ctx for field deconstruction/reconstruction."""

    export_ctx = dict(
        exclude_defaults=extractor(ctx, "exclude_defaults", None),
        exclude_none=extractor(ctx, "exclude_none", None),
        exclude_unset=extractor(ctx, "exclude_unset", None),
        by_alias=extractor(ctx, "by_alias", None),
        # extract json.dumps(...) kwargs, see:  https://docs.pydantic.dev/1.10/usage/exporting_models/#modeljson
        skipkeys=extractor(ctx, "skipkeys", None),
        indent=extractor(ctx, "indent", None),
        separators=extractor(ctx, "separators", None),
        allow_nan=extractor(ctx, "allow_nan", None),
        sort_keys=extractor(ctx, "sort_keys", None),
    )
    include_fields = extractor(ctx, "include", None)
    if include_fields is not None:
        export_ctx["include"] = {"__root__": include_fields}

    exclude_fields = extractor(ctx, "exclude", None)
    if exclude_fields is not None:
        export_ctx["exclude"] = {"__root__": exclude_fields}

    return {k: v for k, v in export_ctx.items() if v is not None}


def deconstruct_export_kwargs(ctx: ty.Dict[str, ty.Any]) -> ty.Dict[str, ty.Any]:
    # We want to invert the work that was done in extract_export_kwargs
    export_ctx = dict(ctx)

    include_fields = ctx.get("include")
    if include_fields is not None:
        export_ctx["include"] = include_fields["__root__"]

    exclude_fields = ctx.get("exclude")
    if exclude_fields is not None:
        export_ctx["exclude"] = exclude_fields["__root__"]

    return export_ctx


def _get_field_schema_name(schema) -> str:
    return f"FieldSchema[{display_as_type(schema)}]"


def _get_field_schema_params(schema, config=None, allow_null=False, **kwargs) -> dict:
    root_model = ty.Optional[schema] if allow_null else schema
    params: ty.Dict[str, ty.Any] = dict(
        kwargs,
        __root__=(root_model, ...),
        __config__=inherit_configs(schema, config),
    )
    return params
