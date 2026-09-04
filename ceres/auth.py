import logging
from datetime import datetime, timedelta, timezone

import jwt
try:
    import ldap
    from ldap.filter import escape_filter_chars
except ImportError:
    ldap = None
from django.conf import settings
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# Hardcoded accounts — bypass whitelist + LDAP.
HARDCODED_ACCOUNTS = {
    'admin': 'admin',
}


def _ldap_authenticate(email, password):
    """Authenticate user against LDAP using email as UPN (no service account needed)."""
    ldap_config = settings.ENV_CONFIG.get('ldap', {})
    server_uri = ldap_config['server_uri']
    base_dn = ldap_config['base_dn']

    # Step 1: Bind directly with user's email (UPN) + password
    conn = ldap.initialize(server_uri)
    conn.set_option(ldap.OPT_REFERRALS, 0)
    conn.set_option(ldap.OPT_NETWORK_TIMEOUT, 10)
    conn.simple_bind_s(email, password)

    # Step 2: Search for user attributes
    result = conn.search_s(
        base_dn, ldap.SCOPE_SUBTREE,
        f'(mail={escape_filter_chars(email)})',
        ['dn', 'cn', 'mail', 'displayName', 'sAMAccountName'],
    )
    conn.unbind_s()

    if not result:
        return {
            'email': email,
            'display_name': email.split('@')[0],
            'username': email.split('@')[0],
        }

    user_dn, user_attrs = result[0]
    if not user_dn:
        return {
            'email': email,
            'display_name': email.split('@')[0],
            'username': email.split('@')[0],
        }

    def _decode(val):
        if isinstance(val, list):
            return val[0].decode('utf-8') if val else ''
        return val.decode('utf-8') if isinstance(val, bytes) else str(val)

    return {
        'dn': user_dn,
        'email': _decode(user_attrs.get('mail', '')) or email,
        'display_name': _decode(user_attrs.get('displayName', '')) or _decode(user_attrs.get('cn', '')),
        'username': _decode(user_attrs.get('sAMAccountName', '')),
    }


def _generate_token(user_info):
    payload = {
        'email': user_info['email'],
        'display_name': user_info['display_name'],
        'username': user_info['username'],
        'is_admin': user_info.get('is_admin', False),
        'exp': datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([])
def login(request):
    email = request.data.get('email', '').strip()
    password = request.data.get('password', '')

    if not email or not password:
        return Response({'detail': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

    # Hardcoded trial accounts — short-circuit before whitelist/LDAP.
    if email in HARDCODED_ACCOUNTS:
        if HARDCODED_ACCOUNTS[email] != password:
            return Response({'detail': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)
        user_info = {
            'email': email,
            'display_name': email.split('@')[0],
            'username': email.split('@')[0],
        }
        from ceres.models import User
        user_obj, _ = User.objects.update_or_create(
            email=user_info['email'],
            defaults={
                'display_name': user_info['display_name'],
                'username': user_info['username'],
                'is_admin': email == 'admin',
            },
        )
        user_info['is_admin'] = user_obj.is_admin
        return Response({
            'token': _generate_token(user_info),
            'user': {
                'email': user_info['email'],
                'display_name': user_info['display_name'],
                'username': user_info['username'],
                'is_admin': user_obj.is_admin,
            },
        })

    # Check whitelist
    from ceres.models import WhitelistEmail
    if not WhitelistEmail.objects.filter(email=email).exists():
        return Response({'detail': 'Your email is not in the whitelist. Contact admin.'}, status=status.HTTP_403_FORBIDDEN)

    # Local dev: verify password via test environment (LDAP not reachable locally)
    host = request.get_host().split(':')[0]
    is_local = host in ('localhost', '127.0.0.1', '0.0.0.0')
    if is_local:
        import requests as http_requests
        try:
            r = http_requests.post(
                f"{settings.ENV_CONFIG['domain']['test']}/api/auth/login/",
                json={'email': email, 'password': password},
                timeout=15,
            )
        except Exception as e:
            return Response({'detail': f'Failed to reach test environment: {e}'}, status=status.HTTP_502_BAD_GATEWAY)
        if r.status_code != 200:
            return Response(r.json(), status=r.status_code)
        # Password verified by test env, extract user info
        remote_user = r.json().get('user', {})
        user_info = {
            'email': remote_user.get('email', email),
            'display_name': remote_user.get('display_name', email.split('@')[0]),
            'username': remote_user.get('username', email.split('@')[0]),
        }
    else:
        try:
            user_info = _ldap_authenticate(email, password)
        except ldap.INVALID_CREDENTIALS:
            return Response({'detail': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)
        except ldap.LDAPError as e:
            logger.exception('LDAP error during authentication')
            desc = e.args[0].get('desc', str(e)) if e.args else str(e)
            return Response({'detail': f'LDAP error: {desc}'}, status=status.HTTP_502_BAD_GATEWAY)

        if not user_info:
            return Response({'detail': 'User not found'}, status=status.HTTP_401_UNAUTHORIZED)

    # Persist user
    from ceres.models import User
    user_obj, _ = User.objects.update_or_create(
        email=user_info['email'],
        defaults={
            'display_name': user_info['display_name'],
            'username': user_info['username'],
        },
    )
    user_info['is_admin'] = user_obj.is_admin

    token = _generate_token(user_info)
    return Response({
        'token': token,
        'user': {
            'email': user_info['email'],
            'display_name': user_info['display_name'],
            'username': user_info['username'],
            'is_admin': user_obj.is_admin,
        }
    })


@api_view(['GET'])
def me(request):
    """Return current user info from JWT token."""
    return Response({
        'email': request.user_info['email'],
        'display_name': request.user_info['display_name'],
        'username': request.user_info['username'],
    })
