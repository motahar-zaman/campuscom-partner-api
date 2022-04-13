from publish.permissions import HasCourseProviderAPIKey
from rest_framework.response import Response
from shared_models.models import CourseSharingContract, Notification, Cart, Payment, CourseEnrollment
from notifications.serializers import PaymentSerializer, NotificationSerializer
from .helpers import format_notification_response
from rest_framework import viewsets
from datetime import datetime
from django_scopes import scopes_disabled

from rest_framework.status import (
    HTTP_200_OK,
)


# Create your views here.
# @permission_classes([HasCourseProviderAPIKey])
class NotificationsViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'head',]
    model = Notification


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
        data = {}

        type = notification.data['type']
        id = notification.data['id']
        data['status'] = notification.status
        data['time'] = notification.creation_time.strftime("%m/%d/%Y, %H:%M:%S")

        with scopes_disabled():
            if type == 'order':
                try:
                    cart = Cart.objects.get(pk=id)
                except Cart.DoesNotExist:
                    return Response({'data': data, 'message': "No details available for this order"},
                                    status=HTTP_200_OK)
                else:
                    data['details'] = format_notification_response(cart)

            elif type == 'payment':
                try:
                    payment = Payment.objects.get(pk=id)
                except Cart.DoesNotExist:
                    return Response({'data': data, 'message': "No details available for this payment"},
                                    status=HTTP_200_OK)
                else:
                    serializer = PaymentSerializer(payment)
                    data['details'] = serializer.data

            elif type == 'enrollment':
                try:
                    enrollment = CourseEnrollment.objects.get(pk=id)
                except CourseEnrollment.DoesNotExist:
                    return Response({'data': data, 'message': "No details available for this enrollment"},
                                    status=HTTP_200_OK)
                else:
                    data['details'] = format_notification_response(enrollment.cart_item.cart,
                                                                   course_enrollment=enrollment)
        return Response(data, status=HTTP_200_OK)


    def list(self, request, *args, **kwargs):
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
