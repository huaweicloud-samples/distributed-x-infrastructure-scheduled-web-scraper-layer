"""Entry point for the scheduled page snapshot function."""
import hashlib
from datetime import datetime, timezone

from config import load_config
from events import event_kind, target_override, trace_id
from fetcher import fetch
from observability import create_logger
from storage import make_client, put_snapshot, result_key

HANDLER_NAME = "index.handler"


def _digest(text):
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def create_handler(deps=None):
    """Build the handler with injectable collaborators for local verification."""
    deps = deps or {}

    def handler(event, context=None):
        env = deps.get("env")
        cfg = deps.get("config") or load_config(env)
        kind = event_kind(event)
        trace = trace_id(event)
        log = deps.get("logger_factory") or create_logger
        logger = log(cfg.service_name, trace=trace, level=cfg.log_level,
                     sink=deps.get("log_sink"))
        url = target_override(event) or cfg.target_url

        logger("INFO", "invocation started", trigger=kind, target=url)
        try:
            opener = deps.get("fetch")
            body, status = fetch(url, timeout=deps.get("timeout", 10), opener=opener)
        except Exception as exc:  # noqa: BLE001 - surfaced as a structured failure
            logger("ERROR", "fetch failed", error=type(exc).__name__)
            return {
                "statusCode": 502,
                "body": {"ok": False, "error": "fetch_failed", "detail": type(exc).__name__},
                "isBase64Encoded": False,
            }

        now = deps.get("clock") or datetime.now(timezone.utc)
        key = result_key(cfg.result_prefix, url, now=now)
        factory = deps.get("client_factory")
        client = (factory(cfg.region, cfg.obs_endpoint) if factory
                  else make_client(cfg.region, cfg.obs_endpoint, context=context))
        object_status = put_snapshot(client, cfg.obs_bucket, key, body)

        payload = {
            "ok": True,
            "trigger": kind,
            "target": url,
            "http_status": status,
            "bytes": len(body.encode("utf-8", errors="replace")),
            "sha256": _digest(body),
            "bucket": cfg.obs_bucket,
            "key": key,
            "object_status": object_status,
            "trace_id": trace,
        }
        logger("INFO", "snapshot stored", key=key, bytes=payload["bytes"])
        return {"statusCode": 200, "body": payload, "isBase64Encoded": False}

    return handler


# FunctionGraph resolves "index.handler" from this archive.
handler = create_handler()
