from rest_framework.response import Response
from rest_framework import viewsets
from shared_models.models import Product

from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT
)

from publish.serializers import ProductSerializer
from publish.permissions import HasStoreAPIKey


class PublishViewSet(viewsets.ModelViewSet):
    model = Product
    serializer_class = ProductSerializer
    # permission_classes = (IsAuthenticated, )
    permission_classes = (HasStoreAPIKey, )
    http_method_names = ['get', 'head', 'post', 'patch', 'update', 'delete']

    def get_queryset(self):
        fields = self.request.GET.copy()
        try:
            fields.pop('limit')
            fields.pop('page')
        except KeyError:
            pass

        queryset = self.model.objects.filter(**fields.dict())

        # always filter by current users store so that one can not access
        # someone elses stuff
        return queryset.filter(store=self.request.store)

    def retrieve(self, request, *args, **kwargs):
        product = self.get_object()
        serializer = self.serializer_class(product)
        return Response(serializer.data, status=HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data, status=HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        data['store'] = str(request.store.id)
        serializer = self.serializer_class(data=data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
        return Response(serializer.data, status=HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.serializer_class(instance, data=request.data, partial=True)

        if serializer.is_valid(raise_exception=True):
            self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=HTTP_204_NO_CONTENT)
