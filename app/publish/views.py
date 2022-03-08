from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from bson import ObjectId
import mongoengine

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

from .helpers import (
    get_datetime_obj,
    upsert_mongo_doc,
    prepare_course_postgres,
    prepare_course_mongo,
    get_execution_site,
    get_instructors,
    get_schedules,
    prepare_section_mongo,
    prepare_section_postgres,
    transale_j1_data,
    get_data
)
import json
from bson.json_util import dumps

from publish.serializers import CourseSerializer, SectionSerializer
from campuslibs.loggers.mongo import save_to_mongo
from .tasks import generic_task_enqueue

@api_view(['POST'])
@permission_classes([HasCourseProviderAPIKey])
def publish(request):
    payload = request.data.copy()

    # first of all, save everything to mongodb
    mongo_data = {'payload': payload,  'status': 'initiated'}
    save_to_mongo(data=mongo_data, collection='partner_data')

    action = payload['action']
    try:
        request_data = payload['data']
    except KeyError:
        try:
            request_data = payload['records']
        except KeyError:
            return Response({'message': 'no data provided'})

    contracts = CourseSharingContract.objects.filter(course_provider=request.course_provider, is_active=True)

    # in this query, we add the course provider although we have the id of the course
    # this is because, we want to make sure we don't change any course to which the
    # user has no access. since course provider is determined from the secured key
    # provided as authorization header, user can not fake this.

    try:
        course_provider_model = CourseProviderModel.objects.get(id=request.course_provider.content_db_reference)
    except CourseProviderModel.DoesNotExist:
        return Response({'message': 'course provider model not found'})

    if action == 'j1-course':
        request_data = transale_j1_data(request_data)
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

            course_model = CourseModel.objects.get(id=course.content_db_reference)

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

        return Response({'message': 'action performed successfully'}, status=HTTP_201_CREATED)

    elif action == 'record':
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mongo_data['course_provider_model_id'] = str(course_provider_model.id)
        mongo_data['course_provider_id'] = str(request.course_provider.id)
        mongo_data['log'] = [{'message': 'initiating', 'time': current_time}]

        collection = 'publish_job'

        db = mongoengine.get_db()
        coll = db[collection]
        result = coll.insert_one(mongo_data)

        # now add task to queue. pass the doc id got from save_mongo_db
        generic_task_enqueue('create.publish', str(result.inserted_id))
        return Response({'message': str(result.inserted_id)}, status=HTTP_200_OK)

    return Response({'message': 'invalid action name'}, status=HTTP_200_OK)


@api_view(['GET'])
@permission_classes([HasCourseProviderAPIKey])
def job_status(request, **kwargs):
    job_id = kwargs['job_id']
    query = {'job_id': ObjectId(job_id)}
    collection = 'queue_item'
    datas = get_data(collection, query)

    data_list = json.loads(dumps(datas))

    print(datas)
    return Response({'data': data_list}, status=HTTP_200_OK)

