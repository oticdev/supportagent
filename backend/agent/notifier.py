import json
import logging
import urllib.request

import config

logger = logging.getLogger(__name__)


def notify_escalation(
    user_name: str,
    user_email: str,
    category: str,
    reason: str,
    appointment_time: str | None,
    escalation_id: str,
) -> None:
    """Sends escalation notification via Slack webhook (if configured)."""
    appointment_str = appointment_time or "Not yet scheduled"

    message = {
        "text": f":rotating_light: *New RelayPay Support Escalation*",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🚨 Support Escalation Required"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Customer:*\n{user_name}"},
                    {"type": "mrkdwn", "text": f"*Email:*\n{user_email}"},
                    {"type": "mrkdwn", "text": f"*Category:*\n{category.title()}"},
                    {"type": "mrkdwn", "text": f"*Appointment:*\n{appointment_str}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Reason:*\n{reason}"},
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": f"Escalation ID: `{escalation_id}`"}
                ],
            },
        ],
    }

    if not config.SLACK_WEBHOOK_URL:
        # Fallback: just log it clearly so it's visible in server output
        logger.warning(
            "SLACK_WEBHOOK_URL not set — escalation logged only.\n"
            "Escalation ID: %s | Customer: %s <%s> | Category: %s | Appointment: %s\nReason: %s",
            escalation_id, user_name, user_email, category, appointment_str, reason,
        )
        return

    try:
        data = json.dumps(message).encode("utf-8")
        req = urllib.request.Request(
            config.SLACK_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
        logger.info("Slack escalation notification sent for %s", escalation_id)
    except Exception:
        logger.exception("Failed to send Slack notification for escalation %s", escalation_id)
