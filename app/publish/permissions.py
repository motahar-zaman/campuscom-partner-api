from django.http import HttpRequest
import typing
from shared_models.models import StoreAPIKey
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.exceptions import AuthenticationFailed

from rest_framework_api_key.permissions import BaseHasAPIKey


# class IsAuthenticated(IsAuthenticated):

#     def has_permission(self, request, view):
#         # the idea is: the store will be determined from the user.
#         # so the user does not have to provide any store
#         # this is becuase, the users will be created per store basis, presumably
#         # request must include some sort of user identification

#         store = Store.objects.get(url_slug='laroche')
#         request.store = store
#         return True
#         # raise AuthenticationFailed()

#     def has_object_permission(self, request, view, obj):
#         if request.method in SAFE_METHODS:
#             # also check if current user has access to this store
#             return True


class HasStoreAPIKey(BaseHasAPIKey):
    model = StoreAPIKey

    def has_permission(self, request: HttpRequest, view: typing.Any) -> bool:
        assert self.model is not None, (
            "%s must define `.model` with the API key model to use"
            % self.__class__.__name__
        )
        key = self.get_key(request)
        if not key:
            return False

        store_api_key = StoreAPIKey.objects.get_from_key(key)
        request.store = store_api_key.store

        return self.model.objects.is_valid(key)
