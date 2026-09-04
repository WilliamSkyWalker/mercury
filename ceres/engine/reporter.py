import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Test Report - {task_id}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; color: #333; padding: 20px; }}
  .container {{ max-width: 1200px; margin: 0 auto; }}
  .header {{ background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .header h1 {{ font-size: 20px; margin-bottom: 12px; }}
  .summary {{ display: flex; gap: 24px; flex-wrap: wrap; }}
  .summary-item {{ text-align: center; }}
  .summary-item .value {{ font-size: 28px; font-weight: bold; }}
  .summary-item .label {{ font-size: 12px; color: #888; margin-top: 4px; }}
  .passed .value {{ color: #52c41a; }}
  .failed .value {{ color: #ff4d4f; }}
  .error .value {{ color: #faad14; }}
  .case-list {{ background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  .case-item {{ padding: 16px 24px; border-bottom: 1px solid #f0f0f0; }}
  .case-item:last-child {{ border-bottom: none; }}
  .case-header {{ display: flex; align-items: center; gap: 12px; cursor: pointer; }}
  .case-header .method {{ background: #1890ff; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
  .case-header .method.post {{ background: #52c41a; }}
  .case-header .method.put {{ background: #faad14; }}
  .case-header .method.delete {{ background: #ff4d4f; }}
  .badge {{ padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
  .badge.passed {{ background: #f6ffed; color: #52c41a; }}
  .badge.failed {{ background: #fff2f0; color: #ff4d4f; }}
  .badge.error {{ background: #fffbe6; color: #faad14; }}
  .badge.skipped {{ background: #f5f5f5; color: #888; }}
  .case-detail {{ display: none; margin-top: 12px; padding: 12px; background: #fafafa; border-radius: 4px; font-size: 13px; }}
  .case-detail.open {{ display: block; }}
  .case-detail pre {{ white-space: pre-wrap; word-break: break-all; background: #f0f0f0; padding: 8px; border-radius: 4px; margin-top: 8px; max-height: 300px; overflow: auto; }}
  .assertion-list {{ margin-top: 8px; }}
  .assertion {{ padding: 4px 0; display: flex; gap: 8px; }}
  .assertion .icon {{ width: 16px; }}
  .duration {{ color: #888; font-size: 12px; margin-left: auto; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Test Report</h1>
    <p style="color:#888;margin-bottom:16px;">Task: {task_id} | Env: {env_name} | {timestamp}</p>
    <div class="summary">
      <div class="summary-item"><div class="value">{total}</div><div class="label">Total</div></div>
      <div class="summary-item passed"><div class="value">{passed}</div><div class="label">Passed</div></div>
      <div class="summary-item failed"><div class="value">{failed}</div><div class="label">Failed</div></div>
      <div class="summary-item error"><div class="value">{errors}</div><div class="label">Errors</div></div>
      <div class="summary-item"><div class="value">{skipped}</div><div class="label">Skipped</div></div>
      <div class="summary-item"><div class="value">{pass_rate}%</div><div class="label">Pass Rate</div></div>
      <div class="summary-item"><div class="value">{duration}ms</div><div class="label">Duration</div></div>
    </div>
  </div>
  <div class="case-list">
    {case_items}
  </div>
</div>
<script>
document.querySelectorAll('.case-header').forEach(h => {{
  h.addEventListener('click', () => {{
    h.nextElementSibling.classList.toggle('open');
  }});
}});
</script>
</body>
</html>"""

CASE_ITEM_TEMPLATE = """
<div class="case-item">
  <div class="case-header">
    <span class="method {method_lower}">{method}</span>
    <span>{case_name}</span>
    <span class="badge {status}">{status}</span>
    <span class="duration">{duration_ms}ms</span>
  </div>
  <div class="case-detail">
    <strong>URL:</strong> {url}<br>
    <strong>Status:</strong> {response_status}
    {assertions_html}
    {error_html}
    <strong>Response:</strong>
    <pre>{response_body}</pre>
  </div>
</div>"""


def generate_report(execution):
    """Generate HTML report for an execution and save locally. Returns file path."""
    from ceres.models import ExecutionCaseResult

    case_results = ExecutionCaseResult.objects.filter(execution=execution).order_by('id')

    case_items = []
    for cr in case_results:
        assertions_html = ''
        if cr.assertion_results:
            assertions_html = '<div class="assertion-list"><strong>Assertions:</strong>'
            for a in cr.assertion_results:
                icon = '&#10004;' if a.get('passed') else '&#10008;'
                color = '#52c41a' if a.get('passed') else '#ff4d4f'
                assertions_html += (
                    f'<div class="assertion">'
                    f'<span class="icon" style="color:{color}">{icon}</span>'
                    f'<span>{a.get("field", "")} {a.get("operator", "")} {a.get("expected", "")}</span>'
                    f'</div>'
                )
            assertions_html += '</div>'

        error_html = ''
        if cr.error_message:
            error_html = f'<p style="color:#ff4d4f"><strong>Error:</strong> {cr.error_message}</p>'

        resp_body = cr.response_body
        if isinstance(resp_body, str) and len(resp_body) > 2000:
            resp_body = resp_body[:2000] + '...(truncated)'

        case_items.append(CASE_ITEM_TEMPLATE.format(
            method=cr.request_method,
            method_lower=cr.request_method.lower(),
            case_name=cr.case_name,
            status=cr.status,
            duration_ms=cr.duration_ms,
            url=cr.request_url,
            response_status=cr.response_status,
            assertions_html=assertions_html,
            error_html=error_html,
            response_body=resp_body,
        ))

    html = HTML_TEMPLATE.format(
        task_id=execution.task_id,
        env_name=execution.env.name if execution.env else 'N/A',
        timestamp=execution.created_at.strftime('%Y-%m-%d %H:%M:%S') if execution.created_at else '',
        total=execution.total_cases,
        passed=execution.passed_cases,
        failed=execution.failed_cases,
        errors=execution.error_cases,
        skipped=execution.skipped_cases,
        pass_rate=execution.pass_rate,
        duration=execution.duration_ms,
        case_items=''.join(case_items),
    )

    # Save locally
    from django.conf import settings
    report_dir = Path(settings.BASE_DIR) / 'templates' / 'static'
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f'{execution.task_id}.html'
    report_path.write_text(html, encoding='utf-8')

    # Upload to S3
    report_url = ''
    try:
        report_url = upload_to_s3(str(report_path), execution.task_id)
    except Exception as e:
        logger.warning(f"S3 upload failed, local report available: {e}")

    return report_url or f'/api/showreport/{execution.task_id}'


def upload_to_s3(file_path, task_id):
    """Upload report to S3. Returns the S3 URL."""
    from django.conf import settings
    import boto3

    env = settings.ENVIRONMENT
    s3_config = None
    try:
        config_path = settings.BASE_DIR / 'mercury' / 'env.json'
        with open(config_path, 'r') as f:
            config = json.load(f)
        s3_config = config.get('S3', {}).get(env)
    except Exception:
        pass

    if not s3_config:
        return ''

    s3_client = boto3.client(
        's3',
        aws_access_key_id=s3_config['aws_access_key_id'],
        aws_secret_access_key=s3_config['aws_secret_access_key'],
    )

    s3_key = f'qa/mercury/{task_id}.html'
    s3_client.upload_file(
        file_path,
        s3_config['bucket_name'],
        s3_key,
        ExtraArgs={'ContentType': 'text/html'},
    )

    return f"s3://{s3_config['bucket_name']}/{s3_key}"
