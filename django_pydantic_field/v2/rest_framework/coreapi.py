from __future__ import annotations

import typing as ty

from rest_framework.compat import coreapi, coreschema
from rest_framework.schemas.coreapi import AutoSchema as _CoreAPIAutoSchema

from .fields import SchemaField

if ty.TYPE_CHECKING:
    from coreschema.schemas import Schema as _CoreAPISchema  # type: ignore[import-untyped]
    from rest_framework.serializers import Serializer

__all__ = ("AutoSchema",)


class AutoSchema(_CoreAPIAutoSchema):
    """Not implemented yet."""

    def get_serializer_fields(self, path: str, method: str) -> list[coreapi.Field]:
        base_field_schemas = super().get_serializer_fields(path, method)
        if not base_field_schemas:
            return []

        serializer: Serializer = self.view.get_serializer()
        pydantic_schema_fields: dict[str, coreapi.Field] = {}

        for field_name, field in serializer.fields.items():
            if not field.read_only and isinstance(field, SchemaField):
                pydantic_schema_fields[field_name] = self._prepare_schema_field(field)

        if not pydantic_schema_fields:
            return base_field_schemas

        return [pydantic_schema_fields.get(field.name, field) for field in base_field_schemas]

    def _prepare_schema_field(self, field: SchemaField) -> coreapi.Field:
        build_core_schema = SimpleCoreSchemaTransformer(field.adapter.json_schema())
        return coreapi.Field(
            name=field.field_name,
            location="form",
            required=field.required,
            schema=build_core_schema(),
            description=field.help_text,
        )


class SimpleCoreSchemaTransformer:
    def __init__(self, json_schema: dict[str, ty.Any]):
        self.root_schema = json_schema

    def __call__(self) -> _CoreAPISchema:
        definitions = self._populate_definitions()
        root_schema = self._transform(self.root_schema)

        if definitions:
            if isinstance(root_schema, coreschema.Ref):
                schema_name = root_schema.ref_name
            else:
                schema_name = root_schema.title or "Schema"
                definitions[schema_name] = root_schema

            root_schema = coreschema.RefSpace(definitions, schema_name)

        return root_schema

    def _populate_definitions(self):
        schemas = self.root_schema.get("$defs", {})
        return {ref_name: self._transform(schema) for ref_name, schema in schemas.items()}

    def _transform(self, schema) -> _CoreAPISchema:
        schemas = [
            *self._transform_type_schema(schema),
            *self._transform_composite_types(schema),
            *self._transform_ref(schema),
        ]
        if not schemas:
            schema = self._transform_any(schema)
        elif len(schemas) == 1:
            schema = schemas[0]
        else:
            schema = coreschema.Intersection(schemas)
        return schema

    def _transform_type_schema(self, schema):
        schema_type = schema.get("type", None)

        if schema_type is not None:
            schema_types = schema_type if isinstance(schema_type, list) else [schema_type]

            for schema_type in schema_types:
                transformer = getattr(self, f"transform_{schema_type}")
                yield transformer(schema)

    def _transform_composite_types(self, schema):
        for operation, transform_name in self.COMBINATOR_TYPES.items():
            value = schema.get(operation, None)

            if value is not None:
                transformer = getattr(self, transform_name)
                yield transformer(schema)

    def _transform_ref(self, schema):
        reference = schema.get("$ref", None)
        if reference is not None:
            yield coreschema.Ref(reference)

    def _transform_any(self, schema):
        attrs = self._get_common_attributes(schema)
        return coreschema.Anything(**attrs)

    # Simple types transformers

    def transform_object(self, schema) -> coreschema.Object:
        properties = schema.get("properties", None)
        if properties is not None:
            properties = {prop: self._transform(prop_schema) for prop, prop_schema in properties.items()}

        pattern_props = schema.get("patternProperties", None)
        if pattern_props is not None:
            pattern_props = {pattern: self._transform(prop_schema) for pattern, prop_schema in pattern_props.items()}

        extra_props = schema.get("additionalProperties", None)
        if extra_props is not None:
            if extra_props not in (True, False):
                extra_props = self._transform(schema)

        return coreschema.Object(
            properties=properties,
            pattern_properties=pattern_props,
            additional_properties=extra_props,  # type: ignore
            min_properties=schema.get("minProperties"),
            max_properties=schema.get("maxProperties"),
            required=schema.get("required", []),
            **self._get_common_attributes(schema),
        )

    def transform_array(self, schema) -> coreschema.Array:
        items = schema.get("items", None)
        if items is not None:
            if isinstance(items, list):
                items = list(map(self._transform, items))
            elif items not in (True, False):
                items = self._transform(items)

        extra_items = schema.get("additionalItems")
        if extra_items is not None:
            if isinstance(items, list):
                items = list(map(self._transform, items))
            elif items not in (True, False):
                items = self._transform(items)

        return coreschema.Array(
            items=items,
            additional_items=extra_items,
            min_items=schema.get("minItems"),
            max_items=schema.get("maxItems"),
            unique_items=schema.get("uniqueItems"),
            **self._get_common_attributes(schema),
        )

    def transform_boolean(self, schema) -> coreschema.Boolean:
        attrs = self._get_common_attributes(schema)
        return coreschema.Boolean(**attrs)

    def transform_integer(self, schema) -> coreschema.Integer:
        return self._transform_numeric(schema, cls=coreschema.Integer)

    def transform_null(self, schema) -> coreschema.Null:
        attrs = self._get_common_attributes(schema)
        return coreschema.Null(**attrs)

    def transform_number(self, schema) -> coreschema.Number:
        return self._transform_numeric(schema, cls=coreschema.Number)

    def transform_string(self, schema) -> coreschema.String:
        return coreschema.String(
            min_length=schema.get("minLength"),
            max_length=schema.get("maxLength"),
            pattern=schema.get("pattern"),
            format=schema.get("format"),
            **self._get_common_attributes(schema),
        )

    # Composite types transformers

    COMBINATOR_TYPES = {
        "anyOf": "transform_union",
        "oneOf": "transform_exclusive_union",
        "allOf": "transform_intersection",
        "not": "transform_not",
    }

    def transform_union(self, schema):
        return coreschema.Union([self._transform(option) for option in schema["anyOf"]])

    def transform_exclusive_union(self, schema):
        return coreschema.ExclusiveUnion([self._transform(option) for option in schema["oneOf"]])

    def transform_intersection(self, schema):
        return coreschema.Intersection([self._transform(option) for option in schema["allOf"]])

    def transform_not(self, schema):
        return coreschema.Not(self._transform(schema["not"]))

    # Common schema transformations

    def _get_common_attributes(self, schema):
        return dict(
            title=schema.get("title"),
            description=schema.get("description"),
            default=schema.get("default"),
        )

    def _transform_numeric(self, schema, cls):
        return cls(
            minimum=schema.get("minimum"),
            maximum=schema.get("maximum"),
            exclusive_minimum=schema.get("exclusiveMinimum"),
            exclusive_maximum=schema.get("exclusiveMaximum"),
            multiple_of=schema.get("multipleOf"),
            **self._get_common_attributes(schema),
        )
