from django.urls import path, include
# from rest_framework import routers

# from publish.views import PublishViewSet, publish
from publish.views import publish
from publish.views import job_status

# router = routers.DefaultRouter()

# router.register(r'publish', PublishViewSet, 'publish')


urlpatterns = [
    # path('', include(router.urls)),
    path('publish/', publish),
    path('job-status/<job_id>', job_status),
]
