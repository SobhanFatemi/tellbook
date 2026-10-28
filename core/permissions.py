from rest_framework.permissions import BasePermission


class IsCreator(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == request.user.Role.CREATOR
        )


class IsOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None) or getattr(obj, "buyer", None)
        return owner == request.user
