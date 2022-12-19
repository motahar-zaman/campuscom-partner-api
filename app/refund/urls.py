from django.urls import path, include
from rest_framework.routers import DefaultRouter
from refund.views import RefundViewSet

router = DefaultRouter(trailing_slash=False)

router.register(r'', RefundViewSet, 'get_refund')


urlpatterns = [
    path('', include(router.urls)),
]
