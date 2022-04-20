from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('publish.urls')),
    path('webhooks/', include('webhooks.urls')),
    path('admin/', admin.site.urls),
    path('notifications/', include('notifications.urls')),
]
