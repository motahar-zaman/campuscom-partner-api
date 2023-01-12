from publish.permissions import HasCourseProviderAPIKey
from rest_framework.response import Response
from shared_models.models import CourseSharingContract, Notification, Cart, Payment, CourseEnrollment
from notifications.serializers import PaymentSerializer, NotificationSerializer
from .helpers import format_notification_response
from rest_framework import viewsets
from datetime import datetime
from django_scopes import scopes_disabled
from rest_framework.decorators import permission_classes
from api_logging import ApiLogging
from rest_framework.status import (
    HTTP_200_OK,
)


# Create your views here.
@permission_classes([HasCourseProviderAPIKey])
class NotificationsViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'head',]
    model = Notification
    log = ApiLogging()


    def get_queryset(self):
        fields = self.request.GET.copy()
        try:
            fields.pop("limit")
            fields.pop("page")
        except KeyError:
            pass

        return self.model.objects.filter(**fields.dict())

    def retrieve(self, request, *args, **kwargs):
        notification = self.get_object()
        data = {'status': notification.status, 'time': notification.creation_time.strftime("%m/%d/%Y, %H:%M:%S")}

        try:
            erp = request.course_provider.configuration.get('erp', '')
        except:
            erp = ''

        with scopes_disabled():
            if notification.data['type'] == 'order':
                try:
                    cart = Cart.objects.get(pk=notification.data['id'])
                except Cart.DoesNotExist:
                    response = {'data': data, 'message': "No details available for this order"}
                    self.log.store_logging_data(request, {'request': kwargs, 'response': response},
                                                'notification retrieve request-response from provider ' +
                                                request.course_provider.name, status_code=HTTP_200_OK, erp=erp)
                    return Response(response, status=HTTP_200_OK)
                else:
                    data['details'] = format_notification_response(cart)

            elif notification.data['type'] == 'payment':
                try:
                    payment = Payment.objects.get(pk=notification.data['id'])
                except Payment.DoesNotExist:
                    response = {'data': data, 'message': "No details available for this payment"}
                    self.log.store_logging_data(request, {'request': kwargs, 'response': response},
                                                'notification retrieve request-response from provider ' +
                                                request.course_provider.name, status_code=HTTP_200_OK, erp=erp)
                    return Response(response, status=HTTP_200_OK)
                else:
                    serializer = PaymentSerializer(payment)
                    data['details'] = serializer.data

        self.log.store_logging_data(request, {'request': kwargs, 'response': data},
                                    'notification retrieve request-response from provider ' +
                                    request.course_provider.name, status_code=HTTP_200_OK, erp=erp)
        return Response(data, status=HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        query_params = request.GET.copy()
        from_date = request.GET.get('from_date', None)
        to_date = request.GET.get('to_date', None)
        status = request.GET.get('status', None)

        try:
            erp = request.course_provider.configuration.get('erp', '')
        except:
            erp = ''

        if from_date:
            query_params.pop('from_date')
        if to_date:
            query_params.pop('to_date')

        if from_date and to_date:
            query_params.appendlist('creation_time__range', [from_date, to_date])
        elif status:
            pass
        else:
            response = {'message': 'Parameter missing of from_date, to_date, status'}
            self.log.store_logging_data(request, {'request': request.GET, 'response': response},
                                        'notification list request-response from provider ' +
                                        request.course_provider.name, status_code=HTTP_200_OK, erp=erp)
            return Response(response, status=HTTP_200_OK)

        # filter by course_provider to ensure notifications are for that course_provider's courses
        query_params.appendlist('course_provider', request.course_provider)

        try:
            notifications = Notification.objects.filter(**query_params.dict())
        except Notification.DoesNotExist:
            return Response({'message': 'No notification found'}, status=HTTP_200_OK)

        notification_serializer = NotificationSerializer(notifications, many=True)

        response = {
            'total': notifications.count(),
            'successful': notifications.filter(status='successful').count(),
            'failed': notifications.filter(status='failed').count(),
            'pending': notifications.filter(status='pending').count(),
            'data': notification_serializer.data
        }

        self.log.store_logging_data(request, {'request': request.GET, 'response': response},
                                    'notification list request-response from provider ' + request.course_provider.name,
                                    status_code=HTTP_200_OK, erp=erp)
        return Response(response, status=HTTP_200_OK)
