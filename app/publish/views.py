from rest_framework.response import Response
from rest_framework import viewsets
from django.shortcuts import get_object_or_404

from shared_models.models import Course, Section, Product, CourseProvider
from models.course.course import Course as CourseModel
from models.course.section import Section as SectionModel

from rest_framework import serializers
from datetime import datetime

from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
)

from rest_framework.decorators import api_view, permission_classes

from publish.serializers import (
    ProductSerializer,
    SectionSerializer,
    CheckSectionModelValidationSerializer,
    CourseSerializer,
    CourseModelSerializer
)

from publish.permissions import HasStoreAPIKey

from django_scopes import scope, scopes_disabled

from django.core.files.uploadedfile import InMemoryUploadedFile
import mimetypes
import uuid

from decouple import config


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


@api_view(['POST'])
@permission_classes([HasStoreAPIKey])
def publish(request):
    # prepare the data for mongodb
    request_data = request.data.copy()

    if 'provider' in request_data:
        course_provider = get_object_or_404(CourseProvider, pk=str(request_data['provider']))
        request_data['provider'] = course_provider.content_db_reference
        request_data['course_provider'] = course_provider.id

    if 'level' in request_data:
        if request_data['level'] == 'unspecified':
            request_data['level'] = ''

    if 'course_image_uri' in request_data and request_data['course_image_uri']:
        del request_data['course_image_uri']
        # S3_IMAGE_DIR = config('S3_IMAGE_DIR', '')
        # request_data['course_image_uri'] = rename_file(request_data['course_image_uri'], request_data['course_image_uri'].name)
        # request_data['image'] = {'original': S3_IMAGE_DIR + '/' + request_data['course_image_uri'].name}

    # preparation for mongodb done

    request_data['from_importer'] = False

    # course save in mongodb
    course_model_serializer = CourseModelSerializer(data=request_data)

    # import ipdb; ipdb.set_trace()

    with scopes_disabled():
        course_model_serializer.is_valid(raise_exception=True)
    course_model_serializer.save()

    # course save in postgres
    request_data['content_db_reference'] = course_model_serializer.data['id']
    course_serializer = CourseSerializer(data=request_data)
    with scopes_disabled():
        course_serializer.is_valid(raise_exception=True)
    course_serializer.save()

    data = course_model_serializer.data

    data['course_image_uri'] = course_serializer['course_image_uri']
    data['content_ready'] = course_serializer['content_ready']
    data['provider'] = {'id': course_serializer['course_provider']['id'], 'name': course_serializer['course_provider']['name']}
    data['id'] = course_serializer['id']
    return Response(data, status=HTTP_201_CREATED)

# class SectionViewSet(
#     viewsets.ModelViewSet, SectionMixin
# ):
#     model = Section
#     serializer_class = SectionSerializer
#     http_method_names = ['head', 'patch', 'update']

#     def get_queryset(self):
#         fields = self.request.GET.copy()
#         try:
#             fields.pop('limit')
#             fields.pop('page')
#         except KeyError:
#             pass

#         return self.get_scoped_queryset(fields=fields)

#     def create(self, request, *args, **kwargs):
#         '''
#         Creates section in postgres first. Then appends the section data in mongodb course sections.
#         In mongodb section is not a individual document rather it is embedded in course.
#         '''
#         # handle 404 response manually
#         with scope(**self.get_user_scope()):
#             course = get_object_or_404(Course, id=request.data['course'])
#         course_model = self.get_mongo_obj_or_404(
#             CourseModel, id=course.content_db_reference
#         )

#         request_data = request.data.copy()

#         if int(request_data['available_seat']) > int(request_data['seat_capacity']):
#             raise serializers.ValidationError(
#                 {
#                     'available_seat': 'Available seat can not be greater than seat capacity'
#                 }
#             )

#         start_date = None
#         end_date = None
#         registration_deadline = None

#         if 'start_date' in request_data:
#             start_date = datetime.fromisoformat(request_data['start_date'])

#         if 'end_date' in request_data:
#             end_date = datetime.fromisoformat(request_data['end_date'])

#         if 'registration_deadline' in request_data:
#             registration_deadline = datetime.fromisoformat(
#                 request_data['registration_deadline']
#             )

#         if start_date and end_date and start_date > end_date:
#             raise serializers.ValidationError(
#                 {'start_date': 'Start date must not be in the future from end date'}
#             )

#         if registration_deadline and end_date and registration_deadline > end_date:
#             raise serializers.ValidationError(
#                 {
#                     'registration_deadline': 'Final Enrollment Date must not be after end date'
#                 }
#             )

#         data = self.prepare_embedded_section(request.data.copy())

#         serializer_mongo = CheckSectionModelValidationSerializer(data=data)
#         with scopes_disabled():
#             serializer_mongo.is_valid(raise_exception=True)

#         request_data['content_db_reference'] = course.content_db_reference
#         serializer = SectionSerializer(data=request_data, context={'request': request})
#         with scopes_disabled():
#             serializer.is_valid(raise_exception=True)
#         # use serializer.save() which returns a created object and handle exception manually
#         self.perform_create(serializer)

#         # Add instructors in section
#         data = self.add_instructors_in_section(data, request_data)

#         course_model.sections.append(SectionModel(**data))
#         course_model.save()
#         data = self.get_section_detail(serializer.data['id'])
#         return Response(self.object_decorator(data), status=HTTP_201_CREATED)

#     def update(self, request, *args, **kwargs):
#         section = self.get_object()
#         course_model = self.get_mongo_obj_or_404(
#             CourseModel, id=section.content_db_reference
#         )
#         section_previous_name = section.name

#         request_data = request.data.copy()

#         if int(request_data['available_seat']) > int(request_data['seat_capacity']):
#             raise serializers.ValidationError(
#                 {
#                     'available_seat': 'Available seat can not be greater than seat capacity'
#                 }
#             )

#         start_date = None
#         end_date = None
#         registration_deadline = None

#         # these incoming dates have Z suffix which is for zulu or to denote UTC timezone. bellow is a hack to fix this.
#         # probably a better way to be to use dateutil or arrow

#         if 'start_date' in request_data:
#             start_date = datetime.fromisoformat(
#                 request_data['start_date'].replace('Z', '+00:00')
#             )

#         if 'end_date' in request_data:
#             end_date = datetime.fromisoformat(
#                 request_data['end_date'].replace('Z', '+00:00')
#             )

#         if 'registration_deadline' in request_data:
#             registration_deadline = datetime.fromisoformat(
#                 request_data['registration_deadline'].replace('Z', '+00:00')
#             )

#         if start_date and end_date and start_date > end_date:
#             raise serializers.ValidationError(
#                 {'start_date': 'Start date must not be in the future from end date'}
#             )

#         if registration_deadline and end_date and registration_deadline > end_date:
#             raise serializers.ValidationError(
#                 {
#                     'registration_deadline': 'Final Enrollment Date must not be after end date'
#                 }
#             )

#         data = self.prepare_embedded_section(request.data.copy())

#         serializer_mongo = CheckSectionModelValidationSerializer(data=data)
#         with scopes_disabled():
#             serializer_mongo.is_valid(raise_exception=True)

#         serializer = SectionSerializer(section, data=request_data, partial=True)
#         # handle exceptions manually
#         with scopes_disabled():
#             serializer.is_valid(raise_exception=True)
#         # use serializer.partial_update() or serializer.save() which returns a created object and handle exception manually
#         self.perform_update(serializer)

#         serializer_mongo = CheckSectionModelValidationSerializer(data=data)
#         with scopes_disabled():
#             serializer_mongo.is_valid(raise_exception=True)
#         # handle exceptions here and return appropriate erros messages

#         # Add instructors in section
#         data = self.add_instructors_in_section(data, request_data)

#         CourseModel.objects(
#             id=course_model.id, sections__code=section_previous_name
#         ).update_one(set__sections__S=SectionModel(**data))
#         data = self.get_section_detail(serializer.data['id'])
#         return Response(self.object_decorator(data))


def rename_file(file_object, image_name):
    def getsize(f):
        f.seek(0)
        f.read()
        s = f.tell()
        f.seek(0)
        return s

    image_name = image_name.strip()
    content_type, charset = mimetypes.guess_type(image_name)
    size = getsize(file_object)
    new_file_name = str(uuid.uuid4()) + '.' + str(content_type).split('/')[-1]
    return InMemoryUploadedFile(
        file=file_object,
        name=new_file_name,
        field_name=None,
        content_type=content_type,
        charset=charset,
        size=size
    )
