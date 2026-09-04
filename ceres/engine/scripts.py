import json
import base64
import logging

logger = logging.getLogger(__name__)


class _SkipSignal(Exception):
    """Raised by mercury.skip() to mark the case as skipped."""
    def __init__(self, reason=''):
        self.reason = reason or ''
        super().__init__(self.reason)


class MercuryAPI:
    """Mercury script API for use in pre/post request scripts.

    Available in scripts as `mercury`:
    - mercury.getVar(name), mercury.setVar(name, value)
    - mercury.getEnvVar(name), mercury.getEnvName()
    - mercury.skip(reason)  — pre-request only; marks case as skipped
    - req.headers, req.body (pre-request)
    - res.status, res.body, res.headers (post-response)
    """

    def __init__(self, variable_context, env_name=''):
        self._ctx = variable_context
        self._env_name = env_name

    def getVar(self, name):
        return self._ctx.get_var(name)

    def setVar(self, name, value):
        self._ctx.set_var(name, value)

    def getEnvVar(self, name):
        return self._ctx.get_env_var(name)

    def getEnvName(self):
        return self._env_name

    def skip(self, reason=''):
        raise _SkipSignal(reason)


class RequestProxy:
    """Mutable request object for pre-request scripts."""

    def __init__(self, headers=None, body=None, url='', method=''):
        self.headers = dict(headers or {})
        self.body = body
        self.url = url
        self.method = method


class DotDict(dict):
    """Dict that supports attribute access for dot notation (res.body.key).

    Data keys take priority over dict methods, so res.body.items returns
    the 'items' value from the data, not dict.items().
    """

    def __getattribute__(self, name):
        # Data keys take priority over dict methods
        if name != '__class__' and not name.startswith('_'):
            try:
                val = self[name]
                if isinstance(val, dict):
                    return DotDict(val)
                if isinstance(val, list):
                    return [DotDict(v) if isinstance(v, dict) else v for v in val]
                return val
            except KeyError:
                pass
        return super().__getattribute__(name)

    def __setattr__(self, name, value):
        self[name] = value


def _wrap_body(body):
    """Wrap response/request body to support dot access."""
    if isinstance(body, dict):
        return DotDict(body)
    if isinstance(body, list):
        return [DotDict(v) if isinstance(v, dict) else v for v in body]
    return body


class ResponseProxy:
    """Read-only response object for post-response scripts."""

    def __init__(self, status=0, body=None, headers=None,
                 ws_handshake_status=None, ws_close_code=None, ws_close_reason=None,
                 ws_messages=None, ws_duration_ms=None, ws_truncated=None):
        self.status = status
        self.body = _wrap_body(body)
        self.headers = dict(headers or {})
        # WS-only fields. None for HTTP cases.
        # camelCase to match the documented script-side names
        # (res.handshakeStatus / res.closeCode / etc.).
        self.handshakeStatus = ws_handshake_status
        self.closeCode = ws_close_code
        self.closeReason = ws_close_reason
        self.messages = _wrap_body(ws_messages) if ws_messages is not None else None
        self.duration_ms = ws_duration_ms
        self.messagesTruncated = ws_truncated


def execute_script(script_text, variable_context, env_name='',
                   request_proxy=None, response_proxy=None,
                   case_name='', phase=''):
    """Execute a Python script with Mercury namespace.

    Args:
        script_text: Python script to execute
        variable_context: VariableContext instance
        env_name: Current environment name
        request_proxy: RequestProxy for pre-request scripts
        response_proxy: ResponseProxy for post-response scripts

    Returns:
        dict with 'success' (bool), 'error' (str or None),
        'request_proxy' (if modified), 'response_proxy'
    """
    if not script_text or not script_text.strip():
        return {'success': True, 'error': None}

    api = MercuryAPI(variable_context, env_name)

    namespace = {
        'mercury': api,
        'json': json,
        'base64': base64,
        '__builtins__': {
            'print': print,
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict,
            'len': len,
            'range': range,
            'enumerate': enumerate,
            'chr': chr,
            'ord': ord,
            'abs': abs,
            'min': min,
            'max': max,
            'sorted': sorted,
            'map': map,
            'filter': filter,
            'zip': zip,
            'any': any,
            'all': all,
            'round': round,
            'set': set,
            'tuple': tuple,
            'hasattr': hasattr,
            'getattr': getattr,
            'isinstance': isinstance,
            'type': type,
            'None': None,
            'True': True,
            'False': False,
            'Exception': Exception,
            'ValueError': ValueError,
            'KeyError': KeyError,
            'TypeError': TypeError,
            '__import__': __import__,
        },
    }

    if request_proxy:
        namespace['req'] = request_proxy
    if response_proxy:
        namespace['res'] = response_proxy

    try:
        exec(script_text, namespace)
        return {
            'success': True,
            'error': None,
        }
    except _SkipSignal as s:
        return {
            'success': True,
            'error': None,
            'skipped': True,
            'skip_reason': s.reason,
        }
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        ctx = f'{case_name}/{phase}' if (case_name or phase) else 'script'
        logger.warning(f'Script execution error in {ctx}: {e}\n{tb}')
        return {
            'success': False,
            'error': str(e),
        }
