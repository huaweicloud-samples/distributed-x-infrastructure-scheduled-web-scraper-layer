"""Write a snapshot object to the private bucket."""
import hashlib
from datetime import datetime, timezone


def result_key(prefix, url, now=None, suffix="html"):
    """Deterministic, sortable object key: prefix/YYYY/MM/DD/HHMMSS-hash.suffix."""
    stamp = now or datetime.now(timezone.utc)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    clean = (prefix or "snapshots").strip().strip("/")
    return "%s/%s-%s.%s" % (
        clean, stamp.strftime("%Y/%m/%d/%H%M%S"), digest, suffix
    )


def make_client(region, endpoint=None, context=None):
    """Build the bucket client from the temporary credentials of the invocation."""
    from obs import ObsClient  # provided by the FunctionGraph Python runtime

    server = endpoint or "https://obs.%s.myhuaweicloud.com" % region
    values = {}
    for method, label in (("getSecurityAccessKey", "access_key"),
                          ("getSecuritySecretKey", "secret_key"),
                          ("getSecurityToken", "security_token")):
        getter = getattr(context, method, None) if context is not None else None
        values[label] = getter() if callable(getter) else ""
    return ObsClient(
        access_key_id=values["access_key"],
        secret_access_key=values["secret_key"],
        security_token=values["security_token"],
        server=server,
    )


def put_snapshot(client, bucket, key, body, content_type="text/html; charset=utf-8"):
    """Store the body and return the response status."""
    if hasattr(client, "putContent"):
        response = client.putContent(bucket, key, content=body, contentType=content_type)
    else:
        response = client.put_object(bucket, key, body, content_type=content_type)
    return getattr(response, "status", None)
