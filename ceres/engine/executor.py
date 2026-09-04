import re
import time
import json
import logging
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

from ceres.engine.variables import VariableContext
from ceres.engine.assertions import evaluate_assertions
from ceres.engine.scripts import execute_script, RequestProxy, ResponseProxy
from ceres.engine.dependency import build_layers
from ceres.engine.ws_executor import run_ws_case

logger = logging.getLogger(__name__)


class TestExecutor:
    """Executes test cases with variable resolution, scripting, and assertions."""

    def __init__(self, env=None, env_name=None):
        env_vars = env.variables if env else {}
        self.env = env
        self.variable_context = VariableContext(env_vars)
        self.env_name = env_name or (env.name if env else '')

    def _run_single_case_with_timeout(self, testcase):
        """Run a single case with a hard timeout wrapper (for serial execution)."""
        case_timeout = (getattr(testcase, 'timeout', 30) or 30) + 30
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.run_single_case, testcase)
            try:
                return future.result(timeout=case_timeout)
            except TimeoutError:
                logger.error(f"Case '{testcase.case_name}' timed out after {case_timeout}s")
                return {
                    'case_name': testcase.case_name,
                    'testcase_id': testcase.id,
                    'status': 'error',
                    'request': {},
                    'response': {},
                    'assertion_results': [],
                    'extracted_variables': {},
                    'error_message': f'Case execution timed out after {case_timeout}s',
                    'duration_ms': case_timeout * 1000,
                }

    def run_single_case(self, testcase):
        """Execute a single test case and return the result dict.

        Flow: pre-script -> resolve vars -> HTTP request -> assertions -> post-script
        """
        start = time.time()
        result = {
            'case_name': testcase.case_name,
            'testcase_id': testcase.id,
            'status': 'passed',
            'request': {},
            'response': {},
            'assertion_results': [],
            'extracted_variables': {},
            'error_message': '',
            'duration_ms': 0,
        }

        temp_dirs = []
        try:
            # Build request headers from structured list
            raw_headers = {}
            if isinstance(testcase.headers, list):
                for h in testcase.headers:
                    if h.get('enabled', True) and h.get('key'):
                        raw_headers[h['key']] = h.get('value', '')
            elif isinstance(testcase.headers, dict):
                raw_headers = testcase.headers

            # Build query params from structured list
            raw_params = {}
            if isinstance(testcase.params, list):
                for p in testcase.params:
                    if p.get('enabled', True) and p.get('key'):
                        raw_params[p['key']] = p.get('value', '')
            elif isinstance(testcase.params, dict):
                raw_params = testcase.params

            # Pre-request script
            req_proxy = RequestProxy(
                headers=raw_headers,
                body=testcase.body,
                url=testcase.url,
                method=testcase.method,
            )
            if testcase.pre_request_script:
                script_result = execute_script(
                    testcase.pre_request_script,
                    self.variable_context,
                    env_name=self.env_name,
                    request_proxy=req_proxy,
                    case_name=testcase.case_name,
                    phase='pre',
                )
                if not script_result['success']:
                    result['status'] = 'error'
                    result['error_message'] = f"Pre-script error: {script_result['error']}"
                    result['duration_ms'] = int((time.time() - start) * 1000)
                    return result
                if script_result.get('skipped'):
                    result['status'] = 'skipped'
                    result['error_message'] = script_result.get('skip_reason', '') or 'Skipped by pre-request script'
                    result['request'] = {
                        'method': testcase.method,
                        'url': testcase.url,
                        'headers': req_proxy.headers,
                        'params': raw_params,
                        'body': req_proxy.body,
                    }
                    result['duration_ms'] = int((time.time() - start) * 1000)
                    return result
                raw_headers = req_proxy.headers

            # Resolve variables in URL, headers, params, body
            url = self.variable_context.resolve(req_proxy.url)
            headers = self.variable_context.resolve_dict(raw_headers)
            params = self.variable_context.resolve_dict(raw_params)

            # WebSocket cases dispatch here once the URL is resolved.
            # pre-script may have rewritten req.url, so this check has to come
            # after variable resolution rather than off the raw model field.
            if url.lower().startswith(('ws://', 'wss://')):
                return self._run_ws_case(testcase, url, headers, start, result)

            # Build request body (pre-script may have modified req.body)
            body_data = None
            if testcase.body_type == 'json' and req_proxy.body:
                body_content = req_proxy.body
                if isinstance(body_content, dict):
                    body_content = self.variable_context.resolve_dict(body_content)
                    body_data = json.dumps(body_content)
                elif isinstance(body_content, list):
                    body_content = self.variable_context.resolve_list(body_content)
                    body_data = json.dumps(body_content)
                elif isinstance(body_content, str):
                    body_data = self.variable_context.resolve(body_content)
                    # Replace unresolved {{var}} placeholders with null for valid JSON
                    body_data = re.sub(r'\{\{\w+\}\}', 'null', body_data)
                    # Fix empty resolved values that break JSON (e.g. "key": ,)
                    body_data = re.sub(r':\s*,', ': null,', body_data)
                    body_data = re.sub(r':\s*\}', ': null}', body_data)
                else:
                    body_data = json.dumps(body_content)
                if 'Content-Type' not in headers and 'content-type' not in headers:
                    headers['Content-Type'] = 'application/json'
            elif testcase.body_type == 'form' and req_proxy.body:
                body_content = req_proxy.body
                if isinstance(body_content, dict):
                    body_data = self.variable_context.resolve_dict(body_content)
                elif isinstance(body_content, list):
                    body_data = self.variable_context.resolve_list(body_content)
                elif isinstance(body_content, str):
                    body_data = self.variable_context.resolve(body_content)
            elif testcase.body_type == 'raw' and req_proxy.body:
                body_data = self.variable_context.resolve(
                    req_proxy.body if isinstance(req_proxy.body, str) else json.dumps(req_proxy.body)
                )

            # Build multipart files dict if body_type is multipart
            files_data = None
            temp_dirs = []
            if testcase.body_type == 'multipart' and req_proxy.body:
                import os
                import tempfile
                from ceres.engine.s3_utils import download_testdata
                files_data = {}
                multipart_fields = {}
                body_content = req_proxy.body if isinstance(req_proxy.body, dict) else {}
                testcase_files = getattr(testcase, 'files', None) or []
                for field_key, field_val in body_content.items():
                    field_val_str = self.variable_context.resolve(str(field_val))
                    if field_val_str.startswith('@file(') and field_val_str.endswith(')'):
                        # All files must be stored in S3 via testcase.files
                        file_name = field_val_str[6:-1]
                        # Strip s3:// prefix if present
                        if file_name.startswith('s3://'):
                            file_name = file_name[5:]
                        file_meta = next((f for f in testcase_files if f.get('name') == file_name), None)
                        if file_meta:
                            tmp_dir = tempfile.mkdtemp(prefix='mercury_')
                            temp_dirs.append(tmp_dir)
                            local_path = os.path.join(tmp_dir, file_name)
                            download_testdata(file_meta['s3_key'], local_path)
                            files_data[field_key] = (
                                file_name,
                                open(local_path, 'rb'),
                                file_meta.get('content_type', 'application/octet-stream'),
                            )
                        else:
                            logger.warning(f"File '{file_name}' not found in testcase.files, "
                                           f"upload it via POST /api/testcases/{testcase.id}/upload-file/")
                            multipart_fields[field_key] = field_val_str
                    else:
                        multipart_fields[field_key] = field_val_str
                body_data = multipart_fields or None
                # Remove content-type header so requests sets multipart boundary
                headers = {k: v for k, v in headers.items()
                           if k.lower() != 'content-type'}

            # Remove None-valued headers
            headers = {k: v for k, v in headers.items() if v is not None}

            # Mark mercury-originated requests so nginx logs can be filtered
            # (coverage_monitor / latency_monitor exclude this UA).
            if not any(k.lower() == 'user-agent' for k in headers):
                headers['User-Agent'] = 'Mercury-Monitor/1.0'

            result['request'] = {
                'method': testcase.method,
                'url': url,
                'headers': headers,
                'params': params,
                'body': body_data,
            }

            # Execute HTTP request (stream=True to avoid downloading large bodies)
            req_timeout = getattr(testcase, 'timeout', 30) or 30
            req_start = time.time()
            response = requests.request(
                method=testcase.method,
                url=url,
                headers=headers,
                params=params if params else None,
                data=body_data if testcase.body_type not in ('json',) else None,
                json=json.loads(body_data) if testcase.body_type == 'json' and body_data and isinstance(body_data, str) else None,
                files=files_data if files_data else None,
                timeout=(10, req_timeout),
                stream=True,
            )
            req_duration = int((time.time() - req_start) * 1000)

            # Read response body with size limit (skip large binary like audio/video)
            content_type = response.headers.get('content-type', '')
            is_binary = any(t in content_type for t in ('audio/', 'video/', 'image/', 'octet-stream'))
            first_chunk_ms = None
            last_chunk_ms = None
            raw_text = ''
            if is_binary:
                response_body = f'[Binary: {content_type}, {response.headers.get("content-length", "unknown")} bytes]'
                response.close()
            else:
                # Read up to 1MB with total timeout
                max_bytes = 1024 * 1024
                chunks = []
                total = 0
                try:
                    for chunk in response.iter_content(chunk_size=8192):
                        chunks.append(chunk)
                        total += len(chunk)
                        if chunk:
                            now_ms = int((time.time() - req_start) * 1000)
                            if first_chunk_ms is None:
                                first_chunk_ms = now_ms
                            last_chunk_ms = now_ms
                        if total >= max_bytes or time.time() - req_start > req_timeout:
                            break
                except Exception:
                    pass
                response.close()
                raw_text = b''.join(chunks).decode('utf-8', errors='replace')
                try:
                    response_body = json.loads(raw_text)
                except (json.JSONDecodeError, ValueError):
                    response_body = raw_text

            result['response'] = {
                'status': response.status_code,
                'headers': dict(response.headers),
                'body': response_body,
                'duration_ms': req_duration,
            }

            if 'text/event-stream' in content_type.lower() and first_chunk_ms is not None:
                token_count = sum(
                    1 for line in raw_text.splitlines() if line.startswith('data:')
                )
                stream_ms = (last_chunk_ms or 0) - first_chunk_ms
                result['response']['stream_metrics'] = {
                    'first_token_ms': first_chunk_ms,
                    'last_token_ms': last_chunk_ms,
                    'token_count': token_count,
                    'tokens_per_sec': round(token_count * 1000.0 / stream_ms, 2)
                        if stream_ms > 0 and token_count > 0 else None,
                }

            # Evaluate assertions
            if testcase.assertions:
                assertion_list = testcase.assertions if isinstance(testcase.assertions, list) else []
                assertion_results = evaluate_assertions(
                    assertion_list,
                    response.status_code,
                    response_body,
                    dict(response.headers),
                    response_duration_ms=req_duration,
                )
                result['assertion_results'] = assertion_results
                if any(not a['passed'] for a in assertion_results):
                    result['status'] = 'failed'

            # Post-response script
            if testcase.post_request_script:
                res_proxy = ResponseProxy(
                    status=response.status_code,
                    body=response_body,
                    headers=dict(response.headers),
                )
                script_result = execute_script(
                    testcase.post_request_script,
                    self.variable_context,
                    env_name=self.env_name,
                    response_proxy=res_proxy,
                    case_name=testcase.case_name,
                    phase='post',
                )
                if not script_result['success']:
                    result['error_message'] = f"Post-script error: {script_result['error']}"

            result['extracted_variables'] = self.variable_context.get_extracted_variables()

        except requests.RequestException as e:
            result['status'] = 'error'
            result['error_message'] = f"HTTP request error: {str(e)}"
        except Exception as e:
            result['status'] = 'error'
            result['error_message'] = f"Execution error: {str(e)}"
        finally:
            # Clean up temp dirs from S3 file downloads
            if temp_dirs:
                import shutil
                for d in temp_dirs:
                    shutil.rmtree(d, ignore_errors=True)

        # Prefer the HTTP-only timing (matches `curl` perception). Fall back to
        # the total wall-clock if the request never reached the network stage
        # (e.g., pre-script crashed) so we still have something to display.
        http_ms = result.get('response', {}).get('duration_ms')
        result['duration_ms'] = http_ms if http_ms is not None else int((time.time() - start) * 1000)
        return result

    def _run_ws_case(self, testcase, url, headers, start, result):
        """Run a WebSocket case. Called from run_single_case after URL resolution.

        Mirrors the HTTP path's return shape so downstream reporting/scripting
        treats both protocols the same.
        """
        ws_steps = getattr(testcase, 'ws_steps', None) or []
        if not ws_steps:
            result['status'] = 'error'
            result['error_message'] = (
                'WebSocket URL but ws_steps is empty. Add at least one send/recv step.'
            )
            result['request'] = {'method': 'WS', 'url': url, 'headers': headers, 'params': {}, 'body': None}
            result['duration_ms'] = int((time.time() - start) * 1000)
            return result

        headers = {k: v for k, v in (headers or {}).items() if v is not None}
        # User-Agent for consistency with HTTP path.
        if not any(k.lower() == 'user-agent' for k in headers):
            headers['User-Agent'] = 'Mercury-Monitor/1.0'

        result['request'] = {
            'method': 'WS',
            'url': url,
            'headers': headers,
            'params': {},
            'body': ws_steps,
        }

        case_timeout = getattr(testcase, 'timeout', 30) or 30
        ws_result = run_ws_case(
            url=url,
            headers=headers,
            steps=ws_steps,
            variable_context=self.variable_context,
            overall_timeout_s=case_timeout,
        )

        messages = ws_result['body']
        # Synthesize a response dict shaped like HTTP so assertions / scripts
        # / persistence layers don't need a separate code path. body == messages
        # so `res.body[*].field` works; `res.messages.*` is a documented alias
        # plumbed via resolve_field.
        # Persisted into ExecutionCaseResult.stream_metrics — same JSONB column
        # we already use for SSE metrics. Distinguishable by the 'protocol' tag.
        ws_metadata = {
            'protocol': 'ws',
            'handshake_status': ws_result['handshake_status'],
            'close_code': ws_result['close_code'],
            'close_reason': ws_result['close_reason'],
            'message_count': len(messages),
            'messages_truncated': ws_result['messages_truncated'],
            'error': ws_result['error'],
            # Full directional conversation log (send + recv + meta entries
            # with t_ms timestamps). UI uses this to render the Transcript view.
            'transcript': ws_result.get('transcript', []),
            'transcript_truncated': ws_result.get('transcript_truncated', False),
        }
        result['response'] = {
            'status': ws_result['status'],
            'headers': ws_result['headers'],
            'body': messages,
            'duration_ms': ws_result['duration_ms'],
            'stream_metrics': ws_metadata,
            'ws': ws_metadata,  # alias kept in-memory for clarity in scripts/UI
        }

        # Transport-level failure → mark error before assertions even run.
        if ws_result['error'] and ws_result['handshake_status'] is None:
            result['status'] = 'error'
            result['error_message'] = ws_result['error']
            result['duration_ms'] = ws_result['duration_ms']
            return result

        # Assertions — pass extras so res.messages / res.handshakeStatus /
        # res.closeCode / res.duration_ms work on the WS result shape.
        if testcase.assertions:
            assertion_list = testcase.assertions if isinstance(testcase.assertions, list) else []
            extras = {
                'messages': messages,
                'handshakeStatus': ws_result['handshake_status'],
                'closeCode': ws_result['close_code'],
                'closeReason': ws_result['close_reason'],
                'duration_ms': ws_result['duration_ms'],
                'messagesTruncated': ws_result['messages_truncated'],
            }
            assertion_results = evaluate_assertions(
                assertion_list,
                ws_result['status'],
                messages,
                ws_result['headers'],
                response_duration_ms=ws_result['duration_ms'],
                extras=extras,
            )
            result['assertion_results'] = assertion_results
            if any(not a['passed'] for a in assertion_results):
                result['status'] = 'failed'

        # Post-response script — same surface as HTTP, plus ws-specific fields.
        if testcase.post_request_script:
            res_proxy = ResponseProxy(
                status=ws_result['status'],
                body=messages,
                headers=ws_result['headers'],
                ws_handshake_status=ws_result['handshake_status'],
                ws_close_code=ws_result['close_code'],
                ws_close_reason=ws_result['close_reason'],
                ws_messages=messages,
                ws_duration_ms=ws_result['duration_ms'],
                ws_truncated=ws_result['messages_truncated'],
            )
            script_result = execute_script(
                testcase.post_request_script,
                self.variable_context,
                env_name=self.env_name,
                response_proxy=res_proxy,
                case_name=testcase.case_name,
                phase='post',
            )
            if not script_result['success']:
                result['error_message'] = f"Post-script error: {script_result['error']}"

        # If a recv timeout or mid-stream error occurred but assertions passed,
        # still surface the error in error_message so it shows up in the UI.
        if ws_result['error'] and not result['error_message']:
            result['error_message'] = ws_result['error']
            if result['status'] == 'passed':
                result['status'] = 'failed'

        result['extracted_variables'] = self.variable_context.get_extracted_variables()
        result['duration_ms'] = ws_result['duration_ms']
        return result

    def execute_cases_async(self, execution_id, testcases):
        """Execute a list of cases sequentially and save results. Runs in a thread."""
        self._run_execution(execution_id, testcases, testplan=None)

    def execute_plan_async(self, execution_id, testcases, testplan=None):
        """Execute a test plan's cases and save results. Runs in a thread."""
        self._run_execution(execution_id, testcases, testplan)

    def _run_execution(self, execution_id, testcases, testplan=None):
        from ceres.models import ExecutionRecord

        start = time.time()
        stop_event = threading.Event()

        if testplan and getattr(testplan, 'notify_on_failure', False) and getattr(testplan, 'feishu_webhook', ''):
            def _watchdog():
                # Phase 1 — 5 min: send early warning
                time.sleep(300)
                if stop_event.is_set():
                    return
                try:
                    from ceres.notifications import send_slow_execution_warning
                    exec_record = ExecutionRecord.all_objects.filter(id=execution_id, status='running').first()
                    if exec_record:
                        send_slow_execution_warning(exec_record, testplan.feishu_webhook, 300)
                    else:
                        return
                except Exception as _e:
                    logger.error(f"Watchdog warning error for execution {execution_id}: {_e}")

                # Phase 2 — 10 min total: interrupt the execution
                time.sleep(300)
                if not stop_event.is_set():
                    stop_event.set()
                    logger.warning(f"Execution {execution_id} timed out after 10 min, interrupting")

            threading.Thread(target=_watchdog, daemon=True).start()

        try:
            self._do_run_execution(execution_id, testcases, testplan, start, stop_event)
        except Exception as e:
            logger.error(f"Execution {execution_id} crashed: {e}", exc_info=True)
            duration = int((time.time() - start) * 1000)
            ExecutionRecord.all_objects.filter(id=execution_id).update(
                status='failed',
                duration_ms=duration,
                error_cases=len(testcases),
            )

    def _save_case_result(self, execution_id, case_result):
        """Save a single case result to DB. Thread-safe."""
        from ceres.models import ExecutionCaseResult

        ExecutionCaseResult.objects.create(
            execution_id=execution_id,
            testcase_id=case_result.get('testcase_id') or None,
            case_name=case_result['case_name'],
            status=case_result['status'],
            request_method=case_result['request'].get('method', ''),
            request_url=case_result['request'].get('url', ''),
            request_headers=case_result['request'].get('headers', {}),
            request_body=case_result['request'].get('body', '') or '',
            response_status=case_result['response'].get('status', 0),
            response_headers=case_result['response'].get('headers', {}),
            response_body=json.dumps(case_result['response'].get('body', ''))
                if not isinstance(case_result['response'].get('body', ''), str)
                else case_result['response'].get('body', ''),
            duration_ms=case_result.get('duration_ms', 0),
            assertion_results=case_result.get('assertion_results', []),
            extracted_variables=case_result.get('extracted_variables', {}),
            error_message=case_result.get('error_message', ''),
            stream_metrics=case_result.get('response', {}).get('stream_metrics'),
        )

    def _do_run_execution(self, execution_id, testcases, testplan, start, stop_event=None):
        from ceres.models import ExecutionRecord

        is_serial = testplan.is_serial if testplan else True

        if is_serial:
            self._do_run_serial(execution_id, testcases, testplan, start, stop_event)
        else:
            self._do_run_parallel(execution_id, testcases, testplan, start, stop_event)

    def _do_run_serial(self, execution_id, testcases, testplan, start, stop_event=None):
        from ceres.models import ExecutionRecord

        passed = 0
        failed = 0
        errors = 0
        skipped = 0

        for testcase in testcases:
            if stop_event and stop_event.is_set():
                break
            case_result = self._run_single_case_with_timeout(testcase)
            self._save_case_result(execution_id, case_result)

            if case_result['status'] == 'passed':
                passed += 1
            elif case_result['status'] == 'failed':
                failed += 1
            elif case_result['status'] == 'skipped':
                skipped += 1
            else:
                errors += 1

            ExecutionRecord.all_objects.filter(id=execution_id).update(
                passed_cases=passed,
                failed_cases=failed,
                error_cases=errors,
                skipped_cases=skipped,
            )

        if stop_event and stop_event.is_set():
            duration = int((time.time() - start) * 1000)
            ExecutionRecord.all_objects.filter(id=execution_id, status='running').update(
                status='interrupted',
                duration_ms=duration,
                passed_cases=passed,
                failed_cases=failed,
                error_cases=errors,
                skipped_cases=skipped,
            )
            logger.warning(f"Execution {execution_id} marked interrupted after {duration // 1000}s")
            return

        self._finalize_execution(execution_id, testcases, testplan, passed, failed, errors, skipped, start)

    def _do_run_parallel(self, execution_id, testcases, testplan, start, stop_event=None):
        from ceres.models import ExecutionRecord

        env_var_names = set(self.variable_context.env_variables.keys())
        layers = build_layers(testcases, env_var_names)

        logger.info(f"Execution {execution_id}: {len(testcases)} cases -> {len(layers)} layers "
                     f"({', '.join(str(len(l)) for l in layers)})")

        passed = 0
        failed = 0
        errors = 0
        skipped = 0
        counters_lock = threading.Lock()

        for layer_idx, layer in enumerate(layers):
            if stop_event and stop_event.is_set():
                break
            if len(layer) == 1:
                # Single case in layer, run directly
                case_result = self.run_single_case(layer[0])
                self._save_case_result(execution_id, case_result)

                if case_result['status'] == 'passed':
                    passed += 1
                elif case_result['status'] == 'failed':
                    failed += 1
                elif case_result['status'] == 'skipped':
                    skipped += 1
                else:
                    errors += 1

                ExecutionRecord.all_objects.filter(id=execution_id).update(
                    passed_cases=passed,
                    failed_cases=failed,
                    error_cases=errors,
                    skipped_cases=skipped,
                )
            else:
                # Multiple cases, run in parallel
                max_workers = min(len(layer), 8)
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    future_to_case = {
                        pool.submit(self.run_single_case, tc): tc
                        for tc in layer
                    }
                    for future in as_completed(future_to_case):
                        tc = future_to_case[future]
                        case_timeout = (getattr(tc, 'timeout', 30) or 30) + 30  # req timeout + 30s buffer
                        try:
                            case_result = future.result(timeout=case_timeout)
                        except TimeoutError:
                            logger.error(f"Case '{tc.case_name}' timed out after {case_timeout}s in layer {layer_idx}")
                            case_result = {
                                'case_name': tc.case_name,
                                'testcase_id': tc.id,
                                'status': 'error',
                                'request': {},
                                'response': {},
                                'assertion_results': [],
                                'extracted_variables': {},
                                'error_message': f'Case execution timed out after {case_timeout}s',
                                'duration_ms': case_timeout * 1000,
                            }
                        self._save_case_result(execution_id, case_result)

                        with counters_lock:
                            if case_result['status'] == 'passed':
                                passed += 1
                            elif case_result['status'] == 'failed':
                                failed += 1
                            elif case_result['status'] == 'skipped':
                                skipped += 1
                            else:
                                errors += 1

                            ExecutionRecord.all_objects.filter(id=execution_id).update(
                                passed_cases=passed,
                                failed_cases=failed,
                                error_cases=errors,
                                skipped_cases=skipped,
                            )

        if stop_event and stop_event.is_set():
            duration = int((time.time() - start) * 1000)
            ExecutionRecord.all_objects.filter(id=execution_id, status='running').update(
                status='interrupted',
                duration_ms=duration,
                passed_cases=passed,
                failed_cases=failed,
                error_cases=errors,
                skipped_cases=skipped,
            )
            logger.warning(f"Execution {execution_id} marked interrupted after {duration // 1000}s")
            return

        self._finalize_execution(execution_id, testcases, testplan, passed, failed, errors, skipped, start)

    def _finalize_execution(self, execution_id, testcases, testplan, passed, failed, errors, skipped, start):
        from ceres.models import ExecutionRecord

        total = len(testcases)
        duration = int((time.time() - start) * 1000)
        # Skipped cases count as passed for pass-rate purposes.
        pass_rate = round(((passed + skipped) / total) * 100, 2) if total > 0 else 0
        final_status = 'passed' if failed == 0 and errors == 0 else 'failed'

        ExecutionRecord.all_objects.filter(id=execution_id).update(
            status=final_status,
            passed_cases=passed,
            failed_cases=failed,
            error_cases=errors,
            skipped_cases=skipped,
            pass_rate=pass_rate,
            duration_ms=duration,
            report_url=f'/executions/{execution_id}',
        )

        if final_status == 'failed' and testplan and testplan.notify_on_failure and testplan.feishu_webhook:
            try:
                from ceres.notifications import send_feishu_notification
                execution = ExecutionRecord.all_objects.get(id=execution_id)
                send_feishu_notification(execution, testplan.feishu_webhook)
            except Exception as e:
                logger.error(f"Notification failed: {e}")

        # Flashcat phone alert: scheduled trigger only, project must be enabled,
        # phone_on_failure on, not muted. Critical on fail; Info on recovery
        # (current passed run preceded by a failed scheduled run of same plan).
        try:
            self._maybe_send_flashcat(execution_id, testplan, final_status)
        except Exception as e:
            logger.error(f"Flashcat alert dispatch error: {e}")

        if final_status == 'failed' and testplan and testplan.retry_count > 0:
            self._handle_retry(execution_id, testcases, testplan)

    def _maybe_send_flashcat(self, execution_id, testplan, final_status):
        from django.conf import settings
        from ceres.models import ExecutionRecord
        from ceres.notifications import send_flashcat_alert

        # Skip everything if the global Flashcat webhook isn't configured —
        # avoids a needless prev-execution DB lookup on Info recovery path too.
        if not (getattr(settings, 'FLASHCAT_WEBHOOK', '') or '').strip():
            return

        if not testplan:
            return
        if not testplan.phone_on_failure or testplan.phone_muted:
            return

        execution = ExecutionRecord.all_objects.get(id=execution_id)

        # Manual / API runs never page; only scheduled cron does.
        if execution.trigger_type != 'scheduled':
            return

        if final_status == 'failed':
            send_flashcat_alert(execution, event_status='Critical')
            return

        # final_status == 'passed' → recovery if previous scheduled exec failed
        prev = (
            ExecutionRecord.all_objects
            .filter(testplan_id=testplan.id, trigger_type='scheduled')
            .exclude(id=execution_id)
            .order_by('-id')
            .first()
        )
        if prev and prev.status == 'failed':
            send_flashcat_alert(execution, event_status='Info')

    def _handle_retry(self, execution_id, testcases, testplan):
        from ceres.models import ExecutionRecord
        import threading
        from datetime import datetime

        execution = ExecutionRecord.all_objects.get(id=execution_id)
        retry_match = __import__('re').search(r'-retry(\d+)$', execution.task_id)
        current_retry = int(retry_match.group(1)) if retry_match else 0

        if current_retry >= testplan.retry_count:
            return

        next_retry = current_retry + 1
        base_id = execution.task_id.split('-retry')[0] if '-retry' in execution.task_id else execution.task_id
        new_task_id = f"{base_id}-retry{next_retry}"

        new_execution = ExecutionRecord.objects.create(
            task_id=new_task_id,
            testplan=testplan,
            env=execution.env,
            env_snapshot=execution.env_snapshot,
            trigger_type=execution.trigger_type,
            status='running',
            total_cases=len(testcases),
        )

        new_executor = TestExecutor(env=execution.env, env_name=self.env_name)
        thread = threading.Thread(
            target=new_executor._run_execution,
            args=(new_execution.id, testcases, testplan),
        )
        thread.start()
