"""Small structured-logger facade; the platform collects the JSON lines."""
import json
from datetime import datetime, timezone

_LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}


def create_logger(service, trace="local-invocation", level="INFO", sink=None):
    emit = sink if sink is not None else (lambda line: print(line, flush=True))
    threshold = _LEVELS.get(str(level).upper(), 20)

    def log(severity, message, **fields):
        if _LEVELS.get(severity, 20) < threshold:
            return
        line = {
            "type": "log",
            "time": datetime.now(timezone.utc).isoformat(),
            "level": severity,
            "service": service,
            "trace_id": trace,
            "message": message,
        }
        line.update(fields)
        emit(json.dumps(line, ensure_ascii=False, sort_keys=True))

    return log
