from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from bson import ObjectId
from mongoengine import get_db

from shared_models.models import Course, Section, CourseSharingContract, StoreCourse, Product, StoreCourseSection
from models.courseprovider.course_provider import CourseProvider as CourseProviderModel
from models.courseprovider.provider_site import CourseProviderSite as CourseProviderSiteModel
from models.courseprovider.instructor import Instructor as InstructorModel
from models.course.course import Course as CourseModel
from datetime import datetime

from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
)

from rest_framework.decorators import api_view, permission_classes
from publish.permissions import HasCourseProviderAPIKey
from django_scopes import scopes_disabled

from publish.serializers import CourseSerializer, SectionSerializer
from campuslibs.loggers.mongo import save_to_mongo


def get_datetime_obj(date_str, time_str=None):
    if date_str is None:
        return None

    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    if time_str is None:
        time_str = '00:00:00'
    time = datetime.strptime(time_str, '%H:%M:%S').time()
    datetime_obj = datetime.combine(date, time)
    return datetime_obj


def upsert_mongo_doc(collection=None, query=None, data=None):
    db = get_db()
    coll = db[collection]
    doc = coll.find_one(query)
    if doc is None:
        result = coll.insert_one(data)
        return result.inserted_id
    else:
        if collection not in ['course_provider_site', 'instructor']:
            result = db.course.update_one(query, {'$set': data}, upsert=True)
        return doc['_id']
    return None


def prepare_course_postgres(data, course_provider, course_provider_model):
    course_data = {
        'course_provider': str(course_provider.id),
        'title': data.get('crs_title'),
        'slug': data.get('formatted_crs_cde'),
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
        'external_id': data.get('catalog_appid'),
        # 'external_url': data.get('external_url'),
        # 'external_version_id': data.get('external_version_id'),
        'code': data.get('crs_cde'),
        'title': data.get('crs_title'),
        'slug': data.get('formatted_crs_cde'),
        'description': data.get('catalog_text'),
        # 'learning_outcome': data.get('learning_outcome'),
        # 'summary': data.get('summary'),
        # 'syllabus_url': data.get('syllabus_url'),
        # 'level': level,
        # 'inquiry_url': data.get('inquiry_url')
        'sections': prepare_section_mongo(data['sections'], course_provider_model)
    }
    return course_model_data


def get_execution_site(data, course_provider_model):
    query = {'provider': course_provider_model.id, 'name': data}
    data = {
        '_cls': 'CourseProviderSite',
        'provider': course_provider_model.id,
        'name': data,
        'code': data
    }
    doc_id = upsert_mongo_doc(collection='course_provider_site', query=query, data=data)
    return doc_id


def get_instructors(data, course_provider_model):
    instructors = []
    for item in data:
        query = {'provider': course_provider_model.id, 'external_id': item.get('section_instructor_appid', '')}
        data = {
            '_cls': 'Instructor',
            'provider': course_provider_model.id,
            'name': item.get('first_name', '') + ' ' + item.get('middle_name', '') + ' ' + item.get('last_name', ''),
            'external_id': item.get('section_instructor_appid', ''),
            'profile_urls': item.get('profile_urls', {}),
            'image': item.get('image', {}),
            'short_bio': item.get('short_bio', ''),
            'detail_bio': item.get('detail_bio', ''),
        }
        instructors.append(upsert_mongo_doc(collection='instructor', query=query, data=data))
    return instructors


def get_schedules(data):
    schedules = []
    for item in data:
        schedules.append({
            'section_type': item.get('meeting_cde', 'LEC'),
            'external_version_id': item.get('external_version_id', ''),
            'name': item.get('name', ''),
            'description': item.get('description', ''),
            'start_at': get_datetime_obj(item.get('begin_dte'), item.get('begin_tim')),
            'end_at': get_datetime_obj(item.get('end_dte'), item.get('end_tim')),
            'building_name': item.get('building_description', ''),
            'building_code': item.get('bldg_cde', ''),
            'room_name': item.get('room_description', ''),
        })
    return schedules


def prepare_section_mongo(data, course_provider_model):
    section_data = []
    for item in data:
        section_data.append({
            'code': item.get('section_appid'),
            'external_version_id': item.get('external_version_id'),
            'description': item.get('description'),
            'registration_url': item.get('registration_url'),
            'details_url': item.get('details_url'),
            'start_date': get_datetime_obj(item.get('first_begin_dte')),
            'end_date': get_datetime_obj(item.get('last_end_dte')),
            'num_seats': item.get('open_seats'),
            'available_seats': item.get('open_seats'),
            'is_active': item.get('is_active'),
            'execution_mode': item.get('execution_mode'),
            'execution_site': get_execution_site(item.get('execution_site'), course_provider_model),
            'registration_deadline': get_datetime_obj(item.get('final_enrollment_dte')),
            'instructors': get_instructors(item.get('instructors', []), course_provider_model),
            'course_fee': {'amount': item.get('course_fees', 0.00), 'currency': 'usd'},
            'credit_hours': item.get('credit_hrs'),
            'ceu_hours': item.get('ceu_hours'),
            'clock_hours': item.get('crs_clock_hrs'),
            'load_hours': item.get('load_hours'),
            'schedules': get_schedules(item.get('schedules', []))
        })
    return section_data


def prepare_section_postgres(data, course, course_model):
    section_data = {
        'course': course.id,
        'name': data.get('section_appid'),
        'fee': data.get('course_fees'),
        'seat_capacity': data.get('open_seats'),
        'available_seat': data.get('open_seats'),
        'execution_mode': data.get('execution_mode', 'self-paced'),
        'registration_deadline': get_datetime_obj(data.get('final_enrollment_dte')),
        'content_db_reference': str(course_model.id),
        'is_active': data.get('is_active', False),
        'start_date': get_datetime_obj(data.get('first_begin_dte')),
        'end_date': get_datetime_obj(data.get('last_end_dte')),
        'execution_site': data.get('execution_site'),
    }
    return section_data


@api_view(['POST'])
@permission_classes([HasCourseProviderAPIKey])
def publish(request):
    payload = request.data.copy()

    # first of all, save everything to mongodb
    mongo_data = {'payload': payload, 'status': 'pending'}
    save_to_mongo(data=mongo_data, collection='partner_data')

    action = payload['action']
    request_data = payload['data']

    contracts = CourseSharingContract.objects.filter(course_provider=request.course_provider, is_active=True)

    # if there is no section data, nothing is gonna make sense so

    if len(request_data['sections']) == 0:
        return Response({'message': 'section data is required'}, status=HTTP_200_OK)

    # in this query, we add the course provider although we have the id of the course
    # this is because, we want to make sure we don't change any course to which the
    # user has no access. since course provider is determined from the secured key
    # provided as authorization header, user can not fake this.

    try:
        course_provider_model = CourseProviderModel.objects.get(id=request.course_provider.content_db_reference)
    except CourseProviderModel.DoesNotExist:
        return Response({'message': 'course provider model not found'})

    if action == 'j1-course':
        course_model_data = prepare_course_mongo(request_data, request.course_provider, course_provider_model)
        course_data = prepare_course_postgres(request_data, request.course_provider, course_provider_model)

        query = {'external_id': course_model_data['external_id'], 'provider': course_model_data['provider']}
        doc_id = upsert_mongo_doc(collection='course', query=query, data=course_model_data)
        course_data['content_db_reference'] = str(doc_id)

        with scopes_disabled():
            try:
                course = Course.objects.get(slug=course_data['slug'])
            except Course.DoesNotExist:
                course_serializer = CourseSerializer(data=course_data)
            else:
                course_serializer = CourseSerializer(course, data=course_data)

            if course_serializer.is_valid(raise_exception=True):
                course = course_serializer.save()

            course_model = CourseModel.objects.get(id=course.content_db_reference)

            # create StoreCourse
            for contract in contracts:
                store_course, created = StoreCourse.objects.get_or_create(
                    course=course,
                    store=contract.store,
                    defaults={'is_published': False, 'enrollment_ready': True}
                )

                for section in request_data['sections']:
                    section_data = prepare_section_postgres(section, course, course_model)
                    try:
                        section = course.sections.get(name=section_data['name'])
                    except Section.DoesNotExist:
                        serializer = SectionSerializer(data=section_data)
                    else:
                        serializer = SectionSerializer(section, data=section_data)

                    if serializer.is_valid(raise_exception=True):
                        section = serializer.save()

                    # create product
                    product, created = Product.objects.get_or_create(
                        store=contract.store,
                        external_id=section.name,  # mandatory field. instead of course external id, it must be a unique filed in section.
                                                   # because section is a product. course is not.
                        product_type='section',
                        defaults={
                            'title': course.title,
                            'tax_code': 'ST080031',
                            'fee': section.fee,
                        }
                    )
                    # create store course section
                    StoreCourseSection.objects.get_or_create(
                        store_course=store_course,
                        section=section,
                        is_published=False,
                        product=product
                    )

        return Response({'message': 'action performed successfully'}, status=HTTP_201_CREATED)

    else:
        return Response({'message': 'invalid action name'}, status=HTTP_200_OK)

    return Response({'message': 'action performed successfully'}, status=HTTP_201_CREATED)
