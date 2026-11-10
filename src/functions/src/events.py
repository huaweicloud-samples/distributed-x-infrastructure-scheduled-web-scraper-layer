"""Decode the invocation shapes this function accepts."""
import json


def _object_body(event):
    body = event.get("body") if isinstance(event, dict) else None
    if isinstance(body, dict):
        return body
    if isinstance(body, str) and body.strip():
        try:
            decoded = json.loads(body)
        except (ValueError, TypeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def event_kind(event):
    """Return one of TIMER, MANUAL, APIG, UNKNOWN."""
    if not isinstance(event, dict):
        return "UNKNOWN"
    if event.get("trigger_type") == "TIMER" or event.get("source") == "timer":
        return "TIMER"
    if event.get("httpMethod") or event.get("requestContext") or "path" in event:
        return "APIG"
    if event.get("schedule") or event.get("schedule_time") or event.get("type") == "timer":
        return "TIMER"
    return "MANUAL"


def target_override(event):
    """Allow an invocation to override the configured page address."""
    if not isinstance(event, dict):
        return None
    for candidate in (event, _object_body(event)):
        for key in ("target_url", "url", "target"):
            value = candidate.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def trace_id(event):
    """Read a caller supplied trace id, case insensitively, or build a local one."""
    if isinstance(event, dict):
        for key, value in event.items():
            if key.lower() in ("x-trace-id", "trace_id", "traceid"):
                if isinstance(value, str) and value.strip():
                    return value.strip()
        headers = event.get("headers")
        if isinstance(headers, dict):
            for key, value in headers.items():
                if key.lower() == "x-trace-id" and isinstance(value, str) and value.strip():
                    return value.strip()
    return "local-invocation"
