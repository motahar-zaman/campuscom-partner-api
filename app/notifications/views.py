from publish.permissions import HasCourseProviderAPIKey
from rest_framework.response import Response
from shared_models.models import CourseSharingContract, Notification, Cart, Payment, CourseEnrollment
from notifications.serializers import PaymentSerializer, NotificationSerializer
from .helpers import format_notification_response
from rest_framework import viewsets
from datetime import datetime
from django_scopes import scopes_disabled
from rest_framework.decorators import permission_classes

from rest_framework.status import (
    HTTP_200_OK,
)


# Create your views here.
@permission_classes([HasCourseProviderAPIKey])
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
        data = {'status': notification.status, 'time': notification.creation_time.strftime("%m/%d/%Y, %H:%M:%S")}

        with scopes_disabled():
            if notification.data['type'] == 'order':
                try:
                    cart = Cart.objects.get(pk=notification.data['id'])
                except Cart.DoesNotExist:
                    return Response({'data': data, 'message': "No details available for this order"},
                                    status=HTTP_200_OK)
                else:
                    data['details'] = format_notification_response(cart)

            elif notification.data['type'] == 'payment':
                try:
                    payment = Payment.objects.get(pk=notification.data['id'])
                except Payment.DoesNotExist:
                    return Response({'data': data, 'message': "No details available for this payment"},
                                    status=HTTP_200_OK)
                else:
                    serializer = PaymentSerializer(payment)
                    data['details'] = serializer.data

        return Response(data, status=HTTP_200_OK)


    def list(self, request, *args, **kwargs):
        from_date = request.GET.get('from_date', None)
        to_date = request.GET.get('to_date', None)
        status = request.GET.get('status', None)

        if from_date and to_date:
            from_date = datetime.strptime(from_date, '%Y-%m-%d')
            to_date = datetime.strptime(to_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            try:
                notifications = Notification.objects.filter(creation_time__range=(from_date, to_date))
                if status:
                    notifications = notifications.filter(status=status)
            except Notification.DoesNotExist:
                return Response({'message': 'Notification not found'})

        elif status:
            try:
                notifications = Notification.objects.filter(status=status)
            except Notification.DoesNotExist:
                return Response({'message': 'Notification not found'})

        else:
            return Response({'message': 'Parameter missing of from_date, to_date, status'}, status=HTTP_200_OK)

        notification_serializer = NotificationSerializer(notifications, many=True)

        response = {
            'total': notifications.count(),
            'successful': notifications.filter(status='successful').count(),
            'failed': notifications.filter(status='failed').count(),
            'pending': notifications.filter(status='pending').count(),
            'data': notification_serializer.data
        }

        return Response(response, status=HTTP_200_OK)
