from rest_framework.response import Response
from django.http import HttpResponse
from shared_models.models import Profile, CourseSharingContract, Notification, Cart, Payment, CourseEnrollment
from models.courseprovider.course_provider import CourseProvider as CourseProviderModel

from publish.serializers import ProfileSerializer, CheckoutLoginUserModelSerializer

from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
)

from rest_framework.decorators import api_view, permission_classes
from publish.permissions import HasCourseProviderAPIKey

from .helpers import transale_j1_data, j1_publish, deactivate_course, validate_j1_payload

from hashlib import md5

from publish.serializers import PublishJobModelSerializer, PublishLogModelSerializer
from campuslibs.loggers.mongo import save_to_mongo
from .tasks import generic_task_enqueue
from models.log.publish_log import PublishLog as PublishLogModel
from django_scopes import scopes_disabled
from datetime import datetime
from decouple import config
from api_logging import ApiLogging

@api_view(['POST'])
@permission_classes([HasCourseProviderAPIKey])
def publish(request):
    payload = request.data.copy()

    # first of all, save everything to mongodb
    mongo_data = {'payload': payload,  'status': 'initiated'}
    save_to_mongo(data=mongo_data, collection='partner_data')
    log = ApiLogging()

    action = payload['action']
    try:
        erp = request.course_provider.configuration.get('erp', '')
    except:
        erp = ''
    try:
        request_data = payload['data']
    except KeyError:
        try:
            request_data = payload['records']
        except KeyError:
            log.store_logging_data(request, {'payload': payload, 'response': {'message': 'no data provided'}},
                                   'publish request-response of '+ action +' from provider ' +
                                   request.course_provider.name, status_code=HTTP_400_BAD_REQUEST, erp=erp)
            return Response({'message': 'no data provided'})

    contracts = CourseSharingContract.objects.filter(course_provider=request.course_provider, is_active=True)

    # in this query, we add the course provider although we have the id of the course
    # this is because, we want to make sure we don't change any course to which the
    # user has no access. since course provider is determined from the secured key
    # provided as authorization header, user can not fake this.

    try:
        course_provider_model = CourseProviderModel.objects.get(id=request.course_provider.content_db_reference)
    except CourseProviderModel.DoesNotExist:
        log.store_logging_data(request, {'payload': payload, 'response': {'message': 'course provider model not found'}},
                               'publish request-response of '+ action +' from provider ' + request.course_provider.name,
                               status_code=HTTP_400_BAD_REQUEST, erp=erp)
        return Response({'message': 'course provider model not found'})

    if action == 'j1-course':
        valid, message = validate_j1_payload(request_data)
        if not valid:
            log.store_logging_data(request, {'payload': payload, 'response': {'message': message}},
                                   'publish request-response of ' + action + ' from provider ' +
                                   request.course_provider.name, status_code=HTTP_400_BAD_REQUEST, erp=erp)
            return Response({'message': message}, status=HTTP_400_BAD_REQUEST)

        # the case of j1: their payload has a key entity_action. depending on its value, stuff will happen.
        # but for others, this key may not be present.
        request_data = transale_j1_data(request_data)
        if payload.get('entity_action', '').strip().lower() == 'd':
            status, message = deactivate_course(request, request_data, contracts, course_provider_model)
            log.store_logging_data(request, {'payload': payload, 'response': {'message': message}},
                                   'publish request-response of ' + action + ' from provider ' +
                                   request.course_provider.name, status_code=HTTP_200_OK, erp=erp)
            return Response({'message': message}, status=HTTP_200_OK)

        response, errors = j1_publish(request, request_data, contracts, course_provider_model)

        log.store_logging_data(request, {'payload': payload, 'response': {'message': 'action performed successfully'}},
                               'publish request-response of ' + action + ' from provider ' + request.course_provider.name,
                               status_code=HTTP_201_CREATED, erp=erp)
        # return Response({'message': 'action performed successfully', 'errors': errors}, status=HTTP_201_CREATED)
        return Response({'message': 'action performed successfully'}, status=HTTP_201_CREATED)

    elif action == 'record_add' or action == 'record_update' or action == 'record_delete' or action == 'record_tag' or action == 'record_untag':
        mongo_data['course_provider_model_id'] = str(course_provider_model.id)
        mongo_data['course_provider_id'] = str(request.course_provider.id)

        publish_job_serializer = PublishJobModelSerializer(data=mongo_data)
        if publish_job_serializer.is_valid():
            publish_job = publish_job_serializer.save()
        else:
            log.store_logging_data(request, {'payload': payload, 'response': {'message': publish_job_serializer.errors}},
                                   'publish request-response of ' + action + ' from provider ' + request.course_provider.name,
                                   status_code=HTTP_201_CREATED, erp=erp)
            return Response({'message': publish_job_serializer.errors}, status=HTTP_400_BAD_REQUEST)

        # now add task to queue. pass the doc id got from save_mongo_db
        generic_task_enqueue('create.publish', str(publish_job.id))
        response_data = {'message': 'successfully created a job', 'job_id': str(publish_job.id)}

        log.store_logging_data(request, {'payload': payload, 'response': response_data},
                               'publish request-response of '+ action + ' from provider ' + request.course_provider.name,
                               status_code=HTTP_200_OK, erp=erp)
        return Response(response_data, status=HTTP_200_OK)

    log.store_logging_data(request, {'payload': payload, 'response': {'message': 'invalid action name'}},
                           'publish request-response of ' + action + ' from  provider ' + request.course_provider.name,
                           status_code=HTTP_200_OK, erp=erp)
    return Response({'message': 'invalid action name'}, status=HTTP_200_OK)


@api_view(['GET'])
@permission_classes([HasCourseProviderAPIKey])
def job_status(request, *args, **kwargs):
    job_id = kwargs['job_id']
    logs = PublishLogModel.objects.filter(publish_job_id=job_id)
    log_serializer = PublishLogModelSerializer(logs, many=True)
    log_data = log_serializer.data
    successful = 0
    failed = 0
    pending = 0
    log = ApiLogging()
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
    try:
        erp = request.course_provider.configuration.get('erp', '')
    except:
        erp = ''
    log.store_logging_data(request, {'request': kwargs, 'response': formatted_data},
                           'request-response of job status from provider ' + request.course_provider.name,
                           status_code=HTTP_200_OK, erp=erp)
    return Response({'data': formatted_data}, status=HTTP_200_OK)


@api_view(['POST'])
@permission_classes([HasCourseProviderAPIKey])
def student(request, **kwargs):
    status = ''
    message = ''
    try:
        action = request.data['action']
    except KeyError:
        return Response({'data': 'action not specified'})

    try:
        data_type = request.data['type']
    except KeyError:
        return Response({'data': 'type not specified'})

    if action == 'record' and data_type == 'student':
        try:
            primary_email = request.data['data']['primary_email']
        except KeyError:
            return Response({'data': 'primary_key must be provide'})

        try:
            profile = Profile.objects.get(primary_email=primary_email)
        except Profile.DoesNotExist:
            status = 'created'
            message = 'new profile created successfully'
            serializer = ProfileSerializer(data=request.data['data'])
        else:
            status = 'updated'
            message = 'profile updated successfully'
            serializer = ProfileSerializer(profile, data=request.data['data'])

        if serializer.is_valid():
            serializer.save()
            data = request.data
            data['data'] = serializer.data
            data['status'] = status
            data['message'] = message

        else:
            data = request.data
            data['errors'] = serializer.errors
            data['status'] = 'failed'
            data['message'] = 'error occured'

        return Response(data, status=HTTP_200_OK)

    return Response({'data': 'Invalid action or type'}, status=HTTP_200_OK)


def health_check(request):
    return HttpResponse(status=HTTP_200_OK)


@api_view(['POST'])
@permission_classes([HasCourseProviderAPIKey])
def checkout_info(request):
    log = ApiLogging()
    try:
        expiration_time = config('CHECKOUT_INFO_EXPIRATION_TIME')
    except Exception as e:
        expiration_time = 600

    payload = request.data.copy()
    login_user_serializer = CheckoutLoginUserModelSerializer(data={'payload': payload, 'status': 'pending', 'expiration_time': expiration_time})

    try:
        erp = request.course_provider.configuration.get('erp', '')
    except:
        erp = ''

    if login_user_serializer.is_valid():
        login_user = login_user_serializer.save()
    else:
        log.store_logging_data(request, {'payload': payload, 'response': {'message': login_user_serializer.errors}},
                               'request-response of checkout-info from provider ' + request.course_provider.name,
                               status_code=HTTP_400_BAD_REQUEST, erp=erp)
        return Response({'message': login_user_serializer.errors}, status=HTTP_400_BAD_REQUEST)

    token = md5(str(login_user.id).encode()).hexdigest()
    login_user.token = token
    login_user.status = 'token created'
    login_user.save()

    response = {'tid': token, 'message': "Checkout Information Received"}
    log.store_logging_data(request, {'payload': payload, 'response': response},
                           'request-response of checkout-info from provider ' + request.course_provider.name,
                           status_code=HTTP_200_OK, erp=erp)
    return Response(response, status=HTTP_200_OK)


