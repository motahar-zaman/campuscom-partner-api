from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from bson import ObjectId
from mongoengine import get_db

from shared_models.models import Course, Section, Product, CourseProvider, CourseSharingContract
from models.courseprovider.course_provider import CourseProvider as CourseProviderModel
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


def prepare_course_postgres(data, course_provider, course_provider_model):
    course_data = {
        'course_provider': str(course_provider.id),
        'title': data.get('title'),
        'slug': data.get('slug'),
        'course_image_uri': data.get('course_image_uri', None),
        'content_ready': data.get('content_ready', False),
        'external_image_url': data.get('external_image_url', None),
    }
    return course_data


def prepare_course_mongo(data, course_provider, course_provider_model):
    level = data.get('level', None)
    if level not in ['beginner', 'intermediate', 'advanced']:
        level = ''

    course_model_data = {
        '_cls': 'Course',
        'provider': ObjectId(course_provider.content_db_reference),
        'from_importer': False,
        'external_id': data.get('external_id'),
        'external_url': data.get('external_url'),
        'external_version_id': data.get('external_version_id'),
        'code': data.get('code'),
        'title': data.get('title'),
        'slug': data.get('slug'),
        'description': data.get('description'),
        'learning_outcome': data.get('learning_outcome'),
        # 'image': {},
        # 'default_image': {},
        'summary': data.get('summary'),
        'syllabus_url': data.get('syllabus_url'),
        'level': level,
        'inquiry_url': data.get('inquiry_url'),
        # 'overrides': data.get('overrides'),
        # 'sections': data.get('sections'),
        # 'programs': data.get('programs'),
        # 'required_courses': data.get('required_courses'),
        # 'recommended_courses': data.get('recommended_courses'),
        # 'subjects': data.get('subjects'),
        # 'keywords': data.get('keywords'),
        # 'careers': data.get('careers'),
        # 'skills': data.get('skills'),
    }
    return course_model_data


def get_execution_site(data, course_provider_model):
    return {
        'provider': course_provider_model.id,
        'name': data.get('name', ''),
        'code': data.get('code', ''),
    }


def get_instructors(data, course_provider_model):
    instructors = []
    for item in data:
        instructors.append({
            'provider': course_provider_model.id,
            'name': item.get('name', ''),
            'external_id': item.get('external_id', ''),
            'profile_urls': item.get('profile_urls', ''),
            'image': item.get('image', {}),
            'short_bio': item.get('short_bio', ''),
            'detail_bio': item.get('detail_bio', ''),
        })
    return instructors


def get_schedules(data):
    schedules = []
    for item in data:
        schedules.append({
            'section_type': item.get('section_type', ''),
            'external_version_id': item.get('external_version_id', ''),
            'name': item.get('name', ''),
            'description': item.get('description', ''),
            'start_at': datetime.fromisoformat(item.get('start_at')),
            'end_at': datetime.fromisoformat(item.get('end_at')),
            'building_name': item.get('building_name', ''),
            'building_code': item.get('building_code', ''),
            'room_name': item.get('room_name', ''),
        })
    return schedules


def prepare_section_mongo(data, course_provider_model):
    section_model_data = {
        'code': data.get('code'),
        'external_version_id': data.get('external_version_id'),
        'description': data.get('description'),
        'registration_url': data.get('registration_url'),
        'details_url': data.get('details_url'),
        'start_date': datetime.fromisoformat(data.get('start_date')),
        'end_date': datetime.fromisoformat(data.get('end_date')),
        'num_seats': data.get('seat_capacity'),
        'available_seats': data.get('available_seats'),
        'is_active': data.get('is_active'),
        'execution_mode': data.get('execution_mode'),
        'execution_site': get_execution_site(data.get('execution_site', {}), course_provider_model),
        'registration_deadline': datetime.fromisoformat(data.get('registration_deadline')),
        'instructors': get_instructors(data.get('instructors', []), course_provider_model),
        'course_fee': {'amount': data.get('fee', 0.00), 'currency': 'usd'},
        'credit_hours': data.get('credit_hours'),
        'ceu_hours': data.get('ceu_hours'),
        'clock_hours': data.get('clock_hours'),
        'load_hours': data.get('load_hours'),
        'schedules': get_schedules(data.get('schedules', [])),
        # 'registration_form_data': data.get('registration_form_data'),
    }
    return section_model_data


def prepare_section_postgres(data, course, course_model):
    section_data = {
        'course': course.id,
        'name': data.get('code'),
        'fee': data.get('fee'),
        'seat_capacity': data.get('seat_capacity'),
        'available_seat': data.get('available_seat'),
        'execution_mode': data.get('execution_mode'),
        'registration_deadline': datetime.fromisoformat(data.get('registration_deadline')),
        'content_db_reference': str(course_model.id),
        'is_active': data.get('is_active', False),
        'start_date': datetime.fromisoformat(data.get('start_date')),
        'end_date': datetime.fromisoformat(data.get('end_date')),
        'execution_site': data.get('execution_site'),
    }
    return section_data


@api_view(['POST'])
@permission_classes([HasStoreAPIKey])
def publish(request):
    # prepare the data for mongodb
    payload = request.data.copy()

    action = payload['action']
    request_data = payload['data']

    contract = CourseSharingContract.objects.filter(store=request.store, is_active=True).first()
    course_provider = contract.course_provider

    # in this query, we add the course provider although we have the id of the course
    # this is because, we want to make sure we don't change any course to which the
    # user has no access. since course provider is determined from the secured key
    # provided as authorization header, user can not fake this.

    try:
        course_provider_model = CourseProviderModel.objects.get(id=course_provider.content_db_reference)
    except CourseProviderModel.DoesNotExist:
        return Response({'message': 'course provider model not found'})

    if action == 'course':
        course_model_data = prepare_course_mongo(request_data, course_provider, course_provider_model)
        course_data = prepare_course_postgres(request_data, course_provider, course_provider_model)

        # course save in mongodb

        # try:
        #     course_model = CourseModel.with_deleted_objects.get(
        #         external_id=course_model_data['external_id'],
        #         provider=course_model_data['provider']
        #     )
        # except CourseModel.DoesNotExist:
        #     db = get_db()
        #     result = db.course.insert_one(course_model_data)
        #     course_data['content_db_reference'] = str(result.inserted_id)
        # else:
        #     course_model.update(__raw__={'$set': course_model_data}, upsert=True)
        #     course_data['content_db_reference'] = str(course_model.id)
        db = get_db()
        query = {'external_id': course_model_data['external_id'], 'provider': course_model_data['provider']}
        doc = db.course.find_one(query)

        if doc is None:
            result = db.course.insert_one(course_model_data)
            course_data['content_db_reference'] = str(result.inserted_id)
        else:
            result = db.course.update_one(query, {'$set': course_model_data}, upsert=True)
            course_data['content_db_reference'] = str(doc['_id'])

        # save in postgres

        # if result.raw_result['updatedExisting']:
        #     course_data['content_db_reference'] = str(course_model.id)
        # else:
        #     course_data['content_db_reference'] = str(result.upserted_id)

        with scopes_disabled():
            try:
                course = Course.objects.get(slug=course_data['slug'])
            except Course.DoesNotExist:
                course_serializer = CourseSerializer(data=course_data)
            else:
                course_serializer = CourseSerializer(course, data=course_data)

            if course_serializer.is_valid(raise_exception=True):
                course_serializer.save()

        return Response({'message': 'action performed successfully'}, status=HTTP_201_CREATED)

    if action == 'section':

        try:
            course_model = CourseModel.objects.get(
                provider=course_provider_model,
                external_id=request_data['course_external_id']
            )
        except CourseModel.DoesNotExist:
            return Response({'message': 'course model not found'})

        with scopes_disabled():
            course = get_object_or_404(Course, course_provider__id=course_provider.id, content_db_reference=str(course_model.id))

        section_model_data = prepare_section_mongo(request_data, course_provider_model)
        course_model.update(add_to_set__sections=section_model_data)

        section_data = prepare_section_postgres(request_data, course, course_model)

        with scopes_disabled():
            try:
                section = course.sections.get(name=section_data['name'])
            except Section.DoesNotExist:
                serializer = SectionSerializer(data=section_data)
            else:
                serializer = SectionSerializer(section, data=section_data)

            if serializer.is_valid(raise_exception=True):
                serializer.save()

    else:
        return Response({'message': 'invalid action name'}, status=HTTP_200_OK)

    return Response({'message': 'action performed successfully'}, status=HTTP_201_CREATED)
