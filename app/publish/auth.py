from shared_models.models import Store
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.exceptions import AuthenticationFailed


class IsAuthenticated(IsAuthenticated):

    def has_permission(self, request, view):
        # the idea is: the store will be determined from the user.
        # so the user does not have to provide any store
        # this is becuase, the users will be created per store basis, presumably
        # request must include some sort of user identification

        store = Store.objects.get(url_slug='laroche')
        request.store = store
        return True
        # raise AuthenticationFailed()

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            # also check if current user has access to this store
            return True
