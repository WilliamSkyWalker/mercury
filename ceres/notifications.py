import json
import logging
import requests

logger = logging.getLogger(__name__)




def send_feishu_notification(execution, webhook_url):
    """Send a Feishu webhook notification for a test execution result."""
    if not webhook_url:
        return

    from django.conf import settings

    base_url = settings.DOMAIN.rstrip('/')
    report_path = execution.report_url or f"/executions/{execution.id}"
    report_link = f"{base_url}{report_path}"

    color = 'red' if execution.status == 'failed' else 'green'
    title = f"Test {'Failed' if execution.status == 'failed' else 'Passed'}: {execution.task_id}"

    env_name = execution.env.name if execution.env else 'N/A'
    plan_name = execution.testplan.name if execution.testplan else 'Ad-hoc'

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": color,
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**Plan:** {plan_name}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**Env:** {env_name}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**Pass Rate:** {execution.pass_rate}%"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**Duration:** {execution.duration_ms}ms"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**Total:** {execution.total_cases}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**Failed:** {execution.failed_cases}"}},
                        *([{"is_short": True, "text": {"tag": "lark_md", "content": f"**Skipped:** {execution.skipped_cases}"}}] if execution.skipped_cases else []),
                    ],
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "View Report"},
                            "url": report_link,
                            "type": "primary",
                        }
                    ],
                },
            ],
        },
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Feishu notification failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Feishu notification error: {e}")


def send_slow_execution_warning(execution, webhook_url, elapsed_seconds):
    """Send an early warning when a scheduled execution is running far longer than expected."""
    if not webhook_url:
        return

    from django.conf import settings

    base_url = (getattr(settings, 'DOMAIN', '') or '').rstrip('/')
    report_link = f"{base_url}/executions/{execution.id}"

    plan_name = execution.testplan.name if execution.testplan else 'Ad-hoc'
    env_name = execution.env.name if execution.env else 'N/A'
    elapsed_min = round(elapsed_seconds / 60, 1)

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"执行超时预警: {plan_name}"},
                "template": "orange",
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**Plan:** {plan_name}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**Env:** {env_name}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**已运行:** {elapsed_min} 分钟"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**Total:** {execution.total_cases}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**通过:** {execution.passed_cases}"}},
                        {"is_short": True, "text": {"tag": "lark_md", "content": f"**错误:** {execution.error_cases}"}},
                    ],
                },
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "执行时间异常，疑似大面积接口超时，请排查服务状态"},
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "查看执行详情"},
                            "url": report_link,
                            "type": "primary",
                        }
                    ],
                },
            ],
        },
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Feishu slow-exec warning failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Feishu slow-exec warning error: {e}")


def send_flashcat_alert(execution, event_status='Critical'):
    """Send a Flashcat custom-event push for a test execution.

    Triggers the phone-call escalation policy configured on the Flashcat side
    when `event_status='Critical'`. Use `event_status='Info'` for recovery.

    The webhook URL comes from settings.FLASHCAT_WEBHOOK (env.json `flashcat`).
    Caller is responsible for the higher-level eligibility checks (project,
    trigger type, mute, etc.).
    """
    from django.conf import settings

    webhook_url = getattr(settings, 'FLASHCAT_WEBHOOK', '') or ''
    if not webhook_url:
        logger.info('Flashcat alert skipped: no FLASHCAT_WEBHOOK configured')
        return

    base_url = settings.DOMAIN.rstrip('/') if getattr(settings, 'DOMAIN', '') else ''
    report_path = execution.report_url or f"/executions/{execution.id}"
    report_link = f"{base_url}{report_path}" if base_url else report_path

    plan_name = execution.testplan.name if execution.testplan else 'Ad-hoc'
    env_name = execution.env.name if execution.env else 'N/A'
    project_name = execution.project.name if execution.project_id else 'N/A'

    # Voice-friendly Chinese title: prefix with the testplan's project name
    # so listeners can tell which project is alerting. Keep everything else
    # in Chinese so phone TTS reads naturally.
    if event_status == 'Critical':
        voice_title = f"{project_name}测试告警，{execution.failed_cases}个用例失败，请查看详情"
    else:
        voice_title = f"{project_name}测试恢复，全部用例通过"

    payload = {
        # alert_key intentionally unique per execution: the user wants every
        # failed run to ring fresh (no Flashcat-side dedup).
        "alert_key": f"mercury-{execution.task_id}",
        "event_status": event_status,
        "title_rule": voice_title,
        "description": (
            f"Project: {project_name}\n"
            f"Plan: {plan_name}\n"
            f"Env: {env_name}\n"
            f"Status: {execution.status}\n"
            f"Pass rate: {execution.pass_rate}% ({execution.passed_cases}/{execution.total_cases})\n"
            f"Failed: {execution.failed_cases}, Errors: {execution.error_cases}, Skipped: {execution.skipped_cases}\n"
            f"Duration: {execution.duration_ms}ms\n"
            f"Report: {report_link}"
        ),
        "labels": {
            "service": "mercury",
            "project": project_name,
            "plan": plan_name,
            "env": env_name,
            "task_id": execution.task_id,
        },
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        if resp.status_code >= 300:
            logger.warning(f"Flashcat alert failed: {resp.status_code} {resp.text}")
        else:
            logger.info(f"Flashcat alert sent ({event_status}) for {execution.task_id}")
    except Exception as e:
        logger.error(f"Flashcat alert error: {e}")
