from rest_framework.authentication import SessionAuthentication as BaseSessionAuthentication

from .invitation_services import account_access_allowed


class SessionAuthentication(BaseSessionAuthentication):
    def authenticate(self, request):
        authentication = super().authenticate(request)
        if authentication is None:
            return None
        user, auth = authentication
        if not account_access_allowed(user):
            return None
        return user, auth

    def authenticate_header(self, request):
        return "Session"
