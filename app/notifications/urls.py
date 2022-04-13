from django.urls import path, include
from rest_framework import routers
from notifications.views import NotificationsViewSet


router = routers.DefaultRouter()

router.register(r'', NotificationsViewSet, 'get_notifications')


urlpatterns = [
    path('', include(router.urls)),
]