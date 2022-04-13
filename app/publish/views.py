from rest_framework.response import Response
from django.http import HttpResponse
from shared_models.models import Profile, CourseSharingContract, Notification, Cart, Payment, CourseEnrollment
from models.courseprovider.course_provider import CourseProvider as CourseProviderModel

from publish.serializers import ProfileSerializer, PaymentSerializer, CheckoutLoginUserModelSerializer,\
    NotificationSerializer

from rest_framework.status import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
)

from rest_framework.decorators import api_view, permission_classes
from publish.permissions import HasCourseProviderAPIKey

from .helpers import transale_j1_data, j1_publish, format_notification_response
from .helpers import transale_j1_data, j1_publish, deactivate_course

from hashlib import md5

from publish.serializers import PublishJobModelSerializer, PublishLogModelSerializer
from campuslibs.loggers.mongo import save_to_mongo
from .tasks import generic_task_enqueue
from models.log.publish_log import PublishLog as PublishLogModel
from django_scopes import scopes_disabled
from datetime import datetime

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
        # the case of j1: their payload has a key entity_action. depending on it's value, stuff will happen.
        # but for others, this key may not be present.
        request_data = transale_j1_data(request_data)
        if payload.get('entity_action', '').strip().lower() == 'd':
            status, message = deactivate_course(request, request_data, contracts, course_provider_model)
            return Response({'message': message}, status=HTTP_200_OK)

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
    payload = request.data.copy()
    login_user_serializer = CheckoutLoginUserModelSerializer(data={'payload': payload, 'status': 'pending', 'expiration_time':10})
    if login_user_serializer.is_valid():
        login_user = login_user_serializer.save()
    else:
        return Response({'message': login_user_serializer.errors}, status=HTTP_400_BAD_REQUEST)

    token = md5(str(login_user.id).encode()).hexdigest()
    login_user.token = token
    login_user.status = 'token created'
    login_user.save()

    return Response({'tid': token, 'message': "Checkout Information Received"}, status=HTTP_200_OK)


@api_view(['POST'])
@permission_classes([HasCourseProviderAPIKey])
def notification_details(request, **kwargs):
    notification_id = kwargs['notification_id']
    data = {}

    try:
        notification = Notification.objects.get(pk=notification_id)
    except Notification.DoesNotExist:
        return Response({'message': 'Notification not found'})
    else:
        type = notification.data['type']
        id = notification.data['id']
        data['status'] = notification.status
        data['time'] = notification.creation_time.strftime("%m/%d/%Y, %H:%M:%S")

        with scopes_disabled():
            if type == 'order':
                try:
                    cart = Cart.objects.get(pk=id)
                except Cart.DoesNotExist:
                    return Response({'data': data, 'message': "No details available for this order"}, status=HTTP_200_OK)
                else:
                    data['details'] = format_notification_response(cart)

            elif type == 'payment':
                try:
                    payment = Payment.objects.get(pk=id)
                except Cart.DoesNotExist:
                    return Response({'data': data, 'message': "No details available for this payment"}, status=HTTP_200_OK)
                else:
                    serializer = PaymentSerializer(payment)
                    data['details'] = serializer.data

            elif type == 'enrollment':
                try:
                    enrollment = CourseEnrollment.objects.get(pk=id)
                except CourseEnrollment.DoesNotExist:
                    return Response({'data': data, 'message': "No details available for this enrollment"}, status=HTTP_200_OK)
                else:
                    data['details'] = format_notification_response(enrollment.cart_item.cart, course_enrollment = enrollment)

    return Response(data, status=HTTP_200_OK)


@api_view(['GET'])
@permission_classes([HasCourseProviderAPIKey])
def get_notifications(request, **kwargs):
    from_date = request.GET.get('from_date', None)
    to_date = request.GET.get('to_date', None)
    status = request.GET.get('status', None)

    if from_date and to_date:
        from_date = datetime.strptime(from_date, '%Y-%m-%d')
        to_date = datetime.strptime(to_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        try:
            notification = Notification.objects.filter(creation_time__range=(from_date, to_date))
            if status:
                notification = notification.filter(status=status)
        except Notification.DoesNotExist:
            return Response({'message': 'Notification not found'})
        else:
            notification_serializer = NotificationSerializer(notification, many=True)

    elif status:
        try:
            notification = Notification.objects.filter(status=status)
        except Notification.DoesNotExist:
            return Response({'message': 'Notification not found'})
        else:
            notification_serializer = NotificationSerializer(notification, many=True)

    else:
        return Response({'message': 'Parameter missing of from_date, to_date, status'}, status=HTTP_200_OK)

    notification_data = notification_serializer.data
    successful = 0
    failed = 0
    pending = 0
    for data in notification_data:
        if data['status'] == 'failed':
            failed += 1
        elif data['status'] == 'successful':
            successful += 1
        else:
            pending += 1

    response = {
        'total': successful + failed + pending,
        'successful': successful,
        'failed': failed,
        'pending': pending,
        'data': notification_data
    }


    return Response(response, status=HTTP_200_OK)

