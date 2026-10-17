"""BulkSMS (bulksms.com) sender: JSON REST API with Basic auth (API token id + secret).

Sends to one number or to a BulkSMS phonebook group. Without credentials nothing is sent
(callers report a dry run). COMMS_ALLOWED_RECIPIENTS restricts real sends while testing.
"""

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.config import Settings

TIMEOUT_SECONDS = 20
# Some provider firewalls reject Python's default "Python-urllib" user agent.
USER_AGENT = "FairPrice/0.1 (+https://github.com/BCG-Hackathon/FairPrice)"


class SmsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Sent:
    to: str
    message_id: str | None
    status: str  # BulkSMS status type, e.g. ACCEPTED


def configured(settings: Settings) -> bool:
    return bool(settings.bulksms_token_id and settings.bulksms_token_secret.get_secret_value())


def allowed_recipients(settings: Settings) -> set[str]:
    """Numbers allowed to receive SMS; empty set means anyone (normal operation)."""
    return {n.strip() for n in settings.comms_allowed_recipients.split(",") if n.strip()}


def send(settings: Settings, message: str, to: str | None = None, group: str | None = None) -> list[Sent]:
    """Send one SMS to a number (E.164) or to every contact in a BulkSMS phonebook group."""
    recipients: str | list[dict] = to if to else [{"type": "GROUP", "name": group}]
    payload = {"to": recipients, "body": message, "longMessageMaxParts": settings.bulksms_max_parts}
    token = f"{settings.bulksms_token_id}:{settings.bulksms_token_secret.get_secret_value()}"
    request = urllib.request.Request(
        f"{settings.bulksms_api_base.rstrip('/')}/messages",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            "Authorization": "Basic " + base64.b64encode(token.encode()).decode(),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            result = json.loads(response.read() or b"[]")
    except urllib.error.HTTPError as exc:
        try:  # errors are RFC 7807 problem documents: {"title": ..., "detail": ...}
            detail = json.loads(exc.read())
            reason = detail.get("detail") or detail.get("title") or exc.reason
        except (ValueError, AttributeError):
            reason = exc.reason
        raise SmsError(f"BulkSMS HTTP {exc.code}: {reason}") from exc
    except urllib.error.URLError as exc:
        raise SmsError(f"BulkSMS unreachable: {exc.reason}") from exc
    messages = result if isinstance(result, list) else [result]
    return [
        Sent(
            to=_e164(str(m.get("to") or to or "")),
            message_id=str(m["id"]) if m.get("id") else None,
            status=(m.get("status") or {}).get("type") or "ACCEPTED",
        )
        for m in messages
    ]


def _e164(number: str) -> str:
    return number if not number or number.startswith("+") else f"+{number}"
