from django.urls import path
from webhooks.views import webhooks


urlpatterns = [
    path('', webhooks),
]
