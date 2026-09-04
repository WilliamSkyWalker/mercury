import json
import logging

from ceres.models import AuditLog

logger = logging.getLogger(__name__)

# Skip audit for read-only and high-frequency endpoints
SKIP_PATHS = ('/api/audit-logs/',)
SKIP_METHODS = ('GET', 'HEAD', 'OPTIONS')


class AuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only audit v2 API write operations
        if not request.path.startswith('/api/'):
            return response
        if request.method in SKIP_METHODS:
            return response
        if any(request.path.startswith(p) for p in SKIP_PATHS):
            return response

        user_email = ''
        if hasattr(request, 'user_info') and isinstance(request.user_info, dict):
            user_email = request.user_info.get('email', '')

        # Parse request body
        body = {}
        try:
            if request.content_type and 'json' in request.content_type:
                body = json.loads(request.body) if request.body else {}
                # Strip sensitive fields
                body.pop('password', None)
        except Exception:
            pass

        try:
            AuditLog.objects.create(
                user_email=user_email,
                action=request.method,
                path=request.path,
                body=body,
                status_code=response.status_code,
                ip_address=request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                           or request.META.get('REMOTE_ADDR'),
            )
        except Exception:
            logger.exception('Failed to create audit log')

        return response
