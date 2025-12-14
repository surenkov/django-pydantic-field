import typing as ty
from types import SimpleNamespace

import pytest
from django.urls import path
from rest_framework import generics, serializers, views
from rest_framework.decorators import api_view, parser_classes, renderer_classes, schema
from rest_framework.response import Response

from tests.conftest import InnerSchema
from tests.test_app.models import SampleModel

rest_framework = pytest.importorskip("django_pydantic_field.v2.rest_framework")


class SampleSerializer(serializers.Serializer):
    field = rest_framework.SchemaField(schema=ty.List[InnerSchema])


class SampleModelSerializer(serializers.ModelSerializer):
    sample_field = rest_framework.SchemaField(schema=InnerSchema)
    sample_list = rest_framework.SchemaField(schema=ty.List[InnerSchema])
    sample_seq = rest_framework.SchemaField(schema=ty.List[InnerSchema], default=list)

    class Meta:
        model = SampleModel
        fields = "sample_field", "sample_list", "sample_seq"


class ClassBasedView(views.APIView):
    parser_classes = [rest_framework.SchemaParser[InnerSchema]]
    renderer_classes = [rest_framework.SchemaRenderer[ty.List[InnerSchema]]]

    def post(self, request, *args, **kwargs):
        assert isinstance(request.data, InnerSchema)
        return Response([request.data])


class ClassBasedViewWithSerializer(generics.RetrieveUpdateAPIView):
    serializer_class = SampleSerializer


class ClassBasedViewWithModel(generics.ListCreateAPIView):
    queryset = SampleModel.objects.all()
    serializer_class = SampleModelSerializer


class ClassBasedViewWithSchemaContext(ClassBasedView):
    parser_classes = [rest_framework.SchemaParser]
    renderer_classes = [rest_framework.SchemaRenderer]

    def get_renderer_context(self):
        ctx = super().get_renderer_context()
        return dict(ctx, renderer_schema=ty.List[InnerSchema])

    def get_parser_context(self, http_request):
        ctx = super().get_parser_context(http_request)
        return dict(ctx, parser_schema=InnerSchema)


@api_view(["GET", "POST"])
@parser_classes([rest_framework.SchemaParser[InnerSchema]])
@renderer_classes([rest_framework.SchemaRenderer[ty.List[InnerSchema]]])
def sample_view(request):
    assert isinstance(request.data, InnerSchema)
    return Response([request.data])


def create_views_urlconf(schema_view_inspector):
    @api_view(["GET", "POST"])
    @schema(schema_view_inspector())
    @parser_classes([rest_framework.SchemaParser[InnerSchema]])
    @renderer_classes([rest_framework.SchemaRenderer[ty.List[InnerSchema]]])
    def sample_view(request):
        assert isinstance(request.data, InnerSchema)
        return Response([request.data])

    class ClassBasedViewWithSerializer(generics.RetrieveUpdateAPIView):
        serializer_class = SampleSerializer
        schema = schema_view_inspector()

    return SimpleNamespace(
        urlpatterns=[
            path("/func", sample_view),
            path("/class", ClassBasedViewWithSerializer.as_view()),
        ],
    )
