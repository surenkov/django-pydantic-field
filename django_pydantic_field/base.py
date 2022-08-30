import logging
import typing as t

from django.core.serializers.json import DjangoJSONEncoder

from pydantic import BaseModel, BaseConfig, ValidationError
from pydantic.main import create_model
from pydantic.typing import display_as_type

__all__ = (
    "ST",
    "SchemaT",
    "ModelType",
    "SchemaEncoder",
    "SchemaDecoder",
    "SchemaWrapper",
)

logger = logging.getLogger(__name__)

SchemaT = t.Union[None, BaseModel, t.Sequence[BaseModel], t.Mapping[str, BaseModel]]
ST = t.TypeVar("ST", bound=SchemaT)

ModelType = t.Type[BaseModel]
ConfigType = t.Type[BaseConfig]


def default_error_handler(obj, err):
    logger.error("Can't parse object with the schema: obj=%s, errors=%s", obj, err)
    return obj


class SchemaEncoder(DjangoJSONEncoder):
    def __init__(self, *args, schema: ModelType, export_cfg=None, **kwargs):
        self.schema = schema
        self.export_cfg = export_cfg or {}
        super().__init__(*args, **kwargs)

    def encode(self, obj):
        try:
            data = self.schema(__root__=obj).json(**self.export_cfg)
        except ValidationError:
            # This branch used for expressions like .filter(data__contains={}).
            # We don't want that {} to be parsed as a schema.
            data = super().encode(obj)

        return data


class SchemaDecoder(t.Generic[ST]):
    def __init__(self, schema: ModelType, error_handler=default_error_handler):
        self.schema = schema
        self.error_handler = error_handler

    def decode(self, obj: t.Any) -> ST:
        try:
            if isinstance(obj, (str, bytes)):
                value = self.schema.parse_raw(obj).__root__  # type: ignore
            else:
                value = self.schema.parse_obj(obj).__root__  # type: ignore
            return value
        except ValidationError as e:
            err = e

        return self.error_handler(obj, (self.schema, err))


class SchemaWrapper(t.Generic[ST]):
    def _wrap_schema(self, schema: t.Type[ST], config: t.Optional[ConfigType] = None, **kwargs) -> ModelType:
        type_name = self._get_field_schema_name(schema)
        params = self._get_field_schema_params(schema, config, **kwargs)
        return create_model(type_name, **params)

    def _get_field_schema_name(self, schema: t.Type[t.Any]) -> str:
        return f"FieldSchema[{display_as_type(schema)}]"

    def _get_field_schema_params(self, schema: t.Type[ST], config: t.Optional[ConfigType] = None, **kwargs) -> dict:
        params: t.Dict[str, t.Any] = dict(kwargs, __root__=(t.Optional[schema], ...))

        if config is None:
            config = getattr(schema, "Config", None)

        if config is not None:
            params.update(__config__=config)

        return params

    def _extract_export_kwargs(self, ctx: dict, extractor=dict.get):
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


JsonClsT = t.TypeVar('JsonClsT', bound=t.Type)

def bind_cls(cls: JsonClsT, **initkw) -> JsonClsT:
    def __init__(self, *args, **kwargs):
        merged_kw = dict(initkw, **kwargs)
        super(bound_cls, self).__init__(*args, **merged_kw)

    bound_cls = type(cls.__name__, (cls,), {"__init__": __init__})
    return t.cast(JsonClsT, bound_cls)
