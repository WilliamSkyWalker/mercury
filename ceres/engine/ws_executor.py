"""WebSocket case executor.

A WS case is a linear script of send/recv/wait/close steps run against a single
long-lived connection. Output mirrors the HTTP executor shape so the rest of the
pipeline (assertions, scripts, reporting) treats it uniformly:

    {
        'status': 0,            # mirrors http status — 101 on successful handshake, 0 on connect fail
        'body': [...],          # list of received messages (parsed JSON when possible)
        'headers': {...},       # handshake response headers (lower-cased keys)
        'duration_ms': int,
        'handshake_status': 101 | None,
        'close_code': int | None,
        'close_reason': str | None,
        'messages_truncated': bool,
        'error': str | None,    # transport-level error (handshake failed, recv timeout, etc.)
    }

Limits:
    - MAX_MESSAGES = 1000 messages kept; further messages are dropped.
    - MAX_BYTES    = 1 MB (sum of message sizes); further messages dropped.
    - DEFAULT_RECV_TIMEOUT_S = 60 — per-step recv timeout when the step omits it.
    - Whole-case budget is enforced by the caller (testcase.timeout via
      ThreadPoolExecutor wrapper in TestExecutor).
"""

import base64
import json
import logging
import time

logger = logging.getLogger(__name__)


MAX_MESSAGES = 1000
MAX_BYTES = 1024 * 1024
DEFAULT_RECV_TIMEOUT_S = 60
# Transcript can hold ~2x the message count (sends + recvs + meta entries),
# so we give it a separately tracked budget.
TRANSCRIPT_MAX_ENTRIES = 2000
TRANSCRIPT_MAX_BYTES = 2 * 1024 * 1024


def _try_parse_json(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError, TypeError):
        return text


def _coerce_payload(payload, payload_type):
    """Return (data, is_binary). data is str for text frames, bytes for binary."""
    if payload_type == 'binary_b64':
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload), True
        return base64.b64decode(payload or ''), True
    if payload_type == 'json':
        if isinstance(payload, str):
            return payload, False
        return json.dumps(payload, ensure_ascii=False), False
    # text / default
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, ensure_ascii=False), False
    return '' if payload is None else str(payload), False


def run_ws_case(url, headers, steps, variable_context, overall_timeout_s):
    """Execute a websocket case.

    Args:
        url: ws:// or wss:// URL, after variable substitution.
        headers: dict of handshake headers (already resolved).
        steps: list of step dicts. Each step is one of:
            {kind: 'send',  payload_type: 'text'|'json'|'binary_b64', payload: ...}
            {kind: 'recv',  timeout_ms?: int}
            {kind: 'wait',  duration_ms: int}
            {kind: 'close', code?: int, reason?: str}
        variable_context: for resolving placeholders inside send payloads.
        overall_timeout_s: hard ceiling for the whole session.

    Returns a dict matching the shape documented at the top of this module.
    """
    try:
        from websockets.sync.client import connect
        from websockets.exceptions import ConnectionClosed, WebSocketException
    except ImportError as e:
        return {
            'status': 0,
            'body': [],
            'headers': {},
            'duration_ms': 0,
            'handshake_status': None,
            'close_code': None,
            'close_reason': None,
            'messages_truncated': False,
            'error': f'websockets library not installed: {e}',
            'transcript': [],
            'transcript_truncated': False,
        }

    start = time.time()
    deadline = start + max(1, overall_timeout_s)

    messages = []
    total_bytes = 0
    truncated = False

    transcript = []
    transcript_bytes = 0
    transcript_truncated = False

    def _now_ms():
        return int((time.time() - start) * 1000)

    def _parse_for_transcript(msg):
        """Same shape as the message cap: parsed JSON for text, base64 stub for binary."""
        if isinstance(msg, (bytes, bytearray)):
            return {
                'type': 'binary',
                'size': len(msg),
                'data_b64': base64.b64encode(msg).decode('ascii'),
            }, len(msg)
        text = msg if isinstance(msg, str) else str(msg)
        return _try_parse_json(text), len(text.encode('utf-8', errors='replace'))

    def _push_transcript(entry, extra_size=0):
        """Append a step entry to the transcript, honoring the 2000/2MB cap.

        Once truncated, every subsequent entry is silently dropped so the
        client can render a "transcript truncated" badge instead of seeing
        an interleaved-but-incomplete log that looks legitimate.
        """
        nonlocal transcript_bytes, transcript_truncated
        if transcript_truncated:
            return
        approx = extra_size + 64  # tiny per-entry framing overhead
        if len(transcript) >= TRANSCRIPT_MAX_ENTRIES or transcript_bytes + approx > TRANSCRIPT_MAX_BYTES:
            transcript_truncated = True
            return
        transcript.append(entry)
        transcript_bytes += approx

    def _record(msg):
        """Add msg to messages[] (for assertions / res.body) AND to transcript."""
        nonlocal total_bytes, truncated
        entry, size = _parse_for_transcript(msg)
        if len(messages) >= MAX_MESSAGES or total_bytes + size > MAX_BYTES:
            truncated = True
        else:
            messages.append(entry)
            total_bytes += size
        _push_transcript({'dir': 'recv', 't_ms': _now_ms(), 'data': entry}, extra_size=size)

    handshake_status = None
    handshake_headers = {}
    close_code = None
    close_reason = None
    error = None
    ws = None

    try:
        ws = connect(
            url,
            additional_headers=headers if headers else None,
            open_timeout=min(10, overall_timeout_s),
            close_timeout=5,
            max_size=MAX_BYTES,
        )
        handshake_status = 101
        _push_transcript({'dir': 'handshake', 't_ms': _now_ms(), 'status': 101})
        # websockets >= 12 exposes the handshake response on the connection
        resp = getattr(ws, 'response', None)
        if resp is not None and getattr(resp, 'headers', None) is not None:
            try:
                handshake_headers = {k.lower(): v for k, v in resp.headers.raw_items()}
            except Exception:
                try:
                    handshake_headers = {k.lower(): v for k, v in dict(resp.headers).items()}
                except Exception:
                    handshake_headers = {}

        for step in steps or []:
            if time.time() > deadline:
                error = f'overall case timeout {overall_timeout_s}s exceeded'
                break

            kind = step.get('kind') if isinstance(step, dict) else None
            if kind == 'send':
                payload = step.get('payload')
                if variable_context is not None:
                    if isinstance(payload, str):
                        payload = variable_context.resolve(payload)
                    elif isinstance(payload, dict):
                        payload = variable_context.resolve_dict(payload)
                    elif isinstance(payload, list):
                        payload = variable_context.resolve_list(payload)
                data, is_binary = _coerce_payload(payload, step.get('payload_type', 'text'))
                ws.send(data)
                # Transcript records the *resolved* payload (post-var substitution).
                # For binary we store the base64 form so the frontend can show
                # something meaningful without dragging raw bytes through JSON.
                if is_binary:
                    sent_entry = {'type': 'binary', 'size': len(data),
                                  'data_b64': base64.b64encode(data).decode('ascii')}
                    sent_size = len(data)
                else:
                    sent_entry = _try_parse_json(data) if isinstance(data, str) else data
                    sent_size = len(data.encode('utf-8', errors='replace')) if isinstance(data, str) else 0
                _push_transcript({'dir': 'send', 't_ms': _now_ms(), 'data': sent_entry},
                                 extra_size=sent_size)

            elif kind == 'recv':
                remaining = deadline - time.time()
                step_timeout = step.get('timeout_ms')
                step_timeout_s = (step_timeout / 1000.0) if step_timeout else DEFAULT_RECV_TIMEOUT_S
                wait_s = max(0.0, min(step_timeout_s, remaining))
                try:
                    msg = ws.recv(timeout=wait_s)
                except TimeoutError:
                    error = f'recv timeout after {step_timeout_s}s'
                    _push_transcript({'dir': 'error', 't_ms': _now_ms(),
                                      'note': error, 'kind': 'recv_timeout'})
                    break
                except ConnectionClosed as e:
                    close_code = getattr(e.rcvd, 'code', None) if getattr(e, 'rcvd', None) else None
                    close_reason = getattr(e.rcvd, 'reason', None) if getattr(e, 'rcvd', None) else None
                    error = f'connection closed during recv (code={close_code})'
                    _push_transcript({'dir': 'close', 't_ms': _now_ms(),
                                      'code': close_code, 'reason': close_reason,
                                      'note': 'server closed mid-recv'})
                    ws = None
                    break
                _record(msg)

            elif kind == 'wait':
                duration_ms = step.get('duration_ms', 0) or 0
                wait_s = max(0.0, min(duration_ms / 1000.0, deadline - time.time()))
                _push_transcript({'dir': 'wait', 't_ms': _now_ms(),
                                  'duration_ms': duration_ms})
                time.sleep(wait_s)

            elif kind == 'close':
                code = step.get('code', 1000)
                reason = step.get('reason', '') or ''
                try:
                    ws.close(code=code, reason=reason)
                except Exception:
                    pass
                close_code = code
                close_reason = reason
                _push_transcript({'dir': 'close', 't_ms': _now_ms(),
                                  'code': code, 'reason': reason})
                ws = None
                break

            else:
                error = f'unknown step kind: {kind!r}'
                _push_transcript({'dir': 'error', 't_ms': _now_ms(), 'note': error})
                break

    except (ConnectionClosed, WebSocketException) as e:
        # Distinguishes handshake failure (no status yet) vs mid-stream loss.
        if handshake_status is None:
            error = f'handshake failed: {e}'
            _push_transcript({'dir': 'error', 't_ms': _now_ms(),
                              'note': error, 'kind': 'handshake'})
        else:
            error = f'websocket error: {e}'
            # If the server sent a close frame, capture it.
            rcvd = getattr(e, 'rcvd', None)
            if rcvd is not None:
                close_code = getattr(rcvd, 'code', close_code)
                close_reason = getattr(rcvd, 'reason', close_reason)
            _push_transcript({'dir': 'error', 't_ms': _now_ms(), 'note': error})
    except OSError as e:
        error = f'connection error: {e}'
        _push_transcript({'dir': 'error', 't_ms': _now_ms(), 'note': error,
                          'kind': 'connect'})
    except Exception as e:
        error = f'ws executor error: {e}'
        _push_transcript({'dir': 'error', 't_ms': _now_ms(), 'note': error})
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
            if close_code is None:
                close_code = 1000

    duration_ms = int((time.time() - start) * 1000)

    return {
        'status': handshake_status or 0,
        'body': messages,
        'headers': handshake_headers,
        'duration_ms': duration_ms,
        'handshake_status': handshake_status,
        'close_code': close_code,
        'close_reason': close_reason,
        'messages_truncated': truncated,
        'error': error,
        'transcript': transcript,
        'transcript_truncated': transcript_truncated,
    }
