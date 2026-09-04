import jwt
from django.conf import settings
from rest_framework import authentication, exceptions

JWT_ALGORITHM = 'HS256'


class JWTUser:
    """Minimal user object wrapping a JWT payload so DRF permissions work."""

    is_authenticated = True

    def __init__(self, payload):
        self._payload = payload
        for key, value in payload.items():
            setattr(self, key, value)

    def __getitem__(self, key):
        return self._payload[key]

    def get(self, key, default=None):
        return self._payload.get(key, default)


class JWTAuthentication(authentication.BaseAuthentication):
    """DRF authentication class that validates JWT tokens."""

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header[7:]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token')

        user = JWTUser(payload)
        request.user_info = payload
        # Also set on Django HttpRequest so middleware can access it
        if hasattr(request, '_request'):
            request._request.user_info = payload
        return (user, token)

    def authenticate_header(self, request):
        return 'Bearer'
