import re
import json


def resolve_field(field_path, response_status, response_body, response_headers,
                  response_duration_ms=None, extras=None):
    """Resolve a field path like 'res.status', 'res.body.data.id', 'res.headers.x-trace-id'.

    Args:
        field_path: Dot-separated path (e.g., 'res.status', 'res.body.data[0].id')
        response_status: HTTP status code
        response_body: Parsed response body (dict/list/str)
        response_headers: Response headers dict
        extras: optional dict of additional top-level fields. Used by WS cases
            to expose res.messages, res.handshakeStatus, res.closeCode,
            res.duration_ms, etc.

    Returns:
        The resolved value, or None if not found
    """
    if not field_path or not isinstance(field_path, str):
        return None

    parts = field_path.split('.', 1)
    if parts[0] != 'res' or len(parts) < 2:
        return None

    rest = parts[1]
    # Strip array suffix from the head token so 'messages[0]' / 'messages.length'
    # still hit the extras lookup; the navigation tail keeps the suffix.
    head_match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)(.*)$', rest)
    head = head_match.group(1) if head_match else rest
    tail = head_match.group(2) if head_match else ''

    if rest == 'status':
        return response_status

    if rest == 'responseTime':
        return response_duration_ms

    if rest.startswith('body'):

        remaining = rest[4:]  # strip 'body'
        if not remaining:
            return response_body
        if remaining.startswith('.'):
            remaining = remaining[1:]
        return _navigate(response_body, remaining)

    if rest.startswith('headers'):
        remaining = rest[7:]  # strip 'headers'
        if not remaining:
            return response_headers
        if remaining.startswith('.'):
            remaining = remaining[1:]
        # headers are case-insensitive
        if isinstance(response_headers, dict):
            lower_headers = {k.lower(): v for k, v in response_headers.items()}
            return lower_headers.get(remaining.lower())
        return None

    if extras and head in extras:
        value = extras[head]
        if not tail:
            return value
        # Strip leading '.' before navigating, leave '[' attached
        nav = tail[1:] if tail.startswith('.') else tail
        return _navigate(value, nav)

    return None


def _navigate(obj, path):
    """Navigate into a nested object using dot notation with array indexing.

    Supports paths like: 'data.items[0].name', 'data.id', 'items[2]', 'items[*].name'
    When [*] is used, returns a _WildcardResult containing all matched values.
    """
    if not path:
        return obj

    # Split by dots but respect array indices
    tokens = _tokenize_path(path)

    return _navigate_tokens(obj, tokens)


def _navigate_tokens(obj, tokens):
    """Recursively navigate tokens, expanding [*] wildcards."""
    if not tokens:
        return obj

    current = obj
    for i, token in enumerate(tokens):
        if current is None:
            return None

        # Check for wildcard like 'items[*]'
        wildcard_match = re.match(r'^(.+?)\[\*\]$', token)
        if wildcard_match:
            field_name = wildcard_match.group(1)
            if isinstance(current, dict) and field_name in current:
                current = current[field_name]
            else:
                return None
            if not isinstance(current, list):
                return None
            remaining_tokens = tokens[i + 1:]
            if not remaining_tokens:
                return _WildcardResult(list(current))
            values = []
            for item in current:
                val = _navigate_tokens(item, remaining_tokens)
                values.append(val)
            return _WildcardResult(values)

        # Pure wildcard [*]
        if token == '[*]':
            if not isinstance(current, list):
                return None
            remaining_tokens = tokens[i + 1:]
            if not remaining_tokens:
                return _WildcardResult(list(current))
            values = []
            for item in current:
                val = _navigate_tokens(item, remaining_tokens)
                values.append(val)
            return _WildcardResult(values)

        # Check for array index like 'items[0]'
        array_match = re.match(r'^(.+?)\[(\d+)\]$', token)
        if array_match:
            field_name = array_match.group(1)
            index = int(array_match.group(2))
            if isinstance(current, dict) and field_name in current:
                current = current[field_name]
            else:
                return None
            if isinstance(current, list) and 0 <= index < len(current):
                current = current[index]
            else:
                return None
        elif token.startswith('[') and token.endswith(']'):
            # Pure index like [0]
            index = int(token[1:-1])
            if isinstance(current, list) and 0 <= index < len(current):
                current = current[index]
            else:
                return None
        elif token == 'length':
            # JS-style .length → Python len()
            if isinstance(current, (list, str, dict)):
                current = len(current)
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(token)
        else:
            return None

    return current


class _WildcardResult:
    """Wrapper for wildcard [*] results, so evaluate_single can handle them."""
    def __init__(self, values):
        self.values = values


def _tokenize_path(path):
    """Split a dotted path into tokens, handling array brackets."""
    tokens = []
    current = ''
    i = 0
    while i < len(path):
        ch = path[i]
        if ch == '.':
            if current:
                tokens.append(current)
                current = ''
        elif ch == '[':
            if current:
                # field[0] - keep together
                bracket_end = path.index(']', i)
                current += path[i:bracket_end + 1]
                i = bracket_end
            else:
                bracket_end = path.index(']', i)
                tokens.append(path[i:bracket_end + 1])
                i = bracket_end
        else:
            current += ch
        i += 1
    if current:
        tokens.append(current)
    return tokens


def evaluate_single(actual, operator, expected):
    """Evaluate a single assertion.

    Returns:
        dict with 'passed' (bool) and 'message' (str)
    """
    try:
        if operator == 'eq':
            passed = actual == expected
        elif operator == 'neq':
            passed = actual != expected
        elif operator == 'gt':
            passed = actual > expected
        elif operator == 'gte':
            passed = actual >= expected
        elif operator == 'lt':
            passed = actual < expected
        elif operator == 'lte':
            passed = actual <= expected
        elif operator == 'in':
            passed = actual in expected
        elif operator == 'nin':
            passed = actual not in expected
        elif operator == 'contains':
            passed = expected in str(actual)
        elif operator == 'notContains':
            passed = expected not in str(actual)
        elif operator == 'isNull':
            passed = actual is None
        elif operator == 'isNotNull':
            passed = actual is not None
        elif operator == 'isEmpty':
            passed = actual is None or (hasattr(actual, '__len__') and len(actual) == 0)
        elif operator == 'isNotEmpty':
            passed = actual is not None and hasattr(actual, '__len__') and len(actual) > 0
        elif operator == 'matches':
            passed = bool(re.search(str(expected), str(actual)))
        else:
            return {'passed': False, 'message': f'Unknown operator: {operator}'}

        if passed:
            return {'passed': True, 'message': f'{operator} check passed'}
        else:
            return {'passed': False, 'message': f'Expected {operator} {expected!r}, got {actual!r}'}

    except Exception as e:
        return {'passed': False, 'message': f'Assertion error: {str(e)}'}


def evaluate_assertions(assertions, response_status, response_body, response_headers,
                        response_duration_ms=None, extras=None):
    """Evaluate a list of assertions against a response.

    Args:
        assertions: List of dicts with 'field', 'operator', 'expected'
        response_status: HTTP status code
        response_body: Parsed response body
        response_headers: Response headers dict
        extras: optional dict of WS-specific fields. See resolve_field.

    Returns:
        List of result dicts with 'field', 'operator', 'expected', 'actual', 'passed', 'message'
    """
    results = []
    for assertion in assertions:
        field = assertion.get('field', '')
        operator = assertion.get('operator', 'eq')
        expected = assertion.get('expected')

        actual = resolve_field(field, response_status, response_body, response_headers,
                               response_duration_ms, extras=extras)

        # Handle wildcard [*] results: check assertion against every element
        if isinstance(actual, _WildcardResult):
            values = actual.values
            if not values:
                results.append({
                    'field': field,
                    'operator': operator,
                    'expected': expected,
                    'actual': [],
                    'passed': False,
                    'message': f'Wildcard matched empty array',
                })
                continue

            all_passed = True
            failed_indices = []
            for idx, val in enumerate(values):
                r = evaluate_single(val, operator, expected)
                if not r['passed']:
                    all_passed = False
                    failed_indices.append(idx)

            if all_passed:
                results.append({
                    'field': field,
                    'operator': operator,
                    'expected': expected,
                    'actual': f'[*] ({len(values)} items all passed)',
                    'passed': True,
                    'message': f'{operator} check passed for all {len(values)} items',
                })
            else:
                failed_vals = [values[i] for i in failed_indices[:3]]
                results.append({
                    'field': field,
                    'operator': operator,
                    'expected': expected,
                    'actual': f'Failed at indices {failed_indices[:5]}, values: {failed_vals}',
                    'passed': False,
                    'message': f'{operator} check failed for {len(failed_indices)}/{len(values)} items',
                })
            continue

        result = evaluate_single(actual, operator, expected)
        results.append({
            'field': field,
            'operator': operator,
            'expected': expected,
            'actual': actual,
            'passed': result['passed'],
            'message': result['message'],
        })

    return results
