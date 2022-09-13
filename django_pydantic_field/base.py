import typing as t

from django.core.serializers.json import DjangoJSONEncoder

import pydantic
from pydantic.config import get_config, inherit_config
from pydantic.typing import display_as_type

__all__ = (
    "SchemaEncoder",
    "SchemaDecoder",
    "wrap_schema",
    "extract_export_kwargs",
)

ST = t.TypeVar("ST", bound="SchemaT")

if t.TYPE_CHECKING:
    from pydantic.dataclasses import DataclassClassOrWrapper

    SchemaT = t.Union[
        pydantic.BaseModel,
        DataclassClassOrWrapper,
        t.Sequence[t.Any],
        t.Mapping[str, t.Any],
        t.Set[t.Any],
        t.FrozenSet[t.Any],
    ]

    ModelType = t.Type[pydantic.BaseModel]
    ConfigType = t.Union[pydantic.ConfigDict, t.Type[pydantic.BaseConfig], t.Type]
    JsonClsT = t.TypeVar("JsonClsT", bound=type)


class SchemaEncoder(DjangoJSONEncoder):
    def __init__(self, *args, schema: "ModelType", export=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.schema = schema
        self.export_params = export or {}

    def encode(self, obj):
        try:
            data = self.schema(__root__=obj).json(**self.export_params)
        except pydantic.ValidationError:
            # This branch used for expressions like .filter(data__contains={}).
            # We don't want that {} to be parsed as a schema.
            data = super().encode(obj)

        return data


class SchemaDecoder(t.Generic[ST]):
    def __init__(self, schema: "ModelType"):
        self.schema = schema

    def decode(self, obj: t.Any) -> "ST":
        if isinstance(obj, (str, bytes)):
            value = self.schema.parse_raw(obj).__root__  # type: ignore
        else:
            value = self.schema.parse_obj(obj).__root__  # type: ignore
        return value


def wrap_schema(
    schema: t.Type["ST"],
    config: t.Optional["ConfigType"] = None,
    allow_null: bool = False,
    **kwargs,
) -> "ModelType":
    type_name = _get_field_schema_name(schema)
    params = _get_field_schema_params(schema, config, allow_null, **kwargs)
    return pydantic.create_model(type_name, **params)


def extract_export_kwargs(ctx: dict, extractor=dict.get):
    export_ctx = dict(
        exclude_defaults=extractor(ctx, "exclude_defaults", None),
        exclude_none=extractor(ctx, "exclude_none", None),
        exclude_unset=extractor(ctx, "exclude_unset", None),
        by_alias=extractor(ctx, "by_alias", None),
    )
    include_fields = extractor(ctx, "include", None)
    if include_fields is not None:
        export_ctx["include"] = {"__root__": include_fields}

    exclude_fields = extractor(ctx, "exclude", None)
    if exclude_fields is not None:
        export_ctx["exclude"] = {"__root__": exclude_fields}

    return {k: v for k, v in export_ctx.items() if v is not None}


def _get_field_schema_name(schema: t.Type[t.Any]) -> str:
    return f"FieldSchema[{display_as_type(schema)}]"


def _get_field_schema_params(
    schema: t.Type["ST"],
    config: t.Optional["ConfigType"] = None,
    allow_null: bool = False,
    **kwargs,
) -> dict:
    root_model = t.Optional[schema] if allow_null else schema
    params: t.Dict[str, t.Any] = dict(kwargs, __root__=(root_model, ...))
    parent_config = getattr(schema, "Config", None)

    if config is not None:
        config = get_config(config)
        if parent_config is not None:
            config = inherit_config(config, parent_config)
    else:
        config = parent_config

    params["__config__"] = config
    return params
