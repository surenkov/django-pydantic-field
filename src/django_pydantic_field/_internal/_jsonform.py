from __future__ import annotations

import copy
import json
import typing as ty

from django_pydantic_field._internal._openapi import _split_null_any_of

_OBJECT_SCHEMA_KEYS = ("properties", "keys", "oneOf", "anyOf", "allOf")
_VALID_ITEM_KEYS = ("type", "$ref", "oneOf", "anyOf", "allOf", "const")
_MAP_CONTAINER_KEYS = ("properties", "keys", "$defs", "definitions")
_COMBINATOR_KEYS = ("anyOf", "oneOf", "allOf")
_NON_EMPTY_STRING_FORMATS = ("date", "date-time", "time", "uuid")


def _resolve_local_ref(ref: ty.Any, root_schema: dict[str, ty.Any]) -> dict[str, ty.Any] | None:
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return None
    target: ty.Any = root_schema
    for part in ref[2:].split("/"):
        if not isinstance(target, dict) or part not in target:
            return None
        target = target[part]
    return target if isinstance(target, dict) else None


def _dereference_root_schema(schema: dict[str, ty.Any]) -> dict[str, ty.Any]:
    if "$ref" not in schema or "type" in schema:
        return schema
    target = _resolve_local_ref(schema["$ref"], schema)
    if not isinstance(target, dict):
        return schema
    rest = {k: v for k, v in schema.items() if k != "$ref"}
    if str(rest.get("title", "")).startswith("FieldSchema[") and "title" in target:
        rest.pop("title", None)
    return {**target, **rest}


def _single_dict_element(items: ty.Any) -> dict[str, ty.Any] | None:
    if isinstance(items, list) and len(items) == 1 and isinstance(items[0], dict):
        return items[0]
    return None


def _merge_unwrapped_branch(
    branch: dict[str, ty.Any], outer: dict[str, ty.Any], excluded_key: str
) -> dict[str, ty.Any]:
    rest = {k: v for k, v in outer.items() if k != excluded_key}
    if rest.get("default") is None:
        rest.pop("default", None)
    return {**branch, **rest}


def _is_nullable_schema(
    schema: ty.Any,
    root_schema: dict[str, ty.Any] | None = None,
    *,
    is_required: bool = True,
    visited_refs: frozenset[str] = frozenset(),
) -> bool:
    if not isinstance(schema, dict):
        return False

    if "$ref" in schema and root_schema is not None:
        ref = schema["$ref"]
        if isinstance(ref, str) and ref not in visited_refs:
            resolved = _resolve_local_ref(ref, root_schema)
            if resolved is not None and _is_nullable_schema(
                resolved,
                root_schema,
                is_required=is_required,
                visited_refs=visited_refs | {ref},
            ):
                return True

    single_all_of = _single_dict_element(schema.get("allOf"))
    if single_all_of is not None and _is_nullable_schema(
        single_all_of,
        root_schema,
        is_required=is_required,
        visited_refs=visited_refs,
    ):
        return True

    schema_type = schema.get("type")
    if schema_type == "null" or (isinstance(schema_type, list) and "null" in schema_type):
        return True

    for comb_key in ("anyOf", "oneOf"):
        branches = schema.get(comb_key)
        if isinstance(branches, list):
            has_null, _ = _split_null_any_of(branches)
            if has_null:
                return True

    # Pydantic v1 Optional[T] does not emit anyOf with {"type": "null"};
    # instead, the property is omitted from parent's "required" (or has default None).
    return not is_required and schema.get("default") is None


def _ensure_item_schema(item_schema: ty.Any, root_schema: dict[str, ty.Any] | None = None) -> dict[str, ty.Any]:
    if not isinstance(item_schema, dict):
        return {"type": "string"}
    normalized = _normalize_schema_node(item_schema, root_schema)
    if not any(k in normalized for k in _VALID_ITEM_KEYS):
        normalized = {**normalized, "type": "string"}
    return normalized


def _collapse_tuple_items(
    prefix_items: list[ty.Any],
    root_schema: dict[str, ty.Any] | None = None,
) -> dict[str, ty.Any]:
    if not prefix_items:
        return {"type": "string"}
    normalized_items = [_ensure_item_schema(sub, root_schema) for sub in prefix_items]
    first = normalized_items[0]
    if len(normalized_items) == 1 or ("title" not in first and all(sub == first for sub in normalized_items[1:])):
        return first
    return {"anyOf": normalized_items}


def _synthesize_branch_title(branch: ty.Any) -> ty.Any:
    if not isinstance(branch, dict) or "title" in branch:
        return branch
    if isinstance(branch.get("type"), str):
        return {**branch, "title": branch["type"].capitalize()}
    if isinstance(branch.get("$ref"), str):
        ref_name = branch["$ref"].rsplit("/", 1)[-1]
        if ref_name:
            return {**branch, "title": ref_name}
    return branch


def _normalize_array_node(normalized: dict[str, ty.Any], root_schema: dict[str, ty.Any] | None) -> None:
    if "prefixItems" in normalized:
        prefix_items = normalized.pop("prefixItems")
        if isinstance(normalized.get("items"), bool):
            normalized.pop("items", None)
        if isinstance(prefix_items, list):
            normalized.setdefault("minItems", len(prefix_items))
            normalized.setdefault("maxItems", len(prefix_items))
            normalized["items"] = _collapse_tuple_items(prefix_items, root_schema)
        else:
            normalized["items"] = _ensure_item_schema(prefix_items, root_schema)
        return

    if "items" in normalized:
        items = normalized["items"]
        if isinstance(normalized.get("additionalItems"), bool):
            normalized.pop("additionalItems", None)
        if isinstance(items, list):
            normalized.setdefault("minItems", len(items))
            normalized.setdefault("maxItems", len(items))
            normalized["items"] = _collapse_tuple_items(items, root_schema)
        elif isinstance(items, dict):
            normalized["items"] = _ensure_item_schema(items, root_schema)
        elif items is False:
            normalized.setdefault("minItems", 0)
            normalized.setdefault("maxItems", 0)
            normalized["items"] = {"type": "string"}
        return

    if normalized.get("maxItems") == 0:
        normalized.setdefault("minItems", 0)
    normalized["items"] = {"type": "string"}


def _is_object_type(schema_type: ty.Any) -> bool:
    if schema_type in ("object", "dict"):
        return True
    return isinstance(schema_type, list) and any(t in ("object", "dict") for t in schema_type)


def _normalize_schema_node(node: ty.Any, root_schema: dict[str, ty.Any] | None = None) -> ty.Any:
    if isinstance(node, list):
        return [_normalize_schema_node(el, root_schema) for el in node]
    if not isinstance(node, dict):
        return node

    normalized = dict(node)

    # 1. Issue #65: Unwrap {"type": "null"} from anyOf before normalizing current node
    if isinstance(normalized.get("anyOf"), list):
        has_null, non_null = _split_null_any_of(normalized["anyOf"])
        if has_null and non_null:
            single_non_null = _single_dict_element(non_null)
            if single_non_null is not None:
                merged = _merge_unwrapped_branch(single_non_null, normalized, "anyOf")
                return _normalize_schema_node(merged, root_schema)

            rest = _merge_unwrapped_branch({}, normalized, "anyOf")
            normalized = {
                **rest,
                "anyOf": [_synthesize_branch_title(_normalize_schema_node(item, root_schema)) for item in non_null],
            }

    # 1b. Pydantic v1 wraps $ref with sibling keywords (default, title, description) in single-element allOf
    single_all_of = _single_dict_element(normalized.get("allOf"))
    if single_all_of is not None:
        merged = _merge_unwrapped_branch(single_all_of, normalized, "allOf")
        return _normalize_schema_node(merged, root_schema)

    # 2. Issue #65: Prune nullable properties from parent object's "required" list
    raw_properties = normalized.get("properties")
    if isinstance(raw_properties, dict) and isinstance(normalized.get("required"), list):
        nullable_props = {
            prop_name
            for prop_name, prop_schema in raw_properties.items()
            if _is_nullable_schema(prop_schema, root_schema, is_required=True)
        }
        if nullable_props:
            new_required = [req for req in normalized["required"] if req not in nullable_props]
            if new_required:
                normalized["required"] = new_required
            else:
                normalized.pop("required", None)

    # 3. Recurse into map containers (properties, keys, $defs, definitions)
    for key in _MAP_CONTAINER_KEYS:
        container = normalized.get(key)
        if isinstance(container, dict):
            normalized[key] = {k: _normalize_schema_node(v, root_schema) for k, v in container.items()}

    # 4. Recurse into combinators (anyOf, oneOf, allOf)
    for comb_key in _COMBINATOR_KEYS:
        comb_val = normalized.get(comb_key)
        if isinstance(comb_val, list):
            normalized[comb_key] = [_normalize_schema_node(sub, root_schema) for sub in comb_val]

    # 5. Issue #66: Normalize array / tuple schemas (prefixItems, items: list, untyped/empty items)
    if normalized.get("type") == "array" or "prefixItems" in normalized or "items" in normalized:
        _normalize_array_node(normalized, root_schema)

    # 6. Issue #64: Normalize additionalProperties & object schemas lacking properties
    if isinstance(normalized.get("additionalProperties"), dict):
        normalized["additionalProperties"] = _ensure_item_schema(normalized["additionalProperties"], root_schema)

    if _is_object_type(normalized.get("type")) and not any(k in normalized for k in _OBJECT_SCHEMA_KEYS):
        normalized["properties"] = {}
        normalized.setdefault("additionalProperties", True)

    return normalized


def normalize_jsonform_schema(schema: dict[str, ty.Any]) -> dict[str, ty.Any]:
    """Normalize a Pydantic v1 or v2 JSON Schema into a django-jsonform compatible schema."""
    normalized = _dereference_root_schema(copy.deepcopy(schema))
    return _normalize_schema_node(normalized, normalized)


def _is_empty_string_coercible(
    schema: dict[str, ty.Any],
    root_schema: dict[str, ty.Any],
    *,
    is_required: bool,
    visited_refs: frozenset[str],
) -> bool:
    if _is_nullable_schema(
        schema,
        root_schema,
        is_required=is_required,
        visited_refs=visited_refs,
    ):
        return True
    if schema.get("format") in _NON_EMPTY_STRING_FORMATS:
        return True
    return isinstance(schema.get("enum"), list) and "" not in schema["enum"]


def _coerce_dict_data(
    data: dict[str, ty.Any],
    schema: dict[str, ty.Any],
    root_schema: dict[str, ty.Any],
) -> tuple[dict[str, ty.Any], bool]:
    raw_props = schema.get("properties")
    properties = raw_props if isinstance(raw_props, dict) else {}
    raw_req = schema.get("required")
    required_set = set(raw_req) if isinstance(raw_req, list) else set()
    add_props = schema.get("additionalProperties")
    changed_any = False
    new_dict = dict(data)

    for key, val in data.items():
        if key in properties:
            item_schema = properties[key]
            item_required = key in required_set
        elif isinstance(add_props, dict):
            item_schema = add_props
            item_required = True
        else:
            continue

        new_val, changed = _coerce_node_data(val, item_schema, root_schema, is_required=item_required)
        if changed:
            new_dict[key] = new_val
            changed_any = True

    return (new_dict if changed_any else data), changed_any


def _coerce_list_data(
    data: list[ty.Any],
    schema: dict[str, ty.Any],
    root_schema: dict[str, ty.Any],
) -> tuple[list[ty.Any], bool]:
    positional_items = schema.get("prefixItems")
    if not isinstance(positional_items, list):
        positional_items = schema.get("items") if isinstance(schema.get("items"), list) else None

    uniform_item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else None
    if positional_items is None and uniform_item_schema is None:
        return data, False

    changed_any = False
    new_list = list(data)
    for idx, el in enumerate(data):
        if positional_items is not None:
            if idx >= len(positional_items):
                break
            el_schema = positional_items[idx]
        else:
            el_schema = uniform_item_schema

        new_el, changed = _coerce_node_data(el, el_schema, root_schema, is_required=True)
        if changed:
            new_list[idx] = new_el
            changed_any = True

    return (new_list if changed_any else data), changed_any


def _coerce_node_data(
    data: ty.Any,
    schema: ty.Any,
    root_schema: dict[str, ty.Any],
    *,
    is_required: bool = True,
    visited_refs: frozenset[str] = frozenset(),
) -> tuple[ty.Any, bool]:
    if not isinstance(schema, dict):
        return data, False

    ref = schema.get("$ref")
    if isinstance(ref, str):
        if ref in visited_refs:
            return data, False
        resolved = _resolve_local_ref(ref, root_schema)
        if resolved is not None:
            merged_schema = {**resolved, **{k: v for k, v in schema.items() if k != "$ref"}}
            return _coerce_node_data(
                data,
                merged_schema,
                root_schema,
                is_required=is_required,
                visited_refs=visited_refs | {ref},
            )

    if data == "" and _is_empty_string_coercible(
        schema,
        root_schema,
        is_required=is_required,
        visited_refs=visited_refs,
    ):
        if schema.get("default") != "":
            return None, True
        return data, False

    # If schema is a combinator (anyOf / oneOf / allOf) wrapping an object/array/tuple,
    # traverse non-null branch(es) when data is a container.
    if isinstance(data, (dict, list)):
        for comb_key in _COMBINATOR_KEYS:
            branches = schema.get(comb_key)
            if not isinstance(branches, list):
                continue
            _, non_null = _split_null_any_of(branches)
            cur_data = data
            changed_comb = False
            for branch in non_null:
                cur_data, branch_changed = _coerce_node_data(
                    cur_data,
                    branch,
                    root_schema,
                    is_required=is_required,
                    visited_refs=visited_refs,
                )
                if branch_changed:
                    changed_comb = True
            if changed_comb:
                return cur_data, True

    if isinstance(data, dict):
        return _coerce_dict_data(data, schema, root_schema)

    if isinstance(data, list):
        return _coerce_list_data(data, schema, root_schema)

    return data, False


def coerce_jsonform_data(raw_json: str | bytes, raw_schema: dict[str, ty.Any]) -> str | bytes:
    """Coerce empty strings ('') emitted by django-jsonform for blank nullable fields into None."""
    try:
        parsed = json.loads(raw_json)
    except (ValueError, TypeError):
        return raw_json

    schema = _dereference_root_schema(raw_schema)
    coerced, changed = _coerce_node_data(parsed, schema, raw_schema, is_required=True)
    if not changed:
        return raw_json
    dumped = json.dumps(coerced)
    return dumped.encode() if isinstance(raw_json, bytes) else dumped
