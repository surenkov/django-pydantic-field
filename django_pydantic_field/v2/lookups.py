from __future__ import annotations

import typing as ty

from django.db.models.expressions import BaseExpression, Col
from django.db.models.lookups import Transform

if ty.TYPE_CHECKING:
    ExprT = ty.TypeVar("ExprT", bound=BaseExpression)


class SchemaKeyTransformAdapter:
    """An adapter class that modifies the key transformation behavior for schema fields.

    This class acts as an adapter, altering how key transformations are performed on schema fields.
    It circumvents the usual adaptation process for `PydanticSchemaField` objects,
    instead opting to use the `JSONField`'s own transformation methods.

    The goal is to utilize the lookup transformation features provided by the `JSONField.encoder` class.
    With the current limitations in Pydantic, it's not feasible to conduct partial value adaptations.

    While this approach is not ideal for QuerySet lookups,
    it allows `JSONField.encoder` (which defaults to `DjangoJSONEncoder`) to perform essential transformations.
    """

    def __init__(self, transform: type[Transform], lookup_name: str):
        self.transform = transform
        self.lookup_name = lookup_name

    def __call__(self, col: Col | None = None, *args, **kwargs) -> Transform | None:
        """All transforms should bypass the SchemaField's adaptaion with `get_prep_value`,
        and routed to JSONField's `get_prep_value` for further processing."""
        if isinstance(col, BaseExpression):
            col = self._get_prep_expression(col)
        return self.transform(col, *args, **kwargs)

    def _get_prep_expression(self, expr: ExprT) -> ExprT:
        from .fields import PydanticSchemaField

        if isinstance(expr.output_field, PydanticSchemaField):
            expr = expr.copy()
            expr.output_field = super(PydanticSchemaField, expr.output_field)  # type: ignore
        return expr
