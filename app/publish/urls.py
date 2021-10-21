from django.urls import path, include
# from rest_framework import routers

# from publish.views import PublishViewSet, publish
from publish.views import publish

# router = routers.DefaultRouter()

# router.register(r'publish', PublishViewSet, 'publish')


urlpatterns = [
    # path('', include(router.urls)),
    path('publish/', publish),
]
