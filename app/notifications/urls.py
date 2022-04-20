from django.urls import path, include
from rest_framework.routers import DefaultRouter
from notifications.views import NotificationsViewSet

router = DefaultRouter(trailing_slash=False)

router.register(r'', NotificationsViewSet, 'get_notifications')


urlpatterns = [
    path('', include(router.urls)),
]
