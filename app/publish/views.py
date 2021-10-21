from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from shared_models.models import Course, Section, Product, CourseProvider, CourseSharingContract
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

from django_scopes import scopes_disabled


# class PublishViewSet(viewsets.ModelViewSet):
#     model = Product
#     serializer_class = ProductSerializer
#     # permission_classes = (IsAuthenticated, )
#     permission_classes = (HasStoreAPIKey, )
#     http_method_names = ['get', 'head', 'post', 'patch', 'update', 'delete']

#     def get_queryset(self):
#         fields = self.request.GET.copy()
#         try:
#             fields.pop('limit')
#             fields.pop('page')
#         except KeyError:
#             pass

#         queryset = self.model.objects.filter(**fields.dict())

#         # always filter by current users store so that one can not access
#         # someone elses stuff
#         return queryset.filter(store=self.request.store)

#     def retrieve(self, request, *args, **kwargs):
#         product = self.get_object()
#         serializer = self.serializer_class(product)
#         return Response(serializer.data, status=HTTP_200_OK)

#     def list(self, request, *args, **kwargs):
#         queryset = self.get_queryset()
#         serializer = self.serializer_class(queryset, many=True)
#         return Response(serializer.data, status=HTTP_200_OK)

#     def create(self, request, *args, **kwargs):
#         data = request.data.copy()
#         data['store'] = str(request.store.id)
#         serializer = self.serializer_class(data=data)
#         if serializer.is_valid(raise_exception=True):
#             serializer.save()
#         return Response(serializer.data, status=HTTP_201_CREATED)

#     def update(self, request, *args, **kwargs):
#         instance = self.get_object()
#         serializer = self.serializer_class(instance, data=request.data, partial=True)

#         if serializer.is_valid(raise_exception=True):
#             self.perform_update(serializer)
#         return Response(serializer.data)

#     def destroy(self, request, *args, **kwargs):
#         instance = self.get_object()
#         self.perform_destroy(instance)
#         return Response(status=HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([HasStoreAPIKey])
def publish(request):
    # prepare the data for mongodb
    payload = request.data.copy()

    action = payload['action']
    request_data = payload['data']

    if action == 'course':

        contract = CourseSharingContract.objects.filter(store=request.store, is_active=True).first()
        course_provider = contract.course_provider

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
        course_model = CourseModel.with_deleted_objects(external_id=request_data['external_id'], provider=request_data['provider'])
        raw_query = {'$set': request_data}
        # import ipdb; ipdb.set_trace()
        result = course_model.update_one(__raw__=raw_query, upsert=True, full_result=True)

        # course save in postgres
        request_data['content_db_reference'] = str(result.upserted_id)

        with scopes_disabled():

            try:
                course = Course.objects.get(slug=request_data['slug'])
            except Course.DoesNotExist:
                course_serializer = CourseSerializer(data=request_data)
            else:
                course_serializer = CourseSerializer(course=course, data=request_data)

            with scopes_disabled():
                course_serializer.is_valid(raise_exception=True)

            course_serializer.save()

        return Response({'message': 'action performed successfully'}, status=HTTP_201_CREATED)

    return Response({'message': 'invalid action name'}, status=HTTP_200_OK)

#     if action == 'section':
#         with scopes_disabled():
#             course = get_object_or_404(Course, id=request.data['course'])

#         course_model = CourseModel.objects.get(id=course.content_db_reference)

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

#         section_data = request.data.copy()

#         data = {
#             'code': section_data.pop('name', ''),
#             'course_fee': {'amount': section_data.pop('fee', ''), 'currency': 'USD'},
#             'num_seats': section_data.pop('seat_capacity', ''),
#             'available_seats': section_data.pop('available_seat', ''),
#             'execution_mode': section_data.pop('execution_mode', ''),
#             'is_active': section_data.pop('is_active', True),
#             'description': section_data.pop('description', ''),
#             'registration_url': section_data.pop('registration_url', ''),
#             'details_url': section_data.pop('details_url', None),
#             'start_date': section_data.pop('start_date', None),
#             'end_date': section_data.pop('end_date', None),
#             'registration_deadline': section_data.pop('registration_deadline', ''),
#             'credit_hours': section_data.pop('credit_hours', ''),
#             'ceu_hours': section_data.pop('ceu_hours', ''),
#             'clock_hours': section_data.pop('clock_hours', 0.0),
#             'load_hours': section_data.pop('load_hours', 0.0),
#         }

#         serializer_mongo = CheckSectionModelValidationSerializer(data=data)
#         with scopes_disabled():
#             serializer_mongo.is_valid(raise_exception=True)

#         request_data['content_db_reference'] = course.content_db_reference
#         serializer = SectionSerializer(data=request_data)
#         with scopes_disabled():
#             serializer.is_valid(raise_exception=True)
#         # use serializer.save() which returns a created object and handle exception manually
#         serializer.save()

#         # Add instructors in section
#         data = self.add_instructors_in_section(data, request_data)

#         course_model.sections.append(SectionModel(**data))
#         course_model.save()
#         return Response({'message': 'action performed successfully'}, status=HTTP_201_CREATED)



# # def rename_file(file_object, image_name):
# #     def getsize(f):
# #         f.seek(0)
# #         f.read()
# #         s = f.tell()
# #         f.seek(0)
# #         return s

# #     image_name = image_name.strip()
# #     content_type, charset = mimetypes.guess_type(image_name)
# #     size = getsize(file_object)
# #     new_file_name = str(uuid.uuid4()) + '.' + str(content_type).split('/')[-1]
# #     return InMemoryUploadedFile(
# #         file=file_object,
# #         name=new_file_name,
# #         field_name=None,
# #         content_type=content_type,
# #         charset=charset,
# #         size=size
# #     )
