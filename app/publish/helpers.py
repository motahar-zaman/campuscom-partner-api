from bson import ObjectId
from mongoengine import get_db
from decimal import Decimal

from datetime import datetime

from json import JSONEncoder
from bson.objectid import ObjectId
from publish.serializers import CourseSerializer, SectionSerializer
from models.course.course import Course as CourseModel
from shared_models.models import Course, Section, CourseSharingContract, StoreCourse, Product, StoreCourseSection
from django_scopes import scopes_disabled
from django.db import transaction

import requests
from models.course.course import Course as CourseModel
from decouple import config


def get_schedules(data):
    schedules = []
    for item in data:
        schedules.append({
            'section_type': item.get('section_type', 'LEC'),
            'external_version_id': item.get('external_version_id', ''),
            'name': item.get('name', ''),
            'description': item.get('description', ''),
            'start_at': get_datetime_obj(item.get('start_at')),
            'end_at': get_datetime_obj(item.get('end_at')),
            'building_name': item.get('building_name', ''),
            'building_code': item.get('building_code', ''),
            'room_name': item.get('room_name', ''),
        })
    return schedules


def get_instructors(data, course_provider_model):
    instructors = []
    for item in data:
        query = {'provider': course_provider_model.id, 'external_id': item.get('external_id', '')}
        data = {
            '_cls': 'Instructor',
            'provider': course_provider_model.id,
            'name': item.get('name', ''),
            'external_id': item.get('external_id', ''),
            'profile_urls': item.get('profile_urls', {}),
            'image': item.get('image', {}),
            'short_bio': item.get('short_bio', ''),
            'detail_bio': item.get('detail_bio', ''),
        }
        instructors.append(upsert_mongo_doc(collection='instructor', query=query, data=data))
    return instructors


def prepare_section_mongo(data, course_provider_model):
    section_data = []
    for item in data:
        try:
            num_seats = int(item.get('num_seats', 0))
        except ValueError:
            num_seats = 0

        try:
            course_fee = float(item.get('course_fee', 0.00))
        except ValueError:
            course_fee = 0.00

        try:
            credit_hours = float(item.get('credit_hours', 0.00))
        except ValueError:
            credit_hours = 0.00
        try:
            ceu_hours = float(item.get('ceu_hours', 0.00))
        except ValueError:
            ceu_hours = 0.00
        try:
            clock_hours = float(item.get('clock_hours', 0.00))
        except ValueError:
            clock_hours = 0.00
        try:
            load_hours = float(item.get('load_hours', 0.00))
        except ValueError:
            load_hours = 0.00

        section_data.append({
            'code': item.get('code'),
            'external_version_id': item.get('external_version_id'),
            'external_id': item.get('code'),
            'description': item.get('description'),
            'registration_url': item.get('registration_url'),
            'details_url': item.get('details_url'),
            'start_date': get_datetime_obj(item.get('start_date')),
            'end_date': get_datetime_obj(item.get('end_date')),
            'num_seats': num_seats,
            'available_seats': item.get('available_seats'),
            'is_active': item.get('is_active'),
            'execution_mode': item.get('execution_mode'),
            'execution_site': get_execution_site(item.get('execution_site'), course_provider_model),
            'registration_deadline': get_datetime_obj(item.get('registration_deadline')),
            'instructors': get_instructors(item.get('instructors', []), course_provider_model),
            'course_fee': {'amount': course_fee, 'currency': 'usd'},
            'credit_hours': credit_hours,
            'ceu_hours': ceu_hours,
            'clock_hours': clock_hours,
            'load_hours': load_hours,
            'schedules': get_schedules(item.get('schedules', []))
        })
    return section_data


def prepare_course_mongo(data, course_provider, course_provider_model):
    level = data.get('level', None)
    if level not in ['beginner', 'intermediate', 'advanced']:
        level = ''

    course_model_data = {
        '_cls': 'Course',
        'provider': ObjectId(course_provider.content_db_reference),
        'from_importer': True,
        'external_id': data.get('external_id'),
        'code': data.get('code'),
        'title': data.get('title'),
        'slug': data.get('slug'),
        'description': data.get('description'),
        'sections': prepare_section_mongo(data.get('sections', []), course_provider_model)
    }
    return course_model_data


def get_datetime_obj(date_time_str):
    if date_time_str is None or date_time_str == '':
        return None

    try:
        date_str, time_str = date_time_str.split('T')
    except ValueError:
        date_str = date_time_str.strip()
        time_str = '00:00:00'

    if time_str == '':
        time_str = '00:00:00'

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
        # if collection == 'course':
        #     old_section_codes = [section['code'] for section in doc['sections']]
        #     new_section_codes = [section['code'] for section in data['sections']]
        #     sections = []

        #     for section in data['sections']:
        #         if section['code'] not in old_section_codes:
        #             # this is new
        #             sections.append(section)
        #         else:
        #             # this is present in the old sections. so has to update
        #             for old_section in doc['sections']:
        #                 if old_section['code'] == section['code']:
        #                     old_section.update(section)
        #                     sections.append(old_section)
        #     for section in doc['sections']:
        #         if section['code'] not in new_section_codes:
        #             # this will not be updated. will remain as is.
        #             sections.append(section)
        #     data['sections'] = sections
        if collection not in ['course_provider_site', 'instructor']:
            result = db.course.update_one(query, {'$set': data}, upsert=True)

        return doc['_id']
    return None


def prepare_course_postgres(data, course_provider, course_provider_model):
    course_data = {
        'course_provider': str(course_provider.id),
        'title': data.get('title'),
        'slug': data.get('slug'),
        'course_image_uri': data.get('course_image_uri', None),
        'external_image_url': data.get('external_image_url', None),
    }
    return course_data


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


def prepare_section_postgres(data, course, course_model):
    content_db_reference = ''
    if course_model:
        content_db_reference = str(course_model.id)
    section_data = {
        'course': course.id,
        'name': data.get('code'),
        'fee': Decimal(data.get('course_fee', '0.00')),
        'seat_capacity': data.get('num_seats'),
        'available_seat': data.get('num_seats'),
        'execution_mode': data.get('execution_mode', 'self-paced'),
        'registration_deadline': get_datetime_obj(data.get('registration_deadline')),
        'content_db_reference': content_db_reference,
        'is_active': data.get('is_active', False),
        'start_date': get_datetime_obj(data.get('start_date')),
        'end_date': get_datetime_obj(data.get('end_date')),
        'execution_site': data.get('execution_site'),
    }

    return section_data


def translate_data(data, mapping):
    translated = []
    for item in data:
        item_data = {}
        for key, value in mapping.items():
            if key == 'name':
                name = item.get('first_name', '') + ' ' + item.get('middle_name', '') + ' ' + item.get('last_name', '')
                ################################
                if name.isspace():
                    name = item.get('name', '')
                item_data[key] = name.replace('  ', ' ')  # replace two consecutive spaces with one
            elif key == 'section_type':
                item_data[key] = item.get('meeting_cde', 'LEC')
            elif key == 'start_at':
                item_data[key] = item.get('begin_dte', '') + 'T' + item.get('begin_tim', '')
            elif key == 'end_at':
                item_data[key] = item.get('end_dte', '') + 'T' + item.get('end_tim', '')
            elif key == 'instructors':
                item_data[key] = translate_data(item['instructors'], value)
            elif key == 'schedules':
                item_data[key] = translate_data(item.get('schedules', []), value)

            elif key == 'execution_mode':
                item_data[key] = item.get(value, 'self-paced')

            elif key == 'is_active':
                item_data[key] = item.get(value, False)

            else:
                try:
                    item_data[key] = item[value]
                except KeyError:
                    item_data[key] = ''
        translated.append(item_data)
    return translated


def transale_j1_data(request_data):
    mapping = {
        'external_id': 'catalog_appid',
        'code': 'crs_cde',
        'title': 'crs_title',
        'slug': 'formatted_crs_cde',
        'description': 'catalog_text',
        'sections': {
            'code': 'section_appid',
            'external_version_id': 'external_version_id',
            'description': 'description',
            'registration_url': 'registration_url',
            'details_url': 'details_url',
            'start_date': 'first_begin_dte',
            'end_date': 'last_end_dte',
            'num_seats': 'open_seats',
            'available_seats': 'open_seats',
            'is_active': 'is_active',
            'execution_mode': 'execution_mode',
            'execution_site': 'execution_site',
            'registration_deadline': 'final_enrollment_dte',
            'instructors': {
                'name': ['first_name', 'middle_name', 'last_name'],
                'external_id': 'section_instructor_appid',
                'profile_urls': 'profile_urls',
                'image': 'image',
                'short_bio': 'short_bio',
                'detail_bio': 'detail_bio'
            },
            'course_fee': 'course_fees',
            'credit_hours': 'credit_hrs',
            'ceu_hours': 'ceu_hours',
            'clock_hours': 'crs_clock_hrs',
            'load_hours': 'load_hours',
            'schedules': {
                'section_type': ['meeting_cde', 'LEC'],
                'external_version_id': 'external_version_id',
                'name': 'name',
                'description': 'description',
                'start_at': ['begin_dte', 'begin_tim'],
                'end_at': ['end_dte', 'end_tim'],
                'building_name': 'building_description',
                'building_code': 'bldg_cde',
                'room_name': 'room_description',
            }
        },
    }

    data = {}

    for key, value in mapping.items():
        if key == 'sections':
            data[key] = translate_data(request_data.get('sections', []), value)
        else:
            data[key] = request_data[value]
    return data


def get_data(collection, query):
    db = get_db()
    coll = db[collection]
    data = coll.find(query)

    return data


def j1_publish(request, request_data, contracts, course_provider_model):
    course_model_data = prepare_course_mongo(request_data, request.course_provider, course_provider_model)
    course_data = prepare_course_postgres(request_data, request.course_provider, course_provider_model)

    query = {'external_id': course_model_data['external_id'], 'provider': course_model_data['provider']}
    doc_id = upsert_mongo_doc(collection='course', query=query, data=course_model_data)
    course_data['content_db_reference'] = str(doc_id)
    with scopes_disabled():
        try:
            course = Course.objects.get(slug=course_data['slug'], course_provider=request.course_provider)
        except Course.DoesNotExist:
            course_serializer = CourseSerializer(data=course_data)
        else:
            course_serializer = CourseSerializer(course, data=course_data)
        if course_serializer.is_valid(raise_exception=True):
            course = course_serializer.save()
            course.active_status = True
            course.save()

        course_model = CourseModel.objects.get(id=course.content_db_reference)
        course_model._is_published = False
        course_model.save()

        # create StoreCourse
        for contract in contracts:
            store_course, created = StoreCourse.objects.get_or_create(
                course=course,
                store=contract.store,
                defaults={'enrollment_ready': True, 'is_published': False, 'is_featured': False}
            )

            for section_data in request_data.get('sections', []):
                section_data = prepare_section_postgres(section_data, course, course_model)
                try:
                    section = course.sections.get(name=section_data['name'])
                except Section.DoesNotExist:
                    serializer = SectionSerializer(data=section_data)
                else:
                    serializer = SectionSerializer(section, data=section_data)

                if serializer.is_valid(raise_exception=True):
                    section = serializer.save()
                    section.active_status = True
                    section.save()

                try:
                    store_course_section = StoreCourseSection.objects.get(store_course=store_course, section=section)
                except StoreCourseSection.DoesNotExist:
                    # create product
                    product = Product.objects.create(
                        store=contract.store,
                        external_id=course_model_data['external_id'],
                        product_type='section',
                        title=course.title,
                        tax_code='ST080031',
                        fee=section.fee,
                        minimum_fee=section.fee
                    )

                    StoreCourseSection.objects.get_or_create(
                        store_course=store_course,
                        section=section,
                        is_published=False,
                        product=product
                    )
                else:
                    product = store_course_section.product
                    product.store = contract.store
                    product.external_id = course_model_data['external_id']
                    product.product_type = 'section'
                    product.title = course.title
                    product.tax_code = 'ST080031'
                    product.fee = section.fee
                    product.minimum_fee = section.fee
                    product.save()

    return True

def es_course_unpublish(store_course):
    '''
    checks the stores key in the course object and removes the store id of the store from which the course is being unpublished.
    if the store id is the sole item, then the whole key is removed
    '''
    baseURL = config('ES_BASE_URL')
    method = 'GET'
    db_ref = store_course.course.content_db_reference
    url = f'{baseURL}/course/_doc/{db_ref}?routing={db_ref}'
    resp = requests.get(url)
    course = resp.json()

    if course['found']:
        try:
            stores = course['_source']['stores']
        except KeyError:
            pass
        else:
            if store_course.store.url_slug in stores:
                stores.remove(store_course.store.url_slug)

                if len(stores) == 0:
                    method = 'DELETE'
                    resp = requests.request(method, url)
                else:
                    url = url.replace('_doc', '_update')
                    payload = {
                        'doc': {
                            "stores": stores
                        }
                    }

                    method = 'POST'
                    resp = requests.request(method, url, json=payload)

def delete_course_action(request, request_data, contracts, course_provider_model):
    # 1. Get the course
    course_model_data = prepare_course_mongo(request_data, request.course_provider, course_provider_model)
    course_data = prepare_course_postgres(request_data, request.course_provider, course_provider_model)
    with scopes_disabled():
        try:
            course = Course.objects.get(slug=course_data['slug'], course_provider=request.course_provider)
        except Course.DoesNotExist:
            return (False, f"course with slug {course_data['slug']} does not exist")

        try:
            course_model = CourseModel.objects.get(id=course.content_db_reference)
        except CourseModel.DoesNotExist:
            pass

    # 2. Get the sections
    section_names = []
    for section_data in request_data.get('sections', []):
        section_data = prepare_section_postgres(section_data, course, course_model)
        section_names.append(section_data['name'])

    with scopes_disabled():
        # if no section is provided, then consider the whole course for deletion/deactivation e.g. all the sections
        if section_names:
            sections = course.sections.filter(name__in=section_names)
        else:
            sections = course.sections.all()

    # 3. Get store courses
    with scopes_disabled():
        store_courses = StoreCourse.objects.filter(course=course, store__in=[contract.store for contract in contracts])

    # 4. Get store course sections
    with scopes_disabled():
        store_course_sections = StoreCourseSection.objects.filter(store_course__in=store_courses, section__in=sections)

    #########################################################################################
    # If all the sections of a course are not to be deleted, then the course is not touched.
    # otherwise, the course is deactivated after deactivating all the sections.
    # this works when no section is provide and we consider the whole course (e.g. all the section) for deactivation
    # but will fail when all the sections are provide.
    # in that case, we must manually check if the course has any section left active after the deactivation
    # operation and if there's none, deactivate the course only then

    # 1. Deactivate the Store Course Sections
    with transaction.atomic():
        with scopes_disabled():
            store_course_sections.update(active_status=False)

            # 2. Deactivate the Products associated with the store course_sections here
            Product.objects.filter(
                id__in=[scs.product.id for scs in store_course_sections]

            ).update(active_status=False)

            # 3. Now the Section
            sections.update(active_status=False)

            # 4. Now the Course if it has no active section
            if course.sections.filter(active_status=True).count() == 0:
                course.active_status = False
                course.save()

                # if the course is deactivated, deactivate the store_courses too
                store_courses.update(active_status=False)

    # once the store_course is deactivated, these must be then removed from ES too
    for store_course in store_courses:
        es_course_unpublish(store_course)

    return (True, 'action performed successfully')
