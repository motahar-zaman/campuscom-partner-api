from django.urls import path, include
# from rest_framework import routers

# from publish.views import PublishViewSet, publish
from publish.views import publish
from publish.views import job_status
from publish.views import student
from publish.views import health_check
from publish.views import checkout_info

# router = routers.DefaultRouter()

# router.register(r'publish', PublishViewSet, 'publish')


urlpatterns = [
    # path('', include(router.urls)),
    path('publish/', publish),
    path('job-status/<job_id>', job_status),
    path('student/', student),
    path('check/', health_check),
    path('checkout-info/', checkout_info),
]
