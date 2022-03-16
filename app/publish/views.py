from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from bson import ObjectId
import mongoengine

from shared_models.models import Course, Section, CourseSharingContract, StoreCourse, Product, StoreCourseSection
from models.courseprovider.course_provider import CourseProvider as CourseProviderModel
from models.courseprovider.provider_site import CourseProviderSite as CourseProviderSiteModel
from models.courseprovider.instructor import Instructor as InstructorModel
from datetime import datetime

from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
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
    transale_j1_data,
    get_data,
    j1_publish
)
import json
from bson.json_util import dumps

from publish.serializers import CourseSerializer, SectionSerializer, PublishJobModelSerializer, PublishLogModelSerializer
from campuslibs.loggers.mongo import save_to_mongo
from .tasks import generic_task_enqueue
from models.publish.publish_job import PublishJob as PublishJobModel
from models.log.publish_log import PublishLog as PublishLogModel

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
        j1_publish(request, request_data, contracts, course_provider_model)

        return Response({'message': 'action performed successfully'}, status=HTTP_201_CREATED)

    elif action == 'record':
        mongo_data['course_provider_model_id'] = str(course_provider_model.id)
        mongo_data['course_provider_id'] = str(request.course_provider.id)

        publish_job_serializer = PublishJobModelSerializer(data=mongo_data)
        if publish_job_serializer.is_valid():
            publish_job = publish_job_serializer.save()
        else:
            return Response({'message': publish_job_serializer.errors}, status=HTTP_400_BAD_REQUEST)

        # now add task to queue. pass the doc id got from save_mongo_db
        generic_task_enqueue('create.publish', str(publish_job.id))
        return Response({'message': 'successfully created a job', 'job_id': str(publish_job.id)}, status=HTTP_200_OK)

    return Response({'message': 'invalid action name'}, status=HTTP_200_OK)


@api_view(['GET'])
@permission_classes([HasCourseProviderAPIKey])
def job_status(request, **kwargs):
    job_id = kwargs['job_id']
    logs = PublishLogModel.objects.filter(publish_job_id=job_id)
    log_serializer = PublishLogModelSerializer(logs, many=True)
    log_data = log_serializer.data
    successful = 0
    failed = 0
    pending = 0
    for data in log_data:
        if data['status'] == "failed":
            failed += 1
        elif data['status'] == "completed":
            successful += 1
        else:
            pending += 1

    response = {
        'total': successful + failed + pending,
        'successful': successful,
        'failed': failed,
        'pending': pending
    }

    formatted_data = {
        'response': response,
        'job': {
            'id': job_id,
            'records': log_data
        }
    }
    return Response({'data': formatted_data}, status=HTTP_200_OK)

